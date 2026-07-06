"""Phase-1 preference resolver (ONBOARDING_AND_PREFERENCE_CAPTURE_SPEC §3, D1).

Covers the PURE precedence logic `path override > user default > inferred > platform default` and the language
active/inactive split. The DB snapshot writer is exercised via integration (needs Postgres/JSONB), not here.

Run: python -m unittest app.tests.test_preference_service
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

import app.db.base  # noqa: F401 — register models before the lazy model imports in the service run

from app.services.preference_service import (
    PROV_INFERRED, PROV_SAVED_DEFAULT, PROV_SYSTEM_DEFAULT, PROV_USER_SELECTED,
    contract_versions, get_user_preference, resolve_preferences, scope_directive, upsert_user_preference,
)
from app.models.preferences import PREFERENCE_SCHEMA_VERSION, UserPreference


class _FakeQuery:
    def __init__(self, result):
        self._result = result

    def filter(self, *a, **k):
        return self

    def one_or_none(self):
        return self._result


class _FakeSession:
    """Minimal stand-in for a SQLAlchemy Session — the repo has no DB-backed test harness, so the CRUD branches
    (missing vs existing row, partial upsert, schema stamping) are exercised without a live Postgres."""

    def __init__(self, existing=None):
        self.existing = existing
        self.added: list = []
        self.committed = False

    def query(self, *a, **k):
        return _FakeQuery(self.existing)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed = True

    def refresh(self, obj):
        pass


class ResolvePreferences(unittest.TestCase):
    def test_coding_defaults(self):
        selected, effective, prov = resolve_preferences(domain="coding")
        self.assertEqual(effective["domain"], "coding")
        self.assertEqual(prov["domain"], PROV_INFERRED)               # classifier seed, no confirmation surface
        self.assertEqual(effective["depth_level"], "working")
        self.assertEqual(prov["depth_level"], PROV_SYSTEM_DEFAULT)
        self.assertEqual(effective["language"], "python")
        self.assertEqual(effective["language_status"], "active_coding")
        self.assertEqual(prov["language"], PROV_SYSTEM_DEFAULT)        # bare default python is NOT a selection
        self.assertEqual(selected, {})

    def test_non_coding_language_inactive(self):
        _, effective, prov = resolve_preferences(domain="math", path_language="java")
        self.assertIsNone(effective["language"])                      # language had NO effect on a math path
        self.assertEqual(effective["language_status"], "inactive_non_coding")

    def test_explicit_path_language_is_a_selection(self):
        _, effective, prov = resolve_preferences(domain="coding", path_language="java")
        self.assertEqual(effective["language"], "java")
        self.assertEqual(prov["language"], PROV_USER_SELECTED)

    def test_user_default_depth_wins_over_platform(self):
        _, effective, prov = resolve_preferences(domain="physics", user_default_depth="deep")
        self.assertEqual(effective["depth_level"], "deep")
        self.assertEqual(prov["depth_level"], PROV_SAVED_DEFAULT)

    def test_selected_overrides_user_default(self):
        _, effective, prov = resolve_preferences(
            domain="coding", user_default_depth="deep", selected={"depth_level": "intuition"})
        self.assertEqual(effective["depth_level"], "intuition")
        self.assertEqual(prov["depth_level"], PROV_USER_SELECTED)

    def test_selected_domain_override(self):
        _, effective, prov = resolve_preferences(domain="coding", selected={"domain": "math"})
        self.assertEqual(effective["domain"], "math")
        self.assertEqual(prov["domain"], PROV_USER_SELECTED)

    def test_coarse_domain_override_drives_language_activity(self):
        # a selected coarse "concept" override is non-coding → language inactive; "coding" → active
        _, eff_concept, _ = resolve_preferences(domain="physics", selected={"domain": "concept"})
        self.assertEqual(eff_concept["domain"], "concept")
        self.assertEqual(eff_concept["language_status"], "inactive_non_coding")
        _, eff_coding, prov = resolve_preferences(domain="math", selected={"domain": "coding"})
        self.assertEqual(eff_coding["domain"], "coding")
        self.assertEqual(eff_coding["language_status"], "active_coding")
        self.assertEqual(prov["domain"], PROV_USER_SELECTED)

    def test_path_override_depth_beats_user_default(self):
        _, eff, prov = resolve_preferences(
            domain="coding", user_default_depth="working", selected={"depth_level": "deep"})
        self.assertEqual(eff["depth_level"], "deep")
        self.assertEqual(prov["depth_level"], PROV_USER_SELECTED)

    def test_goal_scope_surfaced_from_override(self):
        _, eff, prov = resolve_preferences(domain="math", selected={"goal_scope": "focus on recursion only"})
        self.assertEqual(eff["goal_scope"], "focus on recursion only")
        self.assertEqual(prov["goal_scope"], PROV_USER_SELECTED)

    def test_goal_scope_absent_is_system_default(self):
        _, eff, prov = resolve_preferences(domain="math")
        self.assertIsNone(eff["goal_scope"])
        self.assertEqual(prov["goal_scope"], PROV_SYSTEM_DEFAULT)

    def test_scope_directive_pure(self):
        self.assertIsNone(scope_directive(None))
        self.assertIsNone(scope_directive("   "))
        d = scope_directive("only cover DFS and BFS")
        self.assertIn("only cover DFS and BFS", d)

    def test_knowledge_level_always_inactive(self):
        _, effective, prov = resolve_preferences(domain="coding", user_default_knowledge=3)
        self.assertIsNone(effective["knowledge_level"])
        self.assertIn("knowledge_level", effective["inactive_fields"])
        self.assertEqual(prov["knowledge_level"], "phase_2_consumer_not_live")

    def test_contract_versions_shape(self):
        cv = contract_versions()
        for k in ("gate_version", "rewrite_version", "classifier_version", "preference_schema_version"):
            self.assertIn(k, cv)

    def test_schema_version_mirror_matches_model(self):
        # the service mirrors the constant lazily to avoid an import cycle — assert it never drifts
        self.assertEqual(contract_versions()["preference_schema_version"], PREFERENCE_SCHEMA_VERSION)


class UserPreferenceCrud(unittest.TestCase):
    def test_get_missing_returns_none(self):
        self.assertIsNone(get_user_preference(_FakeSession(existing=None), "u1"))

    def test_get_existing_returns_row(self):
        pref = UserPreference(user_id="u1", default_depth_level="deep")
        self.assertIs(get_user_preference(_FakeSession(existing=pref), "u1"), pref)

    def test_upsert_creates_row_when_absent(self):
        db = _FakeSession(existing=None)
        out = upsert_user_preference(db, "u1", {"default_depth_level": "deep", "default_language": "java"})
        self.assertEqual(out.user_id, "u1")
        self.assertEqual(out.default_depth_level, "deep")
        self.assertEqual(out.default_language, "java")
        self.assertEqual(out.schema_version, PREFERENCE_SCHEMA_VERSION)
        self.assertIn(out, db.added)
        self.assertTrue(db.committed)

    def test_upsert_partial_leaves_unset_untouched(self):
        pref = UserPreference(user_id="u1", default_depth_level="working", default_language="python")
        db = _FakeSession(existing=pref)
        out = upsert_user_preference(db, "u1", {"default_depth_level": "deep"})
        self.assertEqual(out.default_depth_level, "deep")     # provided → updated
        self.assertEqual(out.default_language, "python")      # unset → unchanged
        self.assertEqual(db.added, [])                        # existing row, nothing added

    def test_upsert_explicit_none_clears_default(self):
        pref = UserPreference(user_id="u1", default_language="java")
        out = upsert_user_preference(_FakeSession(existing=pref), "u1", {"default_language": None})
        self.assertIsNone(out.default_language)

    def test_upsert_ignores_non_mutable_keys(self):
        db = _FakeSession(existing=None)
        out = upsert_user_preference(db, "u1", {"user_id": "hacked", "schema_version": 999})
        self.assertEqual(out.user_id, "u1")                   # protected key not overwritten from updates
        self.assertEqual(out.schema_version, PREFERENCE_SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
