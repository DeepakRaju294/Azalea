import os
from types import SimpleNamespace
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")


class TurbulenceScopeCoverageTests(unittest.TestCase):
    def test_name_drops_do_not_satisfy_owned_application_scope(self):
        from app.services.scope_validator import validate_owned_scope_coverage

        cards = [
            {
                "blueprint_key": "background",
                "points": [
                    "Applications include aerodynamic drag, industrial mixing, and natural bodies of water."
                ],
            },
            {
                "blueprint_key": "process",
                "points": ["Use vehicle shape and speed to reason about aerodynamic drag."],
            },
        ]
        contract = {
            "owned_scope_content": [
                "aerodynamic drag in vehicles",
                "mixing processes in industrial applications",
                "turbulent flow in natural bodies of water",
            ]
        }
        issues = validate_owned_scope_coverage(cards, contract)
        self.assertFalse(any("aerodynamic drag" in issue for issue in issues))
        self.assertTrue(any("mixing processes" in issue for issue in issues))
        self.assertTrue(any("natural bodies" in issue for issue in issues))

    def test_mechanism_process_covers_energy_cascade_commitments(self):
        from app.services.scope_validator import validate_owned_scope_coverage

        cards = [{
            "blueprint_key": "process",
            "points": [
                "Large eddies receive and carry turbulent kinetic energy.",
                "Nonlinear eddy interactions transfer energy to progressively smaller scales.",
                "At the smallest scales, viscosity converts turbulent kinetic energy into heat.",
            ],
        }]
        contract = {"owned_scope_content": [
            "role of large eddies in energy transfer",
            "how energy cascades to smaller scales",
            "the eventual dissipation via viscosity",
        ]}
        self.assertEqual(validate_owned_scope_coverage(cards, contract), [])

    def test_lean_pipeline_no_longer_stamps_missing_practice_as_valid(self):
        from app.services.lean_lesson_generator import _attach_lean_validation_reports

        topic = SimpleNamespace(
            title="Real-World Applications of Turbulence",
            purpose="Apply turbulence concepts",
            learner_outcome="Analyze turbulence applications",
            course_type="problem_solving_application",
            topic_type="problem_solving_application",
            secondary_course_types=[],
            in_scope=["aerodynamic drag in vehicles", "industrial mixing"],
            out_of_scope=[],
            assumed_prerequisites=[],
            prerequisite_topics=None,
            decomposition_metadata={},
            study_path=None,
        )
        lesson = {
            "lesson_cards": [
                {"blueprint_key": "background", "card_type": "purpose_context", "points": ["Why it matters"]},
                {"blueprint_key": "process", "card_type": "method_process", "points": ["Analyze drag"]},
            ],
            "practice_questions": [],
            "visual_validation_report": {"requires_regeneration": False, "issues": []},
        }
        _attach_lean_validation_reports(lesson, topic)
        self.assertTrue(lesson["practice_quality_report"]["requires_regeneration"])
        self.assertTrue(lesson["validation_report"]["requires_regeneration"])


if __name__ == "__main__":
    unittest.main()
