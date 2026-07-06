"""Phase-1 preference resolution + generation-snapshot capture (ONBOARDING_AND_PREFERENCE_CAPTURE_SPEC §3, D1).

Two layers:
- `resolve_preferences(...)` — PURE. Applies the §3 precedence `path override > user default > inferred >
  platform default` per field and returns (selected, effective, provenance). No DB/ORM, fully unit-testable.
- `write_generation_snapshot(db, study_path)` — writes the immutable `StudyPathGeneration` row for one generation
  and repoints `StudyPath.active_generation_id`. Best-effort: a snapshot failure must NEVER block content
  generation (it is observability/provenance, not a generation dependency).

Phase-1 scope note: with no wizard live yet, `selected` (path overrides) is empty, so `effective` = user default →
platform default, and `domain` provenance is `inferred` (no user confirmation surface exists yet). `language`
keeps the existing per-path value; the honest 4-field language model (requested/applied/status/selector) lands
with the language preflight (§5) — not encoded here. `knowledge_level` is recorded INACTIVE (Phase-2 consumer).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.services.domain_classifier import gate_family_of
from app.services.domain_gate import GATE_VERSION, REWRITE_VERSION

_log = logging.getLogger(__name__)

# Stamped into domain_provenance / snapshots — keep in sync with routes.study_paths._CLASSIFIER_VERSION.
_CLASSIFIER_VERSION = "v1"
# Mirror of app.models.preferences.PREFERENCE_SCHEMA_VERSION. The model import is done LAZILY inside the DB
# functions to avoid the app.models ↔ app.db.base import cycle when this service is imported first; this constant
# is asserted equal to the model's in the unit tests, so drift is caught.
_PREFERENCE_SCHEMA_VERSION = 1

# Platform defaults — the lowest precedence tier (§3).
PLATFORM_DEFAULTS: dict[str, Any] = {"depth_level": "working", "language": "python", "knowledge_level": None}

# The user-level default fields a client may upsert (guards against writing arbitrary columns).
MUTABLE_PREFERENCE_FIELDS = ("default_depth_level", "default_language", "default_knowledge_level")

# Provenance labels (§3): richer than inferred/user so "saw Python & clicked Next" ≠ "system guessed Python".
PROV_INFERRED = "inferred"
PROV_USER_CONFIRMED = "user_confirmed"
PROV_USER_SELECTED = "user_selected"
PROV_SAVED_DEFAULT = "saved_default"
PROV_SYSTEM_DEFAULT = "system_default"


def contract_versions() -> dict[str, Any]:
    """Version stamps of every contract that shaped a generation (kept on the snapshot for explainability)."""
    return {
        "gate_version": GATE_VERSION,
        "rewrite_version": REWRITE_VERSION,
        "classifier_version": _CLASSIFIER_VERSION,
        "preference_schema_version": _PREFERENCE_SCHEMA_VERSION,
    }


def _pick(field: str, selected: dict[str, Any], user_default: Optional[Any], inferred: Optional[Any]):
    """Resolve one field by precedence, returning (value, provenance). `selected` = an explicit path override
    (user_selected); `user_default` = the saved user tier; `inferred` = a classifier/plan-derived seed; else the
    platform default."""
    if field in selected and selected[field] is not None:
        return selected[field], PROV_USER_SELECTED
    if user_default is not None:
        return user_default, PROV_SAVED_DEFAULT
    if inferred is not None:
        return inferred, PROV_INFERRED
    return PLATFORM_DEFAULTS.get(field), PROV_SYSTEM_DEFAULT


def resolve_preferences(
    *,
    domain: Optional[str],
    path_language: Optional[str] = None,
    user_default_depth: Optional[str] = None,
    user_default_language: Optional[str] = None,
    user_default_knowledge: Optional[int] = None,
    selected: Optional[dict[str, Any]] = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """PURE. Return (selected, effective, provenance) for one generation.

    - `domain`: the Phase-0 inferred fine domain (or a user-selected override in `selected`).
    - `path_language`: the existing `StudyPath.language` (the current per-path language) — only meaningful for a
      coding-family path; non-coding paths record `null` (language had no effect).
    """
    selected = dict(selected or {})
    is_coding = gate_family_of(selected.get("domain") or domain) == "coding"

    # domain — user override wins; otherwise the classifier inference seeds it (no confirmation surface yet).
    if selected.get("domain"):
        eff_domain, domain_prov = selected["domain"], PROV_USER_SELECTED
    else:
        eff_domain, domain_prov = domain, PROV_INFERRED

    # depth — no inference tier (we don't guess depth); user default → platform default.
    eff_depth, depth_prov = _pick("depth_level", selected, user_default_depth, None)

    # language — only active on a coding path. A NON-default `path_language` (StudyPath.language, set via the
    # language endpoint) counts as a prior explicit selection; a bare default `python` does not (the existing
    # column can't distinguish "chose python" from "never chose" — the honest 4-field model lands with §5).
    if is_coding:
        lang_selected = dict(selected)
        if ("language" not in lang_selected and path_language
                and path_language != PLATFORM_DEFAULTS["language"]):
            lang_selected["language"] = path_language
        eff_language, lang_prov = _pick("language", lang_selected, user_default_language, None)
        language_status = "active_coding"
    else:
        eff_language, lang_prov, language_status = None, PROV_SYSTEM_DEFAULT, "inactive_non_coding"

    # goal_scope — Phase-3 scope contract (free-text focus/boundaries); consumed as a generation steering hint.
    goal_scope = selected.get("goal_scope") or None

    # knowledge_level — stored but INACTIVE until a Phase-2 consumer exists (§3 "stored without being active").
    effective = {
        "domain": eff_domain,
        "depth_level": eff_depth,
        "language": eff_language,
        "language_status": language_status,
        "goal_scope": goal_scope,
        "knowledge_level": None,
        "inactive_fields": {"knowledge_level": {"reason": "phase_2_consumer_not_live"}},
    }
    provenance = {
        "domain": domain_prov,
        "depth_level": depth_prov,
        "language": lang_prov,
        "goal_scope": PROV_USER_SELECTED if goal_scope else PROV_SYSTEM_DEFAULT,
        "knowledge_level": "phase_2_consumer_not_live",
    }
    return selected, effective, provenance


def scope_directive(goal_scope: str | None) -> str | None:
    """Phase-3 scope-contract consumer (onboarding `goal`). Turn a learner's free-text focus/boundaries into a
    normalized generation steering directive (or None). Pure; the caller folds it into the generation feedback
    channel so topic selection honors the stated scope without changing adapter-computed truth."""
    text = str(goal_scope or "").strip()
    if not text:
        return None
    return ("Learner-specified scope for this path — keep topics within this focus and respect any stated "
            f"boundaries: {text}")


def write_generation_snapshot(
    db: Session,
    study_path: Any,
    *,
    selected: Optional[dict[str, Any]] = None,
    topics: Optional[list[dict[str, Any]]] = None,
) -> Optional[StudyPathGeneration]:
    """Write an immutable generation snapshot and repoint `study_path.active_generation_id`. Best-effort — logs
    and returns None on failure without raising (must never block generation). When `topics` are supplied, the
    honest path-level effective depth is computed + disclosed (§4.2)."""
    from app.models.preferences import StudyPathGeneration, UserPreference  # lazy — breaks the base import cycle
    try:
        # The per-path override (top precedence tier). Falls back to the path's stored selection; a
        # user-selected domain is folded in so its provenance resolves as user_selected (not inferred).
        if selected is None:
            selected = dict(getattr(study_path, "selected_preferences", None) or {})
        else:
            selected = dict(selected)
        if study_path.classification_status == "user_selected" and study_path.domain:
            selected.setdefault("domain", study_path.domain)

        user_pref = (
            db.query(UserPreference)
            .filter(UserPreference.user_id == study_path.user_id)
            .one_or_none()
        )
        sel, effective, provenance = resolve_preferences(
            domain=study_path.domain,
            path_language=getattr(study_path, "language", None),
            user_default_depth=getattr(user_pref, "default_depth_level", None),
            user_default_language=getattr(user_pref, "default_language", None),
            user_default_knowledge=getattr(user_pref, "default_knowledge_level", None),
            selected=selected,
        )
        # Honest path-level effective depth (§4.2) — deep is only material when a topic can actually expand.
        if topics is not None:
            from app.services.depth_profile import compute_effective_depth
            topic_types = [t.get("topic_type") or t.get("course_type") for t in topics]
            effective["depth_resolution"] = compute_effective_depth(effective.get("depth_level"), topic_types)
        next_number = (
            db.query(func.max(StudyPathGeneration.generation_number))
            .filter(StudyPathGeneration.study_path_id == study_path.id)
            .scalar()
            or 0
        ) + 1
        snapshot = StudyPathGeneration(
            study_path_id=study_path.id,
            generation_number=next_number,
            domain=study_path.domain,
            classification_status=study_path.classification_status,
            selected_preferences_json=sel,
            effective_preferences_json=effective,
            preference_provenance_json=provenance,
            contract_versions_json=contract_versions(),
        )
        db.add(snapshot)
        db.flush()
        study_path.active_generation_id = snapshot.id
        db.commit()
        db.refresh(study_path)
        return snapshot
    except Exception as exc:  # noqa: BLE001 — provenance capture must never break content generation
        _log.warning("preference_service: generation snapshot failed (%s) — continuing", exc)
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return None


# --- user-level defaults CRUD (§3) — kept here so the route stays a thin delegator and can be unit-tested
# without importing app.api.deps (which calls load_dotenv() at import and would leak .env flags into tests). ----
def get_user_preference(db: Session, user_id: str) -> Any:
    """Return the user's `UserPreference` row, or None if they have no stored defaults yet."""
    from app.models.preferences import UserPreference  # lazy — breaks the base import cycle
    return db.query(UserPreference).filter(UserPreference.user_id == user_id).one_or_none()


def upsert_user_preference(db: Session, user_id: str, updates: dict[str, Any]) -> Any:
    """Create-or-update the user's defaults. Only keys in `MUTABLE_PREFERENCE_FIELDS` are written (a present key
    with value None clears that default); `schema_version` is re-stamped. Returns the persisted row."""
    from app.models.preferences import PREFERENCE_SCHEMA_VERSION, UserPreference  # lazy — see above
    pref = db.query(UserPreference).filter(UserPreference.user_id == user_id).one_or_none()
    if pref is None:
        pref = UserPreference(user_id=user_id)
        db.add(pref)
    for field in MUTABLE_PREFERENCE_FIELDS:
        if field in updates:
            setattr(pref, field, updates[field])
    pref.schema_version = PREFERENCE_SCHEMA_VERSION
    db.commit()
    db.refresh(pref)
    return pref
