# Free-Text Content Validation Spec — Companion (Q24)

> **Purpose.** The domain gate fixes *shape*; the trace-to-teaching contract keeps *trace-backed* prose honest.
> Neither can stop a **false claim on a card that has no trace to check against** — a background paragraph, a
> concept explanation, an edge-case assertion, a "why it matters" line. The gate cannot catch
> `x² = −4 → (x)² = 0`. This companion defines how such **free-text** content is factually checked before it
> ships.
>
> Companion to `DOMAIN_CARD_NARRATION_AND_RENDERING_SPEC.md` (§12). Sibling: `TRACE_TO_TEACHING_CONTRACT_SPEC.md`
> (the trace-backed half). **Clean split:** a value/claim with a verified trace → trace-to-teaching; a claim with
> **no** trace → here. A field is validated by exactly one of the two.
>
> **Core stance:** conservative by construction. When a claim cannot be established, this layer **withholds or
> softens** it — it never certifies. No card may present unverified free text as established fact.

---

## 1. The problem this owns

Verified adapters back only a subset of cards (a worked example, a formula breakdown). The rest of a lesson is
**free text**: `background`, `concept_intuition`, `components_terms` definitions, `edge_case` assertions,
`practice` prompts, "why this matters" framing. These carry real factual risk no upstream layer catches:
- a **false mathematical claim** (`x² = −4 ⇒ (x)² = 0`, "the derivative of a constant is the constant");
- a **wrong definition** ("a stack is FIFO");
- an **overreaching edge case** ("this always terminates") or a **misattributed rule/law**;
- a claim that **contradicts the card's own verified example** (prose vs. adapter example).

---

## 2. Scope — what is "free text"

Applies to any card **field** not covered by the trace-to-teaching field ledger (§3 there):

| In scope (validated here) | Out of scope (owned elsewhere) |
|---|---|
| `background` prose · `concept_intuition` body · `components_terms` definitions · `edge_case` assertions · `practice` prompt correctness · "why it matters" / interpretation framing | any `authoritative`/`derivable` trace value (→ trace-to-teaching) · topic-type routing (→ Phase 0) · card presence/shape (→ Phase 2 gate) |

A card may be **mixed**: trace-backed fields go through trace-to-teaching, free-text fields through this spec. A
field is never validated by both.

---

## 3. The validation ladder (cheapest, most-certain first)

Each free-text field runs the applicable rungs; the **strongest applicable** verdict wins. L1–L3 are
deterministic and preferred; L4 is a **risk classifier**, not a certifier — it may reject/downgrade but **never
establishes a claim as true**.

### L1 — scope adherence (deterministic)
Do not introduce terminology outside prerequisites or what the topic teaches (narration §3). Enforced against a
topic-level **vocabulary object**, so ordinary prose isn't mistaken for a technical term:
```json
{
  "assumed_prerequisite_terms": ["variable", "equation", "force"],
  "introduced_terms": ["net force", "Newton's second law"],
  "approved_operations": ["substitute", "compute"],
  "approved_symbols": ["F", "m", "a"],
  "term_aliases": { "net-force": "net force", "forces": "force" }
}
```
```text
L1 term handling:
- Only tokens the domain tokenizer classifies as TECHNICAL are checked; ordinary words are never rejected merely
  for being absent. Aliases/plurals/hyphenation normalize before lookup.
- A card may introduce a term only if it's a registered introduced_term AND the card is its designated intro point.
- Unknown candidate technical tokens are logged with tokenizer confidence: HIGH-confidence unknown ⇒ hard fail;
  LOW-confidence ⇒ proceed to L4 / a controlled review path (no unconditional hard-fail until the tokenizer is proven).
```

### L2 — symbolic/numeric sanity (deterministic, domain-aware)
When a claim contains a checkable relation, classify it — evaluation alone is unsafe (`x² = −4` is false over ℝ,
satisfiable over ℂ). Every relation declares or inherits a `symbolic_domain: real | complex | integer | natural |
adapter_defined`:
```text
L2 relation classes:
1. Ground relation — all symbols bound to authoritative values → evaluate in the sealed namespace
   (_eval, no __builtins__) with the shared numeric normalization (trace-to-teaching §5). Refuted ⇒ hard fail.
2. Symbolic identity / implication — variables free → validate ONLY via a deterministic symbolic rule / algebra
   engine / adapter-provided transformation proof, under the declared symbolic_domain. Refuted ⇒ hard fail.
3. Extractable but underdetermined — parses but cannot be proven/refuted under the declared domain → L2 returns
   INDETERMINATE; the field falls to L4 (never a hard fail merely for lacking bindings).
```
So `x²=−4 ⇒ (x)²=0` is refuted by the symbolic rule (class 2), not by guessing a binding; a complex-valid relation
under a `complex` domain is **not** rejected.

### L3 — sibling-trace consistency (deterministic)
If the topic has a verified example trace, free-text prose must not contradict it. Reuse the applicable
trace-to-teaching checks (incl. §10.1 per-quantity attribution + `(trace_id, trace_step_id, output_name|fact_id)`
identity):
```text
- C1 for values · C2 for forbidden claims · C4 for quantity↔unit pairings ·
- C5 when the free-text field asserts an action / method / rule order.
L3 does NOT require every free-text card to describe an operation; C5 applies only to action-bearing claims under
the active narration contract.
```
This catches prose that teaches the wrong method next to a correct worked example ("first isolate acceleration"
beside a substitute-into-F=ma example) even with no numeric/unit conflict. Contradiction ⇒ **hard fail**.

### L4 — bounded risk classifier (reject/downgrade-only, NEVER certifying)
For claims unsettled by L1–L3 (definitions, attributions, "always/never"), a bounded verifier returns a **risk
class**, not a truth certificate:
```text
L4 verdict:  refuted | unsupported | no_objection
- refuted     — conflicts with established knowledge or the stated contract → repair, else withhold.
- unsupported — a factual assertion that cannot be established from allowed evidence → soften or withhold.
- no_objection— no detected contradiction, but NOT certified true → may ship ONLY if the claim is already
                classified as non-factual framing, a bounded pedagogical prompt, or deterministic content whose
                factual basis is carried elsewhere. `no_objection` NEVER promotes an unsupported factual assertion.
```
"Supported" is deliberately **not** a verdict — L4 must never turn "the LLM believes this" into shippable fact.
The verifier degrades safely (treated as unavailable) on error/malformed output; when unavailable, the
deterministic rungs decide and any unsettled factual assertion is softened/withheld, not shipped.

---

## 4. Outcomes — block, soften, or withhold (never certify)

```
field verdict:
  L1–L3 pass, L4 ∈ {no_objection, n/a}     → SHIP (no_objection only for non-factual framing / bounded prompt /
                                              deterministic-content-carried-elsewhere; never a bare factual assertion)
  hard fail (L1 scope / L2 symbolic / L3)   → REPAIR (regenerate field, max 2) → still failing → WITHHOLD field
  L4 refuted                                → REPAIR → still refuted → WITHHOLD field
  L4 unsupported factual assertion          → SOFTEN (deterministically, below) or WITHHOLD
```

**Softening is a deterministic operation, not open-ended rewriting** (v1):
```text
- Preferred action: DELETE the unsupported/refuted sentence.
- Permitted replacement: an existing authoritative/derivable sentence from the card contract, OR a registered
  deterministic template (e.g. one backed by a termination-proof field).
- NOT permitted: an LLM-authored replacement factual sentence.
- Optional framing may remain only if explicitly classified non-factual (no technical/causal assertion).
Example — "This always terminates because the recursion reduces the problem size." → DELETE, or use a template
backed by a termination proof. Do NOT replace with "This generally tends to finish efficiently" (softer, still
unsupported).
```
- **Withhold at field granularity** where possible (drop the offending sentence/definition), escalating to the
  **card** only when the field is the card's reason to exist (e.g. an `edge_case` whose sole assertion is refuted).
- A withheld **required** card follows the Phase-2 §2.1 rule (withholds the family from `on_enforced`, no generic
  fallback) and the trace-to-teaching §12 frontend contract (typed failure, no placeholder, not marked complete).

**Layered result** (mirrors trace-to-teaching §10):
```text
FreeTextValidationResult {
  deterministic: { l1_scope, l2_symbolic, l3_sibling: pass|fail|indeterminate,
                   out_of_scope_terms[], refuted_relations[], symbolic_domain }
  semantic:      { l4: refuted | unsupported | no_objection | unavailable, span?, verifier_available }
  decision:      ship | repair | soften | withhold
  failures:      [ typed, most-severe first ]
  telemetry:     { topic_id, card_type, field, rung, verdict, action, retry_count }
}
```

---

## 5. Flag + rollout

Integrates with `AZALEA_DOMAIN_NARRATION_V2` (no separate flag), mirroring trace-to-teaching:
- `shadow_validate` — run L1–L4, **log** verdicts, don't alter display (measure a family's current false-claim rate).
- `on_enforced` — enforce §4 (block/soften/withhold).

**Exact ship rule (narration §12).** Phase 2 may ship domain labels/templates/layouts before this spec is fully
implemented **only when every truth-bearing value is adapter/trace-backed**. Any generated explanatory claim,
justification, interpretation, or edge-case assertion **outside authoritative metadata** must be **blocked,
deferred, or validated here** before release. **No claim that "the domain system solves factual correctness" may
be made outside verified adapter-backed examples.**

---

## 6. Minimum vertical slice (one fixture, end-to-end)

```text
Minimum vertical slice — a math concept card with a false symbolic claim
Field:  concept_intuition body contains "since x² = −4, we get (x)² = 0"
Expected:
  - L2 classifies this as a symbolic implication (class 2, variables free) under symbolic_domain=real and refutes
    it via the deterministic symbolic rule — NOT by guessing a binding
  - decision = repair; after 2 failed repairs → withhold the field (sentence deleted deterministically)
  - in shadow_validate: legacy display unchanged, verdict logged
  - no legacy/frontend recovery path certifies the claim; L4 is not consulted to "support" it
```

---

## 7. Acceptance-test table (executable contract)

| Test | Fixture | Expected assertion |
|---|---|---|
| `test_l1_rejects_out_of_scope_term` | prose uses a term not assumed/taught | hard fail L1; term in `out_of_scope_terms` |
| `test_l2_rejects_false_symbolic_claim` | "x² = −4 ⇒ (x)² = 0" | hard fail L2 (refuted relation) |
| `test_l2_accepts_true_relation` | "since a = 2, a² = 4" | pass L2 |
| `test_l2_skips_non_extractable` | prose with no clean relation | L2 pass; falls to L4 |
| `test_l3_rejects_contradicting_sibling_example` | prose value conflicts with the topic's worked example | hard fail L3 |
| `test_l4_downgrades_unverifiable_definition` | plausible but unverifiable definition asserted as fact | soften (sentence dropped/reduced) |
| `test_l4_rejects_refuted_definition` | "a stack is FIFO" | repair → withhold field |
| `test_l4_unavailable_degrades_safely` | verifier unavailable | deterministic rungs decide; L4 skipped, logged |
| `test_soften_never_produces_vaguer_falsehood` | refuted claim | output is dropped/scoped, not a hedged version of the false claim |
| `test_soften_uses_only_registered_or_authoritative_replacement` | softened field | deleted or replaced deterministically; never newly-generated factual prose |
| `test_l2_indeterminate_symbolic_relation_falls_to_l4` | parsed but underdetermined relation | not a hard fail for lacking bindings; → L4 |
| `test_l2_uses_declared_symbolic_domain` | relation valid over ℂ under a complex-domain contract | not rejected |
| `test_l4_no_objection_does_not_certify_factual_claim` | unsupported factual claim, L4=no_objection | not shippable as fact (softened/withheld) |
| `test_l1_does_not_reject_nontechnical_prose` | ordinary wording | not flagged as an out-of-scope technical term |
| `test_l3_rejects_operation_conflict_with_sibling_trace` | prose method conflicts with the trace (no numeric conflict) | hard fail L3 via C5 |
| `test_withhold_required_card_blocks_family` | required card, hard fail, on_enforced | topic/family path withheld; no generic fallback |
| `test_shadow_logs_without_user_impact` | same failure, shadow_validate | legacy display remains; typed telemetry emitted |

---

## 8. Regression fixtures

```text
fixtures/free_text/
  false_symbolic_claim.json         # x²=−4 ⇒ (x)²=0 (L2)
  out_of_scope_term.json            # L1
  wrong_definition_stack_fifo.json  # L4 refuted
  overreaching_edge_case.json       # "this always terminates" (L4)
  contradicts_sibling_example.json  # L3 (value/unit)
  operation_conflict_sibling.json   # L3 via C5 (wrong method beside a correct example)
  unsupported_asserted_as_fact.json # L4 soften
  indeterminate_symbolic_relation.json # L2 class 3 → L4
  complex_domain_relation_ok.json   # L2 class 2, symbolic_domain=complex, not rejected
```

---

## 9. Expected implementation surface

```text
Expected to change:
- free_text validator module (L1–L4 + FreeTextValidationResult)
- topic-level vocabulary object (assumed_prerequisite_terms/introduced_terms/approved_operations/symbols/aliases)
  + a domain tokenizer that classifies technical vs. ordinary tokens with confidence
- L2 relation classifier + symbolic rule/algebra engine (or adapter transformation proof) with symbolic_domain
- L3 reuse of trace-to-teaching C1/C2/C4 + C5 for action-bearing free-text
- bounded verifier client returning refuted|unsupported|no_objection (reject/downgrade-only)
- deterministic softener (delete / registered-template / authoritative-sentence replacement only)
- generation retry/soften coordinator
- rollout gate integration + per-field telemetry emitter
- frontend field/card withhold state (shared with trace-to-teaching §12)
- fixture directories (§8)

MUST NOT become a source of truth:
- the L4 verifier (reject/downgrade only; NEVER certifies or authors a claim; "supported" is not a verdict)
- softening that produces a vaguer version of a false claim, or any LLM-authored replacement factual prose
- sealed-eval "truth" for free-variable relations (those need the symbolic rule under a declared domain)
- frontend recovery / legacy narration fallback in on_enforced mode
```

---

## 10. Definition of done

- [ ] The §6 false-symbolic-claim slice is caught by L2 and withheld after failed repair, end-to-end.
- [ ] L1 rejects an out-of-scope term against the Phase-0 topic contract.
- [ ] L2 refutes `x²=−4 ⇒ (x)²=0` via the symbolic rule (class 2), accepts true relations, marks underdetermined
  relations INDETERMINATE (→ L4, not hard-fail), and honors the declared `symbolic_domain` (complex-valid not rejected).
- [ ] L3 rejects prose contradicting the topic's verified example — values/units (C1/C4) **and** a conflicting
  method/rule-order (C5 for action-bearing free-text).
- [ ] L4 returns `refuted | unsupported | no_objection` only — **never certifies**; `no_objection` cannot promote
  an unsupported factual assertion to shippable fact; degrades safely when the verifier is absent.
- [ ] L1 checks only tokenizer-classified technical terms against the topic vocabulary object; ordinary prose is
  never rejected; low-confidence unknowns go to L4/review, not an unconditional hard-fail.
- [ ] Softening is deterministic (delete / registered template / authoritative sentence); never LLM-authored
  replacement prose; never a vaguer falsehood; withholding is field-granular where possible.
- [ ] `shadow_validate` logs verdicts without user impact; `on_enforced` enforces block/soften/withhold.
- [ ] A withheld required card blocks the topic/family and reuses the trace-to-teaching frontend contract.
- [ ] A family's free-text false-claim rate is measured in `shadow_validate` before `on_enforced`.
- [ ] `GenerationPathTelemetry` (shared with trace-to-teaching §15) shows no legacy/frontend-recovery path certified
  a softened/withheld claim — asserted by instrumentation, not code review.

## 11. Non-goals & relationship

- **Not** a general-purpose fact-checker or a claim of universal correctness — it **bounds risk** on free text,
  biased toward withholding.
- **Not** validation of trace-backed values — that is `TRACE_TO_TEACHING_CONTRACT_SPEC` (the §2 split is strict).
- **Not** a Phase-0/Phase-2 routing or shape concern.
- Together the companions close the loop: **trace-to-teaching** keeps trace-backed prose faithful to the trace;
  **free-text validation** bounds the claims that have no trace. Phase 2 `on_enforced` for a family requires
  **both** clean in `shadow_validate`.
