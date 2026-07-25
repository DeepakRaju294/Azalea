"""Phase 0 go/no-go: measure the reproduction HIT RATE of the live worked-example solver.

For each hand-authored (problem, published-answer) fixture, hand the solver the KNOWN problem and check whether
its final answer reproduces the published one. This is the single number that decides whether the retrieval
direction is worth building: if the solver can't reproduce known answers even when handed the exact problem,
retrieval (which only supplies the problem/formula) cannot rescue it; if it can, reproduction-check is a viable
accuracy gate for no-adapter topics.

Needs a real OPENAI_API_KEY (it runs live generation). Read-only: it generates and measures, writes nothing.

    ./venv/Scripts/python.exe -m scripts.retrieval_repro_gonogo
"""
from __future__ import annotations

import os
import sys

from app.services.examples.retrieval_verify import KNOWN_ANSWER_FIXTURES, reproduction_check


def _solve_final_answer(fx) -> str:
    from app.services.examples.solver import solve_worked_example
    topic = {
        "title": fx.concept.replace("_", " ").title(),
        "topic_type": "math_formula_method",
        "course_type": "math_formula_method",
        "subject_key": fx.concept,
        "path_domain": fx.domain,
    }
    sol = solve_worked_example(topic, existing_problem=fx.problem)
    if not isinstance(sol, dict):
        return ""
    return str(sol.get("final_answer") or "")


def main() -> int:
    key = os.getenv("OPENAI_API_KEY")
    if not key or key.strip().lower() == "dummy":
        print("NO API KEY -- this go/no-go runs live generation. Set OPENAI_API_KEY and re-run.")
        return 2

    matched = mismatched = indecisive = 0
    rows = []
    for fx in KNOWN_ANSWER_FIXTURES:
        try:
            produced = _solve_final_answer(fx)
        except Exception as exc:  # noqa: BLE001
            produced, verdict = f"<error: {exc!r}>", "ERROR"
            indecisive += 1
            rows.append((fx.concept, fx.known_answer, produced, verdict, "solver raised"))
            continue
        r = reproduction_check(fx.known_answer, produced)
        if r.matched is True:
            verdict = "MATCH"; matched += 1
        elif r.matched is False:
            verdict = "MISS"; mismatched += 1
        else:
            verdict = "INDECISIVE"; indecisive += 1
        rows.append((fx.concept, fx.known_answer, produced or "<empty>", verdict, r.detail))

    total = len(KNOWN_ANSWER_FIXTURES)
    print(f"\n{'concept':<22}{'published':<14}{'produced':<18}{'verdict':<12}detail")
    print("-" * 96)
    for concept, known, produced, verdict, detail in rows:
        print(f"{concept:<22}{known:<14}{produced[:16]:<18}{verdict:<12}{detail}")
    print("-" * 96)
    print(f"MATCH {matched}/{total}   MISS {mismatched}   INDECISIVE {indecisive}")
    print(f"reproduction hit rate (match / total): {100 * matched / total:.0f}%")
    print(f"decisive accuracy (match / decisive):  "
          f"{100 * matched / (matched + mismatched):.0f}%" if (matched + mismatched) else "n/a")
    return 0


if __name__ == "__main__":
    sys.exit(main())
