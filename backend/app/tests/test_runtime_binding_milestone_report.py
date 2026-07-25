import json
import unittest
from pathlib import Path

from app.services.examples.runtime_binding.milestone_report import build_milestone_a_report


REPO_ROOT = Path(__file__).resolve().parents[3]


class MilestoneAReportTests(unittest.TestCase):
    def test_report_is_deterministic_and_strict(self):
        first = build_milestone_a_report(REPO_ROOT).to_json(indent=None)
        second = build_milestone_a_report(REPO_ROOT).to_json(indent=None)
        self.assertEqual(first, second)
        decoded = json.loads(first)
        self.assertEqual(decoded["summary"]["invalid_rows"], 0)
        self.assertEqual(decoded["summary"]["equivalence_counts"]["failed"]["execution"], 0)
        self.assertIn(decoded["decision"], {"pass", "blocked"})

    def test_cutover_failure_and_mismatch_are_visible(self):
        report = build_milestone_a_report(REPO_ROOT)
        events = report.cutover_demonstration["events"]
        self.assertEqual([event["outcome"] for event in events], [
            "match", "match", "fallback", "quarantined",
        ])
        self.assertTrue(events[2]["alert_required"])
        self.assertEqual(events[3]["next_status"], "quarantined")


if __name__ == "__main__":
    unittest.main()
