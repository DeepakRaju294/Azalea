"""T14 Table-Evaluation Engine type gate. The engine fills a truth table cell by cell; this proves, for EVERY spec
across seeds, that (1) the trace is structurally valid + a teaching trace, (2) select_instance accepts it, (3) the
extracted output column equals an INDEPENDENT recompute, and (4) the table is EXHAUSTIVE (exactly 2^n distinct
input rows — the T14 invariant) and every cell equals its local rule.

Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_table_engine
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples import trace_pipeline as tp
from app.services.examples.trace_adapters.decl import hydrate
from app.services.examples.trace_adapters.families import table_engine as te
from app.services.examples.trace_adapters.families.table_engine import registered_specs, table_decl, _assignments


class TableUnit(unittest.TestCase):
    def test_and_or_column(self):
        [spec] = [s for s in registered_specs() if s.slug == "truth_table_and_or"]
        # A AND (B OR C) over ABC in binary order 000..111
        self.assertEqual(spec.column(), [0, 0, 0, 0, 0, 1, 1, 1])

    def test_xor_column(self):
        [spec] = [s for s in registered_specs() if s.slug == "truth_table_xor"]
        self.assertEqual(spec.column(), [0, 1, 1, 0])


class TableEngineGate(unittest.TestCase):
    def _adapter(self, spec):
        return hydrate(table_decl(spec))

    def test_every_spec_produces_a_valid_teaching_trace(self):
        for spec in registered_specs():
            a = self._adapter(spec)
            with self.subTest(slug=spec.slug):
                for seed in range(8):
                    tr = tp.select_instance(a, seed=seed)
                    self.assertIsNotNone(tr, f"{spec.slug}: no trace at seed {seed}")
                    self.assertEqual(tp.structural_invariants(tr, a), [], f"{spec.slug}: structural not clean")
                    self.assertTrue(a.is_teaching_trace(tr))

    def test_output_column_matches_independent_recompute(self):
        for spec in registered_specs():
            a = self._adapter(spec)
            with self.subTest(slug=spec.slug):
                tr = tp.select_instance(a, seed=0)
                self.assertEqual(tr.final_answer, spec.oracle({}))

    def test_table_is_exhaustive(self):
        # the T14 invariant: exactly 2^n distinct input rows, one fill_row step each
        for spec in registered_specs():
            with self.subTest(slug=spec.slug):
                a = self._adapter(spec)
                tr = tp.select_instance(a, seed=0)
                fill_rows = [s for s in tr.steps if s.operation == "fill_row"]
                self.assertEqual(len(fill_rows), 2 ** len(spec.variables))
                self.assertEqual(len({tuple(sorted(x.items())) for x in _assignments(spec.variables)}),
                                 2 ** len(spec.variables))


if __name__ == "__main__":
    unittest.main()
