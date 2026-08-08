import { useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { ArrowRight, Pause, Play, Radio, Send } from "lucide-react";
import { Link } from "react-router-dom";
import { PageHeader } from "../kit/AppShell";
import { Button, Card, Chip, ConfidenceBadge, EmptyState, StatTile } from "../kit/primitives";
import { JSONViewer } from "../kit/JSONViewer";
import { PipelineFlow } from "../kit/PipelineFlow";
import { api, ClassifiedRecord, LiveEvent, openLive } from "../lib/api";
import { Download, BrainCircuit, Route, Database } from "lucide-react";

const PIPELINE_STAGES = [
  { id: "ingest", label: "Ingest", icon: Download },
  { id: "classify", label: "Classify", icon: BrainCircuit },
  { id: "route", label: "Route", icon: Route },
  { id: "store", label: "Store", icon: Database },
];

const DOMAIN_COLORS: Record<string, string> = {
  Finance: "var(--accent-2)",
  Growth: "var(--accent)",
  Operations: "#7a6dff",
  People: "#f5c24b",
  ESG: "#34d399",
  IT_Ops: "#4aa8ff",
};

type FeedRow = { ev: LiveEvent; rec: ClassifiedRecord; key: string };

export default function Live() {
  const [state, setState] = useState<"ws" | "sse" | "connecting" | "down">("connecting");
  const [rows, setRows] = useState<FeedRow[]>([]);
  const [paused, setPaused] = useState(false);
  const [clients, setClients] = useState<number | null>(null);
  const [selected, setSelected] = useState<FeedRow | null>(null);
  const pausedRef = useRef(paused);
  pausedRef.current = paused;
  const counter = useRef(0);

  useEffect(() => {
    const close = openLive((ev) => {
      if (pausedRef.current) return;
      setRows((old) => {
        const add: FeedRow[] = ev.records.map((rec) => ({ ev, rec, key: `e${counter.current++}` }));
        return [...add, ...old].slice(0, 200);
      });
    }, setState);
    return close;
  }, []);

  useEffect(() => {
    const t = setInterval(() => api.status().then((s) => setClients(s.connected_clients)).catch(() => {}), 10000);
    api.status().then((s) => setClients(s.connected_clients)).catch(() => {});
    return () => clearInterval(t);
  }, []);

  const perMinute = useMemo(() => {
    const cutoff = Date.now() - 60_000;
    return rows.filter((r) => r.ev.receivedAt > cutoff).length;
  }, [rows]);

  const domains = useMemo(() => {
    const counts: Record<string, number> = {};
    rows.forEach(({ rec }) => {
      const d = String(rec.domain ?? "Unclassified");
      counts[d] = (counts[d] ?? 0) + 1;
    });
    return Object.entries(counts).map(([name, value]) => ({ name, value }));
  }, [rows]);

  return (
    <div>
      <PageHeader
        title="Live operations"
        sub="Every record ingested anywhere in the platform streams here in real time, already classified."
        actions={
          <div className="flex items-center gap-2">
            <Chip tone={state === "ws" ? "ok" : state === "down" ? "bad" : "warn"}>
              <Radio size={11} />
              {state === "ws" ? "live · WebSocket" : state === "sse" ? "fallback · SSE" : state}
            </Chip>
            <Button variant="secondary" onClick={() => setPaused((p) => !p)}>
              {paused ? <Play size={13} /> : <Pause size={13} />} {paused ? "Resume" : "Pause"}
            </Button>
          </div>
        }
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <StatTile label="Records / min" value={perMinute} sub="this session" icon={Radio} />
        <StatTile label="Session records" value={rows.length} sub="last 200 kept" />
        <StatTile label="Connected clients" value={clients ?? "—"} sub="from /pipeline/status" />
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[1fr_320px]">
        <Card title="Record feed" noPad className="overflow-hidden">
          {rows.length === 0 ? (
            <EmptyState
              icon={Radio}
              title={state === "ws" ? "Listening — no records yet" : "Waiting for the stream"}
              hint="Send something from the Ingest Playground (even from another tab) and watch it arrive here, classified."
              action={<Link to="/playground" className="text-sm underline decoration-dotted text-dim hover:text-body"><span className="inline-flex items-center gap-1"><Send size={12} />Open Playground <ArrowRight size={12} /></span></Link>}
            />
          ) : (
            <div className="max-h-[520px] divide-y divide-[var(--border)] overflow-y-auto">
              <AnimatePresence initial={false}>
                {rows.map((row) => (
                  <motion.button
                    key={row.key}
                    initial={{ opacity: 0, y: -8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="grid w-full grid-cols-[110px_1fr_auto] items-center gap-3 px-4 py-2.5 text-left hover:bg-surface-2"
                    onClick={() => setSelected(row)}
                  >
                    <span className="truncate text-[12px] text-muted">{row.ev.source}</span>
                    <span className="flex min-w-0 items-center gap-2">
                      <span
                        className="inline-block h-2 w-2 shrink-0 rounded-full"
                        style={{ background: DOMAIN_COLORS[String(row.rec.domain)] ?? "var(--text-muted)" }}
                      />
                      <span className="truncate text-[13px] text-body">
                        {String(row.rec.metric ?? row.rec.domain ?? "record")}
                      </span>
                      <Chip title={`classified by ${row.rec.method ?? "keyword"} tier`}>
                        {String(row.rec.domain ?? "—")}{row.rec.method === "llm" ? " · llm" : ""}
                      </Chip>
                      {row.rec.image_category && <Chip tone="accent">vision: {String(row.rec.image_category)}</Chip>}
                    </span>
                    <span className="flex items-center gap-2">
                      <ConfidenceBadge value={typeof row.rec.confidence === "number" ? row.rec.confidence : null} />
                      <span className="num text-[11px] text-muted">
                        {new Date(row.ev.receivedAt).toLocaleTimeString()}
                      </span>
                    </span>
                  </motion.button>
                ))}
              </AnimatePresence>
            </div>
          )}
        </Card>

        <div className="space-y-4">
          <Card title="Domain distribution" actions={<Chip>session</Chip>}>
            {!Array.isArray(domains) || domains.length === 0 ? (
              <EmptyState title="No data yet" />
            ) : (
              <div className="h-[200px]">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={domains} dataKey="value" nameKey="name" innerRadius={52} outerRadius={78} paddingAngle={3} isAnimationActive={false}>
                      {domains.map((d) => (
                        <Cell key={d.name} fill={DOMAIN_COLORS[d.name] ?? "var(--text-muted)"} stroke="var(--bg)" />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ background: "var(--surface-2)", border: "1px solid var(--border-strong)", borderRadius: 12, color: "var(--text)", fontSize: 12 }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}
            <div className="mt-2 flex flex-wrap gap-1.5">
              {domains.map((d) => (
                <span key={d.name} className="flex items-center gap-1.5 text-[11.5px] text-dim">
                  <span className="inline-block h-2 w-2 rounded-full" style={{ background: DOMAIN_COLORS[d.name] ?? "var(--text-muted)" }} />
                  {d.name} <span className="num text-muted">{d.value}</span>
                </span>
              ))}
            </div>
          </Card>

          {selected && (
            <Card title="Record inspector" actions={<button className="text-xs text-muted hover:text-body" onClick={() => setSelected(null)}>close</button>}>
              <div className="mb-6 mt-2 px-2">
                <PipelineFlow stages={PIPELINE_STAGES} active={4} done={true} />
              </div>
              <JSONViewer data={selected.rec} maxHeight={260} />
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
