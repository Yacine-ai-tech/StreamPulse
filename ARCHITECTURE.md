# StreamPulse — Complete Architecture Reference

Generated from a direct read of the current codebase and live verification
against a real running backend + built frontend (not from docs, not from
memory) on 2026-08-11. Everything below is either verified against source
and a real run, or explicitly marked as unverified/known drift.

---

## 1. Frontend — all 11 pages

Routed in `frontend/src/App.tsx`, shared shell in `frontend/src/kit/AppShell.tsx`.

| Route | Component | What it does |
|---|---|---|
| `/` | `Live.tsx` | Live Operations — WebSocket feed of every record ingested anywhere, already classified; records/min, session records, connected-clients counters; domain-distribution chart |
| `/events` | `Events.tsx` | The persisted pipeline log (`sp_ingestion_log`) — one row per ingestion batch, filterable by status, with replay |
| `/playground` | `Playground.tsx` | Manually fire JSON/CSV/webhook/email test payloads at the real backend |
| `/sources` | `Sources.tsx` | Every source that has delivered data, activity aggregated from the persistent ingestion log |
| `/destinations` | `Destinations.tsx` | Every classified record is delivered to all three destinations (Postgres, WebSocket, SSE) simultaneously |
| `/analytics` | `Analytics.tsx` | Operational counters from the persistent store — records stored, ingestion events, routing success, records-by-source chart |
| `/alerts` | `Alerts.tsx` | Ingestion events that did not complete cleanly, straight from the pipeline log |
| `/automation` | `Automation.tsx` | n8n integration surface — custom node + 5 importable workflow templates |
| `/classifier` | `Classifier.tsx` | Hybrid classification explainer + live try-it against the real classifier |
| `/api-docs` | `ApiDocs.tsx` | Static, hand-written API reference — 17 endpoints across 6 categories, curl/Python/Node snippets, kept in sync with the real backend this session |
| `/user-guide` | `UserGuidePage.tsx` | Usage guide |
| `*` (catch-all) | → `Live.tsx` | Unmatched client-side routes redirect to Live Operations |

---

## 2. Backend — all API endpoints (`api.py`)

**17 application routes** across 6 categories (verified against `ApiDocs.tsx`'s `ENDPOINTS` array, which derives its displayed count from `ENDPOINTS.length` rather than a hardcoded number, so it can't drift again).

### General
| Method | Path | Notes |
|---|---|---|
| GET | `/` | Serves the SPA (`frontend/dist/index.html`) if built, else a JSON pointer |
| GET | `/health` | DB connectivity check, cached 10s |
| GET | `/{full_path:path}` | SPA-fallback catch-all (added this session) — serves real static files from `frontend/dist/` if they exist, else `index.html`. Declared last so every route above still wins |

### Ingestion
| Method | Path | Notes |
|---|---|---|
| POST | `/ingest/json` | `{records:[...], source}` — the funnel every other ingestion path routes through |
| POST | `/ingest/csv` | multipart file upload |
| POST | `/ingest/email` | Gmail-style payload |

### Webhooks
| Method | Path | Notes |
|---|---|---|
| POST | `/webhook/{source_name}` | HMAC-SHA256 verified (`X-Signature-256`) |
| POST | `/webhook/{source_name}/with-vision` | Composes with DocIntel's real `/classify-image` for auction/inventory aggregation |

### Pipeline
| Method | Path | Notes |
|---|---|---|
| GET | `/pipeline/status` | Live counters — connected clients + aggregate stats from the store |
| POST | `/pipeline/replay/{log_id}` | Re-ingests a stored payload through classification again; session-ownership enforced |
| GET | `/pipeline/history` | Last N processed records |

### Live Streaming
| Method | Path | Notes |
|---|---|---|
| WS | `/live` | Broadcasts classified records in real time |
| GET | `/live/sse` | Server-Sent Events fallback, 5s poll |

### Analytics
| Method | Path | Notes |
|---|---|---|
| GET | `/analytics/cache-stats` | Classifier content-hash cache hit/miss rate |
| GET | `/analytics/storage-stats` | pgvector + DuckDB introspection (`{"storage_available": false}` unless those optional backends are enabled) |
| GET | `/analytics/domain-summary` | DuckDB rollup, requires `ENABLE_DUCKDB=true` |
| GET | `/analytics/classification-trends` | DuckDB method-mix-over-time, requires `ENABLE_DUCKDB=true` |
| POST | `/analytics/refresh` | Force DuckDB re-sync from Postgres |

**UI reachability**: every endpoint above is either driving a page directly, or is an intentionally backend-only ops/introspection route (the 5 `/analytics/*` endpoints have no dedicated UI widget — `cache-stats`/`storage-stats` are diagnostic, `domain-summary`/`classification-trends`/`refresh` require `ENABLE_DUCKDB=true`, off by default). All 5 are documented in `/api-docs` regardless.

---

## 3. All features

- **6 source types**: JSON, CSV, email, generic HMAC-signed webhook, vision-composing webhook, n8n custom node
- **3-tier hybrid classifier**: keyword (⩾0.7 confidence, <1ms) → BGE-large embedding similarity (⩾0.5, local model) → Claude Haiku zero-shot (Gemini Flash fallback if no Anthropic key) — every tier's outcome is tagged in the stored record's `method` field, nothing is hidden
- **Two-layer caching**: in-memory content-hash cache (per-process) + optional persistent pgvector cache (`ENABLE_PGVECTOR=true`) — wired into the classifier this session; previously present in code but never actually called
- **Live dashboard** over WebSocket or SSE, dual transport for firewall compatibility
- **n8n first-class integration**: custom "StreamPulse Ingest" node + 5 importable workflow templates (`auction_aggregator`, `invoice_intake`, `crm_sync`, `uptime_alert`, `master_trigger`)
- **Prefect 3 flow** (`orchestration/prefect_flow.py`) for retried/scheduled execution as an alternative to n8n
- **dlt declarative sources** (`ingestion/dlt_sources.py`) for Gmail/Sheets/webhook — incremental loading, schema evolution
- **Optional advanced storage**: pgvector embedding cache, DuckDB analytics engine — both fully functional as of this session (see §8)
- **Vision composition**: `/webhook/{source}/with-vision` calls DocIntel's real `/classify-image` to classify photo + text together (auction listings, invoice intake)
- **Demo-session isolation**: anonymous visitors' test traffic through the UI is scoped to their browser session; real external webhooks/n8n/CRM sources stay globally visible (the point of a public ingestion demo)
- **Anonymous opt-out telemetry** (`TELEMETRY_OPT_OUT=true` to disable)

---

## 4. Providers

| Layer | Provider | Configurable via |
|---|---|---|
| Fast classification | Keyword matching (160+ keywords, 6 domains) | n/a, always-on |
| Embedding | `sentence-transformers`, `BAAI/bge-large-en-v1.5` default | `STREAMPULSE_EMBED_MODEL` |
| LLM escalation | Claude Haiku 4.5 (`LLM_JUDGE`), Gemini 2.5 Flash fallback | `LLM_JUDGE`, auto-fallback if only `GEMINI_API_KEY` set |
| Multi-provider abstraction | LiteLLM | `LLM_DEFAULT`, `LLM_JUDGE` |

---

## 5. Local vs. remote — the configuration model

The embedding model (Tier 2) runs **locally in-process** via `sentence-transformers` — no forced cloud provider, no hardcoded remote endpoint. `STREAMPULSE_EMBED_MODEL` is a plain HuggingFace model name; swapping it doesn't touch code. This satisfies the portfolio-wide "never assume a cloud provider is the only option for GPU/compute-heavy work" constraint: CPU-only environments work (as this session's sandbox proved — no GPU, model ran fine, just slower on first load), and the same code path would pick up a GPU automatically if one were present.

The LLM tier is the only genuinely remote-only piece (Claude/Gemini API calls) — by design, since local LLM inference isn't in StreamPulse's scope the way local embeddings are; LiteLLM's multi-provider abstraction is the configurability lever there.

---

## 6. STRATEGY.md compliance vs. drift

Cross-referenced against `global_docs/STRATEGY.md` §6 (StreamPulse) and §6.10 (2026 stack upgrade).

| STRATEGY.md ask | Status |
|---|---|
| 6 source types (JSON/CSV/email/webhook/Sheets/n8n) | ✅ Done — Sheets via `dlt_sources.py`'s `gsheet_source()`, not a dedicated REST endpoint (OAuth-gated, self-serve) |
| Hybrid classifier (keyword→embedding→LLM, cached) | ✅ Done — was silently broken (Tier 2 imported a module that never existed anywhere in the repo, every non-confident classification skipped straight to the LLM tier); fixed and verified this session |
| n8n custom node + workflows | ✅ Done — node + 5 workflow JSONs |
| Prefect 3 flow | ✅ Done |
| dlt declarative sources | ✅ Done |
| Vision-compose webhook (DocIntel synergy) | ✅ Done — verified against DocIntel's actual current `/classify-image` code, not assumed |
| SSE as WebSocket alternative | ✅ Done |
| pgvector + DuckDB storage | ✅ Done — both were present but non-functional (7 distinct DuckDB bugs, 1 pgvector JSON bug + zero wiring to the classifier); fully fixed and verified end-to-end this session, including a real cross-database import from the live Postgres |
| Multi-provider LLM (no hardcoded provider) | ✅ Done — LiteLLM + Gemini auto-fallback |
| Standalone / no sibling hardcoding | ✅ Done — `.env.example` uses placeholder URLs, `DOCINTEL_URL` is configurable, StreamPulse now has its own dedicated Neon database (was sharing one Neon project with 7 sibling services; split apart this session, see §8) |
| Local-vs-remote GPU configurability | ✅ Done — see §5 |

**No remaining STRATEGY.md drift** for StreamPulse as of this pass.

---

## 7. Cross-project integration

**Direction**: StreamPulse → DocIntel (StreamPulse calls out, DocIntel doesn't know StreamPulse exists). `POST /webhook/{source}/with-vision` sends `file` + `categories` (comma-separated) to `DOCINTEL_URL/classify-image`, expects back `{category, confidence, reasoning}` — verified field-for-field against DocIntel's real `services/vision_extractor.py`.

**Hidden auth layer found and fixed**: DocIntel's internal-token middleware exempted `/classify`, `/extract`, `/process`, `/batch/upload` by exact path but not `/classify-image` — harmless only because `REQUIRE_INTERNAL_TOKEN` defaults `false` there. Fixed on both sides: added `/classify-image` to DocIntel's exempt list, and StreamPulse now sends `X-OmniIntel-Internal-Token` on the outbound call when `OMNIINTEL_INTERNAL_TOKEN` is set locally, so the integration survives either service tightening its auth independently.

---

## 8. What's unverified / known limitations (be honest about this before relying on it)

**Full production-topology deep test performed this session**: `frontend/`
built for real (`npm run build`), backend run exactly as `Dockerfile`'s
`CMD` does (`uvicorn api:app --workers 1`), same origin, no dev proxy.
Every page hit directly (hard navigation, not client-side routing) with
zero console errors and zero failed requests. This is what caught the
SPA-routing bug below — dev mode's Vite server has its own history
fallback that masked it completely.

**Real bugs found and fixed this session** (all live-verified after fixing, not just code-reviewed):
1. `@app.middleware("http")` (compiles to `BaseHTTPMiddleware`) sat in front of `/live/sse`'s `StreamingResponse` — hung indefinitely on client disconnect (Starlette's known task-bridging issue). Rewrote as pure ASGI middleware.
2. Tier 2 classifier imported `services/inference_adapter`, a module that never existed anywhere in this repo. Every non-confident classification silently skipped to the LLM tier. Implemented the embed step locally via `sentence-transformers`.
3. Default embedding model was `bge-m3`, contradicting STRATEGY.md's explicit `bge-large-en-v1.5` spec and requiring an uncached multi-GB download on first use.
4. DuckDB analytics engine: invalid `JSONB` type (Postgres-only, not DuckDB), nested aggregates, Postgres-only `pg_database_size()`, wrong table name (`kpi_metrics` vs `sp_kpi_metrics`), TEXT/TIMESTAMP cast mismatch, missing UNIQUE constraint, positional column misalignment. All 7 fixed; verified via a real cross-database import against the live Postgres.
5. pgvector cache: `json.loads()` called on values psycopg3 already deserializes from JSONB — crashed every cache hit. Fixed, and wired into the classifier (it worked in isolation but nothing ever called it before this session).
6. Vite dev proxy defaulted to port 8000; this project's actual dev port is 8004 everywhere else (README, Dockerfile, `docker-compose.dev.yml`) — broke `/pipeline/*`, `/live`, `/live/sse` in dev mode out of the box.
7. `/analytics` path collision — my own first fix for #6 (proxying `/analytics`) collided with the frontend's own `/analytics` SPA route on a hard refresh. Fixed with a trailing-slash-scoped proxy path.
8. Missing SPA catch-all — only `/` served `index.html`; every other route (and any hard refresh) 404'd against the real production server. Same bug found and fixed in DocIntel and RAGeval (both share the same pattern).
9. `sp_kpi_metrics.source` was always `NULL` for records whose individual payload didn't carry its own `source` field — the batch-level `ingest_json` source wasn't propagated down. Fixed; now the default unless a record specifies its own.

**Database**: StreamPulse now has its own dedicated Neon project (`streampulse-production`), not shared with any sibling service. Real production data (59+ KPI records, 39+ ingestion log rows at time of migration) was migrated with verified row-count parity, live Render deployment repointed and confirmed healthy, and the old shared logical database dropped only after re-checking for cutover-window drift.

**Failure paths deliberately tested live, not just unit-tested**:
- Wrong/missing HMAC signature on `/webhook/*` → clean `401 {"detail": "invalid_signature"}`, verified against the running server with a real correct-signature control case for comparison.
- LLM tier (Tier 3) with deliberately invalid `ANTHROPIC_API_KEY`/`GEMINI_API_KEY` → a real `litellm.AuthenticationError` from Anthropic's actual API, logged, and a graceful fallback to the keyword-tier result — no crash, no fake success.

**Genuinely unverified**:
- The Prefect 3 flow (`orchestration/prefect_flow.py`) has not been run against a real Prefect server this session — it's structurally correct by construction but not execution-verified.
- `ingestion/dlt_sources.py`'s `gmail_source()`/`gsheet_source()` require a real `token.json` OAuth credential this environment doesn't have — not exercised against real Gmail/Sheets data.
- n8n workflow templates (`connectors/n8n/workflows/*.json`) have not been imported into a live n8n instance and run this session — they're valid JSON matching n8n's node schema, but the actual automation behavior when imported hasn't been observed.

---

## 9. Portfolio integration points

- **DocIntel**: consumer, see §7.
- **n8n**: StreamPulse ships importable workflow templates and a custom node for n8n to call *into* StreamPulse's webhook endpoints — StreamPulse doesn't call out to n8n.
- **orchestrator**: no direct code-level integration found or built this session — StreamPulse doesn't currently call the orchestrator's Lightning Studio proxy for anything (it has no GPU-heavy inference step that would need it; the embedding tier runs locally per §5).
