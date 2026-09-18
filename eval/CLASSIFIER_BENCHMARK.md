# StreamPulse — Domain Classifier Benchmark

Accuracy + macro-F1 of the hybrid domain classifier on a curated, balanced labeled set
(`eval/domain_labeled.jsonl`, 48 examples across the bundled reference domain pack — see
`domain_packs/README.md`). Reproducible:
`python eval/run_classifier_benchmark.py` (keyword) and
`STREAMPULSE_HYBRID_LLM=1 python eval/run_classifier_benchmark.py` (LLM escalation).

## Why this set is hard (and honest)
The texts are **paraphrased to avoid the literal domain keywords** (e.g. "we brought in more
money and kept more of it after bills" instead of "revenue/profit/ebitda"). This deliberately
defeats naive keyword matching so the benchmark measures the **value of the LLM tier**, not a
self-aligned keyword set.

## Results (real run, 2026-08-20, 48 examples)
| Tier | Accuracy | Macro-F1 |
|------|----------|----------|
| Keyword only (Tier 1) | **0.083** | 0.105 |
| Keyword → Vector Embedding (Tier 2) | **0.646** | 0.549 |
| Keyword → Embedding → **LLM escalation** (Tier 3, full hybrid) | **0.917** | 0.793 |

**Headline:** on realistic keyword-poor text, keyword matching collapses (8%); the vector-embedding
tier recovers most of that on its own, and the LLM tier resolves nearly all of the rest — the
measured justification for the hybrid design.

**Honest caveats:**
- Real streams are a *mix* of keyword-rich and keyword-poor text, so keyword alone would score far
  above 8% in production (and the LLM tier is opt-in / costs per call).
- The 48-example set is deliberately small and curated (paraphrased text, no public dataset maps
  to this domain taxonomy); a 91.7% full-hybrid score on 48 examples means "strongly separable on
  a small clean set," not a statistically significant production guarantee at scale.
- The embedding tier's threshold is calibrated to prefer precision over recall: it only commits to
  a domain when confident, and defers to the LLM tier otherwise, because a confident-but-wrong
  Tier 2 answer is worse than deferring to a stronger tier. That tradeoff is reflected in the
  Tier-2-only row above (0.646) — most of the gap between it and the full-hybrid row is exactly
  those deferred, harder examples being correctly resolved by Tier 3 instead of guessed by Tier 2.
- The embedding tier calls a remote inference host over HTTP rather than loading the model
  in-process; it's built to poll through on-demand backend cold-boot overhead rather than fail
  on it, so its measured contribution here reflects genuine classification quality, not host
  wake-up latency. First-request latency reflects that cold-boot overhead, not classifier
  inefficiency.
- The LLM tier was evaluated with an OpenAI-compatible chat model via LiteLLM; any of the
  supported providers (see `LLM_JUDGE`) can be swapped in without code changes.

## Update — N=500 synthetic SaaS telemetry set (2026-09-18)

Reproducible: `python eval/generate_classifier_dataset.py` (deterministic, seed=42) then
`python eval/run_classifier_benchmark.py --dataset eval/domain_labeled_500.jsonl --samples 500`.
Template + slot-filling generation across the real 6 domains (Finance/Operations/Growth/People/
ESG/IT_Ops), combinatorially varied (subject × direction × magnitude × phrasing), deduplicated —
built because the original 48-example set was too small for a statistically credible number.

| Metric | Value |
|--------|-------|
| Accuracy | **0.976** |
| Macro-F1 | **0.976** |

Per-domain: ESG 1.00, Finance 0.95, Growth 0.92, IT_Ops 1.00, Operations 1.00, People 0.98 (F1).
Growth is the weakest (0.87 recall) — the most semantically overlapping domain with Finance in
this dataset's vocabulary (both discuss revenue/customer-acquisition-cost figures).

**Note on infrastructure:** the embedding tier now runs `INFERENCE_MODE=local` (in-process
`sentence-transformers`, not a remote inference host as an earlier version of this document
described) — see `BENCHMARK.md` for the real capacity/memory characteristics of that change.
