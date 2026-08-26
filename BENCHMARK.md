# Benchmark Results

This document provides a headline summary of StreamPulse's measured classifier accuracy,
throughput, and webhook security. Full methodology and per-run details are in the `eval/`
directory — this file is the entry point.

> **Infrastructure note.** Throughput results were measured against a **single free-tier
> instance with no autoscaling**. Results under extreme burst load reflect that single-process
> ceiling, not the classifier or pipeline logic. See the throughput section below.

---

## 1. Domain Classifier Accuracy

Measured on a curated, balanced 48-example set deliberately paraphrased to avoid literal
domain keywords — designed to stress-test the vector-embedding and LLM tiers, not keyword
matching. Full details: [`eval/CLASSIFIER_BENCHMARK.md`](eval/CLASSIFIER_BENCHMARK.md)

Reproducible:
```bash
python eval/run_classifier_benchmark.py                          # keyword + embedding tiers
STREAMPULSE_HYBRID_LLM=1 python eval/run_classifier_benchmark.py  # full hybrid with LLM
```

| Tier | Accuracy | Macro-F1 |
|---|---|---|
| Keyword only (Tier 1) | 8.3% | 0.105 |
| Keyword → Vector Embedding (Tier 2) | 64.6% | 0.549 |
| **Full Cascade — Keyword → Embedding → LLM (Tier 3)** | **91.7%** | **0.793** |

**Headline:** on realistic keyword-poor text, keyword matching collapses (8%); the
vector-embedding tier recovers most of the gap on its own, and the LLM tier resolves
nearly all of the rest. This is the empirical justification for the hybrid cascade design.

**Honest caveats:**
- Real streams are a *mix* of keyword-rich and keyword-poor text — keyword alone would
  score far above 8% in production.
- 91.7% on 48 examples means "strongly separable on a small clean set," not a
  statistically significant production guarantee. N > 1,000 is listed as future work.
- The embedding tier calls a remote inference host over HTTP and is built to poll through
  a cold start rather than fail on one, so its measured contribution reflects genuine
  classification quality, not host latency.

---

## 2. Throughput Under Burst Load

Load-tested with 1,000 concurrent webhook requests fired at once (no ramp-up) against a
**single free-tier instance**. Full details: [`eval/THROUGHPUT_BENCHMARK.md`](eval/THROUGHPUT_BENCHMARK.md)

Reproducible: `python eval/run_throughput_benchmark.py`

| Metric | Result |
|---|---|
| Peak Throughput | 22 req/s |
| Avg Response Time | 1,912 ms |
| P95 Response Time | 10,358 ms |
| Error Rate | 100% |
| Memory Peak | 8 MB |
| Database Pool Usage | 68% max |

**How to read this:** a 1,000-request instantaneous burst overwhelmed a single free-tier
process — 100% of requests errored. Near-zero memory and moderate DB-pool usage confirm
the bottleneck was **request-handling capacity (single process, no autoscaling)**, not
memory or the database. This is not a production throughput figure; it establishes that
unthrottled bursts at this scale require either request queuing/backpressure or
horizontal scaling. Sustained (non-burst) throughput and multi-instance behavior are
listed as natural follow-up measurements.

---

## 3. Webhook Security (HMAC Signature Validation)

Measured at a manageable, non-overloaded concurrency (N=100). Full details:
[`eval/WEBHOOK_BENCHMARK.md`](eval/WEBHOOK_BENCHMARK.md)

Reproducible: `python eval/run_webhook_benchmark.py`

| Metric | Result |
|---|---|
| Valid signatures processed | 90 / 90 — **100%** |
| Invalid signatures rejected | 10 / 10 — **100%** |
| Webhook Security Accuracy | **100.0%** |
| Throughput | > 100 req/s |

**Note:** HMAC security correctness was measured at a concurrency level where the instance
could actually process requests. Under the 1,000-request burst in §2, the instance was
saturated before the security layer ran — so the throughput test could not measure security
behavior independently. These are two separate, complementary measurements.

---

## Further Reading

- [`eval/CLASSIFIER_BENCHMARK.md`](eval/CLASSIFIER_BENCHMARK.md) — classifier methodology and caveats
- [`eval/THROUGHPUT_BENCHMARK.md`](eval/THROUGHPUT_BENCHMARK.md) — throughput stress test details
- [`eval/WEBHOOK_BENCHMARK.md`](eval/WEBHOOK_BENCHMARK.md) — HMAC security validation details
- [`RESEARCH.md`](RESEARCH.md) — literature context, cascade design rationale, and honest assessment of novelty
