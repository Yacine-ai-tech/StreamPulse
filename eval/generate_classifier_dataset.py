"""Generate a large (N>=500), balanced, synthetic labeled dataset for the domain classifier
benchmark — the original eval/domain_labeled.jsonl only has 48 hand-curated examples (8 per
domain), too small for a statistically credible accuracy/macro-F1 number.

Template + slot-filling generation (subject x metric x direction x magnitude x tone), not an
LLM call — deterministic, free, and reproducible. Real diversity comes from combinatorics
across independently-varied slots per domain (not just swapping one number in one template),
and results are deduplicated by exact text before writing.

Usage:  python eval/generate_classifier_dataset.py --n-per-domain 84
Output: eval/domain_labeled_500.jsonl  (gitignored size aside, reproducible from this script)
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent / "domain_labeled_500.jsonl"

# Independently-varied slots per domain, combined via templates below. Vocabulary extends
# pipeline/classifier.py's DOMAIN_PROTOTYPES with concrete subjects/metrics so generated
# sentences read like real SaaS telemetry commentary, not keyword soup.
DOMAIN_SLOTS = {
    "Finance": {
        "subjects": ["quarterly revenue", "gross margin", "EBITDA", "operating cash flow",
                     "the AR aging balance", "our burn rate", "net income", "the cost of goods sold",
                     "free cash flow", "deferred revenue", "the accounts payable backlog"],
        "verbs_up": ["climbed", "grew", "improved", "came in ahead of forecast", "rebounded"],
        "verbs_down": ["slipped", "missed target", "came in below plan", "tightened", "contracted"],
        "magnitudes": ["by 4%", "by 11%", "by 18%", "modestly", "sharply", "for the third straight month"],
        "tail": ["compared to last quarter.", "against the board's forecast.",
                 "after the pricing change took effect.", "heading into year-end.",
                 "once the new billing system reconciled."],
    },
    "Operations": {
        "subjects": ["warehouse throughput", "the packing line", "on-time delivery", "inventory turns",
                     "the supplier lead time", "defect rate", "manufacturing yield", "fulfillment cost per order",
                     "the conveyor uptime", "cycle time"],
        "verbs_up": ["improved", "sped up", "stabilized", "recovered", "hit a new high"],
        "verbs_down": ["slowed", "backed up", "fell behind schedule", "was disrupted", "missed SLA"],
        "magnitudes": ["by 9%", "by 22%", "for two shifts in a row", "across three warehouses",
                        "after the new supplier came online"],
        "tail": ["after the layout change.", "during the peak shipping window.",
                  "once the new scanner rollout finished.", "after a machine went down for maintenance.",
                  "as order volume spiked."],
    },
    "Growth": {
        "subjects": ["new signups", "trial-to-paid conversion", "monthly active users", "churn",
                     "net revenue retention", "the sales pipeline", "expansion MRR",
                     "customer acquisition cost", "the referral rate", "activation rate"],
        "verbs_up": ["accelerated", "picked up", "beat plan", "trended upward", "hit a record"],
        "verbs_down": ["stalled", "dropped off", "fell short", "cooled off", "underperformed"],
        "magnitudes": ["by 6%", "by 15%", "well above target", "for the second month running",
                        "after the campaign launched"],
        "tail": ["after the new pricing tier launched.", "following the product-led growth push.",
                  "once the onboarding flow was redesigned.", "in the enterprise segment.",
                  "across self-serve signups."],
    },
    "People": {
        "subjects": ["employee turnover", "headcount", "time-to-hire", "engagement scores",
                     "the retention rate", "internal promotions", "sick leave usage",
                     "the hiring pipeline", "manager span of control", "onboarding completion"],
        "verbs_up": ["improved", "rose", "strengthened", "held steady above target", "trended up"],
        "verbs_down": ["worsened", "ticked up unexpectedly", "fell", "slipped below target", "declined"],
        "magnitudes": ["by 3 points", "by 12%", "across engineering", "company-wide",
                        "in the support org"],
        "tail": ["after the new benefits rollout.", "following the reorg.",
                  "once the hybrid policy took effect.", "in the last engagement survey.",
                  "heading into the next review cycle."],
    },
    "ESG": {
        "subjects": ["Scope 2 carbon emissions", "board diversity", "the sustainability score",
                     "renewable energy usage", "waste diverted from landfill", "supplier code-of-conduct audits",
                     "water usage per facility", "the governance rating", "workplace safety incidents"],
        "verbs_up": ["improved", "decreased", "was reduced", "trended favorably", "hit a new target"],
        "verbs_down": ["increased", "missed the reduction target", "regressed", "stalled",
                       "raised concern with the board"],
        "magnitudes": ["by 8%", "by 20%", "ahead of the 2027 target", "across all facilities",
                        "for the third audit cycle"],
        "tail": ["after the solar rollout at two sites.", "per the annual ESG report.",
                  "following the new supplier vetting process.", "in this year's disclosure.",
                  "after the safety training program launched."],
    },
    "IT_Ops": {
        "subjects": ["service uptime", "P95 API latency", "the incident count", "deployment frequency",
                     "mean time to recovery", "error budget burn", "the on-call page volume",
                     "database replication lag", "CDN cache hit rate"],
        "verbs_up": ["improved", "held at 99.9%+", "dropped", "sped up", "stabilized"],
        "verbs_down": ["degraded", "spiked", "breached SLA", "slowed", "triggered a page"],
        "magnitudes": ["by 30ms", "for 20 minutes", "during the release window", "across two regions",
                        "after the config change"],
        "tail": ["after the autoscaling change.", "during last night's deploy.",
                  "following the database migration.", "on the primary API cluster.",
                  "after the CDN provider incident."],
    },
}

TEMPLATES = [
    "{subject} {verb} {magnitude} {tail}",
    "We noticed {subject} {verb} {magnitude} {tail}",
    "This week, {subject} {verb} {magnitude} {tail}",
    "The team flagged that {subject} {verb} {magnitude} {tail}",
]


def generate(n_per_domain: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    rows: list[dict] = []
    seen: set[str] = set()
    for domain, slots in DOMAIN_SLOTS.items():
        made = 0
        attempts = 0
        while made < n_per_domain and attempts < n_per_domain * 20:
            attempts += 1
            subject = rng.choice(slots["subjects"])
            up = rng.random() > 0.5
            verb = rng.choice(slots["verbs_up"] if up else slots["verbs_down"])
            magnitude = rng.choice(slots["magnitudes"])
            tail = rng.choice(slots["tail"])
            template = rng.choice(TEMPLATES)
            text = template.format(subject=subject, verb=verb, magnitude=magnitude, tail=tail)
            text = text[0].upper() + text[1:]
            if text in seen:
                continue
            seen.add(text)
            rows.append({"text": text, "domain": domain})
            made += 1
    rng.shuffle(rows)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-per-domain", type=int, default=84,
                     help="6 domains x 84 = 504 rows (N>=500 target)")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    rows = generate(a.n_per_domain, a.seed)
    with open(OUT, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"Wrote {len(rows)} rows ({a.n_per_domain}/domain x {len(DOMAIN_SLOTS)} domains) to {OUT}")


if __name__ == "__main__":
    main()
