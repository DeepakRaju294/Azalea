# Grounded Runtime Binding — Milestone A Implementation Plan

> **Status:** Initial implementation plan grounded in the live T6 catalog on 2026-07-24.
> **Authority:** `GROUNDED_RUNTIME_BINDING_SPEC.md` v1.0.6.
> **Scope:** Shared-substrate Milestone A only. This plan does not authorize runtime binding, production
> evidence persistence, sibling claims, live route changes, frontend work, or model-assisted binding.

## 1. Objective and stop condition

Determine whether the live authored T6 formula catalog can move from reviewed expression strings and float
evaluation to one restricted, exact, unit-aware scalar substrate without changing authoritative behavior or
increasing execution complexity.

Milestone A is successful only if the §17.4 go/no-go gate in the architecture spec passes. If it fails, stop
the runtime-binding build and improve the existing `FormulaSpec` system instead.

## 2. Preliminary live-catalog inventory

Source of truth:

```text
backend/app/services/examples/trace_adapters/families/formula_specs.py::ALL_SPECS
backend/app/services/examples/trace_adapters/families/formula_engine.py::FormulaSpec
```

The initial read-only inventory found:

| Measure | Count |
|---|---:|
| Total `FormulaSpec` rows | 133 |
| Registered/live rows | 132 |
| Scalar, single-output rows | 116 |
| Scalar, multi-output rows | 7 |
| Dataset rows | 6 |
| Paired-dataset rows | 3 |
| Rows with constants | 10 |
| Rows with `instance_ok` | 5 |
| Rows with an interpretation callback | 1 |
| Preliminary rational-AST single-output candidates | 95 |

The 95-row figure is a preliminary syntax-and-shape upper bound, not the frozen Wave-0 result. It requires
compiler, unit, domain, callback, trace, and teaching-projection classification.

### 2.1 Preliminary expression distribution

Most frequent shapes among the 95 preliminary candidates:

| Row count | Operator set |
|---:|---|
| 17 | multiplication |
| 13 | division + multiplication |
| 11 | division |
| 9 | addition + division + multiplication |
| 6 | division + multiplication + integer power |
| 6 | division + multiplication + subtraction |
| 5 | multiplication + integer power |
| 4 | division + subtraction |
| 3 | addition + multiplication |
| 3 | addition + multiplication + subtraction |
| 3 | addition |

### 2.2 Known initial blockers

- Function calls: `sqrt`, trigonometric functions, `exp`, `abs`, `max`, factorial, and similar helpers.
- Dataset operations: `sum`, `min`, `max`, median, aligned vectors, `zip`.
- Multi-output dependency and teaching-trace shapes.
- Affine temperature semantics even where arithmetic syntax is rational-closed.
- Custom `instance_ok` and interpretation callbacks that require explicit capability treatment.
- Reviewed constants whose identity, exact typed value, unit, and source row must survive compilation.

Traffic coverage is not yet available from this inventory. Ticket A1 must report catalog coverage separately
from production execution-volume coverage and identify the telemetry source or gap.

## 3. Implementation tickets

### A1 — T6 inventory extractor

Deliver a read-only extractor that:

- Enumerates every registered and non-registered row.
- Parses every output expression without executing it.
- Reports expression nodes, function calls, output dependency shape, datasets, constants, callbacks, units,
  conventions, trace stages, registration state, and source locations.
- Produces per-row `CompileResult`:

```text
CompileResult {
  status: compiled | blocked | invalid
  ast: RestrictedExpression | null
  required_wave: int | null
  unsupported_constructs: [str]
  execution_shape_blockers: [str]
  source_locations: [SourceLocation]
}
```

- Reports both row coverage and available production execution-volume coverage.
- Never rewrites, normalizes heuristically, or executes an unsupported source expression.

Acceptance:

- All 133 rows appear exactly once.
- A parser failure is `invalid`; an intentionally unsupported construct is `blocked`.
- Inventory output is deterministically ordered and canonically serializable.

### A2 — Wave-0 capability decision

Review the A1 report before implementing the executor.

Freeze:

- Supported nodes and integer-power/resource bounds.
- Scalar value and unit types.
- Single/multi-output policy.
- Constant representation.
- Domain-constraint derivation.
- Callback and trace-shape policy.
- Exact eligible, blocked, and invalid rows.

Report:

- Percentage of registered rows eligible.
- Percentage of production T6 executions eligible.
- Formula-family representation.
- Most common eligible execution shapes.
- Estimated migration complexity per row.
- Expected reuse by reviewed runtime relationships.

No minimum percentage is predeclared, but the go/no-go review must explicitly judge whether measured coverage
justifies the substrate.

### A3 — Restricted AST and canonical serialization

Implement the frozen Wave-0 AST without execution.

Required tests:

- Semantically identical supported source forms canonicalize identically.
- Noncommutative operand order remains distinct.
- Exact rational literals have one canonical encoding.
- Unknown nodes and noncanonical numeric encodings fail closed.
- Formatting-only source differences do not alter the canonical digest.
- Semantic changes alter the canonical digest.
- Golden canonical serializations cover representative high-frequency shapes.

Only these digests are implemented:

- `expression_canonical_digest`
- `numeric_unit_policy_digest`
- `execution_input_digest`

### A4 — FormulaSpec compiler

Compile reviewed rows into:

```text
AuthoredRelationshipDescriptor {
  relationship_id
  expression
  symbols
  units
  domain_constraints
  numeric_policy_ref
}
```

Compiler source input is the existing `Output.expr` reviewed string plus declared `givens`, `constants`,
outputs, and unit metadata. It accepts only the frozen grammar. It does not consume aliases, titles, prose,
canonical LaTeX, or helper callbacks as expression semantics.

Reviewed constants remain named artifacts:

```text
AuthoredConstant {
  constant_id
  source_row_id
  symbol
  exact_value
  unit
}
```

They are not flattened into anonymous literals when identity matters to traces or comparison.

Acceptance:

- Unsupported syntax fails before execution.
- Division produces explicit nonzero constraints.
- Undefined/dynamic symbols fail.
- Constants retain identity and units.
- Every inventory and compiler classification agrees.

### A5 — Exact scalar numeric and unit executor

Implement:

- Exact `Fraction` arithmetic.
- Multiplicative canonical units.
- Domain checks.
- AST, integer, power, numerator, denominator, and execution-time bounds.
- Deterministic replay and canonical result serialization.

Do not implement vectors, aggregates, affine units, approximating functions, or arbitrary calls.

### A6 — Execution-equivalence harness

For every eligible row compare:

- Candidate acceptance/rejection and classified reason.
- Canonical and displayed result.
- Units and domain behavior.
- Deterministic replay.

Final-result, formula, unit, domain, candidate-acceptance, or replay drift is non-waivable.

### A7 — Teaching-projection-equivalence harness

Compare independently:

- Trace stages.
- Authoritative intermediates.
- Operation order.
- Rendered authoritative fields.
- Checkpoint coverage.

`accepted_nonsemantic_drift` requires:

- Stable drift category.
- Owner.
- Reviewer and durable reason.
- Linked regression fixture.
- Expiry date or release milestone for recheck.
- Remediation decision.

It remains separate from `pass` and cannot conceal execution drift.

### A8 — Offline report and go/no-go

Produce:

- Full row/wave/blocker inventory.
- Row and traffic coverage.
- Execution and teaching-equivalence summaries.
- Separate passed, accepted-drift, blocked, and failed counts.
- Complexity comparison using a reproducible measurement manifest.
- Unsupported capability boundaries.
- Benefits to authored T6 independent of runtime binding.

Complexity manifest must name:

- Files and functions measured.
- Metric tool/version and command.
- Baseline commit.
- Whether tests/generated code are excluded.
- Core code-path counting method.

Milestone A must show direct authored-T6 value: removal of string evaluation for migrated rows, exact
arithmetic, stronger unit/domain enforcement, deterministic replay, or improved trace verification.

### A9 — Production migration plan

Created only after A8 approves continued migration.

Specify:

- Legacy-primary/substrate-shadow sampling.
- Substrate-primary/legacy-shadow fallback.
- Mismatch alerts and row quarantine.
- Rollback drill.
- Criteria for substrate-only operation and legacy removal.

Per-row state:

```text
substrate_status: enabled | shadow_only | quarantined | disabled
status_version: int
reason: str
updated_at: datetime
```

Automatic fallback is allowed for executor exception, unavailable reviewed policy/registry, timeout,
serialization failure, or internal integrity failure. A substantive result mismatch does not silently fall
back: it alerts, quarantines the row, and can disable the affected migration cohort.

## 4. Fixture selection

Do not freeze the final fixture set until A1/A2 complete.

The preliminary inventory suggests candidate structural fixtures—not final selections:

- Multiplication: `newtons_second_law`.
- Division: `density`.
- Division + multiplication: select from the most common production-relevant family.
- Add/divide/multiply: `trapezoid_area` or another high-volume representative.
- Divide/multiply/power: `kinetic_energy`.
- Reviewed constant: `weight_force`.
- Custom candidate predicate and interpretation: `reynolds_number`.

Final fixtures prioritize measured execution-shape frequency and production relevance while retaining
structural, unit, domain, constant, and teaching-trace diversity.

## 5. Explicit non-work

Milestone A does not implement:

- Full `ConceptContract` or resolution registry.
- Runtime binding or model mapping.
- Evidence or delivery records.
- Database migrations.
- Path ownership or preparation lifecycle.
- `we_policy`, solver ordering, or visible lesson changes.
- Contextual scenarios.
- Frontend structured claims.

No ticket may smuggle one of these in as preparatory work.

## 6. Immediate next ticket

Begin A1: implement the read-only T6 inventory extractor and commit its machine-readable report format before
freezing Wave-0 capability.
