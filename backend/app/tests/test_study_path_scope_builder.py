"""PR5 (plan builder) exit criteria for STUDY_PATH_SCOPE_SPEC Phase 1A. The builder wires PR1–PR4 into one
callable: decomposition input → a facet-consolidated, ordered, evidenced, validated StudyPathScopePlan. Pure —
no grounding, no lessons, no app-service imports. `_bayes_input` is the end-to-end `scope_bayes_total_prob`
fixture (§9)."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.core import study_path_scope as sc
from app.core.study_path_scope import (
    ConceptDraft, DecompositionInput, Facet, PlanningStatus, PrereqDraft, SelectionMethod, StudyPathScopePlan,
)


def _bayes_input() -> DecompositionInput:
    """Goal: learn total probability and Bayes. Two concepts (TP is a prereq of Bayes), conditional
    probability as a background prerequisite, one required requirement, TP mentioned before Bayes."""
    src = sc.ConceptSelectionSource.create(source_id="goal", span="total probability and bayes")
    return DecompositionInput(
        goal="learn total probability and bayes' theorem", domain="math", source_revision="rev1",
        requirements=[sc.GoalRequirement(requirement_id="r_bayes", description="apply Bayes' theorem"),
                      sc.GoalRequirement(requirement_id="r_tp", description="use total probability")],
        selection_sources=[src],
        concepts=[
            ConceptDraft(canonical_concept_key="law_of_total_probability", name="Law of Total Probability",
                         topic_type="math_formula_method", covers_requirements=["r_tp"],
                         bridges_requirements=["r_bayes"], selection_method=SelectionMethod.explicit_goal,
                         evidence_ref=src.selection_source_id),
            ConceptDraft(canonical_concept_key="bayes_theorem", name="Bayes' Theorem",
                         topic_type="math_formula_method", covers_requirements=["r_bayes"],
                         prerequisite_keys=["law_of_total_probability"],
                         selection_method=SelectionMethod.explicit_goal, evidence_ref=src.selection_source_id),
        ],
        prereqs=[PrereqDraft(id="conditional_probability", name="conditional probability",
                             anchor="review P(A|B) first", covers_requirements=["r_bayes"],
                             selection_method=SelectionMethod.source_span, evidence_ref=src.selection_source_id)],
        mention_order=["law_of_total_probability", "bayes_theorem"],
    )


class BuildBayesPath(unittest.TestCase):
    def setUp(self):
        self.plan = sc.build_plan(_bayes_input())

    def test_plan_is_structurally_valid(self):
        self.assertEqual(self.plan.identity.planning_status, PlanningStatus.structurally_valid)
        self.assertEqual(sc.failed_invariants(self.plan.validation), [])

    def test_both_concepts_present_keyed_by_canonical(self):
        keys = {c.identity.canonical_concept_key for c in self.plan.curriculum.concepts}
        self.assertEqual(keys, {"law_of_total_probability", "bayes_theorem"})

    def test_total_probability_ordered_before_bayes(self):
        order = self.plan.curriculum.resolved_concept_order
        by_id = {c.identity.concept_id: c.identity.canonical_concept_key for c in self.plan.curriculum.concepts}
        self.assertEqual([by_id[i] for i in order], ["law_of_total_probability", "bayes_theorem"])

    def test_bayes_has_total_probability_as_prerequisite(self):
        by_key = {c.identity.canonical_concept_key: c for c in self.plan.curriculum.concepts}
        tp_id = by_key["law_of_total_probability"].identity.concept_id
        self.assertIn(tp_id, by_key["bayes_theorem"].prerequisite_concept_ids)

    def test_decomposition_passes_the_exit_gate(self):
        check = sc.check_decomposition(self.plan)
        self.assertTrue(check.ok, f"{check.integrity_issues} / {check.uncovered_requirements}")

    def test_selection_status_is_derived(self):
        by_key = {c.identity.canonical_concept_key: c for c in self.plan.curriculum.concepts}
        # both concepts are explicitly named in the goal → confirmed selection.
        self.assertEqual(by_key["bayes_theorem"].selection_status, sc.SelectionStatus.confirmed)
        self.assertEqual(by_key["law_of_total_probability"].selection_status, sc.SelectionStatus.confirmed)

    def test_prereq_is_not_a_taught_concept(self):
        concept_keys = {c.identity.canonical_concept_key for c in self.plan.curriculum.concepts}
        self.assertNotIn("conditional_probability", concept_keys)
        self.assertIn("conditional_probability", {p.id for p in self.plan.curriculum.prerequisites})

    def test_rebuild_is_deterministic_and_round_trips(self):
        again = sc.build_plan(_bayes_input())
        self.assertEqual(again.to_json(), self.plan.to_json())                       # deterministic
        self.assertEqual(StudyPathScopePlan.from_json(self.plan.to_json()).model_dump(),
                         self.plan.model_dump())                                      # lossless


class BuilderRejects(unittest.TestCase):
    def test_uncovered_requirement_yields_rejected_plan_not_exception(self):
        inp = _bayes_input()
        inp.requirements.append(sc.GoalRequirement(requirement_id="r_orphan", description="never covered"))
        plan = sc.build_plan(inp)      # returned, not raised, so shadow telemetry can record it
        self.assertEqual(plan.identity.planning_status, PlanningStatus.rejected)
        self.assertIn("coverage", sc.failed_invariants(plan.validation))

    def test_facets_consolidate_into_one_concept(self):
        inp = _bayes_input()
        # add a derivation FACET of Bayes at mastery depth → one concept with a derivation section, not a dup.
        inp.target_depth = "mastery"
        inp.concepts.append(ConceptDraft(canonical_concept_key="bayes_theorem", name="Derivation of Bayes'",
                                         topic_type="proof_reasoning", facet=Facet.derivation,
                                         selection_method=SelectionMethod.explicit_goal))
        plan = sc.build_plan(inp)
        bayes = next(c for c in plan.curriculum.concepts
                     if c.identity.canonical_concept_key == "bayes_theorem")
        self.assertEqual(plan.identity.planning_status, PlanningStatus.structurally_valid)
        self.assertGreater(len(bayes.section_plan), 1)                               # derivation became a section
        self.assertEqual(len([c for c in plan.curriculum.concepts
                              if c.identity.canonical_concept_key == "bayes_theorem"]), 1)


if __name__ == "__main__":
    unittest.main()
