"""V2 lesson schema migration.

When the v2 lesson contract (LessonV2 / VisualModel / VisualFrame /
RenderStep) evolves, cached `lesson_json` rows in the database may not
match the new shape. This module:

  1. Carries a CURRENT_LESSON_SCHEMA_VERSION constant.
  2. Provides `migrate_stored_lesson(lesson_json)` that runs registered
     migration steps in order, lifting an old lesson_json to the latest.
  3. Provides `migrate_all_lessons_in_db(db)` for a one-shot pass over
     every v2 lesson row at deploy time.

Migrations register themselves by appending to `_MIGRATION_STEPS`.
Each step has a `from_version` and a function that mutates a lesson_json
dict to bring it up to the next version.

No-op when the lesson is already at CURRENT_LESSON_SCHEMA_VERSION or is
not a v2 lesson at all (e.g. legacy lessons pass through unchanged).
"""

from __future__ import annotations

import logging
from typing import Any, Callable, TYPE_CHECKING

from sqlalchemy.orm import Session

if TYPE_CHECKING:
    pass  # Lesson import is deferred to runtime to avoid circular import

_logger = logging.getLogger(__name__)


# Bump this when a v2 schema change requires a migration.
CURRENT_LESSON_SCHEMA_VERSION = 1


# Each migration step is (from_version, lift_function).
# lift_function takes a lesson_json dict and mutates it in-place to bring
# it to from_version + 1. Functions should be idempotent.
_MIGRATION_STEPS: list[tuple[int, Callable[[dict[str, Any]], None]]] = []


def register_migration(
    from_version: int,
) -> Callable[[Callable[[dict[str, Any]], None]], Callable[[dict[str, Any]], None]]:
    """Decorator: register a migration step that runs when the lesson's
    schema_version equals `from_version`.

    Example:
        @register_migration(from_version=1)
        def add_practice_question_id_to_render_steps(lesson):
            for step in lesson.get("render_steps") or []:
                if "practice_question_id" not in step:
                    step["practice_question_id"] = None
    """

    def decorator(fn: Callable[[dict[str, Any]], None]) -> Callable[[dict[str, Any]], None]:
        _MIGRATION_STEPS.append((from_version, fn))
        # Keep them sorted so migrate_stored_lesson can iterate in order.
        _MIGRATION_STEPS.sort(key=lambda x: x[0])
        return fn

    return decorator


def _stored_version(lesson_json: dict[str, Any]) -> int:
    """Read the schema version off a lesson_json. Defaults to 0 (pre-
    migration tracking) so a first migration moves it to 1."""
    metadata = lesson_json.get("metadata") or {}
    try:
        return int(metadata.get("schema_version") or 0)
    except (TypeError, ValueError):
        return 0


def _set_version(lesson_json: dict[str, Any], version: int) -> None:
    metadata = lesson_json.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
        lesson_json["metadata"] = metadata
    metadata["schema_version"] = version


def migrate_stored_lesson(lesson_json: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Lift a stored lesson_json to the current schema version.

    Returns (migrated_lesson, changed). `changed` is True when at least
    one migration step ran.

    No-op for non-v2 lessons (returns as-is, changed=False).
    """
    if not isinstance(lesson_json, dict):
        return lesson_json, False
    if int(lesson_json.get("lesson_version") or 0) != 2:
        # Not a v2 lesson — pass through.
        return lesson_json, False

    current_version = _stored_version(lesson_json)
    changed = False
    for from_version, step in _MIGRATION_STEPS:
        if current_version != from_version:
            continue
        try:
            step(lesson_json)
        except Exception as exc:  # noqa: BLE001
            _logger.warning(
                "v2 lesson migration step at from_version=%s raised: %s",
                from_version,
                exc,
            )
            break
        current_version = from_version + 1
        _set_version(lesson_json, current_version)
        changed = True

    # Ensure terminal version stamp is present even if no step ran
    if _stored_version(lesson_json) != CURRENT_LESSON_SCHEMA_VERSION and not changed:
        _set_version(lesson_json, CURRENT_LESSON_SCHEMA_VERSION)
        changed = True

    return lesson_json, changed


def migrate_all_lessons_in_db(db: Session) -> dict[str, Any]:
    """Walk every v2 lesson in the DB and run migrations. Returns a
    summary dict {total, migrated, errors}. Safe to call at app startup.
    """
    # Deferred import to avoid circular dependency at module load time.
    from app.models.lesson import Lesson

    summary = {"total": 0, "migrated": 0, "errors": 0}
    lessons = (
        db.query(Lesson)
        .filter(Lesson.lesson_json.isnot(None))
        .all()
    )
    for lesson in lessons:
        if not isinstance(lesson.lesson_json, dict):
            continue
        if int(lesson.lesson_json.get("lesson_version") or 0) != 2:
            continue
        summary["total"] += 1
        try:
            _, changed = migrate_stored_lesson(lesson.lesson_json)
            if changed:
                # SQLAlchemy needs an explicit flag for in-place JSON mutation
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(lesson, "lesson_json")
                summary["migrated"] += 1
        except Exception as exc:  # noqa: BLE001
            _logger.warning("migrate_all_lessons_in_db: lesson %s failed: %s", lesson.id, exc)
            summary["errors"] += 1
    if summary["migrated"]:
        db.commit()
    return summary


# ---------------------------------------------------------------------------
# Registered migrations. Add new ones below as the v2 schema evolves.
# ---------------------------------------------------------------------------


@register_migration(from_version=0)
def _add_practice_question_id_field(lesson: dict[str, Any]) -> None:
    """Migration 0 → 1: ensure every render_step has practice_question_id
    (added 2026-06-04 in the v2 practice card work). Earlier v2 lessons
    were stored before this field existed."""
    for step in (lesson.get("render_steps") or []):
        if not isinstance(step, dict):
            continue
        if "practice_question_id" not in step:
            step["practice_question_id"] = None
