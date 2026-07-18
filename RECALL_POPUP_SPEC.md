# Recall Popups — small spec (v1)

Status: Draft v1 — agreed direction; v1 buildable now on existing infrastructure. Flag: `AZALEA_RECALL_POPUPS`
(new; the old `AZALEA_TERM_GLOSSES` lexical-gloss system stays **permanently dead** and is not revived by this).

## 1. Purpose

One sentence: **when a lesson uses a concept the learner is assumed to already have (external prerequisite) or
was taught earlier in the path, an anchored popover gives just enough recall to continue without leaving the
lesson.** A popup never teaches, never defines new material, never repairs missing prerequisite instruction.

Each popup answers at most three questions:
1. *What should I remember?* (`recall`)
2. *Why is it relevant here?* (`why_here` — v1.5, optional)
3. *Where can I review it?* (`action`)

## 2. Candidate selection — deterministic, never the LLM

Candidates are EXACTLY the links the deterministic scanner already emits (no new discovery pass, no
"find difficult words" scanning — that is the failure mode that got glosses disabled):

- `review_earlier_topic` links → concept taught by an earlier topic in this path.
- `open_study_path` prereq links → external assumed prerequisite.

A link is popup-eligible iff it has a **structural anchor** (`{field, index}`; the existing contract — exact
main-bullet match, word-boundary, never fuzzy). No anchor → no popup (frontend falls back to plain link).
The LLM never decides which phrases become popups; at most it phrases `why_here` (v1.5).

## 3. Content contract

```
RecallPopup (stored ON the interactive link at generation time; clicks are instant, no runtime calls)
  concept_id                       # existing link field
  recall:   str                    # ONE plain sentence: what the concept is
  why_here: str | ""               # v1.5, ONE sentence: its role on this card; OMITTED when uncertain
  action:   {label, kind: review_earlier_topic | open_study_path, target}   # the link's existing target
```

`recall` sources (deterministic, in order):
1. Prereq: the intro's `assumed_prerequisite_glosses[name]` (+ `required_knowledge` as a second line if short).
2. Earlier topic: harvest the owner topic's definition-card bullet for the concept (exact/alias match); if no
   clean harvest → fall back to the link's existing `explanation` ("You saw this earlier in …") — never invent.

`why_here` (v1.5 only): one sentence generated AT LESSON-GENERATION TIME from the anchored card's own text +
the concept, batched per topic, stored on the link. If generation is unsure → empty. Never generated at click.

## 4. Display limits (precision-first)

- ≤ 1 recall popup per card; ≤ 3 per topic; ≤ 1 per concept per topic (first anchored use).
- Never on: the current topic's principal concept; a concept defined on the same card; the intro's prereq card
  name bullets (those keep their existing open-path behavior); anything without a structural anchor.
- Priority when over budget: external prereq needed for this step > earlier-topic concept > notation (§6).

## 5. Interaction

Anchored **popover**, not a modal: opens beside the phrase, does not obscure the card, closes on outside
click/Escape, keyboard accessible. Contains recall (+ why_here when present) and one "Review →" action.
It never auto-launches Q&A. The full dialog remains only for confirming creation of a new prerequisite path.

## 6. Notation popups (parallel v1 track)

Symbol/abbreviation decoding on formula-family cards, generated from **structured spec metadata that already
exists** (`canonical_notes` on formula/rowreduce specs — e.g. "\(\sigma\): the distribution's standard
deviation"), never from prose scanning. Anchored to the symbol's first reuse AFTER the formula card (the
formula card itself already shows the legend). Same popover, shape: `{symbol, meaning, role_here?}`.

## 7. Telemetry (day one)

Log per popup: `concept_id, topic_id, opened, review_clicked`. This measures whether a bridge was needed —
and later validates the scope plan's `uses`/`reviews` designations (never-opened ⇒ maybe no bridge needed;
constantly-opened ⇒ maybe needs real re-teaching, not a popup).

## 8. Staging

- **v1 (now):** popover UI on existing `review_earlier_topic` + `open_study_path` links; deterministic
  `recall` (gloss/harvest); caps; telemetry; notation popups from spec notes. No new LLM calls.
- **v1.5:** `why_here`, generation-time, batched, stored; omitted when uncertain.
- **v2 (scope plan Phase 1/2):** candidates upgraded to `PlannedTopic.uses`/`reviews` + `teaching_owners`/
  `definition_owners` (canonical recall text from the definition owner); anchors from content claims;
  "never popup the principal concept" enforced from `teaches` instead of heuristics.

## 9. Non-goals / never

- No undefined-word or "technical-sounding term" scanning (that system stays dead).
- No teaching new/central concepts via popup; no multi-paragraph popovers; no popup whose absence would break
  comprehension of the card (that content belongs in the lesson).
- No runtime LLM calls on click; no fuzzy string anchors.
