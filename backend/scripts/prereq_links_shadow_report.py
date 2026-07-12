"""Collect + summarize prereq-links shadow data (PREREQ_LINKS_SPEC v8 §6.3a/§6.7).

Runs the Tier-2 classification validator over every study path in the DB (read-only), and prints the
distribution of ok/fallback_reason plus every path whose classification the validator would REJECT (the
load-bearing signal: a concept that is both taught and named as a prerequisite, duplicate ownership, etc.).

Usage:  python scripts/prereq_links_shadow_report.py
"""
import io
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
from app.services.prereq_links_shadow import shadow_report

db = SessionLocal()
paths = db.query(base.StudyPath).order_by(base.StudyPath.created_at.desc()).all()

ok_dist: Counter = Counter()
reason_dist: Counter = Counter()
failing: list[tuple] = []

for sp in paths:
    topics = list(sp.topics or [])
    if not topics:
        continue
    rep = shadow_report(topics)
    ok_dist["ok" if rep["ok"] else "fail"] += 1
    for r, n in (rep["fallback_reasons"] or {}).items():
        reason_dist[r] += n
    if not rep["ok"]:
        failing.append((sp.goal or sp.title or sp.id, rep["fallback_reason"],
                        rep["n_topics"], rep["n_prereqs"]))

total = sum(ok_dist.values())
print(f"paths with topics: {total}")
print(f"ok / fail:         {ok_dist['ok']} / {ok_dist['fail']}")
print(f"fallback reasons:  {dict(reason_dist)}")
print("-" * 90)
if failing:
    print("FAILING paths (classification would fall back to legacy decomposition):")
    for goal, reason, nt, npq in failing:
        print(f"  [{reason}]  topics={nt} prereqs={npq}  goal={goal!r}")
else:
    print("no failing paths — every path's prereq/concept graph is structurally consistent")
