"""Scalable-adapters infra, Phase 2: the tree order-traversals (T1) are now DECLARATIONS hydrated from a type
template (types/t1_traversal.py), not hand-written classes. This locks that migration: they are registered,
carry the right type, hydrate cleanly, and produce contract-valid traces. (Byte-identical-to-the-old-classes
was verified at migration time against a golden; the full ADAPTERS gauntlet in the other suites covers
ongoing correctness.)"""
import unittest

from app.services.examples import trace_pipeline as tp
from app.services.examples.trace_adapters import ADAPTERS
from app.services.examples.trace_adapters.decl import AdapterDecl, hydrate
from app.services.examples.trace_adapters.manifest import MANIFEST
from app.services.examples.trace_adapters.types.t1_traversal import DECLARATIONS
from app.services.examples.trace_contract import structural_invariants, visual_contract_violations


class DeclaredAdapters(unittest.TestCase):
    def test_t1_traversals_are_declarations(self):
        slugs = {d.slug for d in DECLARATIONS}
        # t1_traversal owns the template-built order-traversals + inorder + the graph traversals (all T1)
        self.assertTrue({"tree_preorder", "tree_postorder", "tree_levelorder", "tree_inorder",
                         "bfs", "dfs_iter"} <= slugs)
        for d in DECLARATIONS:
            self.assertIsInstance(d, AdapterDecl)
            self.assertEqual(d.type, "T1")
            self.assertEqual(MANIFEST[d.slug]["type"], "T1")     # declaration + manifest agree on type

    def test_registered_and_contract_valid(self):
        for d in DECLARATIONS:
            self.assertIn(d.slug, ADAPTERS)
            adapter = ADAPTERS[d.slug]
            self.assertEqual(adapter.slug, d.slug)
            trace = tp.select_instance(adapter, seed=3)
            with self.subTest(slug=d.slug):
                self.assertIsNotNone(trace)
                self.assertEqual(structural_invariants(trace, adapter), [])
                self.assertEqual(visual_contract_violations(trace), [])

    def test_old_classes_are_gone(self):
        # the migrated sibling classes must no longer exist in the family module (single source = the decl)
        import app.services.examples.trace_adapters.families.trees as trees
        for name in ("PreorderTraversalAdapter", "PostorderTraversalAdapter", "LevelOrderTraversalAdapter"):
            self.assertFalse(hasattr(trees, name), f"{name} should have been removed after migration")

    def test_hydrate_is_idempotent_shape(self):
        a, b = hydrate(DECLARATIONS[0]), hydrate(DECLARATIONS[0])
        self.assertEqual(type(a).__name__, type(b).__name__)
        self.assertEqual(a.slug, b.slug)


if __name__ == "__main__":
    unittest.main()
