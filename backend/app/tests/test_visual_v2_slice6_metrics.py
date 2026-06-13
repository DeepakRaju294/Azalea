"""Visual System V2 — Slice 6 (telemetry + widening gates). Pure backend, no LLM.

Run: python -m unittest app.tests.test_visual_v2_slice6_metrics
"""
from __future__ import annotations

import unittest

from app.services.visual_v2 import metrics as M
from app.services.visual_v2.build import build_v2_visual
from app.services.visual_v2.metrics import VisualMetrics, widening_gates

BFS_EXAMPLE = {
    "example_id": "bfs", "base_type": "node_link_diagram", "mode": "graph_network",
    "algorithm": "bfs", "input": {"start": "A"},
    "base_structure": {"nodes": ["A", "B", "C", "D", "E"],
                       "edges": [["A", "B"], ["A", "C"], ["B", "D"], ["C", "E"]]},
}


def _validated(mode="graph_network", repaired=False):
    return {"status": "validated", "example": {"mode": mode}, "prose_repaired": repaired}


def _failed(stage, mode="graph_network"):
    return {"status": "failed", "stage": stage, "example": {"mode": mode}}


class TestVisualMetrics(unittest.TestCase):
    def test_rates(self):
        m = VisualMetrics()
        for _ in range(8):
            m.record(_validated())
        m.record(_validated(repaired=True))
        m.record(_failed("ExampleInvariantValidator"))
        self.assertEqual(m.total, 10)
        self.assertEqual(m.validated, 9)
        self.assertAlmostEqual(m.coverage, 0.9)
        self.assertAlmostEqual(m.rejection_rate, 0.1)
        self.assertAlmostEqual(m.repair_rate, 1 / 9)

    def test_snapshot_and_breakdowns(self):
        m = VisualMetrics()
        m.record(_failed("TraceValidator"))
        m.record(_failed("TraceValidator"))
        m.record(_validated(mode="binary_search_range"))
        snap = m.snapshot()
        self.assertEqual(snap["failures_by_stage"]["TraceValidator"], 2)
        self.assertEqual(snap["by_mode"]["binary_search_range"], 1)
        self.assertIn("coverage", snap)

    def test_empty_metrics_are_zero_not_error(self):
        m = VisualMetrics()
        self.assertEqual(m.coverage, 0.0)
        self.assertEqual(m.repair_rate, 0.0)


class TestWideningGates(unittest.TestCase):
    def test_insufficient_samples_blocks(self):
        m = VisualMetrics()
        for _ in range(5):
            m.record(_validated())
        g = widening_gates(m)
        self.assertFalse(g["pass"])
        self.assertTrue(any("insufficient samples" in r for r in g["reasons"]))

    def test_all_good_passes(self):
        m = VisualMetrics()
        for _ in range(20):
            m.record(_validated())
        g = widening_gates(m)
        self.assertTrue(g["pass"], g["reasons"])

    def test_high_rejection_blocks(self):
        m = VisualMetrics()
        for _ in range(18):
            m.record(_validated())
        for _ in range(2):
            m.record(_failed("PedagogicalVisualValidator"))
        g = widening_gates(m)  # 10% rejection > 5%
        self.assertFalse(g["pass"])
        self.assertTrue(any("rejection" in r for r in g["reasons"]))

    def test_high_repair_blocks(self):
        m = VisualMetrics()
        for _ in range(20):
            m.record(_validated(repaired=True))  # 100% repair
        g = widening_gates(m)
        self.assertFalse(g["pass"])
        self.assertTrue(any("repair" in r for r in g["reasons"]))

    def test_known_bad_blocks(self):
        m = VisualMetrics()
        for _ in range(20):
            m.record(_validated())
        g = widening_gates(m, known_bad_failures=1)
        self.assertFalse(g["pass"])
        self.assertTrue(any("known-bad" in r for r in g["reasons"]))


class TestBuildPathRecords(unittest.TestCase):
    def setUp(self):
        M.GLOBAL.reset()

    def tearDown(self):
        M.GLOBAL.reset()

    def test_validated_build_is_recorded(self):
        build_v2_visual(topic={"id": "t"}, mode="graph_network", algorithm="bfs",
                        generate_example=lambda **_k: dict(BFS_EXAMPLE))
        self.assertEqual(M.GLOBAL.total, 1)
        self.assertEqual(M.GLOBAL.validated, 1)
        self.assertEqual(M.GLOBAL.by_mode["graph_network"], 1)

    def test_failed_build_is_recorded_with_stage(self):
        bad = {**BFS_EXAMPLE, "base_structure": {"nodes": ["A"], "edges": []}}
        build_v2_visual(topic={"id": "t"}, mode="graph_network", algorithm="bfs",
                        generate_example=lambda **_k: dict(bad))
        self.assertEqual(M.GLOBAL.total, 1)
        self.assertEqual(M.GLOBAL.validated, 0)
        self.assertEqual(M.GLOBAL.failures_by_stage["ExampleInvariantValidator"], 1)


if __name__ == "__main__":
    unittest.main()
