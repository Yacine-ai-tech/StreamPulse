# Self-Hosting StreamPulse

1. **Docker:** Standalone `docker-compose` setup.
2. **n8n Config:** Ensure n8n is running and point the webhook to `/webhook`.
3. **Security:** Export `WEBHOOK_SECRET` in both StreamPulse `.env` and n8n environment to secure events.

## Environment Variables (`.env`)
You should create a `.env` file based on `.env.example`. Make sure to set the following:

- `POSTGRES_URL`: Connection string for PostgreSQL KPI store.
- `LLM_DEFAULT` & `LLM_JUDGE`: LiteLLM-compatible model names (e.g. `your-preferred-model`).
- API Keys: Provide the corresponding API keys for your models (e.g. `API_KEY` for litellm proxy, etc.).
- `WEBHOOK_SECRET`: Used to secure incoming webhook calls via HMAC.
- `DOCINTEL_URL`: Base URL for DocIntel vision enrichment.
- `CORS_ALLOWED_ORIGINS`: Comma-separated list of allowed origins.
- `TELEMETRY_OPT_OUT`: Set to `true` to opt out of anonymous telemetry.
- `N8N_BASE_URL` & `N8N_API_KEY`: n8n connection details (auto-provisioned).
- `GOOGLE_CLIENT_ID` & `GOOGLE_CLIENT_SECRET`: For Gmail ingestion.
- `CLICKUP_API_KEY` & `CLICKUP_WORKSPACE_ID`: For ClickUp integration.
