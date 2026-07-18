"""Phase-0 goal→domain classifier (DOMAIN_ROUTING_AND_TOPIC_GATE_SPEC §3).

Fine domains (coding · math · logic · statistics · physics · chemistry · biology · electrical_engineering ·
finance · economics · humanities · machine_learning) + derived `mixed`/`unknown`; each maps to a coarse
`gate_family`. Keyword weights are tunable, so we assert domain/family, not exact scores.

Run: python -m unittest app.tests.test_domain_classifier
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.domain_classifier import classify_domain, gate_family_of


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
            "Teach me about black holes and galaxies.": "astronomy",
            "Teach me about plate tectonics and earthquakes.": "earth_science",
            "Teach me the cardiovascular system and its physiology.": "medicine",
            "Teach me Spanish verb conjugation and grammar.": "language_learning",
        }
        for goal, expected in cases.items():
            self.assertEqual(classify_domain(goal).domain, expected, goal)

    def test_gate_family_mapping(self):
        self.assertEqual(classify_domain("Teach me Newton's second law.").gate_family, "science")
        self.assertEqual(classify_domain("Teach me photosynthesis.").gate_family, "science")
        self.assertEqual(classify_domain("What is inflation?").gate_family, "quant")           # economics -> quant
        self.assertEqual(classify_domain("Teach me about black holes.").gate_family, "science")
        self.assertEqual(classify_domain("Teach me Spanish grammar.").gate_family, "expository")
        self.assertEqual(classify_domain("Teach me completing the square.").gate_family, "math")
        self.assertEqual(classify_domain("Teach me propositional logic.").gate_family, "math")
        self.assertEqual(classify_domain("Teach me DFS in Python.").gate_family, "coding")
        # new families (taxonomy expansion): CS systems, statistics, EE, quantitative finance
        self.assertEqual(classify_domain("How does TCP congestion control work?").gate_family, "cs")
        self.assertEqual(classify_domain("Teach me z-scores and standardization.").gate_family, "data_science")
        self.assertEqual(classify_domain("Teach me Ohm's law and circuits.").gate_family, "ee")
        self.assertEqual(classify_domain("Teach me compound interest and NPV.").gate_family, "quant")

    def test_expanded_vocabulary_classifies_confidently(self):
        # Regression for the C.1 keyword-coverage + plural fix: these were UNKNOWN/ambiguous before (the wizard
        # had to ask the domain). The classifier now recognizes them CONFIDENTLY, so onboarding can trust it.
        cases = {
            "union find": "coding",
            "time complexity": "coding",
            "how does encryption work": "coding",
            "backtracking": "coding",
            "linked lists": "coding",                 # regular plural via the trailing-s match
            "derivatives and integrals": "math",      # plurals
            "gaussian elimination": "math",
            "the water cycle": "earth_science",
            "the French Revolution": "humanities",     # history phrase outweighs the "french" language collision
        }
        for goal, expected in cases.items():
            sig = classify_domain(goal)
            self.assertEqual(sig.domain, expected, goal)
            self.assertEqual(sig.classification_status, "classified", f"{goal!r} should classify confidently")

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

    def test_gate_family_of_accepts_fine_family_and_alias(self):
        # fine domain, family name given directly, and the user-facing "concept" alias all resolve
        self.assertEqual(gate_family_of("physics"), "science")
        self.assertEqual(gate_family_of("science"), "science")       # family name itself
        self.assertEqual(gate_family_of("concept"), "expository")    # wizard coarse label
        self.assertEqual(gate_family_of("coding"), "coding")
        self.assertEqual(gate_family_of("math"), "math")
        for junk in ("mixed", "unknown", "", None, "banana"):
            self.assertEqual(gate_family_of(junk), "", repr(junk))

    def test_status_and_confidence_shape(self):
        sig = classify_domain("Teach me DFS in Python.")
        self.assertIn(sig.classification_status, {"classified", "ambiguous"})
        self.assertGreaterEqual(sig.confidence, 0.0)
        self.assertLessEqual(sig.confidence, 1.0)


if __name__ == "__main__":
    unittest.main()
