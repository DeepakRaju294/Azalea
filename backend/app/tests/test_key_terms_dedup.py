"""Deterministic layered key-terms: a later topic's key-terms card must not re-define a term an earlier topic
already defined (the prompt/ledger nudge alone is not obeyed — a live Bayes path re-defined "Conditional
Probability" the intro had defined). The card is dropped entirely if nothing new remains."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.lean_lesson_generator import _dedupe_key_terms_against_earlier


class _Lesson:
    def __init__(self, lesson_json):
        self.lesson_json = lesson_json


class _Topic:
    def __init__(self, tid, order, lesson=None):
        self.id, self.order_index, self.lesson = tid, order, lesson
        self.title, self.course_type, self.topic_type = f"T{order}", "math_formula_method", None
        self.study_path = None


class _Path:
    def __init__(self, topics):
        self.topics = topics
        for t in topics:
            t.study_path = self


_INTRO_DEF = {"card_type": "definition", "title": "Key Terms", "points": [
    "Conditional Probability", "  - Probability of A given B.",
    "Bayes' Theorem", "  - Updates a hypothesis with evidence.",
]}


def _terms(card):
    return [str(p).split(":")[0].strip() for p in (card.get("points") or [])
            if str(p) and not str(p)[0].isspace() and not str(p).lstrip().startswith("-")]


class KeyTermsDedup(unittest.TestCase):
    def _with_intro(self, body_cards):
        intro = _Topic("i", 1, lesson=_Lesson({"lesson_cards": [_INTRO_DEF]}))
        body = _Topic("t2", 2)
        _Path([intro, body])
        return _dedupe_key_terms_against_earlier(body_cards, body)

    def test_removes_term_already_defined_earlier_inline_format(self):
        cards = [{"card_type": "definition", "points": [
            "Event: an outcome.",
            "Conditional Probability: prob of A given B.",   # already defined in the intro
            "Partition: a covering set.",
        ]}]
        out = self._with_intro(cards)
        self.assertEqual(_terms(out[0]), ["Event", "Partition"])

    def test_removes_header_plus_subbullet_format(self):
        cards = [{"card_type": "definition", "points": [
            "Bayes' Theorem", "  - already covered.",       # defined in intro (header format)
            "Likelihood", "  - P(B|A).",
        ]}]
        out = self._with_intro(cards)
        self.assertEqual(_terms(out[0]), ["Likelihood"])

    def test_drops_card_when_nothing_new_remains(self):
        cards = [{"card_type": "definition", "points": [
            "Conditional Probability: dup.", "Bayes' Theorem: dup.",
        ]}]
        out = self._with_intro(cards)
        self.assertFalse(any(c.get("card_type") == "definition" for c in out))

    def test_no_earlier_lesson_leaves_cards_untouched(self):
        body = _Topic("t1", 1)   # first topic, nothing earlier
        _Path([body])
        cards = [{"card_type": "definition", "points": ["Event: an outcome."]}]
        self.assertEqual(_dedupe_key_terms_against_earlier(cards, body), cards)


if __name__ == "__main__":
    unittest.main()
