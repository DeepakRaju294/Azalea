"""Phase 1A offline tests (RETRIEVAL_GROUNDED_EXAMPLE_SPEC §5.1/§15). No API key, no retrieval, no delivery.

Covers the frozen-schema invariants and the acceptance tests implementable at 1A: canonical fingerprint
collision-prevention + equal/differ matrix (A56/A59/A60), evidence-reference integrity (A47–A49/A57), the
per-level evidence policy + confirm/refute conflict rule, and the Slice-1A assurance pipeline.
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples.retrieval.fingerprints import (
    CanonicalizationError, build_instance_fingerprints, hash_canonical, make_evidence_subject,
)
from app.services.examples.retrieval.model import (
    AnswerComparison, AssuranceStrength, EvidenceIntegrityError, EvidenceRecord, EvidenceRevocation,
    InstanceAssuranceDecision, InstanceAssuranceProfile, InstanceAssumption, PublishedInstance,
    VerifierDependency,
)
from app.services.examples.retrieval.slice1a import (
    ASSURANCE_POLICY_VERSION, REPRO_CHECK_CONTRACT_VERSION, REPRO_VERIFIER_VERSION, run_slice1a,
)
from app.services.examples.retrieval.validate import derive_instance_assurance, validate_assurance_decision


def _cmp(**kw):
    base = dict(kind="relative_tolerance", quantity_kind="voltage", unit_dimension="V",
                unit_semantics="absolute", allowed_units=("V",), tolerance="0.01")
    base.update(kw)
    return AnswerComparison(**base)


def _inst(*, answer="1.0 V", target="emf", inputs=(("B", 0.5), ("L", 0.2), ("v", 10.0)),
          problem="A rod of length 0.2 m moves at 10 m/s through 0.5 T.", comparison=None, assumptions=()):
    return PublishedInstance(problem_statement=problem, inputs=tuple(inputs), target=target,
                             published_answer=answer, comparison=comparison or _cmp(),
                             assumptions=tuple(assumptions))


class CanonicalHash(unittest.TestCase):
    def test_deterministic_and_key_order_independent(self):
        a = hash_canonical({"x": 1, "y": 2}, schema="t/v1")
        b = hash_canonical({"y": 2, "x": 1}, schema="t/v1")
        self.assertEqual(a, b)

    def test_schema_namespace_prevents_cross_kind_collision(self):
        # identical fields, different schema -> different hash (spec §5 collision rule)
        self.assertNotEqual(hash_canonical({"v": 1}, schema="a/v1"), hash_canonical({"v": 1}, schema="b/v1"))

    def test_type_tag_prevents_string_number_collision(self):
        self.assertNotEqual(hash_canonical({"v": 1}, schema="t/v1"), hash_canonical({"v": "1"}, schema="t/v1"))

    def test_cosmetic_number_formatting_is_equal(self):
        self.assertEqual(hash_canonical({"v": 0.50}, schema="t/v1"), hash_canonical({"v": 0.5}, schema="t/v1"))
        self.assertEqual(hash_canonical({"v": -0.0}, schema="t/v1"), hash_canonical({"v": 0.0}, schema="t/v1"))

    def test_nan_infinity_rejected(self):
        with self.assertRaises(CanonicalizationError):
            hash_canonical({"v": float("nan")}, schema="t/v1")
        with self.assertRaises(CanonicalizationError):
            hash_canonical({"v": float("inf")}, schema="t/v1")

    def test_pinned_vectors_cross_environment(self):  # A56 — a serialization change must break these
        self.assertEqual(hash_canonical({"a": 1, "b": [0.5, "x"], "c": True}, schema="vec/v1"),
                         "ad9288f5c93184cb5ae01710bebd5513831cfa23f22b9107cdc284213fe9061d")
        self.assertEqual(hash_canonical({"v": 1.047}, schema="vec/v1"),
                         "41eb4f873a6d49e3d7729b5430c84fd662e3efc9bbbfc86957d5ccebc57afab2")


class FingerprintMatrix(unittest.TestCase):
    """A56: must-remain-equal vs must-differ classes."""
    def setUp(self):
        self.base = build_instance_fingerprints(_inst(), check_contract_version="c/v1")

    def _fp(self, **kw):
        return build_instance_fingerprints(_inst(**kw), check_contract_version="c/v1")

    def test_reordering_givens_preserves_semantic(self):
        fp = self._fp(inputs=(("v", 10.0), ("L", 0.2), ("B", 0.5)))
        self.assertEqual(fp.semantic, self.base.semantic)
        self.assertEqual(fp.evidence_subject, self.base.evidence_subject)

    def test_cosmetic_number_format_preserves_semantic(self):
        self.assertEqual(self._fp(inputs=(("B", 0.50), ("L", 0.2), ("v", 10.0))).semantic, self.base.semantic)
        self.assertEqual(self._fp(answer="1.00 V").semantic, self.base.semantic)

    def test_cosmetic_wording_change_moves_presentation_only(self):  # A59
        fp = self._fp(problem="A 0.2 m rod, v=10 m/s, B=0.5 T.")
        self.assertNotEqual(fp.presentation, self.base.presentation)
        self.assertEqual(fp.semantic, self.base.semantic)
        self.assertEqual(fp.evidence_subject, self.base.evidence_subject)

    def test_changed_value_differs(self):
        self.assertNotEqual(self._fp(answer="2.0 V").semantic, self.base.semantic)

    def test_changed_target_differs(self):
        self.assertNotEqual(self._fp(target="power").execution_contract, self.base.execution_contract)

    def test_changed_required_rounding_differs(self):
        fp = self._fp(comparison=_cmp(rounding_rule="2dp"))
        self.assertNotEqual(fp.answer_semantics, self.base.answer_semantics)

    def test_changed_tolerance_moves_comparison_not_semantics(self):  # A60
        fp = self._fp(comparison=_cmp(tolerance="0.05"))
        self.assertNotEqual(fp.comparison_policy, self.base.comparison_policy)
        self.assertEqual(fp.execution_contract, self.base.execution_contract)
        self.assertEqual(fp.answer_semantics, self.base.answer_semantics)
        self.assertNotEqual(fp.evidence_subject, self.base.evidence_subject)   # subject binds comparison

    def test_changed_assumptions_differ(self):
        fp = self._fp(assumptions=(InstanceAssumption("regime", "relativistic"),))
        self.assertNotEqual(fp.execution_contract, self.base.execution_contract)


def _record(status, subject, *, run_id="r1", eid="e1", verifier="reproduction_checker",
            ver=REPRO_VERIFIER_VERSION, contract=REPRO_CHECK_CONTRACT_VERSION,
            check="published_answer_reproduction"):
    return EvidenceRecord(evidence_id=eid, check=check, status=status, subject_fingerprint=subject,
                          verifier_name=verifier, verifier_version=ver, check_contract_version=contract,
                          run_id=run_id, evidence={})


def _decision(level, subject, records, *, run_id="r1", strength=None, comp="reproduction"):
    strength = strength if strength is not None else {
        "verified_reproduction": AssuranceStrength.REPRODUCED_INSTANCE,
        "provisional": AssuranceStrength.PROVISIONAL, "guided": AssuranceStrength.GUIDED}[level]
    return InstanceAssuranceDecision(
        assurance_id="a1", run_id=run_id, subject_kind="published_instance", level=level,
        profile=InstanceAssuranceProfile(strength, comp if level != "guided" else "none"),
        subject_fingerprint=subject, assurance_policy_version=ASSURANCE_POLICY_VERSION,
        verification_dependencies={"reproduction_checker": VerifierDependency(REPRO_VERIFIER_VERSION,
                                                                              REPRO_CHECK_CONTRACT_VERSION)},
        evidence_ids=tuple(r.evidence_id for r in records))


class EvidenceIntegrity(unittest.TestCase):
    SUBJ = "subj-1"

    def test_missing_evidence_fails(self):  # A47
        d = _decision("verified_reproduction", self.SUBJ, [_record("confirm", self.SUBJ)])
        with self.assertRaises(EvidenceIntegrityError):
            validate_assurance_decision(d, [])   # cited but not provided

    def test_revoked_evidence_fails(self):  # A48
        r = _record("confirm", self.SUBJ)
        d = _decision("verified_reproduction", self.SUBJ, [r])
        rev = {r.evidence_id: EvidenceRevocation(r.evidence_id, "t", "wrong", "inc-1")}
        with self.assertRaises(EvidenceIntegrityError):
            validate_assurance_decision(d, [r], rev)

    def test_verifier_binding_mismatch_fails(self):  # A49
        r = _record("confirm", self.SUBJ, ver="reproduction_checker/9.9")
        d = _decision("verified_reproduction", self.SUBJ, [r])   # deps pin 1.0
        with self.assertRaises(EvidenceIntegrityError):
            validate_assurance_decision(d, [r])

    def test_cross_run_evidence_fails(self):  # A57
        r = _record("confirm", self.SUBJ, run_id="OTHER")
        d = _decision("verified_reproduction", self.SUBJ, [r], run_id="r1")
        with self.assertRaises(EvidenceIntegrityError):
            validate_assurance_decision(d, [r])


class PerLevelPolicy(unittest.TestCase):
    SUBJ = "subj-1"

    def test_confirm_earns_verified(self):
        r = _record("confirm", self.SUBJ)
        validate_assurance_decision(_decision("verified_reproduction", self.SUBJ, [r]), [r])

    def test_confirm_plus_refute_conflict_never_verified(self):  # conflict rule
        rs = [_record("confirm", self.SUBJ, eid="e1"), _record("refute", self.SUBJ, eid="e2")]
        with self.assertRaises(EvidenceIntegrityError):
            validate_assurance_decision(_decision("verified_reproduction", self.SUBJ, rs), rs)

    def test_refuted_candidate_cannot_be_provisional(self):  # refuted never ships
        r = _record("refute", self.SUBJ)
        with self.assertRaises(EvidenceIntegrityError):
            validate_assurance_decision(_decision("provisional", self.SUBJ, [r]), [r])

    def test_provisional_forbidden_when_evidence_earns_stronger(self):
        r = _record("confirm", self.SUBJ)
        with self.assertRaises(EvidenceIntegrityError):
            validate_assurance_decision(_decision("provisional", self.SUBJ, [r]), [r])

    def test_indecisive_is_valid_provisional(self):
        r = _record("indecisive", self.SUBJ)
        validate_assurance_decision(_decision("provisional", self.SUBJ, [r]), [r])


class Derivation(unittest.TestCase):
    SUBJ = "subj-1"

    def _derive(self, status):
        r = _record(status, self.SUBJ)
        deps = {"reproduction_checker": VerifierDependency(REPRO_VERIFIER_VERSION, REPRO_CHECK_CONTRACT_VERSION)}
        return derive_instance_assurance(assurance_id="a", run_id="r1", subject_fingerprint=self.SUBJ,
                                         records=[r], verification_dependencies=deps,
                                         assurance_policy_version=ASSURANCE_POLICY_VERSION)

    def test_confirm_to_verified(self):
        self.assertEqual(self._derive("confirm").level, "verified_reproduction")

    def test_refute_to_guided(self):   # proven-wrong -> discarded -> guided floor, never provisional
        self.assertEqual(self._derive("refute").level, "guided")

    def test_indecisive_to_provisional(self):
        self.assertEqual(self._derive("indecisive").level, "provisional")


class Slice1A(unittest.TestCase):
    def test_correct_reproduction_verifies(self):
        rep = run_slice1a(_inst(answer="1.0 V"), "1.0 V")
        self.assertEqual(rep["level"], "verified_reproduction")
        self.assertEqual(rep["reproduction_status"], "confirm")

    def test_wrong_number_refuted_to_guided(self):
        rep = run_slice1a(_inst(answer="1.0 V"), "2.0 V")
        self.assertEqual(rep["reproduction_status"], "refute")
        self.assertEqual(rep["level"], "guided")   # refuted -> discarded, never shipped

    def test_wrong_unit_refuted(self):
        rep = run_slice1a(_inst(answer="1.0 V"), "1.0 A")
        self.assertEqual(rep["reproduction_status"], "refute")

    def test_non_numeric_indecisive_to_provisional(self):
        rep = run_slice1a(_inst(answer="1.0 V"), "see the explanation")
        self.assertEqual(rep["reproduction_status"], "indecisive")
        self.assertEqual(rep["level"], "provisional")

    def test_report_carries_stable_fingerprints(self):
        a = run_slice1a(_inst(), "1.0 V")
        b = run_slice1a(_inst(), "1.0 V")
        self.assertEqual(a["fingerprints"]["semantic"], b["fingerprints"]["semantic"])


if __name__ == "__main__":
    unittest.main()
