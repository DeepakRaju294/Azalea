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
    # G0 metric set (spec §14, external review issue 29). Every fixture here is a KNOWN-CORRECT example, so a
    # MATCH is a correct decision and a MISS is the solver getting a known answer wrong. `false_confirmation`
    # (a WRONG example confirmed) can only be measured once the negative fixture classes (§17) exist — until
    # then it is the headline unknown, not a passing 0.
    decisive = matched + mismatched
    print(f"MATCH {matched}/{total}   MISS {mismatched}   INDECISIVE {indecisive}")
    print(f"decision_rate     (decisive / total)          : {100 * decisive / total:.0f}%")
    print(f"precision         (correct_decisive / decisive): {100 * matched / decisive:.0f}%" if decisive else "precision: n/a")
    print(f"effective_success (correct_decisive / total)  : {100 * matched / total:.0f}%")
    print("false_confirmation_rate: NOT MEASURABLE yet — needs negative fixtures (spec §17); the safety metric.")
    print("NOTE: 10 clean fixtures gate PLUMBING, not architecture (issue 30). Expand corpus before G0 sign-off.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
