"""Named planning fixtures (STUDY_PATH_SCOPE_SPEC §9) exercised end-to-end through build_plan. Phase-1A covers
the PLANNING fixtures only; algorithm_grounding and minimal_grounding are the Phase-1B first slice (adapter-
evidence-only grounding) and are built below. The remaining grounding/certification fixtures (partial_
verification, wrong_concept_executable, source_conflict, course_convention, general_grounding_abuse,
semantic_repair, status_authorization, notation_aliases) need verifier tiers or registries that don't exist
yet and are intentionally not built here. scope_bayes_total_prob lives in test_study_path_scope_builder.py."""
import os
import types
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.core import study_path_scope as sc
from app.core.study_path_scope import (
    AlgorithmGrounding, ConceptDraft, DecompositionInput, Facet, GeneralConceptGrounding, GoalRequirement,
    GroundingStatus, PlanningStatus, PrereqDraft, SelectionMethod,
)


def _req(rid, desc="", required=True):
    return GoalRequirement(requirement_id=rid, description=desc or rid, required=required)


def _c(key, name, reqs=(), *, facet=Facet.core, topic_type="math_formula_method", prereq_keys=(),
       bridges=(), method=SelectionMethod.explicit_goal, aliases=()):
    return ConceptDraft(canonical_concept_key=key, name=name, topic_type=topic_type, facet=facet,
                        covers_requirements=list(reqs), bridges_requirements=list(bridges),
                        prerequisite_keys=list(prereq_keys), selection_method=method, aliases=list(aliases))


class ScopePrereqOnly(unittest.TestCase):
    def test_single_concept_with_a_prereq(self):
        plan = sc.build_plan(DecompositionInput(
            goal="learn completing the square", domain="math", requirements=[_req("r1", "completing the square")],
            concepts=[_c("completing_the_square", "Completing the Square", ["r1"])],
            prereqs=[PrereqDraft(id="quadratic", name="quadratic equations")],
            mention_order=["completing_the_square"]))
        self.assertEqual(plan.identity.planning_status, PlanningStatus.structurally_valid)
        self.assertEqual(len(plan.curriculum.concepts), 1)
        self.assertIn("quadratic", {p.id for p in plan.curriculum.prerequisites})
        self.assertNotIn("quadratic", {c.identity.canonical_concept_key for c in plan.curriculum.concepts})


class ScopeAmbiguousExpectedValue(unittest.TestCase):
    def test_unresolved_ambiguity_rejects_the_plan(self):
        plan = sc.build_plan(DecompositionInput(
            goal="learn expected value", domain="math", requirements=[_req("r1", "expected value")],
            concepts=[_c("expected_value", "Expected Value", ["r1"])],
            unresolved_ambiguities=["'expected value' is discrete or continuous — unresolved"]))
        self.assertEqual(plan.identity.planning_status, PlanningStatus.rejected)
        self.assertIn("selection_honesty", sc.failed_invariants(plan.validation))


class ScopeIndependentOrderSorts(unittest.TestCase):
    def test_goal_mention_order_beats_alphabetical(self):
        # "quicksort and mergesort" — independent; must follow mention order, not alphabetical.
        plan = sc.build_plan(DecompositionInput(
            goal="quicksort and mergesort", domain="coding",
            requirements=[_req("r_q", "quicksort"), _req("r_m", "mergesort")],
            concepts=[_c("quicksort", "Quicksort", ["r_q"], topic_type="algorithm_walkthrough"),
                      _c("mergesort", "Mergesort", ["r_m"], topic_type="algorithm_walkthrough")],
            mention_order=["quicksort", "mergesort"]))
        by_id = {c.identity.concept_id: c.identity.canonical_concept_key for c in plan.curriculum.concepts}
        self.assertEqual([by_id[i] for i in plan.curriculum.resolved_concept_order],
                         ["quicksort", "mergesort"])


class ScopeCyclicDependency(unittest.TestCase):
    def test_cycle_is_rejected_never_auto_broken(self):
        plan = sc.build_plan(DecompositionInput(
            goal="a and b", domain="math", requirements=[_req("r_a"), _req("r_b")],
            concepts=[_c("a", "A", ["r_a"], prereq_keys=["b"]),
                      _c("b", "B", ["r_b"], prereq_keys=["a"])]))
        self.assertEqual(plan.identity.planning_status, PlanningStatus.rejected)
        self.assertIn("order_acyclic", sc.failed_invariants(plan.validation))


class ScopeBridgeConcept(unittest.TestCase):
    def test_total_probability_appears_as_a_bridge_mapping(self):
        plan = sc.build_plan(DecompositionInput(
            goal="learn bayes' theorem", domain="math", requirements=[_req("r_bayes", "bayes")],
            concepts=[_c("bayes_theorem", "Bayes' Theorem", ["r_bayes"], prereq_keys=["law_of_total_probability"]),
                      _c("law_of_total_probability", "Law of Total Probability", (), bridges=["r_bayes"])],
            mention_order=["law_of_total_probability", "bayes_theorem"]))
        self.assertEqual(plan.identity.planning_status, PlanningStatus.structurally_valid)
        relations = {(m.concept_id, m.relation.value)
                     for m in plan.curriculum.decomposition_record.concept_coverage}
        tp_id = next(c.identity.concept_id for c in plan.curriculum.concepts
                     if c.identity.canonical_concept_key == "law_of_total_probability")
        self.assertIn((tp_id, "bridge"), relations)


class ScopeExclusionEnforcement(unittest.TestCase):
    def test_proofs_excluded_leaves_no_proof_section(self):
        plan = sc.build_plan(DecompositionInput(
            goal="derivatives without proofs", domain="math", target_depth="mastery", exclusions=["proofs"],
            requirements=[_req("r1", "derivatives")],
            concepts=[_c("derivatives", "Derivatives", ["r1"]),
                      _c("derivatives", "Proof of the power rule", (), facet=Facet.correctness,
                         topic_type="proof_reasoning")]))
        self.assertEqual(plan.identity.planning_status, PlanningStatus.structurally_valid)
        sections = [s.section_type.value for c in plan.curriculum.concepts for s in c.section_plan]
        self.assertNotIn("proof", sections)


class ScopeDepthCardinality(unittest.TestCase):
    def _input(self, depth):
        return DecompositionInput(
            goal="dijkstra", domain="coding", target_depth=depth, requirements=[_req("r1", "dijkstra")],
            concepts=[_c("dijkstra", "Dijkstra", ["r1"], topic_type="algorithm_walkthrough"),
                      _c("dijkstra", "Implementing Dijkstra", (), facet=Facet.implementation,
                         topic_type="algorithm_walkthrough"),
                      _c("dijkstra", "Why Dijkstra is correct", (), facet=Facet.correctness,
                         topic_type="proof_reasoning")])

    def test_quick_review_is_atomic(self):
        plan = sc.build_plan(self._input("overview"))
        dj = plan.curriculum.concepts[0]
        self.assertEqual(dj.cardinality_policy, sc.CardinalityPolicy.atomic)
        self.assertIsNone(dj.split_reason)

    def test_mastery_is_multi_section(self):
        plan = sc.build_plan(self._input("mastery"))
        dj = plan.curriculum.concepts[0]
        self.assertEqual(dj.cardinality_policy, sc.CardinalityPolicy.multi_section)
        self.assertIsNotNone(dj.split_reason)


class ScopeAliasVsFacet(unittest.TestCase):
    def test_aliases_merge_into_one_concept(self):
        # "Bayes' theorem" + "Bayes' rule" → same canonical key → one concept, the other name an alias.
        plan = sc.build_plan(DecompositionInput(
            goal="bayes", domain="math", requirements=[_req("r1")],
            concepts=[_c("bayes_theorem", "Bayes' Theorem", ["r1"], aliases=["Bayes' rule"])]))
        self.assertEqual(len(plan.curriculum.concepts), 1)
        self.assertIn("Bayes' rule", plan.curriculum.concepts[0].identity.aliases)

    def test_derivation_facet_becomes_a_section_not_a_duplicate(self):
        plan = sc.build_plan(DecompositionInput(
            goal="bayes", domain="math", target_depth="mastery", requirements=[_req("r1")],
            concepts=[_c("bayes_theorem", "Bayes' Theorem", ["r1"]),
                      _c("bayes_theorem", "Derivation of Bayes'", (), facet=Facet.derivation,
                         topic_type="proof_reasoning")]))
        self.assertEqual(len(plan.curriculum.concepts), 1)          # one concept, not a dup
        sections = [s.section_type.value for s in plan.curriculum.concepts[0].section_plan]
        self.assertIn("derivation", sections)


def _topic(title, course_type, subject_key=""):
    """Duck-typed pipeline topic — same shape scope_shadow.py assembles (title/course_type/
    decomposition_metadata), which is all scope_grounding.ground_concept needs to route an adapter."""
    return types.SimpleNamespace(title=title, course_type=course_type,
                                 decomposition_metadata={"subject_key": subject_key})


class ScopeAlgorithmGrounding(unittest.TestCase):
    """§9 scope_algorithm_grounding (Phase 1B first slice): a concept with a verified real adapter grounds
    via AlgorithmGrounding, adapter-evidence only — never invented."""
    def test_bfs_concept_grounds_via_its_verified_adapter(self):
        from app.services.scope_grounding import ground_concept
        plan = sc.build_plan(DecompositionInput(
            goal="graph traversal", domain="coding", requirements=[_req("r1", "bfs")],
            concepts=[_c("bfs", "Breadth-First Search", ["r1"], topic_type="algorithm_walkthrough")]))
        concept = plan.curriculum.concepts[0]
        grounding = ground_concept(concept, _topic("Breadth-First Search", "algorithm_walkthrough"))
        self.assertIsInstance(grounding, AlgorithmGrounding)
        self.assertEqual(grounding.status, GroundingStatus.grounded)
        self.assertEqual(grounding.adapter_slug, "bfs")
        self.assertTrue(grounding.summary.required_artifacts_present)


class ScopeMinimalGrounding(unittest.TestCase):
    """§9 scope_minimal_grounding (Phase 1B first slice): a concept with no adapter match degrades
    explicitly (§6.1 — missing facts degrade, never invent), rather than being silently skipped or
    fabricated."""
    def test_no_adapter_match_degrades_with_a_reason(self):
        from app.services.scope_grounding import ground_concept
        plan = sc.build_plan(DecompositionInput(
            goal="history of computing", domain="coding", requirements=[_req("r1", "history")],
            concepts=[_c("history_of_computing", "Historical Context of Computing", ["r1"],
                         topic_type="conceptual_overview")]))
        concept = plan.curriculum.concepts[0]
        grounding = ground_concept(concept, _topic("Historical Context of Computing", "conceptual_overview"))
        self.assertIsInstance(grounding, GeneralConceptGrounding)
        self.assertEqual(grounding.status, GroundingStatus.degraded)
        self.assertEqual(grounding.degrade_reason, "no_adapter_match")
        self.assertFalse(grounding.summary.required_artifacts_present)


class ScopePlanningLifecycle(unittest.TestCase):
    def test_valid_ungrounded_plan_is_structurally_valid_and_not_started(self):
        plan = sc.build_plan(DecompositionInput(
            goal="completing the square", domain="math", requirements=[_req("r1")],
            concepts=[_c("completing_the_square", "Completing the Square", ["r1"])]))
        self.assertEqual(plan.identity.planning_status, PlanningStatus.structurally_valid)
        self.assertEqual(plan.identity.certification_status, sc.CertificationStatus.not_started)


if __name__ == "__main__":
    unittest.main()
