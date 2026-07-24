"""_lean_card_to_legacy: a "practice" card must produce a real practice_questions entry even when the
model leaves practice_question/practice_answer null (a card whose real question ended up in `points`
instead — reads fine to a human, but the app's interactive practice runs on practice_questions, not
points, so it silently shipped empty). Live: 3 of 4 topics on one generation hit this.

Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_practice_question_backstop
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.lean_lesson_generator import _lean_card_to_legacy


class PracticeQuestionBackstop(unittest.TestCase):
    def test_missing_practice_question_falls_back_to_points(self):
        lean_card = {
            "card_type": "practice",
            "title": "Practice: Compute a Line Integral",
            "points": [
                "Evaluate the line integral of F=(y,-x) over the unit circle.",
                "  - use the standard parameterization r(t) = (cos t, sin t)",
            ],
            # practice_question / practice_answer left null, as the raw model output did live.
        }
        practice_questions: list = []
        _lean_card_to_legacy(lean_card, 0, practice_questions)
        self.assertEqual(len(practice_questions), 1)
        q = practice_questions[0]
        self.assertIn("Evaluate the line integral", q["question_text"])
        self.assertEqual(q["question_type"], "short_answer")

    def test_explicit_practice_question_is_used_as_is(self):
        lean_card = {
            "card_type": "practice",
            "title": "Practice",
            "points": ["Some setup context."],
            "practice_question": "What is the value of the line integral?",
            "practice_answer": "0",
        }
        practice_questions: list = []
        _lean_card_to_legacy(lean_card, 0, practice_questions)
        self.assertEqual(len(practice_questions), 1)
        self.assertEqual(practice_questions[0]["question_text"], "What is the value of the line integral?")
        self.assertEqual(practice_questions[0]["correct_answer"], "0")

    def test_no_points_and_no_practice_question_produces_nothing(self):
        lean_card = {"card_type": "practice", "title": "Practice", "points": []}
        practice_questions: list = []
        _lean_card_to_legacy(lean_card, 0, practice_questions)
        self.assertEqual(practice_questions, [])

    def test_non_practice_card_is_unaffected(self):
        lean_card = {"card_type": "background", "title": "Background", "points": ["Some fact."]}
        practice_questions: list = []
        _lean_card_to_legacy(lean_card, 0, practice_questions)
        self.assertEqual(practice_questions, [])


if __name__ == "__main__":
    unittest.main()
