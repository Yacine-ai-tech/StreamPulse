# StreamPulse — STEPS LOG (living document)

> Continuous engineering log of **every** action on StreamPulse from Week 0 to now. Append newest
> at the bottom. Absolute dates. Branch model: feature branch → PR → merge into `develop`. Secrets
> live only in `.env`/`secrets.md` (gitignored) — never here.

## Project in one line
Real-time data pipeline: webhook ingestion (HMAC-verified), hybrid domain classification
(keyword → embedding → LLM), n8n + Prefect orchestration, dlt sources, SSE streaming, DocIntel
vision-composition synergy. SQLite (dev) / pgvector + DuckDB (advanced). Port 8004.

## Week 0 — scaffold & split (2026-05-20 → 06-05)
- `3fba7de` initial scaffold from the OmniIntelOS split (`api.py`, `store.py`, `core/`).
- `9751a0a` CI pytest; `8707f44` finalize Week 0 (STATUS gitignored); `52374f8`
  `docker-compose.dev.yml` for the Lightning Studio workflow.
- Status: **scaffold** — api + store wired, 1 smoke test, Phase 6 feature work pending.

## New-account Studio provisioning + .env hardening (2026-06-16)
- Cloned onto `upwork_new` Studio; `.env` recreated with real secrets (Anthropic, Groq),
  `WEBHOOK_SECRET` from `secrets.md`, `POSTGRES_URL` empty (SQLite default),
  `DOCINTEL_URL=http://localhost:8001` for the cross-service vision-composition synergy; synced
  local ↔ Studio. No GPU needed (pipeline + cloud LLM; embedding classifier runs on CPU).

## Current state
Scaffold + correct env. Phase 6 build (webhook HMAC verify, hybrid classifier, n8n custom node +
workflows, Prefect 3 orchestration, dlt sources, SSE) is the next major work per EXECUTION_PLAN.

---

## Next — industry & research-standard improvements (planned)
1. **Webhook security**: HMAC-SHA256 verification (constant-time compare) + replay protection;
   unit-test with signed fixtures.
2. **Hybrid domain classifier**: keyword → embedding (BGE) → LLM fallback; report accuracy on a
   labeled stream sample (route eval via RAGeval).
3. **Prefect 3 flow** + **dlt** declarative source (modern, research-strong pipeline patterns).
4. **Vision-composition webhook** → DocIntel `/classify-image` synergy (auction/inventory).
5. **SSE** streaming endpoint + backpressure; **DuckDB/pgvector** advanced storage toggle.
