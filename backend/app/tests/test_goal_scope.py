"""A concept the GOAL explicitly names must stay a TAUGHT topic, not be demoted to an external prerequisite.
Regression for a live path whose goal was "…bayes theorem and law of total probability" but which turned Law of
Total Probability into a prereq link instead of teaching it."""
import unittest

from app.services.topic_decomposition_pipeline import generate_decomposed_topics

_GOAL = "want to learn about bayes theorem and law of total probability"

_RESP = {
    "path_plan": {
        "end_capability": "Apply Bayes' theorem using the law of total probability.",
        "end_capability_actions": ["apply"],
        "required_capabilities": [
            {"capability_id": "understand_ltp", "description": "Law of total probability.",
             "prerequisite_capability_ids": [], "satisfies_end_actions": [],
             "ownership_mode": "standalone", "owner_topic_id": None, "basis": "goal"},
            {"capability_id": "apply_bayes", "description": "Apply Bayes.",
             "prerequisite_capability_ids": ["understand_ltp"], "satisfies_end_actions": ["apply"],
             "ownership_mode": "standalone", "owner_topic_id": None, "basis": "goal"},
        ],
    },
    "topics": [
        {"topic_id": "t_ltp", "capability_id": "understand_ltp", "subject_key": "law_of_total_probability",
         "primary_action": "understand", "content_role": "foundation", "topic_type": "concept_intuition",
         "title": "Law of Total Probability", "unit_title": "Foundations", "purpose": "p", "in_scope": ["partition"],
         "practice_target": "compute", "practice_format": "short_answer",
         "practice_evidence_type": "solve_numeric", "expected_output": "P(A)", "basis": "goal"},
        {"topic_id": "t_bayes", "capability_id": "apply_bayes", "subject_key": "bayes_theorem",
         "primary_action": "apply", "content_role": "application", "topic_type": "math_formula_method",
         "title": "Bayes' Theorem", "unit_title": "Core", "purpose": "p", "in_scope": ["posterior"],
         "practice_target": "apply Bayes", "practice_format": "short_answer",
         "practice_evidence_type": "solve_numeric", "expected_output": "posterior", "basis": "goal"},
    ],
}


class GoalNamedConceptStaysTaught(unittest.TestCase):
    def test_goal_named_foundation_is_a_topic_not_a_prereq(self):
        topics = generate_decomposed_topics(_GOAL, "src", model_fn=lambda p: _RESP)
        titles = [t["title"] for t in topics]
        self.assertIn("Law of Total Probability", titles)   # taught, not folded away
        # ...and NOT sitting in the intro's assumed prerequisites.
        for t in topics:
            if t["course_type"] == "study_path_introduction":
                self.assertNotIn("Law of Total Probability", t.get("assumed_prerequisites") or [])


if __name__ == "__main__":
    unittest.main()
