"""Example System — Phase 0: the ontology is pure data and internally consistent,
and every tandem visual pair is real in the visual ontology.

Run: python -m unittest app.tests.test_example_ontology   (from backend/, PYTHONPATH=.)
"""
from __future__ import annotations

import unittest

from app.core import example_ontology as eo
from app.core.visual_ontology_v2 import MODES_BY_BASE_TYPE


class TestOntologyShape(unittest.TestCase):
    def test_twelve_types(self):
        self.assertEqual(len(eo.EXAMPLE_TYPES), 12)
        self.assertEqual(len(set(eo.EXAMPLE_TYPES)), 12)  # no dupes

    def test_every_type_dict_covers_all_types(self):
        types = set(eo.EXAMPLE_TYPES)
        for name, d in (
            ("APPLICATIONS_BY_TYPE", eo.APPLICATIONS_BY_TYPE),
            ("EXAMPLE_TYPE_DESCRIPTIONS", eo.EXAMPLE_TYPE_DESCRIPTIONS),
            ("EXAMPLE_TYPE_TO_DEFAULT_VISUAL", eo.EXAMPLE_TYPE_TO_DEFAULT_VISUAL),
            ("STEP_ROLES_BY_EXAMPLE_TYPE", eo.STEP_ROLES_BY_EXAMPLE_TYPE),
        ):
            self.assertEqual(set(d) - types, set(), f"{name} has unknown types")
            self.assertEqual(types - set(d), set(), f"{name} missing types")

    def test_no_duplicate_applications_within_a_type(self):
        for t, apps in eo.APPLICATIONS_BY_TYPE.items():
            self.assertEqual(len(apps), len(set(apps)), f"dup application in {t}")

    def test_every_application_has_a_description(self):
        missing = [
            app
            for apps in eo.APPLICATIONS_BY_TYPE.values()
            for app in apps
            if app not in eo.APPLICATION_DESCRIPTIONS
        ]
        self.assertEqual(missing, [], f"applications without a description: {missing}")

    def test_step_roles_nonempty(self):
        for t, roles in eo.STEP_ROLES_BY_EXAMPLE_TYPE.items():
            self.assertTrue(roles, f"{t} has no step roles")
            self.assertEqual(len(roles), len(set(roles)), f"dup step role in {t}")


class TestTandemVisualPairsAreReal(unittest.TestCase):
    def test_default_visual_pairs_exist_in_visual_ontology(self):
        for example_type, (base_type, mode) in eo.EXAMPLE_TYPE_TO_DEFAULT_VISUAL.items():
            self.assertIn(base_type, MODES_BY_BASE_TYPE, f"{example_type}: unknown base_type {base_type}")
            self.assertIn(
                mode, MODES_BY_BASE_TYPE[base_type],
                f"{example_type}: mode {mode} not under base_type {base_type}",
            )


class TestHelpers(unittest.TestCase):
    def test_is_valid_example_type(self):
        self.assertTrue(eo.is_valid_example_type("sequence_state_trace"))
        self.assertFalse(eo.is_valid_example_type("nope"))

    def test_is_valid_application_and_owner(self):
        self.assertTrue(eo.is_valid_application("binary_search"))
        self.assertEqual(eo.example_type_of("binary_search"), "sequence_state_trace")
        self.assertEqual(eo.example_type_of("unique_paths"), "grid_table_trace")
        self.assertIsNone(eo.example_type_of("nope"))

    def test_describe(self):
        self.assertIn("sorted range", eo.describe("binary_search"))
        self.assertIn("1-D ordered sequence", eo.describe("sequence_state_trace"))
        self.assertEqual(eo.describe("nope"), "")


if __name__ == "__main__":
    unittest.main()
