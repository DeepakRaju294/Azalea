"""AnswerComparison-driven comparison engine tests (offline). Honors the comparison KIND + unit contract, and
returns INDECISIVE (never a false confirm) for forms v1 can't judge."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples.retrieval.compare import compare_answer
from app.services.examples.retrieval.model import AnswerComparison


def _cmp(kind="relative_tolerance", tol="0.01", dim="V", unit="V", semantics="absolute", allowed=None):
    return AnswerComparison(kind=kind, quantity_kind=dim, unit_dimension=dim, unit_semantics=semantics,
                            allowed_units=tuple(allowed) if allowed is not None else (unit,), tolerance=tol)


class Compare(unittest.TestCase):
    def test_relative_tolerance_confirm(self):
        self.assertEqual(compare_answer("100 V", "100.5 V", _cmp(tol="0.01")).status, "confirm")

    def test_relative_tolerance_refute(self):
        self.assertEqual(compare_answer("100 V", "110 V", _cmp(tol="0.01")).status, "refute")

    def test_absolute_tolerance(self):
        self.assertEqual(compare_answer("100 V", "100.4 V", _cmp(kind="absolute_tolerance", tol="0.5")).status,
                         "confirm")
        self.assertEqual(compare_answer("100 V", "101 V", _cmp(kind="absolute_tolerance", tol="0.5")).status,
                         "refute")

    def test_exact_numeric_rejects_rounding_slack(self):
        # exact -> only a tiny floor; 100 vs 100.5 is NOT exact
        self.assertEqual(compare_answer("100 V", "100.5 V", _cmp(kind="exact_numeric", tol=None)).status, "refute")
        self.assertEqual(compare_answer("100 V", "100 V", _cmp(kind="exact_numeric", tol=None)).status, "confirm")

    def test_unit_mismatch_refutes(self):
        self.assertEqual(compare_answer("1 J", "1 W", _cmp(dim="J", unit="J")).status, "refute")

    def test_allowed_units_accepted(self):
        self.assertEqual(compare_answer("10 J", "10 N*m", _cmp(dim="J", allowed=["J", "N"])).status, "confirm")

    def test_dimensionless_ignores_unit(self):
        self.assertEqual(compare_answer("0.5", "0.5", _cmp(dim="", semantics="dimensionless")).status, "confirm")

    def test_unknown_unit_indecisive(self):
        self.assertEqual(compare_answer("100 V", "100", _cmp(dim="V")).status, "indecisive")

    def test_non_numeric_indecisive(self):
        self.assertEqual(compare_answer("100 V", "see explanation", _cmp()).status, "indecisive")

    def test_unsupported_kinds_are_indecisive_never_confirm(self):
        for kind in ("unordered_set", "interval", "symbolic_equivalence", "vector", "complex", "angle_mod_2pi"):
            self.assertEqual(compare_answer("x", "x", _cmp(kind=kind)).status, "indecisive", kind)


if __name__ == "__main__":
    unittest.main()
