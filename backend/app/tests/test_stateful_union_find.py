"""Union-Find (T10 stateful) — focused correctness gate. The stateful-engine gate + ADAPTERS gauntlet already
validate every spec; this pins union-find's component count against an independent replay + a hand-checked case.

Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_stateful_union_find
"""
import os
import random
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples import trace_pipeline as tp
from app.services.examples.trace_adapters import ADAPTERS
from app.services.examples.trace_adapters.families import stateful_specs as ss


def _spec():
    return [s for s in ss.ALL_SPECS if s.slug == "union_find"][0]


class UnionFindOracle(unittest.TestCase):
    def test_hand_checked_case(self):
        spec = _spec()
        # 6 elements; union(0,1), union(2,3), union(1,3) -> {0,1,2,3},{4},{5} = 3 components
        s0 = {"ops": [("union", 0, 1), ("union", 2, 3), ("union", 1, 3)], "parent": list(range(6)), "n": 6}
        self.assertEqual(spec.oracle(s0), {"components": "3"})

    def test_apply_matches_oracle_over_full_script(self):
        spec = _spec()
        for seed in range(15):
            s0 = spec.setup(random.Random(seed))
            s = dict(s0)
            for i in range(spec.ops_count(s0)):
                s, _prose = spec.apply(s, i)
            self.assertEqual(spec.answer(s), spec.oracle(s0))     # step-by-step == independent replay


class UnionFindTrace(unittest.TestCase):
    def test_valid_teaching_trace(self):
        adapter = ADAPTERS["union_find"]
        seen = 0
        for seed in range(15):
            tr = tp.select_instance(adapter, seed=seed)
            if tr is None:
                continue
            seen += 1
            self.assertEqual(tp.structural_invariants(tr, adapter), [])
        self.assertGreater(seen, 0, "no valid union_find teaching trace produced")


if __name__ == "__main__":
    unittest.main()
