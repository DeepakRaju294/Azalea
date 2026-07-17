"""§6.2 live emission: the lean generator populates each card's interactive_links from the deterministic
scanner — review_earlier_topic for a concept taught by an EARLIER topic in the path, open_study_path for an
external assumed prerequisite. Flag-gated (AZALEA_PREREQ_LINKS); off ⇒ links stay []."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.lean_lesson_generator import (
    _attach_link_anchors, _concepts_from_prereq_line, _emit_prereq_interactive_links, _lean_card_to_legacy,
    _model_popup_links, _strip_prereq_goal_phrase, _topic_title_aliases,
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

    def test_prereq_links_extracted_from_card_when_field_empty(self):
        # assumed_prerequisites is empty (common), but the prereq card lists prereqs → they become links anyway.
        os.environ[_FLAG] = "1"
        intro = _Topic("i", "Intro", 0, course_type="study_path_introduction")
        _Path([intro, _Topic("t1", "Bayes", 1)])
        cards = [{"card_type": "purpose_context", "title": "Foundational Ideas",
                  "points": ["Basic probability concepts", "  - probabilities sum to 1",
                             "Understanding conditional probability", "  - needed for Bayes"]}]
        out = _emit_prereq_interactive_links(cards, intro)
        links = out[0]["interactive_links"]
        texts = {l["text"] for l in links}
        self.assertIn("Basic probability concepts", texts)
        self.assertIn("conditional probability", texts)                # goal-phrase "Understanding " stripped
        self.assertTrue(all(l["action"] == "open_study_path" for l in links))

    def test_strip_prereq_goal_phrase(self):
        self.assertEqual(_strip_prereq_goal_phrase("Understanding conditional probability"),
                         "conditional probability")
        self.assertEqual(_strip_prereq_goal_phrase("Knowledge of vectors"), "vectors")
        self.assertEqual(_strip_prereq_goal_phrase("Sample spaces"), "Sample spaces")   # no prefix

    def test_concepts_from_sentence_form_prereqs(self):
        # The prereq card is often prose, not a concept list — extraction must still recover the concepts.
        self.assertEqual(
            _concepts_from_prereq_line("… assumed, such as sample space and independence"),
            ["sample space", "independence"])
        self.assertEqual(
            _concepts_from_prereq_line("Understanding conditional probability is essential for Bayes."),
            ["conditional probability"])
        self.assertEqual(_concepts_from_prereq_line("Vectors"), ["Vectors"])   # bare concept

    def test_prereq_links_from_sentence_form_card(self):
        os.environ[_FLAG] = "1"
        intro = _Topic("i", "Intro", 0, course_type="study_path_introduction")
        _Path([intro, _Topic("t1", "Bayes", 1)])
        cards = [{"card_type": "purpose_context", "title": "Prerequisites", "points": [
            "Understanding conditional probability is essential for grasping Bayes.",
            "Basic ideas are assumed, such as sample space and independence.",
        ]}]
        out = _emit_prereq_interactive_links(cards, intro)
        texts = {l["text"] for l in out[0]["interactive_links"]}
        self.assertIn("conditional probability", texts)
        self.assertIn("sample space", texts)

    def test_model_popup_glosses_are_preserved_when_popups_enabled(self):
        # An LLM-authored popup_only gloss for an undefined term survives the emission when popups are ENABLED
        # (AZALEA_TERM_GLOSSES). Nav links are unaffected either way.
        os.environ[_FLAG] = "1"
        os.environ["AZALEA_TERM_GLOSSES"] = "1"
        try:
            intro = _Topic("i", "Intro", 0, course_type="study_path_introduction")
            body = _Topic("t1", "Sampling", 1)
            _Path([intro, body])
            cards = [{"card_type": "background", "points": ["A partition splits the space."],
                      "interactive_links": [
                          {"text": "partition", "action": "popup_only",
                           "explanation": "A split of the sample space into disjoint parts."}]}]
            out = _emit_prereq_interactive_links(cards, body)
            links = out[0]["interactive_links"]
            self.assertTrue(any(l["action"] == "popup_only" and l["text"] == "partition" for l in links))
        finally:
            os.environ.pop("AZALEA_TERM_GLOSSES", None)

    def test_popups_suppressed_when_disabled_but_nav_links_survive(self):
        # Popups OFF (AZALEA_TERM_GLOSSES unset): a model popup_only gloss is dropped, but the deterministic
        # review_earlier_topic nav link is still emitted.
        os.environ[_FLAG] = "1"
        os.environ.pop("AZALEA_TERM_GLOSSES", None)
        _, comp, quick = self._sorting_path()
        cards = [{"card_type": "background", "points": ["Quick Sort builds on Comparison Sort."],
                  "interactive_links": [
                      {"text": "Quick Sort", "action": "popup_only", "explanation": "a fast sort"}]}]
        out = _emit_prereq_interactive_links(cards, quick)
        links = out[0]["interactive_links"]
        self.assertFalse(any(l["action"] == "popup_only" for l in links))          # popup dropped
        self.assertTrue(any(l["action"] == "review_earlier_topic" for l in links))  # nav link kept

    def test_model_popup_dropped_when_anchor_absent(self):
        card = {"points": ["nothing here"], "interactive_links": [
            {"text": "entropy", "action": "popup_only", "explanation": "disorder"}]}
        self.assertEqual(_model_popup_links(card, "nothing here"), [])   # "entropy" not in text

    def test_model_popup_requires_explanation(self):
        card = {"interactive_links": [{"text": "partition", "action": "popup_only", "explanation": ""}]}
        self.assertEqual(_model_popup_links(card, "a partition"), [])

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


class LinkAnchors(unittest.TestCase):
    def test_anchor_tags_the_containing_item(self):
        card = {"points": ["Intro line.", "Uses Counting Principles for outcomes.", "Order matters."]}
        links = [{"text": "Counting Principles", "action": "open_study_path"}]
        _attach_link_anchors(card, links)
        self.assertEqual(links[0]["anchor"], {"field": "points", "index": 1})

    def test_body_and_bullets_fields_supported(self):
        card = {"bullets": ["a partition splits the space"]}
        links = [{"text": "partition", "action": "popup_only"}]
        _attach_link_anchors(card, links)
        self.assertEqual(links[0]["anchor"], {"field": "bullets", "index": 0})

    def test_no_anchor_when_text_absent(self):
        card = {"points": ["nothing relevant here"]}
        links = [{"text": "entropy", "action": "popup_only"}]
        _attach_link_anchors(card, links)
        self.assertNotIn("anchor", links[0])

    def test_anchor_survives_lean_to_legacy(self):
        lean = {"card_type": "background", "points": ["p"], "interactive_links": [
            {"text": "x", "action": "review_earlier_topic", "target": "t", "anchor": {"field": "points", "index": 0}}]}
        legacy = _lean_card_to_legacy(lean, 0, [])
        self.assertEqual(legacy["interactive_links"][0]["anchor"], {"field": "points", "index": 0})


if __name__ == "__main__":
    unittest.main()
