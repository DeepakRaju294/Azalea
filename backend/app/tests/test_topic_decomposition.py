"""Tests for the canonical topic-decomposition constants + helpers (TOPIC_DECOMPOSITION_SPEC.md)."""
import unittest

from app.core.topic_decomposition import (
    TOPIC_TYPES,
    ACTION_VERBS,
    PRACTICE_EVIDENCE_TYPES,
    is_coding_type,
    resolve_topic_type,
    role_matches_type,
    canonical_action,
    match_action,
    normalize_subject_key,
)


class CanonicalEnumTests(unittest.TestCase):
    def test_exactly_twelve_canonical_types(self):
        self.assertEqual(len(TOPIC_TYPES), 12)
        self.assertIn("coding_implementation", TOPIC_TYPES)
        # legacy aliases must NOT leak in as canonical types
        for legacy in ("system_architecture", "debugging_diagnosis", "compare_decide"):
            self.assertNotIn(legacy, TOPIC_TYPES)

    def test_is_coding_type(self):
        self.assertTrue(is_coding_type("coding_implementation"))
        self.assertFalse(is_coding_type("algorithm_walkthrough"))
        self.assertFalse(is_coding_type(None))


class RoleTypeMapTests(unittest.TestCase):
    def test_map_is_complete_over_12_types(self):
        reachable = {resolve_topic_type(r) for r in (
            "orientation", "foundation", "terminology", "operation", "algorithm_trace",
            "implementation", "calculation", "proof", "comparison", "application")}
        reachable |= {resolve_topic_type("mechanism", scientific=True),
                      resolve_topic_type("mechanism", scientific=False)}
        self.assertEqual(reachable, set(TOPIC_TYPES))

    def test_mechanism_routing(self):
        self.assertEqual(resolve_topic_type("mechanism", scientific=True), "science_mechanism")
        self.assertEqual(resolve_topic_type("mechanism", scientific=False), "process_walkthrough")

    def test_role_type_consistency(self):
        self.assertTrue(role_matches_type("implementation", "coding_implementation"))
        self.assertTrue(role_matches_type("mechanism", "science_mechanism"))
        self.assertTrue(role_matches_type("mechanism", "process_walkthrough"))
        self.assertFalse(role_matches_type("operation", "coding_implementation"))


class ActionMatchTests(unittest.TestCase):
    def test_canonical_action(self):
        self.assertEqual(canonical_action("implement"), "implement")
        self.assertEqual(canonical_action("walk through"), "trace")
        self.assertEqual(canonical_action("simulate"), "trace")
        self.assertIsNone(canonical_action("frobnicate"))

    def test_three_level_match(self):
        self.assertEqual(match_action("trace", "trace"), "exact")
        self.assertEqual(match_action("trace", "walk through"), "synonym")
        self.assertEqual(match_action("trace", "implement"), "none")
        self.assertEqual(match_action("trace", "frobnicate"), "none")

    def test_enum_membership(self):
        self.assertEqual(len(ACTION_VERBS), 12)
        self.assertIn("write_code", PRACTICE_EVIDENCE_TYPES)


class SubjectKeyTests(unittest.TestCase):
    def test_identity_preserved(self):
        self.assertEqual(normalize_subject_key("breadth_first_search"), "breadth_first_search")
        self.assertEqual(normalize_subject_key("Binary Search Tree"), "binary_search_tree")

    def test_trailing_algorithm_stripped_domain_kept(self):
        self.assertEqual(normalize_subject_key("Prim's Algorithm"), "prim")
        self.assertEqual(normalize_subject_key("Dijkstra's Algorithm"), "dijkstra")
        self.assertEqual(normalize_subject_key("Genetic Algorithm Selection"),
                         "genetic_algorithm_selection")
        self.assertEqual(normalize_subject_key("Algorithmic Complexity Analysis"),
                         "algorithmic_complexity_analysis")

    def test_framing_words_stripped(self):
        self.assertEqual(normalize_subject_key("Implement BFS"), "bfs")
        self.assertEqual(normalize_subject_key("Understanding the Quick Sort"), "quick_sort")

    def test_never_empty(self):
        self.assertTrue(normalize_subject_key("Overview"))  # all-framing -> falls back, not empty
        self.assertEqual(normalize_subject_key(""), "")


class CodingContinuationVariantTests(unittest.TestCase):
    def test_standalone_keeps_background(self):
        from app.core.course_blueprints import get_topic_blueprint
        bp = get_topic_blueprint("coding_implementation")
        self.assertIn("background", bp["default_card_sequence"])

    def test_follow_up_omits_background_only(self):
        from app.core.course_blueprints import get_topic_blueprint, IMPLEMENTATION_FOLLOW_UP
        full = get_topic_blueprint("coding_implementation")
        variant = get_topic_blueprint(
            "coding_implementation", relationship_to_parent=IMPLEMENTATION_FOLLOW_UP)
        self.assertNotIn("background", variant["default_card_sequence"])
        self.assertEqual(variant["lesson_variant"], "implementation_follow_up")
        # only difference is the removed background card; everything else identical
        self.assertEqual(
            [c for c in full["default_card_sequence"] if c != "background"],
            variant["default_card_sequence"],
        )
        for shared in ("code_walkthrough", "worked_example", "practice"):
            self.assertIn(shared, variant["default_card_sequence"])

    def test_follow_up_flag_ignored_for_non_coding(self):
        from app.core.course_blueprints import get_topic_blueprint, IMPLEMENTATION_FOLLOW_UP
        bp = get_topic_blueprint(
            "algorithm_walkthrough", relationship_to_parent=IMPLEMENTATION_FOLLOW_UP)
        self.assertIn("background", bp["default_card_sequence"])  # variant only applies to coding


if __name__ == "__main__":
    unittest.main()
