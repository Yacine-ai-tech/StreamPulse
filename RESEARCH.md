# StreamPulse: Hybrid LLM Cascade for Real-Time Event Classification

## Abstract
This work represents a working prototype demonstrating a multi-stage, hybrid classification pipeline within an event-streaming architecture. StreamPulse integrates traditional keyword heuristics, local vector embeddings, and zero-shot Large Language Models (LLMs) into a latency- and cost-optimized routing cascade. While built on standard engineering practices for data ingestion, its primary contribution is the empirical demonstration of a "language model cascade" (Dohan et al., 2022) applied to domain classification of real-time business metrics.

## 1. Literature Context

### 1.1 Multi-Source Event Streaming
Modern stream processing architectures, such as those formalized by the Dataflow Model (Akidau et al., 2015) and implemented in Apache Flink (Carbone et al., 2015) or Apache Kafka (Kreps et al., 2011), focus on distributed, exactly-once, and out-of-order event processing. StreamPulse builds on these principles (using Redis/Kafka for pub/sub) but focuses primarily on the semantic routing of records rather than complex sliding window aggregations (e.g., Abadi et al., 2003).

### 1.2 Hybrid Text Classification & Cascades
To balance cost, latency, and accuracy, recent literature explores model cascades (Dohan et al., 2022), where lightweight models handle easy queries and expensive LLMs process difficult ones. StreamPulse implements a three-tier cascade:
1. **Keyword/TF-IDF baseline** (Manning et al., 2008)
2. **Dense retrieval via embeddings** (Karpukhin et al., 2020)
3. **LLM zero-shot classification** (Brown et al., 2020)

### 1.3 LLM-as-a-Judge Evaluation
In modern AI system development, using capable LLMs as judges has become a standard for evaluation (Zheng et al., 2023; Dubois et al., 2024). StreamPulse utilizes similar zero-shot evaluation techniques to assess the viability of its routing logic and to handle fallback classification when earlier tiers lack confidence.

## 2. Implementation Overview

StreamPulse implements a practical, production-ready version of the cascade paradigm. The core of this logic resides in `pipeline/classifier.py`.

### 2.1 The Classification Cascade
1. **Tier 1 (Keyword):** A high-speed heuristic check for domain-specific vocabulary (e.g., "revenue" -> Finance). If the confidence exceeds `CLASSIFIER_KEYWORD_THRESHOLD` (e.g., 0.7), the pipeline returns immediately.
2. **Tier 2 (Vector Embedding):** If keywords fail, the text is embedded using a local model (e.g., BAAI/bge-m3) and compared against domain prototypes using cosine similarity. If the score exceeds `CLASSIFIER_EMBEDDING_THRESHOLD`, the label is assigned. The taxonomy itself is not hardcoded: both the keyword and embedding tiers read their domains from a configurable "domain pack" (a JSON file of domain names to prototype phrasings), making the classifier applicable to any domain taxonomy, not just the business-function set used for evaluation here.
3. **Tier 3 (LLM Escalation):** As a last resort, the record is sent to a high-capability LLM (e.g., Claude Haiku or Gemini) for zero-shot classification.

### 2.2 Content Hash Caching
To further optimize costs, classification results are cached in-memory and persistently via `pgvector` using a SHA-256 hash of the content.

## 3. Empirical Results

Original benchmarks (2026-08-20) were executed against a single free-tier deployment with a
remote embedding host reached over HTTP. Section 3.1's N=500 row and Section 3.2 were
remeasured (2026-09-18) on a sovereign Contabo VPS after two fixes: in-process embedding
(`INFERENCE_MODE=local`, `BAAI/bge-m3`) instead of a remote host, and a blocking-I/O bug in
the ingestion endpoint (see §3.2).

### 3.1 Classifier Accuracy
The classifier was tested on deliberately challenging, keyword-poor text to measure the impact
of the vector-embedding and LLM escalation tiers, using the bundled reference domain pack (see
Section 2.1).

| Tier | N=48 (curated, 2026-08-20) | N=500 (synthetic, 2026-09-18) |
|---|---|---|
| Keyword Only (Tier 1) | 8.3% acc, 0.105 F1 | — |
| Tier 1 + Vector (Tier 2) | 64.6% acc, 0.549 F1 | — |
| **Full Cascade (Tier 3)** | 91.7% acc, 0.793 F1 | **97.6% acc, 0.976 F1** |

The N=500 set is generated (`eval/generate_classifier_dataset.py`, deterministic, seed=42) via
template + slot-filling combinatorics — subject × direction × magnitude × phrasing, varied
independently and deduplicated — across the same 6 domains, not hand-written one at a time.
Per-domain F1: ESG 1.00, IT_Ops 1.00, Operations 1.00, People 0.98, Finance 0.95, Growth 0.92.
Growth is the measurably weakest domain, consistent with its vocabulary overlapping Finance's
(both domains' generated text surfaces revenue/customer-acquisition-cost figures).

*Note: Tier 2's confidence threshold is deliberately calibrated toward precision over recall —
it only commits to a label when confident, deferring ambiguous cases to Tier 3 rather than risk
a confident wrong answer. In real-world streams containing a mix of keyword-rich and
keyword-poor text, Tier 1's standalone accuracy would be significantly higher than the 8.3%
measured on this deliberately keyword-poor set. The N=500 set is synthetic — a template
generator, not captured production traffic — so it measures separability across a wide,
deliberately-varied phrasing space rather than true field accuracy; it is a materially larger
and more diverse sample than N=48, not a claim of having captured real-world traffic patterns.*

### 3.2 Throughput Performance
The ingestion pipeline was load-tested with 1,000 concurrent webhook requests (concurrency=50)
against the current VPS deployment.

| Metric | Historical (free-tier, 2026-08-20) | Current (VPS, 2026-09-18) |
|---|---|---|
| Peak Throughput | 22 req/s | 1.7 req/s |
| Average Response Time | 1,912 ms (P95: 10,358 ms) | 29,144 ms (P95: 42,627 ms) |
| Error Rate | 100% | **0.00%** |

*The historical 100% error rate was a genuine defect, not a load-shape artifact: the ingestion
endpoint called blocking, synchronous database I/O directly from an async request handler
(no `asyncio.to_thread`), and inserted classified records one row at a time instead of batched
— a concurrent burst serialized entirely behind that blocking call, and every request timed
out waiting its turn. Fixed on both counts (`store.py`, `api.py`): all records in a batch land
in one multi-row `INSERT`, and every database call runs off the event loop. The result is
0.00% genuine error rate — everything the pipeline should accept, it now does. The
throughput/latency figures moved the other direction, and that is reported honestly rather
than hidden: they now reflect real per-request classification work (the embedding and
LLM-escalation tiers actually executing per ingested payload) on a 6-vCPU host shared with
five other deployed services, not a lightweight HTTP+DB round-trip — a slower number for a
genuinely more expensive request, not a regression in correctness.

An ingestion-isolated follow-up (`--fast-tier`, resolves at Tier 1, no embedding/LLM call
per request) was then used to pursue a documented sustained-throughput target of ≥480 req/s.
Two further root causes were found and fixed in sequence, each verified independently:
Python's default `asyncio.to_thread()` executor is sized by CPU count
(`min(32, os.cpu_count()+4)`, 10 threads on this 6-vCPU host) rather than by request
concurrency, and every database call was opening a fresh connection (a real TCP+TLS
handshake to the remote Postgres host) instead of reusing a pool. Resizing the executor
took throughput from 1.7 to 8.0 req/s; pooling connections (`psycopg_pool.ConnectionPool`)
took it to 9.2 req/s, with average response time falling from 28.7s to 5.1s and the error
rate holding at 0.00% throughout. The 480 req/s target was not reached: at the test's
concurrency=50 and 5.1s average latency, `50 / 5.1 ≈ 9.8 req/s` is the arithmetic ceiling of
this configuration, matching the measured 9.2 req/s. Closing the remaining gap requires
horizontal scaling (multiple worker processes or instances) rather than a further
single-process code fix; see §5.*

## 4. Honest Assessment & Limitations

**Novelty:** StreamPulse does not invent new stream processing paradigms or embedding models. Instead, it successfully applies the Language Model Cascade framework (Dohan et al., 2022) to a practical webhook ingestion server. It bridges the gap between standard data engineering (FastAPI, Postgres, Kafka) and applied AI.

**Limitations:**
1.  **Stateful Processing:** Unlike Aurora (Abadi et al., 2003) or StatStream (Zhu & Shasha, 2002), StreamPulse currently performs stateless, per-record classification. It lacks complex sliding-window analytics natively, although it exports to DuckDB for retrospective analysis.
2.  **Dataset Composition:** The N=500 full-cascade result (97.6% acc / 0.976 F1) is a materially larger and more diverse sample than the original N=48, but it is synthetically generated (template + slot-filling), not captured production traffic — a genuine step up in statistical breadth, not yet a claim of measured real-world field accuracy.
3.  **Single-Process Throughput Ceiling:** The ingestion-isolated sustained-throughput measurement in §3.2 (9.2 req/s) is bound by a single-worker, single-process FastAPI deployment on shared 6-vCPU hardware — it is an honest measurement of that specific deployment shape, not a ceiling on the architecture itself. A documented target of ≥480 req/s was not reached and, per the arithmetic in §3.2, cannot be reached without horizontal scaling.

## 5. Future Directions

Future research and development will focus on:
1.  **Adaptive Thresholding:** Dynamically adjusting the confidence thresholds between tiers based on system load or a predefined cost budget.
2.  **Stateful Streaming Context:** Incorporating sliding windows (e.g., analyzing the last 10 minutes of logs) to provide temporal context to the LLM classifier, improving accuracy on highly ambiguous single-line logs.
3.  **Real-Traffic Evaluation:** §3.1's N=500 set is synthetic; the next step is a captured-production-traffic sample (or LLM-as-a-judge labeling of real payloads, Zheng et al., 2023) to validate the 97.6% figure against actual field text rather than generated phrasing.
4.  **Horizontal Scaling for Sustained Throughput:** §3.2 isolated and fixed two real single-process bottlenecks (executor sizing, connection pooling), raising ingestion-only throughput from 1.7 to 9.2 req/s, but closing the remaining gap to a ≥480 req/s target requires running multiple worker processes or instances behind a load balancer rather than further single-process tuning.

## References
*   Akidau, T., et al. (2015). "The Dataflow Model: A Practical Approach to Balancing Correctness, Latency, and Cost in Massive-Scale, Unbounded, Out-of-Order Data Processing." *VLDB*.
*   Abadi, D. J., et al. (2003). "Aurora: a new model and architecture for data stream management." *VLDB Journal*.
*   Brown, T., et al. (2020). "Language Models are Few-Shot Learners." *NeurIPS*.
*   Carbone, P., et al. (2015). "Apache Flink: Stream and Batch Processing in a Single Engine." *Data Engineering Bulletin*.
*   Dohan, D., et al. (2022). "Language Model Cascades." *arXiv preprint arXiv:2207.10342*.
*   Dubois, Y., et al. (2024). "AlpacaEval 2.0: Fast and Reliable Automatic Evaluation of LLMs."
*   Karpukhin, V., et al. (2020). "Dense Passage Retrieval for Open-Domain Question Answering." *EMNLP*.
*   Kreps, J., et al. (2011). "Kafka: a Distributed Messaging System for Log Processing." *NetDB*.
*   Manning, C. D., et al. (2008). *Introduction to Information Retrieval*. Cambridge University Press.
*   Zheng, L., et al. (2023). "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena." *NeurIPS*.
*   Zhu, Y., & Shasha, D. (2002). "StatStream: Statistical Monitoring of Thousands of Data Streams in Real Time." *VLDB*.
