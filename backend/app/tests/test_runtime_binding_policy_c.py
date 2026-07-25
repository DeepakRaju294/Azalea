"""Milestone C — route-aware certification + latency policy (spec §2.4, §2.5, §13). Pure/offline."""

import os
import unittest
from unittest import mock

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples.runtime_binding.policy_c import (
    LATENCY_BUDGET_MS,
    certify_runtime_binding_eligibility,
    runtime_binding_enforced,
    within_budget,
)


def _certify(**over):
    base = dict(
        topic_id="t1", registered_owner=None, resolution_status="resolved",
        resolution_validity="reviewed_match", resolved_contract_id="c@1",
        resolution_registry_version=1, claim_status="active", claim_id="claim_1",
    )
    base.update(over)
    return certify_runtime_binding_eligibility(base.pop("topic_id"), **base)


class Latency(unittest.TestCase):
    def test_budget_is_5s(self):
        self.assertEqual(LATENCY_BUDGET_MS, 5000)

    def test_within_and_over(self):
        self.assertTrue(within_budget(80))
        self.assertFalse(within_budget(5001))


class Certification(unittest.TestCase):
    def test_eligible_when_miss_reviewed_and_owned(self):
        d = _certify()
        self.assertEqual(d.we_policy, "runtime_binding_eligible")
        self.assertEqual(d.resolved_contract_id, "c@1")

    def test_registered_owner_blocks(self):
        self.assertEqual(_certify(registered_owner=object()).we_policy, "withhold_fabricated")

    def test_non_reviewed_resolution_blocks(self):
        self.assertEqual(_certify(resolution_validity="model_inferred").we_policy, "withhold_fabricated")
        self.assertEqual(_certify(resolution_status="ambiguous").we_policy, "withhold_fabricated")

    def test_lost_claim_blocks(self):
        self.assertEqual(_certify(claim_status="lost").we_policy, "withhold_fabricated")


class EnforceFlag(unittest.TestCase):
    def test_enforce_off_by_default(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AZALEA_RUNTIME_BINDING_ENFORCE", None)
            self.assertFalse(runtime_binding_enforced())

    def test_enforce_on_when_set(self):
        with mock.patch.dict(os.environ, {"AZALEA_RUNTIME_BINDING_ENFORCE": "enforce"}):
            self.assertTrue(runtime_binding_enforced())


if __name__ == "__main__":
    unittest.main()
