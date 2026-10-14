# Self-Hosting StreamPulse

1. **Docker:** Run the standalone `docker-compose` setup.
2. **n8n:** Make sure n8n is running and point its webhook node at StreamPulse's `/webhook` endpoint.
3. **Security:** Set the same `WEBHOOK_SECRET` in the StreamPulse `.env` and in the n8n environment so events are signed and verified.

## Environment Variables (`.env`)
You should create a `.env` file based on `.env.example`. Make sure to set the following:

Every variable is described in [`.env.example`](.env.example). The main ones:

- `POSTGRES_URL`: Connection string for PostgreSQL KPI store (SQLite when empty).
- `LLM_DEFAULT` & `LLM_JUDGE`: LiteLLM model identifiers in `provider/model` form.
- Provider API keys for the models you reference (see `.env.example` for the variable names).
- `WEBHOOK_SECRET`: Used to secure incoming webhook calls via HMAC.
- `DOCINTEL_URL`: Base URL for DocIntel vision enrichment.
- `CORS_ALLOWED_ORIGINS`: Comma-separated list of allowed origins.
- `TELEMETRY_OPT_OUT`: Set to `true` to disable the anonymous startup ping (see the README for exactly what it contains).
- `N8N_BASE_URL` & `N8N_API_KEY`: n8n connection details (auto-provisioned).

## Embeddings and readiness

Tier 2 of the classifier needs an embedding backend. Set `INFERENCE_MODE=remote` with
`EMBEDDING_ENDPOINT` and `EMBED_TOKEN` to share one embedding service between several
applications, or `INFERENCE_MODE=local` to load `STREAMPULSE_EMBED_MODEL` in the process.

On start the classifier loads its dependencies and embeds the domain prototypes in the
background. `GET /ready` returns 503 `warming_up` until that completes and 200 afterwards; gate
traffic on `/ready` (`/health` is a liveness probe). The keyword and LLM tiers answer requests
while the embedding tier is still warming.
