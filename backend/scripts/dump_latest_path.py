"""Read-only dump of the latest study path: goal, topics, and each topic's lesson cards. For review."""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

for cand in (".env", "backend/.env"):
    if not os.getenv("DATABASE_URL") and os.path.exists(cand):
        for line in open(cand, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

import app.db.base as base
from app.db.database import SessionLocal

db = SessionLocal()
sp = db.query(base.StudyPath).order_by(base.StudyPath.created_at.desc()).first()
print("=" * 90)
print(f"STUDY PATH: {sp.title!r}")
print(f"goal:   {sp.goal!r}")
print(f"domain: {sp.domain!r}   created: {sp.created_at}")
print("=" * 90)

topics = sorted(sp.topics, key=lambda t: t.order_index or 0)
for t in topics:
    print(f"\n[{t.order_index}] {t.title!r}   (course_type={t.course_type})")
    print(f"     purpose: {t.purpose!r}")
    print(f"     learner_outcome: {t.learner_outcome!r}")
    print(f"     assumed_prerequisites: {t.assumed_prerequisites}")
    print(f"     in_scope: {t.in_scope}")
    print(f"     out_of_scope: {t.out_of_scope}")
    md = t.decomposition_metadata or {}
    print(f"     decomp: subject_key={md.get('subject_key')!r} capability_id={md.get('capability_id')!r} "
          f"basis={md.get('basis')!r} content_role={md.get('content_role')!r}")

print("\n" + "=" * 90 + "\nINTRO / ROADMAP LESSON CARDS\n" + "=" * 90)
intro = next((t for t in topics if (t.course_type or "") == "study_path_introduction"
              or (t.decomposition_metadata or {}).get("content_role") == "orientation"), topics[0] if topics else None)
if intro and intro.lesson and intro.lesson.lesson_json:
    lj = intro.lesson.lesson_json
    cards = lj.get("cards") or lj.get("lesson_cards") or []
    print(f"intro topic: {intro.title!r}  ({len(cards)} cards)")
    for i, c in enumerate(cards):
        print(f"\n--- card {i}: type={c.get('card_type')!r} title={c.get('title')!r} ---")
        for key in ("main_concept", "learning_goal", "body", "points", "bullets"):
            if c.get(key):
                print(f"  {key}: {json.dumps(c.get(key), ensure_ascii=False)[:800]}")
        if c.get("interactive_links"):
            print(f"  interactive_links: {json.dumps(c.get('interactive_links'), ensure_ascii=False)[:400]}")
else:
    print("no intro lesson json found")
