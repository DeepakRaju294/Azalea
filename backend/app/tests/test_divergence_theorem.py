"""T13 divergence-theorem adapter — fourth hand-coded member of the vector-calculus family, completing the
Stokes'-theorem path's supporting cast (line integral -> surface integral -> divergence theorem). Two-sided
independent-oracle structure mirrors the Stokes adapter: the volume integral of div(F) (divergence times
volume, exact for a constant divergence) and the total outward flux (hand-worked per-piece contributions)
are computed via structurally DIFFERENT methods, and the terminal invariant demands they agree.

Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_divergence_theorem
"""
import math
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples import trace_pipeline as tp
from app.services.examples.trace_adapters import ADAPTERS
from app.services.examples.trace_adapters.manifest import trace_budget


class DivergenceTheoremGate(unittest.TestCase):
    def _adapter(self):
        return ADAPTERS["divergence_theorem"]

    def _candidates(self):
        return list(self._adapter().candidates(0))

    def test_two_canonical_examples_exist(self):
        self.assertEqual({c["example"] for c in self._candidates()},
                         {"unit_cube_expanding_field", "unit_sphere_radial_field"})

    def test_every_example_produces_a_valid_teaching_trace_within_budget(self):
        a = self._adapter()
        budget = trace_budget("divergence_theorem")
        for cand in self._candidates():
            with self.subTest(example=cand["example"]):
                tr = a.reference(cand, candidate_id=cand["_id"], seed=0)
                self.assertEqual(tp.structural_invariants(tr, a), [], f"structural not clean for {cand}")
                self.assertTrue(a.is_teaching_trace(tr))
                self.assertLessEqual(len(tr.steps), budget, f"{cand}: exceeds trace budget")

    def test_both_theorem_sides_agree_exactly(self):
        # cube: div 3 * volume 1 = 3 = flux (1+0+1+0+1+0); ball: 3 * 4pi/3 = 4pi = sphere flux
        a = self._adapter()
        expected = {"unit_cube_expanding_field": 3.0, "unit_sphere_radial_field": 4.0 * math.pi}
        for cand in self._candidates():
            with self.subTest(example=cand["example"]):
                tr = a.reference(cand, candidate_id=cand["_id"], seed=0)
                fa = tr.final_answer
                self.assertAlmostEqual(fa["volume_integral"], fa["flux"], places=6)
                self.assertAlmostEqual(fa["flux"], expected[cand["example"]], places=5)

    def test_terminal_invariant_rejects_a_mismatched_state(self):
        a = self._adapter()
        inv = {"id": "volume_equals_flux"}
        self.assertTrue(a.invariant_holds(inv, {"complete": True, "volume_integral": 3.0,
                                                "flux_partial": 3.0}))
        self.assertFalse(a.invariant_holds(inv, {"complete": True, "volume_integral": 3.0,
                                                 "flux_partial": 2.0}))
        # non-terminal states are out of the invariant's declared scope
        self.assertTrue(a.invariant_holds(inv, {"complete": False, "volume_integral": 3.0,
                                                "flux_partial": 1.0}))

    def test_final_answer_entailment_only_true_on_the_true_last_step(self):
        a = self._adapter()
        for cand in self._candidates():
            with self.subTest(example=cand["example"]):
                tr = a.reference(cand, candidate_id=cand["_id"], seed=0)
                for step in tr.steps[:-1]:
                    self.assertFalse(a.final_answer_entails(step.state_after, tr.final_answer))
                self.assertTrue(a.final_answer_entails(tr.steps[-1].state_after, tr.final_answer))

    def test_routing_matches_divergence_titles_without_hijacking_siblings(self):
        from app.services.examples.trace_pipeline import route_adapter
        for title in ("The Divergence Theorem", "Gauss's Theorem and Flux",
                      "The Divergence Theorem and Flux Integrals"):
            adapter = route_adapter({"title": title, "topic_type": "math_formula_method"})
            self.assertIsNotNone(adapter, f"{title!r} did not route")
            self.assertEqual(adapter.slug, "divergence_theorem")
        # siblings keep their own routes; Gaussian elimination is a different "gauss" entirely
        for title, slug in (("Stokes' Theorem", "stokes_theorem"),
                            ("Evaluating Surface Integrals", "surface_integral"),
                            ("Computing Line Integrals", "line_integral"),
                            ("Gaussian Elimination", "gaussian_elimination")):
            adapter = route_adapter({"title": title, "topic_type": "math_formula_method"})
            self.assertEqual(getattr(adapter, "slug", None), slug, title)

    def test_both_examples_are_reachable_via_select_instance_across_seeds(self):
        a = self._adapter()
        seen = set()
        for seed in range(4):
            tr = tp.select_instance(a, seed=seed)
            seen.add(round(tr.final_answer["flux"], 3))
        self.assertEqual(len(seen), 2, f"only one example was ever selected across seeds 0-3: {seen}")

    def test_canonical_formula_grounding_facts_present(self):
        cf = getattr(self._adapter(), "_canonical_formula", None)
        self.assertIsNotNone(cf)
        self.assertIn(r"\iiint_{V} (\nabla \cdot F)", cf.canonical_latex)
        self.assertTrue(len(cf.edge_cases) >= 2)
        self.assertIsNone(getattr(self._adapter(), "_formula_spec", None))   # never the narration-flipping attr


if __name__ == "__main__":
    unittest.main()
