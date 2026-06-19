"""Regenerate ONE topic's lesson from scratch — re-runs the generation prompt AND the
enrichment pipeline (code_repair + worked-example solver), then overwrites the cached
lesson row. Use this to actually SEE prompt-driven changes (per-line walkthrough bullets,
varied example values, complete code) that a plain re-read can never produce.

Usage (run from the backend/ directory):
    python regen_lesson.py "merge sort"        # match a topic by title substring
    python regen_lesson.py --id <topic_id>

Writes to the live DB for the single matched lesson only. Requires OPENAI_API_KEY.
"""
from __future__ import annotations

import os
import sys

from sqlalchemy.orm.attributes import flag_modified

from app.db.database import SessionLocal
from app.db.base import Lesson, Topic  # importing via base loads all models in dependency order
from app.api.routes.lessons import (
    build_legacy_lesson_with_v2_visuals,
    get_source_chunks_for_topic,
)


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    key = os.getenv("OPENAI_API_KEY", "")
    if not key or key.strip().lower() == "dummy":
        print("OPENAI_API_KEY is not set to a real key — real generation cannot run.")
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

        print(f"Regenerating: {topic.title}  (id={topic.id}, type={topic.course_type})")
        chunks = get_source_chunks_for_topic(topic=topic, db=db)
        print(f"  source chunks: {len(chunks)} — calling the generator (this hits the LLM)...")
        lesson_json = build_legacy_lesson_with_v2_visuals(topic=topic, chunks=chunks)

        lesson = db.query(Lesson).filter(Lesson.topic_id == topic.id).first()
        if not lesson:
            lesson = Lesson(
                topic_id=str(topic.id),
                title=topic.title,
                lesson_json=lesson_json,
                generation_status="ready",
            )
            db.add(lesson)
        else:
            lesson.title = topic.title
            lesson.lesson_json = lesson_json
            lesson.generation_status = "ready"
            flag_modified(lesson, "lesson_json")
        db.commit()
        print("  Saved. Now inspect it:  python check_lesson.py", repr(" ".join(args)))
    finally:
        db.close()


if __name__ == "__main__":
    main()
