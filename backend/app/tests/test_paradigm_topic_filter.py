"""Auxiliary paradigm/methodology topics are dropped from a study path.

A merge-sort path must not include a standalone "Understanding Divide and Conquer" topic —
the algorithm topics already teach it by example. But when the paradigm IS the learner's
goal, the topics are kept. Deterministic, no LLM.

Run: python -m unittest app.tests.test_paradigm_topic_filter
"""
from __future__ import annotations

import os
import sys
import types
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")
for _name in ("dotenv", "openai"):
    if _name not in sys.modules:
        _m = types.ModuleType(_name)
        if _name == "dotenv":
            _m.load_dotenv = lambda *a, **k: None
        else:
            _m.OpenAI = lambda *a, **k: object()
            for _e in ("APIError", "RateLimitError", "APITimeoutError", "APIConnectionError"):
                setattr(_m, _e, type(_e, (Exception,), {}))
        sys.modules[_name] = _m

from app.services.topic_generator import _drop_paradigm_only_topics, _is_paradigm_only_topic


def _path():
    return [
        {"title": "Introduction to Merge Sort", "course_type": "study_path_introduction", "order_index": 1},
        {"title": "Understanding the Divide-and-Conquer Strategy", "course_type": "concept_intuition",
         "order_index": 2, "prerequisite_topics": ""},
        {"title": "What is Divide-and-Conquer?", "course_type": "concept_intuition", "order_index": 3},
        {"title": "Algorithm Walkthrough of Merge Sort", "course_type": "algorithm_walkthrough",
         "order_index": 4, "assumed_prerequisites": []},
        {"title": "Implementing Merge Sort in Code", "course_type": "coding_implementation", "order_index": 5},
    ]


class TestParadigmFilter(unittest.TestCase):
    def test_drops_paradigm_topics_on_algorithm_path(self):
        kept = _drop_paradigm_only_topics(_path(), "learn merge sort")
        titles = [t["title"] for t in kept]
        self.assertNotIn("Understanding the Divide-and-Conquer Strategy", titles)
        self.assertNotIn("What is Divide-and-Conquer?", titles)
        self.assertEqual(len(kept), 3)
        self.assertEqual([t["order_index"] for t in kept], [1, 2, 3])  # re-indexed
        wt = next(t for t in kept if t["title"].startswith("Algorithm"))
        self.assertIn("divide and conquer", wt["assumed_prerequisites"])  # captured for popup

    def test_keeps_paradigm_when_it_is_the_goal(self):
        kept = _drop_paradigm_only_topics(_path(), "learn divide and conquer")
        self.assertEqual(len(kept), 5)  # the paradigm IS the subject — keep all

    def test_keeps_when_no_concrete_topic(self):
        only_concept = [{"title": "Understanding Divide and Conquer", "course_type": "concept_intuition"}]
        self.assertEqual(len(_drop_paradigm_only_topics(only_concept, "x")), 1)

    def test_concrete_algorithm_title_not_dropped(self):
        # "Merge Sort" mentions no paradigm word and is concrete — never a paradigm topic.
        self.assertFalse(_is_paradigm_only_topic(
            {"title": "Algorithm Walkthrough of Merge Sort", "course_type": "algorithm_walkthrough"},
            "learn merge sort",
        ))


if __name__ == "__main__":
    unittest.main()
