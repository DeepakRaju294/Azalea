# PREREQ_LINKS_SPEC — prerequisites as links, not topics (v8, APPROVED for implementation)

Status: **APPROVED — design frozen, ready to implement (not yet coded).** The review loop converged at v8; further
changes are implementation notes, not spec revisions. Flag: `AZALEA_PREREQ_LINKS` (dark until §11 Phase 2).
Scope: how a study path handles PREREQUISITE knowledge the learner may lack — deliver an **out-of-scope**
prerequisite through the existing `InteractiveLink` infrastructure (inline gloss + on-click link to a fresh,
context-scoped prerequisite study path), **never as a teaching topic inside the current path** — while leaving
**in-scope foundations** as normal teaching topics.

> **v2 changelog (1st review).** Distinguished external prerequisite vs in-path foundation (§0/§1.1); typed
> `AssumedPrerequisite` (§1.2); upstream deterministic context-aware `target_goal` (§3); classification by
> identity not text (§2); verbatim anchoring (§5); `popup_only` eligibility + caps (§2.1–2.3); layered
> card/popup prose (§1.3); operational idempotency (§4); origin metadata (§1.4); cycle guardrails (§4.1);
> flag gates decomposition too (§9/§11).

> **v3 changelog (2nd review — the three mandatory edits + contract tightenings, no redesign).**
> (M1) `InteractiveLink` gains a **`concept_id`** so identity survives generation (§1.3, required for the
> deterministic actions). (M2) Scope classification is now an **auditable procedure** with a 4-rule contract and
> a required `scope_rationale`, not just "decided against goal scope" (§3.1). (M3) The cycle contradiction is
> resolved: **v1 minimally suppresses an exact-ancestor escape hatch** (§4.1, §11 aligned). Plus: identity source
> fixed to **decomposition-emitted (Option A)** (§2); typed **`InPathFoundation`** for a real disjointness check
> (§1.1a); aliases are **resolution-only, never auto-anchored** (§2.4); **deterministic candidate priority** under
> the cap (§2.5a); prereq-card repetition rule (§2.6); **concrete near-duplicate mechanism** — drop the redundant
> field, not the link (§5.1); `popup_only` complexity never promotes to a prereq (§2.1); **server-computed
> lineage** + `target_concept_id` on the click payload (§4, §4.1); **hard-failure scope** with a safe product
> fallback (§6.6); new acceptance tests **A18–A25**.

> **v4 changelog (3rd review — one blocking fallback fix + editorial/wording tightenings, no redesign).**
> (B1, blocking) Two-tier failure: **link-enrichment failure** falls back to the gated path minus links, but a
> **prerequisite-classification-contract failure** must fall back to the **legacy decomposition**, never a
> truncated gated topic list (§6.6, §A27). Plus: §2.2 now defines **candidate generation** (deterministic scan
> for known identities; the LLM proposes only `popup_only`) — closing the numbering gap AND making the
> deterministic actions genuinely deterministic (§2, §2.2, §A26); **resolution normalization vs case-sensitive
> anchoring** separated (§2.2/§5); scope **rule 3 tightened to "develop/demonstrate competency"** and **rule 4 to
> "instructional objective, not mere source presence"** (§3.1); scope warning split into **internal vs
> learner-facing**, v1 internal only (§2.6); **`request_id` retention** via a `UNIQUE(user_id,
> creation_request_id)` constraint (§4); **lineage semantics** documented incl. the clicked concept + rename note
> (§4.1); cycle suppression **serializes to `popup_only`/`target=null`** and the validator enforces it (§4.1);
> new acceptance tests **A26–A27**.

> **v5 changelog (4th review — "begin implementation" pass: four small pre-code edits + clarifications).**
> (1) Foundational dependency types become a **discriminated union** on `classification` (one source of truth for
> `concept_id`/aliases; `prerequisite_id` dropped in favor of `concept_id`) (§1.1a/§1.2). (2) Deterministic scan
> gets **token-boundary + symbol matching rules** so "ring" ≠ "spring" and single-char symbols aren't
> generically scanned (§2.2). (3) New **§6.0 pipeline ordering**: structural classification validation completes
> BEFORE lesson generation, so Tier-2 fallback picks a plan once and never discards generated lessons (§6.0/§6.6a,
> §A30). (4) **A11 + the must-not failure guardrail reworded** to the correct two-tier fallback (collision = Tier
> 2, not Tier 1) (§7/§9). Plus: scanner uses **only decomposition-emitted identities for this path** (global
> glossary deferred) (§2); intro-card cycle exception made explicit (§2.6); scope **rule 1 tightened** to a
> requested learning objective, not mere mention (§3.1, §A29); `scope_warning_internal` becomes a **structured
> `PrerequisiteScopeWarning`** (§2.7, §A31); the **full classified set is preserved** vs the displayed first-N
> (§2.7); live dual-run cost note (§6.6a); new tests **A28–A31**.

> **v6 changelog (5th review — "begin implementation" pass 2: three pre-task edits + refinements).**
> (1) **Two validators**, not one: `prerequisite_classification_validation` (Tier-2 decision point, pre-generation)
> vs `interactive_link_validation` (Tier-1, post-generation) (§6.0/§6.3a/§6.3b). (2) **Identity for ALL teaching
> topics** via a decomposition-emitted `TopicConceptIdentity`, so `review_earlier_topic` works for ordinary core
> topics, not only foundations (§1.1b, §2, §A32). (3) **A15 reclassified Tier 2** — a missing `target_goal` on an
> `assumed_prerequisite` that already lost its topic is a classification-contract failure, not a silent link
> omission (§7/§6.3a). Plus: lineage field **renamed `prerequisite_lineage_concept_ids`** (§1.4/§4.1/§10);
> **plain-text scan projection** + eligible/ineligible regions (headings/code excluded) (§2.2, §A33); scope rule
> stored as a **`scope_rule` enum** beside the rationale (§3.1, §A35); v1 **non-displayed-prereq policy** decided
> (popup/telemetry, no `open_study_path`) (§2.7, §A34); **`priority_order` ordering contract** (§2.7); a named
> **telemetry event set** for the dark rollout (§6.7); new tests **A32–A35**.

> **v7 changelog (6th review — final pre-PR tightenings; converged, no redesign).**
> (1) `scope_rule` **validity per union variant** enforced (`AssumedPrerequisite` == `recognition_only_fallback`;
> `InPathFoundation` ∈ the four in-scope rules) (§6.3a). (2) **Unique concept ownership** among teaching topics —
> one canonical owning topic per `concept_id`; `topic_id`/`concept_id` uniqueness invariants (§1.1b/§6.3a, §A37).
> (3) `review_earlier_topic` scans only topics **earlier than the current** (`topic_index < current`) (§2/§2.2,
> §A36). (4) `creation_request_id` **concurrent-insert + failed-generation** behavior: on unique conflict fetch &
> return the existing path (its current status), never a second generation (§4, §A39/§A40). Plus: projection
> **offsets are internal, not a persisted `InteractiveLink` span** — the frontend anchors the first eligible exact
> occurrence (§2.2); **glossary/navigation collision** precedence (navigation wins; multiple navigation identities
> = Tier 2) (§2.3, §A38); machine-readable **`PrerequisitePrioritySignals`** feeding `priority_order` (§2.7); A22
> reworded for the cycle exception (§7); new tests **A36–A40**.

> **v8 changelog (7th review — resolves the one open contract question, then FREEZE).**
> **Contract decision:** NOT every topic owns a concept — only **concept-owning** topics emit a
> `TopicConceptIdentity`; synthesis/review/application/comparison topics are **non-owning** and emit none. The
> validator requires that every `review_earlier_topic` target resolves to **exactly one** owner, rather than
> forcing every topic to invent an identity (§1.1b, §6.3a, §A41). Plus implementation-note tightenings folded in:
> `topic_index` added to `TopicConceptIdentity` (§1.1b, §A36); structured **`fallback_reason` enum** replaces the
> generic "classification failure" (§6.3a/§6.7); **navigation-set normalized-alias uniqueness** checked upstream
> (§6.3a); **alias normalization** spec'd beyond casing (Unicode + apostrophe variants; hyphens NOT auto-stripped)
> (§2.2); **cycle-suppressed popup exempt** from the incidental `popup_only` cap (still ≤1/topic) (§2.5/§4.1);
> `ask_question` **not emitted** by this feature (compat only) (§1.3); "parent path" → **"current path"** in the
> cycle check (§4.1); `generation_status` gets a **single-worker claim** so idempotency yields one *workflow*, not
> just one row (§4); new test **A41**; §11 gains the **PR split** (PR1 contracts+Tier-2, PR2 scan+Tier-1, PR3
> click+provenance).

## 0. Why this exists

A study path on "Ohm's law" generated a full **topic** for "Introduction to Voltage, Current, and Resistance."
Those were **out-of-scope prerequisites**, not concepts the path set out to teach — teaching them inflated the
path, blurred its goal, and duplicated content that belongs in its own path. The intro card already *named* the
prerequisites; what is missing is a way to (a) briefly explain each in place, and (b) route a still-confused
learner to a dedicated path — **without** spending a topic on it.

The `InteractiveLink` schema (`schemas/lesson_cards.py`) already models this and the frontend already renders the
popups. Two gaps: the **lean generator hardcodes `interactive_links: []`**, and **`open_study_path` is not wired**
(the popup button always opens Q&A; `target` is unused). This spec closes those and adds the decomposition rule.

> **Non-negotiable invariant (v2):** Decomposition classifies every foundational dependency as either an
> **`in_path_foundation`** (required AND within the requested scope) or an **`assumed_prerequisite`** (required
> but OUTSIDE the requested scope). An `in_path_foundation` may emit a teaching topic; an `assumed_prerequisite`
> must NOT — it is delivered by the prerequisite card + an `open_study_path` link. **A concept is never both.**
> The lesson generator CONSUMES this classification and may not alter it. Decomposition is the source of truth
> for prereq-vs-concept AND for scope membership.

## 1. Typed contracts

### 1.1 The classification (decomposition-owned)
Every foundational dependency the decomposition finds is tagged `in_path_foundation | assumed_prerequisite`.
Membership is decided against the requested **goal scope** by the auditable procedure in §3.1 (e.g. "Learn DC
circuits from scratch" pulls voltage *into* scope → `in_path_foundation`; "Learn Ohm's law" leaves voltage *out*
→ `assumed_prerequisite`). The two sets are disjoint by `concept_id` (§1.1a); a concept in `assumed_prerequisites`
may not also be a taught topic (validated, §5/A11).

### 1.1a `FoundationalDependency` — a discriminated union on `classification` (identity emitted, not re-derived — Option A)
Decomposition emits identity **directly**; the lesson generator never runs open-ended concept resolution. A
foundational dependency is a **discriminated union** on `classification`, so `concept_id`/`canonical_name`/`aliases`
have ONE source of truth (no parallel `FoundationalDependency` + subtype pair to keep in sync):
```text
FoundationalDependency = InPathFoundation | AssumedPrerequisite

# shared discriminant + identity (both variants)
#   classification:  "in_path_foundation" | "assumed_prerequisite"
#   concept_id:      str            # stable canonical identity (decomposition-assigned) — the single identity key
#   canonical_name:  str            # canonical concept key/name — the identity used for matching
#   aliases:         str[]          # resolution-only surface forms (§2.4)
#   scope_rule:      enum           # which §3.1 rule fired (structured; §3.1) — for shadow eval
#   scope_rationale: str            # one line justifying scope_rule — for shadow/debug, never learner-facing
#   provenance:      decomposition | source_explicit | inferred

InPathFoundation {
  classification:  "in_path_foundation"
  concept_id:      str
  canonical_name:  str
  aliases:         str[]
  topic_id:        str | null      # the teaching topic it maps to, once ordered
  scope_rule:      enum            # §3.1
  scope_rationale: str
  provenance:      decomposition | source_explicit | inferred
}
```
Disjointness invariant (validated, §A11):
```text
{ ip.concept_id : ip ∈ in_path_foundations } ∩ { ap.concept_id : ap ∈ assumed_prerequisites } == ∅
```
This structured emission need not be persisted long-term, but decomposition must emit enough to VALIDATE the
classification.

### 1.1b `TopicConceptIdentity` — identity for every CONCEPT-OWNING teaching topic (not only foundations)
`review_earlier_topic` must work for an ordinary core concept taught earlier, not just for topics that happen to be
`in_path_foundation`. So decomposition emits an identity record for **every concept-owning** teaching topic:
```text
TopicConceptIdentity {
  topic_id:       str
  topic_index:    int              # position in topic order — drives the "taught EARLIER" test (§2, §A36)
  concept_id:     str
  canonical_name: str
  aliases:        str[]            # resolution-only (§2.4)
}
```
The deterministic scanner (§2.2) therefore receives THREE identity sources:
```text
earlier_topic_identities        (TopicConceptIdentity[] with topic_index < current — → review_earlier_topic)
assumed_prerequisites           (AssumedPrerequisite[]  → open_study_path)
incidental_glossary_identities  (this path's decomposition-emitted glossary only → popup_only seed)
```
Without §1.1b, `review_earlier_topic` would silently only fire for foundation topics — the most important remaining
contract gap in v5.

**Not every topic OWNS a concept (the v8 contract decision).** Synthesis / review / comparison / application /
proof-strategy topics revisit or combine several concepts and introduce **none** — they emit **no**
`TopicConceptIdentity` (forcing them to invent one would be false identity). The contract is therefore about
*owners*, not *topics*:
```text
Only a CONCEPT-OWNING topic emits a TopicConceptIdentity.
Each concept_id has EXACTLY ONE canonical owning topic → exactly one TopicConceptIdentity.
A non-owning topic (synthesis/review/application) emits none; a reinforcement topic does NOT emit a 2nd record.
Uniqueness invariants (validated §6.3a): TopicConceptIdentity.topic_id unique; its concept_id unique;
  AssumedPrerequisite.concept_id unique; InPathFoundation.concept_id unique.
Validation target: every review_earlier_topic reference resolves to EXACTLY ONE owner (not "every topic owns one").
```
Two owners for one `concept_id` is a Tier-2 classification-contract failure (§A37); a non-owning topic with no
identity is normal, not a failure (§A41).

### 1.2 `AssumedPrerequisite` (the other union variant; replaces bare strings)
```text
AssumedPrerequisite {
  classification:  "assumed_prerequisite"
  concept_id:      str             # canonical concept identity (NOT display text) — the single identity key; no separate prerequisite_id
  canonical_name:  str             # canonical concept key/name — the identity used for matching
  aliases:         str[]           # resolution-only surface forms (§2.4)
  display_text:    str             # learner-facing label as it appears in the prereq card bullet
  target_goal:     str             # the SCOPED goal for the on-click path (built upstream, §3)
  why_required:    str | null      # one line: why the current path assumes it
  scope_rule:      enum            # which §3.1 rule fired (here always the recognition-only fallback) — §3.1
  scope_rationale: str             # WHY it fell outside scope (§3.1) — for shadow/debug, never learner-facing
  provenance:      decomposition | source_explicit | inferred
}
```
Because `target_goal` is built by decomposition, the lesson generator never invents it — ownership stays in one
place (consistent with the §0 invariant). `concept_id` is the single identity key everywhere (an
`open_study_path` link's `concept_id` equals this `concept_id`; there is no separate `prerequisite_id`).

### 1.3 `InteractiveLink` (extended: `concept_id` added — M1)
```text
InteractiveLink {
  text:                str          # verbatim phrase in the card (the anchor, §5)
  explanation:         str          # a self-contained 1–3 sentence gloss (popup body) — DEEPER than the bullet
  why_it_matters_here: str | null   # one line connecting the term to THIS point in the path
  action:              popup_only | open_study_path | review_earlier_topic | ask_question
  target:              str | null   # open_study_path → AssumedPrerequisite.target_goal; review_earlier_topic → topic_id
  concept_id:          str | null   # NEW: canonical identity the link represents (survives generation)
}
```
**Why `concept_id` is added (M1).** The classification is identity-based, but a v2 link stored only surface fields
— after generation, nothing downstream knew which canonical concept a link represented. That breaks lineage, cycle
detection, analytics, dedup, alias debugging, and future caching. One optional field fixes all of them; the old
shape cost more than it saved. `target_kind` is NOT added — `action` already implies the target's kind.
Requiredness by action:
```text
open_study_path      → concept_id REQUIRED (== the AssumedPrerequisite.concept_id), target = scoped goal
review_earlier_topic → concept_id REQUIRED (earlier topic's canonical concept_id), target = topic_id
popup_only           → concept_id OPTIONAL (null when unresolved), target = null
ask_question         → concept_id OPTIONAL, target = null
```
**`ask_question` is NOT emitted by this feature** — it remains in the enum for compatibility with existing
producers, which are unchanged. This feature's generator emits only `open_study_path`/`review_earlier_topic`/
`popup_only` (§2); engineers should not expand it to synthesize `ask_question` links.
**Three distinct layers (no duplicate prose):**
- prereq **card bullet**: `**<display_text>** — <one-line what-it-is>` (orientation, visible without interaction).
- popup **`explanation`**: a deeper but still ≤3-sentence clarification (NOT a restatement of the bullet).
- **`why_it_matters_here`**: the contextual tie to the current path.

Near-duplicate prose is handled by the concrete mechanism in §5.1 (drop the redundant field, not the link).

### 1.4 Created-path provenance (recorded now, even though the UI defers it)
A study path created from a prerequisite link records:
```text
origin_path_id:            str | null
origin_topic_id:           str | null
origin_card_id:            str | null
origin_link_text:          str | null
origin_concept_id:         str | null   # the clicked prerequisite's identity
creation_source:           user_goal | prerequisite_link | other
creation_request_id:       str | null   # operational idempotency; UNIQUE(user_id, creation_request_id) (§4)
prerequisite_lineage_concept_ids: str[] # SERVER-COMPUTED; ordered concept_ids traversed through prerequisite links, incl. this path's own origin_concept_id as the final element (§4.1) — never client-authoritative
```
Cheap to add now, painful to retrofit; unlocks analytics, debugging, cycle detection, and a future "return"
breadcrumb without a schema migration later.

## 2. Decision rule — by concept IDENTITY, not text

Because decomposition emits identity (§1.1a, Option A), the lesson generator does NOT resolve concepts open-endedly.
It matches a card phrase against the identities already emitted **for this path** — (a) prior topics, (b)
`assumed_prerequisites`, and (c) any incidental glossary concepts included in THIS decomposition's output. The
scanner may use **only** identity records present in the decomposition output for this path; any global/course-level
concept-registry integration is **deferred** (§12), so it cannot reintroduce open-ended downstream resolution. The
displayed `text` stays the verbatim card phrase; only *classification* uses identity. Known prior-topic and prerequisite candidates are discovered by **deterministic exact scanning** of
finalized card text against emitted canonical names and aliases (§2.2); the LLM proposes only additional
`popup_only` candidates — so `open_study_path` and `review_earlier_topic` never depend on the model *noticing* a
term.

```text
1. match candidate phrase → known concept_id (from emitted identities only; §2.3 on ambiguity).
2. concept_id's owning topic_index < CURRENT topic (taught EARLIER) → review_earlier_topic  (target = that topic_id)
   (a concept whose owning topic comes LATER never yields a backward review link, §A36)
3. concept_id ∈ assumed_prerequisites               → open_study_path       (target = AssumedPrerequisite.target_goal)
4. else, an undefined term worth a gloss            → popup_only            (subject to §2.1)
```
**Precedence collision is a hard failure, not silent resolution:** if a concept is BOTH taught earlier AND in
`assumed_prerequisites`, that is an upstream contradiction (§0 says the sets are disjoint) → validation error
(§A11), never quietly pick one. See §6.6 for failure scope: structural contradictions (this collision) fall back to
the legacy decomposition (Tier 2), while link-only failures fall back to the gated path without links (Tier 1).

Determinism for prereqs (rules 2–3) is intentional: the prereq set + earlier-topic set are authoritative, so the
LLM never decides "is voltage important enough for a path." Rule 4 (`popup_only`) is the ONLY LLM-discretionary
action.

### 2.1 `popup_only` eligibility (the only model-discretion surface — constrain it)
A `popup_only` candidate MUST:
- be necessary to understand the current sentence or visual;
- not already be defined on this card;
- not be common instructional language;
- resolve in ≤ 3 sentences;
- appear verbatim in learner-visible text (§5).

**Exclusions (never a popup):** ordinary words; action verbs; a term already linked recently in this path; terms
only in optional metadata; symbols already explained in a legend/formula annotation.

**Complexity never promotes to a prerequisite (preserves decomposition ownership).** A term whose explanation would
require multiple NEW concepts is **ineligible** for `popup_only`. The generator MUST NOT promote it to
`open_study_path`. If decomposition already classified its identity as an `assumed_prerequisite`, rule 3 applies;
otherwise the candidate is **dropped** and telemetry records a *possible decomposition omission* (§A20). The
generator never discovers-and-creates a prerequisite.

### 2.2 Candidate generation (where candidates come from — makes the deterministic actions actually deterministic)
The pipeline is split so that the navigation actions do not depend on the model noticing a term:
```text
known-identity candidates (→ open_study_path / review_earlier_topic):
  - deterministically SCAN the finalized card text for exact matches (per §2.2 normalization) of the
    canonical names + aliases of emitted identities (prior topics, assumed_prerequisites, known glossary);
  - each match becomes a candidate with text = the card's actual surface phrase (its real casing).
popup_only candidates (→ rule 4 only):
  - the LLM MAY propose additional verbatim anchor phrases, subject to §2.1 eligibility + §5 anchoring.
```
So `open_study_path`/`review_earlier_topic` are emitted by the deterministic scan even if the LLM proposed no link
(§A26); the LLM's discretion is confined to `popup_only`.

**Resolution normalization vs anchoring (they differ):**
```text
identity RESOLUTION: match after this deterministic normalization —
    Unicode NFC → lowercase → normalize apostrophe variants ( ’ ` → ' ) → collapse whitespace → preserve
    semantic punctuation (do NOT auto-strip hyphens: "potential-difference" ≠ "potential difference" unless BOTH
    are listed aliases).  (so "Ohm’s law" resolves to "Ohm's law"; "Potential difference" ↔ "potential difference")
anchor  VALIDATION:  exact, case-sensitive match of the SELECTED surface phrase in finalized text (§5)
```
The candidate keeps the card's real casing; the alias registry need not store every capitalization/apostrophe
variant. No aggressive fuzzy matching — just the punctuation/casing normalization above.

**Match granularity (token boundaries + symbols — avoids "ring" matching "spring"):**
```text
word-based canonical names / aliases → match COMPLETE normalized TOKEN SPANS only (word boundaries),
                                        never a raw substring inside a longer word.
symbol / punctuation-bearing aliases → exact literal match under an explicit per-symbol match policy
                                        (e.g. "O(n)", "π", "∑").
single-character symbols (C, R, V, x) → NOT discovered by generic text scanning; eligible only if REGISTERED
                                        with a symbol-specific policy (else they'd match everywhere).
```
So `ring` never matches `spring`; `V` is not auto-linked on every occurrence; a registered `O(n)` matches
literally. This keeps the deterministic scan precise enough to drive navigation.

**Scan surface = one canonical plain-text projection (validator and frontend MUST agree, §A33):**
```text
final card content
  → produce a learner-visible PLAIN-TEXT projection (strip markdown **bold**, `code`, and \(math\) delimiters)
  → deterministic identity scan over that plain text (offsets used INTERNALLY for overlap resolution only)
  → the anchor's `text` is the plain-text surface phrase; §5 verbatim validation runs against the SAME projection.
```
The validator and the frontend anchor against the identical projection — never one over raw markdown and the other
over rendered text. **Offsets are NOT persisted:** `InteractiveLink` stays `text`-only (no span field); the frontend
deterministically re-anchors the **first eligible exact occurrence** under these same rules. The scanner's offsets
are a transient implementation detail, not a schema contract.

**Eligible vs ineligible regions (avoid surprise links on titles/metadata):**
```text
ELIGIBLE:   body text · bullet text · explanatory labels
INELIGIBLE: card title/heading · navigation labels · optional metadata · code/symbol tokens
            (unless registered under the §2.2 symbol policy)
```
A concept in both a card title and its body links only in the body.

### 2.3 Identity resolution is exact, never fuzzy (controls navigation → must be deterministic)
Matching a card phrase to a `concept_id` uses exact canonical-name/alias equality (after the §2.2 resolution
normalization) only:
```text
resolved   → exactly one concept_id matches → its rule (2/3/4) applies
ambiguous  → >1 concept_id matches          → NO deterministic action; candidate dropped or popup_only-if-eligible (§A19)
unresolved → 0 concept_id matches           → may become popup_only if eligible (§A18); never open_study_path/review
```
No fuzzy/embedding match may silently select an identity for a navigation action.

**Collision precedence across identity sources (§A38):**
```text
navigation identity (earlier-topic OR assumed-prerequisite) OUTRANKS an incidental glossary identity:
  - navigation identity + glossary identity  → use the navigation identity; emit duplicate-identity telemetry.
  - TWO navigation identities (earlier-topic AND assumed-prerequisite) → Tier-2 structural failure (§2 precedence).
```
A glossary match must NEVER downgrade a deterministic navigation action to `popup_only`.

### 2.4 Aliases are resolution-only (never auto-anchored)
`aliases` exist ONLY to resolve a card phrase to a `concept_id`. They are **never inserted into cards** and **never
automatically used as an anchor**. A link's anchor is still the verbatim `text` the generator explicitly selected
and which appears in the finalized card (§5). (This avoids an implementation linking every alias it can find.)

### 2.5 Caps (numeric, testable)
```text
≤ 3 interactive links per card.
≤ 1 open_study_path link per prerequisite per topic.
≤ 1 popup_only link for the same canonical concept per path (path-level, not just per-card).
```
The intro **prerequisites card** is exempt from the per-card cap (it may name > 3 prerequisites), but see §2.6/§2.7.
A **cycle-suppressed** `popup_only` (a safety transform of an `open_study_path`, §4.1) is **exempt from the
incidental `popup_only` path-cap** (it must not be dropped as if it were an ordinary gloss), but is still limited to
≤ 1 per prerequisite per topic.

### 2.5a Candidate priority under the per-card cap (deterministic — A21)
When a card yields more candidates than the cap, select in this order:
```text
1. a required assumed-prerequisite concept NOT yet linked in this topic  (real knowledge gap, escape hatch)
2. an earlier-topic concept directly needed for the current reasoning     (review)
3. remaining assumed-prerequisite candidates
4. popup_only candidates
Within a tier: first occurrence in reading order → longer phrase before shorter → stable concept_id/lexical tie-break.
```
This favors surfacing genuine gaps and review over incidental glosses, while the "not yet linked in this topic"
guard (tier 1) stops one prerequisite from crowding out everything across a topic's cards.

### 2.6 Prerequisite repetition across a topic
```text
The intro prerequisite card ALWAYS provides an interactive gloss for every displayed assumed prerequisite —
  using open_study_path, UNLESS exact-ancestor suppression converts it to popup_only (§4.1).
Later cards link a prerequisite ONLY where it is immediately necessary to the local reasoning,
  and never more than once per prerequisite per topic (§2.5).
```
This prevents the same escape hatch reappearing on every card, while making the cycle-suppression exception to
"always `open_study_path`" explicit (an ancestor prerequisite still gets a gloss, just not a path-opening link).

### 2.7 Too many prerequisites is a scope signal
If decomposition tags **more than N (default 6)** `assumed_prerequisites`, that usually means the requested path is
mis-scoped or the learner-level assumption is wrong. Decomposition emits an explicit **scope warning** + a priority
ordering, never an arbitrarily truncated list with no signal (§A17).

**Truncation is presentation-only — the typed set stays complete (§A31):**
```text
assumed_prerequisites            = the COMPLETE classified set (never truncated / reclassified / deleted).
displayed_assumed_prerequisite_ids = the prioritized first N shown on the prereq card.
```
An omitted-from-display prerequisite still exists in `assumed_prerequisites` and may still resolve for telemetry and
glossing. **v1 policy (§A34):** a prerequisite OUTSIDE `displayed_assumed_prerequisite_ids` may become `popup_only`
or drop, but **must NOT earn an `open_study_path`** on a later card — otherwise a learner meets a deep link to a
prerequisite that was hidden from the declared prerequisite list, and a lower-priority prereq surfaces while a
higher-priority one stays hidden. Shadow data later decides whether to raise the display cap or re-scope.

**`priority_order` — deterministic dependency ordering, computed from machine-readable signals (not prose):**
Decomposition emits, per assumed prerequisite, the signals the ordering needs (they need not persist past ordering):
```text
PrerequisitePrioritySignals {
  is_direct_goal_dependency: bool
  dependent_topic_count:     int     # how many in-scope topics depend on it
  first_use_topic_index:     int
  provenance:                decomposition | source_explicit | inferred
}
```
The ordering then applies deterministically:
```text
1. is_direct_goal_dependency (true first);
2. greater dependent_topic_count;
3. smaller first_use_topic_index (earliest use);
4. source_explicit before inferred;
5. stable concept_id tie-break.
```
The model may contribute an importance hint, but the final ordering is computed from these fields so fixtures are
reproducible.

**Structured warning (not just a string), split so v1 ships no raw diagnostics to a learner:**
```text
PrerequisiteScopeWarning {
  code:           "too_many_assumed_prerequisites"
  count:          int          # e.g. 8
  threshold:      int          # e.g. 6 (N)
  priority_order: str[]        # concept_ids, most-important-first
  message:        str          # human-readable internal text
}
scope_warning_learner_text: str | null   # v1: null (not surfaced). A future gentle framing, e.g.:
  "This topic builds on several earlier ideas. The most important are listed below; if several are unfamiliar,
   consider starting with a broader introductory path."
```
Structured telemetry is easier to aggregate/test/tune across domains. v1 emits the `PrerequisiteScopeWarning`
(internal) only; a learner-facing message is a deferred product decision (§12), never the blunt "this path has too
many prerequisites."

## 3. The prerequisite target goal — built UPSTREAM, deterministic, context-aware

`AssumedPrerequisite.target_goal` is NOT a bare term and NOT an unconstrained LLM sentence. It is produced by
decomposition via a deterministic builder that carries the ORIGIN context, so the generated path is scoped to what
the learner actually needs:
```text
target_goal = build_prerequisite_goal(canonical_name, originating_domain, originating_goal_context)
```
Context matters: "vectors" as a prerequisite to physics ≠ "vectors" as a prerequisite to computer graphics.
```text
# Ohm's law → voltage
"Understand the basics of voltage — what it represents, how it is measured, and how it drives current in a circuit."
# force decomposition → vectors
"Learn the vector fundamentals needed to understand force decomposition."
```
A missing/empty `target_goal` for an `assumed_prerequisite` is a validation failure (or the link is omitted with
telemetry) — the display text is **never** silently used as an unscoped fallback (§A15).

### 3.1 Scope classification is an auditable procedure (M2)
Even when the implementation uses an LLM, the DECISION is constrained by an explicit contract and must emit a
rationale, so it is testable and debuggable rather than an opaque judgment:
```text
A foundational dependency is `in_path_foundation` when AT LEAST ONE holds:
  1. the goal explicitly asks the learner to LEARN / explain / calculate with / compare / demonstrate competency in
     the dependency — not merely MENTIONS it as context (so "Learn voltage and Ohm's law" → voltage in scope, but
     "How does Ohm's law relate voltage and current?" may leave voltage `assumed_prerequisite`, §A29);
  2. the goal contains beginner/from-scratch language AND the dependency is part of the minimum teaching sequence;
  3. achieving the requested goal requires the learner to DEVELOP or DEMONSTRATE COMPETENCY in the dependency
     itself, rather than merely recognize enough of it to follow the target concept;
  4. the user explicitly requires it, OR the source-grounded instructional scope selected for the path identifies
     it as an OBJECTIVE of the requested path — not merely because the term appears in the source material.
Otherwise, if it is required only to RECOGNIZE/UNDERSTAND an in-scope concept (not to achieve the goal itself),
classify it as `assumed_prerequisite`.
```
Every classification carries a **structured `scope_rule` enum** (parsing free text is unreliable) plus a one-line
rationale:
```text
scope_rule: enum {
  explicit_objective            # rule 1
  beginner_minimum_sequence     # rule 2
  competency_required           # rule 3
  source_or_user_objective      # rule 4
  recognition_only_fallback     # the else-branch → assumed_prerequisite
}
scope_rationale: str    # one line of justification; used in shadow eval + debugging, never learner-facing
```
The enum lets shadow eval measure directly which rule fires most, which correlate with fallback, and whether rule 3
is overused across domains (§A35).
The broad-beginner fixture (A9) exercises rule 2/3 (learning DC circuits from scratch requires *developing
competency* in voltage → `in_path_foundation`); the Ohm's-law fixture (A1) exercises the fallback (the goal only
requires *recognizing* voltage → `assumed_prerequisite`). The competency-vs-recognition line in rule 3 is what
keeps "voltage can't be taught without teaching voltage" from silently defeating A1. `scope_rationale` is the
auditable trail that lets shadow telemetry catch scope overcorrection before it reaches a learner. This moves the
ambiguity upstream AND constrains it — the point of §0.

## 4. Lazy generation of prerequisite paths

`open_study_path` stores only `{text, explanation, why_it_matters_here, target, concept_id}` at lesson-generation
time — **no study path is created.** The path is generated **only when the learner clicks**:
```
click → POST /study-paths { goal: link.target, target_concept_id: link.concept_id,
                            origin_path_id, origin_topic_id, origin_card_id, origin_link_text,
                            source: "prerequisite_link", request_id }
      → generate on demand → navigate to it
```
- **Fresh each COMPLETED, INTENTIONAL click** (no semantic dedup in v1). Caching/reuse of an existing path for the
  same goal is an explicit, isolated later optimization (§11), deferred because it does not change the contract.
- **Operational idempotency** (not semantic dedup): a `request_id` scoped to one click attempt lets the backend
  reject/reuse duplicate in-flight requests from a double-click, a repeated press during generation, or a network
  retry — so "fresh each click" means each *intended* invocation, not each HTTP packet (§A14). This is NOT the
  deferred cross-click caching. **Retention:** the created path stores `creation_request_id` with a
  `UNIQUE(user_id, creation_request_id)` constraint; a retry of the same `request_id` returns the already-created
  path instead of generating a second one. No separate idempotency subsystem — one indexed column.
  **Concurrency + failure semantics (§A39/§A40):**
  ```text
  insert path with creation_request_id
  on UNIQUE conflict → fetch & return the EXISTING path (with its current generation_status), never a 2nd generation.
  same request_id ALWAYS resolves to the same path record; retry operates on THAT path (returns its status:
    pending | generating | complete | failed), it does not mint a new one.
  a FAILED generation is not made permanently unrecoverable by the uniqueness contract — retry/regeneration acts on
    the existing record (the exact regen mechanism is outside this spec).
  ```
  (If the path model lacks a `generation_status`, add one: `pending | generating | complete | failed`.)
  **One row ≠ one workflow.** The UNIQUE constraint guarantees a single *row*; to guarantee a single *generation
  workflow* (A39), only one worker may transition `pending|failed → generating` via an atomic compare-and-set / row
  lock. A concurrent caller that loses the claim attaches to the existing row and returns its status — it does NOT
  start a second generation. Status ownership: `pending` = row committed; `generating` = a worker claimed it;
  `complete` = persisted; `failed` = terminal attempt, retryable on the same row.
- **`target_concept_id`** is sent so the server can compute lineage (§4.1) without trusting client-supplied
  ancestry. `link.concept_id` is required for `open_study_path` (§1.3), so it is always available here.
- The popup still shows the gloss + `why_it_matters_here`, so a learner can proceed without clicking; the link is
  the escape hatch, not a forced detour.

### 4.1 Cycle / recursion guardrails (M3 — v1 minimally suppresses, not just detects)
Prerequisite paths may themselves surface prerequisite links, which can loop
(`Ohm's law → voltage → electric potential → voltage`). **Lineage is server-computed only:**
```text
new_path.prerequisite_lineage_concept_ids = parent.prerequisite_lineage_concept_ids + [clicked target_concept_id]
```
**Semantics (the field is named for what it holds):** `prerequisite_lineage_concept_ids` is the ordered list of
**prerequisite concepts traversed through links**, and it **includes the current path's own clicked concept** (the
final element) — hence "lineage," not "ancestry." It is NOT guaranteed to contain the root user-goal concept unless
that root path recorded its own primary concept separately. When emitting links WITHIN a path, the cycle check tests
a candidate against **the current path's own** `prerequisite_lineage_concept_ids` (which already contains this
path's clicked concept + all it descends from) — testing against the current path's list avoids an off-by-one. The
client never supplies authoritative lineage; a malformed/forged payload is ignored and recomputed from persisted
origin data (§A25).

**v1 behavior (resolves the v2 §4.1-vs-rollout contradiction):** once lineage exists, suppressing an EXACT ancestor
is a small deterministic guardrail, so v1 does it. Suppression happens at link-emission time and is **serialized
into the link's final state** (not an `open_study_path` the frontend must remember to ignore):
```text
if a candidate open_study_path's concept_id ∈ the current path's prerequisite_lineage_concept_ids:
    action     := popup_only          # transformed state the validator enforces
    target     := null
    concept_id := retained            # identity kept for analytics/telemetry
    RETAIN the popup explanation (learner still gets the gloss);
    emit telemetry.
```
Natural learner navigation is not blocked; only the exact-ancestor escape hatch is withheld. Anything beyond exact-
ancestor suppression (heuristic near-cycles, policy tuning) stays deferred (§11).

## 5. Anchoring model (verbatim `text` → deterministic frontend behavior)

Validation runs **after** all card rewriting / render-text normalization (so the anchor matches what the learner
sees). Deterministic v1 rules:
- exact, **case-sensitive** match against the finalized card text;
- anchor only the **first eligible occurrence** per card;
- prefer the **longest** matching phrase when candidates overlap (e.g. "electric field" beats "field");
- **reject overlapping** links;
- a link whose `text` is not present verbatim is **dropped** (§A6).

### 5.1 Near-duplicate prose — concrete, deterministic mechanism (not semantic similarity)
Approximate semantic similarity would be nondeterministic and expensive, and dropping a whole link over repetitive
prose is worse than keeping it. So v1 uses a cheap deterministic check and drops only the REDUNDANT FIELD:
```text
Normalize (lowercase, collapse whitespace, strip trailing punctuation), then:
  HARD (fix in place, keep the link):
    - explanation == bullet-text, OR one fully contains the other        → regenerate/omit the popup explanation, keep the bullet + link
    - why_it_matters_here == explanation, OR one contains the other       → set why_it_matters_here = null
  SOFT (telemetry only, no drop):
    - high semantic similarity per the EXISTING quality judge             → warn; leave content, flag for later
```
A structural contradiction (§2 precedence) is still a hard link failure; near-duplicate prose is not — it is a
field-level cleanup. The link survives.

## 6. Implementation surface (the vertical slice — 5 components)

### 6.0 Pipeline ordering (structural validation BEFORE lesson generation — makes Tier-2 fallback cheap)
The stages run in a fixed order so a Tier-2 (§6.6) fallback selects the winning topic plan **once**, before any
lesson is generated against it — never discarding already-generated lessons:
```text
legacy decomposition            (baseline; also the shadow-comparison baseline)
gated decomposition + classification (§6.1)
prerequisite_classification_validation (§6.3a: disjointness/target_goal/collision)  ← Tier-2 decision point
choose winning decomposition    (gated if valid, else legacy — §6.6/§6.6a)
lesson generation               (against the chosen plan only)
link enrichment                 (§6.2)
interactive_link_validation     (§6.3b: anchors/caps/eligibility/near-dupes)        ← Tier-1 decision point
```
Two SEPARATE validators, one per tier — never one validator mixing pre- and post-generation failures.
Because the structural decision precedes generation, Tier 2 never has to throw away lessons; Tier 1 acts only on
the already-chosen plan. This ordering is normative (§A30).

### 6.1 Decomposition (source of truth) — `topic_decomposition` / Engine B
Classify each foundational dependency `in_path_foundation | assumed_prerequisite` by the §3.1 procedure (emitting
`scope_rule` + `scope_rationale`); emit identity directly (§1.1a, Option A) AND a `TopicConceptIdentity` for every
concept-owning teaching topic (§1.1b — synthesis/review topics emit none); fold `assumed_prerequisite`s into the
intro's prerequisites (as typed `AssumedPrerequisite`,
§1.2) and emit **no** teaching topic for them; build each `target_goal` (§3); emit the §2.7 scope warning +
`priority_order` when over the limit. The prereq/concept AND in-scope/out-of-scope splits are decided HERE, never
downstream.

### 6.2 Lean generator — `lean_lesson_generator`
Stop hardcoding `interactive_links: []`. Emit links by the identity rule (§2), anchored per §5, stamping
`concept_id` (§1.3); apply the §2.5a priority under the cap; write the layered prereq card (§1.3/§5.1). Never
re-classify or promote a concept the decomposition already tagged (§2.1).

### 6.3a Classification validation (Tier 2, pre-generation) — `prerequisite_classification_validation`
Runs at the §6.0 Tier-2 decision point, BEFORE lesson generation, on decomposition output only. Each check maps to
a structured **`fallback_reason` enum** (not free text — telemetry + tests read it directly):
```text
fallback_reason ∈ {
  prerequisite_topic_overlap      # a prereq concept_id also owned by a teaching topic (disjointness, §A11)
  missing_target_goal             # an assumed_prerequisite with empty target_goal (§A15)
  duplicate_concept_ownership     # two owners for one concept_id (§A37)
  ambiguous_navigation_identity   # one normalized alias → >1 navigation concept_id (see below)
  invalid_scope_rule              # scope_rule doesn't match the variant (below)
  missing_owner_for_review        # a review_earlier_topic reference with no / >1 owner
}
```
Checks:
- **disjointness** → `prerequisite_topic_overlap`;
- every `assumed_prerequisite` has a non-empty `target_goal` (missing, when the topic was already dropped, is a
  Tier-2 failure, NOT a silent link omission) → `missing_target_goal` (§A15);
- **uniqueness** (§1.1b): `TopicConceptIdentity.topic_id` + `concept_id` unique; `AssumedPrerequisite.concept_id`
  unique; `InPathFoundation.concept_id` unique; two owners for one `concept_id` → `duplicate_concept_ownership`
  (§A37);
- **owner resolvability**: every `review_earlier_topic` reference resolves to EXACTLY ONE owner (a non-owning
  synthesis/review topic having no identity is fine, §A41) → else `missing_owner_for_review`;
- **navigation-set normalized-alias uniqueness** (catch ambiguity ONCE, upstream, not card-by-card): within the
  navigation identity set (earlier-topic ∪ assumed-prerequisite), each normalized canonical-name/alias (§2.2) maps
  to ≤ 1 navigation `concept_id` → else `ambiguous_navigation_identity`. (Glossary overlap is allowed — navigation
  wins, §2.3.)
- **`scope_rule` validity per variant**: `AssumedPrerequisite.scope_rule == recognition_only_fallback`;
  `InPathFoundation.scope_rule ∈ {explicit_objective, beginner_minimum_sequence, competency_required,
  source_or_user_objective}` → else `invalid_scope_rule`.
Any failure → discard the gated decomposition, use the legacy plan (§6.6 Tier 2), stamping the `fallback_reason`.

### 6.3b Link validation (Tier 1, post-generation) — `interactive_link_validation`
Runs after lesson generation + enrichment, on the links only:
`text` verbatim against the §2.2 projection (§5); `concept_id` present for `open_study_path`/`review_earlier_topic`
(§1.3); `open_study_path` has a non-empty `target`; caps (§2.5); `popup_only` eligibility + no-promotion (§2.1);
near-duplicate field cleanup (§5.1); ambiguous/unresolved identity handling (§2.3); cycle-suppression serialized
state (§4.1); dedupe. Any failure → drop the offending link (or, if unrecoverable, `interactive_links = []`, §6.6
Tier 1) — the topic list is untouched.

### 6.4 Frontend — `learn/page.tsx` (`InteractiveLinkPopup`)
Route the action button by `action`: `open_study_path` → create-path-and-navigate with the §4 payload
(`request_id` + `target_concept_id`); `review_earlier_topic` → navigate to `target` topic; `popup_only` → gloss
only, no button; `ask_question` → existing Q&A. Stop routing every action to `onAskAboutText`.

### 6.5 Endpoint — `study_paths` route
Reuse the existing create-study-path flow, callable from the click handler with `goal = link.target`; persist the
origin metadata (§1.4); **server-compute** `prerequisite_lineage_concept_ids` from the parent + `target_concept_id`
(§4.1); honor `request_id` idempotency via `UNIQUE(user_id, creation_request_id)` — a duplicate returns the
existing path (§4). No new generation logic — an entry point.

### 6.6 Failure SCOPE — TWO tiers, because the flag changes decomposition too (A24, A27; B1 blocking)
A supplemental navigation feature must never cost the learner the whole path — BUT the flag also changes the topic
decomposition, so "strip the links" is only the right fallback for ONE of the two failure kinds. Distinguish them:

**Tier 1 — link-enrichment failure** (topic classification is VALID; only the links are bad: a missing anchor, an
ineligible popup, a near-duplicate that can't be cleaned):
```text
Dark/shadow:  mark enrichment invalid; emit telemetry; do NOT expose links; keep the gated topic/lesson output for comparison.
Live:         fail ONLY the enrichment layer → render the gated path with interactive_links = []; do NOT fail generation.
```

**Tier 2 — prerequisite-classification-contract failure** (the foundational sets themselves are contradictory or
malformed: disjointness violated §A11, an `assumed_prerequisite` with no `target_goal` that also lost its topic,
etc.). Here the **gated topic list may be INCOMPLETE** (a foundation was wrongly demoted and its teaching topic
removed), so stripping links is NOT safe — falling back to "no links" would ship a path missing a topic:
```text
Dark/shadow:  discard the gated decomposition result; keep the LEGACY (pre-flag) decomposition as the baseline; emit telemetry.
Live:         DISCARD the gated decomposition; regenerate/reuse the LEGACY topic decomposition (full topic list);
              do NOT merely remove links from the gated topic list.
```
Internally both are hard validator failures (telemetry + blocked bad output); the difference is the fallback
TARGET — Tier 1 falls back to the gated path minus links, Tier 2 falls back to the legacy decomposition. This is
the B1 blocking distinction: never let a classification contradiction silently drop a teaching topic.

### 6.6a Decomposition fallback wiring (Tier 2, §6.6)
Because Tier-2 fallback returns the LEGACY decomposition, generation must keep the pre-flag decomposition reachable
when the flag is on: run the legacy decomposition as the baseline, run the gated classification on top, and if the
gated classification fails **structural validation (§6.0 decision point)**, **use the legacy result** (full topic
list) rather than the partially-mutated gated one. In the dark phase this baseline is already computed for shadow
comparison, so Tier-2 fallback is "prefer the baseline we already have."

**Dual-run cost over the lifecycle (not permanent runtime cost):**
```text
Dark rollout:          always run both (legacy baseline + gated) — needed for shadow comparison anyway.
Initial live rollout:  retain the dual-run for the safety fallback.
Later stabilization:   once reliability thresholds are met, legacy may become ON-DEMAND regeneration on failure,
                       or be dropped — so shadow architecture doesn't silently become permanent 2× decomposition cost.
```

### 6.7 Telemetry event set (the dark rollout lives or dies on this — name it now)
Minimum events so the dark phase produces actionable evidence:
```text
prereq_classification_emitted          prereq_link_emitted            prereq_cycle_suppressed
prereq_classification_fallback         prereq_link_clicked            prereq_scope_over_limit
prereq_link_enrichment_failed          prereq_possible_decomposition_omission
```
Standard dimensions on each (where applicable):
```text
domain · scope_rule · concept_id · action · failure_tier · fallback_reason · prerequisite_count · flag_phase
```
`failure_tier ∈ {tier1_link, tier2_classification}`; `flag_phase ∈ {dark, initial_live, live}`; `fallback_reason`
is the structured §6.3a enum (never free text). This is naming, not a telemetry subsystem — but naming it now is
what makes A1/A9 scope-overcorrection and rule-3 overuse measurable.

## 7. Acceptance tests (behavior → expected)

| # | Scenario | Expected |
|---|---|---|
| A1 | "Ohm's law" path; voltage/current/resistance are out-of-scope prereqs | **no topic** for them; named + briefly explained in the prereq card |
| A2 | A prerequisite (voltage) in `assumed_prerequisites` | `open_study_path` link, `target` = the built scoped goal (§3), `concept_id` set |
| A3 | Click the voltage link | a **new** path is created + navigated to (fresh, even on a 2nd distinct click) |
| A4 | An incidental undefined term (a unit) | `popup_only` gloss; no path, no navigation |
| A5 | A term taught in an earlier topic (same surface form) | `review_earlier_topic` → that topic_id |
| A6 | `text` not present verbatim in the finalized card | link dropped |
| A7 | Flag off (`AZALEA_PREREQ_LINKS` unset) | today's behavior — `interactive_links: []`, no prereq classification change |
| A8 | Caps: a card with 5 candidate links | ≤ 3 emitted, by the §2.5a priority |
| A9 | **Broad beginner goal** ("Learn basic DC circuits from scratch") | voltage/current/resistance stay **teaching topics** (`in_path_foundation`, §3.1 rule 2), NOT prereq links |
| A10 | **Alias resolution**: earlier topic "Voltage"; later card says "potential difference" | `review_earlier_topic`, not popup/open_study_path |
| A11 | **Precedence collision**: a concept_id in BOTH `assumed_prerequisites` and taught earlier | **hard classification-contract failure** (Tier 2, §6.6): discard gated decomposition → use LEGACY decomposition → path renders with `interactive_links = []` |
| A12 | **Repeated term** in one card | a single deterministic anchor (first eligible, §5) |
| A13 | **Overlapping terms** ("field" and "electric field") | only the longest valid phrase linked |
| A14 | **Duplicate click** (same `request_id`) | exactly one path created |
| A15 | `assumed_prerequisite` with no valid `target_goal` (its topic already dropped) | **Tier-2 classification-contract failure** (§6.3a): discard gated decomposition → legacy decomposition chosen before generation → no display-text fallback |
| A16 | Path created from a prereq link | stores `origin_path_id`, `origin_topic_id`, `origin_concept_id`, `creation_source`, `prerequisite_lineage_concept_ids` |
| A17 | Decomposition emits > N prerequisites | explicit scope warning + prioritization, not a silent truncated list |
| **A18** | **Unresolved identity**: card term matches no known concept_id | no `open_study_path`/`review_earlier_topic`; `popup_only` only if eligible (§2.3) |
| **A19** | **Ambiguous identity**: "field" matches >1 concept_id | no deterministic action; dropped or `popup_only`-if-eligible; no arbitrary concept_id assigned (§2.3) |
| **A20** | **Downstream complexity**: undefined term needs a full lesson, absent from `assumed_prerequisites` | NOT promoted to `open_study_path`; dropped + decomposition-omission telemetry (§2.1) |
| **A21** | **Cap priority**: card has 2 prereq + 2 earlier-topic + 2 incidental candidates | exactly 3, chosen by the §2.5a order |
| **A22** | **Repeated prerequisite across topics** | intro card always provides an interactive gloss (normally `open_study_path`, `popup_only` when ancestor-suppressed §4.1); later cards link only where locally necessary, ≤1/topic (§2.6) |
| **A23** | **Exact-ancestor cycle**: prereq path would link a concept in its own ancestry | `open_study_path` suppressed, popup gloss retained, telemetry emitted (§4.1) |
| **A24** | **Safe enrichment fallback**: link validation fails but lesson cards are valid | path renders without links, generation does not fail (§6.6) |
| **A25** | **Server-computed ancestry**: client sends malformed/forged ancestry | backend ignores it, computes lineage from persisted origin data (§4.1) |
| **A26** | **Deterministic discovery**: card contains an exact alias of an assumed prerequisite, but the LLM proposes no link | `open_study_path` still emitted by the deterministic scan (§2.2) — actions don't depend on model discovery |
| **A27** | **Classification-contract failure** (distinct from A24): gated decomposition emits malformed/contradictory foundations | discard gated decomposition → use LEGACY decomposition (full teaching topics) → `interactive_links = []` (§6.6 Tier 2) |
| **A28** | **Token-boundary scan**: alias "ring", card contains "spring"; separately a registered symbol | no match for "ring" inside "spring"; registered symbols match only under their policy (§2.2) |
| **A29** | **Mention without competency request**: "How does Ohm's law relate voltage and current?" | voltage/current classified per §3.1 rule 1 (contextual mention ≠ objective) — may remain `assumed_prerequisite` |
| **A30** | **Fallback precedes generation**: gated decomposition fails structural validation | legacy decomposition chosen BEFORE lesson generation; no lessons generated from the invalid gated topic list (§6.0) |
| **A31** | **Over-limit full-set preservation**: 8 classified, N=6 | all 8 remain in `assumed_prerequisites`; 6 displayed; warning `count=8, threshold=6`; none reclassified/deleted (§2.7) |
| **A32** | **Ordinary earlier-topic identity**: a core concept taught earlier, NOT an `in_path_foundation`, emits a `TopicConceptIdentity` | later exact alias match → `review_earlier_topic` (works beyond foundations, §1.1b) |
| **A33** | **Markdown/plain-text projection**: card contains `**Potential difference** is…` | scan resolves the learner-visible phrase; anchor `text` = "Potential difference"; validator + frontend agree on the same projection (§2.2) |
| **A34** | **Undisplayed prerequisite**: 8 prereqs, N=6; the 7th appears in a later card | no `open_study_path`; `popup_only` or drop; telemetry emitted (§2.7 v1 policy) |
| **A35** | **Scope-rule telemetry**: classification via the beginner minimum-sequence rule | `scope_rule = beginner_minimum_sequence`; `scope_rationale` non-empty (§3.1) |
| **A36** | **Future-topic identity**: a concept's owning topic comes AFTER the current card | no `review_earlier_topic` (only `topic_index < current` is reviewable, §2/§1.1b) |
| **A37** | **Duplicate concept ownership**: two teaching topics claim the same `concept_id` | **Tier-2 classification-contract failure** (§6.3a uniqueness) → legacy decomposition |
| **A38** | **Glossary/navigation collision**: a phrase matches both an incidental glossary identity and an earlier-topic identity | `review_earlier_topic` wins; glossary does not downgrade to `popup_only`; duplicate-identity telemetry (§2.3) |
| **A39** | **Concurrent idempotent requests**: two requests, same `request_id` | one path row, one generation workflow; both callers get the same path (§4) |
| **A40** | **Failed idempotent retry**: a path exists for the `request_id` but generation failed | retry resolves to the SAME path (its `failed` status/regeneration), never a second path (§4) |
| **A41** | **Non-owning synthesis topic**: a comparison/review topic revisits several concepts, introduces none | emits NO new `TopicConceptIdentity`; existing owners stay unique; `review_earlier_topic` still resolves to those canonical owners (§1.1b) |

## 8. Named fixtures
`prereq_ohms_law` · `prereq_in_path_foundation` (A9 broad goal) · `prereq_gloss_only` · `prereq_review_earlier`
(alias, A10) · `prereq_click_creates_path` · `prereq_duplicate_click` (A14) · `prereq_overlapping_terms` (A13) ·
`prereq_repeated_term` (A12) · `prereq_validation_drops_absent_text` · `prereq_validation_flags_prereq_that_is_a_topic`
(A11) · `prereq_no_target_goal` (A15) · `prereq_over_limit` (A17) · `prereq_origin_metadata` (A16) ·
`prereq_unresolved_term` (A18) · `prereq_ambiguous_term` (A19) · `prereq_complex_undefined_term` (A20) ·
`prereq_cap_priority` (A21) · `prereq_repeat_across_topics` (A22) · `prereq_ancestor_cycle` (A23) ·
`prereq_enrichment_fallback` (A24) · `prereq_forged_ancestry` (A25) · `prereq_deterministic_discovery` (A26) ·
`prereq_classification_fallback` (A27) · `prereq_token_boundary_scan` (A28) · `prereq_mention_not_objective` (A29) ·
`prereq_fallback_before_generation` (A30) · `prereq_over_limit_full_set` (A31) · `prereq_ordinary_earlier_topic`
(A32) · `prereq_markdown_projection` (A33) · `prereq_undisplayed_no_open_study_path` (A34) · `prereq_scope_rule_telemetry`
(A35) · `prereq_future_topic_not_reviewable` (A36) · `prereq_duplicate_concept_ownership` (A37) ·
`prereq_glossary_nav_collision` (A38) · `prereq_concurrent_idempotent_request` (A39) · `prereq_failed_idempotent_retry`
(A40) · `prereq_non_owning_synthesis_topic` (A41).

## 9. Must-not (guardrails)
- **A concept is never both** `in_path_foundation` and `assumed_prerequisite` (disjoint by `concept_id`, §1.1a); an
  `assumed_prerequisite` never becomes a teaching topic; an `in_path_foundation` never appears in
  `assumed_prerequisites`.
- **Decomposition is the source of truth** for prereq-vs-concept AND scope membership AND identity AND
  `target_goal`; the lesson generator may not promote/demote/re-scope, invent a target goal, or resolve a new
  identity (§2.1/§2.3).
- **`popup_only` is the only LLM-discretionary action**; the rest follow the identity rule (§2); complexity never
  promotes a term to a prerequisite (§2.1).
- **No prerequisite path is generated until a completed, intentional click** — links carry only
  text/explanation/why/target/concept_id.
- **No semantic dedup/caching in v1** (only operational `request_id` idempotency, §4); caching is §11.
- **Classification uses identity, not text** (§2); anchoring uses verbatim text (§5); aliases are resolution-only
  (§2.4) — all three are separate.
- **Lineage is server-computed** (§4.1); client-supplied ancestry is ignored.
- **A hard validator failure never fails the overall study-path request** (§6.6): a **link** failure (Tier 1) falls
  back to the gated path with `interactive_links = []`; a **classification-contract** failure (Tier 2) falls back
  to the LEGACY decomposition (full topic list) — never a truncated gated topic list.
- **Flag-gated and additive:** with `AZALEA_PREREQ_LINKS` off, output is **structurally and behaviorally
  identical** to today (byte-identity only claimed where deterministic serialization fixtures exist, §11).

## 10. Schema revision (the minimal, mandated additions)
```text
InteractiveLink {
  text:                str
  explanation:         str
  why_it_matters_here: str | null
  action:              popup_only | open_study_path | review_earlier_topic | ask_question
  target:              str | null
  concept_id:          str | null     # NEW (M1)
}
# open_study_path:      target = scoped prerequisite goal ; concept_id = AssumedPrerequisite.concept_id  (both required)
# review_earlier_topic: target = topic_id                ; concept_id = earlier concept_id    (both required)
# popup_only:           target = null                    ; concept_id = resolved id or null
# ask_question:         target = null                    ; concept_id = optional
```
Click payload adds `target_concept_id` (§4); the created path row adds the §1.4 origin fields incl.
`origin_concept_id`, server-computed `prerequisite_lineage_concept_ids`, and `creation_request_id` with
`UNIQUE(user_id, creation_request_id)` for operational idempotency (§4).

## 11. Rollout
- **Phase 1 — data only (dark).** Decomposition classification via §3.1 (+ `scope_rationale`) + identity emission
  (§1.1a) + prereq-fold + typed `AssumedPrerequisite` + `target_goal` (§6.1) + lean generator emits links with
  `concept_id` + layered prereq card (§6.2) + both validators incl. fallback scope (§6.3a/§6.3b/§6.6), behind
  `AZALEA_PREREQ_LINKS`. **The flag gates the decomposition/topic-list changes too** — with it off, the topic list,
  prereq card, links, and validation are all unchanged. Both failure tiers (§6.6) are live in the dark phase (Tier
  2 = legacy-decomposition fallback). Acceptance: A1–A2, A4–A13, A15, A17–A22, A24, A26–A38, A41.
- **Phase 2 — wire the click.** Frontend routing (§6.4) + endpoint entry + origin metadata + server-computed
  ancestry + exact-ancestor suppression + `request_id` idempotency via `UNIQUE(user_id, creation_request_id)`
  (§6.5) → A3, A14, A16, A23, A25, A39–A40. Flip the flag after a live check.
- **Later (deferred):** semantic dedup/caching of prerequisite paths; cycle policy beyond exact-ancestor
  suppression; `ask_question` enrichments; the "return to where you were" breadcrumb (fields already present, §1.4).

### 11.1 PR split (the vertical slice, three PRs)
- **PR1 — data contracts + Tier-2 structural validation.** Union types (§1.1a/§1.2), `TopicConceptIdentity`
  (§1.1b), `scope_rule` (§3.1), uniqueness + `target_goal` + owner-resolvability + `fallback_reason`
  (§6.3a), legacy fallback (§6.6/§6.6a). Tests: A1, A9, A11, A15, A27, A29, A30, A35–A37, A41.
- **PR2 — deterministic scanning + enrichment.** Plain-text projection + boundary matching + alias normalization
  (§2.2), earlier-topic filtering (§2), candidate priority (§2.5a), `InteractiveLink.concept_id` (§1.3), Tier-1
  validation (§6.3b). Tests: A4–A8, A10, A12–A13, A18–A22, A24, A26, A28, A32–A34, A38.
- **PR3 — click path + provenance.** Frontend routing (§6.4), origin fields + lineage (§1.4/§4.1), cycle
  suppression, idempotent endpoint + `generation_status` worker-claim (§4/§6.5). Tests: A3, A14, A16, A23, A25,
  A39–A40.

## 12. Open questions (deferred)
- The exact `build_prerequisite_goal` template per domain (§3) — start with one template + domain/context slots;
  refine from shadow data.
- Whether an over-limit path should hard-fail decomposition or ship with the §2.7 warning (v1: ship with warning).
- The scope-warning threshold N (§2.7, default 6) — tune from shadow data.
- Cycle policy beyond exact-ancestor suppression (§4.1) — heuristic near-cycles left for later.
- A global/course-level concept registry for the deterministic scanner (§2) — v1 uses only this path's
  decomposition-emitted identities; a shared registry is deferred.
- Live dual-run retirement (§6.6a) — when reliability lets the legacy decomposition become on-demand-on-failure or
  be dropped, so fallback isn't permanent 2× cost.

(Resolved in v6: the non-displayed-prereq policy is now decided — §2.7 v1 policy: `popup_only`/drop, never
`open_study_path`.)

## 13. Implementation cautions (build-time, non-behavioral — no design change)
These do not change the contract; they are the failure modes to watch while building the §11.1 PRs:
1. **Keep PR1 narrowly structural** — no lesson-generation or frontend concerns in the classification types /
   fallback wiring.
2. **Implement the plain-text projection (§2.2) ONCE and share it** — scanner, validator, and frontend must not
   build separate approximations.
3. **`fallback_reason` stays machine-readable end-to-end** — never a structured enum in one layer, generic text in
   the next.
4. **Legacy and gated decompositions are immutable values** — never mutate the legacy baseline while building the
   gated result (Tier-2 fallback depends on a clean baseline).
5. **Atomic worker claim** — the UNIQUE `creation_request_id` stops duplicate rows; only the `pending|failed →
   generating` status transition stops duplicate generation workflows (§4).
6. **Non-owning topics stay truly non-owning** — never inject a placeholder `concept_id` just to satisfy
   serialization (§1.1b).
7. **Verify flag-OFF behavior with snapshots** — the flag gates decomposition, not just link rendering, so an
   off-state snapshot must be byte-identical to today where §11 claims it.
