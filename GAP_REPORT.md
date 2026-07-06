# GAP_REPORT — StreamPulse (redesign v2 — 2026-07-06)

## 1. API inventory (api.py + store.py + pipeline/classifier.py, verified)

| Route | Notes |
|---|---|
| `GET /health` | `{status, service, version}` |
| `POST /ingest/json` `{records[], source}` | classifies each record (`{domain, confidence, method:"keyword"\|"llm"}` merged in), stores KPIs, appends ingestion_log, **broadcasts `{event:"ingest", source, records}` on WS**; returns `{source, records_in, records_inserted, log_id}` |
| `POST /ingest/csv` (file, source) | CSV → same path |
| `POST /ingest/email` (JSON payload) | one record from `subject` |
| `POST /webhook/{source}` | **requires HMAC** `X-Signature-256` (sha256 hex over raw body, secret = `WEBHOOK_SECRET`) |
| `POST /webhook/{source}/with-vision` | same + DocIntel `/classify-image` enrichment (`image_category`, `image_confidence`) |
| `GET /pipeline/status` | minimal: `{status, connected_clients}` |
| `GET /pipeline/history?limit=` | `{history: [{id, source, status, records, error, payload(JSON str), created_at, updated_at}]}` |
| `WS /live` | pushes ingest events; client must send occasional text (keepalive) |
| `GET /live/sse` | every 5s: `data: <recent-5 history JSON>` |

## 2. P0 mapping

- Live Operations: WS `/live` feed (real events incl. per-record domain/confidence/method),
  SSE fallback, counters derived client-side (events/min, session totals, domain
  distribution from streamed records). `pipeline/status` shows connected clients.
  Throughput/queue/backpressure widgets from the SPEC: **cut** (no backing fields).
- Events: `/pipeline/history` — expandable rows w/ payload JSON; status filter client-side.
  Note: history rows are ingestion-log entries (batch-level), not per-record — the UI
  labels them "ingestion events" honestly.
- Ingest Playground: `/ingest/json` + `/ingest/email` + `/ingest/csv` unsigned; webhook +
  with-vision tabs compute the real HMAC **in-browser via WebCrypto** from a user-pasted
  secret (never sent anywhere except as the signature header).
- Automation: REAL n8n assets exist — `connectors/n8n/n8n_node.json` + workflows
  `auction_aggregator.json`, `invoice_intake.json` → documentation cards + template
  download. No fake execution history.
- Classifier: factual page from eval/CLASSIFIER_BENCHMARK.md — keyword tier 0.083
  accuracy vs hybrid LLM escalation 1.000 on the 24-example keyword-poor set (with the
  benchmark's own honest caveats quoted).

## 3. Approved minor extensions — none (api.py: additive SPA-serving block only)

## 4. Verified claims

- Hybrid classification = keyword → LLM escalation (`method` field); BGE embedding tier
  is NOT in the current classify() path → decision-path viz shows keyword/llm only.
- DocIntel vision enrichment is real (`with-vision` composes `/classify-image`).
- Prefect flow exists (`orchestration/prefect_flow.py`) — mentioned as fact, no UI.

## 5. Real-vs-Demo

| Element | Source |
|---|---|
| Live feed, counters, domain donut | real WS/SSE events (session-derived aggregates) |
| Events table | real /pipeline/history |
| Playground | real POSTs (webhook signed in-browser) |
| Automation | real template files, download links; DemoBadge "runs on your n8n" |
| Classifier page | factual static, cited to eval/CLASSIFIER_BENCHMARK.md |
