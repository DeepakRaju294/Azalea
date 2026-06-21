"""Bounded AST-gated Python tracer (spec §6, §12 step 7).

Pure backend, no LLM. Execution is env-gated; tests toggle the flag locally.
Run: python -m unittest app.tests.test_gen_foundation_executor
"""
from __future__ import annotations

import os
import unittest
from contextlib import contextmanager

from app.services.gen_foundation import executor


@contextmanager
def execute_enabled(value: str = "1"):
    prev = os.environ.get("AZALEA_GEN_FOUNDATION_EXECUTE")
    os.environ["AZALEA_GEN_FOUNDATION_EXECUTE"] = value
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop("AZALEA_GEN_FOUNDATION_EXECUTE", None)
        else:
            os.environ["AZALEA_GEN_FOUNDATION_EXECUTE"] = prev


SUM_CODE = (
    "def f(n):\n"
    "    total = 0\n"
    "    for i in range(n):\n"
    "        total = total + i\n"
    "    return total\n"
)


class TestExecutorGating(unittest.TestCase):
    def test_disabled_by_default(self):
        # No env flag -> never executes.
        self.assertIsNone(executor.run_trace(SUM_CODE, "python", {"entry": "f", "args": [3]}))

    def test_non_python_rejected(self):
        with execute_enabled():
            self.assertIsNone(executor.run_trace("x = 1;", "java", {}))

    def test_import_rejected(self):
        with execute_enabled():
            self.assertIsNone(executor.run_trace("import os\n", "python", {}))

    def test_dunder_access_rejected(self):
        with execute_enabled():
            code = "def f():\n    return ().__class__\n"
            self.assertIsNone(executor.run_trace(code, "python", {"entry": "f", "args": []}))

    def test_dangerous_name_rejected(self):
        with execute_enabled():
            code = "def f():\n    return open('x')\n"
            self.assertIsNone(executor.run_trace(code, "python", {"entry": "f", "args": []}))


class TestExecutorTracing(unittest.TestCase):
    def test_traces_and_returns(self):
        with execute_enabled():
            events = executor.run_trace(SUM_CODE, "python", {"entry": "f", "args": [3]})
        self.assertIsNotNone(events)
        # final event carries the return value (0+1+2 == 3)
        self.assertEqual(events[-1]["return_value"], 3)
        # line events carry semantic state snapshots
        states = [e for e in events if e.get("state")]
        self.assertTrue(states)
        self.assertIn("total", states[-1]["state"])
        # line refs are within the snippet (1..5)
        for e in events:
            for ln in e.get("code_line_refs", []):
                self.assertTrue(1 <= ln <= 5)

    def test_step_bound_returns_none(self):
        infinite = "def f():\n    x = 0\n    while True:\n        x = x + 1\n    return x\n"
        with execute_enabled():
            self.assertIsNone(executor.run_trace(infinite, "python", {"entry": "f", "args": []}))

    def test_positional_input_list(self):
        with execute_enabled():
            events = executor.run_trace(SUM_CODE, "python", [4])  # bare list -> positional args
        self.assertIsNotNone(events)
        self.assertEqual(events[-1]["return_value"], 6)  # 0+1+2+3


class TestAstGate(unittest.TestCase):
    def test_parse_safe_accepts_clean_code(self):
        self.assertIsNotNone(executor.parse_safe(SUM_CODE, "python"))

    def test_parse_safe_rejects_with_statement(self):
        self.assertIsNone(executor.parse_safe("with open('x') as f:\n    pass\n", "python"))


if __name__ == "__main__":
    unittest.main()
