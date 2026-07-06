"""Phase-2B shadow evaluation (DOMAIN_CARD_NARRATION_AND_RENDERING_SPEC §9.1).

The shadow orchestrator runs the eligibility gate over a finalized card plan and emits telemetry WITHOUT changing
output — and is a STRICT no-op in the default off_legacy config (zero production impact).

Run: python -m unittest app.tests.test_narration_shadow
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")
os.environ["AZALEA_NARRATION_SHADOW_PATH"] = os.devnull  # never write a real telemetry log in tests

from app.services.narration import rollout, shadow


def _cards(*keys):
    return [{"blueprint_key": k} for k in keys]


class ShadowEvaluation(unittest.TestCase):
    def setUp(self):
        os.environ.pop(rollout._ENV_FLAG, None)
        rollout._FAMILY_MODES.clear()

    def tearDown(self):
        os.environ.pop(rollout._ENV_FLAG, None)
        rollout._FAMILY_MODES.clear()

    def test_default_off_legacy_is_noop(self):
        # unset flag ⇒ every card off_legacy ⇒ strict no-op (returns None, writes nothing)
        self.assertIsNone(shadow.evaluate_card_plan("math_formula_method", _cards("process", "worked_example")))

    def test_shadow_validate_emits_decisions(self):
        os.environ[rollout._ENV_FLAG] = "shadow_validate"
        report = shadow.evaluate_card_plan(
            "math_formula_method", _cards("process", "worked_example", "complexity_analysis"))
        self.assertIsNotNone(report)
        self.assertEqual(report["narration_domain"], "math")
        actions = {d["card_type"]: d["action"] for d in report["decisions"]}
        self.assertEqual(actions["process"], "proceed")
        self.assertEqual(actions["worked_example"], "proceed")
        self.assertEqual(actions["complexity_analysis"], "safety_failure")   # not_applicable on math

    def test_formula_breakdown_proceeds_on_math(self):
        os.environ[rollout._ENV_FLAG] = "shadow_validate"
        report = shadow.evaluate_card_plan("math_formula_method", _cards("formula_breakdown"))
        actions = {d["card_type"]: d["action"] for d in report["decisions"]}
        self.assertEqual(actions["formula_breakdown"], "proceed")

    def test_domain_derivation_from_topic_type(self):
        self.assertEqual(shadow.narration_domain_for_topic_type("algorithm_walkthrough"), "coding")
        self.assertEqual(shadow.narration_domain_for_topic_type("science_mechanism"), "science")
        self.assertIsNone(shadow.narration_domain_for_topic_type("nonexistent_type"))

    def test_unmapped_topic_type_is_noop(self):
        os.environ[rollout._ENV_FLAG] = "shadow_validate"
        self.assertIsNone(shadow.evaluate_card_plan("nonexistent_type", _cards("process")))

    def test_family_override_enables_shadow_without_global_flag(self):
        # a per-family override alone (global still off_legacy) is enough to enroll that card
        rollout.set_family_mode("coding", "worked_example", rollout.SHADOW_VALIDATE)
        report = shadow.evaluate_card_plan("algorithm_walkthrough", _cards("worked_example", "process"))
        self.assertIsNotNone(report)
        keys = {d["card_type"] for d in report["decisions"]}
        self.assertEqual(keys, {"worked_example"})   # only the enrolled card is evaluated; process stays off_legacy


if __name__ == "__main__":
    unittest.main()
