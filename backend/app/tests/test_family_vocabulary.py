"""Family vocabulary lives in the INTRO, once (user decision, 2026-07-20 review): live bst path had
In-Order defining Binary Tree/Node, Pre-Order defining Root/Left Child/Right Child, Post-Order defining
Left Subtree/Right Subtree — near-identical anatomy re-taught per topic while the intro defined nothing.
Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_family_vocabulary
"""
import os
import types
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.lean_lesson_generator import _apply_family_vocabulary


def _topic(title, tt, goal="want to learn about bst traversal algorithms"):
    sp = types.SimpleNamespace(goal=goal, topics=[])
    return types.SimpleNamespace(title=title, course_type=tt, topic_type=tt,
                                 order_index=1, study_path=sp, decomposition_metadata={})


class IntroSharedTermsInjection(unittest.TestCase):
    def test_intro_without_terms_card_gets_shared_vocabulary_before_roadmap(self):
        cards = [{"card_type": "purpose_context", "title": "What is BST Traversal?", "points": ["x"]},
                 {"card_type": "roadmap", "title": "Roadmap", "points": ["y"]}]
        _apply_family_vocabulary(cards, _topic("Introduction", "study_path_introduction"))
        kinds = [c["card_type"] for c in cards]
        self.assertEqual(kinds, ["purpose_context", "definition", "roadmap"])
        joined = " ".join(cards[1]["points"])
        for term in ("Node", "Root", "Subtree", "Leaf", "Visit"):
            self.assertIn(term, joined)

    def test_intro_with_model_terms_card_untouched(self):
        cards = [{"card_type": "definition", "title": "Key Terms", "points": ["Node", "  - an element"]},
                 {"card_type": "roadmap", "title": "Roadmap", "points": ["y"]}]
        _apply_family_vocabulary(cards, _topic("Introduction", "study_path_introduction"))
        self.assertEqual(len(cards), 2)                       # no duplicate injection

    def test_non_family_path_untouched(self):
        cards = [{"card_type": "purpose_context", "points": ["x"]},
                 {"card_type": "roadmap", "points": ["y"]}]
        _apply_family_vocabulary(cards, _topic("Introduction", "study_path_introduction",
                                               goal="learn straight line depreciation"))
        self.assertEqual(len(cards), 2)


class MemberTopicGenericTermsDropped(unittest.TestCase):
    def _cards(self):
        return [{"card_type": "definition", "title": "Key Components", "points": [
            "Binary Tree: a tree where each node has at most two children.",
            "Node: an individual element of the tree.",
            "Queue: a FIFO structure holding nodes to process level by level.",
        ]}]

    def test_shared_anatomy_dropped_topic_specific_kept(self):
        cards = self._cards()
        _apply_family_vocabulary(cards, _topic("Level-Order Traversal", "algorithm_walkthrough"))
        joined = " ".join(cards[0]["points"])
        self.assertNotIn("Binary Tree:", joined)
        self.assertNotIn("Node: an individual", joined)
        self.assertIn("Queue:", joined)                       # topic-specific term survives

    def test_terms_card_emptied_of_all_terms_is_removed(self):
        cards = [{"card_type": "definition", "title": "Key Terms", "points": [
            "Root Node", "  - the topmost node.", "Left Child", "  - the left link."]},
            {"card_type": "quick_practice", "points": ["p"]}]
        _apply_family_vocabulary(cards, _topic("Pre-Order Traversal", "algorithm_walkthrough"))
        self.assertEqual([c["card_type"] for c in cards], ["quick_practice"])


if __name__ == "__main__":
    unittest.main()
