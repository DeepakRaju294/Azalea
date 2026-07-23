"""app/services/scope_grounding.py — Phase 1B first slice (adapter-evidence-only grounding).
Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_scope_grounding
"""
import os
import types
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.core.study_path_scope import (
    AlgorithmGrounding, ConceptDraft, DecompositionInput, GeneralConceptGrounding, GoalRequirement,
    GroundingStatus, SelectionMethod, build_plan,
)
from app.services.scope_grounding import ground_concept, ground_concepts, grounding_counts


def _topic(title, course_type, subject_key=""):
    return types.SimpleNamespace(title=title, course_type=course_type,
                                 decomposition_metadata={"subject_key": subject_key})


def _plan(key, name, topic_type):
    return build_plan(DecompositionInput(
        goal=name, domain="coding", requirements=[GoalRequirement(requirement_id="r1", description=name)],
        concepts=[ConceptDraft(canonical_concept_key=key, name=name, topic_type=topic_type,
                               covers_requirements=["r1"], selection_method=SelectionMethod.explicit_goal)]))


class GroundConceptRouting(unittest.TestCase):
    def test_verified_adapter_grounds(self):
        plan = _plan("kruskal", "Kruskal's Algorithm", "algorithm_walkthrough")
        g = ground_concept(plan.curriculum.concepts[0], _topic("Kruskal's Algorithm", "algorithm_walkthrough"))
        self.assertIsInstance(g, AlgorithmGrounding)
        self.assertEqual(g.adapter_slug, "kruskal")

    def test_no_match_degrades_explicitly(self):
        plan = _plan("hash_tables", "Hash Tables", "algorithm_walkthrough")
        g = ground_concept(plan.curriculum.concepts[0], _topic("Hash Tables", "algorithm_walkthrough"))
        self.assertIsInstance(g, GeneralConceptGrounding)
        self.assertEqual(g.degrade_reason, "no_adapter_match")

    def test_intro_type_never_grounds_even_with_matching_words(self):
        # a topic tagged study_path_introduction must never claim adapter-verified content, even if its
        # title happens to contain adapter vocabulary (§6.1 — no invented grounding).
        plan = _plan("bfs_intro", "Breadth-First Search", "study_path_introduction")
        g = ground_concept(plan.curriculum.concepts[0], _topic("Breadth-First Search", "study_path_introduction"))
        self.assertIsInstance(g, GeneralConceptGrounding)


class GroundConceptsBulkAndCounts(unittest.TestCase):
    def test_bulk_grounding_and_counts_rollup(self):
        plan = build_plan(DecompositionInput(
            goal="graph traversal", domain="coding",
            requirements=[GoalRequirement(requirement_id="r1", description="bfs"),
                         GoalRequirement(requirement_id="r2", description="hash tables")],
            concepts=[ConceptDraft(canonical_concept_key="bfs", name="Breadth-First Search",
                                   topic_type="algorithm_walkthrough", covers_requirements=["r1"],
                                   selection_method=SelectionMethod.explicit_goal),
                     ConceptDraft(canonical_concept_key="hash_tables", name="Hash Tables",
                                   topic_type="algorithm_walkthrough", covers_requirements=["r2"],
                                   selection_method=SelectionMethod.explicit_goal)]))
        topics_by_key = {
            "bfs": _topic("Breadth-First Search", "algorithm_walkthrough"),
            "hash_tables": _topic("Hash Tables", "algorithm_walkthrough"),
        }
        groundings = ground_concepts(plan.curriculum.concepts, topics_by_key)
        self.assertEqual(set(groundings), {"bfs", "hash_tables"})
        self.assertEqual(grounding_counts(groundings), {"grounded": 1, "degraded": 1})

    def test_missing_topic_for_a_concept_key_is_skipped_not_crashed(self):
        plan = _plan("bfs", "Breadth-First Search", "algorithm_walkthrough")
        self.assertEqual(ground_concepts(plan.curriculum.concepts, {}), {})


class ShadowReportGroundingFlag(unittest.TestCase):
    """The grounding step is checked independently (AZALEA_STUDY_PATH_SCOPE_GROUNDING) — off by default,
    so shadow_report's existing Phase-1A behavior is byte-for-byte unchanged unless it's explicitly on."""

    def setUp(self):
        self._prev = os.environ.get("AZALEA_STUDY_PATH_SCOPE_GROUNDING")
        os.environ.pop("AZALEA_STUDY_PATH_SCOPE_GROUNDING", None)

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("AZALEA_STUDY_PATH_SCOPE_GROUNDING", None)
        else:
            os.environ["AZALEA_STUDY_PATH_SCOPE_GROUNDING"] = self._prev

    def test_disabled_by_default_no_grounding_summary_key(self):
        from app.services.scope_shadow import shadow_report
        topics = [_topic("Breadth-First Search", "algorithm_walkthrough")]
        report = shadow_report("graph traversal", "coding", topics)
        self.assertNotIn("grounding_summary", report)

    def test_enabled_adds_grounding_summary(self):
        from app.services.scope_shadow import shadow_report
        os.environ["AZALEA_STUDY_PATH_SCOPE_GROUNDING"] = "1"
        topics = [_topic("Breadth-First Search", "algorithm_walkthrough")]
        report = shadow_report("graph traversal", "coding", topics)
        self.assertIn("grounding_summary", report)
        self.assertEqual(report["grounding_summary"], {"grounded": 1, "degraded": 0})


if __name__ == "__main__":
    unittest.main()
