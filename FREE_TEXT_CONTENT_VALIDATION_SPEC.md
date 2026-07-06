# Free-Text Content Validation Spec — Companion (Q24)

> **Purpose.** The domain gate fixes *shape*; the trace-to-teaching contract keeps *trace-backed* prose honest.
> Neither can stop a **false claim on a card that has no trace to check against** — a background paragraph, a
> concept explanation, an edge-case assertion, a "why it matters" line. The gate cannot catch
> `x² = −4 → (x)² = 0`. This companion defines how such **free-text** content is factually checked before it
> ships.
>
> Companion to `DOMAIN_CARD_NARRATION_AND_RENDERING_SPEC.md` (§12). Sibling: `TRACE_TO_TEACHING_CONTRACT_SPEC.md`
> (the trace-backed half). **Clean split:** a value/claim with a verified trace → trace-to-teaching; a claim with
> **no** trace → here.

---

## 1. The problem this owns

Verified adapters back only a subset of cards (a worked example, a formula breakdown). The rest of a lesson is
**free text**: `background`, `concept_intuition`, `components_terms` definitions, `edge_case` assertions,
`practice` prompts, "why this matters" framing. These carry real factual risk that no upstream layer catches:
- a **false mathematical claim** in prose (`x² = −4 ⇒ (x)² = 0`, "the derivative of a constant is the constant");
- a **wrong definition** ("a stack is FIFO");
- an **overreaching edge case** ("this always terminates") or a **misattributed rule/law**;
- a claim that **contradicts the card's own verified example** (prose says one thing, the adapter example another).

Because there is no trace, this layer is **conservative by construction**: when it cannot establish a claim, it
**withholds or softens** the claim — it never certifies it. **No card may present unverified free text as
established fact.**

---

## 2. Scope — what is "free text"

Applies to any card **field** not covered by the trace-to-teaching field ledger (§3 there):

| In scope (validated here) | Out of scope (owned elsewhere) |
|---|---|
| `background` prose · `concept_intuition` body · `components_terms` definitions · `edge_case` assertions · `practice` prompt correctness · "why it matters" / interpretation framing | any `authoritative`/`derivable` trace value (→ trace-to-teaching) · topic-type routing (→ Phase 0) · card presence/shape (→ Phase 2 gate) |

A card may be **mixed**: its trace-backed fields go through trace-to-teaching, its free-text fields through this
spec. A field is never validated by both.

---

## 3. The validation ladder (cheapest, most-certain first)

Each free-text field runs the applicable rungs in order; the **strongest applicable** verdict wins.

- **L1 — scope adherence (deterministic).** Every technical term used appears in `assumed_prerequisites` ∪ the
  concepts taught on this topic (Phase-0 topic contract). An out-of-scope term is a **fail** (the narration §3
  rule "never introduce a term outside what's assumed/taught"). Cheap, high-precision.
- **L2 — extractable symbolic/numeric sanity (deterministic).** When a claim contains a checkable equation/relation
  (`a = b`, `x² = c`, a numeric statement), extract and **evaluate it in the sealed namespace** already used by
  the trace engines (`_eval`, no `__builtins__`). A refuted relation is a **hard fail**. This is the rung that
  catches `x² = −4 ⇒ (x)² = 0`. Only fires when a relation is cleanly extractable — never guesses.
- **L3 — sibling-trace consistency (deterministic).** If the topic has a verified example trace, the free-text
  prose must not contradict its authoritative values/units/operations (reuse trace-to-teaching C1/C2/C4). Prose
  that disagrees with the topic's own worked example is a **hard fail**.
- **L4 — definitional / claim check (bounded verifier, reject-biased).** For claims not settled by L1–L3
  (definitions, attributions, "always/never" edge assertions), a bounded verifier returns
  `supported | refuted | unverifiable` **+ span**, with a **conservative prior**: `unverifiable` is treated as
  *not established*. The verifier may **reject or downgrade**, never upgrade an unverifiable claim to fact.

L1–L3 are deterministic and preferred; L4 handles the residue and is never the sole basis for *shipping* a claim,
only for catching/softening one.

---

## 4. Outcomes — block, soften, or withhold (never certify)

```
field verdict:
  clean (L1–L3 pass, L4 not-refuted)        → SHIP
  hard fail (L1 scope / L2 symbolic / L3)   → REPAIR (regenerate field, max 2) → still failing → WITHHOLD field
  L4 refuted                                → REPAIR → still refuted → WITHHOLD field
  L4 unverifiable claim of fact             → SOFTEN: downgrade to hedged/omitted, OR drop the sentence
```

- **Soften** = remove the assertion-of-fact framing (drop the sentence, or reduce to a taught-scope statement) —
  **not** rephrasing a false claim into a vaguer false claim.
- **Withhold at field granularity** where possible (drop the offending sentence/definition), escalating to the
  **card** only if the field is the card's reason to exist (e.g. an `edge_case` whose sole assertion is refuted).
- A withheld **required** card follows the Phase-2 §2.1 rule (withholds the family from `on_enforced`, no generic
  fallback).
- Telemetry per field: `card_type · field · rung · verdict · action · retries`.

---

## 5. Ship rule + rollout

Integrates with `AZALEA_DOMAIN_NARRATION_V2` (no separate flag), mirroring trace-to-teaching:
- `shadow_validate` — run L1–L4, **log** verdicts, don't alter display (measure the false-claim rate a family
  currently ships).
- `on_enforced` — enforce §4 (block/soften/withhold).

**Exact ship rule (from narration §12).** Phase 2 may ship domain labels/templates/layouts before this spec is
fully implemented **only when every truth-bearing value is adapter/trace-backed**. Any generated explanatory
claim, rule justification, interpretation, or edge-case assertion **outside authoritative metadata** must be
**blocked, deferred, or validated here** before release. **No claim that "the domain system solves factual
correctness" may be made outside verified adapter-backed examples.**

---

## 6. Definition of done

- [ ] L1 scope-adherence check wired to the Phase-0 topic contract (`assumed_prerequisites` ∪ taught concepts).
- [ ] L2 extractable-relation checker on the sealed eval namespace; unit-tested on the `x²=−4` class + true relations.
- [ ] L3 sibling-trace consistency reuses trace-to-teaching C1/C2/C4 when a topic example exists.
- [ ] L4 bounded verifier is **reject/downgrade-only**, conservative on `unverifiable`; degrades safely when absent.
- [ ] §4 outcomes (repair → withhold/soften) integrated with rollout modes + per-field telemetry.
- [ ] A family's free-text false-claim rate is measured in `shadow_validate` before `on_enforced`.
- [ ] No unverified free text is presented as established fact; softening never produces a vaguer falsehood.

## 7. Non-goals & relationship

- **Not** a general-purpose fact-checker or a claim of universal correctness — it **bounds risk** on free text,
  biased toward withholding.
- **Not** validation of trace-backed values — that is `TRACE_TO_TEACHING_CONTRACT_SPEC` (the split in §2 is strict).
- **Not** a Phase-0/Phase-2 routing or shape concern.
- Together the two companions close the loop: **trace-to-teaching** keeps trace-backed prose faithful to the
  trace; **free-text validation** bounds the claims that have no trace. Phase 2 `on_enforced` for a family
  requires **both** clean in `shadow_validate`.
