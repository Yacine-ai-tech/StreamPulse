# StreamPulse — Webhook Router Benchmark

A benchmark of the webhook ingestion and security (HMAC signature) layers. Reproducible:
`python eval/run_webhook_benchmark.py`

## Setup
The benchmark fires 100 concurrent webhook requests simulating the GitHub `issue_comment` payload.
- 90% of requests are properly signed with `topsecret_webhook_key`.
- 10% of requests use an invalid signature to test security rejection.

## Results (N=100)
| Metric | Result |
|--------|--------|
| Valid signatures processed | 90 / 90 (100%) |
| Invalid signatures rejected | 10 / 10 (100%) |
| Webhook Security Accuracy | **100.0%** |
| Throughput | > 100 req/s |

**Headline:** the webhook endpoint successfully authenticates all valid requests and securely rejects tampered/invalid payloads under concurrent load.
