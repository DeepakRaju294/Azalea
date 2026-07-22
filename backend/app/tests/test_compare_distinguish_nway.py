"""compare_distinguish N-way guidance: 46th path review. A 4-member family survey's 'Comparing Traversal
Techniques' topic shipped its actual comparison split into adjacent two-at-a-time pairs ('In-Order vs
Pre-Order', then 'Post-Order vs Level-Order') — In-Order was never compared against Post-Order or
Level-Order at all, and the pairing tracked list order, not any real relationship. The compare_distinguish
blueprint's own guidance (course_blueprints.py) previously said "two ideas" / "idea A ... idea B", biasing
toward pairwise comparison by construction. Offline: build_lean_user_prompt is pure string assembly.
Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_compare_distinguish_nway
"""
import os
import types
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.prompts.lean_lesson_prompt import build_lean_user_prompt


def _fake_comparison_topic():
    sp = types.SimpleNamespace(goal="want to learn about bst traversal", domain="coding", topics=[])
    return types.SimpleNamespace(
        title="Comparing Traversal Techniques", description="", topic_type="compare_distinguish",
        course_type="compare_distinguish", study_path=sp, id="t1", purpose="", learner_outcome=None,
        in_scope=["comparison of in-order, pre-order, post-order, and level-order"], out_of_scope=None,
        modifiers=None, decomposition_metadata=None, assumed_prerequisites=None,
    )


class NWayComparisonGuidance(unittest.TestCase):
    def test_avoid_list_forbids_adjacent_pairwise_chain(self):
        prompt = build_lean_user_prompt(_fake_comparison_topic(), [])
        self.assertIn("never a chain of adjacent two-at-a-time pairs", prompt)
        self.assertIn("never sees A compared against C", prompt)

    def test_example_type_guidance_covers_all_ideas_not_just_two(self):
        prompt = build_lean_user_prompt(_fake_comparison_topic(), [])
        idx = prompt.find("example_type_guidance:")
        self.assertNotEqual(idx, -1)
        section = prompt[idx:idx + 600]
        self.assertIn("cover them ALL together in one holistic view", section)
        self.assertNotIn("Show two similar ideas", section)

    def test_card_specific_purpose_also_covers_all_ideas(self):
        prompt = build_lean_user_prompt(_fake_comparison_topic(), [])
        self.assertIn("every comparison card must address ALL of them together", prompt)


if __name__ == "__main__":
    unittest.main()
