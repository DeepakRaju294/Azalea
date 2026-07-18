"""Structured prerequisites (the durable fix that ends prose-extraction): decomposition emits path_plan.
assumed_prerequisites (clean concept names + glosses); the pipeline lands them on the intro's
assumed_prerequisites (+ a gloss map on decomposition_metadata); the lean generator GROUNDS the prereq card
from that structured list so bullets are clean and each name appears verbatim, which the scanner then turns
into reliable open_study_path links — no prose parsing."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.topic_decomposition_pipeline import (
    _cross_topic_foundations, _is_circular_prereq, _path_assumed_prereqs, _topic_teaches_prereq, _fold_prereq_topics,
    _drop_umbrella_prereqs, _collapse_near_duplicate_topics, generate_decomposed_topics,
)


class NearDuplicateTopicCollapse(unittest.TestCase):
    @staticmethod
    def _t(title, ttype="science_mechanism", scope=None):
        return {"title": title, "topic_type": ttype, "course_type": ttype, "in_scope": scope or []}

    def test_filler_only_title_difference_collapses_and_merges_scope(self):
        # Live failure (TCP path): 'TCP Congestion Control' + 'TCP Congestion Control Mechanisms' — same lesson.
        topics = [self._t("TCP Congestion Control Mechanisms", scope=["slow start", "fast recovery"]),
                  self._t("TCP Congestion Control", scope=["window size", "RTT"])]
        _collapse_near_duplicate_topics(topics)
        self.assertEqual([t["title"] for t in topics], ["TCP Congestion Control Mechanisms"])
        self.assertEqual(topics[0]["in_scope"], ["slow start", "fast recovery", "window size", "RTT"])

    def test_real_distinguishing_word_is_not_collapsed(self):
        # 'Trees' is a real concept, not filler — these stay two topics even at the same type.
        topics = [self._t("Binary Search", "algorithm_walkthrough"),
                  self._t("Binary Search Trees", "algorithm_walkthrough")]
        _collapse_near_duplicate_topics(topics)
        self.assertEqual(len(topics), 2)

    def test_different_types_never_collapse(self):
        topics = [self._t("Binary Search", "algorithm_walkthrough"),
                  self._t("Binary Search", "data_structure_operation")]
        _collapse_near_duplicate_topics(topics)
        self.assertEqual(len(topics), 2)

    def test_distinct_subjects_untouched(self):
        topics = [self._t("Slow Start"), self._t("Fast Retransmit")]
        _collapse_near_duplicate_topics(topics)
        self.assertEqual(len(topics), 2)


class UmbrellaPrereqGuard(unittest.TestCase):
    def test_broad_field_dropped_when_specific_remains(self):
        # Live failure (z-score path): both 'Statistics' AND 'mean and median' — the umbrella just restates
        # the specific concept, which reads as redundant.
        self.assertEqual(_drop_umbrella_prereqs(["Statistics", "mean and median"]), ["mean and median"])
        self.assertEqual(_drop_umbrella_prereqs(["Mathematics", "linear equations"]), ["linear equations"])

    def test_umbrella_kept_when_it_is_the_only_prereq(self):
        self.assertEqual(_drop_umbrella_prereqs(["Statistics"]), ["Statistics"])

    def test_specific_prereqs_untouched(self):
        self.assertEqual(_drop_umbrella_prereqs(["graph theory", "priority queues"]),
                         ["graph theory", "priority queues"])
from app.services.lean_lesson_generator import (
    _assumed_prereq_glosses, _emit_prereq_interactive_links, _ground_prereq_card,
    _relocate_prereq_defs_from_key_terms,
)

_FLAG = "AZALEA_PREREQ_LINKS"

_GOAL = "learn bayes theorem"
_RESP = {
    "path_plan": {
        "end_capability": "Apply Bayes' theorem.",
        "end_capability_actions": ["apply"],
        "assumed_prerequisites": [
            {"name": "conditional probability", "gloss": "the probability of one event given another occurred"},
            {"name": "sample space", "gloss": "the set of all possible outcomes"},
            {"name": "bayes theorem", "gloss": "the goal concept — must NOT be demoted to a prereq"},
        ],
        "required_capabilities": [
            {"capability_id": "apply_bayes", "description": "Apply Bayes.", "prerequisite_capability_ids": [],
             "satisfies_end_actions": ["apply"], "ownership_mode": "standalone", "owner_topic_id": None,
             "basis": "goal"},
        ],
    },
    "topics": [
        {"topic_id": "t_bayes", "capability_id": "apply_bayes", "subject_key": "bayes_theorem",
         "primary_action": "apply", "content_role": "application", "topic_type": "math_formula_method",
         "title": "Bayes' Theorem", "unit_title": "Core", "purpose": "p", "in_scope": ["posterior"],
         "practice_target": "apply Bayes", "practice_format": "short_answer",
         "practice_evidence_type": "solve_numeric", "expected_output": "posterior", "basis": "goal"},
        {"topic_id": "t_upd", "capability_id": "apply_bayes", "subject_key": "belief_update",
         "primary_action": "apply", "content_role": "application", "topic_type": "math_formula_method",
         "title": "Updating Beliefs", "unit_title": "Core", "purpose": "p", "in_scope": ["update"],
         "practice_target": "update", "practice_format": "short_answer",
         "practice_evidence_type": "solve_numeric", "expected_output": "posterior", "basis": "goal"},
    ],
}


class _Topic:
    def __init__(self, tid, title, order, prereqs=None, glosses=None, requirements=None, ctype="concept"):
        self.id, self.title, self.order_index = tid, title, order
        self.course_type, self.topic_type = ctype, None
        self.assumed_prerequisites = prereqs or []
        self.decomposition_metadata = {"assumed_prerequisite_glosses": glosses or {},
                                       "assumed_prerequisite_requirements": requirements or {}}
        self.study_path = None


class _Path:
    def __init__(self, topics, domain="math"):
        self.topics, self.domain = topics, domain
        for t in topics:
            t.study_path = self


class ParseStructuredPrereqs(unittest.TestCase):
    def test_dicts_yield_names_and_glosses(self):
        names, glosses, reqs = _path_assumed_prereqs(
            {"assumed_prerequisites": [{"name": "vectors", "gloss": "arrows with magnitude and direction",
                                        "required_knowledge": "add vectors and compute dot products"}]})
        self.assertEqual(names, ["vectors"])
        self.assertEqual(glosses["vectors"], "arrows with magnitude and direction")
        self.assertEqual(reqs["vectors"], "add vectors and compute dot products")

    def test_plain_strings_and_dedup(self):
        names, glosses, reqs = _path_assumed_prereqs(
            {"assumed_prerequisites": ["Vectors", "vectors", {"name": "Sets"}]})
        self.assertEqual(names, ["Vectors", "Sets"])   # case-insensitive dedup, order kept
        self.assertEqual(glosses, {})
        self.assertEqual(reqs, {})

    def test_missing_field_is_empty(self):
        self.assertEqual(_path_assumed_prereqs({}), ([], {}, {}))

    def test_caps_at_four_prereqs(self):
        # Prereqs are FEW by contract; a flooded list keeps only the leading (most essential) entries.
        many = [{"name": f"concept {i}"} for i in range(8)]
        names, _, _ = _path_assumed_prereqs({"assumed_prerequisites": many})
        self.assertEqual(len(names), 4)


class PipelineEmitsStructuredPrereqs(unittest.TestCase):
    def test_intro_carries_names_and_glosses_excluding_goal_concept(self):
        topics = generate_decomposed_topics(_GOAL, "src", model_fn=lambda p: _RESP)
        intro = next(t for t in topics if t["course_type"] == "study_path_introduction")
        ap = intro.get("assumed_prerequisites") or []
        self.assertIn("conditional probability", ap)
        self.assertIn("sample space", ap)
        self.assertNotIn("bayes theorem", [a.lower() for a in ap])   # goal concept is NOT a prereq
        glosses = (intro.get("decomposition_metadata") or {}).get("assumed_prerequisite_glosses") or {}
        self.assertEqual(glosses["conditional probability"],
                         "the probability of one event given another occurred")


class GroundPrereqCard(unittest.TestCase):
    def test_rebuilds_prereq_card_bullets_from_structured_list(self):
        intro = _Topic("i", "Introduction to Bayes", 0,
                       prereqs=["conditional probability", "sample space"],
                       glosses={"conditional probability": "prob. of A given B",
                                "sample space": "all outcomes"},
                       ctype="study_path_introduction")
        cards = [{"card_type": "prerequisites", "blueprint_key": "prerequisites", "title": "Prerequisites",
                  "points": ["some vague model prose that does not name the concepts cleanly"]}]
        out = _ground_prereq_card(cards, intro)
        pts = out[0]["points"]
        # main bullet = bare topic name (the link anchor); the gloss is its sub-bullet
        self.assertEqual(pts, ["conditional probability", "  - What it is: prob. of A given B",
                               "sample space", "  - What it is: all outcomes"])

    def test_mints_prereq_card_when_none_present(self):
        intro = _Topic("i", "Intro", 0, prereqs=["vectors"], ctype="study_path_introduction")
        cards = [{"card_type": "background", "points": ["overview"]},
                 {"card_type": "roadmap", "blueprint_key": "roadmap", "points": ["topic 1"]}]
        out = _ground_prereq_card(cards, intro)
        keys = [c.get("blueprint_key") or c.get("card_type") for c in out]
        self.assertIn("prerequisites", keys)
        prereq = next(c for c in out if (c.get("blueprint_key") or c.get("card_type")) == "prerequisites")
        self.assertEqual(prereq["points"], ["vectors"])            # no gloss → bare name
        self.assertLess(keys.index("prerequisites"), keys.index("roadmap"))   # before the roadmap

    def test_noop_off_intro(self):
        body = _Topic("t1", "Bayes", 1, prereqs=["conditional probability"])
        cards = [{"card_type": "prerequisites", "points": ["x"]}]
        self.assertEqual(_ground_prereq_card(cards, body)[0]["points"], ["x"])

    def test_noop_when_no_structured_prereqs(self):
        intro = _Topic("i", "Intro", 0, ctype="study_path_introduction")
        cards = [{"card_type": "prerequisites", "points": ["model prose"]}]
        self.assertEqual(_ground_prereq_card(cards, intro)[0]["points"], ["model prose"])

    def test_grounded_names_become_open_study_path_links(self):
        os.environ[_FLAG] = "1"
        try:
            intro = _Topic("i", "Introduction to Bayes", 0,
                           prereqs=["conditional probability"],
                           glosses={"conditional probability": "prob. of A given B"},
                           ctype="study_path_introduction")
            _Path([intro, _Topic("t1", "Bayes' Theorem", 1)])
            cards = [{"card_type": "prerequisites", "blueprint_key": "prerequisites", "title": "Prerequisites",
                      "points": ["prose"]}]
            grounded = _ground_prereq_card(cards, intro)
            out = _emit_prereq_interactive_links(grounded, intro)
            links = out[0]["interactive_links"]
            self.assertEqual(len(links), 1)
            self.assertEqual(links[0]["action"], "open_study_path")
            self.assertEqual(links[0]["text"], "conditional probability")
            self.assertEqual(links[0]["explanation"], "")   # popup is a bare CTA; gloss lives on the card bullet
        finally:
            os.environ.pop(_FLAG, None)


_CA_GOAL = "Want to learn about combinatorial analysis"


class TaughtPrereqGuard(unittest.TestCase):
    def test_topic_teaching_a_declared_prereq_is_detected(self):
        # Live failure (Dijkstra path): 'Graph Representation' was BOTH a declared prereq AND the taught topic
        # 'Implementing Graph Representation'. A concept is EITHER a prereq OR a topic — keep the prereq, fold
        # the topic. _topic_teaches_prereq flags the topic that duplicates a declared prereq.
        prereqs = ["graph theory", "Graph Representation"]
        graph_rep = {"title": "Implementing Graph Representation", "subject_key": "graph_representation"}
        dijkstra = {"title": "Dijkstra's Algorithm Walkthrough", "subject_key": "dijkstra_walk"}
        self.assertTrue(_topic_teaches_prereq(graph_rep, prereqs))
        self.assertFalse(_topic_teaches_prereq(dijkstra, prereqs))    # not a declared prereq -> stays

    def test_fold_removes_prereq_topic_but_keeps_last_teaching_topic(self):
        topics = [{"topic_type": "study_path_introduction", "title": "Intro"},
                  {"title": "Implementing Graph Representation", "subject_key": "graph_representation"},
                  {"title": "Implementing Dijkstra's Algorithm", "subject_key": "dijkstra"}]
        removed = _fold_prereq_topics(topics, ["Graph Representation"], "learn dijkstra's algorithm")
        self.assertEqual(removed, ["Implementing Graph Representation"])
        titles = [t.get("title") for t in topics]
        self.assertNotIn("Implementing Graph Representation", titles)   # folded -> becomes a prereq link
        self.assertIn("Implementing Dijkstra's Algorithm", titles)     # the real subject stays

    def test_end_to_end_prereq_kept_topic_folded(self):
        resp = {
            "path_plan": {"end_capability": "x", "end_capability_actions": ["implement"],
                          "assumed_prerequisites": [
                              {"name": "graph theory", "gloss": "study of graphs", "required_knowledge": "read a graph"},
                              {"name": "Graph Representation", "gloss": "adjacency lists", "required_knowledge": "build one"}],
                          "required_capabilities": [
                              {"capability_id": "c1", "description": "d", "prerequisite_capability_ids": [],
                               "satisfies_end_actions": ["implement"], "ownership_mode": "standalone",
                               "owner_topic_id": None, "basis": "goal"}]},
            "topics": [
                {"topic_id": "t1", "capability_id": "c1", "subject_key": "graph_representation",
                 "primary_action": "implement", "content_role": "coding", "topic_type": "coding_implementation",
                 "title": "Implementing Graph Representation", "purpose": "p", "in_scope": ["adjacency"],
                 "practice_target": "x", "practice_format": "code", "practice_evidence_type": "code",
                 "expected_output": "graph", "basis": "goal"},
                {"topic_id": "t2", "capability_id": "c1", "subject_key": "dijkstra",
                 "primary_action": "implement", "content_role": "coding", "topic_type": "coding_implementation",
                 "title": "Implementing Dijkstra's Algorithm", "purpose": "p", "in_scope": ["shortest path"],
                 "practice_target": "x", "practice_format": "code", "practice_evidence_type": "code",
                 "expected_output": "paths", "basis": "goal"},
            ],
        }
        topics = generate_decomposed_topics("learn dijkstra's algorithm", "src", model_fn=lambda p: resp)
        intro = next(t for t in topics if t["course_type"] == "study_path_introduction")
        ap = [a.lower() for a in (intro.get("assumed_prerequisites") or [])]
        self.assertIn("graph theory", ap)                    # external prereq kept (gets a link)
        self.assertIn("graph representation", ap)             # declared prereq kept (gets a link)
        titles = [t["title"] for t in topics]
        self.assertNotIn("Implementing Graph Representation", titles)   # redundant topic folded away
        self.assertIn("Implementing Dijkstra's Algorithm", titles)     # the real subject stays


class CircularPrereqGuard(unittest.TestCase):
    def test_goal_subject_in_generic_wrapping_is_circular(self):
        # Live failure: the path collapsed because 'Combinatorial Principles' became a prereq whose linked
        # study path would teach the very subject the learner asked for.
        for name in ("Combinatorial Principles", "combinatorics basics", "fundamentals of combinatorial analysis"):
            self.assertTrue(_is_circular_prereq(name, _CA_GOAL), name)

    def test_all_generic_name_is_circular(self):
        self.assertTrue(_is_circular_prereq("basic fundamentals", _CA_GOAL))   # names no outside subject

    def test_different_subject_prereqs_pass(self):
        self.assertFalse(_is_circular_prereq("basic probability", _CA_GOAL))
        self.assertFalse(_is_circular_prereq("binary search trees", "learn BST traversal algorithms"))
        self.assertFalse(_is_circular_prereq("derivatives", "learn integration by parts"))

    def test_llm_emitted_circular_prereq_is_dropped(self):
        resp = {
            "path_plan": {
                "end_capability": "x", "end_capability_actions": ["apply"],
                "assumed_prerequisites": [
                    {"name": "Combinatorial Principles", "gloss": "g", "required_knowledge": "r"},
                    {"name": "basic probability", "gloss": "chance of events", "required_knowledge": "compute simple probabilities"},
                ],
                "required_capabilities": [
                    {"capability_id": "c1", "description": "d", "prerequisite_capability_ids": [],
                     "satisfies_end_actions": ["apply"], "ownership_mode": "standalone",
                     "owner_topic_id": None, "basis": "goal"}],
            },
            "topics": [
                {"topic_id": "t1", "capability_id": "c1", "subject_key": "binomial_theorem",
                 "primary_action": "apply", "content_role": "math_formula_method",
                 "topic_type": "math_formula_method", "title": "Binomial Theorem", "unit_title": "Core",
                 "purpose": "p", "in_scope": ["expansion"], "practice_target": "x",
                 "practice_format": "short_answer", "practice_evidence_type": "solve_numeric",
                 "expected_output": "poly", "basis": "goal"},
                {"topic_id": "t2", "capability_id": "c1", "subject_key": "combinatorial_probability",
                 "primary_action": "apply", "content_role": "application",
                 "topic_type": "problem_solving_application", "title": "Applying Combinatorial Analysis",
                 "unit_title": "Core", "purpose": "p", "in_scope": ["applications"], "practice_target": "x",
                 "practice_format": "short_answer", "practice_evidence_type": "solve_numeric",
                 "expected_output": "count", "basis": "goal"},
            ],
        }
        topics = generate_decomposed_topics(_CA_GOAL, "src", model_fn=lambda p: resp)
        intro = next(t for t in topics if t["course_type"] == "study_path_introduction")
        ap = [a.lower() for a in (intro.get("assumed_prerequisites") or [])]
        self.assertNotIn("combinatorial principles", ap)     # circular → dropped
        self.assertIn("basic probability", ap)               # real outside-subject prereq kept

    def test_circular_foundation_topic_stays_taught_not_folded(self):
        resp = {
            "path_plan": {"end_capability": "x", "end_capability_actions": ["apply"],
                          "required_capabilities": [
                              {"capability_id": "c1", "description": "d", "prerequisite_capability_ids": [],
                               "satisfies_end_actions": ["apply"], "ownership_mode": "standalone",
                               "owner_topic_id": None, "basis": "goal"}]},
            "topics": [
                {"topic_id": "t0", "capability_id": "c1", "subject_key": "combinatorial_principles",
                 "primary_action": "understand", "content_role": "foundation",
                 "topic_type": "math_formula_method", "title": "Combinatorial Principles",
                 "unit_title": "Foundations", "purpose": "p", "in_scope": ["counting"],
                 "practice_target": "x", "practice_format": "short_answer",
                 "practice_evidence_type": "solve_numeric", "expected_output": "count", "basis": "goal"},
                {"topic_id": "t1", "capability_id": "c1", "subject_key": "binomial_theorem",
                 "primary_action": "apply", "content_role": "math_formula_method",
                 "topic_type": "math_formula_method", "title": "Binomial Theorem", "unit_title": "Core",
                 "purpose": "p", "in_scope": ["expansion"], "practice_target": "x",
                 "practice_format": "short_answer", "practice_evidence_type": "solve_numeric",
                 "expected_output": "poly", "basis": "goal"},
            ],
        }
        topics = generate_decomposed_topics(_CA_GOAL, "src", model_fn=lambda p: resp)
        titles = [t["title"] for t in topics]
        self.assertIn("Combinatorial Principles", titles)    # NOT folded away — stays a taught topic
        intro = next(t for t in topics if t["course_type"] == "study_path_introduction")
        ap = [a.lower() for a in (intro.get("assumed_prerequisites") or [])]
        self.assertNotIn("combinatorial principles", ap)


class CrossTopicFoundations(unittest.TestCase):
    def test_shared_in_scope_concept_taught_by_none_is_a_prereq(self):
        teaching = [
            {"subject_key": "law_total_probability", "title": "Law of Total Probability",
             "in_scope": ["conditional probability", "events", "total probability"]},
            {"subject_key": "bayes_theorem", "title": "Bayes' Theorem",
             "in_scope": ["conditional probability", "posterior probability"]},
        ]
        out = _cross_topic_foundations(teaching, "learn bayes theorem")
        self.assertIn("conditional probability", out)     # in both, taught by none
        self.assertNotIn("events", out)                   # only one topic
        self.assertNotIn("total probability", out)        # it IS a topic subject/title
        self.assertNotIn("posterior probability", out)    # only one topic

    def test_goal_named_shared_concept_not_promoted(self):
        teaching = [
            {"subject_key": "a", "title": "A", "in_scope": ["conditional probability"]},
            {"subject_key": "b", "title": "B", "in_scope": ["conditional probability"]},
        ]
        self.assertEqual(_cross_topic_foundations(teaching, "learn conditional probability well"), [])


class RelocatePrereqDefs(unittest.TestCase):
    def test_harvests_gloss_and_removes_term_from_key_terms(self):
        cards = [
            {"card_type": "prerequisites", "title": "Prerequisites", "points": ["placeholder"]},
            {"card_type": "definition", "title": "Key Terms", "points": [
                "Conditional Probability",
                "  - The probability of an event occurring given that another has occurred",
                "Prior Probability",
                "  - The initial estimate before evidence",
            ]},
        ]
        harvested = _relocate_prereq_defs_from_key_terms(cards, ["conditional probability"])
        self.assertEqual(harvested["conditional probability"],
                         "The probability of an event occurring given that another has occurred")
        kt = cards[1]["points"]
        self.assertNotIn("Conditional Probability", kt)                  # term removed from key terms
        self.assertNotIn("  - The probability of an event occurring given that another has occurred", kt)
        self.assertIn("Prior Probability", kt)                          # untouched term stays

    def test_inline_colon_definition_form(self):
        cards = [{"card_type": "components_terms", "points": [
            "Sample space: the set of all possible outcomes", "Event: a subset of outcomes"]}]
        harvested = _relocate_prereq_defs_from_key_terms(cards, ["sample space"])
        self.assertEqual(harvested["sample space"], "the set of all possible outcomes")
        self.assertNotIn("Sample space: the set of all possible outcomes", cards[0]["points"])

    def test_noop_when_no_match(self):
        cards = [{"card_type": "definition", "points": ["Vectors", "  - arrows"]}]
        self.assertEqual(_relocate_prereq_defs_from_key_terms(cards, ["matrices"]), {})
        self.assertEqual(cards[0]["points"], ["Vectors", "  - arrows"])


class GroundHarvestsGlossFromKeyTerms(unittest.TestCase):
    def test_prereq_without_decomp_gloss_pulls_it_from_key_terms(self):
        intro = _Topic("i", "Intro", 0, prereqs=["conditional probability"],
                       ctype="study_path_introduction")   # no decomposition gloss for it
        cards = [
            {"card_type": "prerequisites", "title": "Prerequisites", "points": ["x"]},
            {"card_type": "definition", "title": "Key Terms", "points": [
                "Conditional Probability", "  - probability of A given B has occurred"]},
        ]
        out = _ground_prereq_card(cards, intro)
        prereq = next(c for c in out if (c.get("blueprint_key") or c.get("card_type")) in ("prerequisites",))
        self.assertEqual(prereq["points"], ["conditional probability",
                                            "  - What it is: probability of A given B has occurred"])
        kt = next(c for c in out if c["card_type"] == "definition")["points"]
        self.assertNotIn("Conditional Probability", kt)                 # relocated out of key terms


class PrereqBriefBackstop(unittest.TestCase):
    def test_missing_briefs_filled_by_llm_backstop(self):
        # Live failure: a fold-derived prereq ('Counting Principles') reached the intro with NO gloss and NO
        # required_knowledge → the card showed just the bare name. The backstop must fill both sub-bullets.
        intro = _Topic("i", "Intro", 0, prereqs=["Counting Principles"], ctype="study_path_introduction")
        cards = [{"card_type": "prerequisites", "blueprint_key": "prerequisites",
                  "title": "Prerequisites", "points": ["prose"]}]

        def _briefs(names, goal):
            self.assertEqual(names, ["Counting Principles"])
            return [{"name": "Counting Principles",
                     "gloss": "rules for counting outcomes of combined choices",
                     "required_knowledge": "apply the addition and multiplication rules to count outcomes"}]

        out = _ground_prereq_card(cards, intro, brief_fn=_briefs)
        self.assertEqual(out[0]["points"], [
            "Counting Principles",
            "  - What it is: rules for counting outcomes of combined choices",
            "  - What to learn: apply the addition and multiplication rules to count outcomes"])

    def test_backstop_not_called_when_briefs_present(self):
        intro = _Topic("i", "Intro", 0, prereqs=["vectors"],
                       glosses={"vectors": "arrows"}, requirements={"vectors": "add them"},
                       ctype="study_path_introduction")
        cards = [{"card_type": "prerequisites", "blueprint_key": "prerequisites",
                  "title": "Prerequisites", "points": ["prose"]}]
        called = {"n": 0}

        def _briefs(names, goal):
            called["n"] += 1
            return []

        _ground_prereq_card(cards, intro, brief_fn=_briefs)
        self.assertEqual(called["n"], 0)

    def test_backstop_failure_still_renders_names(self):
        intro = _Topic("i", "Intro", 0, prereqs=["Counting Principles"], ctype="study_path_introduction")
        cards = [{"card_type": "prerequisites", "blueprint_key": "prerequisites",
                  "title": "Prerequisites", "points": ["prose"]}]

        def _boom(names, goal):
            raise RuntimeError("llm down")

        out = _ground_prereq_card(cards, intro, brief_fn=_boom)
        self.assertEqual(out[0]["points"], ["Counting Principles"])   # graceful: bare name, never broken


class ProsePathGrounding(unittest.TestCase):
    def test_prose_prereq_card_rebuilt_to_idea_group_contract(self):
        # Live failure: decomposition emitted NO structured prereqs → the model's prose card stood, with
        # fragment sub-bullets ("Total arrangements of items") instead of the refresher/what-to-learn
        # contract. The prose path must now extract the names and rebuild via the brief backstop.
        intro = _Topic("i", "Intro", 0, ctype="study_path_introduction")   # assumed_prerequisites EMPTY
        cards = [{"card_type": "purpose_context", "title": "Prerequisites for Combinatorial Analysis",
                  "points": ["Basic understanding of factorials", "  - Total arrangements of items",
                             "Knowledge of basic algebra principles", "  - Manipulation of equations"]}]

        def _briefs(names, goal):
            return [{"name": n, "gloss": f"what {n} is", "required_knowledge": f"use {n} fluently"}
                    for n in names]

        out = _ground_prereq_card(cards, intro, brief_fn=_briefs)
        pts = out[0]["points"]
        self.assertIn("factorials", pts)                                   # goal phrase stripped → bare name
        self.assertIn("basic algebra principles", pts)
        self.assertIn("  - What it is: what factorials is", pts)                       # refresher sub-bullet
        self.assertIn("  - What to learn: use factorials fluently", pts)   # what-to-learn sub-bullet
        self.assertNotIn("  - Total arrangements of items", pts)           # model fragment replaced

    def test_no_prereq_card_no_prose_grounding(self):
        intro = _Topic("i", "Intro", 0, ctype="study_path_introduction")
        cards = [{"card_type": "background", "points": ["overview"]}]
        self.assertEqual(_ground_prereq_card(cards, intro, brief_fn=lambda n, g: []), cards)

    def test_name_dash_description_format_extracted(self):
        # Live regression: the model wrote "Name — description. You will use it for …" as ONE main bullet
        # (no sub-bullets, no link). _concepts_from_prereq_line returns [] on that shape; the header extractor
        # must recover the name so the card is rebuilt to the idea-group contract.
        intro = _Topic("i", "Intro", 0, ctype="study_path_introduction")   # assumed_prerequisites EMPTY
        cards = [{"card_type": "purpose_context", "title": "Prerequisites for Combinatorial Analysis",
                  "points": [
                      "Basic Algebra — manipulation of algebraic expressions. You will use it for deriving formulas.",
                      "Basic Probability — understanding likelihoods. Essential for applying combinatorial methods."]}]

        def _briefs(names, goal):
            return [{"name": n, "gloss": f"{n} refresher", "required_knowledge": f"apply {n}"} for n in names]

        out = _ground_prereq_card(cards, intro, brief_fn=_briefs)
        self.assertEqual(out[0]["points"], [
            "Basic Algebra", "  - What it is: Basic Algebra refresher", "  - What to learn: apply Basic Algebra",
            "Basic Probability", "  - What it is: Basic Probability refresher",
            "  - What to learn: apply Basic Probability"])


class RelocatePluralMatch(unittest.TestCase):
    def test_plural_prereq_matches_singular_key_term(self):
        # Live contradiction: 'factorials' was a prereq link while 'Factorial' was ALSO defined as an intro
        # key term. Relocation must match across plural/singular and remove the key term.
        cards = [
            {"card_type": "prerequisites", "title": "Prerequisites", "points": ["x"]},
            {"card_type": "definition", "title": "Key Terms", "points": [
                "Factorial", "  - multiplies a number by every number below it",
                "Permutation", "  - an ordered arrangement"]},
        ]
        harvested = _relocate_prereq_defs_from_key_terms(cards, ["factorials"])
        self.assertEqual(harvested["factorials"], "multiplies a number by every number below it")
        kt = cards[1]["points"]
        self.assertNotIn("Factorial", kt)              # removed from key terms
        self.assertIn("Permutation", kt)               # unrelated term stays


class PrereqIdeaGroupBullets(unittest.TestCase):
    def test_name_is_main_bullet_gloss_and_requirement_are_sub_bullets(self):
        # User spec: main bullet = the bare prereq/topic name (the link anchor); sub-bullets = the
        # what-it-is refresher and what to learn in the linked study path.
        intro = _Topic("i", "Intro", 0, prereqs=["conditional probability"],
                       glosses={"conditional probability": "the probability of one event given another"},
                       requirements={"conditional probability": "compute P(A|B) for concrete events"},
                       ctype="study_path_introduction")
        cards = [{"card_type": "prerequisites", "blueprint_key": "prerequisites",
                  "title": "Prerequisites", "points": ["prose"]}]
        out = _ground_prereq_card(cards, intro)
        self.assertEqual(out[0]["points"], [
            "conditional probability",
            "  - What it is: the probability of one event given another",
            "  - What to learn: compute P(A|B) for concrete events"])

    def test_no_gloss_or_requirement_stays_bare_name(self):
        intro = _Topic("i", "Intro", 0, prereqs=["vectors"], glosses={"vectors": "arrows"},
                       ctype="study_path_introduction")
        cards = [{"card_type": "prerequisites", "blueprint_key": "prerequisites",
                  "title": "Prerequisites", "points": ["prose"]}]
        out = _ground_prereq_card(cards, intro)
        self.assertEqual(out[0]["points"], ["vectors", "  - What it is: arrows"])


class PrereqCardRecognition(unittest.TestCase):
    def test_blueprint_key_is_authoritative(self):
        from app.services.lean_lesson_generator import _is_prereq_card
        self.assertTrue(_is_prereq_card({"blueprint_key": "prerequisites", "title": "Anything At All"}))

    def test_essential_foundations_title_recognized(self):
        # Live round-8 miss: "Essential Foundations for Combinatorial Analysis" got no links.
        from app.services.lean_lesson_generator import _is_prereq_card
        self.assertTrue(_is_prereq_card({"card_type": "purpose_context",
                                         "title": "Essential Foundations for Combinatorial Analysis"}))

    def test_objectives_card_still_not_matched(self):
        from app.services.lean_lesson_generator import _is_prereq_card
        self.assertFalse(_is_prereq_card({"card_type": "purpose_context", "title": "What You Will Learn"}))


class GlossHelper(unittest.TestCase):
    def test_reads_glosses_case_insensitively(self):
        t = _Topic("i", "I", 0, glosses={"Vectors": "arrows"})
        self.assertEqual(_assumed_prereq_glosses(t)["vectors"], "arrows")


if __name__ == "__main__":
    unittest.main()
