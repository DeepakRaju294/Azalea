"""Provenance on every visual model (PROJECTOR_SYSTEM_SPEC §10.1, build step 1).

Every model declares where its per-step state came from, so a T5 visual is diagnosable
as "move it up the ladder" rather than "tweak the renderer". Asserted by tier/source,
never by topic name.

Run: python -m unittest app.tests.test_provenance
"""
from __future__ import annotations

import os
import sys
import types
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")
for _name in ("dotenv", "openai"):
    if _name not in sys.modules:
        try:
            __import__(_name)
        except ImportError:
            _m = types.ModuleType(_name)
            if _name == "dotenv":
                _m.load_dotenv = lambda *a, **k: None
            else:
                _m.OpenAI = lambda *a, **k: object()
                for _e in ("APIError", "RateLimitError", "APITimeoutError", "APIConnectionError"):
                    setattr(_m, _e, type(_e, (Exception,), {}))
            sys.modules[_name] = _m

from app.services.visual_v2 import provenance as prov


class TestProvenanceRecord(unittest.TestCase):
    def test_tier_is_derived_from_source(self):
        for source, tier in [
            ("registered_simulator", "T1"),
            ("authored_projection", "T2"),
            ("inferred_projection", "T3"),
            ("llm_validated_projection", "T4"),
            ("legacy_raw", "T5"),
        ]:
            self.assertEqual(prov.make_provenance(source)["tier"], tier)

    def test_unknown_source_defaults_to_t5(self):
        self.assertEqual(prov.tier_for("nonsense"), "T5")

    def test_make_provenance_carries_all_fields(self):
        p = prov.make_provenance(
            "authored_projection",
            projection_source="authored",
            projection_contract={"current_from": "u"},
            projector_version=prov.PROJECTOR_VERSION,
            code_source="inline_fixture",
        )
        self.assertEqual(p["state_source"], "authored_projection")
        self.assertEqual(p["projection_contract"], {"current_from": "u"})
        self.assertEqual(p["code_source"], "inline_fixture")
        self.assertEqual(p["validation_summary"], {})

    def test_stamp_and_stamp_if_absent(self):
        model = {"id": "m1", "frames": []}
        prov.stamp(model, prov.make_provenance("registered_simulator"))
        self.assertEqual(model["provenance"]["tier"], "T1")
        # stamp_if_absent must NOT relabel an already-stamped model.
        prov.stamp_if_absent(model, prov.make_provenance("legacy_raw"))
        self.assertEqual(model["provenance"]["state_source"], "registered_simulator")
        # but it DOES stamp a bare model.
        bare = {"id": "m2"}
        prov.stamp_if_absent(bare, prov.make_provenance("legacy_raw"))
        self.assertEqual(bare["provenance"]["tier"], "T5")


class TestComputedPathStampsT1(unittest.TestCase):
    def test_registered_pipeline_model_is_t1(self):
        from app.services.visual_v2.pipeline import run_for_registered

        example = {
            "example_id": "bfs_demo",
            "domain_object": "node_link_trace",
            "base_type": "node_link_diagram",
            "mode": "graph_network",
            "algorithm": "bfs",
            "input": {"start": "A"},
            "base_structure": {
                "nodes": ["A", "B", "C", "D", "E"],
                "edges": [["A", "B"], ["A", "C"], ["B", "D"], ["C", "E"], ["D", "E"]],
            },
            "learner_goal": "Trace BFS.",
        }
        result = run_for_registered(example, model_id="prov_bfs")
        self.assertEqual(result["status"], "validated", result.get("errors"))
        p = result["model"]["provenance"]
        self.assertEqual(p["state_source"], "registered_simulator")
        self.assertEqual(p["tier"], "T1")
        self.assertEqual(p["validation_summary"]["pipeline"], "validated")


if __name__ == "__main__":
    unittest.main()
