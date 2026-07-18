"""Phase-0 evidence report (STUDY_PATH_SCOPE_PLAN_SKETCH §9) over the ACCUMULATED shadow telemetry.

Complements scripts/scope_shadow_report.py (a current-state DB sweep): this reads the per-GENERATION history
the live hook appends to AZALEA_STUDY_PATH_SCOPE_TELEMETRY_PATH — including generations later overwritten —
and prints the §9 evidence tables the promotion decision reads:

  1. totals + diff-class / planning-status distributions (with a recent-window cut)
  2. SAME-GOAL STABILITY — the heavily-weighted §9 metric: for goals generated more than once, how stable are
     concept count, diff class, and planning status across runs?
  3. needs_review drill-down — which metric fields actually fire (topic_type diffs vs hard edges vs orphans…)
  4. rejected drill-down — failed invariants
  5. the LABELED_PAIRS baseline — the human-labeled hard-pair set incl. the known false-split
     (deterministic_today=False) cases the canonicalization metrics are measured against

Read-only: no DB, no writes, no LLM. Usage:
  python scripts/scope_phase0_report.py [--recent N] [--json]
"""
import argparse
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

for cand in (".env", "backend/.env"):
    if os.path.exists(cand):
        for line in open(cand, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

# The metric fields whose non-zero values EXPLAIN a needs_review classification (telemetry.ShadowMetrics).
_SIGNAL_FIELDS = (
    "concept_added_count", "concept_removed_count", "prereq_added_count", "prereq_removed_count",
    "order_pairwise_distance", "hard_edge_violation_count", "topic_type_diff_count",
    "orphan_concept_count", "unresolved_ambiguity_count", "semantic_repair_count",
)


def _norm_goal(goal: str) -> str:
    """Normalize a goal for same-goal grouping ('Want to learn about TCP Congestion Control' groups with
    'want to learn about tcp congestion control')."""
    return " ".join(re.findall(r"[a-z0-9]+", str(goal or "").lower()))


def load_rows(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def same_goal_stability(rows: list[dict]) -> list[dict]:
    """Per repeated goal: run count, distinct concept counts, diff-class mix, status mix. Stable = one concept
    count and every run `same`."""
    by_goal: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_goal[_norm_goal(r.get("goal", ""))].append(r)
    out = []
    for goal, rs in by_goal.items():
        if len(rs) < 2:
            continue
        counts = sorted({r.get("concept_count") for r in rs if r.get("concept_count") is not None})
        classes = Counter(r.get("diff_class") for r in rs)
        statuses = Counter(r.get("planning_status") for r in rs)
        out.append({
            "goal": goal, "runs": len(rs),
            "concept_counts": counts,
            "stable_concept_count": len(counts) <= 1,
            "diff_classes": dict(classes),
            "all_same": set(classes) == {"same"},
            "statuses": dict(statuses),
        })
    out.sort(key=lambda g: (-g["runs"], g["goal"]))
    return out


def needs_review_drilldown(rows: list[dict]) -> tuple[Counter, list[dict]]:
    """Which signal fields fire across needs_review rows, plus the row-level detail."""
    field_hits: Counter = Counter()
    detail = []
    for r in rows:
        if r.get("diff_class") != "needs_review":
            continue
        m = r.get("metrics") or {}
        firing = {k: m[k] for k in _SIGNAL_FIELDS if m.get(k)}
        if m.get("concept_overlap_ratio", 1.0) < 1.0:
            firing["concept_overlap_ratio"] = m["concept_overlap_ratio"]
        if m.get("order_exact_match", True) is False:
            firing["order_exact_match"] = False
        for k in firing:
            field_hits[k] += 1
        detail.append({"ts": (r.get("ts") or "")[:19], "goal": (r.get("goal") or "")[:48], "firing": firing})
    return field_hits, detail


def labeled_pairs_baseline() -> dict:
    """The human-labeled hard-pair set (imported as data, per §9 — thresholds are approved against THIS,
    never against shipped behavior)."""
    from app.tests.test_study_path_scope_labeled_pairs import LABELED_PAIRS
    labels = Counter(p["label"] for p in LABELED_PAIRS)
    gaps = [p["pair_id"] for p in LABELED_PAIRS if not p["deterministic_today"]]
    return {"pair_count": len(LABELED_PAIRS), "labels": dict(labels),
            "known_false_splits": gaps,
            "note": "known_false_splits = label says merge but the deterministic layer cannot see it yet; "
                    "the canonicalization false-split rate is measured against these."}


def build_report(rows: list[dict], recent: int) -> dict:
    recent_rows = rows[-recent:] if recent else rows
    field_hits, nr_detail = needs_review_drilldown(rows)
    stability = same_goal_stability(rows)
    return {
        "total_rows": len(rows),
        "diff_class_all": dict(Counter(r.get("diff_class") for r in rows)),
        "planning_status_all": dict(Counter(r.get("planning_status") for r in rows)),
        f"diff_class_recent_{len(recent_rows)}": dict(Counter(r.get("diff_class") for r in recent_rows)),
        "same_goal_stability": stability,
        "stability_summary": {
            "repeated_goals": len(stability),
            "stable_concept_count": sum(1 for g in stability if g["stable_concept_count"]),
            "all_runs_same_class": sum(1 for g in stability if g["all_same"]),
        },
        "needs_review_field_hits": dict(field_hits),
        "needs_review_rows": nr_detail,
        "rejected_rows": [{"ts": (r.get("ts") or "")[:19], "goal": (r.get("goal") or "")[:48],
                           "failed_invariants": r.get("failed_invariants")}
                          for r in rows if r.get("planning_status") == "rejected"],
        "labeled_pairs": labeled_pairs_baseline(),
    }


def print_report(rep: dict) -> None:
    print("=" * 78)
    print("PHASE-0 SHADOW EVIDENCE REPORT (§9)")
    print("=" * 78)
    print(f"rows: {rep['total_rows']}   diff_class: {rep['diff_class_all']}   "
          f"status: {rep['planning_status_all']}")
    recent_key = next(k for k in rep if k.startswith("diff_class_recent_"))
    print(f"recent window ({recent_key.rsplit('_', 1)[1]} rows): {rep[recent_key]}")

    s = rep["stability_summary"]
    print("\n--- SAME-GOAL STABILITY (the heavily-weighted §9 metric) " + "-" * 20)
    print(f"repeated goals: {s['repeated_goals']}   stable concept-count: {s['stable_concept_count']}   "
          f"all-runs-`same`: {s['all_runs_same_class']}")
    for g in rep["same_goal_stability"][:12]:
        flag = "  " if g["stable_concept_count"] else "⚠ "
        print(f"  {flag}{g['goal'][:52]!r}: runs={g['runs']} concept_counts={g['concept_counts']} "
              f"classes={g['diff_classes']}")

    print("\n--- needs_review DRILL-DOWN " + "-" * 49)
    print(f"firing fields: {rep['needs_review_field_hits']}")
    for d in rep["needs_review_rows"][:10]:
        print(f"  {d['ts']} {d['goal']!r}: {d['firing']}")

    print("\n--- REJECTED " + "-" * 64)
    for d in rep["rejected_rows"][:10]:
        print(f"  {d['ts']} {d['goal']!r}: {d['failed_invariants']}")
    if not rep["rejected_rows"]:
        print("  (none)")

    lp = rep["labeled_pairs"]
    print("\n--- LABELED PAIRS BASELINE " + "-" * 50)
    print(f"pairs: {lp['pair_count']}  labels: {lp['labels']}")
    print(f"known false-splits (canonicalization gap): {lp['known_false_splits']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--recent", type=int, default=50, help="recent-window size (default 50)")
    ap.add_argument("--json", action="store_true", help="emit the full report as JSON instead of text")
    args = ap.parse_args()

    path = os.getenv("AZALEA_STUDY_PATH_SCOPE_TELEMETRY_PATH", "").strip() or "telemetry/scope_shadow.jsonl"
    if not os.path.exists(path):
        print(f"no telemetry at {path!r} — set AZALEA_STUDY_PATH_SCOPE_TELEMETRY_PATH or generate paths first")
        sys.exit(1)
    rows = load_rows(path)
    rep = build_report(rows, args.recent)
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=1))
    else:
        print_report(rep)


if __name__ == "__main__":
    main()
