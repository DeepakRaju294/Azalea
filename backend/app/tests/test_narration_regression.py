"""Phase-2 regression fixtures — no cross-domain leakage (DOMAIN_CARD_NARRATION_AND_RENDERING_SPEC §8).

Asserted at the narration-contract + eligibility-gate level (the invasive pipeline wiring is 2B). Each fixture
proves one domain's cards get their own framing and CANNOT pick up another domain's scaffold or a forbidden card.

Run: python -m unittest app.tests.test_narration_regression
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.narration import contracts, matrix


class CompletingTheSquare(unittest.TestCase):
    """§8 fixture 1 — math derivation framing, no loop template, no complexity card."""

    def test_process_is_math_scaffold_not_loop(self):
        c = contracts.narration_contract_for("math")
        self.assertEqual(c.process_scaffold, ("Setup", "Operation", "Result", "Why"))
        self.assertNotIn("Loop / repeated action", c.process_scaffold)

    def test_complexity_card_is_safety_failure_on_math(self):
        d = matrix.evaluate_card("complexity_analysis", "math", blueprint_optional=False)
        self.assertEqual(d.action, matrix.SAFETY_FAILURE)

    def test_formula_breakdown_defined_for_math(self):
        self.assertEqual(matrix.card_status("formula_breakdown", "math"), matrix.DEFINED)


class NewtonsSecondLaw(unittest.TestCase):
    """§8 fixture 2 — science calculation framing; units in the result; interpretation never invented."""

    def test_result_field_carries_units_and_interpretation_framing(self):
        c = contracts.narration_contract_for("physics")
        self.assertEqual(c.domain, "science")
        self.assertIn("units", c.worked_example_fields["result"])
        self.assertIn("interpretation", c.worked_example_fields["result"])

    def test_no_complexity_or_coding_leak_on_science(self):
        self.assertEqual(
            matrix.evaluate_card("complexity_analysis", "science", blueprint_optional=False).action,
            matrix.SAFETY_FAILURE)
        self.assertEqual(matrix.card_status("code_walkthrough", "science"), matrix.NOT_APPLICABLE)

    def test_science_process_is_principle_apply_interpret(self):
        self.assertEqual(contracts.narration_contract_for("science").process_scaffold,
                         ("Principle", "Apply", "Interpret"))


class DFSWalkthrough(unittest.TestCase):
    """§8 fixture 3 — code-state framing intact; no math/science template leaks."""

    def test_coding_process_has_loop_scaffold(self):
        c = contracts.narration_contract_for("coding")
        self.assertIn("Loop / repeated action", c.process_scaffold)
        self.assertEqual(c.worked_example_fields["work"], "the code line (+ trace)")

    def test_complexity_defined_but_formula_breakdown_not_applicable(self):
        self.assertEqual(matrix.card_status("complexity_analysis", "coding"), matrix.DEFINED)
        self.assertEqual(matrix.card_status("formula_breakdown", "coding"), matrix.NOT_APPLICABLE)


class WhatIsInflation(unittest.TestCase):
    """§8 fixture 4 — concept framing uses Idea→Structure→Example; no STEM scaffolds leak."""

    def test_concept_scaffold(self):
        c = contracts.narration_contract_for("economics")           # expository → concept
        self.assertEqual(c.domain, "concept")
        self.assertEqual(c.process_scaffold, ("Idea", "Structure", "Example"))

    def test_no_formula_method_or_complexity_or_mechanism_leak(self):
        for card in ("formula_breakdown", "complexity_analysis", "code_walkthrough"):
            self.assertEqual(matrix.card_status(card, "concept"), matrix.NOT_APPLICABLE, card)

    def test_worked_example_is_concept_framed(self):
        c = contracts.narration_contract_for("humanities")
        self.assertEqual(c.worked_example_fields["work"], "example / comparison / evidence")


if __name__ == "__main__":
    unittest.main()
