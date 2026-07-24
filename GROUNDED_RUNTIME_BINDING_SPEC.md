# Grounded Runtime Binding Spec

> **Status:** Draft v0.9 — architecture approved; ready for implementation planning.
> v0.9 scopes the gen_foundation verification obligations: in v1 provenance decides route order only and the
> live route keeps its current internal gating; the `verified_gen_foundation` label and its tests activate
> with an explicitly named evidence-layer migration (§4.3.2, §9, §15, §17.1). Pedagogical-fitness checks are
> pinned to deterministic evaluators with declared parameter sources, and `sibling_novelty` consumes §2.5
> arbitration rather than a second similarity heuristic (§6.6).
> v0.8 closes the implementation-review blockers: convergence is classified by expression and execution
> shape (§2.3.1), end-to-end fallback fixtures must genuinely miss registered routing (§14.1, §17.2),
> resolution-registry authority is carried through executable/evidence artifacts (§5.2, §5.6, §5.9,
> §12.1), evidence packages receive an immutable pre-narration digest plus delivery record (§5.9, §12.4),
> gen_foundation
> provenance selects a candidate but never substitutes for verification (§4.3, §9), v1 solved forms are
> reviewed variants rather than runtime algebra (§5.3, §7.1), preparation activation is race-safe (§13.2),
> and learner-visible solvability and pedagogical fitness are named verification gates (§5.8, §6).
> v0.7 closes the residual review items: resolution-registry staleness now invalidates caches and
> preparations (§12.1, §13.2, §15), Wave 1's dependency on the v1.1 vector substrate is explicit (§2.3.1),
> the evidence-package persistence surface is named (§17.3, §19), and provenance naming is normalized (§4.3).
> v0.6 stages T6 convergence by expression capability (§2.3), defines legacy-float/shared-substrate
> equivalence (§2.3.2), maps live gen_foundation fields into normalized provenance (§4.3), identifies sibling
> arbitration as new certification machinery (§2.5), excludes cross-currency conversion (§5.7.1), and names
> resolution-registry and preparation persistence homes (§5.2, §13.2, §17.3).
> v0.5 resolves the implementation blockers: provenance-sensitive gen_foundation routing (§4.3),
> substrate-first T6 convergence (§2.3), reviewed resolution authority (§5.2/§6), the v1 unit-system
> decision (§5.7), sibling contract arbitration (§2.5), preparation lifecycle (§13.2), semantic sanitizer
> invariance (§5.10), evidence storage (§12.4), and the infrastructure go/no-go gate (§17.4).
> v0.4 resolved: v1 scope honesty (§1.1), formula-engine convergence stance (§2.3),
> certification timing (§2.4), gen_foundation placement (§4.3), resolution authority gating the derived
> label (§5.2, §9), verification honesty (§6), sanitizer boundary (§5.10), latency in the v1 contract
> (§13, §20), and a named promotion target (§12.2).
>
> **Purpose:** Safely produce worked examples for determinate topics that do not have an exact reviewed
> adapter, without allowing an LLM to become the source of executable truth. This document extends the
> existing adapter/orchestration architecture; it does not replace `ADAPTER_AND_GENERATION_SYSTEM_SPEC.md`,
> `ADAPTER_CONTRACT.md`, `ADAPTER_TAXONOMY_SPEC.md`, `WORKED_EXAMPLE_ACCURACY_SPEC.md`, or
> `TRACE_TO_TEACHING_CONTRACT_SPEC.md`.
>
> **Initial shipping scope (v1):** scalar quantitative examples using reviewed `ConceptContract` records and
> one reviewed reasoning grammar: `direct_formula_calculation`. `discounted_cashflow` is the second vertical
> slice (v1.1), not part of v1's definition of done.

---

## 0. Executive decision

When no exact reviewed adapter exists, the system may ask an LLM to **resolve a concept, select a reviewed
reasoning grammar, and propose bindings**. It may not ask the LLM to invent an executor, verifier, loop,
invariant system, or arbitrary program.

The architectural invariant is:

> **The model may resolve, select, bind, compose, and narrate. Reviewed infrastructure must execute, trace,
> and verify. A runtime binding may specialize reviewed semantics but may not introduce new execution
> semantics.**

Machine-checkable form:

> **For every executable node in a runtime instance, its operational semantics must resolve to an operation
> defined by the selected reviewed grammar version.**

The resulting artifact is not a generated adapter. It is:

```text
reviewed execution grammar
+ grounded concept contract
+ validated runtime bindings
= temporary executable instance
```

Permanent reviewed adapters remain the highest-trust and fastest path. Runtime binding is a bounded fallback
and a source of demand evidence for expanding the reviewed catalog.

### 0.1 Deterministic-first v1

For reviewed scalar contracts, v1 first derives a binding deterministically. An LLM is not required merely
because the runtime-binding route was selected.

```text
v1a: reviewed contract -> deterministic binding -> execute and verify
v1b: model proposes only nontrivial mappings/convention choices in shadow
```

The model is introduced only when deterministic mapping cannot resolve a reviewed choice. Presentation wording
remains a separate narration concern. Shadow comparison must demonstrate that model proposals add coverage
without reducing binding validity before they can affect delivered examples.

---

## 1. Why this exists

The current accuracy boundary is sound but leaves a coverage gap:

```text
exact adapter found       -> verified trace -> worked example
no exact adapter found    -> soft endpoint / illustrative / guided / withheld
```

Allowing the existing from-scratch solver to fill that gap is unsafe. The same model can choose the problem,
formula, assumptions, steps, and answer, then judge its own result. Structural validation can show that the
output is well formed; it cannot establish that the chosen law, convention, or calculation is correct.

At the same time, many uncovered quantitative concepts are not computationally unique. They instantiate a
small number of reusable reasoning grammars:

- direct substitution into a governing relationship;
- discounted sums and discounted weighted averages;
- expected values and weighted averages;
- rate and percentage changes;
- normalization;
- conservation balances;
- small linear systems.

The scalable target is therefore a two-layer catalog:

```text
Reviewed reasoning families                  Reviewed concept contracts
  direct formula calculation                   Ohm's law
  discounted cash flow                         Macaulay duration
  weighted average                             center of mass
  expected value                               expected portfolio return
```

Concept entries can remain small, reviewed declarations while execution, trace construction, testing, and
teaching projection are reused by the family.

### 1.1 What v1 does and does not buy

V1 requires a human-reviewed `ConceptContract` before anything executes. Authoring and reviewing such a
contract is the same order of effort as authoring a reviewed `FormulaSpec` row that the existing T6 engine
already executes with routing, narration, gates, and registration for free. Therefore:

- **V1's deliverable is infrastructure and trust-label plumbing, not coverage.** The restricted executor,
  evidence packages, verification vector, and derived trust levels are the machinery Phase 3 extraction
  needs. Coverage materially expands only when contracts stop requiring bespoke human authoring (Phase 3).
- The reason to author a `ConceptContract` instead of a `FormulaSpec` row must be one of: (a) the contract
  is pure declarative fact — draftable by a model and approvable in one human pass, with a measurably lower
  review bar than executable spec code; (b) one contract serves multiple grammars; (c) the concept needs the
  richer assumption/variant/conflation metadata a spec row cannot carry. If none apply for a given concept,
  author the spec row — reviewed effort must not be routed through the lower-trust tier.

Catalog review enforces that admission rule. A new reviewed scalar relationship becomes a runtime contract
only when at least one of those conditions is recorded in `review_provenance`, or when it is an explicitly
marked runtime-routing fixture. Otherwise registration rejects it and directs the author to `FormulaSpec`.

---

## 2. Relationship to existing architecture

This system reuses the existing artifact chain:

```text
LessonIntent
  -> ExecutionTrace
  -> TeachingTrace
  -> TeachingProjection
  -> TeachingCheckpoint[]
  -> narration
  -> trace-to-teaching validation
  -> cards
```

It adds only the artifacts required to choose and safely instantiate a reviewed family:

```text
Topic scope plan
  -> ContractConceptResolution
  -> ConceptContract
  -> BindingProposal
  -> ValidatedBinding
  -> GeneratedInstance
  -> existing adapter artifact chain
```

### 2.1 Existing systems that remain authoritative

- The study-path scope plan owns the topic's canonical identity, role, depth, `scope_in`, and `scope_out`.
- The task classifier owns whether the requested example is determinate, conceptual, or unresolved.
- Exact reviewed adapters and their routing remain Tier 1.
- Adapter families own execution semantics, trace grammar, template invariants, and teaching projection.
- `TRACE_TO_TEACHING_CONTRACT_SPEC` owns narration fidelity.
- The decision trace owns why a route, concept variant, grammar, binding, degradation, or withhold occurred.

### 2.2 Explicit non-integration with authored `eval`

The current formula family accepts authored `FormulaSpec.expr` strings and evaluates them in a sealed
namespace. That is acceptable because those expressions are reviewed source code.

> **A runtime-generated expression must never be passed directly to `FormulaSpec.expr`, `_eval`, Python
> `eval`, `exec`, a shell, or a dynamically imported callable.**

Runtime bindings use a restricted, parsed expression AST whose node types and functions are allowlisted by
the reviewed grammar. The executor evaluates that AST directly.

### 2.3 Convergence stance with the authored T6 formula engine

`direct_formula_calculation` is functionally the authored formula engine with a restricted AST in place of
reviewed `expr` strings. Two parallel implementations of "substitute → compute → propagate units → verify by
recomputation" would drift. The shared substrate therefore precedes runtime binding:

1. Build `RestrictedExpression`, `NumericPolicy`, canonical units, and the scalar executor.
2. Classify every registered T6 row by both (a) the exact expression nodes/functions it requires and
   (b) its execution shape: output count and dependency DAG, constants, scalar/vector inputs, sampling
   predicates, trace-stage shape, unit/convention requirements, and presentation dependencies.
3. **Wave 0:** shadow-compile and behavior-diff every rational-closed row expressible with the v1 node set
   (`Literal`, `Variable`, `Add`, `Subtract`, `Multiply`, `Divide`, integer `Power`, `Negate`).
4. Move Wave-0 authored rows onto the shared substrate only after their behavior-diff suite is clean.
5. Build v1 runtime `ConceptContract` binding on that proven Wave-0 substrate.
6. Add later waves as reviewed grammar-version extensions: aggregate nodes, then explicitly approximating
   primitives such as `sqrt`, followed by trig/log/exp only when demanded. Each approximation wave declares
   numeric representation, tolerance, domain, and equivalence policy before rows migrate.

Every non-Wave-0 row is enumerated in a machine-readable convergence report with its blocking nodes/functions;
it is not silently counted as a failure and does not block rational-only v1. The authored engine remains
authoritative for every unmigrated row. Runtime binding may enter enforced mode only for grammar versions whose
corresponding authored wave has migrated onto the shared substrate.

#### 2.3.1 Convergence waves

```text
Wave 0  rational scalar closure   + - * / integer-power negate
Wave 1  exact aggregates          sum len min max sorted median/paired-list operations
Wave 2  algebraic approximation   sqrt and other explicitly reviewed algebraic primitives
Wave 3  transcendental            sin cos tan inverse trig log log10 exp
```

Expression-wave membership is derived from parsed expression requirements, not hand-waved per row. A row
requiring several expression waves belongs to the highest required wave. Expression closure alone does not
make a row migratable: the convergence report also emits an `ExecutionShapeCapability` assessment.

```text
ExecutionShapeCapability {
  output_count: int
  output_dependency_dag: object
  constants: [str]
  input_shape: scalar | aligned_vector | mixed
  custom_sampling_predicate: bool
  trace_stage_shape: [str]
  unit_and_convention_features: [str]
  presentation_dependencies: [str]
  supported_by_substrate_version: bool
  blockers: [str]
}
```

A row enters a migration wave only when both its expression requirements and execution shape are supported.
A rational-only row with two ordered outputs is not Wave-0 migratable until the shared substrate supports a
reviewed multi-output dependency DAG.

Wave 1 is NOT a pure node addition after Wave 0: its `sum/len/min/max/sorted/median/paired-list` rows are the
dataset-variant T6 rows, which need aligned-vector value types and grammar-owned vector access — both deferred
by §5.5 to the v1.1 `discounted_cashflow` slice. Wave 1 is therefore gated on the v1.1 vector substrate and
must not be scheduled before it.

#### 2.3.2 Behavior-diff equivalence

The legacy authored engine is float/display based while Wave 0 is exact-rational internally. “Match” means:

- both paths accept/reject the same seeded teaching candidates;
- substrate canonical results, rounded with the row's existing display policy, equal the legacy displayed
  results;
- intermediate authoritative values agree at the declared display precision;
- normalized units, operation order, terminal answer, trace coverage, and rendered authoritative fields agree;
- exact rational equality is required between shared-substrate replay runs, not between rational and legacy
  float internals;
- any residual row-level drift is explicitly classified, reviewed, and either fixed or waived with a durable
  reason before that row migrates.

Bit-level float/rational equality is neither required nor used as the migration gate.

### 2.4 Certification timing and `we_policy`

`we_policy` is stamped at path certification (`_certify_path_scope`), and `enforce_example_plan` strips
non-trace-backed worked examples at finalize — both at different times than example solving. Runtime binding
must be visible to both, or it will silently no-op (or be stripped after paying full generation cost):

- Certification becomes route-aware: a topic that misses registered routing, reaches
  `resolution_validity=reviewed_match`, resolves a reviewed contract, passes contract/scope fit, and wins
  sibling arbitration is stamped `we_policy='runtime_binding_eligible'` (resolution evidence recorded in the
  decision trace) instead of `withhold_fabricated`.
- `enforce_example_plan` accepts an example whose card provenance references a frozen `EvidencePackage`
  with a passing verification vector and an allowed derived trust level; everything else on a non-verified
  topic is stripped exactly as today.
- A binding that fails after certification degrades the topic to the current withhold behavior; it never
  falls through to the unverified from-scratch solver.

### 2.5 Sibling contract ownership

A contract-backed exercise is path-owned, not independently claimable by every topic. Certification arbitrates
on:

```text
(concept_contract_id, variant, grammar_id, lesson_intent_kind)
```

Before stamping eligibility it must establish:

- the contract directly demonstrates the topic's owned `scope_in`;
- assumptions and applicability conditions fit that scope;
- no sibling already owns the same contract/variant/intent exercise;
- a second use is allowed only when `LessonIntent` requires a materially different operation, decision, or
  result—not merely different numbers or narration.

The winning topic receives `runtime_binding_eligible`; losing siblings receive
`runtime_binding_claim_lost` and the claimant topic id in their decision trace. This is new cross-sibling
machinery, not an existing adapter-claim service. Its implementation home is `_certify_path_scope`, where the
full sibling set, owned scopes, and existing requirement/facet/dedup decisions are simultaneously visible.
It prevents the same verified calculation from appearing in several lessons.

---

## 3. Trust boundaries

### 3.1 What the model may do

- Map the scope plan's identity to a reviewed executable contract concept and variant.
- Select among reviewed grammar identifiers.
- Map source variables onto grammar slots.
- Select among reviewed conventions exposed by the grammar.
- Propose learner-friendly labels and example context.
- Narrate a frozen evidence package.
- Add explanatory annotations supported by evidence references.

### 3.2 What the model may not do

- Generate arbitrary executable code.
- Introduce loops, recursion, dynamic dispatch, or custom control flow.
- Add an operation not declared by the selected grammar.
- Define the verifier that judges its own binding.
- Replace grammar-owned invariants with generated invariants.
- Replace or rewrite the concept contract's normalized relationship.
- Declare its own output authoritative.
- Change values, formulas, assumptions, operations, or conclusions while narrating.
- Promote a runtime binding into the reviewed catalog.

### 3.3 Ownership matrix

| Concern | Owner |
|---|---|
| Topic identity and owned learning delta | Scope plan |
| Concept and variant evidence | Concept contract |
| Grammar selection proposal | Resolver/model |
| Allowed operations and control flow | Reviewed grammar |
| Bindings proposal | Resolver/model |
| Binding validation | Deterministic validator |
| Execution and trace | Reviewed grammar |
| Baseline invariants and tests | Reviewed grammar |
| Supplementary check suggestions | Model, non-authoritative |
| Narration | Narration model |
| Formula/value/assumption fidelity | Deterministic trace-to-teaching validator |
| Conceptual authority | Grounding policy |
| Promotion to catalog | Human review + adapter test suite |

### 3.4 Authority chain

The implementation must keep five authorities distinct:

```text
scope authority       -> what concept the path owns
contract authority    -> which relationship, assumptions, and variant are true for execution
binding authority     -> how contract symbols map into a reviewed grammar
execution authority   -> what values and transitions the reviewed grammar produces
narration authority   -> how frozen evidence is explained
```

No downstream authority may rewrite an upstream one. A mismatch returns upstream or degrades; it is never
repaired by silently changing the higher-authority artifact.

---

## 4. End-to-end routing

```text
Topic scope plan
  |
  v
Registered reviewed adapter lookup using persisted scope identity and reviewed aliases
  |
  |-- found (hand-coded adapter or engine row) ------> execute reviewed adapter
  |
  `-- missing
       |
       v
  Resolve contract concept + executable variant
       |
       v
  Refined registered-adapter lookup
       |-- found ------------------------------------> execute reviewed adapter
       |
       `-- missing
            |
            v
  Inspect gen_foundation candidate provenance
       |-- trace_first/reference_backed -------------> use verified gen_foundation artifact
       |
       `-- model_only/unverified/missing
            |
            v
  Retrieve reviewed concept contract
       |-- found
       |
       `-- missing -> v1: no executable binding
                     later phase: extract candidate contract from approved grounding
                          |
                          v
                    validate grounding authority,
                    formula/definition structure,
                    assumptions and variant
       |
       v
  Generate restricted BindingProposal
            |
            v
       Validate against ConceptContract + grammar
            |
            v
       Generate and validate instance
            |
            v
       Execute deterministically
            |
            v
       Reference, boundary, property and
       metamorphic checks
            |
            v
       Freeze EvidencePackage
            |
            v
       Generate evidence-linked cards
            |
            v
       Validate narration fidelity
            |
            v
       Ship, downgrade to illustrative/guided,
       or withhold
```

### 4.1 Ordering constraint

The first exact lookup uses the persisted scope identity and reviewed aliases. Only after that misses does the
system resolve the narrower executable contract concept/variant and perform a refined exact lookup. Expensive
contract retrieval or extraction happens only after both exact lookups fail. An exact adapter already carries
reviewed concept semantics and must not pay the runtime-grounding cost.

### 4.2 Routing priority

```text
1. Registered reviewed adapter (hand-coded adapter or reviewed engine row)
2. Provenance-verified gen_foundation result, only where actual execution/reference evidence exists
3. Grounded runtime binding over a reviewed grammar
4. Source-grounded illustrative or guided explanation
5. Withhold
```

The system never skips a higher-trust applicable tier merely because a lower tier is easier to generate.
Trusted primitive composition is deferred to Phase 4 and is not part of the v1 live route.

Hand-coded adapters and declarative engine rows are one registered lookup with two authoring shapes. Runtime
binding begins only when both the initial and refined registered lookups miss.

### 4.3 Placement relative to gen_foundation

Gen_foundation is not uniformly verified. It may return `trace_first`, `reference_backed`,
`post_generation_trace`, or `model_only`; only the first two establish an authoritative computation source.
Routing therefore depends on final provenance, not on whether gen_foundation returned an artifact:

```text
registered reviewed adapter
  -> gen_foundation trace_first/reference_backed
  -> grounded runtime binding
  -> gen_foundation model_only/post-generation measurement as illustrative or guided only
  -> withhold
```

`trace_first`/`reference_backed` may nominate a higher-priority candidate because the artifact descends from
executed or reviewed reference truth. Provenance is not itself a shipping proof. Once gen_foundation is
migrated onto the evidence layer (§4.3.2), the candidate must produce frozen evidence and pass the
applicable concept/scope match, replay, trace-to-teaching, problem-solvability, and narration-fidelity
checks; a positive live provenance flag never substitutes for those checks.

A model-only artifact may not outrank a reviewed-contract runtime binding and may never receive a verified
trust label. `post_generation_measurement` output is measurement unless its final artifact is rebuilt from
and validated against the execution trace. When routes overlap, the decision trace records the candidate
provenance, verification vector, winner, and reason.

#### 4.3.1 Live-field normalization

The router derives normalized provenance from fields that exist today:

| Normalized category | Live evidence |
|---|---|
| `trace_first` | adapted result has `ground_truth_source="trace_first"` (originating artifact has `trace_first=true` without `reference_backed`) |
| `reference_backed` | adapted result has `ground_truth_source="reference_first"` (originating artifact has `reference_backed=true`) |
| `post_generation_measurement` | pipeline attempted/reconciled generated code but final adapted result has no authoritative `ground_truth_source` |
| `model_only` | no authoritative `ground_truth_source`; no executed/reference-built artifact |

`post_generation_trace` and `model_only` are internal gen_foundation modes, not guaranteed persisted labels;
absence of both positive provenance signals is the shipping-relevant fact. The accuracy ladder's separate
`verification_level="model_only"` vocabulary is unrelated and must not be used to infer gen_foundation
provenance. Normalization lives at the solver/router boundary and is covered by fixtures for every row above.

#### 4.3.2 V1 scope: provenance orders routes; the live route is not retrofitted

Gen_foundation ships today under its own internal gating with none of this spec's evidence machinery, and no
§17.1 implementation unit builds `EvidencePackage`/`DeliveryEvidenceRecord` wrapping for it. Therefore, in
v1:

- the normalized provenance categories decide ROUTE ORDER only;
- a gen_foundation candidate that wins the route ships exactly as production ships it today, under
  gen_foundation's existing internal checks — v1 must not regress a working verified route behind unbuilt
  evidence plumbing;
- the `verified_gen_foundation` derived label (§9), the forged-provenance withhold test, and the frozen-
  evidence obligation on this route all activate only with the **gen_foundation evidence migration** — named
  deferred work, scheduled no earlier than Phase 2, with its own implementation unit and behavior-diff
  against the pre-migration route;
- until that migration, gen_foundation output carries its existing labeling, not a §9 derived level.

---

## 5. Core artifacts

### 5.1 `GrammarManifest`

```text
GrammarManifest {
  grammar_id: str
  version: int
  required_slots: [GrammarSlot]
  optional_slots: [GrammarSlot]
  accepted_value_types: [ValueType]
  supported_expression_nodes: [str]
  convention_schema: { key: [allowed_value] }
  numeric_policy_ref: str
  generation_policy_ref: str
  verification_profile_ref: str
  trace_contract_ref: str
  projection_contract_ref: str
}

GrammarSlot {
  slot_id: str
  role: input_symbols | output_symbol | relationship | convention
  cardinality: one | one_or_more
  required: bool
  accepted_value_types: [ValueType]
}
```

The v1 `direct_formula_calculation` manifest exposes:

```text
given_symbols       input_symbols   one_or_more
unknown_symbol      output_symbol   one
relationship        relationship    one
unit_convention     convention      optional
```

It does not expose semantic operator slots such as `numerator` or `denominator`; those belong to the
contract-owned relationship. Specification validity checks bindings directly against the selected manifest.

### 5.2 `ContractConceptResolution`

```text
ContractConceptResolution {
  scope_concept_id: str
  resolved_contract_concept_id: str
  variant: str
  resolution_registry_version: int
  resolution_entry_version: int
  excluded_variants: [str]
  reasoning_shape: str
  evidence: [ResolutionEvidence]
  status: resolved | ambiguous | unsupported
}

ResolutionEvidence {
  source: scope_plan | explicit_goal | reviewed_alias | grounded_definition | model
  value: str
  authority: reviewed | authoritative_retrieval | user_source | model_inferred
  detail: str
}
```

Rules:

- `scope_concept_id` is copied from the scope plan and is immutable in this pipeline.
- `resolved_contract_concept_id` maps that scope identity to an executable reviewed contract; it does not
  overwrite or silently refine the path's canonical identity.
- If the scope identity is too broad to map safely, return `ambiguous` or a scope-refinement request.
- A model-only variant selection cannot silently resolve a meaningful ambiguity.
- If two variants would materially change the formula, convention, or answer, the variant must be explicit.
- Ambiguous resolution routes to clarification, a neutral comparison/illustration, or withhold—not arbitrary
  selection.
- **Resolution authority flows into its own verification dimension (§6):** reviewed resolution requires an
  exact reviewed concept id, a reviewed alias-to-contract mapping, an explicit learner goal naming the reviewed
  variant, or a previously certified contract mapping. Token similarity and token equality may nominate
  candidates but cannot establish reviewed semantic identity. A resolution supported only by heuristic or
  model evidence fails the v1 shipping gate even when everything downstream verifies against that contract.
  The dangerous case is a wrong-yet-confident mapping onto the single contract that happens to exist.

Reviewed identity and alias mappings live in a versioned `ContractResolutionRegistry` owned by
`runtime_binding/contract_store.py`:

```text
ContractResolutionEntry {
  scope_concept_id: str
  reviewed_aliases: [str]
  contract_concept_id: str
  allowed_variants: [str]
  default_variant: str | null
  version: int
  review_provenance: str
}
```

The registry is the only alias mapping that can establish `resolution_validity=reviewed_match`. Heuristic
token candidates never modify it at runtime.

Both registry versions are frozen into the resolution artifact and flow into validated bindings,
preparations, cache keys, and evidence packages.

### 5.3 `ConceptContract`

```text
ConceptContract {
  contract_id: str
  version: int
  contract_concept_id: str
  variant: str
  definition: GroundedArtifact
  normalized_relationship: NormalizedRelationship
  symbols: { symbol_name: SymbolContract }
  constraints: ContractConstraintSet
  assumptions: [GroundedArtifact]
  applicability_conditions: [GroundedArtifact]
  conventions: [GroundedArtifact]
  expected_interpretations: [GroundedArtifact]
  forbidden_conflations: [GroundedArtifact]
  grounding_status: reviewed | authoritative_retrieval | user_source_only | model_inferred
}

GroundedArtifact {
  artifact_id: str
  kind: definition | formula | assumption | applicability | convention | interpretation | invariant
  normalized_value: object
  source_ref: str
  authority: reviewed | authoritative_retrieval | user_source | model_inferred
}

NormalizedRelationship {
  relationship_id: str
  grammar_id: str
  expression: RestrictedExpression
  input_symbols: [str]
  output_symbol: str
  source_artifact_ids: [str]
}

SymbolContract {
  symbol: str
  role: input | output | constant
  value_type: ValueType
  unit_constraint: UnitConstraint
  meaning_ref: str
  domain_constraints: [Constraint]
}

ContractConstraintSet {
  applicability: [Constraint]
  semantic_domain: [Constraint]
}
```

The distinction between source-derived and model-selected fields is mandatory. A model may propose missing
fields, but they retain `model_inferred` authority and cannot be presented as reviewed facts.

Contract constants use versioned `GroundedArtifact` records containing typed value, unit, authority,
source/version, and validity notes. A bare model-supplied numeric constant can never enter execution.

For v1, every executable relationship is contract-owned and reviewed. The binding references it; the binding
does not provide a second expression that must be compared for semantic equivalence.
Alternative valid definitions or relationships require separate versioned variants rather than an unresolved
list inside one executable contract.

V1 does not perform symbolic algebra to rearrange a relationship. If the requested unknown changes the solved
form, each allowed solved form is a separate reviewed executable variant (for example
`ohms_law_current`, `ohms_law_voltage`, and `ohms_law_resistance`). A missing solved-form variant is
unsupported; the binding model may not derive it at runtime.

### 5.4 `BindingProposal`

```text
BindingProposal {
  proposal_id: str
  concept_contract_id: str
  grammar_id: str
  grammar_version: int
  relationship_ref: str
  slot_bindings: { grammar_slot: concept_symbol }
  convention_selections: { convention_key: allowed_value }
  presentation: {
    input_labels: { symbol: str }
    result_label: str
    display_unit: str
    scenario_hint: str
  }
  supplementary_checks: [NonAuthoritativeCheckSuggestion]
  proposal_source: deterministic | model
}
```

No verifier logic, arbitrary invariant, or executable function is accepted in this artifact.
`scenario_hint` is stylistic and cannot supply, constrain, or override sampled givens.

V1a constructs this proposal deterministically:

- `relationship_ref` comes from the resolved reviewed contract;
- input/output slots come from `NormalizedRelationship` and `SymbolContract.role`;
- grammar and numeric/generation policies come from `GrammarManifest`;
- conventions come from a single compatible reviewed contract selection;
- presentation labels come from reviewed symbol metadata, with narration allowed to paraphrase later.

An LLM proposal is needed only when a later contract exposes multiple reviewed compatible mappings or
conventions that cannot be resolved from scope evidence. Such proposals begin in shadow and may select only
from those reviewed options.

### 5.5 `RestrictedExpression`

Initial allowlisted nodes:

```text
Literal
Variable
Add
Subtract
Multiply
Divide
Power(constant integer exponent only)
Negate
```

`Sum` and aligned-vector operations are deferred to the v1.1 `discounted_cashflow` slice.

Initial prohibitions:

- no arbitrary function calls;
- no attribute access;
- no subscripting outside grammar-owned aligned-vector access;
- no comprehensions;
- no conditionals;
- no loops or recursion;
- no mutation;
- no dynamic names;
- no string evaluation;
- bounded AST depth and node count.

Future functions such as `sqrt`, `log`, or trigonometric operations require explicit grammar-version additions,
domain predicates, and tests. They are not enabled merely because an authored formula engine already exposes
them.

### 5.6 `ValidatedBinding`

```text
ValidatedBinding {
  proposal: BindingProposal
  resolution_registry_version: int
  resolution_entry_version: int
  relationship: RestrictedExpression
  resolved_types: { symbol: ValueType }
  resolved_units: { symbol: Unit }
  constraints: ValidatedConstraintSet
  verification_plan: VerificationPlan
  binding_digest: str
  execution_environment_digest: str
}

ValidatedConstraintSet {
  contract_constraints: [Constraint]
  grammar_constraints: [Constraint]
  derived_expression_constraints: [Constraint]
  generation_quality_constraints: [Constraint]
}
```

`relationship` is loaded from `proposal.relationship_ref`; it is never generated by the binding model.

`binding_digest` is a SHA-256 digest over canonical JSON containing the resolution-registry/entry versions,
concept-contract id/version, relationship id, grammar id/version, normalized slot bindings,
execution-affecting convention selections, and constraints. Presentation labels do not affect executable
identity; a selected display unit does when it requires conversion rather than a label-only rendering.

`execution_environment_digest` covers the unit-system version, numeric-policy version, verification-plan
version, restricted-expression canonicalization version, and reviewed primitive implementation versions.
Execution and narration reference both digests.

The supporting types are owned as follows:

- `ValueType`, `Unit`, and `Constraint`: runtime-binding schema/validator.
- `VerificationPlan` and `VerificationCheck`: runtime-binding verification module.
- `LessonIntent`, `ExecutionTrace`, `TeachingTrace`, `TeachingProjection`, and `TeachingCheckpoint`: existing
  adapter artifacts.
- `DecisionEvidence`: runtime-binding evidence module and decision-trace identifiers.

Constraint origin is never flattened:

- contract applicability failures invalidate conceptual applicability;
- grammar/expression-domain failures block execution;
- generation-quality failures reject and resample the instance without invalidating the binding.

### 5.7 `NumericPolicy`

```text
NumericPolicy {
  policy_id: str
  version: int
  representation: rational
  internal_precision: int | null  # null for exact-rational v1
  comparison_absolute_tolerance: decimal  # zero in v1
  comparison_relative_tolerance: decimal  # zero in v1
  intermediate_rounding: forbidden
  output_rounding_mode: str
  display_precision: int
  significant_figures_policy: str
  currency_minor_unit_policy: str | null
}
```

Every grammar version selects a reviewed numeric policy. Binary floating-point equality is not an
authoritative comparison. Rounding occurs only at the declared output/display boundary; displayed givens must
recompute to the displayed result within the declared policy.

#### 5.7.1 V1 numeric and unit decision

V1 uses no new unit dependency:

- Internal scalar arithmetic uses Python `Fraction`; integer and terminating-decimal inputs parse exactly.
- `Decimal` is used only for policy-controlled display rounding and serialization.
- Units come from a reviewed, versioned registry of multiplicative `UnitSpec` records.
- A unit is `(scale_to_canonical: Fraction, dimensions: DimensionVector, display_symbol: str)`.
- `DimensionVector` uses rational exponents over the base dimensions
  `{mass, length, time, current, temperature, amount, luminous_intensity, currency}`.
- Rates carry inverse-time dimensions when paired with time; “5% per year” is not an untyped decimal.
- Derived units such as newton, joule, volt, ohm, and density units reduce to the base vector.
- V1 permits one currency identity per instance. Cross-currency conversion is rejected: an exchange rate is
  market data and model input, never a fixed `UnitSpec` scale.
- Only multiplicative conversions are supported in v1. Affine/logarithmic units, including
  Celsius/Fahrenheit conversion, are rejected by the grammar.
- Unit-registry version and canonical base-unit policy are included in `execution_environment_digest`.

Comparison is exact for rational results. Tolerance is used only when a later reviewed primitive explicitly
introduces approximation; no such primitive exists in the v1 grammar.

The executor places reviewed limits on AST size, integer magnitude, and `Fraction` numerator/denominator bit
length. Exceeding a bound rejects the candidate or execution.

Unit execution order is fixed:

```text
visible givens
  -> parse into typed quantities
  -> convert to canonical units
  -> execute relationship in canonical quantities
  -> produce canonical result
  -> apply reviewed display conversion
  -> round only at the declared display boundary
```

`TypedValue` preserves canonical value/unit and displayed value/unit. Evidence and traces never hide a unit
conversion; conversion steps reference the applicable unit rule.

### 5.8 `GeneratedInstance`

```text
GenerationPolicy {
  policy_id: str
  version: int
  max_generation_attempts: int
  max_rejected_samples_stored: int
  input_ranges: { symbol: RangeOrSet }
  quality_constraints: [Constraint]
  candidate_ordering: str
}

GeneratedInstance {
  instance_id: str
  binding_digest: str
  execution_environment_digest: str
  seed: int
  generation_policy_id: str
  generation_policy_version: int
  raw_values: { symbol: TypedValue }
  visible_values: { symbol: TypedValue }
  constraints_applied: [{ constraint_id, origin }]
  generation_attempts: int
  rejection_counts: { rejection_code: int }
  rejected_candidate_samples: [{ candidate_id, rejection_code }]
  numeric_policy: NumericPolicy
  expected_result: TypedValue | StructuredResult
  problem_solvability: ProblemSolvabilityResult
  pedagogical_fitness: PedagogicalFitnessResult
  instance_digest: str
}

ProblemSolvabilityResult {
  all_required_symbols_visible_or_reviewed: bool
  requested_output_unambiguous: bool
  display_unit_unambiguous: bool
  learner_visible_recomputation_passed: bool
  required_assumptions_visible: bool
  unused_givens: [str]
  passed: bool
}

PedagogicalFitnessResult {
  scope_relevance: passed | failed
  difficulty_fit: passed | failed
  operation_relevance: passed | failed
  nontriviality: passed | failed
  visible_number_readability: passed | failed
  single_primary_objective: passed | failed
  prerequisite_compatibility: passed | failed
  sibling_novelty: passed | failed
  failures: [str]
}
```

The reviewed grammar owns instance generation. The model may supply a stylistic scenario hint, but it cannot
choose authoritative values. Selection rejects trivial, singular, misleading, assumption-violating, or
rounding-dominated candidates. `instance_digest` covers the binding/environment digests, seed, generation
policy, raw/visible values, numeric policy, and expected result.

Generation policy sets `max_generation_attempts` and `max_rejected_samples_stored`. Production telemetry stores
categorical counts and at most the bounded sample records, without raw rejected values. Full rejected values
are retained only in fixture, failure-debug, or explicitly sampled diagnostic runs.

Every required free symbol must be supplied by a learner-visible given, a reviewed constant, or an explicitly
traced prior value. Learner-visible information must deterministically reproduce the displayed result. Unused
givens are rejected in v1; distractors require a later explicit practice policy. A stylistic `scenario_hint`
is checked against contract assumptions and applicability conditions and is discarded or regenerated when it
implies a conflicting regime.

### 5.9 `EvidencePackage`

```text
EvidencePackage {
  evidence_id: str
  evidence_schema_version: int
  evidence_digest: str
  created_at: datetime
  verification_completed_at: datetime
  binding_digest: str
  execution_environment_digest: str
  instance_digest: str
  resolution_registry_version: int
  resolution_entry_version: int
  lesson_intent: LessonIntent
  concept_resolution: ContractConceptResolution
  concept_contract_refs: [str]
  generated_instance: GeneratedInstance
  problem: {
    visible_givens: [TypedValue]
    question: str
    assumptions_used: [str]
    applicability_conditions_used: [str]
  }
  execution_trace: ExecutionTrace
  teaching_trace: TeachingTrace
  projection: TeachingProjection
  checkpoints: [TeachingCheckpoint]
  final_result: TypedValue | StructuredResult
  decision_evidence: [DecisionEvidence]
  verification: VerificationVector  # narration_fidelity remains not_run in this pre-narration artifact
}

DeliveryEvidenceRecord {
  delivery_evidence_id: str
  evidence_id: str
  evidence_digest: str
  lesson_id: str
  rendered_card_digest: str
  card_provenance_links: [CardEvidenceLink]
  narration_fidelity: passed | failed
  post_sanitization_validation_digest: str
  created_at: datetime
}
```

The package is immutable after successful computational/conceptual verification. Cards are a view over it,
never a second solution. Narration validation necessarily happens after cards and sanitization exist, so it
is stored in a separate append-only `DeliveryEvidenceRecord`; the evidence package is never reopened merely
to change `narration_fidelity` from `not_run`.

`evidence_digest` is a SHA-256 digest over canonical serialization of every authoritative pre-narration field:
resolution, contract/grammar versions, generated instance, problem, execution and teaching traces,
projection, checkpoints, final result, decision evidence, and the pre-narration verification vector.
Persistence is insert-only after verification. Regeneration creates a new evidence id/digest. A delivery
trust label is derived only from the immutable package plus a passing delivery record.

### 5.10 Card provenance

Initial provenance is required at meaningful structured boundaries:

```text
CardEvidenceLink {
  card_id: str
  checkpoint_ids: [str]
  trace_step_ids: [str]
  formula_refs: [str]
  assumption_refs: [str]
  decision_refs: [str]
  numeric_outputs: [{ value, unit, evidence_ref }]
  structured_claims: [StructuredEvidenceClaim]
}

StructuredEvidenceClaim {
  claim_kind: formula | assumption | decision | result
  display_payload: object
  evidence_ref: str
}
```

Sentence-level provenance is not required in the first version. The narrator may paraphrase, group adjacent
checkpoints where the existing projection allows it, split a checkpoint for presentation, define terms, and
add licensed interpretations. It may not add computational claims or semantic transitions.

Formula blocks, numeric claims, assumption blocks, decision blocks, and final-result blocks are structured
fields carrying direct references. Prose around them may remain card-level. This is how v1 deterministically
enforces evidence coverage without sentence-level provenance.

Sanitization boundary: the lesson sanitizer passes (backend `_sanitize_math_in_text` and the frontend
display normalizers) aggressively rewrite LaTeX and prose. Narration fidelity is meaningless if validated on
text the learner never sees. Contract: sanitizer passes MUST NOT enter structured `display_payload` fields
(machine-checkable by semantic identity, not byte equality), and card-level prose fidelity validation runs
AFTER all backend sanitization transforms.

Structured rendering invariance means:

- the same claim kind and evidence reference;
- the same normalized expression AST;
- the same typed numeric value and unit;
- the same assumption/decision/result identity.

Harmless escaping or canonical formatting may change bytes. Frontend display passes consume structured claims
through a dedicated renderer that may format them but cannot rewrite their semantic payload. Until that
renderer exists, enforced runtime-binding cards cannot ship.

---

## 6. Verification model

Verification is stored as a vector, not one boolean:

```text
VerificationPlan {
  plan_id: str
  version: int
  assurance_profile: str
  checks: [VerificationCheckPlan]
}

VerificationCheckPlan {
  check_id: str
  check_type: recomputation | domain | boundary | property | metamorphic | differential
  authority: grammar | contract | derived
  applicability_predicate: object
  parameters: object
  required: bool
  not_applicable_reason: str | null
}

VerificationVector {
  resolution_validity: reviewed_match | deterministic_candidate | model_inferred | ambiguous | failed
  specification_validity: passed | failed
  execution_validity: passed | failed
  conceptual_validity: reviewed_match | grounded_match | user_source_match | unresolved | failed
  problem_solvability: passed | failed
  pedagogical_fitness: passed | failed
  narration_fidelity: passed | failed | not_run
  test_results: [VerificationCheck]
}
```

For the v1 assurance profile:

- resolution validity must be `reviewed_match`;
- independent recomputation is always required;
- expression-domain validation is always required;
- learner-visible problem solvability is always required;
- pedagogical fitness is always required for a delivered worked example;
- every applicable declared boundary check is required;
- at least one contract-owned or deterministically derived property check is required;
- a differential check is required when a reviewed independent reference exists;
- every skipped check records a deterministic `not_applicable_reason`.

Passing one arbitrary check is not sufficient.

`problem_solvability` proves the visible question contains sufficient, unambiguous information to reach the
stored answer. `pedagogical_fitness` proves bounded instructional suitability, not factual correctness.

What this vector establishes must be stated honestly: for a direct formula, "independent recomputation"
re-runs the same expression — it catches tampering and executor bugs, not a wrong formula. AST-derived
metamorphic checks prove the EXECUTOR, not the relationship. In v1, conceptual correctness rests entirely on
human contract review plus the resolution anchoring of §5.2; the differential check is the only true
independent oracle and exists only where a reviewed reference does. Gate-passing ≠ correct
(`WORKED_EXAMPLE_ACCURACY_SPEC.md`) remains the operative lesson.

### 6.1 Resolution validity

- Scope identity is immutable.
- The contract mapping is supported by reviewed identity evidence.
- The executable variant is explicit when it changes formula, convention, applicability, or result.
- Token similarity alone never produces `reviewed_match`.
- Ambiguous, heuristic-only, or model-only resolution does not ship a determinate numeric example in v1.

### 6.2 Specification validity

- Schema is valid.
- Grammar and version exist.
- Every required slot is bound exactly once.
- No undeclared symbol or operation exists.
- Expression AST is within the grammar allowlist and complexity bounds.
- Dependency graph is acyclic.
- Types and units are compatible.
- Every output is reachable.
- Constraints make the expression executable.
- Selected conventions are offered by the grammar.

### 6.3 Execution validity

- Execution terminates within grammar limits.
- Re-execution is deterministic.
- Every trace transition replays.
- The final result recomputes from visible givens.
- Grammar-owned invariants pass.
- Boundary and property tests pass.
- Metamorphic tests pass where the grammar declares them.
- Differential/reference checks pass where available.
- Trace reaches a declared terminal state.

### 6.4 Conceptual validity

- Canonical concept and variant match the scope plan.
- The loaded relationship belongs to the resolved contract id/version.
- The selected grammar manifest supports that relationship's nodes and value types.
- Slot bindings preserve contract symbol identity, cardinality, type, unit, and role.
- Required assumptions and applicability conditions are present.
- Sign, timing, unit, and domain conventions match.
- No excluded variant is silently substituted.
- Interpretations are licensed by grounded artifacts.
- Problem/instance generation respects every required assumption and applicability condition.

Formula/operator comparison belongs to deferred extraction validation. V1 execution never compares a
model-authored relationship with the contract because the relationship is loaded directly from the contract.

Mechanical success does not compensate for conceptual failure.

### 6.5 Narration fidelity

Reuse the trace-to-teaching checks:

- every value and unit maps to evidence;
- every formula maps to the contract;
- operations and ordering match checkpoints;
- required assumptions and decisions are represented;
- no new state transition or conclusion is introduced;
- final visible answer matches the evidence package;
- required cases are not omitted;
- fidelity is evaluated on the post-sanitization text the learner will actually see (§5.10 boundary).

### 6.6 Problem solvability and pedagogical fitness

- Every relationship free symbol resolves to a visible given, reviewed constant, or traced prior result.
- The requested output, quantity meaning, and display unit are unambiguous.
- Visible givens and assumptions independently recompute the final visible answer.
- No necessary assumption remains only in hidden metadata.
- The instance directly exercises the topic's owned learning delta and requested operation.
- Difficulty matches the certified topic depth and prerequisites.
- Values are nontrivial, readable, and not dominated by incidental conversion or rounding.
- The example has one primary learning objective and is materially distinct from sibling examples.

Failure rejects and resamples the instance when instance-specific; a persistent scope/operation mismatch
rejects the binding route for that topic.

Evaluator authority: every solvability and fitness sub-check is a DETERMINISTIC predicate over declared
parameters — §7.1's "must not ask the model whether a result looks sensible" applies here with full force,
because these are exactly the judgments that drift into model calls. Parameter sources are fixed:
`difficulty_fit` and `prerequisite_compatibility` read the certified scope plan (topic depth, declared
prerequisites); `nontriviality` and `visible_number_readability` read the generation policy's
`quality_constraints` (value ranges, integer-size and rounding bounds); `scope_relevance` and
`operation_relevance` read the contract's applicability conditions plus the topic's owned `scope_in`;
`sibling_novelty` consumes the §2.5 arbitration result plus instance-digest comparison against sibling-owned
instances — it is NOT a second similarity heuristic. A fitness check whose predicate cannot be expressed
deterministically is dropped from the profile, not delegated to a model.

### 6.7 Generated checks

The model may suggest supplementary checks, but they are advisory until accepted by a reviewed verifier.
Grammar-owned invariants remain authoritative. A binding cannot establish its own correctness by proposing an
invariant equivalent to its own expression.

---

## 7. Initial reviewed grammars

### 7.1 `direct_formula_calculation`

Purpose:

```text
declared givens
  -> select grounded relationship
  -> substitute
  -> compute
  -> attach units
  -> interpret under declared assumptions
```

Reviewed grammar owns:

- scalar typed inputs;
- restricted expression evaluation;
- substitution trace;
- output calculation;
- unit propagation;
- denominator/domain checks;
- deterministic instance generation;
- terminal result;
- teaching projection;
- baseline boundary/property tests.

Required concept-contract fields:

- canonical relationship;
- variable meanings;
- units/dimensions;
- assumptions;
- applicability conditions;
- result interpretation.

V1 supports one reviewed output relationship per executable variant. Multi-output FormulaSpec rows may use
the shared substrate only after it declares and tests an ordered output dependency DAG; Wave-0 arithmetic
closure alone does not imply that capability. Runtime symbolic rearrangement is prohibited.

Initial metamorphic checks are grammar-declared, not universal. Examples:

- direct proportionality when the grounded AST proves a variable occurs as a single multiplicative factor;
- inverse proportionality when the AST proves a variable occurs only in a denominator;
- unit-preserving recomputation;
- perturbation produces the AST-predicted change.

The system must derive these properties from the validated expression structure or a reviewed concept contract;
it must not ask the model whether a result “looks sensible.”

### 7.2 `discounted_cashflow` (v1.1, deferred from v1)

Purpose:

```text
cash flows + times + rate convention
  -> align flows and times
  -> derive period rate
  -> discount each flow
  -> aggregate
  -> optionally weight/normalize
  -> interpret at the declared valuation date
```

Reviewed grammar owns:

- aligned vector validation;
- cash-flow timing;
- valuation date;
- compounding-frequency conversion;
- sign convention;
- discount factors;
- discounted sum;
- optional reviewed weighted-average projection;
- nonzero-normalizer gate;
- money/time units;
- terminal result and trace;
- cash-flow-specific boundary and metamorphic tests.

Required explicit distinctions:

- present vs future valuation date;
- nominal vs effective rate;
- compounding frequency;
- inflow/outflow sign convention;
- Macaulay vs modified vs effective vs dollar duration where applicable;
- fixed vs state-dependent cash flows.

Example grammar-owned properties:

- scaling every cash flow by a constant scales price by that constant;
- scaling every cash flow does not change a normalized duration result;
- zero rate reduces discount factors to one under the supported convention;
- permuting aligned `(time, cash_flow)` pairs does not change aggregate value;
- permuting one vector without the other is invalid;
- later positive cash flows have no greater present value than identical earlier flows when the supported rate
  is positive.

---

## 8. Grounding policy

Grounding authority is contextual and must be recorded:

| Level | Meaning | Maximum conceptual result |
|---|---|---|
| Reviewed contract | Human-reviewed catalog artifact | `reviewed_match` |
| Authoritative retrieval | Approved textbook, standard, official reference | `grounded_match` |
| User source | Faithful to uploaded material, not independently authoritative | `user_source_match` |
| Model inferred | No external grounding | `unresolved` |

Retrieval alone does not prove a formula match. Grounded material must be transformed into the selected
grammar's normalized slots and compared with the proposed binding.

Initial extraction is grammar-directed:

```text
select reviewed grammar
  -> request only that grammar's required semantic slots
  -> parse formula into RestrictedExpression
  -> validate against source evidence
  -> reject if it does not fit cleanly
```

The first implementation does not attempt unrestricted normalization of arbitrary mathematical prose.

### 8.1 Deferred extraction artifact (Phase 3)

Runtime contract extraction is outside v1. Before Phase 3 it requires:

```text
ContractExtractionCandidate {
  candidate_id: str
  target_scope_concept_id: str
  proposed_contract_concept_id: str
  proposed_variant: str
  source_spans: [SourceSpan]
  extracted_definition: GroundedArtifact | null
  extracted_relationships: [NormalizedRelationship]
  extracted_assumptions: [GroundedArtifact]
  extracted_applicability_conditions: [GroundedArtifact]
  extracted_conventions: [GroundedArtifact]
  unresolved_fields: [str]
  extraction_confidence: decimal
  parser_evidence: [object]
}

ExtractionValidation {
  schema_validity: passed | failed
  source_alignment: passed | failed
  formula_parse: passed | failed
  variable_alignment: passed | failed
  convention_resolution: passed | failed
  round_trip_check: passed | failed
  decision: accept_candidate | retry | reject
  failures: [VerificationCheck]
}
```

An extracted contract may receive `authoritative_retrieval` only when:

- every required semantic field has exact source spans;
- no required field is supported only by model inference;
- every formula parses into the selected grammar;
- variables align completely;
- no unresolved convention can change the answer;
- normalized relationships round-trip to an equivalent source representation;
- multiple source formulas are reconciled deterministically or the candidate is rejected.

Acceptance creates a separately versioned `ConceptContract`; extraction output never flows directly into
execution.

---

## 9. Derived trust levels and shipping policy

Execution route and contract authority are stored orthogonally:

```text
execution_route:
  registered_adapter | gen_foundation | runtime_binding

adapter_authoring_shape:
  hand_coded | engine_row | not_applicable

contract_authority:
  reviewed | authoritative_retrieval | user_source | unresolved
```

Internal verification dimensions remain visible. A derived label is calculated from route, authority, and
verification vector for routing and UI:

| Derived level | Minimum conditions |
|---|---|
| `reviewed_adapter` | Exact reviewed adapter; all trace and narration checks pass |
| `verified_gen_foundation` | Post-migration only (§4.3.2): `trace_first` or `reference_backed` candidate; concept/scope match, replay, solvability, trace-to-teaching, and narration checks pass |
| `reviewed_family_binding` | Runtime binding over a reviewed concept contract + reviewed grammar; all checks pass |
| `grounded_runtime_binding` | Authoritative grounding matches validated runtime binding; execution and narration pass |
| `user_source_grounded_binding` | Binding faithfully matches the declared user source; no independent authority claim |
| `mechanically_verified_only` | Specification/execution/narration pass; conceptual grounding remains unresolved |
| `illustrative` | No determinate claim presented as verified |
| `withheld` | Required verification failed |

Rules:

- Gen-foundation provenance only nominates `verified_gen_foundation`; the label is derived only after the
  complete verification profile passes and a frozen evidence package exists. In v1, before the §4.3.2
  evidence migration, gen_foundation output keeps its existing labeling and never receives a §9 derived
  level.
- `reviewed_family_binding` additionally requires `resolution_validity=reviewed_match`.
- `mechanically_verified_only` must not display a generic “verified” badge.
- In v1, `mechanically_verified_only` is diagnostic only: a determinate numeric worked example at that level
  is withheld rather than shipped. Later product treatment requires an explicit policy decision.
- `user_source_grounded_binding` must be labeled as faithful to the provided source, not independently verified.
- A determinate numeric example cannot ship when resolution or conceptual validity is unresolved.
- Product policy may allow a clearly labeled illustrative scenario, but it must not contain an authoritative
  calculation derived from an ungrounded relationship.
- A failure after bounded repair routes to guided explanation or withhold according to
  `WORKED_EXAMPLE_ACCURACY_SPEC.md`.

---

## 10. Failure and repair policy

```text
Concept resolution ambiguous
  -> request clarification when available; otherwise illustrative comparison or withhold

Contract unavailable/untrusted
  -> do not generate an executable binding

Binding schema/type/unit failure
  -> one targeted binding repair, then withhold runtime-binding route

Concept-contract mismatch
  -> never repair by changing the grounded contract; regenerate binding or withhold

Execution/property failure
  -> regenerate instance if instance-specific; otherwise reject binding

Narration fidelity failure
  -> retry narration over the SAME frozen evidence package, max 2

Repeated failure
  -> guided explanation or withhold; never fall into an unverified from-scratch calculation
```

A repair may narrow or correct a model proposal. It may not lower the required verification standard while
retaining the same trust label.

One targeted binding repair may change only:

- grammar selection, if the same contract explicitly supports the replacement grammar;
- slot mapping;
- an allowed convention selection;
- missing non-authoritative presentation metadata.

It may not change:

- `scope_concept_id` or `resolved_contract_concept_id`;
- concept contract, relationship reference, grounded formula, or source authority;
- required assumptions or applicability conditions;
- excluded variants;
- numeric/verification policy;
- required trust threshold.

Changing a protected field requires restarting upstream resolution and produces a new proposal and decision
trace, not a repair of the existing binding.

---

## 11. Decision trace and diagnostics

Every material decision must be queryable from the persisted path/topic trace. Suggested stages:

```text
runtime_binding.concept_resolved
runtime_binding.concept_ambiguous
runtime_binding.exact_adapter_found
runtime_binding.exact_adapter_missing
runtime_binding.contract_loaded
runtime_binding.contract_extracted
runtime_binding.contract_unavailable
runtime_binding.grammar_selected
runtime_binding.family_binding_found
runtime_binding.contract_claim_won
runtime_binding.contract_claim_lost
runtime_binding.preparation_started
runtime_binding.preparation_ready
runtime_binding.preparation_failed
runtime_binding.preparation_stale
runtime_binding.safety_revoked
runtime_binding.cache_hit
runtime_binding.cache_miss
runtime_binding.gen_foundation_candidate
runtime_binding.route_selected
runtime_binding.proposal_generated
runtime_binding.proposal_rejected
runtime_binding.binding_validated
runtime_binding.execution_passed
runtime_binding.execution_failed
runtime_binding.conceptual_match_passed
runtime_binding.conceptual_match_failed
runtime_binding.evidence_frozen
runtime_binding.narration_passed
runtime_binding.narration_failed
runtime_binding.downgraded
runtime_binding.withheld
```

`runtime_binding.composition_selected` is reserved for Phase 4 and is not part of the v1 instrumentation
contract or expected coverage.

Each entry should include stable identifiers where applicable:

- concept-contract id/version;
- grammar id/version;
- binding digest;
- grounding authority;
- failed verification dimension/check;
- retry count;
- derived trust level;
- degradation reason.

The decision-trace coverage scanner should make missing instrumentation in this new pipeline visible from its
first rollout.

---

## 12. Caching, reuse, and catalog growth

### 12.1 Runtime cache

A validated binding may be cached by:

```text
(scope_concept_id, resolved_contract_concept_id, variant,
 resolution_registry_version, resolution_entry_version, concept_contract_version,
 grammar_id, grammar_version, binding_digest, execution_environment_digest)
```

The cache stores the validated binding—not one fixed learner example. Instance generation remains seeded and
varied within the reviewed grammar.

Invalidation occurs when:

- concept contract changes;
- grammar changes;
- unit/type policy changes;
- verification plan changes;
- the contract-resolution registry version that produced the binding's resolution changes — a registry
  remap can point the same scope identity at a DIFFERENT contract while every identity inside the cached
  binding (contract id/version, grammar) still digest-matches, so the registry version must be part of the
  cache key;
- a safety incident blocks the binding.

### 12.2 Promotion

Runtime artifacts are never promoted automatically. Demand telemetry may nominate a candidate when:

- the concept is frequently requested;
- repeated bindings converge structurally;
- verification pass rates are high;
- no unresolved variant conflict exists;
- failures and repairs are understood.

Promotion requires:

1. human review of the concept contract and binding;
2. permanent catalog entry;
3. adapter/family conformance tests;
4. adversarial, boundary, property, and narration tests;
5. explicit version and manifest registration.

The promotion target is the EXISTING catalog, not a third artifact type: for `direct_formula_calculation`,
promotion means authoring a T6 `FormulaSpec` row (or a hand-coded adapter where the concept warrants one) in
`families/*_specs.py`, with the concept contract retained as its review provenance. Demand telemetry
nominates into the current catalog format so contracts, spec rows, and adapters never become three parallel
catalogs to maintain.

### 12.3 Persistence boundaries

Persist for replay and audit:

- `ContractConceptResolution`;
- selected contract id/version and grammar manifest id/version;
- `ValidatedBinding` and all digests;
- `GeneratedInstance`;
- verification plan/vector;
- frozen `EvidencePackage`;
- decision trace;
- final card provenance links.

Persist only under bounded diagnostic/telemetry retention:

- rejected binding proposals;
- bounded rejected-candidate samples;
- supplementary check suggestions;
- narration retry payloads.

Do not persist indefinitely:

- raw prompts;
- verbose model reasoning;
- unused extraction drafts;
- unbounded rejected raw values.

Retention policy must preserve the minimum artifacts needed to reproduce an output without retaining private or
non-authoritative generation exhaust.

### 12.4 Evidence storage shape

The lesson stores `evidence_id`, `evidence_digest`, `delivery_evidence_id`, derived trust label, and card
provenance links. The immutable
`EvidencePackage` is stored once in a dedicated backend record/object (`evidence_packages`, §17.3), not
embedded repeatedly in lesson cards.

The evidence record is append-only once `verification_completed_at` is set. Narration/card validation is
stored in an append-only delivery record. Final enforcement rejects a missing package or delivery record,
digest mismatch, altered card provenance/rendered-card digest, or artifacts that did not jointly pass the
route's required verification profile.

For v1, the stored package contains the generated instance, verification vector, teaching trace/checkpoints,
and compact execution trace required for replay. Raw execution detail beyond that compact trace is retained
only for fixtures, failures, and sampled production. Cards reference evidence by stable ids.

Deletion/version policy must preserve referential integrity:

- a lesson's evidence package is immutable;
- newer generation creates a new evidence id;
- contract/grammar retirement does not mutate historical evidence;
- replay uses recorded versions/digests or reports `historical_executor_unavailable`;
- storage retention may remove diagnostic exhaust but not evidence referenced by an active lesson.

---

## 13. Rollout

Suggested feature flag:

```text
AZALEA_GROUNDED_RUNTIME_BINDING = off | shadow | enforced
```

Latency is part of the v1 contract, not an open decision: the current full-path build budget (~1 minute for
a 7-topic path) is hard-won. Runtime binding must (a) declare a per-topic latency budget with automatic
degradation to the next tier when exceeded, and (b) run at PLAN TIME where possible — topics are known at
decomposition, so contract resolution, binding validation, and the assurance profile can run in parallel
with lesson generation rather than inline in the solve path, with the §12.1 cache making every repeat hit
free. Only the numeric value of the budget remains open (§19 item 5).

### Phase 0 — offline fixtures

- Implement artifact schemas and restricted expression parser.
- Implement the shared scalar executor, numeric policy, and unit registry.
- Classify every authored T6 FormulaSpec row by convergence wave and emit blockers for non-Wave-0 rows.
- Compile Wave-0 rows into the restricted AST in shadow and pass their behavior-diff gate.
- Move Wave-0 authored T6 onto the shared substrate before v1 runtime binding can be enforced.
- Implement `direct_formula_calculation` over that substrate.
- Use reviewed fixture contracts only.
- No LLM binding generation and no user impact.

### Phase 1 — shadow binding

- On exact-adapter misses, generate and validate binding proposals.
- Execute and compare results, but do not alter delivered lessons.
- Record decision trace, latency, cost, match rate, and failure dimensions.

### Phase 2 — reviewed-contract enforced slice

- Allow runtime binding only when a reviewed concept contract exists.
- Ship under `reviewed_family_binding`.
- Start with several direct-formula concepts.

### Phase 3 — authoritative-grounding slice

- Add grammar-directed extraction from approved sources.
- Ship only when conceptual validity reaches `grounded_match`.
- Add the separately gated `discounted_cashflow` v1.1 slice after scalar formula binding is stable.

### Phase 4 — trusted composition

- Add bounded DAG composition over reviewed primitives.
- No branching, recursion, or custom iteration.
- Repeated successful compositions become reviewed families.

No phase begins until the prior phase's verification and decision-trace coverage are measurable.

### 13.1 Deferred `CompositionPlan` boundary

Composition is not implemented or routed in v1. Before Phase 4, this spec must be versioned with a concrete
`CompositionPlan` contract. Its minimum constraints are already binding:

- directed acyclic graph;
- reviewed typed primitives only;
- fixed maximum nodes and depth;
- no branching, recursion, custom iteration, or mutation;
- statically checkable types and units;
- each node resolves to a reviewed primitive version and owns its trace contract.

### 13.2 Plan-time preparation lifecycle

Runtime-binding preparation is persisted independently from lesson generation:

```text
not_requested -> preparing -> ready
                         \-> failed
ready --------------------> stale
```

`PreparedRuntimeBinding` records topic id, contract/grammar versions, the resolution-registry version its
resolution was produced under, all digests, status, timestamps, failure reason, and claimant/ownership result.
It also records:

```text
preparation_identity_digest
status_version
resolution_entry_version
safety_block_version
superseded_by_preparation_id
```

Persistence home is a dedicated `prepared_runtime_bindings` table keyed by topic id + preparation version, not
`decomposition_metadata`: preparation is asynchronously mutable, independently staleable, and must support
atomic status transitions without rewriting the topic's historical decomposition record. The topic metadata
stores only eligibility/claim decisions and the active preparation id when one is selected.

Rules:

- Certification may stamp `runtime_binding_eligible`; eligibility authorizes preparation, not shipping.
- The solver ships only from `ready` preparation whose versions/digests still match.
- Contract, grammar, unit, numeric, generation, verification, resolution-registry, or scope-plan changes mark
  preparation `stale`.
- A solver encountering `preparing` waits only within its remaining per-topic budget, then degrades.
- A cache miss may prepare synchronously only within that same budget.
- Regeneration reuses `ready` preparation when all identities match; otherwise it creates a new preparation.
- `failed`, timed-out, or stale preparation restores current withhold behavior.
- Final enforcement trusts the frozen passing `EvidencePackage`, never the earlier eligibility stamp.
- `preparation_identity_digest` covers topic/scope identity, resolution registry and entry versions,
  contract/grammar/environment versions, and claimant intent. At most one non-superseded
  `preparing|ready` row may exist for the same identity.
- Status transitions use compare-and-swap on `status_version`. A worker prepared against an older registry,
  scope plan, safety-block version, or active preparation cannot mark itself ready.
- Selecting an active preparation and superseding the previous one is atomic. A late worker may persist
  diagnostics but cannot reactivate an older preparation.
- A safety incident increments `safety_block_version`, stales affected preparations/cache entries, and emits
  `runtime_binding.safety_revoked`.
- Retrying a failed preparation creates a new preparation version; it never mutates a failed artifact into a
  ready one.

Contract resolution, deterministic binding validation, and instance preparation may run concurrently across
topics after decomposition. They may not race lesson persistence without the status/version checks above.

---

## 14. Minimum vertical slices

### 14.1 Direct formula

Use a concept deliberately absent from exact routing but covered by a reviewed test contract. The end-to-end
fixture must not disable or bypass exact lookup: a genuine registered-routing miss is part of acceptance.

Acceptance:

- exact adapter lookup misses;
- scope identity maps to one reviewed contract concept and executable variant;
- reviewed contract loads;
- `direct_formula_calculation` selected;
- binding validates without Python `eval`;
- a `GeneratedInstance` records seed, candidate rejection, raw/visible values, numeric policy, and digest;
- units and domain constraints pass;
- execution recomputes the final result;
- the v1 assurance profile runs independent recomputation, expression-domain validation, every applicable
  boundary check, at least one required property check, and a differential check when a reference exists;
- evidence package freezes;
- every formula, number, unit, assumption, decision, and final result in cards maps to evidence;
- decision trace reconstructs every route and verification decision;
- final derived level is `reviewed_family_binding`.
- learner-visible problem solvability and pedagogical fitness pass.

### 14.2 Discounted cash flow (v1.1)

Use a small fixed-cash-flow instrument under one explicit compounding convention.

Acceptance:

- timing, valuation date, sign convention, and rate convention are explicit;
- aligned vectors are enforced;
- discounted values independently recompute;
- scaling and pair-permutation properties pass;
- the final interpretation names the exact duration/value variant;
- no excluded duration variant appears in narration.

---

## 15. Acceptance tests

Each test binds to a named §17.2 fixture so the table is executable as written — e.g., tampered final
result → `ohms_law`; zero denominator → `density` with V = 0; unit mismatch → `kinetic_energy` with v
supplied in km/h unconverted; wrong relationship reference → a binding for `simple_interest` attempting to
reference another contract's relationship.

### Artifact and parser

- Reject arbitrary calls, attributes, comprehensions, conditionals, loops, and undeclared symbols.
- Reject ASTs above depth/node limits.
- Reject cyclic binding dependencies.
- Prove contract/runtime expressions never enter the authored `formula_engine._eval` string-evaluation path.
- Binding digest changes when contract, relationship, grammar, convention, or slot binding changes.
- Environment digest changes when numeric, unit, verification, parser, or primitive versions change.
- Instance digest changes when seed, generation policy, values, numeric policy, or expected result changes.
- Every registered T6 row receives exactly one convergence wave and explicit required-node/function set.
- Every registered T6 row also receives an execution-shape capability report; rational-only multi-output,
  custom-sampling, or custom-trace rows are not falsely classified as migratable.
- Every Wave-0 row matches legacy displayed results/intermediates under §2.3.2 rather than bit-level float
  equality.
- A `sqrt` row is classified into Wave 2 and does not block the Wave-0 gate.

### Concept resolution and grounding

- Ambiguous duration does not silently select Macaulay duration.
- A wrong-but-unambiguous-looking resolution (single candidate contract, model-inferred mapping only) records
  `mechanically_verified_only` diagnostically and withholds the determinate example in v1.
- Explicit Macaulay goal excludes modified/effective duration.
- User-source-only grounding cannot produce `grounded_runtime_binding`.
- A relationship reference from a different contract/version fails conceptual matching.
- Phase 3 extraction separately rejects a formula with correct symbols but wrong operator structure.
- Missing applicability conditions block verified shipping.

### Specification and execution

- Undefined variable fails specification validity.
- Unit mismatch fails specification validity.
- Zero denominator is rejected or excluded by generated instances.
- Same seed and binding produce identical trace and result.
- Missing visible input, ambiguous requested output, hidden required assumption, or missing display unit fails
  problem solvability.
- A mathematically valid instance that is off-scope, trivial, prerequisite-incompatible, or duplicates a
  sibling-owned operation fails pedagogical fitness.
- Tampered final result fails independent recomputation.
- Grammar-owned metamorphic failure rejects the binding/instance.
- Generated supplementary invariant alone cannot authorize a binding.
- Cross-currency input is rejected; no exchange rate is loaded from the unit registry.

### Narration

- Invented number fails fidelity.
- Changed unit fails fidelity.
- Changed formula fails fidelity.
- Unsupported interpretation fails fidelity.
- Grouped/split presentation with complete evidence references passes.
- A narration retry reuses the same evidence id and binding digest.

### Routing and degradation

- Exact adapter always wins over runtime binding.
- A registered reviewed adapter/engine row wins over runtime binding.
- Failed conceptual matching never falls to legacy from-scratch calculation.
- Repeated narration failure produces guided/withheld state.
- Every material branch produces a decision-trace entry.
- Gen_foundation `ground_truth_source=trace_first|reference_first` may outrank runtime binding; absence of
  those signals does not. In v1 the winning candidate ships under gen_foundation's existing internal gating
  (§4.3.2); after the evidence migration it additionally requires frozen evidence and the complete
  applicable verification profile.
- Post-migration only (§4.3.2): a forged positive gen_foundation provenance flag without replay/scope/
  fidelity evidence is withheld.
- A valid evidence id paired with a mismatched evidence digest or altered card provenance is rejected.
- Accuracy-ladder `verification_level=model_only` is never interpreted as gen_foundation provenance.
- Concurrent preparation uses atomic table transitions and stale versions cannot become active.
- A resolution-registry version bump marks affected prepared bindings stale and invalidates their cache
  entries; a solver can never ship an example resolved under a superseded registry mapping.

---

## 16. Telemetry

Minimum event fields:

```text
topic_id
study_path_id
scope_concept_id
resolved_contract_concept_id
variant
scope_plan_role
exact_adapter_hit
concept_contract_source
concept_contract_version
grammar_id
grammar_version
binding_digest
execution_environment_digest
instance_digest
numeric_policy_id
generation_policy_id
verification_vector
failed_checks
retry_counts
derived_trust_level
final_route
latency_by_stage
model_calls_by_stage
degradation_reason
```

Dashboards should answer:

- Which concepts most often miss exact adapters?
- Which reviewed families cover those misses?
- Where do bindings fail: resolution, grounding, schema, units, execution, properties, or narration?
- Which runtime bindings recur often enough to promote?
- How much latency and cost does the fallback add?
- Are mechanically verified outputs ever mislabeled as conceptually grounded?
- Does any exact-adapter topic incorrectly reach runtime binding?

---

## 17. Initial implementation surface

### 17.1 Ordered implementation units

1. **Artifact and manifest foundation**
   - `GrammarManifest`, `ConceptContract`, `NormalizedRelationship`, symbol metadata,
     `RestrictedExpression`, `NumericPolicy`, canonical serialization, and digesting.
   - No model calls or lesson integration.
2. **Restricted scalar executor**
   - Literal, variable, add, subtract, multiply, divide, integer power, and negation.
   - Decimal/rational arithmetic, domain constraints, canonical units, deterministic replay.
3. **Authored T6 convergence**
   - Classify every reviewed `FormulaSpec` row into a convergence wave.
   - Parse Wave-0 rows into the restricted AST in shadow and run the declared behavior-diff policy.
   - Move Wave-0 T6 rows onto the shared substrate only after equivalence is proven; report exact blockers for
     every later-wave row.
4. **Reviewed contract fixtures**
   - Structurally diverse formulas; no runtime extraction.
5. **Deterministic binding and instance generation**
   - Derive binding where possible; seed control, quality rejection, raw/displayed values, reproducibility.
6. **Existing trace-chain integration**
   - Produce the existing execution/teaching traces, projection, and checkpoints; no narration yet.
7. **Verification and evidence freezing**
   - Assurance profile, recomputation, unit/domain/property checks, digests, immutable evidence.
8. **Evidence-linked narration**
   - Structured claim blocks and trace-to-teaching validation.
9. **Shadow model binding**
   - Only after offline fixtures pass; compare model proposals to deterministic/reviewed expected bindings
     without affecting delivered lessons.

Deferred beyond these units (explicitly NOT v1 scope): the **gen_foundation evidence migration** (§4.3.2) —
wrapping the live gen_foundation route in `EvidencePackage`/`DeliveryEvidenceRecord` so it can earn the
`verified_gen_foundation` label. Scheduled no earlier than Phase 2, with a behavior-diff against the
pre-migration route before cutover.

### 17.2 Initial reviewed fixture sets

Use two distinct fixture groups.

**A. Shared-substrate equivalence fixtures.** These existing registered FormulaSpec rows favor
expression-structure diversity over domain count and prove legacy/shared-substrate behavior equivalence:

```text
Ohm's law                 I = V / R                 division
Kinetic energy            KE = (1/2) m v^2         constant + multiplication + power
Simple interest           A = P (1 + r t)           nested multiplication + addition
Density                    rho = m / V               division with physical constraints
Potential energy          PE = m g h                multivariable multiplication
```

These fixtures must resolve through the registered adapter route in product-like tests. They do not prove
runtime-fallback routing.

**B. Runtime-fallback routing fixtures.** Add at least three reviewed `ConceptContract` fixtures deliberately
absent from the registered adapter/FormulaSpec manifest:

- one single-output division relationship with a nonzero-domain constraint;
- one nested add/multiply relationship with a dimensional or rate convention;
- one integer-power relationship with a reviewed physical applicability condition.

Each has a reviewed resolution-registry entry but no registered routing alias or FormulaSpec row. The
acceptance test runs the normal router, proves both exact lookups miss, and reaches runtime binding. Fixture
concept names are selected only after asserting they are absent from the live manifest; the test fails if
future catalog growth registers them without updating the fixture.

Affine temperature conversion is intentionally deferred until the unit system explicitly supports affine
units; ordinary multiplicative unit conversion is insufficient.

### 17.3 Files

Expected new modules:

```text
backend/app/services/examples/runtime_binding/
  artifacts.py
  resolver.py
  contract_store.py              # ConceptContract + ContractResolutionRegistry
  restricted_expression.py
  convergence.py                 # T6 wave classification + behavior-diff report
  validator.py
  executor.py
  verification.py
  evidence.py
  router.py
  telemetry.py
  grammars/
    direct_formula.py
```

Expected persistence change:

```text
backend/app/models/prepared_runtime_binding.py
backend/app/models/evidence_package.py         # §12.4's immutable evidence store — the most durable
                                               # artifact in the design needs a named home, not an implied one
backend/app/models/delivery_evidence.py        # post-sanitization narration/card fidelity bound to evidence
backend/app/db/base.py                         # import/register all three models
database schema migration for prepared_runtime_bindings + evidence_packages + delivery_evidence
```

The repository currently has no Alembic migration tree and `Base.metadata.create_all()` does not alter
existing deployed tables. Implementation planning must choose and test an explicit safe schema-migration
mechanism before these persistence units ship; adding only the SQLAlchemy models is insufficient.

`discounted_cashflow.py` and aligned-vector expression nodes belong to the v1.1 implementation surface.

Expected integration points:

- `solver.py` (`solve_worked_example`) — the LIVE chain: after the registered-adapter attempt, gen_foundation
  outranks runtime binding only for `trace_first`/`reference_backed` output (§4.3); model-only output does not.
  Runtime binding remains before unverified problem-first LLM fallbacks. `accuracy_ladder.py` is NOT the
  integration point: the ladder is off by standing decision and code placed there never executes.
- `topic_generator.py` (`_certify_path_scope`) and `handoff.py` (`enforce_example_plan`): the §2.4
  route-aware certification stamp and evidence-package acceptance.
- `trace_pipeline.py`: reuse existing artifact/narration path after binding execution.
- `trace_adapters/artifacts.py`: reuse existing trace/projection/checkpoint types; do not duplicate them.
- `topic_scope_service` / persisted scope plan: consume the immutable scope identity and record contract-variant
  mapping evidence without overwriting that identity.
- `decision_trace.py`: record route and verification decisions.
- `decision_trace_coverage.py` / `explain_path.py`: report instrumentation presence and actual decisions.
- trace-to-teaching validator: verify evidence-linked cards.

Do not modify the current formula engine to accept untrusted expression strings.

### 17.4 Infrastructure go/no-go checkpoint

After implementation units 1–3, continue to runtime binding only if all are true:

- every registered T6 row is deterministically classified into a convergence wave;
- every Wave-0 row compiles to `RestrictedExpression` and passes the behavior-diff gate;
- every later-wave row reports its exact unsupported nodes/functions;
- behavior-diff tests show no unexplained execution, rounding, unit, trace, or display drift;
- the shared substrate is simpler to reason about than maintaining two formula executors;
- one reviewed `ConceptContract` can map onto it without adding executable semantics;
- the proposed evidence/verification model supplies audit information unavailable from today's FormulaSpec
  path and is clearly reusable by Phase 3 extraction.

If these conditions fail, stop the runtime-binding build. Extend `FormulaSpec` with richer contract metadata
and continue catalog growth through the existing adapter system instead.

---

## 18. Non-goals

- Arbitrary runtime adapter code generation.
- A general-purpose programming language or unrestricted DSL.
- Runtime-generated verifier logic.
- Automatic adapter promotion.
- General proof verification.
- Executable causal-mechanism or model-comparison adapters.
- Treating user-uploaded content as automatically authoritative.
- Treating model agreement as independent verification.
- Replacing exact reviewed adapters.
- Generating visuals; the evidence package may later support them, but visuals remain a separate layer.

---

## 19. Open decisions

1. Which approved sources qualify as `authoritative_retrieval` per domain?
2. Should an ambiguous variant pause generation for learner clarification or always degrade automatically?
3. Should `discounted_cashflow` be a separate grammar permanently or later specialize a generic discounted
   aggregation grammar?
4. What is the future product treatment for `mechanically_verified_only` after v1's withhold-only policy?
5. The numeric value of the per-topic latency budget. (The structure — budget + automatic degradation +
   plan-time execution + binding cache — is decided in §13; only the number remains open.)
6. Which explicit database-migration mechanism will create/update `prepared_runtime_bindings` and
   `evidence_packages` in existing deployments? Blocking before the persistence units ship.
   Recommendation: adopt Alembic once rather than a one-off guarded script — three new tables are already
   required, Phase 3's contract store will add more, and an ad-hoc migration path becomes its own
   maintenance problem.

---

## 20. Definition of done for v1

- [ ] Exact adapters remain the first and exclusive source of truth when applicable.
- [ ] Every Wave-0 T6 row and v1 runtime binding use the same restricted executor and numeric/unit substrate;
      later-wave or execution-shape-incompatible rows are enumerated with exact blockers.
- [ ] Runtime contract expressions cannot reach Python `eval` or arbitrary execution.
- [ ] `direct_formula_calculation` executes a reviewed concept contract end to end.
- [ ] v1 supports scalar typed values only; extraction, vectors, composition, and discounted cash flow remain
      outside the shipping route.
- [ ] Runtime proposals bind a contract-owned relationship and cannot supply formula semantics.
- [ ] Generated instances and numeric policy make every example reproducible at displayed precision.
- [ ] Verification dimensions are stored separately and derive an honest trust level.
- [ ] Learner-visible problem solvability and pedagogical fitness are required shipping dimensions.
- [ ] Concept/variant ambiguity cannot silently select a materially different formula.
- [ ] Grammar-owned boundary, property, and metamorphic tests run.
- [ ] Evidence packages are immutable and cards carry required provenance.
- [ ] Evidence packages have canonical pre-narration digests; lessons bind evidence id/digest plus an
      append-only delivery record covering rendered cards and post-sanitization narration fidelity.
- [ ] Narration cannot change formulas, values, units, assumptions, decisions, or conclusions.
- [ ] Failed grounding or verification never falls to a from-scratch authoritative calculation.
- [ ] Every material route and verification decision is persisted and explainable.
- [ ] Runtime bindings remain nominations—not automatic additions—to the permanent catalog.
- [ ] The live integration point is `solve_worked_example` (§17.3); nothing routes through the disabled
      accuracy ladder.
- [ ] Certification and `enforce_example_plan` are route-aware per §2.4; a runtime-binding example is never
      generated on a topic that finalize will strip.
- [ ] A per-topic latency budget with automatic degradation is enforced, and plan-time preparation plus the
      binding cache keep the full-path build inside its current budget (§13).
- [ ] V1 withholds every determinate example whose resolution is not `reviewed_match` (§5.2, §6, §9).
- [ ] Gen_foundation outranks runtime binding only with `trace_first` or `reference_backed` provenance (§4.3).
- [ ] Positive gen_foundation provenance decides route order only in v1; the live route ships under its
      existing gating, and the `verified_gen_foundation` label/checks activate solely with the §4.3.2
      evidence migration (named deferred work, not a v1 obligation).
- [ ] Contract ownership arbitration prevents sibling topics from repeating the same exercise (§2.5).
- [ ] Prepared binding state/version checks prevent stale or raced artifacts from shipping (§13.2).
- [ ] Runtime-fallback end-to-end fixtures genuinely miss registered routing; registered T6 fixtures are used
      separately for substrate equivalence.
- [ ] Structured claim rendering preserves semantic identity through backend and frontend transforms (§5.10).
- [ ] Ships with `AZALEA_GROUNDED_RUNTIME_BINDING=shadow` as the default until Phase 2 criteria are met.
