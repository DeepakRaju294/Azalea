# Trace → Teaching Contract Spec — Companion (Q23)

> **Purpose.** The domain gate (Phase 0) + narration contracts (Phase 2) produce **better-shaped** content, but
> shape is not truth. This companion defines how a card's **prose** is allowed to derive from a verified adapter
> **trace**, how a **prose-vs-example contradiction** is detected, and what **blocks shipping**. It is the
> correctness gate that lets Phase 2 move a family from `shadow_validate` to `on_enforced` with *explanatory
> prose* — not just bare adapter values.
>
> Companion to `DOMAIN_CARD_NARRATION_AND_RENDERING_SPEC.md` (§12). Sibling: `FREE_TEXT_CONTENT_VALIDATION_SPEC.md`
> (the other half — claims with **no** trace to check against).
>
> **Core principle:** *the trace defines truth; prose may only surface, derive from, or remain consistent with
> that truth.* No teaching field may fill a missing truth (interpretation, intuition, real-world meaning) with
> plausible-but-unsupported text.

---

## 1. Where this sits (and why prose needs a contract at all)

Phase 2's fact-source registry (§4) already forces every **truth-bearing value** (a result expression, a unit, a
rule tag) to come from the trace via a registered `direct`/`derived` source. But a card is more than its values —
it has **connective prose**: a step's `goal` sentence, the process card's "Why", a `formula_breakdown`'s
explanation. That prose is LLM-authored, and the fact-source registry does not constrain it. Without a contract,
an `on_enforced` card can *look* grounded (correct number, correct unit) while its sentence **says something the
trace never claims** ("the velocity is negative because the object reverses" when the trace computed a magnitude).

**Runtime position** (extends the §2.1 order): `… → narration contract → **trace-to-teaching validation** →
renderer selection → card-safety → rollout decision`. Trace-to-teaching runs **after** the narrator drafts prose
and **before** display; a violation blocks/repairs the card (§10).

---

## 2. The real trace grammar (author against payloads, not theory)

Grounded in the live type-engines (`app/services/examples/trace_adapters/families/*_engine.py`). Every engine
emits the same **step grammar**, so this contract keys off the grammar, not per-adapter data:

```
Step {
  id                      # "s1", "s2", …  (the trace_step_id every card must carry)
  operation               # the operation tag: "identify_knowns", "compute_force", "completion"
  prior_state             # dict — state before this step
  state_after             # dict — state after
  visual_state            # e.g. {"kind": "equation", "<name>": <value>}
  expected_visible_result # the visible result string of the step (e.g. "F = 20 N")
  facts {
    allowed_values        # the ONLY literal numbers prose may use in this step
    required_facts        # facts the step's prose MUST state (see §6 schema)
    forbidden_claims      # claims the step's prose MUST NOT make (see §7 schema)
  }
}
Output { name · equation(display) · expr(eval) · unit · stage_id(=operation) · teaching_focus · fact_kind }
Trace-level { required_operations[] · evidence: operation → [step_ids] · terminal_condition }
```

Two properties make this contract enforceable:
1. **The trace is verified** — the engine's gate re-evaluates every `Output`, so `expr`, `expected_visible_result`,
   and `unit` are ground truth, not model output.
2. **The trace already carries a truth boundary** — `facts.allowed_values` / `required_facts` /
   **`forbidden_claims`** per step, plus `Output.teaching_focus`. Trace-to-teaching's job is largely to
   **enforce fields the trace already declares**, not to invent a new judgment.

> **Schema extension note.** §§6–8 tighten `required_facts`, `forbidden_claims`, and `operation` into typed shapes.
> Today's engines emit the looser forms; the schema upgrade (adding `fact_id`/`acceptable_renderings`,
> structural forbidden claims, and the operation-intent vocabulary) is an **engine-side change delivered with this
> spec**, gated by the engines' own output tests — not implicit narration work.

---

## 3. Authoritative vs. derivable — the field ledger

Extends the Phase-2 fact-source registry (§4). Each teaching field maps to exactly one class:

| Class | Definition | Source | Example |
|---|---|---|---|
| **authoritative** | ground truth from the verified trace; prose may only **surface** it verbatim/formatted | `Step`/`Output` field | `expected_visible_result`, `Output.unit`, `Output.equation`, `operation` |
| **derivable** | a **named deterministic template** over enumerated authoritative inputs (§4 `derived`) | template + input field ids | "next step applies `<operation>` to `<prior_state>`" |
| **connective** | LLM prose that must be **consistent with** the trace but adds no new truth-bearing value | validated_generated | a step's `goal`/`reasoning` sentence, the process "Why" |
| **out-of-contract** | a claim with **no** trace basis (interpretation, real-world meaning, why-it-matters) | — | blocked here → handed to `FREE_TEXT_CONTENT_VALIDATION` or omitted |

**Rule:** `authoritative` prose is surfaced, never paraphrased into a different value; `derivable` runs its
template; `connective` prose ships only if it passes §8 validation; `out-of-contract` claims are **removed** from
the trace-backed card (they are the free-text spec's domain, not this one). A field that is neither authoritative
nor derivable for the active adapter (e.g. science `interpretation`, blocked by the §4 `quantity_kind` gap) is
**omitted**, never connective-generated.

---

## 4. Per-card derivation contract

How each `defined` card derives from the trace (framing labels come from the Phase-2 narration contracts; values
from here). Every emitted card carries its `trace_step_id`(s):

- **`worked_example` step** — one `Step` → one card. `work` = `expected_visible_result` / substituted `equation`
  (authoritative). `result` = `state_after`/`Output` value + `unit` (authoritative). `reasoning` = a `derived`
  line naming the `operation`/`Output.equation` (the rule), **not** free prose. `goal` = connective, validated.
  Step **titles describe the action** (`operation`), never the rule name (narration §3 rule 4).
- **`process` card** — the scaffold steps (`Setup→Operation→Result→Why` etc.) map to the ordered
  `required_operations`; each stage's content is `derived` from the corresponding step(s) via the `evidence` map.
  The "Why" line is **connective** and must cite an `Output.teaching_focus`/`operation`, validated by §8.
- **`formula_breakdown` (math)** — `rule` ← `operation`/`Output.equation` (authoritative); `form` ←
  `expected_visible_result`/`state_after` (authoritative); `parts`/`transformation`/`why` are connective + §8.
- **completion / terminal** — the `completion` operation + `terminal_condition` mark the final card; result lines
  are **terminal, not narrated** (narration §3 rule 5).

---

## 5. Numeric normalization contract (makes C1 operational)

"Every number in prose is in `allowed_values`" is only enforceable with a canonical parse. **Numbers are parsed
by the existing expression parser / sealed eval, never by naïve regex.**

```text
Numeric normalization:
- Parse numeric literals into a canonical rational/decimal form; 3, 3.0, 3.00 are equivalent.
- Units are parsed SEPARATELY from magnitudes (20 N → value 20 + unit "N"); magnitude checked by C1, unit by C4.
- Fractions / ratios / scientific / powers (1/2, 0.5, 2×, x², 10^-3) are parsed via the expression parser and
  canonicalized; a percentage converts to a decimal ONLY when an explicit percent↔decimal conversion is registered
  for that field, else the two forms are distinct.
- Presentational ordinals ("Step 2", list indices) are ignored ONLY in an approved title/label field allow-list;
  everywhere else they are numeric tokens.
- Values inside fenced code blocks are treated by the coding-grammar rules, not the math rules.
- Variable-like tokens (v2, x1) are NOT numeric extractions (identifier, not literal).
- An interval "0 ≤ x ≤ 1" is parsed as its bound literals {0, 1}, each checked.
- An UNRECOGNIZED numeric-like token is a **hard fail (C1)**, never silently ignored — fail closed.
```

`allowed_values` for a step = `facts.allowed_values` ∪ the step's authoritative literals (`state_after`,
`expected_visible_result`, the substituted `equation` operands). A literal outside that set is an **invented
value**.

---

## 6. `required_facts` schema (makes C3 deterministic, not a grading problem)

`required_facts` must be typed so validation is a match, not open-ended semantic grading (else C3 becomes C6 in
disguise). Each required fact:

```json
{
  "fact_id": "force_direction_positive_x",
  "kind": "direction",
  "subject": "net_force",
  "relation": "points",
  "value": "+x",
  "acceptable_renderings": [
    "the net force points in the positive x-direction",
    "the net force points right"
  ],
  "required_in_fields": ["reasoning", "result"]
}
```

**C3 passes** for a fact when the target field contains one of `acceptable_renderings` (normalized match) **or** a
registered deterministic paraphrase rule for `(kind, relation, value)` matches. If neither matches, C3 is a
**repairable** failure carrying the unmatched `fact_id` (the generator is told exactly which fact to add). C3
**never** delegates "does this sentence count as stating the fact?" to the LLM judge.

---

## 7. `forbidden_claims` schema (C2 deterministic + explicit C6 backstop)

Pure string matching misses paraphrase ("changes direction" / "moves backward" / "reverses" / "goes the other
way"). So forbidden claims are encoded **structurally**, with phrase families only as a fast first pass:

```json
{
  "claim_type": "direction_reversal",
  "subject": "object",
  "forbidden_when": { "trace_field": "motion_direction", "equals": "unchanged" },
  "known_phrasings": ["reverses", "changes direction", "moves backward", "goes the other way"]
}
```

- **C2 (deterministic)** rejects any `known_phrasings` hit whose `forbidden_when` predicate holds against the
  trace. This is a first-pass detector, **not complete**.
- **The spec states explicitly:** C2 catches known banned forms; **C6 is required to catch semantic paraphrases of
  forbidden claims** not in `known_phrasings`. Implementation must not assume C2 is complete protection.

---

## 8. Operation contract (makes C5 deterministic)

"The card's claimed action matches its `Step.operation`" needs an operation vocabulary, so "plug the knowns into
F = ma" passes for `substitute_known_values` while "solve for acceleration" fails:

```json
{
  "operation": "substitute_known_values",
  "allowed_action_intents": ["substitute", "plug in", "replace variables with known values"],
  "forbidden_action_intents": ["isolate variable", "differentiate", "integrate", "solve for another quantity"]
}
```

**C5 passes** when the card's action verb maps (via a registered intent lexicon) to an `allowed_action_intent` and
none of the `forbidden_action_intents`; and the card's position respects `required_operations` order. A card
asserting a `forbidden_action_intent` or an unmapped action is a **hard fail**. The intent lexicon is deterministic
config, not an LLM call.

---

## 9. Contradiction detection (prose ⟂ trace)

Deterministic checks **C1–C5 all run** (collect every failure — §10); **C6 runs only if no hard deterministic
failure exists**. Each check names its authoritative basis:

- **C1 — value containment.** Every normalized number (§5) is in the step's allowed set. Outside ⇒ **hard fail**.
  (Catches the `x²=−4 → (x)²=0` class *when a trace exists*.)
- **C2 — forbidden claims.** No `known_phrasings` hit whose `forbidden_when` holds (§7) ⇒ else **hard fail**.
- **C3 — required facts.** Every `required_facts` entry matched in its `required_in_fields` (§6) ⇒ else
  **repairable fail** carrying the `fact_id`.
- **C4 — unit fidelity (per attributed quantity).** A step may carry **several** quantities
  (`allowed_quantities: [{name, value, unit}]` — e.g. mass 4 kg + acceleration 5 m/s² + force 20 N in one step).
  Each numeric quantity in prose is validated against **its own attributed output's** `unit`, not a single
  step-wide unit. An invented/converted unit, or a value paired with the wrong unit, ⇒ **hard fail**. (Attribution
  in §10.1.)
- **C5 — operation/order fidelity.** Action maps to an allowed intent + order respects `required_operations`
  (§8) ⇒ else **hard fail**.
- **C6 — semantic non-contradiction (bounded judge, reject-only, last).** Asked *only* "does this sentence
  contradict {authoritative facts}? yes/no + span." May **only reject**, never add facts. C6 verdict handling:

| C6 result | Behavior |
|---|---|
| ambiguous connective statement, no contradiction | **optional** field → drop the sentence + ship; **required** field → targeted retry. **Never RETAIN** an ambiguous sentence merely because it isn't provably false |
| unsupported causal explanation | **repairable** (retry / remove) |
| misleading interpretation of a verified value | **repairable** (retry) |
| **direct contradiction of the trace** | **hard fail** (retry allowed, but must pass a second validation to ship) |
| judge unavailable | **skip C6**, continue on C1–C5 (fail toward deterministic) |
| judge malformed response | treat as unavailable; log separately |

**Prose-vs-example contradiction** = any C1/C2/C4/C5 failure between a card's sentence and its step, OR two cards
bound to the **same `trace_step_id`** surfacing conflicting authoritative values for the same
`output_name`/`fact_id`. **Cross-card consistency keys on `(trace_id, trace_step_id, output_name|fact_id)`,
never `operation` alone** — two *different* steps may share an `operation` tag (e.g. `substitute_known_values`)
and legitimately produce different intermediate values (§10.1). C6 covers the residual "uses allowed numbers but
still misleads" case.

---

## 10. Validator result payload (the architecture contract)

The validator returns a **layered** result so deterministic facts and judge interpretation never blur, and retry
prompts get the full failure set:

```text
TraceTeachingValidationResult {
  deterministic: { c1..c5: pass|fail, normalized_literals[], matched_required_facts[], unmatched_fact_ids[],
                   operation_alignment }
  semantic:      { c6: pass|reject|unavailable, offending_span?, judge_available }
  decision:      pass | retry | withhold | shadow_log
  failures:      [ { check, class: primary | independent | suppressed, field, detail } ]   # ALL, not just first
  telemetry:     { trace_id, card_type, operation, rollout_mode, retry_count, primary_failure }
}
```

**Execution order:** run all of C1–C5 and collect every failure; do **not** run C6 if any *unsuppressed* hard
deterministic failure exists; retry with the **complete** failure payload; persist the first failure as
`primary_failure` for dashboards while retaining all in `telemetry`.

**Failure classification** (so cascading noise doesn't dominate retries):
- **primary** — directly caused by the card text (e.g. an invented literal).
- **independent** — a separately-observed direct violation (e.g. a wrong unit on a different quantity).
- **suppressed** — a check that isn't meaningful because an upstream parse/source mapping failed (e.g. a field's
  math won't parse ⇒ C1 is *primary*, and C3's "required fact missing" on that field is *suppressed*, not counted
  as an independent omission). Suppressed failures don't drive retries and don't block C6 ordering.

### 10.1 Failure precedence & field scope (closes the remaining ambiguity)

**C1/C4 field scope.** Prose token-scanning applies to **prose-bearing** fields only; authoritative display fields
are validated against their source mapping, not re-scanned:
```text
- Enforced (prose scan): goal · reasoning · why · transformation · parts · connective labels · a11y descriptions.
- Authoritative (source-mapping check, not token scan): work · result · form (checked against Output/state_after).
- Excluded entirely: internal ids · trace_step_id · UI step counters · source citations · approved card labels.
- Coding cards: code blocks + line-number labels delegate to the coding-trace validator, not the math rules.
```
**Quantity attribution (C4).** A step exposes `allowed_quantities: [{name, value, unit}]`; each prose quantity is
matched to one entry, and its unit checked against that entry — never against a single step-wide unit.
**Required-field gating.** C3 runs only for fields the **active narration contract** marks required; C5 runs only
on fields declared to communicate an action.
**Cross-card identity.** Consistency keys on `(trace_id, trace_step_id, output_name|fact_id)`; a card citing
multiple `trace_step_id`s must declare which value came from which step. Same-`operation`, different-step is **not**
a conflict.
**Optional vs. required connective.** An *optional* connective sentence failing C6-ambiguity is **removed**; a
*required* connective field retries. Never retain an ambiguous sentence just because it isn't provably false.

---

## 11. Retries + block conditions

```
draft card → validate (§10)
  decision == pass                     → SHIP
  repairable (C3, repairable-C6)       → targeted regenerate with the full failure payload (max 2), re-validate
  hard fail after retries              → per rollout mode:
      on_enforced     → WITHHOLD the card with typed error trace_teaching_violation:<check>
      shadow_validate → keep the approved safe display, log the violation (no user impact)
```

- **Never** ship a card that fails C1/C2/C4/C5 or a C6 direct contradiction — no "soften and continue," and a
  retried card must pass a **second** full validation before shipping.
- **Never** downgrade a required trace-backed value to connective prose to dodge a check.
- A withheld **required** card withholds the topic-type/family from `on_enforced` (§2.1) — it does **not** silently
  drop to generic narration.

---

## 12. Frontend behavior on withhold (required-card product contract)

Withholding a required card must be a deliberate product state, not a broken carousel:

```text
Required-card withholding behavior:
- Backend returns a typed TOPIC-GENERATION failure, NOT a partial card sequence.
- Frontend does not render an empty/placeholder card and does not break step numbering.
- The topic is marked unavailable/retryable, NOT complete (progress is not credited).
- The learner sees a neutral regeneration state (internal rollout may surface a dev-visible failure card).
- The frontend renders compiled authoritative fields ONLY; it never repairs or infers missing trace semantics.
- Telemetry: topic_id, card_type, operation, validation check, retry_count.
```

---

## 13. Coverage (which trace grammars are contracted)

Keyed to the live engines, not individual adapters:

| Engine | Grammar | Trace-to-teaching status |
|---|---|---|
| **T6 formula** | substitute → compute → result+units | **primary target** (Newton, completing-the-square-adjacent); C1–C5 fully apply |
| **T7 rewrite** | one allowed rule per step → normal form | applies; `operation` = the rewrite rule, `expected_visible_result` = the rewritten form |
| **T8a construction** | add one valid piece per step | applies; `state_after` = the growing structure |
| **T8b derivation** | each step justified by a named rule | applies; `operation` = the named law (ideal for `formula_breakdown`/`proof_plan`) |
| **coding (execution trace)** | line → state delta | already the shipped verified path; this contract formalizes it as the regression baseline |

Because the grammar is uniform, **adding more adapter data rows does not expand this contract** — it widens how
many topics it covers.

---

## 14. Flag + rollout

Part of the `on_enforced` gate under `AZALEA_DOMAIN_NARRATION_V2` (no separate flag):
- `off_legacy` — not run.
- `shadow_validate` — run C1–C6, **log** violations, **do not** alter display (how a family earns `on_enforced`:
  its shadow violation rate must be ~0).
- `on_enforced` — run C1–C6; a hard fail **withholds** the card (§11).

---

## 15. Minimum vertical slice (one fixture, end-to-end)

Prove the whole path on a single T6 example before generalizing:

```text
Minimum vertical slice — Newton's second law
Input:  mass = 4 kg, acceleration = 5 m/s²
Trace:  s1 identify_knowns · s2 substitute_known_values (F = m*a → 4*5) · s3 compute_force (F = 20 N) · s4 completion
Expected teaching output:
  - exactly one worked_example card per trace step, each carrying a valid trace_step_id
  - every numeric literal is trace-authorized (4, 5, 20)
  - final visible result is "F = 20 N"; unit "N" only
  - reasoning names the rule (F = m·a); title describes the action ("substitute the knowns"), not "Newton's law rule"
  - NO legacy narration path and NO frontend recovery path is used
```

**"No legacy path" is instrumented, not code-reviewed.** Generation emits `GenerationPathTelemetry` so the golden
test can assert it, not eyeball it:
```text
GenerationPathTelemetry { narration_path: trace_teaching_v1 | legacy_narration
                          visual_path: compiled_visual_v1 | legacy_visual_repair
                          frontend_recovery_used: bool
                          fallback_reason: enum | null }
golden assert: narration_path == trace_teaching_v1 · visual_path == compiled_visual_v1
             · frontend_recovery_used is False · fallback_reason is null
```

---

## 16. Acceptance-test table (executable contract)

| Test | Fixture | Expected assertion |
|---|---|---|
| `test_c1_rejects_invented_literal` | trace authorizes 4,5,20; prose says "25 N" | reject `trace_teaching_violation:C1` |
| `test_c1_accepts_decimal_normalization` | trace has 3.0; prose says 3 | pass |
| `test_c1_rejects_unrecognized_numeric_token` | prose has a malformed numeric-like token | reject C1 (fail closed) |
| `test_c2_rejects_direction_reversal` | trace motion_direction=unchanged; prose "the object reverses" | reject C2 |
| `test_c2_paraphrase_caught_by_c6` | forbidden claim paraphrased outside known_phrasings | reject C6 |
| `test_c3_requires_named_law` | step requires fact_id force_law_newton | repairable; retry payload carries the fact_id; passes after repair |
| `test_c4_rejects_unit_mutation` | Output 20 N; prose "20 kg" | reject C4 |
| `test_c4_multi_quantity_step_accepts_each_unit` | one step with 4 kg + 5 m/s² + 20 N | pass (each quantity → its attributed unit) |
| `test_c3_suppressed_when_field_unparsable` | field math won't parse | C1 primary; C3 marked suppressed, not independent |
| `test_same_operation_different_step_not_conflict` | two steps, same operation, different values | pass (keyed on trace_step_id) |
| `test_generation_path_telemetry_asserts_no_legacy` | valid slice | narration_path=trace_teaching_v1, frontend_recovery_used=False |
| `test_c5_rejects_operation_mismatch` | operation substitute; prose "solve for acceleration" | reject C5 |
| `test_c5_accepts_intent_synonym` | operation substitute; prose "plug in the knowns" | pass |
| `test_c6_rejects_semantic_contradiction` | allowed values valid but causal claim contradicts trace | reject C6 (hard) |
| `test_c6_unavailable_falls_through` | judge unavailable | C1–C5 decide; C6 skipped, logged |
| `test_all_deterministic_failures_returned` | card fails C1+C4+C5 | failures list contains all three |
| `test_enforced_withholds_required_card` | hard failure, on_enforced | topic/family path withheld; no generic narration |
| `test_shadow_logs_without_user_impact` | same failure, shadow_validate | legacy display remains; typed telemetry emitted |
| `test_conflicting_same_operation_cards` | two cards, same operation, different values | reject (cross-card C1/C4) |

---

## 17. Regression fixtures

```text
fixtures/trace_teaching/
  newton_valid_grounded.json            # the §15 slice, must pass end-to-end
  newton_wrong_unit.json                # C4
  newton_invented_value.json            # C1
  completing_square_invalid_zero.json   # x²=−4 ⇒ (x)²=0 class (C1)
  direction_reversal_claim.json         # C2 / C6
  operation_mismatch.json               # C5
  missing_required_law.json             # C3
  conflicting_same_operation_cards.json # cross-card C1/C4
```

The historical known-failures become permanent fixtures: completing-the-square values changing incorrectly; a
valid magnitude explained as a signed directional quantity; wrong/converted units; duplicate cards citing one
operation with different values; a required operation omitted from the teaching sequence.

---

## 18. Expected implementation surface

```text
Expected to change:
- trace adapter schema/types (add fact_id/acceptable_renderings, structural forbidden_claims, operation-intent vocab)
- narration payload schema/types (carry trace_step_id per card)
- trace_to_teaching validator module (C1–C6 + TraceTeachingValidationResult)
- deterministic numeric/unit parser (reuse the sealed eval, not regex)
- operation-contract registry + fact/forbidden-claim registries
- generation retry coordinator (full-failure-payload retries, max 2)
- rollout gate integration (AZALEA_DOMAIN_NARRATION_V2 shadow/enforced)
- telemetry emitter (per-family validation outcomes) + GenerationPathTelemetry (narration/visual/recovery path)
- frontend topic-generation error state (§12)
- unit/integration fixture directories (§17)

MUST NOT become a source of truth:
- frontend recovery utilities / legacy visual repair passes
- LLM-generated visual JSON
- the generic narration fallback in on_enforced mode
- the C6 judge (reject-only; never authors or repairs missing semantics)
```

---

## 19. Definition of done

- [ ] A T6 Newton fixture passes trace → narration → validation → rendering end-to-end (§15).
- [ ] A completing-the-square fixture with an invented intermediate value is rejected by C1.
- [ ] A wrong-unit fixture is rejected by C4; an operation-mismatch fixture by C5.
- [ ] A required-fact omission produces a targeted retry payload (carrying `fact_id`) and passes only after repair.
- [ ] A semantic contradiction fixture is rejected by C6 **without** C6 adding facts; an unavailable judge falls
  through to C1–C5.
- [ ] All deterministic failures (C1–C5) are returned together; the retry uses the complete payload.
- [ ] In `shadow_validate`, violations emit typed telemetry without changing the learner-visible path.
- [ ] In `on_enforced`, a failed required card blocks the topic/family path and **never** invokes generic narration.
- [ ] Frontend receives compiled authoritative fields only and does not repair missing trace semantics (§12).
- [ ] C4 validates each quantity against its **attributed** unit (multi-quantity step passes); C1/C4 field scope
  (§10.1) is enforced — authoritative fields checked by source mapping, not prose token scan.
- [ ] Failures are classed primary/independent/suppressed; a parse failure suppresses dependent checks.
- [ ] Cross-card consistency keys on `(trace_id, trace_step_id, output_name|fact_id)` — same-operation/different-
  step is not flagged.
- [ ] `GenerationPathTelemetry` is emitted; the golden test asserts `narration_path == trace_teaching_v1`,
  `frontend_recovery_used is False`, `fallback_reason is null` (no legacy path proven by instrumentation, not review).

## 20. Non-goals

- **Not** a change to adapter computation, trace state, or expected answers (§11 of the narration spec holds); the
  schema additions in §§6–8 are metadata the engines already can supply, gated by their own output tests.
- **Not** factual validation of claims with **no** trace basis — that is `FREE_TEXT_CONTENT_VALIDATION_SPEC`.
- **Not** a general fact-checker: it only enforces consistency **with a verified trace that already exists**.
