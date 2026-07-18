"""The invariant-#2 HUMAN-LABELED pair set (STUDY_PATH_SCOPE_PLAN_SKETCH §4 + §9) — the eight hard pairs that
decide semantic delta-distinctness thresholds, plus the failure-grounded TCP fixtures (F1 duplicate topics /
F2 foundation-leak) and canonicalization-stability baselines.

Labels are DATA (`LABELED_PAIRS`) so the Phase-0 threshold machinery can consume them; each test then asserts
what the deterministic layer already guarantees today. Two fixtures intentionally document the CANONICALIZATION
GAP (the model inventing synonym keys defeats key-based dedup): they assert current behavior AND carry the human
label, so Phase-0 false-merge/false-split rates are measured against the label, not against shipped behavior.
No LLM calls; pure build_plan.
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.core import study_path_scope as sc
from app.core.study_path_scope import (
    ConceptDraft, DecompositionInput, Facet, GoalRequirement, PlanningStatus, PrereqDraft, SelectionMethod,
)

# ---------------------------------------------------------------------------------------------------------
# The labeled pair set. `label` is the HUMAN ground truth (merge | keep_separate | ambiguous).
# `deterministic_today` records whether the current key+facet machinery already realizes the label
# (False = realized only once canonicalization assigns the same key — the Phase-0 gap being measured).
# ---------------------------------------------------------------------------------------------------------
LABELED_PAIRS = [
    {"pair_id": "algorithms_vs_mechanisms", "label": "merge", "deterministic_today": True,
     "note": "synonym split of one subject (live F1: TCP 'Algorithms' + 'Mechanisms')"},
    {"pair_id": "intuition_vs_derivation", "label": "merge", "deterministic_today": True,
     "note": "one concept; derivation becomes a SECTION, not a second topic"},
    {"pair_id": "trace_vs_implementation", "label": "merge", "deterministic_today": True,
     "note": "one concept, walkthrough + implementation sections (distinct deltas preserved as sections)"},
    {"pair_id": "formula_vs_application", "label": "merge", "deterministic_today": True,
     "note": "application facet joins the concept as a section"},
    {"pair_id": "definition_vs_operation", "label": "merge", "deterministic_today": True,
     "note": "defining a structure and operating on it are facets of one concept"},
    {"pair_id": "comparison_vs_two_techniques", "label": "keep_separate", "deterministic_today": True,
     "note": "two techniques are two concepts; the comparison is a section/enrichment, never a third subject"},
    {"pair_id": "foundation_vs_prereq", "label": "keep_separate", "deterministic_today": True,
     "note": "prereq stays a prereq (live F2: 'TCP Overview'); prereq ∩ taught = ∅ is a blocking invariant"},
    {"pair_id": "review_vs_duplicate_teaching", "label": "merge", "deterministic_today": True,
     "note": "a second draft of the same (key, facet) is duplicate teaching — consolidated, never two topics"},
    # The canonicalization gap (measured, not yet realized): same subject under INVENTED synonym keys.
    {"pair_id": "synonym_keys_same_subject", "label": "merge", "deterministic_today": False,
     "note": "live F1 raw form: tcp_congestion_{intuition,algorithms,mechanisms} as three keys — key-based "
             "dedup cannot see it; closes via canonicalization (Phase-0 metric: false-split rate)"},
]


def _req(rid, desc="", required=True):
    return GoalRequirement(requirement_id=rid, description=desc or rid, required=required)


def _c(key, name, reqs=(), *, facet=Facet.core, topic_type="science_mechanism", prereq_keys=(),
       method=SelectionMethod.explicit_goal, aliases=()):
    return ConceptDraft(canonical_concept_key=key, name=name, topic_type=topic_type, facet=facet,
                        covers_requirements=list(reqs), prerequisite_keys=list(prereq_keys),
                        selection_method=method, aliases=list(aliases))


def _label(pair_id):
    return next(p for p in LABELED_PAIRS if p["pair_id"] == pair_id)


class LabeledPairTable(unittest.TestCase):
    def test_labels_are_well_formed(self):
        ids = [p["pair_id"] for p in LABELED_PAIRS]
        self.assertEqual(len(ids), len(set(ids)))
        for p in LABELED_PAIRS:
            self.assertIn(p["label"], ("merge", "keep_separate", "ambiguous"))
            self.assertIsInstance(p["deterministic_today"], bool)


class PairAlgorithmsVsMechanisms(unittest.TestCase):
    """Live F1 (canonicalized form): 'TCP Congestion Control Algorithms' + '... Mechanisms' = ONE subject."""

    def test_same_key_synonym_names_consolidate_to_one_concept(self):
        self.assertEqual(_label("algorithms_vs_mechanisms")["label"], "merge")
        plan = sc.build_plan(DecompositionInput(
            goal="learn tcp congestion control", domain="computer_science",
            requirements=[_req("r1", "tcp congestion control")],
            concepts=[_c("tcp_congestion_control", "TCP Congestion Control Algorithms", ["r1"]),
                      _c("tcp_congestion_control", "TCP Congestion Control Mechanisms", (), facet=Facet.method)]))
        self.assertEqual(plan.identity.planning_status, PlanningStatus.structurally_valid)
        self.assertEqual(len(plan.curriculum.concepts), 1)


class PairIntuitionVsDerivation(unittest.TestCase):
    def test_derivation_is_a_section_of_one_concept(self):
        self.assertEqual(_label("intuition_vs_derivation")["label"], "merge")
        plan = sc.build_plan(DecompositionInput(
            goal="bayes theorem", domain="math", target_depth="mastery", requirements=[_req("r1")],
            concepts=[_c("bayes_theorem", "Bayes' Theorem", ["r1"], topic_type="math_formula_method"),
                      _c("bayes_theorem", "Deriving Bayes' Theorem", (), facet=Facet.derivation,
                         topic_type="proof_reasoning")]))
        self.assertEqual(len(plan.curriculum.concepts), 1)
        sections = [s.section_type.value for s in plan.curriculum.concepts[0].section_plan]
        self.assertIn("derivation", sections)


class PairTraceVsImplementation(unittest.TestCase):
    def test_one_concept_with_walkthrough_and_implementation_sections(self):
        # Distinct learning deltas (trace vs implement) are PRESERVED — as sections of one concept, never as
        # two same-subject topics. This is the merge-with-sections resolution of the sketch's hard pair.
        self.assertEqual(_label("trace_vs_implementation")["label"], "merge")
        plan = sc.build_plan(DecompositionInput(
            goal="trace and implement dijkstra", domain="coding", target_depth="mastery",
            requirements=[_req("r1", "dijkstra")],
            concepts=[_c("dijkstra", "Tracing Dijkstra", ["r1"], facet=Facet.method,
                         topic_type="algorithm_walkthrough"),
                      _c("dijkstra", "Implementing Dijkstra", (), facet=Facet.implementation,
                         topic_type="algorithm_walkthrough")]))
        self.assertEqual(len(plan.curriculum.concepts), 1)
        dj = plan.curriculum.concepts[0]
        sections = [s.section_type.value for s in dj.section_plan]
        self.assertIn("walkthrough", sections)
        self.assertIn("implementation", sections)
        self.assertEqual(dj.cardinality_policy, sc.CardinalityPolicy.multi_section)
        self.assertIsNotNone(dj.split_reason)                        # multi-section split is REASONED, not silent


class PairFormulaVsApplication(unittest.TestCase):
    def test_application_facet_joins_the_concept(self):
        self.assertEqual(_label("formula_vs_application")["label"], "merge")
        plan = sc.build_plan(DecompositionInput(
            goal="z-scores", domain="statistics", target_depth="working", requirements=[_req("r1")],
            concepts=[_c("z_score", "The Z-Score Formula", ["r1"], topic_type="math_formula_method"),
                      _c("z_score", "Applying Z-Scores", (), facet=Facet.application,
                         topic_type="problem_solving_application")]))
        self.assertEqual(len(plan.curriculum.concepts), 1)
        sections = [s.section_type.value for s in plan.curriculum.concepts[0].section_plan]
        self.assertIn("application", sections)


class PairDefinitionVsOperation(unittest.TestCase):
    def test_structure_and_its_operation_are_one_concept(self):
        self.assertEqual(_label("definition_vs_operation")["label"], "merge")
        plan = sc.build_plan(DecompositionInput(
            goal="binary search trees", domain="coding", requirements=[_req("r1")],
            concepts=[_c("binary_search_tree", "What a BST Is", ["r1"], topic_type="data_structure_operation"),
                      _c("binary_search_tree", "BST Insertion", (), facet=Facet.method,
                         topic_type="data_structure_operation")]))
        self.assertEqual(len(plan.curriculum.concepts), 1)


class PairComparisonVsTwoTechniques(unittest.TestCase):
    def test_two_techniques_stay_two_concepts(self):
        self.assertEqual(_label("comparison_vs_two_techniques")["label"], "keep_separate")
        plan = sc.build_plan(DecompositionInput(
            goal="compare bfs and dfs", domain="coding",
            requirements=[_req("r_b", "bfs"), _req("r_d", "dfs")],
            concepts=[_c("breadth_first_search", "BFS", ["r_b"], topic_type="algorithm_walkthrough"),
                      _c("depth_first_search", "DFS", ["r_d"], topic_type="algorithm_walkthrough")],
            mention_order=["breadth_first_search", "depth_first_search"]))
        self.assertEqual(plan.identity.planning_status, PlanningStatus.structurally_valid)
        self.assertEqual(len(plan.curriculum.concepts), 2)           # real subjects — never merged


class PairFoundationVsPrereq(unittest.TestCase):
    """Live F2: 'TCP Overview' taught as a topic while being assumed knowledge. prereq ∩ taught = ∅."""

    def test_prereq_form_is_valid(self):
        self.assertEqual(_label("foundation_vs_prereq")["label"], "keep_separate")
        plan = sc.build_plan(DecompositionInput(
            goal="tcp congestion control", domain="computer_science", requirements=[_req("r1")],
            concepts=[_c("tcp_congestion_control", "TCP Congestion Control", ["r1"])],
            prereqs=[PrereqDraft(id="how_tcp_works", name="How TCP Works")]))
        self.assertEqual(plan.identity.planning_status, PlanningStatus.structurally_valid)
        self.assertIn("how_tcp_works", {p.id for p in plan.curriculum.prerequisites})

    def test_same_key_as_both_prereq_and_concept_is_rejected(self):
        # The blocking invariant behind the F2 fix: a concept is EITHER assumed or taught, never both.
        plan = sc.build_plan(DecompositionInput(
            goal="tcp congestion control", domain="computer_science", requirements=[_req("r1")],
            concepts=[_c("tcp_congestion_control", "TCP Congestion Control", ["r1"]),
                      _c("how_tcp_works", "TCP Overview")],
            prereqs=[PrereqDraft(id="how_tcp_works", name="How TCP Works")]))
        self.assertEqual(plan.identity.planning_status, PlanningStatus.rejected)
        self.assertIn("prereq_concept_disjoint", sc.failed_invariants(plan.validation))


class PairReviewVsDuplicateTeaching(unittest.TestCase):
    def test_second_draft_of_same_key_and_facet_consolidates(self):
        self.assertEqual(_label("review_vs_duplicate_teaching")["label"], "merge")
        plan = sc.build_plan(DecompositionInput(
            goal="slow start", domain="computer_science", requirements=[_req("r1")],
            concepts=[_c("slow_start", "Slow Start", ["r1"]),
                      _c("slow_start", "Understanding Slow Start")]))    # same key, same core facet
        self.assertEqual(plan.identity.planning_status, PlanningStatus.structurally_valid)
        self.assertEqual(len(plan.curriculum.concepts), 1)               # duplicate teaching never ships twice


class CanonicalizationGapSynonymKeys(unittest.TestCase):
    """The live F1 RAW form: the model invented tcp_congestion_{intuition,algorithms,mechanisms} as three
    DIFFERENT canonical keys. Key-based dedup cannot see this — by design, the fixture documents the gap the
    Phase-0 canonicalization metrics measure (label=merge, current=keep_separate → a known false split)."""

    def test_current_behavior_documented_as_false_split_baseline(self):
        pair = _label("synonym_keys_same_subject")
        self.assertEqual(pair["label"], "merge")
        self.assertFalse(pair["deterministic_today"])                # the honest gap, in data
        plan = sc.build_plan(DecompositionInput(
            goal="learn tcp congestion control", domain="computer_science",
            requirements=[_req("r1", "tcp congestion control")],
            concepts=[_c("tcp_congestion_intuition", "Introduction to TCP Congestion Control", ["r1"]),
                      _c("tcp_congestion_algorithms", "TCP Congestion Control Algorithms", ()),
                      _c("tcp_congestion_mechanisms", "TCP Congestion Control Mechanisms", ())]))
        # Today: three concepts survive (the false split). When canonicalization closes the gap, this count
        # drops to 1 and THIS assertion must be updated — the test is the baseline, not the aspiration.
        self.assertEqual(len(plan.curriculum.concepts), 3)


class SameGoalStability(unittest.TestCase):
    """§9 same-goal stability: identical decomposition input rebuilds an IDENTICAL plan (ids + order), and a
    display-name change alone never changes identity (rename = no-op on ids)."""

    def _input(self, name="TCP Congestion Control"):
        return DecompositionInput(
            goal="learn tcp congestion control", domain="computer_science",
            requirements=[_req("r1", "tcp congestion control")],
            concepts=[_c("tcp_congestion_control", name, ["r1"]),
                      _c("congestion_window", "The Congestion Window", (), facet=Facet.core,
                         prereq_keys=())],
            prereqs=[PrereqDraft(id="network_protocols", name="Network Protocols")],
            mention_order=["tcp_congestion_control", "congestion_window"])

    def test_rebuild_is_identical(self):
        a, b = sc.build_plan(self._input()), sc.build_plan(self._input())
        self.assertEqual([c.identity.concept_id for c in a.curriculum.concepts],
                         [c.identity.concept_id for c in b.curriculum.concepts])
        self.assertEqual(a.curriculum.resolved_concept_order, b.curriculum.resolved_concept_order)

    def test_rename_does_not_change_identity(self):
        a = sc.build_plan(self._input("TCP Congestion Control"))
        b = sc.build_plan(self._input("Congestion Control in TCP"))   # display-name change only
        self.assertEqual([c.identity.concept_id for c in a.curriculum.concepts],
                         [c.identity.concept_id for c in b.curriculum.concepts])


class PropertyInvariants(unittest.TestCase):
    """The two §12 property checks that close the Phase-1A exit list."""

    def test_facet_consolidation_does_not_change_requirement_coverage(self):
        # Coverage is identical whether a requirement is covered by a lone draft or by one facet of a
        # consolidated multi-facet concept — consolidation must never orphan a requirement.
        lone = sc.build_plan(DecompositionInput(
            goal="dijkstra", domain="coding", requirements=[_req("r1", "dijkstra")],
            concepts=[_c("dijkstra", "Dijkstra", ["r1"], topic_type="algorithm_walkthrough")]))
        merged = sc.build_plan(DecompositionInput(
            goal="dijkstra", domain="coding", target_depth="mastery", requirements=[_req("r1", "dijkstra")],
            concepts=[_c("dijkstra", "Dijkstra", ["r1"], topic_type="algorithm_walkthrough"),
                      _c("dijkstra", "Implementing Dijkstra", (), facet=Facet.implementation,
                         topic_type="algorithm_walkthrough")]))
        for plan in (lone, merged):
            self.assertEqual(plan.identity.planning_status, PlanningStatus.structurally_valid)
            covered = {m.requirement_id for m in plan.curriculum.decomposition_record.concept_coverage}
            self.assertIn("r1", covered)

    def test_every_concept_and_prereq_is_justified_by_an_evidenced_mapping(self):
        plan = sc.build_plan(DecompositionInput(
            goal="bayes theorem", domain="math", requirements=[_req("r1", "bayes")],
            concepts=[_c("bayes_theorem", "Bayes' Theorem", ["r1"],
                         prereq_keys=["law_of_total_probability"], topic_type="math_formula_method"),
                      _c("law_of_total_probability", "Law of Total Probability", (),
                         topic_type="math_formula_method")],
            prereqs=[PrereqDraft(id="conditional_probability", name="Conditional Probability",
                                 covers_requirements=["r1"])]))
        rec = plan.curriculum.decomposition_record
        mapped_concepts = {m.concept_id for m in rec.concept_coverage}
        mapped_prereqs = {m.prereq_id for m in rec.prereq_coverage}
        for m in rec.concept_coverage:                       # every mapping carries evidence
            self.assertTrue(m.evidence)
        for m in rec.prereq_coverage:
            self.assertTrue(m.evidence)
        bayes_id = next(c.identity.concept_id for c in plan.curriculum.concepts
                        if c.identity.canonical_concept_key == "bayes_theorem")
        self.assertIn(bayes_id, mapped_concepts)             # goal concept justified
        self.assertIn("conditional_probability", mapped_prereqs)  # prereq justified


if __name__ == "__main__":
    unittest.main()
