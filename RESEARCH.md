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

Benchmarks were executed against the classifier's real production configuration (2026-08-20):
remote BAAI/bge-m3 embeddings over HTTP, and an LLM-tier model reached via LiteLLM.

### 3.1 Classifier Accuracy (N=48 Curated Set)
The classifier was tested on a deliberately challenging, keyword-poor dataset to measure the impact of the vector-embedding and LLM escalation tiers, using the bundled reference domain pack (see Section 2.1).
*   **Keyword Only (Tier 1):** 8.3% Accuracy, 0.105 Macro-F1
*   **Tier 1 + Vector (Tier 2):** 64.6% Accuracy, 0.549 Macro-F1
*   **Full Cascade (Tier 3):** 91.7% Accuracy, 0.793 Macro-F1

*Note: This evaluation is on a small (N=48) curated set. In real-world streams containing a mix of keyword-rich and keyword-poor text, the baseline performance of Tier 1 would be significantly higher. Tier 2's confidence threshold is deliberately calibrated toward precision over recall — it only commits to a label when confident, deferring ambiguous cases to Tier 3 rather than risk a confident wrong answer, which is why most of the gap between the Tier-2 and full-cascade rows closes rather than compounds. A 91.7% full-cascade score on 48 curated examples demonstrates strong separability on a small clean set, not a statistically significant guarantee at production scale.*

### 3.2 Throughput Performance
The ingestion pipeline was load-tested with 1,000 concurrent webhook requests fired at once (no ramp-up) against a single-instance, free-tier deployment.
*   **Peak Throughput:** 22 req/s
*   **Average Response Time:** 1,912 ms (P95: 10,358 ms)
*   **Error Rate:** 100% under this specific load shape

*This instantaneous burst overwhelmed a single free-tier instance -- every request errored and response times ran into the seconds. Near-zero memory usage and moderate database-pool usage during the test indicate the bottleneck was request-handling capacity (a single process, single instance), not memory or the database. This is not a number to read as production throughput; it demonstrates that unthrottled bursts at this scale need either request queuing/backpressure or horizontal scaling before this load shape is production-safe. Full setup and a dedicated, unsaturated measurement of signature-verification correctness (not exercised meaningfully by this overloaded run) are in the benchmark suite (`eval/THROUGHPUT_BENCHMARK.md`).*

## 4. Honest Assessment & Limitations

**Novelty:** StreamPulse does not invent new stream processing paradigms or embedding models. Instead, it successfully applies the Language Model Cascade framework (Dohan et al., 2022) to a practical webhook ingestion server. It bridges the gap between standard data engineering (FastAPI, Postgres, Kafka) and applied AI.

**Limitations:**
1.  **Stateful Processing:** Unlike Aurora (Abadi et al., 2003) or StatStream (Zhu & Shasha, 2002), StreamPulse currently performs stateless, per-record classification. It lacks complex sliding-window analytics natively, although it exports to DuckDB for retrospective analysis.
2.  **Dataset Size:** The full-cascade accuracy claim is derived from a small N=48 test set. It proves the cascade *can* work on difficult texts but is not a statistically significant guarantee of production accuracy across all domains.

## 5. Future Directions

Future research and development will focus on:
1.  **Adaptive Thresholding:** Dynamically adjusting the confidence thresholds between tiers based on system load or a predefined cost budget.
2.  **Stateful Streaming Context:** Incorporating sliding windows (e.g., analyzing the last 10 minutes of logs) to provide temporal context to the LLM classifier, improving accuracy on highly ambiguous single-line logs.
3.  **Expanded Evaluation:** Creating a larger, more comprehensive evaluation dataset (N>1000) using LLM-as-a-judge techniques (Zheng et al., 2023) to continuously benchmark the classifier across a wider variety of realistic SaaS payloads.

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
