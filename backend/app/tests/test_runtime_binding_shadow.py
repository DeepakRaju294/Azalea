import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.examples.runtime_binding.shadow import summarize_shadow_events
from app.services.examples.trace_adapters.decl import hydrate
from app.services.examples.trace_adapters.families.formula_engine import formula_decl
from app.services.examples.trace_adapters.families.formula_specs import DENSITY, PYTHAGOREAN
from app.services.examples.trace_pipeline import select_instance


class RuntimeBindingShadowTests(unittest.TestCase):
    def test_shadow_is_off_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "shadow.jsonl"
            with patch.dict(os.environ, {
                "AZALEA_T6_SUBSTRATE_SHADOW": "off",
                "AZALEA_T6_SUBSTRATE_SHADOW_PATH": str(path),
            }, clear=False):
                self.assertIsNotNone(select_instance(hydrate(formula_decl(DENSITY)), 1))
            self.assertFalse(path.exists())

    def test_eligible_and_blocked_formula_executions_are_counted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "shadow.jsonl"
            with patch.dict(os.environ, {
                "AZALEA_T6_SUBSTRATE_SHADOW": "observe",
                "AZALEA_T6_SUBSTRATE_SHADOW_PATH": str(path),
                "AZALEA_T6_SUBSTRATE_SHADOW_SAMPLE_RATE": "1",
            }, clear=False):
                self.assertIsNotNone(select_instance(hydrate(formula_decl(DENSITY)), 1))
                self.assertIsNotNone(select_instance(hydrate(formula_decl(PYTHAGOREAN)), 1))
            events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([event["formula_slug"] for event in events], ["density", "pythagorean"])
            self.assertTrue(events[0]["eligible"])
            self.assertTrue(events[0]["execution_match"])
            self.assertFalse(events[1]["eligible"])
            summary = summarize_shadow_events(path)
            self.assertEqual(summary["total_formula_executions"], 2)
            self.assertEqual(summary["eligible_formula_executions"], 1)
            self.assertEqual(summary["eligible_execution_percent"], 50.0)
            self.assertEqual(summary["execution_mismatches"], 0)
            self.assertEqual(summary["comparison_samples"], 2)
            self.assertIsNotNone(summary["comparison_latency_p95_ms"])

    def test_zero_sample_rate_records_volume_without_executing_substrate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "shadow.jsonl"
            with patch.dict(os.environ, {
                "AZALEA_T6_SUBSTRATE_SHADOW": "observe",
                "AZALEA_T6_SUBSTRATE_SHADOW_PATH": str(path),
                "AZALEA_T6_SUBSTRATE_SHADOW_SAMPLE_RATE": "0",
            }, clear=False):
                self.assertIsNotNone(select_instance(hydrate(formula_decl(DENSITY)), 1))
            event = json.loads(path.read_text(encoding="utf-8").strip())
            self.assertTrue(event["eligible"])
            self.assertFalse(event["comparison_sampled"])
            self.assertFalse(event["substrate_executed"])


if __name__ == "__main__":
    unittest.main()
