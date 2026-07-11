"""Collect + summarize StudyPathScope shadow data (STUDY_PATH_SCOPE_SPEC §10).

Runs the shadow diff over every study path in the DB (read-only), writes each as a JSONL row to the telemetry
sink (AZALEA_STUDY_PATH_SCOPE_TELEMETRY_PATH), and prints a summary: diff-class distribution, planning-status
distribution, and any paths whose plan the validator would REJECT or where the scope diverges from the
pipeline (the load-bearing signals). Also folds in any rows the live hook already accumulated.

Usage:  python scripts/scope_shadow_report.py
"""
import io
import json
import os
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

for cand in (".env", "backend/.env"):
    if not os.getenv("DATABASE_URL") and os.path.exists(cand):
        for line in open(cand, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

import app.db.base as base
from app.db.database import SessionLocal
from app.services.scope_shadow import shadow_report

TELE = os.getenv("AZALEA_STUDY_PATH_SCOPE_TELEMETRY_PATH", "").strip()

db = SessionLocal()
paths = db.query(base.StudyPath).order_by(base.StudyPath.created_at.desc()).all()

diff_classes: Counter = Counter()
statuses: Counter = Counter()
rejected: list[tuple] = []
diverged: list[tuple] = []
rows: list[dict] = []

for sp in paths:
    topics = sorted(sp.topics, key=lambda t: t.order_index or 0)
    if not topics:
        continue
    try:
        r = shadow_report(sp.goal or "", sp.domain or "unknown", topics,
                          source_revision=sp.active_generation_id or "")
    except Exception as exc:  # noqa: BLE001
        print(f"  ! shadow failed for {sp.id}: {exc}")
        continue
    diff_classes[r["diff_class"]] += 1
    statuses[r["planning_status"]] += 1
    rows.append({"goal": (sp.goal or "")[:50], "domain": sp.domain, **r})
    if r["planning_status"] == "rejected":
        rejected.append((sp.goal, r["failed_invariants"]))
    if r["diff_class"] not in ("same",) or r["metrics"]["hard_edge_violation_count"] > 0:
        diverged.append((sp.goal, r["diff_class"], r["metrics"]))

print(f"Paths analyzed: {len(rows)}  (domains: {dict(Counter(sp.domain for sp in paths if sp.topics))})")
print(f"diff_class:       {dict(diff_classes)}")
print(f"planning_status:  {dict(statuses)}")
print(f"REJECTED plans:   {len(rejected)}")
for goal, inv in rejected[:10]:
    print(f"   - {goal!r}: {inv}")
print(f"DIVERGED (scope != pipeline or hard-edge violation): {len(diverged)}")
for goal, dc, m in diverged[:10]:
    print(f"   - {goal!r}: {dc}  hard_edge_viol={m['hard_edge_violation_count']} "
          f"concept_add/rem={m['concept_added_count']}/{m['concept_removed_count']}")

if TELE:
    os.makedirs(os.path.dirname(TELE) or ".", exist_ok=True)
    with open(TELE, "a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"\nWrote {len(rows)} rows to {TELE}")

db.close()
