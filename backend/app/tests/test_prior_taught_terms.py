"""An earlier topic's DEFINED key terms must flow into the later topic's do_not_reteach ledger, so a body
topic stops re-defining terms the intro already defined (a live "Ohm's Law" path defined Voltage/Current in
BOTH the intro and the teaching topic). Regression for the cross-topic key-terms layering."""
import unittest

from app.services.assumption_ledger_service import (
    _defined_terms_from_lesson, build_assumption_ledger,
)


class _Lesson:
    def __init__(self, lesson_json):
        self.lesson_json = lesson_json


class _Topic:
    def __init__(self, tid, title, order, lesson=None, in_scope=None):
        self.id, self.title, self.order_index = tid, title, order
        self.purpose = self.learner_outcome = self.practice_target = ""
        self.in_scope = in_scope or []
        self.assumed_prerequisites = []
        self.prerequisite_topics = None
        self.lesson = lesson
        self.study_path = None


class _Path:
    def __init__(self, topics):
        self.topics = topics
        for t in topics:
            t.study_path = self


_KEY_TERMS_CARD = {
    "card_type": "definition", "title": "Key Terms in Ohm's Law",
    "points": [
        "Voltage", "  - The potential difference across a circuit.",
        "Current", "  - The flow of electric charge, measured in amperes.",
    ],
}


class DefinedTermsExtraction(unittest.TestCase):
    def test_extracts_term_headers_not_definition_lines(self):
        terms = _defined_terms_from_lesson({"lesson_cards": [_KEY_TERMS_CARD]})
        self.assertIn("Voltage", terms)
        self.assertIn("Current", terms)
        # the indented meaning lines are NOT terms
        self.assertFalse(any(t.startswith("The ") for t in terms))

    def test_ignores_non_key_terms_cards(self):
        card = {"card_type": "worked_example", "points": ["Voltage", "  - stuff"]}
        self.assertEqual(_defined_terms_from_lesson({"lesson_cards": [card]}), [])


class LedgerCarriesEarlierTerms(unittest.TestCase):
    def test_body_topic_do_not_reteach_includes_intro_defined_terms(self):
        intro = _Topic("i", "Ohm's Law Overview", 1, lesson=_Lesson({"lesson_cards": [_KEY_TERMS_CARD]}))
        body = _Topic("t2", "Calculating with Ohm's Law", 2)
        _Path([intro, body])
        ledger = build_assumption_ledger(topic=body)
        self.assertIn("Voltage", ledger["prior_taught_content"])
        self.assertIn("Current", ledger["prior_taught_content"])
        # do_not_reteach folds prior_taught_content, so the dedup rules can subtract them.
        self.assertIn("Voltage", ledger["do_not_reteach"])

    def test_intro_itself_has_no_prior_terms(self):
        intro = _Topic("i", "Ohm's Law Overview", 1, lesson=_Lesson({"lesson_cards": [_KEY_TERMS_CARD]}))
        body = _Topic("t2", "Calculating", 2)
        _Path([intro, body])
        ledger = build_assumption_ledger(topic=intro)   # nothing earlier than the intro
        self.assertNotIn("Voltage", ledger["prior_taught_content"])


if __name__ == "__main__":
    unittest.main()
