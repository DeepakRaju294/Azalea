"""Wiring test: _verify_free_prose_example downgrades a wrong no-adapter worked example to guided, and keeps a
correct one. The classifier/adapter lookups are patched so the test is deterministic and offline."""
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples import solver
from app.services.examples.answer_anchor import set_answer_oracle, _default_oracle
from app.services.examples.task_classifier import WorkedExampleTask


def _determinate():
    return WorkedExampleTask(task_kind="closed_form_computation", can_construct_valid_instance=True,
                             instance_is_fixed=False, has_executable_terminal_condition=True,
                             has_independently_checkable_endpoint=True, has_unique_or_equivalent_answer=True)


class VerifyWiring(unittest.TestCase):
    def setUp(self):
        os.environ["AZALEA_WORKED_EXAMPLE_ANSWER_ANCHOR"] = "1"
        solver._ANCHOR_ORACLE_SET = True                      # skip re-registering the live oracle
        self.addCleanup(os.environ.pop, "AZALEA_WORKED_EXAMPLE_ANSWER_ANCHOR", None)
        self.addCleanup(set_answer_oracle, _default_oracle)

    def _run(self, sol):
        with patch("app.services.examples.trace_pipeline.route_adapter", return_value=None), \
             patch("app.services.examples.task_classifier.classify_worked_example_task",
                   return_value=_determinate()):
            return solver._verify_free_prose_example({"title": "Zorble Coefficient",
                                                      "course_type": "math_formula_method"}, sol)

    def test_arithmetically_inconsistent_example_is_downgraded(self):
        set_answer_oracle(lambda t, p: None)                 # no endpoint opinion; arithmetic check alone
        sol = {"problem": "compute it", "final_answer": "19/95",
               "cards": [{"points": ["P = 1900 / 11700 = 19 / 95"]}]}   # 0.162 != 0.2
        out = self._run(sol)
        self.assertEqual(out["cards"][0].get("metadata", {}).get("example", {}).get("role"), "guided")

    def test_wrong_final_answer_is_downgraded(self):
        set_answer_oracle(lambda t, p: "0.68")               # independent oracle disagrees with the example
        sol = {"problem": "compute it", "final_answer": "0.88",
               "cards": [{"points": ["P(A) = 0.48 + 0.2 + 0.2 = 0.88"]}]}   # internally consistent, but wrong
        out = self._run(sol)
        self.assertEqual(out["cards"][0].get("metadata", {}).get("example", {}).get("role"), "guided")

    def test_correct_example_is_kept_and_labeled(self):
        set_answer_oracle(lambda t, p: "0.44")               # oracle agrees
        sol = {"problem": "compute it", "final_answer": "0.44",
               "cards": [{"points": ["P(A) = 0.6*0.5 + 0.3*0.4 + 0.2*0.1 = 0.3 + 0.12 + 0.02 = 0.44"]}]}
        out = self._run(sol)
        self.assertEqual(out["final_answer"], "0.44")        # unchanged, not downgraded
        self.assertEqual(out["metadata"]["verification_level"], "answer_anchored")


if __name__ == "__main__":
    unittest.main()
