"""Regression for a live "Ohm's Law" path that generated a SINGLE topic titled "With Ohm's Law": a title that
begins with a dangling preposition/conjunction ("With Ohm's Law") is repaired. (A genuinely single-technique
path is INTENTIONALLY left lean with no synthesized intro — see the fixture tests — so that is unchanged.)"""
import unittest

from app.services.topic_decomposition_pipeline import (
    _repair_topic_title, generate_decomposed_topics,
)

_SINGLE = {
    "path_plan": {
        "end_capability": "Apply Ohm's Law to solve circuit problems.",
        "end_capability_actions": ["calculate"],
        "required_capabilities": [
            {"capability_id": "calculate_ohms_law", "description": "Calculate with Ohm's Law.",
             "prerequisite_capability_ids": [], "satisfies_end_actions": ["calculate"],
             "ownership_mode": "standalone", "owner_topic_id": None, "basis": "goal"},
        ],
    },
    "topics": [
        {"topic_id": "t1", "capability_id": "calculate_ohms_law", "subject_key": "ohms_law_calculation",
         "primary_action": "calculate", "content_role": "operation", "topic_type": "science_mechanism",
         "title": "With Ohm's Law", "unit_title": "Core", "purpose": "Apply the formula.", "in_scope": ["V=IR"],
         "practice_target": "solve", "practice_format": "short_answer",
         "practice_evidence_type": "solve_numeric", "expected_output": "answers", "basis": "goal"},
    ],
}


class TitleRepair(unittest.TestCase):
    def test_strips_dangling_leading_preposition(self):
        self.assertEqual(_repair_topic_title("With Ohm's Law", "ohms_law_calculation"), "Ohm's Law")

    def test_leaves_legit_titles_untouched(self):
        for good in ("For Loops", "In-place Sorting", "Ohm's Law", "Tracing BFS", "On-policy Methods"):
            self.assertEqual(_repair_topic_title(good, "x"), good)

    def test_all_junk_falls_back_to_subject(self):
        self.assertEqual(_repair_topic_title("with of", "merge_sort"), "Merge Sort")


class SingleTopicPipeline(unittest.TestCase):
    def _run(self):
        return generate_decomposed_topics("Want to learn about Ohm's law", "src",
                                          model_fn=lambda payload: _SINGLE)

    def test_single_technique_stays_lean_no_intro(self):
        # Intentional: a genuinely single-technique path is not padded with an orientation intro.
        topics = self._run()
        self.assertEqual([t["course_type"] for t in topics], ["science_mechanism"])

    def test_the_teaching_topic_title_is_repaired_end_to_end(self):
        topics = self._run()
        self.assertEqual(topics[0]["title"], "Ohm's Law")           # not "With Ohm's Law"


if __name__ == "__main__":
    unittest.main()
