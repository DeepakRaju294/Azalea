"""topic_quality_validator's stage_content_gap check: a "process" card content gap is promoted to error
severity (forcing requires_regeneration), unlike background/edge_case gaps which stay warning-severity and
only escalate in aggregate. Live bug (Stokes' theorem path review): a math_formula_method process card
shipped with only "identify the vector field" — missing the formula/substitution/interpretation stages
entirely — correctly flagged by the validator but never strong enough on its own to trigger a retry.

Tests call validate_stage_rule_compliance directly (not the full validate_generated_topic pipeline) so
they isolate this one check from the many unrelated checks (card titles, practice question types, blueprint
coverage) that would otherwise need a fully-realistic fixture just to stay quiet — and a separate small
class checks build_report's requires_regeneration allowlist directly.

Written as a new, isolated file (not test_course_type_system.py) per the standing .env-contamination
landmine note: importing routes leaks AZALEA_* flags across tests; this imports the validator service
directly.

Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_stage_content_gap_severity
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.topic_quality_validator import build_report, validate_stage_rule_compliance

_MATH_SEQUENCE = ["background", "formula_breakdown", "components_terms", "process", "worked_example",
                  "edge_case", "practice"]

# Real live shape (Stokes' path review): only "identify" is covered, formula/substitute/compute/interpret
# are entirely absent — missing 3 of 5 expectations, well over the >=2 gap threshold.
_THIN_PROCESS = [{"blueprint_key": "process", "points": [
    "Identify the vector field F relevant to your problem:", "  - Know the components vital for integration."]}]

_FULL_PROCESS = [{"blueprint_key": "process", "points": [
    "Identify the givens: the vector field F and the curve C to integrate along.",
    "State the formula that applies: the line integral of F along C, valid when F is continuous on C.",
    "Substitute the known values into the formula using the curve's parameterization.",
    "Compute and simplify the resulting integral to reach the numeric result.",
    "Interpret the result — what the computed value represents for this vector field and curve.",
]}]

_THIN_BACKGROUND = [{"blueprint_key": "background", "points": ["Line integrals exist."]}]


def _gap_for(cards, blueprint_key):
    issues: list = []
    validate_stage_rule_compliance(cards, _MATH_SEQUENCE, "math_formula_method", issues,
                                    require_microchecks_and_visuals=False)
    return next((i for i in issues if i.get("code") == "stage_content_gap"
                and i["details"]["blueprint_key"] == blueprint_key), None)


class ProcessCardGapIsError(unittest.TestCase):
    def test_thin_process_card_is_flagged_as_error(self):
        gap = _gap_for(_THIN_PROCESS, "process")
        self.assertIsNotNone(gap, "expected a stage_content_gap issue for the thin process card")
        self.assertEqual(gap["severity"], "error")

    def test_well_filled_process_card_has_no_gap(self):
        self.assertIsNone(_gap_for(_FULL_PROCESS, "process"))


class OtherCardGapsStayWarning(unittest.TestCase):
    def test_background_gap_stays_warning(self):
        gap = _gap_for(_THIN_BACKGROUND, "background")
        self.assertIsNotNone(gap, "expected a stage_content_gap issue for the thin background card")
        self.assertEqual(gap["severity"], "warning")


class RequiresRegenerationAllowlist(unittest.TestCase):
    """build_report only flips requires_regeneration for an allow-listed set of error-severity codes —
    stage_content_gap is now in that set, but ONLY takes effect at error severity (i.e. for "process")."""

    def test_error_severity_stage_content_gap_forces_regeneration(self):
        report = build_report([{"severity": "error", "code": "stage_content_gap", "message": "m", "details": {}}])
        self.assertTrue(report["requires_regeneration"])

    def test_warning_severity_stage_content_gap_does_not_force_regeneration(self):
        report = build_report([{"severity": "warning", "code": "stage_content_gap", "message": "m", "details": {}}])
        self.assertFalse(report["requires_regeneration"])


if __name__ == "__main__":
    unittest.main()
