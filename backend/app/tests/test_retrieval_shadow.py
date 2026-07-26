"""Retrieval-grounding shadow observer tests (offline). Off = no-op; shadow = records what grounding would
conclude, without changing anything. Fail-closed."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples.retrieval.shadow import is_observing, observe_grounding


class Shadow(unittest.TestCase):
    def test_off_is_noop(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AZALEA_RETRIEVAL_GROUNDED_EXAMPLES", None)
            self.assertFalse(is_observing())
            self.assertIsNone(observe_grounding({"title": "Motional EMF"}, "1.0 V"))

    def test_shadow_records_resolved(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "shadow.jsonl")
            with mock.patch.dict(os.environ, {"AZALEA_RETRIEVAL_GROUNDED_EXAMPLES": "shadow",
                                              "AZALEA_RETRIEVAL_SHADOW_PATH": path}, clear=False):
                rec = observe_grounding({"title": "Motional EMF"}, "1.0 V")
            self.assertIsNotNone(rec)
            self.assertEqual(rec["outcome"], "resolved")
            self.assertEqual(rec["concept_key"], "motional_emf")
            self.assertEqual(rec["level"], "verified_reproduction")
            self.assertTrue(os.path.exists(path))

    def test_shadow_records_retrieval_miss(self):
        with mock.patch.dict(os.environ, {"AZALEA_RETRIEVAL_GROUNDED_EXAMPLES": "shadow"}, clear=False):
            rec = observe_grounding({"title": "Bubble Sort"}, "x", write=False)
        self.assertEqual(rec["outcome"], "retrieval_miss")

    def test_wrong_answer_shadow_shows_guided(self):
        with mock.patch.dict(os.environ, {"AZALEA_RETRIEVAL_GROUNDED_EXAMPLES": "shadow"}, clear=False):
            rec = observe_grounding({"title": "Motional EMF"}, "9 V", write=False)
        self.assertEqual(rec["reproduction_status"], "refute")
        self.assertEqual(rec["level"], "guided")


if __name__ == "__main__":
    unittest.main()
