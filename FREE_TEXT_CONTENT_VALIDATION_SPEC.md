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
> **Core stance:** conservative by construction. When a **factual** claim cannot be established, this layer
> **withholds or softens** it — it never certifies. **Non-factual framing** may ship only when it passes scope
> checks and carries no technical or causal assertion. No card may present unverified free text as established fact.

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

**The validation unit is a CLAIM SPAN, not the whole field.** A single field ("A stack uses LIFO order. It is
useful for function calls. This always improves performance.") holds several claims with different verdicts:
```text
Claim segmentation:
- A free-text field is split into ordered claim spans BEFORE L1–L4.
- Each span carries: claim_id · field · text_span · claim_class (factual | non_factual_framing | prompt) ·
  its L1–L4 result · evidence_context · disposition.
- Field disposition is COMPUTED from its claim dispositions:
    all claims ship            → ship field;
    only removable-claim fails → SOFTEN field by deleting/replacing ONLY those spans;
    a required claim fails      → repair or withhold the field/card.
```
This keeps the validator from deleting a whole concept card because one sentence is unsupported, while still
guaranteeing the unsupported sentence can't survive.

Each claim span runs the applicable rungs; the **strongest applicable** verdict wins. L1–L3 are deterministic and
preferred; L4 is a **risk classifier**, not a certifier — it may reject/downgrade but **never establishes a claim
as true**.

### L1 — scope adherence (deterministic)
Do not introduce terminology outside prerequisites or what the topic teaches (narration §3). Enforced against a
topic-level **vocabulary object**, so ordinary prose isn't mistaken for a technical term:
```json
{
  "assumed_prerequisite_terms": ["variable", "equation", "force"],
  "introduced_terms": [
    { "term_id": "net_force", "display": "net force", "intro_card_id": "concept_net_force_intro" },
    { "term_id": "newtons_second_law", "display": "Newton's second law", "intro_card_id": "law_intro" }
  ],
  "approved_operations": ["substitute", "compute"],
  "approved_symbols": ["F", "m", "a"],
  "term_aliases": { "net-force": "net force", "forces": "force" }
}
```
```text
L1 term handling:
- Only tokens the domain tokenizer classifies as TECHNICAL are checked; ordinary words are never rejected merely
  for being absent. Aliases/plurals/hyphenation normalize before lookup.
- A card may introduce a term only if it's a registered introduced_term AND the card is its designated intro point,
  matched by STABLE `intro_card_id` (never by card title/type/position — a reordered sequence must not change what
  terminology is allowed).
- Unknown candidate technical tokens are logged with tokenizer confidence: HIGH-confidence unknown ⇒ hard fail;
  LOW-confidence ⇒ proceed to L4 / a controlled review path (no unconditional hard-fail until the tokenizer is proven).
```

### L2 — symbolic/numeric sanity (deterministic, domain-aware)
When a claim contains a checkable relation, classify it — evaluation alone is unsafe (`x² = −4` is false over ℝ,
satisfiable over ℂ). Every relation declares or inherits a `symbolic_domain: real | complex | integer | natural |
adapter_defined`:
```text
L2 relation / claim classes:
1. Ground relation — all symbols bound to authoritative values → evaluate in the sealed namespace
   (_eval, no __builtins__) with the shared numeric normalization (trace-to-teaching §5). Refuted ⇒ hard fail.
2. Symbolic identity / implication — variables free, a genuine truth-conditional statement → validate ONLY via a
   deterministic symbolic rule / algebra engine / adapter proof, under the declared symbolic_domain. Refuted ⇒ hard fail.
3. Derivation / transformation claim — a source relation presented as transformed into a target ("since P, we get
   Q" as a STEP). The validator must NOT read this as material implication (that would make an impossible-premise
   step vacuously "true"); it checks whether the named/declared operation preserves the required relationship
   (below). Unjustified transform ⇒ hard fail.
4. Extractable but underdetermined — parses but cannot be proven/refuted under the declared domain → L2 returns
   INDETERMINATE; the field falls to L4 (never a hard fail merely for lacking bindings).
```
**Transformation validation (class 3).** A step is judged by whether its operation preserves the declared relation
under the domain — never by truth-table implication:
```text
- equivalence-preserving step  → source and target share the same solution set under the declared domain;
- implication-preserving step  → every solution of source satisfies target, AND the named operation justifies the
                                 directional loss of information;
- contradiction / no-solution  → the target must EXPLICITLY communicate the contradiction / empty solution set;
                                 it may not invent a new equation or conclusion.
A transformation with no registered algebraic operation justifying source→target ⇒ REFUTED.
```
So `x² = −4 ⇒ x² = 0` is a **class-3 transformation** and is **refuted** because no registered operation rewrites
`x²=−4` into `x²=0` and the (empty, over ℝ) solution set is not communicated — **not** treated as a vacuously-true
implication. A complex-valid relation under a `complex` domain is **not** rejected.

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
class**, not a truth certificate. It operates **only over a supplied evidence package** — not "ask a model what it
knows" (that would be an opaque source of truth):
```text
L4 allowed evidence (the ONLY inputs the verifier may use):
- the active topic vocabulary + registered definitions;
- adapter/trace facts when present;
- a VERSIONED domain fact-pack / rule registry;
- explicitly supplied source excerpts/citations for the topic.

L4 verdict:  refuted | unsupported | no_objection   (+ states n/a · unavailable)
- refuted     — a conflicting rule/fact/source is identified → repair, else withhold. MUST carry evidence_ids.
- unsupported — the supplied evidence does not establish the assertion → soften or withhold.
- no_objection— no contradiction found, but NOT certified true → may ship ONLY for non-factual framing / a bounded
                pedagogical prompt / deterministic content whose factual basis is carried elsewhere; NEVER promotes
                a bare unsupported factual assertion.
- n/a         — the field has NO unresolved factual assertion → L4 not needed (this is what allows a clean ship).
- unavailable — L4 was REQUIRED for an unresolved factual assertion but could not run.
```
"Supported" is deliberately **not** a verdict — L4 must never turn "the LLM believes this" into shippable fact.
**`n/a` (no factual assertion) and `unavailable` (couldn't run) are different**: `unavailable` on a factual
assertion → soften/withhold, never a clean pass; `unavailable` on non-factual framing may ship if L1–L3 pass.

**`no_objection` cannot override a claim's class.** L4 may emit `no_objection` **only** for a span whose
`claim_class` is `non_factual_framing`, `prompt`, or deterministic-content-carried-elsewhere. A span classified
**factual** must resolve as `refuted | unsupported | unavailable` — `no_objection` can never make a bare factual
assertion shippable (that removes the ambiguity of "the verifier didn't object, so ship it").

**Version pinning + reproducibility.** Every L4 invocation records the exact evidence it ran against, so a verdict
stays reproducible even after the fact-pack is later revised:
```text
EvidenceContext { fact_pack_id · fact_pack_version · definition_registry_version · source_excerpt_ids[] · trace_ids[] }
- Every L4 invocation records its EvidenceContext; a `refuted` verdict identifies evidence_ids FROM that context.
- Replaying the same card against the same EvidenceContext must yield the same deterministic evidence package
  (and verdict), independent of newer fact-pack versions.
```

**`unsupported` carries a reason** (it drives different rollout actions, not just "delete"):
```text
unsupported_reason:
- no_matching_evidence                            → normally soften/delete the sentence.
- insufficient_scope                              → soften/delete.
- conflicting_evidence_without_resolved_precedence→ a content-GOVERNANCE defect, not a generation bug (flag).
- evidence_pack_missing_for_domain                → keep the FAMILY in shadow_validate (don't just delete sentences).
```

---

## 4. Outcomes — block, soften, or withhold (never certify)

```
field verdict:
  L1–L3 pass, L4 == n/a                     → SHIP (no unresolved factual assertion exists)
  L1–L3 pass, L4 == no_objection            → SHIP ONLY for non-factual framing / bounded prompt /
                                              deterministic-content-carried-elsewhere; never a bare factual assertion
  hard fail (L1 scope / L2 symbolic / L3)   → REPAIR (regenerate field, max 2) → still failing → WITHHOLD field
  L4 refuted                                → REPAIR → still refuted → WITHHOLD field
  L4 unsupported factual assertion          → SOFTEN (deterministically, below) or WITHHOLD
  L4 unavailable, factual assertion         → SOFTEN or WITHHOLD (verifier outage is NOT a clean pass)
  L4 unavailable, non-factual framing       → SHIP if L1–L3 pass
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

**Layered result** — per claim span, with a computed field decision (mirrors trace-to-teaching §10):
```text
FreeTextValidationResult {
  field
  claims: [ {
    claim_id · span · claim_class: factual | non_factual_framing | prompt
    deterministic: { l1_scope, l2_symbolic, l3_sibling: pass|fail|indeterminate,
                     out_of_scope_terms[], refuted_relations[], symbolic_domain }
    semantic:      { l4: refuted | unsupported | no_objection | n/a | unavailable, span?,
                     unsupported_reason?, evidence_ids?[], evidence_context, verifier_available }
                     # evidence_ids REQUIRED on refuted; unsupported_reason set when l4 == unsupported
    decision:      ship | repair | soften | withhold
    failures:      [ typed, most-severe first ]
  } ]
  field_decision:  ship | repair | soften | withhold      # computed from the claim dispositions above
  telemetry:       { topic_id, card_type, field, claim_id, rung, verdict, unsupported_reason?, action,
                     retry_count, evidence_context }
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
Field:  concept_intuition body contains "since x² = −4, we get x² = 0"
Expected:
  - the field is segmented into claim spans; this span is classified a DERIVATION/TRANSFORMATION claim (L2 class 3)
  - L2 refutes it: no registered algebraic operation transforms x²=−4 into x²=0 under symbolic_domain=real, and the
    empty (over ℝ) solution set is not communicated — NOT read as a vacuously-true implication
  - claim decision = repair; after 2 failed repairs → soften by deleting THAT span (valid sibling claims survive);
    if the span is the field's reason to exist → withhold the field
  - in shadow_validate: legacy display unchanged, verdict logged
  - no legacy/frontend recovery path certifies the claim; L4 is not consulted to "support" it
```

---

## 7. Acceptance-test table (executable contract)

| Test | Fixture | Expected assertion |
|---|---|---|
| `test_l1_rejects_out_of_scope_term` | prose uses a term not assumed/taught | hard fail L1; term in `out_of_scope_terms` |
| `test_l2_rejects_invalid_symbolic_transformation` | "Since x² = −4, we get x² = 0." | hard fail L2 (class 3) — no registered algebraic rule justifies the transformation under the domain; not read as vacuous implication |
| `test_l2_accepts_true_symbolic_implication` | "If a = 2, then a² = 4." | pass L2 (class 2 implication under the declared domain) |
| `test_l2_accepts_true_ground_relation` | known a=2 (authoritative); prose "a² = 4" | pass L2 (class 1 ground) |
| `test_l2_skips_non_extractable` | prose with no clean relation | L2 pass; falls to L4 |
| `test_l3_rejects_contradicting_sibling_example` | prose value conflicts with the topic's worked example | hard fail L3 |
| `test_l4_downgrades_unverifiable_definition` | plausible but unverifiable definition asserted as fact | soften (sentence dropped/reduced) |
| `test_l4_rejects_refuted_definition` | "a stack is FIFO" | repair → withhold field |
| `test_l4_unavailable_factual_assertion_withholds` | factual assertion, verifier unavailable | soften/withhold — NOT a clean pass |
| `test_l4_na_non_factual_framing_ships` | field has no unresolved factual assertion (L4=n/a) | ship |
| `test_l4_refuted_carries_evidence_ids` | refuted definition | verdict includes `evidence_ids` |
| `test_l4_refuted_verdict_is_reproducible` | refuted definition vs a pinned fact-pack version | result carries `fact_pack_id`/`fact_pack_version`/`definition_registry_version`+`evidence_ids`; replay on same context → same verdict |
| `test_l4_unsupported_reason_pack_missing_holds_family` | domain has no fact-pack | `unsupported_reason=evidence_pack_missing_for_domain`; family stays shadow_validate (not per-sentence delete) |
| `test_soften_never_produces_vaguer_falsehood` | refuted claim | output is dropped/scoped, not a hedged version of the false claim |
| `test_soften_uses_only_registered_or_authoritative_replacement` | softened field | deleted or replaced deterministically; never newly-generated factual prose |
| `test_l2_indeterminate_symbolic_relation_falls_to_l4` | parsed but underdetermined relation | not a hard fail for lacking bindings; → L4 |
| `test_l2_uses_declared_symbolic_domain` | relation valid over ℂ under a complex-domain contract | not rejected |
| `test_l4_no_objection_cannot_override_claim_class` | span classified factual, verifier returns no_objection | not shipped as fact — resolved as unsupported unless deterministic/authoritative evidence establishes it |
| `test_claim_span_soften_keeps_valid_siblings` | 3-claim field; only the performance claim unsupported | delete/soften only that span; the LIFO definition + framing ship |
| `test_l2_equivalence_transform_passes` | "x + 2 = 5, so x = 3" (subtract 2) | pass L2 (equivalence-preserving, registered op) |
| `test_l1_does_not_reject_nontechnical_prose` | ordinary wording | not flagged as an out-of-scope technical term |
| `test_l3_rejects_operation_conflict_with_sibling_trace` | prose method conflicts with the trace (no numeric conflict) | hard fail L3 via C5 |
| `test_withhold_required_card_blocks_family` | required card, hard fail, on_enforced | topic/family path withheld; no generic fallback |
| `test_shadow_logs_without_user_impact` | same failure, shadow_validate | legacy display remains; typed telemetry emitted |

---

## 8. Regression fixtures

```text
fixtures/free_text/
  invalid_symbolic_transformation.json # "since x²=−4, we get x²=0" — L2 class 3, unjustified transform
  valid_equivalence_transform.json  # "x+2=5, so x=3" — L2 class 3 equivalence-preserving, passes
  multi_claim_field.json            # 3 claims, only one unsupported → span-level soften
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
- claim segmentation pass (field → ordered claim spans with claim_class) — the validation unit
- free_text validator module (L1–L4 per span + FreeTextValidationResult with per-claim results + field_decision)
- topic-level vocabulary object (assumed_prerequisite_terms/introduced_terms/approved_operations/symbols/aliases)
  + a domain tokenizer that classifies technical vs. ordinary tokens with confidence
- L2 relation classifier (ground / symbolic-identity / DERIVATION-transformation / underdetermined) + symbolic
  rule/algebra engine with registered algebraic operations + symbolic_domain (transformation preservation, not
  material implication)
- L3 reuse of trace-to-teaching C1/C2/C4 + C5 for action-bearing free-text
- versioned domain fact-pack / rule registry (L4's allowed evidence) + registered definitions, with per-generation
  EvidenceContext pinning (fact_pack_version / definition_registry_version / source_excerpt_ids / trace_ids)
- bounded verifier client returning refuted|unsupported(+reason)|no_objection|n/a|unavailable over the supplied
  evidence ONLY (reject/downgrade-only; refuted carries evidence_ids; verdicts reproducible against a pinned context)
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
- [ ] The validation unit is a **claim span**: a field is segmented before L1–L4; `field_decision` is computed
  from per-claim dispositions, so an unsupported span is softened/deleted without dropping valid sibling claims.
- [ ] L2 refutes `x²=−4 ⇒ x²=0` as a **class-3 transformation** (no registered algebraic operation justifies it;
  empty solution set not communicated) — **not** as a vacuously-true material implication; accepts a valid
  equivalence-preserving transform; marks underdetermined relations INDETERMINATE (→ L4); honors `symbolic_domain`.
- [ ] `no_objection` never ships a span whose `claim_class` is `factual`; such a span resolves refuted/unsupported/
  unavailable unless deterministic/authoritative evidence establishes it.
- [ ] L3 rejects prose contradicting the topic's verified example — values/units (C1/C4) **and** a conflicting
  method/rule-order (C5 for action-bearing free-text).
- [ ] L4 operates only over the supplied evidence package (vocabulary/definitions · trace facts · versioned
  fact-pack/rule registry · supplied sources); a `refuted` verdict carries `evidence_ids`; **never certifies**.
- [ ] Every L4 verdict records its `EvidenceContext` (fact-pack/definition-registry versions); a refuted verdict
  replays to the same result against the same pinned context.
- [ ] `unsupported` carries an `unsupported_reason`; `evidence_pack_missing_for_domain` holds the family in
  `shadow_validate` rather than deleting individual sentences.
- [ ] L4 `n/a` (no factual assertion) and `unavailable` (couldn't run) are distinct: a factual assertion with
  `unavailable` is softened/withheld, never a clean pass; only `n/a`/`no_objection`-framing ships.
- [ ] L1 checks only tokenizer-classified technical terms against the topic vocabulary object; ordinary prose is
  never rejected; term introduction is matched by stable `intro_card_id`, not position; low-confidence unknowns go
  to L4/review, not an unconditional hard-fail.
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
