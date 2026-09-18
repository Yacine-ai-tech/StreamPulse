import argparse
import asyncio
import time
import hmac
import hashlib
import json
import random
from pathlib import Path
from typing import Dict
import httpx
import psutil
import os

# Webhook secret for HMAC signing (must be set via environment variable)
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET")
if not WEBHOOK_SECRET:
    raise ValueError("WEBHOOK_SECRET environment variable must be set for HMAC signing")

# Sample webhook payload (GitHub issue_comment style). Its "action"/"title"/"body" text
# carries no domain keyword, so it always escalates through the embedding and LLM tiers —
# real per-record classification cost, not pure ingestion overhead. Used for the burst
# error-rate test, where that realistic cost is the point.
SAMPLE_PAYLOAD = {
    "action": "created",
    "issue": {
        "id": 12345,
        "number": 678,
        "title": "Test issue",
        "user": {"login": "testuser"}
    },
    "comment": {
        "id": 98765,
        "body": "Test comment"
    },
    "repository": {
        "id": 54321,
        "name": "test-repo",
        "full_name": "testuser/test-repo"
    }
}

# Keyword-confident payload — resolves at Tier 1 (fast keyword match, no embedding/LLM
# network calls) via connectors/webhook_receiver.py's text-field derivation. Used for the
# sustained-throughput test, which is meant to measure the ingestion pipeline's own
# capacity (parsing, classification dispatch, batched DB write) independent of how long a
# given record's classification happens to take — that's a separate, already-measured cost
# (see the burst error-rate test above).
FAST_TIER_PAYLOAD = {
    "text": ("Revenue, expense, profit, margin, cash, and ebitda figures were reported "
              "in this quarter's financial statement and budget review."),
}

def generate_signature(payload: str, secret: str) -> str:
    """Generate HMAC signature for webhook payload"""
    return hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()

class ThroughputBenchmark:
    def __init__(self, base_url: str = None, fast_tier: bool = False):
        self.base_url = base_url or os.environ.get("API_BASE_URL", "http://localhost:8000")
        self.fast_tier = fast_tier
        self.results = {
            "total_requests": 0,
            "successful": 0,
            "failed": 0,
            "response_times": [],
            "security_rejections": 0,
            "start_time": 0,
            "end_time": 0,
            "error_samples": [],  # first few distinct failures, for diagnosing a 0%/100% run
        }

    async def send_webhook(self, client: httpx.AsyncClient, valid_signature: bool = True) -> float:
        """Send a single webhook request and return response time"""
        payload_str = json.dumps(FAST_TIER_PAYLOAD if self.fast_tier else SAMPLE_PAYLOAD)
        
        if valid_signature:
            signature = generate_signature(payload_str, WEBHOOK_SECRET)
        else:
            signature = "invalid_signature_test"
        
        headers = {
            "X-Signature-256": f"sha256={signature}",
            "Content-Type": "application/json"
        }
        
        start_time = time.time()
        try:
            # content=payload_str.encode(), NOT json=SAMPLE_PAYLOAD — httpx's json= kwarg
            # re-serializes the dict itself (different byte output than payload_str, e.g.
            # separators), so the server-side HMAC (computed over the actual received
            # bytes) never matched the client-computed signature. Every "valid_signature"
            # request was failing verification and counted as a false failure.
            # 10s was too short for real classification latency under load (measured
            # 6-20s even outside a burst) — this let a slow-but-successful response get
            # counted as a hard failure indistinguishable from a real server error.
            response = await client.post(
                f"{self.base_url}/webhook/test_source",
                content=payload_str.encode(),
                headers=headers,
                timeout=60.0
            )
            response_time = time.time() - start_time
            
            self.results["total_requests"] += 1
            if response.status_code == 200:
                self.results["successful"] += 1
            elif response.status_code == 401:
                # The server (api.py) rejects a bad/missing signature with 401, not 403 —
                # this branch was checking the wrong status code, so every one of the 20%
                # intentionally-invalid-signature requests this test sends (see
                # run_concurrent_test's `valid = random.random() < 0.8`) was counted as an
                # unexpected generic failure instead of the expected security rejection.
                # Not counted in `failed` either — correctly rejecting a bad signature is
                # the security check *passing*, not the system failing under load, and
                # mixing the two into one "error rate" made that metric meaningless.
                self.results["security_rejections"] += 1
            else:
                self.results["failed"] += 1
                if len(self.results["error_samples"]) < 5:
                    self.results["error_samples"].append(f"HTTP {response.status_code}: {response.text[:200]}")

            self.results["response_times"].append(response_time)
            return response_time

        except Exception as e:
            if len(self.results["error_samples"]) < 5:
                self.results["error_samples"].append(f"{type(e).__name__}: {str(e)[:200]}")
            response_time = time.time() - start_time
            self.results["total_requests"] += 1
            self.results["failed"] += 1
            self.results["response_times"].append(response_time)
            return response_time
    
    async def run_concurrent_test(self, n_requests: int = 1000, concurrency: int = 50):
        """Run concurrent webhook load test"""
        print("=== StreamPulse Throughput Benchmark ===")
        print(f"Total requests: {n_requests}, Concurrency: {concurrency}")
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
        async with httpx.AsyncClient(limits=limits) as client:
            self.results["start_time"] = time.time()
            
            # Create batches of concurrent requests
            semaphore = asyncio.Semaphore(concurrency)
            
            async def bounded_request():
                async with semaphore:
                    # 80% valid signatures, 20% invalid for security testing
                    valid = random.random() < 0.8
                    return await self.send_webhook(client, valid)
            
            # Run all requests concurrently
            tasks = [bounded_request() for _ in range(n_requests)]
            await asyncio.gather(*tasks)
            
            self.results["end_time"] = time.time()
        
        # Get final memory usage
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        self.results["memory_peak"] = final_memory - initial_memory
        
        # Calculate metrics
        total_time = self.results["end_time"] - self.results["start_time"]
        throughput = self.results["total_requests"] / total_time if total_time > 0 else 0
        
        response_times = self.results["response_times"]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        sorted_times = sorted(response_times)
        p95_response_time = sorted_times[int(len(sorted_times) * 0.95)] if sorted_times else 0
        
        # error_rate: genuine unexpected failures only (security_rejections are no longer
        # folded into `failed` — see send_webhook). security_rate: what fraction of all
        # requests were the intentional ~20% bad-signature test cases, correctly rejected.
        error_rate = (self.results["failed"] / self.results["total_requests"]) * 100 if self.results["total_requests"] > 0 else 0
        security_rate = (self.results["security_rejections"] / self.results["total_requests"]) * 100 if self.results["total_requests"] > 0 else 0
        
        print("\n=== Results ===")
        print(f"Total requests: {self.results['total_requests']}")
        print(f"Successful: {self.results['successful']}")
        print(f"Failed: {self.results['failed']}")
        print(f"Security rejections: {self.results['security_rejections']}")
        print(f"Total time: {total_time:.2f}s")
        print(f"Peak throughput: {throughput:.1f} req/s")
        print(f"Avg response time: {avg_response_time*1000:.1f}ms")
        print(f"P95 response time: {p95_response_time*1000:.1f}ms")
        print(f"Error rate: {error_rate:.2f}%")
        print(f"Security rejection rate: {security_rate:.1f}%")
        print(f"Memory peak: {self.results['memory_peak']:.1f}MB")
        if self.results["error_samples"]:
            print("Error samples:")
            for e in self.results["error_samples"]:
                print(f"  - {e}")

        return {
            "throughput": throughput,
            "avg_response_time": avg_response_time * 1000,  # convert to ms
            "p95_response_time": p95_response_time * 1000,
            "error_rate": error_rate,
            "security_rate": security_rate,
            "memory_peak": self.results["memory_peak"]
        }

def update_benchmark_markdown(results: Dict, n_requests: int, concurrency: int):
    """Update the benchmark markdown with new results. Status is a real comparison against
    each target, not a hardcoded label — a prior version of this function marked every row
    "Passed" unconditionally (e.g. a 29144ms avg response time against a <100ms target),
    and its "Analysis"/"Scaling Behavior" text was hand-written fiction unconnected to
    anything actually measured (a fabricated "68% max" DB pool figure the code never
    computes, claims about throughput at 600-800 req/s this test never ran at)."""
    md_path = Path(__file__).resolve().parent / "THROUGHPUT_BENCHMARK.md"
    from datetime import date

    def status(ok: bool) -> str:
        return "✅ Passed" if ok else "❌ Failed"

    error_ok = results["error_rate"] < 1.0
    throughput_ok = results["throughput"] > 500
    avg_ok = results["avg_response_time"] < 100
    p95_ok = results["p95_response_time"] < 200
    mem_ok = results["memory_peak"] < 500

    content = f"""# StreamPulse — Throughput & Scaling Benchmark

A stress test of StreamPulse's webhook ingestion pipeline under concurrent load. Reproducible:
`python eval/run_throughput_benchmark.py --target <url> --n-requests {n_requests} --concurrency {concurrency}`

## Setup
- Load pattern: {n_requests} webhook requests at concurrency={concurrency}
- Payload size: ~2KB JSON (typical webhook payload)
- Security: 80% valid HMAC signatures, 20% invalid (security testing — see error_rate note below)
- Metrics: Requests/second, error rate, response latency, memory usage

## Results (real run, {date.today().isoformat()})

| Metric | Result | Target | Status |
|--------|--------|--------|--------|
| **Peak Throughput** | **{results['throughput']:.1f} req/s** | > 500 req/s | {status(throughput_ok)} |
| **Avg Response Time** | **{results['avg_response_time']:.0f}ms** | < 100ms | {status(avg_ok)} |
| **P95 Response Time** | **{results['p95_response_time']:.0f}ms** | < 200ms | {status(p95_ok)} |
| **Error Rate** | **{results['error_rate']:.2f}%** | < 1% | {status(error_ok)} |
| **Security Rejection Rate** | **{results['security_rate']:.1f}%** (intentional invalid sigs, ~20% by design) | — | — |
| **Memory Peak** | **{results['memory_peak']:.1f}MB** | < 500MB | {status(mem_ok)} |

**Analysis:**
- error_rate ({results['error_rate']:.2f}%) counts only genuine unexpected failures — the ~20%
  intentional bad-signature requests are tallied separately as security_rejection_rate, since a
  correctly-rejected bad signature is the security check passing, not the system failing.
- Response latency at this concurrency ({concurrency}) reflects real per-request classification
  work (embedding + LLM-tier escalation on the ingested payload), not raw HTTP/DB overhead — a
  concurrency-{concurrency} target well above what this deployment sustains at low latency will
  show slow-but-successful responses like this run's {results['avg_response_time']:.0f}ms average,
  not necessarily errors.
- No database-connection-pool metric is collected by this script; a prior version of this
  document reported a fabricated "68% max" figure that was never actually measured.
"""

    with open(md_path, "w") as f:
        f.write(content)

    print(f"\nBenchmark results written to {md_path}")

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default=os.environ.get("API_BASE_URL", "http://localhost:8000"),
                     help="Base URL of the StreamPulse instance to load-test")
    ap.add_argument("--n-requests", type=int, default=1000)
    ap.add_argument("--concurrency", type=int, default=500,
                     help="Concurrent in-flight requests during the burst")
    ap.add_argument("--fast-tier", action="store_true",
                     help="Use a keyword-confident payload that resolves at Tier 1 (no "
                          "embedding/LLM network calls) — measures the ingestion pipeline's "
                          "own sustained capacity, independent of per-record classification "
                          "cost (which the default payload deliberately exercises instead).")
    args = ap.parse_args()
    base_url = args.target

    # Check if server is running
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/health", timeout=5.0)
            if response.status_code != 200:
                print("Warning: Server health check failed, continuing anyway...")
    except Exception as e:
        print(f"Warning: Could not connect to server at {base_url}: {e}")
        print("Make sure StreamPulse is running before benchmarking")
        return

    benchmark = ThroughputBenchmark(base_url=base_url, fast_tier=args.fast_tier)
    results = await benchmark.run_concurrent_test(n_requests=args.n_requests, concurrency=args.concurrency)
    if args.fast_tier:
        print("\n(--fast-tier run: results reflect ingestion capacity, not written to "
              "THROUGHPUT_BENCHMARK.md automatically — see BENCHMARK.md's sustained-"
              "throughput section for how this number is reported.)")
    else:
        update_benchmark_markdown(results, args.n_requests, args.concurrency)

if __name__ == "__main__":
    asyncio.run(main())