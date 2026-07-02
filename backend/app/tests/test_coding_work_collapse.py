"""§5.4 / study-path review — an iterative algorithm's coding cards re-run the SAME loop body every step.
`_collapse_repeated_coding_work` teaches the loop in full on its first card, then elides the already-shown
machinery on later cards (keeping each card's decision line + a 'rest runs as shown' summary), so the lesson
is not four near-identical walls of code."""
import unittest

from app.services.examples.trace_pipeline import _collapse_repeated_coding_work

_LOOP = [[7], [11], [10], [12], [13], [14]]


def _card(edge):
    return {"code_lines": [list(x) for x in _LOOP], "work": [
        f"w, u, v = heapq.heappop(heap)  // pop the edge {edge} from the heap",
        f"mst.append([u, v, w])  // add edge {edge} to the MST",
        "visited.add(v)  // mark the new vertex visited",
        "for nv, nw in graph[v]:  // scan the neighbours",
        "if nv not in visited:  // skip visited",
        "heapq.heappush(heap, (nw, v, nv))  // push a new candidate"]}


class CodingWorkCollapse(unittest.TestCase):
    def test_first_full_then_repeats_collapsed(self):
        cards = [_card("A–E (2)"), _card("A–B (5)"), _card("B–C (2)")]
        _collapse_repeated_coding_work(cards)
        self.assertEqual(len(cards[0]["work"]), 6, "the FIRST occurrence must teach the full loop")
        for c in cards[1:]:
            self.assertEqual(len(c["work"]), 3, "a repeated loop body must collapse to decision + summary")
            self.assertIn("as shown above", c["work"][-1])
            self.assertEqual(len(c["code_lines"]), 3)

    def test_decision_and_entity_preserved_on_collapsed_cards(self):
        cards = [_card("A–E (2)"), _card("B–C (2)")]
        _collapse_repeated_coding_work(cards)
        # the collapsed card still names ITS edge (the decision is never lost)
        self.assertIn("B–C (2)", " ".join(cards[1]["work"]))
        self.assertIn("heappop", cards[1]["work"][0])

    def test_card_with_new_code_is_not_collapsed(self):
        first = _card("A–E (2)")
        novel = _card("A–B (5)")
        novel["work"].append("decrease_key(heap, v, nw)  // NEW: a line not shown before")
        novel["code_lines"].append([15])
        cards = [first, novel]
        _collapse_repeated_coding_work(cards)
        self.assertEqual(len(cards[1]["work"]), 7, "a card introducing new code stays full")

    def test_non_coding_cards_untouched(self):
        cards = [{"work": ["a", "b", "c", "d"], "result": "r"}]      # no code_lines -> walkthrough card
        _collapse_repeated_coding_work(cards)
        self.assertEqual(len(cards[0]["work"]), 4)


if __name__ == "__main__":
    unittest.main()
