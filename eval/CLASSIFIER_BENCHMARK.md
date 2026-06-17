# StreamPulse — Domain Classifier Benchmark

Accuracy + macro-F1 of the hybrid domain classifier on a curated, balanced labeled set
(`eval/domain_labeled.jsonl`, 24 examples × 6 domains). Reproducible:
`python eval/run_classifier_benchmark.py` (keyword) and
`STREAMPULSE_HYBRID_LLM=1 python eval/run_classifier_benchmark.py` (LLM escalation).

## Why this set is hard (and honest)
The texts are **paraphrased to avoid the literal domain keywords** (e.g. "we brought in more
money and kept more of it after bills" instead of "revenue/profit/ebitda"). This deliberately
defeats naive keyword matching so the benchmark measures the **value of the LLM tier**, not a
self-aligned keyword set.

## Results (real run, 2026-06-17, 24 examples)
| Tier | Accuracy | Macro-F1 |
|------|----------|----------|
| Keyword only | **0.083** | 0.105 |
| Keyword → **LLM escalation** (hybrid) | **1.000** | 1.000 |

**Headline:** on realistic keyword-poor text, keyword matching collapses (8%) while the hybrid
classifier's LLM tier recovers it to 100% — the measured justification for the hybrid design.

**Honest caveats:** real streams are a *mix* of keyword-rich and keyword-poor text, so keyword
alone would score far above 8% in production (and the LLM tier is opt-in / costs per call). The
24-example set is small and curated (no public dataset maps to these 6 custom domains); treat
the 100% as "clearly separable on a small clean set," not a production guarantee.
