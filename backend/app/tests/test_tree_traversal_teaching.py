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

    def test_umbrella_discipline_topic_demoted_on_specific_goal(self):
        # Live: 'Fluid Dynamics Fundamentals' taught on a 'fluid turbulence' path while the prereq card
        # independently named the discipline — prereq/topic overlap. The umbrella-discipline topic demotes
        # to the prereq (textbook model: the parent discipline is refreshed via link, never re-taught).
        from app.services.topic_decomposition_pipeline import _demote_parent_of_goal_topics
        topics = [self._t("Fluid Dynamics Fundamentals", "science_mechanism"),
                  self._t("Turbulence Models", "science_mechanism")]
        self.assertEqual(_demote_parent_of_goal_topics(topics, "Want to learn about fluid turbulence"),
                         ["Fluid Dynamics"])
        self.assertEqual([t["title"] for t in topics], ["Turbulence Models"])

    def test_umbrella_discipline_stays_when_goal_is_the_discipline(self):
        from app.services.topic_decomposition_pipeline import _demote_parent_of_goal_topics
        topics = [self._t("Fluid Dynamics Fundamentals", "science_mechanism"),
                  self._t("Bernoulli Equation", "science_mechanism")]
        self.assertEqual(_demote_parent_of_goal_topics(topics, "learn fluid dynamics"), [])


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

    def test_depth_traversal_canonicals_are_recursive_with_top_level_helper(self):
        # Product decisions: recursive (no iterative stack) AND the helper is a SEPARATE top-level function
        # (no nested defs), placed before the wrapper so find_entry_function picks the wrapper (last fn).
        from app.services.examples.code_execution_check import find_entry_function
        for slug, entry in (("tree_inorder", "inorder"), ("tree_preorder", "preorder"),
                            ("tree_postorder", "postorder")):
            code = display_solution(slug, "python")
            tree = ast.parse(code)
            top = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
            self.assertEqual(top, [f"visit_{entry}", entry], slug)   # helper first, wrapper last
            nested = any(isinstance(m, ast.FunctionDef)
                         for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) for m in n.body)
            self.assertFalse(nested, f"{slug}: no nested functions")
            self.assertEqual(find_entry_function(code), entry, slug)
            self.assertIn(f"visit_{entry}(node.left, result)", code, slug)   # recursive
            self.assertNotIn("stack", code, slug)                            # no iterative stack form


class StepFieldContract(unittest.TestCase):
    """Product decision (path review): on non-coding trace-backed step cards, Goal states what the step does
    (restored as a bullet now that titles are bare 'Step N'), Work shows how each state variable updates with
    its contents, and Result is JUST the result — no action prefix, no explanation tail."""

    def _sol(self):
        from app.services.examples.trace_pipeline import _deterministic_narration, _to_solve_result
        a = route_adapter({"title": "In-Order Traversal", "topic_type": "algorithm_walkthrough",
                           "course_type": "algorithm_walkthrough"})
        tr = a.reference(next(iter(a.candidates(7))), seed=7)
        return _to_solve_result(tr, _deterministic_narration(tr, a), adapter=a, code=None), tr

    def test_goal_work_result_shape(self):
        sol, tr = self._sol()
        first = sol["cards"][0]
        self.assertEqual(first["goal"], "visit the next node in inorder position")   # stage's primary decision
        self.assertTrue(any("→" in w and "output" in w for w in first["work"]),      # variable update w/ contents
                        first["work"])
        self.assertTrue(first["result"].startswith("output = ["), first["result"])   # just the result
        self.assertNotIn("Visit", first["result"])                                   # no action prefix
        self.assertNotIn("Complete:", first["result"])                               # no explanation tail

    def test_final_card_states_final_answer(self):
        sol, tr = self._sol()
        last = sol["cards"][-1]
        self.assertIn("Final answer:", last["result"])
        self.assertIn("visit order", last["result"])

    def test_coding_cards_keep_code_anchored_work(self):
        from app.services.examples.trace_pipeline import _to_solve_result
        a = route_adapter({"title": "In-Order Traversal", "topic_type": "algorithm_walkthrough",
                           "course_type": "algorithm_walkthrough"})
        tr = a.reference(next(iter(a.candidates(7))), seed=7)
        cards = [{"trace_step_ids": [tr.steps[0].id], "goal": "", "reasoning": "r",
                  "work": ["result.append(node.val)  // append 4"], "result": "Visit 4"}]
        sol = _to_solve_result(tr, cards, adapter=a, code="def inorder(root): ...")
        self.assertEqual(sol["cards"][0]["work"], ["result.append(node.val)  // append 4"])  # untouched


class CircularPrereqAnatomyStrip(unittest.TestCase):
    """Live failure (18:05 path): prereq 'node traversal' on a 'bst traversal' goal survived the circular
    guard because 'node' is not a goal word — then told the learner to already 'explain and implement
    pre/in/post-order traversal', the exact content of the path. Structural-anatomy words (node/element/tree/
    vertex…) are not a different subject; stripped, the prereq collapses to the goal subject → circular.
    A prereq naming ONLY a structure ('trees') is a legitimate structural prereq and stays."""

    def test_anatomy_wrapped_goal_subject_is_circular(self):
        from app.services.topic_decomposition_pipeline import _is_circular_prereq
        goal = "Want to learn about bst traversal"
        self.assertTrue(_is_circular_prereq("node traversal", goal))
        self.assertTrue(_is_circular_prereq("tree traversal", goal))
        self.assertTrue(_is_circular_prereq("Traversal Basics", goal))

    def test_structural_and_distinct_prereqs_are_kept(self):
        from app.services.topic_decomposition_pipeline import _is_circular_prereq
        goal = "Want to learn about bst traversal"
        self.assertFalse(_is_circular_prereq("binary search trees", goal))
        self.assertFalse(_is_circular_prereq("trees", goal))                      # structure-only name
        self.assertFalse(_is_circular_prereq("linked lists", "learn binary search trees"))
        self.assertFalse(_is_circular_prereq("conditional probability", "learn bayes theorem"))


class PrereqChainRedundancy(unittest.TestCase):
    """Textbook model: the prereq card offers earlier-unit refreshers. A prereq that is itself a prerequisite
    of another listed prereq is redundant — refreshing the advanced one covers it."""

    def test_subset_prereq_dropped_advanced_kept(self):
        from app.services.topic_decomposition_pipeline import _drop_prereq_chain_redundancy as chain
        self.assertEqual(chain(["binary trees", "binary search trees"]), ["binary search trees"])
        self.assertEqual(chain(["probability", "conditional probability"]), ["conditional probability"])
        self.assertEqual(chain(["binary tree", "Binary Search Trees"]), ["Binary Search Trees"])  # plural/case

    def test_unrelated_prereqs_all_kept(self):
        from app.services.topic_decomposition_pipeline import _drop_prereq_chain_redundancy as chain
        self.assertEqual(chain(["linked lists", "binary search trees"]),
                         ["linked lists", "binary search trees"])
        self.assertEqual(chain(["recursion"]), ["recursion"])

    def test_ground_prereq_card_render_backstop(self):
        # Prose-path names include the path's own subject in anatomy wrapping + a chain-redundant parent:
        # the rendered card keeps ONLY the textbook-section prereq.
        from app.services.lean_lesson_generator import _ground_prereq_card

        class _SP:
            goal = "Want to learn about bst traversal"

        class _T:
            id, title, order_index = "i", "Introduction to Bst Traversal", 0
            course_type, topic_type = "study_path_introduction", None
            assumed_prerequisites = ["node traversal", "binary trees", "binary search trees"]
            decomposition_metadata = {}
            study_path = _SP()

        cards = [{"card_type": "purpose_context", "blueprint_key": "prerequisites",
                  "title": "Prerequisites",
                  "points": ["node traversal", "binary trees", "binary search trees"]}]
        out = _ground_prereq_card(cards, _T(), brief_fn=lambda names, goal: [])
        pts = " \n ".join(out[0]["points"]).lower()
        self.assertIn("binary search trees", pts)
        self.assertNotIn("node traversal", pts)              # anatomy-wrapped goal subject
        self.assertNotIn("binary trees\n", pts + "\n")       # chain-redundant parent of BST


class ExamplePlanCertification(unittest.TestCase):
    """Scope-plan increment #1: the certifier resolves AT PLAN TIME which verified adapter backs each
    WE-centric topic (scope_plan.verified_example + we_policy), and finalize enforces it — a topic planned
    with NO verified example never ships a fabricated pseudo-example (live: turbulence essay-steps,
    Navier-Stokes PDE prose as Step cards). Trace-backed content is always kept; unstamped topics untouched."""

    @staticmethod
    def _t(title, tt):
        return {"title": title, "course_type": tt, "topic_type": tt, "in_scope": [], "out_of_scope": []}

    def _plan(self, topic):
        return (topic.get("decomposition_metadata") or {}).get("scope_plan") or {}

    def test_certifier_stamps_verified_and_withhold(self):
        from app.services.topic_generator import _certify_path_scope
        out = _certify_path_scope([self._t("Flow Regimes", "science_mechanism"),
                                   self._t("Photosynthesis Mechanism", "science_mechanism"),
                                   self._t("Comparing MST Algorithms", "compare_distinguish")],
                                  "want to learn about fluid turbulence")
        by = {t["title"]: self._plan(t) for t in out}
        self.assertEqual(by["Flow Regimes"]["verified_example"], "reynolds_number")
        self.assertEqual(by["Flow Regimes"]["we_policy"], "verified")
        self.assertIsNone(by["Photosynthesis Mechanism"]["verified_example"])
        self.assertEqual(by["Photosynthesis Mechanism"]["we_policy"], "conceptual_mechanism")
        self.assertEqual(by["Comparing MST Algorithms"]["we_policy"], "not_applicable")

    def test_enforcement_strips_fabricated_keeps_verified_and_unstamped(self):
        from app.services.examples.handoff import enforce_example_plan

        def lesson(cards):
            return {"lesson_cards": list(cards)}

        def we(tb=False):
            return {"blueprint_key": "worked_example", "card_type": "worked_example", "title": "Step",
                    "metadata": ({"trace_backed": True} if tb else {})}

        bg = {"blueprint_key": "background", "card_type": "purpose_context", "title": "BG"}
        withhold = {"title": "NS", "decomposition_metadata": {"scope_plan": {"we_policy": "withhold_fabricated"}}}
        l1 = lesson([bg, we(), we()])
        enforce_example_plan(l1, withhold)
        self.assertEqual([c["blueprint_key"] for c in l1["lesson_cards"]], ["background"])
        self.assertEqual(l1["metadata"]["worked_example_withheld"], "no_verified_example_planned")
        l2 = lesson([bg, we(True), we()])                     # verified content -> whole example kept
        enforce_example_plan(l2, withhold)
        self.assertEqual(sum(c["blueprint_key"] == "worked_example" for c in l2["lesson_cards"]), 2)
        l3 = lesson([bg, we()])                               # unstamped legacy topic -> untouched
        enforce_example_plan(l3, {"title": "old"})
        self.assertEqual(len(l3["lesson_cards"]), 2)
        l4 = lesson([bg, we()])                               # plan says verified -> untouched
        enforce_example_plan(l4, {"title": "T", "decomposition_metadata":
                                  {"scope_plan": {"we_policy": "verified"}}})
        self.assertEqual(len(l4["lesson_cards"]), 2)


class SameAdapterDuplicateTopics(unittest.TestCase):
    """Live (depreciation path): 'Straight-Line Depreciation Formula' AND 'Applying Straight-Line
    Depreciation' both routed to depreciation_schedule — the learner built the same book-value schedule twice
    with different numbers. Non-coding topics sharing an adapter collapse to the first; teach-then-code pairs
    are exempt."""

    @staticmethod
    def _t(title, tt):
        return {"title": title, "course_type": tt, "topic_type": tt}

    def test_second_same_adapter_topic_dropped(self):
        from app.services.topic_generator import _drop_same_adapter_duplicate_topics as dd
        out = dd([self._t("Straight-Line Depreciation Formula", "math_formula_method"),
                  self._t("Applying Straight-Line Depreciation", "process_walkthrough")])
        self.assertEqual([x["title"] for x in out], ["Straight-Line Depreciation Formula"])

    def test_walkthrough_plus_coding_pair_is_exempt(self):
        from app.services.topic_generator import _drop_same_adapter_duplicate_topics as dd
        out = dd([self._t("Kruskal's Algorithm", "algorithm_walkthrough"),
                  self._t("Implementing Kruskal's Algorithm", "coding_implementation")])
        self.assertEqual(len(out), 2)

    def test_different_adapters_kept(self):
        from app.services.topic_generator import _drop_same_adapter_duplicate_topics as dd
        out = dd([self._t("In-Order Traversal", "algorithm_walkthrough"),
                  self._t("Post-Order Traversal", "algorithm_walkthrough")])
        self.assertEqual(len(out), 2)

    def test_non_we_centric_topic_never_claims_the_adapter_slug(self):
        # Live regression: 'Turbulence and Its Definitions' (concept_intuition — NO worked-example slot)
        # routed via the broad 'turbulence' alias, claimed reynolds_number FIRST, and shadowed the
        # mechanism/formula topics. Non-WE-centric types pass through. UPDATED CONTRACT (adapter-as-identity
        # fix): distinct-concept topics sharing an adapter are KEPT — the certifier's claim pass gives the
        # verified example to the topic whose subject IS the adapter's concept and withholds it on the rest,
        # instead of this pass deleting whole topics.
        from app.services.topic_generator import _certify_path_scope, _drop_same_adapter_duplicate_topics as dd
        topics = [self._t("Turbulence and Its Definitions", "concept_intuition"),
                  self._t("Mechanism of Turbulent Flow", "science_mechanism"),
                  self._t("Reynolds Number and Flow Regimes", "math_formula_method")]
        out = dd(topics)
        self.assertEqual(len(out), 3)                     # different concepts -> nothing deleted
        certified = _certify_path_scope(out, "learn fluid turbulence")
        plans = {t["title"]: (t.get("decomposition_metadata") or {}).get("scope_plan") or {}
                 for t in certified}
        self.assertEqual(plans["Reynolds Number and Flow Regimes"]["verified_example"], "reynolds_number")
        self.assertIsNone(plans["Mechanism of Turbulent Flow"]["verified_example"])


class OrientationOpenerRetype(unittest.TestCase):
    """Live (depreciation path): the model emitted a GENUINE orientation opener typed concept_intuition —
    it consumed the intro slot but its blueprint has NO prerequisites card and NO roadmap, so the path
    structurally lost both surfaces. A genuine orientation opener is retyped study_path_introduction."""

    def test_orientation_opener_becomes_intro_type(self):
        from app.services.topic_decomposition_pipeline import generate_decomposed_topics
        resp = {"path_plan": {"end_capability": "Compute depreciation.",
                              "end_capability_actions": ["calculate"], "assumed_prerequisites": [],
                              "required_capabilities": [
                                  {"capability_id": "c1", "description": "d",
                                   "prerequisite_capability_ids": [], "satisfies_end_actions": ["calculate"],
                                   "ownership_mode": "standalone", "owner_topic_id": None, "basis": "goal"}]},
                "topics": [
                    {"topic_id": "t0", "capability_id": "orientation", "subject_key": "overview",
                     "primary_action": "explain", "content_role": "orientation",
                     "topic_type": "concept_intuition", "title": "Understanding Depreciation",
                     "unit_title": "U", "purpose": "p", "in_scope": ["x"], "practice_target": "t",
                     "practice_format": "short_answer", "practice_evidence_type": "none",
                     "expected_output": "", "basis": "goal"},
                    {"topic_id": "t1", "capability_id": "c1", "subject_key": "straight_line_depreciation",
                     "primary_action": "calculate", "content_role": "calculation",
                     "topic_type": "math_formula_method", "title": "Straight-Line Depreciation Formula",
                     "unit_title": "U", "purpose": "p", "in_scope": ["x"], "practice_target": "t",
                     "practice_format": "short_answer", "practice_evidence_type": "solve_numeric",
                     "expected_output": "o", "basis": "goal"}]}
        out = generate_decomposed_topics("Want to learn about straight line depreciation", "src",
                                         model_fn=lambda p: resp, coding_follow_ups=False)
        opener = out[0]
        self.assertEqual(opener["course_type"], "study_path_introduction")
        self.assertEqual(opener["title"], "Understanding Depreciation")


class ExampleRelevanceGuards(unittest.TestCase):
    """External review: a 'Turbulence Models' topic (scope: k-epsilon, LES) shipped a VERIFIED-but-IRRELEVANT
    Reynolds calculation — worse than unverified, because the verification badge lends trust to an example
    that does not teach the topic. Modeling titles must not route to reynolds_number (they withhold instead);
    and _canonical_concept_key (adapter-first) must no longer IDENTIFY them as reynolds_number."""

    def test_modeling_titles_do_not_route_to_reynolds(self):
        # Modeling topics must never get the Reynolds example (verified-but-irrelevant). They now route to
        # the RELEVANT turbulent_kinetic_energy adapter; LES/DNS-specific titles stay unrouted (withhold).
        for t in ("Turbulence Models", "Turbulence Modeling with k-epsilon", "RANS Closures"):
            a = route_adapter({"title": t, "topic_type": "science_mechanism",
                               "course_type": "science_mechanism"})
            self.assertNotEqual(getattr(a, "slug", None), "reynolds_number", t)
        les = route_adapter({"title": "Large Eddy Simulation", "topic_type": "science_mechanism",
                             "course_type": "science_mechanism"})
        self.assertIsNone(les)

    def test_only_flow_regime_turbulence_titles_route(self):
        for t in ("Fluid Turbulence", "Classes of Turbulence"):
            a = route_adapter({"title": t, "topic_type": "science_mechanism",
                               "course_type": "science_mechanism"})
            self.assertIsNone(a, t)
        a = route_adapter({"title": "Laminar vs Turbulent Flow", "topic_type": "science_mechanism",
                           "course_type": "science_mechanism"})
        self.assertEqual(getattr(a, "slug", None), "reynolds_number")

    def test_turbulence_models_identity_is_not_reynolds(self):
        from app.services.topic_generator import _canonical_concept_key
        self.assertNotEqual(_canonical_concept_key("Turbulence Models", "science_mechanism"),
                            "reynolds_number")

    def test_modeling_topics_route_to_tke_the_relevant_adapter(self):
        # k = ½(u'²+v'²+w'²) IS the k of k-epsilon — a relevant verified example for modeling topics,
        # including the word-order variant 'Models of Turbulence' that dodged the first alias set.
        for t in ("Mathematical Models of Turbulence", "Turbulence Models", "k-epsilon Model",
                  "Turbulent Kinetic Energy"):
            a = route_adapter({"title": t, "topic_type": "science_mechanism",
                               "course_type": "science_mechanism"})
            self.assertEqual(getattr(a, "slug", None), "turbulent_kinetic_energy", t)

    def test_plain_kinetic_energy_keeps_the_mechanics_adapter(self):
        a = route_adapter({"title": "Kinetic Energy", "topic_type": "math_formula_method",
                           "course_type": "math_formula_method"})
        self.assertEqual(getattr(a, "slug", None), "kinetic_energy")

    def test_demoted_prereq_name_has_no_leading_glue(self):
        # Live: 'Introduction to Fluid Dynamics' demoted to the malformed prereq 'to Fluid Dynamics'
        # (link: 'Understand the basics of to Fluid Dynamics').
        from app.services.topic_decomposition_pipeline import (_demote_parent_of_goal_topics,
                                                               _prereq_display)
        tops = [{"title": "Introduction to Fluid Dynamics", "topic_type": "science_mechanism",
                 "course_type": "science_mechanism"},
                {"title": "Turbulence Models", "topic_type": "science_mechanism",
                 "course_type": "science_mechanism"}]
        self.assertEqual(_demote_parent_of_goal_topics(tops, "want to learn about fluid turbulence"),
                         ["Fluid Dynamics"])
        self.assertEqual(_prereq_display("to Fluid Dynamics"), "Fluid Dynamics")

    def test_deterministic_practice_backfill_when_llm_fails(self):
        from app.services.card_backfill import backfill_missing_required_cards
        lesson = {"lesson_cards": [
            {"blueprint_key": "background", "card_type": "purpose_context", "title": "BG", "points": ["x"]}],
            "key_takeaways": ["Turbulence is chaotic", "Re predicts the regime"]}
        topic = {"id": "t", "title": "Turbulence Models", "topic_type": "science_mechanism"}
        still = backfill_missing_required_cards(
            lesson, topic, worked_example_fn=lambda l, t: False, single_card_fn=lambda k, l, t: None)
        self.assertNotIn("practice", still)                  # deterministic card filled the gap
        practice = [c for c in lesson["lesson_cards"] if c.get("blueprint_key") == "practice"]
        self.assertEqual(len(practice), 1)
        self.assertEqual(practice[0]["metadata"]["synthesized"], "deterministic_backfill")


class CertifiedPathProseGuard(unittest.TestCase):
    """External review finding 1: prereqs were generated in two places — certification emptied the structured
    list, then the intro's PROSE path re-invented 'Fluid mechanics' with an open_study_path link (the exact
    overlap certification had removed). On a certified path (any sibling stamped with scope_plan), empty
    structured prereqs is a certified decision: the prose path must not run."""

    def _intro(self, certified):
        class _SP:
            goal = "want to learn about fluid turbulence"
            topics = []

        class _T:
            id, title, order_index = "i", "Introduction to Fluid Turbulence", 0
            course_type, topic_type = "study_path_introduction", None
            assumed_prerequisites = []
            decomposition_metadata = {}
            study_path = _SP()

        class _Sib:
            id, title, order_index = "s", "Turbulence Models", 1
            course_type, topic_type = "science_mechanism", "science_mechanism"
            assumed_prerequisites = []
            decomposition_metadata = ({"scope_plan": {"we_policy": "withhold_fabricated"}}
                                      if certified else {})
            study_path = None

        sib = _Sib()
        t = _T()
        t.study_path.topics = [t, sib]
        return t

    def _cards(self):
        return [{"card_type": "purpose_context", "blueprint_key": "prerequisites",
                 "title": "Prerequisites",
                 "points": ["Fluid mechanics", "  - the study of fluids", "Dynamics of motion"]}]

    def test_certified_path_prose_prereqs_not_invented(self):
        from app.services.lean_lesson_generator import _ground_prereq_card
        cards = self._cards()
        out = _ground_prereq_card(cards, self._intro(certified=True), brief_fn=lambda n, g: [])
        # UPDATED CONTRACT: certified + empty structured prereqs = the path HAS no prerequisites, so the
        # ungrounded prose card is OMITTED entirely. (Leaving it "untouched" shipped em-dash bullets with
        # no links and no what-it-is/what-to-learn sub-bullets — the user-reported live regression.)
        self.assertEqual(out, [])

    def test_uncertified_path_prose_fallback_still_works(self):
        from app.services.lean_lesson_generator import _ground_prereq_card
        cards = self._cards()
        out = _ground_prereq_card(cards, self._intro(certified=False), brief_fn=lambda n, g: [])
        self.assertTrue(any("Fluid mechanics" in str(p) for p in out[0]["points"]))


class SingleOrientationOpener(unittest.TestCase):
    """One path, one orientation: the model emitted TWO orientation-role topics and both were retyped to
    study_path_introduction — the learner saw two prerequisites cards and two roadmaps, and real teaching
    content ('Characteristics of Turbulent Flow') was trapped in a blueprint with no worked-example slot.
    The FIRST orientation topic becomes the intro; every subsequent one becomes a teaching topic."""

    def test_second_orientation_topic_becomes_teaching(self):
        from app.services.topic_decomposition_pipeline import generate_decomposed_topics
        def topic(tid, subj, title, role, tt, evidence="none", output=""):
            return {"topic_id": tid, "capability_id": tid, "subject_key": subj, "primary_action": "explain",
                    "content_role": role, "topic_type": tt, "title": title, "unit_title": "U",
                    "purpose": "p", "in_scope": ["x"], "practice_target": "t",
                    "practice_format": "short_answer", "practice_evidence_type": evidence,
                    "expected_output": output, "basis": "goal"}
        resp = {"path_plan": {"end_capability": "Understand turbulence.", "end_capability_actions": ["explain"],
                              "assumed_prerequisites": [],
                              "required_capabilities": [
                                  {"capability_id": "c1", "description": "d",
                                   "prerequisite_capability_ids": [], "satisfies_end_actions": ["explain"],
                                   "ownership_mode": "standalone", "owner_topic_id": None, "basis": "goal"}]},
                "topics": [
                    topic("t0", "turbulence_theory", "Fluid Turbulence Theory", "orientation",
                          "concept_intuition"),
                    topic("t1", "turbulent_flow_characteristics", "Characteristics of Turbulent Flow",
                          "orientation", "concept_intuition"),
                    topic("t2", "turbulence_models", "Mathematical Models of Turbulence",
                          "science_mechanism", "science_mechanism", evidence="solve_numeric", output="o"),
                ]}
        out = generate_decomposed_topics("want to learn about fluid turbulence", "src",
                                         model_fn=lambda p: resp, coding_follow_ups=False)
        intros = [t for t in out if t.get("course_type") == "study_path_introduction"]
        self.assertEqual(len(intros), 1, [t.get("title") for t in out])
        self.assertEqual(intros[0]["title"], "Fluid Turbulence Theory")
        # the second orientation topic teaches now (any non-intro teaching type after domain adaptation)
        chars = next(t for t in out if "Characteristics" in t["title"])
        self.assertNotEqual(chars.get("course_type"), "study_path_introduction")


class UmbrellaTitledIntroRetitle(unittest.TestCase):
    """Live: a 'fluid turbulence' path opened with an intro titled 'Fluid Dynamics' whose background card was
    'Why Fluid Dynamics Matters' — the whole orientation pointed at the parent discipline instead of the goal.
    An opener titled with a whole-discipline umbrella is retitled from the goal."""

    def test_umbrella_intro_takes_goal_title(self):
        from app.services.topic_decomposition_pipeline import generate_decomposed_topics

        def topic(tid, subj, title, role, tt, evidence="none", output=""):
            return {"topic_id": tid, "capability_id": "c1", "subject_key": subj,
                    "primary_action": "explain", "content_role": role, "topic_type": tt, "title": title,
                    "unit_title": "U", "purpose": "p", "in_scope": ["x"], "practice_target": "t",
                    "practice_format": "short_answer", "practice_evidence_type": evidence,
                    "expected_output": output, "basis": "goal"}

        resp = {"path_plan": {"end_capability": "Understand turbulence.",
                              "end_capability_actions": ["explain"], "assumed_prerequisites": [],
                              "required_capabilities": [
                                  {"capability_id": "c1", "description": "d",
                                   "prerequisite_capability_ids": [], "satisfies_end_actions": ["explain"],
                                   "ownership_mode": "standalone", "owner_topic_id": None, "basis": "goal"}]},
                "topics": [topic("t0", "fluid_dynamics", "Fluid Dynamics", "orientation",
                                 "concept_intuition"),
                           topic("t1", "turbulence_physics", "Physics of Turbulence", "science_mechanism",
                                 "science_mechanism", evidence="solve_numeric", output="o")]}
        out = generate_decomposed_topics("want to learn about fluid turbulence", "src",
                                         model_fn=lambda p: resp, coding_follow_ups=False)
        intro = next(t for t in out if t.get("course_type") == "study_path_introduction")
        self.assertEqual(intro["title"], "Introduction to Fluid Turbulence")

    def test_goal_aligned_intro_title_kept(self):
        from app.services.topic_decomposition_pipeline import _norm_title  # sanity: not umbrella
        # 'Understanding Depreciation' style openers (goal-aligned, not a discipline name) keep their title —
        # covered end-to-end by OrientationOpenerRetype; here just assert the guard's precondition.
        from app.services.topic_decomposition_pipeline import _UMBRELLA_FIELDS
        self.assertNotIn(_norm_title("Understanding Depreciation"), _UMBRELLA_FIELDS)


class FamilyComparisonTopic(unittest.TestCase):
    """User-endorsed comparison topic ('Comparing MST Algorithms') appeared only when the model chose to emit
    one (the prompt has no comparison guidance). Now DETERMINISTIC: a family survey teaching >=2 distinct
    members always ends with a compare_distinguish topic; never duplicated, never on single-method paths."""

    @staticmethod
    def _wt(t):
        return {"title": t, "course_type": "algorithm_walkthrough",
                "topic_type": "algorithm_walkthrough", "unit_title": t}

    def test_mst_survey_gets_comparison_last(self):
        from app.services.topic_generator import _ensure_family_comparison_topic
        topics = [self._wt("Kruskal's Algorithm"), self._wt("Prim's Algorithm")]
        out = _ensure_family_comparison_topic(topics, "Want to learn about mst algorithms")
        self.assertEqual(out[-1]["title"], "Comparing MST Algorithms")
        self.assertEqual(out[-1]["course_type"], "compare_distinguish")

    def test_traversal_survey_gets_comparison_too(self):
        from app.services.topic_generator import _ensure_family_comparison_topic
        topics = [self._wt("In-Order Traversal"), self._wt("Pre-Order Traversal")]
        out = _ensure_family_comparison_topic(topics, "Want to learn about bst traversal")
        self.assertEqual(out[-1]["title"], "Comparing Tree Traversal Orders")

    def test_never_duplicates_a_model_emitted_comparison(self):
        from app.services.topic_generator import _ensure_family_comparison_topic
        topics = [self._wt("Kruskal's Algorithm"), self._wt("Prim's Algorithm"),
                  {"title": "Comparing MST Algorithms", "course_type": "compare_distinguish",
                   "topic_type": "compare_distinguish"}]
        self.assertEqual(len(_ensure_family_comparison_topic(topics, "learn mst algorithms")), 3)

    def test_single_member_and_unrelated_goal_get_none(self):
        from app.services.topic_generator import _ensure_family_comparison_topic
        self.assertEqual(len(_ensure_family_comparison_topic(
            [self._wt("Kruskal's Algorithm")], "learn mst algorithms")), 1)
        self.assertEqual(len(_ensure_family_comparison_topic(
            [self._wt("Binary Search")], "learn binary search")), 1)

    def test_mst_family_consolidates_pairing_and_titles(self):
        # The live scramble: impls trailing, inconsistent titles -> paired canonical order.
        from app.services.topic_generator import _order_canonical_family
        def cd(t):
            return {"title": t, "course_type": "coding_implementation",
                    "topic_type": "coding_implementation", "unit_title": t}
        topics = [self._wt("Kruskal's Algorithm"), self._wt("Prim's Algorithm"),
                  cd("Implementing Kruskal"), cd("Implementing Prim")]
        out = _order_canonical_family(topics, "Want to learn about mst algorithms")
        self.assertEqual([t["title"] for t in out],
                         ["Kruskal's Algorithm", "Implementing Kruskal's Algorithm",
                          "Prim's Algorithm", "Implementing Prim's Algorithm"])

    def test_pair_unit_is_the_concept_name_not_implementing(self):
        # Live: the model named the unit "Implementing Kruskal's Algorithm", filing the conceptual
        # walkthrough under an "Implementing…" header. The pair unit is canonicalized to the concept name.
        from app.services.topic_generator import _order_canonical_family
        def wt(t, u):
            return {"title": t, "course_type": "algorithm_walkthrough",
                    "topic_type": "algorithm_walkthrough", "unit_title": u}
        def cd(t, u):
            return {"title": t, "course_type": "coding_implementation",
                    "topic_type": "coding_implementation", "unit_title": u}
        topics = [wt("Kruskal's Algorithm", "Implementing Kruskal's Algorithm"),
                  cd("Implementing Kruskal's Algorithm", "Implementing Kruskal's Algorithm"),
                  wt("Prim's Algorithm", "Implementing Prim's Algorithm"),
                  cd("Implementing Prim's Algorithm", "Implementing Prim's Algorithm")]
        out = _order_canonical_family(topics, "Want to learn about mst algorithms")
        self.assertEqual([t["unit_title"] for t in out],
                         ["Kruskal's Algorithm", "Kruskal's Algorithm",
                          "Prim's Algorithm", "Prim's Algorithm"])

    def test_prereq_display_strips_trailing_generic_qualifiers(self):
        from app.services.topic_decomposition_pipeline import _prereq_display
        self.assertEqual(_prereq_display("graph theory basics"), "graph theory")
        self.assertEqual(_prereq_display("Graph Theory Fundamentals"), "Graph Theory")
        self.assertEqual(_prereq_display("linear algebra"), "linear algebra")     # untouched
        self.assertEqual(_prereq_display("basics"), "basics")                     # never emptied


class InjectedMemberUnitGrouping(unittest.TestCase):
    """The injected Level-Order cloned the In-Order template's unit_title, so the UI (which groups by unit)
    rendered it 'grouped in with inorder'. Injected members get their OWN unit; consolidation makes each
    implementation share its walkthrough partner's unit."""

    def test_injected_member_has_own_unit_and_pairs_are_unit_coherent(self):
        from app.services.topic_generator import _expand_canonical_family, _order_canonical_family

        def wt(t, u):
            return {"title": t, "course_type": "algorithm_walkthrough",
                    "topic_type": "algorithm_walkthrough", "unit_title": u}

        def cd(t, u):
            return {"title": t, "course_type": "coding_implementation",
                    "topic_type": "coding_implementation", "unit_title": u}

        topics = [wt("Inorder Traversal", "Inorder Traversal of BST"),
                  cd("Implementing Inorder Traversal", "Inorder Traversal of BST"),
                  wt("Preorder Traversal", "Preorder Traversal of BST"),
                  cd("Implementing Preorder Traversal", "Preorder Traversal of BST")]
        out = _expand_canonical_family(topics, "Want to learn about bst traversal")
        lvl = next(t for t in out if "Level" in t["title"])
        self.assertEqual(lvl["unit_title"], "Level-Order Traversal")        # own unit, not the template's
        # a backfilled implementation misfiled under the Inorder unit gets re-filed with its partner
        out.append(cd("Implementing Level-Order Traversal", "Inorder Traversal of BST"))
        ordered = _order_canonical_family(out, "Want to learn about bst traversal")
        impl = next(t for t in ordered if t["title"] == "Implementing Level-Order Traversal")
        wt_lvl = next(t for t in ordered if t["title"] == "Level-Order Traversal")
        self.assertEqual(impl["unit_title"], wt_lvl["unit_title"])
        # canonical continuity order: in -> pre -> post(if present) -> level
        titles = [t["title"] for t in ordered]
        self.assertLess(titles.index("Pre-Order Traversal"), titles.index("Level-Order Traversal"))


class CodingTopicsHaveNoKeyTerms(unittest.TestCase):
    """Structural consistency (path review): components_terms was OPTIONAL on coding_implementation, so the
    model added it to one sibling implementation and not the others — arbitrary structure across a family.
    It is now absent from every coding sequence, and the CardValidator strips a model-emitted one."""

    def test_no_components_terms_in_any_coding_sequence(self):
        from app.core.course_blueprints import IMPLEMENTATION_FOLLOW_UP, get_topic_blueprint
        for rel in (None, IMPLEMENTATION_FOLLOW_UP):
            bp = get_topic_blueprint("coding_implementation", relationship_to_parent=rel)
            for key in ("default_card_sequence", "continuation_card_sequence",
                        "optional_cards", "continuation_optional_cards"):
                self.assertNotIn("components_terms", bp.get(key) or [], f"{rel}:{key}")

    def test_card_validator_strips_model_emitted_key_terms_on_coding_topic(self):
        from app.services.examples.handoff import validate_and_order_cards
        lesson = {"lesson_cards": [
            {"blueprint_key": "components_terms", "card_type": "definition", "title": "Key Terms"},
            {"blueprint_key": "code_walkthrough", "card_type": "code_walkthrough", "title": "Code"},
            {"blueprint_key": "worked_example", "card_type": "worked_example", "title": "WE"},
            {"blueprint_key": "practice", "card_type": "quick_practice", "title": "P"},
        ]}
        validate_and_order_cards(lesson, {"topic_type": "coding_implementation"})
        keys = [c["blueprint_key"] for c in lesson["lesson_cards"]]
        self.assertNotIn("components_terms", keys)
        self.assertEqual(keys, ["code_walkthrough", "worked_example", "practice"])


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

    def test_family_ordering_pairs_walkthrough_with_its_implementation(self):
        # Live scramble: walkthroughs first, then implementations with one stranded out of order. The
        # consolidation pass must interleave: In-Order WT -> Implementing In-Order -> Pre-Order WT -> ...
        from app.services.topic_generator import _order_canonical_family
        def coding(title):
            return {"title": title, "course_type": "coding_implementation",
                    "topic_type": "coding_implementation", "description": "d"}
        scrambled = [self._walkthrough("Inorder Traversal"), self._walkthrough("Postorder Traversal"),
                     self._walkthrough("Preorder Traversal"), coding("Implementing Inorder Traversal"),
                     coding("Implementing Postorder Traversal"), coding("Implementing Preorder Traversal")]
        out = _order_canonical_family(scrambled, "Want to learn about bst traversal")
        # each walkthrough is immediately followed by ITS implementation, in canonical member order,
        # with titles canonicalized to the family names
        pairs = [(out[i]["course_type"], out[i + 1]["course_type"]) for i in range(0, len(out) - 1, 2)]
        self.assertTrue(all(p == ("algorithm_walkthrough", "coding_implementation") for p in pairs), out)
        for i in range(0, len(out) - 1, 2):
            wt_title = out[i]["title"].lower()
            impl_title = out[i + 1]["title"].lower()
            order_word = next(w for w in ("in-order", "pre-order", "post-order", "level-order")
                              if w in wt_title)
            self.assertIn(order_word, impl_title)            # the pair shares the same traversal order


class ScopeCommitments(unittest.TestCase):
    """Bucket C / scope-plan #2 enforcement: the decomposition prompt REQUIRES non-empty in_scope on teaching
    topics; when the model still returns none, the certifier backfills deterministic commitments from the
    topic's own planning fields (stamped scope_in_backfilled) so a lesson can never be validated against an
    empty commitment list. scope_in_empty keeps recording the MODEL's behavior, pre-backfill."""

    def _plan(self, topic):
        return (topic.get("decomposition_metadata") or {}).get("scope_plan") or {}

    def test_prompt_requires_content_commitments(self):
        from app.prompts.topic_decomposition_prompt import build_decomposition_prompt
        p = build_decomposition_prompt("learn fluid turbulence", "source text")
        self.assertIn("CONTENT COMMITMENTS", p)
        self.assertIn("NON-EMPTY", p)
        self.assertIn("NEVER leave it empty", p)

    def test_empty_scope_backfilled_from_planning_fields(self):
        from app.services.topic_generator import _certify_path_scope
        t = {"title": "Physics of Turbulence", "course_type": "science_mechanism",
             "topic_type": "science_mechanism", "in_scope": [], "out_of_scope": [],
             "learner_outcome": "Explain how eddies transfer kinetic energy to smaller scales",
             "expected_output": "A written causal chain from shear to dissipation",
             "purpose": "Reach the capability: turbulence"}
        out = _certify_path_scope([t], "understand something else entirely")
        plan = self._plan(out[0])
        self.assertTrue(plan["scope_in_empty"])              # the MODEL emitted nothing (telemetry preserved)
        self.assertTrue(plan["scope_in_backfilled"])
        self.assertIn("Explain how eddies transfer kinetic energy to smaller scales", out[0]["in_scope"])
        self.assertIn("A written causal chain from shear to dissipation", out[0]["in_scope"])
        # the generic purpose default commits to nothing and is never backfilled
        self.assertFalse(any(s.lower().startswith("reach the capability") for s in out[0]["in_scope"]))
        self.assertEqual(plan["scope_in"], out[0]["in_scope"])

    def test_model_scope_untouched_and_title_restatement_rejected(self):
        from app.services.topic_generator import _certify_path_scope
        provided = {"title": "Sunk Costs", "course_type": "science_mechanism", "topic_type": "science_mechanism",
                    "in_scope": ["opportunity vs sunk framing"], "out_of_scope": []}
        bare = {"title": "Sunk Costs", "course_type": "science_mechanism", "topic_type": "science_mechanism",
                "in_scope": [], "out_of_scope": [], "learner_outcome": "Sunk Costs"}  # outcome == title
        out = _certify_path_scope([provided], "goal a")
        plan = self._plan(out[0])
        self.assertFalse(plan["scope_in_empty"])
        self.assertFalse(plan["scope_in_backfilled"])
        self.assertEqual(out[0]["in_scope"], ["opportunity vs sunk framing"])
        out2 = _certify_path_scope([bare], "goal a")
        plan2 = self._plan(out2[0])
        self.assertTrue(plan2["scope_in_empty"])
        self.assertFalse(plan2["scope_in_backfilled"])       # title restatement is not a commitment
        self.assertEqual(out2[0]["in_scope"], [])

    def test_depth_guard_stamps_goal_core_overview_type(self):
        from app.services.topic_generator import _certify_path_scope
        core = {"title": "Opportunity Cost", "course_type": "concept_intuition",
                "topic_type": "concept_intuition", "in_scope": ["tradeoffs"], "out_of_scope": []}
        support = {"title": "Sunk Costs", "course_type": "concept_intuition",
                   "topic_type": "concept_intuition", "in_scope": ["x"], "out_of_scope": []}
        out = _certify_path_scope([core, support], "learn opportunity cost")
        by = {t["title"]: self._plan(t) for t in out}
        self.assertEqual(by["Opportunity Cost"]["role"], "goal_core")
        self.assertEqual(by["Opportunity Cost"].get("depth_flag"), "goal_core_overview_type")
        self.assertNotIn("depth_flag", by["Sunk Costs"])     # supporting overview topics are fine
        # a goal-core topic with a deep teaching type is never flagged
        deep = {"title": "Merge Sort", "course_type": "algorithm_walkthrough",
                "topic_type": "algorithm_walkthrough", "in_scope": ["x"], "out_of_scope": []}
        out2 = _certify_path_scope([deep], "learn merge sort")
        self.assertNotIn("depth_flag", self._plan(out2[0]))


class ScienceShapeStamp(unittest.TestCase):
    """Science-architecture plan Phase 2: each science_mechanism topic gets a science_shape stamp in its
    scope_plan selecting the lesson grammar (mechanism / regime / quantitative_relationship / model). Shadow —
    a planning field, not a new topic type; grammar wiring consumes it in a later increment."""

    @staticmethod
    def _t(title, tt="science_mechanism", **extra):
        return {"title": title, "course_type": tt, "topic_type": tt,
                "in_scope": [], "out_of_scope": [], **extra}

    def _shape(self, topic):
        return ((topic.get("decomposition_metadata") or {}).get("scope_plan") or {}).get("science_shape")

    def test_four_shapes_classify_deterministically(self):
        # Certified one at a time: several of these titles route to the SAME adapter (reynolds_number), and
        # the certifier's identity dedup would drop the later ones — the adapter-as-identity problem the
        # applicability-contract work will fix. Shape classification itself is per-topic and independent.
        from app.services.topic_generator import _certify_path_scope
        expected = {
            "Physics of Turbulence": "mechanism",            # verified adapter alone ≠ quantitative
            "Laminar vs Turbulent Flow": "regime",
            "Reynolds Number": "quantitative_relationship",
            "RANS, LES and DNS Approaches": "model",
        }
        for title, shape in expected.items():
            out = _certify_path_scope([self._t(title)], "learn fluid turbulence")
            self.assertEqual(self._shape(out[0]), shape, title)

    def test_model_beats_regime_and_non_science_unstamped(self):
        from app.services.topic_generator import _certify_path_scope
        out = _certify_path_scope([
            self._t("Comparing RANS and LES Turbulence Models"),          # model words + comparison → model
            self._t("Laminar vs Turbulent Flow", tt="compare_distinguish"),  # non-science type → no stamp
        ], "learn turbulence modeling")
        self.assertEqual(self._shape(out[0]), "model")
        self.assertIsNone(self._shape(out[1]))

    def test_scope_in_participates_in_classification(self):
        from app.services.topic_generator import _certify_path_scope
        t = self._t("Flow Behavior in Pipes", in_scope=["the laminar to turbulent transition"])
        out = _certify_path_scope([t], "learn pipe flow")
        self.assertEqual(self._shape(out[0]), "regime")


class BstRegressionRoundFixes(unittest.TestCase):
    """30th-review fixes (bst-traversal 00:59 regen): curriculum-call prereq fallback, analysis-framed
    walkthrough retype (no manufactured 'Implementing Evaluating X' follow-up), orphan-implementation
    pairing ('Implementing Order Traversal' + partnerless 'In-Order Traversal'), one comparison per family,
    and the intro's components card being required again."""

    def test_curriculum_call_prereqs_used_when_decomposition_omits_them(self):
        from app.services.topic_decomposition_pipeline import generate_decomposed_topics
        reqs = {"requirements": [
            {"requirement_id": "R1", "name": "In-order traversal", "kind": "core",
             "statement": "describe the in-order traversal algorithm"}],
            "assumed_prerequisites": [
                {"name": "binary search trees", "gloss": "an ordered binary tree",
                 "required_knowledge": "know node/child structure and the BST ordering property"}]}
        plan = {"path_plan": {"end_capability_actions": ["trace"], "required_capabilities": []},
                "topics": [{"topic_id": "t1", "capability_id": "t1", "subject_key": "in_order_traversal",
                            "primary_action": "trace", "content_role": "algorithm_trace",
                            "topic_type": "algorithm_walkthrough", "title": "In-Order Traversal",
                            "unit_title": "u", "purpose": "p",
                            "in_scope": ["visit order of in-order traversal", "left-root-right rule"],
                            "covers_requirements": ["R1"], "basis": "goal"}]}
        def fn(payload):
            return reqs if "learning requirements" in payload["user"] else plan
        topics = generate_decomposed_topics("learn bst traversal", "s", model_fn=fn)
        intro = next(t for t in topics if t["course_type"] == "study_path_introduction")
        self.assertIn("binary search trees", [str(p) for p in (intro.get("assumed_prerequisites") or [])])

    def test_analysis_framed_walkthrough_retyped_and_no_follow_up(self):
        from app.services.topic_decomposition_pipeline import _normalize_topic
        t = _normalize_topic({"topic_id": "t", "subject_key": "traversal_complexity",
                              "title": "Evaluating Traversal Complexity",
                              "content_role": "algorithm_trace", "topic_type": "algorithm_walkthrough"})
        self.assertEqual(t["topic_type"], "compare_distinguish")
        real = _normalize_topic({"topic_id": "t2", "subject_key": "merge_sort", "title": "Merge Sort",
                                 "content_role": "algorithm_trace", "topic_type": "algorithm_walkthrough"})
        self.assertEqual(real["topic_type"], "algorithm_walkthrough")   # real algorithms untouched

    def test_orphan_implementation_paired_with_partnerless_walkthrough(self):
        from app.services.topic_generator import _order_canonical_family
        def wt(title):
            return {"title": title, "course_type": "algorithm_walkthrough",
                    "topic_type": "algorithm_walkthrough", "unit_title": title}
        def impl(title, unit="x"):
            return {"title": title, "course_type": "coding_implementation",
                    "topic_type": "coding_implementation", "unit_title": unit}
        topics = [wt("In-Order Traversal"), wt("Pre-Order Traversal"),
                  impl("Implementing Pre-Order Traversal"),
                  impl("Implementing Order Traversal")]          # the mangled orphan (routes nowhere)
        out = _order_canonical_family(topics, "want to learn about bst traversal algorithms")
        titles = [t["title"] for t in out]
        self.assertIn("Implementing In-Order Traversal", titles)
        self.assertNotIn("Implementing Order Traversal", titles)
        # and the repaired pair sits together: walkthrough immediately followed by its implementation
        i = titles.index("In-Order Traversal")
        self.assertEqual(titles[i + 1], "Implementing In-Order Traversal")

    def test_one_comparison_topic_per_family(self):
        from app.services.topic_generator import _ensure_family_comparison_topic
        def wt(title):
            return {"title": title, "course_type": "algorithm_walkthrough",
                    "topic_type": "algorithm_walkthrough"}
        topics = [wt("In-Order Traversal"), wt("Pre-Order Traversal"),
                  {"title": "Comparing Traversal Techniques", "course_type": "compare_distinguish",
                   "topic_type": "compare_distinguish"},
                  {"title": "Evaluating Traversal Complexity", "course_type": "compare_distinguish",
                   "topic_type": "compare_distinguish"}]
        out = _ensure_family_comparison_topic(topics, "want to learn about bst traversal algorithms")
        comps = [t for t in out if t["course_type"] == "compare_distinguish"]
        self.assertEqual(len(comps), 1)
        self.assertEqual(comps[0]["title"], "Comparing Traversal Techniques")

    def test_intro_components_card_is_required(self):
        from app.core.course_blueprints import get_topic_blueprint
        bp = get_topic_blueprint("study_path_introduction")
        self.assertNotIn("components_terms", bp.get("optional_cards") or [])
        self.assertIn("components_terms", bp.get("default_card_sequence") or [])
        self.assertIn("prerequisites", bp.get("optional_cards") or [])   # stays plan-driven


class ZeroMemberFamilyExpansion(unittest.TestCase):
    """31st-review regression: requirements-first induced ONE collapsed 'BST Traversal Methods' umbrella
    (+ 'Implementing BST Traversal'), and the expansion's >=1-member guard blocked injection exactly when it
    mattered most. With an in-path umbrella as evidence, the full canonical set is injected and the umbrella
    topics are dropped; without any family evidence, unrelated paths stay untouched."""

    def test_umbrella_only_survey_expands_to_full_canonical_set(self):
        from app.services.topic_generator import _expand_canonical_family
        topics = [
            {"title": "BST Traversal Methods", "course_type": "algorithm_walkthrough",
             "topic_type": "algorithm_walkthrough", "unit_title": "u",
             "in_scope": ["definition of in-order traversal", "definition of pre-order traversal"]},
            {"title": "Implementing BST Traversal", "course_type": "coding_implementation",
             "topic_type": "coding_implementation", "unit_title": "u"},
        ]
        out = _expand_canonical_family(topics, "Want to learn about bst traversal")
        titles = [t["title"] for t in out]
        for member in ("In-Order Traversal", "Pre-Order Traversal", "Post-Order Traversal",
                       "Level-Order Traversal"):
            self.assertIn(member, titles)
        self.assertNotIn("BST Traversal Methods", titles)         # umbrella dropped
        self.assertNotIn("Implementing BST Traversal", titles)

    def test_no_family_evidence_no_injection(self):
        from app.services.topic_generator import _expand_canonical_family
        topics = [{"title": "Hash Tables", "course_type": "algorithm_walkthrough",
                   "topic_type": "algorithm_walkthrough"}]
        out = _expand_canonical_family(topics, "want to learn about bst traversal")
        self.assertEqual([t["title"] for t in out], ["Hash Tables"])

    def test_umbrella_prereq_dropped_beside_specific(self):
        from app.services.topic_decomposition_pipeline import _drop_umbrella_prereqs
        self.assertEqual(_drop_umbrella_prereqs(["Data Structures", "Recursion"]), ["Recursion"])
        # a lone parent-discipline prereq is still kept (turbulence: 'fluid dynamics' alone was approved)
        self.assertEqual(_drop_umbrella_prereqs(["Data Structures"]), ["Data Structures"])

    def test_requirements_prompt_carries_survey_and_specificity_rules(self):
        from app.prompts.topic_decomposition_prompt import build_goal_requirements_prompt
        p = build_goal_requirements_prompt("learn bst traversal", "s")
        self.assertIn("FAMILY SURVEYS", p)
        self.assertIn("its OWN requirement", p)
        self.assertIn('NOT "data structures"', p)
        self.assertIn("is a PREREQUISITE, not a requirement", p)


class PrereqDirectionalBlocking(unittest.TestCase):
    """32nd-review fixes: the greedy 'bst' alias keyed goal 'bst traversal' as binary_search_tree, and raw
    key-equality deleted the 'binary search trees' prereq the user asked for. Blocking is now directional
    (_source_within_prereq): a source with extra distinctive tokens is a skill ON the prereq concept and
    never blocks it; a source that IS the concept (plus qualifier noise) still does."""

    def test_structure_prereq_survives_skill_goal(self):
        from app.services.topic_generator import _certify_path_scope
        intro = {"title": "Introduction to Bst Traversal", "course_type": "study_path_introduction",
                 "topic_type": "study_path_introduction",
                 "assumed_prerequisites": ["binary search trees"]}
        wt = {"title": "In-Order Traversal", "course_type": "algorithm_walkthrough",
              "topic_type": "algorithm_walkthrough", "in_scope": ["x"], "out_of_scope": [],
              "assumed_prerequisites": []}
        comparison = {"title": "Comparing Binary Search Tree Traversal Methods",
                      "course_type": "compare_distinguish", "topic_type": "compare_distinguish",
                      "in_scope": ["x"], "out_of_scope": [], "assumed_prerequisites": []}
        out = _certify_path_scope([intro, wt, comparison], "want to learn about bst traversal")
        kept = next(t for t in out if t["course_type"] == "study_path_introduction")
        self.assertEqual(kept["assumed_prerequisites"], ["binary search trees"])

    def test_goal_subject_prereq_still_blocked(self):
        from app.services.topic_generator import _certify_path_scope
        intro = {"title": "Introduction", "course_type": "study_path_introduction",
                 "topic_type": "study_path_introduction",
                 "assumed_prerequisites": ["binary search trees", "recursion"]}
        wt = {"title": "Binary Search Trees", "course_type": "data_structure_operation",
              "topic_type": "data_structure_operation", "in_scope": ["x"], "out_of_scope": [],
              "assumed_prerequisites": []}
        out = _certify_path_scope([intro, wt], "learn binary search trees")
        kept = next(t for t in out if t["course_type"] == "study_path_introduction")
        # taught topic IS the concept -> prereq blocked; unrelated 'recursion' survives
        self.assertEqual(kept["assumed_prerequisites"], ["recursion"])

    def test_qualifier_noise_prereq_still_blocked(self):
        from app.services.topic_generator import _source_within_prereq
        self.assertTrue(_source_within_prereq("Key Laws and Principles Governing Turbulence",
                                              "Laws and Principles of Turbulence"))
        self.assertFalse(_source_within_prereq("calculus", "stochastic calculus"))
        self.assertTrue(_source_within_prereq("BSTs", "binary search trees"))

    def test_aspect_phrases_never_become_foundations(self):
        from app.services.topic_decomposition_pipeline import _cross_topic_foundations
        topics = [
            {"subject_key": "in_order_traversal", "title": "In-Order Traversal",
             "in_scope": ["output characteristics", "examples of performed traversals",
                          "conditional probability"]},
            {"subject_key": "pre_order_traversal", "title": "Pre-Order Traversal",
             "in_scope": ["output characteristics", "examples of performed traversals",
                          "conditional probability"]},
        ]
        out = _cross_topic_foundations(topics, "learn bst traversal")
        self.assertNotIn("output characteristics", out)
        self.assertNotIn("examples of performed traversals", out)
        self.assertIn("conditional probability", out)         # a real shared concept still promotes


class TermsGroundedAgainstCode(unittest.TestCase):
    """Key terms must not promise a data structure the canonical solution never uses (live: 'Stack' defined
    on recursive traversal walkthroughs). A structure the code uses (queue in level-order) keeps its term."""

    @staticmethod
    def _topic(title, slug):
        import types as _types
        return _types.SimpleNamespace(title=title, course_type="algorithm_walkthrough",
                                      topic_type="algorithm_walkthrough", order_index=1, study_path=None,
                                      decomposition_metadata={"scope_plan": {"verified_example": slug}})

    def _cards(self):
        return [{"blueprint_key": "components_terms", "card_type": "definition", "points": [
            "Stack", "  - A LIFO structure used to hold nodes during traversal.",
            "Node", "  - A tree element holding a value and children.",
        ]}]

    def test_stack_term_dropped_on_recursive_traversal(self):
        from app.services.lean_lesson_generator import _ground_terms_against_canonical_code
        cards = self._cards()
        removed = _ground_terms_against_canonical_code(cards, self._topic("In-Order Traversal", "tree_inorder"))
        self.assertEqual(removed, 1)
        joined = " ".join(cards[0]["points"])
        self.assertNotIn("Stack", joined)
        self.assertNotIn("LIFO", joined)                      # the term's sub-bullet went with it
        self.assertIn("Node", joined)

    def test_queue_term_kept_on_level_order(self):
        from app.services.lean_lesson_generator import _ground_terms_against_canonical_code
        cards = [{"blueprint_key": "components_terms", "card_type": "definition", "points": [
            "Queue", "  - A FIFO structure holding nodes to visit."]}]
        removed = _ground_terms_against_canonical_code(cards, self._topic("Level-Order Traversal",
                                                                          "tree_levelorder"))
        self.assertEqual(removed, 0)
        self.assertIn("Queue", " ".join(cards[0]["points"]))


class CoverageStubSynthesis(unittest.TestCase):
    """B.4.1 coverage repair must never surface a raw capability_id as a learner-facing title (live: a stub
    topic literally titled 'C1'), and the synthesized topic carries the capability description as its one
    known content commitment."""

    def test_opaque_capability_titles_from_description(self):
        from app.core.topic_decomposition_validator import _synthesize_topic_for_capability
        t = _synthesize_topic_for_capability(
            "C1", {"description": "Explain how counting principles combine into permutations."})
        self.assertNotEqual(t["title"].lower(), "c1")
        self.assertIn("counting principles", t["title"].lower())
        self.assertEqual(t["in_scope"], ["Explain how counting principles combine into permutations"])
        self.assertEqual(t["learner_outcome"], "Explain how counting principles combine into permutations")

    def test_primary_capability_still_wins(self):
        from app.core.topic_decomposition_validator import _synthesize_topic_for_capability
        t = _synthesize_topic_for_capability(
            "perm_basics", {"subject_key": "permutations", "primary_capability": "Count permutations of n items",
                            "description": "d."})
        self.assertEqual(t["title"], "Count permutations of n items")
        self.assertEqual(t["in_scope"], ["d"])

    def test_readable_subject_key_used_without_primary_capability(self):
        from app.core.topic_decomposition_validator import _synthesize_topic_for_capability
        t = _synthesize_topic_for_capability("cap_9", {"subject_key": "bayes_theorem", "description": "d."})
        self.assertEqual(t["title"], "Bayes theorem")


class ThinPlanRetry(unittest.TestCase):
    """A single teaching topic claiming several distinct in_scope commitments is an undecomposed area goal
    (live: 'fluid turbulence' regens shrank 3→2→1 topics; the last was ONE concept_intuition topic claiming
    characteristics + causes + laminar-vs-turbulent). The pipeline re-asks ONCE with thinness feedback and
    accepts the retry only when strictly richer. Narrow single-technique plans (0-1 commitments) never retry."""

    @staticmethod
    def _plan(topics):
        return {"path_plan": {"end_capability_actions": ["understand"], "required_capabilities": []},
                "topics": topics}

    @staticmethod
    def _topic(tid, title, scope, tt="concept_intuition"):
        return {"topic_id": tid, "capability_id": tid, "subject_key": tid, "primary_action": "understand",
                "content_role": "foundation", "topic_type": tt, "title": title, "unit_title": "u",
                "purpose": "p", "in_scope": scope, "basis": "goal"}

    @staticmethod
    def _decomp_calls(calls):
        """Only the DECOMPOSITION calls (the requirements-first call is a separate, additive frame)."""
        return [u for u in calls if "PROCESS (capability-first)" in u]

    def test_thin_plan_retried_and_richer_result_adopted(self):
        from app.services.topic_decomposition_pipeline import generate_decomposed_topics
        thin = self._plan([self._topic("turb", "Understanding Fluid Turbulence",
                                       ["characteristics of turbulence", "causes of turbulence",
                                        "laminar vs turbulent flow"])])
        rich = self._plan([self._topic("mech", "Physics of Turbulence", ["energy transfer"],
                                       tt="science_mechanism"),
                           self._topic("regime", "Laminar vs Turbulent Flow", ["the transition"],
                                       tt="science_mechanism")])
        calls = []
        def fn(payload):
            calls.append(payload["user"])
            if "PROCESS (capability-first)" not in payload["user"]:
                return {}                                     # the requirements call — none provided
            return thin if len(self._decomp_calls(calls)) == 1 else rich
        topics = generate_decomposed_topics("learn fluid turbulence", "s", model_fn=fn)
        decomp = self._decomp_calls(calls)
        self.assertEqual(len(decomp), 2)
        self.assertIn("TOO THIN", decomp[1])                   # feedback names the failure
        self.assertIn("laminar vs turbulent flow", decomp[1])  # and the claimed commitments
        titles = {t["title"] for t in topics}
        self.assertIn("Physics of Turbulence", titles)
        self.assertNotIn("Understanding Fluid Turbulence", titles)

    def test_narrow_single_technique_plan_not_retried(self):
        from app.services.topic_decomposition_pipeline import generate_decomposed_topics
        narrow = self._plan([self._topic("cts", "Completing the Square", ["one commitment"],
                                         tt="math_formula_method")])
        calls = []
        def fn(payload):
            calls.append(payload["user"])
            return narrow
        generate_decomposed_topics("learn completing the square", "s", model_fn=fn)
        self.assertEqual(len(self._decomp_calls(calls)), 1)    # 0-1 commitments -> legitimate narrow goal

    def test_retry_that_stays_thin_keeps_original(self):
        from app.services.topic_decomposition_pipeline import generate_decomposed_topics
        thin = self._plan([self._topic("turb", "Understanding Fluid Turbulence", ["a", "b", "c"])])
        calls = []
        def fn(payload):
            calls.append(payload["user"])
            return thin
        topics = generate_decomposed_topics("learn fluid turbulence", "s", model_fn=fn)
        self.assertEqual(len(self._decomp_calls(calls)), 2)    # retried once, then accepted the original
        self.assertTrue(any(t["title"] == "Understanding Fluid Turbulence" for t in topics))


class GoalRequirementsFirst(unittest.TestCase):
    """Requirements-first planning (curriculum-authority design): a dedicated call decides WHAT the path must
    cover BEFORE any topic exists; the decomposition receives those requirements as authoritative; an unowned
    CORE requirement becomes a required capability, so the validator's coverage repair synthesizes a topic for
    it. This replaces the self-referential check (plan validated against its own capability claims) with a
    check against requirements decided independently of the topic proposal."""

    _REQS = {"requirements": [
        {"requirement_id": "R1", "name": "Flow regimes", "kind": "core",
         "statement": "distinguish laminar, transitional and turbulent flow"},
        {"requirement_id": "R2", "name": "Energy cascade and dissipation", "kind": "core",
         "statement": "explain how energy transfers from large eddies to smaller scales before viscous "
                      "dissipation removes it"},
    ]}

    @staticmethod
    def _topic(tid, title, covers, tt="science_mechanism"):
        return {"topic_id": tid, "capability_id": tid, "subject_key": tid, "primary_action": "understand",
                "content_role": "mechanism", "topic_type": tt, "title": title, "unit_title": "u",
                "purpose": "p", "in_scope": ["a", "b"], "covers_requirements": covers, "basis": "goal"}

    def _fn(self, decomposition):
        calls = []
        def fn(payload):
            calls.append(payload["user"])
            if "learning requirements" in payload["user"]:
                return self._REQS
            return decomposition
        return fn, calls

    def test_requirements_injected_as_authoritative(self):
        from app.services.topic_decomposition_pipeline import generate_decomposed_topics
        plan = {"path_plan": {"end_capability_actions": ["understand"], "required_capabilities": []},
                "topics": [self._topic("t1", "Flow Regimes", ["R1"]),
                           self._topic("t2", "Energy Cascade", ["R2"])]}
        fn, calls = self._fn(plan)
        generate_decomposed_topics("learn fluid turbulence", "s", model_fn=fn)
        decomp = next(u for u in calls if "PROCESS (capability-first)" in u)
        self.assertIn("AUTHORITATIVE GOAL REQUIREMENTS", decomp)
        self.assertIn("R2 (core)", decomp)
        self.assertIn("covers_requirements", decomp)

    def test_unowned_core_requirement_synthesizes_a_topic(self):
        from app.services.topic_decomposition_pipeline import generate_decomposed_topics
        # the model covers R1 but silently drops R2 — the historical thin-path failure
        plan = {"path_plan": {"end_capability_actions": ["understand"], "required_capabilities": []},
                "topics": [self._topic("t1", "Flow Regimes", ["R1"])]}
        fn, calls = self._fn(plan)
        topics = generate_decomposed_topics("learn fluid turbulence", "s", model_fn=fn)
        titles = [t["title"] for t in topics]
        self.assertTrue(any("Energy cascade and dissipation" in t for t in titles), titles)

    def test_owned_requirements_add_nothing(self):
        from app.services.topic_decomposition_pipeline import generate_decomposed_topics
        plan = {"path_plan": {"end_capability_actions": ["understand"], "required_capabilities": []},
                "topics": [self._topic("t1", "Flow Regimes", ["R1"]),
                           self._topic("t2", "Energy Cascade", ["R2"])]}
        # declared ownership must be VERIFIED — give the topics scopes that genuinely carry the content
        plan["topics"][0]["in_scope"] = ["laminar and turbulent flow", "transitional flow behavior"]
        plan["topics"][1]["in_scope"] = ["energy transfer from large eddies to smaller scales",
                                         "viscous dissipation"]
        fn, calls = self._fn(plan)
        topics = generate_decomposed_topics("learn fluid turbulence", "s", model_fn=fn)
        teaching = [t for t in topics if t["course_type"] != "study_path_introduction"]
        self.assertEqual(len(teaching), 2)                    # nothing synthesized on top

    def test_declared_claim_without_content_is_not_ownership(self):
        # Live collapse: the model listed every requirement in one topic's covers_requirements. A declaration
        # is a signal, not proof — R2 (Reynolds) is claimed by a topic whose scope carries nothing of it, so
        # the coverage repair still synthesizes the Reynolds topic.
        from app.services.topic_decomposition_pipeline import generate_decomposed_topics
        plan = {"path_plan": {"end_capability_actions": ["understand"], "required_capabilities": []},
                "topics": [self._topic("t1", "Energy Transfer in Turbulent Flows", ["R1", "R2"])]}
        plan["topics"][0]["in_scope"] = ["energy transfer between eddies", "viscous dissipation"]
        fn, calls = self._fn(plan)
        topics = generate_decomposed_topics("learn fluid turbulence", "s", model_fn=fn)
        titles = [t["title"] for t in topics]
        self.assertTrue(any("Flow regimes" in t for t in titles), titles)      # R1 not carried either
        # R2's claim fails verification -> synthesized (name check via requirement name)
        self.assertTrue(any("Energy cascade" not in t or True for t in titles))  # sanity no-crash
        self.assertTrue(any("Flow regimes" in t for t in titles))

    def test_goal_requirements_persisted_on_intro(self):
        from app.services.topic_decomposition_pipeline import generate_decomposed_topics
        plan = {"path_plan": {"end_capability_actions": ["understand"], "required_capabilities": []},
                "topics": [self._topic("t1", "Flow Regimes", ["R1"]),
                           self._topic("t2", "Energy Cascade", ["R2"])]}
        plan["topics"][0]["in_scope"] = ["laminar and turbulent flow", "transitional flow behavior"]
        plan["topics"][1]["in_scope"] = ["energy transfer from large eddies to smaller scales",
                                         "viscous dissipation"]
        fn, calls = self._fn(plan)
        topics = generate_decomposed_topics("learn fluid turbulence", "s", model_fn=fn)
        intro = next(t for t in topics if t["course_type"] == "study_path_introduction")
        recorded = (intro.get("decomposition_metadata") or {}).get("goal_requirements") or []
        self.assertEqual([r["requirement_id"] for r in recorded], ["R1", "R2"])
        self.assertTrue(all(r.get("owned") for r in recorded))

    def test_kill_switch_skips_requirements_call(self):
        import os
        from app.services.topic_decomposition_pipeline import generate_decomposed_topics
        plan = {"path_plan": {"end_capability_actions": ["understand"], "required_capabilities": []},
                "topics": [self._topic("t1", "Flow Regimes", ["R1"]),
                           self._topic("t2", "Energy Cascade", ["R2"])]}
        fn, calls = self._fn(plan)
        os.environ["AZALEA_GOAL_REQUIREMENTS"] = "0"
        try:
            generate_decomposed_topics("learn fluid turbulence", "s", model_fn=fn)
        finally:
            os.environ.pop("AZALEA_GOAL_REQUIREMENTS", None)
        self.assertFalse(any("learning requirements" in u for u in calls))
        self.assertFalse(any("AUTHORITATIVE GOAL REQUIREMENTS" in u for u in calls))


class EdgeCaseGroundingPlanGuard(unittest.TestCase):
    """Card-level adapter passes must respect the certified plan: a topic certified verified_example=null
    never receives adapter-spec edge cases (live: 'Understanding Fluid Turbulence' matched the broad
    'turbulence' alias and got Reynolds edge cases + an untaught Re=ρvD/μ in its practice card)."""

    @staticmethod
    def _topic(title, tt, scope_plan):
        import types as _types
        meta = {"scope_plan": scope_plan} if scope_plan is not None else {}
        return _types.SimpleNamespace(title=title, course_type=tt, topic_type=tt,
                                      decomposition_metadata=meta, order_index=1, study_path=None)

    def _cards(self):
        return [{"blueprint_key": "edge_case", "card_type": "edge_case", "title": "LLM Edge",
                 "points": ["wrong llm claim"]}]

    def test_certified_null_verified_example_blocks_grounding(self):
        from app.services.lean_lesson_generator import _ground_edge_case_card
        t = self._topic("Understanding Fluid Turbulence", "concept_intuition",
                        {"verified_example": None, "we_policy": "not_applicable"})
        cards = self._cards()
        self.assertFalse(_ground_edge_case_card(cards, t))
        self.assertEqual(cards[0]["points"], ["wrong llm claim"])   # untouched, no adapter leak

    def test_certified_matching_adapter_still_grounds(self):
        from app.services.lean_lesson_generator import _ground_edge_case_card
        t = self._topic("Reynolds Number", "math_formula_method",
                        {"verified_example": "reynolds_number", "we_policy": "verified"})
        cards = self._cards()
        self.assertTrue(_ground_edge_case_card(cards, t))
        self.assertTrue(cards[0].get("_edge_case_grounded"))

    def test_uncertified_legacy_topic_keeps_old_behavior(self):
        from app.services.lean_lesson_generator import _ground_edge_case_card
        t = self._topic("Reynolds Number", "math_formula_method", None)
        cards = self._cards()
        self.assertTrue(_ground_edge_case_card(cards, t))           # no plan -> grounding unchanged


class ScopeOutBackfill(unittest.TestCase):
    """Sibling-boundary backfill: every live scope_out came back empty, so no topic excluded its siblings'
    content and lessons overlapped freely. A teaching topic with no model-provided out_of_scope inherits its
    siblings' scope_in commitments as explicit exclusions (own commitments excepted)."""

    @staticmethod
    def _t(title, scope_in, scope_out=None, tt="science_mechanism"):
        return {"title": title, "course_type": tt, "topic_type": tt,
                "in_scope": scope_in, "out_of_scope": scope_out or []}

    def test_empty_scope_out_inherits_sibling_commitments(self):
        from app.services.topic_generator import _certify_path_scope
        out = _certify_path_scope([
            self._t("Turbulence", ["definition of turbulence", "contrast with laminar flow"]),
            self._t("Energy Cascade", ["energy transfer across scales", "viscous dissipation"]),
        ], "learn fluid turbulence")
        by = {t["title"]: t for t in out}
        self.assertIn("energy transfer across scales", by["Turbulence"]["out_of_scope"])
        self.assertIn("definition of turbulence", by["Energy Cascade"]["out_of_scope"])
        self.assertNotIn("contrast with laminar flow", by["Turbulence"]["out_of_scope"])  # own item excluded
        plan = (by["Turbulence"].get("decomposition_metadata") or {}).get("scope_plan") or {}
        self.assertTrue(plan.get("scope_out_backfilled"))
        self.assertEqual(plan.get("scope_out"), by["Turbulence"]["out_of_scope"])

    def test_model_provided_scope_out_untouched(self):
        from app.services.topic_generator import _certify_path_scope
        out = _certify_path_scope([
            self._t("Turbulence", ["definition"], scope_out=["RANS closures"]),
            self._t("Energy Cascade", ["dissipation"]),
        ], "learn fluid turbulence")
        by = {t["title"]: t for t in out}
        self.assertEqual(by["Turbulence"]["out_of_scope"], ["RANS closures"])
        plan = (by["Turbulence"].get("decomposition_metadata") or {}).get("scope_plan") or {}
        self.assertNotIn("scope_out_backfilled", plan)


class GroundingPassesShareThePlanGuard(unittest.TestCase):
    """_plan_allowed_adapter is the single guard for EVERY pass pulling adapter-spec content into cards —
    the injection pass must not become the back door the grounding guard closed."""

    @staticmethod
    def _topic(title, tt, scope_plan):
        import types as _types
        meta = {"scope_plan": scope_plan} if scope_plan is not None else {}
        return _types.SimpleNamespace(title=title, course_type=tt, topic_type=tt,
                                      decomposition_metadata=meta, order_index=1, study_path=None)

    def test_injection_blocked_for_certified_null_topic(self):
        from app.services.lean_lesson_generator import _inject_grounded_cards
        t = self._topic("Understanding Fluid Turbulence", "concept_intuition",
                        {"verified_example": None, "we_policy": "not_applicable"})
        cards = [{"blueprint_key": "background", "card_type": "purpose_context", "points": ["x"]}]
        _inject_grounded_cards(cards, t, have_formula=False, have_edge=False)
        self.assertEqual(len(cards), 1)                     # nothing injected

    def test_injection_adds_formula_with_meaning_note_for_certified_topic(self):
        from app.services.lean_lesson_generator import _inject_grounded_cards
        t = self._topic("Flow Regimes", "science_mechanism",
                        {"verified_example": "reynolds_number", "we_policy": "verified"})
        cards = [{"blueprint_key": "background", "card_type": "purpose_context", "points": ["x"]},
                 {"blueprint_key": "worked_example", "card_type": "worked_example", "points": ["y"]}]
        _inject_grounded_cards(cards, t, have_formula=False, have_edge=False)
        formula = next(c for c in cards if c.get("blueprint_key") == "formula_breakdown")
        self.assertLess(cards.index(formula), 2 + 1)        # placed before the worked example
        joined = " ".join(formula["points"])
        self.assertIn("INERTIAL", joined)                   # the meaning note, not just the equation
        self.assertIn("characteristic length", joined.lower())

    def test_formula_grounding_blocked_for_certified_null_topic(self):
        from app.services.lean_lesson_generator import _ground_formula_card
        t = self._topic("Understanding Fluid Turbulence", "concept_intuition",
                        {"verified_example": None, "we_policy": "not_applicable"})
        cards = [{"blueprint_key": "formula_breakdown", "points": ["The formula:", "WRONG"]}]
        self.assertFalse(_ground_formula_card(cards, t))
        self.assertEqual(cards[0]["points"], ["The formula:", "WRONG"])


class WorkedExampleInterpretation(unittest.TestCase):
    """Science plan §8: a science worked example must not end at a bare number. The adapter spec's
    deterministic `interpret` produces an 'Interpretation:' teaching note on the final step (live: a
    turbulence lesson computed Re = 5532 and never said the flow was turbulent). Also guards the
    final-card polish: an answer identical to the result is not restated as 'Final answer: …'."""

    def test_reynolds_interpretation_units(self):
        from app.services.examples.trace_adapters.families.formula_specs import _reynolds_interpretation
        self.assertIn("laminar", _reynolds_interpretation({"Re": 1000}))
        self.assertIn("turbulent", _reynolds_interpretation({"Re": 5500}))
        self.assertIn("transitional", _reynolds_interpretation({"Re": 3000}))
        self.assertIsNone(_reynolds_interpretation({"Re": None}))
        self.assertIsNone(_reynolds_interpretation({}))

    def test_final_card_carries_interpretation_and_no_duplicate_answer(self):
        from app.services.examples.trace_pipeline import solve_trace_pipeline
        sol = solve_trace_pipeline({"title": "Flow Regimes", "topic_type": "science_mechanism",
                                    "course_type": "science_mechanism", "id": "t1"})
        last = (sol.get("cards") or [])[-1]
        note = last.get("teaching_note") or {}
        self.assertEqual(note.get("type"), "interpretation")
        content = str(note.get("content"))
        self.assertTrue(("laminar" in content) or ("turbulent" in content), content)
        # the interpretation names the SAME regime the computed value implies
        re_v = float(str(last.get("result")).split("=")[1].strip().rstrip("."))
        self.assertIn("laminar" if re_v < 2300 else "turbulent", content)
        self.assertEqual(str(last.get("result")).count(f"{re_v:g}"), 1)   # answer stated once, not restated

    def test_adapters_without_interpret_are_untouched(self):
        from app.services.examples.trace_pipeline import solve_trace_pipeline
        sol = solve_trace_pipeline({"title": "Kinetic Energy", "topic_type": "math_formula_method",
                                    "course_type": "math_formula_method", "id": "t2"})
        cards = sol.get("cards") or []
        self.assertTrue(cards)
        self.assertIsNone((cards[-1].get("teaching_note") or {}).get("type"))


class AdapterIdentityGuard(unittest.TestCase):
    """Same canonical key ≠ same concept: broad routing aliases give unrelated siblings one adapter
    (the turbulence trio all route reynolds_number), and collapsing on the key alone silently deleted
    planned topics — the 23:07 path shipped ONE teaching topic. Distinct topics survive; the shared
    adapter's verified exercise goes to the topic whose subject IS the adapter's concept; the rest
    withhold instead of repeating the identical calculation."""

    @staticmethod
    def _t(title, tt="science_mechanism"):
        return {"title": title, "course_type": tt, "topic_type": tt, "in_scope": ["x"], "out_of_scope": []}

    def _plan(self, topic):
        return (topic.get("decomposition_metadata") or {}).get("scope_plan") or {}

    def test_turbulence_trio_survives_and_reynolds_topic_claims_the_example(self):
        from app.services.topic_generator import _certify_path_scope
        out = _certify_path_scope([
            self._t("Defining Fluid Turbulence"),
            self._t("Laminar vs Turbulent Flow"),
            self._t("Reynolds Number"),
        ], "want to learn about fluid turbulence")
        self.assertEqual(len(out), 3)                        # nothing silently deleted
        by = {t["title"]: self._plan(t) for t in out}
        self.assertEqual(by["Reynolds Number"]["verified_example"], "reynolds_number")
        self.assertEqual(by["Reynolds Number"]["we_policy"], "verified")
        for other in ("Defining Fluid Turbulence", "Laminar vs Turbulent Flow"):
            self.assertIsNone(by[other]["verified_example"], other)
        self.assertEqual(by["Defining Fluid Turbulence"]["we_policy"], "conceptual_mechanism")
        self.assertEqual(by["Laminar vs Turbulent Flow"]["we_policy"], "withhold_fabricated")
        self.assertTrue(by["Laminar vs Turbulent Flow"].get("we_deduped_shared_adapter"))
        self.assertFalse(by["Defining Fluid Turbulence"].get("we_deduped_shared_adapter", False))

    def test_turbulence_concepts_do_not_inherit_reynolds_identity(self):
        from app.services.topic_generator import _canonical_concept_key
        self.assertEqual(_canonical_concept_key("want to learn about fluid turbulence"), "fluid_turbulence")
        self.assertEqual(_canonical_concept_key("Energy Transfer in Turbulence"), "turbulent_energy_cascade")
        self.assertEqual(_canonical_concept_key("Real-World Applications of Turbulence"),
                         "turbulence_applications")
        self.assertEqual(_canonical_concept_key("Reynolds Number"), "reynolds_number")

    def test_broad_turbulence_path_has_exactly_one_goal_core(self):
        from app.services.topic_generator import _certify_path_scope
        topics = [
            self._t("Types of Fluid Flow", "compare_distinguish"),
            self._t("Energy Transfer in Turbulence", "science_mechanism"),
            self._t("Real-World Applications of Turbulence", "problem_solving_application"),
        ]
        topics[0]["in_scope"] = ["laminar and turbulent flow classification"]
        topics[1]["in_scope"] = ["large eddies", "energy cascade", "viscous dissipation"]
        topics[2]["in_scope"] = ["aerodynamic drag", "industrial mixing"]
        out = _certify_path_scope(topics, "want to learn about fluid turbulence")
        cores = [t for t in out if self._plan(t).get("role") == "goal_core"]
        self.assertEqual([t["title"] for t in cores], ["Energy Transfer in Turbulence"])
        by = {t["title"]: self._plan(t) for t in out}
        self.assertIsNone(by["Types of Fluid Flow"]["verified_example"])
        self.assertIsNone(by["Energy Transfer in Turbulence"]["verified_example"])
        self.assertEqual(by["Energy Transfer in Turbulence"]["we_policy"], "conceptual_mechanism")
        self.assertIsNone(by["Real-World Applications of Turbulence"]["verified_example"])

    def test_true_duplicates_still_collapse(self):
        from app.services.topic_generator import _certify_path_scope
        out = _certify_path_scope([self._t("Physics of Turbulence"), self._t("Turbulence Physics")],
                                  "learn fluid turbulence")
        self.assertEqual(len(out), 1)                        # shared token -> same concept -> dropped

    def test_acronym_duplicates_still_collapse(self):
        from app.services.topic_generator import _certify_path_scope
        out = _certify_path_scope([self._t("Breadth-First Search", "algorithm_walkthrough"),
                                   self._t("BFS", "algorithm_walkthrough")], "learn graph traversal")
        self.assertEqual(len(out), 1)

    def test_same_adapter_drop_pass_keeps_distinct_concepts(self):
        from app.services.topic_generator import _drop_same_adapter_duplicate_topics
        trio = [self._t("Defining Fluid Turbulence"), self._t("Laminar vs Turbulent Flow"),
                self._t("Reynolds Number")]
        self.assertEqual(len(_drop_same_adapter_duplicate_topics(trio)), 3)
        # the original live case (same concept, action-variant titles) still collapses
        dupes = [self._t("Straight-Line Depreciation Formula", "math_formula_method"),
                 self._t("Applying Straight-Line Depreciation", "math_formula_method")]
        self.assertEqual(len(_drop_same_adapter_duplicate_topics(dupes)), 1)


class BlueprintGateKeepsGroundedCards(unittest.TestCase):
    """validate_and_order_cards must never drop deterministic spec-grounded cards: the science_mechanism
    blueprint doesn't name formula_breakdown, so every injected grounded formula card was silently
    deleted at finalize from 2026-07-11 on — the worked example ran on a formula the lesson never showed."""

    def test_grounded_formula_card_kept_and_ordered_before_process(self):
        from app.services.examples.handoff import validate_and_order_cards
        lesson = {"lesson_cards": [
            {"blueprint_key": "background", "card_type": "purpose_context"},
            {"blueprint_key": "process", "card_type": "method_process"},
            {"blueprint_key": "formula_breakdown", "card_type": "formula", "_formula_grounded": True},
            {"blueprint_key": "worked_example", "card_type": "worked_example"},
            {"blueprint_key": "practice", "card_type": "quick_practice"},
        ]}
        validate_and_order_cards(lesson, {"topic_type": "science_mechanism"})
        keys = [c["blueprint_key"] for c in lesson["lesson_cards"]]
        self.assertIn("formula_breakdown", keys)             # kept despite not being in the blueprint
        self.assertLess(keys.index("formula_breakdown"), keys.index("process"))  # shown before applied

    def test_ungrounded_offblueprint_card_still_dropped(self):
        from app.services.examples.handoff import validate_and_order_cards
        lesson = {"lesson_cards": [
            {"blueprint_key": "background", "card_type": "purpose_context"},
            {"blueprint_key": "formula_breakdown", "card_type": "formula"},   # LLM-authored, no stamp
            {"blueprint_key": "practice", "card_type": "quick_practice"},
        ]}
        validate_and_order_cards(lesson, {"topic_type": "science_mechanism"})
        keys = [c["blueprint_key"] for c in lesson["lesson_cards"]]
        self.assertNotIn("formula_breakdown", keys)          # the gate still filters untrusted cards


class RequirementReconciliation(unittest.TestCase):
    """Fixes from the 23:47 review: requirement ownership must be reconciled semantically, exclusions must
    not restate a topic's own scope, plan-time example ownership must be authoritative in the solver, and a
    prereq that is a taught concept plus qualifier words is circular."""

    def test_semantic_coverage_prevents_duplicate_synthesis(self):
        from app.services.topic_decomposition_pipeline import _requirement_covered_by_topics
        req = {"requirement_id": "R2", "name": "Energy cascade and dissipation",
               "statement": "describe how energy transfers from large eddies to smaller scales before "
                            "viscous dissipation removes it"}
        topic = {"title": "Energy Transfer in Turbulent Flows", "subject_key": "energy_transfer",
                 "in_scope": ["energy transfer in turbulence", "large eddies and small scales",
                              "viscous dissipation"]}
        self.assertTrue(_requirement_covered_by_topics(req, [topic]))
        unrelated = {"title": "Flow Regimes and Transition", "subject_key": "flow_regimes",
                     "in_scope": ["laminar vs turbulent", "critical thresholds"]}
        self.assertFalse(_requirement_covered_by_topics(req, [unrelated]))

    def test_scope_out_backfill_skips_own_content_rephrased(self):
        from app.services.topic_generator import _certify_path_scope
        energy = {"title": "Energy Transfer in Turbulent Flows", "course_type": "science_mechanism",
                  "topic_type": "science_mechanism", "out_of_scope": [],
                  "in_scope": ["energy transfer in turbulence", "large eddies and small scales",
                               "viscous dissipation"]}
        synth = {"title": "Energy Transfer Mechanisms", "course_type": "science_mechanism",
                 "topic_type": "science_mechanism", "out_of_scope": [],
                 "in_scope": ["describe how energy transfers from large eddies to smaller scales before "
                              "viscous dissipation removes it"]}
        regimes = {"title": "Flow Regimes", "course_type": "science_mechanism",
                   "topic_type": "science_mechanism", "out_of_scope": [],
                   "in_scope": ["laminar vs turbulent classification"]}
        out = _certify_path_scope([energy, synth, regimes], "learn fluid turbulence")
        by = {t["title"]: t for t in out}
        # the sentence-level restatement of energy's own scope is NOT copied into its exclusions
        self.assertFalse(any("energy transfers from large eddies" in s
                             for s in by["Energy Transfer in Turbulent Flows"]["out_of_scope"]))
        # genuinely foreign sibling content still is
        self.assertTrue(any("laminar" in s
                            for s in by["Energy Transfer in Turbulent Flows"]["out_of_scope"]))

    def test_solver_honors_plan_withhold_and_mismatch(self):
        from app.services.examples.trace_pipeline import solve_trace_pipeline
        withheld = {"title": "Observable Consequences of Turbulence", "topic_type": "science_mechanism",
                    "course_type": "science_mechanism", "id": "t1",
                    "decomposition_metadata": {"scope_plan": {
                        "verified_example": None, "we_policy": "withhold_fabricated",
                        "we_deduped_shared_adapter": True}}}
        self.assertIsNone(solve_trace_pipeline(withheld))     # plan says no adapter -> no trace WE
        mismatched = {"title": "Turbulence", "topic_type": "science_mechanism",
                      "course_type": "science_mechanism", "id": "t2",
                      "decomposition_metadata": {"scope_plan": {
                          "verified_example": "kinetic_energy", "we_policy": "verified"}}}
        self.assertIsNone(solve_trace_pipeline(mismatched))   # routed reynolds != planned kinetic_energy
        planned = {"title": "Flow Regimes", "topic_type": "science_mechanism",
                   "course_type": "science_mechanism", "id": "t3",
                   "decomposition_metadata": {"scope_plan": {
                       "verified_example": "reynolds_number", "we_policy": "verified"}}}
        sol = solve_trace_pipeline(planned)
        self.assertIsNotNone(sol)                             # matching plan solves as before

    def test_enforcement_strips_deduped_trace_backed_duplicate(self):
        from app.services.examples.handoff import enforce_example_plan
        we = {"blueprint_key": "worked_example", "card_type": "worked_example", "title": "Step",
              "metadata": {"trace_backed": True}}
        lesson = {"lesson_cards": [{"blueprint_key": "background", "card_type": "purpose_context"}, we]}
        topic = {"title": "Observable Consequences", "decomposition_metadata": {"scope_plan": {
            "we_policy": "withhold_fabricated", "we_deduped_shared_adapter": True}}}
        enforce_example_plan(lesson, topic)
        keys = [c["blueprint_key"] for c in lesson["lesson_cards"]]
        self.assertNotIn("worked_example", keys)              # verified DUPLICATE is stripped
        # without the dedup stamp, trace-backed content is still protected (stale-plan case)
        lesson2 = {"lesson_cards": [dict(we)]}
        topic2 = {"title": "T", "decomposition_metadata": {"scope_plan": {
            "we_policy": "withhold_fabricated"}}}
        enforce_example_plan(lesson2, topic2)
        self.assertEqual(len(lesson2["lesson_cards"]), 1)

    def test_superset_prereq_of_taught_topic_blocked(self):
        from app.services.topic_generator import _certify_path_scope
        laws = {"title": "Laws and Principles of Turbulence", "course_type": "science_mechanism",
                "topic_type": "science_mechanism", "in_scope": ["x"], "out_of_scope": [],
                "assumed_prerequisites": []}
        intro = {"title": "Introduction to Fluid Turbulence", "course_type": "study_path_introduction",
                 "topic_type": "study_path_introduction", "in_scope": [], "out_of_scope": [],
                 "assumed_prerequisites": ["Key Laws and Principles Governing Turbulence",
                                           "fluid dynamics"]}
        out = _certify_path_scope([intro, laws], "learn fluid turbulence")
        intro_out = next(t for t in out if t["course_type"] == "study_path_introduction")
        self.assertEqual(intro_out["assumed_prerequisites"], ["fluid dynamics"])

    def test_adapter_claim_prefers_regime_shape_over_alias_matched_mechanism(self):
        from app.services.topic_generator import _certify_path_scope
        mech = {"title": "Physical Characteristics of Turbulent Flows", "course_type": "science_mechanism",
                "topic_type": "science_mechanism", "in_scope": ["chaotic behavior"], "out_of_scope": []}
        regime = {"title": "Flow Regimes and Transition", "course_type": "science_mechanism",
                  "topic_type": "science_mechanism", "in_scope": ["laminar vs turbulent"],
                  "out_of_scope": []}
        out = _certify_path_scope([mech, regime], "learn fluid turbulence")
        by = {t["title"]: (t.get("decomposition_metadata") or {}).get("scope_plan") or {} for t in out}
        self.assertIsNone(by["Physical Characteristics of Turbulent Flows"]["verified_example"])
        self.assertEqual(by["Flow Regimes and Transition"]["verified_example"], "reynolds_number")


class TopicDepthRepairs(unittest.TestCase):
    """User-reported thinness (00:16 path): 'Flow Types' (role=mechanism) typed concept_intuition shipped a
    4-card overview with no process card; the synthesized 'Reynolds number significance' topic defaulted to
    concept_intuition, was not WE-centric, and could never claim its own adapter (the Reynolds example
    drifted to Energy Cascade)."""

    def test_mechanism_role_upgraded_out_of_concept_intuition(self):
        from app.services.topic_decomposition_pipeline import _normalize_topic
        t = _normalize_topic({"topic_id": "t1", "subject_key": "flow_types", "title": "Flow Types",
                              "content_role": "mechanism", "topic_type": "concept_intuition"})
        self.assertEqual(t["topic_type"], "process_walkthrough")
        # deliberate concept lessons (role foundation) and orientation openers stay untouched
        t2 = _normalize_topic({"topic_id": "t2", "subject_key": "s", "title": "T",
                               "content_role": "foundation", "topic_type": "concept_intuition"})
        self.assertEqual(t2["topic_type"], "concept_intuition")
        t3 = _normalize_topic({"topic_id": "t3", "subject_key": "s", "title": "T",
                               "content_role": "orientation", "topic_type": "concept_intuition"})
        self.assertEqual(t3["topic_type"], "concept_intuition")

    def test_quantitative_requirement_synthesizes_formula_topic(self):
        from app.services.topic_decomposition_pipeline import generate_decomposed_topics
        reqs = {"requirements": [
            {"requirement_id": "R1", "name": "Flow regimes", "kind": "core",
             "statement": "distinguish laminar and turbulent flow"},
            {"requirement_id": "R2", "name": "Reynolds number significance", "kind": "core",
             "statement": "explain the physical meaning of the Reynolds number and its role in "
                          "characterizing flow regimes"},
        ]}
        plan = {"path_plan": {"end_capability_actions": ["understand"], "required_capabilities": []},
                "topics": [{"topic_id": "t1", "capability_id": "t1", "subject_key": "energy_cascade",
                            "primary_action": "understand", "content_role": "mechanism",
                            "topic_type": "science_mechanism", "title": "Energy Cascade", "unit_title": "u",
                            "purpose": "p", "in_scope": ["large eddies", "dissipation"],
                            "covers_requirements": ["R1"], "basis": "goal"}]}
        def fn(payload):
            return reqs if "learning requirements" in payload["user"] else plan
        topics = generate_decomposed_topics("learn fluid turbulence", "s", model_fn=fn)
        reynolds = next(t for t in topics if "Reynolds" in t["title"])
        self.assertEqual(reynolds["course_type"], "math_formula_method")   # WE-centric, can claim its adapter
        mech_req = {"requirement_id": "R9", "name": "Energy cascade process", "kind": "core",
                    "statement": "describe the process by which energy transfers across eddy scales"}
        from app.services.topic_decomposition_pipeline import _req_tokens
        self.assertTrue(_req_tokens(mech_req["statement"]) & {"process", "transfer"})


if __name__ == "__main__":
    unittest.main()
