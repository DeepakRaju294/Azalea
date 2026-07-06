"""Phase-2 rollout modes — AZALEA_DOMAIN_NARRATION_V2 (DOMAIN_CARD_NARRATION_AND_RENDERING_SPEC §9.1).

Three modes form a rollout ladder (not off→on):
- `off_legacy`      — pre-rollout / dev baseline ONLY: existing narration + renderer. NOT eligible for production
                      once any card/domain contract is activated (old math/science narration is the unsafe thing
                      this work removes).
- `shadow_validate` — production shows an approved safe/legacy path; Phase-2 contracts + fact-source +
                      render-model validation run WITHOUT display; telemetry compares outcomes.
- `on_enforced`     — approved Phase-2 contracts + spike-approved renderer shown; a validation failure uses only
                      an approved same-domain fallback, else WITHHOLDS the card/path with a typed error.

Scope is PER FAMILY (`RolloutFamily`), so a science failure never rolls back math/coding. **Hard rule:** once a
family enters shadow_validate/on_enforced it may NOT return to off_legacy — its only rollback targets are
shadow_validate or an approved same-domain fallback. The default global mode comes from the env flag; per-family
overrides live in `_FAMILY_MODES`.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

OFF_LEGACY = "off_legacy"
SHADOW_VALIDATE = "shadow_validate"
ON_ENFORCED = "on_enforced"
MODES = (OFF_LEGACY, SHADOW_VALIDATE, ON_ENFORCED)

_ENV_FLAG = "AZALEA_DOMAIN_NARRATION_V2"


@dataclass(frozen=True)
class RolloutFamily:
    """A rollout unit + its live mode/versions (§9.1 telemetry attributes)."""
    topic_domain: str
    card_type: str
    optional_topic_type: Optional[str] = None
    mode: str = OFF_LEGACY
    contract_version: str = "v1"
    renderer_version: str = "v1"
    fallback_allowlist_version: str = "v1"


def _default_mode() -> str:
    """Global default from the env flag (unset/invalid ⇒ off_legacy, the dev baseline)."""
    v = str(os.getenv(_ENV_FLAG, "") or "").strip().lower()
    return v if v in MODES else OFF_LEGACY


# Per-family mode overrides. Keyed by (topic_domain, card_type, optional_topic_type). The first slice — math /
# math_formula_method / completing-the-square — CANNOT enter on_enforced until formula_breakdown (math) is
# `defined` (§2.1); until then it runs in shadow_validate. Seeded empty of on_enforced entries deliberately.
_FAMILY_MODES: dict[tuple[str, str, Optional[str]], str] = {}


def set_family_mode(topic_domain: str, card_type: str, mode: str,
                    optional_topic_type: Optional[str] = None) -> None:
    """Register/override a family's mode (validated). Enforces the ladder direction: a family already at
    shadow_validate/on_enforced may not be set back to off_legacy (§9.1)."""
    if mode not in MODES:
        raise ValueError(f"unknown narration mode: {mode!r}")
    key = (topic_domain, card_type, optional_topic_type)
    current = _FAMILY_MODES.get(key)
    if current in (SHADOW_VALIDATE, ON_ENFORCED) and mode == OFF_LEGACY:
        raise ValueError(
            f"family {key} is live ({current}); cannot roll back to off_legacy — use shadow_validate (§9.1)"
        )
    _FAMILY_MODES[key] = mode


def resolve_mode(topic_domain: str, card_type: str,
                 optional_topic_type: Optional[str] = None) -> str:
    """The active mode for a (domain, card_type[, topic_type]) family: the most specific registered override,
    else the topic-type-agnostic family override, else the global default."""
    for key in ((topic_domain, card_type, optional_topic_type), (topic_domain, card_type, None)):
        if key in _FAMILY_MODES:
            return _FAMILY_MODES[key]
    return _default_mode()


def rollback_target(current_mode: str) -> str:
    """Where a live family rolls back to on failure — NEVER off_legacy once live (§9.1). A shadow family that
    can't safely display would be handled by the no-safe-display rule (caller), not by dropping to off_legacy."""
    if current_mode == ON_ENFORCED:
        return SHADOW_VALIDATE
    return SHADOW_VALIDATE


def rollout_family(topic_domain: str, card_type: str,
                   optional_topic_type: Optional[str] = None) -> RolloutFamily:
    """Build the telemetry-bearing RolloutFamily record for the resolved mode."""
    return RolloutFamily(
        topic_domain=topic_domain,
        card_type=card_type,
        optional_topic_type=optional_topic_type,
        mode=resolve_mode(topic_domain, card_type, optional_topic_type),
    )
