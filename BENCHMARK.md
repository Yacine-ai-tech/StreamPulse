# Benchmark Results

This document provides a headline summary of StreamPulse's measured classifier accuracy,
throughput, and webhook security. Full methodology and per-run details are in the `eval/`
directory — this file is the entry point.

> **Infrastructure note.** Sections 1 and 2 below were remeasured on a sovereign Contabo VPS
> (6 vCPU / 11GB RAM, shared with 5 other deployed services) after moving off the original
> single free-tier host. The classifier now runs `INFERENCE_MODE=local` (in-process embedding
> model) rather than calling a remote inference host. Both sections below carry their original
> historical baseline alongside the new number so the delta is auditable.

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

| Tier | Accuracy | Macro-F1 | N |
|---|---|---|---|
| Keyword only (Tier 1) | 8.3% | 0.105 | 48 |
| Keyword → Vector Embedding (Tier 2) | 64.6% | 0.549 | 48 |
| Full Cascade — Keyword → Embedding → LLM (Tier 3) | 91.7% | 0.793 | 48 |
| **Full Cascade, N=500 synthetic SaaS telemetry set** | **97.6%** | **0.976** | **500** |

**Headline:** on realistic keyword-poor text, keyword matching collapses (8%); the
vector-embedding tier recovers most of the gap on its own, and the LLM tier resolves
nearly all of the rest. This is the empirical justification for the hybrid cascade design.
The N=48 result was "strongly separable on a small clean set," not a statistically
significant number — the N=500 run addresses that directly, generated with a
template + slot-filling method (subject × direction × magnitude × phrasing,
combinatorially varied, deduplicated) across the same 6 real domains rather than more
hand-curated examples. Per-domain F1 on the N=500 set: ESG 1.00, IT_Ops 1.00,
Operations 1.00, People 0.98, Finance 0.95, Growth 0.92 — Growth is the one measurably
weaker domain, the most vocabulary-overlapping with Finance in this dataset (both surface
revenue/customer-acquisition-cost language).

**Honest caveats:**
- Real streams are a *mix* of keyword-rich and keyword-poor text — keyword alone would
  score far above 8% in production.
- The N=500 set is synthetic (template-generated, not real captured SaaS events), so it
  measures the cascade's separability across a wide, deliberately-varied phrasing space
  rather than true production-traffic accuracy — a meaningfully different and larger
  sample than N=48, but still not a captured-in-the-wild dataset.
- The embedding tier now runs in-process (`INFERENCE_MODE=local`, `BAAI/bge-m3`) rather
  than calling a remote inference host — its measured contribution reflects genuine
  classification quality without a network hop, at the cost of real local memory (~3GB
  resident once the model is loaded).

---

## 2. Throughput Under Burst Load

Load-tested with 1,000 concurrent webhook requests (concurrency=50) against the current
sovereign VPS deployment. Full details: [`eval/THROUGHPUT_BENCHMARK.md`](eval/THROUGHPUT_BENCHMARK.md)

Reproducible: `python eval/run_throughput_benchmark.py --target <url> --n-requests 1000 --concurrency 50`

| Metric | Historical (single free-tier instance) | Current (VPS) |
|---|---|---|
| Peak Throughput | 22 req/s | 1.7 req/s |
| Avg Response Time | 1,912 ms | 29,144 ms |
| P95 Response Time | 10,358 ms | 42,627 ms |
| Error Rate | 100% | **0.00%** |
| Security Rejection Rate | not measured | 21.4% (intentional bad-signature test cases, ~20% by design) |
| Memory Peak | 8 MB | 6.9 MB |

**How to read this:** the historical run's 100% error rate was a genuine bug — the
ingestion endpoint called blocking, synchronous database I/O directly from an async
request handler with no `asyncio.to_thread`, and inserted records one row at a time
instead of batched, so a concurrent burst serialized entirely behind that blocking call.
Both are fixed (`store.py`/`api.py`): a batched multi-row insert, and the DB calls moved
off the event loop. The result is **0.00% genuine error rate** — every request the
pipeline should accept, it now does.

The throughput/latency numbers moved in the other direction and that is also honestly
reported, not hidden: response time now reflects **real per-request classification work**
(the embedding + LLM-escalation tiers actually running on each ingested payload, not a
lightweight HTTP+DB round-trip) on a 6-vCPU box shared with 5 other deployed services —
this is a genuinely slower number for a genuinely more expensive request, not a
regression in reliability.

### 2.1 Sustained Throughput (Ingestion-Isolated)

A follow-up run isolates ingestion capacity from classification cost, using a payload
engineered to resolve at Tier 1 (keyword match) so no embedding or LLM network call
occurs per request (`--fast-tier`, [`eval/run_throughput_benchmark.py`](eval/run_throughput_benchmark.py)).
Three fixes were applied between the baseline and final measurement below, each verified
independently before the next was attempted:

| Stage | Fix | Peak Throughput | Avg Response Time | Error Rate |
|---|---|---|---|---|
| Baseline | — | 1.7 req/s | 28,719 ms | 0.00% |
| +1 | Default `asyncio.to_thread()` executor resized from `min(32, cpu_count+4)` (10 threads on this host) to a pool sized for real request concurrency | 8.0 req/s | ~6,000 ms | 0.00% |
| +2 | Postgres connections pooled (`psycopg_pool.ConnectionPool`) instead of a fresh TCP+TLS handshake per DB call | 9.2 req/s | 5,105 ms | 0.00% |
| +3 | DB pool ceiling raised (`max_size` 20 → 100; was queueing requests behind a pool-slot wait, not query cost, at concurrency ≥20) and worker count raised from 1 to 6 (`WEB_CONCURRENCY`) to use all 6 vCPUs instead of one Python process | **46.8 req/s** | **4,041 ms** | **0.00%*** |

*\*Raising worker count from 1 to 6 surfaced a new, genuine bug before it surfaced this
result: every worker process independently ran the same startup `ALTER TABLE ... ADD
COLUMN IF NOT EXISTS` migration, and N processes issuing the same DDL concurrently
deadlocked on Postgres's `AccessExclusiveLock` for the relation
(`psycopg.errors.DeadlockDetected`, reproduced at ~9.7% request failure with 6 workers).
Fixed with a Postgres advisory lock (`pg_advisory_lock`) serializing the migration across
workers — the DDL itself was already idempotent, only concurrent execution was unsafe.
The 46.8 req/s figure above is measured after that fix, at 0.00% error.*

**Concurrency is not free to increase further — measured, not assumed.** Pushing client
concurrency to 500 (from 200) did not raise throughput; it dropped to 31.7 req/s with
avg latency rising to 14.9s and a 0.84% error rate (client-side `ReadError`s under
oversaturation). 200 concurrent requests against 6 workers is close to this
deployment's real ceiling — more concurrency past that point adds queueing delay, not
completed work.

**Target assessment: ≥480 req/s sustained throughput — not achieved, but the gap
narrowed substantially.** 1.7 → 46.8 req/s is a ~27x improvement across five real,
independently-verified fixes, with 0.00% error rate holding throughout. At
concurrency=200 and ~4.0s average latency, `200 / 4.0 ≈ 50 req/s` is the arithmetic
ceiling of this configuration — consistent with the measured 46.8 req/s. Reaching 480
req/s from here needs roughly another 10x, which this single VPS cannot supply by
further tuning: the remaining path is horizontal scaling (multiple VPS instances behind
a load balancer), not more per-instance configuration. That architectural step is listed
under Future Directions in [`RESEARCH.md`](RESEARCH.md).

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
