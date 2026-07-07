# Free-Text Content Validation Spec — Companion (Q24)

> **Purpose.** The domain gate fixes *shape*; the trace-to-teaching contract keeps *trace-backed* prose honest.
> Neither can stop a **false claim on a card that has no trace to check against** — a background paragraph, a
> concept explanation, an edge-case assertion, a "why it matters" line. The gate cannot catch
> `x² = −4 → (x)² = 0`. This companion defines how such **free-text** content is factually checked before it
> ships.
>
> Companion to `DOMAIN_CARD_NARRATION_AND_RENDERING_SPEC.md` (§12). Sibling: `TRACE_TO_TEACHING_CONTRACT_SPEC.md`
> (the trace-backed half). **Clean split — assigned per CLAIM SPAN, not per field:** a trace-backed span → owned by
> trace-to-teaching; a free-text span → owned by this contract; a deterministic-carried span → owned by its
> registered source. A single UI field may contain spans from different ownership paths, but **no individual span
> is validated by more than one truth-owning path** (§2).
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

Applies to every claim span whose backend-assigned `content_ownership` is `free_text`. A UI field may contain a
mixture of trace-owned, deterministic-owned, and free-text spans; **this contract owns only the free-text spans**.
The card fields that TYPICALLY carry free-text spans (vs. what's owned elsewhere):

| In scope (validated here) | Out of scope (owned elsewhere) |
|---|---|
| `background` prose · `concept_intuition` body · `components_terms` definitions · `edge_case` assertions · `practice` prompt **prose** (terminology / unsupported claims / framing) · "why it matters" / interpretation framing | any `authoritative`/`derivable` trace value (→ trace-to-teaching) · topic-type routing (→ Phase 0) · card presence/shape (→ Phase 2 gate) · **practice PROBLEM correctness** (→ `PracticeProblemContract`, below) |

**Validation ownership is assigned per CLAIM SPAN, not per field.** A span is validated by exactly one
truth-owning path:
```text
- content_ownership trace_authoritative / trace_derivable  → trace-to-teaching;
- content_ownership free_text (factual / non_factual_framing / prompt) → this spec;
- content_ownership deterministic_carried_elsewhere        → its registered deterministic source.
```
A single UI field may contain spans owned by DIFFERENT paths (a trace-backed result sentence followed by a
free-text explanation), but **no individual span is validated by two truth-owning paths.** (Field routing is per
span; do not route a whole field wholesale to one validator.)

**`content_ownership` and `span_requirement` are BACKEND-derived, never generator-authored** (this is the last
bypass: if the model could self-label a span `deterministic_carried_elsewhere` or `optional`, a false claim would
dodge establishment / deletion):
```text
1. Generator-supplied content_ownership / span_requirement are NOT trusted payload — they are DISCARDED before
   routing (a model label is never a routing instruction).
2. Backend routing assigns ownership from registered mappings ONLY (field ledger / source mapping / deterministic
   template registry); span_requirement { optional | required | essential } from { narration_contract | card_schema
   | registered_template }.
3. Backend routing selects `deterministic_carried_elsewhere` but provenance { deterministic_source_id ·
   source_version · source_field } is missing/invalid → HARD ROUTING FAILURE: shadow_validate logs + retains the
   approved path; on_enforced withholds the span/field per its backend requirement. NEVER a silent free_text downgrade.
4. No backend mapping at all → the span is `free_text` and must establish normally (a discarded model label does
   NOT make it deterministic).
```

**Practice-problem correctness is NOT a free-text claim** (this validator must not silently become a
problem-generator validator). A generated practice prompt ("A 7 kg object accelerates at 3 m/s². Find the net
force.") has intentionally-new values that are NOT supposed to match a sibling trace; checking its *prose* for
unsupported claims does not establish that the problem has a valid, satisfiable answer:
```text
- Q24 checks a practice prompt's PROSE only: terminology (L1), unsupported claims (L4), framing.
- Practice PROBLEM correctness is owned by a `PracticeProblemContract` + its deterministic evaluator/adapter:
  { problem_id · domain/topic · generated_inputs · constraints · expected_answer|solver_contract ·
    accepted_solution_path(s) · unit/domain_assumptions · deterministic_evaluator · prompt_rendering_fields }.
- A practice prompt MUST NOT be treated as established just because Q24 raised no objection — it ships only when a
  PracticeProblemContract supplies a valid expected answer + deterministic constraint evaluation.
```
A narrow **bridge** (not a merge) carries the contract result into Q24's render decision. For any `claim_class ==
prompt` whose field is a practice prompt:
```text
PracticeBinding { practice_problem_id · practice_contract_version · practice_validation_status: valid|invalid|
                  unavailable · evaluator_id · evaluator_version }
Render eligibility (practice prompt) = Q24 prose validation passes
  AND PracticeBinding.practice_validation_status == valid
  AND the rendered inputs/units/expected-answer match the bound PracticeProblemContract.
Q24 `no_objection` alone is NEVER render eligibility for a generated practice problem.
```

---

## 3. The validation ladder (cheapest, most-certain first)

**The validation unit is a CLAIM SPAN, not the whole field.** A single field ("A stack uses LIFO order. It is
useful for function calls. This always improves performance.") holds several claims with different verdicts:
```text
Claim segmentation:
- EVERY validated text field is split into ordered claim spans BEFORE ownership routing + validation; each span is
  then dispatched to exactly ONE truth-owning path (trace-owned and deterministic spans are segmented too, not
  only after being called free text).
- Each span carries: claim_id · field · text_span · claim_class (factual | non_factual_framing | prompt |
  unclassified) · content_ownership (free_text | trace_authoritative | trace_derivable |
  deterministic_carried_elsewhere) · span_requirement (optional | required | essential) + requirement_source ·
  its L1–L4 result · evidence_context · disposition.
  (claim_class = what the span MEANS; content_ownership = where its truth COMES FROM; span_requirement = whether
  its failure deletes vs. withholds. All three are backend-derived — a deterministic sentence can be semantically
  factual yet not free-text truth this validator owns.)
- Field disposition is COMPUTED from its claim dispositions:
    all claims ship            → ship field;
    only removable-claim fails → SOFTEN field by deleting/replacing ONLY those spans;
    a required claim fails      → repair or withhold the field/card.
```
**Coverage contract (segmentation is the enforcement boundary — a missed clause is a bypass).**
```text
- Claim spans form an ORDERED, NON-OVERLAPPING cover of every non-whitespace character in the field.
- Every residual span is assigned factual | non_factual_framing | prompt | unclassified.
- `unclassified` residual text FAILS CLOSED: shadow_validate logs `segmentation_coverage_gap`; on_enforced repairs
  or withholds that span/field.
- A span may hold multiple atomic propositions ONLY when they share the same claim_class AND validation basis;
  otherwise it must be split (a definition + a performance assertion in one sentence → two spans).
- **Unclassified-span requiredness**: an unclassified span INHERITS the backend requirement of its containing
  field/card slot; if that has no explicit requirement mapping, it is treated as **required** (on_enforced →
  withhold field; shadow → log `segmentation_coverage_gap`). An unclassified span is **never** eligible for
  optional deletion merely because its class couldn't be determined (else a missed definition/constraint could be
  dropped as "optional" precisely when segmentation failed).
```
This keeps the validator from deleting a whole concept card because one sentence is unsupported, while still
guaranteeing the unsupported sentence can't survive — and that no factual clause slips through as unvalidated residue.

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
**Transformation validation (class 3) — canonical OUTPUT first, then semantics.** A declared operation is checked
syntactically against its OWN output *before* any solution-set reasoning (a wrong target must not be excused just
because it coincidentally shares a solution set with the source):
```text
1. Canonical operation application — apply the registered declared operation to the NORMALIZED source relation
   under the declared domain.
2. Target conformance — the canonical result must match the declared target (or a registered canonical-equivalent
   rendering of it). If it does NOT → REFUTED, even when source and target share a solution set.
3. Relation-mode conformance (ONLY after step 2 passes) — every declared class-3 transformation carries a
   BACKEND-derived `relation_mode`; the RENDERED prose must match its logical strength (correct algebra can still
   teach an invalid *solving* step):
   - `equivalence` → source and target share the same solution set under the domain; the target MAY replace the
     source (equivalence language allowed: "rewrite as", "is equivalent to", "solving gives");
   - `necessary_condition` → source-solutions ⊆ target-solutions (a ONE-WAY consequence); the target may NOT be
     used as an equivalent replacement unless the reverse implication is separately established, and the prose MUST
     carry a registered directional marker ("any solution must satisfy", "therefore a necessary condition is",
     "this implies"). **Equivalence language on a necessary_condition op ⇒ REFUTED.**
   - `contradiction` / `no_solution` → the target must EXPLICITLY communicate the empty solution set /
     inconsistency; it may not invent a new equation or conclusion.
A transformation with no DECLARED operation is INDETERMINATE → L4 (never operation-inferred); a declared operation
whose canonical output ≠ the declared target ⇒ REFUTED; a one-way step rendered with equivalence language ⇒ REFUTED.
```
> **Invariant:** a declared transformation must be (1) syntactically faithful to the registered operation, (2)
> semantically valid under the domain, AND (3) rendered with the correct logical strength (equivalent rewrite /
> one-way consequence / contradiction). Correct algebra with the wrong logical framing is still refused — e.g.
> `x = 2 ⇒ x² = 4` is a valid necessary_condition, but rendering it as an equivalence ("solving gives x² = 4, so
> x = ±2") is refuted because `x²=4` admits `x = −2` that the source excludes.
**Operation identification (v1 = surfaced/declared, never inferred by an LLM).**
```text
- v1: the operation must be SURFACED in the span ("Subtract 2 from both sides: x = 3") OR attached as registered
  deterministic metadata on the span. If no operation is named/declared → INDETERMINATE (→ L4), not a guess.
- later (optional): a DETERMINISTIC implicit-operation resolver may bind source→target ONLY when EXACTLY ONE
  registered operation transforms source into target under the domain (zero or multiple fits → indeterminate /
  reject per the card contract). Never inferred by an LLM.
```
So *"Squaring both sides of x² = −4 gives x² = 0"* is a **class-3 transformation with a DECLARED operation**
(`square_both_sides`) and is **refuted** because applying that operation to `x²=−4` yields `x⁴=16`, not the
declared target `x²=0` (and the empty-over-ℝ solution set is not communicated) — **not** treated as a
vacuously-true implication. An **undeclared** step ("since x²=−4, we get x²=0", no operation surfaced/attached) is
**INDETERMINATE → L4** instead (Operation identification, above) — the validator never *infers* the operation to
manufacture a refutation. A complex-valid relation under a `complex` domain is **not** rejected.

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
**Sibling-trace binding (never bind by proximity).** A general rule/definition must NOT be checked against a
concrete example's values just because it sits next to it:
```text
- explicit_example_reference → the span refers to a named/example-specific value, operation, or result → bind to
  the declared (trace_id, trace_step_id, output_name|fact_id) and run C1/C2/C4/C5 against THOSE facts.
- topic_general_rule        → the span states a general rule/definition → do NOT run example-value containment;
  validate via L2 (symbolic) or L4 (evidence) instead.
- mixed                     → split the span so the example-specific and general portions bind separately.
L3 applies C1/C2/C4/C5 ONLY against the exact sibling-trace facts the span references; it must not infer
example-specific binding from topic proximity.
```
This still catches prose that teaches the wrong method next to a correct worked example ("first isolate
acceleration" beside a substitute-into-F=ma example), while a general "F = ma relates force, mass, and
acceleration" definition beside a 4 kg / 20 N example is **not** forced to restate those values. Contradiction ⇒
**hard fail**.

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
`claim_class` is `non_factual_framing`/`prompt`, or whose `content_ownership == deterministic_carried_elsewhere`. A
`factual`, free-text-owned span must resolve as `refuted | unsupported | unavailable` — `no_objection` can never
make a bare factual assertion shippable (that removes the ambiguity of "the verifier didn't object, so ship it").

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

**Passing a check is NOT establishment.** L1 is scope-checking, L3 is contradiction-checking — neither *proves* a
general claim. Every claim records how (if at all) it was established, so an implementation can't treat "L1+L2+L3
didn't fail" as proof:
```text
ClaimEstablishment {
  status: established | not_established
  basis:  trace_authoritative | deterministic_ground_relation | deterministic_symbolic_transformation |
          registered_definition | fact_pack_rule | supplied_source_excerpt | none
  evidence_ids?: []
}
Ship rule — a claim_class==factual span may ship ONLY when:
  - ClaimEstablishment.status == established (a concrete basis above, not merely "no check failed"); OR
  - the field is authoritative/derivable and owned by trace-to-teaching (validated there, not here).
Passing L1/L2/L3 WITHOUT producing an establishment basis does NOT establish a free-text factual claim → it is
unsupported (soften/withhold).
```
**Establishment is set by a DETERMINISTIC resolver, never by L4.** (Otherwise L4 quietly becomes a certifier by
"finding support" in the fact-pack.)
```text
Claim-establishment resolver — runs before/alongside L4, over the span + pinned EvidenceContext. May mark a
factual span `established` ONLY via:
  1. exact/normalized match to a registered definition;
  2. deterministic match to a fact-pack rule;
  3. a registered explicit source-span entailment/mapping for that claim type;
  4. a deterministic L2 proof / registered transformation;
  5. authoritative trace ownership (delegated to trace-to-teaching).
It returns { basis, evidence_ids }; it NEVER uses an LLM verdict as establishment.

L4's role: invoked only for spans not already deterministically established, refuted, or delegated. L4 may
refute / mark unsupported / abstain — it can NEVER move ClaimEstablishment from not_established → established.
```

**Hard-fail span disposition** (a hard-fail/refutation is resolved at the SPAN via its backend-derived
`span_requirement` — mechanically evaluable, not an implementation guess):
```text
- Retry the span up to 2 times, then if it still fails/refutes, by span_requirement:
    optional  → deterministic DELETE; field_decision = soften;
    required  → WITHHOLD the field after failed repair;
    essential → WITHHOLD the card / topic family after failed repair.
- In all cases NEVER retain or paraphrase the failed claim.
```
**The SAME `span_requirement` disposition governs every non-shippable factual outcome** — refuted, unsupported,
AND unavailable (verifier outage). A registered deterministic replacement may substitute ONLY when it already has
an independent establishment basis and preserves the card contract. (So a *required* definition that is merely
unsupported still withholds the field — it is not deleted just because it wasn't hard-refuted.)
```
field verdict (per span; field_decision computed from spans):
  L1–L3 pass, L4 == n/a                     → SHIP (no unresolved factual assertion exists)
  L1–L3 pass, L4 == no_objection            → SHIP ONLY for non_factual_framing / prompt /
                                              content_ownership==deterministic_carried_elsewhere; never a factual span
  hard fail (L1 scope / L2 symbolic / L3)   → REPAIR (max 2) → still failing: optional span → DELETE/soften;
                                              required/essential span → WITHHOLD field/card
  L4 refuted                                → REPAIR (max 2) → still refuted: same span disposition as above
  L4 unsupported factual assertion          → by span_requirement: optional → SOFTEN/DELETE; required → WITHHOLD
                                              field; essential → WITHHOLD card/family
  L4 unavailable, factual assertion         → same span_requirement disposition (verifier outage is NOT a clean pass)
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
    claim_id · span · claim_class: factual | non_factual_framing | prompt | unclassified
    content_ownership: free_text | trace_authoritative | trace_derivable | deterministic_carried_elsewhere
    span_requirement: optional | required | essential   # backend-derived; drives delete-vs-withhold
    requirement_source: narration_contract | card_schema | registered_template
    ownership_provenance?: { deterministic_source_id, source_version, source_field }   # required if carried_elsewhere
    deterministic: { l1_scope, l2_symbolic, l3_sibling: pass|fail|indeterminate,
                     out_of_scope_terms[], refuted_relations[], symbolic_domain }
    semantic:      { l4: refuted | unsupported | no_objection | n/a | unavailable, span?,
                     unsupported_reason?, evidence_ids?[], evidence_context, verifier_available }
                     # evidence_ids REQUIRED on refuted; unsupported_reason set when l4 == unsupported
    establishment: { status: established | not_established, basis, evidence_ids?[] }   # factual spans ship only if established
    practice_binding?: { practice_problem_id, practice_contract_version, practice_validation_status,
                         evaluator_id, evaluator_version }   # practice prompts: render-eligible only if status==valid
    decision:      ship | repair | soften | withhold
    failures:      [ typed, most-severe first ]
  } ]
  field_decision:  ship | repair | soften | withhold      # computed from the claim dispositions above
  telemetry:       { topic_id, card_type, field, claim_id, content_ownership, span_requirement, requirement_source,
                     rung, verdict, unsupported_reason?, action, retry_count, evidence_context }
                     # requirement_source lets you tell a correct contract-mapped withhold from a fallback default
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
Field:  concept_intuition body contains "Squaring both sides of x² = −4 gives x² = 0."
        (declared operation surfaced in prose; equivalently, transformation_metadata { operation_id:
         square_both_sides, source: "x²=−4", target: "x²=0", relation_mode: equivalence } is attached to the span)
Expected:
  - the field is segmented into claim spans; this span is a DERIVATION/TRANSFORMATION claim (L2 class 3) with a
    DECLARED operation (never inferred)
  - L2 refutes it: square_both_sides applied to x²=−4 yields x⁴=16, NOT the declared target x²=0 (empty-over-ℝ
    solution set not communicated) — not a vacuously-true implication
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
| `test_l2_rejects_invalid_symbolic_transformation` | "Squaring both sides of x² = −4 gives x² = 0." (declared op `square_both_sides`) | hard fail L2 (class 3) — the DECLARED operation yields x⁴=16, not the target x²=0; not read as vacuous implication, not inferred |
| `test_l2_rejects_wrong_target_with_same_solution_set` | domain=real; source x²=−4; op `square_both_sides`; target x²=0 | hard fail L2 (target-conformance) — canonical output x⁴=16 ≠ target; NOT excused by source+target both having the empty ℝ solution set |
| `test_l2_rejects_one_way_transform_rendered_as_equivalence` | source x=2; op `square_both_sides`; target x²=4; relation_mode `equivalence` | hard fail L2 — canonical target matches but target has extra solution (x=−2); a one-way step can't be an equivalence |
| `test_l2_accepts_declared_necessary_condition` | "If x = 2, then any solution must satisfy x² = 4." op `square_both_sides`; relation_mode `necessary_condition` | pass L2 — source-solutions ⊆ target AND a registered directional marker is present |
| `test_l2_accepts_true_symbolic_implication` | "If a = 2, then a² = 4." | pass L2 (class 2 implication under the declared domain) |
| `test_l2_accepts_true_ground_relation` | known a=2 (authoritative); prose "a² = 4" | pass L2 (class 1 ground) |
| `test_l2_skips_non_extractable` | prose with no cleanly extractable relation | `l2_symbolic = indeterminate` (NOT pass); no L2 establishment basis created; factual spans continue to establishment + L4 |
| `test_l3_rejects_contradicting_sibling_example` | prose value conflicts with the topic's worked example | hard fail L3 |
| `test_l4_downgrades_unverifiable_definition` | plausible but unverifiable definition asserted as fact | soften (sentence dropped/reduced) |
| `test_l4_refuted_required_definition_withholds` | required components_terms def "A stack is FIFO." | repair ×2 → still refuted → withhold field/card |
| `test_l4_refuted_optional_span_deleted` | optional background sentence "A stack is FIFO." | repair ×2 → still refuted → delete span; siblings remain; field_decision = soften |
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
| `test_claim_segmentation_covers_entire_field` | "Stacks are LIFO, which always improves performance." | both the definition and the performance claim are spans; no factual residual left `unclassified` |
| `test_unclassified_residual_fails_closed` | field with an unsegmented factual clause | `segmentation_coverage_gap` in shadow; repair/withhold in on_enforced |
| `test_unclassified_span_inherits_backend_field_requirement` | unclassified residual clause inside a required components_terms field | on_enforced withholds the field; not silently deleted as optional |
| `test_passing_checks_without_basis_is_unsupported` | factual claim passes L1/L2/L3 but has no establishment basis | not shipped; `establishment.status=not_established` → unsupported |
| `test_l4_cannot_establish_factual_span` | factual free_text span, no deterministic basis, L4=no_objection | stays `not_established` → unsupported (L4 can't establish) |
| `test_hardfail_optional_span_deleted_required_withholds` | invalid-transform span, failed repair | optional → deleted (siblings ship); required → field/card withheld |
| `test_unsupported_required_span_withholds` | required components_terms def with no establishment basis (unsupported, not refuted) | required span → withhold field; not deleted just for being unsupported |
| `test_deterministic_carried_elsewhere_ships` | factual span with backend `content_ownership=deterministic_carried_elsewhere` + provenance, L4=no_objection | ships (truth owned by the deterministic source, not free-text) |
| `test_generator_ownership_labels_are_ignored` | generator emits `content_ownership=deterministic_carried_elsewhere`, no backend mapping | label discarded; backend routes independently → span is free_text and must establish normally |
| `test_backend_deterministic_mapping_missing_provenance_fails_closed` | backend mapping selects deterministic_carried_elsewhere but provenance missing/invalid | hard routing failure; NO fallback to free_text (withhold per backend requirement) |
| `test_span_requirement_is_backend_derived` | same invalid claim in optional background vs required components_terms def | backend requirement → delete for background, withhold for the required def; model-provided labels ignored |
| `test_l3_does_not_bind_general_rule_to_example_values` | general F=ma definition beside a 4 kg / 20 N example | no C1/C4 failure for not restating example values |
| `test_practice_prompt_requires_problem_contract` | new force-law problem with generated values | Q24 prose/scope may pass, but **render eligibility is FALSE unless `PracticeBinding.practice_validation_status == valid`** for the bound PracticeProblemContract; Q24 no_objection alone is not eligibility |
| `test_l2_equivalence_transform_passes` | "x + 2 = 5. Subtract 2 from both sides: x = 3." | pass L2 (declared equivalence-preserving op) |
| `test_l2_undeclared_operation_is_indeterminate` | "x + 2 = 5, so x = 3" (no operation surfaced/attached) | INDETERMINATE → L4 (no LLM guess of the step) |
| `test_l1_does_not_reject_nontechnical_prose` | ordinary wording | not flagged as an out-of-scope technical term |
| `test_l3_rejects_operation_conflict_with_sibling_trace` | prose method conflicts with the trace (no numeric conflict) | hard fail L3 via C5 |
| `test_withhold_required_card_blocks_family` | required card, hard fail, on_enforced | topic/family path withheld; no generic fallback |
| `test_shadow_logs_without_user_impact` | same failure, shadow_validate | legacy display remains; typed telemetry emitted |

---

## 8. Regression fixtures

```text
fixtures/free_text/
  invalid_symbolic_transformation.json # "squaring both sides of x²=−4 gives x²=0" — L2 class 3, DECLARED op yields wrong target
  undeclared_transformation_indeterminate.json # "since x²=−4, we get x²=0" (no op) — INDETERMINATE → L4
  valid_equivalence_transform.json  # "x+2=5; subtract 2 from both sides: x=3" — declared op, equivalence-preserving, passes
  wrong_target_same_solution_set.json # declared square_both_sides, x²=−4→x²=0 — refuted on target conformance
  one_way_as_equivalence.json       # x=2→x²=4 rendered as equivalence — refuted (relation_mode)
  declared_necessary_condition_ok.json # "any solution must satisfy x²=4" — necessary_condition, passes
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
- claim segmentation pass (field → ordered claim spans with claim_class, FULL non-whitespace coverage,
  unclassified-residual fail-closed, multi-proposition splitting) — the validation unit
- claim-establishment resolver (status/basis/evidence_ids) — DETERMINISTIC (definition/fact-pack/source/L2-proof/
  trace); runs before/alongside L4; L4 can never mark established. A factual span ships only when established
- BACKEND ownership + requiredness router: content_ownership (free_text | trace_authoritative | trace_derivable |
  deterministic_carried_elsewhere, with ownership_provenance) + span_requirement (optional | required | essential
  from narration_contract | card_schema | registered_template) — generator-authored labels are rejected
- sibling-trace binding resolver (explicit_example_reference | topic_general_rule | mixed) for L3
- PracticeBinding bridge to PracticeProblemContract + its deterministic evaluator (render-gates practice prompts;
  Q24 owns prose only)
- free_text validator module (L1–L4 per span + FreeTextValidationResult with per-claim results + field_decision)
- topic-level vocabulary object (assumed_prerequisite_terms/introduced_terms/approved_operations/symbols/aliases)
  + a domain tokenizer that classifies technical vs. ordinary tokens with confidence
- L2 relation classifier (ground / symbolic-identity / DERIVATION-transformation / underdetermined) + symbolic
  rule/algebra engine with registered algebraic operations + symbolic_domain + relation_mode (equivalence |
  necessary_condition | contradiction) + registered directional-marker lexicon (transformation preservation +
  correct logical strength, not material implication)
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

- [ ] The §6 false-symbolic-claim span is rejected by L2; after failed repair it is deterministically DELETED when
  optional (valid sibling spans survive), or WITHHOLDS the field/card when required — never retained/paraphrased.
- [ ] L1 rejects an out-of-scope term against the Phase-0 topic contract.
- [ ] `ClaimEstablishment` is set by the DETERMINISTIC resolver (definition/fact-pack/source/L2-proof/trace),
  never by L4; L4 can never move a span from `not_established → established`.
- [ ] `content_ownership` is distinct from `claim_class`; `no_objection` ships only `non_factual_framing`/`prompt`
  or `content_ownership==deterministic_carried_elsewhere`, never a free-text `factual` span.
- [ ] `content_ownership` and `span_requirement` are **backend-derived**; generator-supplied labels are DISCARDED
  before routing (not a routing instruction). Backend-selected `deterministic_carried_elsewhere` with missing/invalid
  `ownership_provenance` is a hard routing failure (never a free_text downgrade); a span with no backend mapping
  defaults to `free_text`.
- [ ] An `unclassified` span inherits its field/card requirement, defaults to **required** when unmapped, and is
  never eligible for optional deletion — a missed clause can't be dropped as "optional."
- [ ] Span disposition is driven by backend `span_requirement`: optional → delete, required → withhold field,
  essential → withhold card/family — applied **uniformly** to refuted, unsupported, AND unavailable factual spans
  (a required unsupported definition withholds, not deletes). `requirement_source` is carried in the result +
  telemetry (a contract-mapped withhold is distinguishable from a fallback default).
- [ ] A class-3 transformation is validated against a **surfaced/declared** operation (or registered metadata);
  an undeclared step is INDETERMINATE → L4, never an LLM-inferred operation. The §6 slice's refuted fixture carries
  a **declared** operation whose result ≠ the declared target (not an inferred refutation).
- [ ] A declared class-3 transformation also conforms to its backend `relation_mode`: `equivalence` needs equal
  solution sets (+ may replace); `necessary_condition` needs source⊆target AND a registered directional marker
  (equivalence language on a one-way step ⇒ refuted); `contradiction` states the empty set.
- [ ] A practice prompt is render-eligible only when Q24 prose passes AND `PracticeBinding.practice_validation_status
  == valid` AND the rendered inputs/units/answer match the bound `PracticeProblemContract`; Q24 `no_objection` alone
  is never eligibility.
- [ ] The validation unit is a **claim span**: a field is segmented before L1–L4; `field_decision` is computed
  from per-claim dispositions, so an unsupported span is softened/deleted without dropping valid sibling claims.
- [ ] Claim spans **cover every non-whitespace character** (ordered, non-overlapping); `unclassified` residual
  text fails closed (`segmentation_coverage_gap` in shadow; repair/withhold in on_enforced).
- [ ] A `factual` span ships only when `ClaimEstablishment.status == established` (a concrete basis) or it is
  trace-owned — passing L1/L2/L3 without a basis is **not** establishment.
- [ ] L3 binds C1/C2/C4/C5 only to the sibling-trace facts a span **explicitly references**; a general
  rule/definition is not forced to restate a neighboring example's values.
- [ ] L2 refutes the DECLARED class-3 transformation "squaring both sides of x²=−4 gives x²=0" on **target
  conformance** — the canonical operation output is x⁴=16, not the declared target (refuted **even though** source
  and target share the empty ℝ solution set); an UNdeclared transformation is INDETERMINATE → L4 (never
  operation-inferred); accepts a valid equivalence-preserving transform; honors `symbolic_domain`.
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
- **Not** a practice-problem-correctness validator — Q24 checks practice prompt *prose*; problem validity (a valid,
  satisfiable, correctly-answered problem) is owned by `PracticeProblemContract` + its deterministic evaluator (§2).
- Together the companions close the loop: **trace-to-teaching** keeps trace-backed prose faithful to the trace;
  **free-text validation** bounds the claims that have no trace. Phase 2 `on_enforced` for a family requires
  **both** clean in `shadow_validate`.
