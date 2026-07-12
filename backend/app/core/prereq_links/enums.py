"""Enums for the prerequisite-links contracts (PREREQ_LINKS_SPEC v8). Pure — no app imports.

PR1 scope: the typed data contracts + Tier-2 structural validation. Dark behind `AZALEA_PREREQ_LINKS`; this
package is pure pydantic + stdlib so it is safe to import in tests (no .env / route contamination)."""
from __future__ import annotations

from enum import Enum


class Classification(str, Enum):              # §1.1 — the disjoint discriminant
    in_path_foundation = "in_path_foundation"        # required AND in scope → may emit a teaching topic
    assumed_prerequisite = "assumed_prerequisite"    # required but OUT of scope → delivered by a link


class ScopeRule(str, Enum):                   # §3.1 — which scope rule fired (structured, for shadow eval)
    explicit_objective = "explicit_objective"                # rule 1
    beginner_minimum_sequence = "beginner_minimum_sequence"  # rule 2
    competency_required = "competency_required"              # rule 3
    source_or_user_objective = "source_or_user_objective"    # rule 4
    recognition_only_fallback = "recognition_only_fallback"  # else → assumed_prerequisite


# The four rules that place a dependency IN scope (an in_path_foundation must use one of these; §6.3a).
IN_SCOPE_RULES: frozenset[ScopeRule] = frozenset({
    ScopeRule.explicit_objective,
    ScopeRule.beginner_minimum_sequence,
    ScopeRule.competency_required,
    ScopeRule.source_or_user_objective,
})


class Provenance(str, Enum):                  # §1.1a/§1.2
    decomposition = "decomposition"
    source_explicit = "source_explicit"
    inferred = "inferred"


class FallbackReason(str, Enum):              # §6.3a — structured Tier-2 failure codes (never free text)
    prerequisite_topic_overlap = "prerequisite_topic_overlap"        # disjointness violated (§A11)
    missing_target_goal = "missing_target_goal"                      # assumed_prereq w/ empty target_goal (§A15)
    duplicate_concept_ownership = "duplicate_concept_ownership"      # two owners for one concept_id (§A37)
    ambiguous_navigation_identity = "ambiguous_navigation_identity"  # one alias → >1 nav concept_id
    invalid_scope_rule = "invalid_scope_rule"                        # scope_rule doesn't match the variant
    missing_owner_for_review = "missing_owner_for_review"            # review ref with no / >1 owner
    duplicate_identity_key = "duplicate_identity_key"                # topic_id / concept_id uniqueness broken


class LinkAction(str, Enum):                  # §1.3 — InteractiveLink.action (existing enum, mirrored here)
    popup_only = "popup_only"
    open_study_path = "open_study_path"
    review_earlier_topic = "review_earlier_topic"
    ask_question = "ask_question"
