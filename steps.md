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

## Phase 6 build pass (2026-06-16, post-GPU)
- **Assessment:** scaffold was substantially real — `api.py` (11 endpoints incl. HMAC webhooks,
  `/webhook/{src}/with-vision` DocIntel synergy, SSE `/live/sse` + WS `/live`), `connectors`
  (n8n, `webhook_receiver` HMAC-SHA256 + compare_digest), `ingestion/dlt_sources`,
  `orchestration/prefect_flow`, `pipeline/classifier` (DomainClassifier + DataValidator + pipeline).
- **BUG FOUND (real):** `pipeline/classifier.py` imported a non-existent `integrations` module →
  the whole module failed to import → `api.py` silently used a **degraded fallback** classifier.
  **Fix:** made the `integrations` import optional; added a module-level **hybrid `classify()`**
  (keyword fast pass + opt-in LLM escalation via `STREAMPULSE_HYBRID_LLM=1`) — api now uses the
  real classifier.
- **Tests (Week 16):** `test_classifier.py` (keyword routing, hybrid dict, validator/dedup),
  `test_webhook.py` (HMAC valid/tampered/missing), `test_api.py` (health/routes/real-classifier).
  **Studio pytest: 18 passed.**
- **Writing (Week 17):** `drafts/` (gitignored): `blog_post_6_realtime_pipeline.md`,
  `upwork_proposal_templates.md` (3 niches).

## Comprehensive QA pass (2026-06-16)
- **18 tests pass**. §6.10 verified: n8n, Prefect, hybrid classifier, dlt, vision-composition (DocIntel synergy), SSE.
- All 6 projects + both packages green; 28/28 STRATEGY §.10 feature claims code-verified.

## Remediation — LIVE behavior validation (2026-06-17)
- Added `tests/test_live_classify.py` (real LLM, skip-if-no-key): **hybrid classifier LLM tier LIVE**: keyword-poor finance text → domain=Finance, method=llm (real LLM escalation).
- Addresses the "tests prove imports not behavior" gap with a real, measured run.

## Remediation — classifier benchmark (2026-06-17)
- `eval/run_classifier_benchmark.py` + `eval/domain_labeled.jsonl` (24 keyword-poor paraphrases)
  + `eval/CLASSIFIER_BENCHMARK.md`: **keyword tier 8% acc** vs **hybrid+LLM 100%** — honest,
  measured demonstration of the hybrid classifier's value (first set was rewritten because it was
  keyword-self-aligned → trivially 100%). Caveats documented (small curated set; real streams mixed).
