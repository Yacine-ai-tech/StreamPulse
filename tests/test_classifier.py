"""DomainClassifier + hybrid classify + DataValidator tests (pure, offline)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.classifier import DataValidator, DomainClassifier, classify  # noqa: E402


def test_keyword_classification_finance():
    domain, conf = DomainClassifier.classify("Q2 revenue and ebitda vs budget forecast")
    assert domain == "Finance" and conf > 0


def test_classify_module_returns_dict():
    # Dense enough in People keywords (7 matches / confidence=0.7) to clear
    # CLASSIFIER_KEYWORD_THRESHOLD on Tier 1 alone, keeping this test offline
    # (no embedding model load, no LLM call) per the module docstring.
    out = classify("headcount turnover engagement salary training recruitment retention")
    assert out["domain"] == "People"
    assert 0 <= out["confidence"] <= 1
    assert out["method"] == "keyword"


def test_classify_unknown_is_general():
    out = classify("the weather is nice today")
    assert out["domain"] == "General"


def test_validate_numeric_strips_symbols():
    ok, val = DataValidator.validate_numeric("$1,234.50")
    assert ok and val == 1234.50
    ok2, _ = DataValidator.validate_numeric("not-a-number")
    assert not ok2


def test_deduplicate():
    from pipeline.classifier import DataRecord
    r = lambda: DataRecord("webhook", "Finance", "revenue", 1.0, "2026-01-01", {})
    out = DataValidator.deduplicate([r(), r()])
    assert len(out) == 1
