"""A coding_implementation topic that follows a same-subject walkthrough is an implementation follow-up:
the division tags it with the implementation_follow_up modifier (keeping course_type intact), and generation
drops the redundant background card."""
import unittest

from app.core.course_blueprints import IMPLEMENTATION_FOLLOW_UP, get_topic_blueprint
from app.services.topic_generator import _mark_coding_follow_ups


def _is_follow_up(topic: dict) -> bool:
    return IMPLEMENTATION_FOLLOW_UP in (topic.get("modifiers") or [])


class MarkCodingFollowUps(unittest.TestCase):
    def _run(self, topics):
        _mark_coding_follow_ups(topics)
        return topics

    def test_coding_after_same_subject_walkthrough_is_tagged(self):
        topics = self._run([
            {"title": "Kruskal's Algorithm Walkthrough", "topic_type": "algorithm_walkthrough"},
            {"title": "Implementing Kruskal's Algorithm", "topic_type": "coding_implementation"},
        ])
        self.assertTrue(_is_follow_up(topics[1]))
        self.assertEqual(topics[1]["topic_type"], "coding_implementation")   # type is NOT changed

    def test_coding_after_unrelated_walkthrough_is_not_tagged(self):
        topics = self._run([
            {"title": "Dijkstra Walkthrough", "topic_type": "algorithm_walkthrough"},
            {"title": "Implementing Merge Sort", "topic_type": "coding_implementation"},
        ])
        self.assertFalse(_is_follow_up(topics[1]))          # different subject -> keep its background

    def test_standalone_coding_topic_is_not_tagged(self):
        topics = self._run([
            {"title": "Introduction", "topic_type": "study_path_introduction"},
            {"title": "Implementing a Hash Map", "topic_type": "coding_implementation"},
        ])
        self.assertFalse(_is_follow_up(topics[1]))          # no preceding walkthrough -> keep background

    def test_idempotent(self):
        topics = [
            {"title": "BFS Walkthrough", "topic_type": "algorithm_walkthrough"},
            {"title": "Implementing BFS", "topic_type": "coding_implementation"},
        ]
        _mark_coding_follow_ups(topics)
        _mark_coding_follow_ups(topics)
        self.assertEqual(topics[1]["modifiers"].count(IMPLEMENTATION_FOLLOW_UP), 1)


class FollowUpBlueprintDropsBackground(unittest.TestCase):
    def test_relationship_strips_background_but_stays_coding(self):
        bp = get_topic_blueprint("coding_implementation", relationship_to_parent=IMPLEMENTATION_FOLLOW_UP)
        self.assertNotIn("background", bp["default_card_sequence"])
        self.assertEqual(bp["topic_type"], "coding_implementation")   # still coding for detection


if __name__ == "__main__":
    unittest.main()
