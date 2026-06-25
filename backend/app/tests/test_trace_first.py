"""Tests for the trace-first worked-example foundation (root fix D)."""
import unittest

from app.services.gen_foundation.trace_first import build_cards_from_trace


def ev(i, state, line):
    return {"step_index": i, "code_line_refs": [line], "state": state, "func": "f"}


class TraceFirstTests(unittest.TestCase):
    def _events(self):
        # a run that accumulates: mst grows 1 edge at a time to completion, then returns
        return [
            ev(0, {"mst": []}, 3),
            ev(1, {"mst": [["A", "B", 1]]}, 5),
            ev(2, {"mst": [["A", "B", 1], ["B", "C", 2]]}, 5),
            ev(3, {"mst": [["A", "B", 1], ["B", "C", 2], ["C", "D", 3]]}, 5),
            {"step_index": 4, "code_line_refs": [], "state": {}, "return_value": [["A", "B", 1], ["B", "C", 2], ["C", "D", 3]]},
        ]

    def test_builds_state_accurate_cards(self):
        out = build_cards_from_trace(self._events())
        self.assertTrue(out["trace_backed"])
        self.assertEqual(out["source"], "trace_first")
        # final answer is the REAL return value (can't truncate/drift)
        self.assertEqual(out["final_answer"], [["A", "B", 1], ["B", "C", 2], ["C", "D", 3]])
        # each card's state is a recorded state, monotonic to completion
        states = [c["state"]["mst"] for c in out["cards"] if c["state"].get("mst") is not None]
        self.assertEqual(states[-1], [["A", "B", 1], ["B", "C", 2], ["C", "D", 3]])
        self.assertEqual(out["cards"][0]["prior_state"], None)
        self.assertEqual(out["cards"][1]["prior_state"], out["cards"][0]["state"])

    def test_groups_to_max_cards(self):
        events = [ev(i, {"x": i}, 5) for i in range(40)]
        events.append({"step_index": 99, "code_line_refs": [], "state": {}, "return_value": 39})
        out = build_cards_from_trace(events, max_cards=8)
        self.assertLessEqual(len(out["cards"]), 8)
        self.assertEqual(out["final_answer"], 39)

    def test_empty_trace_returns_empty(self):
        self.assertEqual(build_cards_from_trace(None), {})
        self.assertEqual(build_cards_from_trace([]), {})

    def test_dedups_noop_states(self):
        events = [ev(0, {"x": 1}, 3), ev(1, {"x": 1}, 4), ev(2, {"x": 2}, 5),
                  {"step_index": 3, "code_line_refs": [], "state": {}, "return_value": 2}]
        out = build_cards_from_trace(events)
        # the two identical {x:1} states collapse — only real state changes become steps
        xs = [c["state"].get("x") for c in out["cards"]]
        self.assertEqual(xs, [1, 2])


class TraceFirstLiveWiringTests(unittest.TestCase):
    def test_pipeline_replaces_model_cards_with_real_trace(self):
        import os
        from app.services.gen_foundation.pipeline import run_first_pass
        os.environ["AZALEA_GEN_FOUNDATION_EXECUTE"] = "1"
        os.environ["AZALEA_TRACE_FIRST"] = "1"
        try:
            code = "def run(nums):\n    out = []\n    for n in nums:\n        out.append(n * 2)\n    return out\n"
            artifact = {
                "cards": [{"title": "x", "goal": "g", "how": "h", "work": ["w"], "result": "r",
                           "state_relevance": "none", "state_delta": None, "cases_covered": [],
                           "explanation_mode": "implementation_how", "code_refs": [2]}],
                "final_answer": "WRONG model claim", "code": code,
                "example_input": {"entry": "run", "args": [[1, 2, 3]]},
            }
            res = run_first_pass(
                {"topic_type": "coding_implementation", "title": "Doubler", "code_language": "python"},
                solver=lambda p: dict(artifact), auditor=lambda p: None, repair=lambda p: None)
            a = res.artifact or {}
            self.assertTrue(a.get("trace_first"))
            self.assertEqual(a.get("final_answer"), [2, 4, 6])      # REAL result replaces the wrong claim
            self.assertTrue(res.ok)
            self.assertGreater(len(a.get("cards") or []), 1)
        finally:
            os.environ.pop("AZALEA_GEN_FOUNDATION_EXECUTE", None)
            os.environ.pop("AZALEA_TRACE_FIRST", None)


if __name__ == "__main__":
    unittest.main()
