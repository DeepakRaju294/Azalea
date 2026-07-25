# Retrieval-Grounded Example Spec

> **Status:** Draft v0.1 — architecture proposal. Phase 0 (offline reproduction core) is IMPLEMENTED and
> merged (`app/services/examples/retrieval_verify.py`, `scripts/retrieval_repro_gonogo.py`,
> `test_retrieval_verify.py`). Everything else here is design, gated behind an offline go/no-go.
>
> **One-line thesis:** For a topic with no verifying adapter, *retrieve* an authoritative example or formula,
> *validate* it through a cheap→strong verification ladder, and *generate* a worked example — ONLY after the
> existing verified pipeline has genuinely missed, and never re-doing work a cache or a published answer
> already settles.
>
> **End-state target (the completeness goal):** by the end of this spec, **every topic that desires a worked
> example gets one** — adapter or not. The non-adapter architecture must be *sound* (it never certifies a
> wrong example) AND drive toward *complete* (the fraction of desired examples actually delivered → 100%).
> Abstaining to a guided card is a TRANSITIONAL safety state, tracked and driven to zero by the escalation
> ladder (§1.6), never the accepted destination.

---

## 0. Executive decision

1. **Delivery reuses the live path, not the parked one.** The worked example is produced and shipped through
   the existing `solve_worked_example` → legacy solver → `answer_anchor` path (Option 3), *grounded* with
   retrieved facts. We do NOT finish Grounded Runtime Binding's Milestone C (persistence / ownership /
   cutover) to ship a retrieved example. We DO reuse the one genuinely valuable already-built piece of that
   system: the Milestone A **dimensional/unit check** (`runtime_binding/units.py` + `compiler.py`) as a cheap
   verification tier. "Borrow the jewel, skip the machinery."
2. **Retrieval is a fallback, never the front door.** The routing cascade (§3) tries every already-verified
   producer first (adapter → gen_foundation → runtime-binding-if-ever-live). Retrieval runs ONLY on a genuine
   miss. This is both a correctness and a cost decision (§4).
3. **Accuracy comes from the verifier, not the source.** Retrieval improves *grounding*; a deterministic (or
   independent) *check* provides accuracy. Coverage of the strong guarantee therefore equals the set of
   topics whose output is checkable. Everything else degrades gracefully to a *sourced* guided explanation
   (attributable, not proven) or abstains.
4. **Fail-closed, shadow-first.** Every new tier ships OFF, then in observe/shadow (records what it would do,
   changes nothing), then live behind a flag, exactly as Grounded Runtime Binding rolled out.
5. **Go/no-go before Phase 1.** `scripts/retrieval_repro_gonogo.py` must show the live solver reproduces
   published answers at an acceptable rate (§14 gate G0) before any retrieval plumbing is built.
6. **Soundness AND completeness are BOTH end-state requirements (§1.5).** Correctness is never traded for
   coverage (no wrong example ships as verified) and coverage is never abandoned (no desired example is
   silently dropped). The tension is resolved by an *escalation* ladder (§1.6) that runs alongside the
   *validation* ladder: when a rung can't confirm, the system escalates to a stronger acquisition rung rather
   than giving up, and the residual uncovered set is a tracked quantity with a target of zero.

---

## 1. Why this exists

Today, a topic with no adapter gets one of two outcomes (verified live, in `solver.py`):

- **Concept-domain suppression** (`path_domain == "concept"`, no adapter): the worked example is *stripped*
  and not shipped (a fabricated example drifts off-topic). Whole domains ship with zero examples.
- **Determinate, no adapter**: the legacy LLM solver produces an example, gated by `answer_anchor`
  (arithmetic consistency + independent-eval oracle) — but the anchor catches arithmetic slips, NOT a
  *dimensionally-plausible wrong formula*, because the model supplied both the formula and the numbers.

The gap is a *verified* example for the large class of no-adapter **formula/computation** topics (EM, thermo,
finance, chemistry, …) without hand-authoring an adapter or a reviewed contract for each. Retrieval +
validation is the general acquisition path; the existing verifiers (dimensional check, answer anchor,
reproduction check) are what make it safe.

## 1.5 Soundness & completeness contract (the end-state the architecture must satisfy)

Two invariants, both mandatory, deliberately in tension and reconciled by §1.6:

- **Soundness (never wrong).** No path ever ships an example marked `verified`/`*_reproduced`/`*_corroborated`
  that a named verification tier did not confirm. A wrong-but-confident example is the one thing the system
  must never produce. This is inviolable — it is NOT relaxed to hit coverage.
- **Completeness (never silently absent).** For every topic whose blueprint DESIRES a worked example, the
  system must ultimately deliver an *actual example* — not a guided substitute. Define:
  - `desired(topic)` — the blueprint requests a worked_example card (§ `_blueprint_wants_worked_example`).
  - `delivered(topic)` — a worked example (of the appropriate KIND, §1.7) is shipped.
  - **Coverage = |delivered ∧ desired| / |desired|**, tracked continuously; **end-state target = 100%.**

**How both hold at once — the residual is closing, not accepted.** At any instant, some desired examples are
not yet verifiable by an automated tier. Those are NOT dropped and NOT shipped as false-verified. Instead they
are ESCALATED (§1.6). The only case that reaches a transitional guided card is a desired example that has
exhausted every escalation rung AND has not yet cleared human review — and that case is a *tracked residual*
(`coverage_gap`) that the review queue and catalog growth drive toward zero. Soundness is permanent;
completeness is monotonically approached and its shortfall is always visible, never silent.

**Provisional trust (the mechanism that lets completeness advance without breaking soundness).** A desired
example the ladders can produce but not yet strongly verify MAY ship as `provisional` — clearly trust-marked
(and, per §11, frontend-badged) and simultaneously enqueued for review. `provisional` is honest (it does NOT
claim to be verified), so soundness holds; it counts toward `delivered`, so completeness advances; and review
either promotes it to a verified cache entry (permanent coverage) or corrects it. Whether `provisional` is
enabled is a policy flag per rollout phase (off until Phase 2, §14).

## 1.6 Escalation ladder (completeness) — complements the validation ladder (correctness)

The validation ladder (§8) answers "is THIS example correct?" The escalation ladder answers "if we can't
confirm one yet, how do we still get a correct one?" Run top-down; each rung either DELIVERS a verified
example or ESCALATES to the next — nothing is silently dropped:

```
E0. PIPELINE / CACHE        adapter | gen_foundation | runtime-binding | cache hit    -> verified, DONE
E1. RETRIEVE + REPRODUCE    published (problem,answer) reproduced (V1)                 -> verified, DONE
E2. RETRIEVE + CORROBORATE  >=2 sources agree + dimensional (V2/V3)                    -> verified, DONE
E3. GROUNDED LLM-BIND       transcribed formula bound + independent check (V4/dimensional) -> verified if it confirms
E4. BROADEN RETRIEVAL       more whitelisted sources / alternate concept keys, retry E1-E3
E5. HUMAN-REVIEW-ONCE       enqueue; a one-time review certifies -> cached verified (permanent coverage)
E6. PROVISIONAL (transitional, flag-gated)  ship trust-marked + enqueued for E5        -> counts delivered, honestly
── only if provisional is OFF and E0-E5 all pending ──
E7. GUIDED (transitional floor)  sourced guided card; logged as coverage_gap, feeds the review queue
```

Every escalation is recorded (§13). The `coverage_gap` counter = topics that reached E7. The goal of the whole
system is to shrink E7→E6→E5 traffic over time as the cache/catalog fills, until E0–E2 cover the steady state.

## 1.7 What "an example" means (so completeness is well-defined across topic kinds)

Completeness does not force a *numeric* example onto a topic that has no number. "Deliver an example" means the
KIND appropriate to the topic, each with its own verification:

- **Computational** (formula/algorithm): a worked example with a checked final answer (V1/V2/V4). Primary case.
- **Qualitative/conceptual**: a *sourced illustrative example* — a concrete scenario drawn from and
  span-grounded (V3) to a whitelisted source (e.g., a canonical instance of the concept). This is a real
  example (grounded, attributable), NOT the guided fallback, and it makes conceptual topics count toward
  coverage instead of being permanently exempt.
- The determinacy gate (§3 step 4) therefore ROUTES to the right kind; it does not exempt a topic from having
  an example.

## 2. Relationship to existing architecture (reuse, don't rebuild)

| Existing component | Role here | Reused as-is? |
|---|---|---|
| `solve_worked_example` routing (`solver.py`) | the cascade retrieval slots INTO | extended, not replaced |
| `trace_pipeline` / adapters | fast path #1 (verified, skip retrieval) | as-is |
| `gen_foundation` (sandbox execution) | fast path #2 (verified, skip retrieval) | as-is |
| `runtime_binding` A substrate (`units.py`, `compiler.py`, `executor.py`) | dimensional-check verification tier | reused (import) |
| `runtime_binding` B/C (delivery, persistence, ownership) | **not used** | — |
| `answer_anchor` (`anchor_final_answer`, `math_eval_oracle`) | verification tier (independent endpoint) | as-is |
| `retrieval_verify` (Phase 0) | reproduction-check tier + fixtures | as-is |
| `guided_explanation.build_guided_explanation` | abstention output | as-is |
| `goal_plan_cache` pattern | template for the verified-contract cache | pattern, new store |
| `decision_trace.record_lesson_decision` | every routing/verification decision persisted | as-is |

**Guiding invariant (inherited):** this layer introduces NO new execution semantics. Arithmetic is executed by
the existing exact executor or done deterministically; the LLM narrates and transcribes but never grades its
own numeric work.

---

## 3. End-to-end routing cascade

`resolve_worked_example(topic)` — the decision order. **Each step that succeeds SHORT-CIRCUITS the rest**;
this ordering is the correctness and cost design (§4).

```
0. CACHE LOOKUP            concept already verified before?  -> reuse (skip everything)         [SAVE: max]
1. ADAPTER                 route_adapter(topic) hits?        -> verified trace, DONE            [SAVE: skip retrieval]
2. GEN_FOUNDATION          sandbox-executes the topic?       -> verified execution, DONE        [SAVE: skip retrieval]
3. RUNTIME_BINDING (live)  reviewed contract resolves?       -> verified binding, DONE          [if ever cut over]
   ── everything below is the NEW retrieval path; reached only on a genuine miss ──
4. DETERMINACY GATE        output checkable?  computational -> 5 ; qualitative -> 5' (sourced illustrative)
5. RETRIEVE                fetch authoritative example/formula from whitelisted sources
6. VALIDATE (ladder §8)    reproduction | cross-source+dimensional | span-grounding | anchor
                           any tier CONFIRMS?                -> 7 ; none does -> ESCALATE (§1.6 E4-E7)
7. GENERATE + CACHE        ground the solver with the validated fact; ship; write cache
8. ESCALATE                broaden retrieval -> human-review-once -> provisional (flag) -> guided (floor);
                           the topic is logged as coverage_gap until a rung delivers (never silently absent)
```

Steps 0–3 are the "**already found through the pipeline**" fast paths: when an existing verified producer
owns the topic, retrieval never runs. Step 4 ROUTES by kind (§1.7) — it never *exempts* a topic from having an
example; qualitative topics take the sourced-illustrative branch (5'), computational topics the numeric branch.
Step 8 is the completeness escalation (§1.6), not a dead end: guided is only the transitional floor when
provisional is off and every stronger rung is still pending, and it is always counted as a `coverage_gap`.

## 4. Cost model — where we save significantly (explicit)

Retrieval + validation is the *most expensive* path (network fetch + transcription LLM call + multiple
verification calls). The savings are entirely in **not reaching it**, and in **not repeating it**:

| Saving | Mechanism | What is skipped |
|---|---|---|
| **S1 Pipeline hit** | steps 1–3 short-circuit | ALL retrieval + validation for any adapter/gen_foundation/runtime-binding-owned topic (the majority of computational topics already covered) |
| **S2 Cache hit** | step 0 short-circuit | retrieval + transcription + validation, on every repeat of an already-verified concept (amortizes review to ~zero, `goal_plan_cache` pattern) |
| **S3 Determinacy gate** | step 4 | retrieval for qualitative/conceptual topics that have no checkable answer — they were going to a guided card regardless |
| **S4 Known-answer reproduction** | validation tier V1 | the need to *independently know the formula*: reproducing a published (problem, answer) pair validates formula + application end-to-end, sidestepping formula-correctness reasoning entirely |
| **S5 Cross-source early exit** | validation tier V2 | further source fan-out once the first two whitelisted sources agree |
| **S6 Abstain-fast** | step 8 | the legacy solver's expensive outline-retry / repair loops on unverifiable topics — abstention replaces "regenerate until it looks right" |
| **S7 Shadow reuse of fixtures** | Phase 0 | building retrieval before knowing it's worth it — the go/no-go is one script run |

**Budget guardrails:** retrieval path total wall-clock target ≤ existing per-topic worked-example budget
(no net regression); a single retrieval fetch ≤ 3 s, whole validation ladder ≤ 5 s, or the path abstains (S6).
Cache write on every confirmed result is mandatory (S2 is the primary scaling lever).

---

## 5. Core artifacts (typed schemas)

```python
# Retrieval
@dataclass(frozen=True)
class SourceRef:
    source_id: str          # whitelisted source key (e.g. "openstax_physics")
    url: str
    tier: Literal["textbook", "reference", "encyclopedic", "other"]
    retrieved_at: str       # ISO-8601

@dataclass(frozen=True)
class RetrievedFact:
    kind: Literal["worked_example", "formula", "definition"]
    concept_key: str
    raw_text: str           # the verbatim retrieved passage (span-grounding checks against THIS)
    source: SourceRef

@dataclass(frozen=True)
class RetrievedExample(RetrievedFact):     # kind="worked_example"
    stated_problem: str
    published_answer: str   # the ground truth for reproduction-check (V1)

# Transcription (prose -> structured, only for kind="formula")
@dataclass(frozen=True)
class TranscribedRelationship:
    concept_key: str
    expression_source: str  # compiles to the runtime_binding RestrictedExpression grammar
    output_symbol: str
    symbols: tuple[SymbolSpec, ...]   # name, role, unit, meaning  (mirrors ConceptContract SymbolContract)
    authority: Literal["authoritative_retrieval"]
    sources: tuple[SourceRef, ...]

# Validation
VerificationTier = Literal[
    "reproduction",         # V1 reproduced a published answer end-to-end          (strongest)
    "cross_source_dimensional",  # V2 >=2 sources agree AND units balance
    "span_grounded",        # V3 the claim is verbatim-supported by its source     (anti-hallucination)
    "answer_anchored",      # V4 existing independent-eval endpoint agrees
]
@dataclass(frozen=True)
class ValidationResult:
    confirmed: bool
    tier: Optional[VerificationTier]   # the tier that confirmed, or None
    evidence: Mapping[str, Any]        # tier-specific proof (matched value, agreeing sources, span, ...)
    detail: str

# Delivery / trust
TrustLevel = Literal[
    "trace_verified",         # adapter (existing)              — verified
    "execution_verified",     # gen_foundation (existing)       — verified
    "retrieval_reproduced",   # V1                              — verified
    "retrieval_corroborated", # V2/V3                           — verified
    "sourced_illustrative",   # qualitative, span-grounded (§1.7) — verified-as-sourced
    "answer_anchored",        # V4 (existing)                   — verified (weak)
    "provisional",            # delivered, trust-marked, enqueued for review (§1.5) — TRANSITIONAL, honest
    "guided_fallback",        # transitional floor only; a coverage_gap, not a delivered example
]
# soundness: only validate.py may assign a *verified* level, from tier evidence. completeness: everything
# except guided_fallback counts as delivered(topic).

# Cache
@dataclass(frozen=True)
class VerifiedConceptEntry:
    concept_key: str
    relationship: Optional[TranscribedRelationship]   # None for reproduction-only entries
    validation: ValidationResult
    trust_level: TrustLevel
    version: int
    created_at: str
```

## 6. Retrieval subsystem

- **Whitelisted sources only.** A static, reviewed `SOURCE_WHITELIST` (textbook/reference tier). No open-web
  free-for-all. Each source carries a `tier` weight used by cross-source corroboration.
- **Retrieve two kinds, preferring the first:**
  1. `RetrievedExample` — a full (problem, published answer) pair. Enables V1 (strongest, S4). Preferred.
  2. `RetrievedFact(kind="formula")` — the canonical relationship, when no published example is found.
- **Determinism/repro:** cache raw retrievals by `(concept_key, source_id)`; a re-run replays the cache, so
  generation stays reproducible and offline-testable via recorded fixtures.
- **Infra gate:** whether the backend can perform retrieval at generation time is an OPEN infra question
  (§19) resolved at the start of Phase 1; until then retrieval is fed from recorded fixtures only.

## 7. Transcription (prose → structured)

Only for `kind="formula"` (a `RetrievedExample` needs no transcription — V1 works on its numbers directly).
One bounded LLM call: retrieved passage → `TranscribedRelationship` (expression + typed/united symbols). This
is the single new model step, and it is **immediately checked** by the dimensional tier — a transcription
whose units don't balance is rejected before anything ships. `authority="authoritative_retrieval"`; the
runtime-binding compiler's authority gate is widened to accept this level **only** behind the flag.

## 8. Validation ladder (cheap→strong; on no confirmation, hand off to the escalation ladder §1.6)

Run in order; **stop at the first tier that CONFIRMS.** If none confirms → abstain (§ step 8). A tier may also
return *indecisive* (cannot judge) — indecisive is never treated as confirmation and never as refutation.

- **V1 — Reproduction (strongest, S4).** If a `RetrievedExample` was found: hand the solver its
  `stated_problem`, take the produced final answer, `reproduction_check` against `published_answer`
  (`retrieval_verify.py`, already built). Match → CONFIRMED `retrieval_reproduced`. Validates formula AND our
  application end-to-end without independently knowing the physics.
- **V2 — Cross-source + dimensional.** For a transcribed formula: (a) require ≥2 whitelisted sources to state
  an equivalent relationship (semantic-equivalence check; early-exit on first agreement, S5); AND (b) the
  dimensional check (`runtime_binding` A substrate) confirms units reduce to the output unit. Both → CONFIRMED
  `retrieval_corroborated`.
- **V3 — Span-grounding (anti-hallucination).** A dedicated verifier call: does the source passage *verbatim*
  support the claim? Must quote the supporting span. No span → the retrieval was hallucinated/misattributed →
  drop that source (not a confirmation on its own; a *gate* on V1/V2 sources).
- **V4 — Answer anchor (existing).** The independent-eval endpoint agrees with the final answer. Weakest;
  already live. CONFIRMED `answer_anchored` only if reached without V1–V3 (parity with today).

**Unit-mismatch rule:** V2's dimensional check is a hard veto (wrong units ⇒ never confirmed). V1's
`reproduction_check` records a unit mismatch but does not veto on it in v0 (magnitude-first); promote to a veto
once fixtures show it's safe.

## 9. Generation

On a CONFIRMED validation: ground the existing legacy solver with the validated fact (inject the reproduced
example or the transcribed formula as authoritative context) and produce the worked example through the
normal card path. The solver does the arithmetic deterministically where possible; the validated fact
constrains it. Output carries `metadata.verification_level = trust_level` and `metadata.sources`.

## 10. Caching & amortized review (the scaling lever, S2)

- On every CONFIRMED result, write a `VerifiedConceptEntry` keyed by `concept_key`. Subsequent topics on the
  same concept short-circuit at step 0 — retrieval/transcription/validation all skipped.
- Entries are versioned; a source-whitelist change or a spec version bump invalidates affected entries.
- A confirmed entry is effectively a *machine-reviewed contract*: it is exactly the durable data a human would
  otherwise hand-author for T6/runtime-binding. Over time the cache becomes the contract catalog, populated by
  retrieval instead of by hand — the whole point of the direction.
- **Optional review queue:** entries confirmed only at the weakest tier (V4) or with any unit mismatch may be
  flagged for one-time human review before caching, keeping high-stakes content honest without blocking the
  common case.

## 11. Trust levels & shipping policy

- **Ship as a worked example** iff `trust_level in {trace_verified, execution_verified, retrieval_reproduced,
  retrieval_corroborated, sourced_illustrative, answer_anchored, provisional}`. All of these count as
  `delivered(topic)` for coverage.
- **`provisional`** ships the example but is trust-marked (frontend badges it as under review) AND enqueued
  (E5). It never claims verification — soundness holds — while advancing completeness. Enabled by policy flag
  from Phase 2 only.
- **`guided_fallback`** is NOT a delivered example: it is the transitional floor (E7), always logged as a
  `coverage_gap` and fed to the review queue. Its rate is a tracked defect trending to zero, not a resting
  state.
- **Soundness gate:** no path may ship a *verified* level its tier didn't confirm; no path ships an unverified
  free-prose worked example as if verified — that regression is explicitly closed. `provisional` is the ONLY
  way an unverified example reaches a learner, and only when honestly marked + queued.
- Trust level + sources are recorded on the card and in telemetry; the frontend badges provenance and the
  provisional state (§ future, additive).

## 12. Failure & abstention policy

- Any retrieval/transcription/validation exception is contained; the path degrades to the next ESCALATION
  rung (§1.6), not straight to a guided card. Generation can never *depend* on retrieval succeeding.
- The guided floor (E7) replaces expensive regenerate-until-plausible loops (S6) — but it is a TRACKED DEFECT
  (`coverage_gap`), not a resting success. Soundness forbids shipping wrong; completeness forbids resting at a
  guided card. Every guided-floor topic is enqueued so the review queue converts it to a delivered example.

## 13. Decision trace & telemetry

Every routing hop and tier outcome is persisted via `record_lesson_decision` (which producer won; why
retrieval was/ wasn't reached; which tier confirmed or why all abstained) and surfaced by `explain_path.py`.
Telemetry counters: pipeline-hit rate (S1), cache-hit rate (S2), retrieval-reached rate, per-tier
confirm/indecisive/refute counts, per-escalation-rung distribution (E0–E7), **Coverage (§1.5)**,
`coverage_gap` count, `provisional` count + its promotion/correction outcomes from review, and end-to-end
latency per path. Coverage and `coverage_gap` are the headline completeness metrics; per-tier confirm counts
and audited soundness violations (target: 0) are the headline soundness metrics.

---

## 14. Rollout milestones + go/no-go gates

- **Phase 0 — offline reproduction core. DONE.** `retrieval_verify.py` (reproduction_check + 10 fixtures),
  `test_retrieval_verify.py` (15 tests), `scripts/retrieval_repro_gonogo.py`.
  **Gate G0 (blocks Phase 1):** run the go/no-go; the live solver must reproduce published answers at an
  agreed rate (proposed ≥ 70% decisive-accuracy, with abstention covering the rest). If it fails, retrieval is
  not pursued — reproduction can't gate what the solver can't produce.
- **Phase 1 — retrieval + validation ladder, SHADOW.** Source whitelist, retrieval (fixture-fed until the
  infra gate clears), transcription, V1–V4, cache — wired into `solve_worked_example` as an *observer* after
  the pipeline miss (records `ValidationResult` + would-be trust level to telemetry, ships nothing). Mirrors
  `runtime_binding/live_shadow.py`.
  **Gate G1:** on real traffic, shadow shows (a) acceptable retrieval-reached precision, (b) V1/V2 confirm
  rate high enough to matter, (c) zero cases where a tier confirmed a demonstrably wrong example (audited
  sample). Also: infra gate (can we retrieve at gen time?) resolved.
- **Phase 2 — live delivery + escalation.** Flip the flag: confirmed → ship grounded example with trust
  level; unconfirmed → escalation ladder (§1.6) with `provisional` enabled + review queue live. Cache active.
  Concept-domain suppression (§1) is replaced by the sourced-illustrative branch (§1.7), so qualitative topics
  gain examples too. `guided_fallback` becomes the tracked floor, not the default.
  **Gate G2:** live shows more verified examples, ZERO soundness violations (no wrong example shipped as
  verified — audited), coverage strictly up vs. the suppression baseline, latency within budget.
- **Phase 3 — completeness convergence.** Not new machinery — an operating discipline. Drive Coverage (§1.5)
  to the end-state target by: working the review queue (E5) so provisional/guided items become cached-verified;
  growing the source whitelist to shrink E4/E7; letting the cache (S2) absorb the steady state. Coverage and
  `coverage_gap` are dashboarded per domain.
  **Gate G3 (spec DONE):** Coverage ≥ target (proposed ≥ 99% of desired examples delivered, of which the
  overwhelming majority verified, the rest provisional-under-review), `guided_fallback` rate near zero and
  strictly decreasing, and every remaining gap is an explicit queue item — never a silent absence.

## 15. Minimum vertical slice (first end-to-end, one concept)

`motional_emf` fixture → retrieval returns its `RetrievedExample` (from recorded fixture) → V1 reproduction
against "1.0 V" → CONFIRMED `retrieval_reproduced` → grounded solver ships the example → cache entry written →
a second `motional_emf` topic short-circuits at step 0. Everything offline via fixtures; no live network.

## 16. Acceptance tests (executable table)

| # | Given | When | Then |
|---|---|---|---|
| A1 | adapter routes for topic | resolve | retrieval NEVER invoked; trace_verified (S1) |
| A2 | gen_foundation solves topic | resolve | retrieval NEVER invoked; execution_verified (S1) |
| A3 | concept already in cache | resolve | steps 1–7 skipped; cached trust level returned (S2) |
| A4 | qualitative topic (not determinate) | resolve | determinacy gate abstains to sourced guided; no retrieval (S3) |
| A5 | RetrievedExample, solver reproduces published answer | validate | CONFIRMED `retrieval_reproduced` (V1) |
| A6 | RetrievedExample, solver produces wrong number | validate | V1 refutes; falls to next tier / abstains; NOT shipped |
| A7 | formula transcribed, units don't balance | validate | V2 dimensional veto; not confirmed via V2 |
| A8 | two whitelisted sources agree + units balance | validate | CONFIRMED `retrieval_corroborated` (V2); fan-out stopped (S5) |
| A9 | claim not supported by source passage | validate | V3 span-grounding drops the source (anti-hallucination) |
| A10 | no tier confirms | resolve | abstain: sourced guided card, never a fabricated worked example (S6) |
| A11 | confirmed result | after ship | `VerifiedConceptEntry` written; every decision in decision trace |
| A12 | retrieval raises | resolve | contained; degrades to abstention; generation unaffected |
| A13 | reproduction indecisive (non-numeric produced) | validate | treated as neither confirm nor refute; ladder continues |
| A14 | desired example, no tier confirms, provisional ON | resolve | ships `provisional` (trust-marked) + enqueued; counts delivered; NOT `guided_fallback` (completeness) |
| A15 | desired example, no tier confirms, provisional OFF | resolve | `guided_fallback` floor; logged as `coverage_gap`; enqueued for review — never silently absent |
| A16 | qualitative topic with a span-groundable source | resolve | sourced illustrative example (§1.7); counts delivered; NOT a guided card |
| A17 | ANY desired example, any path | resolve | `delivered=True` OR an explicit `coverage_gap` record exists — the disjunction is exhaustive (completeness invariant) |
| A18 | wrong example, no tier confirms | resolve | NEVER shipped as a *verified* level; may ship only as honestly-marked `provisional` (soundness invariant) |

## 17. Named fixtures

- `KNOWN_ANSWER_FIXTURES` (exists, `retrieval_verify.py`): 10 (problem, formula, published-answer) triples,
  EM/mechanics/circuits/finance/chemistry. Reused as the V1 corpus.
- `RECORDED_RETRIEVALS` (new): per fixture, a recorded `RetrievedExample` + 2 `RetrievedFact` formula sources
  (one agreeing, one deliberately conflicting) so V2/V3/span-grounding are exercised offline.
- `HALLUCINATED_RETRIEVAL` (new): a passage that does NOT contain the claimed formula → V3 must drop it.
- `WRONG_BUT_DIMENSIONAL` (new): a formula with correct units but wrong coefficient → passes dimensional,
  must be caught by V1/cross-source, proving the ladder's independence claim.

## 18. Implementation surface

New:
- `app/services/examples/retrieval/` package: `sources.py` (whitelist), `fetch.py` (retrieval + record/replay
  cache), `transcribe.py` (prose→`TranscribedRelationship`, one LLM call), `validate.py` (the V1–V4 ladder),
  `cache.py` (`VerifiedConceptEntry` store, `goal_plan_cache` pattern), `router.py`
  (`resolve_worked_example` cascade), `shadow.py` (Phase 1 observer).
- Tests mirroring each, plus the offline vertical-slice test (§15).

Reused (imported, not reimplemented): `retrieval_verify.reproduction_check`; `runtime_binding.units`/`compiler`
(dimensional check); `answer_anchor`; `guided_explanation`; `decision_trace`; the `solve_worked_example`
cascade seam.

**MUST NOT be a source of truth:**
- The **LLM** must not be the source of a formula's correctness — only the retrieved source (via V2/V3) or a
  reproduced published answer (V1) is. The transcription call proposes; it never certifies.
- **A single source** must not confirm a formula (V2 requires ≥2; V3 gates hallucination). Reproduction (V1)
  may confirm from one source because the published *answer* is the independent check.
- **`retrieval_reproduced`/`corroborated`** must not be writable by generation code directly — only
  `validate.py` sets a trust level, from tier evidence.
- The **cache** must not persist a *verified* entry that wasn't CONFIRMED by a named tier; no "assumed good"
  writes. (A `provisional` entry may be cached as provisional, never promoted to verified without review.)
- This layer must not introduce new execution semantics or a second arithmetic engine — reuse the exact
  executor / deterministic eval.
- **Completeness must not be bought with soundness:** raising coverage must never be implemented by relabeling
  an unconfirmed example as verified. The only lever for delivering-without-confirming is honestly-marked
  `provisional` + enqueue. Conversely, **soundness must not be used to excuse silent absence:** a topic that
  can't be verified must escalate and be tracked as a `coverage_gap`, never dropped without a record.
- No topic that `desires` an example may exit `resolve_worked_example` with neither a `delivered` example nor
  a logged `coverage_gap` — the two outcomes are exhaustive and one must always hold (A17).

## 19. Non-goals

- Finishing Grounded Runtime Binding Milestone C (persistence/ownership/live delivery). Explicitly out.
- Open-web retrieval. Whitelisted sources only.
- *Numeric* proof of qualitative claims. Qualitative topics get a **sourced illustrative example** (§1.7) —
  grounded and attributable, counting toward completeness — not a numeric proof and not a mere guided card.
- Symbolic/CAS calculus (deferred, as in the adapter taxonomy).
- Frontend provenance badging (future, additive).

## 20. Open decisions

- **Infra:** can the backend retrieve at generation time (network/egress, a search/reference API, latency)? If
  not, Phase 1 stays fixture-fed and Phase 2 waits on infra. Resolve at Phase 1 start (Gate G1).
- **G0 threshold:** the exact reproduction hit-rate bar (proposed ≥70% decisive-accuracy). Set from the
  go/no-go output before committing to Phase 1.
- **Source whitelist:** which sources, and the equivalence-check method for V2 (symbolic parse vs. bounded LLM
  yes/no).
- **Review queue:** whether weakest-tier confirmations require one-time human review before caching.
```
