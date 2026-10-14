import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity, Award, BookOpen, Boxes, Brain, Cable, Cloud, Cog, Cpu, Database, FileText, Filter,
  Gauge, GitBranch, Globe, Layers, Lock, Mic, Network, Pause, Play, Radio, RadioTower, Scale,
  Search, ShieldCheck, Sigma, Sparkles, Terminal, Wrench, Workflow, Zap, type LucideIcon,
} from "lucide-react";
import { PageHeader } from "../kit/AppShell";
import { Button, Card, Chip } from "../kit/primitives";
import { PipelineFlow, type Stage } from "../kit/PipelineFlow";

const ICONS: Record<string, LucideIcon> = {
  Activity, Award, BookOpen, Boxes, Brain, Cable, Cloud, Cog, Cpu, Database, FileText, Filter,
  Gauge, GitBranch, Globe, Layers, Lock, Mic, Network, Radio, RadioTower, Scale, Search,
  ShieldCheck, Sigma, Sparkles, Terminal, Wrench, Workflow, Zap,
};

type NodeInfo = { id: string; label: string; layer: string; icon: string; summary: string; detail: string[]; env?: string[] };
type StageInfo = { id: string; label: string; icon: string; text: string; nodes: string[] };
type Arch = {
  title: string; sub: string; lifecycleTitle: string; layers: string[]; nodes: NodeInfo[]; stages: StageInfo[];
  endpoints: [string, string][]; decisions: [string, string][]; links: { to: string; label: string }[];
};

const DATA: Arch = {
  "title": "Architecture",
  "sub": "How raw events from many sources become classified, stored and streamed KPI records.",
  "lifecycleTitle": "Life of an ingest request",
  "layers": [
    "Sources",
    "Classification",
    "Persistence",
    "Delivery"
  ],
  "nodes": [
    {
      "id": "api",
      "label": "Ingestion API",
      "layer": "Sources",
      "icon": "GitBranch",
      "summary": "JSON, CSV, e-mail and signed webhooks.",
      "detail": [
        "Requests carry a visitor session, an internal token or a valid webhook signature.",
        "Blocking work runs on a sized worker pool so bursts do not queue behind the interpreter default."
      ],
      "env": [
        "REQUIRE_INTERNAL_TOKEN",
        "WEBHOOK_SECRET",
        "DEMO_SESSION_SCOPING"
      ]
    },
    {
      "id": "hooks",
      "label": "Webhook receiver",
      "layer": "Sources",
      "icon": "ShieldCheck",
      "summary": "HMAC-SHA256 verification and payload normalisation.",
      "detail": [
        "Constant-time signature comparison over the raw body.",
        "Optional image-bearing webhooks are enriched through DocIntel image classification."
      ],
      "env": [
        "WEBHOOK_SECRET",
        "DOCINTEL_URL"
      ]
    },
    {
      "id": "keyword",
      "label": "Tier 1 · Keyword",
      "layer": "Classification",
      "icon": "Search",
      "summary": "Pattern hits per domain; sub-millisecond.",
      "detail": [
        "Confidence is 0.4 + 0.2 per hit; a clear keyword never reaches the expensive tiers."
      ],
      "env": [
        "CLASSIFIER_KEYWORD_THRESHOLD"
      ]
    },
    {
      "id": "embed",
      "label": "Tier 2 · Embedding",
      "layer": "Classification",
      "icon": "Brain",
      "summary": "Cosine similarity to prototype phrases of each domain.",
      "detail": [
        "Multilingual embedding model, local or a remote endpoint.",
        "A remote host that is still starting is polled within a time budget; client errors fail fast.",
        "Threshold is set above the highest observed confident-but-wrong score."
      ],
      "env": [
        "CLASSIFIER_EMBEDDING_THRESHOLD",
        "INFERENCE_MODE",
        "EMBEDDING_ENDPOINT",
        "STREAMPULSE_EMBED_MODEL"
      ]
    },
    {
      "id": "llm",
      "label": "Tier 3 · LLM",
      "layer": "Classification",
      "icon": "Sparkles",
      "summary": "Zero-shot label from the domain list when tiers 1–2 are inconclusive.",
      "detail": [
        "Rate limits switch to a failover model; authentication errors switch to the configured fallback.",
        "Failed calls are never cached, so an outage cannot poison the cache."
      ],
      "env": [
        "LLM_JUDGE",
        "LLM_JUDGE_FALLBACK",
        "LLM_JUDGE_FAILOVER",
        "CLASSIFIER_LLM_TIMEOUT_SECONDS"
      ]
    },
    {
      "id": "packs",
      "label": "Domain packs",
      "layer": "Classification",
      "icon": "FileText",
      "summary": "The taxonomy is data: {domain: [prototype phrases]}.",
      "detail": [
        "Swap the pack to change domains without changing code."
      ],
      "env": [
        "STREAMPULSE_DOMAIN_PACK"
      ]
    },
    {
      "id": "store",
      "label": "KPI store",
      "layer": "Persistence",
      "icon": "Database",
      "summary": "KPI metrics and an ingestion log.",
      "detail": [
        "SQLite locally, Postgres in production; optional pgvector cache and DuckDB analytics."
      ],
      "env": [
        "POSTGRES_URL",
        "ENABLE_PGVECTOR",
        "ENABLE_DUCKDB"
      ]
    },
    {
      "id": "live",
      "label": "Live feed",
      "layer": "Delivery",
      "icon": "Radio",
      "summary": "WebSocket and SSE, scoped to the owning session.",
      "detail": [
        "Redis or Kafka fan-out reaches other instances."
      ],
      "env": [
        "MESSAGE_BROKER",
        "REDIS_URL",
        "KAFKA_BROKER_URL"
      ]
    },
    {
      "id": "out",
      "label": "Outbound webhook",
      "layer": "Delivery",
      "icon": "Cable",
      "summary": "Forwards enriched records to a configured destination.",
      "detail": [
        "The service's own token is never forwarded; a dedicated destination token is."
      ],
      "env": [
        "EXTERNAL_WEBHOOK_URL",
        "EXTERNAL_WEBHOOK_TOKEN"
      ]
    }
  ],
  "stages": [
    {
      "id": "auth",
      "label": "Authenticate",
      "icon": "ShieldCheck",
      "text": "Visitor session, internal token or webhook signature; the ingestion is logged as running.",
      "nodes": [
        "api",
        "hooks"
      ]
    },
    {
      "id": "tier1",
      "label": "Keyword",
      "icon": "Search",
      "text": "Cache lookup, then keyword patterns. A clear match ends here.",
      "nodes": [
        "keyword"
      ]
    },
    {
      "id": "tier2",
      "label": "Embedding",
      "icon": "Brain",
      "text": "Similarity to domain prototypes; commits above the calibrated threshold.",
      "nodes": [
        "embed",
        "packs"
      ]
    },
    {
      "id": "tier3",
      "label": "LLM",
      "icon": "Sparkles",
      "text": "Only inconclusive records reach the model; failures keep the keyword result.",
      "nodes": [
        "llm"
      ]
    },
    {
      "id": "persist",
      "label": "Persist",
      "icon": "Database",
      "text": "KPI metrics are written and the ingestion is marked completed or failed.",
      "nodes": [
        "store"
      ]
    },
    {
      "id": "deliver",
      "label": "Deliver",
      "icon": "Radio",
      "text": "Live subscribers, other instances and the outbound webhook receive the records.",
      "nodes": [
        "live",
        "out"
      ]
    }
  ],
  "endpoints": [
    [
      "POST /ingest/json",
      "Ingest a batch of JSON records"
    ],
    [
      "POST /ingest/csv",
      "Ingest an uploaded CSV file"
    ],
    [
      "POST /ingest/email",
      "Ingest an e-mail style payload"
    ],
    [
      "POST /webhook/{source}",
      "Signed webhook (X-Signature-256)"
    ],
    [
      "POST /webhook/{source}/with-vision",
      "Signed webhook with image enrichment"
    ],
    [
      "GET /pipeline/status",
      "Counters and current state"
    ],
    [
      "GET /pipeline/history",
      "Recent ingestions for the caller's session"
    ],
    [
      "POST /pipeline/replay/{id}",
      "Re-run a recorded ingestion"
    ],
    [
      "WS /live",
      "Live event feed"
    ],
    [
      "GET /live/sse",
      "Server-sent events feed"
    ],
    [
      "GET /analytics/domain-summary",
      "Records per domain"
    ],
    [
      "GET /analytics/classification-trends",
      "Classification trends"
    ],
    [
      "GET /analytics/cache-stats",
      "Classifier cache statistics"
    ],
    [
      "POST /analytics/refresh",
      "Refresh analytics tables"
    ],
    [
      "GET /health",
      "Liveness"
    ],
    [
      "GET /ready",
      "Readiness: 503 warming_up until the classifier is loaded"
    ]
  ],
  "decisions": [
    [
      "Cheapest tier first",
      "Most real rows carry a clear keyword, so the embedding and LLM tiers run only when needed."
    ],
    [
      "Calibrated thresholds",
      "A deferred answer is safer than a wrong confident one, so thresholds sit above observed false positives."
    ],
    [
      "Taxonomy as data",
      "New domains need a JSON pack, not a deployment."
    ]
  ],
  "links": [
    {
      "to": "/research",
      "label": "Research"
    },
    {
      "to": "/benchmark",
      "label": "Benchmarks"
    }
  ]
};

export default function ArchitecturePage() {
  const [selected, setSelected] = useState<string>(DATA.nodes[0].id);
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [filter, setFilter] = useState("");

  const stages: (Stage & { text: string; nodes: string[] })[] = useMemo(
    () => DATA.stages.map((s) => ({ ...s, icon: ICONS[s.icon] ?? Zap })), []);

  useEffect(() => {
    if (!playing) return;
    const t = setInterval(() => setStep((s) => (s + 1) % (stages.length + 1)), 1800);
    return () => clearInterval(t);
  }, [playing, stages.length]);

  const current = stages[Math.min(step, stages.length - 1)];
  const lit = useMemo(() => new Set(step < stages.length ? current.nodes : []), [step, current, stages.length]);
  const node = DATA.nodes.find((n) => n.id === selected) ?? DATA.nodes[0];
  const endpoints = DATA.endpoints.filter(([r, p]) => (r + " " + p).toLowerCase().includes(filter.toLowerCase()));

  return (
    <div className="p-8 max-w-6xl mx-auto h-full overflow-y-auto space-y-8">
      <PageHeader
        title={DATA.title}
        sub={DATA.sub}
        actions={
          <div className="flex gap-2">
            {DATA.links.map((l) => (
              <Link key={l.to} to={l.to}><Button variant="secondary">{l.label}</Button></Link>
            ))}
          </div>
        }
      />

      <Card title={DATA.lifecycleTitle}>
        <div className="flex items-center justify-between mb-2">
          <div className="text-xs text-dim">Pick a stage or let it play; the components involved are highlighted below.</div>
          <Button variant="secondary" onClick={() => setPlaying((p) => !p)}>
            {playing ? <Pause size={14} className="mr-1 inline" /> : <Play size={14} className="mr-1 inline" />}
            {playing ? "Pause" : "Play"}
          </Button>
        </div>
        <PipelineFlow stages={stages} active={step} done={step >= stages.length} />
        <div className="mt-3 flex flex-wrap gap-2">
          {stages.map((s, i) => (
            <button key={s.id} onClick={() => { setPlaying(false); setStep(i); }}
              className={`rounded-lg border px-3 py-1 text-xs ${i === step ? "border-accent text-body" : "border-line text-dim"}`}>
              {i + 1}. {s.label}
            </button>
          ))}
        </div>
        <p className="mt-3 text-sm text-dim">{step < stages.length ? current.text : "Complete."}</p>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          {DATA.layers.map((layer) => (
            <Card key={layer} title={layer}>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {DATA.nodes.filter((n) => n.layer === layer).map((n) => {
                  const Icon = ICONS[n.icon] ?? Boxes;
                  const active = selected === n.id;
                  return (
                    <button key={n.id} onClick={() => setSelected(n.id)}
                      className={`text-left rounded-xl border p-3 transition-colors ${active ? "border-accent bg-surface-2" : "border-line bg-surface"} ${lit.has(n.id) ? "ring-1 ring-accent" : ""}`}>
                      <div className="flex items-center gap-2 text-sm font-semibold text-body"><Icon size={14} /> {n.label}</div>
                      <div className="mt-1 text-xs text-dim">{n.summary}</div>
                    </button>
                  );
                })}
              </div>
            </Card>
          ))}
        </div>

        <Card title={node.label} className="h-fit lg:sticky lg:top-4">
          <p className="text-sm text-dim">{node.summary}</p>
          <ul className="mt-3 space-y-2 text-xs text-dim list-disc pl-4">
            {node.detail.map((d) => <li key={d}>{d}</li>)}
          </ul>
          {node.env && node.env.length > 0 && (
            <div className="mt-4">
              <div className="text-[11px] uppercase tracking-wider text-muted mb-1">Configuration</div>
              <div className="flex flex-wrap gap-1.5">{node.env.map((e) => <Chip key={e}>{e}</Chip>)}</div>
            </div>
          )}
        </Card>
      </div>

      <Card title="Interfaces">
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter routes…"
          aria-label="Filter routes"
          className="w-full mb-3 rounded-lg border border-line bg-surface-2 px-3 py-2 text-xs text-body outline-none focus:border-accent"
        />
        <div className="divide-y divide-line text-xs">
          {endpoints.map(([r, p]) => (
            <div key={r} className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-4 py-2">
              <code className="sm:w-72 shrink-0 text-body">{r}</code>
              <span className="text-dim">{p}</span>
            </div>
          ))}
          {endpoints.length === 0 && <div className="py-3 text-dim">No route matches.</div>}
        </div>
      </Card>

      <Card title="Design decisions">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs text-dim">
          {DATA.decisions.map(([t, d]) => (
            <div key={t} className="rounded-xl border border-line bg-surface-2 p-4">
              <div className="font-semibold text-body text-sm mb-1">{t}</div>{d}
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
