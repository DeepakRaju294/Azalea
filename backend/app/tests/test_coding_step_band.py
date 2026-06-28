"""coding_step_band: the adapter-derived step-count GUIDELINE (floor + generous ceiling) the legacy
coding gate accepts. The band is read off the algorithm's adapter natural trace LENGTH (count only, never
its data/values), padded wide so a natural example is never rejected and only a line-trace explosion is.
Offline."""
import unittest

from app.services.examples.solver import (CODING_STEP_RANGES, _gate_coding_outline, coding_step_band)


def _topic(title):
    return {"title": title, "topic_type": "coding_implementation"}


class CodingStepBand(unittest.TestCase):
    def test_band_matches_adapter_natural_length(self):
        lo, hi = coding_step_band(_topic("Implementing Prim's Algorithm"))
        self.assertLessEqual(lo, 4)            # Prim naturally makes 4-5 structural steps
        self.assertGreaterEqual(hi, 5)
        self.assertLess(hi, 18)                # generous but bounded — no room for a line trace

    def test_merge_sort_floor_not_overpadded(self):
        # the old static (8,18) force-padded every example; the adapter makes 4-7, so the floor must be low
        lo, _ = coding_step_band(_topic("Implementing Merge Sort"))
        self.assertLessEqual(lo, 4)

    def test_no_adapter_falls_back_to_static_default(self):
        self.assertEqual(coding_step_band(_topic("Implementing a Custom Widget Cache")),
                         CODING_STEP_RANGES["default"])

    def test_gate_rejects_line_trace_explosion(self):
        band = coding_step_band(_topic("Implementing Kruskal's Algorithm"))
        big = {"solution_plan": [{"kind": "visit", "description": f"s{i}"} for i in range(33)]}
        ok, _, reason = _gate_coding_outline(big, step_range=band, required=[])
        self.assertFalse(ok)
        self.assertEqual(reason, "outline_over_max")

    def test_gate_accepts_natural_length(self):
        band = coding_step_band(_topic("Implementing Kruskal's Algorithm"))
        plan = {"solution_plan": [{"kind": "visit", "description": f"edge {i}"} for i in range(6)]}
        ok, _, _ = _gate_coding_outline(plan, step_range=band, required=[])
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
