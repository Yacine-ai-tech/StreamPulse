# StreamPulse n8n Integration

First-class n8n connector for StreamPulse.

## Importing Workflows

1. In n8n: **Workflows → Import from File**
2. Choose any of:
   - `workflows/auction_aggregator.json` — multi-source auction listing aggregator
   - `workflows/invoice_intake.json` — Gmail-attachment → DocIntel → StreamPulse pipeline
   - `workflows/crm_sync.json` — Sheet/CRM → KPI stream

## Custom Node

`n8n_node.json` defines the **StreamPulse Webhook** node — a one-step way to push records into StreamPulse with the correct HMAC signature.

## Webhook URL

Default: `POST http://your-host:8004/webhook/{source_name}`

Include header: `X-Signature-256: sha256=<HMAC of body using WEBHOOK_SECRET>`
