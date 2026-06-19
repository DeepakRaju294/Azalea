"""Lesson freshness/caching policy.

Caching is ON (saved lessons are served on read), which makes rendering reliable: when a long
streaming generation drops before its `complete` event, the fallback read still returns the lesson
the generator just saved instead of regenerating it forever.

`fresh_on_open` (testing): when True, the STREAMING open regenerates the lesson from scratch each
time a topic is opened — so you still see the true, end-to-end effect of generation changes — while
every other read (the fallback, re-renders) serves the freshly-saved copy. Pre-generation warmers
are skipped in this mode since each open regenerates anyway.

Set AZALEA_FRESH_ON_OPEN=0 to serve cached lessons on open too (no per-open regeneration). Read at
call time so it can be toggled without a restart.
"""
from __future__ import annotations

import os


def fresh_on_open() -> bool:
    # Default OFF: serve the saved lesson on open (instant, reliable) — a multi-minute generation
    # cannot survive a single streaming request, so regenerating on every open leaves topics stuck
    # in "generating". Regenerate explicitly with regen_lesson.py to test fresh output. Set
    # AZALEA_FRESH_ON_OPEN=1 to opt back into per-open regeneration.
    return os.getenv("AZALEA_FRESH_ON_OPEN", "0") == "1"
