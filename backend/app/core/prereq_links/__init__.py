"""prereq_links — prerequisites-as-links contracts + Tier-2 structural validation (PREREQ_LINKS_SPEC v8).

PR1 ships the typed data contracts (§1) and the classification validator (§6.3a) only — no lesson generation,
no deterministic scan, no frontend. Dark behind `AZALEA_PREREQ_LINKS`. Pure package — pydantic + stdlib only,
so it is safe to import in tests (no .env / route contamination)."""
from __future__ import annotations

from .enums import (
    IN_SCOPE_RULES, Classification, FallbackReason, LinkAction, Provenance, ScopeRule,
)
from .models import (
    AssumedPrerequisite, DecompositionClassification, FoundationalDependency, InPathFoundation,
    PrerequisitePrioritySignals, PrerequisiteScopeWarning, TopicConceptIdentity,
)
from .validation import (
    ClassificationFailure, ClassificationValidationResult, normalize_identity, validate_classification,
)

__all__ = [
    # enums
    "Classification", "ScopeRule", "IN_SCOPE_RULES", "Provenance", "FallbackReason", "LinkAction",
    # models
    "InPathFoundation", "AssumedPrerequisite", "FoundationalDependency", "TopicConceptIdentity",
    "PrerequisitePrioritySignals", "PrerequisiteScopeWarning", "DecompositionClassification",
    # validation (§6.3a Tier-2)
    "validate_classification", "ClassificationValidationResult", "ClassificationFailure", "normalize_identity",
]
