"""Q24 full-ladder orchestration (FREE_TEXT_CONTENT_VALIDATION_SPEC.md §3/§4).

Exercises segment → route → classify → L1/L2/L3/establishment/L4 → disposition as one FreeTextValidationResult,
and the shadow/enforce split. Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_free_text_orchestrator
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.free_text import (classify, evidence, l1_scope, l3_sibling, l4_verifier,
                                     orchestrator, routing, validator)
from app.services.free_text.orchestrator import FieldContext


def _math_pack():
    return evidence.FactPack(
        fact_pack_id="math", fact_pack_version="v1", definition_registry_version="v1",
        definitions=(evidence.RegisteredDefinition(
            "def_discriminant", "the discriminant determines the number of real roots"),),
    )


class Classifier(unittest.TestCase):
    def test_declarative_defaults_factual(self):
        self.assertEqual(classify.classify_claim("A stack is a data structure."), validator.FACTUAL)

    def test_framing_without_signal_is_non_factual(self):
        self.assertEqual(classify.classify_claim("This is genuinely worth appreciating."),
                         validator.NON_FACTUAL_FRAMING)

    def test_framing_with_checkable_signal_stays_factual(self):
        # "always" is a checkable absolute → factual even though it reads like framing
        self.assertEqual(classify.classify_claim("In practice this always terminates."), validator.FACTUAL)

    def test_question_is_prompt(self):
        self.assertEqual(classify.classify_claim("What is the discriminant?"), validator.PROMPT)


class FullLadder(unittest.TestCase):
    FIELD = ("A quadratic can have no real solution. "
             "Squaring both sides of x² = −4 gives x² = 0. "
             "This is genuinely worth appreciating.")

    def test_transformation_span_refuted_and_deleted(self):
        r = orchestrator.validate_field(
            "body", self.FIELD,
            FieldContext(requirements={"c1": routing.OPTIONAL}), mode=validator.ON_ENFORCED)
        self.assertEqual(r.field_decision, validator.SOFTEN)
        self.assertNotIn("x² = 0", r.field_text_out)
        c1 = [c for c in r.claims if c.claim_id == "c1"][0]
        self.assertEqual(c1.claim_class, validator.FACTUAL)
        self.assertEqual(c1.decision, orchestrator.ACTION_DELETE)

    def test_framing_span_ships_without_establishment(self):
        r = orchestrator.validate_field(
            "body", self.FIELD, FieldContext(requirements={"c1": routing.OPTIONAL}))
        c2 = [c for c in r.claims if c.claim_id == "c2"][0]
        self.assertEqual(c2.claim_class, validator.NON_FACTUAL_FRAMING)
        self.assertEqual(c2.decision, orchestrator.ACTION_SHIP)

    def test_unestablished_factual_optional_is_softened(self):
        # a plain factual sentence with no fact pack and no establishment basis is unsupported → deleted (optional)
        r = orchestrator.validate_field(
            "body", "A monad is a monoid in the category of endofunctors.",
            FieldContext(requirements={"c0": routing.OPTIONAL}))
        c0 = r.claims[0]
        self.assertEqual(c0.claim_class, validator.FACTUAL)
        self.assertEqual(c0.establishment.status, "not_established")
        self.assertEqual(c0.decision, orchestrator.ACTION_DELETE)
        self.assertEqual(r.field_decision, validator.SOFTEN)

    def test_established_factual_ships(self):
        r = orchestrator.validate_field(
            "body", "The discriminant determines the number of real roots.",
            FieldContext(fact_pack=_math_pack(), requirements={"c0": routing.REQUIRED}))
        c0 = r.claims[0]
        self.assertEqual(c0.establishment.status, "established")
        self.assertEqual(c0.decision, orchestrator.ACTION_SHIP)
        self.assertEqual(r.field_decision, validator.SHIP)

    def test_unestablished_required_withholds_field(self):
        r = orchestrator.validate_field(
            "body", "A stack is FIFO.",
            FieldContext(requirements={"c0": routing.REQUIRED}))
        self.assertEqual(r.field_decision, validator.WITHHOLD)
        self.assertEqual(r.field_text_out, "")

    def test_l1_out_of_scope_term_withholds_required(self):
        vocab = l1_scope.TopicVocabulary(
            assumed_prerequisite_terms=frozenset({"equation"}),
            technical_terms=frozenset({"hamiltonian"}))
        r = orchestrator.validate_field(
            "body", "The Hamiltonian governs it.",
            FieldContext(vocab=vocab, requirements={"c0": routing.REQUIRED}))
        c0 = r.claims[0]
        self.assertEqual(c0.l1.status, l1_scope.FAIL)
        self.assertEqual(r.field_decision, validator.WITHHOLD)

    def test_l3_contradiction_deletes_optional(self):
        facts = (l3_sibling.SiblingFact("t", "s", "net force", "20", "N"),)
        r = orchestrator.validate_field(
            "body", "In this example the net force is 25 N.",
            FieldContext(sibling_facts=facts, requirements={"c0": routing.OPTIONAL}))
        c0 = r.claims[0]
        self.assertEqual(c0.l3.status, l3_sibling.FAIL)
        self.assertEqual(c0.decision, orchestrator.ACTION_DELETE)


class ShadowVsEnforce(unittest.TestCase):
    FIELD = "Squaring both sides of x² = −4 gives x² = 0."

    def test_shadow_leaves_display_unchanged_but_computes_decision(self):
        r = orchestrator.validate_field(
            "body", self.FIELD, FieldContext(requirements={"c0": routing.OPTIONAL}),
            mode=validator.SHADOW_VALIDATE)
        self.assertEqual(r.field_text_out, self.FIELD)         # unchanged
        self.assertEqual(r.field_decision, validator.SOFTEN)   # but decision computed
        rows = r.telemetry(topic_id="t", card_type="concept_intuition")
        self.assertEqual(rows[0]["l2_verdict"], "refuted")
        self.assertEqual(rows[0]["transformation_failure_stage"], "target_conformance")

    def test_enforce_applies_disposition(self):
        r = orchestrator.validate_field(
            "body", self.FIELD, FieldContext(requirements={"c0": routing.OPTIONAL}),
            mode=validator.ON_ENFORCED)
        self.assertEqual(r.field_text_out, "")   # single span deleted → empty field → soften to nothing


if __name__ == "__main__":
    unittest.main()
