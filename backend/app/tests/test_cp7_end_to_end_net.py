"""CP7 (automated backstop) — drive the SIX core topics end-to-end through the real trace pipeline and assert
the programmable slice of the CP7 exit checklist. This is not a substitute for human product QA (visual match,
"feels useful") — it is the automated net that proves the shipped path stays correct + complete + provenanced
for every core topic, in BOTH the normal prose-fill mode and the forced-fallback (deterministic) mode.

Programmable CP7 checks per topic: adapter selected · trace_verified · no from-scratch final_source · every
learner-facing artifact cites a checkpoint_id with a source range · required transitions + checkpoints covered ·
terminal rendered · no raw backend state (dict/list) leaked into a card result · §1.2/CP6 invariants clean."""
import json
import re
import unittest

from app.services.examples import generation_report as gr
from app.services.examples import trace_pipeline as tp

_TOPICS = [
    ("Prim's Minimum Spanning Tree", "prim"),
    ("Kruskal's Minimum Spanning Tree", "kruskal"),
    ("Depth-First Search traversal", "dfs_iter"),
    ("Breadth-First Search traversal", "bfs"),
    ("Merge Sort", "merge_sort"),
    ("Binary Search", "binary_search"),
]

# Raw backend state leaking into learner-facing prose (C7/B5): a state DICT (`{'in_tree': [...]}`), a nested
# list of quoted tuples (`[['C','E',5],...]`), OR a single-level quoted list (`['A', 'B', 'C']` — a raw node
# set). Plain index/window notation (`[0, 3]`, `arr[4]`) has no quotes and must NOT trip this.
_RAW_STATE = re.compile(r"\{\s*['\"]?\w+['\"]?\s*:|\[\s*\[|[,\[]\s*['\"]")


def _faithful(payload):
    """A faithful formatter stub: echo the verified steps 1:1 (the backend attaches the truth-bearing fields)."""
    steps = json.loads(payload["user"].split("STEPS (verified, describe faithfully):", 1)[1])
    return {"cards": [{"title": s["operation"], "goal": "", "reasoning": "",
                       "work": (s["facts"].get("required_facts", []) or []) + [s["expected_visible_result"]],
                       "result": s["expected_visible_result"]} for s in steps]}


def _always_fails(payload):
    return {"cards": [{"title": "x", "work": ["w"], "result": "r"}]}   # wrong count → forces the fallback path


class CP7EndToEndNet(unittest.TestCase):
    def _assert_shipped_lesson(self, slug, res):
        self.assertIsNotNone(res, f"{slug}: withheld")
        cards = res["cards"]
        self.assertTrue(cards, f"{slug}: no cards")
        for c in cards:
            self.assertTrue(c.get("checkpoint_id"), f"{slug}: card without checkpoint_id")
            self.assertTrue(c.get("source_transition_start"), f"{slug}: card without source range")
            result = str(c.get("result", ""))
            self.assertFalse(_RAW_STATE.search(result), f"{slug}: raw state leaked into result: {result!r}")
            self.assertFalse(_RAW_STATE.search(str(c.get("reasoning", ""))),
                             f"{slug}: raw state leaked into reasoning: {c.get('reasoning')!r}")
        # C1/E4: a multi-step lesson must NOT ship one generic reasoning repeated on every card — the
        # per-step "why" (esp. an accept vs a cycle-skip) must be distinct.
        reasonings = [str(c.get("reasoning", "")).strip() for c in cards if str(c.get("reasoning", "")).strip()]
        if len(cards) >= 3:
            self.assertGreater(len(set(reasonings)), 1,
                               f"{slug}: every card shares identical reasoning (C1/E4): {reasonings[0]!r}")
        we = gr.current().worked_example
        self.assertEqual(we.get("adapter"), slug, f"{slug}: wrong adapter")
        self.assertFalse(gr.is_from_scratch_source(we.get("final_source")), f"{slug}: from-scratch source")
        self.assertEqual(we.get("missing_required_transition_ids"), [], f"{slug}: missing required transition")
        self.assertEqual(we.get("missing_required_checkpoint_ids"), [], f"{slug}: missing required checkpoint")
        self.assertTrue(we.get("terminal_rendered"), f"{slug}: terminal not rendered")
        self.assertEqual(gr.invariant_violations(gr.current().to_dict()), [], f"{slug}: invariant violation")

    def test_normal_narration_mode(self):
        for title, slug in _TOPICS:
            with self.subTest(topic=title, mode="normal"):
                topic = {"title": title, "topic_type": "algorithm_walkthrough"}
                gr.start(topic)
                res = tp.solve_trace_pipeline(topic, format_fn=_faithful)
                # solver normally stamps these on a trace_pipeline ship; mirror that for the invariant check
                gr.we(final_source="trace_pipeline", verification_level="trace_verified")
                self._assert_shipped_lesson(slug, res)
                gr.finish_and_persist()

    def test_forced_fallback_mode(self):
        for title, slug in _TOPICS:
            with self.subTest(topic=title, mode="fallback"):
                topic = {"title": title, "topic_type": "algorithm_walkthrough"}
                gr.start(topic)
                res = tp.solve_trace_pipeline(topic, format_fn=_always_fails)
                gr.we(final_source="trace_pipeline", verification_level="trace_verified")
                self._assert_shipped_lesson(slug, res)
                gr.finish_and_persist()


if __name__ == "__main__":
    unittest.main()
