# Retrieval-Grounded Example Spec

> **Status:** Draft v0.2 — revised against a full external review (31 issues + schema revision). Phase 0
> (offline reproduction core) is IMPLEMENTED and merged; Phase 0 experimentation continues. **Phase 1 is
> BLOCKED** until the ten pre-Phase-1 decisions in §21 are resolved. Every review issue is dispositioned in
> §22.
>
> **Governing principle (from the review, adopted verbatim as law):**
> *Retrieval supplies candidate semantics; independent verification controls trust — and **verification
> evidence attaches to the exact semantic artifact it checked**. Evidence for a published instance never
> silently becomes evidence for a generated instance or a reusable concept-level contract.*
>
> **End-state target (completeness):** by the end of this spec every topic that *eligibly desires* a worked
> example (denominator defined in §1.5) gets one — adapter or not. This is pursued WITHOUT ever assigning an
> example a stronger assurance level than its evidence supports.

---

## 0. Executive decision

1. **Evidence, assurance, and scope are three separate things (§5, §8).** A *check* (span match, dimensional
   balance, reproduction, execution, endpoint agreement) is not a *trust level*, and neither is meaningful
   without a *scope* (instance / relationship / template). Assurance is *derived* from checks by a policy
   table; no generation code writes an assurance level directly.
2. **Delivery reuses the live path; we borrow the jewel, skip the machinery.** Ship through the existing
   `solve_worked_example` cascade; reuse Grounded Runtime Binding's Milestone-A dimensional check
   (`runtime_binding/units.py`,`compiler.py`) as ONE evidence check. We do NOT finish GRB Milestone C.
3. **Retrieval is a producer behind the existing resolver, not a second router (§18, issue 24).** One
   authoritative ordering owns short-circuit; retrieval exposes `try_resolve(context) -> Candidate|None`.
4. **Online resolution and offline acquisition/review are different machines (§1.6, §16).** A live lesson
   request never blocks on human review or slow acquisition; it returns the best policy-allowed output now,
   and a background worker promotes the catalog later.
5. **Soundness is operational, not absolute (§1.5, issue 5).** We guarantee *verification integrity* (no
   result is labeled beyond its evidence policy) as a hard invariant, and drive *semantic correctness* toward
   zero audited critical errors via fixtures, audits, and an incident path — a measured target, not a claim.
6. **Fail-closed, shadow-first, gated.** Each rung ships OFF → shadow (async/sampled, §14/issue 25) → live
   behind a flag, with named go/no-go gates whose metrics are precise (§14/issue 29).

---

## 1. Why this exists

No-adapter topics today get either concept-domain suppression (no example at all) or an LLM example gated only
by `answer_anchor` — which catches arithmetic inconsistency but NOT a dimensionally-plausible wrong formula,
because the model supplied both the formula and the numbers. The gap is a *correctly-assured* example for the
large class of no-adapter topics, acquired without hand-authoring an adapter per formula. Retrieval is the
acquisition path; independent checks are what make it safe; the assurance model is what keeps us honest about
exactly how safe each result is.

## 1.5 Soundness & completeness — operational definitions (issues 5, 17, 18)

**Verification integrity (hard invariant).** No artifact is assigned an assurance level whose evidence policy
(§8) is not satisfied by named, persisted `EvidenceRecord`s over *that artifact's* fingerprint. This is
inviolable and testable offline.

**Semantic correctness (measured target).** A whitelisted source can be wrong; two dependent sources can share
an error; an executor can have a bug; a reviewer can err. We therefore do NOT claim "no verified example is
ever wrong." We claim: audited factual/computational error among verified outputs stays below a defined
threshold, target zero *critical* errors, enforced by adversarial fixtures (§17), audits (§14 G1/§14 G3), and
an incident path (§10/issue 28).

**Completeness — a falsifiable denominator (issue 18).** Define `eligible_desired(topic)` = the blueprint
requests a worked example AND: blueprint structurally valid; topic allowed by content policy; requested example
KIND supported (§1.7); required source rights available (§20); language supported; no active retrieval outage
attributed. Hard topics are NOT silently excluded — each exclusion is a *categorized, counted* reason. Then:

```
Visible Coverage   = delivered            / eligible_desired      # includes provisional
Verified Coverage  = strongly_verified    / eligible_desired      # excludes provisional & answer-anchored-only
Resolved Coverage  = (verified ∨ human_approved) / eligible_desired
Provisional Exposure = provisional_shipped / delivered            # gamed-metric guard (issue 17)
```

`delivered = an actual example of the right KIND shipped` (any assurance except `guided`). `guided` is NOT
delivered; it is a tracked `coverage_gap`. **End-state (G3):** Verified+Resolved Coverage ≥ target with
Provisional Exposure bounded and shrinking — so 100% cannot be "achieved" by marking everything provisional.

## 1.6 Two machines: online resolution vs offline acquisition (issues 16, 24)

```
ONLINE  resolve_worked_example(topic) -> one of:
          DeliveredExample | ProvisionalExample | GuidedFallback | PendingAcquisition
        never blocks on network-heavy acquisition or human review; returns best policy-allowed output NOW.

OFFLINE acquisition/promotion worker, driven by AcquisitionState:
          retrieval_pending -> verification_pending -> review_pending -> approved|corrected|rejected
        promotes catalog entries; a later generation run (or regen) picks up the upgraded assurance.
```

The escalation "ladder" is a *state machine* spanning both, not a synchronous function cascade. E5 (human
review) and slow acquisition live OFFLINE; the online path emits `PendingAcquisition` + best current output.

## 1.7 What "an example" means, per kind (issue 6)

The determinacy gate ROUTES by kind; it never exempts a topic from having an example.

- **Computational** (formula/algorithm): worked example with a checked final answer + checked trace (§9).
- **Qualitative/conceptual**: a *sourced illustrative instance* — a concrete canonical scenario, span-grounded
  to a whitelisted source (an `EvidenceCheck`, not a full confirmation). Ships as `source_grounded`. This is a
  real, attributable example that counts toward Visible/Resolved Coverage — distinct from `guided`.
- **Non-exampleable / unsafe / unsupported-kind**: excluded from `eligible_desired` with a categorized reason;
  gets `guided` and a queue item, never a fabricated example.

---

## 2. Relationship to existing architecture (reuse, single owner)

| Existing component | Role | Reuse |
|---|---|---|
| `solve_worked_example` cascade (`solver.py`) | THE authoritative resolver + ordering | extended; retrieval plugs in as a producer, does not re-route (issue 24) |
| adapters / `gen_foundation` | producers 1–2 (verified) | as-is |
| `runtime_binding` A substrate (`units`,`compiler`,`executor`) | dimensional-balance + deterministic-execution checks | imported |
| `runtime_binding` B/C | **unused** | — |
| `answer_anchor` | endpoint-agreement check (WEAK, §8/issue 4) | as-is, downgraded in assurance |
| `retrieval_verify` (Phase 0) | reproduction check + fixtures | as-is |
| `guided_explanation` | guided floor output | as-is |
| `goal_plan_cache` pattern | template for the fingerprint-keyed catalog | pattern |
| `decision_trace` | every routing/check/assurance decision persisted | as-is |

**Invariant (inherited):** no new execution semantics; arithmetic runs on the existing exact executor or
deterministic eval. The LLM transcribes/narrates/proposes-mappings; it never grades its own numeric work and
never makes a final equivalence decision (§8/issue 11).

## 3. Routing cascade (short-circuit order; one owner)

```
0. CACHE          two-stage lookup (§10): concept candidate -> APPLICABILITY check -> compatible fingerprint hit
1. ADAPTER        route_adapter hits            -> trace_verified, DONE                       [S1]
2. GEN_FOUNDATION sandbox-executes              -> execution_verified, DONE                   [S1]
3. RUNTIME_BINDING(live) reviewed contract      -> execution_verified, DONE                   [if ever live]
   ── retrieval producer, reached only on a genuine miss ──
4. KIND GATE      computational | qualitative | excluded  (routes; never exempts, §1.7)
5. RETRIEVE       whitelisted, secured (§6/issue 22); record immutable snapshots (§6/issue 21)
6. CHECKS+ASSURE  run EvidenceChecks over the CANDIDATE's fingerprint; derive AssuranceLevel (§8)
7. GENERATE       ground solver; VERIFY TRACE against the assured artifact (§9); ship with assurance+sources
8. ESCALATE       FailureClass -> next state (§12); online returns best-now; offline queues acquisition/review
```

Steps 0–3 are the "already found through the pipeline" fast paths (retrieval never runs). Step 4 routes by
kind. Step 8 never silently drops: the topic exits as delivered/provisional/pending/guided **and** always
leaves either a delivered example or a logged `coverage_gap` (A17).

## 4. Cost model — savings, corrected (issue 6)

| Saving | Mechanism | Skips |
|---|---|---|
| **S1 Pipeline hit** | steps 1–3 | all retrieval + checks for pipeline-owned topics |
| **S2 Cache hit** | step 0 (fingerprint + applicability) | retrieval + transcription + checks on a *compatible* prior result (only when applicability holds, §10) |
| **S3 Kind gate** | step 4 | *numeric* transcription/reproduction for qualitative topics — but they STILL do lightweight illustrative retrieval + span check (narrowed from "skip retrieval") |
| **S4 Known-answer reproduction** | check V1 | needing to independently know the formula, *for the reproduced instance only* (issue 1) |
| **S5 Cross-source early exit** | check V2 | further fan-out once two INDEPENDENT families agree (§6/issue 10) |
| **S6 Escalate-not-loop** | step 8 | the solver's regenerate-until-plausible loops |
| **S7 Go/no-go first** | Phase 0 | building retrieval before the reproduction gate passes |

Budgets are per-path, not one aggregate (§14/issue 26).

---

## 5. Core artifacts (revised separated model — issues 1, 2, 3, 10, 14, 19, 20, 21, 23)

```python
# --- concept identity & resolution (issue 23) ---
@dataclass(frozen=True)
class ConceptResolution:
    canonical_concept: str
    variant: str                       # simple vs compound interest; perpendicular vs arbitrary-angle EMF; ...
    domain: str
    confidence: float
    evidence: tuple[str, ...]
    ambiguity_candidates: tuple[str, ...]   # low-confidence/ambiguous -> broaden or review, never auto-reuse

# --- sources (issues 10, 20, 21) ---
@dataclass(frozen=True)
class SourceSnapshot:
    content_hash: str                  # immutable identity of the exact bytes used
    snapshot_location: Optional[str]   # stored copy or None (hash + short excerpt only)
    retrieved_at: str
    retrieval_method_version: str
    license_policy_version: str

@dataclass(frozen=True)
class SourceRef:
    source_id: str
    publisher_id: str
    corpus_family: str                 # independence group; V2 needs 2 DISTINCT families (issue 10)
    upstream_source_ids: tuple[str, ...]
    edition: Optional[str]
    tier: Literal["textbook", "reference", "encyclopedic", "other"]
    reuse_policy: Literal["internal_verification_only", "short_excerpt_allowed",
                          "derived_example_allowed", "full_republication_allowed"]   # issue 20
    snapshot: SourceSnapshot

# --- candidate (what retrieval produced) ---
@dataclass(frozen=True)
class CandidateArtifact:
    artifact_id: str
    fingerprint: str                   # semantic fingerprint of THIS candidate (see invariant below)
    concept: ConceptResolution
    kind: Literal["published_instance", "relationship", "illustrative_instance"]
    payload: Mapping[str, Any]         # instance inputs+answer, or transcribed relationship, or scenario
    assumptions: tuple[str, ...]
    constraints: tuple[str, ...]       # applicability / regime (issue 12)
    regime: tuple[str, ...]
    answer_comparison: Optional["AnswerComparison"]   # for instances (issue 14)
    sources: tuple[SourceRef, ...]

@dataclass(frozen=True)
class AnswerComparison:                # issue 14 — comparison policy travels WITH the answer
    kind: Literal["exact_numeric", "relative_tolerance", "absolute_tolerance", "symbolic_equivalence",
                  "unordered_set", "interval", "textual_enum", "vector"]
    tolerance: Optional[str]           # Decimal-as-str
    expected_unit: Optional[str]
    rounding_rule: Optional[str]

# --- evidence vs assurance vs scope (issues 1, 3, 4) ---
EvidenceCheck = Literal["source_span_match", "source_independence", "dimensional_balance",
                        "published_answer_reproduction", "deterministic_execution",
                        "independent_endpoint_agreement", "trace_consistency"]

@dataclass(frozen=True)
class EvidenceRecord:
    check: EvidenceCheck
    status: Literal["confirm", "refute", "indecisive", "unsupported"]   # unsupported != pass (issue 12)
    subject_fingerprint: str           # the artifact THIS evidence is about
    verifier_version: str
    evidence: Mapping[str, Any]

AssuranceLevel = Literal["verified_execution", "verified_reproduction", "corroborated_relationship",
                         "source_grounded", "answer_anchored", "provisional", "guided"]

@dataclass(frozen=True)
class AssuranceDecision:
    level: AssuranceLevel
    subject_fingerprint: str
    reusable_scope: Literal["instance", "relationship", "template", "none"]   # issue 1/19
    policy_version: str
    evidence_ids: tuple[str, ...]

# --- delivery (issue 1 invariant) ---
@dataclass(frozen=True)
class DeliveredExample:
    semantic_fingerprint: str
    assurance: AssuranceDecision
    source_refs: tuple[SourceRef, ...]
    card_payload: Mapping[str, Any]
    # INVARIANT (enforced): delivered.semantic_fingerprint == assurance.subject_fingerprint
    # UNLESS assurance.reusable_scope in {"relationship","template"} AND card_payload was deterministically
    # derived from that relationship AND re-checked (deterministic_execution) over the NEW instance (§9).

# --- reusable catalog identity (issue 2) ---
@dataclass(frozen=True)
class ContractIdentity:
    canonical_concept: str
    variant: str
    relation_fingerprint: str
    assumptions_fingerprint: str
    symbol_schema_fingerprint: str
    unit_system: str
    verifier_version: str
    source_snapshot_version: str

# --- review & lifecycle (issues 16, 19) ---
AcquisitionState = Literal["retrieval_pending", "verification_pending", "review_pending",
                           "approved", "corrected", "rejected"]

@dataclass(frozen=True)
class ReviewCertificate:
    artifact_fingerprint: str
    approved_scope: Literal["instance", "relationship", "template"]
    reviewer_id: str
    reviewed_at: str
    source_snapshot_hashes: tuple[str, ...]
    verifier_versions: Mapping[str, str]
    assumptions: tuple[str, ...]
    decision: Literal["approved", "corrected", "rejected"]
    notes: str
```

## 6. Retrieval subsystem (issues 10, 20, 21, 22)

- **Security (issue 22).** Source IDs map to FIXED host+path policies; no model-selected URLs. Block redirects
  off-policy, private networks, and metadata services (SSRF); enforce response-size + MIME limits; sanitize
  HTML; **extraction is isolated from generation prompts** — the LLM receives structured, clearly-delimited
  *untrusted evidence spans*, never a raw page dump, and a fixed instruction that source text cannot alter
  system behavior. All fetches + redirects audit-logged.
- **Snapshots (issue 21).** Every retrieval records a `SourceSnapshot` (content hash + method/license
  versions). Audits examine the exact bytes used; cache invalidation keys off snapshot hashes + whitelist
  policy version, not a generic spec bump.
- **Independence (issue 10).** `corpus_family`/`upstream_source_ids` are maintained (initially by hand). V2
  requires two DISTINCT families; copies of one upstream do not corroborate.
- **Licensing (issue 20).** `reuse_policy` gates what delivery may do: ship the source example, paraphrase,
  or use it for internal verification only. Mode A "reproduce-and-ship" (§8) requires `derived_example_allowed`
  or stronger; otherwise only Mode B or verification-only use is permitted.
- **Determinism.** Retrievals are recorded and replayed by `(source_id, content_hash)`, keeping generation
  reproducible and enabling offline fixtures.

## 7. Transcription (prose → structured; only for `kind="relationship"`)

One bounded LLM call: untrusted evidence span → a proposed relationship (expression + typed/united symbols +
assumptions/constraints). It PROPOSES; it certifies nothing. Immediately subjected to dimensional balance and
equivalence checks (§8). `authority="authoritative_retrieval"`; the runtime-binding compiler's authority gate
is widened to accept it ONLY behind the Phase-1 flag.

## 8. Evidence checks and assurance derivation (issues 1, 3, 4, 11, 12, 13)

Checks produce `EvidenceRecord`s; a **policy table** derives the `AssuranceDecision`. No check is itself an
assurance level.

**Checks:**
- **`source_span_match`** — the claim is verbatim-supported by a source span. Proves attribution, NOT
  correctness (issue 3). Gates V1/V2 sources; alone yields at most `source_grounded`.
- **`source_independence`** — ≥2 distinct corpus families agree (issue 10).
- **`dimensional_balance`** — returns `balanced|mismatch|unsupported`; **`unsupported` is INDECISIVE, never a
  pass** (issue 12). Narrow declared scope; dimensionless constants, angles, logs/exponentials, affine temps,
  vectors, piecewise, hidden-unit empirical coefficients → `unsupported`.
- **`published_answer_reproduction`** (V1) — solver reproduces a published answer for a SPECIFIC instance,
  under that instance's `AnswerComparison` (issue 14), with the three-valued unit rule (issue 13:
  numeric+unit_match→confirm, numeric+unit_unknown→indecisive, numeric+unit_mismatch→**refute**). Already
  implemented in `retrieval_verify.py`.
- **`deterministic_execution`** — the exact executor evaluates a validated relationship on given inputs.
- **`independent_endpoint_agreement`** (answer anchor) — WEAK; the endpoint agrees but the model may have
  chosen the formula (issue 4).
- **`trace_consistency`** (§9) — the generated trace matches the assured artifact.

**V1 has two explicit modes (issue 1):**
- **Mode A — reproduce-and-ship.** Deliver a pedagogically re-narrated version of the EXACT retrieved
  instance; narration may change, the mathematical instance may not. `reusable_scope="instance"`;
  requires `reuse_policy ≥ derived_example_allowed`.
- **Mode B — derive-and-reverify.** Use the reproduced instance to APPROVE a `relationship`; then generate a
  NEW instance and independently `deterministic_execution`-check the relationship on the new inputs. Only Mode
  B may set `reusable_scope="relationship"`. Until an executable relationship exists, V1 certifies the
  original instance ONLY.

**Equivalence for V2 (issue 11) — decision is deterministic, LLM only proposes mappings:**
1. Parse both relationships to the restricted AST. 2. Normalize variable names via symbol ROLES. 3.
Canonicalize algebraic form where supported. 4. Compare normalized expressions. 5. Compare assumptions +
applicability. 6. LLM may propose symbol mappings but NEVER makes the final equivalence call. 7. Unsupported
structures ESCALATE, never "guess-equal." V2 is initially limited to relationships the restricted compiler can
normalize (e.g. `F=m*a` ≡ `a=F/m` under `m≠0`); empirical/coefficient forms need matching definitions +
assumptions, else not equivalent.

**Assurance policy table (derivation):**
```
deterministic_execution over a reviewed/relationship-approved artifact (new instance rechecked) -> verified_execution
V1 confirm (numeric+unit_match) under AnswerComparison, instance scope                           -> verified_reproduction  [instance only]
source_independence(2 families) + canonical_equivalence + dimensional_balance + applicability     -> corroborated_relationship
source_span_match only (qualitative or single-source)                                             -> source_grounded
independent_endpoint_agreement only                                                               -> answer_anchored        [NOT verified; NOT cache-promotable]
none confirm, policy permits delivery                                                             -> provisional            [enqueue review]
otherwise                                                                                          -> guided                 [coverage_gap]
```
`answer_anchored` is explicitly a weak, NON-reusable level (issue 4): it is never written as a verified reusable
contract and never promoted from cache without stronger evidence or review.

## 9. Generation + trace-level verification (issue 15)

A correct endpoint does not certify the instructional trace. After generation:
```
assured artifact -> generated trace -> trace_consistency check -> final-answer check -> ship
```
For computational examples each `TraceStep` carries structured `(input_state, operation, output_state,
narration)`. Narration may be model-authored; the state transition must be executable-or-checked against the
assured relationship. Asserts: every introduced number traces to the problem or a prior deterministic step;
every formula used matches the assured relationship; units propagate; the displayed answer equals the assured
endpoint. A trace that fails is repaired or the example is downgraded — never shipped as verified.

## 10. Catalog: keys, applicability, concurrency, correction (issues 2, 27, 28)

- **Two-stage lookup (issue 2).** `concept candidate → applicability check (assumptions/constraints/regime/unit
  system satisfied by the current topic) → exact compatible `ContractIdentity` hit`. A semantically related
  entry that fails applicability is a MISS, not a hit (simple vs compound interest, perpendicular vs
  arbitrary-angle EMF, classical vs relativistic KE, etc.).
- **Only confirmed → verified cache.** A `provisional` entry may be cached AS provisional, never promoted to
  verified without a `ReviewCertificate` or stronger evidence (§8, issue 4).
- **Concurrency (issue 27).** Idempotency keys on `ContractIdentity`; compare-and-swap promotion; **monotonic
  assurance** (a lower-assurance write never overwrites a higher-assurance valid entry); evidence merge;
  tombstones for rejected candidates; poisoning recovery.
- **Correction / revocation (issue 28).** Delivered cards store dependency links to their contract fingerprint
  + evidence snapshots. Incident path: `report → quarantine contract → stop new delivery → locate dependent
  cards → regenerate or mark corrected → invalidate descendants → re-audit the source family`. Learners who saw
  a revoked example are identifiable for remediation.

## 11. Assurance levels & shipping policy (issues 4, 9)

- **Ship as an example** iff level ∈ {`verified_execution`, `verified_reproduction`, `corroborated_relationship`,
  `source_grounded`, `answer_anchored`, `provisional`}. All count as `delivered`. Only the first three (+ human
  review) count as *strongly verified* for Verified Coverage; `answer_anchored` and `provisional` do not.
- **`provisional` requires visible trust marking (issue 9) — a Phase-2 BLOCKING frontend dependency.** Phase 2
  cannot enable provisional delivery until the frontend has: a visible provisional/under-review badge, source
  display, correction/retraction behavior, and analytics that distinguish learner exposure. Backend metadata
  alone is insufficient.
- **`guided`** is not a delivered example: it is the transitional floor, always a logged `coverage_gap` +
  queue item.
- **Integrity gate:** only the assurance-derivation layer sets a level, from `EvidenceRecord`s over the
  matching fingerprint; generation code cannot label. No unverified free-prose example ships as verified; the
  ONLY unverified example that reaches a learner is honestly-marked `provisional`.

## 12. Failure classification → next state (issues 7, 8)

```python
FailureClass = Literal["transient_infrastructure", "source_not_found", "source_conflict",
                       "transcription_invalid", "verification_refuted", "verification_indecisive",
                       "policy_blocked"]
```
| Class | Next state |
|---|---|
| transient_infrastructure | retry / queued acquisition (NOT a semantic refutation, issue 8) |
| source_not_found | broaden retrieval (more families / alternate concept keys) |
| source_conflict | human review |
| transcription_invalid | discard candidate; try alternate source |
| verification_refuted | discard candidate; continue |
| verification_indecisive | stronger verifier or review |
| policy_blocked | guided or provisional per policy |

A budget timeout is `transient_infrastructure`, never a refutation (issue 26). "No automated tier confirms" is
NOT itself a terminal outcome — it enters this state machine, whose terminal is decided by review/provisional
policy (rewrites A10; A14/A15 test the two policy outcomes).

## 13. Decision trace & telemetry (issue 17)

Every routing hop, check status, assurance derivation, and failure class is persisted via
`record_lesson_decision` and surfaced by `explain_path.py`. Headline metrics: the three coverage numbers +
Provisional Exposure (§1.5); per-check confirm/refute/indecisive/unsupported counts; per-escalation-state
distribution; pipeline/cache hit rates; **provisional aging** (median time-to-promotion, correction rate,
expired-provisional count, learner exposures before correction); audited soundness violations (target 0).

---

## 14. Rollout milestones + gates (issues 25, 26, 29, 30, 31)

- **Phase 0 — offline core. DONE.** `retrieval_verify.py` (three-valued reproduction check incl. unit rule),
  `test_retrieval_verify.py` (17 tests), `scripts/retrieval_repro_gonogo.py`.
  **Gate G0 (precise, issue 29):** report `decision_rate = decisive/total`, `precision = correct_decisive/
  decisive`, `effective_success = correct_decisive/total`, `false_confirmation_rate = wrong_confirmed/
  confirmed`, broken down by domain, with confidence intervals. **False-confirmation rate is the safety
  metric.** G0 requires high precision + a minimum decision rate + zero severe unit/quantity mismatches — and
  requires the expanded fixture corpus (issue 30), because 10 clean fixtures validate plumbing, not
  architecture.
- **Phase 1 — retrieval + checks, SHADOW (issue 25).** Sources, secured retrieval, transcription, checks,
  assurance derivation, catalog — as an **async or sampled** observer over recorded/production misses, with
  strict time+cost budgets and cancellation; NEVER a synchronous per-miss fan-out on the live path. Shadow
  overhead measured independently of live latency.
  **Gate G1 (issue 31):** a written review protocol BEFORE launch — sample size, stratified selection,
  reviewer qualifications, severity classes, confidence bounds, disagreement handling. Oversample
  `answer_anchored`-only, unit-`unsupported`, cross-source, low-confidence concept resolutions, high-impact
  domains, provisional candidates. Pass = acceptable retrieval precision, useful V1/Mode-B + V2 confirm rates,
  ZERO confirmed-wrong in the audit, infra + independence + licensing + security resolved.
- **Phase 2 — live delivery + escalation.** Flip on; provisional enabled ONLY with the frontend dependency
  (§11/issue 9) shipped; review queue + offline promotion live. Per-path latency budgets enforced (issue 26):
  distinct budgets for V1-cached, V1-network, V2-cached, V2-network+transcription, qualitative-illustrative;
  with fetch concurrency, cancel-after-confirmation, max-sources, model timeout, retry, circuit breaker.
  **Gate G2:** more verified examples, ZERO integrity violations (audited), Verified+Resolved Coverage up vs.
  baseline, Provisional Exposure bounded, latency within budget.
- **Phase 3 — completeness convergence.** Operate the queue; grow source families; let the cache absorb the
  steady state. **Gate G3 (spec DONE):** Verified+Resolved Coverage ≥ target, Provisional Exposure small and
  strictly decreasing, `guided` rate near zero, every remaining gap an explicit queue item.

## 15. Minimum vertical slices (two, deliberately separate — issue 1)

**Slice 1 — instance-level (safe first).**
```
motional_emf fixture -> retrieve exact published instance -> V1 reproduce value AND unit
-> Mode A: re-narrate the SAME instance into cards -> trace_consistency check
-> instance-scope cache entry -> a repeat request reuses the exact instance
```
Does NOT claim a reusable `motional_emf` relationship.

**Slice 2 — relationship-level (only after Slice 1).**
```
two INDEPENDENT-family sources -> restricted-AST transcription -> canonical equivalence
-> dimensional + applicability validation -> corroborated_relationship
-> generate a NEW instance -> deterministic_execution rechecks the new answer
-> relationship-scope cache entry (Mode B)
```
Keeping the scopes separate prevents the largest over-certification bug.

## 16. Acceptance tests

| # | Given | When | Then |
|---|---|---|---|
| A1 | adapter routes | resolve | retrieval never invoked; trace_verified (S1) |
| A2 | gen_foundation solves | resolve | retrieval never invoked; execution_verified (S1) |
| A3 | compatible cache entry (applicability holds) | resolve | steps 1–7 skipped; cached assurance returned (S2) |
| A4 | qualitative topic, retrieval MISS | resolve | escalates; guided + coverage_gap (a *miss*, not "all qualitative") |
| A5 | published instance, solver reproduces value+unit | check | V1 confirm → verified_reproduction, instance scope |
| A6 | published instance, wrong number | check | V1 refute; not shipped verified |
| A7 | transcribed formula, units don't balance | check | dimensional_balance=mismatch; not corroborated |
| A8 | two INDEPENDENT families agree + dims + applicability | check | corroborated_relationship; fan-out stopped (S5) |
| A9 | claim not in source span | check | source_span_match=refute; source dropped |
| A10 | no check confirms | resolve | enters escalation state machine; outcome per policy (not auto-guided) |
| A11 | confirmed result | after ship | catalog entry + all decisions in trace |
| A12 | retrieval raises (transient) | resolve | transient_infrastructure; retry/queue; NOT a refutation |
| A13 | reproduction non-numeric produced | check | indecisive; ladder continues |
| A14 | no confirm, provisional ON + frontend ready | resolve | ships provisional (badged) + enqueued; delivered; not guided |
| A15 | no confirm, provisional OFF | resolve | guided floor; coverage_gap; enqueued |
| A16 | qualitative topic WITH span-groundable source | resolve | source_grounded illustrative example; counts separately from guided |
| A17 | any eligible-desired example | resolve | delivered OR a logged coverage_gap — exhaustive disjunction |
| A18 | wrong example, no confirm | resolve | never a verified level; only honest provisional (integrity) |
| A19 | V1 reproduced source instance, generator changes numbers | resolve | new instance cannot inherit V1 evidence without re-execution (fingerprint invariant) |
| A20 | same concept_key, different variant | cache | applicability check → MISS |
| A21 | two URLs copy one upstream family | check | source_independence fails |
| A22 | final answer right, an intermediate step invalid | generate | trace rejected/repaired before ship |
| A23 | answer_anchored-only result | derive | not a strongly-verified reusable contract; not cache-promoted |
| A24 | source bytes change at same URL | cache | old snapshot still auditable; invalidation by snapshot hash |
| A25 | provisional item ages past SLA | telemetry | escalation alert + policy action |
| A26 | verified entry later revoked | incident | dependent lessons quarantined/regenerated |
| A27 | dimensional checker can't handle the form | check | returns unsupported (indecisive), never implicit pass |
| A28 | source text contains prompt injection | retrieve | instructions ignored; only extracted evidence used |
| A29 | human approves ONE instance | review | not reusable as relationship-level certification (scope) |
| A30 | narration introduces unsupported claim | generate | claim removed or source-grounded before ship |
| A31 | numeric matches but unit differs | check | V1 refute (issue 13) |
| A32 | qualitative topic has authoritative canonical instance | resolve | sourced illustrative ships; counted apart from guided |
| A33 | retrieval times out | resolve | infrastructure failure, not semantic refutation |
| A34 | concurrent writes, different assurance | cache | higher valid assurance preserved; evidence merged (CAS) |

## 17. Named fixtures — CLASSES not just examples (issue 30)

Build fixture *classes*, each with expected outcome (including negatives where the correct result is
abstain/escalate/refute): clean numeric; unit conversion; **wrong published answer** (must refute/flag);
ambiguous formula; **same dimensions wrong coefficient** (`WRONG_BUT_DIMENSIONAL`, must not pass on dims
alone); source dependency (fails independence); multiple valid answer forms; **dimensionally-unsupported
expression** (must be indecisive); qualitative illustrative; formula-with-assumptions; **adversarial prompt
injection**; changed source snapshot; symbol collision; multi-step derivation; interval/set/symbolic answers.
`KNOWN_ANSWER_FIXTURES` (10, merged) remains the clean-numeric class; it is a floor, not the corpus.

## 18. Implementation surface (single resolver — issue 24)

New `app/services/examples/retrieval/`: `sources.py` (whitelist + independence families + reuse policy),
`fetch.py` (secured retrieval, snapshots, record/replay), `transcribe.py`, `checks.py` (the EvidenceChecks),
`assurance.py` (policy-table derivation — the ONLY writer of assurance levels), `catalog.py` (fingerprint keys,
applicability, CAS/monotonic, tombstones), `acquisition.py` (offline state machine + review certificates),
`producer.py` (`try_resolve(context) -> Candidate|None`, the narrow interface the existing resolver calls),
`shadow.py` (async/sampled observer). Reused: `retrieval_verify`, `runtime_binding.units`/`compiler`/
`executor`, `answer_anchor`, `guided_explanation`, `decision_trace`, and the `solve_worked_example` seam.

**MUST NOT be a source of truth:**
- The LLM never certifies a formula's correctness (only source independence/reproduction/execution does) and
  never makes the final equivalence decision — it proposes transcriptions and symbol mappings only.
- A single source never confirms a relationship (V2 needs 2 independent families; span-match alone →
  `source_grounded` at most). Reproduction (V1) may confirm one instance because the published answer is the
  independent check — but ONLY that instance (fingerprint invariant).
- `answer_anchored` is never written as verified or promoted from cache without stronger evidence/review.
- Assurance levels are writable ONLY by `assurance.py`, from evidence over the matching fingerprint.
- The catalog never persists a verified entry that wasn't confirmed; provisional never auto-promotes.
- Completeness is never bought with soundness (no relabeling unconfirmed as verified); soundness never excuses
  silent absence (an unconfirmable topic escalates and is counted as a `coverage_gap`, never dropped).
- No `eligible_desired` topic exits the resolver without either a delivered example or a logged `coverage_gap`.
- Retrieval never introduces new execution semantics or a second arithmetic engine.

## 19. Non-goals

Finishing GRB Milestone C; open-web retrieval; numeric "proof" of qualitative claims (they get sourced
illustrative examples); symbolic/CAS calculus; making the equivalence DECISION with an LLM.

## 20. Open decisions

Infra (can the backend retrieve at gen time, within budget?); G0 thresholds (precision floor, min decision
rate, false-confirmation ceiling); source whitelist + independence families; equivalence coverage boundary of
the restricted compiler; provisional review SLA (N days); reviewer roster/qualifications.

## 21. Pre-Phase-1 decision checklist (BLOCKS Phase 1)

1. Exactly what V1 certifies — instance (Mode A) vs relationship (Mode B). 2. Contract-fingerprint cache keys +
applicability lookup replace concept-only keys. 3. EvidenceCheck vs AssuranceLevel vs Scope separated. 4.
`answer_anchored` downgraded from verified/reusable. 5. Qualitative-routing contradiction resolved (§1.7/§3/S3,
A4/A16). 6. Frontend provisional badging made a Phase-2 blocking dependency. 7. Source independence, snapshots,
licensing, security specified. 8. Human review modeled as an async state machine. 9. Answer-comparison policies
defined. 10. Trace-level verification added after generation. (All are drafted above; §21 tracks their
sign-off.)

## 22. Review disposition (external review issues 1–31)

| Issue | Disposition | Section |
|---|---|---|
| 1 V1 verifies instance not arbitrary example | ADOPTED — Mode A/B + fingerprint invariant | §5,§8,§15 |
| 2 concept_key too coarse | ADOPTED — ContractIdentity + applicability | §5,§10 |
| 3 gates vs tiers conflated | ADOPTED — EvidenceCheck vs AssuranceLevel | §5,§8 |
| 4 answer_anchored not verified | ADOPTED — downgraded, non-reusable | §8,§11 |
| 5 "never wrong" not absolute | ADOPTED — integrity vs correctness | §1.5 |
| 6 qualitative routing contradiction | ADOPTED — kind gate routes, narrowed S3 | §1.7,§3,§4 |
| 7 A10/A14/A15 conflict | ADOPTED — A10 → state machine | §12,§16 |
| 8 exception vs escalation | ADOPTED — FailureClass table | §12 |
| 9 provisional needs frontend | ADOPTED — Phase-2 blocker | §11,§14 |
| 10 source independence | ADOPTED — corpus families | §5,§6 |
| 11 semantic equivalence | ADOPTED — AST-first, LLM maps only | §8 |
| 12 dimensional weaker than claimed | ADOPTED — unsupported=indecisive, applicability | §8 |
| 13 V1 unit mismatch | ADOPTED — refute; **implemented in code** | §8, `retrieval_verify.py` |
| 14 answer comparison policy | ADOPTED — AnswerComparison | §5,§8 |
| 15 correct answer ≠ correct trace | ADOPTED — trace_consistency | §9 |
| 16 review is async | ADOPTED — two machines + AcquisitionState | §1.6,§16 |
| 17 provisional gaming | ADOPTED — 3 coverage metrics + SLA | §1.5,§13 |
| 18 end-state not falsifiable | ADOPTED — eligible_desired denominator | §1.5 |
| 19 review certificate | ADOPTED — ReviewCertificate + scope | §5 |
| 20 licensing | ADOPTED — reuse_policy | §5,§6 |
| 21 immutable snapshots | ADOPTED — SourceSnapshot | §5,§6 |
| 22 retrieval security | ADOPTED — SSRF/injection/sanitization | §6 |
| 23 concept resolution | ADOPTED — ConceptResolution | §5 |
| 24 second router risk | ADOPTED — producer interface, one resolver | §2,§18 |
| 25 shadow latency | ADOPTED — async/sampled + budgets | §14 |
| 26 latency budget | ADOPTED — per-path budgets | §4,§14 |
| 27 cache concurrency | ADOPTED — CAS/monotonic/tombstones | §10 |
| 28 correction/revocation | ADOPTED — incident path + dep links | §10 |
| 29 G0 metrics | ADOPTED — precise metric set | §14 |
| 30 fixtures too small/clean | ADOPTED — fixture classes + negatives | §17 |
| 31 G1 sampling | ADOPTED — review protocol | §14 |
| Schema revision | ADOPTED — separated core model | §5 |
| A19–A34 | ADOPTED | §16 |
| Impl sequence | ADOPTED — §21 checklist + two slices | §15,§21 |
```
