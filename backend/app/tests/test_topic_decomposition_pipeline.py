"""Tests for the topic-decomposition generation orchestration (injected LLM, no API call)."""
import unittest

from app.services.topic_decomposition_pipeline import generate_decomposed_topics


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

    def test_no_duplicate_and_ordered(self):
        topics = self._run()
        # graph foundation, BFS trace, then the appended coding follow-up
        self.assertEqual([t["title"] for t in topics],
                         ["Representing Graphs", "Tracing BFS", "Implementing Breadth First Search"])

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
        self.assertEqual(topics[0]["subject_key"], "prim")  # trailing 'algorithm' stripped


if __name__ == "__main__":
    unittest.main()
