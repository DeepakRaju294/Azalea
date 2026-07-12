"""§6.2 live emission: the lean generator populates each card's interactive_links from the deterministic
scanner — review_earlier_topic for a concept taught by an EARLIER topic in the path, open_study_path for an
external assumed prerequisite. Flag-gated (AZALEA_PREREQ_LINKS); off ⇒ links stay []."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.lean_lesson_generator import (
    _emit_prereq_interactive_links, _lean_card_to_legacy, _topic_title_aliases,
)

_FLAG = "AZALEA_PREREQ_LINKS"


class _Topic:
    def __init__(self, tid, title, order, prereqs=None, course_type="concept"):
        self.id, self.title, self.order_index = tid, title, order
        self.course_type, self.topic_type = course_type, None
        self.assumed_prerequisites = prereqs or []
        self.decomposition_metadata = {}
        self.study_path = None


class _Path:
    def __init__(self, topics, domain="cs"):
        self.topics, self.domain = topics, domain
        for t in topics:
            t.study_path = self


class PrereqLinkEmission(unittest.TestCase):
    def setUp(self):
        self._prev = os.environ.get(_FLAG)

    def tearDown(self):
        if self._prev is None:
            os.environ.pop(_FLAG, None)
        else:
            os.environ[_FLAG] = self._prev

    def _sorting_path(self):
        intro = _Topic("i", "Introduction to Sorting", 0, course_type="study_path_introduction")
        comp = _Topic("t1", "Comparison Sort", 1)
        quick = _Topic("t2", "Quick Sort", 2)
        _Path([intro, comp, quick])
        return intro, comp, quick

    def test_flag_off_leaves_links_empty(self):
        os.environ.pop(_FLAG, None)
        _, _, quick = self._sorting_path()
        cards = [{"card_type": "background", "points": ["Quick Sort relies on Comparison Sort ideas."]}]
        out = _emit_prereq_interactive_links(cards, quick)
        self.assertEqual(out[0].get("interactive_links", "MISSING"), "MISSING")

    def test_review_earlier_topic_for_intra_path_dependency(self):
        os.environ[_FLAG] = "1"
        _, comp, quick = self._sorting_path()
        cards = [{"card_type": "background", "points": ["Quick Sort builds on Comparison Sort."]}]
        out = _emit_prereq_interactive_links(cards, quick)
        links = out[0]["interactive_links"]
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["action"], "review_earlier_topic")
        self.assertEqual(links[0]["target"], "t1")                 # Comparison Sort's topic_id
        self.assertEqual(links[0]["text"], "Comparison Sort")
        self.assertEqual(links[0]["concept_id"], "comparison_sort")

    def test_no_self_link_to_current_topic(self):
        os.environ[_FLAG] = "1"
        _, _, quick = self._sorting_path()
        cards = [{"card_type": "background", "points": ["Quick Sort is a fast sort."]}]  # mentions itself only
        out = _emit_prereq_interactive_links(cards, quick)
        self.assertEqual(out[0]["interactive_links"], [])

    def test_short_form_reference_links_via_title_alias(self):
        # A later topic that refers to an earlier one by its SHORT name ("total probability") must still link
        # to the full-title topic ("Law of Total Probability"). This is why a live Bayes path showed no links.
        os.environ[_FLAG] = "1"
        intro = _Topic("i", "Bayesian Overview", 0, course_type="study_path_introduction")
        totalp = _Topic("t1", "Law of Total Probability", 1)
        bayes = _Topic("t2", "Bayes' Theorem", 2)
        _Path([intro, totalp, bayes])
        cards = [{"card_type": "formula", "points": ["Bayes' theorem builds on total probability."]}]
        out = _emit_prereq_interactive_links(cards, bayes)
        links = out[0]["interactive_links"]
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["action"], "review_earlier_topic")
        self.assertEqual(links[0]["target"], "t1")
        self.assertEqual(links[0]["text"], "total probability")

    def test_conversion_preserves_interactive_links(self):
        # THE bug that hid every link: the lean->legacy conversion hardcoded interactive_links: [], discarding
        # whatever the emission put on the lean card. It must carry them through.
        lean = {"card_type": "formula", "title": "X", "points": ["a"], "interactive_links": [
            {"text": "total probability", "action": "review_earlier_topic", "target": "t2",
             "concept_id": "ltp", "explanation": "e"}]}
        legacy = _lean_card_to_legacy(lean, 0, [])
        self.assertEqual(len(legacy["interactive_links"]), 1)
        self.assertEqual(legacy["interactive_links"][0]["action"], "review_earlier_topic")

    def test_conversion_defaults_empty_when_no_links(self):
        legacy = _lean_card_to_legacy({"card_type": "formula", "title": "X", "points": ["a"]}, 0, [])
        self.assertEqual(legacy["interactive_links"], [])

    def test_title_aliases(self):
        self.assertEqual(_topic_title_aliases("Law of Total Probability"), ["Total Probability"])
        self.assertEqual(_topic_title_aliases("Calculating Voltage"), ["Voltage"])
        self.assertEqual(_topic_title_aliases("Bayes' Theorem"), [])   # no leading filler → no alias

    def test_open_study_path_for_external_prerequisite_on_intro(self):
        os.environ[_FLAG] = "1"
        intro = _Topic("i", "Introduction to Ohm's Law", 0, prereqs=["Voltage"],
                       course_type="study_path_introduction")
        _Path([intro, _Topic("t1", "Ohm's Law", 1)])
        cards = [{"card_type": "definition", "title": "Prerequisites", "points": ["You should know Voltage."]}]
        out = _emit_prereq_interactive_links(cards, intro)
        links = out[0]["interactive_links"]
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["action"], "open_study_path")
        self.assertEqual(links[0]["text"], "Voltage")
        self.assertTrue(links[0]["target"])                        # a scoped target goal

    def test_open_study_path_only_on_prereq_card_not_scattered(self):
        # A prereq mentioned on a non-prereq card AND the prereq card → the link appears ONLY on the prereq card.
        os.environ[_FLAG] = "1"
        intro = _Topic("i", "Intro to Ohm's Law", 0, prereqs=["Voltage"],
                       course_type="study_path_introduction")
        _Path([intro, _Topic("t1", "Ohm's Law", 1)])
        cards = [
            {"card_type": "purpose_context", "title": "Overview", "points": ["Voltage drives current here."]},
            {"card_type": "purpose_context", "title": "Prerequisites for Ohm's Law", "points": ["Voltage basics."]},
        ]
        out = _emit_prereq_interactive_links(cards, intro)
        self.assertEqual(out[0]["interactive_links"], [])                       # overview card: no scattered link
        self.assertEqual(len(out[1]["interactive_links"]), 1)                   # prereq card: the link
        self.assertEqual(out[1]["interactive_links"][0]["action"], "open_study_path")


if __name__ == "__main__":
    unittest.main()
