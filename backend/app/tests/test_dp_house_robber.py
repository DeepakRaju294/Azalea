"""House Robber (T5 dynamic programming) — focused correctness gate. The full ADAPTERS gauntlet already validates
every adapter's trace; this pins the house-robber oracle + trace explicitly (dp[i] = max(dp[i-1], dp[i-2]+nums[i]),
answer dp[n-1], every filled cell == the independent oracle).

Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_dp_house_robber
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples import trace_pipeline as tp
from app.services.examples.trace_adapters import ADAPTERS
from app.services.examples.trace_adapters.families.dp import _true_house_robber, _true_max_subarray


class HouseRobberOracle(unittest.TestCase):
    def test_known_values(self):
        self.assertEqual(_true_house_robber([2, 7, 9, 3, 1])[-1], 12)   # 2 + 9 + 1
        self.assertEqual(_true_house_robber([1, 2, 3, 1])[-1], 4)       # 1 + 3
        self.assertEqual(_true_house_robber([5])[-1], 5)
        self.assertEqual(_true_house_robber([2, 1, 1, 2])[-1], 4)       # 2 + 2

    def test_recurrence_holds(self):
        nums = [3, 8, 2, 6, 7]
        dp = _true_house_robber(nums)
        for i in range(2, len(nums)):
            self.assertEqual(dp[i], max(dp[i - 1], dp[i - 2] + nums[i]))


class HouseRobberTrace(unittest.TestCase):
    def setUp(self):
        self.adapter = ADAPTERS["house_robber"]

    def test_valid_teaching_trace_and_answer_matches_oracle(self):
        seen = 0
        for seed in range(20):
            tr = tp.select_instance(self.adapter, seed=seed)
            if tr is None:
                continue
            seen += 1
            self.assertEqual(tp.structural_invariants(tr, self.adapter), [])
            nums = list(tr.steps[0].prior_state["nums"])
            self.assertEqual(tr.final_answer, {"max_loot": _true_house_robber(nums)[-1]})
            # every filled cell equals the independent oracle
            dp = list(tr.steps[-1].state_after["dp"])
            self.assertEqual(dp, _true_house_robber(nums))
        self.assertGreater(seen, 0, "no valid house_robber teaching trace produced")


class MaxSubarrayOracle(unittest.TestCase):
    def test_known_values(self):
        self.assertEqual(max(_true_max_subarray([-2, 1, -3, 4, -1, 2, 1, -5, 4])), 6)   # [4,-1,2,1]
        self.assertEqual(max(_true_max_subarray([5, 4, -1, 7, 8])), 23)
        self.assertEqual(max(_true_max_subarray([-3, -1, -2])), -1)                     # all negative
        self.assertEqual(max(_true_max_subarray([2])), 2)

    def test_recurrence_holds(self):
        nums = [3, -2, 5, -1, 6]
        dp = _true_max_subarray(nums)
        for i in range(1, len(nums)):
            self.assertEqual(dp[i], max(nums[i], dp[i - 1] + nums[i]))


class MaxSubarrayTrace(unittest.TestCase):
    def test_valid_teaching_trace_and_answer_is_max_of_dp(self):
        adapter = ADAPTERS["max_subarray"]
        seen = 0
        for seed in range(30):
            tr = tp.select_instance(adapter, seed=seed)
            if tr is None:
                continue
            seen += 1
            self.assertEqual(tp.structural_invariants(tr, adapter), [])
            nums = list(tr.steps[0].prior_state["nums"])
            self.assertEqual(tr.final_answer, {"max_sum": max(_true_max_subarray(nums))})
            dp = list(tr.steps[-1].state_after["dp"])
            self.assertEqual(dp, _true_max_subarray(nums))
        self.assertGreater(seen, 0, "no valid max_subarray teaching trace produced")


if __name__ == "__main__":
    unittest.main()
