"""Cache-refresh trigger: an existing cached lesson stamped by an OLDER bridge version
re-enriches on read, so it picks up the latest fixes without manual regeneration.

Run: python -m unittest app.tests.test_cache_refresh
"""
from __future__ import annotations

import os
import sys
import types
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")
for _name in ("dotenv", "openai"):
    if _name not in sys.modules:
        try:
            __import__(_name)
        except ImportError:
            _m = types.ModuleType(_name)
            if _name == "dotenv":
                _m.load_dotenv = lambda *a, **k: None
            else:
                _m.OpenAI = lambda *a, **k: object()
                for _e in ("APIError", "RateLimitError", "APITimeoutError", "APIConnectionError"):
                    setattr(_m, _e, type(_e, (Exception,), {}))
            sys.modules[_name] = _m

from app.services.legacy_v2_visual_bridge import (
    VISUAL_BRIDGE_VERSION,
    needs_visual_refresh as lesson_json_needs_hybrid_visual_refresh,
)


def _lesson(bridge_meta):
    return {"lesson_cards": [{"id": "1", "blueprint_key": "background"}],
            "metadata": {"visual_v2_bridge": bridge_meta} if bridge_meta is not None else {}}


class TestCacheRefresh(unittest.TestCase):
    def test_no_bridge_metadata_refreshes(self):
        self.assertTrue(lesson_json_needs_hybrid_visual_refresh(_lesson(None)))

    def test_old_unversioned_stamp_refreshes(self):
        # legacy lessons stamped before versions existed → treated as v1 → refresh.
        self.assertTrue(lesson_json_needs_hybrid_visual_refresh(_lesson({"enabled": True})))

    def test_older_version_refreshes(self):
        self.assertTrue(lesson_json_needs_hybrid_visual_refresh(
            _lesson({"enabled": True, "version": VISUAL_BRIDGE_VERSION - 1})))

    def test_current_version_does_not_refresh(self):
        self.assertFalse(lesson_json_needs_hybrid_visual_refresh(
            _lesson({"enabled": True, "version": VISUAL_BRIDGE_VERSION})))

    def test_newer_version_does_not_refresh(self):
        self.assertFalse(lesson_json_needs_hybrid_visual_refresh(
            _lesson({"enabled": True, "version": VISUAL_BRIDGE_VERSION + 1})))


if __name__ == "__main__":
    unittest.main()
