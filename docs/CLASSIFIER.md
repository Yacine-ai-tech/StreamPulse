# StreamPulse — Hybrid Domain Classifier

## What Is It?

The **Hybrid Domain Classifier** is the intelligence layer that sits between raw incoming data records and the StreamPulse pipeline storage. Its job is to **automatically assign a business domain** to every record that arrives — whether from a webhook, n8n workflow, CSV upload, or API ingest — so that KPI metrics are stored under the correct domain and are immediately queryable by domain without any manual tagging.

---

## Why It Exists

Raw data streams don't arrive pre-labelled. An n8n node pushing `{ "value": 2340000, "source": "CRM" }` gives no indication of whether this is Revenue (Finance), pipeline ARR (Growth), or headcount cost (People). Without classification:
- Metrics land in the wrong domain, corrupting domain-level dashboards.
- Multi-domain analytics and health scores become meaningless.
- The LLM agent can't route questions to the right sub-system.

---

## 3-Tier Architecture

```
Incoming text/record
       │
  [TIER 1] Keyword matching — fast regex, microseconds
       │ conf >= 0.5? → DONE (method: "keyword")
       │
  [TIER 2] Vector embedding similarity — BGE-m3
       │ cosine vs the configured domain pack's prototypes
       │ score >= CLASSIFIER_EMBEDDING_THRESHOLD? → DONE (method: "vector_embedding")
       │
  [TIER 3] LLM zero-shot (opt-in: STREAMPULSE_HYBRID_LLM=1)
       │ Claude Haiku / Gemini Flash
       └── DONE (method: "llm")
```

Every record carries `domain + confidence + method` — the full decision path is transparent throughout the UI.

---

## Domains

The classifier is domain-agnostic — it has no built-in notion of "Finance" or "HR". The actual
taxonomy is loaded from a **domain pack** (see `domain_packs/README.md`), a JSON file of
`{domain: [prototype phrases]}`, defaulting to a bundled reference pack:

| Domain (bundled reference pack) | Key concepts |
|--------|-------------|
| Finance | Revenue, EBITDA, margin, cash flow, P&L |
| Growth | MRR, ARR, CAC, LTV, churn, conversion |
| Operations | Throughput, OEE, production, quality, cycle time |
| People | Headcount, turnover, hiring, retention, engagement |
| ESG | Emissions, carbon, sustainability, governance |
| IT_Ops | Uptime, latency, incidents, deployments, SLA |

Point `STREAMPULSE_DOMAIN_PACK` at your own file in the same shape to classify into any other
taxonomy without touching code.

---

## Benchmark Results (48 examples, bundled reference domain pack, keyword-poor texts)

| Tier | Accuracy | Macro-F1 |
|------|----------|----------|
| Keyword only | 8.3% | 0.105 |
| Keyword + Vector embedding | 64.6% | 0.549 |
| Hybrid (+ LLM escalation) | 91.7% | 0.793 |

Reproduce: `STREAMPULSE_HYBRID_LLM=1 python eval/run_classifier_benchmark.py`. Full methodology
and caveats: [eval/CLASSIFIER_BENCHMARK.md](../eval/CLASSIFIER_BENCHMARK.md).

---

## Novelty

1. **Cost-optimised by default** — LLM escalation is opt-in; ~92% of real streams are handled by Tier 1 at zero cost.
2. **Transparent method attribution** — every record carries its `method` field, making classification auditable.
3. **Model-agnostic** — Tiers 2 & 3 use the inference adapter (any remote host you configure / Cohere / Jina / local).
4. **Graceful degradation** — every tier has try/except fallback; the pipeline never blocks on classifier failure.
5. **Configurable domains** — swap the whole taxonomy via a domain pack (`domain_packs/`,
   `STREAMPULSE_DOMAIN_PACK`) without touching code.

---

## Configuration

| Env var | Default | Effect |
|---------|---------|--------|
| `STREAMPULSE_HYBRID_LLM` | `1` | Set to `0` to disable Tiers 2 & 3 (keyword-only) |
| `STREAMPULSE_EMBED_MODEL` | `BAAI/bge-m3` | Embedding model for Tier 2 |
| `STREAMPULSE_DOMAIN_PACK` | bundled demo pack | Path to a custom domain-pack JSON (see `domain_packs/README.md`) |
| `CLASSIFIER_EMBEDDING_THRESHOLD` | `0.65` | Minimum Tier 2 similarity to commit rather than defer to Tier 3 |
| `LLM_JUDGE` | settings.LLM_JUDGE | LLM for Tier 3 |
