"""T11 subsets-backtracking adapter (ADAPTER_TAXONOMY_SPEC.md §6 T11 backlog: subsets). Proves: (1) the trace is
structurally valid + a teaching trace across seeds, (2) the declared final_answer (every subset found) matches
an INDEPENDENT oracle — bitmask enumeration, a genuinely different algorithm than the recursive
include/exclude backtracking the adapter itself performs, and (3) the trace stays within the T11 type's
18-step budget.

Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_subsets_backtracking
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples import trace_pipeline as tp
from app.services.examples.trace_adapters import ADAPTERS
from app.services.examples.trace_adapters.manifest import trace_budget


def _bitmask_power_set(elements: list) -> list:
    """INDEPENDENT oracle: every subset via bitmask enumeration (0..2^n-1), not recursion/backtracking."""
    n = len(elements)
    out = []
    for mask in range(2 ** n):
        out.append([elements[i] for i in range(n) if mask & (1 << i)])
    return out


class SubsetsBacktrackingGate(unittest.TestCase):
    def _adapter(self):
        return ADAPTERS["subsets_backtracking"]

    def test_every_seed_produces_a_valid_teaching_trace_within_budget(self):
        a = self._adapter()
        budget = trace_budget("subsets_backtracking")
        for seed in range(20):
            with self.subTest(seed=seed):
                tr = tp.select_instance(a, seed=seed)
                self.assertIsNotNone(tr, f"no teaching trace at seed {seed}")
                self.assertEqual(tp.structural_invariants(tr, a), [], f"structural not clean at seed {seed}")
                self.assertTrue(a.is_teaching_trace(tr))
                self.assertLessEqual(len(tr.steps), budget, f"seed {seed}: exceeds T11 trace budget")

    def test_final_answer_matches_independent_bitmask_oracle(self):
        a = self._adapter()
        for seed in range(20):
            with self.subTest(seed=seed):
                tr = tp.select_instance(a, seed=seed)
                self.assertIn("A, B, C", tr.problem)  # sanity: elements appear in clean (no-bracket) prose
                found = tr.final_answer["subsets"]
                # compare as sorted-of-sorted so generation order doesn't matter, only the SET of subsets
                got = sorted(sorted(s) for s in found)
                oracle = sorted(sorted(s) for s in _bitmask_power_set(["A", "B", "C"]))
                self.assertEqual(got, oracle, f"seed {seed}: {found} != oracle")
                self.assertEqual(len(found), 2 ** 3, f"seed {seed}: wrong subset count")

    def test_final_answer_entailment_only_true_on_the_true_last_step(self):
        a = self._adapter()
        tr = tp.select_instance(a, seed=0)
        for step in tr.steps[:-1]:
            self.assertFalse(a.final_answer_entails(step.state_after, tr.final_answer),
                             f"{step.id}: entailment should only hold on the TRUE last step")
        self.assertTrue(a.final_answer_entails(tr.steps[-1].state_after, tr.final_answer))

    def test_no_element_repeated_in_any_partial_subset(self):
        a = self._adapter()
        tr = tp.select_instance(a, seed=3)
        for step in tr.steps:
            subset = step.state_after["subset"]
            self.assertEqual(len(subset), len(set(subset)), f"{step.id}: duplicate element in {subset}")


if __name__ == "__main__":
    unittest.main()
