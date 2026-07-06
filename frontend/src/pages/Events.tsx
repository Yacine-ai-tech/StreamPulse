import { useEffect, useState } from "react";
import { ChevronDown, ChevronRight, ListTree, RefreshCw } from "lucide-react";
import { PageHeader } from "../kit/AppShell";
import { Button, Card, Chip, EmptyState, Skeleton } from "../kit/primitives";
import { Segmented, Select } from "../kit/misc";
import { JSONViewer } from "../kit/JSONViewer";
import { api, HistoryRow, parsePayload } from "../lib/api";

export default function Events() {
  const [rows, setRows] = useState<HistoryRow[] | null>(null);
  const [filter, setFilter] = useState("all");
  const [limit, setLimit] = useState("100");
  const [err, setErr] = useState("");

  const load = () => {
    setRows(null); setErr("");
    api.history(Number(limit)).then((r) => setRows(r.history)).catch((e) => setErr(String(e)));
  };
  useEffect(load, [limit]);

  const visible = (rows ?? []).filter((r) =>
    filter === "all" ? true : filter === "failed" ? (r.status !== "completed" || !!r.error) : r.status === "completed",
  );

  return (
    <div>
      <PageHeader
        title="Ingestion events"
        sub="The persisted pipeline log — one row per ingestion batch, with source, status, record count and stored payload."
        actions={
          <div className="flex items-center gap-2">
            <Segmented value={filter} onChange={setFilter}
              options={[{ value: "all", label: "All" }, { value: "ok", label: "Completed" }, { value: "failed", label: "Problems" }]} />
            <Select value={limit} onChange={setLimit} options={["50", "100", "250"].map((v) => ({ value: v, label: `last ${v}` }))} />
            <Button variant="ghost" onClick={load} aria-label="refresh"><RefreshCw size={14} /></Button>
          </div>
        }
      />

      {err && <Card><div className="text-sm text-bad">{err}</div></Card>}
      {!rows ? (
        <Skeleton className="h-72 w-full" />
      ) : visible.length === 0 ? (
        <Card>
          <EmptyState icon={ListTree} title="No ingestion events" hint="Send data via the Playground, a webhook, or the n8n node — every batch lands here." />
        </Card>
      ) : (
        <Card noPad className="overflow-hidden">
          <div className="grid grid-cols-[90px_1fr_90px_110px_170px] gap-2 border-b border-line px-5 py-2.5 text-[11px] font-medium uppercase tracking-wide text-muted max-md:grid-cols-[1fr_90px]">
            <span>ID</span><span>Source</span><span className="max-md:hidden">Records</span><span>Status</span><span className="max-md:hidden">When</span>
          </div>
          <div className="divide-y divide-[var(--border)]">
            {visible.map((r) => <Row key={r.id} r={r} />)}
          </div>
        </Card>
      )}
    </div>
  );
}

function Row({ r }: { r: HistoryRow }) {
  const [open, setOpen] = useState(false);
  const bad = r.status !== "completed" || !!r.error;
  return (
    <div className={bad ? "bg-[rgba(255,107,107,0.04)]" : ""}>
      <button className="grid w-full grid-cols-[90px_1fr_90px_110px_170px] items-center gap-2 px-5 py-3 text-left hover:bg-surface-2 max-md:grid-cols-[1fr_90px]" onClick={() => setOpen((o) => !o)}>
        <span className="num flex items-center gap-1.5 text-[12px] text-muted">
          {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />} #{r.id}
        </span>
        <span className="truncate text-sm text-body">{r.source}</span>
        <span className="num text-[13px] text-dim max-md:hidden">{r.records}</span>
        <span><Chip tone={bad ? "bad" : "ok"}>{r.error ? "error" : r.status}</Chip></span>
        <span className="num text-[11.5px] text-muted max-md:hidden">{new Date(r.created_at + "Z").toLocaleString()}</span>
      </button>
      {open && (
        <div className="space-y-3 px-5 pb-4">
          {r.error && <div className="rounded-xl border border-line bg-[rgba(255,107,107,0.06)] p-3 text-[13px] text-dim">{r.error}</div>}
          <JSONViewer data={{ ...r, payload: parsePayload(r) }} maxHeight={280} />
        </div>
      )}
    </div>
  );
}
