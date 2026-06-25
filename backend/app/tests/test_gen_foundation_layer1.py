"""Tests for Layer 1: executor stdlib allow-list, structured output, skip reasons, agreement telemetry."""
import os
import unittest

from app.services.gen_foundation.executor import (
    ExecutionResult, execute, execution_skip_reason, run_trace, parse_safe,
)
from app.services.gen_foundation.pipeline import _answers_agree, _executor_final_answer

HEAPQ_CODE = (
    "import heapq\n"
    "def run(nums):\n"
    "    h = []\n"
    "    for n in nums:\n"
    "        heapq.heappush(h, n)\n"
    "    out = []\n"
    "    while h:\n"
    "        out.append(heapq.heappop(h))\n"
    "    return out\n"
)
DEQUE_CODE = (
    "from collections import deque\n"
    "def run(n):\n"
    "    q = deque([n])\n"
    "    seen = []\n"
    "    while q:\n"
    "        seen.append(q.popleft())\n"
    "    return seen\n"
)


class AstGateTests(unittest.TestCase):
    def test_allowlisted_imports_pass_gate(self):
        self.assertIsNotNone(parse_safe(HEAPQ_CODE, "python"))
        self.assertIsNotNone(parse_safe(DEQUE_CODE, "python"))

    def test_disallowed_imports_rejected(self):
        self.assertIsNone(parse_safe("import os\ndef run():\n    return 1\n", "python"))
        self.assertIsNone(parse_safe("import numpy\ndef run():\n    return 1\n", "python"))
        self.assertIsNone(parse_safe("from . import x\ndef run():\n    return 1\n", "python"))


class SkipReasonTests(unittest.TestCase):
    def test_disabled_by_default(self):
        os.environ.pop("AZALEA_GEN_FOUNDATION_EXECUTE", None)
        self.assertEqual(execution_skip_reason(HEAPQ_CODE, "python"), "execution_disabled")

    def test_reasons_when_enabled(self):
        os.environ["AZALEA_GEN_FOUNDATION_EXECUTE"] = "1"
        try:
            self.assertEqual(execution_skip_reason("print(1)", "java"), "unsupported_language")
            self.assertEqual(execution_skip_reason("import os\ndef r():\n    return 1\n", "python"),
                             "unsafe_or_unparseable")
            self.assertEqual(execution_skip_reason("x = 1\n", "python"), "no_entry_function")
            self.assertIsNone(execution_skip_reason(HEAPQ_CODE, "python"))
        finally:
            os.environ.pop("AZALEA_GEN_FOUNDATION_EXECUTE", None)


class ExecuteTests(unittest.TestCase):
    def setUp(self):
        os.environ["AZALEA_GEN_FOUNDATION_EXECUTE"] = "1"

    def tearDown(self):
        os.environ.pop("AZALEA_GEN_FOUNDATION_EXECUTE", None)

    def test_heapq_executes(self):
        res = execute(HEAPQ_CODE, "python", {"entry": "run", "args": [[3, 1, 2]]})
        self.assertIsInstance(res, ExecutionResult)
        self.assertEqual(res.status, "executed")
        self.assertEqual(res.return_value, [1, 2, 3])
        self.assertTrue(res.trace_events)
        self.assertIsNone(res.exception)

    def test_deque_executes(self):
        res = execute(DEQUE_CODE, "python", {"entry": "run", "args": [5]})
        self.assertEqual(res.status, "executed")
        self.assertEqual(res.return_value, [5])

    def test_disallowed_import_skipped(self):
        res = execute("import os\ndef run():\n    return os.getpid()\n", "python", {"entry": "run", "args": []})
        self.assertEqual(res.status, "skipped")
        self.assertEqual(res.skip_reason, "unsafe_or_unparseable")

    def test_runtime_exception_captured(self):
        res = execute("def run():\n    return [][1]\n", "python", {"entry": "run", "args": []})
        self.assertEqual(res.status, "error")
        self.assertIn("IndexError", res.exception or "")

    def test_run_trace_backcompat(self):
        events = run_trace(HEAPQ_CODE, "python", {"entry": "run", "args": [[3, 1, 2]]})
        self.assertTrue(events)
        self.assertEqual(_executor_final_answer(events), [1, 2, 3])


class SandboxTests(unittest.TestCase):
    def setUp(self):
        os.environ["AZALEA_GEN_FOUNDATION_EXECUTE"] = "1"

    def tearDown(self):
        os.environ.pop("AZALEA_GEN_FOUNDATION_EXECUTE", None)

    def test_subprocess_matches_in_process(self):
        from app.services.gen_foundation.executor import execute, execute_sandboxed
        code = "def run(x):\n    return x * 3\n"
        inp = {"entry": "run", "args": [7]}
        ip = execute(code, "python", inp)
        sb = execute_sandboxed(code, "python", inp)
        self.assertEqual(ip.return_value, 21)
        self.assertEqual(sb.return_value, 21)
        self.assertEqual(sb.status, "executed")
        self.assertTrue(sb.trace_events)


class AgreementTests(unittest.TestCase):
    def test_scalar_agreement(self):
        self.assertTrue(_answers_agree("MST weight 57", (57, [("A", "B")])))
        self.assertFalse(_answers_agree("MST weight 58", (57, [])))

    def test_sequence_agreement(self):
        self.assertTrue(_answers_agree("sorted [1, 2, 3]", [1, 2, 3]))

    def test_uncheckable_returns_none(self):
        self.assertIsNone(_answers_agree("the tree is balanced", "ok"))
        self.assertIsNone(_answers_agree("weight 5", "no numbers here"))


if __name__ == "__main__":
    unittest.main()
