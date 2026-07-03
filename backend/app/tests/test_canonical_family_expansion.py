"""A FAMILY SURVEY goal ("sorting algorithms") must cover its canonical members even though the decomposition
LLM under-generates them and the rest of the pipeline is subtractive. _expand_canonical_family injects the
missing members deterministically (each routes to its verified adapter). Regression for the "only bubble +
merge/quick" sorting paths. Offline."""
import unittest

from app.services.examples.trace_pipeline import route_adapter
from app.services.topic_generator import _expand_canonical_family


def _slugs(topics):
    out = set()
    for t in topics:
        a = route_adapter({"title": t.get("title", ""), "topic_type": t.get("topic_type")})
        if a:
            out.add(a.slug)
    return out


class CanonicalFamilyExpansion(unittest.TestCase):
    def test_sorting_survey_backfills_all_five(self):
        topics = [
            {"title": "Bubble Sort Algorithm Walkthrough", "topic_type": "algorithm_walkthrough"},
            {"title": "Quicksort Algorithm Walkthrough", "topic_type": "algorithm_walkthrough"},
        ]
        out = _expand_canonical_family(topics, "learn about sorting algorithms")
        self.assertEqual(_slugs(out),
                         {"bubble_sort", "selection_sort", "insertion_sort", "merge_sort", "quick_sort"})
        # injected topics are walkthroughs (they get coding follow-ups downstream)
        self.assertTrue(all(t["topic_type"] == "algorithm_walkthrough"
                            for t in out if t not in topics))

    def test_title_variants_are_deduped_by_routing(self):
        # "Quick Sort" and "Quicksort" both route to quick_sort -> quick_sort is NOT injected twice
        topics = [{"title": "Quick Sort Walkthrough", "topic_type": "algorithm_walkthrough"}]
        out = _expand_canonical_family(topics, "sorting algorithms")
        quick = [t for t in out if route_adapter({"title": t["title"],
                 "topic_type": t["topic_type"]}) and route_adapter({"title": t["title"],
                 "topic_type": t["topic_type"]}).slug == "quick_sort"]
        self.assertEqual(len(quick), 1, "quick_sort must not be duplicated across title variants")

    def test_graph_traversal_survey(self):
        topics = [{"title": "Breadth-First Search Walkthrough", "topic_type": "algorithm_walkthrough"}]
        out = _expand_canonical_family(topics, "graph traversal")
        self.assertEqual(_slugs(out), {"bfs", "dfs_iter"})

    def test_non_family_goal_untouched(self):
        topics = [{"title": "Dijkstra's Algorithm Walkthrough", "topic_type": "algorithm_walkthrough"}]
        self.assertEqual(len(_expand_canonical_family(topics, "learn dijkstra")), 1)

    def test_family_goal_but_no_members_present_untouched(self):
        # sorting goal, but the path teaches no sort -> do not inject into an unrelated path
        topics = [{"title": "Hash Tables", "topic_type": "algorithm_walkthrough"}]
        self.assertEqual(len(_expand_canonical_family(topics, "sorting algorithms")), 1)

    def test_single_method_goal_does_not_trigger(self):
        # "implement quicksort" is one method, not a survey -> no marker match, no injection
        topics = [{"title": "Quicksort Walkthrough", "topic_type": "algorithm_walkthrough"}]
        self.assertEqual(len(_expand_canonical_family(topics, "implement quicksort")), 1)


if __name__ == "__main__":
    unittest.main()


class CanonicalFamilyOrdering(unittest.TestCase):
    """A family survey's topics are grouped in canonical order, each walkthrough next to its coding follow-up
    (the expansion + coding backfill otherwise scramble them — insertion's code was stranded at the end)."""
    def test_scrambled_sorts_are_reordered(self):
        from app.services.topic_generator import _order_canonical_family
        scrambled = [
            {"title": "Introduction to Sorting Algorithms", "topic_type": "study_path_introduction"},
            {"title": "Bubble Sort Algorithm Walkthrough", "topic_type": "algorithm_walkthrough"},
            {"title": "Selection Sort Algorithm Walkthrough", "topic_type": "algorithm_walkthrough"},
            {"title": "Insertion Sort Algorithm Walkthrough", "topic_type": "algorithm_walkthrough"},
            {"title": "Implementing Selection Sort in Code", "topic_type": "coding_implementation"},
            {"title": "Implementing Bubble Sort in Code", "topic_type": "coding_implementation"},
            {"title": "Merge Sort Algorithm Walkthrough", "topic_type": "algorithm_walkthrough"},
            {"title": "Implementing Merge Sort", "topic_type": "coding_implementation"},
            {"title": "Quicksort Algorithm Walkthrough", "topic_type": "algorithm_walkthrough"},
            {"title": "Implementing Quicksort", "topic_type": "coding_implementation"},
            {"title": "Implementing Insertion Sort in Code", "topic_type": "coding_implementation"},
        ]
        out = _order_canonical_family(scrambled, "learn about sorting algorithms")
        titles = [t["title"] for t in out]
        self.assertEqual(titles[0], "Introduction to Sorting Algorithms")     # intro stays first
        # canonical order, WT immediately before its code
        self.assertEqual(titles[1:5], ["Bubble Sort Algorithm Walkthrough", "Implementing Bubble Sort in Code",
                                       "Selection Sort Algorithm Walkthrough", "Implementing Selection Sort in Code"])
        self.assertEqual(titles[-1], "Implementing Quicksort")                # insertion code no longer stranded
        self.assertNotIn("Implementing Insertion Sort in Code", titles[-2:])  # it's now next to insertion WT
