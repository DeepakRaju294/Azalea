"""Preview what the new pipeline generates for a topic (spec §12, manual inspection).

    python -m app.services.gen_foundation.preview merge_sort
    python -m app.services.gen_foundation.preview "Dijkstra's algorithm" coding_implementation graph_traversal

Runs the real single-pass pipeline (live model) and prints the rendered worked example
in the legacy card shape — the exact thing the app would render. Bypasses the shadow
flag so you can inspect regardless of whether it's enabled in production.
"""
from __future__ import annotations

import json
import sys

from .fixture_run import FIXTURES, _load_env
from .integration import artifact_to_legacy
from .llm import default_solver
from .pipeline import run_first_pass


def _resolve_topic(args: list[str]) -> dict:
    key = args[0] if args else "merge_sort"
    for topic, *_ in FIXTURES:
        if topic["id"] == key:
            return topic
    # free-form: preview NAME [topic_type] [topic_family]
    return {
        "id": key, "title": key,
        "topic_type": args[1] if len(args) > 1 else "coding_implementation",
        "topic_family": args[2] if len(args) > 2 else "",
        "summary": f"Worked example for {key}.",
    }


def main(args: list[str]) -> None:
    _load_env()
    topic = _resolve_topic(args)
    print(f"\n=== preview: {topic.get('title') or topic['id']} "
          f"({topic.get('topic_type')}/{topic.get('topic_family') or '-'}) ===")
    res = run_first_pass(topic, solver=default_solver)
    print(f"ok={res.ok}  calls={res.model_calls}  degraded={res.degraded}  note={res.note or '-'}")
    print(f"audit={res.audit_telemetry}  reconcile={res.reconciliation_telemetry}")
    if res.validation_errors:
        print("validation_errors:")
        for e in res.validation_errors[:10]:
            print(f"   - {e}")
    if not res.artifact:
        return

    legacy = artifact_to_legacy(res.artifact)
    print(f"\nPROBLEM: {legacy.get('problem')}")
    for i, card in enumerate(legacy.get("cards") or [], 1):
        print(f"\n[{i}] {card.get('title')}")
        if card.get("goal"):
            print(f"    goal:      {card['goal']}")
        if card.get("reasoning"):
            print(f"    reasoning: {card['reasoning']}")
        for w in card.get("work") or []:
            print(f"      - {w}")
        if card.get("result"):
            print(f"    result:    {card['result']}")
        if card.get("code_lines"):
            print(f"    code_lines: {card['code_lines']}")
    print(f"\nFINAL ANSWER: {legacy.get('final_answer')}")
    print(f"\n(generated_by={legacy.get('generated_by')})")


if __name__ == "__main__":
    main(sys.argv[1:])
