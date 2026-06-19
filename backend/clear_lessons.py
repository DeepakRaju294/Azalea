"""Clear cached lessons from the DB so the next view regenerates them fresh.

With caching disabled (AZALEA_DISABLE_LESSON_CACHE != "0") every view already regenerates, but
this wipes the stored rows for a clean slate and removes any stale 'generating'/'failed' rows that
could otherwise short-circuit a fresh build.

Usage (run from the backend/ directory, with the venv python):
    python clear_lessons.py --all                       # delete EVERY stored lesson
    python clear_lessons.py --study-path <study_path_id> # delete lessons for one path's topics
    python clear_lessons.py --topic <topic_id>          # delete one lesson
    python clear_lessons.py "merge sort"                # delete lessons whose topic title matches

Nothing is deleted unless you pass one of the above (no silent no-arg wipe).
"""
from __future__ import annotations

import sys

from app.db.database import SessionLocal
from app.db.base import Lesson, Topic  # importing via base loads all models in dependency order
from app.services.lesson_cache import lesson_cache_disabled


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        print(f"\n[this process sees caching disabled = {lesson_cache_disabled()}]")
        return

    db = SessionLocal()
    try:
        q = db.query(Lesson)
        if args[0] == "--all":
            label = "ALL lessons"
        elif args[0] == "--study-path" and len(args) > 1:
            topic_ids = [t.id for t in db.query(Topic.id).filter(Topic.study_path_id == args[1])]
            q = q.filter(Lesson.topic_id.in_(topic_ids))
            label = f"lessons for study path {args[1]}"
        elif args[0] == "--topic" and len(args) > 1:
            q = q.filter(Lesson.topic_id == args[1])
            label = f"lesson for topic {args[1]}"
        else:
            needle = " ".join(args)
            topic_ids = [t.id for t in db.query(Topic.id).filter(Topic.title.ilike(f"%{needle}%"))]
            q = q.filter(Lesson.topic_id.in_(topic_ids))
            label = f"lessons whose topic title matches {needle!r}"

        rows = q.all()
        if not rows:
            print(f"No {label} found — nothing to delete.")
            return
        for r in rows:
            db.delete(r)
        db.commit()
        print(f"Deleted {len(rows)} {label}. They will regenerate fresh on next view.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
