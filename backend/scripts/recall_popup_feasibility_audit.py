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
# A fragment whose FIRST word is one of these is a behaviour/purpose/example clause, not a self-contained
# definition — §4 rejects it ("Enables simplification…", "Useful for scenarios where…").
_NON_DEFINITIONAL_LEAD = {
    "confirms", "returns", "computes", "sends", "receives", "does", "is", "are", "makes", "creates", "adds",
    "removes", "checks", "sets", "gets", "runs", "holds", "enables", "allows", "helps", "provides", "lets",
    "supports", "used", "use", "useful", "important", "needed", "required", "for", "when", "where", "which",
    "this", "that", "these", "they", "it", "e", "eg", "example",
}
_LEADING_PRONOUN = {"it", "this", "these", "they", "that", "he", "she", "we", "you"}
_DEF_VERB = re.compile(
    r"\b(is|are|means|refers to|represents?|describes?|denotes?|counts?|measures?|arranges?)\b")


def _singular_plural_prefix(text, want):
    """startswith, tolerant of a trailing plural 's' on the leading concept token
    ('a combination is…' matches want 'combinations')."""
    if text.startswith(want):
        return True
    tw = want.split()
    tt = text.split()
    if not tw or len(tt) < len(tw):
        return False
    for a, b in zip(tt, tw):
        if a == b or a.rstrip("s") == b.rstrip("s"):
            continue
        return False
    return True


def _self_contained_definition(sent, want):
    """§4 shape-1: the sentence must OPEN with the concept (optionally behind the/a/an, singular/plural tolerant),
    carry a definitional verb, and contain no dangling/pronoun/context lead. Returns True/False."""
    low = sent.strip().lower()
    words = re.findall(r"[a-z]+", low)
    if not words or words[0] in _LEADING_PRONOUN:
        return False
    ns = _norm(sent)
    stripped = re.sub(r"^(the|a|an)\s+", "", ns)
    if not (_singular_plural_prefix(ns, want) or _singular_plural_prefix(stripped, want)):
        return False
    if not _DEF_VERB.search(low):
        return False
    if any(d in low for d in _DANGLING):
        return False
    return True


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
    """§4 shape 2/3: the {Term} — {fragment} predicate must be a self-contained definition, not a
    behaviour/purpose/example clause."""
    low = frag.lower()
    if any(d in low for d in _DANGLING):
        return None, "dangling_reference"
    first = re.findall(r"[a-z]+", low)
    if first and first[0] in _NON_DEFINITIONAL_LEAD:
        return None, "non_definitional_lead"
    if len(frag.split()) < 3:
        return None, "fragment_too_short"
    return frag.rstrip("."), None


def sentence_definitions(owner_lesson, want):
    """§4 shape-1: a complete sentence that is SELF-CONTAINED — opens with the concept (behind at most the/a/an),
    carries a definitional verb, no dangling/pronoun/context lead. Title-only matches are NOT sufficient."""
    for card in iter_cards(owner_lesson):
        if card.get("card_type") not in ("definition", "core_idea", "purpose_context"):
            continue
        for _f, _i, s in card_items(card):
            st = s.strip().lstrip("- ").strip()
            if len(st.split()) >= 6 and st.endswith((".", ")")) and _self_contained_definition(st, want):
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
    owner_resolved_rows = []   # every owner-resolved candidate + its harvest outcome (for manual precision labeling)

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
                owner_resolved_rows.append({
                    "concept": text, "owner": topic_title.get(owner, "")[:40],
                    "harvest": recall or f"[REJECT:{reason}]",
                })
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
    per100 = funnel["candidates"] / (lessons_scanned or 1) * 100
    recent_prev = recent_with_reviews / recent_window * 100

    # Staged rates — each stage on ITS OWN denominator (the spec's strict_harvest_rate is harvests / anchored
    # review links, NOT kept / all candidates, which conflates anchor availability + harvest + caps).
    def _rate(a, b):
        return round(a / b, 3) if b else None
    stage_rates = {
        "anchor_eligibility":  _rate(funnel["anchor_eligible"], funnel["candidates"]),          # 25/41
        "owner_resolution":    _rate(funnel["owner_resolved"], funnel["anchor_eligible"]),        # 21/25
        "strict_harvest":      _rate(funnel["harvested"], funnel["owner_resolved"]),              # deterministic §4 pass / 21
        "post_cap_survival":   _rate(funnel["kept"], funnel["harvested"]),
        "end_to_end_yield":    _rate(funnel["kept"], funnel["candidates"]),
    }
    strict_harvest_rate = stage_rates["strict_harvest"]  # SPEC definition: harvests / anchored (owner-resolved)

    # Decision is PROVISIONAL until human precision is labeled on the owner-resolved sample (the script's
    # deterministic §4 pass is necessary, not sufficient — a human must confirm the surviving lines read as
    # trustworthy self-contained recall). The script therefore never emits a final `strict_v1`.
    fallback_needed = funnel.get("fallback_would_harvest", 0) > max(3, funnel["harvested"] * 0.3)
    if recent_prev < 5 and per100 < 3:
        decision = "do_not_build_provisional"
        why = "review links too rare even in the recent window to justify the UI/staleness/telemetry surface."
    elif fallback_needed:
        decision = "enable_4b_provisional"
        why = "strict §4 under-covers on the tightened harvester; the §4b fallback looks load-bearing."
    else:
        decision = "strict_v1_provisional"
        why = ("tightened strict §4 harvests {h}/{o} owner-resolved candidates; recent-window candidate "
               "prevalence {p:.0f}%. PROVISIONAL — confirm human precision on the owner-resolved sample below "
               "before committing to the UI build.").format(
                   h=funnel["harvested"], o=funnel["owner_resolved"], p=recent_prev)

    report = {
        "prevalence": {
            "lessons_scanned": lessons_scanned,
            "lessons_with_review_links": lessons_with_reviews,
            "review_link_candidates": funnel["candidates"],
            "review_links_per_100_lessons": round(per100, 2),
            f"recent_{recent_window}_lessons_with_review_links_pct": round(recent_prev, 1),
            "topics_total": n_topics,
        },
        "funnel": dict(funnel),
        "drop_reasons": dict(drops),
        "stage_rates": stage_rates,
        "strict_harvest_rate": strict_harvest_rate,  # SPEC: harvests / anchored(owner-resolved)
        "human_precision_on_sample": None,  # REQUIRED before finalizing — label owner_resolved_cases manually
        "kept_popups": funnel["kept"],
        "decision": decision,
        "rationale": why,
        "owner_resolved_cases": owner_resolved_rows,   # the sample to hand-label for precision
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
    rk = next(k for k in p if k.startswith("recent_") and k.endswith("_pct"))
    print(f"recent-window prevalence:   {p[rk]}%  ({rk.split('_')[1]} newest lessons w/ >=1 review link; "
          f"NOT verified flag-on)")
    print("\n--- HARVEST FUNNEL (each stage on its own denominator) " + "-" * 24)
    for k in ("candidates", "tier_exact_item", "tier_word_boundary", "tier_substring_fallback", "tier_None",
              "anchor_eligible", "owner_resolved", "harvested", "kept"):
        if k in funnel:
            print(f"  {k:26} {funnel[k]}")
    print("\n--- STAGE RATES " + "-" * 63)
    for k, v in stage_rates.items():
        print(f"  {k:26} {v}")
    print(f"  strict_harvest_rate (SPEC: harvested / owner-resolved) = {strict_harvest_rate}")
    print("\n--- DROP REASONS " + "-" * 62)
    for k, v in drops.most_common():
        print(f"  {k:26} {v}")
    print("\n--- OWNER-RESOLVED CASES (hand-label these for precision) " + "-" * 22)
    for c in owner_resolved_rows:
        print(f"  {c['concept'][:26]:26} | {c['owner']:40} | {c['harvest']}")
    print("\n" + "=" * 80)
    print(f"DECISION: {report['decision'].upper()}  (human_precision_on_sample: NOT YET LABELED)")
    print(f"  {report['rationale']}")
    print("=" * 80)


if __name__ == "__main__":
    main()
