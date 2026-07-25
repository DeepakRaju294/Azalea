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

from app.services.examples.retrieval_verify import (
    KNOWN_ANSWER_FIXTURES, reproduction_check, run_checker_corpus,
)


def _print_checker_corpus() -> bool:
    """Offline (no API key) adversarial-corpus report: confusion matrix + the critical-false-confirmation gate
    (spec §17). Returns True if it BLOCKS G0 (a critical false confirmation), which no live number can override."""
    rep = run_checker_corpus()
    print("\n=== offline checker corpus (reproduction_check on adversarial pairs) ===")
    print(f"{'case':<20}{'class':<28}{'expected':<12}{'observed':<12}sev")
    print("-" * 84)
    for x in rep["results"]:
        flag = "  <-- FALSE CONFIRM" if x.false_confirmation else ("" if x.matched_expectation else "  <-- unexpected")
        print(f"{x.case.case_id:<20}{x.case.fixture_class:<28}{x.case.expected:<12}{x.observed:<12}{x.case.severity}{flag}")
    print("-" * 84)
    print("confusion (expected -> observed):")
    for (exp, obs), n in sorted(rep["confusion"].items()):
        print(f"  {exp:<12} -> {obs:<12} : {n}")
    print(f"matched_expectation {rep['matched']}/{rep['total']}   "
          f"false_confirmations {len(rep['false_confirmations'])}   "
          f"critical {len(rep['critical_false_confirmations'])}")
    if rep["blocking"]:
        print("*** G0 BLOCKED: a CRITICAL false confirmation exists — no live number overrides this. ***")
    return bool(rep["blocking"])


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
    # The adversarial checker corpus runs OFFLINE and gates G0 first: a critical false confirmation blocks
    # regardless of the live reproduction rate.
    blocked = _print_checker_corpus()

    key = os.getenv("OPENAI_API_KEY")
    if not key or key.strip().lower() == "dummy":
        print("\nNO API KEY -- the LIVE reproduction run needs one. Set OPENAI_API_KEY and re-run for the "
              "solver hit rate. (The offline checker corpus above already ran.)")
        return 1 if blocked else 2

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
    print("false_confirmation on live fixtures: 0 possible here (all are KNOWN-CORRECT); the adversarial "
          "false-confirmation gate is the offline checker corpus above.")
    print("NOTE: these live fixtures are all clean_numeric — they gate PLUMBING. Architecture sign-off needs "
          "the full fixture classes wired into the LIVE path (spec §17).")
    if blocked:
        print("\n*** OVERALL: G0 BLOCKED by the offline checker corpus (critical false confirmation). ***")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
