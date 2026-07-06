import { Download, Workflow, Boxes, ReceiptText } from "lucide-react";
import { PageHeader } from "../kit/AppShell";
import { Card, Chip, DemoBadge } from "../kit/primitives";

/* Real repo assets (verified): connectors/n8n/n8n_node.json and two workflow templates.
   These are served by the backend repo itself on GitHub — download links point there.
   No fake execution history: templates run on YOUR n8n instance. */

const GH = "https://github.com/Yacine-ai-tech/StreamPulse/blob/master/connectors/n8n";

const ITEMS = [
  {
    icon: Boxes,
    title: "StreamPulse n8n node",
    file: "n8n_node.json",
    desc: "Custom n8n node that posts records into /ingest/json with source attribution — drop it into any workflow to make StreamPulse the destination.",
    tag: "node",
  },
  {
    icon: Workflow,
    title: "Auction aggregation",
    file: "workflows/auction_aggregator.json",
    desc: "End-to-end template: watch a webhook for auction listings, enrich image-bearing items via the /with-vision route (DocIntel), and land classified records in the pipeline.",
    tag: "workflow",
  },
  {
    icon: ReceiptText,
    title: "Invoice intake",
    file: "workflows/invoice_intake.json",
    desc: "Template for accounts-payable intake: email-in invoices are normalized and ingested with Finance-domain classification for downstream syncing.",
    tag: "workflow",
  },
];

export default function Automation() {
  return (
    <div>
      <PageHeader
        title="Automation"
        sub="First-class n8n integration — a custom node plus ready-to-import workflow templates that make StreamPulse the intelligent destination for automated data."
        actions={<DemoBadge label="templates run on your n8n" />}
      />
      <div className="grid gap-4 lg:grid-cols-3">
        {ITEMS.map((it) => (
          <Card key={it.file} hover>
            <div className="flex items-center justify-between">
              <it.icon size={20} style={{ color: "var(--accent)" }} strokeWidth={1.6} />
              <Chip>{it.tag}</Chip>
            </div>
            <div className="mt-3 text-[15px] font-semibold text-body">{it.title}</div>
            <div className="num mt-0.5 font-mono text-[11px] text-muted">connectors/n8n/{it.file}</div>
            <p className="mt-3 min-h-[88px] text-[13px] leading-6 text-dim">{it.desc}</p>
            <a
              className="mt-2 inline-flex items-center gap-1.5 text-[13px] font-medium underline decoration-dotted text-dim hover:text-body"
              href={`${GH}/${it.file}`}
              target="_blank"
              rel="noreferrer"
            >
              <Download size={13} /> View template on GitHub
            </a>
          </Card>
        ))}
      </div>
      <Card title="How it fits" className="mt-5">
        <p className="text-[13px] leading-6 text-dim">
          n8n handles the orchestration; StreamPulse is the intelligence layer. Workflows deliver raw
          events to <code className="font-mono text-[12px]">/webhook/&#123;source&#125;</code> (HMAC-signed) or{" "}
          <code className="font-mono text-[12px]">/ingest/json</code>; every record is classified
          (keyword → LLM escalation), optionally vision-enriched by DocIntel, stored, and broadcast to
          the Live Operations stream. A Prefect flow (<code className="font-mono text-[12px]">orchestration/prefect_flow.py</code>)
          covers scheduled batch pulls on the same path.
        </p>
      </Card>
    </div>
  );
}
