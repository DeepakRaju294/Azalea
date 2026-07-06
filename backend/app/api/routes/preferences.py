"""Phase-1 user-preference endpoints (ONBOARDING_AND_PREFERENCE_CAPTURE_SPEC §3).

Mutable user-level defaults (depth / language / knowledge). These supply the *user default* tier of the
precedence chain `path override > user default > inferred > platform default`; per-path resolution + the immutable
per-generation snapshot live in `preference_service`. Changing a default here affects only FUTURE generations
(Q25) — it never regenerates an existing path. The DB logic lives in `preference_service` so it is unit-testable
without importing this module's `deps` chain.
"""
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.ownership import get_user_id
from app.models.preferences import PREFERENCE_SCHEMA_VERSION
from app.schemas.preferences import UserPreferenceRead, UserPreferenceUpdate
from app.services.preference_service import get_user_preference, upsert_user_preference

router = APIRouter()


def _empty_defaults() -> UserPreferenceRead:
    """A user with no stored row has all-None defaults (every field falls through to inferred/platform)."""
    return UserPreferenceRead(
        default_depth_level=None,
        default_language=None,
        default_knowledge_level=None,
        schema_version=PREFERENCE_SCHEMA_VERSION,
    )


@router.get("/", response_model=UserPreferenceRead)
def get_user_preferences(
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    pref = get_user_preference(db, get_user_id(current_user))
    return pref if pref is not None else _empty_defaults()


@router.put("/", response_model=UserPreferenceRead)
def update_user_preferences(
    payload: UserPreferenceUpdate,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    return upsert_user_preference(
        db, get_user_id(current_user), payload.model_dump(exclude_unset=True)
    )
