"""Reviewed contract resolution (spec §5.2).

Maps a scope-plan concept identity onto a reviewed executable `ConceptContract`. The registry is the ONLY
authority that can establish `resolution_validity=reviewed_match`: an exact reviewed concept id or a reviewed
alias-to-contract mapping. Token similarity may *nominate* a candidate but never establishes reviewed
identity, so a heuristic/model-only resolution can never ship a determinate example in v1 (§6.1). Both the
registry version and the matched entry version are frozen into the resolution so downstream cache keys and
evidence can detect a remap (§12.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ResolutionValidity = Literal["reviewed_match", "deterministic_candidate", "model_inferred", "ambiguous", "failed"]


@dataclass(frozen=True)
class ResolutionEvidence:
    source: Literal["scope_plan", "explicit_goal", "reviewed_alias", "grounded_definition", "model"]
    value: str
    authority: Literal["reviewed", "authoritative_retrieval", "user_source", "model_inferred"]
    detail: str = ""


@dataclass(frozen=True)
class ContractResolutionEntry:
    scope_concept_id: str
    reviewed_aliases: tuple[str, ...]
    contract_concept_id: str
    contract_id: str
    allowed_variants: tuple[str, ...]
    default_variant: str
    version: int
    review_provenance: str


@dataclass(frozen=True)
class ContractConceptResolution:
    scope_concept_id: str
    resolved_contract_concept_id: str
    contract_id: str
    variant: str
    resolution_registry_version: int
    resolution_entry_version: int
    excluded_variants: tuple[str, ...]
    evidence: tuple[ResolutionEvidence, ...]
    status: Literal["resolved", "ambiguous", "unsupported"]
    resolution_validity: ResolutionValidity


def _norm(text: str) -> str:
    return " ".join(text.strip().lower().split())


class ContractResolutionRegistry:
    """Versioned, reviewed alias->contract mapping. Immutable at runtime: heuristic candidates never mutate
    it. Bumping `version` (a new registry generation) is what invalidates downstream caches/preparations."""

    def __init__(self, version: int, entries: list[ContractResolutionEntry]) -> None:
        self.version = version
        self._entries = list(entries)
        self._by_scope: dict[str, ContractResolutionEntry] = {}
        self._by_alias: dict[str, list[ContractResolutionEntry]] = {}
        for entry in self._entries:
            self._by_scope[_norm(entry.scope_concept_id)] = entry
            for alias in (entry.scope_concept_id, *entry.reviewed_aliases):
                self._by_alias.setdefault(_norm(alias), []).append(entry)

    @property
    def entries(self) -> tuple[ContractResolutionEntry, ...]:
        return tuple(self._entries)

    def resolve(self, scope_concept_id: str, *, requested_variant: str | None = None) -> ContractConceptResolution:
        key = _norm(scope_concept_id)
        entry = self._by_scope.get(key)
        source: Literal["scope_plan", "reviewed_alias"] = "scope_plan"
        if entry is None:
            matches = {e.contract_id: e for e in self._by_alias.get(key, [])}
            if len(matches) == 1:
                entry = next(iter(matches.values()))
                source = "reviewed_alias"
            elif len(matches) > 1:
                return self._unresolved(scope_concept_id, "ambiguous")
        if entry is None:
            return self._unresolved(scope_concept_id, "unsupported")

        variant = requested_variant or entry.default_variant
        if variant not in entry.allowed_variants:
            return self._unresolved(scope_concept_id, "unsupported")
        excluded = tuple(v for v in entry.allowed_variants if v != variant)
        evidence = (
            ResolutionEvidence(source, scope_concept_id, "reviewed", entry.review_provenance),
        )
        return ContractConceptResolution(
            scope_concept_id=scope_concept_id,
            resolved_contract_concept_id=entry.contract_concept_id,
            contract_id=entry.contract_id,
            variant=variant,
            resolution_registry_version=self.version,
            resolution_entry_version=entry.version,
            excluded_variants=excluded,
            evidence=evidence,
            status="resolved",
            resolution_validity="reviewed_match",
        )

    def _unresolved(
        self, scope_concept_id: str, status: Literal["ambiguous", "unsupported"]
    ) -> ContractConceptResolution:
        return ContractConceptResolution(
            scope_concept_id=scope_concept_id,
            resolved_contract_concept_id="",
            contract_id="",
            variant="",
            resolution_registry_version=self.version,
            resolution_entry_version=0,
            excluded_variants=(),
            evidence=(),
            status=status,
            resolution_validity="failed" if status == "unsupported" else "ambiguous",
        )
