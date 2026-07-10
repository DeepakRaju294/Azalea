"""Card header normalization (_card_headers) — CARD_CONTENT_CHARTER_SPEC §7.

main_concept must be a CONCRETE claim (not an instructor objective like "Detail the foundational knowledge") and
must differ from learning_goal — fixing the pervasive main_concept==learning_goal instructor-voice duplication.
Offline. Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_card_headers
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.lean_lesson_generator import _card_headers


class CardHeaders(unittest.TestCase):
    def test_instructor_voice_job_falls_back_to_concrete_title(self):
        mc, lg = _card_headers({"learning_job": "Detail the foundational knowledge for this topic"},
                               "Essential Background")
        self.assertEqual(mc, "Essential Background")                 # concrete, not the objective
        self.assertEqual(lg, "Detail the foundational knowledge for this topic")
        self.assertNotEqual(mc, lg)

    def test_concrete_job_is_kept_and_goal_cleared(self):
        mc, lg = _card_headers({"learning_job": "Half the linear coefficient, square it, add and subtract"}, "The Rule")
        self.assertEqual(mc, "Half the linear coefficient, square it, add and subtract")
        self.assertEqual(lg, "")                                      # distinct (empty, not a duplicate)

    def test_various_instructor_voice_verbs_rejected(self):
        for job in ("Understand the process", "Introduce the concept", "Familiarize with key components",
                    "Identify essential prerequisites", "Follow the sequence of steps", "Overview of the method"):
            mc, lg = _card_headers({"learning_job": job}, "Concrete Title")
            self.assertEqual(mc, "Concrete Title", f"{job!r} should fall back to the title")
            self.assertNotEqual(mc, lg)

    def test_missing_job_uses_title(self):
        mc, lg = _card_headers({}, "Key Terms")
        self.assertEqual(mc, "Key Terms")
        self.assertEqual(lg, "")

    def test_never_equal(self):
        for job in ("", "Detail X", "A concrete claim about Y", "Understand Z"):
            mc, lg = _card_headers({"learning_job": job}, "Some Title")
            self.assertNotEqual((mc, lg)[0], (mc, lg)[1])


if __name__ == "__main__":
    unittest.main()
