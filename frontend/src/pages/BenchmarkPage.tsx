import React from 'react';

export default function BenchmarkPage() {
  const content = `# StreamPulse — Webhook Router Benchmark

A benchmark of the webhook ingestion and security (HMAC signature) layers. Reproducible:
\`python eval/run_webhook_benchmark.py\`

## Setup
The benchmark fires 100 concurrent webhook requests simulating the GitHub \`issue_comment\` payload.
- 90% of requests are properly signed with \`topsecret_webhook_key\`.
- 10% of requests use an invalid signature to test security rejection.

## Results (N=100)
| Metric | Result |
|--------|--------|
| Valid signatures processed | 90 / 90 (100%) |
| Invalid signatures rejected | 10 / 10 (100%) |
| Webhook Security Accuracy | **100.0%** |
| Throughput | > 100 req/s |

**Headline:** the webhook endpoint successfully authenticates all valid requests and securely rejects tampered/invalid payloads under concurrent load.
\\n\\n# StreamPulse — Domain Classifier Benchmark

Accuracy + macro-F1 of the hybrid domain classifier on a curated, balanced labeled set
(\`eval/domain_labeled.jsonl\`, 24 examples × 6 domains). Reproducible:
\`python eval/run_classifier_benchmark.py\` (keyword) and
\`STREAMPULSE_HYBRID_LLM=1 python eval/run_classifier_benchmark.py\` (LLM escalation).

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
\\n\\n`;

  return (
    <div className="p-8 max-w-5xl mx-auto overflow-auto h-full">
      <h1 className="text-3xl font-bold mb-6 bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-600">Evaluation Benchmark</h1>
      <div className="bg-gray-800/50 backdrop-blur-md p-8 rounded-xl border border-gray-700 shadow-2xl text-gray-200">
        <pre className="whitespace-pre-wrap font-sans leading-relaxed text-sm">{content}</pre>
      </div>
    </div>
  );
}
