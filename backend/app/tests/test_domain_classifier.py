"""Phase-0 goal→domain classifier (DOMAIN_ROUTING_AND_TOPIC_GATE_SPEC §3 / §6 fixtures).

Deterministic heuristic: the acceptance-fixture prompts must resolve to the right v1 domain
(coding · math · science · concept), and a nothing-matches prompt must yield `fallback_concept`
(not `classifier_failed`). Keyword weights are tunable, so we assert the DOMAIN, not exact scores.

Run: python -m unittest app.tests.test_domain_classifier
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.domain_classifier import classify_domain


class DomainClassifierFixtures(unittest.TestCase):
    def test_spec_acceptance_fixtures(self):
        cases = {
            "Teach me completing the square.": "math",
            "Teach me DFS in Python.": "coding",
            "Teach me Newton's second law.": "science",
            "Teach me photosynthesis.": "science",
            "Teach me how to calculate force using F = ma.": "science",
            "What is inflation?": "concept",
            "Build a neural net in PyTorch.": "coding",
            "Understand gradient descent mathematically.": "math",
        }
        for goal, expected in cases.items():
            self.assertEqual(classify_domain(goal).domain, expected, goal)

    def test_nothing_matches_is_fallback_concept_not_failure(self):
        sig = classify_domain("asdfghjkl qwerty zxcvb")
        self.assertEqual(sig.domain, "concept")
        self.assertEqual(sig.classification_status, "fallback_concept")
        self.assertNotEqual(sig.classification_status, "classifier_failed")

    def test_empty_goal_is_fallback_concept(self):
        for g in ("", None, "   "):
            self.assertEqual(classify_domain(g).classification_status, "fallback_concept")

    def test_status_and_confidence_shape(self):
        sig = classify_domain("Teach me DFS in Python.")
        self.assertIn(sig.classification_status, {"classified", "low_confidence"})
        self.assertGreaterEqual(sig.confidence, 0.0)
        self.assertLessEqual(sig.confidence, 1.0)

    def test_subdomain_family_is_controlled(self):
        # completing the square -> math/algebra family
        self.assertEqual(classify_domain("Teach me completing the square.").subdomain_family, "algebra")
        # DFS in Python -> coding/algorithms family
        self.assertEqual(classify_domain("Teach me DFS in Python.").subdomain_family, "algorithms")

    def test_scores_recorded_for_all_four_domains(self):
        scores = classify_domain("Teach me completing the square.").scores
        self.assertEqual(set(scores), {"coding", "math", "science", "concept"})


if __name__ == "__main__":
    unittest.main()
