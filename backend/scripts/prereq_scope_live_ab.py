"""Manual A/B harness for Guard 4 (AZALEA_PREREQ_SCOPE_LIVE — PREREQ_LINKS_SPEC.md §3.1/§6.1's real scope
classifier wired into live decomposition, topic_decomposition_pipeline.py).

Runs the real pipeline TWICE per goal (flag off, flag on) and diffs which concepts stay taught topics vs get
folded into assumed_prerequisites. It calls the live LLM twice per goal (decomposition + classifier calls), so
it needs a real OPENAI_API_KEY and makes real requests. It touches NO database and NO request path — run it
by hand to see what Guard 4 would actually change before trusting it on real traffic.

Guard 4 is one-directional (can only KEEP a foundation candidate taught, never externalize one the existing
guards already kept), so `newly_folded` should ALWAYS be empty — if it isn't, that's a bug, not just a
disagreement, and this script flags it loudly.

    python -m scripts.prereq_scope_live_ab                          # the default goal set
    python -m scripts.prereq_scope_live_ab "learn ohm's law" physics  # one ad-hoc (goal, domain)
"""
from __future__ import annotations

import os
import sys

from app.services.topic_generator import generate_topics_from_chunks

_LIVE_FLAG = "AZALEA_PREREQ_SCOPE_LIVE"
_ENGINE_B_FLAG = "AZALEA_TOPIC_DECOMPOSITION"

# (goal, domain) — an A1-style narrow goal (expect NO change: nothing genuinely foundational-and-in-scope to
# rescue) alongside an A9-style broad from-scratch goal (expect some foundation topics to stay taught).
DEFAULT_GOALS: list[tuple[str, str]] = [
    ("learn ohm's law", "physics"),
    ("learn basic electrical circuits from scratch", "physics"),
]


def _run(goal: str, domain: str, live: bool) -> list[dict]:
    prev_engine_b = os.environ.get(_ENGINE_B_FLAG)
    prev_live = os.environ.get(_LIVE_FLAG)
    os.environ[_ENGINE_B_FLAG] = "1"          # Guard 4 only runs inside Engine B decomposition
    os.environ[_LIVE_FLAG] = "1" if live else "0"
    try:
        return generate_topics_from_chunks(chunks=[], goal=goal, domain=domain) or []
    finally:
        for flag, prev in ((_ENGINE_B_FLAG, prev_engine_b), (_LIVE_FLAG, prev_live)):
            if prev is None:
                os.environ.pop(flag, None)
            else:
                os.environ[flag] = prev


def _report(label: str, topics: list[dict]) -> dict:
    intro = next((t for t in topics if t.get("course_type") == "study_path_introduction"), None)
    taught = {t.get("title") for t in topics if t is not intro}
    prereqs = set((intro or {}).get("assumed_prerequisites") or [])
    print(f"  {label:9} taught={len(taught)}  assumed_prerequisites={sorted(prereqs)}")
    for title in sorted(taught):
        print(f"            - {title}")
    return {"taught": taught, "prereqs": prereqs}


def main() -> None:
    goals: list[tuple[str, str]]
    if len(sys.argv) > 1:
        domain = sys.argv[2] if len(sys.argv) > 2 else ""
        goals = [(sys.argv[1], domain)]
    else:
        goals = DEFAULT_GOALS

    if not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "dummy":
        print("!! no real OPENAI_API_KEY — this harness makes live calls and will fail offline.")

    for goal, domain in goals:
        print(f"\nGOAL: {goal!r}  domain={domain!r}")
        try:
            off = _report("off", _run(goal, domain, live=False))
            on = _report("on", _run(goal, domain, live=True))
        except Exception as exc:  # noqa: BLE001 — a live failure is a datapoint, keep going
            print(f"  ERROR: {exc}")
            continue
        newly_taught = on["taught"] - off["taught"]
        newly_folded = off["taught"] - on["taught"]
        print(f"  => newly taught (flag on): {sorted(newly_taught) or 'none'}")
        if newly_folded:
            print(f"  !! UNEXPECTED — newly folded (should NEVER happen, Guard 4 is one-directional): "
                  f"{sorted(newly_folded)}")
        else:
            print("  => newly folded: none (expected — Guard 4 can only keep, never externalize)")


if __name__ == "__main__":
    main()
