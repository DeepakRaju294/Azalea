"""Coding worked examples get BOTH code + diagram from one trace, reach completion,
and degrade safely (PROJECTOR_SYSTEM_SPEC §6.4 INV-DUAL-SLOT generation).

- DFS (no code fixture → fallback path) yields code + node_link diagram, runs to
  completion, and the diagram's terminal matches the code's return.
- A non-graph program degrades to clean code-only (no wrong/empty diagram).
- A terminal mismatch drops the diagram (code-only).
Asserted by behavior, not topic.

Run: python -m unittest app.tests.test_coding_dual_slot
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")
os.environ["AZALEA_VISUAL_V2_MODES"] = "all"

from app.services.examples.code_diagram import (
    attach_diagram_to_cards,
    build_node_link_diagram_from_trace,
    derive_graph_from_trace,
)
from app.services.visual_v2.code_lesson_integration import apply_code_execution_to_lesson
from app.services.visual_v2.simulators.code_tracer import trace_execution

DFS = '''def dfs(graph, start):
    visited = []
    stack = [start]
    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.append(node)
        for nb in graph[node]:
            if nb not in visited:
                stack.append(nb)
    return visited'''

SUM = '''def total(arr):
    s = 0
    for x in arr:
        s = s + x
    return s'''

_GRAPH = {"A": ["B", "C"], "B": ["A", "D"], "C": ["A", "E"], "D": ["B", "E"], "E": ["C", "D"]}


def _lesson(code):
    return {"lesson_cards": [
        {"id": "1", "blueprint_key": "background"},
        {"id": "2", "blueprint_key": "code_walkthrough", "code_snippet": code},
        {"id": "3", "blueprint_key": "worked_example", "code_snippet": code},
        {"id": "4", "blueprint_key": "practice"}], "visual_models": []}


class TestBuilder(unittest.TestCase):
    def test_derives_graph_and_builds_diagram(self):
        steps, ret = trace_execution(DFS, "dfs", {"args": [_GRAPH, "A"]})
        self.assertEqual(set(derive_graph_from_trace(steps)["nodes"]), set("ABCDE"))
        d = build_node_link_diagram_from_trace(steps, model_id="m", start="A")
        self.assertIsNotNone(d)
        final = d["model"]["frames"][-1]["state"]
        visited = {e["node_id"] for e in final["node_state_map"] if e["state"] in ("completed", "current")}
        self.assertEqual(visited, set(ret))  # diagram terminal == code result

    def test_non_graph_program_has_no_diagram(self):
        steps, _ = trace_execution(SUM, "total", {"array": [1, 2, 3, 4]})
        self.assertIsNone(derive_graph_from_trace(steps))
        self.assertIsNone(build_node_link_diagram_from_trace(steps, model_id="m"))


class TestAttachDegrade(unittest.TestCase):
    def test_terminal_mismatch_is_dropped(self):
        steps, _ = trace_execution(DFS, "dfs", {"args": [_GRAPH, "A"]})
        diagram = build_node_link_diagram_from_trace(steps, model_id="m", start="A")
        # frames whose code-terminal output disagrees with the diagram's visited set
        bad_frames = [{"state_after": {"output": ["A", "B"]}}]  # only A,B; diagram visits all
        lesson = {"visual_models": []}
        cards = [{"visual_v2_ref": {"frame_index": 0}}]
        attached = attach_diagram_to_cards(lesson, cards, bad_frames, diagram, source="x")
        self.assertFalse(attached)
        self.assertNotIn("diagram_v2_ref", cards[0])


class TestEndToEnd(unittest.TestCase):
    def test_dfs_fallback_gets_code_and_diagram_to_completion(self):
        lesson = _lesson(DFS)
        ok = apply_code_execution_to_lesson(
            lesson, {"id": "t", "title": "Implement DFS", "topic_type": "coding_implementation"}, sandboxed=False
        )
        self.assertTrue(ok)
        we = [c for c in lesson["lesson_cards"] if c.get("blueprint_key") == "worked_example"]
        self.assertTrue(we)
        for c in we:
            self.assertTrue((c.get("visual_v2_ref") or {}).get("visual_model_id"), "missing code slot")
            self.assertTrue((c.get("diagram_v2_ref") or {}).get("visual_model_id"), "missing diagram slot")
        # the diagram reaches the terminal (all 5 nodes) on the final card
        diag = next(m for m in lesson["visual_models"] if m["id"].endswith("_diagram"))
        final = diag["frames"][-1]["state"]
        visited = {e["node_id"] for e in final["node_state_map"] if e["state"] in ("completed", "current")}
        self.assertEqual(visited, set("ABCDE"))

    def test_non_graph_coding_is_code_only(self):
        lesson = _lesson(SUM)
        ok = apply_code_execution_to_lesson(
            lesson, {"id": "t", "title": "Sum an Array", "topic_type": "coding_implementation"}, sandboxed=False
        )
        self.assertTrue(ok)  # code worked example still applies
        we = [c for c in lesson["lesson_cards"] if c.get("blueprint_key") == "worked_example"]
        self.assertTrue(all(not (c.get("diagram_v2_ref") or {}).get("visual_model_id") for c in we))


if __name__ == "__main__":
    unittest.main()
