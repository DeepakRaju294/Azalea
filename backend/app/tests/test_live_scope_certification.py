import unittest

from app.prompts.lean_lesson_prompt import TOPIC_FAMILY_FRAGMENTS, _detect_topic_families
from app.services.topic_generator import (
    _append_missing_coding_topics,
    _canonical_concept_key,
    _certify_path_scope,
    _mark_coding_follow_ups,
)


def _topic(title: str, topic_type: str, **extra):
    return {"title": title, "course_type": topic_type, "topic_type": topic_type, **extra}


class LiveScopeCertificationTests(unittest.TestCase):
    def test_acronym_and_expanded_names_share_one_identity(self):
        self.assertEqual(_canonical_concept_key("MST algorithms"), "minimum_spanning_tree")
        self.assertEqual(_canonical_concept_key("Minimum Spanning Trees"), "minimum_spanning_tree")
        self.assertEqual(_canonical_concept_key("BST traversal"), "binary_search_tree")
        self.assertEqual(_canonical_concept_key("Binary Search Trees"), "binary_search_tree")

    def test_scope_certification_removes_circular_prerequisite_and_duplicate_facet(self):
        topics = [
            _topic("Introduction", "study_path_introduction",
                   assumed_prerequisites=["Minimum Spanning Tree", "Weighted Graphs"],
                   decomposition_metadata={"brief_refresh_prerequisites": ["MST", "Cycle"]}),
            _topic("Kruskal's Algorithm", "algorithm_walkthrough"),
            _topic("Implementing Kruskal's", "coding_implementation"),
            _topic("Implementing Kruskal", "coding_implementation"),
        ]

        result = _certify_path_scope(topics, "Learn MST algorithms")

        self.assertNotIn("Implementing Kruskal", [t["title"] for t in result])
        intro = result[0]
        self.assertEqual(intro["assumed_prerequisites"], ["Weighted Graphs"])
        self.assertEqual(intro["decomposition_metadata"]["brief_refresh_prerequisites"], ["Cycle"])
        self.assertEqual(result[1]["decomposition_metadata"]["canonical_concept_key"], "kruskal")
        self.assertEqual(result[2]["decomposition_metadata"]["concept_facet"], "implementation")

    def test_coding_backfill_and_followup_use_canonical_identity_not_title_tokens(self):
        topics = [
            _topic("Kruskal's Algorithm", "algorithm_walkthrough"),
            _topic("Implementing Kruskal", "coding_implementation"),
        ]

        result = _append_missing_coding_topics(topics, "Learn MST algorithms")
        self.assertEqual(len(result), 2)
        _mark_coding_follow_ups(result)
        self.assertIn("implementation_follow_up", result[1]["modifiers"])

    def test_mst_topics_receive_targeted_accuracy_contract(self):
        for title in ("Kruskal's Algorithm", "Prim", "Minimum Spanning Trees"):
            self.assertIn("minimum_spanning_tree", _detect_topic_families(title))
        rules = TOPIC_FAMILY_FRAGMENTS["minimum_spanning_tree"]
        self.assertIn("minimum spanning FOREST", rules)
        self.assertIn("Equal-weight edges require no change", rules)


if __name__ == "__main__":
    unittest.main()
