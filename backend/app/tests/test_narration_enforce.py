"""Phase-2B on_enforced DISPLAY step (DOMAIN_CARD_NARRATION_AND_RENDERING_SPEC §9.1).

Fully offline. Verifies the enforce step is a strict no-op until a math family is enrolled, that it applies the
terminal_not_narrated rule + framing metadata when enrolled, that it is math-scoped (coding untouched), and that
a not-ready enrolled card falls back to legacy display (never a broken withhold).
Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_narration_enforce
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.narration import enforce, rollout

_MATH_TOPIC = "math_formula_method"     # → narration domain "math"
_CODING_TOPIC = "algorithm_walkthrough"  # → narration domain "coding"

# The robotic narrated-terminal wrapper trace_pipeline appends; math result lines are terminal, not narrated.
_NARRATED = "(x + 3)^2 - 9. Complete: the conclusion is reached. Final result: (x + 3)^2 - 9."


def _we_card() -> dict:
    return {"blueprint_key": "worked_example", "title": "Difference of squares",
            "result": _NARRATED, "points": ["We factor.", "Total. Complete: done. Final result: 5."]}


class EnforceDisplayStep(unittest.TestCase):
    def setUp(self):
        rollout._FAMILY_MODES.clear()   # isolate: no family enrolled by default

    def tearDown(self):
        rollout._FAMILY_MODES.clear()

    def test_default_is_a_strict_noop(self):
        card = _we_card()
        out = enforce.apply_enforced_narration(_MATH_TOPIC, [card])
        self.assertIs(out[0], card)
        self.assertNotIn("narration_mode", card)       # untouched
        self.assertIn("Complete:", card["result"])     # wrapper NOT stripped when not enrolled

    def test_enrolled_math_card_gets_terminal_rule_and_framing(self):
        rollout.set_family_mode("math", "worked_example", rollout.ON_ENFORCED)
        card = _we_card()
        enforce.apply_enforced_narration(_MATH_TOPIC, [card])
        # terminal_not_narrated: the robotic "Complete: … Final result: …" wrapper is gone, answer preserved.
        self.assertNotIn("Complete:", card["result"])
        self.assertIn("(x + 3)^2 - 9", card["result"])
        self.assertNotIn("Complete:", card["points"][1])
        self.assertEqual(card["points"][1], "Total.")
        # framing metadata attached (additive, for the renderer) + mode recorded.
        self.assertEqual(card["narration_mode"], rollout.ON_ENFORCED)
        self.assertEqual(card["narration"]["domain"], "math")
        self.assertEqual(card["narration"]["result_line_rule"], "terminal_not_narrated")
        self.assertEqual(card["narration"]["process_scaffold"], ["Setup", "Operation", "Result", "Why"])

    def test_math_scoped_coding_untouched(self):
        # even with a coding family enrolled, v1 only enforces the math slice.
        rollout.set_family_mode("coding", "worked_example", rollout.ON_ENFORCED)
        card = {"blueprint_key": "worked_example", "result": _NARRATED}
        enforce.apply_enforced_narration(_CODING_TOPIC, [card])
        self.assertNotIn("narration_mode", card)
        self.assertIn("Complete:", card["result"])     # coding keeps its narrated completion (test_c4_completion)

    def test_not_ready_enrolled_card_falls_back_not_withheld(self):
        # an unmapped card in an enrolled family is not ready → legacy fallback, content untouched (no withhold).
        rollout.set_family_mode("math", "mystery_card", rollout.ON_ENFORCED)
        card = {"blueprint_key": "mystery_card", "result": _NARRATED}
        enforce.apply_enforced_narration(_MATH_TOPIC, [card])
        self.assertEqual(card["narration_mode"], "legacy_fallback")
        self.assertIn("Complete:", card["result"])     # legacy display preserved, not stripped, not dropped
        self.assertNotIn("narration", card)

    def test_math_path_process_topic_resolves_to_math(self):
        # the reviewed bug: a math path's worked example lives under a process_walkthrough topic, which maps to
        # concept by topic type alone. With the path's subject domain threaded, it now resolves to math and the
        # math contract is enforced.
        rollout.set_family_mode("math", "worked_example", rollout.ON_ENFORCED)
        card = _we_card()
        enforce.apply_enforced_narration("process_walkthrough", [card], path_domain="math")
        self.assertEqual(card["narration_mode"], rollout.ON_ENFORCED)
        self.assertNotIn("Complete:", card["result"])

    def test_process_topic_without_path_domain_stays_concept(self):
        # without a math path domain, process_walkthrough → concept → math-scoped enforce is a no-op.
        rollout.set_family_mode("math", "worked_example", rollout.ON_ENFORCED)
        card = _we_card()
        enforce.apply_enforced_narration("process_walkthrough", [card])
        self.assertNotIn("narration_mode", card)

    def test_clean_terminal_is_preserved(self):
        # the terse "This is the final result." (already clean) must NOT be stripped.
        rollout.set_family_mode("math", "worked_example", rollout.ON_ENFORCED)
        card = {"blueprint_key": "worked_example", "result": "(x - 4)(x + 4). This is the final result."}
        enforce.apply_enforced_narration(_MATH_TOPIC, [card])
        self.assertIn("This is the final result.", card["result"])


class SurgicalActivation(unittest.TestCase):
    def setUp(self):
        rollout._FAMILY_MODES.clear()
        self._prev = os.environ.pop(enforce._MATH_SLICE_FLAG, None)

    def tearDown(self):
        rollout._FAMILY_MODES.clear()
        os.environ.pop(enforce._MATH_SLICE_FLAG, None)
        if self._prev is not None:
            os.environ[enforce._MATH_SLICE_FLAG] = self._prev

    def test_flag_unset_is_dark(self):
        enforce.enroll_audited_math_slice()
        self.assertEqual(rollout._FAMILY_MODES, {})

    def test_flag_enrolls_only_the_audited_slice(self):
        os.environ[enforce._MATH_SLICE_FLAG] = "on_enforced"
        enforce.enroll_audited_math_slice()
        self.assertEqual(rollout.resolve_mode("math", "worked_example"), rollout.ON_ENFORCED)
        self.assertEqual(rollout.resolve_mode("math", "formula_breakdown"), rollout.ON_ENFORCED)
        # NOT the whole domain — an unaudited math card type + other domains stay off_legacy.
        self.assertEqual(rollout.resolve_mode("math", "background"), rollout.OFF_LEGACY)
        self.assertEqual(rollout.resolve_mode("coding", "worked_example"), rollout.OFF_LEGACY)


if __name__ == "__main__":
    unittest.main()
