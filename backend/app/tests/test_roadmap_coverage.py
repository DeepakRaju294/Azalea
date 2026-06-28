"""Deterministic roadmap coverage (lean intro): every non-intro sibling topic must be previewed,
regardless of what the model emitted (the roadmap rule is prompt-only). Fully offline."""
import types
import unittest

from app.services.lean_lesson_generator import (_enforce_roadmap_coverage, _roadmap_summary_for,
                                                _roadmap_terms)


def _topic(order, title, ctype, purpose=""):
    return types.SimpleNamespace(id=f"t{order}", order_index=order, title=title,
                                 course_type=ctype, topic_type=ctype, purpose=purpose,
                                 learner_outcome="")


def _path_topic(siblings, current):
    sp = types.SimpleNamespace(topics=siblings)
    current.study_path = sp
    return current


def _roadmap(points):
    return {"blueprint_key": "roadmap", "card_type": "roadmap", "title": "Roadmap", "points": points}


class RoadmapTermsTests(unittest.TestCase):
    def test_keeps_concept_and_modifier_drops_glue(self):
        self.assertEqual(_roadmap_terms("Implementing Kruskal's Algorithm"), {"implementing", "kruskal"})
        self.assertEqual(_roadmap_terms("Kruskal's Algorithm Walkthrough"), {"kruskal", "walkthrough"})


class RoadmapCoverageTests(unittest.TestCase):
    def setUp(self):
        self.intro = _topic(1, "Introduction to MST", "study_path_introduction")
        self.t2 = _topic(2, "Kruskal's Algorithm Walkthrough", "algorithm_walkthrough", "This topic shows Kruskal.")
        self.t3 = _topic(3, "Implementing Kruskal's Algorithm", "coding_implementation", "This topic codes Kruskal.")
        self.t4 = _topic(4, "Comparing MST Algorithms", "compare_distinguish", "This topic compares the algorithms.")
        self.sibs = [self.intro, self.t2, self.t3, self.t4]
        _path_topic(self.sibs, self.intro)

    def test_missing_topics_are_injected(self):
        cards = [_roadmap(["Kruskal's Algorithm Walkthrough:", "  - the greedy edge selection"])]
        out = _enforce_roadmap_coverage(cards, self.intro)
        text = " ".join(out[0]["points"]).lower()
        self.assertIn("implementing kruskal", text)        # t3 was dropped -> injected
        self.assertIn("comparing mst", text)               # t4 was dropped -> injected
        self.assertIn("codes kruskal", text.lower())       # summary pulled from purpose

    def test_complete_roadmap_is_unchanged(self):
        cards = [_roadmap([
            "Kruskal's Algorithm Walkthrough:", "  - x",
            "Implementing Kruskal's Algorithm:", "  - y",
            "Comparing MST Algorithms:", "  - z",
        ])]
        before = list(cards[0]["points"])
        out = _enforce_roadmap_coverage(cards, self.intro)
        self.assertEqual(out[0]["points"], before)

    def test_two_same_concept_topics_need_their_own_line(self):
        # 'implementing' + 'kruskal' present but in SEPARATE lines must NOT satisfy the coding topic
        cards = [_roadmap(["Kruskal's Algorithm Walkthrough:", "  - implementing greedy edges"])]
        out = _enforce_roadmap_coverage(cards, self.intro)
        self.assertIn("implementing kruskal", " ".join(out[0]["points"]).lower())

    def test_creates_roadmap_when_none_exists(self):
        out = _enforce_roadmap_coverage([], self.intro)
        roadmaps = [c for c in out if (c.get("blueprint_key") or c.get("card_type")) == "roadmap"]
        self.assertEqual(len(roadmaps), 1)
        text = " ".join(roadmaps[0]["points"]).lower()
        for frag in ("kruskal", "comparing mst"):
            self.assertIn(frag, text)


if __name__ == "__main__":
    unittest.main()
