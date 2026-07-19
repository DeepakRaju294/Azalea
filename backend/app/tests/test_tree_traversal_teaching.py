"""BST-traversal path review fixes (2026-07-19): structure-true step reasons, an attemptable setup card
(tree shape + prediction task), hyphen-safe coding-topic titles, and space-form routing so the coding
topics receive the ONE canonical verified implementation instead of inconsistent LLM code."""
import ast
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples.trace_adapters.families.trees import (
    InorderTraversalAdapter, _inorder_reason, _tree_setup_display,
)
from app.services.examples.trace_pipeline import _to_solve_result, route_adapter
from app.services.examples.solver import _build_solution_cards
from app.services.examples.canonical_solutions import display_solution
from app.services.topic_generator import _subject_phrase


class InorderStepReasons(unittest.TestCase):
    """The old single template ('X's left subtree is fully visited') was applied blindly — false for leaves.
    Every reason must now be TRUE of the node's actual structure."""

    def _trace(self, seed=7):
        a = InorderTraversalAdapter()
        inst = next(iter(a.candidates(seed)))
        return inst, a.reference(inst, seed=seed)

    def test_leaf_steps_never_claim_a_left_subtree(self):
        for seed in range(12):
            inst, tr = self._trace(seed)
            tree = inst["tree"]
            for step in tr.steps:
                node = step.inputs["node"]
                if tree[node]["left"] is None:
                    self.assertNotIn("left subtree is fully visited", step.reason,
                                     f"seed {seed}: node {node} has no left subtree but the reason claims one")

    def test_left_subtree_reason_only_on_nodes_that_have_one(self):
        for seed in range(12):
            inst, tr = self._trace(seed)
            tree = inst["tree"]
            for step in tr.steps:
                if "left subtree is fully visited" in step.reason:
                    self.assertIsNotNone(tree[step.inputs["node"]]["left"])

    def test_first_step_root_wording_when_root_has_no_left_child(self):
        # A right-skewed tree: root IS the first inorder visit — say "the root", not "the leftmost node".
        tree = {2: {"left": None, "right": 37}, 37: {"left": None, "right": None}}
        self.assertIn("the root 2 has no left child", _inorder_reason(tree, 2, 2, 1))
        # A genuine leftmost (non-root) first visit keeps the walk-left explanation.
        tree2 = {10: {"left": 4, "right": None}, 4: {"left": None, "right": None}}
        self.assertIn("leftmost", _inorder_reason(tree2, 10, 4, 1))


class SetupCardDisplay(unittest.TestCase):
    """The setup card must be attemptable: show the tree's shape and pose the prediction task — not just
    'the BST built by inserting [...]' which forces a mental replay of the inserts."""

    def test_setup_display_shows_every_parent_and_poses_the_task(self):
        tree = {2: {"left": None, "right": 37}, 37: {"left": 32, "right": 38},
                32: {"left": 21, "right": None}, 21: {"left": 4, "right": None},
                4: {"left": None, "right": None}, 38: {"left": None, "right": None}}
        lines = _tree_setup_display(tree, 2, "an inorder")
        joined = "\n".join(lines)
        self.assertIn("The tree (parent → children):", lines[0])
        self.assertIn("2 → right: 37", joined)
        self.assertIn("37 → left: 32, right: 38", joined)
        self.assertIn("Your task:", joined)
        self.assertIn("Predict the order an inorder traversal visits the nodes", joined)

    def test_single_node_tree_still_describes_the_tree(self):
        lines = _tree_setup_display({9: {"left": None, "right": None}}, 9, "a preorder")
        self.assertTrue(any("only the root 9" in l for l in lines))

    def test_setup_display_flows_from_trace_to_setup_card(self):
        a = InorderTraversalAdapter()
        inst = next(iter(a.candidates(3)))
        tr = a.reference(inst, seed=3)
        self.assertTrue(tr.setup_display, "trace must carry setup_display")
        step = {"goal": "visit the first node", "reasoning": "it is next in inorder",
                "work": ["visit it"], "result": "output updated"}
        sol = _to_solve_result(tr, [step])
        cards = _build_solution_cards(sol, {"id": "t1", "topic_type": "algorithm_walkthrough"})
        setup_points = "\n".join(cards[0]["points"])
        self.assertIn("The tree (parent → children):", setup_points)
        self.assertIn("Your task:", setup_points)
        # the tree lines come AFTER the problem statement
        self.assertLess(setup_points.index("Problem:"), setup_points.index("The tree"))


class SubjectKeyHyphenCompounds(unittest.TestCase):
    """normalize_subject_key split 'In-Order' and the framing word 'in' swallowed it -> subject_key
    'order_traversal' -> the policy coding topic 'Implementing Order Traversal' -> routing miss -> the topic
    shipped unverified LLM code instead of the canonical (live bug, second layer beyond _subject_phrase)."""

    def test_hyphen_compound_survives_framing_strip(self):
        from app.core.topic_decomposition import normalize_subject_key
        self.assertEqual(normalize_subject_key("In-Order Traversal"), "in_order_traversal")
        self.assertEqual(normalize_subject_key("Post-Order Traversal"), "post_order_traversal")
        # all-framing compounds still drop; plain framing stripping unchanged
        self.assertEqual(normalize_subject_key("Step-by-Step Guide to Merge Sort"), "merge_sort")
        self.assertEqual(normalize_subject_key("Understanding Quick Sort Algorithm"), "quick_sort")

    def test_policy_coding_title_from_fixed_subject_key_routes(self):
        from app.core.topic_decomposition import normalize_subject_key
        from app.services.topic_decomposition_pipeline import _subject_phrase
        title = f"Implementing {_subject_phrase(normalize_subject_key('In-Order Traversal'))}"
        self.assertEqual(title, "Implementing In Order Traversal")
        ad = route_adapter({"title": title, "topic_type": "coding_implementation",
                            "course_type": "coding_implementation"})
        self.assertEqual(getattr(ad, "slug", None), "tree_inorder")


class AcronymParentDemotion(unittest.TestCase):
    """A full 'Binary Search Tree' walkthrough on a 'bst traversal' path overlapped the BST prerequisite —
    prereqs and taught topics must never overlap. The topic (the multiword expansion of an acronym the goal
    uses) is demoted to a structured prerequisite; the subject a path's siblings implement never is."""

    @staticmethod
    def _t(title, tt="algorithm_walkthrough"):
        return {"title": title, "topic_type": tt, "course_type": tt}

    def test_bst_expansion_demoted_on_bst_traversal_goal(self):
        from app.services.topic_decomposition_pipeline import _demote_parent_of_goal_topics
        topics = [self._t("Binary Search Tree"), self._t("In-Order Traversal"),
                  self._t("Post-Order Traversal"),
                  self._t("Implementing In Order Traversal", "coding_implementation")]
        demoted = _demote_parent_of_goal_topics(topics, "Want to learn about BST traversal")
        self.assertEqual(demoted, ["Binary Search Tree"])
        self.assertNotIn("Binary Search Tree", [t["title"] for t in topics])

    def test_acronym_subject_its_siblings_implement_is_never_demoted(self):
        from app.services.topic_decomposition_pipeline import _demote_parent_of_goal_topics
        topics = [self._t("Breadth-First Search"), self._t("Implementing BFS", "coding_implementation")]
        self.assertEqual(_demote_parent_of_goal_topics(topics, "learn bfs traversal"), [])
        self.assertEqual(len(topics), 2)

    def test_goal_that_is_just_the_acronym_never_demotes(self):
        from app.services.topic_decomposition_pipeline import _demote_parent_of_goal_topics
        topics = [self._t("Binary Search Tree"), self._t("BST Insertion")]
        # goal IS the acronym subject (no substantive word beyond it) -> the expansion topic stays
        self.assertEqual(_demote_parent_of_goal_topics(topics, "learn about bst"), [])


class CodingTopicTitleAndRouting(unittest.TestCase):
    """'In-Order Traversal' must keep its 'In-' when titling the coding topic, and both hyphen and space
    title forms must route to the tree adapters — routing is what stamps the canonical verified code, so a
    routing miss is how the three sibling topics shipped THREE inconsistent TreeNode variants."""

    def test_subject_phrase_preserves_hyphenated_compounds(self):
        self.assertEqual(_subject_phrase("In-Order Traversal"), "In-Order Traversal")
        self.assertEqual(_subject_phrase("Post-Order Traversal"), "Post-Order Traversal")
        # all-framing hyphen compounds still drop; plain framing-word stripping is unchanged
        self.assertEqual(_subject_phrase("Trace Quick Sort Step-by-Step"), "Quick Sort")
        self.assertEqual(_subject_phrase("Trace Quick Sort Algorithm Step by Step"), "Quick Sort")

    def test_space_form_titles_route_to_tree_adapters(self):
        cases = {"Implementing In Order Traversal": "tree_inorder",
                 "Implementing In-Order Traversal": "tree_inorder",
                 "Implementing Post Order Traversal": "tree_postorder",
                 "Implementing Pre Order Traversal": "tree_preorder"}
        for title, slug in cases.items():
            ad = route_adapter({"title": title, "topic_type": "coding_implementation",
                                "course_type": "coding_implementation"})
            self.assertEqual(getattr(ad, "slug", None), slug, title)

    def test_bare_in_order_phrase_does_not_false_route(self):
        ad = route_adapter({"title": "Sorting Numbers In Order", "topic_type": "coding_implementation",
                            "course_type": "coding_implementation"})
        self.assertIsNone(ad)


class CanonicalTreeCodeSelfContained(unittest.TestCase):
    """The displayed canonical must say what .val/.left/.right ARE (the live lessons referenced node.val on a
    class the panel never defined) and must still parse."""

    def test_tree_canonicals_carry_node_shape_comment_and_parse(self):
        for slug in ("tree_inorder", "tree_preorder", "tree_postorder", "tree_levelorder"):
            code = display_solution(slug, "python")
            self.assertIsNotNone(code, slug)
            self.assertIn("Each tree node has .val", code, slug)
            ast.parse(code)


if __name__ == "__main__":
    unittest.main()
