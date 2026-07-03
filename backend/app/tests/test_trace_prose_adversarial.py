"""Adversarial Stage-4b tests (WORKED_EXAMPLE_REASONING_SPEC v8 §12b/§17): prove the prose guard BLOCKS a
lying formatter — not just that happy-path prose passes. A formatter stub deliberately emits the
learner-visible failures the guard exists to catch (wrong value, wrong accept/reject, un-discussed probe);
the guard must return a HARD violation. Severity split: only contradictions block; missing facts are advisory.
Fully offline (no LLM)."""
import unittest

from app.services.examples import trace_pipeline as tp
from app.services.examples.trace_adapters import ADAPTERS
from app.services.examples.trace_contract import (ContractTrace, Step, hard_prose_violations,
                                                  validate_prose)


def _card(step, work):
    return {"trace_step_ids": [step.id], "title": step.operation, "goal": step.decision,
            "reasoning": step.reason, "work": list(work), "result": "",
            "prior_state": step.prior_state, "result_state": step.state_after}


def _bare_card(step, work):
    """A card whose ONLY prose is `work` — no faithful title/goal/reason to accidentally mask the lie."""
    return {"trace_step_ids": [step.id], "title": "", "goal": "", "reasoning": "", "work": list(work),
            "result": "", "prior_state": step.prior_state, "result_state": step.state_after}


def _faithful_card(step):
    from app.services.examples.trace_contract import _fact_text
    work = [_fact_text(f) for f in step.facts.get("required_facts", [])] + [step.expected_visible_result]
    return _card(step, work)


class _StubAdapter:
    def validate_prose_claims(self, card, step):
        return []


class SeveritySplit(unittest.TestCase):
    """The three classes are assigned correctly and hard_prose_violations() filters to contradictions."""
    def test_value_forbidden_are_hard_missing_is_advisory(self):
        step = Step(id="s1", operation="probe", prior_state={}, state_after={},
                    facts={"allowed_values": [5], "required_facts": ["mid is 5"],
                           "forbidden_claims": ["target found"]})
        trace = ContractTrace(problem="p", conventions={}, initial_state={}, final_answer=None, steps=[step])
        # prose: states 7 (not allowed) + "target found" (forbidden) + omits "mid is 5" (missing)
        v = validate_prose([_card(step, ["the value is 7; target found"])], trace, _StubAdapter())
        by = {(x.code, x.severity) for x in v}
        self.assertIn(("value_not_allowed", "hard"), by)
        self.assertIn(("forbidden_claim", "hard"), by)
        self.assertIn(("missing_fact", "missing"), by)
        hard = hard_prose_violations(v)
        self.assertTrue(hard and all(x.severity == "hard" for x in hard))
        self.assertFalse(any(x.code == "missing_fact" for x in hard))   # missing never blocks


class LyingFormatterIsCaught(unittest.TestCase):
    DETERMINISTIC = ["binary_search", "bfs", "dfs_iter", "kruskal", "merge_sort", "quick_sort", "insertion_sort", "selection_sort", "bubble_sort", "heap_sort", "dijkstra",
                     "arithmetic_eval", "prim", "tree_inorder", "tree_preorder", "tree_postorder",
                     "tree_levelorder", "quadratic", "kinematics", "bst_search", "longest_increasing_subsequence", "coin_change", "n_queens", "bellman_ford", "union_find", "euclid_gcd", "induction_proof", "floyd_warshall", "sieve_of_eratosthenes"]

    def _trace(self, slug):
        a = ADAPTERS[slug]
        return a, tp.select_instance(a, seed=3)

    def test_every_adapter_has_adversarial_coverage(self):
        # §E: adversarial/hallucination coverage is machine-REQUIRED — every registered adapter must be here,
        # so a new adapter can't ship without a lying-formatter test.
        self.assertEqual(set(ADAPTERS) - set(self.DETERMINISTIC), set())

    def test_faithful_cards_have_no_hard_violations(self):
        for slug in self.DETERMINISTIC:
            a, tr = self._trace(slug)
            with self.subTest(slug=slug):
                cards = [_faithful_card(s) for s in tr.steps]
                self.assertEqual(hard_prose_violations(validate_prose(cards, tr, a)), [],
                                 f"{slug}: faithful prose wrongly flagged")

    def test_out_of_range_value_is_a_hard_violation(self):
        for slug in self.DETERMINISTIC:
            a, tr = self._trace(slug)
            step = next((s for s in tr.steps if s.facts.get("allowed_values")), None)
            if step is None:
                continue
            with self.subTest(slug=slug):
                lie = _card(step, ["the value here is 987654"])   # 987654 not in allowed_values
                hard = hard_prose_violations(validate_prose([lie], tr, a))
                self.assertTrue(any(x.code == "value_not_allowed" for x in hard),
                                f"{slug}: out-of-range value not caught as hard")

    def test_kruskal_accept_step_described_as_skip_is_caught(self):
        a, tr = self._trace("kruskal")
        accept = next(s for s in tr.steps if s.decision == "accept")
        u, v, w = accept.inputs["edge"]
        lie = _bare_card(accept, [f"consider edge ({u},{v},{w}); skip it as a cycle"])   # wrong decision
        hard = hard_prose_violations(validate_prose([lie], tr, a))
        self.assertTrue(any(x.code == "decision_mismatch" for x in hard),
                        "Kruskal accept-as-skip not caught")

    def test_kruskal_skip_step_described_as_accept_is_caught(self):
        a, tr = self._trace("kruskal")
        skip = next((s for s in tr.steps if s.decision == "skip"), None)
        if skip is None:
            self.skipTest("seed produced no skip step")
        u, v, w = skip.inputs["edge"]
        lie = _bare_card(skip, [f"add edge ({u},{v},{w}) to the MST"])   # wrong decision
        hard = hard_prose_violations(validate_prose([lie], tr, a))
        self.assertTrue(any(x.code == "decision_mismatch" for x in hard),
                        "Kruskal skip-as-accept not caught")

    def test_binary_search_undiscussed_probe_is_caught(self):
        a, tr = self._trace("binary_search")
        step = tr.steps[0]
        lie = _bare_card(step, ["we look at the middle and move on"])   # never states the probed value
        hard = hard_prose_violations(validate_prose([lie], tr, a))
        self.assertTrue(any(x.code == "value_not_discussed" for x in hard),
                        "binary search un-discussed probe not caught")


class DecisionContradictionGuard(unittest.TestCase):
    """A1 (STUDY_PATH_CONTENT_SPEC): the LIVE Step-5 bug — Result says 'accept' (satisfying the adapter's
    mention-check) while Work asserts 'skip'/'already linked'. The generic guard must catch what the
    adapter's narrow check misses, without false-positiving on a negated mention."""
    def _trace(self, slug):
        a = ADAPTERS[slug]
        return a, tp.select_instance(a, seed=3)

    def test_skip_in_work_with_accept_in_result_is_caught(self):
        a, tr = self._trace("kruskal")
        accept = next(s for s in tr.steps if s.decision == "accept")
        u, v, w = accept.inputs["edge"]
        card = {"trace_step_ids": [accept.id], "title": "", "goal": "", "reasoning": "",
                "work": [f"edge ({u},{v},{w}) connects components already linked", "skip the edge"],
                "result": f"Edge ({u},{v},{w}) accept; MST so far [...]",   # 'accept' satisfies the adapter
                "prior_state": accept.prior_state, "result_state": accept.state_after}
        hard = hard_prose_violations(validate_prose([card], tr, a))
        self.assertTrue(any(x.code == "decision_contradiction" for x in hard),
                        "accept step with 'skip' in Work not caught")

    def test_negated_skip_on_accept_is_not_flagged(self):
        a, tr = self._trace("kruskal")
        accept = next(s for s in tr.steps if s.decision == "accept")
        u, v, w = accept.inputs["edge"]
        card = {"trace_step_ids": [accept.id], "title": "", "goal": "", "reasoning": "",
                "work": [f"add edge ({u},{v},{w}) to the MST; we do not skip it — the components differ"],
                "result": f"Edge ({u},{v},{w}) accept; MST so far [...]",
                "prior_state": accept.prior_state, "result_state": accept.state_after}
        hard = hard_prose_violations(validate_prose([card], tr, a))
        self.assertFalse(any(x.code == "decision_contradiction" for x in hard),
                         "negated 'do not skip' wrongly flagged")

    def test_reference_to_prior_skipped_edge_is_not_flagged(self):
        # over-withholding risk: an accept line that REFERENCES a previously-skipped edge while asserting
        # 'add' must not be flagged (the line states the real action + merely mentions the other).
        a, tr = self._trace("kruskal")
        accept = next(s for s in tr.steps if s.decision == "accept")
        u, v, w = accept.inputs["edge"]
        card = {"trace_step_ids": [accept.id], "title": "", "goal": "", "reasoning": "",
                "work": [f"Add edge ({u},{v},{w}) to the MST; unlike edge (D,E) which we skipped earlier, "
                         "this one connects new components"],
                "result": f"Edge ({u},{v},{w}) accept; MST so far [...]",
                "prior_state": accept.prior_state, "result_state": accept.state_after}
        hard = hard_prose_violations(validate_prose([card], tr, a))
        self.assertFalse(any(x.code == "decision_contradiction" for x in hard),
                         "prior-skipped-edge reference wrongly flagged (over-withholding)")


class CodeAnchoredAllowlist(unittest.TestCase):
    """A3: the numeric allowlist (conceptual-trace vocabulary) must NOT apply to a code-anchored worked
    example, where code runtime values (heap start cost 0, indices) legitimately appear."""
    def _step_trace(self):
        step = Step(id="s1", operation="x", prior_state={}, state_after={},
                    facts={"allowed_values": [1, 2, 4, 7, 14], "required_facts": [], "forbidden_claims": []})
        return step, ContractTrace(problem="p", conventions={}, initial_state={}, final_answer=None,
                                   steps=[step])

    def test_default_flags_structural_number_but_code_anchored_exempts_it(self):
        step, tr = self._step_trace()
        card = _card(step, ["cost, u = heapq.heappop(min_heap) // pop (0, 'A')"])   # 0 not in allowed
        self.assertTrue(any(x.code == "value_not_allowed"
                            for x in validate_prose([card], tr, _StubAdapter())))
        self.assertFalse(any(x.code == "value_not_allowed"
                             for x in validate_prose([card], tr, _StubAdapter(), code_anchored=True)))


if __name__ == "__main__":
    unittest.main()
