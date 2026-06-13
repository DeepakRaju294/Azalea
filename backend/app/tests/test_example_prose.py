"""Example System — Phase 4: prose slots are trace-grounded + delta-focused, and the
ProseValidator rejects ungrounded/forbidden prose (spec §4.1, §5.3 #4).

Run: python -m unittest app.tests.test_example_prose
"""
from __future__ import annotations

import unittest

from app.core.example_fixtures import FIXTURES
from app.services.examples.handoff import _milestone_frame_indices, fixture_to_canonical_example
from app.services.examples.prose_slot import (
    ProseSlot,
    build_prose_slots,
    deterministic_points,
    fill_slots,
    validate_points,
)
from app.services.visual_v2.pipeline import run_for_registered

ALL = [fx for fxs in FIXTURES.values() for fx in fxs]


def _slots_for(fixture):
    result = run_for_registered(fixture_to_canonical_example(fixture), model_id="t")
    milestones = _milestone_frame_indices(result, fixture)
    return build_prose_slots(result, milestones, fixture), milestones


class TestSlotBuilding(unittest.TestCase):
    def test_one_grounded_slot_per_milestone(self):
        for fx in ALL:
            slots, milestones = _slots_for(fx)
            self.assertEqual(len(slots), len(milestones), fx.fixture_id)
            for s in slots:
                self.assertTrue(s.current_frame_delta.strip(), f"{fx.fixture_id}: empty delta")
                self.assertTrue(s.allowed_facts, f"{fx.fixture_id}: no allowed_facts")

    def test_deterministic_prose_is_always_in_sync(self):
        for fx in ALL:
            slots, _ = _slots_for(fx)
            for s in slots:
                self.assertEqual(validate_points(s, deterministic_points(s)), [], f"{fx.fixture_id}/{s.slot_id}")

    def test_binary_search_delta_mentions_pointers(self):
        bs = [fx for fx in ALL if fx.fixture_id == "binary_search_concept_found_late_01"][0]
        slots, _ = _slots_for(bs)
        joined = " ".join(s.current_frame_delta for s in slots).lower()
        self.assertIn("low", joined)
        self.assertIn("high", joined)
        self.assertIn("mid", joined)


class TestProseValidator(unittest.TestCase):
    def _slot(self, **kw):
        base = dict(slot_id="s", frame_index=0, step_role="x", previous_frame_summary="",
                    current_frame_delta="", bullets=(), allowed_facts=("low=0", "high=6", "mid=3"),
                    required_mentions=(), forbidden_mentions=("def ",))
        base.update(kw)
        return ProseSlot(**base)

    def test_rejects_ungrounded_number(self):
        s = self._slot()
        self.assertTrue(validate_points(s, ["mid is 99"]))  # 99 not in allowed_facts

    def test_accepts_grounded_number(self):
        s = self._slot()
        self.assertEqual(validate_points(s, ["mid is 3, high is 6"]), [])

    def test_rejects_forbidden_mention(self):
        s = self._slot()
        self.assertTrue(validate_points(s, ["def binary_search(arr):"]))


class TestFillFallsBack(unittest.TestCase):
    def test_bad_generator_falls_back_to_deterministic(self):
        bs = [fx for fx in ALL if fx.example_type == "sequence_state_trace"][0]
        slots, _ = _slots_for(bs)
        bad = lambda slot: ["the answer is 9999"]  # ungrounded → rejected → fallback
        filled = fill_slots(slots, generator=bad)
        for points, slot in zip(filled, slots):
            self.assertEqual(points, deterministic_points(slot))


if __name__ == "__main__":
    unittest.main()
