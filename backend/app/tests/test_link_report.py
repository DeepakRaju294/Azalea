"""One canonical interactive-link report (link_report.py): single key, single shape, written by the lean
pipeline, the legacy validator, and core-text-only mode — replacing the two competing report names the
external review flagged (`interactive_link_validation_report` vs `interactive_link_report`)."""
import unittest

from app.services.interactive_link_validation import validate_and_repair_interactive_links
from app.services.link_report import LINK_REPORT_KEY, build_link_report


class BuildLinkReport(unittest.TestCase):
    def test_counts_by_action_and_totals(self):
        cards = [
            {"interactive_links": [
                {"text": "a", "action": "open_study_path", "target": "t"},
                {"text": "b", "action": "review_earlier_topic", "target": "x"}]},
            {"interactive_links": [{"text": "c", "action": "popup_only", "explanation": "e"}]},
            {"interactive_links": []},
        ]
        r = build_link_report(cards, source="lean_emission", removed_count=2)
        self.assertTrue(r["is_valid"] and r["passed"])          # both status aliases agree
        self.assertEqual(r["kept_count"], 3)
        self.assertEqual(r["generated_count"], 5)               # kept + removed
        self.assertEqual(r["removed_link_count"], 2)            # legacy field kept for quality validator
        self.assertEqual(r["counts_by_action"],
                         {"open_study_path": 1, "review_earlier_topic": 1, "popup_only": 1})
        self.assertEqual(r["contract"], "prereq_links_v1")

    def test_issues_flip_validity(self):
        r = build_link_report(None, source="legacy_validator", issues=["bad"])
        self.assertFalse(r["is_valid"])
        self.assertFalse(r["passed"])

    def test_legacy_validator_writes_canonical_key_and_shape(self):
        lesson = {"lesson_cards": [
            {"main_concept": "X", "interactive_links": [
                {"text": "vectors", "explanation": "", "action": "open_study_path",
                 "target": "t", "concept_id": "vectors"}]},
        ]}
        report = validate_and_repair_interactive_links(lesson)
        self.assertIs(lesson[LINK_REPORT_KEY], report)
        self.assertIn("is_valid", report)
        self.assertIn("counts_by_action", report)
        self.assertEqual(report["source"], "legacy_validator")
        # ...and the nav link survived with its identity (the c0f3cd7 contract)
        kept = lesson["lesson_cards"][0]["interactive_links"]
        self.assertEqual(kept[0]["concept_id"], "vectors")


if __name__ == "__main__":
    unittest.main()
