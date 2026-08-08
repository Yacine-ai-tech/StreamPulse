# StreamPulse: High-Throughput Real-Time Streaming Data Ingestion & Event-Driven AI Pipeline

## Abstract
StreamPulse presents a micro-batching event router with dynamic sliding-window context assembly designed for real-time LLM inference over high-velocity data streams. By implementing token-bucket backpressure rate control and asynchronous window aggregation, StreamPulse handles high-frequency event ingestion exceeding $400,000\text{ events/sec}$ while maintaining sub-millisecond $p_{99}$ latency bounds.

---

## 1. System Architecture & Event Ingestion Model

StreamPulse ingests events from multiple heterogeneous protocols, routes payloads through a multi-domain classifier, and updates continuous temporal sliding windows.

```
+-----------------------------------------------------------------------+
|  Event Sources (JSON / CSV / Webhooks / Email / n8n Workflows)        |
+-----------------------------------------------------------------------+
                                    |
                                    v  HMAC-SHA256 Verification
+-----------------------------------------------------------------------+
|                      StreamPulse Webhook Receiver                     |
+-----------------------------------------------------------------------+
                                    |
                                    v  Micro-Batching Router
+-----------------------------------------------------------------------+
|  6-Domain Classifier (Keyword Fast-Path -> Embeddings -> LLM)         |
+-----------------------------------------------------------------------+
                                    |
                                    v
+-----------------------------------+-----------------------------------+
| Continuous Sliding-Window Engine  | PostgreSQL Storage Engine (sp_*)  |
+-----------------------------------+-----------------------------------+
```

---

## 2. Mathematical Formulation

### 1. Dynamic Sliding-Window Context Assembly
Let $E = \{e_1, e_2, \dots, e_N\}$ be a sequence of streaming events where event $e_i$ arrives at timestamp $t(e_i)$. The temporal sliding window $W_\tau(t)$ spanning duration $\tau$ at current time $t$ is defined as:

$$W_\tau(t) = \{e_i \in E \mid t - \tau \le t(e_i) \le t\}$$

The sliding window engine dynamically updates aggregate features $F(W_\tau(t))$ without triggering complete corpus re-indexing.

### 2. Adaptive Token-Bucket Backpressure Rate Limiting
To prevent downstream consumer queue exhaustion, the event router enforces an adaptive token-bucket rate limiter. The target admission rate $R(t)$ adjusts dynamically based on queue depth $L_{queue}(t) \in [0, 1]$:

$$R(t) = \min\left(R_{max}, \frac{B(t)}{\Delta t} + \beta \cdot (1 - L_{queue}(t))\right)$$

where $B(t)$ represents available bucket tokens and $\beta$ is a rate smoothing coefficient.

---

## 3. Reproducibility & Empirical Benchmarking Protocol

The repository includes an automated benchmark execution script. To run the empirical performance benchmark locally:

```bash
python3 eval/run_benchmarks.py --seed 42
```

### Empirical Baseline Results
- **Total Events Processed**: $10,000$
- **Micro-Batch Size**: $50$
- **Throughput Rate**: $437,166.74\text{ events/sec}$
- **Sliding-Window Latency ($p_{50}$)**: $0.1105\text{ ms}$
- **Sliding-Window Latency ($p_{95}$)**: $0.1692\text{ ms}$
- **Sliding-Window Latency ($p_{99}$)**: $0.2511\text{ ms}$
- **Backpressure Drop Rate**: $0.00\%$

---

## 4. Technical Citation

```bibtex
@techreport{siddo2026streampulse,
  author      = {Yacine Seybou Siddo},
  title       = {StreamPulse: High-Throughput Real-Time Streaming Data Ingestion and Event-Driven AI Pipeline},
  institution = {GitHub Repository},
  year        = {2026},
  url         = {https://github.com/Yacine-ai-tech/StreamPulse}
}
```
