"""Diagnostic: is the v2 enrichment pipeline actually running on a stored lesson?

Usage (run from the backend/ directory):
    python check_lesson.py "merge sort"      # match a topic by title substring (case-insensitive)
    python check_lesson.py --id <topic_id>   # match a topic by exact id

It answers "are my changes executing?" by showing, for the matched lesson:
  * the bridge VERSION stamped on the cached lesson vs. the current code version,
    and whether a re-enrich will fire on the next read;
  * the enrichment STAMPS the pipeline writes (clean_code_repair, worked_example_solver)
    — including the solver's reason when it produced nothing (e.g. no API key);
  * the code_walkthrough card shape: code line count vs. number of main bullets vs.
    the stored highlight ranges — so you can see whether the one-line-per-bullet
    structure is present yet (that part only changes when the lesson is REGENERATED).
"""
from __future__ import annotations

import json
import re
import sys

from app.db.database import SessionLocal
from app.db.base import Lesson, Topic  # importing via base loads all models in dependency order
from app.services.legacy_v2_visual_bridge import VISUAL_BRIDGE_VERSION, needs_visual_refresh


def _main_bullets(points) -> list[str]:
    return [str(p) for p in (points or []) if str(p).strip() and not re.match(r"^\s+-\s+", str(p))]


def _nonblank_lines(code: str) -> int:
    return sum(1 for ln in (code or "").splitlines() if ln.strip())


def _key(card: dict) -> str:
    return str(card.get("blueprint_key") or card.get("card_type") or "").lower()


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return

    db = SessionLocal()
    try:
        if args[0] == "--id" and len(args) > 1:
            topic = db.query(Topic).filter(Topic.id == args[1]).first()
        else:
            needle = " ".join(args)
            topic = (
                db.query(Topic)
                .filter(Topic.title.ilike(f"%{needle}%"))
                .order_by(Topic.created_at.desc())
                .first()
            )
        if not topic:
            print(f"No topic matched {args!r}.")
            return

        lesson = db.query(Lesson).filter(Lesson.topic_id == topic.id).first()
        print(f"TOPIC   : {topic.title}  (id={topic.id})")
        print(f"type    : {topic.course_type}")
        if not lesson:
            print("LESSON  : none stored.")
            return
        print(f"status  : {lesson.generation_status}")

        lj = lesson.lesson_json if isinstance(lesson.lesson_json, dict) else {}
        meta = lj.get("metadata") if isinstance(lj.get("metadata"), dict) else {}
        bridge = meta.get("visual_v2_bridge") if isinstance(meta.get("visual_v2_bridge"), dict) else {}
        stamped = int(bridge.get("version") or 1) if bridge else None

        print("\n--- enrichment / cache ---")
        print(f"current code VISUAL_BRIDGE_VERSION : {VISUAL_BRIDGE_VERSION}")
        print(f"stamped on this cached lesson      : {stamped}")
        print(f"will re-enrich on next read?       : {needs_visual_refresh(lj)}")
        print(f"clean_code_repair stamp            : {meta.get('clean_code_repair')}")
        print(f"worked_example_solver stamp        : {json.dumps(meta.get('worked_example_solver'))}")

        cards = lj.get("lesson_cards") if isinstance(lj.get("lesson_cards"), list) else []
        keys = [_key(c) for c in cards if isinstance(c, dict)]
        print(f"\n--- card sequence ({len(cards)} cards) ---")
        print("  " + " -> ".join(keys))

        wt = [c for c in cards if isinstance(c, dict) and _key(c) == "code_walkthrough"]
        print(f"\n--- code_walkthrough cards ({len(wt)}) ---")
        for i, c in enumerate(wt):
            code = str(c.get("code_snippet") or "")
            first_def = next((ln.strip() for ln in code.splitlines() if ln.strip().startswith("def ")), "(no def)")
            mb = _main_bullets(c.get("points") or c.get("bullets"))
            hl = c.get("highlight_lines_per_step")
            print(f"  [{i}] {str(c.get('title') or '').strip()!r}")
            print(f"      code: {_nonblank_lines(code)} non-blank lines; first def: {first_def}")
            print(f"      main bullets: {len(mb)}   highlight_lines_per_step: {hl}")
            singles = isinstance(hl, list) and all(
                isinstance(r, list) and len(r) == 2 and r[0] == r[1] for r in hl
            )
            print(f"      one-line-per-bullet shape present? {singles and len(mb) == len(hl)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
