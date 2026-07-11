"""PR2 (decomposition + mappings) exit criteria for STUDY_PATH_SCOPE_SPEC Phase 1A. Pure schema + pure
derivation — no grounding, no lessons, no app-service imports. Locks the ONE selection-status function and the
PR2 exit gate: referential integrity + full required-requirement coverage (§1.4, §11, §12)."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.core import study_path_scope as sc
from app.core.study_path_scope import (
    ConceptIdentity, ConceptRelation, EvidenceStatus, MappingHealth, MappingStatus, SelectionEvidence,
    SelectionMethod, SelectionStatus, StudyPathScopePlan,
)


def _ev(method: SelectionMethod, status: EvidenceStatus = EvidenceStatus.supporting,
        ref: str = "") -> SelectionEvidence:
    return SelectionEvidence.create(method=method, requirement_id="r1", target_id="c_x", evidence_ref=ref,
                                    status=status)


class MappingStatusDerivation(unittest.TestCase):
    """SelectionEvidence[] → one mapping status — the strongest supporting method wins; a conflict dominates."""

    def test_strong_method_is_confirmed(self):
        self.assertEqual(sc.derive_mapping_status([_ev(SelectionMethod.explicit_goal)]), MappingStatus.confirmed)
        self.assertEqual(sc.derive_mapping_status([_ev(SelectionMethod.user_confirmed)]), MappingStatus.confirmed)

    def test_source_and_curriculum_are_supported(self):
        self.assertEqual(sc.derive_mapping_status([_ev(SelectionMethod.source_span)]), MappingStatus.supported)
        self.assertEqual(sc.derive_mapping_status([_ev(SelectionMethod.curriculum_graph)]), MappingStatus.supported)

    def test_model_consensus_alone_is_only_ambiguous(self):
        # model inference is a SIGNAL, never enough to confirm/​support selection (§1.4).
        self.assertEqual(sc.derive_mapping_status([_ev(SelectionMethod.model_consensus)]), MappingStatus.ambiguous)

    def test_conflict_dominates_even_with_strong_support(self):
        ev = [_ev(SelectionMethod.explicit_goal), _ev(SelectionMethod.source_span, EvidenceStatus.conflicting)]
        self.assertEqual(sc.derive_mapping_status(ev), MappingStatus.conflicting)

    def test_empty_evidence_is_ambiguous_not_confirmed(self):
        self.assertEqual(sc.derive_mapping_status([]), MappingStatus.ambiguous)

    def test_strongest_of_several_supporting_wins(self):
        ev = [_ev(SelectionMethod.model_consensus), _ev(SelectionMethod.explicit_goal)]
        self.assertEqual(sc.derive_mapping_status(ev), MappingStatus.confirmed)


class ConceptSelectionAggregate(unittest.TestCase):
    """RequirementConceptMapping[] → (selection_status, mapping_health) — two orthogonal signals, exposed
    together (§1.4). This is the single table-tested aggregation function."""

    def _m(self, status: MappingStatus, relation=ConceptRelation.direct):
        return sc.RequirementConceptMapping(mapping_id="m", requirement_id="r1", concept_id="c_x",
                                            relation=relation, status=status)

    def test_no_mappings_is_unsupported_and_clean(self):
        self.assertEqual(sc.aggregate_concept_selection([]), (SelectionStatus.unsupported, MappingHealth.clean))

    def test_strongest_inclusion_justifies_existence(self):
        out = sc.aggregate_concept_selection([self._m(MappingStatus.supported), self._m(MappingStatus.confirmed)])
        self.assertEqual(out, (SelectionStatus.confirmed, MappingHealth.clean))

    def test_confirmed_existence_still_reports_a_warning_from_another_mapping(self):
        # "the strongest inclusion mapping justifies existence, but a blocking/warning mapping still counts."
        out = sc.aggregate_concept_selection([self._m(MappingStatus.confirmed), self._m(MappingStatus.ambiguous)])
        self.assertEqual(out, (SelectionStatus.confirmed, MappingHealth.contains_warning))

    def test_conflict_counts_as_blocking_health_but_does_not_justify_existence(self):
        out = sc.aggregate_concept_selection([self._m(MappingStatus.conflicting)])
        self.assertEqual(out, (SelectionStatus.unsupported, MappingHealth.contains_blocking))

    def test_conflict_health_survives_alongside_a_confirmed_mapping(self):
        out = sc.aggregate_concept_selection([self._m(MappingStatus.confirmed), self._m(MappingStatus.conflicting)])
        self.assertEqual(out, (SelectionStatus.confirmed, MappingHealth.contains_blocking))


def _plan_with_decomposition() -> StudyPathScopePlan:
    """A minimal but referentially-complete plan: one required requirement, one concept, one registered source,
    a direct evidenced concept mapping, and a prereq mapping."""
    tp = ConceptIdentity.create(name="Law of Total Probability", topic_type="math_formula_method",
                                canonical_concept_key="law_of_total_probability")
    bayes = ConceptIdentity.create(name="Bayes' Theorem", topic_type="math_formula_method",
                                   canonical_concept_key="bayes_theorem")
    registry = sc.SelectionSourceRegistry()
    src = sc.ConceptSelectionSource.create(source_id="syllabus", span="Unit 3: Bayes' theorem")
    registry.add(src)

    req = sc.GoalRequirement(requirement_id="r1", description="apply Bayes' theorem")
    concept_map = sc.build_concept_mapping(
        requirement_id="r1", concept_id=bayes.concept_id, relation=ConceptRelation.direct,
        evidence=[SelectionEvidence.create(method=SelectionMethod.explicit_goal, requirement_id="r1",
                                           target_id=bayes.concept_id, evidence_ref=src.selection_source_id)])
    bridge_map = sc.build_concept_mapping(
        requirement_id="r1", concept_id=tp.concept_id, relation=ConceptRelation.bridge,
        evidence=[SelectionEvidence.create(method=SelectionMethod.curriculum_graph, requirement_id="r1",
                                           target_id=tp.concept_id, evidence_ref=src.selection_source_id)])
    prereq_map = sc.build_prereq_mapping(
        requirement_id="r1", prereq_id="cond_prob",
        evidence=[SelectionEvidence.create(method=SelectionMethod.source_span, requirement_id="r1",
                                           target_id="cond_prob", evidence_ref=src.selection_source_id)])

    plan = StudyPathScopePlan(
        identity=sc.ScopeIdentity(scope_id=sc.scope_id_for("bayes", "math")),
        intent=sc.ScopeIntent(goal="apply Bayes' theorem", goal_requirements=[req]),
        classification=sc.Classification(domain="math"),
        selection_sources=registry,
        curriculum=sc.CurriculumGraph(
            prerequisites=[sc.Prereq(id="cond_prob", name="conditional probability")],
            concepts=[sc.Concept(identity=tp), sc.Concept(identity=bayes,
                                                          prerequisite_concept_ids=[tp.concept_id])],
            resolved_concept_order=[tp.concept_id, bayes.concept_id],
            decomposition_record=sc.DecompositionRecord(
                goal_claims=[req], concept_coverage=[concept_map, bridge_map], prereq_coverage=[prereq_map]),
        ),
    )
    return plan


class ReferentialIntegrity(unittest.TestCase):
    def test_complete_plan_passes_the_exit_gate(self):
        check = sc.check_decomposition(_plan_with_decomposition())
        self.assertTrue(check.ok, f"{check.integrity_issues} / {check.uncovered_requirements}")

    def test_deleting_a_source_surfaces_a_dangling_evidence_ref(self):
        plan = _plan_with_decomposition()
        plan.selection_sources.sources.clear()          # §12 property: delete a source → integrity failure
        check = sc.check_decomposition(plan)
        self.assertFalse(check.ok)
        self.assertTrue(any(i.kind == "dangling_evidence_ref" for i in check.integrity_issues))

    def test_mapping_to_a_missing_concept_is_flagged(self):
        plan = _plan_with_decomposition()
        plan.curriculum.decomposition_record.concept_coverage.append(
            sc.build_concept_mapping(requirement_id="r1", concept_id="c_ghost__core",
                                     relation=ConceptRelation.direct))
        issues = sc.check_decomposition(plan).integrity_issues
        self.assertTrue(any(i.kind == "missing_concept" for i in issues))

    def test_mapping_to_a_missing_prereq_is_flagged(self):
        plan = _plan_with_decomposition()
        plan.curriculum.decomposition_record.prereq_coverage.append(
            sc.build_prereq_mapping(requirement_id="r1", prereq_id="ghost_prereq"))
        issues = sc.check_decomposition(plan).integrity_issues
        self.assertTrue(any(i.kind == "missing_prereq" for i in issues))


class RequirementCoverage(unittest.TestCase):
    def test_uncovered_required_requirement_is_reported(self):
        plan = _plan_with_decomposition()
        plan.curriculum.decomposition_record.goal_claims.append(
            sc.GoalRequirement(requirement_id="r2", description="uncovered", required=True))
        check = sc.check_decomposition(plan)
        self.assertIn("r2", check.uncovered_requirements)

    def test_enrichment_alone_does_not_cover_a_requirement(self):
        # enrichment is extra depth; it never discharges a required goal (§1.4).
        plan = _plan_with_decomposition()
        rec = plan.curriculum.decomposition_record
        rec.goal_claims.append(sc.GoalRequirement(requirement_id="r3", description="enrich only"))
        cid = plan.curriculum.concepts[1].identity.concept_id
        rec.concept_coverage.append(sc.build_concept_mapping(
            requirement_id="r3", concept_id=cid, relation=ConceptRelation.enrichment,
            evidence=[_ev(SelectionMethod.explicit_goal)]))
        self.assertIn("r3", sc.check_decomposition(plan).uncovered_requirements)

    def test_optional_requirement_never_blocks_coverage(self):
        plan = _plan_with_decomposition()
        plan.curriculum.decomposition_record.goal_claims.append(
            sc.GoalRequirement(requirement_id="r4", description="nice to have", required=False))
        self.assertNotIn("r4", sc.check_decomposition(plan).uncovered_requirements)


class DerivedFieldOwnership(unittest.TestCase):
    def test_apply_selection_status_is_the_lone_writer(self):
        plan = _plan_with_decomposition()
        sc.apply_selection_status(plan)
        by_key = {c.identity.canonical_concept_key: c for c in plan.curriculum.concepts}
        bayes = by_key["bayes_theorem"]
        self.assertEqual(bayes.selection_status, SelectionStatus.confirmed)   # explicit_goal direct mapping
        self.assertEqual(bayes.mapping_health, MappingHealth.clean)
        tp = by_key["law_of_total_probability"]
        self.assertEqual(tp.selection_status, SelectionStatus.supported)      # curriculum_graph bridge mapping


class Serialization(unittest.TestCase):
    def test_round_trip_with_decomposition_is_lossless(self):
        p = sc.apply_selection_status(_plan_with_decomposition())
        again = StudyPathScopePlan.from_json(p.to_json())
        self.assertEqual(again.model_dump(), p.model_dump())
        self.assertEqual(again.to_json(), p.to_json())

    def test_rebuild_is_deterministic(self):
        self.assertEqual(_plan_with_decomposition().to_json(), _plan_with_decomposition().to_json())


if __name__ == "__main__":
    unittest.main()
