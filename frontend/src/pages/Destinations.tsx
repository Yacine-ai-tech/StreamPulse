import { useEffect, useState } from "react";
import { Database, Radio, RadioTower, RefreshCw } from "lucide-react";
import { PageHeader } from "../kit/AppShell";
import { Button, Card, Chip, Skeleton } from "../kit/primitives";
import { api } from "../lib/api";

/* v1 "Destinations" — where processed records actually go. All three destinations are
   real platform capabilities; counters come from /pipeline/status. */

type Status = { connected_clients?: number; records_stored?: number; ingestion_events?: number; backend?: string };

export default function Destinations() {
  const [st, setSt] = useState<Status | null>(null);
  const load = () => { setSt(null); api.status().then(setSt).catch(() => setSt({})); };
  useEffect(load, []);

  return (
    <div>
      <PageHeader
        title="Destinations"
        sub="Every classified record is delivered to all three destinations simultaneously."
        actions={<Button variant="ghost" onClick={load} aria-label="refresh"><RefreshCw size={14} /></Button>}
      />
      {!st ? (
        <Skeleton className="h-56 w-full" />
      ) : (
        <div className="grid gap-4 lg:grid-cols-3">
          <Card hover>
            <Database size={18} style={{ color: "var(--accent)" }} strokeWidth={1.7} />
            <div className="mt-3 text-[15px] font-semibold text-body">KPI store</div>
            <div className="num mt-0.5 font-mono text-[11.5px] text-muted">{st.backend === "postgres" ? "PostgreSQL (Neon)" : "SQLite"}</div>
            <p className="mt-3 text-[13px] leading-6 text-dim">
              Normalized, classified records persisted with period, domain, value, unit and
              confidence — durable across deploys on the Postgres backend.
            </p>
            <div className="mt-3 flex gap-2">
              {st.records_stored != null && <Chip className="num">{st.records_stored} records</Chip>}
              {st.ingestion_events != null && <Chip className="num">{st.ingestion_events} events</Chip>}
            </div>
          </Card>
          <Card hover>
            <Radio size={18} style={{ color: "var(--accent)" }} strokeWidth={1.7} />
            <div className="mt-3 text-[15px] font-semibold text-body">WebSocket broadcast</div>
            <div className="num mt-0.5 font-mono text-[11.5px] text-muted">WS /live</div>
            <p className="mt-3 text-[13px] leading-6 text-dim">
              Every ingested batch is pushed to all connected clients the moment it is
              classified — this powers the Live Operations feed.
            </p>
            <div className="mt-3">
              <Chip className="num" tone={st.connected_clients ? "ok" : "default"}>
                {st.connected_clients ?? 0} connected now
              </Chip>
            </div>
          </Card>
          <Card hover>
            <RadioTower size={18} style={{ color: "var(--accent)" }} strokeWidth={1.7} />
            <div className="mt-3 text-[15px] font-semibold text-body">Server-sent events</div>
            <div className="num mt-0.5 font-mono text-[11.5px] text-muted">GET /live/sse</div>
            <p className="mt-3 text-[13px] leading-6 text-dim">
              One-way stream of recent pipeline activity for clients that cannot hold a
              WebSocket — the UI falls back to it automatically.
            </p>
          </Card>
        </div>
      )}
    </div>
  );
}
