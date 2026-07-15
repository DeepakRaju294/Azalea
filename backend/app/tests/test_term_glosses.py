"""Glossary popups (AZALEA_TERM_GLOSSES): a dedicated LLM pass attaches popup_only glosses for TECHNICAL terms
the prose uses but never defines (not prerequisites, not defined key terms, not taught-topic names). The model
call is injected so the test is deterministic and offline."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.lean_lesson_generator import (
    _acceptable_gloss_term, _attach_undefined_term_glosses, _emit_prereq_interactive_links,
    _lesson_defined_term_names,
)

_FLAG = "AZALEA_TERM_GLOSSES"


class _Topic:
    def __init__(self, tid, title, order, prereqs=None, ctype="math_formula_method"):
        self.id, self.title, self.order_index = tid, title, order
        self.course_type, self.topic_type = ctype, None
        self.assumed_prerequisites = prereqs or []
        self.decomposition_metadata = {}
        self.study_path = None


class _Path:
    def __init__(self, topics, domain="math"):
        self.topics, self.domain = topics, domain
        for t in topics:
            t.study_path = self


def _fixed(glosses):
    """A model_fn that ignores its inputs and returns a fixed gloss list."""
    return lambda prose, exclude, title: glosses


class TermGlosses(unittest.TestCase):
    def setUp(self):
        self._prev = os.environ.get(_FLAG)
        os.environ[_FLAG] = "1"

    def tearDown(self):
        if self._prev is None:
            os.environ.pop(_FLAG, None)
        else:
            os.environ[_FLAG] = self._prev

    def _cards(self):
        return [
            {"card_type": "formula", "title": "Formula", "points": [
                "The partitions are disjoint and cover the whole sample space."]},
            {"card_type": "definition", "title": "Key Terms", "points": [
                "P(A)", "  - probability of event A"]},
        ]

    def test_attaches_popup_for_undefined_term(self):
        topic = _Topic("t", "Law of Total Probability", 1)
        _Path([topic])
        cards = self._cards()
        out = _attach_undefined_term_glosses(cards, topic, model_fn=_fixed(
            [{"term": "disjoint", "gloss": "having no outcomes in common"}]))
        links = out[0].get("interactive_links") or []
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["action"], "popup_only")
        self.assertEqual(links[0]["text"], "disjoint")
        self.assertEqual(links[0]["explanation"], "having no outcomes in common")

    def test_flag_off_is_noop_and_skips_model(self):
        os.environ.pop(_FLAG, None)
        topic = _Topic("t", "T", 1)
        _Path([topic])
        called = {"n": 0}

        def _fn(prose, exclude, title):
            called["n"] += 1
            return [{"term": "disjoint", "gloss": "x"}]

        out = _attach_undefined_term_glosses(self._cards(), topic, model_fn=_fn)
        self.assertEqual(called["n"], 0)
        self.assertNotIn("interactive_links", out[0])

    def test_excludes_defined_terms_prereqs_and_topic_titles(self):
        topic = _Topic("t", "Bayes' Theorem", 2, prereqs=["conditional probability"])
        sib = _Topic("t1", "Law of Total Probability", 1)
        _Path([sib, topic])
        cards = [
            {"card_type": "formula", "points": [
                "Bayes' Theorem uses conditional probability and the law of total probability; P(A) is the prior."]},
            {"card_type": "definition", "points": ["P(A)", "  - the prior"]},
        ]
        # The model (mis)returns excluded terms; the attach step must drop all of them.
        out = _attach_undefined_term_glosses(cards, topic, model_fn=_fixed([
            {"term": "conditional probability", "gloss": "x"},   # a prerequisite
            {"term": "P(A)", "gloss": "x"},                       # a defined key term
            {"term": "Bayes' Theorem", "gloss": "x"},             # the topic's own title
            {"term": "Law of Total Probability", "gloss": "x"},   # a sibling taught topic
        ]))
        self.assertEqual(out[0].get("interactive_links", []), [])

    def test_case_insensitive_surface_form(self):
        topic = _Topic("t", "T", 1)
        _Path([topic])
        cards = [{"card_type": "purpose_context", "points": ["A Partition splits the sample space."]}]
        out = _attach_undefined_term_glosses(cards, topic, model_fn=_fixed(
            [{"term": "partition", "gloss": "a split into non-overlapping parts"}]))
        # anchored using the surface form actually present in the text ("Partition")
        self.assertEqual(out[0]["interactive_links"][0]["text"], "Partition")

    def test_not_attached_on_definition_or_prereq_cards(self):
        topic = _Topic("t", "T", 1)
        _Path([topic])
        cards = [{"card_type": "definition", "points": ["disjoint sets have no overlap"]}]
        out = _attach_undefined_term_glosses(cards, topic, model_fn=_fixed(
            [{"term": "disjoint", "gloss": "no overlap"}]))
        self.assertNotIn("interactive_links", out[0])   # a key-terms card is not a glossable surface

    def test_gloss_survives_emission(self):
        os.environ["AZALEA_PREREQ_LINKS"] = "1"
        try:
            topic = _Topic("t", "Law of Total Probability", 1)
            _Path([topic])
            cards = [{"card_type": "formula", "points": ["The partitions are disjoint sets."]}]
            attached = _attach_undefined_term_glosses(cards, topic, model_fn=_fixed(
                [{"term": "disjoint", "gloss": "having no outcomes in common"}]))
            out = _emit_prereq_interactive_links(attached, topic)
            links = out[0]["interactive_links"]
            self.assertTrue(any(l["action"] == "popup_only" and l["text"] == "disjoint" for l in links))
        finally:
            os.environ.pop("AZALEA_PREREQ_LINKS", None)


class OverGlossingFilter(unittest.TestCase):
    def test_rejects_ordinary_words_and_course_vocabulary(self):
        excl = {"conditional probability", "bayes theorem"}
        excl_norm = {"conditional probability", "bayes theorem"}
        for bad in ("scenarios", "decisions", "probabilities", "outcomes", "prior probabilities",
                    "posterior probability", "substituted probabilities", "conditional probability"):
            self.assertFalse(_acceptable_gloss_term(bad, excl_norm), bad)

    def test_keeps_real_technical_terms(self):
        for good in ("sample space", "probabilistic reasoning", "disjoint", "partition"):
            self.assertTrue(_acceptable_gloss_term(good, set()), good)

    def test_attach_drops_over_glossed_terms_live(self):
        os.environ[_FLAG] = "1"
        topic = _Topic("t", "Law of Total Probability", 1)
        _Path([topic])
        cards = [{"card_type": "purpose_context", "points": [
            "Different scenarios affect the probabilities across the sample space."]}]
        out = _attach_undefined_term_glosses(cards, topic, model_fn=_fixed([
            {"term": "scenarios", "gloss": "different situations"},        # ordinary → dropped
            {"term": "probabilities", "gloss": "likelihoods"},             # course vocab → dropped
            {"term": "sample space", "gloss": "the set of all outcomes"},  # real term → kept
        ]))
        links = out[0].get("interactive_links") or []
        self.assertEqual([l["text"] for l in links], ["sample space"])


class DefinedTermNames(unittest.TestCase):
    def test_extracts_headers_skips_indented_and_equations(self):
        cards = [{"card_type": "definition", "points": [
            "Prior Probability", "  - the initial estimate", "$$P(A)$$", "Likelihood: the evidence prob"]}]
        names = _lesson_defined_term_names(cards)
        self.assertIn("prior probability", names)
        self.assertIn("likelihood", names)
        self.assertNotIn("the initial estimate", names)
        self.assertNotIn("$$p(a)$$", names)


if __name__ == "__main__":
    unittest.main()
