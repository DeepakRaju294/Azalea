"""Math method/process cards must not borrow the algorithm 'starting state / stopping condition' scaffold —
a formula application is a one-shot calculation, not a loop. Algorithm types keep the loop framing."""
import unittest

from app.core.course_stage_rules import STAGE_RULES


def _process_text(topic_type: str) -> str:
    rule = STAGE_RULES.get(topic_type, {}).get("process", {})
    parts = list(rule.get("content") or [])
    parts += list(rule.get("notes") or [])
    return " ".join(parts).lower()


_ALGO_FRAMES = ("starting state", "repeated action", "stopping condition", "output rule")


class MathProcessFraming(unittest.TestCase):
    def test_math_formula_method_uses_calculation_framing(self):
        txt = _process_text("math_formula_method")
        self.assertIn("substitute", txt)
        self.assertIn("interpret", txt)
        # the algorithm frames only appear in the negative instruction ("do NOT use ...") — never as bullets
        content = " ".join(STAGE_RULES["math_formula_method"]["process"].get("content") or []).lower()
        for frame in _ALGO_FRAMES:
            self.assertNotIn(frame, content, f"{frame!r} should not be a math process bullet")

    def test_problem_solving_application_uses_calculation_framing(self):
        content = " ".join(STAGE_RULES["problem_solving_application"]["process"].get("content") or []).lower()
        self.assertIn("substitute", content)
        for frame in _ALGO_FRAMES:
            self.assertNotIn(frame, content)

    def test_algorithm_walkthrough_keeps_loop_framing(self):
        content = " ".join(STAGE_RULES["algorithm_walkthrough"]["process"].get("content") or []).lower()
        self.assertIn("repeated action", content)      # algorithms still describe iteration
        self.assertIn("stopping condition", content)


if __name__ == "__main__":
    unittest.main()
