"""Tests for the deterministic topic-decomposition validator (spec B.4)."""
import unittest

from app.core.topic_decomposition_validator import (
    validate_topic_decomposition,
    CLEAR_DUPLICATE, SAFE_REPAIR, AMBIGUOUS_OVERLAP, SUBJECT_MERGE,
)


def cap(cid, *, mode="standalone", owner=None, prereqs=None, end=None, basis="goal"):
    return {"capability_id": cid, "ownership_mode": mode, "owner_topic_id": owner,
            "prerequisite_capability_ids": prereqs or [], "satisfies_end_actions": end or [], "basis": basis}


def topic(tid, cid, *, subject, action, role, evidence, output, parents=None,
          tt="algorithm_walkthrough", basis="goal", practice_format="trace"):
    return {
        "topic_id": tid, "capability_id": cid, "subject_key": subject, "primary_action": action,
        "content_role": role, "topic_type": tt, "practice_evidence_type": evidence,
        "expected_output": output, "basis": basis,
        "practice_target": f"do {action}", "practice_format": practice_format,
        "topic_relationships": [{"parent_topic_id": p, "relationship": "implementation_follow_up"} for p in (parents or [])],
    }


class DuplicateTests(unittest.TestCase):
    def _plan(self):
        return {"end_capability_actions": [], "required_capabilities": [cap("bfs_understand")]}

    def test_clear_duplicate_dropped(self):
        # Two standalone topics owning the SAME capability -> the later is a clear duplicate.
        a = topic("t1", "bfs_understand", subject="breadth_first_search", action="understand",
                  role="foundation", evidence="explain_model", output="explain why BFS finds distance")
        b = topic("t2", "bfs_understand", subject="breadth_first_search", action="explain",
                  role="foundation", evidence="explain_model", output="explain why BFS finds distance")
        res = validate_topic_decomposition(self._plan(), [a, b])
        ids = [t["topic_id"] for t in res.topics]
        self.assertEqual(ids, ["t1"])  # later duplicate dropped
        self.assertTrue(any(x.outcome == CLEAR_DUPLICATE for x in res.actions))

    def test_trace_vs_implement_kept(self):
        plan = {"end_capability_actions": [],
                "required_capabilities": [cap("bfs_trace"), cap("bfs_impl")]}
        a = topic("t1", "bfs_trace", subject="breadth_first_search", action="trace",
                  role="algorithm_trace", evidence="trace_state", output="visit order + queue")
        b = topic("t2", "bfs_impl", subject="breadth_first_search", action="implement",
                  role="implementation", evidence="write_code", output="working function",
                  tt="coding_implementation", parents=["t1"], practice_format="coding")
        res = validate_topic_decomposition(plan, [a, b])
        self.assertEqual({t["topic_id"] for t in res.topics}, {"t1", "t2"})  # complementary, kept

    def test_sole_owner_guard_not_dropped(self):
        # both look like clear duplicates, but t2 is the sole owner of a required capability
        plan = {"end_capability_actions": [],
                "required_capabilities": [cap("c1"), cap("c2")]}
        a = topic("t1", "c1", subject="bfs", action="understand", role="foundation",
                  evidence="explain_model", output="same thing")
        b = topic("t2", "c2", subject="bfs", action="explain", role="foundation",
                  evidence="explain_model", output="same thing")
        res = validate_topic_decomposition(plan, [a, b])
        self.assertEqual({t["topic_id"] for t in res.topics}, {"t1", "t2"})  # c2 sole owner -> guard
        self.assertTrue(any(x.outcome == AMBIGUOUS_OVERLAP for x in res.actions))

    def test_ambiguous_resolver_can_drop(self):
        plan = {"end_capability_actions": [],
                "required_capabilities": [cap("c1"), cap("c1")]}  # same cap owned twice -> both removable
        a = topic("t1", "c1", subject="bfs", action="understand", role="foundation",
                  evidence="explain_model", output="output A")
        b = topic("t2", "c1", subject="bfs", action="understand", role="comparison",
                  evidence="explain_model", output="output B")  # diff role+output -> ambiguous
        res = validate_topic_decomposition(
            plan, [a, b], resolve_overlap=lambda x, y: {"decision": "drop_topic", "surviving_topic_id": "t1"})
        self.assertEqual([t["topic_id"] for t in res.topics], ["t1"])


class SubjectMergeTests(unittest.TestCase):
    def test_understand_plus_apply_merge_into_one_topic(self):
        # THE over-decomposition regression: the model split one concept into "understand" + "apply".
        plan = {"end_capability_actions": ["apply"],
                "required_capabilities": [
                    cap("understand_bayes"),
                    cap("apply_bayes", prereqs=["understand_bayes"], end=["apply"])]}
        u = topic("t_u", "understand_bayes", subject="bayes_theorem", action="understand",
                  role="foundation", evidence="explain_model", output="explain Bayes",
                  tt="concept_intuition", practice_format="short_answer")
        a = topic("t_a", "apply_bayes", subject="bayes_theorem_application", action="apply",
                  role="application", evidence="solve_numeric", output="a solved Bayes problem",
                  tt="problem_solving_application", practice_format="math_input")
        res = validate_topic_decomposition(plan, [u, a])
        self.assertEqual(len(res.topics), 1)                                   # one topic, not two
        self.assertEqual(res.topics[0]["topic_type"], "problem_solving_application")  # richer arc wins
        self.assertTrue(any(x.outcome == SUBJECT_MERGE for x in res.actions))
        self.assertTrue(res.ok)                                               # coverage still satisfied
        self.assertTrue(res.topics[0]["expected_output"])                     # stayed practice-capable

    def test_same_action_same_subject_is_NOT_merged(self):
        # two topics, same subject, SAME action -> that's a duplicate/ambiguous case, not a facet split:
        # the merge must leave it to the sole-owner guard (both kept), never silently fold them.
        plan = {"end_capability_actions": [],
                "required_capabilities": [cap("c1"), cap("c2")]}
        a = topic("t1", "c1", subject="bayes_theorem", action="understand", role="foundation",
                  evidence="explain_model", output="same", tt="concept_intuition")
        b = topic("t2", "c2", subject="bayes_theorem", action="explain", role="foundation",
                  evidence="explain_model", output="same", tt="concept_intuition")
        res = validate_topic_decomposition(plan, [a, b])
        self.assertFalse(any(x.outcome == SUBJECT_MERGE for x in res.actions))
        self.assertEqual({t["topic_id"] for t in res.topics}, {"t1", "t2"})   # sole-owner guard, both kept

    def test_trace_vs_implement_not_merged(self):
        # coding_implementation is excluded — trace vs implement is a genuine split, kept as two topics.
        plan = {"end_capability_actions": ["implement"],
                "required_capabilities": [cap("bfs_trace"), cap("bfs_impl", end=["implement"])]}
        a = topic("t1", "bfs_trace", subject="breadth_first_search", action="trace",
                  role="algorithm_trace", evidence="trace_state", output="visit order")
        b = topic("t2", "bfs_impl", subject="breadth_first_search", action="implement",
                  role="implementation", evidence="write_code", output="working function",
                  tt="coding_implementation", practice_format="coding")
        res = validate_topic_decomposition(plan, [a, b])
        self.assertFalse(any(x.outcome == SUBJECT_MERGE for x in res.actions))
        self.assertEqual({t["topic_id"] for t in res.topics}, {"t1", "t2"})


class RepairAndCoverageTests(unittest.TestCase):
    def test_safe_repair_coding_practice(self):
        plan = {"end_capability_actions": ["implement"],
                "required_capabilities": [cap("impl", end=["implement"])]}
        t = topic("t1", "impl", subject="bfs", action="implement", role="implementation",
                  evidence="write_code", output="function", tt="coding_implementation",
                  parents=["p1"], practice_format="trace")  # inherited trace practice
        res = validate_topic_decomposition(plan, [t])
        self.assertEqual(res.topics[0]["practice_format"], "coding")
        self.assertTrue(any(x.outcome == SAFE_REPAIR for x in res.actions))

    def test_order_index_follows_prereqs(self):
        plan = {"end_capability_actions": [],
                "required_capabilities": [cap("a"), cap("b", prereqs=["a"])]}
        tb = topic("tb", "b", subject="s", action="trace", role="algorithm_trace",
                   evidence="trace_state", output="b")
        ta = topic("ta", "a", subject="s2", action="understand", role="foundation",
                   evidence="explain_model", output="a")
        res = validate_topic_decomposition(plan, [tb, ta])  # given out of order
        idx = {t["topic_id"]: t["order_index"] for t in res.topics}
        self.assertLess(idx["ta"], idx["tb"])  # prerequisite 'a' first

    def test_unowned_standalone_capability_is_repaired(self):
        # B.4.1 coverage REPAIR: a required standalone capability the model dropped is SYNTHESIZED, not failed,
        # so a goal's named concept always gets a topic (fixes the dropped-concept bug).
        plan = {"end_capability_actions": [],
                "required_capabilities": [cap("missing")]}
        res = validate_topic_decomposition(plan, [])
        self.assertTrue(res.ok)                                            # repaired, not failed
        self.assertEqual([t["capability_id"] for t in res.topics], ["missing"])   # a topic now owns it
        self.assertTrue(any(x.outcome == "REPAIR" for x in res.actions))

    def test_embedded_capability_without_owner_still_fails(self):
        # embedded/unowned-mode gaps are NOT auto-repaired (ambiguous) — they still flag
        plan = {"end_capability_actions": [],
                "required_capabilities": [cap("emb", mode="embedded", owner=None)]}
        res = validate_topic_decomposition(plan, [])
        self.assertFalse(res.ok)
        self.assertTrue(any("no owner" in x.detail for x in res.actions))

    def test_orientation_intro_is_always_ordered_first(self):
        # The intro must lead the path even when the LLM wired the capability graph so it would sort last
        # (here the intro capability declares the concepts as its prereqs -> topo rank would put it last).
        plan = {"end_capability_actions": [],
                "required_capabilities": [
                    cap("bayes"), cap("total_prob"),
                    cap("orientation", prereqs=["bayes", "total_prob"])]}
        intro = topic("t_intro", "orientation", subject="probability", action="understand",
                      role="orientation", evidence="explain_model", output="orientation",
                      tt="study_path_introduction", practice_format="none")
        tb = topic("t_b", "bayes", subject="bayes_theorem", action="understand", role="calculation",
                   evidence="solve_numeric", output="P(A|B)", tt="math_formula_method")
        tt = topic("t_t", "total_prob", subject="total_probability", action="understand",
                   role="calculation", evidence="solve_numeric", output="P(A)", tt="math_formula_method")
        res = validate_topic_decomposition(plan, [tb, tt, intro])
        first = min(res.topics, key=lambda t: t["order_index"])
        self.assertEqual(first["topic_id"], "t_intro")   # intro leads despite the graph
        self.assertEqual(first["order_index"], 1)

    def test_reachability_requires_practice_capable_owner(self):
        plan = {"end_capability_actions": ["implement"],
                "required_capabilities": [cap("impl", end=["implement"])]}
        # owner exists but is NOT practice-capable (no expected_output)
        t = topic("t1", "impl", subject="bfs", action="implement", role="implementation",
                  evidence="write_code", output="")
        res = validate_topic_decomposition(plan, [t])
        self.assertFalse(res.ok)
        self.assertTrue(any(x.rule == "reachability" for x in res.actions))

    def test_full_valid_path_ok(self):
        plan = {"end_capability_actions": ["trace", "implement"],
                "required_capabilities": [
                    cap("bfs_trace", end=["trace"]),
                    cap("bfs_impl", prereqs=["bfs_trace"], end=["implement"], basis="required_by_policy")]}
        ta = topic("t1", "bfs_trace", subject="breadth_first_search", action="trace",
                   role="algorithm_trace", evidence="trace_state", output="visit order")
        tb = topic("t2", "bfs_impl", subject="breadth_first_search", action="implement",
                   role="implementation", evidence="write_code", output="working function",
                   tt="coding_implementation", parents=["t1"], practice_format="coding", basis="required_by_policy")
        res = validate_topic_decomposition(plan, [ta, tb])
        self.assertTrue(res.ok, [a.detail for a in res.actions])
        self.assertEqual(len(res.topics), 2)


if __name__ == "__main__":
    unittest.main()
