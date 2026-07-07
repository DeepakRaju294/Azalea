"""Free-text validation vertical slice (FREE_TEXT_CONTENT_VALIDATION_SPEC.md §6/§7).

The §6 slice end-to-end (declared square_both_sides on x²=−4 refuted on target conformance → optional span deleted,
siblings survive, no fallback restores it), plus guard cases proving the mechanics aren't hardcoded to the one
fixture: a valid equivalence transform passes, an undeclared step is indeterminate, surface/metadata operation and
relation mismatches fail closed with the typed null-field state, generator-authored metadata is ignored as
authority, and metadata-only requires registered backend provenance.

Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_free_text_slice
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.free_text import binding as bindmod
from app.services.free_text import relations, transformation, validator


def _prov():
    return bindmod.BindingProvenance(
        binding_source=bindmod.REGISTERED_BACKEND_SOURCE,
        binding_source_id="algebra_ops", binding_source_version="v1", binding_field="transformation",
    )


class Relations(unittest.TestCase):
    def test_parse_unicode_relation(self):
        rel = relations.parse_relation("x² = −4")
        self.assertIsNotNone(rel)
        self.assertTrue(relations.relations_equal(rel, relations.parse_relation("x^2 = -4")))

    def test_square_both_sides_canonical_output(self):
        rel = relations.parse_relation("x² = −4")
        out = relations.get_operation("square_both_sides").apply(rel)
        self.assertTrue(relations.relations_equal(out, relations.parse_relation("x⁴ = 16")))
        self.assertFalse(relations.relations_equal(out, relations.parse_relation("x² = 0")))

    def test_orientation_and_scale_independent_equality(self):
        self.assertTrue(relations.relations_equal(
            relations.parse_relation("x⁴ = 16"), relations.parse_relation("16 = x⁴")))
        self.assertTrue(relations.relations_equal(
            relations.parse_relation("2x = 6"), relations.parse_relation("x = 3")))


class Transformation(unittest.TestCase):
    def test_l2_rejects_invalid_symbolic_transformation(self):
        span = bindmod.SpanInput(text="Squaring both sides of x² = −4 gives x² = 0.")
        tr = transformation.validate_transformation(span)
        self.assertEqual(tr.verdict, transformation.VERDICT_REFUTED)
        self.assertEqual(tr.transformation_failure_stage, bindmod.STAGE_TARGET_CONFORMANCE)
        self.assertTrue(relations.relations_equal(
            tr.canonical_output_relation, relations.parse_relation("x⁴ = 16")))
        self.assertEqual(tr.binding.surfaced_operation_id, "square_both_sides")

    def test_l2_equivalence_transform_passes(self):
        span = bindmod.SpanInput(text="Subtracting 2 from both sides of x + 2 = 5 gives x = 3.")
        tr = transformation.validate_transformation(span)
        self.assertEqual(tr.verdict, transformation.VERDICT_PASS)
        self.assertEqual(tr.target_conformance, transformation.CONF_PASS)

    def test_l2_undeclared_operation_is_indeterminate(self):
        span = bindmod.SpanInput(text="Since x + 2 = 5, we get x = 3.")
        tr = transformation.validate_transformation(span)
        self.assertEqual(tr.verdict, transformation.VERDICT_INDETERMINATE)
        self.assertFalse(tr.binding.is_transformation)

    def test_l2_accepts_declared_necessary_condition(self):
        b = bindmod.BackendBinding(provenance=_prov(), operation_id="square_both_sides",
                                   relation_mode=transformation.NECESSARY_CONDITION)
        span = bindmod.SpanInput(
            text="Squaring both sides of x = 2 gives a necessary condition: x² = 4.", backend_binding=b)
        tr = transformation.validate_transformation(span)
        self.assertEqual(tr.verdict, transformation.VERDICT_PASS)
        self.assertEqual(tr.relation_mode_conformance, transformation.CONF_PASS)

    def test_l2_rejects_one_way_transform_rendered_as_equivalence(self):
        b = bindmod.BackendBinding(provenance=_prov(), operation_id="square_both_sides",
                                   relation_mode=transformation.EQUIVALENCE)
        span = bindmod.SpanInput(text="Squaring both sides of x = 2 gives x² = 4.", backend_binding=b)
        tr = transformation.validate_transformation(span)
        self.assertEqual(tr.verdict, transformation.VERDICT_REFUTED)
        self.assertEqual(tr.transformation_failure_stage, bindmod.STAGE_RELATION_MODE)


class BindingConformance(unittest.TestCase):
    def test_l2_rejects_surface_operation_metadata_mismatch(self):
        b = bindmod.BackendBinding(provenance=_prov(), operation_id="subtract_2_from_both_sides")
        span = bindmod.SpanInput(
            text="Dividing both sides by 2 of x + 2 = 5 gives x = 3.", backend_binding=b)
        tr = transformation.validate_transformation(span)
        self.assertEqual(tr.verdict, transformation.VERDICT_REFUTED)
        self.assertEqual(tr.binding.binding_conformance, bindmod.FAIL)
        self.assertEqual(tr.transformation_failure_stage, bindmod.STAGE_OPERATION_BINDING)
        # typed null state: a failed operation bind exposes no resolved op and no canonical output
        self.assertIsNone(tr.binding.resolved_operation_id)
        self.assertIsNone(tr.canonical_output_relation)
        self.assertEqual(tr.target_conformance, transformation.CONF_UNEVALUATED)

    def test_l2_rejects_surface_relation_metadata_mismatch(self):
        b = bindmod.BackendBinding(provenance=_prov(), operation_id="subtract_2_from_both_sides",
                                   source_relation="x + 2 = 5", target_relation="x = 3")
        span = bindmod.SpanInput(
            text="Subtracting 2 from both sides of x + 3 = 5 gives x = 3.", backend_binding=b)
        tr = transformation.validate_transformation(span)
        self.assertEqual(tr.verdict, transformation.VERDICT_REFUTED)
        self.assertEqual(tr.binding.relation_binding_conformance, bindmod.FAIL)
        self.assertEqual(tr.transformation_failure_stage, bindmod.STAGE_RELATION_BINDING)
        # operation bind passed → resolved op may be retained, but canonical output is still not produced
        self.assertEqual(tr.binding.resolved_operation_id, "subtract_2_from_both_sides")
        self.assertIsNone(tr.canonical_output_relation)

    def test_l2_rejects_generator_authored_operation_metadata(self):
        # generator claims a validating contract; there is NO backend_binding → it must be ignored as authority
        span = bindmod.SpanInput(
            text="Squaring both sides of x² = −4 gives x² = 0.",
            generator_metadata={"operation_id": "square_both_sides", "target_relation": "x² = 0",
                                "relation_mode": "equivalence"},
        )
        tr = transformation.validate_transformation(span)
        self.assertEqual(tr.verdict, transformation.VERDICT_REFUTED)  # still refuted on the surfaced truth
        self.assertEqual(tr.binding.binding_provenance.binding_source, bindmod.SURFACED_EXTRACTION)

    def test_metadata_only_requires_registered_backend_provenance(self):
        text = "The step takes x + 2 = 5 to x = 3."
        good = bindmod.BackendBinding(provenance=_prov(), operation_id="subtract_2_from_both_sides",
                                      source_relation="x + 2 = 5", target_relation="x = 3")
        tr_ok = transformation.validate_transformation(
            bindmod.SpanInput(text=text, backend_binding=good, allow_metadata_backed=True))
        self.assertEqual(tr_ok.verdict, transformation.VERDICT_PASS)
        self.assertEqual(tr_ok.binding.binding_conformance, bindmod.METADATA_ONLY)

        # missing/invalid backend provenance → hard failure, never a silent unvalidated pass
        bad = bindmod.BackendBinding(
            provenance=bindmod.BindingProvenance(binding_source=bindmod.SURFACED_EXTRACTION),
            operation_id="subtract_2_from_both_sides", source_relation="x + 2 = 5", target_relation="x = 3")
        tr_bad = transformation.validate_transformation(
            bindmod.SpanInput(text=text, backend_binding=bad, allow_metadata_backed=True))
        self.assertEqual(tr_bad.verdict, transformation.VERDICT_REFUTED)
        self.assertTrue(tr_bad.binding.hard_routing_failure)
        self.assertIsNone(tr_bad.canonical_output_relation)


class SliceDisposition(unittest.TestCase):
    FIELD = ("A quadratic can have no real solution. "
             "Squaring both sides of x² = −4 gives x² = 0. "
             "Such equations still matter in physics.")

    def test_optional_span_deleted_siblings_survive(self):
        result = validator.validate_field(
            self.FIELD, requirements={"c1": validator.OPTIONAL})
        self.assertEqual(result.field_decision, validator.SOFTEN)
        # the false claim is gone…
        self.assertNotIn("x² = 0", result.field_text_out)
        self.assertNotIn("Squaring both sides", result.field_text_out)
        # …and the valid sibling sentences survive
        self.assertIn("no real solution", result.field_text_out)
        self.assertIn("matter in physics", result.field_text_out)
        # retries were exhausted before deletion; no fallback restored the text
        deleted = [s for s in result.spans if s.decision == "delete"]
        self.assertEqual(len(deleted), 1)
        self.assertEqual(deleted[0].retry_count, validator.MAX_REPAIRS)

    def test_required_span_withholds_field(self):
        result = validator.validate_field(
            self.FIELD, requirements={"c1": validator.REQUIRED})
        self.assertEqual(result.field_decision, validator.WITHHOLD)
        self.assertEqual(result.field_text_out, "")   # no placeholder, no fallback

    def test_no_fallback_restores_a_repaired_claim(self):
        # even a repair_fn that "fixes" by returning the SAME false text must not resurrect the claim
        result = validator.validate_field(
            self.FIELD, requirements={"c1": validator.OPTIONAL},
            repair_fn=lambda t: t)  # useless repair
        self.assertEqual(result.field_decision, validator.SOFTEN)
        self.assertNotIn("x² = 0", result.field_text_out)


if __name__ == "__main__":
    unittest.main()
