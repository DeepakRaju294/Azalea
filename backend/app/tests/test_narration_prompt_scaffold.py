"""Path-A narration scaffold injection into the lean user prompt (DOMAIN_CARD_NARRATION_AND_RENDERING_SPEC §3).

A math path's process/method card should be framed with the math scaffold (Setup/Operation/Result/Why), not the
coding loop framing. The directive is injected into the lean user prompt when the math slice flag is live, and is
dark otherwise. Offline (no OpenAI call — build_lean_user_prompt is pure string assembly).
Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_narration_prompt_scaffold
"""
import os
import types
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.narration import contracts, enforce
from app.prompts.lean_lesson_prompt import build_lean_user_prompt


def _fake_math_topic():
    """A minimal Topic-like object for a math path's process_walkthrough topic (attrs read via getattr)."""
    sp = types.SimpleNamespace(goal="Learn completing the square", domain="math", topics=[])
    return types.SimpleNamespace(
        title="Steps to Complete the Square", description="", topic_type="process_walkthrough",
        course_type="process_walkthrough", study_path=sp, id="t1", purpose="", learner_outcome=None,
        in_scope=None, out_of_scope=None, modifiers=None, decomposition_metadata=None,
        assumed_prerequisites=None,
    )


class UnitDirective(unittest.TestCase):
    def test_math_directive_names_math_frames_and_forbids_loop_framing(self):
        d = contracts.process_scaffold_directive("math")
        for f in ("Setup", "Operation", "Result", "Why"):
            self.assertIn(f, d)
        self.assertIn("Repeated action", d)          # explicitly forbidden
        self.assertIn("not a running program", d)

    def test_coding_and_unknown_have_no_directive(self):
        self.assertIsNone(contracts.process_scaffold_directive("coding"))
        self.assertIsNone(contracts.process_scaffold_directive("mixed"))


class PromptInjection(unittest.TestCase):
    def setUp(self):
        self._prev = os.environ.pop(enforce._MATH_SLICE_FLAG, None)

    def tearDown(self):
        os.environ.pop(enforce._MATH_SLICE_FLAG, None)
        if self._prev is not None:
            os.environ[enforce._MATH_SLICE_FLAG] = self._prev

    def test_flag_off_is_dark(self):
        prompt = build_lean_user_prompt(_fake_math_topic(), [])
        self.assertNotIn("PROCESS/METHOD CARD FRAMES", prompt)

    def test_flag_on_injects_math_scaffold_for_math_path(self):
        os.environ[enforce._MATH_SLICE_FLAG] = "on_enforced"
        prompt = build_lean_user_prompt(_fake_math_topic(), [])
        self.assertIn("PROCESS/METHOD CARD FRAMES (math)", prompt)
        self.assertIn('"Operation"', prompt)


if __name__ == "__main__":
    unittest.main()
