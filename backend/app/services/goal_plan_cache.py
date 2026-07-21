"""Goal-keyed curriculum persistence (scope-plan increment #3).

The single biggest driver of topic-count variance across identical goals is the requirements-first
curriculum call itself (topic_decomposition_pipeline._goal_requirements) — a fresh LLM turn every time,
with real sampling variance (live: 'fluid turbulence' produced 3, then 2, then 1, then 4, then 2 teaching
topics across five same-evening regens, each starting from a DIFFERENT set of curriculum requirements).

This caches ONLY the curriculum (requirements + external assumed_prerequisites) — deliberately narrow.
Everything downstream (decomposition against those requirements, coverage repair, certification, family-
survey backfill, card grounding) still runs FRESH on every generation, so a bug fix to any of those passes
benefits a cached-curriculum generation exactly as much as a fresh one. Caching the full topic list would
freeze in whatever bugs existed in the SHAPING layer at cache-write time; caching just the curriculum
stabilizes the "what must this course cover" axis (the actual source of the lottery) without doing that.

Off by default (`AZALEA_GOAL_PLAN_CACHE` unset) — the whole point of a flag here is that ~350 existing
tests call `_goal_requirements`/`generate_decomposed_topics` directly with an injected `model_fn` and
assert exact call counts; an always-on cache would make those order-dependent on whatever goal string a
PRIOR test happened to use. Enable with `AZALEA_GOAL_PLAN_CACHE=1` (defaults to
`telemetry/goal_plan_cache.json`) or point `AZALEA_GOAL_PLAN_CACHE_PATH` at an explicit file.

Best-effort throughout: a cache read/write failure must never break generation — worst case, the requirements
call just runs as it always did.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from typing import Any, Optional

_log = logging.getLogger(__name__)

_DEFAULT_PATH = os.path.join("telemetry", "goal_plan_cache.json")


def _enabled() -> bool:
    return os.getenv("AZALEA_GOAL_PLAN_CACHE", "").strip().lower() in ("1", "true", "on", "yes")


def _cache_path() -> Optional[str]:
    if not _enabled():
        return None
    return os.getenv("AZALEA_GOAL_PLAN_CACHE_PATH") or _DEFAULT_PATH


def goal_key_for(goal: Optional[str]) -> str:
    """The same canonical-identity key certification uses for goal_core matching — already stems goal-
    intent filler ('want', 'about', 'i', ...) so phrasing variance ('learn fluid turbulence' vs 'I want to
    understand fluid turbulence') collapses onto one cache entry. Deferred import: topic_generator.py
    imports FROM topic_decomposition_pipeline.py (this module's caller), so importing it back here at
    module level would cycle — safe at call time since both modules are fully loaded by then."""
    from app.services.topic_generator import _canonical_concept_key
    return _canonical_concept_key(goal)


def _load(path: str) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:  # noqa: BLE001 — a corrupt cache file must never break generation
        _log.warning("goal_plan_cache: failed to read %s — treating as empty", path, exc_info=True)
        return {}


def _save(path: str, data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    dir_ = os.path.dirname(path) or "."
    fd, tmp_path = tempfile.mkstemp(prefix=".goal_plan_cache_", dir=dir_)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp_path, path)   # atomic on both POSIX and Windows — no torn reads
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def lookup_cached_plan(goal: Optional[str]) -> Optional[dict[str, Any]]:
    """The cached {requirements, assumed_prerequisites} for this goal, or None when disabled/missing/
    unreadable. Never raises."""
    path = _cache_path()
    if not path:
        return None
    try:
        key = goal_key_for(goal)
        if not key:
            return None
        entry = _load(path).get(key)
        if not isinstance(entry, dict) or not entry.get("requirements"):
            return None
        return {"requirements": entry["requirements"],
                "assumed_prerequisites": entry.get("assumed_prerequisites") or []}
    except Exception:  # noqa: BLE001 — a cache lookup failure must never break generation
        _log.warning("goal_plan_cache: lookup failed for goal %r", goal, exc_info=True)
        return None


def store_plan(goal: Optional[str], requirements: list[dict[str, Any]],
               assumed_prerequisites: list[dict[str, Any]]) -> None:
    """Upsert the curriculum for this goal's key. Overwrites any prior entry — the most recent REAL
    curriculum call (including a feedback-informed one) is treated as the best-known plan going forward.
    No-op when disabled or requirements is empty (never cache a failed/empty call)."""
    path = _cache_path()
    if not path or not requirements:
        return
    try:
        key = goal_key_for(goal)
        if not key:
            return
        data = _load(path)
        prior = data.get(key) if isinstance(data.get(key), dict) else {}
        data[key] = {
            "requirements": requirements,
            "assumed_prerequisites": assumed_prerequisites,
            "source_goal": str(goal or ""),
            "hit_count": int(prior.get("hit_count") or 0),
            "created_at": prior.get("created_at") or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        _save(path, data)
    except Exception:  # noqa: BLE001 — a cache write failure must never break generation
        _log.warning("goal_plan_cache: store failed for goal %r", goal, exc_info=True)


def record_cache_hit(goal: Optional[str]) -> None:
    """Best-effort hit-count bump — observability only, never blocks the (already-returned) cached result."""
    path = _cache_path()
    if not path:
        return
    try:
        key = goal_key_for(goal)
        data = _load(path)
        entry = data.get(key)
        if isinstance(entry, dict):
            entry["hit_count"] = int(entry.get("hit_count") or 0) + 1
            entry["last_hit_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            _save(path, data)
    except Exception:  # noqa: BLE001
        pass
