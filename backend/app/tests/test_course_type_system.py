from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.core.course_blueprints import COURSE_BLUEPRINTS
from app.core.course_stage_rules import STAGE_RULES
from app.prompts.lesson_prompt import SYSTEM_PROMPT, build_lesson_user_prompt, format_card_sequence
from app.schemas.lesson_cards import FlexibleLessonJson
from app.services.course_type_classifier import classify_topic_course_type
from app.services.lesson_generator import (
    build_lesson_from_topic_and_chunks,
    ensure_topic_generation_metadata,
    generate_and_finalize_lesson,
    get_lesson_blueprint_card_sequence,
    sync_validation_report,
)
from app.services.review_injection_service import maybe_inject_review_card
from app.services.scope_validator import validate_scope_adherence
from app.services.topic_quality_validator import (
    calculate_blueprint_coverage,
    validate_generated_topic,
)
from app.services.topic_scope_service import build_topic_scope_contract


class CourseTypeSystemTests(unittest.TestCase):
    def test_every_blueprint_stage_has_stage_rules(self) -> None:
        missing: dict[str, list[str]] = {}
        extra: dict[str, list[str]] = {}

        for course_type, blueprint in COURSE_BLUEPRINTS.items():
            expected_keys = set(blueprint.get("default_card_sequence") or [])
            expected_keys.update(blueprint.get("continuation_card_sequence") or [])
            stage_keys = set(STAGE_RULES.get(course_type, {}).keys())

            missing_keys = sorted(expected_keys - stage_keys)
            extra_keys = sorted(stage_keys - expected_keys)
            if missing_keys:
                missing[course_type] = missing_keys
            if extra_keys:
                extra[course_type] = extra_keys

        self.assertEqual(missing, {})
        self.assertEqual(extra, {})

    def test_card_sequence_includes_stage_guidance_and_styled_support(self) -> None:
        coding_rules = STAGE_RULES["coding_implementation"]
        rendered = format_card_sequence(
            ["variables_state_needed", "full_code"],
            coding_rules,
        )

        self.assertIn('blueprint_key "variables_state_needed"', rendered)
        self.assertIn("Content:", rendered)
        self.assertIn("Styled support: variable table", rendered)
        self.assertIn("Styled support: full syntax-highlighted code block", rendered)

    def test_blueprint_key_counts_as_coverage_even_with_custom_title(self) -> None:
        cards = [
            {
                "blueprint_key": "state_components",
                "title": "A custom learner-facing title",
                "card_type": "definition",
                "points": ["Queue, visited set, and result order are algorithm state."],
            }
        ]

        coverage = calculate_blueprint_coverage(
            cards=cards,
            expected_sequence=["context_first_impression", "state_components"],
        )

        self.assertEqual(coverage["matched_count"], 1)
        self.assertEqual(coverage["missing_keys"], ["context_first_impression"])

    def test_stage_rule_validator_flags_missing_expected_microcheck(self) -> None:
        lesson = {
            "course_type": "algorithm_walkthrough",
            "lesson_cards": [
                {
                    "id": "card-1",
                    "blueprint_key": "algorithm_rule_main_idea",
                    "card_type": "core_idea",
                    "title": "Algorithm Rule",
                    "body": [],
                    "bullets": [],
                    "points": [
                        "The algorithm processes the next frontier item and preserves the invariant."
                    ],
                    "main_concept": "algorithm rule",
                    "new_concepts": [],
                    "review_concepts": [],
                    "prerequisite_concepts": [],
                    "related_formulas": [],
                    "related_symbols": [],
                    "common_misconceptions": [],
                    "concept_support": [],
                    "interactive_links": [],
                    "styled_elements": [],
                    "visual_plan": {},
                    "annotations": [],
                    "example": "",
                    "micro_check": {"type": "", "prompt": "", "answer": ""},
                    "deeper_explanation": "",
                    "what_to_notice": "The rule controls every step.",
                    "next_transition": "Now track state.",
                    "quality_score": 85,
                    "estimated_seconds": 35,
                    "transition_text": "Now track state.",
                    "next_card_label": "Continue",
                    "practice_question_index": -1,
                    "visual_index": -1,
                }
            ],
            "practice_questions": [
                {
                    "question_type": "short_answer",
                    "concept_tested": "algorithm rule",
                    "why_this_matters": "Checks whether the rule is usable.",
                }
            ],
        }

        report = validate_generated_topic(lesson, "algorithm_walkthrough")
        issue_codes = {issue["code"] for issue in report["issues"]}

        self.assertIn("stage_microcheck_missing", issue_codes)

    def test_review_injection_adds_lightweight_prerequisite_card(self) -> None:
        lesson = {
            "course_type": "algorithm_walkthrough",
            "lesson_cards": [
                {
                    "id": "card-1",
                    "blueprint_key": "context_first_impression",
                    "card_type": "intro",
                    "title": "Context",
                    "points": ["Prim's algorithm grows a minimum spanning tree."],
                    "review_concepts": [],
                },
                {
                    "id": "card-2",
                    "blueprint_key": "algorithm_rule_main_idea",
                    "card_type": "core_idea",
                    "title": "Rule",
                    "points": ["Choose the lightest crossing edge."],
                    "review_concepts": [],
                },
            ],
        }
        topic = SimpleNamespace(
            title="Prim's algorithm",
            prerequisite_topics="Graphs, Priority queues",
            course_type="algorithm_walkthrough",
        )

        report = maybe_inject_review_card(lesson, topic)

        self.assertTrue(report["injected"])
        self.assertEqual(lesson["lesson_cards"][1]["blueprint_key"], "review_injection")
        self.assertEqual(
            lesson["lesson_cards"][1]["styled_elements"][0]["type"],
            "checklist",
        )
        self.assertEqual(lesson["lesson_cards"][1]["micro_check"]["type"], "reveal")

    def test_review_injection_skips_review_refresh_courses(self) -> None:
        lesson = {
            "course_type": "review_refresh",
            "lesson_cards": [{"id": "card-1", "title": "Recall"}],
        }
        topic = SimpleNamespace(
            title="Derivatives",
            prerequisite_topics="Limits",
            course_type="review_refresh",
        )

        report = maybe_inject_review_card(lesson, topic)

        self.assertFalse(report["injected"])
        self.assertEqual(len(lesson["lesson_cards"]), 1)

    def test_bst_traversal_classifies_as_algorithm_walkthrough(self) -> None:
        result = classify_topic_course_type(
            user_goal="I want to learn BST traversals",
            topic_title="BST Traversals",
            topic_purpose="Trace inorder, preorder, and postorder visit order.",
        )

        self.assertEqual(result["primary_course_type"], "algorithm_walkthrough")

    def test_bst_traversal_scope_contract_blocks_sibling_operations(self) -> None:
        topic = SimpleNamespace(
            title="BST Traversals",
            purpose="Trace traversal order through a binary search tree.",
            course_type="algorithm_walkthrough",
            secondary_course_types=[],
            prerequisite_topics="",
        )

        contract = build_topic_scope_contract(topic)

        self.assertIn("BST search", contract["out_of_scope_content"])
        self.assertIn("how BST deletion works", contract["must_not_teach"])
        self.assertEqual(
            contract["allowed_card_sequence"],
            [
                "context_first_impression",
                "algorithm_rule_main_idea",
                "state_components",
                "how_it_works",
                "comprehensive_walkthrough_example",
                "final_result_output",
                "practice",
            ],
        )

    def test_scope_validator_flags_bst_traversal_drift(self) -> None:
        contract = {
            "current_topic": "BST Traversals",
            "allowed_card_sequence": ["context_first_impression", "practice"],
            "out_of_scope_content": ["BST search", "BST insertion", "BST deletion"],
            "must_not_teach": ["how BST insertion works", "BST deletion cases"],
        }
        lesson = {
            "lesson_cards": [
                {
                    "blueprint_key": "context_first_impression",
                    "title": "Traversal Context",
                    "main_concept": "BST traversal",
                    "points": ["Traversal visits nodes in a chosen order."],
                },
                {
                    "blueprint_key": "how_it_works",
                    "title": "BST insertion",
                    "main_concept": "how BST insertion works",
                    "points": ["Insert by comparing values from root downward."],
                },
            ],
            "practice_questions": [
                {
                    "question_text": "Which BST deletion cases apply here?",
                    "concept_tested": "BST deletion cases",
                }
            ],
        }

        report = validate_scope_adherence(lesson, contract)

        self.assertFalse(report["passed"])
        self.assertTrue(report["requires_regeneration"])
        self.assertGreaterEqual(len(report["issues"]), 2)

    def test_scope_validator_flags_order_prerequisite_and_visual_drift(self) -> None:
        contract = {
            "current_topic": "BST Traversals",
            "course_type": "algorithm_walkthrough",
            "allowed_card_sequence": [
                "context_first_impression",
                "algorithm_rule_main_idea",
                "practice",
            ],
            "assumed_prerequisites": ["node"],
            "brief_refresh_prerequisites": [
                "BST property: left values are smaller, right values are larger."
            ],
            "popup_only_prerequisites": ["recursion"],
            "prerequisite_mini_path_candidates": ["call stack"],
            "out_of_scope_content": ["BST insertion"],
            "must_not_teach": ["how BST insertion works"],
        }
        lesson = {
            "lesson_cards": [
                {
                    "blueprint_key": "algorithm_rule_main_idea",
                    "title": "Traversal Rule",
                    "main_concept": "Traversal rule",
                    "points": ["Traversal chooses a node order before outputting values."],
                    "interactive_links": [],
                    "visual_plan": {},
                },
                {
                    "blueprint_key": "context_first_impression",
                    "title": "Node",
                    "main_concept": "node",
                    "points": ["A node stores values and links to children."],
                    "interactive_links": [],
                    "visual_plan": {},
                },
                {
                    "blueprint_key": "practice",
                    "title": "Recursion Check",
                    "main_concept": "recursion",
                    "points": ["Recursion repeats the same traversal on smaller subtrees."],
                    "interactive_links": [],
                    "visual_plan": {
                        "type": "node_link_diagram",
                        "title": "BST insertion path",
                        "nodes": [{"id": "1", "label": "insert 5"}],
                    },
                },
            ],
            "practice_questions": [
                {
                    "question_type": "essay",
                    "question_text": "Explain the traversal output order.",
                    "concept_tested": "traversal order",
                }
            ],
            "visual_plan": [],
        }

        report = validate_scope_adherence(lesson, contract)
        issue_text = "\n".join(report["issues"])

        self.assertFalse(report["passed"])
        self.assertIn("appears out of order", issue_text)
        self.assertIn("assumed prerequisite", issue_text)
        self.assertIn("popup-only prerequisite", issue_text)
        self.assertIn("visual/styled content", issue_text)
        self.assertIn("Practice question types", issue_text)

    def test_inorder_traversal_scope_stays_on_traversal(self) -> None:
        topic = SimpleNamespace(
            title="Inorder Traversal",
            purpose="Trace left-current-right traversal on a BST.",
            course_type="algorithm_walkthrough",
            secondary_course_types=[],
            prerequisite_topics="",
        )

        contract = build_topic_scope_contract(topic)

        self.assertEqual(contract["course_type"], "algorithm_walkthrough")
        self.assertIn("traversal order", contract["in_scope_content"])
        self.assertIn("BST insertion", contract["out_of_scope_content"])
        self.assertIn("how BST deletion works", contract["must_not_teach"])

    def test_implement_inorder_traversal_gets_coding_continuation(self) -> None:
        result = classify_topic_course_type(
            user_goal="Teach me how to implement inorder traversal in C++",
            topic_title="Implement inorder traversal in C++",
            topic_purpose="Write recursive traversal code.",
        )
        topic = SimpleNamespace(
            title="Implement inorder traversal in C++",
            purpose="Write recursive traversal code.",
            course_type=result["primary_course_type"],
            secondary_course_types=result["secondary_course_types"],
            prerequisite_topics="",
        )

        contract = build_topic_scope_contract(topic)

        self.assertEqual(contract["course_type"], "algorithm_walkthrough")
        self.assertIn("coding_implementation", contract["secondary_course_types"])
        self.assertIn("code_build_up", contract["allowed_card_sequence"])
        self.assertIn("full_code", contract["allowed_card_sequence"])
        self.assertIn("how BST insertion works", contract["must_not_teach"])

    def test_bst_deletion_classifies_as_data_structure_operation(self) -> None:
        result = classify_topic_course_type(
            user_goal="Teach me BST deletion",
            topic_title="BST deletion",
            topic_purpose="Understand the delete operation cases.",
        )

        self.assertEqual(result["primary_course_type"], "data_structure_operation")

    def test_bst_deletion_scope_allows_deletion_cases_only(self) -> None:
        topic = SimpleNamespace(
            title="BST deletion",
            purpose="Delete nodes while preserving the BST invariant.",
            course_type="data_structure_operation",
            secondary_course_types=[],
            prerequisite_topics="",
        )

        contract = build_topic_scope_contract(topic)

        self.assertEqual(contract["course_type"], "data_structure_operation")
        self.assertIn("two-child deletion case", contract["in_scope_content"])
        self.assertIn("inorder successor or predecessor replacement", contract["in_scope_content"])
        self.assertIn("BST insertion", contract["out_of_scope_content"])
        self.assertIn("how inorder traversal works", contract["must_not_teach"])
        self.assertNotIn("BST deletion cases", contract["must_not_teach"])

    def test_scope_validator_accepts_in_scope_bst_deletion_lesson(self) -> None:
        topic = SimpleNamespace(
            title="BST deletion",
            purpose="Delete nodes while preserving the BST invariant.",
            course_type="data_structure_operation",
            secondary_course_types=[],
            prerequisite_topics="",
        )
        contract = build_topic_scope_contract(topic)
        lesson = {
            "lesson_cards": [
                {
                    "blueprint_key": "structure_refresh_first_impression",
                    "title": "BST Deletion Context",
                    "main_concept": "BST deletion setup",
                    "points": ["Deletion removes one node while preserving the ordering invariant."],
                    "visual_index": 0,
                },
                {
                    "blueprint_key": "operation_goal",
                    "title": "Deletion Goal",
                    "main_concept": "BST deletion goal",
                    "points": ["Choose the deletion case before changing child links."],
                },
                {
                    "blueprint_key": "cases_scenarios",
                    "title": "Deletion Cases",
                    "main_concept": "two-child deletion case",
                    "points": ["Two-child deletion replaces the value using a successor."],
                    "visual_index": 0,
                },
                {
                    "blueprint_key": "how_operation_works",
                    "title": "Relink The Tree",
                    "main_concept": "pointer or child-link update",
                    "points": ["After replacement, remove the successor from its old position."],
                    "visual_index": 0,
                },
                {
                    "blueprint_key": "comprehensive_operation_example",
                    "title": "Deletion Walkthrough",
                    "main_concept": "BST deletion walkthrough",
                    "points": ["Deleting a two-child node preserves left-smaller and right-larger order."],
                    "visual_index": 0,
                },
                {
                    "blueprint_key": "validity_invariant_check",
                    "title": "Invariant Check",
                    "main_concept": "BST invariant check after deletion",
                    "points": ["Every changed link still separates smaller and larger subtrees."],
                    "visual_index": 0,
                },
                {
                    "blueprint_key": "benefits_limitations_complexity",
                    "title": "Deletion Complexity",
                    "main_concept": "deletion complexity",
                    "points": ["Runtime depends on tree height, not total values directly."],
                },
                {
                    "blueprint_key": "practice",
                    "title": "Deletion Practice",
                    "main_concept": "perform BST deletion",
                    "points": ["Identify the case before choosing the structural change."],
                    "visual_index": 0,
                },
            ],
            "practice_questions": [
                {
                    "question_type": "visual_labeling",
                    "question_text": "Which node replaces the deleted two-child node?",
                    "concept_tested": "two-child deletion case",
                }
            ],
            "visual_plan": [
                {
                    "type": "node_link_diagram",
                    "title": "BST deletion example",
                    "nodes": [{"id": "5", "label": "5", "x": 50, "y": 20}],
                    "edges": [],
                }
            ],
        }
        for card in lesson["lesson_cards"]:
            card["micro_check"] = {
                "prompt": "What does this deletion card require you to decide?",
                "answer": "Use the current card's deletion rule before changing the tree.",
            }

        report = validate_scope_adherence(lesson, contract)

        self.assertTrue(report["passed"], report["issues"])

    def test_scope_validator_rejects_insertion_inside_bst_deletion_lesson(self) -> None:
        topic = SimpleNamespace(
            title="BST deletion",
            purpose="Delete nodes while preserving the BST invariant.",
            course_type="data_structure_operation",
            secondary_course_types=[],
            prerequisite_topics="",
        )
        contract = build_topic_scope_contract(topic)
        lesson = {
            "lesson_cards": [
                {
                    "blueprint_key": "structure_refresh_first_impression",
                    "title": "BST Deletion Context",
                    "main_concept": "BST deletion setup",
                    "points": ["Deletion removes one node while preserving the ordering invariant."],
                },
                {
                    "blueprint_key": "operation_goal",
                    "title": "BST insertion",
                    "main_concept": "how BST insertion works",
                    "points": ["Insertion walks downward and attaches a new leaf."],
                },
            ],
            "practice_questions": [],
        }

        report = validate_scope_adherence(lesson, contract)

        self.assertFalse(report["passed"])
        self.assertTrue(any("insertion" in issue.lower() for issue in report["issues"]))

    def test_scope_validator_requires_full_allowed_blueprint_sequence(self) -> None:
        contract = {
            "current_topic": "BST Traversals",
            "course_type": "algorithm_walkthrough",
            "allowed_card_sequence": [
                "context_first_impression",
                "algorithm_rule_main_idea",
                "state_components",
                "practice",
            ],
            "out_of_scope_content": [],
            "must_not_teach": [],
        }
        lesson = {
            "lesson_cards": [
                {
                    "blueprint_key": "context_first_impression",
                    "title": "Context",
                    "main_concept": "Traversal context",
                    "points": ["Traversal means visiting each node in a chosen order."],
                },
                {
                    "blueprint_key": "algorithm_rule_main_idea",
                    "title": "Rule",
                    "main_concept": "Traversal rule",
                    "points": ["The rule decides when the current node is visited."],
                    "micro_check": {
                        "prompt": "When is the current node visited?",
                        "answer": "It depends on the traversal rule.",
                    },
                },
                {
                    "blueprint_key": "practice",
                    "title": "Practice",
                    "main_concept": "Traversal practice",
                    "points": ["Predict the output order from a small tree."],
                },
            ],
            "practice_questions": [
                {
                    "question_type": "ordering",
                    "question_text": "Order the visited nodes.",
                    "concept_tested": "traversal order",
                }
            ],
        }

        report = validate_scope_adherence(lesson, contract)

        self.assertFalse(report["passed"])
        self.assertTrue(
            any("state_components" in issue for issue in report["issues"]),
            report["issues"],
        )

    def test_scope_validator_requires_stage_rule_microchecks(self) -> None:
        contract = {
            "current_topic": "BST Traversals",
            "course_type": "algorithm_walkthrough",
            "allowed_card_sequence": [
                "context_first_impression",
                "algorithm_rule_main_idea",
                "practice",
            ],
            "out_of_scope_content": [],
            "must_not_teach": [],
        }
        lesson = {
            "lesson_cards": [
                {
                    "blueprint_key": "context_first_impression",
                    "title": "Context",
                    "main_concept": "Traversal context",
                    "points": ["Traversal means visiting each node in a chosen order."],
                },
                {
                    "blueprint_key": "algorithm_rule_main_idea",
                    "title": "Rule",
                    "main_concept": "Traversal rule",
                    "points": ["The rule decides when the current node is visited."],
                    "micro_check": {"type": "", "prompt": "", "answer": ""},
                },
                {
                    "blueprint_key": "practice",
                    "title": "Practice",
                    "main_concept": "Traversal practice",
                    "points": ["Predict the output order from a small tree."],
                },
            ],
            "practice_questions": [
                {
                    "question_type": "ordering",
                    "question_text": "Order the visited nodes.",
                    "concept_tested": "traversal order",
                }
            ],
        }

        report = validate_scope_adherence(lesson, contract)

        self.assertFalse(report["passed"])
        self.assertTrue(
            any("missing required micro_check" in issue for issue in report["issues"]),
            report["issues"],
        )

    def test_scope_validator_requires_explicit_stage_visual_support(self) -> None:
        contract = {
            "current_topic": "BST deletion",
            "course_type": "data_structure_operation",
            "allowed_card_sequence": ["structure_refresh_first_impression"],
            "out_of_scope_content": [],
            "must_not_teach": [],
        }
        lesson = {
            "lesson_cards": [
                {
                    "blueprint_key": "structure_refresh_first_impression",
                    "title": "BST Structure",
                    "main_concept": "valid BST at rest",
                    "points": ["A valid BST keeps smaller values on the left."],
                }
            ],
            "practice_questions": [
                {
                    "question_type": "visual_labeling",
                    "question_text": "Label the root.",
                    "concept_tested": "BST structure",
                }
            ],
        }

        report = validate_scope_adherence(lesson, contract)

        self.assertFalse(report["passed"])
        self.assertTrue(
            any("missing required visual support" in issue for issue in report["issues"]),
            report["issues"],
        )

    def test_scope_validator_requires_explicit_stage_styled_support(self) -> None:
        contract = {
            "current_topic": "Implement traversal",
            "course_type": "coding_implementation",
            "allowed_card_sequence": ["variables_state_needed"],
            "out_of_scope_content": [],
            "must_not_teach": [],
        }
        lesson = {
            "lesson_cards": [
                {
                    "blueprint_key": "variables_state_needed",
                    "title": "Variables",
                    "main_concept": "variables needed",
                    "points": ["Each variable tracks a specific part of traversal state."],
                    "micro_check": {
                        "prompt": "What does the stack track?",
                        "answer": "Nodes waiting to be visited.",
                    },
                }
            ],
            "practice_questions": [
                {
                    "question_type": "coding",
                    "question_text": "Write the traversal function.",
                    "concept_tested": "variables needed",
                }
            ],
        }

        report = validate_scope_adherence(lesson, contract)

        self.assertFalse(report["passed"])
        self.assertTrue(
            any("missing required styled_elements support" in issue for issue in report["issues"]),
            report["issues"],
        )

    def test_bst_search_and_insertion_scopes_block_sibling_operations(self) -> None:
        search_topic = SimpleNamespace(
            title="BST search",
            purpose="Find whether a target value appears in a BST.",
            course_type="data_structure_operation",
            secondary_course_types=[],
            prerequisite_topics="",
        )
        insert_topic = SimpleNamespace(
            title="BST insertion",
            purpose="Insert a new value at the correct leaf position.",
            course_type="data_structure_operation",
            secondary_course_types=[],
            prerequisite_topics="",
        )

        search_contract = build_topic_scope_contract(search_topic)
        insert_contract = build_topic_scope_contract(insert_topic)

        self.assertIn("BST search goal", search_contract["in_scope_content"])
        self.assertIn("BST deletion", search_contract["out_of_scope_content"])
        self.assertIn("BST insertion goal", insert_contract["in_scope_content"])
        self.assertIn("BST deletion cases", insert_contract["must_not_teach"])

    def test_what_is_bst_classifies_as_concept_intuition(self) -> None:
        result = classify_topic_course_type(
            user_goal="What is a BST?",
            topic_title="Binary Search Tree",
            topic_purpose="Understand the structure and ordering property.",
        )

        self.assertEqual(result["primary_course_type"], "concept_intuition")

    def test_compare_scope_does_not_allow_full_side_lessons(self) -> None:
        topic = SimpleNamespace(
            title="BFS vs DFS",
            purpose="Distinguish traversal behavior and use cases.",
            course_type="compare_distinguish",
            secondary_course_types=[],
            prerequisite_topics="",
        )

        contract = build_topic_scope_contract(topic)

        self.assertEqual(contract["course_type"], "compare_distinguish")
        self.assertIn("same example applied to both ideas", contract["in_scope_content"])
        self.assertIn("complete standalone reteach of either side", contract["out_of_scope_content"])

    def test_coding_scope_keeps_lesson_on_implementation(self) -> None:
        topic = SimpleNamespace(
            title="Implement Inorder Traversal in C++",
            purpose="Write the recursive traversal function.",
            course_type="coding_implementation",
            secondary_course_types=[],
            prerequisite_topics="",
        )

        contract = build_topic_scope_contract(topic)

        self.assertEqual(contract["course_type"], "algorithm_walkthrough")
        self.assertIn("coding_implementation", contract["secondary_course_types"])
        self.assertIn("code_build_up", contract["allowed_card_sequence"])

    def test_lesson_prompt_no_longer_forces_generic_14_card_flow(self) -> None:
        self.assertNotIn("Format every lesson using this card sequence", SYSTEM_PROMPT)
        self.assertNotIn("The example set must cover the full surface area", SYSTEM_PROMPT)

    def test_lesson_prompt_includes_topic_scope_contract(self) -> None:
        topic = SimpleNamespace(
            title="BST Traversals",
            purpose="Trace traversal order.",
            unit_title="Trees",
            prerequisite_topics="",
            source_refs="",
            course_type="algorithm_walkthrough",
            secondary_course_types=[],
            knowledge_level=2,
        )
        prompt = build_lesson_user_prompt(
            topic=topic,
            chunks=[],
            topic_scope_contract={
                "current_topic": "BST Traversals",
                "allowed_card_sequence": ["context_first_impression", "practice"],
                "must_not_teach": ["BST deletion cases"],
            },
        )

        self.assertIn("TOPIC SCOPE CONTRACT", prompt)
        self.assertIn("BST deletion cases", prompt)
        self.assertIn("Generic fallback cards are only allowed", prompt)

    def test_flexible_lesson_schema_accepts_scope_runtime_fields(self) -> None:
        payload = {
            "course_type": "algorithm_walkthrough",
            "secondary_course_types": ["coding_implementation"],
            "knowledge_level": 2,
            "topic_scope_contract": {
                "current_topic": "Inorder Traversal",
                "course_type": "algorithm_walkthrough",
                "allowed_card_sequence": ["context_first_impression", "practice"],
            },
            "lesson_cards": [
                {
                    "id": "card-1",
                    "blueprint_key": "context_first_impression",
                    "card_type": "intro",
                    "title": "Traversal Context",
                    "main_concept": "Traversal context",
                    "learning_goal": "Understand what this traversal card covers.",
                    "points": ["Traversal visits nodes in a chosen order."],
                    "styled_elements": [
                        {
                            "type": "checklist",
                            "title": "Traversal reminders",
                            "data": {"items": []},
                        }
                    ],
                }
            ],
            "practice_questions": [
                {
                    "question_type": "math",
                    "question_text": "How many nodes are visited?",
                    "given": {"nodes": 7},
                }
            ],
            "scope_validation_report": {"passed": True, "issues": []},
            "validation_report": {"passed": True, "issues": []},
        }

        parsed = FlexibleLessonJson(**payload)

        self.assertEqual(parsed.topic_scope_contract.current_topic, "Inorder Traversal")
        self.assertEqual(parsed.lesson_cards[0].learning_goal, "Understand what this traversal card covers.")
        self.assertEqual(parsed.practice_questions[0].question_type, "math")

    def test_sync_validation_report_combines_runtime_reports(self) -> None:
        lesson = {
            "scope_validation_report": {
                "passed": False,
                "requires_regeneration": True,
                "issues": ["Card 1 teaches forbidden content."],
            },
            "visual_validation_report": {
                "passed": True,
                "requires_regeneration": False,
                "issues": [],
            },
            "topic_quality_report": {
                "passed": False,
                "requires_regeneration": False,
                "issues": [
                    {
                        "severity": "error",
                        "code": "stage_microcheck_missing",
                        "message": "Required microcheck is missing.",
                    }
                ],
            },
        }

        sync_validation_report(lesson)

        self.assertFalse(lesson["validation_report"]["passed"])
        self.assertTrue(lesson["validation_report"]["requires_regeneration"])
        self.assertEqual(len(lesson["validation_report"]["issues"]), 2)
        self.assertIn("scope_validation_report", lesson["validation_reports"])

    def test_lesson_generator_metadata_fallback_classifies_bare_bst_traversal_topic(self) -> None:
        topic = SimpleNamespace(
            title="BST Traversals",
            purpose="Trace traversal order through a binary search tree.",
            course_type=None,
            secondary_course_types=None,
            knowledge_level=None,
            source_refs="",
        )

        ensure_topic_generation_metadata(topic)
        contract = build_topic_scope_contract(topic)

        self.assertEqual(topic.course_type, "algorithm_walkthrough")
        self.assertIsInstance(topic.knowledge_level, int)
        self.assertEqual(contract["course_type"], "algorithm_walkthrough")
        self.assertIn("BST insertion", contract["out_of_scope_content"])

    def test_blueprint_sequence_metadata_prefers_scope_contract_sequence(self) -> None:
        lesson = {
            "topic_scope_contract": {
                "allowed_card_sequence": [
                    "context_first_impression",
                    "practice",
                    "code_build_up",
                ]
            }
        }
        blueprint = {
            "default_card_sequence": [
                "context_first_impression",
                "definition",
                "practice",
            ]
        }

        sequence = get_lesson_blueprint_card_sequence(lesson, blueprint)

        self.assertEqual(
            sequence,
            ["context_first_impression", "practice", "code_build_up"],
        )

    def test_generate_and_finalize_lesson_injects_scope_for_bare_topic(self) -> None:
        topic = SimpleNamespace(
            title="BST Traversals",
            purpose="Trace traversal order through a binary search tree.",
            course_type=None,
            secondary_course_types=None,
            knowledge_level=None,
            source_refs="",
            unit_title="Trees",
            prerequisite_topics="",
        )

        with patch(
            "app.services.lesson_generator.generate_structured_lesson",
            return_value=build_valid_bst_traversal_lesson(),
        ) as generate_mock:
            lesson = generate_and_finalize_lesson(topic=topic, chunks=[])

        self.assertEqual(topic.course_type, "algorithm_walkthrough")
        self.assertEqual(lesson["course_type"], "algorithm_walkthrough")
        self.assertEqual(
            lesson["topic_scope_contract"]["allowed_card_sequence"],
            [
                "context_first_impression",
                "algorithm_rule_main_idea",
                "state_components",
                "how_it_works",
                "comprehensive_walkthrough_example",
                "final_result_output",
                "practice",
            ],
        )
        self.assertTrue(lesson["scope_validation_report"]["passed"], lesson["scope_validation_report"]["issues"])
        called_prompt = generate_mock.call_args.kwargs["user_prompt"]
        self.assertIn("TOPIC SCOPE CONTRACT", called_prompt)
        self.assertIn("BST insertion", called_prompt)

    def test_build_lesson_retries_once_when_scope_validator_catches_drift(self) -> None:
        topic = SimpleNamespace(
            title="BST Traversals",
            purpose="Trace traversal order through a binary search tree.",
            course_type=None,
            secondary_course_types=None,
            knowledge_level=None,
            source_refs="",
            unit_title="Trees",
            prerequisite_topics="",
        )

        with patch(
            "app.services.lesson_generator.generate_structured_lesson",
            side_effect=[
                build_drifting_bst_traversal_lesson(),
                build_valid_bst_traversal_lesson(),
                build_valid_bst_traversal_lesson(),
                build_valid_bst_traversal_lesson(),
                build_valid_bst_traversal_lesson(),
            ],
        ) as generate_mock:
            lesson = build_lesson_from_topic_and_chunks(topic=topic, chunks=[])

        self.assertGreaterEqual(generate_mock.call_count, 2)
        self.assertTrue(lesson["scope_validation_report"]["passed"], lesson["scope_validation_report"]["issues"])
        card_text = " ".join(card["title"] for card in lesson["lesson_cards"]).lower()
        self.assertNotIn("insertion", card_text)

def build_valid_bst_traversal_lesson() -> dict:
    visual = {
        "type": "node_link_diagram",
        "title": "BST traversal example",
        "nodes": [
            {"id": "4", "label": "4", "x": 50, "y": 15},
            {"id": "2", "label": "2", "x": 30, "y": 38},
            {"id": "6", "label": "6", "x": 70, "y": 38},
        ],
        "edges": [
            {"from": "4", "to": "2", "style": "solid"},
            {"from": "4", "to": "6", "style": "solid"},
        ],
        "traversal_path": ["2", "4", "6"],
    }
    return {
        "intro": "You are learning BST traversal order.",
        "purpose": "Traversal lets you visit every node in a controlled order.",
        "context": "This topic uses the BST property only as a brief reading aid.",
        "learning_objective": "Trace traversal state and produce the final visit order.",
        "components": ["current node", "left subtree", "right subtree", "output order"],
        "concepts": ["traversal order", "current node", "output order"],
        "process": ["Choose the traversal rule.", "Visit nodes according to that rule."],
        "limitations": ["Traversal does not explain insertion, deletion, or balancing."],
        "worked_examples": ["Trace inorder on 2, 4, 6."],
        "edge_cases": ["Empty subtree contributes no visited value."],
        "practice": ["Order the visited nodes."],
        "key_takeaways": ["Traversal is about visit order, not modifying the tree."],
        "visual_plan": [visual],
        "lesson_cards": [
            bst_traversal_card(
                1,
                "context_first_impression",
                "Context / First Impression",
                "intro",
                "Traversal visits each node without changing links.",
                visual_index=-1,
            ),
            bst_traversal_card(
                2,
                "algorithm_rule_main_idea",
                "Algorithm Rule / Main Idea",
                "core_idea",
                "The rule decides when the current node is output.",
            ),
            bst_traversal_card(
                3,
                "state_components",
                "State / Components",
                "definition",
                "State tracks current node, pending subtree, and output.",
                visual_index=0,
            ),
            bst_traversal_card(
                4,
                "how_it_works",
                "How It Works",
                "method_process",
                "Inorder traversal visits left subtree, current node, then right subtree.",
                visual_index=0,
            ),
            bst_traversal_card(
                5,
                "comprehensive_walkthrough_example",
                "Comprehensive Walkthrough Example",
                "worked_example",
                "The example outputs 2, then 4, then 6.",
                visual_index=0,
            ),
            bst_traversal_card(
                6,
                "final_result_output",
                "Final Result / Output",
                "summary",
                "The final output is the visited values in order.",
                visual_index=0,
            ),
            bst_traversal_card(
                7,
                "practice",
                "Practice",
                "quick_practice",
                "Predict the traversal order for a small tree.",
                visual_index=-1,
                practice_question_index=0,
            ),
        ],
        "practice_questions": [
            {
                "question_type": "ordering",
                "question_text": "Order the inorder traversal of root 4 with children 2 and 6.",
                "concept_tested": "traversal order",
                "related_section": "Final Result / Output",
                "why_this_matters": "This checks whether the visit rule produces the final output.",
                "correct_answer": "2, 4, 6",
                "explanation": "Inorder visits left subtree, current node, then right subtree.",
            }
        ],
        "source_preview": "Generated from topic metadata.",
        "adaptation_metadata": {
            "starting_mode": "default",
            "estimated_state": "not_provided",
            "adaptation_summary": "Azalea used the scoped traversal sequence.",
            "teaching_strategy": "algorithm-walkthrough",
        },
    }


def bst_traversal_card(
    index: int,
    blueprint_key: str,
    title: str,
    card_type: str,
    point: str,
    visual_index: int = -1,
    practice_question_index: int = -1,
) -> dict:
    micro_check = {"type": "", "prompt": "", "answer": ""}
    if blueprint_key not in {"context_first_impression", "practice"}:
        micro_check = {
            "type": "reveal",
            "prompt": "What does this traversal step determine?",
            "answer": "It determines the next visited node or output state.",
        }

    return {
        "id": f"card-{index}",
        "blueprint_key": blueprint_key,
        "card_type": card_type,
        "title": title,
        "main_concept": f"{title} for BST traversal",
        "learning_goal": f"Use {title.lower()} to trace traversal only.",
        "points": [point],
        "body": "",
        "bullets": [],
        "new_concepts": ["BST traversal"] if index == 1 else [],
        "review_concepts": [],
        "prerequisite_concepts": ["BST property"] if index == 1 else [],
        "concept_support": [],
        "interactive_links": [],
        "styled_elements": [],
        "visual_plan": {},
        "visual_index": visual_index,
        "annotations": [],
        "example": "",
        "micro_check": micro_check,
        "deeper_explanation": "",
        "what_to_notice": "Notice that traversal reads nodes without modifying links.",
        "estimated_seconds": 35,
        "transition_text": "Continue to the next traversal stage.",
        "next_card_label": "Continue",
        "practice_question_index": practice_question_index,
        "quality_score": 90,
    }


def build_drifting_bst_traversal_lesson() -> dict:
    lesson = build_valid_bst_traversal_lesson()
    lesson["lesson_cards"][1]["title"] = "BST insertion"
    lesson["lesson_cards"][1]["main_concept"] = "how BST insertion works"
    lesson["lesson_cards"][1]["points"] = ["Insertion walks downward and attaches a new leaf."]
    return lesson


if __name__ == "__main__":
    unittest.main()
