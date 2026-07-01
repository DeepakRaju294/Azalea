"""The 'no applicable adapter' system: routing SAFETY (an intro/overview topic must not grab a computational
adapter) and the missing-adapter DEMAND tracker (computational topics with no adapter are recorded for the
build-next queue)."""
import os
import tempfile
import unittest

from app.services.examples.trace_pipeline import route_adapter


class RoutingSafety(unittest.TestCase):
    def test_worked_topics_still_route(self):
        self.assertEqual(route_adapter({"title": "Merge Sort", "topic_type": "algorithm_walkthrough"}).slug,
                         "merge_sort")
        self.assertEqual(route_adapter({"title": "Implementing Kruskal's Algorithm",
                                        "topic_type": "coding_implementation"}).slug, "kruskal")

    def test_intro_and_meta_topics_do_not_route(self):
        # ABOUT the concept, not a solvable instance -> defer (None), never a confidently-wrong worked example
        self.assertIsNone(route_adapter({"title": "Introduction to Merge Sort", "topic_type": "algorithm_walkthrough"}))
        self.assertIsNone(route_adapter({"title": "Applications of Dijkstra's Algorithm"}))
        self.assertIsNone(route_adapter({"title": "History of Quicksort"}))
        self.assertIsNone(route_adapter({"title": "When to Use Kruskal vs Prim"}))

    def test_study_path_introduction_never_routes(self):
        self.assertIsNone(route_adapter({"title": "Binary Search", "topic_type": "study_path_introduction"}))

    def test_unrelated_topic_defers(self):
        self.assertIsNone(route_adapter({"title": "The French Revolution", "topic_type": "coding_implementation"}))


class DemandTracker(unittest.TestCase):
    def setUp(self):
        self._fd, self._path = tempfile.mkstemp(suffix=".jsonl")
        os.close(self._fd)
        os.remove(self._path)                       # start empty
        os.environ["AZALEA_ADAPTER_DEMAND_LOG"] = self._path

    def tearDown(self):
        os.environ.pop("AZALEA_ADAPTER_DEMAND_LOG", None)
        if os.path.exists(self._path):
            os.remove(self._path)

    def _summary(self):
        from app.services.examples.adapter_demand import summarize
        return summarize()

    def test_records_computational_topic_without_adapter(self):
        from app.services.examples.adapter_demand import record_unadapted_topic
        rec = record_unadapted_topic({"title": "Implementing Radix Sort", "topic_type": "coding_implementation"})
        self.assertTrue(rec)
        s = self._summary()
        self.assertEqual(len(s), 1)
        self.assertEqual(s[0]["count"], 1)
        self.assertIn("radix", s[0]["signature"])

    def test_does_not_record_when_an_adapter_exists(self):
        from app.services.examples.adapter_demand import record_unadapted_topic
        self.assertFalse(record_unadapted_topic(
            {"title": "Implementing Merge Sort", "topic_type": "coding_implementation"}))
        self.assertEqual(self._summary(), [])

    def test_does_not_record_non_computational_topic(self):
        from app.services.examples.adapter_demand import record_unadapted_topic
        self.assertFalse(record_unadapted_topic(
            {"title": "The History of Computing", "topic_type": "study_path_introduction"}))

    def test_repeated_requests_aggregate_and_rank(self):
        from app.services.examples.adapter_demand import record_unadapted_topic
        for title in ("Implementing Radix Sort", "Radix Sort in Python", "Radix Sort"):
            record_unadapted_topic({"title": title, "topic_type": "coding_implementation"})
        record_unadapted_topic({"title": "Bellman-Ford Algorithm", "topic_type": "algorithm_walkthrough"})
        s = self._summary()
        self.assertEqual(s[0]["count"], 3)               # radix (3) ranks above bellman-ford (1)
        self.assertIn("radix", s[0]["signature"])
        self.assertGreaterEqual(len(s[0]["distinct_titles"]), 2)


if __name__ == "__main__":
    unittest.main()
