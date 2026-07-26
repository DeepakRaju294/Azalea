"""Delivery boundary + escalation state machine tests (offline).

Delivery: per-kind/risk shipping policy, eligibility (ShippingPolicyError, NOT integrity error), and the
fail-closed delivery-scope assertion (A39/A40 flavor). Escalation: §12 failure->next-state, and the resolution
outcomes that encode 'no adapter never blocks' + refute->guided (never a wrong ship).
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples.retrieval.delivery import (
    DeliveredInstance, ShippingPolicy, assert_delivery_scope, meets_threshold, ship_disposition,
    validate_shipping_eligibility,
)
from app.services.examples.retrieval.escalation import (
    next_state, route_disposition, route_retrieval_miss,
)
from app.services.examples.retrieval.model import (
    AssuranceStrength, EvidenceIntegrityError, EvidenceRecord, InstanceAssuranceDecision,
    InstanceAssuranceProfile, ShippingPolicyError, VerifierDependency,
)
from app.services.examples.retrieval.fingerprints import InstanceFingerprintSet
from app.services.examples.retrieval.slice1a import REPRO_CHECK_CONTRACT_VERSION, REPRO_VERIFIER_VERSION

SUBJ = "subj-1"
_DEPS = {"reproduction_checker": VerifierDependency(REPRO_VERIFIER_VERSION, REPRO_CHECK_CONTRACT_VERSION)}


def _decision(level, *, strength, comp, subject=SUBJ, eids=("e1",)):
    return InstanceAssuranceDecision(
        assurance_id="a1", run_id="r1", subject_kind="published_instance", level=level,
        profile=InstanceAssuranceProfile(strength, comp), subject_fingerprint=subject,
        assurance_policy_version="v1", verification_dependencies=_DEPS, evidence_ids=eids)


def _verified():
    return _decision("verified_reproduction", strength=AssuranceStrength.REPRODUCED_INSTANCE, comp="reproduction")


def _provisional():
    return _decision("provisional", strength=AssuranceStrength.PROVISIONAL, comp="reproduction")


def _record(status="confirm", subject=SUBJ, eid="e1"):
    return EvidenceRecord(evidence_id=eid, check="published_answer_reproduction", status=status,
                          subject_fingerprint=subject, verifier_name="reproduction_checker",
                          verifier_version=REPRO_VERIFIER_VERSION, check_contract_version=REPRO_CHECK_CONTRACT_VERSION,
                          run_id="r1", evidence={})


class ShippingPolicyTests(unittest.TestCase):
    def test_verified_meets_ordinary(self):
        self.assertTrue(meets_threshold(_verified(), kind="computational", risk="ordinary", policy=ShippingPolicy()))

    def test_uniform_bar_verified_meets_every_risk(self):
        # user decision: uniform bar — reproduction-verified is enough in ordinary AND high-risk domains.
        for risk in ("ordinary", "high"):
            self.assertTrue(meets_threshold(_verified(), kind="computational", risk=risk, policy=ShippingPolicy()))

    def test_disposition_verified_ships(self):
        self.assertEqual(ship_disposition(_verified()), "ship_verified")

    def test_provisional_ships_provisional_when_allowed(self):
        self.assertEqual(ship_disposition(_provisional(), policy=ShippingPolicy(allow_provisional=True)),
                         "ship_provisional")

    def test_provisional_withheld_when_not_allowed(self):
        self.assertEqual(ship_disposition(_provisional(), policy=ShippingPolicy(allow_provisional=False)),
                         "withhold_guided")

    def test_eligibility_raises_policy_error_not_integrity(self):
        with self.assertRaises(ShippingPolicyError):
            validate_shipping_eligibility(_provisional(), policy=ShippingPolicy(allow_provisional=False))


class DeliveryScope(unittest.TestCase):
    def _fp(self, evidence_subject=SUBJ):
        return InstanceFingerprintSet(execution_contract="x", answer_semantics="y", comparison_policy="c",
                                      evidence_subject=evidence_subject, presentation="p")

    def test_valid_instance_delivery_passes(self):
        d = DeliveredInstance(self._fp(), _verified(), {"points": ["..."]})
        assert_delivery_scope(d, {"e1": _record()})

    def test_missing_evidence_fails(self):  # A47 at delivery
        d = DeliveredInstance(self._fp(), _verified(), {})
        with self.assertRaises(EvidenceIntegrityError):
            assert_delivery_scope(d, {})

    def test_fingerprint_mismatch_fails(self):  # A40 flavor
        d = DeliveredInstance(self._fp(evidence_subject="OTHER"), _verified(), {})
        with self.assertRaises(EvidenceIntegrityError):
            assert_delivery_scope(d, {"e1": _record()})


class Escalation(unittest.TestCase):
    def test_failure_next_states(self):
        self.assertEqual(next_state("transient_infrastructure"), "retry_or_queue")
        self.assertEqual(next_state("verification_refuted"), "discard_candidate")
        self.assertEqual(next_state("source_conflict"), "human_review")
        self.assertEqual(next_state("verification_indecisive"), "stronger_verifier_or_review")

    def test_verified_delivers_no_gap(self):
        r = route_disposition("ship_verified")
        self.assertEqual(r.learner_output, "delivered")
        self.assertFalse(r.coverage_gap)
        self.assertFalse(r.blocked_no_adapter)

    def test_provisional_enqueued(self):
        r = route_disposition("ship_provisional")
        self.assertEqual(r.learner_output, "provisional")
        self.assertEqual(r.acquisition_state, "review_pending")

    def test_withheld_is_guided_coverage_gap_never_blocked(self):
        r = route_disposition("withhold_guided")
        self.assertEqual(r.learner_output, "guided")
        self.assertTrue(r.coverage_gap)
        self.assertFalse(r.blocked_no_adapter)   # never blocked for lack of an adapter

    def test_retrieval_miss_still_not_blocked(self):
        r = route_retrieval_miss()
        self.assertEqual(r.learner_output, "guided")
        self.assertEqual(r.acquisition_state, "retrieval_pending")
        self.assertFalse(r.blocked_no_adapter)


if __name__ == "__main__":
    unittest.main()
