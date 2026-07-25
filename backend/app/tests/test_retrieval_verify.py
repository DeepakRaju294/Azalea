"""Offline tests for the retrieval-verification core (Phase 0). No API key, no retrieval — they pin the
reproduction-check decision logic: it accepts a produced answer that reproduces a published one (through
display rounding, scientific notation, and unit-convention differences) and rejects a real numeric error,
and it stays INDECISIVE (never a false 'wrong') when a magnitude can't be extracted."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples.retrieval_verify import (
    KNOWN_ANSWER_FIXTURES, extract_magnitude, extract_unit, reproduction_check,
)


class ExtractMagnitude(unittest.TestCase):
    def test_plain_and_unit(self):
        self.assertEqual(extract_magnitude("100 V"), 100.0)
        self.assertEqual(extract_magnitude("9 J"), 9.0)

    def test_scientific_notation_variants(self):
        for s in ("8.99e9 N", "8.99 x 10^9 N", "8.99 * 10 ** 9", "8.99E9"):
            self.assertEqual(extract_magnitude(s), 8.99e9, s)

    def test_thousands_separator(self):
        self.assertEqual(extract_magnitude("1,102.50"), 1102.5)

    def test_no_number(self):
        self.assertIsNone(extract_magnitude("undefined"))

    def test_unit_token(self):
        self.assertEqual(extract_unit("100 V"), "V")
        self.assertEqual(extract_unit("9.98e4 Pa"), "Pa")
        self.assertEqual(extract_unit("42"), "")


class ReproductionCheck(unittest.TestCase):
    def test_exact_match(self):
        self.assertTrue(reproduction_check("1.0 V", "1 V").matched)

    def test_display_rounding_matches(self):
        # 9.98e4 Pa (published, rounded) vs 99768 Pa (our exact) — same quantity, must pass.
        r = reproduction_check("9.98e4 Pa", "99768 Pa")
        self.assertTrue(r.matched, r.detail)

    def test_scientific_notation_matches(self):
        self.assertTrue(reproduction_check("8.99e9 N", "8.99 x 10^9 N").matched)

    def test_percent_fraction_convention_matches(self):
        # same quantity, different convention (8.33 vs 0.0833) — accepted in a unit-free numeric context.
        self.assertTrue(reproduction_check("8.33", "0.0833", require_unit_match=False).matched)

    def test_real_error_rejected(self):
        # off by ~10% — a genuine wrong answer, must NOT be accepted.
        r = reproduction_check("100 V", "90 V")
        self.assertFalse(r.matched)
        self.assertIn("mismatch", r.detail)

    def test_off_by_one_rejected(self):
        self.assertFalse(reproduction_check("42", "41", require_unit_match=False).matched)

    def test_indecisive_when_no_magnitude(self):
        # a non-numeric produced answer is INDECISIVE (None), never a false 'wrong' — so abstention, not a
        # wrong-answer verdict, is what a caller sees.
        r = reproduction_check("100 V", "see explanation")
        self.assertIsNone(r.matched)
        self.assertFalse(r.decisive)

    def test_unit_mismatch_REFUTES_even_when_magnitude_agrees(self):
        # 1 V vs 1 A: magnitude agrees but the physical quantity is wrong — REFUTED, not confirmed
        # (external review issue 13: a magnitude match with the wrong unit is not a reproduction).
        r = reproduction_check("1 V", "1 A")
        self.assertFalse(r.matched)
        self.assertEqual(r.unit_status, "mismatch")
        self.assertIn("refuted", r.detail)

    def test_unit_match_confirms(self):
        r = reproduction_check("100 V", "100 V")
        self.assertTrue(r.matched)
        self.assertEqual(r.unit_status, "match")

    def test_unknown_unit_is_indecisive_by_default(self):
        # magnitude agrees but the produced side carries no unit — INDECISIVE under the safe default, never a
        # silent pass. A trusted unit-free context can opt out via require_unit_match=False.
        r = reproduction_check("100 V", "100")
        self.assertIsNone(r.matched)
        self.assertEqual(r.unit_status, "unknown")
        self.assertTrue(reproduction_check("100 V", "100", require_unit_match=False).matched)


class Fixtures(unittest.TestCase):
    def test_every_fixture_answer_is_reproducible_from_its_own_formula(self):
        # Sanity gate on the FIXTURES themselves: evaluating each canonical formula on hand-substituted inputs
        # reproduces the stated published answer. This proves the fixtures are internally correct BEFORE they
        # are ever used to judge the live solver (a wrong fixture would silently corrupt the go/no-go).
        import math  # noqa: F401 — available to eval'd formulas if ever needed
        env = {
            "motional_emf": dict(B=0.5, L=0.2, v=10),
            "faraday_emf": dict(N=200, dPhi=0.05, dt=0.1),
            "inductor_energy": dict(L=2, I=3),
            "rl_time_constant": dict(L=10, R=5),
            "capacitor_energy": dict(C=2, V=3),
            "coulomb_force": dict(k=8.99e9, q1=1, q2=1, r=1),
            "kinetic_energy": dict(m=2, v=3),
            "ohms_law": dict(V=12, R=4),
            "compound_interest": dict(P=1000, r=0.05, t=2),
            "ideal_gas_pressure": dict(n=1, R=8.314, T=300, Vol=0.025),
        }
        for fx in KNOWN_ANSWER_FIXTURES:
            rhs = fx.canonical_formula.split("=", 1)[1].strip()
            value = eval(rhs, {"__builtins__": {}}, dict(env[fx.concept]))  # noqa: S307 — fixed local test data
            # the computed value is unit-free by construction, so compare magnitude only here.
            r = reproduction_check(fx.known_answer, str(value), require_unit_match=False)
            self.assertTrue(r.matched, f"{fx.concept}: computed {value} vs published {fx.known_answer} ({r.detail})")

    def test_fixture_domains_are_diverse(self):
        self.assertGreaterEqual(len({fx.domain for fx in KNOWN_ANSWER_FIXTURES}), 4)


if __name__ == "__main__":
    unittest.main()
