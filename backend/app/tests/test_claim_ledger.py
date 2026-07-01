"""Typed claim ledger (ADAPTER_DEVELOPMENT_SPEC §7): a named derived/output quantity must be stated with ITS
value — a formula constant can't be passed off as the answer. Conservative: it only fires on an explicit
`name <copula> number`, so faithful prose is never flagged."""
import unittest

from app.services.examples.trace_adapters import ADAPTERS
from app.services.examples.trace_contract import claim_ledger, validate_claim_ledger, validate_prose
from app.services.examples.trace_pipeline import select_instance


class ClaimLedgerUnit(unittest.TestCase):
    _L = claim_ledger(inputs={"a": 1, "b": -5, "c": 6}, constants={"square": 2, "four": 4},
                      derived={"D": 1}, outputs={"roots": [2, 3]})

    def test_correct_claim_passes(self):
        self.assertEqual(validate_claim_ledger("the discriminant D = 1, so two real roots", self._L, 0, "s"), [])

    def test_formula_constant_stated_as_derived_is_caught(self):
        # "D = 4" — 4 is only the formula constant, the discriminant is 1
        v = validate_claim_ledger("here D = 4 which is positive", self._L, 0, "s")
        self.assertEqual([x.code for x in v], ["mislabeled_value"])

    def test_wrong_output_is_caught(self):
        v = validate_claim_ledger("the roots are 5", self._L, 0, "s")
        self.assertEqual([x.code for x in v], ["mislabeled_value"])

    def test_no_named_claim_is_inert(self):
        self.assertEqual(validate_claim_ledger("we substitute and simplify", self._L, 0, "s"), [])


class ClaimLedgerOnQuadratic(unittest.TestCase):
    def test_quadratic_discriminant_step_declares_a_ledger(self):
        trace = select_instance(ADAPTERS["quadratic"], seed=7)
        disc_step = next(s for s in trace.steps if s.operation == "compute_discriminant")
        ledger = disc_step.facts.get("claims")
        self.assertIsInstance(ledger, dict)
        self.assertIn("D", ledger["derived"])

    def test_faithful_quadratic_prose_is_not_flagged(self):
        # the real trace's own prose must never trip the ledger (soundness)
        trace = select_instance(ADAPTERS["quadratic"], seed=7)
        cards = [{"trace_step_ids": [s.id], "reasoning": s.reason, "work": [], "result": s.expected_visible_result}
                 for s in trace.steps]
        flagged = [v for v in validate_prose(cards, trace, ADAPTERS["quadratic"]) if v.code == "mislabeled_value"]
        self.assertEqual(flagged, [])


if __name__ == "__main__":
    unittest.main()
