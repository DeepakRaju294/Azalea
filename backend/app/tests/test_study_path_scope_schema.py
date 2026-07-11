"""PR1 (schema + identity) exit criteria for STUDY_PATH_SCOPE_SPEC Phase 1A. Pure schema — no grounding,
no lessons, no app-service imports. These lock the identity/serialization guarantees everything else rests on."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.core import study_path_scope as sc
from app.core.study_path_scope import (
    CardinalityPolicy, ConceptIdentity, Facet, LessonSectionPlan, SectionType, StudyPathScopePlan,
)


def _plan() -> StudyPathScopePlan:
    tp = ConceptIdentity.create(name="Law of Total Probability", topic_type="math_formula_method",
                                canonical_concept_key="law_of_total_probability")
    bayes = ConceptIdentity.create(name="Bayes' Theorem", topic_type="math_formula_method",
                                   canonical_concept_key="bayes_theorem")
    return StudyPathScopePlan(
        identity=sc.ScopeIdentity(scope_id=sc.scope_id_for("total probability and bayes", "math")),
        intent=sc.ScopeIntent(goal="total probability and bayes",
                              goal_requirements=[sc.GoalRequirement(requirement_id="r1", description="bayes")]),
        classification=sc.Classification(domain="math"),
        curriculum=sc.CurriculumGraph(
            prerequisites=[sc.Prereq(id="cond_prob", name="conditional probability",
                                     anchor="if P(A|B) is new, review it first")],
            concepts=[
                sc.Concept(identity=tp, planned_grounding=sc.PlannedGrounding(grammar=sc.Grammar.formula)),
                sc.Concept(identity=bayes, prerequisite_concept_ids=[tp.concept_id],
                           planned_grounding=sc.PlannedGrounding(grammar=sc.Grammar.formula)),
            ],
            resolved_concept_order=[tp.concept_id, bayes.concept_id],
        ),
    )


class SerializationIdentity(unittest.TestCase):
    def test_round_trip_is_lossless(self):
        p = _plan()
        again = StudyPathScopePlan.from_json(p.to_json())
        self.assertEqual(again.model_dump(), p.model_dump())      # exit criterion (2): serialize↔deserialize identical
        self.assertEqual(again.to_json(), p.to_json())

    def test_rebuild_is_deterministic(self):
        self.assertEqual(_plan().to_json(), _plan().to_json())    # exit criterion (3): same input → same bytes


class ConceptIdentityRules(unittest.TestCase):
    def test_ids_derive_from_canonical_key_not_display_name(self):
        a = ConceptIdentity.create(name="Bayes Rule", topic_type="math_formula_method",
                                   canonical_concept_key="bayes_theorem")
        b = ConceptIdentity.create(name="Bayes' Theorem", topic_type="math_formula_method",
                                   canonical_concept_key="bayes_theorem")
        self.assertEqual(a.concept_id, b.concept_id)             # rename is a no-op for identity
        self.assertEqual(a.topic_id, b.topic_id)

    def test_facets_of_one_concept_get_distinct_ids(self):
        core = ConceptIdentity.create(name="Bayes' Theorem", topic_type="math_formula_method",
                                      canonical_concept_key="bayes_theorem", facet=Facet.core)
        deriv = ConceptIdentity.create(name="Derivation of Bayes'", topic_type="proof_reasoning",
                                       canonical_concept_key="bayes_theorem", facet=Facet.derivation)
        self.assertNotEqual(core.concept_id, deriv.concept_id)   # distinct facets, same canonical key
        self.assertEqual(core.canonical_concept_key, deriv.canonical_concept_key)

    def test_key_falls_back_to_slug_when_absent(self):
        c = ConceptIdentity.create(name="Completing The Square", topic_type="math_formula_method")
        self.assertEqual(c.canonical_concept_key, "completing_the_square")


class DerivedFields(unittest.TestCase):
    def test_cardinality_policy_is_derived_from_section_count(self):
        cid = ConceptIdentity.create(name="Dijkstra", topic_type="algorithm_walkthrough",
                                     canonical_concept_key="dijkstra")
        atomic = sc.Concept(identity=cid)
        self.assertEqual(atomic.cardinality_policy, CardinalityPolicy.atomic)
        multi = sc.Concept(identity=cid, section_plan=[
            LessonSectionPlan.create(concept_id=cid.concept_id, section_type=SectionType.walkthrough, order=1),
            LessonSectionPlan.create(concept_id=cid.concept_id, section_type=SectionType.complexity, order=2),
        ])
        self.assertEqual(multi.cardinality_policy, CardinalityPolicy.multi_section)

    def test_record_id_is_stable_and_semantic(self):
        a = sc.record_id("mapping", "scope1", "r1", "concept", "c_bayes__core", "direct")
        b = sc.record_id("mapping", "scope1", "r1", "concept", "c_bayes__core", "direct")
        self.assertEqual(a, b)                                   # deterministic from semantic parts
        self.assertNotEqual(a, sc.record_id("mapping", "scope1", "r2", "concept", "c_bayes__core", "direct"))


class PackagePurity(unittest.TestCase):
    def test_package_pulls_in_no_app_services(self):
        # Phase-1A guardrail: importing the schema package must not load app services/routes (no .env/LLM
        # contamination). Checked in a FRESH interpreter so a full-suite run can't mask it.
        import subprocess
        import sys
        code = ("import app.core.study_path_scope, sys;"
                "leaked=[m for m in sys.modules if m.startswith('app.services') or m.startswith('app.api')];"
                "print(';'.join(leaked))")
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                             env={**os.environ, "OPENAI_API_KEY": "dummy"})
        self.assertEqual(out.stdout.strip(), "", f"scope package leaked heavy imports: {out.stdout.strip()}")


if __name__ == "__main__":
    unittest.main()
