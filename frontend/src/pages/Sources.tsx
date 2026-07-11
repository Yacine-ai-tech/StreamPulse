import { useEffect, useMemo, useState } from "react";
import { Cable, Mail, FileSpreadsheet, Webhook, Send, RefreshCw, PlugZap } from "lucide-react";
import { Link } from "react-router-dom";
import { PageHeader } from "../kit/AppShell";
import { Button, Card, Chip, EmptyState, Skeleton } from "../kit/primitives";
import { api, HistoryRow } from "../lib/api";

/* v1 "Sources" — real per-source activity aggregated from the persistent ingestion log.
   Status is derived from actual recent events, never invented. */

const KNOWN = [
  { match: /webhook|^wh/i, icon: Webhook, label: "Webhooks", how: "POST /webhook/{source} (HMAC-signed) — optionally /with-vision for DocIntel enrichment" },
  { match: /mail|gmail/i, icon: Mail, label: "Email", how: "POST /ingest/email — Gmail-style payloads, subject becomes the metric hint" },
  { match: /csv|sheet/i, icon: FileSpreadsheet, label: "CSV / Sheets", how: "POST /ingest/csv — one record per row" },
  { match: /.*/, icon: Send, label: "JSON / REST", how: "POST /ingest/json — records[] with metric/value/raw" },
];

export default function Sources() {
  const [rows, setRows] = useState<HistoryRow[] | null>(null);
  const load = () => { setRows(null); api.history(250).then((r) => setRows(r.history)).catch(() => setRows([])); };
  useEffect(load, []);

  const bySource = useMemo(() => {
    const m = new Map<string, HistoryRow[]>();
    (rows ?? []).forEach((r) => m.set(r.source, [...(m.get(r.source) ?? []), r]));
    return [...m.entries()].sort((a, b) => b[1].length - a[1].length);
  }, [rows]);

  return (
    <div>
      <PageHeader
        title="Sources"
        sub="Every source that has delivered data, with activity aggregated from the persistent ingestion log."
        actions={<Button variant="ghost" onClick={load} aria-label="refresh"><RefreshCw size={14} /></Button>}
      />

      {!rows ? (
        <Skeleton className="h-56 w-full" />
      ) : bySource.length === 0 ? (
        <Card>
          <EmptyState icon={Cable} title="No sources have delivered data yet"
            hint="Send something from the Ingest Playground — the source appears here with its live stats."
            action={<Link to="/playground" className="text-sm underline decoration-dotted text-dim hover:text-body">Open Playground</Link>} />
        </Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
          {bySource.map(([source, events]) => {
            const kind = KNOWN.find((k) => k.match.test(source))!;
            const ok = events.filter((e) => e.status === "completed" && !e.error).length;
            const recs = events.reduce((a, e) => a + (e.records || 0), 0);
            const last = events[0];
            const healthy = ok / events.length >= 0.9;
            return (
              <Card key={source} hover>
                <div className="flex items-center justify-between">
                  <kind.icon size={18} style={{ color: "var(--accent)" }} strokeWidth={1.7} />
                  <Chip tone={healthy ? "ok" : "warn"}>
                    <PlugZap size={11} /> {Math.round((ok / events.length) * 100)}% success
                  </Chip>
                </div>
                <div className="mt-3 truncate text-[15px] font-semibold text-body" title={source}>{source}</div>
                <div className="text-[11.5px] text-muted">{kind.label}</div>
                <div className="num mt-3 flex gap-4 text-[12.5px] text-dim">
                  <span><strong className="text-body">{events.length}</strong> events</span>
                  <span><strong className="text-body">{recs}</strong> records</span>
                </div>
                <div className="num mt-1.5 text-[11.5px] text-muted">last activity {new Date(last.created_at + "Z").toLocaleString()}</div>
              </Card>
            );
          })}
        </div>
      )}

      <Card title="Connect a new source" className="mt-5">
        <div className="grid gap-3 lg:grid-cols-2">
          {KNOWN.map((k) => (
            <div key={k.label} className="flex items-start gap-3 rounded-xl border border-line bg-surface-2 px-4 py-3">
              <k.icon size={16} className="mt-0.5 shrink-0 text-dim" />
              <div>
                <div className="text-[13px] font-semibold text-body">{k.label}</div>
                <div className="num mt-0.5 font-mono text-[11.5px] leading-5 text-muted">{k.how}</div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
