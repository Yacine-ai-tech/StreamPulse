"""Calibrate CLASSIFIER_EMBEDDING_THRESHOLD against a held-out calibration set.

Uses eval/domain_calibration.jsonl -- a set disjoint from eval/domain_labeled.jsonl
(the reported benchmark set) specifically so the threshold isn't tuned on the same
data the final benchmark numbers are measured on.

For each calibration example, computes the raw (unthresholded) embedding-tier
similarity score via pipeline.classifier.embedding_domain_match -- the exact same
scoring path production uses -- then sweeps candidate thresholds and reports the one
that maximizes macro-F1 on this calibration set.

Usage: python eval/calibrate_embedding_threshold.py
Needs: scikit-learn (metrics), and the same EMBEDDING_ENDPOINT/EMBED_TOKEN
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

    # A below-threshold example does NOT get predicted "General" in the real cascade --
    # it defers to Tier 3 (LLM), a generally strong fallback. So the metric that matters
    # here isn't accuracy/F1 as if "General" were the fallback label (that trivially
    # rewards a low threshold, since it never penalizes accepting a wrong match instead
    # of deferring). What matters is: of the examples Tier 2 is confident enough to
    # answer at each threshold (the "accepted set"), what fraction does it get right
    # (precision)? A threshold should be chosen high enough that the accepted set's
    # precision is trustworthy -- errors there are Tier 2 confidently overriding a tier
    # (LLM) that would likely have been correct, which is strictly worse than deferring.
    print(f"{'threshold':>10} | {'accepted':>8} | {'correct':>7} | precision")
    print("-" * 48)
    best_threshold = None
    for step in range(5, 96, 5):  # 0.05 .. 0.95
        threshold = step / 100.0
        accepted = [(d, t) for (d, s), t in zip(raw_scores, y_true) if s >= threshold]
        n = len(accepted)
        correct = sum(1 for d, t in accepted if d == t)
        precision = correct / n if n else float("nan")
        marker = ""
        # First threshold (scanning upward) where every accepted example in this small
        # calibration sample is correct -- a necessary, not sufficient, bar; still
        # cross-check against a larger/live sample before trusting it blindly.
        if best_threshold is None and n > 0 and correct == n:
            best_threshold = threshold
            marker = "  <-- first perfect-precision threshold"
        print(f"{threshold:>10.2f} | {n:>8d} | {correct:>7d} | {precision:.3f}{marker}" if n else
              f"{threshold:>10.2f} | {n:>8d} | {correct:>7d} |    n/a")

    if best_threshold is not None:
        print(f"\nRecommended CLASSIFIER_EMBEDDING_THRESHOLD = {best_threshold} "
              f"(first threshold with 100% precision on the accepted set)")
    else:
        print("\nNo threshold in the sweep reached 100% precision on the accepted set -- "
              "the domain prototypes likely need improving, not just the threshold.")


if __name__ == "__main__":
    main()
