"""Build-time verification of the canonical solutions (canonical_solutions.py).

Python is the ONE verified source: it is EXECUTED here so a wrong reference can never ship (graph-MST ones
also run through the A2 executor). Other languages are translated-from-Python on demand + cached; that path
is exercised with a deterministic stand-in translator (no network), including the offline fallback."""
import unittest

from app.services.examples import canonical_solutions as cs
from app.services.examples.canonical_solutions import (CANONICAL_SOLUTIONS, canonical_python,
                                                       display_solution, set_translator)
from app.services.examples.code_execution_check import check_graph_topic_code


def _run(slug: str, call: str):
    ns: dict = {}
    exec(canonical_python(slug), ns)            # noqa: S102 — our own trusted code, executed to verify it
    return eval(call, ns)                        # noqa: S307


class CanonicalPythonRuns(unittest.TestCase):
    _GRAPH = {0: [1, 2], 1: [0, 3], 2: [0, 3], 3: [1, 2]}

    def test_bfs_order(self):
        self.assertEqual(_run("bfs", f"bfs({self._GRAPH}, 0)"), [0, 1, 2, 3])

    def test_dfs_order(self):
        self.assertEqual(_run("dfs_iter", f"dfs({self._GRAPH}, 0)"), [0, 1, 3, 2])

    def test_dijkstra_distances(self):
        g = {0: [(1, 4), (2, 1)], 1: [], 2: [(1, 2)]}
        self.assertEqual(_run("dijkstra", f"dijkstra({g}, 0)"), {0: 0, 2: 1, 1: 3})

    def test_merge_sort(self):
        self.assertEqual(_run("merge_sort", "merge_sort([5, 2, 9, 1, 5, 6])"), [1, 2, 5, 5, 6, 9])

    def test_binary_search(self):
        self.assertEqual(_run("binary_search", "binary_search([1, 3, 5, 7, 9], 7)"), 3)
        self.assertEqual(_run("binary_search", "binary_search([1, 3, 5, 7, 9], 4)"), -1)

    def test_arithmetic_precedence(self):
        self.assertEqual(_run("arithmetic_eval", "evaluate([3, '+', 4, '*', 2, '-', 1])"), 10)


class CanonicalMstViaExecutor(unittest.TestCase):
    def test_kruskal_is_a_valid_mst(self):
        self.assertEqual(check_graph_topic_code(canonical_python("kruskal"), "kruskal").status, "ok")

    def test_prim_is_a_valid_mst(self):
        self.assertEqual(check_graph_topic_code(canonical_python("prim"), "prim").status, "ok")


class PythonDisplay(unittest.TestCase):
    def test_python_display_strips_imports_keeps_body(self):
        disp = display_solution("bfs", "python")
        for line in disp.splitlines():
            self.assertFalse(line.startswith(("import ", "from ")), line)
        self.assertIn("def bfs", disp)
        self.assertIn("deque", disp)              # still USES the facility, just not the import line

    def test_every_slug_has_python_source(self):
        for slug in CANONICAL_SOLUTIONS:
            self.assertTrue(canonical_python(slug))


class TranslationOnDemand(unittest.TestCase):
    """C++/Java are translated from the Python once and cached; the translator is injectable."""
    def setUp(self):
        self._orig = cs._translator
        cs._cache.clear()
        cs._cache_loaded = True                   # skip the on-disk cache
        self._saved_persist = cs._persist_cache
        cs._persist_cache = lambda: None          # don't touch the cache file during tests

    def tearDown(self):
        set_translator(self._orig)
        cs._cache.clear()
        cs._persist_cache = self._saved_persist

    def test_translation_used_stripped_and_cached(self):
        calls = {"n": 0}

        def fake(py, lang):
            calls["n"] += 1
            return "#include <vector>\nstd::vector<int> bfs() { return {}; }"

        set_translator(fake)
        out1 = display_solution("bfs", "cpp")
        out2 = display_solution("bfs", "cpp")     # second call must hit the cache, not the translator
        self.assertIn("std::vector<int> bfs()", out1)
        self.assertNotIn("#include", out1)        # includes stripped for display
        self.assertEqual(out1, out2)
        self.assertEqual(calls["n"], 1)           # translated once, then cached

    def test_offline_translation_returns_none(self):
        set_translator(lambda py, lang: None)     # offline / failure
        self.assertIsNone(display_solution("bfs", "cpp"))
        self.assertIsNotNone(display_solution("bfs", "python"))   # python always available


if __name__ == "__main__":
    unittest.main()
