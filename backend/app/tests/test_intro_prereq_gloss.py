"""The study-path intro must GLOSS each named prerequisite in one line (§1.3 orientation layer), not list bare
terms. A live "Ohm's Law" intro listed "Electric Current / Voltage / Electrical Resistance" with no explanation,
stranding a first-time learner. The gloss guidance is intro-only; body topics keep 'use without definition'."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.prompts.lean_lesson_prompt import build_lean_system_prompt


class IntroPrereqGloss(unittest.TestCase):
    def test_prompt_requires_concrete_named_prerequisites_not_goals(self):
        p = build_lean_system_prompt(omit_worked_example=False)
        # prerequisites must be a NAMED concept + one-line what-it-is (key-terms shape), not the bare term...
        self.assertIn("<Concept name> — <what it is>", p)
        self.assertIn("concrete NAMED concept", p)
        # ...and goal/meta phrasing is explicitly banned (the exact vagueness seen on a live path).
        self.assertIn("BANNED goal/meta phrasing", p)
        for banned in ("Understanding", "Knowledge of", "Awareness of"):
            self.assertIn(banned, p)
        # still orientation, scoped to the intro; body topics keep "use without definition".
        self.assertIn("NOT reteaching", p)
        self.assertIn("body topics still use assumed prerequisites without definition", p)
        self.assertIn("without fully explaining them", p)


if __name__ == "__main__":
    unittest.main()
