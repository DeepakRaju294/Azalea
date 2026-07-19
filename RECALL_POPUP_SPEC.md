# Recall Popups — small spec (rev 7)

Status: Draft rev 7 — **approved to run the feasibility audit; contract frozen otherwise.** rev 7 closes three
localized items a seventh review found: a single `source_anchor` can't describe a header+bullet definition
(→ bounded `source_span`), the cryptographic hash/serialization contract was unstated (→ SHA-256 + versioned
length-delimited canonical JSON), and the **active lesson prompt still instructs the model to emit lexical
`popup_only` glosses** (`lean_lesson_prompt.py:324`) — contradicting this spec's dead-gloss premise (→ a
decommission task, §13). Flag: `AZALEA_RECALL_POPUPS` (requires `AZALEA_PREREQ_LINKS`).

> **The defining rule (unchanged, load-bearing):** *No trustworthy recall line means no popup. The ordinary
> review link remains the fallback.* Every decision below is downstream of precision-first.

> **rev 7 changes (all from the seventh review — localized contract + a code decommission):**
> 1. **Bounded `source_span {field, start_index, end_index}`** (§5) — replaces the single-item source anchor so
>    header+bullet harvesting is unambiguous (inline: `start==end`; header+bullet: `end==start+1`, no further
>    siblings). The DISPLAYING anchor stays the single-item `ContentItemAnchor`.
> 2. **Hash/serialization contract** (§5c) — text hash = SHA-256 over UTF-8 of normalized text, lowercase hex;
>    `popup_id` = SHA-256 over a versioned, length-delimited canonical JSON (stable key order, compact), never raw
>    concatenation. `popup_id` is reproducible from the stored link + payload + card context — NOT the payload alone.
> 3. **Decommission active lexical-gloss prompt instructions** (§13) — independent of the audit outcome; keep
>    `popup_only` only where other contracts still require it (cycle-suppressed prereq); never reuse `popup_only`
>    for `RecallPopupV1`.
> 4. **Current-side stale reasons** (§6b) — add `missing_current_card | missing_current_anchor |
>    current_anchor_hash_mismatch` alongside the source-side sentinels.

> **Carried:** §0 feasibility audit is a HARD BUILD GATE (recompute anchor tiers in memory; prevalence metrics;
> `do_not_build` is legitimate); content-hash-only staleness (no per-lesson revision ID); two-sided staleness;
> §4 harvest = concise definition LINE (dash form); §4b fixtures-gated; §6 v1 ranking = order-distance; §7
> cached-render decision; §9 notation NOT buildable from `canonical_notes`; typed action-aware payload validation.

## 0. Feasibility gate — run BEFORE building the UI (read-only audit)

> **AUDIT RESULT (2026-07-18, `scripts/recall_popup_feasibility_audit.py` over 1482 stored lessons) → DECISION:
> `defer_to_v2`. Freeze the interaction design; do NOT start the standalone UI/staleness build.** (An earlier pass
> over-claimed via a loose harvester; it was tightened to enforce §4 self-containment — sentence must open with the
> concept + definitional verb, no pronoun/behaviour/example/modal-"can indicate" lead, no variable-legend heads —
> and every metric is now on its own denominator with the 21 owner-resolved cases hand-labeled and stored.)
> - **Prevalence:** 41 `review_earlier_topic` candidates corpus-wide (2.2%); recent-200-lessons-with-review-links
>   = **14%** (a recency window, NOT a verified flag-on cohort).
> - **Staged rates (own denominators):** anchor-eligibility 25/41 = **0.61**; owner-resolution 21/25 = **0.84**;
>   `deterministic_harvester_acceptance` 11/21 = **0.52** (named honestly — it is the extractor's raw accept rate,
>   NOT "strict harvest", since some accepts are non-clean).
> - **Audited against an EXTERNAL immutable label file** (`scripts/recall_popup_hand_labels.json`, joined by
>   `case_key` — the audit never manufactures verdicts; unlabeled cases surface, not scored). `raw_harvester_
>   acceptance` 11/21; **`audited_strict_valid_yield` = 9/21 ≈ 0.43** (clean definitions actually delivered);
>   **`audited_precision` = 9/11 ≈ 0.82** (of what it kept); `harvester_false_negatives` = 1 (a valid "Row
>   operations are…" definition the extractor dropped on a trailing colon). Labels (occurrence): strict_valid 10,
>   borderline_function 9, invalid 2.
> - **Diversity — strict-valid is the meaningful measure (occurrences overstate breadth):** the delivered clean
>   definitions dedup to only **5 unique recall lines across 4 concepts and 5 study paths** (all-harvested, incl.
>   borderline: 7 lines / 6 concepts / 7 paths). Most "kept" are the *same* "Combinations represent…" line. Four
>   concepts of genuinely-strict content across the whole corpus is far weaker than the occurrence count implies.
> - §4b was NOT load-bearing (failures are absent/function-statement owners, not prose-rescuable) — stays deferred.
> **Read:** anchor + owner stages are healthy and the harvester is precise; the binding constraints are **low volume
> + thin concept diversity + inconsistent definition ownership** — which manual labeling clarifies but cannot fix.
> `defer_to_v2` is a recorded **product judgment on this evidence, not an automatic threshold**. Fold into **v2
> scope-plan `uses`/`definition_owners`**, where candidate volume and canonical definition ownership become
> structural. **Content-type decision to settle at v2 (see §4 note): lean toward the broader typed "recall
> statement" contract** — a strict definition is safe but a concise functional reminder ("TCP congestion control
> regulates the flow of data over a network") is often exactly what lets a learner resume reading.


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
- stamped with `source_topic_id`, `source_card_id`, `source_span`, `source_text_hash`, `harvester_version`
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

> **Content-type decision (settle at v2 — the §0 audit surfaced it; RECOMMENDATION: option (b)).** v1 as written
> promises a strict *definition* (what the concept IS) and therefore rejects **function/behaviour statements** ("TCP
> congestion control **regulates** the flow of data over a network"; "…**calculates** the total probability…") and
> **notation-laden** lines (a Z-score line ending `Z = (X-μ)/σ`). The audit labeled those `borderline_function`:
> self-contained and genuinely useful as recall, but not definitions. Decide by **learner value, not taxonomy** — a
> strict definition is safe but a concise functional reminder is often exactly what lets a learner resume reading.
> **(a)** keep the strict-definition promise (higher precision, lower yield — 0.43); **(b, recommended)** broaden to
> a **typed trustworthy *recall statement*** with a `recall_type ∈ {definition, function, theorem_summary,
> notation}`, EACH with its own deterministic acceptance rules, all still rejecting unresolved notation, examples,
> and dangling/pronoun/modal-"can indicate" leads. `notation` stays gated behind the §9 typed-symbol prerequisite.
> The stored payload records `recall_type` (extending `recall_source`) so telemetry can compare which types earn
> opens. This raises yield (the ~9 borderline_function cases become first-class) without loosening precision.

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
- satisfies the SAME source provenance as §4 (`source_topic_id`, `source_card_id`, `source_span`,
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

ContentItemAnchor                # single displaying item (matches the existing link anchor, lean_lesson_generator.py:4262)
  field
  index

SourceSpan                       # bounded source region — a definition may span header + one bullet
  field
  start_index
  end_index                      # inline: end == start; header + one bullet: end == start + 1; no further siblings

RecallPopupV1
  recall                       # one harvested recall line (§4 / §4b)
  needed_here                  # v1.5 optional: one sentence, generation-time, omitted when uncertain
  current_anchor_text_hash     # hash of the DISPLAYING card's anchored item — input to popup_id + current-side staleness (§6b)
  source_topic_id
  source_card_id
  source_span: SourceSpan      # WHERE in the owner card the recall came from — bounded, ≤2 items
  source_text_hash             # hash(normalize(reconstructed recall line)) — source-side staleness (§6b)
  harvester_version            # extractor/template version — re-run the SAME version to re-hash (§6b)
  recall_source                # structured_definition | harvested_background_definition
  popup_id                     # content-hash join key (§5c) — NO generation ID
  popup_version
```
No `action_label` — the frontend derives "Review topic" from the link action. The payload does NOT duplicate
action-kind/target — those stay on the link. **No `*_lesson_generation_id`** — no per-lesson revision ID exists
(one `Lesson` row per topic, mutated in place); v1 is content-hash only (Option B). The displaying link's own
`anchor` is the single-item `ContentItemAnchor {field, index}` (+ `match_kind`); `current_anchor_text_hash` is the
canonical hash of the item that anchor points at.

### 5c. Hash + serialization contract

- **Text hash** (`source_text_hash`, `current_anchor_text_hash`): SHA-256 over the UTF-8 bytes of the canonically
  normalized text (§5: NFC → trim → collapse internal whitespace → preserve math symbols → no lowercase),
  serialized as lowercase hex.
- **`popup_id`**: SHA-256 over a **canonical JSON payload** whose structural quoting already delimits every
  component (so raw string concatenation's boundary ambiguity cannot arise). Canonicalization = UTF-8, keys sorted
  lexicographically, no insignificant whitespace (compact separators `,`/`:`), then hash the UTF-8 bytes. (This is
  the delimiter — no separate length-prefix framing is needed once fields are JSON-quoted with sorted keys.)
  ```json
  {"concept_id":"…","current_anchor_text_hash":"…","current_card_id":"…","current_topic_id":"…","popup_version":"1","source_text_hash":"…","v":1}
  ```
- `popup_id` is reproducible from the **stored link + recall payload + containing lesson/card context** (it needs
  `current_topic_id`, `current_card_id`, and the link's `concept_id`) — NOT from `RecallPopupV1` in isolation.

**`source_text_hash` hashes the reconstructed recall LINE, not the whole card** — regenerating an unrelated bullet
on the owner card must not invalidate an unchanged recall line. It is computed by running the deterministic
extractor over `source_span` (read the ≤2 bounded items → parse accepted shape → reconstruct the recall line →
canonicalize), NOT by hashing the raw item (the raw `Term: fragment` won't match the reconstructed
`Term — fragment`). Canonicalization is §5's. If any item in `source_span` disappears, treat as stale.

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
  MUST carry `anchor` (incl. `match_kind`) and `recall_popup` — and be **action-aware + typed**, not a blind dict
  copy. Validate `recall_popup` through models (`RecallPopupV1`, `ContentItemAnchor`), not scattered dict checks,
  enforcing: recognized `popup_version`; action == `review_earlier_topic`; nonempty `recall`; valid hash format
  for `source_text_hash` + `current_anchor_text_hash`; `target` + `concept_id` present; eligible current
  `match_kind`; both current and source anchors present; `source_topic_id == target`; `needed_here` within its
  length budget; no multi-paragraph content. A payload failing any check is **dropped without dropping the
  underlying link** (→ plain review pill).
- **Frontend `normalizeInteractiveLinks()` (`page.tsx` ~6247)** carries a comment about the `concept_id` drop that
  "made every click null". `recall_popup` is top-level → MUST be added to its field copy. `anchor.match_kind` is
  nested inside `anchor` (already copied whole on the frontend) → survives there; still assert it. The frontend
  `.slice(0, 6)` cap + lowercased-text dedup run AFTER backend caps (§6) — backend caps must land within them.

Required contract test — assert survival end to end, on BOTH initial generation AND future-card regeneration:
```
generation → schema validation → backend normalize_link → lesson persistence → API response
           → frontend normalization → inline rendering
```
surviving fields: `concept_id`, `anchor.match_kind`, `recall_popup` (incl. `current_anchor_text_hash`,
`source_text_hash`, `harvester_version`, `source_span`, `recall_source`).

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
Drop reasons (selection-time): `missing_anchor | weak_anchor | current_topic_concept | defined_on_card |
missing_recall | duplicate_concept | over_card_cap | over_topic_cap`. Serialization-time staleness reasons live in
§6b (`stale_current_anchor | stale_source | …`).

### 6b. Attach ordering + staleness

- Recall attachment runs **after** final card ordering and content cleanup, so anchors and card IDs are stable:
  `finalize content → finalize card IDs + visible text → emit review links → attach match_kind → harvest recall
  → rank + cap → validate payload/source/anchor → persist`. If later enrichment rewrites the **displaying**
  anchored item, revalidate the anchor and re-hash **`current_anchor_text_hash`**; if it rewrites the **owner**
  source items, re-hash **`source_text_hash`**. (Each hash tracks its own side — §5c.)
- **Staleness validation runs at API serialization on lesson retrieval** — NOT the frontend (the owner lesson may
  not be loaded in the browser). It **always re-extracts and re-hashes** (a generation ID could not prove
  immutability anyway — lessons are mutated in place), validating **BOTH sides** because both the displaying and
  the owner lesson can mutate in place:
  ```
  Current/displaying side (this lesson):
    locate link.anchor {field,index} in the current card → verify eligible match_kind →
    verify link text still has an exact/word-boundary match → hash the anchored item →
    compare current_anchor_text_hash
  Source/owner side (batch-load distinct source cards, ≤3 per topic):
    read source_span (≤2 items) → rerun the SAME harvester_version over it (parse shape →
    reconstruct line → canonicalize) → compare source_text_hash
  ```
  If EITHER side fails (mismatch, or card/anchor gone) → **strip only `recall_popup` from a RESPONSE COPY**, keep
  the underlying review link (renders as the plain pill), emit `stale_current_anchor` or `stale_source`. **Never
  mutate the ORM-backed `lesson_json`** — a read endpoint must not become a repair/mutation path.
- **Harvester-version compatibility:** if `harvester_version` is unknown to the running app → strip the popup,
  keep the review link, log `unsupported_harvester_version`. Do NOT silently rerun the newest extractor (its
  output may differ even on unchanged source). Keep at least the currently-emitted version supported while cached
  lessons may still carry it.
- **Typed stale-event** (dedup so repeated reads don't emit unbounded identical events):
  ```
  { reason, expected_hash, observed_hash: str | null }     dedup key = popup_id + reason + observed_hash
  reason hierarchy — two umbrella reasons, each with granular causes (log the granular one; group by umbrella):
    stale_current_anchor  ⊇  { missing_current_card, missing_current_anchor, current_anchor_hash_mismatch }
    stale_source          ⊇  { missing_source_card, missing_source_span, harvest_failed, source_hash_mismatch }
    unsupported_harvester_version  (standalone — precedes both, since it blocks re-hashing at all)
  ```
  (Rejected for v1: eager reverse-dependency invalidation on owner regeneration — operationally stronger but more
  infrastructure than v1 warrants.)

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
- In-place mutation of the DISPLAYING card's anchored item (re-extracted `current_anchor_text_hash` mismatch)
  strips the popup (`stale_current_anchor`), keeps the review link.
- An `unsupported_harvester_version` payload is stripped (never rerun through a newer extractor), keeps the link.
- `popup_id` recomputed from the stored payload matches the emitted `popup_id` (reproducibility).
- Pre-rev-5 stored links (no `match_kind`) are classified in-memory by the audit, not counted as zero.
- `Term: fragment` becomes the dash definition line; a verb-led fragment (`ACK: confirms receipt`) is rejected.
- `Term: fragment` and header+bullet shapes construct a recall line deterministically; multi-bullet/context-
  dependent fragments are rejected.
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

## 13. Decommission the active lexical-gloss prompt (independent of the audit)

The spec calls the lexical-gloss system dead, but the ACTIVE lesson prompt still instructs the model to generate
`popup_only` glosses for "technical terms a motivated beginner would pause to look up"
(`lean_lesson_prompt.py:324`). Because `popup_only` is rendered inline, these glosses are a **currently
user-visible feature** — so this is a product decision, not silent cleanup, and is called out here rather than
executed by this spec. When approved:
- Remove the lexical-popup generation instructions from active prompts; stop requesting undefined-term popups from
  the lesson model.
- Keep the `popup_only` action ONLY where other contracts still require it (e.g. cycle-suppressed prerequisite
  behavior). Keep old stored lessons with glosses readable.
- Do NOT reuse `popup_only` for `RecallPopupV1` — recall remains an additive enrichment of `review_earlier_topic`.
- Rationale: the active instruction wastes output tokens, encourages unwanted `interactive_links`, adds noise to
  structured generation, and preserves the exact lexical-vs-recall ambiguity this spec exists to end.
