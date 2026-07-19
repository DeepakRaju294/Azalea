"""Recall-popup feasibility audit (RECALL_POPUP_SPEC.md §0) — READ-ONLY.

Answers the ONE question seven design passes could not: against the real stored corpus, do earlier-topic
recall popups actually form, and are there enough candidates to justify the UI + telemetry surface?

No DB writes, no generation, no LLM. Recomputes anchor tiers IN MEMORY (stored links predate `match_kind`),
runs the §0 harvest funnel over every `review_earlier_topic` link, and prints prevalence + funnel + a decision
(strict_v1 | enable_4b | do_not_build). Emits JSON to stdout with --json.

Usage:  python scripts/recall_popup_feasibility_audit.py [--json] [--show N]
"""
import argparse
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

for cand in (".env", "../.env", "backend/.env"):
    if not os.getenv("DATABASE_URL") and os.path.exists(cand):
        for line in open(cand, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
os.environ.setdefault("OPENAI_API_KEY", "dummy")

import app.db.base as base
from app.db.database import SessionLocal


def _norm(s: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(s or "").lower()))


def iter_cards(o):
    """Yield every dict that looks like a card (carries text fields and/or interactive_links)."""
    if isinstance(o, dict):
        if isinstance(o.get("interactive_links"), list) or "card_type" in o:
            yield o
        for v in o.values():
            yield from iter_cards(v)
    elif isinstance(o, list):
        for v in o:
            yield from iter_cards(v)


def card_items(card):
    """The card's text items as (field, index, text), mirroring _attach_link_anchors' field order."""
    out = []
    for f in ("points", "bullets", "body"):
        v = card.get(f)
        if isinstance(v, list):
            for i, it in enumerate(v):
                out.append((f, i, str(it)))
        elif isinstance(v, str) and f == "body" and v.strip():
            out.append((f, 0, v))
    return out


def anchor_tier(card, link_text):
    """Replicate lean_lesson_generator._attach_link_anchors preference → the match_kind that WOULD be stored.
    Returns exact_item | word_boundary | substring_fallback | None."""
    text = str(link_text or "").lower()
    if not text:
        return None
    word_re = re.compile(rf"(?<![\w/]){re.escape(text)}(?![\w/])", re.IGNORECASE)
    exact = main = anywhere = None
    for _f, _i, s in card_items(card):
        low = s.lower()
        if text not in low:
            continue
        if exact is None and low.strip().strip(":").strip() == text:
            exact = "exact_item"
        is_sub = s.startswith(("  ", "- ", "\t")) and s.lstrip().startswith("-")
        if main is None and not is_sub and word_re.search(s):
            main = "word_boundary"
        if anywhere is None:
            anywhere = "substring_fallback"
    return exact or main or anywhere


# ---- §4 strict harvest over an owner lesson ------------------------------------------------------------

_DANGLING = ("this process", "as above", "as shown", "this method", "the above", "it does this")
_VERB_LED = {"confirms", "returns", "computes", "sends", "receives", "does", "is", "are", "makes",
             "creates", "adds", "removes", "checks", "sets", "gets", "runs", "holds"}


def definition_entries(lesson_json):
    """(head, full_text) for every Term: fragment style definition item in the owner lesson — the `components`
    section strings and any `definition`/components card points/bullets."""
    out = []
    comps = lesson_json.get("components")
    if isinstance(comps, list):
        for it in comps:
            if isinstance(it, str) and ":" in it:
                out.append((it.split(":", 1)[0].strip(), it.strip()))
    for card in iter_cards(lesson_json):
        if card.get("card_type") not in ("definition", "core_idea", "purpose_context"):
            continue
        for _f, _i, s in card_items(card):
            if ":" in s and not s.lstrip().startswith("-") is False:  # include sub-bullets too
                head = s.split(":", 1)[0].strip().lstrip("- ").strip()
                out.append((head, s.strip()))
    return out


def _clean_frag(frag):
    low = frag.lower()
    if any(d in low for d in _DANGLING):
        return None, "dangling_reference"
    first = re.findall(r"[a-z]+", low)
    if first and first[0] in _VERB_LED:
        return None, "verb_led_fragment"
    if len(frag.split()) < 3:
        return None, "fragment_too_short"
    return frag.rstrip("."), None


def sentence_definitions(owner_lesson, want):
    """§4 shape-1: a definition/core_idea/purpose card whose title matches the concept OR a complete sentence
    that itself opens with the concept — used directly. Yields (head, sentence)."""
    for card in iter_cards(owner_lesson):
        if card.get("card_type") not in ("definition", "core_idea", "purpose_context"):
            continue
        nt = _norm(card.get("title") or "")
        head_match = bool(nt) and (nt == want or want in nt or nt in want)
        for _f, _i, s in card_items(card):
            st = s.strip().lstrip("- ").strip()
            if len(st.split()) >= 6 and st.endswith((".", ")")) and st[:1].isupper():
                if _norm(st).startswith(want) or head_match:
                    yield (card.get("title") or want, st)


def prose_fallback(owner_lesson, want):
    """§4b projection ONLY (not strict §4): first definitional sentence in intro/purpose prose that opens with
    the concept and carries a definitional verb. Returns the sentence or None."""
    chunks = []
    for key in ("intro", "purpose"):
        v = owner_lesson.get(key)
        if isinstance(v, str):
            chunks.append(v)
        elif isinstance(v, dict):
            chunks += [s for _f, _i, s in card_items(v)]
    for c in chunks:
        for sent in re.split(r"(?<=[.!?])\s+", c):
            if _norm(sent).startswith(want) and re.search(r"\b(is|are|means|refers to)\b", sent.lower()) \
                    and len(sent.split()) >= 6 and not any(d in sent.lower() for d in _DANGLING):
                return sent.strip()
    return None


def harvest_recall(concept_text, owner_lesson):
    """Strict §4 only. Returns (recall_line, drop_reason). §4 shape 2/3 (Term: fragment) then shape 1 (sentence)."""
    want = _norm(concept_text)
    if not want:
        return None, "no_concept_text"
    for head, full in definition_entries(owner_lesson):
        nh = _norm(head)
        if nh and (nh == want or want in nh or nh in want) and ":" in full:
            cleaned, _r = _clean_frag(full.split(":", 1)[1].strip())
            if cleaned:
                return f"{head} — {cleaned}.", None
    for _head, sent in sentence_definitions(owner_lesson, want):
        return (sent if sent.endswith((".", ")")) else sent + "."), None
    return None, "no_definition"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--show", type=int, default=15, help="how many per-candidate rows to print")
    args = ap.parse_args()

    db = SessionLocal()

    # Preload: topic_id -> lesson_json, and normalized title -> [topic_id] (title-targeted links).
    topic_title = {}
    lesson_by_topic = {}
    for t in db.query(base.Topic).yield_per(500):
        topic_title[t.id] = t.title or ""
    title_index = defaultdict(list)
    for tid, ttl in topic_title.items():
        title_index[_norm(ttl)].append(tid)

    for l in db.query(base.Lesson).yield_per(300):
        if isinstance(l.lesson_json, dict):
            lesson_by_topic[l.topic_id] = l.lesson_json

    # Walk every lesson, collect review_earlier_topic candidates.
    funnel = Counter()
    drops = Counter()
    lessons_scanned = 0
    lessons_with_reviews = 0
    per_topic_kept = defaultdict(int)
    per_topic_concept = defaultdict(set)
    survivors = []
    rows = []

    recent_window = 200
    recent_with_reviews = 0
    for rank, l in enumerate(db.query(base.Lesson).order_by(base.Lesson.created_at.desc()).yield_per(300)):
        j = l.lesson_json
        if not isinstance(j, dict):
            continue
        lessons_scanned += 1
        disp_topic = l.topic_id
        had = False
        card_kept = defaultdict(int)
        for ci, card in enumerate(iter_cards(j)):
            for lk in card.get("interactive_links") or []:
                if (lk.get("action") or "").strip() != "review_earlier_topic":
                    continue
                had = True
                funnel["candidates"] += 1
                text = lk.get("text") or ""
                concept = lk.get("concept_id") or text
                target = (lk.get("target") or "").strip()

                # Stage 1: anchor eligibility (recomputed in memory).
                tier = anchor_tier(card, text)
                funnel[f"tier_{tier}"] += 1
                if tier not in ("exact_item", "word_boundary"):
                    drops["weak_or_missing_anchor"] += 1
                    rows.append((text[:32], target[:12], tier, "-", "weak_or_missing_anchor"))
                    continue
                funnel["anchor_eligible"] += 1

                # Stage 2: resolve unique owner.
                owner = None
                if target in lesson_by_topic:
                    owner = target
                elif target in topic_title:
                    owner = target
                else:
                    cands = title_index.get(_norm(target)) or title_index.get(_norm(text))
                    owner = cands[0] if cands and len(set(cands)) == 1 else None
                if not owner or owner == disp_topic:
                    drops["owner_unresolved"] += 1
                    rows.append((text[:32], target[:12], tier, "-", "owner_unresolved"))
                    continue
                owner_lesson = lesson_by_topic.get(owner)
                if not owner_lesson:
                    drops["owner_no_lesson"] += 1
                    rows.append((text[:32], target[:12], tier, "-", "owner_no_lesson"))
                    continue
                funnel["owner_resolved"] += 1

                # Stage 3: strict §4 harvest (+ §4b projection when strict fails).
                recall, reason = harvest_recall(text, owner_lesson)
                if recall is None:
                    drops[reason] += 1
                    if reason == "no_definition" and prose_fallback(owner_lesson, _norm(text)):
                        funnel["fallback_would_harvest"] += 1
                    rows.append((text[:32], target[:12], tier, "-", reason))
                    continue
                funnel["harvested"] += 1

                # Stage 4: caps (<=1/card, <=3/topic, <=1/concept).
                if card_kept[ci] >= 1:
                    drops["over_card_cap"] += 1
                    continue
                if per_topic_kept[disp_topic] >= 3:
                    drops["over_topic_cap"] += 1
                    continue
                if _norm(concept) in per_topic_concept[disp_topic]:
                    drops["duplicate_concept"] += 1
                    continue
                card_kept[ci] += 1
                per_topic_kept[disp_topic] += 1
                per_topic_concept[disp_topic].add(_norm(concept))
                funnel["kept"] += 1
                survivors.append({"concept": text, "recall": recall, "tier": tier})
                rows.append((text[:32], target[:12], tier, recall[:40], "KEPT"))
        if had:
            lessons_with_reviews += 1
            if rank < recent_window:
                recent_with_reviews += 1

    db.close()

    cand = funnel["candidates"] or 1
    n_topics = len(topic_title) or 1
    strict_rate = funnel["kept"] / cand
    per100 = funnel["candidates"] / (lessons_scanned or 1) * 100
    recent_prev = recent_with_reviews / recent_window * 100  # % of recent (flag-on era) lessons w/ a candidate

    # Decision: prevalence must be read on the RECENT (flag-on) window — the full corpus is diluted by ~1000
    # pre-feature lessons. Harvest must clear the bar and §4b must not be load-bearing.
    fallback_needed = funnel.get("fallback_would_harvest", 0) > max(3, funnel["kept"] * 0.3)
    if recent_prev < 5 and per100 < 3:
        decision = "do_not_build"
        why = ("even among recent flag-on lessons the review links are too rare to justify a dedicated popover "
               "UI + two-sided staleness + telemetry surface.")
    elif strict_rate >= 0.35 and not fallback_needed:
        decision = "strict_v1"
        why = (f"harvest is viable (strict §4 covers owner-resolved candidates; §4b not load-bearing) and "
               f"recent-window prevalence is {recent_prev:.0f}% of lessons — build v1 with strict §4 only.")
    elif fallback_needed:
        decision = "enable_4b"
        why = "candidates exist but strict §4 under-covers; the §4b background-definition fallback is load-bearing."
    else:
        decision = "strict_v1_low_volume"
        why = ("harvest works but absolute volume is modest; build only if the anchor-stage loss (legacy "
               "title-target links) is expected to shrink as the corpus shifts to scanner concept-links.")

    report = {
        "prevalence": {
            "lessons_scanned": lessons_scanned,
            "lessons_with_review_links": lessons_with_reviews,
            "review_link_candidates": funnel["candidates"],
            "review_links_per_100_lessons": round(per100, 2),
            f"recent_{recent_window}_pct_with_review_link": round(recent_prev, 1),
            "topics_total": n_topics,
        },
        "funnel": dict(funnel),
        "drop_reasons": dict(drops),
        "strict_harvest_rate": round(strict_rate, 3),
        "kept_popups": funnel["kept"],
        "decision": decision,
        "rationale": why,
        "sample_survivors": survivors[:10],
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return

    p = report["prevalence"]
    print("=" * 80)
    print("RECALL-POPUP FEASIBILITY AUDIT (RECALL_POPUP_SPEC §0) — read-only")
    print("=" * 80)
    print(f"lessons scanned:            {p['lessons_scanned']}")
    print(f"lessons w/ review links:    {p['lessons_with_review_links']}  "
          f"({p['lessons_with_review_links']/(p['lessons_scanned'] or 1)*100:.1f}%)")
    print(f"review_earlier_topic cands: {p['review_link_candidates']}")
    print(f"per 100 lessons (all-time): {p['review_links_per_100_lessons']}")
    rk = next(k for k in p if k.startswith("recent_") and k.endswith("with_review_link"))
    print(f"recent-window prevalence:   {p[rk]}%  ({rk.split('_')[1]} newest lessons w/ >=1 review link)")
    print("\n--- HARVEST FUNNEL " + "-" * 60)
    for k in ("candidates", "tier_exact_item", "tier_word_boundary", "tier_substring_fallback", "tier_None",
              "anchor_eligible", "owner_resolved", "harvested", "kept"):
        if k in funnel:
            print(f"  {k:26} {funnel[k]}")
    print("\n--- DROP REASONS " + "-" * 62)
    for k, v in drops.most_common():
        print(f"  {k:26} {v}")
    print(f"\nstrict_harvest_rate (kept / candidates): {report['strict_harvest_rate']}")
    print(f"kept popups: {report['kept_popups']}")
    if survivors:
        print("\n--- SAMPLE SURVIVING POPUPS " + "-" * 51)
        for s in survivors[:8]:
            print(f"  [{s['tier']}] {s['concept']!r} → {s['recall']}")
    print("\n" + "=" * 80)
    print(f"DECISION: {report['decision'].upper()}")
    print(f"  {report['rationale']}")
    print("=" * 80)
    if args.show:
        print(f"\n--- PER-CANDIDATE (first {args.show}) " + "-" * 40)
        print(f"  {'text':32} {'target':12} {'tier':18} {'recall/outcome'}")
        for r in rows[:args.show]:
            print(f"  {r[0]:32} {r[1]:12} {str(r[2]):18} {r[4]}  {r[3] if r[3]!='-' else ''}")


if __name__ == "__main__":
    main()
