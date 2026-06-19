"""Terminal 'walkthrough player': render a stored lesson the way the frontend steps through it,
so the rendered experience can be inspected without screenshots or a running browser.

For each code_walkthrough / coding worked_example card it reproduces the frontend's stepping —
one step per main bullet, the code panel with a >> marker on the SINGLE highlighted line for that
step, and the bullets revealed so far. Other cards print their title + bullet tree.

Usage (run from the backend/ directory, with the venv python):
    python preview_lesson.py "merge sort"
    python preview_lesson.py --id <topic_id>
    python preview_lesson.py --id <topic_id> --walkthrough-only
"""
from __future__ import annotations

import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001 — best-effort on terminals that don't support it
    pass

from app.db.database import SessionLocal
from app.db.base import Lesson, Topic  # importing via base loads all models in dependency order

RESET = "\033[0m"
DIM = "\033[2m"
BOLD = "\033[1m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
GREEN = "\033[32m"


def _key(card: dict) -> str:
    return str(card.get("blueprint_key") or card.get("card_type") or "").strip().lower()


def _is_sub(point: str) -> bool:
    return bool(re.match(r"^\s+-\s+", str(point)))


def _group_main_bullets(points: list[str]) -> list[list[str]]:
    """Group each main bullet with the sub-bullets that follow it (the frontend's grouping)."""
    groups: list[list[str]] = []
    for p in points:
        if not str(p).strip():
            continue
        if _is_sub(p) and groups:
            groups[-1].append(p)
        else:
            groups.append([p])
    return groups


def _render_code(code: str, highlight: tuple[int, int] | None, max_line: int | None) -> str:
    lines = code.split("\n")
    width = len(str(len(lines)))
    out = []
    for i, ln in enumerate(lines, start=1):
        if max_line is not None and i > max_line:
            break
        marked = highlight is not None and highlight[0] <= i <= highlight[1]
        gutter = f"{i:>{width}}"
        if marked:
            out.append(f"{YELLOW}{BOLD}>> {gutter} | {ln}{RESET}")
        else:
            out.append(f"{DIM}   {gutter} | {ln}{RESET}")
    return "\n".join(out)


def _render_bullets(bullets: list[str], active_from: int) -> str:
    out = []
    for idx, b in enumerate(bullets):
        text = str(b)
        is_new = idx >= active_from
        prefix = "   - " if _is_sub(text) else " * "
        body = text.strip()
        if _is_sub(text):
            body = re.sub(r"^\s*-\s*", "", body)
        color = (GREEN if is_new else DIM)
        out.append(f"{color}{prefix}{body}{RESET}")
    return "\n".join(out)


def _play_code_card(card: dict, label: str) -> None:
    code = str(card.get("code_snippet") or "")
    points = [str(p) for p in (card.get("points") or card.get("bullets") or [])]
    groups = _group_main_bullets(points)
    hl = card.get("highlight_lines_per_step")
    title = str(card.get("title") or "").strip()

    cumulative: list[str] = []
    max_line = 0
    for i, group in enumerate(groups):
        prev_len = len(cumulative)
        cumulative = cumulative + group
        spec = hl[i] if isinstance(hl, list) and i < len(hl) and isinstance(hl[i], list) and len(hl[i]) == 2 else None
        highlight = (spec[0], spec[1]) if spec else None
        if highlight:
            max_line = max(max_line, highlight[1])
        print(f"\n{CYAN}=== {label}: {title}  |  step {i + 1}/{len(groups)}  "
              f"|  highlight line {highlight[0] if highlight else '-'} ==={RESET}")
        print(_render_code(code, highlight, max_line or None))
        print(f"{BOLD}WHAT'S HAPPENING:{RESET}")
        print(_render_bullets(cumulative, prev_len))


def _format_bullet(text: str) -> str:
    if _is_sub(text):
        return "   - " + re.sub(r"^\s*-\s*", "", text.strip())
    return " * " + text.strip()


def _print_plain_card(card: dict, label: str) -> None:
    title = str(card.get("title") or "").strip()
    print(f"\n{CYAN}=== {label}: {title} ==={RESET}")
    body = card.get("body")
    if body:
        for line in (body if isinstance(body, list) else [body]):
            if str(line).strip():
                print(f"   {str(line).strip()}")
    for p in (card.get("points") or card.get("bullets") or []):
        if str(p).strip():
            print(_format_bullet(str(p)))


def _print_card_extras(card: dict) -> None:
    """Everything else a card renders: the subtitle line (what_to_notice, shown under the title
    when body is empty), the visual panel text (visual_description — in your visual-debug mode this
    is what shows in the right panel), and practice question/answer."""
    wtn = card.get("what_to_notice")
    if wtn and not card.get("body") and str(wtn).strip():
        print(f"{DIM}SUBTITLE: {str(wtn).strip()}{RESET}")
    vd = card.get("visual_description")
    if vd and str(vd).strip():
        print(f"{DIM}VISUAL (debug panel): {str(vd).strip()}{RESET}")
    q = card.get("practice_question")
    if q and str(q).strip():
        print(f"{BOLD}PRACTICE Q:{RESET} {str(q).strip()}")
        for ch in (card.get("practice_choices") or []):
            print(f"   [ ] {str(ch).strip()}")
        if card.get("practice_answer"):
            print(f"   ANSWER: {str(card.get('practice_answer')).strip()}")
        if card.get("practice_feedback"):
            print(f"   FEEDBACK: {str(card.get('practice_feedback')).strip()}")


def main() -> None:
    args = sys.argv[1:]
    walkthrough_only = "--walkthrough-only" in args
    args = [a for a in args if a != "--walkthrough-only"]
    if not args:
        print(__doc__)
        return

    db = SessionLocal()
    try:
        if args[0] == "--id" and len(args) > 1:
            topic = db.query(Topic).filter(Topic.id == args[1]).first()
        else:
            topic = (
                db.query(Topic)
                .filter(Topic.title.ilike(f"%{' '.join(args)}%"))
                .order_by(Topic.created_at.desc())
                .first()
            )
        if not topic:
            print(f"No topic matched {args!r}.")
            return
        lesson = db.query(Lesson).filter(Lesson.topic_id == topic.id).first()
        if not lesson or not isinstance(lesson.lesson_json, dict):
            print("No lesson stored.")
            return

        print(f"{BOLD}{topic.title}{RESET}  ({topic.course_type})")
        cards = lesson.lesson_json.get("lesson_cards") or []
        for card in cards:
            if not isinstance(card, dict):
                continue
            k = _key(card)
            has_code = bool(str(card.get("code_snippet") or "").strip())
            if k == "code_walkthrough" and has_code:
                _play_code_card(card, "WALKTHROUGH")
            elif k == "worked_example" and has_code and card.get("highlight_lines_per_step"):
                _play_code_card(card, "WORKED EXAMPLE")
            elif not walkthrough_only:
                _print_plain_card(card, k.upper())
            else:
                continue  # --walkthrough-only: skip non-code cards entirely
            _print_card_extras(card)
    finally:
        db.close()


if __name__ == "__main__":
    main()
