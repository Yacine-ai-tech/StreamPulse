import { ArrowRight, Split } from "lucide-react";
import { PageHeader } from "../kit/AppShell";
import { Card, Chip, StatTile } from "../kit/primitives";

/* Figures verified against eval/CLASSIFIER_BENCHMARK.md — including the
   benchmark's own caveats. Do not edit without re-running the benchmark. */

export default function Classifier() {
  return (
    <div>
      <PageHeader
        title="Hybrid classification"
        sub="Every record is routed through a three-tier classifier: instant keyword matching, a vector-embedding fallback against domain prototypes, escalated to an LLM only when both are inconclusive. Each record carries its decision path."
      />

      <Card title="Decision path">
        <div className="flex flex-wrap items-center gap-3 py-2">
          {["Incoming record", "Keyword tier", "Confident?", "Vector embedding tier", "Confident?", "LLM escalation", "Domain + confidence + method"].map((s, i, arr) => (
            <span key={s} className="flex items-center gap-3">
              <span className={`rounded-xl border px-3.5 py-2 text-[13px] ${i === 1 || i === 3 || i === 5 ? "border-[var(--accent)] text-body" : "border-line text-dim"}`}>
                {s}
              </span>
              {i < arr.length - 1 && <ArrowRight size={14} className="text-muted" />}
            </span>
          ))}
        </div>
        <p className="mt-3 text-[13px] leading-6 text-dim">
          The <code className="font-mono text-[12px]">method</code> field on every classified record
          ("keyword", "vector_embedding", "llm", or a "*_fallback"/"*_low_conf" variant when a tier
          couldn't reach confidence) is visible throughout the UI — in the Live feed and the record
          inspector — so you always know which tier made the call.
        </p>
      </Card>

      <div className="mt-5 grid gap-4 sm:grid-cols-4">
        <StatTile label="Keyword tier alone" value="8.3%" sub="accuracy on keyword-poor text" delta={{ text: "collapses", good: false }} icon={Split} />
        <StatTile label="+ Vector embedding" value="54.0%" sub="same 24-example benchmark" delta={{ text: "partial recovery" }} />
        <StatTile label="+ LLM escalation" value="91.7%" sub="full 3-tier hybrid" delta={{ text: "recovers most of it" }} />
        <StatTile label="Domains" value="6" sub="Finance · Growth · Operations · People · ESG · IT_Ops" />
      </div>

      <Card title="Methodology and caveats" className="mt-5" actions={<Chip>eval/CLASSIFIER_BENCHMARK.md</Chip>}>
        <p className="text-[13px] leading-6 text-dim">
          The benchmark set is deliberately hard: 24 texts paraphrased to avoid the literal domain
          keywords, so it measures the value of the embedding and LLM tiers rather than a
          self-aligned keyword list. The published caveats apply here too: real streams mix
          keyword-rich and keyword-poor text (keyword-only scores far above 8% in production), the
          LLM tier is opt-in and costs per call, and 91.7% on a small curated set means "clearly
          separable on a small clean set", not a production guarantee.
          Reproduce with <code className="font-mono text-[12px]">python eval/run_classifier_benchmark.py</code>{" "}
          (keyword-only) or <code className="font-mono text-[12px]">STREAMPULSE_HYBRID_LLM=1 python eval/run_classifier_benchmark.py</code>{" "}
          (full hybrid, needs an LLM key).
        </p>
      </Card>
    </div>
  );
}
