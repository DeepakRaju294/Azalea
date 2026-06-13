"""Visual System V2 — Slice 4 (flags, prose sync, build orchestration).

The LLM is stubbed (dependency-injected), so this stays deterministic and runs
with no network/openai. Run:
  python -m unittest app.tests.test_visual_v2_slice4   (from backend/, PYTHONPATH=.)
"""
from __future__ import annotations

import os
import unittest

from app.services.visual_v2 import flags
from app.services.visual_v2.build import build_v2_visual
from app.services.visual_v2.llm import build_example_prompt, build_prose_prompt
from app.services.visual_v2.prose import deterministic_prose, validate_text_sync

BFS_EXAMPLE = {
    "example_id": "bfs_appendix",
    "base_type": "node_link_diagram",
    "mode": "graph_network",
    "algorithm": "bfs",
    "input": {"start": "A"},
    "base_structure": {
        "nodes": ["A", "B", "C", "D", "E"],
        "edges": [["A", "B"], ["A", "C"], ["B", "D"], ["C", "E"]],
    },
}
TOPIC = {"id": "t1", "title": "Breadth-First Search"}


def _example_stub(**_kwargs):
    return dict(BFS_EXAMPLE)


class TestFlags(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("AZALEA_VISUAL_V2_MODES", None)

    def test_disabled_by_default(self):
        os.environ.pop("AZALEA_VISUAL_V2_MODES", None)
        self.assertFalse(flags.is_v2_enabled("graph_network", "bfs"))

    def test_specific_key_enables_only_that_algorithm(self):
        os.environ["AZALEA_VISUAL_V2_MODES"] = "graph_network:bfs"
        self.assertTrue(flags.is_v2_enabled("graph_network", "bfs"))
        self.assertFalse(flags.is_v2_enabled("graph_network", "dfs"))

    def test_bare_mode_enables_all_algorithms(self):
        os.environ["AZALEA_VISUAL_V2_MODES"] = "graph_network"
        self.assertTrue(flags.is_v2_enabled("graph_network", "bfs"))
        self.assertTrue(flags.is_v2_enabled("graph_network", "dfs"))


class TestTextSyncValidator(unittest.TestCase):
    def test_in_sync_refs_pass(self):
        frame = {"state_after": {"active": "A", "frontier": {"kind": "queue", "items": ["B", "C"]}, "output": ["A"]}}
        refs = {"mentioned_elements": ["A", "B"], "mentioned_values": {"active": "A", "output": ["A"], "frontier": ["B", "C"]}}
        self.assertEqual(validate_text_sync(refs, frame, {"A", "B", "C"}), [])

    def test_unknown_element_rejected(self):
        frame = {"state_after": {"active": "A", "frontier": {"kind": "queue", "items": []}, "output": ["A"]}}
        errs = validate_text_sync({"mentioned_elements": ["Z"]}, frame, {"A"})
        self.assertTrue(any("not a node" in e for e in errs))

    def test_value_mismatch_rejected(self):
        frame = {"state_after": {"active": "A", "frontier": {"kind": "queue", "items": ["C", "D"]}, "output": ["A", "B"]}}
        errs = validate_text_sync({"mentioned_values": {"output": ["A", "C"], "frontier": ["D", "C"]}}, frame, {"A", "B", "C", "D"})
        self.assertEqual(len(errs), 2)  # output + frontier both wrong


class TestBuildOrchestration(unittest.TestCase):
    def test_build_with_deterministic_prose(self):
        result = build_v2_visual(topic=TOPIC, mode="graph_network", algorithm="bfs", generate_example=_example_stub)
        self.assertEqual(result["status"], "validated")
        self.assertEqual(len(result["render_steps"]), 5)
        for rs in result["render_steps"]:
            self.assertIn("points", rs)
            self.assertIn("text_refs", rs)
        self.assertNotIn("prose_repaired", result)  # deterministic prose is in-sync

    def test_build_with_in_sync_llm_prose_is_kept(self):
        def good_prose(**_kw):
            # Only mentions valid ids, no value claims → always passes sync.
            return [{"step_index": i, "points": [f"Custom prose {i}"], "text_refs": {"mentioned_elements": ["A"]}} for i in range(5)]

        result = build_v2_visual(topic=TOPIC, mode="graph_network", algorithm="bfs", generate_example=_example_stub, generate_prose=good_prose)
        self.assertEqual(result["status"], "validated")
        self.assertNotIn("prose_repaired", result)
        self.assertEqual(result["render_steps"][0]["points"], ["Custom prose 0"])

    def test_build_with_drifting_llm_prose_falls_back(self):
        def drifting_prose(**_kw):
            # Claims a wrong output → must be caught and replaced by in-sync prose.
            return [{"step_index": i, "points": ["bad"], "text_refs": {"mentioned_values": {"output": ["Z"]}}} for i in range(5)]

        result = build_v2_visual(topic=TOPIC, mode="graph_network", algorithm="bfs", generate_example=_example_stub, generate_prose=drifting_prose)
        self.assertTrue(result.get("prose_repaired"))
        self.assertTrue(result.get("sync_errors"))
        # Fell back to deterministic prose, which is in-sync.
        self.assertNotEqual(result["render_steps"][0]["points"], ["bad"])

    def test_build_with_invalid_example_fails(self):
        def bad_example(**_kw):
            return {**BFS_EXAMPLE, "base_structure": {"nodes": ["A"], "edges": []}}

        result = build_v2_visual(topic=TOPIC, mode="graph_network", algorithm="bfs", generate_example=bad_example)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["stage"], "ExampleInvariantValidator")


class TestPromptBuilders(unittest.TestCase):
    def test_example_prompt_is_data_only(self):
        system, user = build_example_prompt(TOPIC, "graph_network", "bfs")
        self.assertIn("DATA ONLY", system)
        self.assertIn("no coordinates", user.lower())

    def test_prose_prompt_includes_read_only_trace(self):
        from app.services.visual_v2.simulators.registry import get_simulator

        trace = get_simulator("bfs")(BFS_EXAMPLE)
        system, user = build_prose_prompt(trace)
        self.assertIn("READ-ONLY", system)
        self.assertIn("text_refs", user)


if __name__ == "__main__":
    unittest.main()
