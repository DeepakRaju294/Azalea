"""The redundant formula-family 'Step 1: Knowns' restatement is folded onto the setup card and dropped, with
the step-count contract kept consistent. A real first step (identify_coefficients, ...) is left alone."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples.solver import _build_solution_cards, _fold_redundant_knowns_step


def _sol_with_knowns():
    return {
        "problem": "Events B1 and B2 partition the sample space with P(B1)=0.7 ... Find P(A).",
        "expected_final_answer": "P_A = 0.62", "expected_steps": 3, "full_steps": 3,
        "cards": [
            {"title": "Knowns", "goal": "",
             "reasoning": "the given quantities are P(B1) = 0.7, P(A|B1) = 0.8, P(A|B2) = 0.2",
             "work": ["P(B1) = 0.7, P(A|B1) = 0.8, P(A|B2) = 0.2"],
             "result": "Knowns: P(B1) = 0.7, P(A|B1) = 0.8, P(A|B2) = 0.2."},
            {"title": "The remaining partition probability", "goal": "",
             "reasoning": "P(B2) = 1 - P(B1) = 0.3", "work": ["P(B2) = 0.3"],
             "result": "the remaining partition probability: P(B2) = 1 - P(B1) = 0.3."},
            {"title": "Total probability", "goal": "",
             "reasoning": "P(A) = P(A|B1)*P(B1) + P(A|B2)*P(B2) = 0.62", "work": ["P(A) = 0.62"],
             "result": "total probability: P(A) = 0.62."},
        ],
    }


class FoldKnowns(unittest.TestCase):
    def test_knowns_folded_and_count_decremented(self):
        sol = _sol_with_knowns()
        _fold_redundant_knowns_step(sol)
        self.assertEqual(len(sol["cards"]), 2)                       # knowns step dropped
        self.assertFalse(any(str(c.get("result", "")).startswith("Knowns:") for c in sol["cards"]))
        self.assertEqual(sol["expected_steps"], 2)                   # contract decremented to match
        self.assertEqual(sol["full_steps"], 2)
        self.assertIn("P(B1) = 0.7", sol["setup_givens"])           # givens captured for the setup card

    def test_setup_card_lists_givens_and_first_step_is_a_computation(self):
        sol = _sol_with_knowns()
        _fold_redundant_knowns_step(sol)
        cards = _build_solution_cards(sol, {"id": "t1"})
        self.assertTrue(any(str(p).startswith("Given:") for p in cards[0]["points"]))   # setup lists givens
        self.assertNotIn("Knowns", " ".join(str(p) for p in cards[1]["points"]))        # step 1 is real work
        self.assertIn("remaining partition", " ".join(str(p) for p in cards[1]["points"]).lower())

    def test_idempotent(self):
        sol = _sol_with_knowns()
        _fold_redundant_knowns_step(sol)
        _fold_redundant_knowns_step(sol)                            # second call is a no-op
        self.assertEqual(len(sol["cards"]), 2)
        self.assertEqual(sol["expected_steps"], 2)

    def test_real_first_step_is_left_alone(self):
        sol = {"problem": "Solve x^2 - 3x + 2 = 0.", "expected_steps": 3, "full_steps": 3, "cards": [
            {"title": "Coefficients", "reasoning": "read off the coefficients",
             "result": "coefficients: a = 1, b = -3, c = 2."},
            {"title": "Discriminant", "reasoning": "b^2 - 4ac", "result": "discriminant: 1."},
        ]}
        _fold_redundant_knowns_step(sol)
        self.assertEqual(len(sol["cards"]), 2)                       # untouched (not a knowns restatement)
        self.assertEqual(sol["expected_steps"], 3)
        self.assertNotIn("setup_givens", sol)


if __name__ == "__main__":
    unittest.main()
