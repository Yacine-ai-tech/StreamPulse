import { useEffect, useMemo, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { Activity, Database, Gauge, RefreshCw } from "lucide-react";
import { PageHeader } from "../kit/AppShell";
import { Button, Card, Chip, EmptyState, Skeleton, StatTile } from "../kit/primitives";
import { api, HistoryRow } from "../lib/api";

/* v1 "Analytics" — operational widgets computed from the real store: /pipeline/status
   aggregates plus per-source volumes derived from the ingestion log. */

type Status = Record<string, number | string>;

export default function Analytics() {
  const [st, setSt] = useState<Status | null>(null);
  const [rows, setRows] = useState<HistoryRow[] | null>(null);
  const load = () => {
    setSt(null); setRows(null);
    api.status().then((s) => setSt(s as Status)).catch(() => setSt({}));
    api.history(250).then((r) => setRows(r.history)).catch(() => setRows([]));
  };
  useEffect(load, []);

  const perSource = useMemo(() => {
    const m = new Map<string, number>();
    (rows ?? []).forEach((r) => m.set(r.source, (m.get(r.source) ?? 0) + (r.records || 0)));
    return [...m.entries()].map(([source, records]) => ({ source, records })).sort((a, b) => b.records - a.records).slice(0, 10);
  }, [rows]);

  const okRate = useMemo(() => {
    if (!rows || rows.length === 0) return null;
    const ok = rows.filter((r) => r.status === "completed" && !r.error).length;
    return Math.round((ok / rows.length) * 100);
  }, [rows]);

  return (
    <div>
      <PageHeader
        title="Analytics"
        sub="Operational counters from the persistent store — everything here survives restarts on the Postgres backend."
        actions={<Button variant="ghost" onClick={load} aria-label="refresh"><RefreshCw size={14} /></Button>}
      />
      {!st || !rows ? (
        <Skeleton className="h-64 w-full" />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatTile label="Records stored" value={Number(st.records_stored ?? 0)} icon={Database} sub={`backend: ${st.backend ?? "?"}`} />
            <StatTile label="Ingestion events" value={Number(st.ingestion_events ?? 0)} icon={Activity} />
            <StatTile label="Routing success" value={okRate == null ? "—" : `${okRate}%`} icon={Gauge}
              delta={okRate != null ? { text: okRate >= 95 ? "healthy" : "review failures", good: okRate >= 95 } : undefined} />
            <StatTile label="Distinct sources" value={Number(st.distinct_sources ?? 0)} sub={`${st.connected_clients ?? 0} live clients`} />
          </div>
          <Card title="Records by source" className="mt-5" actions={<Chip>top {perSource.length}</Chip>}>
            {!Array.isArray(perSource) || perSource.length === 0 ? (
              <EmptyState title="No ingestion volume yet" />
            ) : (
              <div className="h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={perSource} layout="vertical" margin={{ top: 4, right: 24, left: 8, bottom: 0 }}>
                    <CartesianGrid stroke="var(--grid-line)" horizontal={false} />
                    <XAxis type="number" tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={false} tickLine={false} allowDecimals={false} />
                    <YAxis type="category" dataKey="source" width={140} tick={{ fill: "var(--text-2)", fontSize: 11.5 }} axisLine={false} tickLine={false} />
                    <Tooltip cursor={{ fill: "rgba(255,255,255,.03)" }}
                      contentStyle={{ background: "var(--surface-2)", border: "1px solid var(--border-strong)", borderRadius: 12, color: "var(--text)", fontSize: 12 }} />
                    <Bar dataKey="records" fill="var(--accent)" radius={[0, 6, 6, 0]} maxBarSize={18} isAnimationActive={false} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
