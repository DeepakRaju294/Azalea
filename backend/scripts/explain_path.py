"""Human-readable dump of a study path's DECISION TRACE: why each topic exists, why its identity/scope/
adapter turned out the way it did, and what path-level curriculum decisions produced the topic list.

Reads decomposition_metadata.decision_trace (per topic, extended by every deterministic pass from the
curriculum call through certification through card grounding) and decomposition_metadata.path_decision_trace
(on the intro — decisions with no single topic subject: the requirements call, thin-plan retry, requirement
coverage, prereq merging, topic drops/demotions/folds). See app/core/decision_trace.py for how these are
recorded.

Also prints an INSTRUMENTATION COVERAGE section (app/core/decision_trace_coverage.py) — which pipeline
layers have ANY decision-trace call at all, so a reader can tell "nothing fired here" apart from "nothing
COULD have fired here" before reading the trace itself. Each trace entry is annotated with whether its
`stage` string still matches a call site in CURRENT source ("resolved"/"ambiguous"/"unresolved") — this is
a claim about source right now, not proof a historical generation ran that exact file/line.

Usage:
  python scripts/explain_path.py                  # latest study path
  python scripts/explain_path.py <study_path_id>   # a specific path
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

for cand in (".env", "backend/.env"):
    if not os.getenv("DATABASE_URL") and os.path.exists(cand):
        for line in open(cand, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

import app.db.base as base
from app.core.decision_trace_coverage import (
    PIPELINE_LAYERS, file_status, files_with_decision_trace_calls, resolve_stage, scan_decision_trace_call_sites,
)
from app.db.database import SessionLocal

db = SessionLocal()
if len(sys.argv) > 1:
    sp = db.query(base.StudyPath).filter(base.StudyPath.id == sys.argv[1]).first()
else:
    sp = db.query(base.StudyPath).order_by(base.StudyPath.created_at.desc()).first()

if sp is None:
    print("no study path found")
    sys.exit(1)

print("=" * 100)
print(f"STUDY PATH: {sp.title!r}")
print(f"goal:   {sp.goal!r}")
print(f"domain: {sp.domain!r}   created: {sp.created_at}")
print("=" * 100)

topics = sorted(sp.topics, key=lambda t: t.order_index or 0)

# --- instrumentation coverage ------------------------------------------------------------------------------
scan = scan_decision_trace_call_sites()
counts = files_with_decision_trace_calls(scan)
print(f"\n{'-' * 100}\nINSTRUMENTATION COVERAGE — which pipeline layers CAN log a decision at all\n{'-' * 100}")
for layer, files in PIPELINE_LAYERS.items():
    print(f"\n{layer}")
    for f in files:
        status = file_status(f, scan)
        if status == "some instrumentation detected":
            print(f"  {f:60} some instrumentation detected ({counts.get(f, 0)} calls)")
        elif status == "unknown":
            print(f"  {f:60} scan failed — instrumentation status unknown")
        else:
            print(f"  {f:60} no instrumentation detected")
    if layer == "lesson_generation":
        print("  note: presence does not imply full card-assembly coverage — card-grounding AND the LaTeX "
              "sanitizer are logged today (lesson.math_sanitized), other card-assembly passes are not")
if scan.parse_errors:
    print(f"\n  scan errors ({len(scan.parse_errors)}):")
    for e in scan.parse_errors:
        print(f"    {e['file']}: {e['error']}")
print("\nInterpretation: absence of trace entries from a file marked 'no instrumentation detected' above is "
      "structurally inconclusive — it never fired because it CAN'T, not because nothing applied.")


def _annotate_source(stage) -> str:
    outcome, sites = resolve_stage(str(stage), scan)
    if outcome == "resolved":
        s = sites[0]
        return f"{s.file}:{s.line} (resolved)"
    if outcome == "ambiguous":
        locs = ", ".join(f"{s.file}:{s.line}" for s in sites)
        return f"ambiguous — matches {len(sites)} current call sites: {locs}"
    return "unresolved in current source tree"


def _print_entries(entries, indent="   "):
    for e in entries:
        print(f"{indent}[{e.get('stage')}] {e.get('decision')}")
        print(f"{indent}    why: {e.get('reason')}")
        print(f"{indent}    source: {_annotate_source(e.get('stage'))}")
        detail = e.get("detail")
        if detail:
            print(f"{indent}    {json.dumps(detail, ensure_ascii=False)[:300]}")


print("\n('resolved' means a matching call site exists in the CURRENT source tree — not proof this "
      "generation actually ran that exact file/line; source can change between generation and inspection.)")

# --- path-level decisions (curriculum call, thin-plan retry, coverage, prereq merging) --------------------
intro = next((t for t in topics if (t.course_type or "") == "study_path_introduction"), None)
path_trace = ((intro.decomposition_metadata or {}).get("path_decision_trace") or []) if intro else []
if path_trace:
    print(f"\n{'-' * 100}\nPATH-LEVEL DECISIONS ({len(path_trace)}) — curriculum call, thin-plan retry, "
          f"requirement coverage, prerequisite merging\n{'-' * 100}")
    _print_entries(path_trace, indent="  ")
else:
    print("\n(no path-level decision trace found — either an older path, or the requirements-first flag "
          "was off for this generation)")

goal_reqs = ((intro.decomposition_metadata or {}).get("goal_requirements") or []) if intro else []
if goal_reqs:
    print(f"\n{'-' * 100}\nCURRICULUM REQUIREMENTS ({len(goal_reqs)})\n{'-' * 100}")
    for r in goal_reqs:
        print(f"  {r.get('requirement_id')} [{r.get('kind')}] owned={r.get('owned')!r}: {r.get('name')}")
        print(f"      {r.get('statement')}")

# --- per-topic decisions -------------------------------------------------------------------------------
print(f"\n{'=' * 100}\nPER-TOPIC DECISIONS\n{'=' * 100}")
for t in topics:
    md = t.decomposition_metadata or {}
    trace = md.get("decision_trace") or []
    plan = md.get("scope_plan") or {}
    print(f"\n[{t.order_index}] {t.title!r}   ({t.course_type})")
    if plan:
        print(f"    scope_plan: role={plan.get('role')!r} depth={plan.get('depth')!r} "
              f"we_policy={plan.get('we_policy')!r} verified_example={plan.get('verified_example')!r} "
              f"science_shape={plan.get('science_shape')!r}")
    if not trace:
        print("    (no decisions recorded for this topic — nothing deterministic touched it beyond "
              "the model's own output)")
        continue
    _print_entries(trace)
