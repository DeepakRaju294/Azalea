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


def _fake_science_topic():
    """A science path's science_mechanism topic (the turbulence 'Physics of Turbulence' shape)."""
    sp = types.SimpleNamespace(goal="Learn fluid turbulence", domain="science", topics=[])
    return types.SimpleNamespace(
        title="Physics of Turbulence", description="", topic_type="science_mechanism",
        course_type="science_mechanism", study_path=sp, id="t1", purpose="", learner_outcome=None,
        in_scope=None, out_of_scope=None, modifiers=None, decomposition_metadata=None,
        assumed_prerequisites=None,
    )


class SciencePromptInjection(unittest.TestCase):
    """AZALEA_NARRATION_SCIENCE_SLICE activates the science scaffold (Principle/Apply/Interpret) — path A only.

    Guards the regression where science topics kept the coding loop framing ('Repeated action / Stopping
    condition'), which produced mechanism prose like 'turbulence persists until forces stabilize it'."""

    def setUp(self):
        self._prev = {f: os.environ.pop(f, None)
                      for f in (enforce._MATH_SLICE_FLAG, enforce._SCIENCE_SLICE_FLAG)}

    def tearDown(self):
        for f, v in self._prev.items():
            os.environ.pop(f, None)
            if v is not None:
                os.environ[f] = v

    def test_science_directive_names_science_frames(self):
        d = contracts.process_scaffold_directive("science")
        for f in ("Principle", "Apply", "Interpret"):
            self.assertIn(f, d)
        self.assertIn("Repeated action", d)          # explicitly forbidden
        self.assertIn("not a running program", d)

    def test_flag_off_is_dark(self):
        prompt = build_lean_user_prompt(_fake_science_topic(), [])
        self.assertNotIn("PROCESS/METHOD CARD FRAMES", prompt)

    def test_flag_on_injects_science_scaffold_for_science_topic(self):
        os.environ[enforce._SCIENCE_SLICE_FLAG] = "on_enforced"
        prompt = build_lean_user_prompt(_fake_science_topic(), [])
        self.assertIn("PROCESS/METHOD CARD FRAMES (science)", prompt)
        self.assertIn('"Principle"', prompt)
        self.assertIn('"Interpret"', prompt)

    def test_science_flag_does_not_activate_math_paths(self):
        os.environ[enforce._SCIENCE_SLICE_FLAG] = "on_enforced"
        prompt = build_lean_user_prompt(_fake_math_topic(), [])
        self.assertNotIn("PROCESS/METHOD CARD FRAMES", prompt)

    def test_math_flag_does_not_activate_science_paths(self):
        os.environ[enforce._MATH_SLICE_FLAG] = "on_enforced"
        prompt = build_lean_user_prompt(_fake_science_topic(), [])
        self.assertNotIn("PROCESS/METHOD CARD FRAMES", prompt)

    def test_subject_agnostic_topic_on_science_path_gets_science_scaffold(self):
        """A science path's process_walkthrough resolves to science via the path domain."""
        os.environ[enforce._SCIENCE_SLICE_FLAG] = "on_enforced"
        t = _fake_science_topic()
        t.topic_type = "process_walkthrough"
        t.course_type = "process_walkthrough"
        prompt = build_lean_user_prompt(t, [])
        self.assertIn("PROCESS/METHOD CARD FRAMES (science)", prompt)

    def test_science_slice_mode_rejects_unknown_values(self):
        os.environ[enforce._SCIENCE_SLICE_FLAG] = "banana"
        self.assertEqual(enforce.science_slice_mode(), "")
        os.environ[enforce._SCIENCE_SLICE_FLAG] = "on_enforced"
        self.assertEqual(enforce.science_slice_mode(), "on_enforced")


def _fake_topic(topic_type, we_policy, science_shape=None):
    """A minimal Topic-like object carrying a certified scope_plan (attrs read via getattr)."""
    sp = types.SimpleNamespace(goal="learn fluid turbulence", domain="physics", topics=[])
    plan = {"we_policy": we_policy}
    if science_shape:
        plan["science_shape"] = science_shape
    return types.SimpleNamespace(
        title="Observable Consequences of Turbulence", description="", topic_type=topic_type,
        course_type=topic_type, study_path=sp, id="t1", purpose="", learner_outcome=None,
        in_scope=["mixing", "drag"], out_of_scope=None, modifiers=None,
        decomposition_metadata={"scope_plan": plan}, assumed_prerequisites=None,
    )


class NoCalculationGuard(unittest.TestCase):
    """36th path review: a withhold_fabricated topic with NO verified adapter — nothing to substitute
    values into — still got a process card framed as 'Identify the givens... Substitute known values...
    Compute outcomes...'. No prompt rule was gating this at all; it was purely the model's own default
    'solve for X' template. Gated on we_policy, independent of science_shape (fires for problem_solving_
    application topics too, which carry no science_shape)."""

    def test_fires_for_withhold_fabricated(self):
        prompt = build_lean_user_prompt(_fake_topic("problem_solving_application", "withhold_fabricated"), [])
        self.assertIn("No-calculation guard", prompt)

    def test_fires_for_conceptual_mechanism(self):
        prompt = build_lean_user_prompt(_fake_topic("science_mechanism", "conceptual_mechanism"), [])
        self.assertIn("No-calculation guard", prompt)

    def test_fires_for_not_applicable(self):
        prompt = build_lean_user_prompt(_fake_topic("compare_distinguish", "not_applicable"), [])
        self.assertIn("No-calculation guard", prompt)

    def test_does_not_fire_for_verified_adapter_topic(self):
        prompt = build_lean_user_prompt(_fake_topic("science_mechanism", "verified"), [])
        self.assertNotIn("No-calculation guard", prompt)

    def test_composes_with_science_shape_directive(self):
        prompt = build_lean_user_prompt(
            _fake_topic("science_mechanism", "conceptual_mechanism", science_shape="mechanism"), [])
        self.assertIn("Science lesson shape: MECHANISM", prompt)
        self.assertIn("No-calculation guard", prompt)


if __name__ == "__main__":
    unittest.main()
