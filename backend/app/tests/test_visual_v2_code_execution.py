"""Visual System V2 — code_execution mode (Phase 1 golden). Pure backend, no LLM.

Proves "run once, read the truth": the inorder code is executed a single time and
the recorded line/variable/output trace is the source of the visual. Deterministic.
Run: python -m unittest app.tests.test_visual_v2_code_execution
"""
from __future__ import annotations

import unittest

from app.services.visual_v2.compilers.code_execution import compile_from_trace
from app.services.visual_v2.delta_fold import DeltaFoldEngine
from app.services.visual_v2.example_invariants import validate_example
from app.services.visual_v2.profiles import delta_vocabulary, profile_for_mode
from app.services.visual_v2.simulators.code_tracer import (
    TreeNode,
    build_tree,
    serialize_value,
    simulate_code_execution,
    trace_execution,
)

CODE = """def inorderTraversal(root):
    result = []
    traverse(root, result)
    return result

def traverse(node, result):
    if node is None:
        return
    traverse(node.left, result)
    result.append(node.val)
    traverse(node.right, result)"""

EXAMPLE = {
    "example_id": "inorder",
    "base_type": "code_execution_panel",
    "mode": "code_execution",
    "algorithm": "code_execution",
    "code": CODE,
    "entry_function": "inorderTraversal",
    "input": {"tree": [2, 1, 3]},  # BST → inorder = [1, 2, 3]
}

BASE_CASE_LINE = 7   # `if node is None:`
APPEND_LINE = 10     # `result.append(node.val)`


class TestPrimitives(unittest.TestCase):
    def test_build_tree_levelorder(self):
        root = build_tree([2, 1, 3])
        self.assertEqual(root.val, 2)
        self.assertEqual(root.left.val, 1)
        self.assertEqual(root.right.val, 3)

    def test_serialize_treenode_to_value(self):
        self.assertEqual(serialize_value(TreeNode(5)), 5)
        self.assertEqual(serialize_value([TreeNode(1), TreeNode(2)]), [1, 2])
        self.assertIsNone(serialize_value(None))


class TestTraceTruth(unittest.TestCase):
    def setUp(self):
        self.steps, self.result = trace_execution(CODE, "inorderTraversal", {"tree": [2, 1, 3]})

    def test_actual_return_is_sorted_inorder(self):
        self.assertEqual(self.result, [1, 2, 3])

    def test_base_case_line_runs_multiple_times_incl_none(self):
        # The `if node is None` check executes on every call — real nodes AND None.
        hits = [s for s in self.steps if s["line"] == BASE_CASE_LINE]
        self.assertGreaterEqual(len(hits), 4)

    def test_append_line_runs_once_per_node(self):
        appends = [s for s in self.steps if s["line"] == APPEND_LINE]
        self.assertEqual(len(appends), 3)

    def test_call_stack_recorded(self):
        deep = [s for s in self.steps if len(s["call_stack"]) >= 2]
        self.assertTrue(deep)  # inorderTraversal › traverse › traverse …
        self.assertEqual(self.steps[0]["call_stack"][0], "inorderTraversal")


class TestSimulateAndFold(unittest.TestCase):
    def setUp(self):
        self.trace = simulate_code_execution(EXAMPLE)
        self.frames = DeltaFoldEngine().fold(
            self.trace["initial_state"], self.trace["steps"], set(), delta_vocabulary("code_execution")
        )

    def test_trace_source(self):
        self.assertEqual(self.trace["trace_source"], "deterministic_simulator")
        self.assertTrue(len(self.trace["steps"]) > 8)

    def test_each_frame_highlights_one_line(self):
        for frame in self.frames:
            self.assertEqual(len(frame["state_after"]["highlight_lines"]), 1)

    def test_final_output_is_the_real_result(self):
        self.assertEqual(self.frames[-1]["state_after"]["output"], [1, 2, 3])

    def test_output_grows_monotonically(self):
        outputs = [f["state_after"]["output"] for f in self.frames if f["state_after"]["output"]]
        for earlier, later in zip(outputs, outputs[1:]):
            self.assertEqual(later[: len(earlier)], earlier)  # only ever appends


class TestCodeExecutionCompiler(unittest.TestCase):
    def setUp(self):
        self.trace = simulate_code_execution(EXAMPLE)
        self.frames = DeltaFoldEngine().fold(
            self.trace["initial_state"], self.trace["steps"], set(), delta_vocabulary("code_execution")
        )
        self.model, self.render_steps = compile_from_trace(
            trace=self.trace, frames=self.frames, code=CODE,
            profile=profile_for_mode("code_execution"), model_id="m1",
        )

    def test_model_shape_matches_frontend(self):
        self.assertEqual(self.model["base_type"], "code_execution_panel")
        self.assertEqual(self.model["base"]["code"], CODE)
        self.assertEqual(self.model["base"]["language"], "python")
        self.assertEqual(len(self.model["frames"]), len(self.trace["steps"]))
        self.assertIn("element_catalog", self.model)

    def test_frame_matches_CodeFrameState_contract(self):
        frame = self.model["frames"][0]
        # VisualFrame wrapper the renderer needs.
        for key in ("index", "state", "selectable_elements", "transitions"):
            self.assertIn(key, frame)
        state = frame["state"]
        # highlight_lines is a [start, end] RANGE (CodeExecutionPanel reads [hStart, hEnd]).
        self.assertEqual(len(state["highlight_lines"]), 2)
        # variables is an array of {name, value:str}.
        self.assertTrue(all(set(v) == {"name", "value"} and isinstance(v["value"], str) for v in state["variables"]))
        # call_stack is string[]; output is string[].
        self.assertTrue(all(isinstance(x, str) for x in state["call_stack"]))
        self.assertTrue(all(isinstance(x, str) for x in state["output"]))
        self.assertIn("visible_until_line", state)

    def test_final_output_renders_result(self):
        self.assertEqual(self.model["frames"][-1]["state"]["output"], ["1, 2, 3"])

    def test_render_steps_aligned(self):
        self.assertEqual(len(self.render_steps), len(self.frames))
        self.assertTrue(all(rs["caption"] for rs in self.render_steps))


class TestSandbox(unittest.TestCase):
    """Subprocess sandbox (spawns real processes; a bit slower)."""

    def test_sandboxed_matches_in_process(self):
        from app.services.visual_v2.simulators.sandbox import run_sandboxed

        steps_in, result_in = trace_execution(CODE, "inorderTraversal", {"tree": [2, 1, 3]})
        steps_sb, result_sb = run_sandboxed(CODE, "inorderTraversal", {"tree": [2, 1, 3]})
        self.assertEqual(result_sb, result_in)
        self.assertEqual(len(steps_sb), len(steps_in))

    def test_simulate_sandboxed_produces_trace(self):
        trace = simulate_code_execution(EXAMPLE, sandboxed=True)
        self.assertEqual(trace["trace_source"], "deterministic_simulator")
        self.assertTrue(len(trace["steps"]) > 8)

    def test_infinite_loop_is_step_capped_not_hung(self):
        # The step cap stops a busy loop and returns a (capped) trace — no hang.
        from app.services.visual_v2.simulators.sandbox import run_sandboxed

        steps, result = run_sandboxed("def f(x):\n    while True:\n        x = x + 1", "f", {"args": [0]})
        self.assertTrue(len(steps) > 0)
        self.assertIsNone(result)

    def test_blocking_call_times_out(self):
        # A C-level block (no line events) is caught by the subprocess timeout.
        from app.services.visual_v2.simulators.sandbox import SandboxError, run_sandboxed

        with self.assertRaises(SandboxError):
            run_sandboxed("import time\ndef f(x):\n    time.sleep(10)", "f", {"args": [0]}, timeout=1.0)


class TestCodeExampleValidator(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate_example(EXAMPLE), [])

    def test_missing_entry_function(self):
        ex = {**EXAMPLE, "entry_function": "doesNotExist"}
        self.assertTrue(any("not defined" in e for e in validate_example(ex)))

    def test_unparseable_code(self):
        ex = {**EXAMPLE, "code": "def f(:\n  pass"}
        self.assertTrue(any("does not parse" in e for e in validate_example(ex)))

    def test_no_input(self):
        ex = {**EXAMPLE, "input": {}}
        self.assertTrue(any("constructible input" in e for e in validate_example(ex)))


if __name__ == "__main__":
    unittest.main()
