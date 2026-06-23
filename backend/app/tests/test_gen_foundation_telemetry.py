"""Tests for durable shadow telemetry (the oracle-gap dataset)."""
import json
import os
import tempfile
import unittest

from app.services.gen_foundation.metrics import measure_run, record_run_telemetry
from app.services.gen_foundation.pipeline import RunResult


def _result(ok=True, artifact=None, degraded=False, **execution):
    return RunResult(
        ok=ok,
        artifact=artifact if artifact is not None else {"cards": [{}, {}]},
        model_calls=1,
        reconciliation_telemetry={"reconciliation_status": "matched", "execution": execution},
        degraded=degraded,
    )


class MeasureTests(unittest.TestCase):
    def test_captures_execution_fields(self):
        m = measure_run("t1", _result(executed=True, skip_reason=None,
                                       final_answer_agreement=False, property_violations=["mst: bad"]))
        self.assertTrue(m.executed)
        self.assertIs(m.final_answer_agreement, False)
        self.assertEqual(m.property_violations, ["mst: bad"])
        self.assertFalse(m.blocked)

    def test_skipped_execution_recorded(self):
        m = measure_run("t2", _result(executed=False, skip_reason="execution_disabled"))
        self.assertFalse(m.executed)
        self.assertEqual(m.execution_skip_reason, "execution_disabled")
        self.assertIsNone(m.final_answer_agreement)

    def test_blocked_when_degraded(self):
        m = measure_run("t3", _result(ok=False, artifact=None, degraded=True))
        self.assertTrue(m.blocked)


class PersistTests(unittest.TestCase):
    def test_appends_jsonl_lines(self):
        r = _result(executed=True, skip_reason=None, final_answer_agreement=True, property_violations=[])
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "telemetry.jsonl")
            record_run_telemetry("topic-1", r, path=path)
            record_run_telemetry("topic-2", r, path=path)
            lines = open(path, encoding="utf-8").read().strip().splitlines()
        self.assertEqual(len(lines), 2)
        rec = json.loads(lines[0])
        self.assertEqual(rec["topic_id"], "topic-1")
        self.assertTrue(rec["executed"])
        self.assertTrue(rec["final_answer_agreement"])

    def test_never_raises_on_bad_path(self):
        # a non-writable path must not propagate — telemetry can't break generation
        record_run_telemetry("t", _result(executed=True), path="/nonexistent_dir/telemetry.jsonl")


if __name__ == "__main__":
    unittest.main()
