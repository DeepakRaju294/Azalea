"""Generation-foundation schemas + deterministic validators (spec §12 step 1).

Pure backend, no LLM. Run: python -m unittest app.tests.test_gen_foundation
"""
from __future__ import annotations

import unittest

from app.services.gen_foundation import trace as trace_mod
from app.services.gen_foundation.state import (
    DEFAULT_BOUNDS,
    InvalidStateDeltaError,
    StateBounds,
    apply_delta,
    derive_chain,
    get_schema,
    validate_delta_bounds,
    validate_state_bounds,
)
from app.services.gen_foundation.cards import is_coding_card
from app.services.gen_foundation.validators import (
    validate_card,
    validate_confidence_meta,
    validate_projection_caps,
    validate_projection_coverage,
    validate_state_chain,
    validate_trace_event_budget,
)

MERGE = get_schema("merge_state_v1")


# --- semantic state keystone (§7, §7.1) ---------------------------------------

class TestStateDelta(unittest.TestCase):
    def test_apply_delta_is_pure(self):
        before = {"merged": [2, 3], "i": 1}
        delta = {"ops": [{"op": "append", "path": "merged", "values": [4]},
                         {"op": "set", "path": "i", "value": 2}]}
        after = apply_delta(before, delta, MERGE)
        self.assertEqual(after["merged"], [2, 3, 4])
        self.assertEqual(after["i"], 2)
        # input untouched
        self.assertEqual(before, {"merged": [2, 3], "i": 1})

    def test_undeclared_path_rejected(self):
        with self.assertRaises(InvalidStateDeltaError):
            apply_delta({}, {"ops": [{"op": "set", "path": "not_a_path", "value": 1}]}, MERGE)

    def test_append_to_scalar_rejected(self):
        with self.assertRaises(InvalidStateDeltaError):
            apply_delta({}, {"ops": [{"op": "append", "path": "i", "values": [1]}]}, MERGE)

    def test_add_requires_number_path(self):
        with self.assertRaises(InvalidStateDeltaError):
            apply_delta({}, {"ops": [{"op": "add", "path": "merged", "value": 1}]}, MERGE)
        out = apply_delta({"i": 1}, {"ops": [{"op": "add", "path": "i", "value": 2}]}, MERGE)
        self.assertEqual(out["i"], 3)

    def test_pop_empty_rejected(self):
        with self.assertRaises(InvalidStateDeltaError):
            apply_delta({"merged": []}, {"ops": [{"op": "pop", "path": "merged"}]}, MERGE)

    def test_move_between_lists(self):
        graph = get_schema("graph_traversal_v1")
        out = apply_delta(
            {"frontier": ["A", "B"], "visited": []},
            {"ops": [{"op": "move", "path": "visited", "source": "frontier"}]},
            graph,
        )
        self.assertEqual(out["frontier"], ["A"])
        self.assertEqual(out["visited"], ["B"])

    def test_unknown_op_rejected(self):
        with self.assertRaises(InvalidStateDeltaError):
            apply_delta({}, {"ops": [{"op": "frobnicate", "path": "i"}]}, MERGE)


class TestDeriveChain(unittest.TestCase):
    def test_chain_folds_in_order(self):
        initial = {"merged": [], "i": 0, "j": 0}
        deltas = [
            {"ops": [{"op": "push", "path": "merged", "value": 2}, {"op": "add", "path": "i", "value": 1}]},
            None,  # a static/none step carries state forward
            {"ops": [{"op": "push", "path": "merged", "value": 3}, {"op": "add", "path": "j", "value": 1}]},
        ]
        snaps = derive_chain(initial, deltas, MERGE)
        self.assertEqual(snaps[0]["merged"], [2])
        self.assertEqual(snaps[1]["merged"], [2])  # unchanged on None
        self.assertEqual(snaps[2]["merged"], [2, 3])
        self.assertEqual(snaps[2]["i"], 1)
        self.assertEqual(snaps[2]["j"], 1)
        # snapshots are independent objects
        self.assertIsNot(snaps[0], snaps[1])


class TestStateBounds(unittest.TestCase):
    def test_too_many_ops_flagged(self):
        delta = {"ops": [{"op": "add", "path": "i", "value": 1}] * 99}
        self.assertTrue(validate_delta_bounds(delta, StateBounds(max_ops_per_delta=5)))

    def test_giant_collection_flagged(self):
        out = validate_state_bounds({"merged": list(range(100))}, StateBounds(max_collection_len=10))
        self.assertTrue(any("collection length" in e for e in out))

    def test_within_bounds_ok(self):
        self.assertEqual(validate_delta_bounds({"ops": [{"op": "add", "path": "i", "value": 1}]}), [])


# --- card contracts (§4) ------------------------------------------------------

class TestCardContracts(unittest.TestCase):
    def _base(self, **over):
        card = {"title": "t", "goal": "g", "reasoning": "r", "work": ["a"], "result": "x",
                "state_relevance": "none", "state_delta": None}
        card.update(over)
        return card

    def _coding(self, **over):
        card = {"title": "t", "goal": "g", "how": "the loop appends the smaller",
                "work": ["2<3 append 2"], "result": "merged=[2]", "state_relevance": "stateful",
                "state_delta": {"ops": [{"op": "push", "path": "merged", "value": 2}]},
                "primary_kind": "merge", "explanation_mode": "implementation_how",
                "code_refs": [14, 15]}
        card.update(over)
        return card

    def test_is_coding_card(self):
        self.assertTrue(is_coding_card(self._coding()))
        self.assertFalse(is_coding_card(self._base()))

    def test_base_card_valid(self):
        self.assertEqual(validate_card(self._base()), [])

    def test_coding_card_valid(self):
        self.assertEqual(validate_card(self._coding()), [])

    def test_coding_card_with_reasoning_rejected(self):
        out = validate_card(self._coding(reasoning="abstract"))
        self.assertTrue(any("must use 'how'" in e for e in out))

    def test_stateful_requires_delta(self):
        out = validate_card(self._base(state_relevance="stateful"))
        self.assertTrue(any("requires a non-null state_delta" in e for e in out))

    def test_static_forbids_delta(self):
        card = self._coding(state_relevance="static")
        out = validate_card(card)
        self.assertTrue(any("must have state_delta == null" in e for e in out))

    def test_bad_code_refs_rejected(self):
        out = validate_card(self._coding(code_refs=[0, -1, "x"]))
        self.assertTrue(any("code_refs" in e for e in out))

    def test_too_many_work_lines_flagged(self):
        out = validate_card(self._base(work=["a"] * 9))
        self.assertTrue(any("work lines" in e for e in out))


# --- state chain validator (§7/§9) --------------------------------------------

class TestStateChainValidator(unittest.TestCase):
    def test_valid_chain(self):
        cards = [
            {"state_delta": {"ops": [{"op": "push", "path": "merged", "value": 2}]}},
            {"state_delta": None},
            {"state_delta": {"ops": [{"op": "push", "path": "merged", "value": 3}]}},
        ]
        self.assertEqual(validate_state_chain({"merged": []}, cards, MERGE), [])

    def test_broken_delta_reported_and_stops(self):
        cards = [
            {"state_delta": {"ops": [{"op": "set", "path": "nope", "value": 1}]}},
            {"state_delta": {"ops": [{"op": "push", "path": "merged", "value": 3}]}},
        ]
        out = validate_state_chain({"merged": []}, cards, MERGE)
        self.assertTrue(any("does not resolve" in e for e in out))


# --- projection caps (§5.2) ---------------------------------------------------

class TestProjectionCaps(unittest.TestCase):
    def test_count_within_band_ok(self):
        cards = [{} for _ in range(8)]
        self.assertEqual(validate_projection_caps("coding_implementation", cards), [])

    def test_below_minimum_flagged(self):
        out = validate_projection_caps("coding_implementation", [{} for _ in range(3)])
        self.assertTrue(any("minimum" in e for e in out))

    def test_above_cap_flagged_split_topic(self):
        # caps raised so complete algorithm traces ship; only an absurd length is still rejected
        out = validate_projection_caps("coding_implementation", [{} for _ in range(55)])
        self.assertTrue(any("split the topic" in e for e in out))

    def test_absolute_ceiling(self):
        res = trace_mod.check_card_count("complex_recursive_dp", 55)
        self.assertFalse(res.ok)

    def test_event_budget(self):
        self.assertEqual(validate_trace_event_budget(12, False), [])
        self.assertTrue(validate_trace_event_budget(13, False))
        self.assertEqual(validate_trace_event_budget(20, True), [])
        self.assertTrue(validate_trace_event_budget(21, True))

    def test_unknown_category_raises(self):
        with self.assertRaises(ValueError):
            trace_mod.caps_for_category("nope")


# --- projection coverage (§9.1), mode-aware -----------------------------------

class TestProjectionCoverage(unittest.TestCase):
    def _cov(self):
        return {
            "required_cases": {"split": ["step_1"], "merge": ["step_3"]},
            "final_trace_event": "e30",
            "teaching_step_reaching_final": "step_3",
        }

    def test_semantic_coverage_ok_model_only(self):
        out = validate_projection_coverage(
            self._cov(), ["split", "merge"], ["step_1", "step_2", "step_3"], "model_only"
        )
        self.assertEqual(out, [])

    def test_uncovered_case_flagged(self):
        cov = self._cov()
        out = validate_projection_coverage(
            cov, ["split", "merge", "tail_copy"], ["step_1", "step_3"], "post_generation_trace"
        )
        self.assertTrue(any("tail_copy" in e for e in out))

    def test_case_maps_to_unknown_step(self):
        cov = self._cov()
        cov["required_cases"]["split"] = ["ghost"]
        out = validate_projection_coverage(cov, ["split", "merge"], ["step_1", "step_3"], "model_only")
        self.assertTrue(any("unknown step" in e for e in out))

    def test_final_step_must_exist(self):
        cov = self._cov()
        cov["teaching_step_reaching_final"] = "ghost"
        out = validate_projection_coverage(cov, ["split", "merge"], ["step_1", "step_3"], "model_only")
        self.assertTrue(any("not a real step" in e for e in out))

    def test_trace_backed_requires_event_in_range(self):
        cov = self._cov()
        # canonical mode with trace ranges: split's event (5) falls outside step_1's range -> error
        out = validate_projection_coverage(
            cov, ["split", "merge"], ["step_1", "step_3"], "canonical",
            step_trace_ranges={"step_1": {"start": 0, "end": 2}, "step_3": {"start": 10, "end": 30}},
            case_event_index={"split": 5, "merge": 12},
            final_trace_event_index=30,
        )
        self.assertTrue(any("trace_range contains its event" in e for e in out))

    def test_trace_backed_passes_when_in_range(self):
        cov = self._cov()
        out = validate_projection_coverage(
            cov, ["split", "merge"], ["step_1", "step_3"], "canonical",
            step_trace_ranges={"step_1": {"start": 0, "end": 6}, "step_3": {"start": 10, "end": 30}},
            case_event_index={"split": 5, "merge": 12},
            final_trace_event_index=30,
        )
        self.assertEqual(out, [])


# --- trace confidence metadata (§6.3) + modes ---------------------------------

class TestTraceMeta(unittest.TestCase):
    def test_valid_meta(self):
        meta = {"trace_mode": "post_generation_trace", "trace_confidence": "high",
                "trace_validation_status": "passed"}
        self.assertEqual(validate_confidence_meta(meta), [])

    def test_bad_enum_flagged(self):
        out = validate_confidence_meta({"trace_mode": "weird", "trace_confidence": "x",
                                        "trace_validation_status": "y"})
        self.assertEqual(len(out), 3)

    def test_trace_field_owner_by_mode(self):
        self.assertEqual(trace_mod.trace_field_owner("post_generation_trace"), "reconciler")
        self.assertEqual(trace_mod.trace_field_owner("preexisting_trace"), "model")
        self.assertEqual(trace_mod.trace_field_owner("canonical"), "deterministic")
        self.assertEqual(trace_mod.trace_field_owner("model_only"), "none")

    def test_reconciliation_threshold(self):
        minor = dict(final_answer_matches=True, execution_succeeded=True, unaligned_cards=1,
                     coverage_holds=True, invalid_code_refs_percent=10.0)
        self.assertEqual(trace_mod.classify_reconciliation(**minor), "minor")
        major = {**minor, "unaligned_cards": 3}
        self.assertEqual(trace_mod.classify_reconciliation(**major), "major")
        major2 = {**minor, "final_answer_matches": False}
        self.assertEqual(trace_mod.classify_reconciliation(**major2), "major")


if __name__ == "__main__":
    unittest.main()
