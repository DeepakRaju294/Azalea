# Recall Popups — small spec (rev 2)

Status: Draft rev 2 — direction agreed; **v1 scope NARROWED after a code-grounded review** to what the existing
link pipeline can actually produce. Flag: `AZALEA_RECALL_POPUPS` (requires `AZALEA_PREREQ_LINKS`). The old
`AZALEA_TERM_GLOSSES` lexical-gloss system stays **permanently dead** and is not revived by this.

> **rev 2 changes (all from the review — rev 1 promised behavior the pipeline structurally prevents):**
> 1. v1 is **earlier-topic recall ONLY.** External-prerequisite `open_study_path` links live ONLY on the intro
>    prereq card (`lean_lesson_generator.py` "open_study_path links live ONLY here — never scattered
>    elsewhere"), which v1 excludes → zero prereq popups were possible. Prereq recall waits for scope-plan `uses`.
> 2. **Additive `recall_popup` payload** on the link — never overload the existing string `action` field.
> 3. **Anchor `match_kind`** required; a bare `{field,index}` does NOT prove eligibility (the anchor function
>    still permits a `substring_fallback`). Only `exact_item`/`word_boundary` are popup-eligible.
> 4. **Frontend routing change** required: `review_earlier_topic` renders as a PILL today
>    (`INLINE_ANCHOR_ACTIONS = {popup_only, ask_question, open_study_path}`); it renders inline ONLY when it has
>    an eligible `recall_popup` + eligible anchor + flag — never added to the set unconditionally.
> 5. **No non-recall fallback:** "You saw this earlier in …" is navigation, not recall — if no clean recall
>    sentence harvests, show NO popup (keep the ordinary review pill). Precision-first.
> 6. **Notation popovers** split to a separate flag (`AZALEA_NOTATION_POPOVERS`, v1.1) — different source and
>    eligibility; must not consume the recall budget.

## 1. Purpose

**When a body lesson uses a concept an EARLIER topic in this path already taught, an anchored popover gives just
enough recall to continue without leaving the lesson.** It never teaches, never defines new material, never
repairs missing instruction. It answers, at most: *what should I remember?* (`recall`) and *where can I review
it?* (`Review topic`). `why_here` is v1.5.

## 2. v1 candidate selection — deterministic, earlier-topic only

Candidates are EXACTLY the existing `review_earlier_topic` links the deterministic scanner emits (concept taught
by an earlier topic in this path). No word discovery; the LLM never picks phrases. A candidate is popup-eligible
iff ALL hold:
- its anchor `match_kind ∈ {exact_item, word_boundary}` (§3),
- it is NOT the current topic's principal concept, and NOT defined on the same card,
- a clean recall sentence harvests from the owner topic (§4) — else no popup.

External prerequisites are OUT of v1 (see rev-2 note 1). The intro prereq card keeps its existing
gloss/requirement + open-path behavior, unchanged.

## 3. Anchor eligibility — `match_kind`

`_attach_link_anchors` gains a recorded tier (it already computes it, just doesn't store it):
```
anchor: { field, index, match_kind: exact_item | word_boundary | substring_fallback }
```
Recall popups accept only `exact_item` / `word_boundary`. A `substring_fallback` link still navigates — as a
plain pill, never an inline recall popover. (Existing anchor tests extended to assert `match_kind`.)

## 4. Recall content — strict harvest, no invention

`recall` is harvested deterministically from the owner topic (resolved via the link's `target` topic_id). Accept
ONLY when:
- the owner topic resolves uniquely,
- the candidate sentence comes from a definition-owning card (a `definition`/key-terms bullet, or a structured
  definition record) whose head matches the concept or an approved alias,
- it is ONE complete sentence, within the display budget,
- it contains no unresolved notation and no dangling reference ("this process", "as above"),
- it is stamped with `source_topic_id` + `source_card_id`.

If any check fails → **omit the popup, keep the review pill.** Never substitute the "You saw this earlier in …"
navigation line as recall content.

## 5. Payload (stored on the link at generation time; clicks are instant, no runtime calls)

```
InteractiveLink
  action        # unchanged existing string ("review_earlier_topic")
  target        # unchanged owner topic_id
  concept_id    # unchanged
  anchor        # unchanged + match_kind (§3)
  recall_popup: RecallPopupV1 | null      # additive; presence is the frontend gate

RecallPopupV1
  recall            # one harvested sentence (§4)
  needed_here       # v1.5 optional: one sentence, generation-time, omitted when uncertain
  action_label      # "Review topic"
  source_topic_id
  source_card_id
  popup_version
```
The recall payload does NOT duplicate action-kind/target — those stay on the link.

## 6. Selection pipeline + caps (candidates ≠ rendered)

```
1 collect deterministic candidates (eligible review_earlier_topic links)
2 reject: missing/weak anchor, current-topic concept, defined-on-card, missing clean recall
3 rank remaining (earlier-topic concept needed for this step first)
4 apply caps: <=1 per card, <=3 per topic, <=1 per concept (first eligible use)
5 attach recall_popup payloads
6 record dropped reasons  (telemetry)
```
Drop reasons: `missing_anchor | weak_anchor | current_topic_concept | defined_on_card | missing_recall |
duplicate_concept | over_card_cap | over_topic_cap`.

## 7. Frontend interaction

Anchored **popover**, not a modal: opens beside the phrase, does not obscure the card, closes on outside
click/Escape, keyboard accessible; contains `recall` (+ `needed_here` when present) and one "Review topic →"
action; never auto-launches Q&A. Routing: a `review_earlier_topic` link renders inline **iff** flag +
`recall_popup != null` + eligible anchor; otherwise the existing pill. Do NOT add `review_earlier_topic` to
`INLINE_ANCHOR_ACTIONS` unconditionally. The frontend gate is the presence of `recall_popup` (a backend env flag
alone cannot govern rendering).

## 8. Telemetry (day one) — impressions included

Events/counters: `eligible, rendered (impression), opened, dismissed, action_clicked`. Dimensions:
`popup_version, source (earlier_topic | prerequisite | notation), concept_id, topic_id, card_id,
anchor_match_kind, recall_source (structured_definition | harvested_definition)`. Rates: render-among-eligible,
open-per-impression, review-click-per-open, repeated-open, post-exposure confusion, topic-switch. A high open
rate is a DIAGNOSTIC (useful / opaque label / weak recall / needs re-teaching), never auto-interpreted as
"re-teach".

## 9. Notation popovers — separate track (`AZALEA_NOTATION_POPOVERS`, v1.1)

Symbol/abbreviation decoding on formula-family cards, from **existing structured spec metadata**
(`canonical_notes` on formula/rowreduce specs), never prose. Contract: `{symbol, meaning, units?,
current_value?, source (formula spec/card), exact rendered-symbol anchor}`. Anchored to the symbol's first reuse
AFTER the formula card (never on the original legend). Separate flag + budget so a notation-heavy math lesson
never consumes the recall-popup budget.

## 10. Dependencies / non-goals

- `AZALEA_RECALL_POPUPS` **requires** `AZALEA_PREREQ_LINKS`; with prereq-links off, generation is a no-op that
  logs `dependency_missing`.
- Never: undefined-word / "technical-sounding" scanning (dead); teaching new/central concepts via popup;
  multi-paragraph popovers; a popup whose absence breaks comprehension (that belongs in the lesson); runtime
  LLM calls on click; fuzzy (`substring_fallback`) anchors for popups.

## 11. Staging

- **v1 (now):** earlier-topic recall popovers, strict harvest, `match_kind` gate, pill fallback, caps,
  telemetry, the frontend routing change. No LLM. No prereq recall. No notation.
- **v1.1:** notation popovers under `AZALEA_NOTATION_POPOVERS`.
- **v1.5:** `needed_here`, generation-time, batched, stored, omitted when uncertain.
- **v2 (scope plan):** candidates from `PlannedTopic.uses`/`reviews` + `teaching_owners`/`definition_owners`
  (canonical recall from the definition owner), anchors from content claims, "never the principal concept"
  enforced from `teaches`. THIS is where body-topic prerequisite recall becomes possible — because scope
  ownership makes local necessity explicit.
