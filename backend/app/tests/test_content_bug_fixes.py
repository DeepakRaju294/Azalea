"""Regression tests for two content bugs found reviewing a live Stokes' Theorem path:
  1) card blueprint_key/card_type polluted with prompt flag descriptors
     ('comparison continuation-only repeatable') — the model copied a prompt annotation into the key.
  2) integer-valued floats rendered as machine output in worked-example state ('curl = 0.0, 0.0, 1.0').
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples.trace_pipeline import _fmt_state_val
from app.services.lean_lesson_generator import _clean_blueprint_key


class CleanBlueprintKey(unittest.TestCase):
    def test_strips_flag_descriptors(self):
        self.assertEqual(_clean_blueprint_key("comparison continuation-only repeatable"), "comparison")
        self.assertEqual(_clean_blueprint_key("background optional continuation-only repeatable"), "background")

    def test_leaves_clean_keys_untouched(self):
        for k in ("comparison", "worked_example", "components_terms", "formula_breakdown", "process"):
            self.assertEqual(_clean_blueprint_key(k), k)

    def test_does_not_mangle_unexpected_multiword_key(self):
        # a genuine (if unusual) multi-word key that isn't just flags is left alone, not truncated
        self.assertEqual(_clean_blueprint_key("some weird key"), "some weird key")


class FmtStateVal(unittest.TestCase):
    def test_integer_valued_floats_render_as_ints(self):
        self.assertEqual(_fmt_state_val(1.0), "1")
        self.assertEqual(_fmt_state_val(0.0), "0")
        self.assertEqual(_fmt_state_val(-0.0), "0")
        self.assertEqual(_fmt_state_val([0.0, 0.0, 1.0]), "0, 0, 1")   # curl, not "0.0, 0.0, 1.0"

    def test_non_integer_floats_trimmed(self):
        self.assertEqual(_fmt_state_val(1.5707963), "1.5708")
        self.assertEqual(_fmt_state_val([1.0, 2.5]), "1, 2.5")

    def test_bool_untouched(self):
        self.assertEqual(_fmt_state_val(True), "True")

    def test_none_and_empty(self):
        self.assertEqual(_fmt_state_val(None), "none")
        self.assertEqual(_fmt_state_val([]), "(empty)")


if __name__ == "__main__":
    unittest.main()
