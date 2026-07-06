import { useState } from "react";
import { motion } from "framer-motion";
import { Send, AlertTriangle, FileUp, KeyRound } from "lucide-react";
import { PageHeader } from "../kit/AppShell";
import { Button, Card, Chip, EmptyState } from "../kit/primitives";
import { Label, Segmented } from "../kit/misc";
import { JSONViewer } from "../kit/JSONViewer";
import { api, IngestResult } from "../lib/api";

const SAMPLE_JSON = JSON.stringify(
  { records: [
      { metric: "revenue_q3", value: 487.6, unit: "MUSD", raw: "Q3 revenue up 18.7% YoY" },
      { metric: "uptime_july", value: 99.95, unit: "%", raw: "no incidents this week" },
  ]},
  null, 2,
);

const SAMPLE_EMAIL = JSON.stringify(
  { subject: "Q2 Forecast Update", from: "ap@acme.com", body: "Please find attached the latest revenue forecast for Q2..." },
  null, 2,
);

type Tab = "json" | "email" | "csv" | "webhook";

export default function Playground() {
  const [tab, setTab] = useState<Tab>("json");
  const [body, setBody] = useState(SAMPLE_JSON);
  const [source, setSource] = useState("playground");
  const [secret, setSecret] = useState("");
  const [vision, setVision] = useState(false);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [result, setResult] = useState<IngestResult | null>(null);

  const switchTab = (t: string) => {
    setTab(t as Tab);
    setResult(null); setErr("");
    if (t === "json") setBody(SAMPLE_JSON);
    if (t === "email") setBody(SAMPLE_EMAIL);
    if (t === "webhook") setBody(SAMPLE_JSON);
  };

  const run = async () => {
    setBusy(true); setErr(""); setResult(null);
    try {
      if (tab === "json") {
        const parsed = JSON.parse(body);
        setResult(await api.ingestJson(parsed.records ?? [parsed], source));
      } else if (tab === "email") {
        setResult(await api.ingestEmail(JSON.parse(body)));
      } else if (tab === "csv") {
        if (!csvFile) throw new Error("Choose a CSV file first");
        setResult(await api.ingestCsv(csvFile, source));
      } else {
        if (!secret) throw new Error("Webhook calls require the shared secret (HMAC X-Signature-256)");
        setResult(await api.webhook(source, body, secret, vision));
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  };

  return (
    <div>
      <PageHeader
        title="Ingest playground"
        sub="Send real payloads through every ingestion path. Keep Live Operations open in another tab — records arrive there the moment they're classified."
      />

      <div className="mb-4">
        <Segmented value={tab} onChange={switchTab}
          options={[
            { value: "json", label: "JSON" },
            { value: "email", label: "Email" },
            { value: "csv", label: "CSV" },
            { value: "webhook", label: "Webhook (signed)" },
          ]} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Request">
          <div className="space-y-4">
            {tab !== "email" && (
              <div>
                <Label>Source name</Label>
                <input value={source} onChange={(e) => setSource(e.target.value)}
                  className="w-full rounded-input border border-line-strong bg-surface-2 px-3 py-2 text-sm text-body outline-none focus:border-[var(--accent)]" />
              </div>
            )}
            {tab === "csv" ? (
              <div>
                <Label>CSV file</Label>
                <label className="flex cursor-pointer items-center gap-2 rounded-input border border-dashed border-line-strong px-3 py-3 text-sm text-dim hover:border-[var(--accent)]">
                  <FileUp size={15} /> {csvFile ? csvFile.name : "Choose a .csv file"}
                  <input type="file" accept=".csv" className="hidden" onChange={(e) => setCsvFile(e.target.files?.[0] ?? null)} />
                </label>
              </div>
            ) : (
              <div>
                <Label>{tab === "email" ? "Gmail-style payload" : "Payload"}</Label>
                <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={10}
                  className="num w-full rounded-input border border-line-strong bg-surface-2 px-3 py-2 font-mono text-[12px] leading-5 text-body outline-none focus:border-[var(--accent)]" />
              </div>
            )}
            {tab === "webhook" && (
              <>
                <div>
                  <Label>Shared secret (used in-browser to compute X-Signature-256 — never stored)</Label>
                  <div className="flex items-center gap-2">
                    <KeyRound size={15} className="shrink-0 text-muted" />
                    <input type="password" value={secret} onChange={(e) => setSecret(e.target.value)} placeholder="WEBHOOK_SECRET"
                      className="w-full rounded-input border border-line-strong bg-surface-2 px-3 py-2 text-sm text-body outline-none focus:border-[var(--accent)]" />
                  </div>
                </div>
                <label className="flex items-center gap-2 text-[13px] text-dim">
                  <input type="checkbox" checked={vision} onChange={(e) => setVision(e.target.checked)} className="accent-[var(--accent)]" />
                  Route through <code className="font-mono text-[12px]">/with-vision</code> — records with an <code className="font-mono text-[12px]">image_url</code> are enriched by DocIntel
                </label>
              </>
            )}
            <Button onClick={run} disabled={busy}>
              <Send size={14} /> {busy ? "Sending…" : "Send"}
            </Button>
          </div>
        </Card>

        <Card title="Response">
          {err ? (
            <div className="flex items-start gap-3"><AlertTriangle size={16} className="mt-0.5 shrink-0 text-bad" /><div className="text-[13px] text-dim">{err}</div></div>
          ) : !result ? (
            <EmptyState icon={Send} title="No request sent yet" hint="Pick a path, edit the sample payload and send. The response below is the platform's real answer." />
          ) : (
            <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="space-y-3">
              <div className="flex flex-wrap gap-1.5">
                <Chip tone="ok">ingested</Chip>
                <Chip className="num">{result.records_in} in</Chip>
                <Chip className="num">{result.records_inserted} inserted</Chip>
                <Chip className="num">log #{result.log_id}</Chip>
                <Chip>{result.source}</Chip>
              </div>
              <JSONViewer data={result} maxHeight={300} />
              <p className="text-[12.5px] text-muted">
                Check <strong className="text-dim">Live Operations</strong> — this batch was broadcast to every connected client, classified per record.
              </p>
            </motion.div>
          )}
        </Card>
      </div>
    </div>
  );
}
