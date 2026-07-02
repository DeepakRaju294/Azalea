"""Phase 1 (binary search) tests for the worked-example trace pipeline — fully offline (no LLM)."""
import unittest

from app.services.examples.trace_adapters.families.sequence import BinarySearchAdapter
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
        self.assertEqual(tp.route_adapter(self.topic).slug, "binary_search")
        self.assertEqual(tp.route_adapter({"title": "Understanding Kruskal's Algorithm"}).slug, "kruskal")
        self.assertIsNone(tp.route_adapter({"title": "Graph Algorithms"}))   # no fuzzy routing

    def test_graph_bfs_dfs_route_but_tree_traversal_does_not(self):
        # graph BFS/DFS (visited-set, cycles) route to the graph adapters...
        self.assertEqual(tp.route_adapter({"title": "Breadth-First Search on a graph"}).slug, "bfs")
        self.assertEqual(tp.route_adapter({"title": "Depth-First Search traversal"}).slug, "dfs_iter")
        # ...and TREE traversal is a DIFFERENT algorithm — it routes to its own tree adapter, NEVER the graph one
        self.assertEqual(tp.route_adapter({"title": "Level-order traversal of a binary tree"}).slug, "tree_levelorder")
        self.assertEqual(tp.route_adapter({"title": "Preorder traversal of a BST"}).slug, "tree_preorder")
        self.assertEqual(tp.route_adapter({"title": "Postorder traversal of a tree"}).slug, "tree_postorder")
        self.assertEqual(tp.route_adapter({"title": "DFS preorder traversal of a tree"}).slug, "tree_preorder")
        # a binary-search TREE is not array binary search
        self.assertIsNone(tp.route_adapter({"title": "Binary Search Tree insertion"}))
        self.assertEqual(tp.route_adapter({"title": "Binary Search in a sorted array"}).slug, "binary_search")

    def test_raw_dict_result_replaced_with_prose_and_completion(self):
        # C7: a formatter that echoes the raw state dict (old coding behavior) -> result becomes the verified
        # prose EVR; the last card states completion. Both are deterministic + trace-preserving.
        topic = {"title": "Understanding Kruskal's Algorithm"}
        adapter = tp.route_adapter(topic)
        trace = tp.select_instance(adapter, tp._seed_for(topic))
        raw = {"cards": [{"title": "t", "goal": "", "reasoning": "r", "work": ["w"],
                          "result": str(s.state_after)} for s in trace.steps]}
        cards = tp._normalize_and_attach(raw, trace)
        self.assertIsNotNone(cards)
        self.assertFalse(any(str(c["result"]).startswith("{") for c in cards))   # no raw dict survives
        self.assertEqual(cards[0]["result"], trace.steps[0].expected_visible_result)  # verified prose
        self.assertRegex(cards[-1]["result"].lower(), r"complete|final")          # completion stated
        self.assertEqual(cards[0]["result_state"], trace.steps[0].state_after)    # raw state kept for the panel

    def test_end_to_end_ships_correct_result(self):
        # inject a faithful formatter built from the selected trace
        adapter = tp.route_adapter(self.topic)
        trace = tp.select_instance(adapter, tp._seed_for(self.topic))
        res = tp.solve_trace_pipeline(self.topic, format_fn=faithful_formatter(trace))
        self.assertIsNotNone(res)
        self.assertEqual(res["generated_by"], "trace_pipeline")
        self.assertEqual(len(res["cards"]), len(trace.steps))
        self.assertTrue(all(c.get("trace_step_ids") for c in res["cards"]))

    def test_bad_narration_ships_trace_preserving_not_none(self):
        # SPEC §1.2/§4.3.1 step 2: a bad/contradicting LLM narration no longer withholds-to-None (which fell
        # to a from-scratch fallback). It ships a trace-preserving deterministic narration of the SAME trace.
        adapter = tp.route_adapter(self.topic)
        trace = tp.select_instance(adapter, tp._seed_for(self.topic))
        res = tp.solve_trace_pipeline(self.topic, format_fn=lambda p: {"cards": [
            {"title": "x", "goal": "g", "reasoning": "r", "work": ["nonsense 999"], "result": "done"}
        ] * 99})
        self.assertIsNotNone(res)
        self.assertEqual(res["generated_by"], "trace_pipeline")
        self.assertEqual(len(res["cards"]), len(trace.steps))            # one card per verified step
        self.assertTrue(all(c.get("trace_step_ids") for c in res["cards"]))
        self.assertFalse(any("nonsense" in str(c.get("work")) for c in res["cards"]))  # not the bad prose

    def test_flag_off_by_default(self):
        self.assertFalse(tp._enabled())


if __name__ == "__main__":
    unittest.main()
