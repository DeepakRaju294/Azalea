"""Prune phantom roadmap previews (_prune_phantom_roadmap_previews).

The intro roadmap must not preview a topic the path does not contain (the model over-promised an "Applications"
topic that was never generated). Complement to _enforce_roadmap_coverage. Offline.
Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_roadmap_phantom_prune
"""
import os
import types
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.lean_lesson_generator import _prune_phantom_roadmap_previews


def _intro_topic_with_one_body_topic():
    intro = types.SimpleNamespace(id="t1", title="Introduction to Completing the Square",
                                  topic_type="study_path_introduction", course_type="study_path_introduction")
    steps = types.SimpleNamespace(id="t2", title="Steps to Complete the Square",
                                  topic_type="process_walkthrough", course_type="process_walkthrough")
    sp = types.SimpleNamespace(topics=[intro, steps])
    intro.study_path = sp
    return intro


def _roadmap(points):
    return {"blueprint_key": "roadmap", "card_type": "roadmap", "points": list(points)}


class PhantomPrune(unittest.TestCase):
    def test_inline_phantom_preview_pruned_real_kept(self):
        card = _roadmap([
            "This path covers the following topics:",
            "  - Steps to Complete the Square: Detailed breakdown of the procedure.",
            "  - Applications of Completing the Square: Relevance in graphing and theory.",
        ])
        _prune_phantom_roadmap_previews([card], _intro_topic_with_one_body_topic())
        joined = "\n".join(card["points"])
        self.assertIn("Steps to Complete the Square", joined)          # real sibling kept
        self.assertNotIn("Applications", joined)                        # phantom pruned
        self.assertIn("This path covers", joined)                       # prose lead-in kept

    def test_bare_header_phantom_drops_its_subpoints(self):
        card = _roadmap([
            "Steps to Complete the Square:",
            "  - The step-by-step procedure.",
            "Applications of Completing the Square:",
            "  - Graphing parabolas and solving.",
        ])
        _prune_phantom_roadmap_previews([card], _intro_topic_with_one_body_topic())
        self.assertEqual(card["points"], ["Steps to Complete the Square:", "  - The step-by-step procedure."])

    def test_card_without_any_real_preview_is_untouched(self):
        # a concept list (no sibling previewed) must not be pruned — we only prune genuine topic roadmaps
        card = _roadmap(["Key ideas:", "  - vertex form", "  - the discriminant"])
        before = list(card["points"])
        _prune_phantom_roadmap_previews([card], _intro_topic_with_one_body_topic())
        self.assertEqual(card["points"], before)

    def test_no_siblings_is_noop(self):
        lone = types.SimpleNamespace(id="t1", title="Intro", topic_type="study_path_introduction",
                                     course_type="study_path_introduction")
        lone.study_path = types.SimpleNamespace(topics=[lone])
        card = _roadmap(["Something of Great Importance: text."])
        _prune_phantom_roadmap_previews([card], lone)
        self.assertEqual(len(card["points"]), 1)


if __name__ == "__main__":
    unittest.main()
