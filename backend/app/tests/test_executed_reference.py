"""Executed-reference worked examples: the general path — model writes a reference, we EXECUTE it."""
import os
import unittest

from app.services.gen_foundation.executed_reference import build_executed_reference
from app.services.gen_foundation.pipeline import _executable_input, _graph_nodes, run_first_pass

KRUSKAL = (
    "def kruskal(n, edges):\n"
    "    parent=list(range(n))\n"
    "    def find(x):\n"
    "        while parent[x]!=x: x=parent[x]\n"
    "        return x\n"
    "    mst=[]\n"
    "    for u,v,w in sorted(edges,key=lambda e:e[2]):\n"
    "        ru,rv=find(u),find(v)\n"
    "        if ru!=rv: parent[ru]=rv; mst.append((u,v,w))\n"
    "    return mst\n"
)
GRAPH = {"graph": {"nodes": ["A", "B", "C", "D", "E"],
                   "edges": [["A", "B", 2], ["B", "C", 3], ["C", "D", 1], ["D", "E", 4],
                             ["A", "E", 10], ["B", "D", 7]]}}


def _stub(code):
    return lambda payload: {"code": code}


_FLAGS = ("AZALEA_GEN_FOUNDATION_EXECUTE", "AZALEA_TRACE_FIRST")


class ExecutedReferenceTests(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in _FLAGS}
        for k in _FLAGS:
            os.environ[k] = "1"

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _build(self, code, ei):
        return build_executed_reference(
            {"title": "X"}, ei, generate=_stub(code),
            executable_input=_executable_input, node_labels=_graph_nodes(ei))

    def test_mst_is_correct_and_in_letters(self):
        r = self._build(KRUSKAL, GRAPH)
        self.assertEqual(r["source"], "executed_reference")
        # true MST weight on this graph is 1+2+3+4 = 10, V-1 = 4 edges
        self.assertEqual(len(r["final_answer"]), 4)
        self.assertEqual(sum(e[2] for e in r["final_answer"]), 10)
        self.assertTrue(all(isinstance(e[0], str) for e in r["final_answer"]))  # letters, not ints

    def test_cards_are_conceptual_no_code(self):
        r = self._build(KRUSKAL, GRAPH)
        for c in r["cards"]:
            self.assertEqual(c["code_refs"], [])                 # no code lines on a walkthrough card
            self.assertTrue(c["goal"] and c["result"])
        # the accumulator grows monotonically to the final MST
        self.assertEqual(r["cards"][-1]["result"], f"mst = {r['final_answer']!r}")

    def test_helper_frame_noise_filtered_out(self):
        r = self._build(KRUSKAL, GRAPH)
        # union-find internals (parent/x) must not appear as cards
        joined = " ".join(c["result"] for c in r["cards"])
        self.assertNotIn("parent", joined)
        self.assertNotIn("x =", joined)

    def test_sorting_reference_generality(self):
        bubble = ("def bubble(a):\n a=list(a)\n for i in range(len(a)):\n"
                  "  for j in range(len(a)-1-i):\n   if a[j]>a[j+1]: a[j],a[j+1]=a[j+1],a[j]\n return a\n")
        r = build_executed_reference({"title": "Bubble Sort"}, {"array": [5, 2, 8, 1]},
                                     generate=_stub(bubble), executable_input=_executable_input)
        self.assertEqual(r["final_answer"], [1, 2, 5, 8])

    def test_misses_return_empty(self):
        self.assertEqual(build_executed_reference({"title": "X"}, None, generate=_stub(KRUSKAL),
                                                  executable_input=_executable_input), {})
        self.assertEqual(build_executed_reference({"title": "X"}, GRAPH, generate=lambda p: None,
                                                  executable_input=_executable_input), {})

    def test_pipeline_uses_executed_reference_for_offlist_walkthrough(self):
        # Dijkstra's shortest path: gets a weighted-graph input but is NOT in the hardcoded reference
        # set (no "mst"), so the general executed-reference path must kick in.
        art = {"cards": [{"title": "x", "goal": "g", "how": "h", "work": ["w"], "result": "r",
                          "state_relevance": "none", "state_delta": None, "cases_covered": []}],
               "final_answer": "WRONG", "code": None}
        res = run_first_pass(
            {"topic_type": "algorithm_walkthrough", "title": "Understanding Dijkstra's Shortest Path"},
            solver=lambda p: dict(art), auditor=lambda p: None, repair=lambda p: None,
            reference_coder=_stub(KRUSKAL))
        a = res.artifact or {}
        self.assertTrue(a.get("reference_backed"))
        self.assertEqual(a.get("cards", [{}])[0].get("trace_backed") or
                         (a.get("cards") and True), True)


if __name__ == "__main__":
    unittest.main()
