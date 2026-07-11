"""PR4 (planning validation + shadow telemetry) exit criteria for STUDY_PATH_SCOPE_SPEC Phase 1A. Pure — the
PlanningValidator §4.1–4.9, dual-status derivation, and neutral shadow diff. No grounding, no lessons, no
app-service imports (§4, §7, §10, §12)."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.core import study_path_scope as sc
from app.core.study_path_scope import (
    CertificationStatus, ConceptRelation, DiffClass, EvidenceStatus, PlanningStatus, SelectionEvidence,
    SelectionMethod, StudyPathScopePlan,
)


def _valid_plan() -> StudyPathScopePlan:
    """A minimal plan that passes all nine planning invariants: two math concepts (bridge→direct), both
    mapped (no orphan), acyclic with a correct resolved order, clean glossary, legal topic types."""
    tp = sc.ConceptIdentity.create(name="Law of Total Probability", topic_type="math_formula_method",
                                   canonical_concept_key="law_of_total_probability")
    bayes = sc.ConceptIdentity.create(name="Bayes' Theorem", topic_type="math_formula_method",
                                      canonical_concept_key="bayes_theorem")
    registry = sc.SelectionSourceRegistry()
    src = sc.ConceptSelectionSource.create(source_id="syllabus", span="Unit 3")
    registry.add(src)
    req = sc.GoalRequirement(requirement_id="r1", description="apply Bayes")

    def ev(method, target):
        return SelectionEvidence.create(method=method, requirement_id="r1", target_id=target,
                                        evidence_ref=src.selection_source_id)

    concept_map = sc.build_concept_mapping(requirement_id="r1", concept_id=bayes.concept_id,
                                           relation=ConceptRelation.direct,
                                           evidence=[ev(SelectionMethod.explicit_goal, bayes.concept_id)])
    bridge_map = sc.build_concept_mapping(requirement_id="r1", concept_id=tp.concept_id,
                                          relation=ConceptRelation.bridge,
                                          evidence=[ev(SelectionMethod.curriculum_graph, tp.concept_id)])
    return StudyPathScopePlan(
        identity=sc.ScopeIdentity(scope_id=sc.scope_id_for("bayes", "math")),
        intent=sc.ScopeIntent(goal="apply Bayes", goal_requirements=[req]),
        classification=sc.Classification(domain="math"),
        selection_sources=registry,
        curriculum=sc.CurriculumGraph(
            prerequisites=[sc.Prereq(id="conditional_probability", name="conditional probability")],
            concepts=[sc.Concept(identity=tp),
                      sc.Concept(identity=bayes, prerequisite_concept_ids=[tp.concept_id])],
            resolved_concept_order=[tp.concept_id, bayes.concept_id],
            glossary=[sc.GlossaryTerm(term="probability", gloss="a likelihood")],
            decomposition_record=sc.DecompositionRecord(
                goal_claims=[req], concept_coverage=[bridge_map, concept_map]),
        ),
    )


class HappyPath(unittest.TestCase):
    def test_valid_plan_is_structurally_valid(self):
        plan = sc.validate_and_stamp(_valid_plan())
        self.assertEqual(plan.identity.planning_status, PlanningStatus.structurally_valid)
        self.assertEqual(plan.identity.certification_status, CertificationStatus.not_started)   # unchanged in 1A
        self.assertEqual(sc.failed_invariants(plan.validation), [])
        # every emitted audit is a PLANNING audit (no certification invariants run in 1A).
        self.assertTrue(all(a.validator.value == "planning" for a in plan.validation.invariants))

    def test_round_trip_with_validation_is_lossless(self):
        plan = sc.validate_and_stamp(_valid_plan())
        again = StudyPathScopePlan.from_json(plan.to_json())
        self.assertEqual(again.model_dump(), plan.model_dump())


class PlanningInvariants(unittest.TestCase):
    """Each mutation breaks exactly one §4 invariant → rejected, with that invariant in the failed set."""

    def _reject(self, plan, invariant):
        plan = sc.validate_and_stamp(plan)
        self.assertEqual(plan.identity.planning_status, PlanningStatus.rejected)
        self.assertIn(invariant, sc.failed_invariants(plan.validation))

    def test_uncovered_requirement(self):        # §4.1
        p = _valid_plan()
        p.curriculum.decomposition_record.goal_claims.append(
            sc.GoalRequirement(requirement_id="r2", description="uncovered"))
        self._reject(p, "coverage")

    def test_orphan_concept(self):               # §4.1
        p = _valid_plan()
        orphan = sc.ConceptIdentity.create(name="Unrelated", topic_type="math_formula_method",
                                           canonical_concept_key="unrelated")
        p.curriculum.concepts.append(sc.Concept(identity=orphan))
        self._reject(p, "no_orphan_concept")

    def test_duplicate_concept(self):            # §4.2
        p = _valid_plan()
        dup = sc.ConceptIdentity.create(name="Bayes again", topic_type="math_formula_method",
                                        canonical_concept_key="bayes_theorem")   # same (key, facet)
        p.curriculum.concepts.append(sc.Concept(identity=dup))
        self._reject(p, "no_duplication")

    def test_prereq_also_taught(self):           # §4.3
        p = _valid_plan()
        p.curriculum.prerequisites.append(sc.Prereq(id="bayes_theorem", name="Bayes' Theorem"))
        self._reject(p, "prereq_concept_disjoint")

    def test_cyclic_order(self):                 # §4.4
        p = _valid_plan()
        tp, bayes = p.curriculum.concepts
        tp.prerequisite_concept_ids = [bayes.identity.concept_id]   # tp↔bayes cycle
        self._reject(p, "order_acyclic")

    def test_hard_edge_violation_in_resolved_order(self):   # §4.4
        p = _valid_plan()
        p.curriculum.resolved_concept_order = list(reversed(p.curriculum.resolved_concept_order))
        self._reject(p, "order_honours_hard_edges")

    def test_glossary_duplicate_term(self):      # §4.5
        p = _valid_plan()
        p.curriculum.glossary.append(sc.GlossaryTerm(term="probability", gloss="dup"))
        self._reject(p, "glossary_unique")

    def test_glossary_keyterm_clash(self):       # §4.5
        p = _valid_plan()
        p.curriculum.concepts[0].key_terms = ["probability"]   # also a glossary term
        self._reject(p, "glossary_keyterm_disjoint")

    def test_coding_topic_in_math_path(self):    # §4.6
        p = _valid_plan()
        p.curriculum.concepts[1].identity.topic_type = "coding_implementation"
        self._reject(p, "domain_legality")

    def test_multi_section_without_split_reason(self):   # §4.7
        p = _valid_plan()
        c = p.curriculum.concepts[1]
        c.section_plan = [
            sc.LessonSectionPlan.create(concept_id=c.identity.concept_id,
                                        section_type=sc.SectionType.walkthrough, order=1),
            sc.LessonSectionPlan.create(concept_id=c.identity.concept_id,
                                        section_type=sc.SectionType.complexity, order=2),
        ]
        c.split_reason = None
        self._reject(p, "section_structure")

    def test_objective_owned_only_by_optional_section(self):   # §4.7
        p = _valid_plan()
        c = p.curriculum.concepts[1]
        c.learning_objectives = [sc.Objective(objective_id="o1", statement="analyze complexity")]
        c.section_plan = [sc.LessonSectionPlan.create(concept_id=c.identity.concept_id,
                                                      section_type=sc.SectionType.complexity, order=1,
                                                      objective_ids=["o1"], optional=True)]
        self._reject(p, "section_structure")

    def test_section_violates_exclusion(self):   # §4.8
        p = _valid_plan()
        p.intent.exclusions = ["proofs"]
        c = p.curriculum.concepts[1]
        c.split_reason = "spans facets: correctness"
        c.section_plan = [
            sc.LessonSectionPlan.create(concept_id=c.identity.concept_id,
                                        section_type=sc.SectionType.foundation, order=1),
            sc.LessonSectionPlan.create(concept_id=c.identity.concept_id,
                                        section_type=sc.SectionType.proof, order=2),
        ]
        self._reject(p, "exclusions_honoured")

    def test_unresolved_ambiguity_blocks(self):  # §4.9
        p = _valid_plan()
        p.curriculum.decomposition_record.unresolved_ambiguities = ["'expected value' is ambiguous"]
        self._reject(p, "selection_honesty")

    def test_blocking_mapping_conflict_blocks(self):   # §4.9
        p = _valid_plan()
        bayes = p.curriculum.concepts[1]
        p.curriculum.decomposition_record.concept_coverage.append(
            sc.build_concept_mapping(requirement_id="r1", concept_id=bayes.identity.concept_id,
                                     relation=ConceptRelation.direct,
                                     evidence=[SelectionEvidence.create(
                                         method=SelectionMethod.source_span, requirement_id="r1",
                                         target_id=bayes.identity.concept_id,
                                         status=EvidenceStatus.conflicting)]))
        self._reject(p, "selection_honesty")


class ShadowTelemetry(unittest.TestCase):
    def _baseline_from(self, plan) -> sc.ShadowBaseline:
        cur = plan.curriculum
        by_id = {c.identity.concept_id: c for c in cur.concepts}
        return sc.ShadowBaseline(
            concept_keys=[c.identity.canonical_concept_key for c in cur.concepts],
            prereq_ids=[p.id for p in cur.prerequisites],
            concept_order=[by_id[i].identity.canonical_concept_key for i in cur.resolved_concept_order],
            topic_types={c.identity.canonical_concept_key: c.identity.topic_type for c in cur.concepts})

    def test_identical_plan_and_baseline_is_same(self):
        plan = _valid_plan()
        m = sc.shadow_diff(plan, self._baseline_from(plan))
        self.assertEqual(m.diff_class, DiffClass.same)
        self.assertEqual(m.concept_overlap_ratio, 1.0)
        self.assertEqual(m.hard_edge_violation_count, 0)

    def test_added_concept_needs_review_not_regression(self):
        # the current pipeline is not ground truth — a pure addition is reviewable, not a regression (§10).
        plan = _valid_plan()
        base = self._baseline_from(plan)
        base.concept_keys = ["law_of_total_probability"]     # baseline lacked bayes
        base.concept_order = ["law_of_total_probability"]
        m = sc.shadow_diff(plan, base)
        self.assertEqual(m.concept_added_count, 1)
        self.assertEqual(m.diff_class, DiffClass.needs_review)

    def test_hard_edge_violation_is_a_regression(self):
        plan = _valid_plan()
        base = self._baseline_from(plan)
        plan.curriculum.resolved_concept_order = list(reversed(plan.curriculum.resolved_concept_order))
        m = sc.shadow_diff(plan, base)
        self.assertGreater(m.hard_edge_violation_count, 0)
        self.assertEqual(m.diff_class, DiffClass.scope_regression)

    def test_order_pairwise_distance_counts_swaps(self):
        plan = _valid_plan()
        base = self._baseline_from(plan)
        base.concept_order = list(reversed(base.concept_order))
        m = sc.shadow_diff(plan, base)
        self.assertFalse(m.order_exact_match)
        self.assertEqual(m.order_pairwise_distance, 1)


if __name__ == "__main__":
    unittest.main()
