"""Prereq consolidation: a concept_intuition whose subject isn't taught on the path is a prerequisite that
folds into the intro (assumed foundations silent, glossed statements one-lined), and body topics are marked to
assume-not-explain it. The assume-vs-gloss rule is STRUCTURAL: a whole skill/topic assumes, a single
statement (form/notation/formula) glosses; default gloss."""
import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.topic_generator import _classify_prerequisite, _fold_prereqs_into_intro
from app.services.topic_scope_service import build_topic_scope_contract


class ClassifyPrerequisite(unittest.TestCase):
    def test_broad_skills_are_assumed(self):
        for title in ["Understanding Algebraic Principles", "What Are Quadratics",
                      "Understanding Quadratic Equations", "Understanding Functions", "Working with Graphs"]:
            self.assertEqual(_classify_prerequisite(title), "assume", title)

    def test_statements_are_glossed(self):
        for title in ["Vertex Form of a Parabola", "Labeling Coefficients a, b, c", "The Discriminant Formula",
                      "Slope-Intercept Form", "Sigma Notation", "The Distributive Property"]:
            self.assertEqual(_classify_prerequisite(title), "gloss", title)

    def test_default_is_gloss(self):
        # an unrecognized, non-foundational concept defaults to the safe side (gloss)
        self.assertEqual(_classify_prerequisite("Priority Queues"), "gloss")
        self.assertEqual(_classify_prerequisite("Amortized Analysis"), "gloss")


class FoldPrereqsIntoIntro(unittest.TestCase):
    def _path(self):
        return [
            {"title": "Introduction to Completing the Square", "topic_type": "study_path_introduction"},
            {"title": "Understanding Quadratic Equations", "topic_type": "concept_intuition"},   # prereq -> assume
            {"title": "Vertex Form of a Parabola", "topic_type": "concept_intuition"},            # prereq -> gloss
            {"title": "Steps to Complete the Square", "topic_type": "process_walkthrough"},       # taught target
        ]

    def test_prereqs_leave_the_body_and_land_on_the_intro(self):
        res = _fold_prereqs_into_intro([dict(t) for t in self._path()])
        types = [t["topic_type"] for t in res]
        self.assertNotIn("concept_intuition", types)                       # both prereqs folded out of the body
        intro = next(t for t in res if t["topic_type"] == "study_path_introduction")
        self.assertEqual(intro["assumed_prerequisites"], ["Quadratic Equations"])
        # glossed statements ride in decomposition_metadata (no Topic column) as brief_refresh_prerequisites,
        # which the scope contract feeds to the intro prompt as a 1-3 line refresh
        self.assertEqual(
            intro["decomposition_metadata"]["brief_refresh_prerequisites"], ["Vertex Form Parabola"]
        )

    def test_body_topics_are_told_to_assume_not_explain(self):
        res = _fold_prereqs_into_intro([dict(t) for t in self._path()])
        body = next(t for t in res if t["topic_type"] == "process_walkthrough")
        self.assertIn("Quadratic Equations", body["assumed_prerequisites"])
        self.assertIn("Vertex Form Parabola", body["assumed_prerequisites"])

    def test_a_taught_concepts_intuition_is_kept(self):
        # "What is Completing the Square?" IS taught here (its subject matches the walkthrough) -> stays inline
        path = [
            {"title": "Introduction to Completing the Square", "topic_type": "study_path_introduction"},
            {"title": "What is Completing the Square?", "topic_type": "concept_intuition"},
            {"title": "Steps to Complete the Square", "topic_type": "process_walkthrough"},
        ]
        res = _fold_prereqs_into_intro([dict(t) for t in path])
        self.assertIn("What is Completing the Square?", [t["title"] for t in res])

    def test_no_intro_means_no_change(self):
        path = [{"title": "Understanding Quadratics", "topic_type": "concept_intuition"},
                {"title": "Steps to Complete the Square", "topic_type": "process_walkthrough"}]
        self.assertEqual(len(_fold_prereqs_into_intro([dict(t) for t in path])), 2)


class GlossedPrereqsReachTheScopeContract(unittest.TestCase):
    """The intro's folded gloss (stashed in decomposition_metadata) surfaces as the contract's
    brief_refresh_prerequisites, which the prompt renders as a 1-3 line refresh."""

    def _intro(self, **kw):
        return SimpleNamespace(
            id="t1", title="Introduction to Completing the Square",
            topic_type="study_path_introduction", purpose="", learner_outcome="",
            prerequisite_topics=None, in_scope=None, out_of_scope=None,
            secondary_course_types=[], **kw,
        )

    def test_brief_refresh_flows_from_decomposition_metadata(self):
        topic = self._intro(
            assumed_prerequisites=["Quadratic Equations"],
            decomposition_metadata={"brief_refresh_prerequisites": ["Vertex Form Parabola"]},
        )
        contract = build_topic_scope_contract(topic, study_path=None)
        self.assertIn("Vertex Form Parabola", contract["brief_refresh_prerequisites"])
        self.assertIn("Quadratic Equations", contract["assumed_prerequisites"])

    def test_assumed_wins_over_brief_refresh(self):
        # a concept that is both assumed and glossed is assumed silently, never double-listed
        topic = self._intro(
            assumed_prerequisites=["Vertex Form Parabola"],
            decomposition_metadata={"brief_refresh_prerequisites": ["Vertex Form Parabola"]},
        )
        contract = build_topic_scope_contract(topic, study_path=None)
        self.assertNotIn("Vertex Form Parabola", contract["brief_refresh_prerequisites"])
        self.assertIn("Vertex Form Parabola", contract["assumed_prerequisites"])


class GlossedPrereqsReachTheLeanPrompt(unittest.TestCase):
    """The live (lean) generation path emits the intro's folded gloss as a 'Briefly refresh' instruction."""

    def test_lean_prompt_includes_brief_refresh_block(self):
        from app.prompts.lean_lesson_prompt import build_lean_user_prompt

        topic = SimpleNamespace(
            id="t1", study_path=None, title="Introduction to Completing the Square",
            purpose="Orient the learner.", topic_type="study_path_introduction", course_type="study_path_introduction",
            secondary_course_types=[], modifiers=[], in_scope=None, out_of_scope=None,
            prerequisite_topics=None, assumed_prerequisites=["Quadratic Equations"], practice_target=None,
            practice_format=None,
            decomposition_metadata={"brief_refresh_prerequisites": ["Vertex Form Parabola"]},
        )
        prompt = build_lean_user_prompt(topic=topic, chunks=[])
        self.assertIn("Briefly refresh", prompt)
        self.assertIn("Vertex Form Parabola", prompt)
        self.assertIn("Assumed prerequisites: Quadratic Equations", prompt)


if __name__ == "__main__":
    unittest.main()
