"""Shadow measurement — aggregator + driver (authorizes on_enforced).

Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_shadow_metrics
"""
import json
import os
import tempfile
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services import shadow_harness, shadow_metrics
from app.services.trace_teaching import grammar


class Aggregator(unittest.TestCase):
    def test_free_text_violation_rate_and_reasons(self):
        record = {"domain": "math", "fields": [{"claims": [
            {"action": "delete", "transformation_failure_stage": "target_conformance", "l2_verdict": "refuted"},
            {"action": "ship"},
            {"action": "withhold_field", "l4": "unsupported"},
        ]}]}
        r = shadow_metrics.aggregate([(shadow_metrics.FREE_TEXT, record)])
        d = r.domains["math"]
        self.assertEqual(d.units, 3)
        self.assertEqual(d.violations, 2)
        self.assertAlmostEqual(d.violation_rate, 2 / 3)
        self.assertEqual(d.by_reason["l2:target_conformance"], 1)
        self.assertEqual(d.by_reason["l4:unsupported"], 1)

    def test_trace_teaching_violation_aggregation(self):
        record = {"domain": "coding", "fields": [
            {"decision": "withhold", "failures": ["C1"]},
            {"decision": "pass", "failures": []},
        ]}
        r = shadow_metrics.aggregate([(shadow_metrics.TRACE_TEACHING, record)])
        d = r.domains["coding"]
        self.assertEqual(d.units, 2)
        self.assertEqual(d.violations, 1)
        self.assertEqual(d.by_reason["trace:C1"], 1)

    def test_enforce_ready_verdict(self):
        clean = {"domain": "math", "fields": [{"claims": [{"action": "ship"}, {"action": "ship"}]}]}
        dirty = {"domain": "science", "fields": [{"claims": [{"action": "delete"}, {"action": "ship"}]}]}
        r = shadow_metrics.aggregate([(shadow_metrics.FREE_TEXT, clean), (shadow_metrics.FREE_TEXT, dirty)])
        self.assertTrue(r.enforce_ready("math"))              # 0% → ready
        self.assertFalse(r.enforce_ready("science"))          # 50% → not ready
        self.assertFalse(r.enforce_ready("unmeasured"))       # never measured → not ready
        self.assertTrue(r.enforce_ready("science", threshold=0.6))   # tolerant threshold

    def test_load_and_aggregate_files(self):
        rec = {"domain": "math", "fields": [{"claims": [{"action": "delete"}]}]}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ft.jsonl")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n\n")   # blank line tolerated
            r = shadow_metrics.aggregate_files(free_text_path=path)
            self.assertEqual(r.domains["math"].violations, 1)


class Driver(unittest.TestCase):
    def test_measures_false_transformation_over_fixture_plan(self):
        bad = ("math_formula_method",
               [{"card_type": "concept_intuition", "explanation": "Squaring both sides of x² = −4 gives x² = 0."}])
        report = shadow_harness.evaluate(free_text_plans=[bad], enroll=[("math", "concept_intuition")])
        d = report.domains["math"]
        self.assertGreaterEqual(d.violations, 1)
        self.assertFalse(report.enforce_ready("math"))
        self.assertTrue(any(k.startswith("l2:") for k in d.by_reason))

    def test_clean_framing_plan_is_enforce_ready(self):
        clean = ("math_formula_method",
                 [{"card_type": "concept_intuition", "explanation": "This is genuinely worth appreciating."}])
        report = shadow_harness.evaluate(free_text_plans=[clean], enroll=[("math", "concept_intuition")])
        self.assertTrue(report.enforce_ready("math"))

    def test_trace_plan_violation_measured(self):
        steps = {"s3": grammar.Step(id="s3", operation="compute", allowed_values=("4", "5", "20"))}
        cards = [{"card_type": "worked_example", "trace_step_ids": ["s3"], "points": ["the net force is 25 N"]}]
        report = shadow_harness.evaluate(
            trace_plans=[("t1", cards, steps, "coding", "worked_example")],
            enroll=[("coding", "worked_example")])
        self.assertGreaterEqual(report.domains["coding"].violations, 1)

    def test_driver_does_not_leak_enrollment_or_write_logs(self):
        from app.services.narration import rollout
        before = dict(rollout._FAMILY_MODES)
        shadow_harness.evaluate(
            free_text_plans=[("math_formula_method",
                              [{"card_type": "concept_intuition", "explanation": "worth appreciating."}])],
            enroll=[("math", "concept_intuition")])
        self.assertEqual(rollout._FAMILY_MODES, before)   # global enrollment restored


if __name__ == "__main__":
    unittest.main()
