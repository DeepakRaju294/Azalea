"""Example System — Phase 3: the generic adapter applies a fixture to a lesson
end-to-end (declare → pick → pipeline → swap cards). Flag-gated, no LLM yet.

Run: python -m unittest app.tests.test_example_handoff
"""
from __future__ import annotations

import os
import sys
import types
import unittest

# Sandbox guard: ensure_worked_example_setup imports lean_lesson_generator, which
# needs dotenv/openai at module load.
os.environ.setdefault("OPENAI_API_KEY", "dummy")
for _name in ("dotenv", "openai"):
    if _name not in sys.modules:
        try:
            __import__(_name)
        except ImportError:
            _mod = types.ModuleType(_name)
            if _name == "dotenv":
                _mod.load_dotenv = lambda *a, **k: None
            else:
                _mod.OpenAI = lambda *a, **k: object()
                for _exc in ("APIError", "RateLimitError", "APITimeoutError", "APIConnectionError"):
                    setattr(_mod, _exc, type(_exc, (Exception,), {}))
            sys.modules[_name] = _mod

from app.services.examples.handoff import (
    apply_fixture_to_lesson,
    ensure_worked_example_setup,
    validate_and_order_cards,
)

CASES = [
    ("Binary Search", "algorithm_walkthrough", "indexed_sequence_diagram"),
    ("Implementing Binary Search", "coding_implementation", "code_execution_panel"),
    ("BFS Traversal of a Graph", "algorithm_walkthrough", "node_link_diagram"),
    ("Unique Paths (DP)", "algorithm_walkthrough", "grid_matrix_diagram"),
]


def _lesson():
    return {
        "lesson_cards": [
            {"id": "1", "blueprint_key": "background", "title": "Intro"},
            {"id": "2", "blueprint_key": "worked_example", "title": "old WE", "code_snippet": "x=1"},
            {"id": "3", "blueprint_key": "practice", "title": "Practice"},
        ],
        "visual_models": [],
    }


class TestApplyFixture(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("AZALEA_VISUAL_V2_MODES", None)

    def test_each_case_applies_and_swaps_cards(self):
        os.environ["AZALEA_VISUAL_V2_MODES"] = "all"
        for n, (title, ttype, base_type) in enumerate(CASES):
            with self.subTest(title=title):
                lesson = _lesson()
                topic = {"id": f"t{n}", "title": title, "topic_type": ttype}
                self.assertTrue(apply_fixture_to_lesson(lesson, topic), f"{title} did not apply")

                # Extra models are legitimate: the coding diagram + the edge-case
                # model (for applications with an edge fixture). The PRIMARY model
                # comes first and matches the lens.
                is_coding = ttype == "coding_implementation"
                self.assertGreaterEqual(len(lesson["visual_models"]), 1)
                self.assertEqual(lesson["visual_models"][0]["base_type"], base_type)
                if is_coding:
                    self.assertEqual(lesson["visual_models"][1]["base_type"], "indexed_sequence_diagram")
                    for card in lesson["lesson_cards"]:
                        if card.get("card_type") == "worked_example":
                            self.assertIn("diagram_v2_ref", card)

                worked = [c for c in lesson["lesson_cards"] if c.get("card_type") == "worked_example"]
                self.assertGreaterEqual(len(worked), 4, f"{title}: only {len(worked)} step cards")
                model_id = lesson["visual_models"][0]["id"]
                for card in worked:
                    ref = card["visual_v2_ref"]
                    self.assertEqual(ref["source"], "v2_example_ontology")
                    self.assertEqual(ref["visual_model_id"], model_id)
                    self.assertTrue(0 <= ref["frame_index"] < len(lesson["visual_models"][0]["frames"]))
                # Surrounding cards preserved.
                self.assertEqual(lesson["lesson_cards"][0]["blueprint_key"], "background")
                self.assertEqual(lesson["lesson_cards"][-1]["blueprint_key"], "practice")

    def test_flag_off_is_noop(self):
        os.environ.pop("AZALEA_VISUAL_V2_MODES", None)
        lesson = _lesson()
        topic = {"id": "t", "title": "Binary Search", "topic_type": "algorithm_walkthrough"}
        self.assertFalse(apply_fixture_to_lesson(lesson, topic))
        self.assertEqual(lesson["visual_models"], [])

    def test_unknown_topic_falls_back(self):
        os.environ["AZALEA_VISUAL_V2_MODES"] = "all"
        lesson = _lesson()
        topic = {"id": "t", "title": "The Fall of Rome", "topic_type": "concept_intuition"}
        self.assertFalse(apply_fixture_to_lesson(lesson, topic))
        self.assertEqual(lesson["visual_models"], [])

    def test_intro_topic_gets_no_example(self):
        # An intro (background + roadmap only) must stay untouched, even with a
        # matching title — the blueprint has no worked_example slot.
        os.environ["AZALEA_VISUAL_V2_MODES"] = "all"
        lesson = {
            "lesson_cards": [
                {"id": "1", "blueprint_key": "background", "title": "Why search matters"},
                {"id": "2", "blueprint_key": "roadmap", "title": "What you'll learn"},
            ],
            "visual_models": [],
        }
        topic = {"id": "i", "title": "Introduction to Binary Search", "topic_type": "study_path_introduction"}
        self.assertFalse(apply_fixture_to_lesson(lesson, topic))
        self.assertEqual([c["blueprint_key"] for c in lesson["lesson_cards"]], ["background", "roadmap"])
        self.assertEqual(lesson["visual_models"], [])

    def test_stale_apply_is_removed_from_intro(self):
        # An intro that wrongly received an example before the blueprint gate
        # existed is cleaned up on the next apply attempt.
        os.environ["AZALEA_VISUAL_V2_MODES"] = "all"
        lesson = {
            "lesson_cards": [
                {"id": "1", "blueprint_key": "background"},
                {"id": "2", "blueprint_key": "roadmap"},
                {"id": "v2-ex-v2_binary_search_i-1", "blueprint_key": "worked_example",
                 "card_type": "worked_example",
                 "visual_v2_ref": {"visual_model_id": "v2_binary_search_i", "frame_index": 0,
                                   "source": "v2_example_ontology"}},
                {"id": "v2-cw-binary_search_code_loop_found_late_01-1", "blueprint_key": "code_walkthrough"},
            ],
            "visual_models": [{"id": "v2_binary_search_i", "base_type": "indexed_sequence_diagram", "frames": []}],
            "metadata": {"visual_v2_example_ontology": {"version": 2, "model_id": "v2_binary_search_i"}},
        }
        topic = {"id": "i", "title": "Introduction to Binary Search", "topic_type": "study_path_introduction"}
        self.assertFalse(apply_fixture_to_lesson(lesson, topic))
        self.assertEqual([c["blueprint_key"] for c in lesson["lesson_cards"]], ["background", "roadmap"])
        self.assertEqual(lesson["visual_models"], [])
        self.assertNotIn("visual_v2_example_ontology", lesson["metadata"])

    def test_setup_guaranteed_for_legacy_concept_lesson(self):
        # A topic the fixtures DON'T cover (legacy path) still gets a setup card.
        lesson = {
            "lesson_cards": [
                {"id": "1", "blueprint_key": "background", "title": "Merge sort"},
                {"id": "2", "blueprint_key": "worked_example", "title": "Step 1",
                 "points": ["Split the array in half."], "visual_plan": {"type": "indexed_sequence_diagram"}},
                {"id": "3", "blueprint_key": "worked_example", "title": "Step 2",
                 "points": ["Merge the halves."]},
                {"id": "4", "blueprint_key": "practice", "title": "Practice"},
            ],
        }
        ensure_worked_example_setup(lesson, {"id": "t", "title": "Merge Sort", "topic_type": "algorithm_walkthrough"})
        worked = [c for c in lesson["lesson_cards"] if str(c.get("blueprint_key")) == "worked_example"]
        first_meta = worked[0].get("metadata") or {}
        self.assertTrue(first_meta.get("worked_example_setup"), "no setup card inserted")

    def test_setup_not_duplicated_on_v2_concept_lesson(self):
        os.environ["AZALEA_VISUAL_V2_MODES"] = "all"
        lesson = _lesson()
        topic = {"id": "t", "title": "Binary Search", "topic_type": "algorithm_walkthrough"}
        apply_fixture_to_lesson(lesson, topic)
        ensure_worked_example_setup(lesson, topic)
        setups = [
            c for c in lesson["lesson_cards"]
            if (c.get("metadata") or {}).get("worked_example_setup") or c.get("title") == "Worked Example Setup"
        ]
        self.assertEqual(len(setups), 1, [c.get("title") for c in setups])

    def test_coding_gets_setup_card_then_action_steps(self):
        # The setup card states the problem; Step 1 is an ACTUAL solving action.
        os.environ["AZALEA_VISUAL_V2_MODES"] = "all"
        lesson = _lesson()
        topic = {"id": "t", "title": "Implementing Binary Search", "topic_type": "coding_implementation"}
        apply_fixture_to_lesson(lesson, topic)
        worked = [c for c in lesson["lesson_cards"] if c.get("card_type") == "worked_example"]
        self.assertEqual(worked[0]["title"], "Worked Example Setup")
        self.assertIn("The problem:", worked[0]["points"][0])
        self.assertTrue((worked[0].get("metadata") or {}).get("worked_example_setup"))
        # Step 1 acts (binds inputs / runs line 2), not restates the problem.
        self.assertNotIn("The problem:", worked[1]["points"][0])
        # No duplicate from the enrich-time guarantee.
        ensure_worked_example_setup(lesson, topic)
        setups = [c for c in lesson["lesson_cards"] if (c.get("metadata") or {}).get("worked_example_setup")]
        self.assertEqual(len(setups), 1)

    def test_edge_case_and_practice_roles(self):
        # §5.2/§7.2: a verified edge-case card replaces the LLM ones; an isomorphic
        # practice question with a deterministic answer leads the practice run.
        os.environ["AZALEA_VISUAL_V2_MODES"] = "all"
        lesson = {
            "lesson_cards": [
                {"id": "1", "blueprint_key": "background"},
                {"id": "2", "blueprint_key": "worked_example"},
                {"id": "3", "blueprint_key": "edge_case", "title": "LLM edge 1"},
                {"id": "4", "blueprint_key": "edge_case", "title": "LLM edge 2"},
                {"id": "5", "blueprint_key": "practice", "card_type": "quick_practice"},
            ],
            "visual_models": [],
        }
        topic = {"id": "t", "title": "Binary Search", "topic_type": "algorithm_walkthrough"}
        apply_fixture_to_lesson(lesson, topic)
        apply_fixture_to_lesson(lesson, topic)  # idempotent on re-apply

        edges = [c for c in lesson["lesson_cards"] if c.get("blueprint_key") == "edge_case"]
        self.assertEqual(len(edges), 1)
        self.assertIn("returns -1", " ".join(edges[0]["points"]))
        self.assertIn("_edge", edges[0]["visual_v2_ref"]["visual_model_id"])

        questions = lesson.get("practice_questions") or []
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]["correct_answer"], "9")  # 72 in the variant array
        ours = [c for c in lesson["lesson_cards"] if str(c.get("id", "")).startswith("v2-practice-")]
        self.assertEqual(len(ours), 1)
        self.assertEqual(ours[0]["practice_question_index"], 0)
        # Blueprint order: ... worked_example run, edge_case, then practice.
        keys = [c["blueprint_key"] for c in lesson["lesson_cards"]]
        self.assertLess(keys.index("edge_case"), keys.index("practice"))

    def test_card_validator_orders_and_filters(self):
        # CardValidator (spec §5.3 #5): blueprint keys only, in blueprint order;
        # relative order within a key is preserved; never empties a lesson.
        lesson = {
            "lesson_cards": [
                {"id": "p", "blueprint_key": "practice"},
                {"id": "w1", "blueprint_key": "worked_example", "n": 1},
                {"id": "e", "blueprint_key": "edge_case"},
                {"id": "b", "blueprint_key": "background"},
                {"id": "w2", "blueprint_key": "worked_example", "n": 2},
                {"id": "x", "blueprint_key": "roadmap"},  # not allowed in a walkthrough
            ],
        }
        validate_and_order_cards(lesson, {"topic_type": "algorithm_walkthrough"})
        keys = [c["blueprint_key"] for c in lesson["lesson_cards"]]
        self.assertEqual(keys, ["background", "worked_example", "worked_example", "edge_case", "practice"])
        worked = [c for c in lesson["lesson_cards"] if c["blueprint_key"] == "worked_example"]
        self.assertEqual([c["n"] for c in worked], [1, 2])  # stable within a key

    def test_card_validator_never_empties(self):
        lesson = {"lesson_cards": [{"id": "x", "blueprint_key": "nonsense"}]}
        validate_and_order_cards(lesson, {"topic_type": "concept_intuition"})
        self.assertEqual(len(lesson["lesson_cards"]), 1)

    def test_metadata_records_fixture(self):
        os.environ["AZALEA_VISUAL_V2_MODES"] = "all"
        lesson = _lesson()
        topic = {"id": "t", "title": "Unique Paths (DP)", "topic_type": "algorithm_walkthrough"}
        apply_fixture_to_lesson(lesson, topic)
        meta = lesson["metadata"]["visual_v2_example_ontology"]
        self.assertEqual(meta["application"], "unique_paths")
        self.assertEqual(meta["fixture_id"], "unique_paths_concept_3x4_01")


if __name__ == "__main__":
    unittest.main()
