# StreamPulse

[![CI](https://github.com/Yacine-ai-tech/StreamPulse/actions/workflows/ci.yml/badge.svg)](https://github.com/Yacine-ai-tech/StreamPulse/actions/workflows/ci.yml) [![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)

**A real-time business data pipeline.** Six source types, a hybrid classification cascade, a
live dashboard, and first-class n8n integration.

**Live dashboard:** https://streampulse.ysiddo-ai-projects.app/ — live stream at `/live/sse`.
Self-hosting instructions: [SELF_HOSTING.md](SELF_HOSTING.md).

## What It Does

- **Six source types**: JSON, CSV, Gmail email, HMAC-verified webhooks, Google Sheets, and
  custom n8n integration.
- **Hybrid, six-domain classifier**: a keyword fast path, an embedding fallback, and Claude
  Haiku zero-shot classification as a last resort, with content-hash caching.
- **`/webhook/{source}/with-vision`**: composes with DocIntel's `/classify-image` for
  auction-listing and inventory aggregation.
- **Live dashboard** via WebSocket (`/live`) or Server-Sent Events (`/live/sse`).
- **An n8n custom node plus 5 importable workflows** in `connectors/n8n/`.
- **A Prefect 3 flow** for retried, scheduled execution in `orchestration/prefect_flow.py`.
- **dlt declarative sources** for Gmail, Sheets, and webhook ingestion in
  `ingestion/dlt_sources.py`. `run_webhook_pipeline()` runs the webhook source through a real
  dlt pipeline with merge-based incremental loading, deduplicated by a content-hash primary
  key — the one source needing no external OAuth credential, and the one with a runnable
  end-to-end test (`tests/test_dlt_sources.py`, DuckDB destination by default; pass
  `destination="postgres"` for production). `gmail_source`/`gsheet_source` need a `token.json`
  this repo does not ship, and degrade to an empty generator without one.
- **Storage**: pgvector for an embedding cache, DuckDB for analytics queries (both optional).
- **Multi-provider LLM routing** via LiteLLM, with configurable classification thresholds.

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn api:app --port 8004
```

## Supported Sources

| Source | Endpoint | Notes |
|--------|----------|-------|
| JSON | POST /ingest/json | `{records: [...]}` |
| CSV | POST /ingest/csv | Multipart file upload |
| Gmail / Email | POST /ingest/email | Gmail-style payload |
| Generic webhook | POST /webhook/{source} | HMAC `X-Signature-256` verified |
| Vision webhook | POST /webhook/{source}/with-vision | Composes with DocIntel `/classify-image` |
| n8n custom node | Webhook with a signed body | See `connectors/n8n/` |

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
   │ (with cache) │
   └──────┬───────┘
          ▼
   ┌──────────────┐       ┌────────────────┐
   │  KPI Store   │──────▶│ Live Dashboard │
   │ (Postgres/   │       │ WebSocket+SSE  │
   │  SQLite)     │       └────────────────┘
   └──────┬───────┘               ▲
          │                        │
          └───────────────────────┘
         (optional: pgvector cache + DuckDB analytics)
```

## n8n Integration

```bash
# In n8n: Workflows → Import from File
ls connectors/n8n/workflows/
# auction_aggregator.json — multi-source auction-listing aggregator
# invoice_intake.json     — Gmail attachment → DocIntel → StreamPulse pipeline
# crm_sync.json           — Sheet/CRM → KPI stream synchronization
# uptime_alert.json       — scheduled uptime check → email alert
# master_trigger.json     — scheduled harness exercising the other workflows
```

## Tests

35 test functions across smoke, API, classifier, webhook, end-to-end, and exhaustive endpoint
coverage:

```bash
pytest tests/ -q
```

## Research Contribution

StreamPulse applies the language-model-cascade pattern (Dohan et al., 2022) to real-time event
classification:

- **Hybrid classification cascade**: keyword matching, dense embedding similarity, and
  zero-shot LLM classification as a last resort, with content-hash caching to avoid
  reclassifying identical payloads.
- **Batched, non-blocking ingestion**: measured 0.00% error rate on a 1,000-request concurrent
  burst against the current deployment, after moving database writes off the request's event
  loop and batching inserts (see `eval/THROUGHPUT_BENCHMARK.md`).
- **Empirical comparison of classification tiers**: keyword, embedding, and LLM accuracy and
  latency measured independently on the same evaluation set.

For the full literature context and honest assessment of novelty, see [RESEARCH.md](RESEARCH.md).

## Benchmark Reproduction Suite

```bash
python3 eval/run_benchmarks.py --seed 42
```

## Anonymous Telemetry

On startup, a background thread sends one HTTP POST, at most once per six hours per running
instance: `{"service": "StreamPulse", "event": "startup", "instance_id": "<random
identifier>"}` — no document content, filenames, extraction results, API keys, IP addresses,
or configuration is included. The instance identifier is randomly generated, not derived from
any hardware identifier, and persisted to `logs/.telemetry_instance_id`; delete that file to
reset it. Destination defaults to `TELEMETRY_URL`, an adoption-tracking endpoint used to count
distinct installs, the same way many open-source CLIs report anonymous install counts.
`TELEMETRY_OPT_OUT=true` disables it outright, or `TELEMETRY_URL` can be repointed to a
different collector or a local no-op.

## License

Open-source under the AGPL-3.0 License, free for researchers, students, and open-source
projects. A commercial license is available for closed-source or enterprise use — see
[COMMERCIAL.md](COMMERCIAL.md).

![telemetry](https://gateway.ysiddo-ai-projects.app/pixel.png)
