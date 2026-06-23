"""Tests for the coding follow-up graph mutation (spec A.7 / B.5 step 5)."""
import unittest

from app.core.topic_decomposition_appender import append_coding_follow_ups, IMPLEMENTATION_FOLLOW_UP
from app.core.topic_decomposition_validator import validate_topic_decomposition


def cap(cid, *, prereqs=None, end=None, basis="goal"):
    return {"capability_id": cid, "ownership_mode": "standalone", "owner_topic_id": None,
            "prerequisite_capability_ids": prereqs or [], "satisfies_end_actions": end or [], "basis": basis}


def walkthrough(tid, cid, subject, *, end=None):
    return {"topic_id": tid, "capability_id": cid, "subject_key": subject, "primary_action": "trace",
            "content_role": "algorithm_trace", "topic_type": "algorithm_walkthrough",
            "practice_target": "trace it", "practice_format": "trace", "practice_evidence_type": "trace_state",
            "expected_output": f"trace of {subject}", "basis": "goal", "unit_title": "Walkthroughs"}


class AppenderTests(unittest.TestCase):
    def _plan(self):
        return {"end_capability_actions": ["trace"],
                "required_capabilities": [cap("bfs_trace", end=["trace"])]}

    def test_appends_follow_up_and_capability(self):
        plan, topics = append_coding_follow_ups(
            self._plan(), [walkthrough("t1", "bfs_trace", "breadth_first_search")])
        # topic added right after the walkthrough
        self.assertEqual([t["topic_id"] for t in topics], ["t1", "t1_implementation"])
        impl = topics[1]
        self.assertEqual(impl["topic_type"], "coding_implementation")
        self.assertEqual(impl["primary_action"], "implement")
        self.assertEqual(impl["topic_relationships"][0],
                         {"parent_topic_id": "t1", "relationship": IMPLEMENTATION_FOLLOW_UP})
        self.assertEqual(impl["basis"], "required_by_policy")
        self.assertEqual(impl["unit_title"], "Walkthroughs")  # inherits unit; Part C handles background
        # capability added to the graph with the parent as prerequisite
        cids = {c["capability_id"]: c for c in plan["required_capabilities"]}
        self.assertIn("breadth_first_search_implementation", cids)
        new = cids["breadth_first_search_implementation"]
        self.assertEqual(new["prerequisite_capability_ids"], ["bfs_trace"])
        self.assertEqual(new["satisfies_end_actions"], ["implement"])
        self.assertEqual(new["basis"], "required_by_policy")

    def test_idempotent_when_impl_exists(self):
        wt = walkthrough("t1", "bfs_trace", "breadth_first_search")
        existing = {"topic_id": "t2", "capability_id": "bfs_impl", "subject_key": "breadth_first_search",
                    "primary_action": "implement", "topic_type": "coding_implementation"}
        _, topics = append_coding_follow_ups(self._plan(), [wt, existing])
        impls = [t for t in topics if t.get("primary_action") == "implement"]
        self.assertEqual(len(impls), 1)  # no second follow-up synthesized

    def test_disabled_noop(self):
        plan, topics = append_coding_follow_ups(
            self._plan(), [walkthrough("t1", "bfs_trace", "breadth_first_search")], enabled=False)
        self.assertEqual(len(topics), 1)

    def test_append_then_validate_is_consistent(self):
        # End-to-end: synthesized follow-up + capability pass the validator with no gaps.
        plan, topics = append_coding_follow_ups(
            self._plan(), [walkthrough("t1", "bfs_trace", "breadth_first_search", end=["trace"])])
        res = validate_topic_decomposition(plan, topics)
        self.assertTrue(res.ok, [a.detail for a in res.actions])
        # the implementation capability is owned (not unowned)
        self.assertFalse(any("unowned" in a.detail for a in res.actions))
        # ordering: walkthrough before its coding follow-up
        idx = {t["topic_id"]: t["order_index"] for t in res.topics}
        self.assertLess(idx["t1"], idx["t1_implementation"])


if __name__ == "__main__":
    unittest.main()
