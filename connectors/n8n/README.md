# StreamPulse n8n Integration

First-class n8n connector for StreamPulse.

## Importing Workflows

1. In n8n: **Workflows → Import from File**
2. Choose any of:
   - `workflows/auction_aggregator.json` — multi-source auction listing aggregator
   - `workflows/invoice_intake.json` — Gmail-attachment → DocIntel → StreamPulse pipeline
   - `workflows/crm_sync.json` — Sheet/CRM → KPI stream
   - `workflows/uptime_alert.json` — scheduled uptime check → email alert
   - `workflows/master_trigger.json` — scheduled harness that exercises the others

**Before running an imported workflow**, replace the placeholder URLs/emails baked into
its HTTP Request and Send Email nodes (e.g. `https://your-streampulse-instance.example.com`,
`https://your-docintel-instance.example.com`, `alerts@your-domain.example.com`) with your
own deployment's actual host and addresses. These are static JSON templates — they can't
read environment variables at import/runtime, so there's no env var to set instead; edit
the node parameters directly in the n8n UI (or in the JSON before importing).

## Custom Node

`n8n_node.json` defines the **StreamPulse Webhook** node — a one-step way to push records into StreamPulse with the correct HMAC signature.

## Webhook URL

Default: `POST http://your-host:8004/webhook/{source_name}`

Include header: `X-Signature-256: sha256=<HMAC of body using WEBHOOK_SECRET>`
