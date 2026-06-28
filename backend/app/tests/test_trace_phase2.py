"""Phase 2/3 framework tests: arithmetic verifier, the critic seam, and reason→extract — offline."""
import os
import unittest

from app.services.examples import trace_pipeline as tp
from app.services.examples.trace_adapters import ADAPTERS
from app.services.examples.trace_adapters.families.formula import _eval
from app.services.examples.verifiers import verify_arithmetic, verify_via_critic
from app.services.examples.reason_extract import produce_via_reason_extract
from app.services.examples.trace_contract import Step, structural_invariants


class ArithmeticTests(unittest.TestCase):
    def setUp(self):
        self.a = ADAPTERS["arithmetic_eval"]

    def test_reference_respects_precedence(self):
        tr = self.a.reference({"tokens": [3, "+", 4, "*", 2]})         # 3 + 8 = 11
        self.assertEqual(tr.final_answer, {"value": 11})
        self.assertEqual(structural_invariants(tr, self.a), [])
        self.assertTrue(verify_arithmetic(tr).ok)
        self.assertEqual(_eval([3, "+", 4, "*", 2]), 11)

    def test_verifier_catches_a_wrong_step(self):
        tr = self.a.reference({"tokens": [3, "+", 4, "*", 2]})
        # corrupt one step's claimed result
        bad_steps = list(tr.steps)
        s = bad_steps[0]
        bad_steps[0] = Step(id=s.id, operation=s.operation, prior_state=s.prior_state,
                            state_after=s.state_after, inputs={**s.inputs, "result": 999})
        from dataclasses import replace
        bad = replace(tr, steps=bad_steps)
        v = verify_arithmetic(bad)
        self.assertFalse(v.ok)
        self.assertEqual(v.illegal_step["id"], s.id)


class CriticTests(unittest.TestCase):
    def _trace(self):
        return ADAPTERS["arithmetic_eval"].reference({"tokens": [2, "+", 3]})

    def test_critic_unavailable_is_soft_pass(self):
        v = verify_via_critic(self._trace(), critic_fn=lambda p: None)
        self.assertTrue(v.ok)
        self.assertIn("critic_unavailable_soft_pass", v.errors)

    def test_critic_blocks_on_illegal_step(self):
        v = verify_via_critic(self._trace(), critic_fn=lambda p: {"illegal_step": {"id": "s1", "reason": "bad"}})
        self.assertFalse(v.ok)
        self.assertEqual(v.illegal_step["id"], "s1")

    def test_critic_clean_passes(self):
        self.assertTrue(verify_via_critic(self._trace(), critic_fn=lambda p: {"illegal_step": None}).ok)


class ReasonExtractTests(unittest.TestCase):
    def test_stub_reason_extract_builds_a_trace(self):
        reason = lambda p: "Step 1: 2 + 3 = 5. FINAL ANSWER: 5"
        extract = lambda p: {"problem": "2+3", "initial_state": {"tokens": [2, "+", 3]},
                             "final_answer": {"value": 5},
                             "steps": [{"id": "s1", "operation": "apply_op",
                                        "inputs": {"a": 2, "op": "+", "b": 3, "result": 5},
                                        "prior_state": {"tokens": [2, "+", 3]}, "state_after": {"tokens": [5]},
                                        "reason": "add"}]}
        tr = produce_via_reason_extract({"title": "x"}, {"tokens": [2, "+", 3]},
                                        reason_fn=reason, extract_fn=extract)
        self.assertIsNotNone(tr)
        self.assertEqual(len(tr.steps), 1)
        self.assertEqual(tr.provenance["source"], "reason_extract")
        self.assertTrue(verify_arithmetic(tr).ok)

    def test_unavailable_returns_none(self):
        self.assertIsNone(produce_via_reason_extract({"title": "x"}, {}, reason_fn=lambda p: None,
                                                     extract_fn=lambda p: {}))


class ReasonExtractWiringTests(unittest.TestCase):
    """The non-deterministic path: a topic with no deterministic adapter routes through reason→extract."""
    def setUp(self):
        os.environ["AZALEA_WORKED_EXAMPLE_REASON_EXTRACT"] = "1"

    def tearDown(self):
        os.environ.pop("AZALEA_WORKED_EXAMPLE_REASON_EXTRACT", None)

    _EXTRACT = {"problem": "P", "initial_state": {"s": 0}, "final_answer": {"s": 1},
                "steps": [{"id": "s1", "operation": "op", "inputs": {}, "prior_state": {"s": 0},
                           "state_after": {"s": 1}, "reason": "advance",
                           "facts": {"allowed_values": [], "required_facts": [], "forbidden_claims": []}}]}
    _FMT = {"cards": [{"title": "t", "goal": "g", "reasoning": "r", "work": ["w"], "result": "done"}]}

    def test_non_deterministic_topic_ships_via_reason_extract(self):
        res = tp.solve_trace_pipeline(
            {"title": "Proof by Induction"}, format_fn=lambda p: self._FMT,
            reason_fn=lambda p: "…FINAL ANSWER: ok", extract_fn=lambda p: self._EXTRACT,
            critic_fn=lambda p: {"illegal_step": None})
        self.assertIsNotNone(res)
        self.assertEqual(res["generated_by"], "trace_pipeline")
        self.assertEqual(res["metadata"]["provenance"]["source"], "reason_extract")

    def test_critic_rejection_withholds(self):
        res = tp.solve_trace_pipeline(
            {"title": "Proof by Induction"}, format_fn=lambda p: self._FMT,
            reason_fn=lambda p: "x", extract_fn=lambda p: self._EXTRACT,
            critic_fn=lambda p: {"illegal_step": {"id": "s1", "reason": "invalid"}})
        self.assertIsNone(res)

    def test_disabled_by_default_defers(self):
        os.environ.pop("AZALEA_WORKED_EXAMPLE_REASON_EXTRACT", None)   # flag off
        self.assertIsNone(tp.solve_trace_pipeline({"title": "Proof by Induction"},
                                                  reason_fn=lambda p: "x", extract_fn=lambda p: self._EXTRACT))


if __name__ == "__main__":
    unittest.main()
