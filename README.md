# StreamPulse

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)


[![CI](https://github.com/Yacine-ai-tech/StreamPulse/actions/workflows/ci.yml/badge.svg)](https://github.com/Yacine-ai-tech/StreamPulse/actions/workflows/ci.yml) [![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)

**Real-time business data pipeline. 6+ source types, live dashboard, first-class n8n integration.**
> 🔗 **Live dashboard:** https://streampulse.ysiddo-ai-projects.app/  ·  live stream at `/live/sse`.
> On-demand backend (first request ~30–60 s to wake).
> Self-hosting: see [SELF_HOSTING.md](SELF_HOSTING.md).

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

## Tests

35 test functions across smoke, API, classifier, webhook, e2e, and exhaustive endpoint coverage:

```bash
pytest tests/ -q
```

## License

AGPL-3.0

## ⚖️ License & Enterprise Use (Dual-License)

This project is open-source under the **AGPL-3.0 License**. It is completely free for researchers, students, and open-source hobbyists.

> **Commercial Use:** The AGPLv3 license requires that any proprietary network service (SaaS, internal corporate tools) that uses or modifies this code must also open-source its entire backend. 
> 
> If you wish to use this framework in a closed-source commercial environment, or require **Enterprise features** (SSO, Active Directory, Custom VPC Deployment, Strict RBAC), you must obtain a **Commercial License**. 
> Please reach out to discuss commercial licensing and integration consulting.

## 📡 Anonymous Telemetry
This project collects anonymous, GDPR-compliant startup pings to help the author understand usage volume and prioritize development. 
* **What is collected:** A startup event timestamp and anonymized deployment origin. No API keys, no user prompts, and no sensitive application data is ever collected.
* **How to disable:** We respect your privacy and development environment. To opt-out, simply set `TELEMETRY_OPT_OUT=true` in your `.env` file.


<!-- Project Analytics -->
<img src="https://gateway.ysiddo-ai-projects.app/pixel/StreamPulse" width="1" height="1" style="display:none;" alt="">

## Licensing
This project is licensed under the [AGPL-3.0 License](LICENSE).

**Commercial Use:** If you wish to use this software commercially without releasing your own source code, please see [COMMERCIAL.md](COMMERCIAL.md) to obtain a commercial license.

**Telemetry:** See [TELEMETRY.md](TELEMETRY.md) for our privacy-first data practices.
