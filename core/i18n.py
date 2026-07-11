"""
Minimal i18n shim for StreamPulse.

The n8n connector uses I18N.lang() to pick between en/fr description strings.
This module reads the LANG env var (e.g. "fr", "en", "fr_FR") and returns
the 2-letter language code, defaulting to "en".
"""
from __future__ import annotations
import os
from typing import Any

_TRANSLATIONS: dict[str, dict[str, str]] = {}


class I18N:
    @staticmethod
    def lang() -> str:
        """Return the active 2-letter language code (en / fr)."""
        raw = os.getenv("LANG", os.getenv("LANGUAGE", "en")).lower()
        code = raw.split("_")[0].split(".")[0]
        return code if code in ("en", "fr") else "en"

    @staticmethod
    def t(key: str, **kwargs: Any) -> str:
        lang = I18N.lang()
        tmap = _TRANSLATIONS.get(lang, _TRANSLATIONS.get("en", {}))
        template = tmap.get(key, key)
        return template.format(**kwargs) if kwargs else template


def t(key: str, **kwargs: Any) -> str:
    """Module-level shorthand for I18N.t()."""
    return I18N.t(key, **kwargs)
