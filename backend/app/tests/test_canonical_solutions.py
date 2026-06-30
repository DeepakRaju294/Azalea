"""Build-time verification of the canonical displayed solutions (canonical_solutions.py).

The Python form is EXECUTED here so a wrong displayed implementation can never ship; the graph-MST ones are
also run through the A2 executor. Display forms are checked to carry no import/boilerplate lines."""
import unittest

from app.services.examples.canonical_solutions import (CANONICAL_SOLUTIONS, LANGUAGES, display_solutions,
                                                       python_executable)
from app.services.examples.code_execution_check import check_graph_topic_code


def _run(slug: str, call: str):
    ns: dict = {}
    exec(python_executable(slug), ns)          # noqa: S102 — our own trusted code, executed to verify it
    return eval(call, ns)                       # noqa: S307


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
        # 3 + 4 * 2 - 1  ==  3 + 8 - 1  ==  10  (multiply binds before add/subtract)
        self.assertEqual(_run("arithmetic_eval", "evaluate([3, '+', 4, '*', 2, '-', 1])"), 10)


class CanonicalMstViaExecutor(unittest.TestCase):
    """The two MST solutions are validated by the same A2 executor that guards displayed code."""
    def test_kruskal_is_a_valid_mst(self):
        self.assertEqual(check_graph_topic_code(python_executable("kruskal"), "kruskal").status, "ok")

    def test_prim_is_a_valid_mst(self):
        self.assertEqual(check_graph_topic_code(python_executable("prim"), "prim").status, "ok")


class DisplayStripsImports(unittest.TestCase):
    def test_every_slug_has_all_three_languages(self):
        for slug, sols in CANONICAL_SOLUTIONS.items():
            self.assertEqual(set(sols), set(LANGUAGES), slug)

    def test_display_has_no_import_or_boilerplate_lines(self):
        for slug in CANONICAL_SOLUTIONS:
            disp = display_solutions(slug)
            for line in disp["python"].splitlines():
                self.assertFalse(line.startswith(("import ", "from ")), f"{slug} py: {line}")
            for line in disp["cpp"].splitlines():
                self.assertFalse(line.startswith(("#include", "using namespace")), f"{slug} cpp: {line}")
            for line in disp["java"].splitlines():
                self.assertFalse(line.startswith("import "), f"{slug} java: {line}")

    def test_display_keeps_the_algorithm_body(self):
        # stripping imports must not gut the code — the def/signature survives
        self.assertIn("def bfs", display_solutions("bfs")["python"])
        self.assertIn("deque", display_solutions("bfs")["python"])     # still USES the facility


if __name__ == "__main__":
    unittest.main()
