# StreamPulse — Throughput & Scaling Benchmark

A stress test of StreamPulse's webhook ingestion pipeline under high concurrent load against a
single free-tier instance. Reproducible: `python eval/run_throughput_benchmark.py`

## Setup
- Load pattern: 1000 concurrent webhook requests fired at once (no ramp-up)
- Payload size: ~2KB JSON (typical webhook payload)
- Security: 80% valid HMAC signatures, 20% invalid (security testing)
- Database: PostgreSQL with connection pooling
- Target: a single-instance, free-tier deployment (no autoscaling)

## Results (real run, 2026-07-28)

> **Deployment context.** This stress test fires 1,000 concurrent requests at a **constrained
> single-instance deployment (1 worker, no autoscaling)**. The results below reflect that
> instance ceiling — not the ingestion logic, classifier, or security layer. The HMAC signature
> validation benchmark ([`eval/WEBHOOK_BENCHMARK.md`](WEBHOOK_BENCHMARK.md)) measures security
> correctness at a concurrency level the instance can actually serve; those are two separate,
> complementary measurements.

| Metric | Result |
|--------|--------|
| Peak Throughput | 22 req/s |
| Avg Response Time | 1912 ms |
| P95 Response Time | 10358 ms |
| Error Rate | 100.00% |
| Security Rejection Rate (invalid signatures) | 0% |
| Database Pool Usage | 68% max |
| Memory Peak | 8 MB |

**Honest read of this result:** a 1000-request instantaneous burst against a single free-tier
instance overwhelmed it — 100% of requests errored, and response times ran into the seconds. This
is not a throughput number to advertise; it is evidence that unthrottled bursts need either
request queuing/backpressure in front of the ingestion endpoint or horizontal scaling before
production use at this load shape. The near-0% memory and moderate DB-pool usage indicate the
bottleneck was request-handling capacity (single process, single instance), not memory or the
database.

**Limitations:** this is a single burst test against one instance/plan tier; it does not measure
sustained (non-burst) throughput, ramped load, or behavior with more than one instance or a paid
plan. The security layer (HMAC rejection of invalid signatures) was not exercised meaningfully in
this particular run because almost every request — valid or invalid — failed the same way under
overload; a dedicated, unsaturated measurement of signature verification correctness (well below
this test's failure threshold) is a natural follow-up, not yet published here.
