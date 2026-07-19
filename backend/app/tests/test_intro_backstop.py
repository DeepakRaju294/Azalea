"""Outermost intro guarantee in topic_generator — a multi-topic path always opens with an orientation
topic, even if the pipeline-level guarantee was bypassed (regeneration / stale decomposition)."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.topic_generator import _ensure_intro_topic

_TWO = [{"title": "Law of Total Probability", "course_type": "math_formula_method"},
        {"title": "Bayes' Theorem", "course_type": "problem_solving_application"}]


class IntroBackstop(unittest.TestCase):
    def test_prepends_intro_when_absent(self):
        out = _ensure_intro_topic([dict(t) for t in _TWO], "total probability and bayes")
        self.assertEqual(len(out), 3)
        self.assertEqual(out[0]["course_type"], "study_path_introduction")
        self.assertEqual(out[0]["order_index"], 1)
        self.assertEqual([t["order_index"] for t in out], [1, 2, 3])
        self.assertTrue(out[0]["title"].startswith("Introduction to"))

    def test_idempotent_when_intro_present(self):
        withintro = [{"title": "Intro", "course_type": "study_path_introduction"}] + _TWO
        out = _ensure_intro_topic([dict(t) for t in withintro], "g")
        self.assertEqual(sum(1 for t in out if t["course_type"] == "study_path_introduction"), 1)

    def test_respects_orientation_role(self):
        withrole = [{"title": "Start", "course_type": "concept_intuition", "content_role": "orientation"}] + _TWO
        out = _ensure_intro_topic([dict(t) for t in withrole], "g")
        self.assertEqual(len(out), 3)   # orientation role already present -> no synthetic intro

    def test_single_topic_gets_intro_too(self):
        # Product decision (live failure: a certified-down-to-one-topic path shipped with no orientation,
        # no prereq card, no roadmap): single-topic paths open with an intro like every other path.
        out = _ensure_intro_topic([dict(_TWO[0])], "g")
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["course_type"], "study_path_introduction")


if __name__ == "__main__":
    unittest.main()
