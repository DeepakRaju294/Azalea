"""Tier 2 — deterministic-first narration. For a WALKTHROUGH adapter that declares `provides_narration`, the
verified trace IS the content: the pipeline ships cards straight from the trace (no LLM re-authoring), so the
whole class of formatter defects (leaked grammar labels, wrong values, dropped mechanism) cannot occur. Fully
offline. Coding topics keep the code-anchored LLM path."""
import unittest

from app.services.examples import trace_pipeline as tp
from app.services.examples.trace_adapters import ADAPTERS, NARRATION_SLUGS
from app.services.examples.trace_contract import (hard_prose_violations, validate_fidelity,
                                                  validate_prose)


class DeterministicNarrationGate(unittest.TestCase):
    def test_every_declared_narration_adapter_is_clean_across_seeds(self):
        # An adapter may only claim provides_narration if it passes fidelity + hard-prose on its OWN
        # deterministic cards for many instances — otherwise it must stay on the LLM path (§Tier 2 gate).
        for slug in sorted(NARRATION_SLUGS):
            a = ADAPTERS[slug]
            self.assertTrue(getattr(a, "provides_narration", False), slug)
            for seed in range(30):
                tr = tp.select_instance(a, seed=seed)
                if tr is None:
                    continue
                det = tp._deterministic_narration(tr, a)
                with self.subTest(slug=slug, seed=seed):
                    self.assertTrue(validate_fidelity(det, tr, a, validate_visual_state=False).ok)
                    self.assertEqual(hard_prose_violations(validate_prose(det, tr, a)), [])

    def test_titles_have_no_step_ordinal_and_no_truncated_number(self):
        for slug in sorted(NARRATION_SLUGS):
            a = ADAPTERS[slug]
            for seed in range(20):
                tr = tp.select_instance(a, seed=seed)
                for c in tp._deterministic_narration(tr, a):
                    t = c["title"]
                    with self.subTest(slug=slug, seed=seed, title=t):
                        self.assertFalse(t.startswith("Step "), t)      # entity-named, not "Step N:"
                        self.assertFalse(t.rstrip().endswith(("[", "(", ",")), t)  # not a truncated fragment


class FormulaStepSlotting(unittest.TestCase):
    """A formula step's `reason` is the worked computation and `decision` is the answer, so the generic
    reason->reasoning / decision->work mapping mis-slots them (computation in Reasoning, only the answer in
    Work). Formula adapters must slot: reasoning=verbal, WORK=the computation, result=the answer."""

    def _compute_cards(self, slug):
        a = ADAPTERS[slug]
        tr = tp.select_instance(a, seed=7)
        # skip the givens-listing and completion steps; keep the compute steps
        return [(s, c) for s, c in zip(tr.steps, tp._deterministic_narration(tr, a))
                if str(getattr(s, "operation", "")) not in ("identify_knowns", "completion")]

    def test_combinations_work_holds_the_solved_formula_not_the_answer(self):
        pairs = self._compute_cards("combinations")
        self.assertTrue(pairs)
        _, card = pairs[0]
        joined_work = " ".join(card["work"])
        self.assertIn("C(n,r)", joined_work)                     # the formula is SOLVED OUT in Work
        self.assertIn("=", joined_work)
        self.assertNotIn("=", card["reasoning"])                 # Reasoning is verbal, not an equation
        self.assertTrue(card["reasoning"].lower().startswith("substitute"))
        self.assertNotIn("n!/", card["result"])                  # Result is the answer, not the formula

    def test_multi_step_formula_each_step_slotted(self):
        pairs = self._compute_cards("bayes_theorem")
        self.assertGreaterEqual(len(pairs), 2)
        for _, card in pairs:
            self.assertIn("=", " ".join(card["work"]))           # every step's work carries its computation
            self.assertNotIn("=", card["reasoning"])


class ShipsWithoutLLM(unittest.TestCase):
    def test_sort_walkthrough_ships_deterministically_without_calling_the_formatter(self):
        def boom(*a, **k):
            raise AssertionError("the LLM format_fn must not be called for a narration adapter")
        for title in ("Bubble Sort Algorithm Walkthrough", "Quicksort Algorithm Walkthrough",
                      "BFS Traversal of a Graph", "Kruskal's Algorithm Walkthrough",
                      "Inorder Traversal of a BST", "Dijkstra's Shortest Path"):
            topic = {"id": "t", "title": title, "topic_type": "algorithm_walkthrough"}
            res = tp.solve_trace_pipeline(topic, format_fn=boom, seed=3)
            with self.subTest(title=title):
                self.assertIsNotNone(res)
                cards = res["cards"]
                self.assertTrue(cards)
                # no leaked stage-grammar labels reach the learner
                for c in cards:
                    for w in c["work"]:
                        self.assertNotIn("decision:", w.lower())
                        self.assertNotIn("aggregated supporting", w.lower())


if __name__ == "__main__":
    unittest.main()
