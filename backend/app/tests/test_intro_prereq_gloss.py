"""The study-path intro must GLOSS each named prerequisite in one line (§1.3 orientation layer), not list bare
terms. A live "Ohm's Law" intro listed "Electric Current / Voltage / Electrical Resistance" with no explanation,
stranding a first-time learner. The gloss guidance is intro-only; body topics keep 'use without definition'."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.prompts.lean_lesson_prompt import build_lean_system_prompt


class IntroPrereqGloss(unittest.TestCase):
    def test_prompt_requires_one_line_orientation_for_named_prerequisites(self):
        p = build_lean_system_prompt(omit_worked_example=False)
        # the intro must gloss named prerequisites, not list bare terms...
        self.assertIn("give each named prerequisite a ONE-LINE plain-language orientation", p)
        self.assertIn("not the bare term", p)
        # ...and it must stay orientation, scoped to the intro (body topics unaffected).
        self.assertIn("NOT reteaching", p)
        self.assertIn("body topics still use assumed prerequisites without definition", p)
        # the "use without definition" body-topic principle is still present (not clobbered).
        self.assertIn("without fully explaining them", p)


if __name__ == "__main__":
    unittest.main()
