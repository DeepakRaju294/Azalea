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
import hashlib
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
# Interpretation / use / purpose statements masquerade as definitions because a stray copula appears later
# ("A z-score CAN INDICATE whether a point IS typical"). Reject them explicitly (spec §4 wants what a concept IS).
_MODAL_NONDEF = re.compile(
    r"\bcan (indicate|show|be used|help|tell|reveal|determine)\b|\b(is|are|can be) used to\b|\bhelps? to\b")


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
    if _MODAL_NONDEF.search(low):
        return False
    if not _DEF_VERB.search(low):
        return False
    if any(d in low for d in _DANGLING):
        return False
    return True


def _is_variable_head(head):
    """A single short symbol/variable head (n, r, X, Z, σ) is a formula-legend entry, not a concept definition —
    it matches concepts only because a single letter is a substring ('n' in 'combinations')."""
    return len(re.sub(r"[^a-z0-9]", "", head.lower())) <= 2


def definition_entries(lesson_json):
    """(head, full_text) for every Term: fragment style definition item in the owner lesson — the `components`
    section strings and any `definition`/components card points/bullets. Variable-legend heads are skipped."""
    out = []
    comps = lesson_json.get("components")
    if isinstance(comps, list):
        for it in comps:
            if isinstance(it, str) and ":" in it:
                head = it.split(":", 1)[0].strip()
                if not _is_variable_head(head):
                    out.append((head, it.strip()))
    for card in iter_cards(lesson_json):
        if card.get("card_type") not in ("definition", "core_idea", "purpose_context"):
            continue
        for _f, _i, s in card_items(card):
            if ":" in s:  # any Term: fragment item, main bullet OR "  - " sub-bullet
                head = s.split(":", 1)[0].strip().lstrip("- ").strip()
                if not _is_variable_head(head):
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


# ---- Human labels: an EXTERNAL, immutable record joined by case_key --------------------------------------
# The deterministic harvester is only a proxy. The audit does NOT manufacture "human" verdicts — it JOINS an
# analyst-authored label file (recall_popup_hand_labels.json) by a stable case_key. Any owner-resolved case with
# no matching label is reported as "unlabeled", and precision/yield are computed over LABELED cases only. Rerunning
# against future lessons therefore surfaces new unlabeled cases instead of inventing labels for them.
# Verdict ∈ strict_valid | borderline_function | invalid.
_LABELS_PATH = os.path.join(os.path.dirname(__file__), "recall_popup_hand_labels.json")


def case_key(concept, owner_title, harvest):
    """v1 key (used by labels key_version 1): concept + owner title + (reject | normalized harvested-line prefix).
    Human-readable but can collide when different paths teach the same concept with the same opening text."""
    h = "reject" if harvest.startswith("[REJECT") else _norm(harvest)[:60]
    return f"{_norm(concept)} || {_norm(owner_title)} || {h}"


def case_key_v2(path_id, disp_topic, owner_topic, concept_id_or_text, candidate_source):
    """v2 key (collision-resistant; for future audit cohorts): bind the case to its actual identities + a FULL
    source hash, so two paths teaching the same concept — or two sources sharing an opening — never collide."""
    src_hash = hashlib.sha256(_norm(candidate_source).encode("utf-8")).hexdigest()
    parts = [str(path_id or ""), str(disp_topic or ""), str(owner_topic or ""),
             _norm(concept_id_or_text), src_hash]
    return "v2:" + hashlib.sha256("||".join(parts).encode("utf-8")).hexdigest()[:24]


def load_labels():
    """Return (by_key, meta, key_version). Joins on the v1 or v2 key field per the file's key_version."""
    if not os.path.exists(_LABELS_PATH):
        return {}, {}, 1
    with open(_LABELS_PATH, encoding="utf-8") as f:
        doc = json.load(f)
    key_version = int(doc.get("key_version", 1))
    by_key = {c["case_key"]: c["verdict"] for c in doc.get("cases", [])}
    meta = {k: doc.get(k) for k in ("labeling_version", "key_version", "labeled_on", "reviewer", "review_method")}
    return by_key, meta, key_version


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


def relaxed_source(concept_text, owner_lesson):
    """Best owner definitional snippet for the concept WITHOUT the quality gate — so the label file can record the
    actual candidate text even when strict §4 rejected it."""
    want = _norm(concept_text)
    for head, full in definition_entries(owner_lesson):
        nh = _norm(head)
        if nh and (nh == want or want in nh or nh in want):
            return full[:160]
    for card in iter_cards(owner_lesson):
        if card.get("card_type") not in ("definition", "core_idea", "purpose_context"):
            continue
        for _f, _i, s in card_items(card):
            st = s.strip().lstrip("- ").strip()
            if _norm(st).startswith(want) or _singular_plural_prefix(re.sub(r"^(the|a|an)\s+", "", _norm(st)), want):
                return st[:160]
    return ""


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
    ap.add_argument("--emit-label-template", action="store_true",
                    help="print distinct owner-resolved cases (case_key + source) to author the label file")
    args = ap.parse_args()

    labels_by_key, labels_meta, key_version = load_labels()
    db = SessionLocal()

    # Preload: topic_id -> lesson_json / title / study_path, and normalized title -> [topic_id].
    topic_title = {}
    topic_path = {}
    lesson_by_topic = {}
    for t in db.query(base.Topic).yield_per(500):
        topic_title[t.id] = t.title or ""
        topic_path[t.id] = getattr(t, "study_path_id", None)
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
    candidate_concepts = set()
    harvested_concepts = set()
    harvested_lines = set()
    paths_with_harvest = set()

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
                candidate_concepts.add(_norm(text))

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
                harvest_str = recall or f"[REJECT:{reason}]"
                cand_src = (recall or relaxed_source(text, owner_lesson) or "[none]")[:160]
                ckey = case_key(text, topic_title.get(owner, ""), harvest_str)
                ckey2 = case_key_v2(topic_path.get(disp_topic), disp_topic, owner,
                                    lk.get("concept_id") or text, cand_src)
                join_key = ckey if key_version == 1 else ckey2
                owner_resolved_rows.append({
                    "case_key": ckey,
                    "case_key_v2": ckey2,
                    "concept": text, "owner": topic_title.get(owner, "")[:40],
                    "harvest": harvest_str,
                    "harvested": recall is not None,
                    "recall_line": recall,
                    "path": topic_path.get(disp_topic),
                    "candidate_source": cand_src,
                    "label": labels_by_key.get(join_key, "unlabeled"),
                })
                if recall is None:
                    drops[reason] += 1
                    if reason == "no_definition" and prose_fallback(owner_lesson, _norm(text)):
                        funnel["fallback_would_harvest"] += 1
                    rows.append((text[:32], target[:12], tier, "-", reason))
                    continue
                funnel["harvested"] += 1
                harvested_concepts.add(_norm(text))
                harvested_lines.add(recall.strip())
                if topic_path.get(disp_topic):
                    paths_with_harvest.add(topic_path[disp_topic])

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

    if args.emit_label_template:
        seen = {}
        for c in owner_resolved_rows:
            seen.setdefault(c["case_key"], c)
        template = {
            "labeling_version": "TEMPLATE — fill verdict + rationale, then set metadata",
            "key_version": 2, "labeled_on": "YYYY-MM-DD", "reviewer": "", "review_method": "",
            "_note": "Set key_version=2 and use case_key_v2 as the joined `case_key` for new cohorts (collision-"
                     "resistant). key_version=1 files join on the human-readable v1 case_key.",
            "cases": [{"case_key": c["case_key_v2"], "case_key_v1": c["case_key"], "concept": c["concept"],
                       "owner": c["owner"], "candidate_source": c["candidate_source"],
                       "verdict": "", "rationale": ""}
                      for c in seen.values()],
        }
        print(json.dumps(template, ensure_ascii=False, indent=1))
        return

    cand = funnel["candidates"] or 1
    n_topics = len(topic_title) or 1
    per100 = funnel["candidates"] / (lessons_scanned or 1) * 100
    recent_prev = recent_with_reviews / recent_window * 100

    def _rate(a, b):
        return round(a / b, 3) if b else None

    # Pipeline stages, each on its OWN denominator. The harvester ACCEPTANCE stage is named honestly: it is the
    # deterministic §4 extractor's raw accept rate, NOT "strict harvest" — some accepts are later hand-labeled
    # non-clean, so calling it strict would make the metric and the audited result disagree.
    stage_rates = {
        "anchor_eligibility":              _rate(funnel["anchor_eligible"], funnel["candidates"]),
        "owner_resolution":                _rate(funnel["owner_resolved"], funnel["anchor_eligible"]),
        "deterministic_harvester_acceptance": _rate(funnel["harvested"], funnel["owner_resolved"]),
    }

    # Join the EXTERNAL hand labels (never manufactured here). Precision, yield and diversity are computed over
    # LABELED cases; unlabeled cases are surfaced, not scored.
    labels = Counter(c["label"] for c in owner_resolved_rows)
    unlabeled = labels.get("unlabeled", 0)
    harvested_cases = [c for c in owner_resolved_rows if c["harvested"]]
    strict_valid_delivered = [c for c in harvested_cases if c["label"] == "strict_valid"]
    strict_valid_missed = [c for c in owner_resolved_rows if c["label"] == "strict_valid" and not c["harvested"]]

    audited = {
        "raw_harvester_acceptance": f'{funnel["harvested"]}/{funnel["owner_resolved"]}',
        "audited_strict_valid_yield": f'{len(strict_valid_delivered)}/{funnel["owner_resolved"]}',   # delivered clean defs
        "audited_precision": f'{len(strict_valid_delivered)}/{len(harvested_cases)}',                # of what it kept
        "harvester_false_negatives": len(strict_valid_missed),   # valid def content the extractor missed
        "unlabeled_cases": unlabeled,
        "label_provenance": labels_meta,
    }

    # Diversity — mixed (any harvested) AND strict-valid-only (the meaningful measure under the strict contract).
    sv_delivered = strict_valid_delivered
    diversity = {
        "unique_candidate_concepts": len(candidate_concepts),
        "any_harvested_concepts": len(harvested_concepts),
        "any_harvested_recall_lines": len(harvested_lines),
        "paths_with_any_harvested_popup": len(paths_with_harvest),
        "strict_valid_concepts": len({_norm(c["concept"]) for c in sv_delivered}),
        "strict_valid_recall_lines": len({c["recall_line"] for c in sv_delivered if c["recall_line"]}),
        "paths_with_strict_valid_popup": len({c["path"] for c in sv_delivered if c["path"]}),
    }

    # DECISION is a recorded PRODUCT JUDGMENT, not an automatic threshold (the spec explicitly rejects a universal
    # minimum-viable-cohort number). The evidence below supports deferral; a human owner would flip it only by
    # deciding this cohort is worth a dedicated UI.
    decision = "defer_to_v2"
    why = ("PRODUCT JUDGMENT (not a fixed threshold). The harvester is precise ({prec}) but the strict-valid "
           "cohort is tiny: {svl} unique recall lines across {svp} study paths and {svc} concepts, audited "
           "strict-valid yield {yld} of owner-resolved. Volume + concept diversity + inconsistent definition "
           "ownership are the binding constraints, which labeling clarifies but cannot fix. Freeze the interaction "
           "design; revisit under v2 scope-plan `uses`/`definition_owners`.").format(
               prec=audited["audited_precision"], svl=diversity["strict_valid_recall_lines"],
               svp=diversity["paths_with_strict_valid_popup"], svc=diversity["strict_valid_concepts"],
               yld=audited["audited_strict_valid_yield"])

    report = {
        "prevalence": {
            "lessons_scanned": lessons_scanned,
            "lessons_with_review_links": lessons_with_reviews,
            "review_link_candidates": funnel["candidates"],
            "review_links_per_100_lessons": round(per100, 2),
            f"recent_{recent_window}_lessons_with_review_links_pct": round(recent_prev, 1),
            "topics_total": n_topics,
        },
        "diversity": diversity,
        "funnel": dict(funnel),
        "drop_reasons": dict(drops),
        "stage_rates": stage_rates,
        "audited": audited,
        "labels": dict(labels),
        "decision": decision,
        "rationale": why,
        "owner_resolved_cases": owner_resolved_rows,   # each carries case_key + label + candidate_source
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
    print("\n--- STAGE RATES (own denominators) " + "-" * 44)
    for k, v in stage_rates.items():
        print(f"  {k:36} {v}")
    print("\n--- AUDITED (external hand labels, joined) " + "-" * 36)
    print(f"  raw_harvester_acceptance:     {audited['raw_harvester_acceptance']}")
    print(f"  audited_strict_valid_yield:   {audited['audited_strict_valid_yield']}   (delivered clean definitions)")
    print(f"  audited_precision:            {audited['audited_precision']}   (of what the harvester kept)")
    print(f"  harvester_false_negatives:    {audited['harvester_false_negatives']}   (valid content the extractor missed)")
    print(f"  labels:                       {dict(labels)}")
    print(f"  label_provenance:             {audited['label_provenance']}")
    if audited["unlabeled_cases"]:
        print(f"  ** {audited['unlabeled_cases']} UNLABELED cases — add them to {os.path.basename(_LABELS_PATH)} **")
    print("\n--- DIVERSITY (strict-valid is the meaningful measure) " + "-" * 25)
    for k, v in diversity.items():
        mark = " <=" if k.startswith("strict_valid") or k == "paths_with_strict_valid_popup" else ""
        print(f"  {k:34} {v}{mark}")
    print("\n--- DROP REASONS " + "-" * 62)
    for k, v in drops.most_common():
        print(f"  {k:26} {v}")
    print("\n--- OWNER-RESOLVED CASES (joined label per case) " + "-" * 30)
    for c in owner_resolved_rows:
        print(f"  [{c['label'][:11]:11}] {c['concept'][:20]:20} | {c['owner'][:26]:26} | {c['harvest'][:52]}")
    print("\n" + "=" * 80)
    print(f"DECISION: {report['decision'].upper()}")
    print(f"  {report['rationale']}")
    print("=" * 80)


if __name__ == "__main__":
    main()
