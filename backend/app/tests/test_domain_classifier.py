"""Phase-0 goal→domain classifier (DOMAIN_ROUTING_AND_TOPIC_GATE_SPEC §3).

Fine domains (coding · math · logic · statistics · physics · chemistry · biology · electrical_engineering ·
finance · economics · humanities · machine_learning) + derived `mixed`/`unknown`; each maps to a coarse
`gate_family`. Keyword weights are tunable, so we assert domain/family, not exact scores.

Run: python -m unittest app.tests.test_domain_classifier
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.domain_classifier import classify_domain


class DomainClassifierFixtures(unittest.TestCase):
    def test_fine_domain_fixtures(self):
        cases = {
            "Teach me completing the square.": "math",
            "Teach me DFS in Python.": "coding",
            "Teach me Newton's second law.": "physics",
            "Teach me photosynthesis.": "biology",
            "Teach me how to calculate force using F = ma.": "physics",
            "What is inflation?": "economics",
            "Analyze the themes in Hamlet.": "humanities",
            "Teach me stoichiometry.": "chemistry",
            "Teach me how Ohm's Law works in a circuit.": "electrical_engineering",
            "Teach me hypothesis testing and p-values.": "statistics",
            "Teach me propositional logic and truth tables.": "logic",
            "How do I calculate compound interest?": "finance",
        }
        for goal, expected in cases.items():
            self.assertEqual(classify_domain(goal).domain, expected, goal)

    def test_gate_family_mapping(self):
        self.assertEqual(classify_domain("Teach me Newton's second law.").gate_family, "science")
        self.assertEqual(classify_domain("Teach me photosynthesis.").gate_family, "science")
        self.assertEqual(classify_domain("What is inflation?").gate_family, "expository")
        self.assertEqual(classify_domain("Teach me completing the square.").gate_family, "math")
        self.assertEqual(classify_domain("Teach me propositional logic.").gate_family, "math")
        self.assertEqual(classify_domain("Teach me DFS in Python.").gate_family, "coding")

    def test_unknown_when_nothing_matches(self):
        for g in ("asdfghjkl qwerty zxcvb", "", None, "   "):
            sig = classify_domain(g)
            self.assertEqual(sig.domain, "unknown", repr(g))
            self.assertEqual(sig.gate_family, "")                 # non-gating
            self.assertEqual(sig.classification_status, "ambiguous")

    def test_mixed_when_two_families_comparable(self):
        # balanced coding + math signal -> mixed (non-gating), not a single winner
        sig = classify_domain("python function loop recursion and algebra calculus theorem proof")
        self.assertEqual(sig.domain, "mixed")
        self.assertEqual(sig.gate_family, "")

    def test_status_and_confidence_shape(self):
        sig = classify_domain("Teach me DFS in Python.")
        self.assertIn(sig.classification_status, {"classified", "ambiguous"})
        self.assertGreaterEqual(sig.confidence, 0.0)
        self.assertLessEqual(sig.confidence, 1.0)


if __name__ == "__main__":
    unittest.main()
