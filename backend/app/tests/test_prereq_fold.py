"""Prereq consolidation: a concept_intuition whose subject isn't taught on the path is a prerequisite that
folds into the intro (assumed foundations silent, glossed statements one-lined), and body topics are marked to
assume-not-explain it. The assume-vs-gloss rule is STRUCTURAL: a whole skill/topic assumes, a single
statement (form/notation/formula) glosses; default gloss."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.topic_generator import _classify_prerequisite, _fold_prereqs_into_intro


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
        self.assertEqual([g["concept"] for g in intro["glossed_prerequisites"]], ["Vertex Form Parabola"])

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


if __name__ == "__main__":
    unittest.main()
