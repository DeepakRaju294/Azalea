"""Type-level invariant suites (ADAPTER_DEVELOPMENT_SPEC §2, §type-tests). Beyond per-adapter conformance,
EVERY adapter of a given TYPE must satisfy that type's invariant — so 20 search adapters can't each invent
their own notion of 'correct'. Also cross-checks the machine-readable manifest against the live registry."""
import unittest

from app.services.examples.trace_adapters import ADAPTERS
from app.services.examples.trace_adapters.manifest import (by_type, failure_policy, manifest_gaps,
                                                          trace_budget)
from app.services.examples.trace_pipeline import select_instance


class ManifestConsistency(unittest.TestCase):
    def test_manifest_matches_registry(self):
        # every registered adapter has a complete entry; no phantom entries; coding<->canonical agree
        self.assertEqual(manifest_gaps(), [])

    def test_every_adapter_stays_within_its_type_trace_budget(self):
        # a bounded instance must not explode into a 40-card lesson — guards a drifting generator + a new
        # adapter of the type. Checked across many seeds.
        for slug, adapter in ADAPTERS.items():
            budget = trace_budget(slug)
            worst = max(len(select_instance(adapter, seed=s).steps) for s in range(1, 40))
            with self.subTest(slug=slug):
                self.assertLessEqual(worst, budget, f"{slug}: {worst} steps > type budget {budget}")

    def test_failure_policy_keeps_verified_text_on_render_failure(self):
        # a correct trace with a visual/frontend failure must NOT withhold the whole lesson
        p = failure_policy("binary_search")
        self.assertIn("withhold", p["invalid_trace"])
        self.assertIn("text", p["visual_compile_failure"])
        self.assertIn("text", p["frontend_render_failure"])


class TypeInvariants(unittest.TestCase):
    def _traces(self, type_id):
        return [(slug, select_instance(ADAPTERS[slug], seed=5)) for slug in by_type().get(type_id, [])]

    @staticmethod
    def _first_list(answer):
        return next((v for v in answer.values() if isinstance(v, list)), None)

    def test_t1_traversal_visits_each_element_exactly_once(self):
        for slug, tr in self._traces("T1"):
            with self.subTest(slug=slug):
                order = self._first_list(tr.final_answer)
                self.assertTrue(order, f"{slug}: no visit order")
                self.assertEqual(len(order), len(set(map(str, order))), f"{slug}: a node is visited twice")

    def test_t2_greedy_shows_both_positive_and_negative_outcomes(self):
        # ANTI-OVERSIMPLIFICATION (the Dijkstra warning): a greedy/frontier trace must exercise >=2 decision
        # outcomes (accept AND skip/reject/no-improvement), each with evidence — never a single 'always pick'.
        for slug, tr in self._traces("T2"):
            with self.subTest(slug=slug):
                nonterminal = [c for c in tr.required_cases if c != "completion"]
                self.assertGreaterEqual(len(nonterminal), 2, f"{slug}: only one decision outcome (oversimplified)")
                for c in nonterminal:
                    self.assertTrue(tr.case_evidence.get(c), f"{slug}: required outcome {c!r} unproven")

    def test_t3_divide_and_conquer_reaches_the_combined_answer(self):
        for slug, tr in self._traces("T3"):
            with self.subTest(slug=slug):
                ans = self._first_list(tr.final_answer)
                self.assertEqual(ans, sorted(ans), f"{slug}: combine did not yield a sorted result")

    def test_t4_search_domain_never_grows_and_net_shrinks(self):
        for slug, tr in self._traces("T4"):
            with self.subTest(slug=slug):
                windows = [s.state_after["hi"] - s.state_after["lo"] for s in tr.steps
                           if "lo" in s.state_after and "hi" in s.state_after]
                self.assertTrue(windows, f"{slug}: no lo/hi search domain")
                for a, b in zip(windows, windows[1:]):
                    self.assertLessEqual(b, a, f"{slug}: search domain grew (re-expanded)")
                if len(windows) > 1:
                    self.assertLess(windows[-1], windows[0], f"{slug}: search domain did not narrow")

    def test_t6_formula_answer_is_entailed_by_the_final_state(self):
        for slug, tr in self._traces("T6"):
            with self.subTest(slug=slug):
                self.assertTrue(ADAPTERS[slug].final_answer_entails(tr.steps[-1].state_after, tr.final_answer),
                                f"{slug}: final state does not entail the stated answer")

    def test_t7_rewrite_preserves_value_at_every_step(self):
        for slug, tr in self._traces("T7"):
            with self.subTest(slug=slug):
                inv = next((i for i in tr.invariants
                            if "preserv" in str(i.get("id")) or "value" in str(i.get("id"))), None)
                self.assertIsNotNone(inv, f"{slug}: T7 must declare a value-preservation invariant")
                for s in tr.steps:
                    self.assertTrue(ADAPTERS[slug].invariant_holds(inv, s.state_after),
                                    f"{slug}: value not preserved at {s.id}")


if __name__ == "__main__":
    unittest.main()
