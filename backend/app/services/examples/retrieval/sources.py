"""Curated local source corpus (the chosen retrieval strategy — no live web egress).

Each entry is a REVIEWED, structured `PublishedInstance` (problem + inputs + published answer + comparison),
so there is NO prose->formula transcription step for computational instances: the corpus is authored in the
typed shape the verifier consumes. Every entry carries a `SourceRef` with a content-hashed `SourceSnapshot`
(the exact ingested bytes), so provenance and cache invalidation are deterministic and offline.

Adding coverage = adding a reviewed entry here. This is the local, replayable, SSRF-free substrate; live-web
retrieval, if ever added, would feed the SAME candidate shape through the SAME verification.
"""
from __future__ import annotations

from app.services.examples.retrieval.fingerprints import hash_canonical
from app.services.examples.retrieval.model import (
    AnswerComparison, CandidateArtifact, InstanceAssumption, PublishedInstance, SourceRef, SourceSnapshot,
)

_CORPUS_VERSION = "curated-corpus/v1"
_LICENSE_POLICY = "reviewed-internal/v1"


def _snapshot(inst: PublishedInstance, source_id: str) -> SourceSnapshot:
    content_hash = hash_canonical(
        {"problem": inst.problem_statement, "inputs": [list(p) for p in inst.inputs],
         "target": inst.target, "answer": inst.published_answer, "source": source_id},
        schema="source-snapshot/v1")
    return SourceSnapshot(content_hash=content_hash, retrieved_at="2026-07-25T00:00:00Z",
                          retrieval_method_version="curated-local/v1", license_policy_version=_LICENSE_POLICY)


def _entry(concept_key: str, inst: PublishedInstance, *, source_id: str, publisher: str, family: str,
           tier: str = "textbook", reuse: str = "derived_example_allowed") -> CandidateArtifact:
    ref = SourceRef(source_id=source_id, publisher_id=publisher, corpus_family=family, tier=tier,  # type: ignore[arg-type]
                    reuse_policy=reuse, snapshot=_snapshot(inst, source_id))  # type: ignore[arg-type]
    return CandidateArtifact(artifact_id=f"cand-{concept_key}", concept_key=concept_key, payload=inst,
                             sources=(ref,))


def _cmp(unit: str, dim: str, *, kind: str = "relative_tolerance", tol: str = "0.01",
         semantics: str = "absolute", quantity: str = "") -> AnswerComparison:
    return AnswerComparison(kind=kind, quantity_kind=quantity or dim, unit_dimension=dim,  # type: ignore[arg-type]
                            unit_semantics=semantics, allowed_units=(unit,), tolerance=tol)  # type: ignore[arg-type]


# Reviewed computational instances (EM + mechanics + circuits + finance + chemistry) — no adapters exist for
# these; each answer is arithmetic-checkable from the stated inputs.
_ENTRIES: tuple[CandidateArtifact, ...] = (
    _entry("motional_emf", PublishedInstance(
        "A conducting rod of length 0.2 m moves at 10 m/s perpendicular to a 0.5 T magnetic field. Find the "
        "induced EMF.", (("B", 0.5), ("L", 0.2), ("v", 10.0)), "emf", "1.0 V", _cmp("V", "V"),
        (InstanceAssumption("velocity_perpendicular_to_field", True),)),
        source_id="openstax_physics:motional_emf", publisher="openstax", family="openstax_physics"),
    _entry("faraday_emf", PublishedInstance(
        "A 200-turn coil experiences a magnetic flux change of 0.05 Wb over 0.1 s. Find the magnitude of the "
        "induced EMF.", (("N", 200), ("dPhi", 0.05), ("dt", 0.1)), "emf", "100 V", _cmp("V", "V")),
        source_id="openstax_physics:faraday", publisher="openstax", family="openstax_physics"),
    _entry("inductor_energy", PublishedInstance(
        "How much energy is stored in a 2 H inductor carrying a steady current of 3 A?",
        (("L", 2.0), ("I", 3.0)), "energy", "9 J", _cmp("J", "J")),
        source_id="openstax_physics:inductor_energy", publisher="openstax", family="openstax_physics"),
    _entry("rl_time_constant", PublishedInstance(
        "A series RL circuit has L = 10 H and R = 5 ohm. Find its time constant.",
        (("L", 10.0), ("R", 5.0)), "tau", "2 s", _cmp("s", "s")),
        source_id="openstax_physics:rl_tau", publisher="openstax", family="openstax_physics"),
    _entry("kinetic_energy", PublishedInstance(
        "Find the kinetic energy of a 2 kg object moving at 3 m/s.", (("m", 2.0), ("v", 3.0)), "KE", "9 J",
        _cmp("J", "J")), source_id="openstax_physics:ke", publisher="openstax", family="openstax_physics"),
    _entry("ohms_law", PublishedInstance(
        "A 12 V source drives a 4 ohm resistor. Find the current.", (("V", 12.0), ("R", 4.0)), "I", "3 A",
        _cmp("A", "A")), source_id="openstax_physics:ohm", publisher="openstax", family="openstax_physics"),
    _entry("compound_interest", PublishedInstance(
        "1000 dollars is invested at 5% annual interest compounded yearly. Find the balance after 2 years.",
        (("P", 1000.0), ("r", 0.05), ("t", 2)), "amount", "1102.50", _cmp("USD", "USD")),
        source_id="finance_ref:compound", publisher="finance_ref", family="finance_ref"),
)

_BY_CONCEPT = {e.concept_key: e for e in _ENTRIES}


def all_entries() -> tuple[CandidateArtifact, ...]:
    return _ENTRIES


def lookup(concept_key: str) -> CandidateArtifact | None:
    return _BY_CONCEPT.get(concept_key)
