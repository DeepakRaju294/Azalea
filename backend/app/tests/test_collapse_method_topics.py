"""A single simple procedure gets decomposed into TWO full method lessons of different types (e.g. a
process_walkthrough AND a problem_solving_application of "completing the square"). Both regenerate the same
background, steps, and worked example, so the learner reads the lesson twice. _collapse_same_subject_method_topics
keeps the teaching walkthrough and drops the duplicate. Legit same-subject companions (coding follow-up,
concept intuition) and distinct-subject family members are left alone. Deterministic, no LLM.

Run: python -m unittest app.tests.test_collapse_method_topics
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.topic_generator import _collapse_same_subject_method_topics as collapse


def _types(topics):
    return [t["course_type"] for t in topics]


def _titles(topics):
    return [t["title"] for t in topics]


class CollapseSameSubjectMethodTopics(unittest.TestCase):
    def test_walkthrough_plus_application_collapses_to_the_walkthrough(self):
        path = [
            {"title": "Introduction to Completing the Square", "course_type": "study_path_introduction"},
            {"title": "Understanding the Completing the Square Process", "course_type": "process_walkthrough"},
            {"title": "Completing the Square: Example Problems", "course_type": "problem_solving_application"},
        ]
        res = collapse([dict(t) for t in path])
        self.assertEqual(len(res), 2)
        self.assertNotIn("problem_solving_application", _types(res))  # the duplicate application is dropped
        self.assertIn("Understanding the Completing the Square Process", _titles(res))  # walkthrough kept

    def test_application_kept_when_it_is_the_only_method_topic(self):
        path = [
            {"title": "Introduction to Completing the Square", "course_type": "study_path_introduction"},
            {"title": "Completing the Square: Example Problems", "course_type": "problem_solving_application"},
        ]
        res = collapse([dict(t) for t in path])
        self.assertEqual(len(res), 2)  # nothing to collapse against -> kept

    def test_distinct_subject_family_members_are_untouched(self):
        path = [
            {"title": "Introduction to Sorting", "course_type": "study_path_introduction"},
            {"title": "Bubble Sort Walkthrough", "course_type": "algorithm_walkthrough"},
            {"title": "Merge Sort Walkthrough", "course_type": "algorithm_walkthrough"},
            {"title": "Quick Sort Walkthrough", "course_type": "algorithm_walkthrough"},
        ]
        res = collapse([dict(t) for t in path])
        self.assertEqual(len(res), 4)

    def test_coding_followup_of_same_subject_is_not_collapsed(self):
        # teach-then-code is a valid split; coding_implementation is not a "method lesson" duplicate
        path = [
            {"title": "BFS Walkthrough", "course_type": "algorithm_walkthrough"},
            {"title": "Implementing BFS", "course_type": "coding_implementation"},
        ]
        res = collapse([dict(t) for t in path])
        self.assertEqual(len(res), 2)

    def test_intuition_plus_walkthrough_of_same_subject_is_not_collapsed(self):
        # intuition-before-mechanics is a valid split; concept_intuition is not a "method lesson"
        path = [
            {"title": "What is a Hash Table", "course_type": "concept_intuition"},
            {"title": "Hash Table Insertion Walkthrough", "course_type": "data_structure_operation"},
        ]
        res = collapse([dict(t) for t in path])
        self.assertEqual(len(res), 2)

    def test_two_walkthroughs_of_same_subject_keep_the_earlier(self):
        path = [
            {"title": "Completing the Square Process", "course_type": "process_walkthrough"},
            {"title": "Completing the Square Walkthrough Step by Step", "course_type": "algorithm_walkthrough"},
        ]
        res = collapse([dict(t) for t in path])
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["title"], "Completing the Square Process")  # tie -> earlier kept

    def test_never_empties_the_path(self):
        # even a pathological all-same-subject list keeps at least one topic
        path = [
            {"title": "Completing the Square Process", "course_type": "process_walkthrough"},
            {"title": "Completing the Square Application", "course_type": "problem_solving_application"},
        ]
        res = collapse([dict(t) for t in path])
        self.assertGreaterEqual(len(res), 1)


if __name__ == "__main__":
    unittest.main()
