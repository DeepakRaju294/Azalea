"""Tests for required-card backfill (#2) + card-failure logging (#3)."""
import json
import os
import tempfile
import unittest

from app.services.card_backfill import backfill_missing_required_cards, _is_empty
from app.services.card_failure_log import log_card_failure


def card(key, points=None):
    return {"blueprint_key": key, "card_type": key, "title": key, "points": points or ["content"]}


CODING_TOPIC = {"id": "t1", "title": "Implementing Kruskal's", "topic_type": "coding_implementation",
                "topic_family": "graph_mst"}


class BackfillTests(unittest.TestCase):
    def test_regenerates_missing_worked_example(self):
        # the Kruskal failure: only code_walkthrough + practice present
        lesson = {"lesson_cards": [card("code_walkthrough"), card("practice")]}
        calls = {}

        def we_fn(lesson_json, topic):
            lesson_json["lesson_cards"].append(card("worked_example", ["step 1", "step 2"]))
            calls["we"] = True
            return True

        still = backfill_missing_required_cards(lesson, CODING_TOPIC, worked_example_fn=we_fn,
                                                single_card_fn=lambda k, l, t: card(k))
        self.assertTrue(calls.get("we"))
        keys = [c["blueprint_key"] for c in lesson["lesson_cards"]]
        self.assertIn("worked_example", keys)
        self.assertNotIn("worked_example", still)

    def test_regenerates_missing_required_generic_card_in_order(self):
        # background is REQUIRED; components_terms/edge_case are optional and are NOT backfilled
        lesson = {"lesson_cards": [card("code_walkthrough"), card("practice")]}
        still = backfill_missing_required_cards(
            lesson, CODING_TOPIC,
            worked_example_fn=lambda l, t: (l["lesson_cards"].append(card("worked_example", ["s"])) or True),
            single_card_fn=lambda k, l, t: card(k))
        keys = [c["blueprint_key"] for c in lesson["lesson_cards"]]
        self.assertIn("background", keys)                    # required -> backfilled
        self.assertNotIn("components_terms", keys)            # optional -> left alone
        self.assertLess(keys.index("background"), keys.index("code_walkthrough"))  # placed by blueprint order
        self.assertEqual(still, [])

    def test_drop_logged_when_regeneration_fails(self):
        lesson = {"lesson_cards": [card("code_walkthrough"), card("practice")]}
        still = backfill_missing_required_cards(
            lesson, CODING_TOPIC,
            worked_example_fn=lambda l, t: False,        # solver can't produce one
            single_card_fn=lambda k, l, t: None)         # generic gen fails too
        self.assertIn("worked_example", still)           # honestly reported as still missing

    def test_empty_worked_example_counts_as_missing(self):
        self.assertTrue(_is_empty({"blueprint_key": "worked_example", "points": []}))
        self.assertFalse(_is_empty({"blueprint_key": "worked_example", "points": ["a step"]}))

    def test_nothing_to_do_when_complete(self):
        lesson = {"lesson_cards": [card("code_walkthrough"), card("worked_example", ["s"]), card("practice")]}
        self.assertEqual(
            backfill_missing_required_cards(lesson, CODING_TOPIC,
                                            worked_example_fn=lambda l, t: True,
                                            single_card_fn=lambda k, l, t: card(k)),
            [])


class FailureLogTests(unittest.TestCase):
    def test_writes_jsonl_with_reason(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "fail.jsonl")
            log_card_failure(topic=CODING_TOPIC, card_key="worked_example", stage="backfill",
                             reason="missing_required_card", action="regenerated", path=p)
            rec = json.loads(open(p, encoding="utf-8").read().strip())
        self.assertEqual(rec["card_key"], "worked_example")
        self.assertEqual(rec["reason"], "missing_required_card")
        self.assertEqual(rec["action"], "regenerated")
        self.assertEqual(rec["topic_family"], "graph_mst")

    def test_never_raises(self):
        log_card_failure(card_key="x", stage="s", reason="r", path="/nonexistent_dir/f.jsonl")


if __name__ == "__main__":
    unittest.main()
