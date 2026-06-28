"""Generation Report (§M7) — the always-on causal record of how a worked example was produced.
Verifies the accumulator records the trace-pipeline decision (adapter, ship/withhold + reason) so an
audit reads the record instead of guessing. Offline."""
import unittest
from unittest import mock

from app.services.examples import generation_report as gr
from app.services.examples import trace_pipeline as tp
from app.services.examples.trace_adapters import ADAPTERS


class CodingRouting(unittest.TestCase):
    def test_coding_prefers_legacy_over_gen_foundation(self):
        # When the adapter defers, a CODING topic must use the bounded legacy structural solver, NOT
        # gen_foundation (which over-produces a line trace). gen_foundation still owns non-coding.
        from app.services.examples import solver
        topic = {"title": "Implementing Kruskal", "topic_type": "coding_implementation"}
        with mock.patch("app.services.gen_foundation.flags.is_shadow_enabled", return_value=True), \
             mock.patch("app.services.examples.trace_pipeline._enabled", return_value=False), \
             mock.patch("app.services.gen_foundation.integration.solve_via_pipeline") as gf, \
             mock.patch.object(solver, "_solve_coding_worked_example",
                               return_value={"cards": [{"x": 1}]}) as legacy:
            res = solver.solve_worked_example(topic, code="def kruskal(g): return []")
        gf.assert_not_called()                 # gen_foundation skipped for coding
        legacy.assert_called_once()            # bounded legacy structural solver used instead
        self.assertIsNotNone(res)


class GenerationReportAccumulator(unittest.TestCase):
    def test_records_are_no_ops_without_an_active_report(self):
        gr._current.set(None)
        gr.we(adapter="x")          # must not raise
        gr.error("y")
        self.assertIsNone(gr.current())

    def test_start_and_persist_roundtrip(self):
        r = gr.start({"id": "t1", "topic_type": "algorithm_walkthrough", "title": "Kruskal Walkthrough"})
        gr.we(adapter="kruskal", final_source="trace_pipeline")
        gr.error("noted")
        d = r.to_dict()
        self.assertEqual(d["topic_type"], "algorithm_walkthrough")
        self.assertEqual(d["worked_example"]["adapter"], "kruskal")
        self.assertEqual(d["errors"], ["noted"])
        gr.finish_and_persist()
        self.assertIsNone(gr.current())     # cleared after persist


class TracePipelineRecordsOutcome(unittest.TestCase):
    def _faithful(self, payload):
        import json
        steps = json.loads(payload["user"].split("STEPS (verified, describe faithfully):", 1)[1])
        return {"cards": [{"title": s["operation"], "goal": "", "reasoning": "",
                           "work": s["facts"].get("required_facts", []) + [s["expected_visible_result"]],
                           "result": s["expected_visible_result"]} for s in steps]}

    def test_ship_is_recorded(self):
        gr.start({"title": "Kruskal's Algorithm Walkthrough", "topic_type": "algorithm_walkthrough"})
        tp.solve_trace_pipeline({"title": "Kruskal's Algorithm Walkthrough",
                                 "topic_type": "algorithm_walkthrough"}, format_fn=self._faithful)
        we = gr.current().worked_example
        self.assertEqual(we.get("adapter"), "kruskal")
        self.assertTrue(we.get("tp_shipped"))
        self.assertEqual(we.get("tp_reason"), "shipped")
        self.assertEqual(we.get("formatter_cards"), we.get("verified_steps"))
        gr.finish_and_persist()

    def test_count_mismatch_withhold_is_recorded(self):
        gr.start({"title": "Kruskal's Algorithm Walkthrough", "topic_type": "algorithm_walkthrough"})
        # a formatter that returns the WRONG number of cards (1) -> count_mismatch withhold
        bad = lambda p: {"cards": [{"title": "x", "work": ["w"], "result": "r"}]}
        res = tp.solve_trace_pipeline({"title": "Kruskal's Algorithm Walkthrough",
                                       "topic_type": "algorithm_walkthrough"}, format_fn=bad)
        self.assertIsNone(res)
        we = gr.current().worked_example
        self.assertFalse(we.get("tp_shipped"))
        self.assertEqual(we.get("tp_reason"), "count_mismatch")
        gr.finish_and_persist()

    def test_no_adapter_is_recorded(self):
        gr.start({"title": "Hash Tables", "topic_type": "algorithm_walkthrough"})
        tp.solve_trace_pipeline({"title": "Hash Tables", "topic_type": "algorithm_walkthrough"},
                                format_fn=self._faithful)
        self.assertEqual(gr.current().worked_example.get("adapter"), None)
        self.assertEqual(gr.current().worked_example.get("tp_reason"), "no_adapter")
        gr.finish_and_persist()


class TargetedRetry(unittest.TestCase):
    """M7-driven: the retry loop now feeds the failure back into the next attempt, so a recoverable
    withhold (wrong card count) is fixed instead of discarded. Proven with a feedback-responsive stub."""
    def test_count_mismatch_recovers_with_feedback(self):
        topic = {"title": "Kruskal's Algorithm Walkthrough", "topic_type": "algorithm_walkthrough"}
        gr.start(topic)
        calls = {"n": 0}

        def fmt(payload):
            calls["n"] += 1
            if "FIX FROM THE PREVIOUS ATTEMPT" not in payload["user"]:
                return {"cards": [{"title": "x", "work": ["w"], "result": "r"}]}   # wrong count -> withhold
            import json
            body = payload["user"].split("STEPS (verified, describe faithfully):", 1)[1].split("\n\nFIX", 1)[0]
            steps = json.loads(body)                                              # got feedback -> faithful N cards
            return {"cards": [{"title": s["operation"], "goal": "", "reasoning": "",
                               "work": [s["expected_visible_result"]],            # 1 line -> no aggregation retry
                               "result": s["expected_visible_result"]} for s in steps]}

        res = tp.solve_trace_pipeline(topic, format_fn=fmt)
        self.assertIsNotNone(res, "targeted retry did not recover the count mismatch")
        self.assertEqual(calls["n"], 2)                                          # 2nd attempt saw the feedback
        self.assertTrue(gr.current().worked_example.get("tp_shipped"))
        gr.finish_and_persist()

    def test_too_many_work_lines_triggers_aggregation_retry(self):
        # M6->retry: a walkthrough with 3 work lines must be re-formatted to <=2 (never withheld).
        topic = {"title": "Kruskal's Algorithm Walkthrough", "topic_type": "algorithm_walkthrough"}
        gr.start(topic)
        calls = {"n": 0}

        def fmt(payload):
            calls["n"] += 1
            import json
            steps = json.loads(payload["user"].split("STEPS (verified, describe faithfully):", 1)[1])
            aggregated = "AT MOST 2" in payload["user"]                           # the retry feedback marker
            out = []
            for s in steps:
                evr = s["expected_visible_result"]                               # names the edge + decision
                # neutral supporting lines (no accept/reject verbs -> only the decision lives in evr)
                work = [evr, "update the structure"] if aggregated else [evr, "examine the endpoints", "update the structure"]
                out.append({"title": s["operation"], "goal": "", "reasoning": "", "work": work, "result": evr})
            return {"cards": out}

        res = tp.solve_trace_pipeline(topic, format_fn=fmt)
        self.assertIsNotNone(res)
        self.assertEqual(calls["n"], 2)                                          # retried once to aggregate
        self.assertTrue(all(len(c.get("work") or []) <= 2 for c in res["cards"] if c.get("work")))
        gr.finish_and_persist()


if __name__ == "__main__":
    unittest.main()
