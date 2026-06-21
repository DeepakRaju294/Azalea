"""Shadow + visual feature flags (spec §1, §12 step 2; §10.6).

The generation-foundation work is built behind a shadow flag so the new single-pass
schemas/validators can run and be measured without changing production output. Visuals
have their own switch (VGA §14) that stays off until the renderer is wired.

Both default OFF. Reading them never has side effects.
"""
from __future__ import annotations

import os

_TRUTHY = {"1", "true", "yes", "on"}


def _flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in _TRUTHY


def is_shadow_enabled() -> bool:
    """`AZALEA_GEN_FOUNDATION_SHADOW` — run the new single-pass path in shadow (§12)."""
    return _flag("AZALEA_GEN_FOUNDATION_SHADOW")


def is_visuals_enabled() -> bool:
    """`AZALEA_VISUALS_ENABLED` — trigger visual generation/render (VGA §14). Default false."""
    return _flag("AZALEA_VISUALS_ENABLED")
