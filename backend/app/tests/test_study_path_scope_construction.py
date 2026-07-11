"""PR3 (plan construction) exit criteria for STUDY_PATH_SCOPE_SPEC Phase 1A. Pure — facets→sections, the
owned dependency ordering, exclusions, objective→section, bridge guard. No grounding, no lessons, no
app-service imports (§1.6, §6.3, §11, §12)."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.core import study_path_scope as sc
from app.core.study_path_scope import (
    CardinalityPolicy, DiscoveredFacet, Facet, Objective, SectionType,
)


def _facet(facet: Facet, name: str, *, objectives=(), topic_type="algorithm_walkthrough") -> DiscoveredFacet:
    return DiscoveredFacet(facet=facet, name=name, topic_type=topic_type, objectives=list(objectives))


class FacetConsolidation(unittest.TestCase):
    def test_quick_review_is_atomic(self):
        concept, sections = sc.consolidate_facets(
            "dijkstra", [_facet(Facet.core, "Dijkstra")], target_depth="overview")
        self.assertEqual(concept.cardinality_policy, CardinalityPolicy.atomic)
        self.assertEqual([s.section_type for s in sections], [SectionType.foundation])
        self.assertIsNone(concept.split_reason)                       # split_reason null iff atomic (§12)

    def test_mastery_incl_implementation_and_correctness_is_multi_section(self):
        concept, sections = sc.consolidate_facets(
            "dijkstra",
            [_facet(Facet.core, "Dijkstra", objectives=[Objective(objective_id="o1", statement="trace it")]),
             _facet(Facet.implementation, "Implementing Dijkstra",
                    objectives=[Objective(objective_id="o2", statement="implement it")]),
             _facet(Facet.correctness, "Why Dijkstra is correct",
                    objectives=[Objective(objective_id="o3", statement="prove greedy choice")])],
            target_depth="mastery")
        self.assertEqual(concept.cardinality_policy, CardinalityPolicy.multi_section)
        types = [s.section_type for s in sections]
        self.assertEqual(types, [SectionType.foundation, SectionType.proof, SectionType.implementation])
        self.assertIsNotNone(concept.split_reason)

    def test_identity_is_the_core_facet_regardless_of_which_facets_appear(self):
        # 'derivation of Bayes' becomes a SECTION of one core concept, not a separate identity (§1.4/§12).
        concept, sections = sc.consolidate_facets(
            "bayes_theorem",
            [_facet(Facet.core, "Bayes' Theorem", topic_type="math_formula_method"),
             _facet(Facet.derivation, "Derivation of Bayes'", topic_type="proof_reasoning")],
            target_depth="mastery")
        self.assertEqual(concept.identity.facet, Facet.core)
        self.assertEqual(concept.identity.canonical_concept_key, "bayes_theorem")
        self.assertIn(SectionType.derivation, [s.section_type for s in sections])

    def test_aliases_are_merged_from_all_facets(self):
        concept, _ = sc.consolidate_facets(
            "bayes_theorem",
            [DiscoveredFacet(facet=Facet.core, name="Bayes' Theorem", aliases=["Bayes' rule"])])
        self.assertIn("Bayes' rule", concept.identity.aliases)


class DepthAndExclusions(unittest.TestCase):
    def test_deep_facets_dropped_below_their_depth(self):
        _, sections = sc.consolidate_facets(
            "dijkstra",
            [_facet(Facet.core, "Dijkstra"), _facet(Facet.derivation, "Derivation")],
            target_depth="working")                                    # derivation needs mastery
        self.assertEqual([s.section_type for s in sections], [SectionType.foundation])

    def test_exclusion_removes_proof_section(self):
        # "derivatives without proofs" → the proof (correctness) section is excluded (§8).
        _, sections = sc.consolidate_facets(
            "derivatives",
            [_facet(Facet.core, "Derivatives"), _facet(Facet.correctness, "Proof of the power rule")],
            target_depth="mastery", exclusions=["proofs"])
        self.assertNotIn(SectionType.proof, [s.section_type for s in sections])

    def test_exclusion_does_not_touch_unrelated_sections(self):
        _, sections = sc.consolidate_facets(
            "dijkstra",
            [_facet(Facet.core, "Dijkstra"), _facet(Facet.implementation, "Implementing Dijkstra")],
            target_depth="mastery", exclusions=["proofs"])
        self.assertIn(SectionType.implementation, [s.section_type for s in sections])


class ObjectiveToSection(unittest.TestCase):
    def test_every_facet_objective_lands_in_a_non_optional_section(self):
        # exit criterion (6): every required objective → a non-optional section.
        concept, sections = sc.consolidate_facets(
            "dijkstra",
            [_facet(Facet.core, "Dijkstra", objectives=[Objective(objective_id="o1", statement="trace")]),
             _facet(Facet.implementation, "Impl",
                    objectives=[Objective(objective_id="o2", statement="implement")])],
            target_depth="mastery")
        owning = {oid: s for s in sections for oid in s.objective_ids}
        for obj in concept.learning_objectives:
            self.assertIn(obj.objective_id, owning)
            self.assertFalse(owning[obj.objective_id].optional,
                             f"required objective {obj.objective_id} owned only by an optional section")

    def test_enrichment_facet_without_objective_is_optional(self):
        _, sections = sc.consolidate_facets(
            "dijkstra",
            [_facet(Facet.core, "Dijkstra"), _facet(Facet.application, "Applications")],
            target_depth="working")
        app = next(s for s in sections if s.section_type == SectionType.application)
        self.assertTrue(app.optional)


class Ordering(unittest.TestCase):
    def test_hard_edge_is_respected(self):
        r = sc.resolve_concept_order(["c_b", "c_a"], edges=[("c_a", "c_b")])
        self.assertEqual(r.order, ["c_a", "c_b"])
        self.assertTrue(r.acyclic)
        self.assertEqual(sc.count_hard_edge_violations(r.order, [("c_a", "c_b")]), 0)

    def test_independent_concepts_follow_mention_order_not_alphabetical(self):
        # "quicksort and mergesort" → goal-mention order, not alphabetical (§8).
        r = sc.resolve_concept_order(["c_mergesort", "c_quicksort"], edges=[],
                                     mention_order=["c_quicksort", "c_mergesort"])
        self.assertEqual(r.order, ["c_quicksort", "c_mergesort"])

    def test_reordering_non_mention_inputs_does_not_change_final_order(self):
        # property (§12): only mention/source/soft/edges decide order — not input list order.
        a = sc.resolve_concept_order(["c_a", "c_b", "c_c"], edges=[("c_a", "c_b")],
                                     mention_order=["c_b", "c_a"])
        b = sc.resolve_concept_order(["c_c", "c_b", "c_a"], edges=[("c_a", "c_b")],
                                     mention_order=["c_b", "c_a"])
        self.assertEqual(a.order, b.order)

    def test_stable_id_is_the_final_tiebreak(self):
        r = sc.resolve_concept_order(["c_z", "c_a", "c_m"], edges=[])
        self.assertEqual(r.order, ["c_a", "c_m", "c_z"])

    def test_cycle_is_reported_never_auto_broken(self):
        r = sc.resolve_concept_order(["c_a", "c_b"], edges=[("c_a", "c_b"), ("c_b", "c_a")])
        self.assertFalse(r.acyclic)
        self.assertEqual(set(r.cyclic), {"c_a", "c_b"})

    def test_every_acyclic_order_has_zero_hard_edge_violations(self):
        # property (§12): a well-ordered plan never violates a hard edge.
        ids = ["c_a", "c_b", "c_c", "c_d"]
        edges = [("c_a", "c_c"), ("c_b", "c_c"), ("c_c", "c_d")]
        r = sc.resolve_concept_order(ids, edges=edges, mention_order=["c_b", "c_a"])
        self.assertTrue(r.acyclic)
        self.assertEqual(sc.count_hard_edge_violations(r.order, edges), 0)

    def test_hard_edges_from_concepts_builds_prereq_edges(self):
        cid = sc.ConceptIdentity.create(name="B", topic_type="t", canonical_concept_key="b")
        pid = sc.ConceptIdentity.create(name="A", topic_type="t", canonical_concept_key="a")
        concepts = [sc.Concept(identity=pid),
                    sc.Concept(identity=cid, prerequisite_concept_ids=[pid.concept_id])]
        edges = sc.hard_edges_from_concepts(concepts)
        r = sc.resolve_concept_order([c.identity.concept_id for c in concepts], edges=edges)
        self.assertEqual(r.order, [pid.concept_id, cid.concept_id])


class BridgeGuard(unittest.TestCase):
    def test_all_five_conditions_required(self):
        base = dict(dependency_evidenced=True, necessary_for_required=True, already_prereq=False,
                    depth_permitted=True, minimal=True)
        self.assertTrue(sc.bridge_insertion_allowed(**base))
        self.assertFalse(sc.bridge_insertion_allowed(**{**base, "dependency_evidenced": False}))
        self.assertFalse(sc.bridge_insertion_allowed(**{**base, "necessary_for_required": False}))
        self.assertFalse(sc.bridge_insertion_allowed(**{**base, "already_prereq": True}))
        self.assertFalse(sc.bridge_insertion_allowed(**{**base, "depth_permitted": False}))
        self.assertFalse(sc.bridge_insertion_allowed(**{**base, "minimal": False}))


if __name__ == "__main__":
    unittest.main()
