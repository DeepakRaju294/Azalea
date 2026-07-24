"""Stem-canonicalized requirement/topic token matching (_stem6 in topic_decomposition_pipeline.py).

Live bug (Stokes' theorem path, 'what is purpose of stokes theorem statement topic'): requirement R5
"state and interpret Stokes' theorem in the context of physics and mathematics" was ruled UNOWNED even
though a real "Stokes' Theorem Interpretation" topic clearly taught it — 'interpret' vs 'interpretation'
and 'physics' vs 'physical' each failed exact-token equality (only a crude plural strip existed), leaving
the overlap one token short. B.4.1 then synthesized a duplicate "Stokes' theorem statement" topic ON TOP
of the goal-core topic, so the learner met the theorem's statement twice (once at position 2, before line/
surface integrals were even taught). 6-char-prefix stemming makes derivational variants meet while leaving
short distinguishing prefixes ('pre'/'in' in the family-survey case) untouched.

Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_requirement_stem_matching
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.topic_decomposition_pipeline import (
    _requirement_covered_by_topics,
    _stem6,
    generate_decomposed_topics,
)


class Stem6Behavior(unittest.TestCase):
    def test_derivational_variants_share_a_stem(self):
        self.assertEqual(_stem6({"interpret"}), _stem6({"interpretation"}))
        self.assertEqual(_stem6({"physic"}), _stem6({"physical"}))       # after _req_tokens' plural strip
        self.assertEqual(_stem6({"evaluate"}), _stem6({"evaluating"}))

    def test_short_distinguishing_tokens_pass_through_unchanged(self):
        # 'pre' vs 'in' (the family-survey trap) must never be merged or truncated away.
        self.assertEqual(_stem6({"pre", "in", "order"}), {"pre", "in", "order"})


class InterpretationTopicOwnsStatementRequirement(unittest.TestCase):
    def test_r5_is_covered_by_the_interpretation_topic(self):
        req = {"requirement_id": "R5", "name": "Stokes' theorem statement", "kind": "core",
               "statement": "state and interpret Stokes' theorem in the context of physics and mathematics."}
        topics = [{"title": "Stokes' Theorem Interpretation",
                   "subject_key": "stokes_theorem_interpretation",
                   "in_scope": ["formal statement of Stokes' theorem",
                                "interpretation in physical and mathematical contexts"]}]
        self.assertTrue(_requirement_covered_by_topics(req, topics))

    def test_unrelated_topic_still_does_not_cover_it(self):
        req = {"requirement_id": "R5", "name": "Stokes' theorem statement", "kind": "core",
               "statement": "state and interpret Stokes' theorem in the context of physics and mathematics."}
        topics = [{"title": "Computing Line Integrals", "subject_key": "line_integrals",
                   "in_scope": ["line integral formula", "work done by a vector field"]}]
        self.assertFalse(_requirement_covered_by_topics(req, topics))


class NameContainmentOwnership(unittest.TestCase):
    """Live (round 10, user: 'the divergence theorem topic feels not needed'): R4 name 'The divergence
    theorem' vs the real topic 'Applying the Divergence Theorem' — the STATEMENT-token overlap was one
    short ('apply' is a stopword), so a duplicate 'The Divergence Theorem' topic was synthesized, and the
    redundancy guard couldn't drop it because 'divergence' also appears in R1 ('gradients, curls, and
    divergences') and was classified as cross-requirement family vocabulary. A requirement whose NAME is
    fully contained in a topic's identity is now owned by that topic."""

    def test_applying_topic_owns_the_divergence_theorem_requirement(self):
        req = {"requirement_id": "R4", "name": "The divergence theorem", "kind": "core",
               "statement": "apply the divergence theorem and understand its relationship to Stokes' theorem."}
        topics = [{"title": "Applying the Divergence Theorem",
                   "subject_key": "divergence_theorem_application",
                   "in_scope": ["divergence theorem applications in flux problems"]}]
        self.assertTrue(_requirement_covered_by_topics(req, topics))

    def test_name_containment_does_not_leak_across_family_members(self):
        # 'Pre-order traversal' keeps its distinguishing 'pre' token — In-Order can never contain it.
        req = {"requirement_id": "R2", "name": "Pre-order traversal", "kind": "core",
               "statement": "describe the pre-order traversal algorithm"}
        topics = [{"title": "In-Order Traversal", "subject_key": "in_order_traversal",
                   "in_scope": ["visit order", "left-root-right"]}]
        self.assertFalse(_requirement_covered_by_topics(req, topics))

    def test_single_word_name_cannot_claim_by_one_shared_word(self):
        req = {"requirement_id": "R9", "name": "Integrals", "kind": "core",
               "statement": "master every kind of integral used in vector analysis and beyond"}
        topics = [{"title": "Computing Line Integrals", "subject_key": "line_integrals",
                   "in_scope": ["line integral computation"]}]
        self.assertFalse(_requirement_covered_by_topics(req, topics))

    def test_end_to_end_no_duplicate_divergence_topic(self):
        from app.services.topic_decomposition_pipeline import generate_decomposed_topics
        reqs = {"requirements": [
            {"requirement_id": "R1", "name": "Vector calculus basics", "kind": "core",
             "statement": "apply fundamental concepts of vector calculus, including gradients, curls, "
                          "and divergences."},
            {"requirement_id": "R4", "name": "The divergence theorem", "kind": "core",
             "statement": "apply the divergence theorem and understand its relationship to Stokes' theorem."},
        ]}
        plan = {"path_plan": {"end_capability_actions": ["understand"], "required_capabilities": []},
                "topics": [
                    {"topic_id": "t1", "capability_id": "t1", "subject_key": "vector_calculus",
                     "primary_action": "understand", "content_role": "core",
                     "topic_type": "math_formula_method", "title": "Fundamental Concepts of Vector Calculus",
                     "unit_title": "u", "purpose": "p",
                     "in_scope": ["gradients", "curls", "divergences"],
                     "covers_requirements": ["R1"], "basis": "goal"},
                    {"topic_id": "t2", "capability_id": "t2", "subject_key": "divergence_theorem_application",
                     "primary_action": "apply", "content_role": "core",
                     "topic_type": "math_formula_method", "title": "Applying the Divergence Theorem",
                     "unit_title": "u", "purpose": "p",
                     "in_scope": ["divergence theorem applications in flux problems"],
                     "covers_requirements": ["R4"], "basis": "goal"}]}
        def fn(payload):
            return reqs if "learning requirements" in payload["user"] else plan
        topics = generate_decomposed_topics("want to learn about stokes theorem", "s", model_fn=fn)
        divergence_titled = [t["title"] for t in topics if "divergence" in t["title"].lower()]
        self.assertEqual(len(divergence_titled), 1, divergence_titled)   # no synthesized duplicate


class PrereqDelegation(unittest.TestCase):
    """User decision ('Vector Calculus Basics' round): a requirement whose concept the path already
    declares as an external PREREQUISITE is delegated to that prerequisite — the prereq link (a full
    dedicated path) teaches it strictly better than the hollow 3-card concept_intuition overview that
    synthesis would produce, and better than shield-keeping a foundation stub."""

    def test_delegation_classifier(self):
        from app.services.topic_decomposition_pipeline import _requirement_delegated_to_prereq
        r1 = {"requirement_id": "R1", "name": "Vector calculus basics", "kind": "core",
              "statement": "apply fundamental concepts of vector calculus, including gradients, curls, "
                           "and divergences."}
        self.assertEqual(_requirement_delegated_to_prereq(r1, ["vector calculus"]), "vector calculus")
        # unrelated and single-token prereqs never delegate
        self.assertIsNone(_requirement_delegated_to_prereq(r1, ["differential equations"]))
        self.assertIsNone(_requirement_delegated_to_prereq(r1, ["calculus"]))

    def test_delegated_requirement_synthesizes_no_topic_end_to_end(self):
        from app.services.topic_decomposition_pipeline import generate_decomposed_topics
        reqs = {"requirements": [
            {"requirement_id": "R1", "name": "Vector calculus basics", "kind": "core",
             "statement": "apply fundamental concepts of vector calculus, including gradients, curls, "
                          "and divergences."},
            {"requirement_id": "R5", "name": "Stokes' theorem statement", "kind": "core",
             "statement": "state and interpret Stokes' theorem"},
        ], "assumed_prerequisites": [{"name": "vector calculus", "gloss": "g"}]}
        plan = {"path_plan": {"end_capability_actions": ["understand"], "required_capabilities": []},
                "topics": [{"topic_id": "t1", "capability_id": "t1", "subject_key": "stokes_theorem",
                            "primary_action": "apply", "content_role": "core",
                            "topic_type": "math_formula_method", "title": "Stokes' Theorem",
                            "unit_title": "u", "purpose": "p",
                            "in_scope": ["statement of stokes theorem"],
                            "covers_requirements": ["R5"], "basis": "goal"}]}
        def fn(payload):
            return reqs if "learning requirements" in payload["user"] else plan
        topics = generate_decomposed_topics("want to learn about stokes theorem", "s", model_fn=fn)
        titles = [t["title"].lower() for t in topics]
        self.assertFalse(any("vector calculus" in t for t in titles), titles)   # no synthesized stub
        intro = next(t for t in topics if t["course_type"] == "study_path_introduction")
        prereq_names = {(p if isinstance(p, str) else p.get("name", "")).lower()
                        for p in (intro.get("assumed_prerequisites") or [])}
        self.assertIn("vector calculus", prereq_names)                           # concept lives as prereq
        path_trace = (intro.get("decomposition_metadata") or {}).get("path_decision_trace") or []
        self.assertTrue(any(e["stage"] == "requirement.delegated_to_prerequisite" for e in path_trace))

    def test_requirement_without_matching_prereq_still_synthesizes(self):
        from app.services.topic_decomposition_pipeline import generate_decomposed_topics
        reqs = {"requirements": [
            {"requirement_id": "R2", "name": "Surface integrals", "kind": "core",
             "statement": "evaluate surface integrals and their significance"}],
            "assumed_prerequisites": [{"name": "vector calculus", "gloss": "g"}]}
        plan = {"path_plan": {"end_capability_actions": ["understand"], "required_capabilities": []},
                "topics": [{"topic_id": "t1", "capability_id": "t1", "subject_key": "stokes_theorem",
                            "primary_action": "apply", "content_role": "core",
                            "topic_type": "math_formula_method", "title": "Stokes' Theorem",
                            "unit_title": "u", "purpose": "p", "in_scope": ["statement of stokes theorem"],
                            "covers_requirements": [], "basis": "goal"}]}
        def fn(payload):
            return reqs if "learning requirements" in payload["user"] else plan
        topics = generate_decomposed_topics("want to learn about stokes theorem", "s", model_fn=fn)
        self.assertTrue(any("surface integral" in t["title"].lower() for t in topics))


class ConceptProcessCard(unittest.TestCase):
    """concept_intuition's blueprint now carries a process card as its MAIN TEACHING card — live concept
    topics kept shipping as hollow background+edge_case+practice shells ('doesn't teach anything much at
    all'). The rule is concept-shaped: explanation, never the algorithm loop scaffold."""

    def test_blueprint_sequence_includes_process(self):
        from app.core.course_blueprints import get_topic_blueprint
        bp = get_topic_blueprint("concept_intuition")
        self.assertIn("process", bp["default_card_sequence"])
        self.assertNotIn("process", bp["optional_cards"])            # required, not skippable
        self.assertNotIn("worked_example", bp["default_card_sequence"])   # still no worked example

    def test_concept_process_rule_is_explanation_shaped(self):
        from app.core.course_stage_rules import STAGE_RULES
        rule = STAGE_RULES["concept_intuition"]["process"]
        content = " ".join(rule["content"]).lower()
        self.assertIn("why the concept exists", content)
        self.assertIn("naive", content)
        self.assertNotIn("repeated action", content)
        self.assertNotIn("stopping condition", content)


class FamilySurveyRegressionGuard(unittest.TestCase):
    """The documented reverted-fix trap in _requirement_covered_by_topics' KNOWN LIMITATION note: a broader
    matching rule once let 'In-Order Traversal' falsely claim coverage of the 'Pre-order traversal'
    requirement. Stemming must NOT reintroduce that — pre/in are short tokens the stem leaves intact, and
    the shared family vocabulary alone stays under the >=3 threshold."""

    def test_in_order_topic_does_not_claim_pre_order_requirement(self):
        req = {"requirement_id": "R2", "name": "Pre-order traversal", "kind": "core",
               "statement": "describe the pre-order traversal algorithm"}
        topics = [{"title": "In-Order Traversal", "subject_key": "in_order_traversal",
                   "in_scope": ["visit order", "left-root-right"]}]
        self.assertFalse(_requirement_covered_by_topics(req, topics))

    def test_pre_order_requirement_still_synthesizes_its_own_topic_end_to_end(self):
        # the full family-survey pipeline scenario from test_tree_traversal_teaching, re-asserted here so
        # a future stemming change that breaks synthesis fails THIS focused file too.
        reqs = {"requirements": [
            {"requirement_id": "R1", "name": "In-order traversal", "kind": "core",
             "statement": "describe the in-order traversal algorithm"},
            {"requirement_id": "R2", "name": "Pre-order traversal", "kind": "core",
             "statement": "describe the pre-order traversal algorithm"},
        ]}
        plan = {"path_plan": {"end_capability_actions": ["trace"], "required_capabilities": []},
                "topics": [{"topic_id": "t1", "capability_id": "t1", "subject_key": "in_order_traversal",
                            "primary_action": "trace", "content_role": "algorithm_trace",
                            "topic_type": "algorithm_walkthrough", "title": "In-Order Traversal",
                            "unit_title": "u", "purpose": "p",
                            "in_scope": ["visit order", "left-root-right"],
                            "covers_requirements": ["R1"], "basis": "goal"}]}
        def fn(payload):
            return reqs if "learning requirements" in payload["user"] else plan
        topics = generate_decomposed_topics("want to learn about bst traversal algorithms", "s",
                                            model_fn=fn, coding_follow_ups=True)
        self.assertTrue(any("Pre-order" in t["title"] for t in topics),
                        "pre-order requirement must still get its own synthesized topic")


class BookTitleCase(unittest.TestCase):
    """Live (topic 2 on a Stokes' path): a synthesized topic inherits its requirement's name VERBATIM —
    "The divergence theorem" shipped lowercase beside Title Case siblings. Every final topic title is now
    book-title-cased; words already carrying an uppercase (Stokes', BST, Pre-order) are never touched."""

    def test_book_title_case_rules(self):
        from app.services.topic_decomposition_pipeline import _book_title_case
        self.assertEqual(_book_title_case("The divergence theorem"), "The Divergence Theorem")
        self.assertEqual(_book_title_case("introduction to stokes theorem"), "Introduction to Stokes Theorem")
        self.assertEqual(_book_title_case("Stokes' Theorem"), "Stokes' Theorem")           # untouched
        self.assertEqual(_book_title_case("Comparing RANS and LES Models"),
                         "Comparing RANS and LES Models")                                   # acronyms kept
        self.assertEqual(_book_title_case("Pre-order traversal"), "Pre-order Traversal")   # hyphen word kept
        self.assertEqual(_book_title_case("applications of the theorem in physics"),
                         "Applications of the Theorem in Physics")

    def test_synthesized_topic_title_is_title_cased_end_to_end(self):
        from app.services.topic_decomposition_pipeline import generate_decomposed_topics
        reqs = {"requirements": [
            {"requirement_id": "R1", "name": "Stokes' theorem statement", "kind": "core",
             "statement": "state and interpret Stokes' theorem"},
            {"requirement_id": "R2", "name": "the divergence theorem", "kind": "core",
             "statement": "apply the divergence theorem and its relationship to flux"},
        ]}
        plan = {"path_plan": {"end_capability_actions": ["understand"], "required_capabilities": []},
                "topics": [{"topic_id": "t1", "capability_id": "t1", "subject_key": "stokes_theorem",
                            "primary_action": "apply", "content_role": "core",
                            "topic_type": "math_formula_method", "title": "Stokes' Theorem",
                            "unit_title": "u", "purpose": "p",
                            "in_scope": ["statement of stokes theorem"],
                            "covers_requirements": ["R1"], "basis": "goal"}]}
        def fn(payload):
            return reqs if "learning requirements" in payload["user"] else plan
        topics = generate_decomposed_topics("want to learn about stokes theorem", "s", model_fn=fn)
        titles = [t["title"] for t in topics]
        self.assertIn("The Divergence Theorem", titles)          # synthesized from lowercase R2 name
        self.assertNotIn("the divergence theorem", titles)
        for title in titles:
            first = title.split()[0]
            self.assertTrue(first[0].isupper() or not first[0].isalpha(), title)


if __name__ == "__main__":
    unittest.main()
