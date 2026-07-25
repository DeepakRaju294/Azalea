"""Milestone B — offline runtime-binding evidence (GROUNDED_RUNTIME_BINDING_SPEC.md §17.1 units 5-9, §20.2).

Fully offline / in-memory: reviewed contract + resolution registry -> deterministic binding -> seeded instance
-> neutral structured problem -> trace/projection/checkpoints -> verification vector -> immutable evidence.
No live route, persistence, sibling arbitration, frontend, or model call. Proves the §20.2 gate items.
"""

import os
import unittest
from fractions import Fraction

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples.runtime_binding import fixtures as F
from app.services.examples.runtime_binding.binding import BindingError, validate_binding
from app.services.examples.runtime_binding.contract import compile_contract_descriptor
from app.services.examples.runtime_binding.evidence import (
    EvidenceError,
    InMemoryEvidenceStore,
    freeze_evidence,
)
from app.services.examples.runtime_binding.generation import generate_instance
from app.services.examples.runtime_binding.grammar import DIRECT_FORMULA_CALCULATION as GRAMMAR
from app.services.examples.runtime_binding.problem import ProblemError, build_problem_statement
from app.services.examples.runtime_binding.resolution import ContractResolutionRegistry
from app.services.examples.runtime_binding.router import bind_offline
from app.services.examples.runtime_binding.trace import build_trace_bundle
from app.services.examples.runtime_binding.verification import run_verification
from app.services.examples.trace_pipeline import route_adapter

CONTRACTS = F.MILESTONE_B_CONTRACTS
REGISTRY = F.MILESTONE_B_REGISTRY


def _registered_lookup(scope_concept_id: str):
    title = {
        "volumetric_flow_rate": "Volumetric Flow Rate",
        "total_charge_two_currents": "Total Charge From Two Currents",
        "free_fall_distance": "Free-Fall Distance From Rest",
    }.get(scope_concept_id, scope_concept_id)
    return route_adapter({"title": title, "topic_type": "math_formula_method"})


def _bind(scope, seed=0):
    return validate_binding(CONTRACTS[_cid(scope)], REGISTRY.resolve(scope), GRAMMAR)


def _cid(scope):
    return next(c.contract_id for c in CONTRACTS.values() if c.contract_concept_id == scope)


class ContractsAndAbsence(unittest.TestCase):
    def test_all_fixtures_compile_on_substrate(self):
        for cid, contract in CONTRACTS.items():
            with self.subTest(cid=cid):
                d = compile_contract_descriptor(contract)
                self.assertEqual(d.output_symbol, contract.output.symbol)

    def test_fixture_titles_genuinely_miss_the_live_manifest(self):
        # anti-drift guard (§17.2): if catalog growth ever registers one of these, this test FAILS on purpose.
        for title in F.MILESTONE_B_ABSENCE_TITLES:
            with self.subTest(title=title):
                self.assertIsNone(route_adapter({"title": title, "topic_type": "math_formula_method"}))

    def test_structural_diversity(self):
        sources = {c.relationship.expression_source for c in CONTRACTS.values()}
        self.assertTrue(any("/" in s for s in sources))          # division
        self.assertTrue(any("+" in s for s in sources))          # add/multiply
        self.assertTrue(any("**" in s for s in sources))         # integer power


class Resolution(unittest.TestCase):
    def test_reviewed_match_by_concept_and_alias(self):
        r = REGISTRY.resolve("volumetric_flow_rate")
        self.assertEqual((r.status, r.resolution_validity), ("resolved", "reviewed_match"))
        r2 = REGISTRY.resolve("computing volumetric flow rate")     # reviewed alias
        self.assertEqual(r2.contract_id, r.contract_id)

    def test_unknown_is_unsupported_not_a_guess(self):
        r = REGISTRY.resolve("some concept with no reviewed entry")
        self.assertEqual(r.status, "unsupported")
        self.assertNotEqual(r.resolution_validity, "reviewed_match")

    def test_ambiguous_alias_does_not_silently_pick(self):
        entries = list(REGISTRY.entries)
        # two entries sharing an alias -> ambiguous
        clash = ContractResolutionRegistry(9, [
            entries[0].__class__(**{**entries[0].__dict__, "reviewed_aliases": ("shared alias",)}),
            entries[1].__class__(**{**entries[1].__dict__, "reviewed_aliases": ("shared alias",)}),
        ])
        r = clash.resolve("shared alias")
        self.assertEqual(r.status, "ambiguous")


class BindingAndGeneration(unittest.TestCase):
    def test_binding_requires_reviewed_match(self):
        bad = REGISTRY.resolve("unknown concept")
        with self.assertRaises(BindingError):
            validate_binding(CONTRACTS[_cid("free_fall_distance")], bad, GRAMMAR)

    def test_generation_is_reproducible(self):
        b = _bind("free_fall_distance")
        i1 = generate_instance(b, seed=11)
        i2 = generate_instance(b, seed=11)
        self.assertEqual(i1.instance_digest, i2.instance_digest)
        self.assertEqual(i1.visible_values, i2.visible_values)

    def test_binding_digest_changes_when_registry_version_changes(self):
        contract = CONTRACTS[_cid("free_fall_distance")]
        r1 = REGISTRY.resolve("free_fall_distance")
        bumped = ContractResolutionRegistry(REGISTRY.version + 1, list(REGISTRY.entries))
        r2 = bumped.resolve("free_fall_distance")
        d1 = validate_binding(contract, r1, GRAMMAR).binding_digest
        d2 = validate_binding(contract, r2, GRAMMAR).binding_digest
        self.assertNotEqual(d1, d2)

    def test_generated_instance_quality_passes(self):
        for scope in ("volumetric_flow_rate", "total_charge_two_currents", "free_fall_distance"):
            with self.subTest(scope=scope):
                self.assertTrue(generate_instance(_bind(scope), seed=4).quality.passed)


class TraceChain(unittest.TestCase):
    def test_trace_has_terminal_and_checkpoints_trace_to_steps(self):
        b = _bind("total_charge_two_currents")
        inst = generate_instance(b, seed=2)
        tb = build_trace_bundle(b, inst)
        terminal = tb.trace.by_id(tb.projection.terminal_transition_id)
        self.assertTrue(terminal.state_after.get("complete"))
        step_ids = {s.id for s in tb.trace.steps}
        for cp in tb.checkpoints:
            self.assertTrue(set(cp.source_step_ids) <= step_ids)


class Verification(unittest.TestCase):
    def test_passes_for_all_fixtures(self):
        for scope in ("volumetric_flow_rate", "total_charge_two_currents", "free_fall_distance"):
            with self.subTest(scope=scope):
                b = _bind(scope)
                inst = generate_instance(b, seed=6)
                v = run_verification(b, inst, build_trace_bundle(b, inst))
                self.assertTrue(v.passed, [(c.check_id, c.status) for c in v.checks if c.status == "failed"])
                self.assertEqual(v.narration_fidelity, "not_run")

    def test_tampered_result_fails_recomputation(self):
        b = _bind("free_fall_distance")
        inst = generate_instance(b, seed=6)
        tampered = inst.__class__(**{**inst.__dict__, "expected_result": str(Fraction(inst.expected_result) + 1)})
        v = run_verification(b, tampered, build_trace_bundle(b, inst))
        self.assertFalse(v.passed)
        self.assertTrue(any(c.check_id == "recomputation" and c.status == "failed" for c in v.checks))

    def test_proportionality_detected_where_input_is_multiplicative_factor(self):
        # volumetric flow rate Q = V / t: V is a pure multiplicative factor -> proportional check present
        b = _bind("volumetric_flow_rate")
        inst = generate_instance(b, seed=6)
        v = run_verification(b, inst, build_trace_bundle(b, inst))
        self.assertTrue(any(c.check_id == "proportional:V" and c.status == "passed" for c in v.checks))


class EvidenceFreezing(unittest.TestCase):
    def _frozen(self, scope, seed=6):
        b = _bind(scope)
        inst = generate_instance(b, seed=seed)
        tb = build_trace_bundle(b, inst)
        return freeze_evidence(b, inst, tb, run_verification(b, inst, tb))

    def test_freeze_requires_passing_vector(self):
        b = _bind("free_fall_distance")
        inst = generate_instance(b, seed=6)
        tb = build_trace_bundle(b, inst)
        tampered = inst.__class__(**{**inst.__dict__, "expected_result": str(Fraction(inst.expected_result) + 1)})
        v = run_verification(b, tampered, tb)
        with self.assertRaises(EvidenceError):
            freeze_evidence(b, tampered, tb, v)

    def test_evidence_digest_reproducible_and_result_sensitive(self):
        a = self._frozen("free_fall_distance", seed=6)
        b = self._frozen("free_fall_distance", seed=6)
        self.assertEqual(a.evidence_digest, b.evidence_digest)
        c = self._frozen("free_fall_distance", seed=7)
        self.assertNotEqual(a.evidence_digest, c.evidence_digest)   # different instance -> new evidence id/digest

    def test_store_is_insert_only_and_idempotent(self):
        store = InMemoryEvidenceStore()
        pkg = self._frozen("volumetric_flow_rate", seed=6)
        store.insert(pkg)
        store.insert(pkg)                     # idempotent same-digest re-insert
        self.assertEqual(len(store), 1)
        self.assertIs(store.get(pkg.evidence_id), pkg)

    def test_cards_reference_evidence_steps(self):
        pkg = self._frozen("total_charge_two_currents", seed=6)
        self.assertTrue(pkg.card_links)
        for link in pkg.card_links:
            for claim in link.structured_claims:
                self.assertTrue(claim.evidence_ref.startswith(pkg.contract_id))


class NeutralProblem(unittest.TestCase):
    def test_display_text_is_faithful_to_structured_fields(self):
        b = _bind("volumetric_flow_rate")
        inst = generate_instance(b, seed=6)
        stmt = build_problem_statement(b, inst)
        self.assertEqual(stmt.target_symbol, "Q")
        self.assertIn("(Q)", stmt.question_display_text)
        self.assertNotIn("Q = ", stmt.question_display_text)      # unknown never supplied

    def test_validate_rejects_target_or_unit_mismatch(self):
        b = _bind("volumetric_flow_rate")
        inst = generate_instance(b, seed=6)
        stmt = build_problem_statement(b, inst)
        from app.services.examples.runtime_binding.problem import validate_problem_statement
        broken = stmt.__class__(**{**stmt.__dict__, "requested_display_unit": "kg"})
        with self.assertRaises(ProblemError):
            validate_problem_statement(broken, b, inst)


class OfflineEndToEnd(unittest.TestCase):
    def test_registered_miss_then_verified_evidence(self):
        for scope in ("volumetric_flow_rate", "total_charge_two_currents", "free_fall_distance"):
            with self.subTest(scope=scope):
                r = bind_offline(scope, contracts=CONTRACTS, registry=REGISTRY,
                                 registered_lookup=_registered_lookup, seed=5)
                self.assertEqual(r.decision, "runtime_binding_evidence")
                self.assertIsNotNone(r.evidence)
                self.assertTrue(r.verification.passed)

    def test_registered_hit_never_binds(self):
        r = bind_offline("kinetic_energy", contracts=CONTRACTS, registry=REGISTRY,
                         registered_lookup=lambda s: route_adapter({"title": "Kinetic Energy", "topic_type": "math_formula_method"}),
                         seed=1)
        self.assertEqual(r.decision, "registered_adapter_wins")
        self.assertIsNone(r.evidence)

    def test_unresolved_scope_is_withheld_never_guessed(self):
        r = bind_offline("nonexistent concept", contracts=CONTRACTS, registry=REGISTRY,
                         registered_lookup=lambda s: None, seed=1)
        self.assertEqual(r.decision, "withheld")
        self.assertIsNone(r.evidence)

    def test_end_to_end_is_replay_stable(self):
        a = bind_offline("free_fall_distance", contracts=CONTRACTS, registry=REGISTRY,
                         registered_lookup=_registered_lookup, seed=5)
        b = bind_offline("free_fall_distance", contracts=CONTRACTS, registry=REGISTRY,
                         registered_lookup=_registered_lookup, seed=5)
        self.assertEqual(a.evidence.evidence_digest, b.evidence.evidence_digest)


if __name__ == "__main__":
    unittest.main()
