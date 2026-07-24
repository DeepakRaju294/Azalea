"""T13 line-integral adapter (vector-calculus family, second hand-coded member — closes part of the
"only 1 example throughout path" gap on Stokes'-theorem paths). Proves: (1) both hand-picked examples
produce a structurally valid teaching trace within budget, (2) the INDEPENDENT-oracle: the hand-worked
antiderivative value is confirmed by machine-side midpoint quadrature of the ORIGINAL field/curve lambdas —
a structurally different method — and reference() refuses to emit a trace on a mismatch, (3) final-answer
entailment fires only on the true last step, (4) routing hits line-integral titles WITHOUT hijacking
Stokes'/surface-integral topics.

Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_line_integral
"""
import math
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples import trace_pipeline as tp
from app.services.examples.trace_adapters import ADAPTERS
from app.services.examples.trace_adapters.manifest import trace_budget


class LineIntegralGate(unittest.TestCase):
    def _adapter(self):
        return ADAPTERS["line_integral"]

    def _candidates(self):
        return list(self._adapter().candidates(0))

    def test_two_canonical_examples_exist(self):
        self.assertEqual({c["example"] for c in self._candidates()},
                         {"parabola_conservative_field", "quarter_circle_rotational_field"})

    def test_every_example_produces_a_valid_teaching_trace_within_budget(self):
        a = self._adapter()
        budget = trace_budget("line_integral")
        for cand in self._candidates():
            with self.subTest(example=cand["example"]):
                tr = a.reference(cand, candidate_id=cand["_id"], seed=0)
                self.assertEqual(tp.structural_invariants(tr, a), [], f"structural not clean for {cand}")
                self.assertTrue(a.is_teaching_trace(tr))
                self.assertLessEqual(len(tr.steps), budget, f"{cand}: exceeds trace budget")

    def test_hand_value_matches_independent_numeric_quadrature(self):
        from app.services.examples.trace_adapters.families.vector_calculus import (
            _LINE_INTEGRAL_EXAMPLES, _numeric_line_integral)
        expected = {"parabola_conservative_field": 1.0,
                    "quarter_circle_rotational_field": math.pi / 2.0}
        for name, ex in _LINE_INTEGRAL_EXAMPLES.items():
            with self.subTest(example=name):
                self.assertAlmostEqual(ex["value"], expected[name], places=9)
                self.assertAlmostEqual(_numeric_line_integral(ex), ex["value"], places=5)

    def test_reference_refuses_a_trace_the_oracle_rejects(self):
        # Corrupt one example's hand value; reference() must raise rather than emit a wrong trace.
        from app.services.examples.trace_adapters.families import vector_calculus as vc
        a = self._adapter()
        original = vc._LINE_INTEGRAL_EXAMPLES["parabola_conservative_field"]["value"]
        vc._LINE_INTEGRAL_EXAMPLES["parabola_conservative_field"]["value"] = 2.5
        try:
            with self.assertRaises(AssertionError):
                a.reference({"example": "parabola_conservative_field", "_id": "x"}, seed=0)
        finally:
            vc._LINE_INTEGRAL_EXAMPLES["parabola_conservative_field"]["value"] = original

    def test_final_answer_entailment_only_true_on_the_true_last_step(self):
        a = self._adapter()
        for cand in self._candidates():
            with self.subTest(example=cand["example"]):
                tr = a.reference(cand, candidate_id=cand["_id"], seed=0)
                for step in tr.steps[:-1]:
                    self.assertFalse(a.final_answer_entails(step.state_after, tr.final_answer))
                self.assertTrue(a.final_answer_entails(tr.steps[-1].state_after, tr.final_answer))

    def test_routing_matches_line_integral_titles_without_hijacking_siblings(self):
        from app.services.examples.trace_pipeline import route_adapter
        for title in ("Computing Line Integrals", "Line Integral Computation", "Line Integrals"):
            adapter = route_adapter({"title": title, "topic_type": "math_formula_method"})
            self.assertIsNotNone(adapter, f"{title!r} did not route")
            self.assertEqual(adapter.slug, "line_integral")
        stokes = route_adapter({"title": "Stokes' Theorem", "topic_type": "math_formula_method"})
        self.assertEqual(getattr(stokes, "slug", None), "stokes_theorem")
        # a line-integral mention inside a Stokes/surface title must NOT pull this adapter
        for title in ("Line Integrals in Stokes' Theorem", "Surface and Line Integrals of Divergence"):
            adapter = route_adapter({"title": title, "topic_type": "math_formula_method"})
            self.assertNotEqual(getattr(adapter, "slug", None), "line_integral", title)

    def test_both_examples_are_reachable_via_select_instance_across_seeds(self):
        a = self._adapter()
        seen = set()
        for seed in range(4):
            tr = tp.select_instance(a, seed=seed)
            seen.add(round(tr.final_answer["work"], 3))
        self.assertEqual(len(seen), 2, f"only one example was ever selected across seeds 0-3: {seen}")

    def test_canonical_formula_grounding_facts_present(self):
        cf = getattr(self._adapter(), "_canonical_formula", None)
        self.assertIsNotNone(cf)
        self.assertIn(r"\int_{C} F \cdot dr", cf.canonical_latex)
        self.assertTrue(len(cf.edge_cases) >= 2)
        self.assertIsNone(getattr(self._adapter(), "_formula_spec", None))   # never the narration-flipping attr


if __name__ == "__main__":
    unittest.main()
