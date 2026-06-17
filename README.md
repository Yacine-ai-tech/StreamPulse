# StreamPulse

[![CI](https://github.com/Yacine-ai-tech/StreamPulse/actions/workflows/ci.yml/badge.svg)](https://github.com/Yacine-ai-tech/StreamPulse/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Real-time business data pipeline. 6+ source types, live dashboard, first-class n8n integration.**

## What It Does

- **6 source types**: JSON, CSV, Gmail email, webhooks (HMAC-verified), Google Sheets, custom n8n
- **6-domain classifier**: keyword fast-path → embedding fallback → Claude Haiku zero-shot
- **`/webhook/{source}/with-vision`**: composes with DocIntel `/classify-image` for auction/inventory aggregation
- **Live dashboard** via WebSocket (`/live`) or Server-Sent Events (`/live/sse`)
- **n8n custom node + 3 importable workflows** in `connectors/n8n/`
- **Prefect 3 flow** for retried, scheduled execution in `orchestration/prefect_flow.py`
- **dlt declarative sources** for Gmail / Sheets / webhook in `ingestion/dlt_sources.py`

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn api:app --port 8004
```

## Supported Sources

| Source         | Endpoint                            | Notes                                       |
|----------------|-------------------------------------|---------------------------------------------|
| JSON           | POST /ingest/json                   | `{records: [...]}`                          |
| CSV            | POST /ingest/csv                    | multipart file upload                       |
| Gmail / Email  | POST /ingest/email                  | Gmail-style payload                         |
| Generic webhook| POST /webhook/{source}              | HMAC X-Signature-256 verified               |
| Vision webhook | POST /webhook/{source}/with-vision  | composes with DocIntel `/classify-image`    |
| n8n custom node| Webhook + signed body               | see `connectors/n8n/`                       |

## Architecture

```
   ┌─────────────┐
   │ Webhook/CSV │
   │ /JSON/Email │
   │  /n8n/dlt   │
   └──────┬──────┘
          ▼
   ┌──────────────┐    optional   ┌──────────────────┐
   │ Webhook      │──────────────▶│ DocIntel         │
   │ Receiver     │               │ /classify-image  │
   │ (HMAC verify)│◀──────────────│ (vision compose) │
   └──────┬───────┘               └──────────────────┘
          ▼
   ┌──────────────┐
   │  Classifier  │ ← keyword → embeddings → Claude Haiku
   │ (6 domains)  │
   └──────┬───────┘
          ▼
   ┌──────────────┐       ┌────────────────┐
   │  KPI Store   │──────▶│ Live Dashboard │
   │ (Postgres or │       │ WebSocket+SSE  │
   │  SQLite)     │       └────────────────┘
   └──────────────┘
```

## n8n Integration

```bash
# In n8n: Workflows → Import from File
ls connectors/n8n/workflows/
# auction_aggregator.json  invoice_intake.json  crm_sync.json
```

## License

MIT
