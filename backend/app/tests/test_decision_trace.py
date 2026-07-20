"""Decision-trace primitive (app/core/decision_trace.py): the mechanism giving every deterministic pipeline
pass a persisted, queryable record of WHY it made each choice, alongside the existing log-line narration.

Two contracts matter: (1) recording is completely safe against malformed input (a broken instrumentation
call must never break generation), and (2) the two-audience split — record_topic_decision/take_topic_trace
for decomposition-time (moves into decomposition_metadata at persistence), record_lesson_decision for
lesson-generation-time (writes DIRECTLY, since that layer runs after the topic is already persisted and
works against a Topic ORM object as often as a dict).
Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_decision_trace
"""
import os
import types
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.core.decision_trace import (
    record_lesson_decision, record_path_decision, record_topic_decision, take_path_trace, take_topic_trace,
)


class TopicTrace(unittest.TestCase):
    def test_record_then_take_round_trips(self):
        t = {"title": "X"}
        record_topic_decision(t, "stage.a", "did X", "because Y", extra=1)
        self.assertNotIn("decision_trace", t)          # internal key stays internal until taken
        trace = take_topic_trace(t)
        self.assertEqual(len(trace), 1)
        self.assertEqual(trace[0]["stage"], "stage.a")
        self.assertEqual(trace[0]["decision"], "did X")
        self.assertEqual(trace[0]["reason"], "because Y")
        self.assertEqual(trace[0]["detail"], {"extra": 1})
        self.assertNotIn("_decision_trace", t)          # popped, not just read

    def test_multiple_records_preserve_order(self):
        t = {}
        record_topic_decision(t, "s1", "d1", "r1")
        record_topic_decision(t, "s2", "d2", "r2")
        trace = take_topic_trace(t)
        self.assertEqual([e["stage"] for e in trace], ["s1", "s2"])

    def test_no_detail_kwargs_omits_detail_key(self):
        t = {}
        record_topic_decision(t, "s", "d", "r")
        self.assertNotIn("detail", take_topic_trace(t)[0])

    def test_none_and_empty_detail_values_stripped(self):
        t = {}
        record_topic_decision(t, "s", "d", "r", a=None, b=[], c="", d_val="kept")
        entry = take_topic_trace(t)[0]
        self.assertEqual(entry["detail"], {"d_val": "kept"})

    def test_never_raises_on_malformed_input(self):
        record_topic_decision(None, "s", "d", "r")               # no-op, no crash
        record_topic_decision("not a dict", "s", "d", "r")        # no-op, no crash
        record_topic_decision(123, "s", "d", "r")
        self.assertEqual(take_topic_trace(None), [])
        self.assertEqual(take_topic_trace("not a dict"), [])

    def test_take_on_topic_with_no_recordings_is_empty(self):
        self.assertEqual(take_topic_trace({"title": "untouched"}), [])


class PathTrace(unittest.TestCase):
    def test_record_then_take_round_trips_and_is_non_destructive(self):
        p = {}
        record_path_decision(p, "s", "d", "r", n=1)
        trace1 = take_path_trace(p)
        trace2 = take_path_trace(p)                    # non-destructive — read again
        self.assertEqual(trace1, trace2)
        self.assertEqual(len(trace1), 1)

    def test_never_raises_on_malformed_input(self):
        record_path_decision(None, "s", "d", "r")
        self.assertEqual(take_path_trace(None), [])


class LessonDecision(unittest.TestCase):
    """record_lesson_decision writes DIRECTLY into decomposition_metadata['decision_trace'] (never the
    internal _decision_trace working key) and handles both a dict topic and an ORM-like object via
    attribute assignment — always by REASSIGNING the dict (never in-place mutation), since a plain JSON
    column's in-place mutation is invisible to SQLAlchemy's change tracking."""

    def test_dict_topic_written_directly_to_decomposition_metadata(self):
        t = {"decomposition_metadata": {"existing_key": "kept"}}
        record_lesson_decision(t, "card.x", "did X", "because Y")
        meta = t["decomposition_metadata"]
        self.assertEqual(meta["existing_key"], "kept")     # prior content preserved
        self.assertEqual(len(meta["decision_trace"]), 1)
        self.assertEqual(meta["decision_trace"][0]["stage"], "card.x")

    def test_object_topic_written_via_attribute_reassignment(self):
        t = types.SimpleNamespace(decomposition_metadata={"scope_plan": {"role": "goal_core"}})
        record_lesson_decision(t, "card.y", "did Y", "because Z")
        self.assertEqual(t.decomposition_metadata["scope_plan"]["role"], "goal_core")
        self.assertEqual(len(t.decomposition_metadata["decision_trace"]), 1)

    def test_appends_across_multiple_calls(self):
        t = {"decomposition_metadata": {}}
        record_lesson_decision(t, "s1", "d1", "r1")
        record_lesson_decision(t, "s2", "d2", "r2")
        self.assertEqual([e["stage"] for e in t["decomposition_metadata"]["decision_trace"]], ["s1", "s2"])

    def test_appends_onto_trace_already_persisted_by_decomposition(self):
        # the realistic case: decomposition already moved its own trace into decomposition_metadata
        # before lesson generation runs — record_lesson_decision must EXTEND that list, not replace it.
        t = {"decomposition_metadata": {"decision_trace": [{"stage": "identity.assigned", "decision": "x",
                                                            "reason": "y"}]}}
        record_lesson_decision(t, "card.formula_grounded", "d", "r")
        stages = [e["stage"] for e in t["decomposition_metadata"]["decision_trace"]]
        self.assertEqual(stages, ["identity.assigned", "card.formula_grounded"])

    def test_never_raises_on_malformed_input(self):
        record_lesson_decision(None, "s", "d", "r")
        record_lesson_decision(object(), "s", "d", "r")   # no decomposition_metadata attr, not settable


if __name__ == "__main__":
    unittest.main()
