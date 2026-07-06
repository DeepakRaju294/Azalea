# Trace → Teaching Contract Spec — Companion (Q23)

> **Purpose.** The domain gate (Phase 0) + narration contracts (Phase 2) produce **better-shaped** content, but
> shape is not truth. This companion defines how a card's **prose** is allowed to derive from a verified adapter
> **trace**, how a **prose-vs-example contradiction** is detected, and what **blocks shipping**. It is the
> correctness gate that lets Phase 2 move a family from `shadow_validate` to `on_enforced` with *explanatory
> prose* — not just bare adapter values.
>
> Companion to `DOMAIN_CARD_NARRATION_AND_RENDERING_SPEC.md` (§12). Sibling: `FREE_TEXT_CONTENT_VALIDATION_SPEC.md`
> (the other half — claims with **no** trace to check against).

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
and **before** display; a violation blocks/repairs the card (§6).

---

## 2. The real trace grammar (author against payloads, not theory)

Grounded in the live type-engines (`app/services/examples/trace_adapters/families/*_engine.py`). Every engine
emits the same **step grammar**, so this contract keys off the grammar, not per-adapter data:

```
Step {
  id                      # "s1", "s2", …
  operation               # the operation tag: "identify_knowns", "compute_force", "completion"
  prior_state             # dict — state before this step
  state_after             # dict — state after
  visual_state            # e.g. {"kind": "equation", "<name>": <value>}
  expected_visible_result # the visible result string of the step (e.g. "F = 20 N")
  facts {
    allowed_values        # the ONLY literal numbers prose may use in this step
    required_facts        # facts the step's prose MUST state (kind + content)
    forbidden_claims      # claims the step's prose MUST NOT make
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
template; `connective` prose ships only if it passes §5 validation; `out-of-contract` claims are **removed** from
the trace-backed card (they are the free-text spec's domain, not this one).

---

## 4. Per-card derivation contract

How each `defined` card derives from the trace (framing labels come from the Phase-2 narration contracts; values
from here):

- **`worked_example` step** — one `Step` → one card. `work` = `expected_visible_result` / substituted `equation`
  (authoritative). `result` = `state_after`/`Output` value + `unit` (authoritative). `reasoning` = a `derived`
  line naming the `operation`/`Output.equation` (the rule), **not** free prose. `goal` = connective, validated.
  Step **titles describe the action** (`operation`), never the rule name (narration §3 rule 4).
- **`process` card** — the scaffold steps (`Setup→Operation→Result→Why` etc.) map to the ordered
  `required_operations`; each stage's content is `derived` from the corresponding step(s) via the `evidence` map.
  The "Why" line is **connective** and must cite an `Output.teaching_focus`/`operation`, validated by §5.
- **`formula_breakdown` (math)** — `rule` ← `operation`/`Output.equation` (authoritative); `form` ←
  `expected_visible_result`/`state_after` (authoritative); `parts`/`transformation`/`why` are connective + §5.
- **completion / terminal** — the `completion` operation + `terminal_condition` mark the final card; result lines
  are **terminal, not narrated** (narration §3 rule 5).

Any field a card needs that is neither authoritative nor derivable for the active adapter (e.g. science
`interpretation`, blocked by the §4 `quantity_kind` gap) is **omitted**, never connective-generated.

---

## 5. Contradiction detection (prose ⟂ trace)

A drafted card passes only if **all** hold. Checks are ordered cheapest-first; the first hard failure stops the
card (§6). All are deterministic except C6.

- **C1 — value containment.** Every number in the card's prose is in that step's `facts.allowed_values` (∪ the
  step's authoritative values). A literal not in the allowed set is an **invented value** → hard fail. (Directly
  catches the `x²=−4 → (x)²=0` class *when a trace exists*.)
- **C2 — forbidden claims.** The prose asserts none of `facts.forbidden_claims` (string/pattern match) → hard fail.
- **C3 — required facts.** The prose states every `facts.required_facts` for that step (by `fact_kind`) → else
  repairable fail (retry to add it).
- **C4 — unit fidelity.** Any unit token in prose equals `Output.unit` (no invented/converted units) → hard fail.
- **C5 — operation/order fidelity.** The card's claimed action matches its `Step.operation`, and card order
  respects `required_operations` order → hard fail on mismatch.
- **C6 — semantic non-contradiction (bounded LLM judge, last).** A cheap verifier is asked *only*: "does this
  sentence contradict {authoritative facts}?" with a **yes/no + offending span**. It may **only reject**, never
  add facts. Runs last, on prose that already passed C1–C5.

**Prose-vs-example contradiction** = any C1/C2/C4/C5 failure between a card's sentence and the step it renders, or
between two cards citing the same `operation` with different authoritative values. C6 covers the residual
"technically uses allowed numbers but the sentence still misleads" case.

---

## 6. Retries + block conditions

```
draft card → C1..C6
  all pass                         → SHIP
  repairable fail (C3, some C6)    → targeted regenerate (max 2), re-validate
  hard fail after retries          → per rollout mode:
      on_enforced  → WITHHOLD the card with typed error trace_teaching_violation:<check>
      shadow_validate → keep legacy display, log the violation (no user impact)
```

- **Never** ship a card that fails C1/C2/C4/C5 — no "soften and continue."
- **Never** downgrade a required trace-backed value to connective prose to dodge a check.
- A withheld **required** card withholds the topic-type/family from `on_enforced` (§2.1) — it does not silently
  drop to generic narration.
- Every outcome emits telemetry: `card_type · operation · check · outcome · retries` (feeds the §9.1 per-family
  validation telemetry).

---

## 7. Coverage (which trace grammars are contracted)

Keyed to the live engines, not individual adapters:

| Engine | Grammar | Trace-to-teaching status |
|---|---|---|
| **T6 formula** | substitute → compute → result+units | **primary target** (completing-the-square-adjacent, Newton); C1–C5 fully apply |
| **T7 rewrite** | one allowed rule per step → normal form | applies; `operation` = the rewrite rule, `expected_visible_result` = the rewritten form |
| **T8a construction** | add one valid piece per step | applies; `state_after` = the growing structure |
| **T8b derivation** | each step justified by a named rule | applies; `operation` = the named law (ideal for `formula_breakdown`/`proof_plan`) |
| **coding (execution trace)** | line → state delta | already the shipped verified path; this contract formalizes it as the regression baseline |

Because the grammar is uniform, **adding more adapter data rows does not expand this contract** — it widens how
many topics it covers (see the sequencing note in the program overview / this PR description).

---

## 8. Flag + rollout

Trace-to-teaching validation is **part of the `on_enforced` gate** under `AZALEA_DOMAIN_NARRATION_V2`:
- `off_legacy` — not run.
- `shadow_validate` — run C1–C6, **log** violations, **do not** alter display (this is how a family earns
  `on_enforced`: its shadow violation rate must be ~0).
- `on_enforced` — run C1–C6; a hard fail **withholds** the card (§6).

No separate flag: a family cannot reach `on_enforced` prose until its shadow trace-teaching violation rate is
clean, which is exactly the gate this provides.

---

## 9. Definition of done

- [ ] Field ledger (§3) implemented: each teaching field classified authoritative/derivable/connective/out-of-contract.
- [ ] Per-card derivation (§4) wired for `worked_example`/`process`/`formula_breakdown` on the T6 grammar first.
- [ ] C1–C5 deterministic checks implemented + unit-tested against real T6 traces (completing-the-square, Newton).
- [ ] C6 bounded judge implemented as **reject-only**, never fact-adding; disabled if unavailable (fail toward C1–C5).
- [ ] Retry/withhold (§6) integrated with the §9.1 rollout modes + per-family telemetry.
- [ ] A family enters `on_enforced` only after a clean `shadow_validate` trace-teaching violation rate.
- [ ] Out-of-contract claims are removed from trace-backed cards and routed to `FREE_TEXT_CONTENT_VALIDATION`.

## 10. Non-goals

- **Not** a change to adapter computation, trace state, or expected answers (§11 of the narration spec holds).
- **Not** factual validation of claims with **no** trace basis — that is `FREE_TEXT_CONTENT_VALIDATION_SPEC`.
- **Not** a general fact-checker: it only enforces consistency **with a verified trace that already exists**.
