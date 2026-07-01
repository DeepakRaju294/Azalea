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

    def test_every_type_has_a_machine_testable_visual_budget(self):
        from app.services.examples.trace_adapters.manifest import ADAPTER_TYPES, TYPE_VISUAL_BUDGET
        for tid in ADAPTER_TYPES:
            with self.subTest(type=tid):
                vb = TYPE_VISUAL_BUDGET[tid]
                for field in ("max_focus_entities", "max_new_labels", "max_changed_entities",
                              "max_visible_state_groups"):
                    self.assertIsInstance(vb[field], int)   # numeric -> a compiler/test can enforce it
                self.assertTrue(vb["focus_roles"], f"{tid}: no allowed focus roles")

    def test_teaching_target_within_semantic_ceiling(self):
        from app.services.examples.trace_adapters.manifest import (ADAPTER_TYPES, TYPE_TEACHING_TARGET,
                                                                  TYPE_TRACE_BUDGET)
        for tid in ADAPTER_TYPES:
            with self.subTest(type=tid):
                self.assertLessEqual(TYPE_TEACHING_TARGET[tid], TYPE_TRACE_BUDGET[tid])

    def test_trace_replay_is_executable_from_initial_state(self):
        # §7-review: a plausible-looking state SEQUENCE is not enough — the chain must actually REPLAY:
        # step0.prior == initial, each step.prior == previous step_after (no hidden mutation / skipped
        # transition / discontinuity), and the terminal state entails the answer. structural_invariants is the
        # production replay gate; assert it stays clean across many seeds for every adapter.
        from app.services.examples.trace_contract import structural_invariants
        for slug, adapter in ADAPTERS.items():
            for seed in range(1, 20):
                tr = select_instance(adapter, seed=seed)
                with self.subTest(slug=slug, seed=seed):
                    self.assertEqual(structural_invariants(tr, adapter), [],
                                     f"{slug}@{seed}: trace does not replay from initial state")

    def test_teaching_checkpoints_cite_complete_source_provenance(self):
        # §7.3: every checkpoint must name its contiguous source-step range + state anchors (card -> checkpoint
        # -> source steps -> verified trace). No selected step may vanish; ranges must be contiguous & ordered.
        for slug, adapter in ADAPTERS.items():
            tr = select_instance(adapter, seed=7)
            order = {s.id: i for i, s in enumerate(tr.steps)}
            checkpoints = adapter.teaching_checkpoints(tr)
            with self.subTest(slug=slug):
                self.assertTrue(checkpoints, f"{slug}: no teaching checkpoints")
                seen: list[int] = []
                for cp in checkpoints:
                    self.assertTrue(cp.source_step_ids, f"{slug}: checkpoint {cp.checkpoint_id} cites no steps")
                    idxs = [order[sid] for sid in cp.source_step_ids]
                    self.assertEqual(idxs, list(range(idxs[0], idxs[0] + len(idxs))),
                                     f"{slug}: checkpoint {cp.checkpoint_id} range not contiguous")
                    self.assertIn(cp.state_before_step_id, order)
                    self.assertIn(cp.state_after_step_id, order)
                    seen.extend(idxs)
                self.assertEqual(seen, sorted(seen), f"{slug}: checkpoints out of trace order")


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

    @staticmethod
    def _search_space(state):
        # generalized across T4 state models: an integer window [lo,hi] (binary search) OR a `remaining`
        # candidate count (BST search subtree). This generalization is exactly what proving the T4 gate forced.
        if "lo" in state and "hi" in state:
            return state["hi"] - state["lo"]
        if "remaining" in state:
            return state["remaining"]
        return None

    def test_t4_search_domain_never_grows_and_net_shrinks(self):
        for slug, tr in self._traces("T4"):
            with self.subTest(slug=slug):
                sizes = [self._search_space(s.state_after) for s in tr.steps]
                sizes = [x for x in sizes if x is not None]
                self.assertTrue(sizes, f"{slug}: no measurable search space")
                for a, b in zip(sizes, sizes[1:]):
                    self.assertLessEqual(b, a, f"{slug}: search space grew (re-expanded)")
                if len(sizes) > 1:
                    self.assertLess(sizes[-1], sizes[0], f"{slug}: search space did not narrow")

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
