"""Tests for the shadow telemetry aggregator (Group 2)."""
import importlib.util
import os
import unittest

# load the standalone script module
_SPEC = importlib.util.spec_from_file_location(
    "aggregate_shadow_telemetry",
    os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "aggregate_shadow_telemetry.py"),
)
agg = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(agg)


def tel(family, *, executed, agreement=None, violations=None, blocked=False, skip=None, valid=True, state=None):
    return {"topic_family": family, "first_pass_valid": valid, "blocked": blocked,
            "executed": executed, "final_answer_agreement": agreement,
            "property_violations": violations or [], "execution_skip_reason": skip, "state_agreement": state}


class AggregateTests(unittest.TestCase):
    def test_per_family_rates(self):
        rows = [
            tel("graph_mst", executed=True, agreement=True, state=1.0),
            tel("graph_mst", executed=True, agreement=False, violations=["mst: V-1"], state=0.5),
            tel("graph_mst", executed=False, skip="unsafe_or_unparseable"),
            tel("array_sort", executed=True, agreement=True, state=1.0),
        ]
        out = agg.aggregate(rows)
        self.assertEqual(out["overall"]["runs"], 4)
        mst = out["per_family"]["graph_mst"]
        self.assertEqual(mst["n"], 3)
        self.assertAlmostEqual(mst["executed_rate"], round(2 / 3, 3))
        self.assertAlmostEqual(mst["answer_agreement_rate"], 0.5)      # 1 of 2 checkable agreed
        self.assertAlmostEqual(mst["property_violation_rate"], 0.5)    # 1 of 2 executed had a violation
        self.assertEqual(mst["top_skip_reasons"], {"unsafe_or_unparseable": 1})
        self.assertAlmostEqual(mst["avg_state_agreement"], 0.75)

    def test_card_failure_rollup(self):
        failures = [
            {"topic_family": "graph_mst", "card_key": "worked_example",
             "reason": "missing_required_card", "action": "regenerated"},
            {"topic_family": "graph_mst", "card_key": "worked_example",
             "reason": "missing_required_card", "action": "dropped"},
        ]
        out = agg.aggregate([tel("graph_mst", executed=True)], failures)
        cf = out["card_failures"]
        self.assertEqual(cf["total"], 2)
        self.assertEqual(cf["by_action"], {"regenerated": 1, "dropped": 1})
        self.assertAlmostEqual(cf["regeneration_recovery_rate"], 0.5)
        self.assertIn("graph_mst/worked_example", cf["actions_by_family_card"])

    def test_empty_safe(self):
        out = agg.aggregate([])
        self.assertEqual(out["overall"]["runs"], 0)
        self.assertEqual(out["per_family"], {})


if __name__ == "__main__":
    unittest.main()
