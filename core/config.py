"""Slim StreamPulse configuration."""
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
    LLM_DEFAULT = os.getenv("LLM_DEFAULT", "groq/llama-3.3-70b-versatile")
    LLM_JUDGE = os.getenv("LLM_JUDGE", "anthropic/claude-haiku-4-5")

    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
    if not WEBHOOK_SECRET and os.getenv("ENV") == "production":
        raise ValueError("WEBHOOK_SECRET must be set in production")

    DOCINTEL_URL = os.getenv("DOCINTEL_URL", "https://docintel-f4g1.onrender.com")

    CORS_ALLOWED_ORIGINS = [
        o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "*").split(",")
        if o.strip()
    ]

    # ── n8n integration ───────────────────────────────────────────────
    N8N_BASE_URL  = os.getenv("N8N_BASE_URL", "")
    N8N_API_KEY   = os.getenv("N8N_API_KEY", "")

    # ── Outbound Webhook Integration (e.g., to IntelAI) ───────────────
    EXTERNAL_WEBHOOK_URL = os.getenv("EXTERNAL_WEBHOOK_URL", "")
    EXTERNAL_WEBHOOK_SCHEMA_TYPE = os.getenv("EXTERNAL_WEBHOOK_SCHEMA_TYPE", "kpi_metrics")

    # ── Google OAuth2 (Sheets / Drive / Gmail) ────────────────────────
    GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GMAIL_PRIMARY        = os.getenv("GMAIL_PRIMARY", "")
    DRIVE_ACCOUNT        = os.getenv("DRIVE_ACCOUNT", "")
    GSHEETS_ACCOUNT      = os.getenv("GSHEETS_ACCOUNT", "")

    # ── ClickUp ───────────────────────────────────────────────────────
    CLICKUP_API_KEY       = os.getenv("CLICKUP_API_KEY", "")
    CLICKUP_WORKSPACE_ID  = os.getenv("CLICKUP_WORKSPACE_ID", "")


settings = Settings()
