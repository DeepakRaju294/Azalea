"""Shadow generation pipeline — prepass, audit, reconcile, orchestration, metrics.

Pure backend, fully offline (all model calls injected as fakes). No LLM, no DB.
Run: python -m unittest app.tests.test_gen_foundation_pipeline
"""
from __future__ import annotations

import copy
import unittest

from app.services.gen_foundation.audit import PatchBudgetError, apply_patch
from app.services.gen_foundation.metrics import aggregate, compare_to_legacy, measure_run
from app.services.gen_foundation.pipeline import run_first_pass
from app.services.gen_foundation.prepass import build_prepass_config
from app.services.gen_foundation.reconcile import reconcile


# --- fixtures -----------------------------------------------------------------

def simple_artifact(n: int = 5) -> dict:
    cards = [
        {
            "title": f"Step {i+1}", "goal": f"g{i}", "reasoning": "because",
            "work": ["do a thing"], "result": "now true",
            "state_relevance": "none", "state_delta": None, "cases_covered": [f"c{i}"],
        }
        for i in range(n)
    ]
    coverage = {
        "required_cases": {f"c{i}": [f"step_{i+1}"] for i in range(n)},
        "teaching_step_reaching_final": f"step_{n}",
    }
    return {"cards": cards, "projection_coverage": coverage, "final_answer": "answer"}


def coding_cards(n: int = 7) -> list[dict]:
    return [
        {
            "title": f"Step {i+1}", "goal": "g", "how": "the loop appends the next value",
            "work": ["append"], "result": "merged grows", "state_relevance": "stateful",
            "state_delta": {"ops": [{"op": "push", "path": "merged", "value": i}]},
            "primary_kind": "merge", "explanation_mode": "implementation_how",
            "code_refs": [10 + i], "cases_covered": [f"c{i}"],
        }
        for i in range(n)
    ]


def coding_artifact(n: int = 7) -> dict:
    coverage = {
        "required_cases": {f"c{i}": [f"step_{i+1}"] for i in range(n)},
        "teaching_step_reaching_final": f"step_{n}",
    }
    return {
        "cards": coding_cards(n), "initial_resolved_state": {"merged": []},
        "projection_coverage": coverage, "final_answer": "[0,1,2,3,4,5,6]",
    }


def fake(artifact):
    """A solver/auditor that returns a fixed object (deep-copied)."""
    return lambda payload: copy.deepcopy(artifact)


def none_model(payload):
    return None


# --- prepass (§2) -------------------------------------------------------------

class TestPrepass(unittest.TestCase):
    def test_non_coding_is_model_only(self):
        cfg = build_prepass_config({"topic_type": "concept"})
        self.assertEqual(cfg.trace_mode, "model_only")
        self.assertEqual(cfg.example_category, "simple_concept")
        self.assertIsNone(cfg.state_schema)

    def test_coding_generated_in_pass_is_post_generation(self):
        cfg = build_prepass_config({"topic_type": "coding_implementation", "topic_family": "array_sort"})
        self.assertEqual(cfg.trace_mode, "post_generation_trace")
        self.assertEqual(cfg.state_schema, "merge_state_v1")
        self.assertEqual(cfg.example_category, "coding_implementation")

    def test_coding_with_preexisting_code(self):
        cfg = build_prepass_config(
            {"topic_type": "coding_implementation", "topic_family": "array_sort", "code": "def f(): ..."}
        )
        self.assertEqual(cfg.trace_mode, "preexisting_trace")

    def test_recursive_family_uses_complex_band(self):
        cfg = build_prepass_config({"topic_type": "concept", "topic_family": "recursive_divide_and_conquer"})
        self.assertEqual(cfg.example_category, "complex_recursive_dp")
        self.assertEqual(cfg.minimum_example_cards, 8)


# --- patch audit (§8) ---------------------------------------------------------

class TestPatchAudit(unittest.TestCase):
    def setUp(self):
        self.cards = [dict(c, card_id=f"step_{i+1}") for i, c in enumerate(simple_artifact(5)["cards"])]

    def test_pass_no_edits(self):
        out, tele = apply_patch(self.cards, {"status": "pass_no_edits", "edits": []})
        self.assertEqual(tele.audit_status, "pass_no_edits")
        self.assertEqual(len(out), 5)

    def test_replace_field(self):
        patch = {"status": "pass_with_edits",
                 "edits": [{"op": "replace_field", "card_id": "step_2", "field": "title", "value": "New"}]}
        out, tele = apply_patch(self.cards, patch)
        self.assertEqual(out[1]["title"], "New")
        self.assertEqual(tele.patches_applied, 1)
        # original untouched
        self.assertEqual(self.cards[1]["title"], "Step 2")

    def test_delete_and_insert(self):
        patch = {"status": "pass_with_edits", "edits": [
            {"op": "delete_card", "card_id": "step_3"},
            {"op": "insert_card", "after_card_id": "step_1", "card": {"title": "Inserted"}},
        ]}
        out, _ = apply_patch(self.cards, patch)
        self.assertEqual(len(out), 5)  # -1 +1
        self.assertEqual(out[1]["title"], "Inserted")

    def test_budget_too_many_edits(self):
        patch = {"status": "pass_with_edits",
                 "edits": [{"op": "replace_field", "card_id": "step_1", "field": "goal", "value": "x"}] * 6}
        with self.assertRaises(PatchBudgetError):
            apply_patch(self.cards, patch)

    def test_budget_too_many_structural(self):
        patch = {"status": "pass_with_edits", "edits": [
            {"op": "delete_card", "card_id": "step_1"},
            {"op": "delete_card", "card_id": "step_2"},
            {"op": "delete_card", "card_id": "step_3"},
        ]}
        with self.assertRaises(PatchBudgetError):
            apply_patch(self.cards, patch)

    def test_forbidden_op(self):
        with self.assertRaises(PatchBudgetError):
            apply_patch(self.cards, {"status": "pass_with_edits", "edits": [{"op": "rewrite_all"}]})


# --- reconciler (§6.1) --------------------------------------------------------

class TestReconcile(unittest.TestCase):
    def test_no_trace_is_unavailable(self):
        res = reconcile(coding_cards(7), None)
        self.assertEqual(res.coverage_after_execution, "unavailable")
        self.assertFalse(res.execution_succeeded)

    def test_matched_when_refs_valid_and_answer_matches(self):
        cards = coding_cards(7)
        events = [{"code_line_refs": [10 + i]} for i in range(7)]
        res = reconcile(cards, events, model_final_answer="x", executor_final_answer="x")
        self.assertEqual(res.reconciliation_status, "matched")
        self.assertEqual(res.mismatch_severity, "minor")
        self.assertEqual(len(res.attached_ranges), 7)

    def test_mismatched_when_refs_invalid(self):
        cards = coding_cards(7)
        events = [{"code_line_refs": [999]} for _ in range(7)]
        res = reconcile(cards, events, model_final_answer="x", executor_final_answer="x")
        self.assertEqual(res.mismatch_severity, "major")
        self.assertEqual(res.reconciliation_status, "mismatched")

    def test_major_when_final_answer_differs(self):
        cards = coding_cards(7)
        events = [{"code_line_refs": [10 + i]} for i in range(7)]
        res = reconcile(cards, events, model_final_answer="a", executor_final_answer="b")
        self.assertEqual(res.mismatch_severity, "major")


# --- pipeline orchestration (§1, §9.2, §12) -----------------------------------

class TestPipeline(unittest.TestCase):
    def test_happy_path_two_calls(self):
        res = run_first_pass(
            {"topic_type": "concept"}, solver=fake(simple_artifact(5)), auditor=none_model
        )
        self.assertTrue(res.ok)
        self.assertEqual(res.validation_errors, [])
        self.assertEqual(res.model_calls, 2)  # first pass + audit
        self.assertEqual(res.audit_telemetry["audit_status"], "pass_no_edits")

    def test_coding_runs_reconcile_telemetry(self):
        res = run_first_pass(
            {"topic_type": "coding_implementation", "topic_family": "array_sort"},
            solver=fake(coding_artifact(7)), auditor=none_model,
        )
        self.assertTrue(res.ok)
        self.assertEqual(res.reconciliation_telemetry["coverage_after_execution"], "unavailable")

    def test_audit_applies_valid_patch(self):
        patch = {"status": "pass_with_edits",
                 "edits": [{"op": "replace_field", "card_id": "step_2", "field": "title", "value": "Better"}]}
        res = run_first_pass({"topic_type": "concept"}, solver=fake(simple_artifact(5)), auditor=fake(patch))
        self.assertTrue(res.ok)
        self.assertEqual(res.audit_telemetry["audit_status"], "pass_with_edits")
        self.assertEqual(res.artifact["cards"][1]["title"], "Better")

    def test_audit_rejects_patch_that_breaks_validation(self):
        # a patch that pushes work over the 6-line cap must be rejected; first pass ships.
        patch = {"status": "pass_with_edits",
                 "edits": [{"op": "replace_field", "card_id": "step_1", "field": "work", "value": ["x"] * 9}]}
        res = run_first_pass({"topic_type": "concept"}, solver=fake(simple_artifact(5)), auditor=fake(patch))
        self.assertTrue(res.ok)
        self.assertEqual(res.artifact["cards"][0]["work"], ["do a thing"])  # unchanged
        self.assertEqual(res.audit_telemetry["patches_rejected"], 1)

    def test_recovery_repairs_invalid_first_pass(self):
        invalid = simple_artifact(5)
        invalid.pop("final_answer")  # invalid -> recovery
        res = run_first_pass(
            {"topic_type": "concept"}, solver=fake(invalid),
            repair=fake(simple_artifact(5)), auditor=none_model,
        )
        self.assertTrue(res.ok)
        self.assertEqual(res.model_calls, 3)  # first + repair + audit (§9.2)

    def test_degrades_when_repair_fails(self):
        invalid = simple_artifact(5)
        invalid.pop("final_answer")
        res = run_first_pass({"topic_type": "concept"}, solver=fake(invalid), repair=none_model)
        self.assertTrue(res.degraded)
        self.assertEqual(res.artifact.get("worked_example_status"), "withheld_invalid")

    def test_solver_unavailable(self):
        res = run_first_pass({"topic_type": "concept"}, solver=none_model)
        self.assertFalse(res.ok)
        self.assertEqual(res.note, "solver_unavailable")


# --- metrics (§11, §12 step 5) ------------------------------------------------

class TestMetrics(unittest.TestCase):
    def test_measure_and_compare(self):
        res = run_first_pass({"topic_type": "concept"}, solver=fake(simple_artifact(5)), auditor=none_model)
        m = measure_run("t1", res)
        self.assertEqual(m.card_count, 5)
        self.assertTrue(m.first_pass_valid)
        self.assertEqual(m.model_calls, 2)

        legacy = {"cards": [{} for _ in range(8)]}
        comp = compare_to_legacy("t1", res, legacy, legacy_model_calls=5)
        self.assertEqual(comp.calls_delta, 2 - 5)  # shadow cheaper
        agg = aggregate([comp])
        self.assertEqual(agg["n"], 1)
        self.assertEqual(agg["first_pass_validity_rate"], 1.0)
        self.assertEqual(agg["avg_calls_delta"], -3.0)


if __name__ == "__main__":
    unittest.main()
