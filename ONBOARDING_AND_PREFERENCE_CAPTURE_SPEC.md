# Onboarding & Preference Capture Spec — Phase 1

> **Purpose.** The wizard that lets a learner **confirm the inferred domain** and set the few preferences that
> change generation (depth, language), plus how those preferences persist and resolve. **Onboarding is NOT a
> dependency for content routing** — the domain gate (`DOMAIN_ROUTING_AND_TOPIC_GATE_SPEC.md`) ships in Phase 0
> on the *inferred* domain; this spec just lets the user override it and layer preferences.
>
> Split from `CONTENT_ADAPTATION_OVERVIEW.md`. Siblings: routing/gate (Phase 0),
> `DOMAIN_CARD_NARRATION_AND_RENDERING_SPEC.md` (Phase 2).

---

## 1. Infer vs. ask

*Infer everything we can; ask only what we cannot infer confidently AND will consume.* Inference (routing spec
§3) pre-fills the wizard so most steps are a one-tap confirm.

A field is **shown** only when **all** of the following are true:
1. it **applies** to the current domain/path;
2. it has a **live downstream consumer**;
3. it is **not already known** with sufficient confidence — *unless* it is shown as a lightweight confirmation.

**A field with no live consumer must not appear in the wizard.**

**`depth_level` ⊥ `knowledge_level`** — orthogonal axes: depth = *how far the content goes*; knowledge = *where
the learner starts*. Label them distinctly; wire to different knobs (depth → the Phase-1A structural knobs of
`DEPTH_PROFILE_V1`, §4.1; knowledge → Phase-2 assume/gloss threshold).

---

## 2. The question graph

Questions are **data, not branches** — each an `applies_when` predicate over `PromptSignals` + answers-so-far,
with a required `consumer` and an inferred `prefill`. Shown only if it **applies** and has a **live consumer**; a
high-confidence inferred answer may be **skipped or shown as a lightweight confirmation** per the
minimum-question policy (Q8).

| Step | id | Question | `applies_when` | Options |
|---|---|---|---|---|
| 1 Content Type | `domain` | "What kind of topic is this?" | always | coding · math · science · concept (pre-selected) |
| 2 Preferences | `depth` | "How deep should we go?" | always | intuition · working (default) · deep |
| 2 Preferences | `language` | "Which language for examples?" | `domain == coding` AND supported | **only supported languages** (see §5) |
| — | `knowledge_level` | **Deferred to Phase 2 — not shown** (no live consumer yet; showing it would violate §1) | — | *(persistence field reserved; not asked)* |
| — | `goal` | **Deferred to Phase 3 — not shown** | — | placeholder |

So the **Phase-1 wizard has two live steps: Content Type · Preferences.** `Experience` and `Goals` are deferred
(their consumers aren't live), consistent with §1's "a field with no live consumer must not appear."

- **Q8 — minimum-question policy (resolved).** Don't force a wizard every time:
  ```
  if domain confidence high AND saved preferences exist:
      show a compact confirm ("Generating as Math · Working depth · Change")
  else:
      show the wizard
  ```
  A first-time user sees **at least one lightweight confirmation surface**: at normal confidence, domain +
  depth; at **very-high-confidence** domain classification the two may combine into **one compact confirm** (so
  "Teach me DFS in Python" isn't two screens).
- **Q9 — defaults (resolved).** Every question has a **preselected default** so Next works with zero
  interaction — but label the source: **"We detected…"** (inferred) vs **"Your usual preference"** (saved) vs a
  quiet fallback (don't imply confidence).
- **Q11 — skippability (resolved).** A returning/power user can skip entirely, using stored/default prefs.

- **Q7 — back-navigation (resolved).** Changing an earlier answer **recomputes the applicability of all later
  questions.** Answers to questions that no longer apply are **retained as dormant saved preferences** but are
  **excluded from the current path override and generation request.** Example: coding → picks Java → goes back →
  changes domain to math ⇒ language disappears from the flow; the saved default `Java` stays for future coding
  paths; the current path does **not** carry `language=Java`. (Prevents stale language leaking into non-coding
  paths.)
- **Q10 — "Other" (resolved).** No free-text "Other" in v1. **Domain:** no "Other" — unsupported/ambiguous
  prompts route to `concept`. **Language:** no "Other"; show only adapter-supported languages, and if no
  supported non-Python option exists, **don't show the language question at all** (matches Option B, §5).
- **Domain-change language handling (resolved).**
  - **coding → math/science/concept:** language becomes **inactive**, excluded from the path request.
  - **math/science/concept → coding:** run a **new `PlanPreview`**; show language only if the compatibility
    intersection contains a selectable non-default option.
  - **coding → coding** with a scope change that alters adapter compatibility: **invalidate** the prior preview
    and recompute the supported-language intersection. (Closes the bug where an old language selection survives a
    coding-scope change.)

### 2.1 Wizard page (UX)
Sits between the home-page prompt and the study-path view: centered card, one question per screen, a top
**progress stepper** — **Phase 1 shows `Content Type · Preferences`** (Experience/Goals appear only when their
consumers go live) — a **"You selected" recap rail**, Exit
always available, **"change later in settings"** under the primary button. Pixel design is a UI task, not spec.

---

## 3. Preferences schema & persistence (Q12–Q15 resolved)

User-level defaults + per-path overrides:

```
UserPreference { default_depth_level, default_language, default_knowledge_level, schema_version }
StudyPathPreference {
  study_path_id, domain, subdomain_family, subdomain_label,
  depth_level, language, knowledge_level,
  provenance JSON, preference_schema_version
}
```

- **Precedence:** `path override > user default > inferred value > platform default`.
- **Provenance (richer than inferred/user):** `inferred · user_confirmed · user_selected · saved_default ·
  system_default`. "User saw Python preselected and clicked Next" (`user_confirmed`) ≠ "system guessed Python,
  user never saw it" (`inferred`). A `user_confirmed`/`user_selected` domain overrides per-topic inference; an
  `inferred` one only seeds it.
- **Versioning:** `schema_version` on both, so preferences can evolve.
- **Q25 — edit-later:** changing `language`/`depth` in settings applies to **new** paths and offers an **opt-in
  re-gen** of an existing path; it never silently regenerates.
- **Q27 — migration:** existing users/paths default to `{domain: inferred-or-concept, depth: working, language:
  python}`; never re-ask retroactively.

**Active vs. stored preferences.** A preference may be **stored without being active** for the current path — so
the UI must never present a stored value as if it shaped output when it didn't. `knowledge_level` is stored in
Phase 1 but not consumed until Phase 2; `default_language=Java` may be stored at user level but inactive for a
path whose adapters only support Python. Capture this (exact persistence shape is a v1 detail, but the behavior
is required). Four unambiguous states per field: **stored** (a preference exists) · **requested** (chosen or
inherited for this path) · **active/applied** (it actually changed this generation) · **inactive** (retained but
did not affect output). `language` is tracked by its own state model (below) — on a coding path Python is
*applied* even when the requested language wasn't honored, which is **not** the same as inactive:
```
StudyPathPreference {
  ...
  inactive_fields: { knowledge_level: { reason: "phase_2_consumer_not_live" } },
  requested_language: "java", applied_language: "python", language_status: "fallback_applied"
}
```
`active_fields` is **derived, never persisted independently** (avoids drift where it says language is inactive
while `applied_language = python`): `domain` always active · `depth_level` active when `effective_depth` is
resolved · language active **iff** `applied_language != null`.

**Language state — distinguish *applied* from *honored*.** "Inactive" must mean *no language affected output*,
**not** "the requested language wasn't honored." For a Python-only coding path Python **is** applied (it shapes
the code); it just isn't the requested language. Four separate fields:
```
requested_language:        java | python | null
applied_language:          java | python | cplusplus | null
language_status:           honored | default_applied | fallback_applied | inactive_non_coding
language_selector_status:  shown | hidden_python_only | hidden_preflight_unavailable | hidden_no_compatible_intersection
```
| Situation | requested | applied | status |
|---|---|---|---|
| math / science / concept path | (default may exist) | `null` | `inactive_non_coding` |
| coding path, Python-only | none | python | `default_applied` |
| coding path, Java requested but unavailable | java | python | `fallback_applied` |
| coding path, Java selected + supported | java | java | `honored` |

Only `inactive_non_coding` means language had **no** effect; the other statuses all *applied* a language. The UI
can then honestly say "Examples are shown in Python for this path" without falsely recording no-effect.

**Python is also a real choice** (don't collapse an intentional Python preference into an automatic default):
- explicitly **selected or saved** Python that is applied → `honored`;
- Python applied because **no explicit request** was made and it is the only/default route → `default_applied`;
- Python applied after a **different requested language** couldn't be honored → `fallback_applied`.

**Migration — do not overload `StudyPath.language`.** The existing column is non-null and defaults to `"python"`
for **every** path, which contradicts the honest-language model. Persist the new fields as **distinct** columns
(`requested_language · applied_language · language_status · language_selector_status`); migrate the old
`StudyPath.language` → `requested_language` **for coding paths only**, inactive elsewhere, and **never** display
"shown in Python" on a math/science/concept path.

**Compact-confirm provenance.** When the compact confirmation (Q8) is shown and the learner proceeds **without
edits**: visible **inferred** values become `user_confirmed`; visible **saved** values stay `saved_default`
unless changed; values **not shown** stay `inferred`/`system_default`. A user action on a *visible* confirmation
counts as confirmation; an invisible default does not. This lets later logic distinguish "accepted Math after
seeing it" from "inferred Math, never seen" — which matters for override precedence and classifier-quality
telemetry.

### 3.1 Path lifecycle (provisional → confirmed → generated)
```
1. user submits prompt
2. backend classifies → persists provisional StudyPath.domain + classification_status (Phase 0)
3. backend returns a lightweight PlanPreview (§5)
4. onboarding shows confirmation / preferences
5. user confirms or overrides
6. backend persists path override + provenance
7. topic generation runs from the EFFECTIVE domain + effective preferences
8. already-generated content is NEVER silently replaced
```
Domain changed **before** generation → use the new domain immediately. Domain changed **after** topics/cards
exist → keep the current path stable and offer an **explicit regenerate** (never silent).

**DECIDED (D1) — mutable user defaults + immutable per-generation snapshot.** `UserPreference` = mutable
defaults; **each generation writes an immutable `StudyPathGeneration` snapshot**; `StudyPath` points at the
active generation revision. (Answers "why did this path generate Java / working depth / formula_breakdown-but-no-
edge-case?" and "what changed on regenerate?" — a fully-mutable record loses that history.) v1 shape (no heavy
revision system needed):
```
StudyPathGeneration {
  id · study_path_id · generation_number · domain · classification_status
  selected_preferences_json · effective_preferences_json · preference_provenance_json
  contract_versions_json · created_at
}
```
- changing user defaults affects only **future** generations;
- changing a live path creates an **explicit regeneration revision** (never silent);
- old generated content stays explainable.

---

## 4. Consumer map (a question ships only when its row is live)

| Field | Plugs into | Phase |
|---|---|---|
| `domain` | the topic-type gate (routing spec) | already live in Phase 0 |
| `depth_level` | `DEPTH_PROFILE_V1`: optional cards · edge-case · practice count · adapter instance count | Phase 1 |
| `depth_level` | narration/rendering depth (intuition length, justification) — narration spec | Phase 2 |
| `language` | supported-adapter selection + code rendering (§5) | Phase 1, **gated** |
| `knowledge_level` | *(phase 2)* assume/gloss threshold | Phase 2 |
| `goal` | *(phase 3)* scope contract | Phase 3 |

### 4.1 Depth rollout (two stages — keep Phase 1 honest)

Depth's *rhetorical/rendering* behavior is owned by the Phase-2 narration spec, so Phase 1 ships only the
**structural** half:

- **Phase 1A — structural depth (`DEPTH_PROFILE_V1`):** optional-card inclusion · edge-case inclusion · number
  of practice prompts · number of verified adapter instances requested. *No dependency on renderer work.*
- **Phase 2 — rhetorical/rendering depth:** longer intuition framing · expanded derivation justification ·
  deeper within-card narration · domain-specific presentation.

The §1 `depth ⊥ knowledge` note refers to Phase-1A knobs for `depth`.

### 4.2 Effective-depth validation (depth must have a real effect)

Not every topic type/adapter supports every `deep` expansion (an adapter may have one deterministic instance; a
concept may have no meaningful edge case; a blueprint may have no optional cards). Each topic type/adapter
declares its Phase-1A capabilities: optional cards available · edge-case support · max verified example
instances · max practice prompts. After planning, compute `effective_depth` from the selected depth + those
capabilities:
- honorable → generate normally;
- one expansion unavailable → keep the selected depth where possible, **log the omitted capability**;
- cannot materially differ from `working` → **disclose the effective plan** rather than silently claiming `deep`;
- **never fabricate** an extra example / edge case / practice item just to hit a depth count.

**Path-level effective depth.** Compute `effective_depth` across the **completed path**, not only per topic. For
`deep`, the path is materially deeper only when ≥1 deep-only expansion is present **and** depth is added across
the applicable topics — not one isolated expansion in a ten-topic path. If some topics can't expand, disclose
"**Deep mode applied where supported.**" If no meaningful path-level expansion is available, set
`effective_depth = working_limited` and display that limitation before/alongside generation. (No rigid numeric
threshold yet, but a token expansion must not satisfy the `deep` contract.)

`effective_depth_reason` enum: `honored · optional_cards_unavailable · edge_case_unavailable ·
adapter_instance_limit · practice_capacity_limit · no_material_expansion_available`.

---

## 5. Language — Option B (Q16 resolved)

**Do not claim "examples in your language" until it's honorable.** Trace adapters ship a Python
`canonical_solution`. Three options considered; **v1 = Option B: language is restricted to supported adapters.**

- Surface **only** languages whose adapter/rendering path is actually supported for the selected path (e.g.
  Python for all coding adapters; Java/C++ for selected algorithm adapters).
- **Python-fallback scope.** For **coding** paths: if the supported-language intersection is `{Python}`, Python
  is applied as the only available code-example language (`default_applied`); if the intersection is **empty** or
  compatibility is unavailable, Python is applied only as a **disclosed fallback** (`fallback_applied`) under the
  final-validation policy. For **non-coding** paths (math/science/concept): `inactive_non_coding` — no control,
  no "shown in Python" message on a completing-the-square path.
- **Do not add the language wizard question until this is implemented.** (Option A — language-neutral trace +
  render — is the eventual goal; Option C — prose-only language — is rejected as deceptive.)

**Compatibility invariant (hard).** A language selector may be shown **only when every required code-bearing
topic** in the generated path has a compatible adapter/rendering route for that language. (A path with DFS-in-Java
but a Python-only recursion card must not promise Java and silently fall back per-card.)

**Language compatibility preflight.** The selector can't trust the prompt alone — required code-bearing topics
aren't known until planning. Before showing it, run a **lightweight planning pass** that determines: the proposed
topic types · the required code-bearing topics · candidate adapters/renderers · the **intersection** of languages
all of them support. The selector displays **only that intersection.** If the pass is unavailable, low-confidence,
or would require full generation: **don't show the selector** — apply Python and disclose it as the active example
language. (This is what makes Option B implementable rather than aspirational; it must not trigger a full,
duplicate generation just to populate the selector.)

**Preflight plan reuse.** The preflight returns a **versioned `PlanPreview`** artifact — proposed topic types ·
code-bearing topic IDs · candidate adapter/rendering routes · supported-language intersection · planner
version / input hash. **Generation must reuse this artifact when its inputs are unchanged**; it may re-plan only
when the learner changes domain, depth, or another planning-relevant preference. (Prevents two independent
planners diverging and inflating the mismatch rate.)

**Language binding model.** `PlanPreview` is **language-neutral** — candidate topics, required code-bearing
topics, and per-topic supported-language routes. Selecting Java does **not** discard the preview; it creates a
`LanguageBoundPlanPreview` that picks the Java-compatible route for **every** required code-bearing topic. A
**new base preview** is required only if language selection would change topic composition, topic type, scope, or
adapter eligibility. Flow:
`prompt + domain + depth → language-neutral PlanPreview → intersection → select Java → Java-bound plan → final
validation → generation`.

**`PlanPreview` invalidation.** The **base** (language-neutral) preview is invalid when any input that can change
topic composition, adapter selection, or code-bearing status changes: the raw prompt / uploaded-source set ·
selected domain · selected depth · scope-altering edits · planner / routing / adapter-catalog **version**. A
**language selection does not invalidate** the base preview (it binds, per the model above) unless it would alter
topic composition/type/scope/adapter eligibility. Display-only UI state never invalidates. A preview is reusable
**only** when its stored **input hash + relevant version ids** match the current request.

**Final language compatibility validation.** The preflight is based on a *proposed* plan; the real plan may add a
Python-only code-bearing topic the preflight didn't anticipate. After the actual topic/adapter plan is produced
and **before lesson generation**, recompute the intersection across every *actual* required code-bearing topic:
- still compatible → continue;
- no longer compatible → **do not fall back per card.** Regenerate the plan only if a compatible plan can be
  produced **deterministically**; otherwise apply **Python uniformly** for the whole coding path, set
  `applied_language = python`, `language_status = fallback_applied`, disclose the applied language, and emit
  **`language_plan_mismatch`** telemetry. (`inactive_non_coding` is reserved for non-coding paths — a coding
  fallback is *applied*, not inactive.)

**Rule: no per-card mixed-language fallback** — a path never starts in Java and quietly switches to Python.

**Two Python cases — keep distinct in telemetry + language state:**
1. **Python-only path** — no selector shown because the intersection is `{Python}`: `applied_language = python`,
   `language_status = default_applied`, `language_selector_status = hidden_python_only`.
2. **Disclosed fallback** — a stored/requested language was unavailable or final validation failed:
   `applied_language = python`, `language_status = fallback_applied`, with the fallback reason + telemetry event.

They may look similar to the learner but must differ in persisted state and telemetry.

---

## 6. Phase-1 entry criteria

**All resolved in this doc:** Q7 (§2), Q8/Q9/Q11 (§2), Q10 (§2), Q12–Q15 (§3), Q16 (§5), depth split (§4.1),
Q25/Q27 (§3). Nothing left "small."

## 7. Phase 1 — definition of done

- [ ] First-time users see domain confirmation + depth selection.
- [ ] Returning users with high-confidence domain + saved prefs see a compact confirmation, or may skip.
- [ ] Every shown question has a live consumer.
- [ ] Changing domain recomputes later question applicability (Q7); dormant answers don't enter the path override.
- [ ] User defaults + path overrides persist with provenance + schema version.
- [ ] Precedence resolves as `path > user > inferred > system`.
- [ ] `knowledge_level` is **not shown** until it has a live consumer (or its Phase-1 consumer is explicitly
  implemented + tested); the Phase-1 stepper is `Content Type · Preferences`.
- [ ] Language options are derived from a **preflight compatibility intersection** across every required
  code-bearing topic; if no reliable intersection exists, the selector is hidden and Python is disclosed as
  applied (no duplicate full generation to populate it).
- [ ] Unsupported language choices are never presented as selectable (§5 invariant).
- [ ] The applied language is visible when it differs from a saved/requested preference.
- [ ] Changing settings never silently regenerates an existing path.
- [ ] **Test:** a user who changes `coding → math` after picking Java produces a path preference with **no active
  language field** and **no language parameter** in the generation request.
- [ ] **Test:** a user who picks Java from a valid preflight **never** receives a mixed Java/Python path — final
  validation either keeps Java for **all** code-bearing cards or applies one disclosed fallback language uniformly.
- [ ] **Test:** selecting `deep` never silently produces a `working`-equivalent path — the plan contains ≥1
  declared deep-only expansion, or records/discloses the effective-depth limitation (§4.2).
- [ ] Generation **reuses the `PlanPreview`** from the language preflight when inputs are unchanged (no
  double-planning).
- [ ] **Test:** changing any `PlanPreview`-invalidating input creates a new preview; generation **rejects a stale
  preview** whose input hash or planner version doesn't match the current request.
- [ ] Telemetry logged (below).
- [ ] The **wizard is feature-flagged** and can be disabled **without affecting Phase-0 routing** (Phase 0 stays
  stable if onboarding has a rollout issue).

## 8. Telemetry (Q26)

Core: domain-override rate · depth distribution · wizard skip rate. Plus:
- **wizard abandonment by rendered step**, split first-time vs returning (stays valid when Experience/Goals ship).
- **language requested-vs-applied mismatch rate** (is Option B too restrictive/confusing?)
- **`language_plan_mismatch` rate** — preflight said compatible but final validation didn't (§5).
- **inferred → user-confirmed domain disagreement, bucketed by classifier confidence** (proves the
  high-confidence compact-confirm rule is safe).

**Non-goal:** onboarding does not gate content routing (Phase 0 already runs on the inferred domain).
