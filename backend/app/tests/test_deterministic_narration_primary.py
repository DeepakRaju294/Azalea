"""Tier 2 — deterministic-first narration. For a WALKTHROUGH adapter that declares `provides_narration`, the
verified trace IS the content: the pipeline ships cards straight from the trace (no LLM re-authoring), so the
whole class of formatter defects (leaked grammar labels, wrong values, dropped mechanism) cannot occur. Fully
offline. Coding topics keep the code-anchored LLM path."""
import unittest

from app.services.examples import trace_pipeline as tp
from app.services.examples.trace_adapters import ADAPTERS
from app.services.examples.trace_contract import (hard_prose_violations, validate_fidelity,
                                                  validate_prose)

_NARRATION_SORTS = ["bubble_sort", "selection_sort", "insertion_sort", "merge_sort", "quick_sort"]


class DeterministicNarrationGate(unittest.TestCase):
    def test_declared_sorts_narrate_cleanly_across_seeds(self):
        # every declared-narration sort must pass fidelity + hard-prose on its OWN deterministic cards, for
        # many instances — otherwise it must not claim provides_narration.
        for slug in _NARRATION_SORTS:
            a = ADAPTERS[slug]
            self.assertTrue(getattr(a, "provides_narration", False), slug)
            for seed in range(30):
                tr = tp.select_instance(a, seed=seed)
                det = tp._deterministic_narration(tr, a)
                with self.subTest(slug=slug, seed=seed):
                    self.assertTrue(validate_fidelity(det, tr, a, validate_visual_state=False).ok)
                    self.assertEqual(hard_prose_violations(validate_prose(det, tr, a)), [])

    def test_titles_have_no_step_ordinal_and_no_truncated_number(self):
        for slug in _NARRATION_SORTS:
            a = ADAPTERS[slug]
            for seed in range(20):
                tr = tp.select_instance(a, seed=seed)
                for c in tp._deterministic_narration(tr, a):
                    t = c["title"]
                    with self.subTest(slug=slug, seed=seed, title=t):
                        self.assertFalse(t.startswith("Step "), t)      # entity-named, not "Step N:"
                        self.assertFalse(t.rstrip().endswith(("[", "(", ",")), t)  # not a truncated fragment


class ShipsWithoutLLM(unittest.TestCase):
    def test_sort_walkthrough_ships_deterministically_without_calling_the_formatter(self):
        def boom(*a, **k):
            raise AssertionError("the LLM format_fn must not be called for a narration adapter")
        for title in ("Bubble Sort Algorithm Walkthrough", "Quicksort Algorithm Walkthrough",
                      "Insertion Sort Algorithm Walkthrough", "Merge Sort Algorithm Walkthrough"):
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
