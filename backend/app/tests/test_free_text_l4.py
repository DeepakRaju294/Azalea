"""Q24-d rungs — establishment resolver, L4 bounded verifier, L3 sibling-trace binding (§3/§4/§7).

Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_free_text_l4
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.free_text import establishment, evidence, l3_sibling, l4_verifier


def _pack():
    return evidence.FactPack(
        fact_pack_id="cs_ds", fact_pack_version="v2", definition_registry_version="v5",
        definitions=(evidence.RegisteredDefinition("def_stack_lifo", "a stack is lifo"),),
        rules=(evidence.FactPackRule("rule_stack_not_fifo", "a stack is fifo", evidence.DENY),),
    )


class Establishment(unittest.TestCase):
    def test_registered_definition_establishes(self):
        e = establishment.resolve_establishment("A stack is LIFO.", fact_pack=_pack())
        self.assertEqual(e.status, establishment.ESTABLISHED)
        self.assertEqual(e.basis, establishment.REGISTERED_DEFINITION)
        self.assertIn("def_stack_lifo", e.evidence_ids)

    def test_l2_proof_establishes_symbolic(self):
        e = establishment.resolve_establishment("Subtracting 2 gives x = 3.", l2_proven=True)
        self.assertEqual(e.basis, establishment.DETERMINISTIC_SYMBOLIC_TRANSFORMATION)

    def test_unmatched_claim_is_not_established(self):
        e = establishment.resolve_establishment("A stack is great for undo history.", fact_pack=_pack())
        self.assertEqual(e.status, establishment.NOT_ESTABLISHED)
        self.assertEqual(e.basis, establishment.NONE)


class L4(unittest.TestCase):
    def test_l4_refutes_against_deny_rule_with_evidence(self):
        r = l4_verifier.verify("A stack is FIFO.", l4_verifier.FACTUAL, fact_pack=_pack())
        self.assertEqual(r.verdict, l4_verifier.REFUTED)
        self.assertIn("rule_stack_not_fifo", r.evidence_ids)

    def test_l4_refuted_verdict_is_reproducible(self):
        p = _pack()
        a = l4_verifier.verify("A stack is FIFO.", l4_verifier.FACTUAL, fact_pack=p)
        b = l4_verifier.verify("A stack is FIFO.", l4_verifier.FACTUAL, fact_pack=p)
        self.assertEqual(a, b)
        self.assertEqual(a.evidence_context.fact_pack_version, "v2")

    def test_l4_factual_unmatched_is_unsupported_not_no_objection(self):
        r = l4_verifier.verify("A stack is great for undo history.", l4_verifier.FACTUAL, fact_pack=_pack())
        self.assertEqual(r.verdict, l4_verifier.UNSUPPORTED)
        self.assertEqual(r.unsupported_reason, l4_verifier.NO_MATCHING_EVIDENCE)

    def test_l4_no_objection_only_for_eligible_classes(self):
        framing = l4_verifier.verify("This idea is worth appreciating.",
                                     l4_verifier.NON_FACTUAL_FRAMING, fact_pack=_pack())
        self.assertEqual(framing.verdict, l4_verifier.NA)
        carried = l4_verifier.verify("The result is 20 N.", l4_verifier.FACTUAL, fact_pack=_pack(),
                                     content_ownership=l4_verifier.DETERMINISTIC_CARRIED_ELSEWHERE)
        self.assertEqual(carried.verdict, l4_verifier.NO_OBJECTION)

    def test_l4_unavailable_is_not_a_clean_pass(self):
        r = l4_verifier.verify("A stack is FIFO.", l4_verifier.FACTUAL, fact_pack=_pack(),
                               verifier_available=False)
        self.assertEqual(r.verdict, l4_verifier.UNAVAILABLE)

    def test_l4_missing_pack_holds_family(self):
        r = l4_verifier.verify("Some domain claim.", l4_verifier.FACTUAL, fact_pack=None)
        self.assertEqual(r.verdict, l4_verifier.UNSUPPORTED)
        self.assertEqual(r.unsupported_reason, l4_verifier.EVIDENCE_PACK_MISSING_FOR_DOMAIN)


class L3Binding(unittest.TestCase):
    FACTS = (l3_sibling.SiblingFact("t1", "s1", "net force", "20", "N"),)

    def test_l3_does_not_bind_general_rule_to_example_values(self):
        # a general F=ma definition beside a 20 N example is NOT forced to restate the example value
        r = l3_sibling.check_sibling_consistency(
            "F = ma relates force, mass, and acceleration.", self.FACTS)
        self.assertEqual(r.binding_class, l3_sibling.TOPIC_GENERAL_RULE)
        self.assertEqual(r.c1_values, l3_sibling.NOT_APPLICABLE)
        self.assertEqual(r.status, l3_sibling.PASS)

    def test_l3_rejects_contradicting_sibling_example(self):
        r = l3_sibling.check_sibling_consistency(
            "In this example the net force is 25 N.", self.FACTS)
        self.assertEqual(r.binding_class, l3_sibling.EXPLICIT_EXAMPLE_REFERENCE)
        self.assertEqual(r.c1_values, l3_sibling.FAIL)
        self.assertEqual(r.status, l3_sibling.FAIL)

    def test_l3_accepts_consistent_sibling_reference(self):
        r = l3_sibling.check_sibling_consistency(
            "In this example the net force is 20 N.", self.FACTS)
        self.assertEqual(r.c1_values, l3_sibling.PASS)
        self.assertEqual(r.status, l3_sibling.PASS)

    def test_l3_forbidden_claim_flows_through_shared_c2(self):
        from app.services.trace_teaching import grammar as g
        fc = (g.ForbiddenClaim("direction_reversal", "object",
                               {"trace_field": "motion_direction", "equals": "unchanged"},
                               ("reverses", "moves backward")),)
        r = l3_sibling.check_sibling_consistency(
            "Here the object reverses at 20 N.", self.FACTS,
            forbidden_claims=fc, trace_field_values={"motion_direction": "unchanged"})
        self.assertEqual(r.c2_forbidden, l3_sibling.FAIL)
        self.assertEqual(r.status, l3_sibling.FAIL)

    def test_l3_operation_mismatch_flows_through_shared_c5(self):
        from app.services.trace_teaching import grammar as g
        oc = g.OperationContract("substitute_known_values",
                                 ("substitute", "plug in"), ("solve for", "differentiate"))
        r = l3_sibling.check_sibling_consistency(
            "Here we solve for acceleration using 20 N.", self.FACTS,
            operation_contract=oc, action_bearing=True)
        self.assertEqual(r.c5_action, l3_sibling.FAIL)
        self.assertEqual(r.status, l3_sibling.FAIL)


if __name__ == "__main__":
    unittest.main()
