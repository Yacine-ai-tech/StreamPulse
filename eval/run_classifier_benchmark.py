"""Domain-classifier benchmark — accuracy + macro-F1 on a labeled set. Defaults to the large
synthetic set (eval/domain_labeled_500.jsonl, 504 examples, N>=500 target — generate it first
with `python eval/generate_classifier_dataset.py`); pass --dataset to use the original small
curated set (eval/domain_labeled.jsonl, 48 examples) instead. Reports the fast keyword tier and
(with STREAMPULSE_HYBRID_LLM=1 + a key) the LLM-escalation tier.

Usage:  python eval/run_classifier_benchmark.py --samples 500       # keyword tier, N>=500
        STREAMPULSE_HYBRID_LLM=1 python eval/run_classifier_benchmark.py    # + LLM escalation
Needs:  scikit-learn (metrics).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

DEFAULT_DATASET = ROOT / "eval" / "domain_labeled_500.jsonl"
DEFAULT_CACHE_FILE = ROOT / "eval" / "cache" / "classifier_benchmark_cache.jsonl"


def _load_cache(cache_file: Path) -> dict:
    done: dict = {}
    if not cache_file.exists():
        return done
    with cache_file.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "idx" in d:
                done[d["idx"]] = d
    return done


def _append_cache(cache_file: Path, record: dict) -> None:
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    with cache_file.open("a") as fh:
        fh.write(json.dumps(record) + "\n")


def main():
    from sklearn.metrics import accuracy_score, classification_report, f1_score
    from pipeline.classifier import classify

    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=DEFAULT_DATASET,
                     help=f"Labeled JSONL set (default: {DEFAULT_DATASET.name}, N>=500)")
    ap.add_argument("--samples", type=int, default=0, help="cap the dataset to this many rows (0 = all)")
    ap.add_argument("--cache-file", type=Path, default=DEFAULT_CACHE_FILE,
                     help="Path to .jsonl cache file for resumption after interruption")
    ap.add_argument("--reset-cache", action="store_true")
    args = ap.parse_args()

    if not args.dataset.exists() and args.dataset == DEFAULT_DATASET:
        print(f"{args.dataset} not found — generating it now (python eval/generate_classifier_dataset.py)...")
        from generate_classifier_dataset import generate
        with open(args.dataset, "w") as f:
            for r in generate(n_per_domain=84, seed=42):
                f.write(json.dumps(r) + "\n")

    if args.reset_cache and args.cache_file.exists():
        args.cache_file.unlink()

    rows = [json.loads(l) for l in open(args.dataset) if l.strip()]
    if args.samples:
        rows = rows[: args.samples]

    done_cache = _load_cache(args.cache_file)
    if done_cache:
        print(f"Cache: {args.cache_file} ({len(done_cache)}/{len(rows)} already classified, resuming)")

    y_true = [r["domain"] for r in rows]
    y_pred = []
    for i, r in enumerate(rows):
        cached = done_cache.get(i)
        if cached is not None:
            y_pred.append(cached["pred"])
            continue
        pred = classify(r["text"])["domain"]
        y_pred.append(pred)
        _append_cache(args.cache_file, {"idx": i, "pred": pred})
        # Small stagger between examples -- the embedding/LLM tiers call a shared
        # remote host; firing many requests back-to-back is itself a source of
        # contention-driven failures independent of the host's baseline reliability.
        time.sleep(0.5)

    acc = accuracy_score(y_true, y_pred)
    macro_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
    print(f"\nStreamPulse domain classifier — {len(rows)} labeled examples (6 domains)")
    print(f"  accuracy : {acc:.3f}")
    print(f"  macro-F1 : {macro_f1:.3f}")
    print("\n" + classification_report(y_true, y_pred, zero_division=0))


if __name__ == "__main__":
    main()
