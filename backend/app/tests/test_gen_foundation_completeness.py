"""Tests for the Layer 0 completeness gate (gen_foundation)."""
import unittest

from app.services.gen_foundation.completeness import (
    completeness_errors, step_reaching_final, _answer_signature,
)


def card(result, work=None):
    return {"result": result, "work": work or []}


class SignatureTests(unittest.TestCase):
    def test_scalar_uses_last_number(self):
        sig = _answer_signature("Total MST weight: 57")
        self.assertEqual(sig, {"checkable": True, "kind": "scalar", "result_value": "57"})

    def test_sequence_preferred(self):
        sig = _answer_signature("Sorted array: [1, 2, 3, 6, 8, 10]")
        self.assertEqual(sig["kind"], "sequence")
        self.assertEqual(sig["sequence"], ["1", "2", "3", "6", "8", "10"])

    def test_textual_not_checkable(self):
        self.assertFalse(_answer_signature("the list is now sorted").get("checkable"))
        self.assertFalse(_answer_signature("").get("checkable"))


class CompletenessTests(unittest.TestCase):
    def test_truncated_prims_fails(self):
        # claims MST weight 57, but the cards stop mid-run and 57 appears nowhere
        artifact = {
            "final_answer": "Minimum spanning tree weight: 57",
            "step_ids": ["step_1", "step_2"],
            "cards": [card("Start at A; add edges (B,31),(C,3)"),
                      card("Add edge B–C, running total 30")],
        }
        errs = completeness_errors(artifact)
        self.assertTrue(errs and "final_answer" in errs[0])
        self.assertIsNone(step_reaching_final(artifact["cards"], artifact["step_ids"], "weight 57"))

    def test_complete_run_passes(self):
        artifact = {
            "final_answer": "Minimum spanning tree weight: 57",
            "step_ids": ["step_1", "step_2", "step_3"],
            "cards": [card("Add edge D–E, total 1"),
                      card("Add edge F–G, total 4"),
                      card("All vertices included. Total MST weight: 57")],
        }
        self.assertEqual(completeness_errors(artifact), [])
        self.assertEqual(
            step_reaching_final(artifact["cards"], artifact["step_ids"], "weight 57"), "step_3")

    def test_sequence_answer_reached(self):
        artifact = {
            "final_answer": "Final sorted array: [1, 2, 3, 6, 8, 10]",
            "step_ids": ["step_1", "step_2"],
            "cards": [card("Partition around pivot"),
                      card("Merge to get [1, 2, 3, 6, 8, 10]")],
        }
        self.assertEqual(completeness_errors(artifact), [])

    def test_word_boundary_no_false_match(self):
        # answer value 57 must not be 'reached' by a card that only contains 157
        artifact = {
            "final_answer": "total 57",
            "step_ids": ["step_1"],
            "cards": [card("the running cost is 157 so far")],
        }
        self.assertTrue(completeness_errors(artifact))

    def test_textual_answer_skips_gate(self):
        artifact = {
            "final_answer": "the BST now satisfies the ordering invariant",
            "step_ids": ["step_1"],
            "cards": [card("insert 5 under 3")],
        }
        self.assertEqual(completeness_errors(artifact), [])  # not checkable -> not a failure

    def test_picks_last_reaching_step(self):
        # 57 appears in an early card too; the TERMINAL (last) match is the reaching step
        cards = [card("intermediate note mentioning 57"),
                 card("more work"),
                 card("Total MST weight: 57")]
        self.assertEqual(step_reaching_final(cards, ["a", "b", "c"], "weight 57"), "c")


if __name__ == "__main__":
    unittest.main()
