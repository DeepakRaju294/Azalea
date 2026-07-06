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
deterministic and preferred; L4 handles the residue and is **never the sole basis for shipping** a claim, only for
catching/softening one.

- **L1 — scope adherence (deterministic).** Every technical term used appears in `assumed_prerequisites` ∪ the
  concepts taught on this topic (the Phase-0 topic contract). An out-of-scope term ⇒ **hard fail** (narration §3
  "never introduce a term outside what's assumed/taught"). Term extraction uses the same tokenizer as the topic
  contract; an unknown technical token fails closed rather than being ignored.
- **L2 — extractable symbolic/numeric sanity (deterministic).** When a claim contains a checkable
  equation/relation, extract it and **evaluate in the sealed namespace** used by the trace engines (`_eval`, no
  `__builtins__`) with the **shared numeric-normalization contract** (trace-to-teaching §5). A refuted relation ⇒
  **hard fail**. This rung catches `x² = −4 ⇒ (x)² = 0`. Fires **only** when a relation is cleanly extractable —
  never guesses; a non-extractable statement passes L2 and falls to L4.
- **L3 — sibling-trace consistency (deterministic).** If the topic has a verified example trace, free-text prose
  must not contradict its authoritative values/units/operations (reuse trace-to-teaching C1/C2/C4, **including its
  §10.1 per-quantity unit attribution + `(trace_id, trace_step_id, output_name|fact_id)` identity** — a free-text
  value only conflicts when it disagrees with the *same* step's authoritative value). Disagreeing with the topic's
  own worked example ⇒ **hard fail**.
- **L4 — definitional / claim check (bounded verifier, reject-biased).** For claims unsettled by L1–L3
  (definitions, attributions, "always/never" assertions), a bounded verifier returns
  `supported | refuted | unverifiable` + span, with a **conservative prior**: `unverifiable` is *not established*.
  The verifier may **reject or downgrade**, never upgrade an unverifiable claim to fact; degrades safely (treated
  as unavailable) on error/malformed output.

---

## 4. Outcomes — block, soften, or withhold (never certify)

```
field verdict:
  clean (L1–L3 pass, L4 not-refuted)        → SHIP
  hard fail (L1 scope / L2 symbolic / L3)   → REPAIR (regenerate field, max 2) → still failing → WITHHOLD field
  L4 refuted                                → REPAIR → still refuted → WITHHOLD field
  L4 unverifiable claim of fact             → SOFTEN: drop the sentence / reduce to a taught-scope statement
```

- **Soften** = remove the assertion-of-fact framing (drop the sentence, or reduce to a taught-scope statement) —
  **never** rephrase a false claim into a vaguer false claim.
- **Withhold at field granularity** where possible (drop the offending sentence/definition), escalating to the
  **card** only when the field is the card's reason to exist (e.g. an `edge_case` whose sole assertion is refuted).
- A withheld **required** card follows the Phase-2 §2.1 rule (withholds the family from `on_enforced`, no generic
  fallback) and the trace-to-teaching §12 frontend contract (typed failure, no placeholder, not marked complete).

**Layered result** (mirrors trace-to-teaching §10):
```text
FreeTextValidationResult {
  deterministic: { l1_scope, l2_symbolic, l3_sibling: pass|fail, out_of_scope_terms[], refuted_relations[] }
  semantic:      { l4: supported|refuted|unverifiable, span?, verifier_available }
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
  - L2 extracts x² = −4 and (x)² = 0, evaluates in the sealed namespace, finds them inconsistent
  - decision = repair; after 2 failed repairs → withhold the field (sentence dropped)
  - in shadow_validate: legacy display unchanged, verdict logged
  - no legacy/frontend recovery path certifies the claim
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
  contradicts_sibling_example.json  # L3
  unverifiable_asserted_as_fact.json# L4 soften
```

---

## 9. Expected implementation surface

```text
Expected to change:
- free_text validator module (L1–L4 + FreeTextValidationResult)
- scope-adherence checker wired to the Phase-0 topic contract (assumed_prerequisites ∪ taught concepts)
- extractable-relation checker reusing the sealed eval + shared numeric normalization (trace-to-teaching §5)
- bounded verifier client (reject/downgrade-only)
- generation retry/soften coordinator
- rollout gate integration + per-field telemetry emitter
- frontend field/card withhold state (shared with trace-to-teaching §12)
- fixture directories (§8)

MUST NOT become a source of truth:
- the L4 verifier (reject/downgrade only; never certifies or authors a claim)
- softening that produces a vaguer version of a false claim
- frontend recovery / legacy narration fallback in on_enforced mode
```

---

## 10. Definition of done

- [ ] The §6 false-symbolic-claim slice is caught by L2 and withheld after failed repair, end-to-end.
- [ ] L1 rejects an out-of-scope term against the Phase-0 topic contract.
- [ ] L2 catches the `x²=−4` class and accepts true relations; non-extractable statements fall through cleanly.
- [ ] L3 rejects prose contradicting the topic's own verified example (reusing trace-to-teaching C1/C2/C4).
- [ ] L4 is reject/downgrade-only, conservative on `unverifiable`, and degrades safely when absent.
- [ ] Softening never emits a vaguer falsehood; withholding is field-granular where possible.
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
