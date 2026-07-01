"""CP3 — coverage-based acceptance: a worked example is acceptable when coverage is COMPLETE, even if the card
count differs from the step count; and it is rejected when a required transition, the terminal, a valid id, or a
truthful claim is missing/wrong. The five CP3 boundary cases, over a real Kruskal trace."""
import unittest

from app.services.examples.trace_contract import coverage_complete
from app.services.examples.trace_pipeline import _seed_for, route_adapter, select_instance

_TOPIC = {"title": "Kruskal's Minimum Spanning Tree", "topic_type": "algorithm_walkthrough"}


def _kruskal():
    ad = route_adapter(_TOPIC)
    return ad, select_instance(ad, _seed_for(_TOPIC))


def _cards(groups):
    return [{"trace_step_ids": list(g), "result": "", "work": [], "reasoning": ""} for g in groups]


class CoverageComplete(unittest.TestCase):
    def setUp(self):
        self.ad, self.trace = _kruskal()
        if self.ad is None or not self.trace.steps:
            self.skipTest("kruskal adapter/trace unavailable")
        self.ids = [s.id for s in self.trace.steps]

    def test_1_grouped_but_complete_accepts(self):
        # every step covered, but grouped into 2 cards -> count != #steps, yet acceptable
        mid = max(1, len(self.ids) // 2)
        cards = _cards([self.ids[:mid], self.ids[mid:]])
        self.assertNotEqual(len(cards), len(self.trace.steps))
        ok, reason = coverage_complete(cards, self.trace)
        self.assertTrue(ok, reason)

    def test_2_missing_terminal_rejects(self):
        ok, reason = coverage_complete(_cards([self.ids[:-1]]), self.trace)
        self.assertFalse(ok)
        # the terminal is also the `completion` required case, so either reason is a correct rejection
        self.assertTrue("terminal" in reason or "completion" in reason, reason)

    def test_3_missing_required_case_rejects(self):
        term = self.ids[-1]
        req = next((rc for rc in self.trace.required_cases
                    if term not in set(self.trace.case_evidence.get(rc, []))), None)
        if req is None:
            self.skipTest("no non-terminal required case")
        drop = set(self.trace.case_evidence.get(req, []))
        ok, reason = coverage_complete(_cards([[i for i in self.ids if i not in drop]]), self.trace)
        self.assertFalse(ok)
        self.assertIn("missing_required_transition", reason)

    def test_4_prose_contradiction_rejects(self):
        skip = next((s for s in self.trace.steps
                     if str(getattr(s, "decision", "")).lower().startswith(("skip", "reject"))), None)
        if skip is None:
            self.skipTest("no skip-decision step")
        cards = [{"trace_step_ids": [i], "result": "", "work": [], "reasoning": ""} for i in self.ids]
        for c in cards:
            if c["trace_step_ids"][0] == skip.id:
                c["work"] = ["we accept this edge and add it to the tree"]   # asserts accept on a skip step
        ok, reason = coverage_complete(cards, self.trace, self.ad)
        self.assertFalse(ok)
        self.assertIn("hard_prose", reason)

    def test_5_unknown_id_rejects(self):
        ok, reason = coverage_complete(_cards([self.ids + ["bogus_step_id"]]), self.trace)
        self.assertFalse(ok)
        self.assertIn("unknown_trace_id", reason)


if __name__ == "__main__":
    unittest.main()
