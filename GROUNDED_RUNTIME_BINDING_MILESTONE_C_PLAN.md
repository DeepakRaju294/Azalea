# Grounded Runtime Binding — Milestone C Implementation Plan

> **Status:** Implementation plan. Authority: `GROUNDED_RUNTIME_BINDING_SPEC.md` v1.0.6, §17.1 units 10–11,
> §20.3, §2.5, §13.2, §4.3.2, §5.9–§5.10.
> **Entry gate (spec §2131):** C may not begin until Milestone B's offline gate passes (DONE, commit
> `77886a2`) **and the §19 persistence + latency decisions are closed.** Those two decisions are the user's;
> see §0 below. Everything past the decision boundary is blocked on them.

## 0. Blocking decisions (user) — the C entry gate

1. **Database migration mechanism (§19 item 6).** The repo has NO Alembic tree and `create_all()` cannot
   alter deployed tables. C introduces four tables (`sibling_exercise_claims`, `prepared_runtime_bindings`,
   `evidence_packages`, `delivery_evidence`). Recommendation: adopt Alembic once. **Blocked until chosen.**
2. **Per-topic latency budget (§19 item 5).** C enforces a budget with automatic degradation. The structure
   is decided; only the number is open. Needed before latency enforcement + shadow rollout.

Additional product decisions surfaced by C (not strictly blocking unit-10 scaffolding):
- ambiguous-variant behavior (pause for clarification vs auto-degrade) — §19 item 2.
- product treatment of `mechanically_verified_only` beyond withhold — §19 item 4.

## 1. Decision-INDEPENDENT scaffolding (buildable now, offline)

These are pure in-memory domain logic — no DB, no live route, no frontend — and are the foundation the rest
of C persists/wires:

- **C10a — generic exercise ownership.** `ExerciseClaim` + transactional in-memory `ClaimLedger`: at most one
  `active` claim per `(path_plan_version, ownership_tuple)`; activating a replacement atomically supersedes
  the prior; `claim_currency(claim)` true only while the claim is the active, non-superseded one.
  `path_plan_version` = deterministic digest of the certified scope plan (no plan-version column exists yet).
  Runtime binding is the FIRST consumer; the model is generic.
- **C10b — preparation lifecycle state machine.** `PreparedRuntimeBinding` + transitions
  `not_requested→preparing→ready|failed`, `ready→stale`; CAS on `status_version`; `preparation_identity_digest`
  over topic/scope + all versions; safety-block versioning; supersession; retry creates a new preparation
  (never mutates a failed one into ready). In-memory ledger; the DB is a later backing store.
- **C10c — derived trust level + canonical delivery serialization (pure).** The §9 trust-level function
  (route + authority + verification → label; `reviewed_contract_runtime_binding`), and the versioned
  canonical delivery-payload serializer + digest (§5.10) as a pure function with golden tests. No frontend.

## 2. Decision-BLOCKED work (after §0)

- **C10d — persistence + migrations.** SQLAlchemy models + the chosen migration mechanism for the four
  tables; the in-memory ledgers become thin caches over insert-only/append-only tables.
- **C10e — certification + solver integration (LIVE ROUTE).** Route-aware `we_policy='runtime_binding_eligible'`
  in `_certify_path_scope`; claim arbitration homed there; `enforce_example_plan` accepts evidence-backed
  examples; `solve_worked_example` slots runtime binding after registered adapters + verified gen_foundation,
  before unverified fallbacks. Shadow first; enforce only after the gate.
- **C10f — latency enforcement + plan-time preparation.** Budget + automatic degradation; concurrent
  plan-time preparation with the CAS/version guards. Needs the §0.2 number.
- **C11 — delivery evidence + frontend structured renderer.** `DeliveryEvidenceRecord`, post-sanitization
  validation, the frontend structured-claim renderer + semantic-identity conformance suite (§5.10), and
  enforced-slice rollback controls.
- **Decision trace + telemetry wiring** for every material route/verification/degradation decision.

## 3. Explicitly out of scope (post-v1)
gen_foundation evidence migration (§4.3.2), contextual scenario catalog, authoritative extraction,
model-assisted binding, composition. No unit may smuggle these in.

## 4. Gate (§20.3)
Shadow criteria, latency budgets, rollback behavior, and final stripping behavior pass; ship reviewed
contracts under `reviewed_contract_runtime_binding`. Enforce only after the shadow slice is clean.
