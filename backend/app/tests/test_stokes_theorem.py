"""T13 Stokes'-theorem adapter (ADAPTER_TAXONOMY_SPEC.md T13 backlog: vector calculus). Proves: (1) both
hand-picked examples produce a structurally valid teaching trace within the T13 step budget, (2) the
INDEPENDENT-oracle claim — Stokes' theorem's own two-sided equality — actually holds: the surface integral of
curl(F) over S (computed via area x constant curl) and the line integral of F around the boundary of S
(computed via summed exact per-segment integrals, a structurally different method) agree, (3) final_answer
entailment fires only on the true last step.

`candidates(seed)` does not vary by seed (both examples are hand-picked, fixed instances, same shape as
subsets_backtracking) — so `select_instance` always returns the first one; this test calls `reference()` on
each candidate directly to exercise both.

Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_stokes_theorem
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples import trace_pipeline as tp
from app.services.examples.trace_adapters import ADAPTERS
from app.services.examples.trace_adapters.manifest import trace_budget


class StokesTheoremGate(unittest.TestCase):
    def _adapter(self):
        return ADAPTERS["stokes_theorem"]

    def _candidates(self):
        return list(self._adapter().candidates(0))

    def test_two_canonical_examples_exist(self):
        self.assertEqual({c["example"] for c in self._candidates()},
                         {"unit_disk_rotational_field", "unit_square_shear_field"})

    def test_every_example_produces_a_valid_teaching_trace_within_budget(self):
        a = self._adapter()
        budget = trace_budget("stokes_theorem")
        for cand in self._candidates():
            with self.subTest(example=cand["example"]):
                tr = a.reference(cand, candidate_id=cand["_id"], seed=0)
                self.assertEqual(tp.structural_invariants(tr, a), [], f"structural not clean for {cand}")
                self.assertTrue(a.is_teaching_trace(tr))
                self.assertLessEqual(len(tr.steps), budget, f"{cand}: exceeds T13 trace budget")

    def test_surface_integral_matches_independent_line_integral_oracle(self):
        # The independent-oracle claim IS Stokes' theorem itself: two structurally different computations
        # (area x constant curl, vs. summed exact per-segment boundary integrals) must agree.
        a = self._adapter()
        expected = {"unit_disk_rotational_field": 2.0 * 3.14159265358979,   # 2 * pi, hand-verified
                    "unit_square_shear_field": 1.0}
        for cand in self._candidates():
            with self.subTest(example=cand["example"]):
                tr = a.reference(cand, candidate_id=cand["_id"], seed=0)
                fa = tr.final_answer
                self.assertAlmostEqual(fa["surface_integral"], fa["line_integral"], places=6)
                self.assertAlmostEqual(fa["surface_integral"], expected[cand["example"]], places=5)

    def test_final_answer_entailment_only_true_on_the_true_last_step(self):
        a = self._adapter()
        for cand in self._candidates():
            with self.subTest(example=cand["example"]):
                tr = a.reference(cand, candidate_id=cand["_id"], seed=0)
                for step in tr.steps[:-1]:
                    self.assertFalse(a.final_answer_entails(step.state_after, tr.final_answer),
                                     f"{cand['example']} {step.id}: entailment should only hold on the "
                                     f"TRUE last step")
                self.assertTrue(a.final_answer_entails(tr.steps[-1].state_after, tr.final_answer))

    def test_invariant_only_meaningfully_checked_at_the_terminal_step(self):
        a = self._adapter()
        tr = a.reference({"example": "unit_disk_rotational_field", "_id": "x"}, seed=0)
        inv = tr.invariants[0]
        for step in tr.steps[:-1]:
            self.assertTrue(a.invariant_holds(inv, step.state_after))   # not-yet-complete states pass trivially
        self.assertTrue(a.invariant_holds(inv, tr.steps[-1].state_after))

    def test_routing_matches_stokes_theorem_titles(self):
        from app.services.examples.trace_pipeline import route_adapter
        for title in ("Mathematical Statement of Stokes' Theorem", "Applying Stokes' Theorem",
                     "Stokes theorem"):
            adapter = route_adapter({"title": title, "topic_type": "math_formula_method"})
            self.assertIsNotNone(adapter, f"{title!r} did not route")
            self.assertEqual(adapter.slug, "stokes_theorem")

    def test_both_examples_are_reachable_via_select_instance_across_seeds(self):
        # Regression: select_instance always returns the FIRST candidate whose trace passes
        # is_teaching_trace — with a fixed candidates() order, the second example would never ship to a
        # real learner no matter how many times a path regenerates.
        a = self._adapter()
        seen = set()
        for seed in range(4):
            tr = tp.select_instance(a, seed=seed)
            seen.add(round(tr.final_answer["surface_integral"], 3))
        self.assertEqual(len(seen), 2, f"only one example was ever selected across seeds 0-3: {seen}")

    def test_curl_formula_topic_does_not_collide_with_stokes(self):
        # Regression guard: a title mentioning both curl and Stokes' theorem must route to the full
        # surface-vs-boundary adapter, not the unrelated 2D point-value curl formula plug-in.
        from app.services.examples.trace_pipeline import route_adapter
        adapter = route_adapter({"title": "Curl and Stokes' Theorem", "topic_type": "math_formula_method"})
        self.assertIsNotNone(adapter)
        self.assertEqual(adapter.slug, "stokes_theorem")


if __name__ == "__main__":
    unittest.main()
