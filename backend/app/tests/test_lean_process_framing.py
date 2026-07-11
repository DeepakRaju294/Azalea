"""The lean lesson prompt must carve out a FORMULA/calculation exception to the algorithm loop-scaffold
framing — a one-shot formula application (Ohm's law, kinetic energy) has no iteration or termination, so it
must use calculation stages, not "Starting state / Repeated action / Stopping condition". Fixes the robotic
process card seen when a formula concept is decomposed as science_mechanism."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.prompts.lean_lesson_prompt import build_lean_system_prompt


class LeanProcessFraming(unittest.TestCase):
    def test_prompt_has_formula_calculation_exception(self):
        p = build_lean_system_prompt(omit_worked_example=False)
        # the loop-scaffold instruction still exists (algorithms need it)...
        self.assertIn("Starting state", p)
        # ...but a formula/calculation card is explicitly exempted and pointed at calculation stages.
        self.assertIn("FORMULA / one-shot CALCULATION", p)
        self.assertIn("do NOT use the", p)
        for stage in ("identify the givens", "state the formula", "substitute", "compute", "interpret"):
            self.assertIn(stage, p)


if __name__ == "__main__":
    unittest.main()
