import { useEffect, useMemo, useState } from "react";
import { BellRing, RefreshCw, TriangleAlert } from "lucide-react";
import { PageHeader } from "../kit/AppShell";
import { Button, Card, Chip, EmptyState, Skeleton, StatTile } from "../kit/primitives";
import { JSONViewer } from "../kit/JSONViewer";
import { api, HistoryRow, parsePayload } from "../lib/api";

/* v1 "Alerts" — a real derived view: failures and error events filtered from the
   persistent ingestion log. A query over real data, not a fake alerting engine. */

export default function Alerts() {
  const [rows, setRows] = useState<HistoryRow[] | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const load = () => { setRows(null); api.history(250).then((r) => setRows(r.history)).catch(() => setRows([])); };
  useEffect(load, []);

  const problems = useMemo(
    () => (rows ?? []).filter((r) => r.status !== "completed" || !!r.error),
    [rows],
  );

  return (
    <div>
      <PageHeader
        title="Alerts"
        sub="Ingestion events that did not complete cleanly, straight from the pipeline log."
        actions={<Button variant="ghost" onClick={load} aria-label="refresh"><RefreshCw size={14} /></Button>}
      />
      {!rows ? (
        <Skeleton className="h-56 w-full" />
      ) : (
        <>
          <div className="mb-5 grid gap-4 sm:grid-cols-3">
            <StatTile label="Events checked" value={rows.length} sub="most recent" />
            <StatTile label="Problems" value={problems.length}
              delta={problems.length ? { text: "needs review", good: false } : { text: "all clear" }} icon={TriangleAlert} />
            <StatTile label="Clean rate" value={rows.length ? `${Math.round(((rows.length - problems.length) / rows.length) * 100)}%` : "—"} />
          </div>
          {problems.length === 0 ? (
            <Card>
              <EmptyState icon={BellRing} title="No failed ingestion events"
                hint="Failures, rejected payloads and per-record errors will surface here as they happen." />
            </Card>
          ) : (
            <div className="space-y-3">
              {problems.map((r, i) => (
                <Card key={r.id}>
                  <button className="flex w-full flex-wrap items-center gap-3 text-left" onClick={() => setOpen(open === i ? null : i)}>
                    <TriangleAlert size={15} className="shrink-0 text-bad" />
                    <span className="num text-[12px] text-muted">#{r.id}</span>
                    <span className="min-w-0 flex-1 truncate text-sm text-body">{r.source}</span>
                    <Chip tone="bad">{r.error ? "error" : r.status}</Chip>
                    <span className="num text-[11.5px] text-muted">{new Date(r.created_at + "Z").toLocaleString()}</span>
                  </button>
                  {open === i && (
                    <div className="mt-3 space-y-3 border-t border-line pt-3">
                      {r.error && <div className="rounded-xl border border-line bg-[rgba(255,107,107,0.06)] p-3 text-[13px] text-dim">{r.error}</div>}
                      <JSONViewer data={{ ...r, payload: parsePayload(r) }} maxHeight={240} />
                    </div>
                  )}
                </Card>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
