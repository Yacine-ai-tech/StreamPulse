# StreamPulse — Throughput & Scaling Benchmark

A stress test of StreamPulse's webhook ingestion pipeline under concurrent load. Reproducible:
`python eval/run_throughput_benchmark.py --target <url> --n-requests 1000 --concurrency 50`

## Setup
- Load pattern: 1000 webhook requests at concurrency=50
- Payload size: ~2KB JSON (typical webhook payload)
- Security: 80% valid HMAC signatures, 20% invalid (security testing — see error_rate note below)
- Metrics: Requests/second, error rate, response latency, memory usage

## Results (real run, 2026-09-18)

| Metric | Result | Target | Status |
|--------|--------|--------|--------|
| **Peak Throughput** | **1.7 req/s** | > 500 req/s | ❌ Failed |
| **Avg Response Time** | **29144ms** | < 100ms | ❌ Failed |
| **P95 Response Time** | **42627ms** | < 200ms | ❌ Failed |
| **Error Rate** | **0.00%** | < 1% | ✅ Passed |
| **Security Rejection Rate** | **21.4%** (intentional invalid sigs, ~20% by design) | — | — |
| **Memory Peak** | **6.9MB** | < 500MB | ✅ Passed |

**Analysis:**
- error_rate (0.00%) counts only genuine unexpected failures — the ~20%
  intentional bad-signature requests are tallied separately as security_rejection_rate, since a
  correctly-rejected bad signature is the security check passing, not the system failing.
- Response latency at this concurrency (50) reflects real per-request classification
  work (embedding + LLM-tier escalation on the ingested payload), not raw HTTP/DB overhead — a
  concurrency-50 target well above what this deployment sustains at low latency will
  show slow-but-successful responses like this run's 29144ms average,
  not necessarily errors.
- No database-connection-pool metric is collected by this script; a prior version of this
  document reported a fabricated "68% max" figure that was never actually measured.
