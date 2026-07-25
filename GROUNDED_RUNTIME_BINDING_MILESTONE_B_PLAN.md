# Grounded Runtime Binding — Milestone B Implementation Plan

> **Status:** Implementation plan. Authority: `GROUNDED_RUNTIME_BINDING_SPEC.md` v1.0.6, §17.1 units 5–9,
> §20.2, and the §2598 continue-gate (passed by Milestone A, commit `3096120`).
> **Scope:** Offline runtime-binding evidence only. Entirely in-memory / fixture-backed. This plan does NOT
> authorize any live solver route, production database, sibling arbitration, preparation service, delivery
> evidence, frontend renderer, `we_policy` change, or model-assisted binding (all Milestone C or post-v1).

## 1. Objective and stop condition

Prove, offline, that a reviewed `ConceptContract` absent from the registered adapter/FormulaSpec manifest can
be deterministically resolved, bound, instantiated, executed on the Milestone A substrate, verified, and
frozen into an immutable in-memory `EvidencePackage` whose cards trace back to that evidence — with **no
pre-narration model call** and a **genuine registered-lookup miss** on the way in.

Milestone B is complete when every offline acceptance/replay fixture passes (§20.2). It stops at the boundary
to Milestone C: the first thing requiring persistence, live routing, or a §19 persistence/latency decision.

## 2. What B reuses (no duplication)

- Substrate (Milestone A): `restricted_expression`, `executor.execute_descriptor`, `units.parse_unit`,
  `policy` digests, `artifacts.AuthoredRelationshipDescriptor`.
- Trace types: `trace_contract.ContractTrace` / `Step`; `trace_adapters.artifacts.LessonIntent`,
  `TeachingProjection`, `TeachingCheckpoint`.
- The registered-adapter route (`trace_pipeline.route_adapter`) as the lookup whose MISS gates binding.

## 3. Tickets

### B5 — reviewed contract + resolution fixtures
- `contract.py`: `ConceptContract`, `NormalizedRelationship`, `SymbolContract`, `GroundedArtifact`,
  `ConceptConstraintSet`; a deterministic builder compiling the reviewed relationship into an
  `AuthoredRelationshipDescriptor` (fail-closed, reusing the substrate compiler path). Every executable field
  reviewed; model-inferred fields impossible in v1 (fixtures only).
- `resolution.py`: `ContractResolutionEntry`, versioned `ContractResolutionRegistry`,
  `ContractConceptResolution`, and `resolve()` — reviewed authority only (exact concept id / reviewed alias);
  token similarity never yields `reviewed_match`.
- `grammar.py`: the `direct_formula_calculation` `GrammarManifest` (slots, allowed nodes, policy refs).
- `fixtures.py`: three reviewed contracts deliberately ABSENT from the live manifest (§17.2 group B) —
  single-output division w/ nonzero domain; nested add/multiply w/ a rate/dimensional convention;
  integer-power w/ a physical applicability condition — plus their registry entries. A fixture test asserts
  each is absent from the live routing manifest and fails if catalog growth later registers it.

### B6 — deterministic binding + instance generation
- `binding.py`: deterministic `BindingProposal` (no model), `ValidatedBinding` with `binding_digest`;
  validation checks slots/types/units/domain against the grammar + contract.
- `generation.py`: `GenerationPolicy`, seeded `generate_instance`, `InstanceQualityResult` (domain validity,
  nontriviality, readability, rounding stability), reproducibility (same seed → same instance), `instance_digest`.
- `pedagogy.py`: minimal versioned `PedagogicalPolicy` + deterministic `PedagogicalConstraint` predicates
  used later by fitness (difficulty/nontriviality/readability/objective-count) — data + predicates only.

### B7 — trace-chain integration
- `trace.py`: from an executed instance build a `ContractTrace` (parameterize/substitute/compute/evaluate
  Steps), a `TeachingProjection`, and `TeachingCheckpoint`s. No narration/LLM. Authoritative intermediates
  come from the substrate execution, never re-derived.

### B8 — verification + immutable evidence
- `verification.py`: `VerificationCheck`, `VerificationVector`, and the v1 assurance profile — resolution
  validity, specification validity, execution validity (independent recomputation via the substrate),
  domain, AST-derived property/metamorphic (proportionality/inverse), problem solvability, pedagogical
  fitness. Honest: recomputation catches tampering/executor bugs, not a wrong reviewed formula.
- `evidence.py`: frozen immutable `EvidencePackage` + `evidence_digest`; `CardEvidenceLink` /
  `StructuredEvidenceClaim`; an in-memory insert-only store. Regeneration → new id/digest.

### B9 — offline evidence-linked narration + end-to-end
- `problem.py`: neutral `ProblemStatement` + deterministic pure-substitution renderer; display text validated
  against the structured target/operation/unit fields.
- `router.py`: offline `bind_offline(scope_concept_id, lookup_fn)` — proves the registered lookup MISSES,
  then runs resolve→bind→generate→execute→verify→freeze, returning evidence + decision, never touching a
  live route.
- End-to-end fixture test: registered miss → verified frozen evidence, replay-stable, cards trace to evidence.

## 4. Explicit non-work (Milestone C / post-v1)
Persistence/migrations, prepared-binding lifecycle, sibling/claim arbitration, solver/certification wiring,
`we_policy`, live route ordering, delivery evidence, frontend renderer, decision-trace/telemetry wiring,
model-assisted binding, authoritative extraction, contextual scenario catalog, vectors/aggregates/affine
units. No ticket may smuggle these in.

## 5. Gate
Every offline acceptance/replay test green; suite at the 19-name baseline; then stop for the Milestone C
persistence/latency decisions (§19).
