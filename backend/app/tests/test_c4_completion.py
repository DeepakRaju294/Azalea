"""C4 — the last card must state COMPLETION and the stopping CRITERION (why the algorithm is done), not just
the final result. A first-time learner needs to know why it stopped ('V−1 edges accepted', 'every node
visited', 'one sorted run'), not only the answer. The criterion is the adapter's declared `terminal`."""
import re
import unittest

from app.services.examples.trace_adapters import ADAPTERS
from app.services.examples.trace_pipeline import (_deterministic_narration, _ensure_completion,
                                                  select_instance)


class C4Completion(unittest.TestCase):
    def test_ensure_completion_states_criterion_and_answer(self):
        # direct, unambiguous: a card that does NOT already say complete gets the criterion + the final answer.
        class _T:
            final_answer = {"mst_edges": [["A", "B", 2]], "total_weight": 2}
        cards = [{"result": "some intermediate state"}]
        _ensure_completion(cards, _T(), terminal="V-1 edges accepted (a spanning tree)")
        self.assertIn("Complete: V-1 edges accepted (a spanning tree)", cards[0]["result"])
        self.assertIn("Final result:", cards[0]["result"])

    def test_no_terminal_has_a_bare_digit(self):
        # the terminal is appended into the completion clause, which IS prose-validated on the LLM ship path.
        # A bare digit not in the step's allowed_values trips `value_not_allowed` and knocks the ship to the
        # deterministic fallback. Keep stopping criteria as digit-free prose ('a spanning tree', not 'V-1 edges').
        for slug, adapter in sorted(ADAPTERS.items()):
            crit = str(adapter.example_spec.terminal or "")
            with self.subTest(slug=slug):
                self.assertNotRegex(crit, r"\d", f"{slug}: terminal has a digit (breaks the LLM ship): {crit!r}")

    def test_every_adapter_last_card_states_completion(self):
        for slug, adapter in sorted(ADAPTERS.items()):
            tr = select_instance(adapter, seed=5)
            cards = _deterministic_narration(tr, adapter)
            last = str(cards[-1]["result"])
            with self.subTest(slug=slug):
                # completion is stated (either the natural terminal word or the appended "Complete:")
                self.assertRegex(last, r"[Cc]omplete|found|absent|sorted|\bfinal\b",
                                 f"{slug}: last card does not state completion: {last!r}")
                # when we appended the criterion, a distinctive word of the declared terminal is present
                if "Complete:" in last:
                    crit = str(adapter.example_spec.terminal or "")
                    key = next((w for w in re.findall(r"[A-Za-z]{4,}", crit)), "")
                    if key:
                        self.assertIn(key, last, f"{slug}: stopping criterion {crit!r} not surfaced")


if __name__ == "__main__":
    unittest.main()
