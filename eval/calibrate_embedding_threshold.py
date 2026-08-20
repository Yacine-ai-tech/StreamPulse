"""Calibrate CLASSIFIER_EMBEDDING_THRESHOLD against a held-out calibration set.

Uses eval/domain_calibration.jsonl -- a set disjoint from eval/domain_labeled.jsonl
(the reported benchmark set) specifically so the threshold isn't tuned on the same
data the final benchmark numbers are measured on.

For each calibration example, computes the raw (unthresholded) embedding-tier
similarity score via pipeline.classifier.embedding_domain_match -- the exact same
scoring path production uses -- then sweeps candidate thresholds and reports the one
that maximizes macro-F1 on this calibration set.

Usage: python eval/calibrate_embedding_threshold.py
Needs: scikit-learn (metrics), and the same EMBEDDING_ENDPOINT/INFERENCE_TOKEN
production uses (set via env or .env).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    from sklearn.metrics import f1_score
    from pipeline.classifier import embedding_domain_match

    rows = [json.loads(l) for l in open(ROOT / "eval" / "domain_calibration.jsonl") if l.strip()]

    y_true = []
    raw_scores = []  # (predicted_domain, score) per example, unthresholded
    print(f"Scoring {len(rows)} calibration examples against the embedding tier...")
    for i, r in enumerate(rows):
        match = embedding_domain_match(r["text"])
        if match is None:
            print(f"  [{i+1}/{len(rows)}] embed call failed for: {r['text'][:50]!r} -- skipping")
            continue
        domain, score, _ = match
        y_true.append(r["domain"])
        raw_scores.append((domain, score))
        print(f"  [{i+1}/{len(rows)}] true={r['domain']:10s} predicted={domain:10s} score={score:.3f}")
        # Small stagger between calls -- avoids hammering the shared embedding host
        # in a tight loop, which is itself a contributor to spurious failures.
        time.sleep(0.5)

    if not raw_scores:
        print("No successful embedding calls -- cannot calibrate. Is the embedding host reachable?")
        sys.exit(1)

    print(f"\n{len(raw_scores)}/{len(rows)} calibration examples scored successfully.\n")

    best_threshold = None
    best_f1 = -1.0
    print(f"{'threshold':>10} | {'macro-F1':>9} | accuracy")
    print("-" * 40)
    for step in range(5, 96, 5):  # 0.05 .. 0.95
        threshold = step / 100.0
        y_pred = [domain if score >= threshold else "General" for domain, score in raw_scores]
        f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
        acc = sum(1 for t, p in zip(y_true, y_pred) if t == p) / len(y_true)
        marker = ""
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = threshold
            marker = "  <-- best so far"
        print(f"{threshold:>10.2f} | {f1:>9.3f} | {acc:.3f}{marker}")

    print(f"\nRecommended CLASSIFIER_EMBEDDING_THRESHOLD = {best_threshold} (macro-F1={best_f1:.3f} on calibration set)")


if __name__ == "__main__":
    main()
