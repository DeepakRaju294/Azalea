"""Trace → Teaching C1–C6 (TRACE_TO_TEACHING_CONTRACT_SPEC.md §9/§16).

Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_trace_teaching
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.trace_teaching import checks, grammar, numeric
from app.services.trace_teaching import validator as ttv


def _newton_step():
    return grammar.Step(
        id="s3", operation="compute_force", expected_visible_result="F = 20 N",
        allowed_values=("4", "5", "20"),
        allowed_quantities=(
            grammar.AllowedQuantity("s3.mass", "mass", "4", "kg"),
            grammar.AllowedQuantity("s3.acceleration", "acceleration", "5", "m/s²"),
            grammar.AllowedQuantity("s3.force", "net force", "20", "N", output_name="F"),
        ),
        trace_field_values={"motion_direction": "unchanged"},
        forbidden_claims=(grammar.ForbiddenClaim(
            "direction_reversal", "object", {"trace_field": "motion_direction", "equals": "unchanged"},
            ("reverses", "changes direction", "moves backward")),),
        operation_contract=grammar.OperationContract(
            "substitute_known_values",
            ("substitute", "plug in", "replace variables"),
            ("solve for", "isolate variable", "differentiate", "integrate")),
    )


class Numeric(unittest.TestCase):
    def test_decimal_normalization(self):
        self.assertEqual(numeric.canonical_number("3"), numeric.canonical_number("3.0"))

    def test_unrecognized_token(self):
        self.assertTrue(numeric.extract_numbers("the value 2x3 is odd")[0].unrecognized)

    def test_identifier_not_numeric(self):
        self.assertEqual(numeric.extract_numbers("velocity v2 changes"), [])

    def test_value_unit_pair(self):
        pairs = numeric.extract_value_unit_pairs("the force is 20 N here")
        self.assertEqual(pairs[0][1], "N")


class C1(unittest.TestCase):
    def test_c1_rejects_invented_literal(self):
        r = checks.c1_value_containment("the net force is 25 N", _newton_step())
        self.assertEqual(r.status, checks.FAIL)
        self.assertEqual(r.detail, "invented_value")

    def test_c1_accepts_allowed_values(self):
        r = checks.c1_value_containment("substitute 4 and 5 to get 20", _newton_step())
        self.assertEqual(r.status, checks.PASS)

    def test_c1_rejects_unrecognized_numeric_token(self):
        r = checks.c1_value_containment("the answer is 2x3", _newton_step())
        self.assertEqual(r.status, checks.FAIL)
        self.assertEqual(r.detail, "unrecognized_numeric_token")


class C2(unittest.TestCase):
    def test_c2_rejects_direction_reversal(self):
        r = checks.c2_forbidden_claims("the object reverses at the top", _newton_step())
        self.assertEqual(r.status, checks.FAIL)

    def test_c2_passes_when_predicate_false(self):
        step = grammar.Step(id="s3", operation="x", trace_field_values={"motion_direction": "reversed"},
                            forbidden_claims=_newton_step().forbidden_claims)
        self.assertEqual(checks.c2_forbidden_claims("the object reverses", step).status, checks.PASS)


class C4(unittest.TestCase):
    def test_c4_rejects_unit_mutation(self):
        r = checks.c4_unit_fidelity("the net force is 20 kg", _newton_step())
        self.assertEqual(r.status, checks.FAIL)
        self.assertTrue(r.detail.startswith("unit_mutation"))
        self.assertEqual(r.quantity_id, "s3.force")

    def test_c4_multi_quantity_accepts_each_unit(self):
        r = checks.c4_unit_fidelity("mass 4 kg and acceleration 5 m/s² give 20 N", _newton_step())
        self.assertEqual(r.status, checks.PASS)

    def test_c4_quantity_attribution_ambiguous(self):
        step = grammar.Step(id="s2", operation="x", allowed_quantities=(
            grammar.AllowedQuantity("s2.vi", "initial velocity", "5", "m/s"),
            grammar.AllowedQuantity("s2.vf", "final velocity", "5", "m/s")))
        r = checks.c4_unit_fidelity("the speed is 5 m/s", step)
        self.assertEqual(r.status, checks.FAIL)
        self.assertEqual(r.detail, "quantity_attribution_ambiguous")
        self.assertEqual(set(r.candidate_quantity_ids), {"s2.vi", "s2.vf"})


class C5(unittest.TestCase):
    def test_c5_rejects_operation_mismatch(self):
        r = checks.c5_operation("now solve for acceleration", _newton_step().operation_contract)
        self.assertEqual(r.status, checks.FAIL)

    def test_c5_accepts_intent_synonym(self):
        r = checks.c5_operation("plug in the known values", _newton_step().operation_contract)
        self.assertEqual(r.status, checks.PASS)

    def test_c5_order_respected(self):
        req = ("identify_knowns", "substitute_known_values", "compute_force")
        self.assertEqual(checks.c5_order("compute_force", 2, req).status, checks.PASS)
        self.assertEqual(checks.c5_order("compute_force", 0, req).status, checks.FAIL)


class C3(unittest.TestCase):
    def test_c3_required_fact_repairable_with_id(self):
        step = grammar.Step(id="s3", operation="x", required_facts=(grammar.RequiredFact(
            "force_law_newton", "law", "force", "equals", "m*a",
            ("newton's second law", "f = m·a"), ("reasoning",)),))
        [r] = checks.c3_required_facts("reasoning", "we just multiply the numbers", step)
        self.assertEqual(r.status, checks.REPAIRABLE)
        self.assertEqual(r.fact_id, "force_law_newton")
        [ok] = checks.c3_required_facts("reasoning", "by Newton's second law we get this", step)
        self.assertEqual(ok.status, checks.PASS)


class C6(unittest.TestCase):
    def test_c6_rejects_semantic_contradiction(self):
        r = checks.c6_semantic("the velocity is negative", {}, judge=lambda p, f: checks.C6_REJECT)
        self.assertEqual(r.status, checks.FAIL)

    def test_c6_unavailable_is_not_applicable(self):
        r = checks.c6_semantic("anything", {})
        self.assertEqual(r.status, checks.NOT_APPLICABLE)


class Validator(unittest.TestCase):
    def test_all_deterministic_failures_returned(self):
        # invented literal (C1) + unit mutation (C4) + operation mismatch (C5) in one action-bearing field
        r = ttv.run_checks("solve for acceleration to get 25 kg", _newton_step(),
                           field_name="reasoning", action_bearing=True)
        checks_failed = {f.check for f in r.failures}
        self.assertIn("C1", checks_failed)
        self.assertIn("C4", checks_failed)
        self.assertIn("C5", checks_failed)
        self.assertEqual(r.decision, ttv.WITHHOLD)

    def test_c6_skipped_when_deterministic_failure(self):
        r = ttv.run_checks("the force is 25 N", _newton_step(), field_name="reasoning",
                           judge=lambda p, f: checks.C6_REJECT)
        self.assertEqual(r.c6.status, checks.NOT_APPLICABLE)   # not run because C1 hard-failed

    def test_clean_field_passes_and_runs_c6(self):
        r = ttv.run_checks("substitute 4 and 5 to compute 20 N", _newton_step(),
                           field_name="reasoning", action_bearing=True,
                           judge=lambda p, f: checks.C6_PASS)
        self.assertEqual(r.decision, ttv.PASS)
        self.assertEqual(r.c6.status, checks.PASS)

    def test_c3_suppressed_when_field_unparsable(self):
        step = grammar.Step(id="s3", operation="x", allowed_values=("20",),
                            required_facts=(grammar.RequiredFact(
                                "law", "law", "f", "eq", "ma", ("newton's law",), ("reasoning",)),))
        r = ttv.run_checks("the answer is 2x3", step, field_name="reasoning", required_field=True)
        c1_fail = [f for f in r.failures if f.check == "C1"][0]
        c3_fail = [f for f in r.failures if f.check == "C3"][0]
        self.assertEqual(c1_fail.failure_class, ttv.PRIMARY)
        self.assertEqual(c3_fail.failure_class, ttv.SUPPRESSED)


if __name__ == "__main__":
    unittest.main()
