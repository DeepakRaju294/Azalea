"""Phase 1 (binary search) tests for the worked-example trace pipeline — fully offline (no LLM)."""
import unittest

from app.services.examples.trace_adapters.binary_search import BinarySearchAdapter
from app.services.examples.trace_contract import (structural_invariants, validate_fidelity, validate_prose)
from app.services.examples import trace_pipeline as tp


def faithful_formatter(trace):
    """A stub formatter that writes correct, fact-respecting prose for each step (one card per step)."""
    def fmt(_payload):
        cards = []
        for s in trace.steps:
            mid, val, tgt = s.inputs["mid"], s.inputs["value"], s.inputs["target"]
            if s.decision == "found":
                work = [f"check mid {mid}: nums[{mid}] = {val}", f"{val} equals target {tgt} — found at index {mid}"]
                result = f"found at index {mid}"
            else:
                side = "right" if s.decision == "go_right" else "left"
                op = "<" if s.decision == "go_right" else ">"
                work = [f"check mid {mid}: nums[{mid}] = {val}", f"{val} {op} target {tgt}, search {side}"]
                result = f"window now [{s.state_after['lo']}, {s.state_after['hi']}]"
            cards.append({"title": f"Probe index {mid}", "goal": "Check the middle element",
                          "reasoning": f"nums[{mid}] = {val}", "work": work, "result": result})
        return {"cards": cards}
    return fmt


class BinarySearchReferenceTests(unittest.TestCase):
    def setUp(self):
        self.adapter = BinarySearchAdapter()

    def _trace(self, nums, target):
        return self.adapter.reference({"nums": nums, "target": target, "_id": "t"}, seed=1)

    def test_reference_finds_correct_index(self):
        tr = self._trace([10, 20, 30, 40, 50, 60, 70], 50)
        self.assertEqual(tr.final_answer, {"found_index": 4})
        self.assertEqual(structural_invariants(tr, self.adapter), [])   # gap-free, entails, invariants hold

    def test_reference_absent_target(self):
        tr = self._trace([10, 20, 30, 40, 50], 35)
        self.assertEqual(tr.final_answer, {"found_index": -1})
        self.assertEqual(structural_invariants(tr, self.adapter), [])

    def test_chain_is_gap_free(self):
        tr = self._trace([1, 3, 5, 7, 9, 11, 13, 15], 3)
        self.assertTrue(self.adapter.states_equivalent(tr.steps[0].prior_state, tr.initial_state))
        for a, b in zip(tr.steps, tr.steps[1:]):
            self.assertTrue(self.adapter.states_equivalent(b.prior_state, a.state_after))

    def test_stage0_selects_a_teaching_instance(self):
        # the chosen instance must exercise both bound moves AND a found/absent case
        trace = tp.select_instance(self.adapter, seed=7)
        self.assertIsNotNone(trace)
        self.assertTrue(self.adapter.is_teaching_trace(trace))


class FidelityTests(unittest.TestCase):
    def setUp(self):
        self.adapter = BinarySearchAdapter()
        self.trace = self.adapter.reference({"nums": [1, 3, 5, 7, 9, 11, 13], "target": 3}, seed=1)
        self.cards = tp._normalize_and_attach(faithful_formatter(self.trace)(None), self.trace)

    def test_faithful_cards_pass_fidelity_and_prose(self):
        self.assertIsNotNone(self.cards)
        self.assertTrue(validate_fidelity(self.cards, self.trace, self.adapter).ok)
        self.assertEqual(validate_prose(self.cards, self.trace, self.adapter), [])

    def test_tampered_machine_state_is_caught(self):
        bad = [dict(c) for c in self.cards]
        bad[0] = dict(bad[0]); bad[0]["result_state"] = {"lo": 99, "hi": 99, "found": None}
        fid = validate_fidelity(bad, self.trace, self.adapter)
        self.assertFalse(fid.ok)
        self.assertEqual(fid.code, "result_mismatch")

    def test_wrong_value_in_prose_is_caught(self):
        bad = [dict(c) for c in self.cards]
        bad[0] = dict(bad[0]); bad[0]["work"] = ["check mid 0: nums[0] = 999"]; bad[0]["result"] = "search right"
        viol = validate_prose(bad, self.trace, self.adapter)
        self.assertTrue(viol)                       # 999 not in allowed_values + required value missing


class OrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.topic = {"id": "bs1", "title": "Understanding Binary Search"}

    def test_routing(self):
        self.assertIsNotNone(tp.route_adapter(self.topic))
        self.assertIsNone(tp.route_adapter({"title": "Understanding Kruskal's Algorithm"}))
        self.assertIsNone(tp.route_adapter({"title": "Graph Algorithms"}))   # no fuzzy routing

    def test_end_to_end_ships_correct_result(self):
        # inject a faithful formatter built from the selected trace
        adapter = tp.route_adapter(self.topic)
        trace = tp.select_instance(adapter, tp._seed_for(self.topic))
        res = tp.solve_trace_pipeline(self.topic, format_fn=faithful_formatter(trace))
        self.assertIsNotNone(res)
        self.assertEqual(res["generated_by"], "trace_pipeline")
        self.assertEqual(len(res["cards"]), len(trace.steps))
        self.assertTrue(all(c.get("trace_step_ids") for c in res["cards"]))

    def test_withholds_on_bad_prose(self):
        res = tp.solve_trace_pipeline(self.topic, format_fn=lambda p: {"cards": [
            {"title": "x", "goal": "g", "reasoning": "r", "work": ["nonsense 999"], "result": "done"}
        ] * 99})
        self.assertIsNone(res)   # wrong card count / bad prose -> withhold

    def test_flag_off_by_default(self):
        self.assertFalse(tp._enabled())


if __name__ == "__main__":
    unittest.main()
