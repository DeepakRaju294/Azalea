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


class PostorderCanonicalReproducesTrace(unittest.TestCase):
    """The old tree_postorder canonical was the reversed-preorder trick (result[::-1]): right FINAL answer but
    ZERO of the trace's intermediate states occur during execution — so every per-step code annotation
    contradicted the walkthrough (live bug), and the variant gate skipped all non-array shapes so nothing
    caught it. The canonical is now a true-postorder flagged stack, and the gate covers trees."""

    def test_gate_applies_to_tree_traces(self):
        from app.services.examples.code_execution_check import reproduces_trace_applies
        from app.services.examples.canonical_solutions import canonical_python
        a = route_adapter({"title": "Post-Order Traversal", "topic_type": "data_structure_operation",
                           "course_type": "data_structure_operation"})
        tr = a.reference(next(iter(a.candidates(5))), seed=5)
        self.assertTrue(reproduces_trace_applies(tr, canonical_python("tree_postorder")))

    def test_all_traversal_canonicals_reproduce_their_traces(self):
        from app.services.examples.code_execution_check import code_reproduces_trace
        from app.services.examples.canonical_solutions import canonical_python
        for slug, title in (("tree_inorder", "In-Order Traversal"), ("tree_preorder", "Pre-Order Traversal"),
                            ("tree_postorder", "Post-Order Traversal"),
                            ("tree_levelorder", "Level-Order Traversal")):
            a = route_adapter({"title": title, "topic_type": "data_structure_operation",
                               "course_type": "data_structure_operation"})
            code = canonical_python(slug)
            for seed in range(6):
                tr = a.reference(next(iter(a.candidates(seed))), seed=seed)
                self.assertEqual(code_reproduces_trace(code, tr), [], f"{slug} seed {seed}")

    def test_reversed_preorder_variant_is_now_caught(self):
        # The exact code that shipped: right final answer, wrong per-step states -> the gate must flag it.
        from app.services.examples.code_execution_check import code_reproduces_trace
        bad = ("def postorder(root):\n"
               "    result = []\n"
               "    stack = [root]\n"
               "    while stack:\n"
               "        node = stack.pop()\n"
               "        if node is None:\n"
               "            continue\n"
               "        result.append(node.val)\n"
               "        stack.append(node.left)\n"
               "        stack.append(node.right)\n"
               "    return result[::-1]\n")
        a = route_adapter({"title": "Post-Order Traversal", "topic_type": "data_structure_operation",
                           "course_type": "data_structure_operation"})
        tr = a.reference(next(iter(a.candidates(5))), seed=5)
        self.assertNotEqual(code_reproduces_trace(bad, tr), [])


class SpaceFormInOrderSubjectKey(unittest.TestCase):
    """The model also proposes the SPACE form ('in order traversal') — the framing word 'in' swallowed it
    even after the hyphen fix (live: subject_key still order_traversal on the 16:53 path)."""

    def test_space_form_fuses_to_compound(self):
        from app.core.topic_decomposition import normalize_subject_key
        self.assertEqual(normalize_subject_key("in order traversal"), "in_order_traversal")
        self.assertEqual(normalize_subject_key("In Order Traversal"), "in_order_traversal")

    def test_prepositional_in_order_to_is_not_fused(self):
        from app.core.topic_decomposition import normalize_subject_key
        self.assertNotIn("in_order", normalize_subject_key("sort numbers in order to find the median"))

    def test_subject_phrase_space_form(self):
        self.assertEqual(_subject_phrase("In Order Traversal"), "In-Order Traversal")


class NoPrereqTopicOverlap(unittest.TestCase):
    """Live duplicate: assumed_prerequisites = ['binary_search_tree' (model slug), 'Binary Search Tree'
    (demotion display name)] — dedup must be shape-blind and render display form."""

    _RESP = {
        "path_plan": {
            "end_capability": "Traverse a BST.",
            "end_capability_actions": ["trace"],
            # live duplicate: the model emitted the PLURAL alongside the demotion's singular display name
            "assumed_prerequisites": ["binary search trees"],
            "required_capabilities": [
                {"capability_id": "c_trav", "description": "Traverse.", "prerequisite_capability_ids": [],
                 "satisfies_end_actions": ["trace"], "ownership_mode": "standalone", "owner_topic_id": None,
                 "basis": "goal"},
            ],
        },
        "topics": [
            {"topic_id": "t_bst", "capability_id": "c_trav", "subject_key": "binary_search_tree",
             "primary_action": "trace", "content_role": "mechanism", "topic_type": "data_structure_operation",
             "title": "Binary Search Tree", "unit_title": "Core", "purpose": "p", "in_scope": ["bst"],
             "practice_target": "t", "practice_format": "short_answer",
             "practice_evidence_type": "trace_structure", "expected_output": "o", "basis": "goal"},
            {"topic_id": "t_in", "capability_id": "c_trav", "subject_key": "in order traversal",
             "primary_action": "trace", "content_role": "mechanism", "topic_type": "data_structure_operation",
             "title": "In-Order Traversal", "unit_title": "Core", "purpose": "p", "in_scope": ["inorder"],
             "practice_target": "t", "practice_format": "short_answer",
             "practice_evidence_type": "trace_structure", "expected_output": "o", "basis": "goal"},
            {"topic_id": "t_post", "capability_id": "c_trav", "subject_key": "post-order traversal",
             "primary_action": "trace", "content_role": "mechanism", "topic_type": "data_structure_operation",
             "title": "Post-Order Traversal", "unit_title": "Core", "purpose": "p", "in_scope": ["postorder"],
             "practice_target": "t", "practice_format": "short_answer",
             "practice_evidence_type": "trace_structure", "expected_output": "o", "basis": "goal"},
            # live redundancy: the model's own umbrella implementation of the goal itself
            {"topic_id": "t_umb", "capability_id": "c_trav", "subject_key": "binary_search_tree_traversal",
             "primary_action": "implement", "content_role": "implementation",
             "topic_type": "coding_implementation", "title": "Implementing BST Traversal",
             "unit_title": "Core", "purpose": "p", "in_scope": ["code"],
             "practice_target": "t", "practice_format": "short_answer",
             "practice_evidence_type": "write_code", "expected_output": "o", "basis": "goal"},
        ],
    }

    def _run(self):
        from app.services.topic_decomposition_pipeline import generate_decomposed_topics
        return generate_decomposed_topics("Want to learn about BST traversal", "src",
                                          model_fn=lambda p: self._RESP, coding_follow_ups=True)

    def test_single_display_form_bst_prereq_and_no_bst_topic(self):
        topics = self._run()
        titles = [t["title"] for t in topics]
        self.assertNotIn("Binary Search Tree", titles)       # demoted, not taught
        intro = next(t for t in topics if t.get("course_type") == "study_path_introduction")
        ap = intro.get("assumed_prerequisites") or []
        # plural-blind: 'binary search trees' (model) and 'Binary Search Tree' (demotion) are ONE concept
        bst = [a for a in ap if "".join(sorted(w.rstrip("s") for w in a.lower().replace("_", " ").split()))
               == "".join(sorted(w.rstrip("s") for w in "binary search tree".split()))]
        self.assertEqual(len(bst), 1, f"exactly one BST prereq expected, got {ap}")
        self.assertNotIn("_", bst[0])                        # display form, never the raw slug

    def test_umbrella_goal_coding_topic_is_dropped(self):
        topics = self._run()
        titles = [t["title"] for t in topics]
        self.assertNotIn("Implementing BST Traversal", titles)
        # the specific member implementations remain
        self.assertTrue(any(t.get("course_type") == "coding_implementation" for t in topics))

    def test_coding_follow_up_title_keeps_in_and_routes(self):
        topics = self._run()
        coding = [t for t in topics if t.get("course_type") == "coding_implementation"
                  and "order" in t["title"].lower() and "post" not in t["title"].lower()]
        self.assertTrue(coding, "in-order coding follow-up expected")
        title = coding[0]["title"]
        self.assertIn("In", title.split("Implementing ")[-1])   # never 'Implementing Order Traversal'
        ad = route_adapter({"title": title, "topic_type": "coding_implementation",
                            "course_type": "coding_implementation"})
        self.assertEqual(getattr(ad, "slug", None), "tree_inorder", title)


class CanonicalTreeCodeSelfContained(unittest.TestCase):
    """The displayed canonical must say what .val/.left/.right ARE (the live lessons referenced node.val on a
    class the panel never defined) and must still parse. Product decision: the in/pre/post traversal
    canonicals are the RECURSIVE teaching-standard form (level-order stays a queue)."""

    def test_tree_canonicals_carry_node_shape_comment_and_parse(self):
        for slug in ("tree_inorder", "tree_preorder", "tree_postorder", "tree_levelorder"):
            code = display_solution(slug, "python")
            self.assertIsNotNone(code, slug)
            self.assertIn("Each tree node has .val", code, slug)
            ast.parse(code)

    def test_depth_traversal_canonicals_are_recursive(self):
        for slug in ("tree_inorder", "tree_preorder", "tree_postorder"):
            code = display_solution(slug, "python")
            self.assertIn("def visit(node):", code, slug)           # recursive helper
            self.assertIn("visit(node.left)", code, slug)
            self.assertNotIn("stack", code, slug)                    # no iterative stack form


class TreeTraversalFamilyExpansion(unittest.TestCase):
    """A 'bst traversal' path shipped without Level-Order (the model under-generates; the decomposed branch
    never ran the family backfill). The tree_traversal canonical family injects missing members."""

    @staticmethod
    def _walkthrough(title):
        return {"title": title, "course_type": "algorithm_walkthrough",
                "topic_type": "algorithm_walkthrough", "description": "d"}

    def test_missing_members_injected_for_bst_traversal_goal(self):
        from app.services.topic_generator import _expand_canonical_family
        topics = [self._walkthrough("Inorder Traversal"), self._walkthrough("Postorder Traversal"),
                  self._walkthrough("Preorder Traversal")]
        out = _expand_canonical_family(topics, "Want to learn about bst traversal")
        joined = " | ".join(t["title"] for t in out)
        self.assertIn("Level-Order Traversal", joined)
        # present members are not duplicated
        self.assertEqual(sum("Inorder" in t["title"] or "In-Order" in t["title"] for t in out), 1)

    def test_unrelated_goal_never_injects(self):
        from app.services.topic_generator import _expand_canonical_family
        topics = [self._walkthrough("Binary Search")]
        out = _expand_canonical_family(topics, "learn binary search")
        self.assertEqual(len(out), 1)


if __name__ == "__main__":
    unittest.main()
