"""
StreamPulse configuration — runtime settings loaded from environment variables.

All API keys and secrets must be supplied via environment variables.
Defaults are safe for local development; always override in production.
"""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)


class Settings:
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = os.getenv("LOG_FORMAT", "%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    LOGS_DIR = str(LOGS_DIR)

    POSTGRES_URL = os.getenv("POSTGRES_URL", "")
    LLM_DEFAULT = os.getenv("LLM_DEFAULT", "groq/openai/gpt-oss-120b")
    # Matches LLM_DEFAULT's provider rather than Anthropic -- keeps the classifier's
    # Tier-3 escalation on the same provider as the rest of the app by default, so a
    # fresh deploy doesn't depend on a second provider's account/credits being set up
    # separately. Override via LLM_JUDGE to point Tier 3 at a different model/provider.
    LLM_JUDGE = os.getenv("LLM_JUDGE", "groq/openai/gpt-oss-120b")

    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET") or __import__("secrets").token_hex(32)
    if os.getenv("ENV") == "production" and not os.getenv("WEBHOOK_SECRET"):
        raise ValueError("WEBHOOK_SECRET must be explicitly set in production")

    DOCINTEL_URL = os.getenv("DOCINTEL_URL", "http://localhost:8001")

    CORS_ALLOWED_ORIGINS = [
        o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "*").split(",")
        if o.strip()
    ]

    # ── n8n integration ───────────────
    # Note: These are for connecting TO an external n8n instance
    N8N_BASE_URL = os.getenv("N8N_BASE_URL", "")
    N8N_API_KEY = os.getenv("N8N_API_KEY", "")

    # ── Outbound Webhook Integration (e.g., to IntelAI) ───────────────
    EXTERNAL_WEBHOOK_URL = os.getenv("EXTERNAL_WEBHOOK_URL", "")
    EXTERNAL_WEBHOOK_SCHEMA_TYPE = os.getenv("EXTERNAL_WEBHOOK_SCHEMA_TYPE", "kpi_metrics")

    # ── Classifier Configuration ───────────────────────────────────────
    CLASSIFIER_KEYWORD_THRESHOLD = float(os.getenv("CLASSIFIER_KEYWORD_THRESHOLD", "0.7"))
    # Calibrated against eval/domain_calibration.jsonl (held out from the reported
    # benchmark set) via eval/calibrate_embedding_threshold.py: true-domain similarity
    # separated cleanly from competing domains across 0.05-0.50, degrading above 0.55.
    # Kept conservative (mid-range of the confirmed-safe zone rather than the sweep's
    # raw best-F1 value) since the shared embedding host's instability capped the
    # calibration sample size well below what would justify picking the extreme edge.
    CLASSIFIER_EMBEDDING_THRESHOLD = float(os.getenv("CLASSIFIER_EMBEDDING_THRESHOLD", "0.35"))
    CLASSIFIER_LLM_CONFIDENCE = float(os.getenv("CLASSIFIER_LLM_CONFIDENCE", "0.7"))
    CLASSIFIER_ENABLE_CACHE = os.getenv("CLASSIFIER_ENABLE_CACHE", "true").lower() in ("1", "true", "yes")
    STREAMPULSE_HYBRID_LLM = os.getenv("STREAMPULSE_HYBRID_LLM", "1")
    STREAMPULSE_EMBED_MODEL = os.getenv("STREAMPULSE_EMBED_MODEL", "BAAI/bge-m3")

    # ── Remote Inference (for memory-constrained environments) ─────────────
    # Fully env-driven, no hardcoded provider — set EMBEDDING_ENDPOINT + INFERENCE_TOKEN
    # to point at any generic embed host (self-hosted orchestrator, HF Inference API,
    # etc.), same pattern as IntelAI/RAGeval's EMBED_URL+INFERENCE_TOKEN. The previous
    # default silently pointed at https://api-inference.huggingface.co, a domain that
    # no longer resolves at all (HF retired it for router.huggingface.co) — confirmed
    # live, so this was failing outright with no visible error, not just unauthenticated.
    INFERENCE_MODE = os.getenv("INFERENCE_MODE", "remote").lower()
    EMBEDDING_ENDPOINT = os.getenv("EMBEDDING_ENDPOINT", "")
    INFERENCE_TOKEN = os.getenv("INFERENCE_TOKEN", os.getenv("HF_TOKEN", ""))

    # ── Storage Configuration ───────────────────────────────────────────
    ENABLE_PGVECTOR = os.getenv("ENABLE_PGVECTOR", "false").lower() in ("1", "true", "yes")
    ENABLE_DUCKDB = os.getenv("ENABLE_DUCKDB", "false").lower() in ("1", "true", "yes")
    DUCKDB_PATH = os.getenv("DUCKDB_PATH", "streampulse_analytics.duckdb")


settings = Settings()


# Gemini model fallback — when OPENAI_API_KEY is absent but GEMINI_API_KEY is
# present, any LLM model string referencing OpenAI/GPT is remapped to Gemini
# Flash automatically, requiring no code-level changes when switching providers.
def _apply_gemini_fallback():
    openai_key = getattr(settings, "OPENAI_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
    gemini_key = getattr(settings, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")

    if not openai_key and gemini_key:
        def fallback(model_str):
            if model_str and ("openai" in model_str.lower() or "gpt-" in model_str.lower()):
                return "gemini/gemini-2.5-flash"
            return model_str

        for attr in dir(settings):
            if attr.startswith("LLM_") and isinstance(getattr(settings, attr), str):
                setattr(settings, attr, fallback(getattr(settings, attr)))

        if hasattr(settings, "JUDGE_MODELS") and isinstance(settings.JUDGE_MODELS, list):
            settings.JUDGE_MODELS = [fallback(m) for m in settings.JUDGE_MODELS]


_apply_gemini_fallback()
