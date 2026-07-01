"""T4 GATE PROOF (ADAPTER_DEVELOPMENT_SPEC §2.1). A type is "ready to scale" only after a SECOND adapter proves
the grammar survives a different state model. Binary search uses an integer window [lo,hi]; BST search uses a
tree node + `remaining` subtree — two state models, same T4 invariant (search space strictly shrinks). Includes
the fixed BST regression fixtures (found-after-left / found-after-right / absent)."""
import unittest

from app.services.examples.trace_adapters import ADAPTERS
from app.services.examples.trace_adapters.families.trees import BSTSearchAdapter, _insert
from app.services.examples.trace_adapters.manifest import by_type
from app.services.examples.trace_pipeline import select_instance

_ADAPTER = BSTSearchAdapter()


def _bst(values):
    tree, root = {}, None
    for v in values:
        root = _insert(tree, root, v)
    return tree, root


def _search(values, target):
    tree, root = _bst(values)
    return _ADAPTER.reference({"tree": tree, "root": root, "target": target, "insert_order": values})


class T4GateTwoStateModels(unittest.TestCase):
    def test_t4_has_binary_search_and_bst_search(self):
        self.assertEqual(set(by_type().get("T4", [])), {"binary_search", "bst_search"})

    def test_the_two_state_models_are_genuinely_different(self):
        arr = select_instance(ADAPTERS["binary_search"], seed=3).steps[0].state_after
        tree = select_instance(ADAPTERS["bst_search"], seed=3).steps[0].state_after
        self.assertIn("lo", arr)
        self.assertIn("hi", arr)                              # integer-window model
        self.assertIn("remaining", tree)
        self.assertNotIn("lo", tree)                          # tree-node model, not array bounds


class BSTSearchFixtures(unittest.TestCase):
    # tree from inserting [10, 5, 15, 3, 7, 12, 20]
    _VALUES = [10, 5, 15, 3, 7, 12, 20]

    def _shrinks(self, trace):
        rem = [s.state_after["remaining"] for s in trace.steps]
        self.assertTrue(all(b <= a for a, b in zip(rem, rem[1:])), rem)   # never grows
        self.assertEqual(rem[-1], 0)                                      # exhausted at the end

    def test_found_after_left(self):
        tr = _search(self._VALUES, 3)                         # 3 < 10 -> left, 3 < 5 -> left, found
        self.assertTrue(tr.final_answer["found"])
        self.assertEqual(tr.final_answer["found_at"], 3)
        self.assertTrue(tr.case_evidence.get("go_left"))
        self._shrinks(tr)

    def test_found_after_right(self):
        tr = _search(self._VALUES, 20)                        # 20 > 10 -> right, 20 > 15 -> right, found
        self.assertTrue(tr.final_answer["found"])
        self.assertEqual(tr.final_answer["found_at"], 20)
        self.assertTrue(tr.case_evidence.get("go_right"))
        self._shrinks(tr)

    def test_absent(self):
        tr = _search(self._VALUES, 8)                         # 8<10->L, 8>5->R, 8>7->R null -> absent
        self.assertFalse(tr.final_answer["found"])
        self.assertIsNone(tr.final_answer["found_at"])
        self.assertTrue(tr.case_evidence.get("absent"))
        self._shrinks(tr)


if __name__ == "__main__":
    unittest.main()
