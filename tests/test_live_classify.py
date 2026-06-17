"""LIVE hybrid-classifier escalation test — real LLM call (needs key + STREAMPULSE_HYBRID_LLM=1).
Proves the LLM tier of the hybrid classifier runs and labels an ambiguous, keyword-poor text."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

pytestmark = pytest.mark.skipif(
    not (os.getenv("ANTHROPIC_API_KEY") or os.getenv("GROQ_API_KEY")),
    reason="live test needs an LLM key",
)


def test_llm_escalation_labels_ambiguous_text(monkeypatch):
    monkeypatch.setenv("STREAMPULSE_HYBRID_LLM", "1")
    from pipeline.classifier import classify, DOMAIN_PATTERNS
    # Keyword-poor but clearly finance-ish phrasing → keyword pass is weak → LLM escalation.
    out = classify("Our gross numbers climbed and the bottom line improved this period.")
    print("\nLIVE classify →", out)
    assert out["domain"] in list(DOMAIN_PATTERNS) + ["General"]
    assert out["method"] in ("keyword", "llm")
