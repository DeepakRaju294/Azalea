"""Milestone C unit 10c — derived trust level (§9) + canonical delivery serialization (§5.10), pure/offline."""

import os
import unittest
from dataclasses import replace

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples.runtime_binding import fixtures as F
from app.services.examples.runtime_binding.binding import validate_binding
from app.services.examples.runtime_binding.delivery import (
    CANONICAL_DELIVERY_SERIALIZATION_VERSION,
    canonical_delivery_payload,
    canonical_delivery_payload_digest,
    derived_trust_level,
)
from app.services.examples.runtime_binding.evidence import freeze_evidence
from app.services.examples.runtime_binding.generation import generate_instance
from app.services.examples.runtime_binding.grammar import DIRECT_FORMULA_CALCULATION as GRAMMAR
from app.services.examples.runtime_binding.trace import build_trace_bundle
from app.services.examples.runtime_binding.verification import run_verification


def _frozen(scope="free_fall_distance", seed=6):
    cid = next(c.contract_id for c in F.MILESTONE_B_CONTRACTS.values() if c.contract_concept_id == scope)
    b = validate_binding(F.MILESTONE_B_CONTRACTS[cid], F.MILESTONE_B_REGISTRY.resolve(scope), GRAMMAR)
    inst = generate_instance(b, seed=seed)
    tb = build_trace_bundle(b, inst)
    return freeze_evidence(b, inst, tb, run_verification(b, inst, tb))


class TrustLevel(unittest.TestCase):
    def _vector(self, scope="free_fall_distance"):
        cid = next(c.contract_id for c in F.MILESTONE_B_CONTRACTS.values() if c.contract_concept_id == scope)
        b = validate_binding(F.MILESTONE_B_CONTRACTS[cid], F.MILESTONE_B_REGISTRY.resolve(scope), GRAMMAR)
        inst = generate_instance(b, seed=6)
        return run_verification(b, inst, build_trace_bundle(b, inst))

    def test_reviewed_contract_runtime_binding(self):
        self.assertEqual(
            derived_trust_level("runtime_binding", "reviewed", self._vector()),
            "reviewed_contract_runtime_binding",
        )

    def test_model_inferred_resolution_caps_at_mechanically_verified_only(self):
        v = replace(self._vector(), resolution_validity="model_inferred")
        self.assertEqual(derived_trust_level("runtime_binding", "reviewed", v), "mechanically_verified_only")

    def test_failed_vector_is_withheld(self):
        v = replace(self._vector(), execution_validity="failed")
        self.assertEqual(derived_trust_level("runtime_binding", "reviewed", v), "withheld")

    def test_route_labels(self):
        v = self._vector()
        self.assertEqual(derived_trust_level("registered_adapter", "reviewed", v), "reviewed_adapter")
        self.assertEqual(derived_trust_level("gen_foundation", "reviewed", v), "verified_gen_foundation")
        self.assertEqual(derived_trust_level("runtime_binding", "authoritative_retrieval", v), "grounded_runtime_binding")


class DeliverySerialization(unittest.TestCase):
    def test_versioned_and_deterministic(self):
        pkg = _frozen()
        payload = canonical_delivery_payload(pkg)
        self.assertEqual(payload["serialization_version"], CANONICAL_DELIVERY_SERIALIZATION_VERSION)
        self.assertEqual(canonical_delivery_payload_digest(pkg), canonical_delivery_payload_digest(pkg))

    def test_digest_is_layout_free_but_claim_sensitive(self):
        pkg = _frozen()
        base = canonical_delivery_payload_digest(pkg)
        # a changed structured claim payload changes the digest
        link0 = pkg.card_links[0]
        claim0 = link0.structured_claims[0]
        mutated_claim = replace(claim0, display_payload=claim0.display_payload + " X")
        mutated_link = replace(link0, structured_claims=(mutated_claim, *link0.structured_claims[1:]))
        mutated_pkg = replace(pkg, card_links=(mutated_link, *pkg.card_links[1:]))
        self.assertNotEqual(base, canonical_delivery_payload_digest(mutated_pkg))

    def test_only_structured_claims_travel(self):
        payload = canonical_delivery_payload(_frozen())
        for card in payload["cards"]:
            self.assertIn("structured_claims", card)
            for claim in card["structured_claims"]:
                self.assertEqual(set(claim), {"claim_kind", "display_payload", "evidence_ref"})


if __name__ == "__main__":
    unittest.main()
