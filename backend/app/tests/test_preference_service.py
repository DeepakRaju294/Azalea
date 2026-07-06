"""Phase-1 preference resolver (ONBOARDING_AND_PREFERENCE_CAPTURE_SPEC §3, D1).

Covers the PURE precedence logic `path override > user default > inferred > platform default` and the language
active/inactive split. The DB snapshot writer is exercised via integration (needs Postgres/JSONB), not here.

Run: python -m unittest app.tests.test_preference_service
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.preference_service import (
    PROV_INFERRED, PROV_SAVED_DEFAULT, PROV_SYSTEM_DEFAULT, PROV_USER_SELECTED,
    contract_versions, resolve_preferences,
)


class ResolvePreferences(unittest.TestCase):
    def test_coding_defaults(self):
        selected, effective, prov = resolve_preferences(domain="coding")
        self.assertEqual(effective["domain"], "coding")
        self.assertEqual(prov["domain"], PROV_INFERRED)               # classifier seed, no confirmation surface
        self.assertEqual(effective["depth_level"], "working")
        self.assertEqual(prov["depth_level"], PROV_SYSTEM_DEFAULT)
        self.assertEqual(effective["language"], "python")
        self.assertEqual(effective["language_status"], "active_coding")
        self.assertEqual(prov["language"], PROV_SYSTEM_DEFAULT)        # bare default python is NOT a selection
        self.assertEqual(selected, {})

    def test_non_coding_language_inactive(self):
        _, effective, prov = resolve_preferences(domain="math", path_language="java")
        self.assertIsNone(effective["language"])                      # language had NO effect on a math path
        self.assertEqual(effective["language_status"], "inactive_non_coding")

    def test_explicit_path_language_is_a_selection(self):
        _, effective, prov = resolve_preferences(domain="coding", path_language="java")
        self.assertEqual(effective["language"], "java")
        self.assertEqual(prov["language"], PROV_USER_SELECTED)

    def test_user_default_depth_wins_over_platform(self):
        _, effective, prov = resolve_preferences(domain="physics", user_default_depth="deep")
        self.assertEqual(effective["depth_level"], "deep")
        self.assertEqual(prov["depth_level"], PROV_SAVED_DEFAULT)

    def test_selected_overrides_user_default(self):
        _, effective, prov = resolve_preferences(
            domain="coding", user_default_depth="deep", selected={"depth_level": "intuition"})
        self.assertEqual(effective["depth_level"], "intuition")
        self.assertEqual(prov["depth_level"], PROV_USER_SELECTED)

    def test_selected_domain_override(self):
        _, effective, prov = resolve_preferences(domain="coding", selected={"domain": "math"})
        self.assertEqual(effective["domain"], "math")
        self.assertEqual(prov["domain"], PROV_USER_SELECTED)

    def test_knowledge_level_always_inactive(self):
        _, effective, prov = resolve_preferences(domain="coding", user_default_knowledge=3)
        self.assertIsNone(effective["knowledge_level"])
        self.assertIn("knowledge_level", effective["inactive_fields"])
        self.assertEqual(prov["knowledge_level"], "phase_2_consumer_not_live")

    def test_contract_versions_shape(self):
        cv = contract_versions()
        for k in ("gate_version", "rewrite_version", "classifier_version", "preference_schema_version"):
            self.assertIn(k, cv)

    def test_schema_version_mirror_matches_model(self):
        # the service mirrors the constant lazily to avoid an import cycle — assert it never drifts
        import app.db.base  # ensure base is loaded before importing the model directly
        from app.models.preferences import PREFERENCE_SCHEMA_VERSION
        self.assertEqual(contract_versions()["preference_schema_version"], PREFERENCE_SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
