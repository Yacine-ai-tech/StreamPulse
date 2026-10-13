# StreamPulse n8n Integration Guide

## Overview

This directory holds the public integration layer for connecting StreamPulse to n8n: workflow
templates, a property schema for the ingest step, and documentation. Everything is meant to be
copied into your own n8n instance and adapted. No credential or host name is included.

## What is included

### 1. Property schema (`n8n_node.json`)
Describes the fields an ingest step needs (method, URL, body parameters). It is not an
installable community node; in n8n, use the built-in **HTTP Request** node.

### 2. Workflow templates (`workflows/`)

- **`auction_aggregator.json`**: multi-source auction listing aggregation
- **`invoice_intake.json`**: Gmail attachment, DocIntel extraction, then StreamPulse
- **`crm_sync.json`**: sheet or CRM rows pushed to a KPI stream
- **`uptime_alert.json`**: scheduled uptime check with an e-mail alert
- **`master_trigger.json`**: scheduled harness that exercises the other workflows

### 3. Python client (`../n8n.py`)
A small client for calling an n8n instance from StreamPulse. It takes its URL and API key from
configuration.

## Using the templates

1. Import a template (Workflows → Import from File).
2. Replace the placeholder host names and addresses in the HTTP Request and Send Email nodes.
3. Create the credentials the nodes ask for in n8n (see [README.md](README.md)); the templates
   reference credentials by name and contain no secret values.
4. Activate the workflow.

## StreamPulse endpoints used by the templates

### Ingestion
- `POST /webhook/{source_name}`: generic webhook receiver; verifies the `X-Signature-256`
  header (HMAC-SHA256 of the raw body with `WEBHOOK_SECRET`)
- `POST /webhook/{source_name}/with-vision`: webhook that also runs DocIntel vision extraction
- `POST /ingest/json`: direct JSON ingestion
- `POST /ingest/csv`: CSV file upload
- `POST /ingest/email`: e-mail style payload

### Reading
- `GET /pipeline/status` and `GET /pipeline/history`: pipeline state and recent runs
- `GET /live/sse` and the `/live` WebSocket: real-time record stream
- `GET /analytics/domain-summary` and `GET /analytics/classification-trends`: aggregates

## Security notes

- Use HTTPS endpoints in production.
- Keep webhook secrets and tokens in n8n credentials, not in workflow JSON that you commit.
- Authenticate service-to-service calls with the internal token credential described in the README.

## Contributing

When adding a template:
1. Keep it generic and reusable.
2. Reference credentials by name; never include values.
3. Document what the workflow does and which credentials it needs.
4. Test it on a current n8n release.
