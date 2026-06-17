"""Domain-classifier benchmark — accuracy + macro-F1 on a curated, balanced labeled set
(eval/domain_labeled.jsonl, 30 examples across the 6 domains). Reports the fast keyword tier and
(with STREAMPULSE_HYBRID_LLM=1 + a key) the LLM-escalation tier.

Usage:  python eval/run_classifier_benchmark.py            # keyword tier
        STREAMPULSE_HYBRID_LLM=1 python eval/run_classifier_benchmark.py   # + LLM escalation
Needs:  scikit-learn (metrics).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    from sklearn.metrics import accuracy_score, classification_report, f1_score
    from pipeline.classifier import classify

    rows = [json.loads(l) for l in open(ROOT / "eval" / "domain_labeled.jsonl") if l.strip()]
    y_true = [r["domain"] for r in rows]
    y_pred = [classify(r["text"])["domain"] for r in rows]

    acc = accuracy_score(y_true, y_pred)
    macro_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
    print(f"\nStreamPulse domain classifier — {len(rows)} labeled examples (6 domains)")
    print(f"  accuracy : {acc:.3f}")
    print(f"  macro-F1 : {macro_f1:.3f}")
    print("\n" + classification_report(y_true, y_pred, zero_division=0))


if __name__ == "__main__":
    main()
