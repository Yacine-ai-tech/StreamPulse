# StreamPulse Architecture

How StreamPulse turns raw events from many sources into classified, stored and streamed KPI
records. This page complements [`README.md`](README.md) (what it is and how to run it),
[`RESEARCH.md`](RESEARCH.md) (why a tiered classifier) and [`BENCHMARK.md`](BENCHMARK.md)
(measured accuracy and throughput). An interactive version is in the dashboard under
**Architecture**.

## 1. System overview

```
 sources ──▶ ingestion API ──▶ classification cascade ──▶ store ──▶ live feed
 (JSON, CSV, e-mail,          keyword → embedding → LLM   (SQL)     (WebSocket, SSE,
  signed webhooks, n8n)             │                                 Redis/Kafka)
                                    └── cache                          └─▶ outbound webhook
```

## 2. Components

| Component | Role |
|---|---|
| Ingestion API | JSON, CSV, e-mail payloads, signed webhooks, webhook-with-vision |
| Webhook receiver | HMAC-SHA256 verification (constant-time) and payload normalisation |
| Classifier | three-tier cascade with a content-hash cache and a persistent vector cache |
| Domain packs | taxonomy as data: `{domain: [prototype phrases]}`, swapped without code changes |
| Store | KPI metrics and an ingestion log; SQLite locally, Postgres in production |
| Live fan-out | WebSocket and SSE feeds, optional Redis or Kafka for several nodes |
| Outbound webhook | forwards enriched records to a configured destination |
| Analytics | optional DuckDB aggregations for trends and domain summaries |
| Orchestration | optional Prefect flow and dlt sources for scheduled pulls |
| Dashboard | live operations, events, playground, sources, destinations, analytics, alerts, classifier |

## 3. The classification cascade

| Tier | How | Commits when | Cost |
|---|---|---|---|
| Cache | content hash lookup (memory, optional pgvector) | hit | none |
| 1 Keyword | pattern hits per domain; confidence 0.4 + 0.2 per hit | confidence ≥ keyword threshold | sub-millisecond |
| 2 Embedding | cosine similarity to prototype phrases per domain (multilingual model) | similarity ≥ embedding threshold | one embedding call |
| 3 LLM | zero-shot label from the domain list | valid label returned | one model call |

Each record carries the `method` that decided it, so quality and cost can be audited. A record that
no tier can settle keeps its keyword result and is not cached, so a provider outage cannot poison
the cache. Thresholds are calibrated on held-out data: set above the highest observed
confident-but-wrong embedding score, because deferring to the LLM is safer than a wrong
confident answer.

Embedding calls go to a local model or a remote embedding endpoint (`INFERENCE_MODE`). A remote host
that is still starting is polled within a time budget; definitive client errors fail fast.

## 4. Life of an ingest request

1. Authenticate: a visitor session header, an internal token, or a valid webhook signature.
2. Record the ingestion (status `running`).
3. Classify every record concurrently; blocking work runs on a sized worker pool.
4. Persist KPI metrics, then mark the ingestion `completed` (or `failed` with the error).
5. Broadcast to live subscribers of the owning session, and to other nodes through the broker.
6. Forward to the outbound webhook, if configured.
7. Respond with counts, per-domain totals and per-record method and confidence.

## 5. Design decisions

| Decision | Reason |
|---|---|
| Cheapest tier first | most real rows carry a clear keyword; the expensive tiers run only when needed |
| Taxonomy as data | new domains need a JSON pack, not a deployment |
| Calibrated, not maximal, thresholds | wrong-but-confident answers are worse than a deferred one |
| Per-record `method` | every decision is explainable and measurable |
| Session-scoped live feeds | anonymous visitors only see events they produced; signed integrations are global |
| Optional heavy components | pgvector, DuckDB, Redis/Kafka, Prefect and dlt stay off unless configured |
| Outbound token isolation | the service's own token is never forwarded to third-party destinations |

## 6. Interfaces

| Route | Purpose |
|---|---|
| `POST /ingest/json`, `/ingest/csv`, `/ingest/email` | ingest records |
| `POST /webhook/{source}`, `/webhook/{source}/with-vision` | signed webhooks |
| `GET /pipeline/status`, `/pipeline/history`; `POST /pipeline/replay/{id}` | pipeline state and replay |
| `WS /live`, `GET /live/sse` | live event feed |
| `GET /analytics/*`; `POST /analytics/refresh` | aggregations |
| `GET /health`, `GET /ready` | liveness; readiness (classifier warm) |

## 7. Configuration

Everything is environment-driven; [`.env.example`](.env.example) lists every variable with its
purpose. Groups: classifier thresholds and models, inference endpoint and wake budget, storage
(`POSTGRES_URL`, `ENABLE_PGVECTOR`, `ENABLE_DUCKDB`), broker, webhook secret and integrations,
access (`REQUIRE_INTERNAL_TOKEN`, `CORS_ALLOWED_ORIGINS`, `DEMO_SESSION_SCOPING`), telemetry.

## 8. Startup and readiness

On start the classifier imports its heavy dependencies and embeds the domain prototypes in the
background. `/ready` returns 503 `warming_up` until that completes; route traffic only after it
returns 200. Until then the keyword tier and the LLM tier already answer requests.

## 9. Privacy

An optional startup ping carries only service name, version and a random installation id; disable
it with `TELEMETRY_OPT_OUT=true` or `DO_NOT_TRACK=1`. Event payloads and credentials never leave the
deployment except to destinations you configure.
