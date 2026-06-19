"""Problem-first LLM worked-example solver (Slice 1: full text breakdown + completion).

A non-code topic's worked example is replaced by a single focused solve rendered as a
setup card + one card per step, with the last card carrying the final answer and stamped
reaches_final_answer. Asserted by behavior; the LLM is a stub (no network).

Run: python -m unittest app.tests.test_worked_example_solver
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples.solver import (
    _build_solution_cards,
    _expand_coarse_actions,
    _gate_outline,
    _is_coarse_action,
    _split_action,
    apply_llm_solved_worked_example,
    solve_worked_example,
)
from app.services.examples.worked_example_audit import audit_worked_examples


def _step(title, goal, reasoning, work, result, visual, cases=None):
    card = {"title": title, "goal": goal, "reasoning": reasoning,
            "work": work if isinstance(work, list) else [work], "result": result, "visual": visual}
    if cases:
        card["cases_covered"] = cases
    return card


def _outline(problem, answer, cases, n_full=4, visual="initial figure"):
    # A passing action outline: >= 4 full steps, every required_case covered by some action.
    return {
        "problem": problem, "expected_final_answer": answer, "problem_visual": visual,
        "required_cases": list(cases),
        "solution_plan": [
            {"full_step": s, "action": f"action {s}",
             "cases_covered": (list(cases) if s == n_full else [])}
            for s in range(1, n_full + 1)
        ],
    }


def _stub(payload):
    # Two-phase: a passing outline, then the Goal/Reasoning/Work/Result cards.
    if payload.get("phase") == "outline":
        return _outline("Solve 2x^2 - 4x - 6 = 0 for x.", "x = 3 or x = -1",
                        ["positive discriminant", "two real roots"],
                        visual="The equation centered, with a, b, c labeled below.")
    return {
        "problem": "Solve 2x^2 - 4x - 6 = 0 for x.",
        "expected_final_answer": "x = 3 or x = -1",
        "cards": [
            _step("Identify coefficients", "Name a, b, c.", "Read the standard form ax^2+bx+c.",
                  ["a = 2", "b = -4", "c = -6"], "a = 2, b = -4, c = -6",
                  "coefficients boxed under the equation"),
            _step("Compute the discriminant", "Find the discriminant.", "Root count needs b^2 - 4ac.",
                  ["b^2 - 4ac = 16 + 48", "= 64", "sqrt(64) = 8"], "discriminant = 64 (sqrt = 8)",
                  "16 + 48 = 64, sqrt(64)=8 highlighted", cases=["positive discriminant"]),
            _step("Apply the formula", "Solve for x.", "x = (-b ± sqrt)/2a.",
                  ["x = (4 ± 8) / 4", "x = 12/4 or x = -4/4"], "x = 3 or x = -1",
                  "two branches for + and -", cases=["two real roots"]),
        ],
        "final_answer": "x = 3 or x = -1",
    }


def _steps_stub(payload):
    # Robustness: the model used the legacy steps/detail shape instead of cards.
    if payload.get("phase") == "outline":
        return _outline("Compute the mean of 2, 4, 9.", "5", [])
    return {
        "problem": "Compute the mean of 2, 4, 9.",
        "steps": [{"title": "Sum", "detail": ["2 + 4 + 9 = 15."]},
                  {"title": "Divide", "detail": ["15 / 3 = 5."]}],
        "final_answer": "5",
    }


def _bad_stub(payload):
    if payload.get("phase") == "outline":
        return _outline("x", "y", [])
    return {"problem": "x", "cards": [], "final_answer": ""}  # nothing to render


# --- Coding-implementation structural path (CODING_WORKED_EXAMPLE_SPEC) -------------------------
_MERGE_CASES = ["split_with_slicing", "immediate_base_case_return",
                "parent_receives_recursive_result", "merge_selection", "tail_copy"]


def _coding_outline(problem="Sort [38, 27, 43, 3] with merge_sort.", answer="[3, 27, 38, 43]"):
    # 8 structural actions covering all 5 merge_sort required cases (merge_sort range is (8, 18)).
    plan = [
        {"kind": "split", "description": "Split [38, 27, 43, 3] into [38, 27] and [43, 3]",
         "cases_covered": ["split_with_slicing"]},
        {"kind": "recursive_call", "description": "Call merge_sort([38, 27])", "cases_covered": []},
        {"kind": "split", "description": "Split [38, 27] into [38] and [27]", "cases_covered": []},
        {"kind": "base_case", "description": "merge_sort([38]) -> return [38]",
         "cases_covered": ["immediate_base_case_return"]},
        {"kind": "base_case", "description": "merge_sort([27]) -> return [27]", "cases_covered": []},
        {"kind": "merge_selection", "description": "Merge [38] and [27]: 38 > 27, append 27",
         "cases_covered": ["merge_selection"]},
        {"kind": "merge_tail", "description": "copy remaining [38]; parent receives [27, 38]",
         "cases_covered": ["tail_copy", "parent_receives_recursive_result"]},
        {"kind": "merge_selection", "description": "Top merge -> [3, 27, 38, 43]", "cases_covered": []},
    ]
    return {"problem": problem, "expected_final_answer": answer, "problem_visual": "four boxes",
            "required_cases": list(_MERGE_CASES), "solution_plan": plan}


def _coding_cards(answer="[3, 27, 38, 43]"):
    cards = [{"title": f"Step {i}", "goal": "g", "reasoning": "r",
              "work": [f"mid = {i}", f"L = arr[:{i}] = [{i}]"], "result": f"left = [{i}]",
              "code_lines": [[2], [3]], "cases_covered": list(_MERGE_CASES) if i == 0 else []}
             for i in range(7)]
    cards.append({"title": "Done", "work": [f"return {answer}"], "result": answer, "code_lines": [[9]]})
    return {"problem": "Sort [38, 27, 43, 3] with merge_sort.", "expected_final_answer": answer,
            "cards": cards, "final_answer": answer}


def _coding_stub(payload):
    return _coding_outline() if payload.get("phase") == "outline" else _coding_cards()


def _lesson():
    return {
        "lesson_cards": [
            {"blueprint_key": "background", "title": "Intro"},
            {"blueprint_key": "worked_example", "title": "Example", "points": ["A rushed half-example."]},
            {"blueprint_key": "practice", "title": "Practice"},
        ],
        "metadata": {},
    }


class TestSolve(unittest.TestCase):
    def test_solve_normalizes_shape(self):
        sol = solve_worked_example({"title": "Quadratics"}, solver=_stub)
        self.assertEqual(sol["final_answer"], "x = 3 or x = -1")
        self.assertEqual(len(sol["cards"]), 3)

    def test_steps_fallback_shape(self):
        sol = solve_worked_example({"title": "Mean"}, solver=_steps_stub)
        self.assertEqual(len(sol["cards"]), 2)
        self.assertEqual(sol["cards"][0]["work"], ["2 + 4 + 9 = 15."])

    def test_empty_solution_is_none(self):
        self.assertIsNone(solve_worked_example({"title": "X"}, solver=_bad_stub))

    def test_cards_have_setup_and_final(self):
        sol = solve_worked_example({"title": "Quadratics"}, solver=_stub)
        cards = _build_solution_cards(sol, {"id": "t1"})
        self.assertGreaterEqual(len(cards), 4)                 # setup + 3 steps
        self.assertTrue(cards[0]["metadata"].get("worked_example_setup"))
        self.assertIn("2x^2 - 4x - 6", " ".join(cards[0]["points"]))   # setup states the problem
        # rich per-card visual description carried (Phase-2 foundation)
        self.assertIn("a, b, c", cards[0]["visual_description"])      # setup uses problem_visual
        self.assertTrue(all(c.get("visual_description") for c in cards))
        # setup carries the hidden expected answer (not shown in the problem text)
        self.assertEqual(cards[0]["metadata"]["expected_final_answer"], "x = 3 or x = -1")
        self.assertNotIn("x = 3 or x = -1", cards[0]["points"][1])  # answer not spoiled in setup
        # each step carries the structured Goal/Reasoning/Work/Result fields + example index
        self.assertEqual(cards[1]["work"], ["a = 2", "b = -4", "c = -6"])
        self.assertEqual(cards[1]["result"], "a = 2, b = -4, c = -6")
        self.assertTrue(cards[1]["reasoning"])
        self.assertEqual(cards[1]["metadata"]["example"], {"role": "step", "index": 1, "total": 3})
        self.assertEqual(cards[2]["metadata"]["cases_covered"], ["positive discriminant"])
        last = cards[-1]
        # the last step's conclusion (its `result`) is stored for the blueprint to verify
        self.assertEqual(last["metadata"]["final_answer"], "x = 3 or x = -1")
        self.assertEqual(last["result"], "x = 3 or x = -1")


class TestCoding(unittest.TestCase):
    def test_coding_uses_structural_path_and_attaches_ide_code(self):
        seen = {"systems": []}

        def capture(payload):
            seen["systems"].append(payload.get("system"))
            seen["user"] = payload.get("user")
            return _coding_outline() if payload.get("phase") == "outline" else _coding_cards()

        code = "def merge_sort(arr):\n    if len(arr) > 1:\n        mid = len(arr) // 2\n    return arr"
        lesson = {
            "lesson_cards": [
                {"blueprint_key": "worked_example", "code_snippet": code, "points": ["old"]},
                {"blueprint_key": "practice"},
            ],
            "metadata": {},
        }
        applied = apply_llm_solved_worked_example(
            lesson, {"id": "c1", "title": "Merge Sort", "topic_type": "coding_implementation"}, solver=capture,
        )
        self.assertTrue(applied)
        cards_system = seen["systems"][-1]                    # the LAST call is the cards phase
        self.assertIn("structural", cards_system.lower())     # structural coding cards prompt used
        self.assertIn("line number", cards_system.lower())    # mentions code_lines / no prose line nums
        self.assertIn(code, seen["user"])                     # the code was handed to the solve
        we = [c for c in lesson["lesson_cards"] if c.get("blueprint_key") == "worked_example"]
        self.assertTrue(all(c.get("code_snippet") == code for c in we))  # IDE code on every card
        joined = " ".join(p for c in we for p in c.get("points", [])).lower()
        self.assertNotIn("line ", joined)                     # no "line N executes" in the text
        # the per-action code anchor is carried into step metadata (best-effort, len-matched)
        self.assertEqual(we[1]["metadata"].get("code_lines"), [[2], [3]])


class TestAtomicity(unittest.TestCase):
    def test_placeholder_actions_are_coarse(self):
        self.assertTrue(_is_coarse_action("Recursively sort the left half [8, 5, 7]")[0])
        self.assertTrue(_is_coarse_action("Merge the results")[0])
        self.assertTrue(_is_coarse_action("Process the subtree")[0])

    def test_bundled_list_is_coarse(self):
        coarse, _ = _is_coarse_action("Find midpoint; split into halves; recurse left; merge")
        self.assertTrue(coarse)

    def test_atomic_two_verb_move_is_allowed(self):
        # one cause-and-effect transition (compare + append) is NOT coarse
        self.assertFalse(_is_coarse_action("Compare the two front values and append the smaller")[0])
        self.assertFalse(_is_coarse_action("Compute mid = (0 + 3) // 2 = 1")[0])

    def test_split_keeps_brackets_intact(self):
        self.assertEqual(
            _split_action("Sort the array [5, 2, 8] then compare 5 and 2"),
            ["Sort the array [5, 2, 8]", "compare 5 and 2"],
        )

    def test_expand_splits_bundled_action(self):
        plan = [{"full_step": 1, "action": "compute mid; split; merge", "cases_covered": ["c"]}]
        out = _expand_coarse_actions(plan)
        self.assertEqual([a["action"] for a in out], ["compute mid", "split", "merge"])
        self.assertTrue(all(a["full_step"] == 1 and a["cases_covered"] == ["c"] for a in out))

    def test_gate_rejects_coarse_plan(self):
        outline = {"required_cases": [], "solution_plan": [
            {"full_step": s, "action": "Recursively sort the half", "cases_covered": []}
            for s in range(1, 5)
        ]}
        ok, feedback = _gate_outline(outline)
        self.assertFalse(ok)
        self.assertIn("COARSE", feedback)


class TestCompletenessRetry(unittest.TestCase):
    def test_incomplete_cards_trigger_backstop_resolve(self):
        # The outline always passes the gate; the FIRST cards expansion comes back incomplete
        # (too few steps, doesn't reach the answer), so the single downstream backstop re-solves.
        cards_calls = {"n": 0}

        def _step(i, work, result):
            return {"title": f"Step {i}", "work": [work], "result": result}

        def flaky(payload):
            if payload.get("phase") == "outline":
                return _outline("Sort [5, 2, 8].", "[2, 5, 8]", [])
            cards_calls["n"] += 1
            if cards_calls["n"] == 1:
                return {"cards": [_step(0, "split", "halves [5] [2,8]"), _step(1, "merge", "partial")],
                        "final_answer": "[2, 5, 8]"}
            return {"cards": [_step(i, f"compare {i}", f"merged prefix {i}") for i in range(5)]
                             + [_step(5, "append last", "[2, 5, 8]")],
                    "final_answer": "[2, 5, 8]"}

        lesson = {"lesson_cards": [{"blueprint_key": "worked_example", "points": ["x"]},
                                   {"blueprint_key": "practice"}], "metadata": {}}
        import app.services.examples.solver as solver_mod
        old = solver_mod._MAX_RESOLVE_ATTEMPTS
        solver_mod._MAX_RESOLVE_ATTEMPTS = 1  # enable the (default-off) backstop for this test
        try:
            applied = apply_llm_solved_worked_example(lesson, {"id": "t1", "title": "Merge Sort"}, solver=flaky)
        finally:
            solver_mod._MAX_RESOLVE_ATTEMPTS = old
        self.assertTrue(applied)
        self.assertEqual(cards_calls["n"], 2)  # one backstop re-solve of the cards
        we = [c for c in lesson["lesson_cards"] if c.get("blueprint_key") == "worked_example"]
        self.assertGreaterEqual(len(we), 7)  # setup + 6 steps from the re-solve


class TestApply(unittest.TestCase):
    def test_replaces_worked_example_and_completes(self):
        lesson = _lesson()
        applied = apply_llm_solved_worked_example(lesson, {"id": "t1", "title": "Quadratics"}, solver=_stub)
        self.assertTrue(applied)
        keys = [c.get("blueprint_key") for c in lesson["lesson_cards"]]
        self.assertEqual(keys[0], "background")               # other cards preserved, in place
        self.assertEqual(keys[-1], "practice")
        we = [c for c in lesson["lesson_cards"] if c.get("blueprint_key") == "worked_example"]
        self.assertGreaterEqual(len(we), 4)
        self.assertNotIn("A rushed half-example.", [p for c in we for p in c.get("points", [])])
        # Completion is now guaranteed upstream — the audit sees nothing incomplete.
        report = audit_worked_examples(lesson, {"id": "t1"}, regenerate=None)
        self.assertEqual(report["status"], "complete")

    def test_failed_solve_leaves_lesson_untouched(self):
        lesson = _lesson()
        before = [dict(c) for c in lesson["lesson_cards"]]
        applied = apply_llm_solved_worked_example(lesson, {"id": "t1", "title": "X"}, solver=lambda p: None)
        self.assertFalse(applied)
        self.assertEqual(lesson["lesson_cards"], before)

    def test_creates_worked_example_when_blueprint_wants_one(self):
        # Coding topic whose generation produced NO worked example — the solver must create one
        # (the blueprint requires it) from the lesson's code, not silently leave none.
        lesson = {"lesson_cards": [
            {"blueprint_key": "components_terms", "title": "Key terms"},
            {"blueprint_key": "code_walkthrough", "title": "Code",
             "code_snippet": "def merge_sort(arr):\n    return sorted(arr)"},
        ], "metadata": {}}
        applied = apply_llm_solved_worked_example(
            lesson, {"id": "c1", "title": "Merge Sort", "topic_type": "coding_implementation"}, solver=_coding_stub,
        )
        self.assertTrue(applied)
        we = [c for c in lesson["lesson_cards"] if c.get("blueprint_key") == "worked_example"]
        self.assertGreaterEqual(len(we), 1)  # created from scratch via the structural coding path

    def test_topic_without_worked_example_slot_is_skipped(self):
        # study_path_introduction's blueprint has no worked_example slot -> nothing to author.
        lesson = {"lesson_cards": [{"blueprint_key": "background"}], "metadata": {}}
        self.assertFalse(apply_llm_solved_worked_example(
            lesson, {"id": "t1", "topic_type": "study_path_introduction"}, solver=_stub))


class TestCodingStructural(unittest.TestCase):
    """The coding-implementation structural path: slug ranges, the hard outline gate, code-anchored
    cards, and the no-line-trace fallback marker (CODING_WORKED_EXAMPLE_SPEC v1)."""

    def test_slug_resolution_and_v1_ranges(self):
        from app.services.examples.solver import _coding_topic_slug, _coding_step_range
        self.assertEqual(_coding_topic_slug({"title": "Implementing Merge Sort"}), "merge_sort")
        self.assertEqual(_coding_topic_slug({"title": "Binary Search in Python"}), "binary_search")
        self.assertEqual(_coding_topic_slug({"title": "Some Custom Algorithm"}), "default")
        self.assertEqual(_coding_step_range("merge_sort"), (8, 18))   # v1 teaching default, not (12, 30)

    def test_gate_allows_large_plan_no_upper_bound(self):
        # The gate intentionally has NO upper bound — a long structural plan must NOT be rejected,
        # so the worked example runs the full trace to the result instead of being cut short.
        from app.services.examples.solver import _gate_coding_outline
        outline = {"required_cases": [], "solution_plan": [
            {"kind": "pass", "description": f"a{i}", "cases_covered": []} for i in range(40)]}
        ok, _, reason = _gate_coding_outline(outline, step_range=(3, 6), required=[])
        self.assertTrue(ok)
        self.assertEqual(reason, "")

    def test_gate_rejects_line_level_kinds(self):
        from app.services.examples.solver import _gate_coding_outline
        outline = {"required_cases": [], "solution_plan": [
            {"kind": "assignment", "description": f"i{i} = 0", "cases_covered": []} for i in range(4)]}
        ok, _, reason = _gate_coding_outline(outline, step_range=(3, 6), required=[])
        self.assertFalse(ok)
        self.assertEqual(reason, "line_level_kind")

    def test_gate_rejects_other_over_cap(self):
        from app.services.examples.solver import _gate_coding_outline
        plan = [{"kind": "other", "description": f"a{i}", "cases_covered": []} for i in range(5)]
        plan += [{"kind": "pass", "description": f"b{i}", "cases_covered": []} for i in range(3)]
        ok, _, reason = _gate_coding_outline({"required_cases": [], "solution_plan": plan},
                                             step_range=(8, 18), required=[])
        self.assertFalse(ok)
        self.assertEqual(reason, "other_over_cap")

    def test_gate_rejects_missing_required_case(self):
        from app.services.examples.solver import _gate_coding_outline
        plan = [{"kind": "split", "description": f"a{i}", "cases_covered": []} for i in range(10)]
        ok, _, reason = _gate_coding_outline({"required_cases": _MERGE_CASES, "solution_plan": plan},
                                             step_range=(8, 18), required=_MERGE_CASES)
        self.assertFalse(ok)
        self.assertEqual(reason, "missing_required_cases")

    def test_gate_passes_structural_plan(self):
        from app.services.examples.solver import _gate_coding_outline
        ok, _, _ = _gate_coding_outline(_coding_outline(), step_range=(8, 18), required=_MERGE_CASES)
        self.assertTrue(ok)

    def test_structural_solve_emits_code_anchored_cards(self):
        sol = solve_worked_example(
            {"title": "Merge Sort", "topic_type": "coding_implementation"},
            code="def merge_sort(arr):\n    ...", solver=_coding_stub,
        )
        self.assertEqual(sol["coding_slug"], "merge_sort")
        self.assertEqual(len(sol["cards"]), 8)
        self.assertEqual(sol["cards"][0]["code_lines"], [[2], [3]])

    def test_recoverable_gate_failure_ships_best_effort(self):
        # lean omits the worked example, so abandoning = a blank topic. An under-min outline therefore
        # ships best-effort (renders) rather than returning a marker, as long as the cards call works.
        def stub(payload):
            if payload.get("phase") == "outline":  # 3 actions < default min of 5
                return {"required_cases": [], "solution_plan": [
                    {"kind": "pass", "description": f"pass {i}", "cases_covered": []} for i in range(3)]}
            return {"cards": [{"title": f"S{i}", "work": [f"x = {i}"], "result": f"r{i}"} for i in range(3)],
                    "final_answer": "done"}
        sol = solve_worked_example(
            {"title": "Some Algorithm", "topic_type": "coding_implementation"}, code="def f(): ...", solver=stub)
        self.assertNotIn("coding_fallback_used", sol)   # rendered, not abandoned
        self.assertEqual(len(sol["cards"]), 3)

    def test_large_plan_ships_complete_without_trimming(self):
        # No upper limit: a long structural plan (40 actions) ships IN FULL — never trimmed/cut short.
        seen = {}

        def stub(payload):
            if payload.get("phase") == "outline":
                return {"required_cases": [], "solution_plan": [
                    {"kind": "pass", "description": f"pass {i}", "cases_covered": []} for i in range(40)]}
            seen["cards_user"] = payload.get("user")
            return {"cards": [{"title": "S", "work": ["x = 1"], "result": "r"}], "final_answer": "done"}
        sol = solve_worked_example(
            {"title": "Some Algorithm", "topic_type": "coding_implementation"}, code="def f(): ...", solver=stub)
        self.assertNotIn("coding_fallback_used", sol)
        self.assertIn("40. ", seen["cards_user"])  # all 40 actions reached the cards call — none trimmed

    def test_empty_plan_returns_fallback_marker(self):
        # A truly empty plan is the only hard abandon for the outline phase.
        def stub(payload):
            return {"required_cases": [], "solution_plan": []}
        sol = solve_worked_example(
            {"title": "Some Algorithm", "topic_type": "coding_implementation"}, code="def f(): ...", solver=stub)
        self.assertTrue(sol.get("coding_fallback_used"))
        self.assertEqual(sol["reason"], "empty_plan")

    def test_cards_error_returns_fallback_marker(self):
        def stub(payload):  # outline passes, but the cards call yields nothing
            return _coding_outline() if payload.get("phase") == "outline" else None
        sol = solve_worked_example(
            {"title": "Merge Sort", "topic_type": "coding_implementation"}, code="def merge_sort(arr): ...", solver=stub)
        self.assertTrue(sol.get("coding_fallback_used"))
        self.assertEqual(sol["reason"], "cards_call_error")

    def test_fallback_marker_keeps_base_example(self):
        def bad(payload):
            return {"required_cases": [], "solution_plan": [
                {"kind": "pass", "description": "only one", "cases_covered": []}]}
        lesson = {"lesson_cards": [
            {"blueprint_key": "worked_example", "code_snippet": "def bs(): ...", "points": ["base example"]},
            {"blueprint_key": "practice"}], "metadata": {}}
        applied = apply_llm_solved_worked_example(
            lesson, {"id": "c9", "title": "Binary Search", "topic_type": "coding_implementation"}, solver=bad)
        self.assertFalse(applied)
        self.assertEqual(lesson["metadata"]["worked_example_solver"]["status"], "coding_fallback_used")
        we = [c for c in lesson["lesson_cards"] if c.get("blueprint_key") == "worked_example"]
        self.assertIn("base example", [p for c in we for p in c.get("points", [])])  # base example untouched


if __name__ == "__main__":
    unittest.main()
