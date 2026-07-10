"""Shadow A/B harness for topic decomposition (TOPIC_DECOMPOSITION_SPEC.md — Engine B go/no-go).

Runs Engine A (legacy LLM prompt) and Engine B (capability-graph, AZALEA_TOPIC_DECOMPOSITION) on the
SAME goal-only inputs and diffs the two things Engine B exists to fix:
  * COVERAGE — every concept named in the goal gets a topic (the dropped-concept regression), and
  * PADDING  — no extra Basics/Steps/Practicing topics beyond the concepts that were asked for.

It calls the live LLM twice per goal, so it needs a real OPENAI_API_KEY and makes real requests. It
touches NO database and NO request path — run it by hand to collect the shadow data that decides whether
to flip AZALEA_TOPIC_DECOMPOSITION=1.

    python -m scripts.topic_decomposition_ab                      # the default regression set
    python -m scripts.topic_decomposition_ab "bfs and dfs"        # one ad-hoc goal
"""
from __future__ import annotations

import os
import re
import sys

from app.services.topic_generator import generate_topics_from_chunks

# (goal, [concept phrases that MUST each own a topic]).  The concept list is the coverage oracle:
# Engine B's whole point is that each of these survives into a distinct topic.
DEFAULT_GOALS: list[tuple[str, list[str]]] = [
    ("law of total probability and bayes theorem", ["total probability", "bayes"]),
    ("completing the square", ["completing the square"]),
    ("binary search and merge sort", ["binary search", "merge sort"]),
    ("gradient descent", ["gradient descent"]),
    ("bubble sort", ["bubble sort"]),
]

_STOP = {"the", "of", "and", "a", "an", "for", "to", "law"}


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if w not in _STOP}


def _covers(concept: str, topics: list[dict]) -> bool:
    """A concept is covered when some topic's title/subject contains all its non-stopword tokens."""
    need = _tokens(concept)
    for t in topics:
        hay = _tokens(f"{t.get('title', '')} {t.get('subject_key', '')} {t.get('topic', '')}")
        if need and need <= hay:
            return True
    return False


def _run(goal: str, engine_b: bool) -> list[dict]:
    prev = os.environ.get("AZALEA_TOPIC_DECOMPOSITION")
    os.environ["AZALEA_TOPIC_DECOMPOSITION"] = "1" if engine_b else "0"
    try:
        return generate_topics_from_chunks(chunks=[], goal=goal) or []
    finally:
        if prev is None:
            os.environ.pop("AZALEA_TOPIC_DECOMPOSITION", None)
        else:
            os.environ["AZALEA_TOPIC_DECOMPOSITION"] = prev


def _report(goal: str, concepts: list[str], label: str, topics: list[dict]) -> dict:
    titles = [t.get("title") or t.get("topic") or "?" for t in topics]
    missing = [c for c in concepts if not _covers(c, topics)]
    extra = max(0, len(topics) - len(concepts))
    print(f"  {label:8} {len(topics):>2} topics  covered={len(concepts) - len(missing)}/{len(concepts)}"
          f"  padding={extra}")
    for t in titles:
        print(f"           - {t}")
    if missing:
        print(f"           MISSING: {', '.join(missing)}")
    return {"n": len(topics), "missing": missing, "padding": extra}


def main() -> None:
    goals: list[tuple[str, list[str]]]
    if len(sys.argv) > 1:
        goals = [(g, [g]) for g in sys.argv[1:]]
    else:
        goals = DEFAULT_GOALS

    if not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "dummy":
        print("!! no real OPENAI_API_KEY — this harness makes live calls and will fail offline.")

    verdicts: list[str] = []
    for goal, concepts in goals:
        print(f"\nGOAL: {goal}   (concepts: {', '.join(concepts)})")
        try:
            a = _report(goal, concepts, "A(leg)", _run(goal, engine_b=False))
            b = _report(goal, concepts, "B(cap)", _run(goal, engine_b=True))
        except Exception as exc:  # noqa: BLE001 — a live failure is a datapoint, keep going
            print(f"  ERROR: {exc}")
            verdicts.append("err")
            continue
        # Engine B wins the row when it covers every concept AND pads no worse than legacy.
        ok = not b["missing"] and b["padding"] <= a["padding"]
        verdicts.append("B>=A" if ok else "regress")
        print(f"  => {'OK  Engine B covers all + no extra padding' if ok else 'REGRESSION — inspect above'}")

    good = sum(1 for v in verdicts if v == "B>=A")
    print(f"\nSUMMARY: {good}/{len(verdicts)} goals clean for Engine B  ({verdicts})")


if __name__ == "__main__":
    main()
