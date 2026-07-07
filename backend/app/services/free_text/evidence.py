"""Shared evidence layer for establishment + L4 (Q24 §3/§4).

The bounded verifier and the establishment resolver both operate over a SUPPLIED, VERSIONED evidence package — not
"ask a model what it knows." A `FactPack` pins its own versions; every L4 verdict records the `EvidenceContext` it
ran against so a `refuted` verdict replays to the same result even after the pack is later revised.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Tuple


def normalize_claim(text: str) -> str:
    """Deterministic claim normalization for evidence lookup (lowercase, trim trailing punctuation, collapse ws)."""
    t = text.strip().lower()
    t = re.sub(r"[.!?;:,]+$", "", t)
    return re.sub(r"\s+", " ", t)


@dataclass(frozen=True)
class EvidenceContext:
    fact_pack_id: str = ""
    fact_pack_version: str = ""
    definition_registry_version: str = ""
    source_excerpt_ids: Tuple[str, ...] = ()
    trace_ids: Tuple[str, ...] = ()


@dataclass(frozen=True)
class RegisteredDefinition:
    definition_id: str
    statement: str          # store already-normalized (or normalized on load)


@dataclass(frozen=True)
class FactPackRule:
    rule_id: str
    statement: str          # normalized
    polarity: str           # "assert" | "deny"


ASSERT = "assert"
DENY = "deny"


@dataclass(frozen=True)
class FactPack:
    fact_pack_id: str
    fact_pack_version: str
    definition_registry_version: str = ""
    definitions: Tuple[RegisteredDefinition, ...] = ()
    rules: Tuple[FactPackRule, ...] = ()

    def context(self, *, source_excerpt_ids: Tuple[str, ...] = (),
                trace_ids: Tuple[str, ...] = ()) -> EvidenceContext:
        return EvidenceContext(self.fact_pack_id, self.fact_pack_version, self.definition_registry_version,
                               tuple(source_excerpt_ids), tuple(trace_ids))

    def asserted(self) -> Dict[str, Tuple[str, str]]:
        """normalized statement → (evidence_id, kind) for anything the pack asserts true."""
        out: Dict[str, Tuple[str, str]] = {}
        for d in self.definitions:
            out[normalize_claim(d.statement)] = (d.definition_id, "definition")
        for r in self.rules:
            if r.polarity == ASSERT:
                out.setdefault(normalize_claim(r.statement), (r.rule_id, "rule"))
        return out

    def denied(self) -> Dict[str, str]:
        """normalized statement → rule_id for anything the pack knows to be false."""
        return {normalize_claim(r.statement): r.rule_id for r in self.rules if r.polarity == DENY}
