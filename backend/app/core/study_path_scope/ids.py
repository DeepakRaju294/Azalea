"""Deterministic identifiers for the StudyPathScope (§12 code-time decisions).

The load-bearing rule: **IDs derive from stable SEMANTIC inputs, never from mutable display titles or
creation order** — so an identical input rebuilds identical IDs (shadow-diffable) and renaming a topic does
not churn identity. `canonical_concept_key` is GLOBAL semantic identity; `concept_id`/`topic_id`/`section_id`
are scope-local occurrences derived from it. Pure — no app imports."""
from __future__ import annotations

import hashlib
import re
from typing import Any

_SLUG = re.compile(r"[^a-z0-9]+")


def stable_slug(text: Any) -> str:
    """Lowercase alnum+underscore slug. A *fallback* canonical key when no adapter slug / catalog id exists."""
    s = _SLUG.sub("_", str(text or "").strip().lower()).strip("_")
    return s or "unknown"


def _val(x: Any) -> str:
    return x.value if hasattr(x, "value") else str(x)


def short_hash(*parts: Any) -> str:
    return hashlib.sha1("\x1f".join(_val(p) for p in parts).encode("utf-8")).hexdigest()[:12]


def scope_id_for(goal: str, domain: str, source_revision: str = "") -> str:
    """Deterministic from the INPUT — identical goal/domain/source rebuilds the same scope_id."""
    return "scope_" + short_hash(stable_slug(goal), _val(domain), source_revision)


def concept_local_id(canonical_concept_key: str, facet: Any) -> str:
    """Scope-local concept occurrence. Stable across rebuilds AND display renames (keyed on the canonical
    concept key + facet, not the name), so two facets of one concept get distinct ids and a rename is a no-op."""
    return f"c_{canonical_concept_key}__{_val(facet)}"


def topic_id_for(concept_id: str) -> str:
    return "t_" + (concept_id[2:] if concept_id.startswith("c_") else concept_id)


def section_id_for(concept_id: str, section_type: Any, order: int) -> str:
    base = concept_id[2:] if concept_id.startswith("c_") else concept_id
    return f"s_{base}__{_val(section_type)}__{order}"


def record_id(prefix: str, *semantic_parts: Any) -> str:
    """Stable id for a mapping/audit/repair/evidence record — hashed from its SEMANTIC parts (not order),
    so the same finding keeps the same id across rebuilds and shadow diffs can tell new vs unchanged."""
    return f"{prefix}_" + short_hash(*semantic_parts)
