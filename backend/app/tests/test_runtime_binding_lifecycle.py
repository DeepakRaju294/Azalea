"""Milestone C unit 10a/10b — generic exercise ownership + preparation lifecycle (offline, in-memory).

Proves the transactional claim invariants and the CAS/version-guarded preparation state machine that C's
persistence and certification wiring will later back with tables. No DB, live route, or frontend.
"""

import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples.runtime_binding.lifecycle import (
    ClaimLedger,
    OwnershipTuple,
    PreparationError,
    PreparationIdentity,
    PreparationLedger,
    path_plan_version,
)

TUP = OwnershipTuple("free_fall_distance@1", "distance_from_rest", "direct_formula_calculation", "worked_example")
PLAN = [{"topic_id": "t1", "scope_in": ["free fall"], "role": "goal_core"},
        {"topic_id": "t2", "scope_in": ["kinematics"], "role": "supporting"}]


class PathPlanVersion(unittest.TestCase):
    def test_deterministic_and_order_sensitive(self):
        self.assertEqual(path_plan_version(PLAN), path_plan_version(PLAN))
        self.assertNotEqual(path_plan_version(PLAN), path_plan_version(list(reversed(PLAN))))

    def test_scope_change_changes_version(self):
        changed = [{**PLAN[0], "scope_in": ["free fall", "extra"]}, PLAN[1]]
        self.assertNotEqual(path_plan_version(PLAN), path_plan_version(changed))


class Ownership(unittest.TestCase):
    def setUp(self):
        self.ppv = path_plan_version(PLAN)
        self.ledger = ClaimLedger()

    def test_first_topic_wins_second_loses(self):
        a = self.ledger.claim(self.ppv, TUP, "t1")
        b = self.ledger.claim(self.ppv, TUP, "t2")
        self.assertEqual(a.status, "active")
        self.assertEqual(b.status, "lost")
        self.assertEqual(b.lost_to_topic_id, "t1")

    def test_same_owner_reclaim_is_idempotent(self):
        a = self.ledger.claim(self.ppv, TUP, "t1")
        a2 = self.ledger.claim(self.ppv, TUP, "t1")
        self.assertEqual(a.claim_id, a2.claim_id)

    def test_claim_currency_true_only_while_active(self):
        a = self.ledger.claim(self.ppv, TUP, "t1")
        self.assertTrue(self.ledger.is_current(a))
        self.ledger.supersede_plan(self.ppv)
        self.assertFalse(self.ledger.is_current(a))

    def test_lost_claim_is_never_current(self):
        self.ledger.claim(self.ppv, TUP, "t1")
        b = self.ledger.claim(self.ppv, TUP, "t2")
        self.assertFalse(self.ledger.is_current(b))

    def test_new_plan_version_is_a_fresh_key(self):
        self.ledger.claim(self.ppv, TUP, "t1")
        other_ppv = path_plan_version(list(reversed(PLAN)))
        c = self.ledger.claim(other_ppv, TUP, "t2")
        self.assertEqual(c.status, "active")     # different plan version, no contention


def _identity(claim_id="claim_1", claim_version=1, **overrides) -> PreparationIdentity:
    base = dict(
        topic_id="t1", path_plan_version=path_plan_version(PLAN), sibling_claim_id=claim_id,
        sibling_claim_version=claim_version, contract_version=1, grammar_version=1,
        pedagogical_policy_version=1, resolution_registry_version=1, resolution_entry_version=1,
        binding_digest="bd", execution_environment_digest="eed",
    )
    base.update(overrides)
    return PreparationIdentity(**base)


class Preparation(unittest.TestCase):
    def setUp(self):
        self.claims = ClaimLedger()
        self.claim = self.claims.claim(path_plan_version(PLAN), TUP, "t1")
        self.preps = PreparationLedger()
        self.identity = _identity(claim_id=self.claim.claim_id)

    def test_request_then_ready_with_current_claim(self):
        p = self.preps.request(self.identity)
        self.assertEqual(p.status, "preparing")
        r = self.preps.mark_ready(p, p.status_version, self.claims, self.claim)
        self.assertEqual(r.status, "ready")

    def test_request_is_idempotent_for_same_identity(self):
        p1 = self.preps.request(self.identity)
        p2 = self.preps.request(self.identity)
        self.assertEqual(p1.preparation_id, p2.preparation_id)

    def test_stale_status_version_cannot_mark_ready(self):
        p = self.preps.request(self.identity)
        self.preps.mark_ready(p, p.status_version, self.claims, self.claim)   # advances status_version
        with self.assertRaises(PreparationError):
            self.preps.mark_ready(p, p.status_version, self.claims, self.claim)  # stale read

    def test_ready_requires_current_claim(self):
        p = self.preps.request(self.identity)
        self.claims.supersede_plan(path_plan_version(PLAN))     # claim no longer current
        with self.assertRaises(PreparationError):
            self.preps.mark_ready(p, p.status_version, self.claims, self.claim)

    def test_safety_bump_stales_live_preparations(self):
        p = self.preps.request(self.identity)
        self.preps.bump_safety_block()
        self.assertEqual(self.preps.get(p.preparation_id).status, "stale")

    def test_ready_rejected_after_safety_bump(self):
        p = self.preps.request(self.identity)
        v = p.status_version
        self.preps.bump_safety_block()
        with self.assertRaises(PreparationError):
            self.preps.mark_ready(p, v, self.claims, self.claim)

    def test_retry_creates_new_preparation_never_mutates_failed(self):
        p = self.preps.request(self.identity)
        failed = self.preps.mark_failed(p, p.status_version, "executor error")
        self.assertEqual(failed.status, "failed")
        retried = self.preps.retry(failed)
        self.assertNotEqual(retried.preparation_id, failed.preparation_id)
        self.assertEqual(retried.status, "preparing")
        self.assertEqual(self.preps.get(failed.preparation_id).status, "failed")   # untouched

    def test_identity_digest_changes_with_any_version(self):
        base = self.identity.digest()
        self.assertNotEqual(base, _identity(claim_id=self.claim.claim_id, resolution_registry_version=2).digest())
        self.assertNotEqual(base, _identity(claim_id=self.claim.claim_id, pedagogical_policy_version=2).digest())


if __name__ == "__main__":
    unittest.main()
