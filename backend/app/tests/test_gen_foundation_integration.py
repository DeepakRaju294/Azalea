"""Production cutover adapter + executed reconcile (spec §12 step 6, §6.1).

Pure backend, offline (model + executor injected). No LLM, no DB.
Run: python -m unittest app.tests.test_gen_foundation_integration
"""
from __future__ import annotations

import copy
import os
import unittest
from contextlib import contextmanager

from app.services.gen_foundation.integration import (
    _flat_refs_to_ranges,
    artifact_to_legacy,
    card_to_legacy,
    solve_via_pipeline,
)
from app.services.gen_foundation.pipeline import run_first_pass


@contextmanager
def shadow_enabled():
    prev = os.environ.get("AZALEA_GEN_FOUNDATION_SHADOW")
    os.environ["AZALEA_GEN_FOUNDATION_SHADOW"] = "1"
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop("AZALEA_GEN_FOUNDATION_SHADOW", None)
        else:
            os.environ["AZALEA_GEN_FOUNDATION_SHADOW"] = prev


def fake(obj):
    return lambda payload: copy.deepcopy(obj)


def none_model(payload):
    return None


def simple_artifact_with_problem(n=5):
    cards = [
        {"title": f"S{i+1}", "goal": f"g{i}", "reasoning": "r", "work": ["w"],
         "result": "res", "state_relevance": "none", "state_delta": None, "cases_covered": [f"c{i}"]}
        for i in range(n)
    ]
    cards[-1]["result"] = "sorted = [1,2,3]"  # terminal step reaches the final answer (completeness gate)
    return {
        "problem": "sort [3,1,2]",
        "cards": cards,
        "projection_coverage": {
            "required_cases": {f"c{i}": [f"step_{i+1}"] for i in range(n)},
            "teaching_step_reaching_final": f"step_{n}",
        },
        "final_answer": "[1,2,3]",
    }


class TestAdapter(unittest.TestCase):
    def test_flat_refs_compress_to_ranges(self):
        self.assertEqual(_flat_refs_to_ranges([14, 15, 16, 18, 19, 21]), [[14, 16], [18, 19], [21, 21]])
        self.assertIsNone(_flat_refs_to_ranges([]))

    def test_coding_card_how_maps_to_reasoning(self):
        card = {"title": "Merge", "goal": "g", "how": "the while loop appends the smaller",
                "work": ["2<3"], "result": "merged=[2]", "explanation_mode": "implementation_how",
                "code_refs": [14, 15, 16]}
        legacy = card_to_legacy(card)
        self.assertEqual(legacy["reasoning"], "the while loop appends the smaller")
        self.assertEqual(legacy["code_lines"], [[14, 16]])

    def test_base_card_keeps_reasoning(self):
        legacy = card_to_legacy({"title": "t", "goal": "g", "reasoning": "decisive",
                                 "work": ["w"], "result": "r"})
        self.assertEqual(legacy["reasoning"], "decisive")
        self.assertIsNone(legacy["code_lines"])

    def test_artifact_to_legacy_shape(self):
        legacy = artifact_to_legacy(simple_artifact_with_problem(4))
        self.assertEqual(legacy["problem"], "sort [3,1,2]")
        self.assertEqual(len(legacy["cards"]), 4)
        self.assertEqual(legacy["final_answer"], legacy["expected_final_answer"])
        self.assertEqual(legacy["generated_by"], "gen_foundation")


class TestSolveViaPipeline(unittest.TestCase):
    def test_returns_none_when_flag_off(self):
        # No shadow flag -> never engages; caller falls back to legacy.
        self.assertIsNone(
            solve_via_pipeline({"topic_type": "concept"}, solver=fake(simple_artifact_with_problem()))
        )

    def test_returns_legacy_dict_when_flag_on(self):
        with shadow_enabled():
            out = solve_via_pipeline(
                {"topic_type": "concept"},
                solver=fake(simple_artifact_with_problem(5)), auditor=none_model,
            )
        self.assertIsNotNone(out)
        self.assertEqual(out["problem"], "sort [3,1,2]")
        self.assertEqual(len(out["cards"]), 5)
        self.assertEqual(out["generated_by"], "gen_foundation")
        self.assertIn("_telemetry", out)

    def test_offline_solver_falls_back(self):
        # Flag on but model unavailable -> None -> caller uses legacy.
        with shadow_enabled():
            self.assertIsNone(solve_via_pipeline({"topic_type": "concept"}, solver=none_model))

    def test_solver_none_does_not_crash(self):
        # The PRODUCTION hook forwards solver=None. That must coerce to the default adapter, not
        # call None(payload) -> TypeError (which silently fell back to legacy for every topic).
        with shadow_enabled():
            try:
                out = solve_via_pipeline({"topic_type": "concept"}, solver=None, auditor=None, repair=None)
            except TypeError:
                self.fail("solver=None must not raise TypeError")
            # offline (no key) -> returns None gracefully rather than crashing
            self.assertIsNone(out)


class TestExecutedReconcile(unittest.TestCase):
    def _coding_artifact(self, n=7):
        cards = [
            {"title": f"S{i+1}", "goal": "g", "how": "appends", "work": ["x"], "result": "r",
             "state_relevance": "stateful",
             "state_delta": {"ops": [{"op": "push", "path": "merged", "value": i}]},
             "primary_kind": "merge", "explanation_mode": "implementation_how",
             "code_refs": [10 + i], "cases_covered": [f"c{i}"]}
            for i in range(n)
        ]
        cards[-1]["result"] = "merged = [0,1,2,3,4,5,6]"  # terminal step reaches the final answer
        return {
            "code": "def merge():\n    return []\n",
            "cards": cards,
            "initial_resolved_state": {"merged": []},
            "projection_coverage": {
                "required_cases": {f"c{i}": [f"step_{i+1}"] for i in range(n)},
                "teaching_step_reaching_final": f"step_{n}",
            },
            "final_answer": "[0,1,2,3,4,5,6]",
        }

    def test_pipeline_reconciles_against_injected_trace(self):
        # An injected executor returns a real-shaped trace whose lines match the cards' code_refs.
        fake_exec = lambda code, lang, inp: [{"code_line_refs": [10 + i]} for i in range(7)]
        # No code on the topic -> post_generation_trace (code is generated in-pass, on the artifact).
        topic = {"topic_type": "coding_implementation", "topic_family": "array_sort"}
        res = run_first_pass(
            topic, solver=fake(self._coding_artifact(7)), auditor=none_model, executor=fake_exec
        )
        self.assertTrue(res.ok)
        self.assertEqual(res.reconciliation_telemetry["coverage_after_execution"], "passed")
        self.assertEqual(res.reconciliation_telemetry["reconciliation_status"], "matched")
        self.assertIn("trace_ranges", res.artifact)


if __name__ == "__main__":
    unittest.main()
