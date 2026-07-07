"""Q24 free-text shadow hook (FREE_TEXT_CONTENT_VALIDATION_SPEC.md §5).

Verifies the generation hook is a strict no-op until a family is enrolled, measures the false-claim rate when
enrolled, and NEVER mutates the card plan. Tests the hook module directly (importing lean_lesson_generator would
trip the .env/load_dotenv landmine). Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_free_text_shadow
"""
import copy
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.free_text import shadow
from app.services.narration import rollout


class FreeTextShadowHook(unittest.TestCase):
    def setUp(self):
        self._orig_path = shadow._TELEMETRY_PATH
        shadow._TELEMETRY_PATH = os.devnull

    def tearDown(self):
        shadow._TELEMETRY_PATH = self._orig_path
        rollout._FAMILY_MODES.clear()   # don't leak family enrollment across tests

    def _card(self):
        return {"card_type": "concept_intuition",
                "explanation": "Squaring both sides of x² = −4 gives x² = 0.",
                "body": ["A quadratic can have no real solution."]}

    def test_strict_noop_when_not_enrolled(self):
        # default off_legacy → no report, no evaluation
        report = shadow.evaluate_card_plan("math_formula_method", [self._card()])
        self.assertIsNone(report)

    def test_non_gating_domain_is_noop(self):
        rollout.set_family_mode("math", "concept_intuition", rollout.SHADOW_VALIDATE)
        self.assertIsNone(shadow.evaluate_card_plan(None, [self._card()]))

    def test_measures_false_claim_when_enrolled(self):
        rollout.set_family_mode("math", "concept_intuition", rollout.SHADOW_VALIDATE)
        cards = [self._card()]
        before = copy.deepcopy(cards)
        report = shadow.evaluate_card_plan("math_formula_method", cards)
        self.assertIsNotNone(report)
        self.assertEqual(report["domain"], "math")
        # the false transformation is counted as an L2 refutation
        total_refuted = sum(f["summary"]["l2_refuted"] for f in report["fields"])
        self.assertGreaterEqual(total_refuted, 1)
        # the hook NEVER mutates the plan (shadow)
        self.assertEqual(cards, before)

    def test_telemetry_rows_carry_failure_stage(self):
        rollout.set_family_mode("math", "concept_intuition", rollout.SHADOW_VALIDATE)
        report = shadow.evaluate_card_plan("math_formula_method", [self._card()])
        stages = [row.get("transformation_failure_stage")
                  for f in report["fields"] for row in f["claims"]]
        self.assertIn("target_conformance", stages)


if __name__ == "__main__":
    unittest.main()
