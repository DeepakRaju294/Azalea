"""Tests for the topic-decomposition generation orchestration (injected LLM, no API call)."""
import copy
import os
import unittest

from app.services.topic_decomposition_pipeline import generate_decomposed_topics

_LIVE_FLAG = "AZALEA_PREREQ_SCOPE_LIVE"


# A realistic single-call response: a BFS path with a trace topic; the coding follow-up is appended.
FAKE_RESPONSE = {
    "path_plan": {
        "end_capability": "Trace and implement BFS on a graph.",
        "end_capability_actions": ["trace", "implement"],
        "required_capabilities": [
            {"capability_id": "graph_rep", "description": "Represent a graph.",
             "prerequisite_capability_ids": [], "satisfies_end_actions": [],
             "ownership_mode": "standalone", "owner_topic_id": None, "basis": "goal"},
            {"capability_id": "bfs_trace", "description": "Trace BFS.",
             "prerequisite_capability_ids": ["graph_rep"], "satisfies_end_actions": ["trace"],
             "ownership_mode": "standalone", "owner_topic_id": None, "basis": "goal"},
        ],
    },
    "topics": [
        {"topic_id": "t_graph", "capability_id": "graph_rep", "subject_key": "graph",
         "primary_action": "represent", "content_role": "foundation", "topic_type": "concept_intuition",
         "title": "Representing Graphs", "unit_title": "Foundations", "purpose": "p", "in_scope": ["nodes"],
         "practice_target": "draw a graph", "practice_format": "short_answer",
         "practice_evidence_type": "explain_model", "expected_output": "a graph drawing", "basis": "goal"},
        {"topic_id": "t_bfs", "capability_id": "bfs_trace", "subject_key": "breadth_first_search",
         "primary_action": "trace", "content_role": "algorithm_trace", "topic_type": "algorithm_walkthrough",
         "title": "Tracing BFS", "unit_title": "Algorithms", "purpose": "p", "in_scope": ["queue"],
         "practice_target": "trace BFS", "practice_format": "trace",
         "practice_evidence_type": "trace_state", "expected_output": "visit order", "basis": "goal"},
    ],
}


class PipelineTests(unittest.TestCase):
    def _run(self, response=FAKE_RESPONSE):
        return generate_decomposed_topics("learn BFS", "source", model_fn=lambda payload: response)

    def test_produces_legacy_shaped_topics(self):
        topics = self._run()
        for t in topics:
            for field in ("title", "topic_type", "course_type", "unit_title", "order_index",
                          "purpose", "in_scope", "practice_format"):
                self.assertIn(field, t)
        self.assertEqual([t["order_index"] for t in topics], list(range(1, len(topics) + 1)))

    def test_coding_follow_up_appended_with_part_c_signal(self):
        topics = self._run()
        titles = [t["title"] for t in topics]
        self.assertIn("Implementing Breadth First Search", titles)
        impl = next(t for t in topics if t["title"] == "Implementing Breadth First Search")
        self.assertEqual(impl["topic_type"], "coding_implementation")
        self.assertEqual(impl["relationship_to_parent"], "implementation_follow_up")
        self.assertIn("implementation_follow_up", impl["modifiers"])  # carried for Part C
        self.assertEqual(impl["basis"], "required_by_policy")
        # prerequisite points at the walkthrough's TITLE (legacy string form)
        self.assertEqual(impl["prerequisite_topics"], "Tracing BFS")

    def test_coding_follow_ups_disabled_skips_implementation_topic(self):
        # Non-coding domains (coding_follow_ups=False): NO 'Implementing X' topic is appended.
        topics = generate_decomposed_topics(
            "learn BFS", "source", model_fn=lambda p: FAKE_RESPONSE, coding_follow_ups=False)
        titles = [t["title"] for t in topics]
        self.assertNotIn("Implementing Breadth First Search", titles)
        self.assertFalse(any(t.get("course_type") == "coding_implementation" for t in topics))

    def test_no_duplicate_and_ordered(self):
        topics = self._run()
        # 'Representing Graphs' is a FOUNDATION -> folded into a synthesized intro as an assumed prerequisite;
        # the taught topics are the BFS trace + its appended coding follow-up, in order.
        self.assertEqual([t["title"] for t in topics],
                         ["Introduction to Bfs", "Tracing BFS", "Implementing Breadth First Search"])
        intro = topics[0]
        self.assertEqual(intro["course_type"], "study_path_introduction")
        self.assertIn("Representing Graphs", intro.get("assumed_prerequisites") or [])

    def test_persists_audit_blob(self):
        impl = next(t for t in self._run() if t["title"] == "Implementing Breadth First Search")
        meta = impl["decomposition_metadata"]
        self.assertEqual(meta["schema_version"], 1)
        self.assertEqual(meta["subject_key"], "breadth_first_search")
        self.assertEqual(meta["primary_action"], "implement")
        self.assertEqual(meta["basis"], "required_by_policy")
        self.assertEqual(meta["relationship_to_parent"], "implementation_follow_up")

    def test_injected_resolver_drops_ambiguous(self):
        # two same-subject topics with the same action but different roles/outputs -> ambiguous;
        # an injected resolver that keeps the first should drop the second.
        resp = {"path_plan": {"end_capability_actions": [], "required_capabilities": [
                    {"capability_id": "c", "ownership_mode": "standalone",
                     "prerequisite_capability_ids": [], "satisfies_end_actions": [], "basis": "goal"}]},
                "topics": [
                    {"topic_id": "a", "capability_id": "c", "subject_key": "heap", "primary_action": "trace",
                     "content_role": "algorithm_trace", "topic_type": "algorithm_walkthrough", "title": "Heap A",
                     "practice_evidence_type": "trace_state", "expected_output": "out A", "basis": "goal",
                     "practice_target": "x", "practice_format": "trace"},
                    {"topic_id": "b", "capability_id": "c", "subject_key": "heap", "primary_action": "trace",
                     "content_role": "comparison", "topic_type": "comparison_table", "title": "Heap B",
                     "practice_evidence_type": "trace_state", "expected_output": "out B", "basis": "goal",
                     "practice_target": "y", "practice_format": "trace"}],
                }
        topics = generate_decomposed_topics(
            "g", "s", model_fn=lambda p: resp,
            resolve_overlap=lambda x, y: {"decision": "drop_topic", "surviving_topic_id": "a"})
        titles = [t["title"] for t in topics]
        self.assertIn("Heap A", titles)
        self.assertNotIn("Heap B", titles)

    def test_empty_response_returns_empty(self):
        self.assertEqual(generate_decomposed_topics("g", "s", model_fn=lambda p: {}), [])
        self.assertEqual(generate_decomposed_topics("g", "s", model_fn=lambda p: "not json"), [])

    def test_subject_key_normalized(self):
        resp = {"path_plan": {"end_capability_actions": [], "required_capabilities": [
                    {"capability_id": "c", "ownership_mode": "standalone", "prerequisite_capability_ids": [],
                     "satisfies_end_actions": [], "basis": "goal"}]},
                "topics": [{"topic_id": "t", "capability_id": "c", "subject_key": "Prim's Algorithm",
                            "primary_action": "trace", "content_role": "algorithm_trace",
                            "topic_type": "algorithm_walkthrough", "title": "Prim's", "basis": "goal",
                            "practice_format": "trace", "practice_evidence_type": "trace_state",
                            "expected_output": "x", "practice_target": "y"}]}
        topics = generate_decomposed_topics("g", "s", model_fn=lambda p: resp)
        prim = next(t for t in topics if t["title"] == "Prim's")   # topics[0] is now the synthesized intro
        self.assertEqual(prim["subject_key"], "prim")              # trailing 'algorithm' stripped


class GuardFourScopeClassifier(unittest.TestCase):
    """AZALEA_PREREQ_SCOPE_LIVE (Guard 4): the real §3.1 classifier as an additional, one-directional
    override on the foundation-fold cascade. Off by default; per-candidate isolated; a classifier failure
    or disagreement degrades to today's existing fold (same outcome as test_no_duplicate_and_ordered)."""

    def setUp(self):
        self._prev = os.environ.get(_LIVE_FLAG)

    def tearDown(self):
        if self._prev is None:
            os.environ.pop(_LIVE_FLAG, None)
        else:
            os.environ[_LIVE_FLAG] = self._prev

    def _run(self, live, scope_fn, response=FAKE_RESPONSE):
        if live:
            os.environ[_LIVE_FLAG] = "1"
        else:
            os.environ.pop(_LIVE_FLAG, None)
        return generate_decomposed_topics(
            "learn BFS", "source", model_fn=lambda p: response, domain="cs",
            prereq_scope_model_fn=scope_fn)

    def test_flag_off_by_default_ignores_an_in_scope_classifier(self):
        # Even with a classifier that WOULD keep it taught, the flag being off means Guard 4 never runs.
        fn = lambda p: {"scope_rule": "explicit_objective", "scope_rationale": "x"}
        topics = self._run(live=False, scope_fn=fn)
        intro = topics[0]
        self.assertIn("Representing Graphs", intro.get("assumed_prerequisites") or [])
        self.assertNotIn("Representing Graphs", [t["title"] for t in topics])
        trace = (intro.get("decomposition_metadata") or {}).get("path_decision_trace") or []
        self.assertFalse(any(e["stage"] == "topics.foundation_kept_by_scope_classifier" for e in trace))

    def test_flag_on_classifier_in_scope_keeps_it_taught(self):
        fn = lambda p: {"scope_rule": "explicit_objective", "scope_rationale": "the goal requires it"}
        topics = self._run(live=True, scope_fn=fn)
        self.assertIn("Representing Graphs", [t["title"] for t in topics])
        intro = next(t for t in topics if t["course_type"] == "study_path_introduction")
        self.assertNotIn("Representing Graphs", intro.get("assumed_prerequisites") or [])
        trace = (intro.get("decomposition_metadata") or {}).get("path_decision_trace") or []
        kept = [e for e in trace if e["stage"] == "topics.foundation_kept_by_scope_classifier"]
        self.assertEqual(len(kept), 1)
        self.assertIn("Representing Graphs", kept[0]["decision"])

    def test_flag_on_classifier_fallback_is_a_no_op(self):
        fn = lambda p: {"scope_rule": "recognition_only_fallback", "scope_rationale": ""}
        topics = self._run(live=True, scope_fn=fn)
        intro = topics[0]
        self.assertIn("Representing Graphs", intro.get("assumed_prerequisites") or [])
        self.assertNotIn("Representing Graphs", [t["title"] for t in topics])

    def test_flag_on_classifier_raises_degrades_to_fold_without_propagating(self):
        def fn(payload):
            raise RuntimeError("simulated classifier failure")
        topics = self._run(live=True, scope_fn=fn)   # must not raise
        intro = topics[0]
        self.assertIn("Representing Graphs", intro.get("assumed_prerequisites") or [])
        self.assertNotIn("Representing Graphs", [t["title"] for t in topics])

    def test_one_failing_candidate_does_not_suppress_another(self):
        resp = copy.deepcopy(FAKE_RESPONSE)
        resp["path_plan"]["required_capabilities"].append(
            {"capability_id": "graph_units", "description": "Units.", "prerequisite_capability_ids": [],
             "satisfies_end_actions": [], "ownership_mode": "standalone", "owner_topic_id": None,
             "basis": "goal"})
        resp["topics"].insert(1, {
            "topic_id": "t_units", "capability_id": "graph_units", "subject_key": "graph_units",
            "primary_action": "represent", "content_role": "foundation", "topic_type": "concept_intuition",
            "title": "Units of Measurement", "unit_title": "Foundations", "purpose": "p",
            "in_scope": ["units"], "practice_target": "x", "practice_format": "short_answer",
            "practice_evidence_type": "explain_model", "expected_output": "y", "basis": "goal",
        })

        def fn(payload):
            if payload.get("canonical_name") == "Representing Graphs":
                raise RuntimeError("simulated failure for this one candidate")
            return {"scope_rule": "explicit_objective", "scope_rationale": "kept"}

        topics = self._run(live=True, scope_fn=fn, response=resp)
        titles = [t["title"] for t in topics]
        intro = topics[0]
        # the failing candidate still folds (today's behavior) ...
        self.assertNotIn("Representing Graphs", titles)
        self.assertIn("Representing Graphs", intro.get("assumed_prerequisites") or [])
        # ... but the other candidate is unaffected and stays taught
        self.assertIn("Units of Measurement", titles)
        self.assertNotIn("Units of Measurement", intro.get("assumed_prerequisites") or [])


if __name__ == "__main__":
    unittest.main()
