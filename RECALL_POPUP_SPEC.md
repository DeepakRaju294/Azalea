# Recall Popups — small spec (rev 3)

Status: Draft rev 3 — **architecturally approved** (rev 2). The remaining open question is **coverage, not
correctness**: strict definition-harvest may yield almost no popups against today's stored lessons. rev 3 makes
the **feasibility audit a hard gate before build** (§0), adds a narrowly-constrained fallback source that only
turns on if the audit demands it (§4b), replaces the non-deterministic ranking with a fully deterministic order
(§6), makes the cached-render / flag-off decision explicit (§7), adds source-staleness provenance (§5, §6b), and
downgrades notation to "not buildable from current metadata" (§9). Flag: `AZALEA_RECALL_POPUPS` (requires
`AZALEA_PREREQ_LINKS`). The old `AZALEA_TERM_GLOSSES` lexical-gloss system stays **permanently dead**.

> **The defining rule (unchanged, load-bearing):** *No trustworthy recall sentence means no popup. The ordinary
> review link remains the fallback.* Every decision below is downstream of precision-first.

> **rev 3 changes (all from the third review — approval + refinements):**
> 0. **Feasibility audit is a build gate.** Measure `clean_recall_harvest_rate` on recent stored paths BEFORE
>    building the UI. Low rate → §4b, not looser scanning.
> 1. **Deterministic ranking** — drop "needed for this step" (that needs v2 `uses`); use anchor-tier → DAG
>    proximity → occurrence order → `concept_id`.
> 2. **Cached-render decision made** — payload presence governs frontend rendering; flag-off stops NEW emission;
>    cached popups keep rendering unless their `source_content_hash` no longer matches (suppress-on-stale).
> 3. **Slim payload** — drop `action_label` (frontend derives it); add `source_content_hash` + `popup_id`.
> 4. **Persistence contract** — `normalizeInteractiveLinks()` MUST copy `recall_popup` (top-level → else dropped,
>    the verified `concept_id` bug class). `match_kind` rides inside `anchor` and already survives.
> 5. **Telemetry = event records** joined by `popup_id`, not a boolean `opened`.
> 6. **Notation (§9) is NOT buildable** from `canonical_notes` (verified free-form prose) — needs a typed symbol
>    schema or a deterministic parser + fixtures first.

## 0. Feasibility gate — run BEFORE building the UI (read-only audit)

The whole feature can be "correct" and still worthless if almost nothing harvests. Owner-topic identities today are
title/alias based; an owner lesson may explain a concept in a background card ("TCP congestion control regulates
the flow of data over a network") without ever emitting a `definition`/key-terms bullet headed by that concept —
which §4 (strict) would reject. So, before UI work, run the read-only funnel over recent stored paths:

```
review_earlier_topic links
  → anchored with acceptable match_kind (§3)
  → unique owner topic resolved
  → matching definition candidate found on a definition-owning card (§4)
  → candidate passes sentence-quality checks (§4)
  → popup survives caps (§6)
```

Record count + drop-reason distribution. Headline metric:

```
clean_recall_harvest_rate = successful recall payloads / anchored review links
```

Decision rule:
- **Adequate** rate → build v1 as the strict spec (§4 only).
- **Low** rate → ADD the constrained background-definition source (§4b) — never loosen into general prose or LLM
  term discovery. If §4b's precision can't be demonstrated via fixtures, keep the stricter rule and accept lower
  coverage.

Data note: lessons are DB-resident (the on-disk "cache" is only a freshness flag); the local
`prereq_links_shadow.jsonl` is aggregate-only (counts, not links) — it corroborates that review-link volume is
sparse but cannot compute the rate. The audit therefore runs against stored study paths (the app's own session),
read-only, emitting the funnel above to a JSONL — no generation, no writes.

## 1. Purpose

**When a body lesson uses a concept an EARLIER topic in this path already taught, an anchored popover gives just
enough recall to continue without leaving the lesson.** It never teaches, never defines new material, never
repairs missing instruction. It answers, at most: *what should I remember?* (`recall`) and *where can I review
it?* (`Review topic`). `needed_here` is v1.5.

## 2. v1 candidate selection — deterministic, earlier-topic only

Candidates are EXACTLY the existing `review_earlier_topic` links the deterministic scanner emits. No word
discovery; the LLM never picks phrases. Popup-eligible iff ALL hold:
- anchor `match_kind ∈ {exact_item, word_boundary}` (§3),
- NOT the current topic's principal concept, and NOT defined on the same card,
- a clean recall sentence harvests from the owner topic (§4 / §4b) — else no popup.

External prerequisites remain OUT of v1: `open_study_path` prereq links live ONLY on the intro prereq card
(`lean_lesson_generator.py` "open_study_path links live ONLY here"), which v1 excludes. Body-topic prerequisite
recall waits for scope-plan `uses` (v2). The intro prereq card is unchanged.

## 3. Anchor eligibility — `match_kind`

`_attach_link_anchors` gains a recorded tier (it already computes it):
```
anchor: { field, index, match_kind: exact_item | word_boundary | substring_fallback }
```
Recall popups accept only `exact_item` / `word_boundary`. A `substring_fallback` link still navigates — as a
plain pill, never an inline recall popover. (Existing anchor tests extended to assert `match_kind`.) Note: because
`match_kind` is nested inside `anchor`, frontend normalization already carries it (§5b) — but assert it in tests.

## 4. Recall content — strict harvest (primary), no invention

`recall` is harvested deterministically from the owner topic (resolved via the link's `target` topic_id). Accept
ONLY when:
- the owner topic resolves uniquely,
- the sentence comes from a **definition-owning card** (a `definition`/key-terms bullet or a structured definition
  record) whose head matches the concept or an approved alias,
- it is ONE complete sentence, within the display budget,
- no unresolved notation and no dangling reference ("this process", "as above"),
- stamped with `source_topic_id`, `source_card_id`, `source_content_hash` (§5), and `recall_source =
  structured_definition`.

If any check fails → **omit the popup, keep the review pill.** Never substitute the "You saw this earlier in …"
navigation line as recall content.

## 4b. Constrained background-definition source (ONLY if §0 audit shows §4 coverage is too low)

The first complete definitional sentence from the owner topic's designated background/definition section, accepted
ONLY when all hold:
- begins with the canonical concept or an approved alias,
- contains a definitional verb (`is`, `means`, `refers to`) or a tightly-accepted domain pattern,
- contains no instructions, examples, transitions, or unresolved references,
- passes the same length + notation checks as §4,
- stamped `recall_source = harvested_background_definition` (distinct from `structured_definition`).

The search stays confined to the already-resolved owner topic + the known concept identity — this is NOT prose
scanning. Enable §4b only behind passing fixtures (§10). If precision can't be demonstrated, keep §4 alone.

## 5. Payload (stored on the link at generation time; clicks are instant, no runtime calls)

```
InteractiveLink
  action        # unchanged existing string ("review_earlier_topic")
  target        # unchanged owner topic_id
  concept_id    # unchanged
  anchor        # unchanged + match_kind (§3)
  recall_popup: RecallPopupV1 | null      # additive; presence is the frontend gate (§5b, §7)

RecallPopupV1
  recall              # one harvested sentence (§4 / §4b)
  needed_here         # v1.5 optional: one sentence, generation-time, omitted when uncertain
  source_topic_id
  source_card_id
  source_content_hash # hash of the owner card's content at harvest time — staleness detector (§6b)
  recall_source       # structured_definition | harvested_background_definition
  popup_id            # deterministic: hash(topic_id, card_id, concept_id, popup_version) — telemetry join key
  popup_version
```
No `action_label` — the frontend derives "Review topic" from the link action (only store backend wording when it
is genuinely variable). The payload does NOT duplicate action-kind/target — those stay on the link.

### 5b. Persistence / normalization contract (verified bug class)

`normalizeInteractiveLinks()` reconstructs the link object field-by-field (`page.tsx` ~6247) and carries an
explicit comment about the `concept_id` drop that "made every click null". Therefore:
- **`recall_popup` is top-level → it MUST be added to the normalizer's field copy, or it is silently dropped.**
- `anchor.match_kind` is nested inside `anchor` (already copied whole) → survives; still assert it.
- The normalizer's `.slice(0, 6)` link cap and lowercased-text dedup run AFTER the backend caps (§6) — backend
  caps must land within those limits so a rendered popup is never dropped client-side.

Required contract test — assert survival end to end:
```
generation → schema validation → lesson persistence → API response → frontend normalization → inline rendering
```
surviving fields: `concept_id`, `anchor.match_kind`, `recall_popup`, `source_content_hash`, `recall_source`.

## 6. Selection pipeline + caps (candidates ≠ rendered) — fully deterministic

```
1 collect deterministic candidates (eligible review_earlier_topic links)
2 reject: weak/missing anchor, current-topic concept, defined-on-card, missing clean recall (§4/§4b)
3 rank remaining — DETERMINISTIC, no semantic "needed for this step" (that is v2):
    a exact_item anchor before word_boundary anchor
    b closest prerequisite owner in the topic order / DAG
    c earliest anchored occurrence in the card
    d stable concept_id tie-break
4 apply caps: <=1 per card, <=3 per topic, <=1 per concept (first eligible use)
5 attach recall_popup payloads
6 record dropped reasons (telemetry)
```
Drop reasons: `missing_anchor | weak_anchor | current_topic_concept | defined_on_card | missing_recall |
duplicate_concept | over_card_cap | over_topic_cap | stale_source`.

### 6b. Attach ordering + staleness

- Recall attachment runs **after** final card ordering and content cleanup, so anchors and card IDs are stable:
  `finalize content → finalize card IDs + visible text → emit review links → attach match_kind → harvest recall
  → rank + cap → validate payload/source/anchor → persist`. If later enrichment rewrites an anchored item,
  revalidate the anchor and re-hash `source_content_hash`.
- The owner lesson can be regenerated after a dependent lesson is cached. Detect stale recall by comparing
  `source_content_hash` against the current owner card. **Policy: suppress the popup on mismatch** (precision-first)
  and log `stale_source`; the ordinary review pill remains.

## 7. Frontend interaction + gating

Anchored **popover**, not a modal: opens beside the phrase, does not obscure the card, closes on outside
click/Escape, keyboard accessible; contains `recall` (+ `needed_here` when present) and one "Review topic →"
action; never auto-launches Q&A.

Routing: a `review_earlier_topic` link renders inline **iff** it has `recall_popup != null` + eligible anchor;
otherwise the existing pill. Do NOT add `review_earlier_topic` to `INLINE_ANCHOR_ACTIONS` unconditionally.

Gating contract (decided):
- Backend `AZALEA_RECALL_POPUPS` controls whether payloads are **emitted**. The frontend needs no env-flag
  knowledge.
- The frontend renders the feature **only when a valid `recall_popup` is present** (payload presence alone).
- Turning the backend flag off stops emission for **newly generated** lessons.
- **Cached lessons that already carry payloads keep rendering** — UNLESS §6b suppresses a stale one. (Rejected
  alternative: an API-level effective-feature flag that instantly suppresses all cached popups on flag-off. Not
  worth the coupling — a strict, precision-harvested recall sentence is not harmful to keep showing.)

## 8. Telemetry (day one) — event records, joined by `popup_id`

Generation-time events: `recall_candidate_evaluated`, `recall_candidate_dropped` (with drop reason).
Learner events: `recall_popup_rendered` (impression), `recall_popup_opened`, `recall_popup_dismissed`,
`recall_popup_action_clicked` — each with a timestamp, joined to generation via `popup_id`. Dimensions:
`popup_version, source (earlier_topic | notation), recall_source (structured_definition |
harvested_background_definition), concept_id, topic_id, card_id, anchor_match_kind`. Rates: render-among-eligible,
open-per-impression, review-click-per-open, repeated-open. A high open rate is a DIAGNOSTIC (useful / opaque label
/ weak recall / needs re-teaching), never auto-interpreted.

## 9. Notation popovers — NOT buildable from current metadata (blocked, `AZALEA_NOTATION_POPOVERS`, v1.1)

Intent: symbol/abbreviation decoding on formula-family cards from structured metadata, never prose. **Blocked:**
`canonical_notes` on formula/rowreduce specs is verified **free-form prose**, mixing legends with explanatory
sentences ("Energy grows with the SQUARE of speed — doubling v quadruples KE"). Parsing notation out of it would
recreate the lexical-scanning problem this whole spec exists to kill.

Prerequisite before this track opens: EITHER add a typed symbol schema to the specs
(`{symbol, meaning, units?, formula_owner}` records) OR write a deterministic parser with passing fixtures over
the existing `canonical_notes`. Until one exists, notation stays unbuilt. When it ships: anchored to the symbol's
first reuse AFTER the formula card (never the original legend); separate flag + budget so a notation-heavy math
lesson never consumes the recall budget.

## 10. Acceptance tests

- Clean §4 definition harvest succeeds and renders inline; pill disappears.
- Missing definition → ordinary review pill, no popup.
- §4b background definitional sentence succeeds ONLY under the strict rules (fixtures gate §4b's very existence).
- Dangling "this process" sentence is rejected.
- Unresolved notation is rejected.
- `substring_fallback` anchor never produces a popup (stays a pill).
- `exact_item` anchor outranks `word_boundary` in ranking.
- `recall_popup` survives `normalizeInteractiveLinks()` (the §5b end-to-end contract test).
- `anchor.match_kind` survives normalization.
- Invalid/missing payload retains the pill.
- One concept shown once per topic; ≤1 per card; ≤3 per topic.
- Owner-source regeneration (hash mismatch) suppresses the stale popup (`stale_source`), keeps the pill.
- Backend flag off → no NEW payloads emitted.
- Prerequisite links remain unchanged.
- Notation popovers (when built) do not consume the recall caps.

## 11. Dependencies / non-goals

- `AZALEA_RECALL_POPUPS` **requires** `AZALEA_PREREQ_LINKS`; with prereq-links off, generation is a no-op that
  logs `dependency_missing`.
- Never: undefined-word / "technical-sounding" scanning (dead); teaching new/central concepts via popup;
  multi-paragraph popovers; a popup whose absence breaks comprehension (that belongs in the lesson); runtime
  LLM calls on click; fuzzy (`substring_fallback`) anchors for popups.

## 12. Staging

- **v1 (now):** §0 feasibility audit → earlier-topic recall popovers, strict §4 harvest (+ §4b only if the audit
  demands and fixtures prove it), `match_kind` gate, deterministic ranking, pill fallback, caps, staleness
  suppression, the §5b persistence contract, the frontend routing change, telemetry. No LLM. No prereq recall.
  No notation.
- **v1.1:** notation popovers — BLOCKED on a typed symbol schema or deterministic parser (§9).
- **v1.5:** `needed_here`, generation-time, batched, stored, omitted when uncertain.
- **v2 (scope plan):** candidates from `PlannedTopic.uses`/`reviews` + `teaching_owners`/`definition_owners`
  (canonical recall from the definition owner), anchors from content claims, "never the principal concept"
  enforced from `teaches`. THIS is where body-topic prerequisite recall becomes possible — because scope
  ownership makes local necessity explicit, and where a real "needed for this step" ranking replaces §6's
  deterministic proxy.
