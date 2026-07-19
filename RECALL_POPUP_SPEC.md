# Recall Popups — small spec (rev 5)

Status: Draft rev 5 — **approved for the feasibility-audit stage; UI implementation waits until the revision/
staleness model below is what actually ships.** rev 5 corrects the one real infrastructure mismatch a fifth review
found — **there is no per-lesson generation/revision ID** (`Lesson.topic_id` is unique → one row per topic,
`lesson_json` is mutated IN PLACE on regen/enrichment; `Lesson.id` never changes; `StudyPath.active_generation_id`
is path-level). So v1 uses **content hashes only** (no generation IDs) and **always re-extracts + re-hashes** the
source sentence at serialization. Flag: `AZALEA_RECALL_POPUPS` (requires `AZALEA_PREREQ_LINKS`). The old
`AZALEA_TERM_GLOSSES` lexical-gloss system stays **permanently dead**.

> **The defining rule (unchanged, load-bearing):** *No trustworthy recall sentence means no popup. The ordinary
> review link remains the fallback.* Every decision below is downstream of precision-first.

> **rev 5 changes (all from the fifth review — infra correction):**
> 1. **No generation IDs (Option B).** `source_lesson_generation_id`/`current_lesson_generation_id` are NOT
>    grounded (verified: no per-regen revision ID; lessons update in place). v1 keys off content hashes only:
>    `source_text_hash` + `current_anchor_text_hash` (§5).
> 2. **Regeneration-safe `popup_id`** (§5) = hash(current_topic_id, current_card_id, current_anchor_text_hash,
>    concept_id, source_text_hash, popup_version) — no generation ID.
> 3. **Staleness ALWAYS re-extracts + re-hashes** (§6b) — a generation ID could not prove immutability anyway
>    (in-place mutation). Re-run the deterministic extractor at `source_anchor` every retrieval.
> 4. **API suppression is non-mutating** (§6b) — strip from a RESPONSE COPY; never touch ORM `lesson_json`. Dedup
>    stale telemetry by `popup_id + stale_source_hash`.
> 5. **Harvest = a concise definition LINE, not synthesized sentence** (§4) — `The {term} is {fragment}` breaks on
>    verb-led/plural fragments; use the grammatically-robust dash form + `harvester_version` provenance.
> 6. **Audit recomputes anchor tiers in memory** (§0) — pre-rev-5 stored links lack `match_kind`; add prevalence
>    metrics so a rare-but-precise feature isn't mistaken for a viable one.
> 7. **Backend normalizer is action-aware** (§5b) — validate the payload, don't just copy arbitrary dicts through.

> **Carried:** §0 feasibility audit is a HARD BUILD GATE; §4b constrained background-definition fallback
> (fixtures-gated, same provenance); §6 v1 ranking = order-distance (`order_index` is a real field); §7
> cached-render decision; §9 notation NOT buildable from `canonical_notes` (verified free-form prose).

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

**The audit MUST recompute anchor tiers in memory.** Stored links generated before rev 5 carry `anchor:
{field, index}` with NO `match_kind` — counting stored eligible anchors would report ~zero. Rerun the updated
anchor classifier over stored cards+links in memory (`stored card + link → recompute exact_item / word_boundary /
substring_fallback → continue funnel`); no persistence.

Decision rule:
- **Adequate** rate → build v1 as the strict spec (§4 only).
- **Low** rate → ADD the constrained background-definition source (§4b) — never loosen into general prose or LLM
  term discovery. If §4b's precision can't be demonstrated via fixtures, keep the stricter rule and accept lower
  coverage.

Read-only means **no DB mutations and no generation calls**; the only output is an append-only audit report or
process output. Default to emitting the funnel as JSON to stdout; persist to a telemetry path only when explicitly
requested, so a dry run is genuinely non-mutating. Data note: lessons are DB-resident (the on-disk "cache" is only
a freshness flag); the local `prereq_links_shadow.jsonl` is aggregate-only (counts, not links) — it corroborates
that review-link volume is sparse but cannot compute the rate. The audit therefore runs against stored study paths
(the app's own read session).

**Decision record (report raw COUNTS alongside rates — a high rate over 3 links is meaningless):**
```
FeasibilityDecision
  paths_sampled
  anchored_review_links
  strict_harvest_successes        strict_harvest_rate
  fallback_harvest_successes      fallback_harvest_rate     # §4b, computed as a projection
  human_precision_on_sample       # labeled sample, both sources
  # candidate PREVALENCE — precision on a rare feature isn't a viable feature:
  paths_with_review_links         topics_with_review_links
  review_links_per_100_topics     eligible_popups_per_100_topics
  decision: strict_v1 | enable_4b | do_not_build
  rationale
```
Enable §4b ONLY when it materially improves coverage AND a labeled sample shows acceptable precision AND the
resulting rendered-popup count is large enough to evaluate. Usefulness depends on volume + quality, not a single
universal threshold — hence the decision record over a bare number. If review links themselves are rare
(low `review_links_per_100_topics`), even excellent precision may not justify dedicated UI + telemetry —
`do_not_build` is a legitimate outcome.

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
- it yields ONE concise, self-contained recall statement via an accepted source shape (below), within the display
  budget,
- no unresolved notation and no dangling reference ("this process", "as above"),
- stamped with `source_topic_id`, `source_card_id`, `source_anchor`, `source_text_hash`, `harvester_version`
  (§5), and `recall_source = structured_definition`.

**Accepted source shapes (deterministic, NO LLM).** Key-term cards store fragments, not sentences. The UX needs a
concise, self-contained recall *statement* — NOT necessarily a grammatical sentence — so DON'T synthesize
`"The {term} is {fragment}."` (it breaks on verb-led/plural fragments: `ACK: confirms receipt` →
*"The ACK is confirms receipt."*; `Congestion windows: limits on outstanding data` → *"The congestion windows is
limits…"*). Instead:
1. **Complete inline sentence** — use directly.
2. **`Term: fragment` / header + one definition bullet** — assemble the grammatically-robust **definition line**
   `{Term} — {fragment}` (e.g. *"Congestion window — a sender-side limit on unacknowledged data."*). Concise,
   number-agnostic, no copula to get wrong.
3. **Multiple bullets, or a verb-led / context-dependent fragment** — **reject** (no popup).

This is shape-driven string assembly, never generation. Stamp the extractor with `harvester_version` (below) so a
future template change never makes old payloads look corrupt. This widens strict coverage without touching §4b.

If any check fails → **omit the popup, keep the review pill.** Never substitute the "You saw this earlier in …"
navigation line as recall content.

## 4b. Constrained background-definition source (ONLY if §0 audit shows §4 coverage is too low)

The first complete definitional sentence from the owner topic's designated background/definition section, accepted
ONLY when all hold:
- begins with the canonical concept or an approved alias,
- contains a definitional verb (`is`, `means`, `refers to`) or a tightly-accepted domain pattern,
- contains no instructions, examples, transitions, or unresolved references,
- passes the same length + notation checks as §4,
- satisfies the SAME source provenance as §4 (`source_topic_id`, `source_card_id`, `source_anchor`,
  `source_text_hash`, `harvester_version`), only with `recall_source = harvested_background_definition`.

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
  recall                       # one harvested recall line (§4 / §4b)
  needed_here                  # v1.5 optional: one sentence, generation-time, omitted when uncertain
  source_topic_id
  source_card_id
  source_anchor: {field, item_index}   # WHERE in the owner card the recall came from
  source_text_hash             # hash(normalize(reconstructed recall line)) — content-level staleness (§6b)
  harvester_version            # extractor/template version — re-run the SAME version to re-hash (§6b)
  recall_source                # structured_definition | harvested_background_definition
  popup_id                     # content-hash join key (below) — NO generation ID
  popup_version
```
No `action_label` — the frontend derives "Review topic" from the link action. The payload does NOT duplicate
action-kind/target — those stay on the link. **No `*_lesson_generation_id`** — no per-lesson revision ID exists
(one `Lesson` row per topic, mutated in place); v1 is content-hash only (Option B).

**`source_text_hash` hashes the reconstructed recall LINE, not the whole card** — regenerating an unrelated bullet
on the owner card must not invalidate an unchanged recall line. It is computed by running the deterministic
extractor at `source_anchor` (raw item → parse accepted shape → reconstruct the recall line → canonicalize), NOT
by hashing the raw item (the raw `Term: fragment` won't match the reconstructed `Term — fragment`). Fixed
canonicalization: Unicode NFC → trim → collapse internal whitespace → **preserve** mathematical symbols → do NOT
lowercase (exact comparison). If the source card or `source_anchor` disappears, treat as stale.

**`popup_id` is regeneration-safe via content hashes** — a lesson regenerated with different recall text at the
same IDs must NOT merge telemetry:
```
popup_id = hash(current_topic_id, current_card_id, current_anchor_text_hash, concept_id,
                source_text_hash, popup_version)
```
`current_anchor_text_hash` = the same canonical hash of the DISPLAYING card's anchored item text.

### 5b. Persistence / normalization contract (TWO verified strip paths)

Interactive links are reconstructed field-by-field in BOTH tiers — either drops the new fields silently:
- **Backend `normalize_link` (`interactive_link_validation.py` ~126)** rebuilds the dict with only
  `text/explanation/why_it_matters_here/action/target` (+ conditional `concept_id`) — it does **not copy `anchor`
  at all**, so it would drop `anchor.match_kind` AND `recall_popup`. This path runs on **card regeneration**. It
  MUST carry `anchor` (incl. `match_kind`) and `recall_popup` — and be **action-aware**, not a blind dict copy:
  only `review_earlier_topic` may carry a `RecallPopupV1`; require `target`, `concept_id`, an eligible anchor,
  `source_topic_id == target`, all required source fields, and a recognized `popup_version`. A payload failing any
  check is **dropped without dropping the underlying link** (→ plain review pill).
- **Frontend `normalizeInteractiveLinks()` (`page.tsx` ~6247)** carries a comment about the `concept_id` drop that
  "made every click null". `recall_popup` is top-level → MUST be added to its field copy. `anchor.match_kind` is
  nested inside `anchor` (already copied whole on the frontend) → survives there; still assert it. The frontend
  `.slice(0, 6)` cap + lowercased-text dedup run AFTER backend caps (§6) — backend caps must land within them.

Required contract test — assert survival end to end, on BOTH initial generation AND future-card regeneration:
```
generation → schema validation → backend normalize_link → lesson persistence → API response
           → frontend normalization → inline rendering
```
surviving fields: `concept_id`, `anchor.match_kind`, `recall_popup` (incl. `source_text_hash`, `harvester_version`,
`source_anchor`, `recall_source`).

## 6. Selection pipeline + caps (candidates ≠ rendered) — fully deterministic

```
1 collect deterministic candidates (eligible review_earlier_topic links)
2 reject: weak/missing anchor, current-topic concept, defined-on-card, missing clean recall (§4/§4b)
3 rank remaining — DETERMINISTIC, no semantic "needed for this step" (that is v2):
    a exact_item anchor before word_boundary anchor
    b smallest positive order distance: current_topic.order_index - owner_topic.order_index
      (order_index is a real field; v1 has no trustworthy dependency DAG — graph distance is v2)
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
  revalidate the anchor and re-hash `source_text_hash`.
- **Staleness validation runs at API serialization on lesson retrieval** — NOT the frontend (the owner lesson may
  not be loaded in the browser). It **always re-extracts and re-hashes** (a generation ID could not prove
  immutability anyway — lessons are mutated in place): collect distinct source topic/card refs → batch-load their
  current `lesson_json` (≤3 per topic keeps this small) → **rerun the SAME `harvester_version` extractor at
  `source_anchor`** (raw item → parse shape → reconstruct line → canonicalize) → compare `source_text_hash`. On
  mismatch, or if the card/anchor is gone → **strip the `recall_popup` from a RESPONSE COPY**, leave the
  underlying review link intact, emit `stale_source`. **Never mutate the ORM-backed `lesson_json`** — a read
  endpoint must not become a repair/mutation path. Dedup stale telemetry by `popup_id + stale_source_hash` so
  repeated reads don't emit unbounded identical events. (Rejected for v1: eager reverse-dependency invalidation on
  owner regeneration — operationally stronger but more infrastructure than v1 warrants.)

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
- **Cached lessons that already carry payloads keep rendering** — UNLESS §6b (API-serialization staleness) strips
  a stale one. (Rejected alternative: an API-level effective-feature flag that instantly suppresses all cached
  popups on flag-off. Not worth the coupling — a strict, precision-harvested recall sentence is not harmful to
  keep showing.)

## 8. Telemetry (day one) — event records, joined by `popup_id`

Generation-time events: `recall_candidate_evaluated`, `recall_candidate_dropped` (with drop reason).
Learner events: `recall_popup_rendered` (impression), `recall_popup_opened`, `recall_popup_dismissed`,
`recall_popup_action_clicked` — each with a timestamp, joined to generation via `popup_id`. Dimensions (names
disambiguate the DISPLAYING lesson from the OWNER supplying recall): `popup_version, source (earlier_topic |
notation), recall_source (structured_definition | harvested_background_definition), concept_id, current_topic_id,
current_card_id, source_topic_id, source_card_id, anchor_match_kind`.

**Impression semantics:** an impression = *the anchored trigger was rendered in the active card while that card
was visible* — do NOT emit one on every React rerender. Use a stable exposure key `popup_id + study_session_id +
card_visit_id`. Distinguish repeated opens within one card visit from opens after returning later. Rates:
render-among-eligible, open-per-impression, review-click-per-open, repeated-open. A high open rate is a DIAGNOSTIC
(useful / opaque label / weak recall / needs re-teaching), never auto-interpreted.

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
- Owner-source regeneration (re-extracted `source_text_hash` mismatch, or missing card/anchor) strips the stale
  popup from a response copy at API serialization (`stale_source`), keeps the pill and the review link, and does
  NOT mutate stored `lesson_json`.
- Pre-rev-5 stored links (no `match_kind`) are classified in-memory by the audit, not counted as zero.
- `Term: fragment` becomes the dash definition line; a verb-led fragment (`ACK: confirms receipt`) is rejected.
- `Term: fragment` and header+bullet shapes construct a sentence deterministically; multi-bullet/context-dependent
  fragments are rejected.
- `recall_popup` + `anchor.match_kind` survive BOTH backend `normalize_link` and future-card regeneration (not
  only frontend normalization).
- Backend flag off → no NEW payloads emitted.
- Prerequisite links remain unchanged.
- Notation popovers (when built) do not consume the recall caps.

**Accessibility / UI behavior** (the current popover is a `<details>` element — these are NOT automatic; outside-
click, focus restoration, and viewport collision especially are not free):
- Enter/Space opens the popover; Escape closes it and restores focus to the trigger.
- Outside click closes it; only one recall popover is open at a time.
- The "Review topic →" action is keyboard-reachable; navigating to the review topic closes the popover.
- A screen reader announces the concept name + recall content.
- The popover stays within the viewport on narrow screens.
- Opening the popover never advances the lesson or triggers Q&A.

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
