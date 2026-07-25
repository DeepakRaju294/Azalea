# Retrieval-Grounded Example Spec

> **Status:** Draft v0.4 (freeze-prep pass) — **APPROVED AS THE PHASE-1A ARCHITECTURE BASELINE** (fifth review).
> Broad architectural revision is CLOSED; this pass applied only freeze-prep correctness fixes: enforceable
> run/verifier identity (the one flagged genuine defect), a shared `validate_assurance_decision`, typed
> `EvidenceIntegrityError` instead of `assert`, evidence-vs-assurance-vs-shipping policy separation, `[FREEZE
> FOR 1A]`/`[DRAFT]`/`[DEFERRED]` tags on every §5 schema, G0 categorical hard-blocks, and the executable §21
> checklist. Deeper abstractions remain DEFERRED to named sub-gates (§18.5).
>
> **The ONLY remaining Phase-1A blockers** (nothing broader): (1) expand + pass G0 on the adversarial/live
> fixtures (§17); (2) canonical-fingerprint test vectors (A56); (3) strict evidence-reference integrity
> (A47–A49, A57); (4) freeze the instance-level schemas (`PublishedInstance`, `AnswerComparison`,
> `FingerprintSet`, `EvidenceRecord`, `AssuranceDecision`); (5) executable A35–A40 + missing/stale-evidence
> tests. After those pass, begin Phase-1A shadow (Slice 1A: fixture → reproduction evidence → assurance →
> report). v0.2 issues → §22; v0.3 → §23; v0.4 → §24.
>
> **Recommended implementation order (adopted):** expand+run adversarial fixtures → freeze 1A schemas →
> canonical serialization with test vectors → evidence-integrity validation → Slice 1A only. Do NOT build
> catalog reuse / predicate extraction / qualitative grounding / relationship transcription before their
> sub-gates (§18.5).
>
> **"Signed off" means, per item:** an APPROVED frozen schema, an EXECUTABLE §16 test for its invariant, and
> architectural acceptance recorded here — not prose.
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
Visible Coverage        = delivered / eligible_desired                 # includes provisional
Policy-Satisfied Cov.    = |meets required_threshold(kind,risk)| / eligible_desired   # PRIMARY (issue 14, §11)
Verified Coverage        = strongly_verified / eligible_desired        # execution/reproduction/corroboration
Provisional Exposure     = provisional_shipped / delivered             # gamed-metric guard (issue 17)
```

`delivered = an actual example of the right KIND shipped` (any assurance except `guided`). `guided` is NOT
delivered; it is a tracked `coverage_gap`. **Policy-Satisfied Coverage is the primary completeness metric**
(issue 14): it credits an example only when it meets the assurance bar for its KIND and DOMAIN RISK (§11), so a
`source_attributed` qualitative example counts while the same level on a high-risk computational topic does
not. **End-state (G3):** Policy-Satisfied Coverage ≥ target with Provisional Exposure bounded and shrinking —
100% cannot be "achieved" by marking everything provisional.

## 1.6 Two machines: online resolution vs offline acquisition (issues 16, 24)

```
ONLINE  resolve_worked_example(topic) -> ResolutionResult {
          learner_output:    DeliveredExample | ProvisionalExample | GuidedFallback   # always visible NOW
          acquisition_state: Optional[AcquisitionState]                               # metadata, not output
        }  never blocks on network-heavy acquisition or human review.

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
  to a whitelisted source (an `EvidenceCheck`, not a full confirmation). Ships as `source_attributed`. This is a
  real, attributable example that counts toward Visible and Policy-Satisfied Coverage — distinct from `guided`.
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

# --- typed candidate payloads (v0.3 review issue 1 — the thing being verified is now typed, not Mapping[str,Any]) ---
@dataclass(frozen=True)
class Predicate:                        # [DRAFT — 1E] a structured applicability condition — restricted AST (v0.4 issue 4)
    operator: Literal["eq", "neq", "lt", "lte", "gt", "gte", "in", "approximately", "boolean"]
    subject: str                        # "temperature", "speed_over_c", "n", "angle_deg", "mass", "regime"
    value: "StructuredValue"            # number / enum member / bool — never free text
    tolerance: Optional[str] = None
# Booleans alone can't express speed<<c, n>=1, angle==90, mass!=0, rate_period==compounding_period, or
# enum regimes (laminar|turbulent). Satisfiability stays three-valued (satisfied|violated|unknown) and
# deterministic — NO LLM at the applicability boundary (§10).

@dataclass(frozen=True)
class PublishedInstance:                # [FREEZE FOR 1A]
    problem_statement: str
    inputs: tuple["BoundValue", ...]
    target: "QuantitySpec"
    published_answer: "StructuredAnswer"
    comparison: "AnswerComparison"
    assumptions: tuple[Predicate, ...]

@dataclass(frozen=True)
class RelationshipArtifact:             # [DRAFT — 1D]
    expression_ast: "RestrictedExpression"   # reuses runtime_binding restricted grammar
    output_symbol: "SymbolSpec"
    symbols: tuple["SymbolSpec", ...]
    assumptions: tuple[Predicate, ...]
    constraints: tuple[Predicate, ...]

@dataclass(frozen=True)
class IllustrativeInstance:             # [DRAFT — 1C]
    scenario: str
    supported_claims: tuple["GroundedClaim", ...]

CandidatePayload = Union[PublishedInstance, RelationshipArtifact, IllustrativeInstance]

@dataclass(frozen=True)
class GroundedClaim:                    # [DRAFT — 1C] v0.3 issue 6 + v0.4 issue 7 — durable, auditable span identity
    claim_id: str
    text: str
    supporting_source_id: str
    source_snapshot_hash: str           # the EXACT bytes (source_id can change; hash can't)
    start_offset: int                   # span located by offsets, not a string that may recur
    end_offset: int
    extraction_version: str
    support_kind: Literal["verbatim_support", "direct_entailment", "inference"]   # HOW MUCH inference was needed
    entailment_status: Literal["supported", "unsupported", "ambiguous"]

@dataclass(frozen=True)
class AnswerComparison:                 # [FREEZE FOR 1A] v0.3 issue 14 + v0.4 issue 10 — normalized QUANTITY semantics
    kind: Literal["exact_numeric", "relative_tolerance", "absolute_tolerance", "symbolic_equivalence",
                  "unordered_set", "interval", "textual_enum", "vector", "complex", "angle_mod_2pi"]
    quantity_kind: str                  # "temperature_absolute" vs "temperature_difference"; "percent" vs "percentage_points"
    unit_dimension: str                 # dimensional signature the answer must carry
    unit_semantics: Literal["absolute", "difference", "ratio", "dimensionless"]
    allowed_units: tuple[str, ...]      # unit-equivalent acceptable answers (e.g. J, N*m)
    coordinate_frame: Optional[str]     # vectors/complex — frame the answer is expressed in
    tolerance: Optional[str]            # Decimal-as-str
    rounding_rule: Optional[str]        # a REQUIRED rounding rule belongs to answer_semantics identity (§5 fingerprints)

@dataclass(frozen=True)
class CandidateArtifact:
    artifact_id: str
    concept: ConceptResolution
    payload: CandidatePayload          # TYPED discriminated union; `kind` is DERIVED, not a free field (issue 9)
    fingerprints: "FingerprintSet"     # computed from canonical serialization, NOT a free string (issue 2)
    sources: tuple[SourceRef, ...]
    @property
    def kind(self) -> str:             # single source of truth — tag can never disagree with payload
        return {PublishedInstance: "published_instance", RelationshipArtifact: "relationship",
                IllustrativeInstance: "illustrative_instance"}[type(self.payload)]

# --- fingerprints (v0.3 issue 2; v0.4 issues 2,3 — several DISTINCT identities, versioned + canonical) ---
@dataclass(frozen=True)
class FingerprintSet:                # [FREEZE FOR 1A]
    # relation vs execution-contract are SEPARATE (v0.4 issue 3): F=m*a and a=F/m are the same RELATION but
    # different EXECUTION CONTRACTS (different output symbol, required inputs, singularities, goal). Cache reuse
    # and generation key on `execution_contract`, NOT `relation_equivalence`.
    relation_equivalence: str   # canonical mathematical relation (F=m*a ≡ a=F/m under m!=0)
    execution_contract: str     # output_symbol + input roles + required knowns + domain constraints + unit_system + orientation
    # answer identity is split from comparison policy (v0.4 issue 2): a required rounding/sig-fig rule that
    # changes the correctness CONDITION lives with the answer semantics, NOT presentation.
    answer_semantics: str       # canonical inputs + target quantity + assumptions + expected answer&unit + REQUIRED rounding/sig-figs
    comparison_policy: str      # verification tolerance / comparison KIND (how closeness is judged)
    evidence_subject: str       # exact artifact representation a verifier checked (EvidenceRecord binds to this)
    source_snapshot: str        # exact retrieved evidence bytes (== SourceSnapshot.content_hash lineage)
    presentation: str           # narration + COSMETIC number formatting only; changes freely, touches nothing above
    hash_version: str           # canonical-serialization + hash algorithm version
    @property
    def semantic(self) -> str:  # Mode-A instance identity — a CANONICAL HASH (v0.4 issue 2), never a concat.
        # hash_canonical({...}, version=hash_version): fixed serialization + text/numeric/Unicode normalization,
        # decimal repr, tuple ordering, null-vs-missing rules. Phase-1A sign-off REQUIRES cross-environment
        # test vectors (A56) that reproduce exact expected hashes.
        return hash_canonical({"execution_contract": self.execution_contract,
                               "answer_semantics": self.answer_semantics}, version=self.hash_version)
# Canonicalization (documented + versioned). PRESERVES identity: whitespace; cosmetic sci-notation formatting;
# symbol renames (normalized by ROLE); reordering givens; unit-EQUIVALENT restatement under the same unit_system;
# narration/prose->diagram. CHANGES identity: a different output target (execution_contract); a REQUIRED rounding
# or significant-figure rule (answer_semantics — 1.047 vs "to 2 dp = 1.05" are NOT the same instance); a changed
# verification tolerance (comparison_policy); different assumptions/regime (execution_contract). Source provenance
# affects `source_snapshot` ONLY, never the semantic identities.

# --- evidence vs assurance vs scope (issues 1, 3, 4) ---
EvidenceCheck = Literal["source_span_match", "source_independence", "dimensional_balance",
                        "published_answer_reproduction", "deterministic_execution",
                        "independent_endpoint_agreement", "trace_consistency"]

VerifierName = Literal["reproduction_checker", "executor", "comparison_engine", "dimensional_checker",
                       "span_grounder", "trace_validator"]

@dataclass(frozen=True)
class EvidenceRecord:                   # [FREEZE FOR 1A]
    evidence_id: str
    check: EvidenceCheck
    status: Literal["confirm", "refute", "indecisive", "unsupported"]   # unsupported != pass (issue 12)
    subject_fingerprint: str           # the artifact THIS evidence is about
    verifier_name: VerifierName        # WHICH component produced it — exact binding, not set-membership (issue 2)
    verifier_version: str
    check_contract_version: str        # the verifier's own contract version — evidence validity depends on the
                                       # VERIFIER, not the assurance/shipping policy (issue 8): a raw reproduction
                                       # stays valid when a shipping threshold changes; assurance is RE-DERIVED.
    run_id: str                        # binds records to one validation run (A57)
    revoked: bool                      # incident path can revoke (v0.4 issue 1 / §10)
    evidence: Mapping[str, Any]        # includes the execution context (solver/model/prompt version) — NOT the
                                       # semantic fingerprint (issue 9): a solver-version change must not change
                                       # the instance's identity, only this record's provenance.

AssuranceLevel = Literal["verified_execution", "verified_reproduction", "corroborated_relationship",
                         "source_attributed", "answer_anchored", "provisional", "guided"]   # renamed, issue 6

# AUTOMATED strength ordering (v0.3 issue 4). Human review is DELIBERATELY NOT on this axis (v0.4 issue 6) —
# it is orthogonal, so `if strength >= HUMAN_REVIEWED` can't accidentally flatten the profile.
class AssuranceStrength(IntEnum):
    GUIDED = 0
    PROVISIONAL = 10
    SOURCE_ATTRIBUTED = 20
    ANSWER_ANCHORED = 25
    CORROBORATED = 30
    REPRODUCED_INSTANCE = 40
    EXECUTION_VERIFIED = 50

@dataclass(frozen=True)
class AssuranceProfile:                 # v0.3 issue 5 + v0.4 issue 6 — automated strength and review are ORTHOGONAL
    automated_strength: AssuranceStrength
    computational_check: Literal["none", "endpoint", "reproduction", "deterministic_execution"]
    semantic_basis: Literal["single_source", "corroborated_sources", "reviewed_relationship"]
    review_status: Literal["unreviewed", "approved", "corrected", "rejected"]
    review_scope: Literal["instance", "relationship", "template", "none"]
# required_threshold() reads BOTH dimensions, e.g. "automated_strength >= EXECUTION_VERIFIED OR (review_status
# == approved AND review_scope covers this artifact)". A reviewed-but-non-executable relationship therefore
# does NOT satisfy an execution-required high-risk threshold (§11).

@dataclass(frozen=True)
class AssuranceDecision:                 # [FREEZE FOR 1A]
    assurance_id: str
    run_id: str                          # A57 — all cited evidence must share THIS run (v0.4-2 issue 1)
    level: AssuranceLevel
    profile: AssuranceProfile            # carries automated_strength + orthogonal review dims
    subject_fingerprint: str             # == the EvidenceRecords' subject_fingerprint
    reusable_scope: Literal["instance", "relationship", "template", "none"]   # issue 1/19
    assurance_policy_version: str        # policy that DERIVED this level (distinct from evidence + shipping, issue 8)
    verification_dependencies: Mapping[VerifierName, str]   # verifier_name -> version; exact binding (issue 2)
    evidence_ids: tuple[str, ...]

# --- delivery (v0.3 issue 1 invariant; v0.4 issue 1 — inspect ACTUAL evidence records, not profile labels) ---
@dataclass(frozen=True)
class DeliveredExample:
    fingerprints: FingerprintSet
    assurance: AssuranceDecision
    source_refs: tuple[SourceRef, ...]
    card_payload: Mapping[str, Any]
class EvidenceIntegrityError(RuntimeError):   # production raises this — NOT `assert` (issue 6; assert is
    pass                                      # disabled under -O). `assert` below is spec shorthand only.

def assert_delivery_scope(d: DeliveredExample, evidence_by_id: Mapping[str, "EvidenceRecord"],
                          active_policy: "ShippingPolicy") -> None:
    """MUST be called at every delivery boundary. FAILS CLOSED (raises EvidenceIntegrityError in production).
    Delegates 'does the evidence actually EARN the level' to the shared validator (issue 3), then enforces
    run/verifier binding and the fingerprint-scope rule."""
    missing = set(d.assurance.evidence_ids) - evidence_by_id.keys()
    if missing:
        raise EvidenceIntegrityError(f"missing assurance evidence: {sorted(missing)}")
    records = [evidence_by_id[eid] for eid in d.assurance.evidence_ids]
    for r in records:
        if r.revoked:
            raise EvidenceIntegrityError(f"revoked evidence {r.evidence_id}")
        if r.run_id != d.assurance.run_id:                                   # A57 (issue 1)
            raise EvidenceIntegrityError(f"evidence {r.evidence_id} from another run")
        if d.assurance.verification_dependencies.get(r.verifier_name) != r.verifier_version:   # exact (issue 2)
            raise EvidenceIntegrityError(f"verifier {r.verifier_name} version mismatch")
    # the evidence combination must actually earn the level — shared with assurance.py, not re-implemented (issue 3)
    validate_assurance_decision(d.assurance, records, active_policy)
    if d.fingerprints.evidence_subject == d.assurance.subject_fingerprint:
        return
    if d.assurance.reusable_scope not in ("relationship", "template"):
        raise EvidenceIntegrityError("evidence/subject fingerprint mismatch")
    if not any(r.check == "deterministic_execution" and r.status == "confirm"
               and r.subject_fingerprint == d.fingerprints.semantic for r in records):
        raise EvidenceIntegrityError("no deterministic_execution evidence binds to THIS delivered instance")

def validate_assurance_decision(assurance: AssuranceDecision, records: list["EvidenceRecord"],
                                active_policy: "ShippingPolicy") -> None:
    """[FREEZE FOR 1A] The SINGLE authority on 'does this evidence set earn this level' — called at derivation
    (assurance.py refuses to MINT invalid), at catalog load (refuse/mark invalid), and at delivery (final
    fail-closed). Defense in depth (issue 7): the same rule at all three boundaries. Confirms e.g.
    verified_reproduction cites a `published_answer_reproduction` record with status=confirm over
    assurance.subject_fingerprint — never an indecisive one — and that the level clears active_policy for the
    topic's kind+risk. Raises EvidenceIntegrityError on any gap."""
    ...

ResolutionOutcome = Union["DeliveredExample", "ProvisionalExample", "GuidedFallback"]

@dataclass(frozen=True)
class ResolutionResult:                 # issue 13 — pending acquisition is METADATA, not a learner output
    learner_output: ResolutionOutcome   # always something a learner can see NOW
    acquisition_state: Optional[AcquisitionState]   # offline promotion continues independently
# learner-level outcomes stay exhaustive: delivered example OR a guided coverage_gap.

# --- reusable catalog identity (issue 2) ---
@dataclass(frozen=True)
class ContractIdentity:           # [DRAFT — 1E]
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
class ReviewCertificate:           # [DEFERRED — HUMAN REVIEW]
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
- **Independence has DIMENSIONS, and is a conservative heuristic — NOT proof of epistemic independence (issue
  10).** Distinguish: *publisher independence*, *content-lineage independence* (upstream copy chains),
  *derivation independence*, *example-instance independence*. Two textbooks independently deriving a classical
  law from the same accepted physics is fine (derivation-independent); two sites copying one erroneous example
  are not (content-lineage-dependent). Policy by check: **V2 relationship corroboration** may accept
  publisher+content-lineage independence; **V1 reproduction** values a second *instance/derivation* over
  another restatement of the same formula. `corpus_family`/`upstream_source_ids` are hand-curated initially;
  the spec states plainly this is a conservative heuristic, not a guarantee of true independence.
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
  correctness (issue 3). Gates V1/V2 sources; alone yields at most `source_attributed`.
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
source_span_match only (qualitative or single-source)                                             -> source_attributed
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

## 10. Catalog: keys, applicability, concurrency, correction (issues 2, 8, 9, 27, 28)

- **Two-stage lookup (issue 2).** `concept candidate → applicability check → exact compatible `ContractIdentity`
  hit`. A semantically related entry that fails applicability is a MISS (simple vs compound interest,
  perpendicular vs arbitrary-angle EMF, classical vs relativistic KE).
- **Applicability is three-valued satisfiability over STRUCTURED predicates, never an LLM judgment (issue 9).**
  A cached entry's required `Predicate`s (`velocity_perpendicular_to_field`, `classical_regime`, …) are checked
  against properties derived from the current topic context. Result ∈ `{satisfied, violated, unknown}`;
  **`unknown` is a cache MISS/escalation, never a permissive hit.** "Does this formula apply here?" must not
  become a soft LLM call at the cache boundary — properties are extracted structurally; genuinely
  undecidable ones return `unknown` and fall through to fresh acquisition.
- **Invalidation keys off a per-component dependency manifest, not one version (issue 8).** Each entry persists
  `verification_dependencies = {concept_resolver, expression_parser, canonicalizer, unit_registry, executor,
  comparison_engine, assurance_policy, source_extraction, trace_validator: <version>}`. A changed component
  invalidates ONLY entries whose manifest references it — neither too broad (one bump nukes everything) nor
  too weak (a canonicalizer change silently trusted).
- **Only confirmed → verified cache.** A `provisional` entry may be cached AS provisional, never promoted to
  verified without a `ReviewCertificate` or stronger evidence (§8, issue 4).
- **Concurrency (issue 27).** Idempotency keys on `ContractIdentity`; compare-and-swap promotion; **monotonic
  assurance** (a lower-assurance write never overwrites a higher-assurance valid entry); evidence merge;
  tombstones for rejected candidates; poisoning recovery.
- **Correction / revocation (issue 28).** Delivered cards store dependency links to their contract fingerprint
  + evidence snapshots. Incident path: `report → quarantine contract → stop new delivery → locate dependent
  cards → regenerate or mark corrected → invalidate descendants → re-audit the source family`. Learners who saw
  a revoked example are identifiable for remediation.

## 11. Assurance levels & shipping policy (issues 4, 5, 7, 8, 9, 14)

- **Relationship assurance ≠ delivered-instance assurance (v0.4 issue 8).** `corroborated_relationship` is a
  CATALOG-level assurance — it authorizes deterministic GENERATION, it is provenance, NOT a learner example's
  assurance. A delivered COMPUTATIONAL instance must earn its OWN level: `verified_execution` (new inputs
  executed, the normal Mode-B outcome), `verified_reproduction` (Mode A), `answer_anchored`, or `provisional`.
  A relationship's assurance never silently becomes the card's assurance without executing the new instance.
- **Learner-example shipping levels** are therefore {`verified_execution`, `verified_reproduction`,
  `source_attributed` (qualitative), `answer_anchored`*, `provisional`}. `corroborated_relationship` is a
  catalog state, not a learner-example state. Strength is ordered (`AssuranceStrength`, §5) + read alongside
  the orthogonal review dims — never a flat "strongly verified" bucket (issues 4, 6).
- **`answer_anchored` is an INTERNAL result, not a durable learner state (v0.4 issue 5).** It ships to a
  learner ONLY when a rollout policy explicitly permits below-threshold content, and when it does it is
  represented as **`provisional` carrying endpoint evidence** (badged under-review, enqueued, TTL) — not a
  separate permanent quasi-verified state. This prevents Visible Coverage being inflated by weak endpoint
  agreement while Policy-Satisfied Coverage stays honest. (*shown above as a level for evidence-derivation
  clarity; at the shipping boundary it materializes as provisional-with-endpoint-evidence.)
- **Shipping threshold is per KIND and per DOMAIN RISK (issue 14 + required addition #4).** The minimum
  assurance to ship is `required_threshold(kind, domain_risk)`, not one universal bar:

  Threshold reads BOTH the ordered `automated_strength` AND the orthogonal review dims (issue 6): "meets X" =
  `automated_strength ≥ X` **OR** (`review_status == approved` AND `review_scope` covers this artifact).

  | kind / risk | ordinary educational | high-risk domain (medical, safety, legal, finance-advice) |
  |---|---|---|
  | computational | automated_strength ≥ REPRODUCED_INSTANCE, or approved review | automated_strength ≥ EXECUTION_VERIFIED, or approved review of instance scope |
  | qualitative | ≥ SOURCE_ATTRIBUTED (all material claims grounded, §9/issue 6), or approved review | approved review required |

  **Policy-Satisfied Coverage** = `|artifacts meeting required_threshold(kind,risk)| / eligible_desired` —
  this replaces a single universal "resolved" bar so a `source_attributed` qualitative example can satisfy
  policy while the same level on a high-risk computational topic does not (issue 14).
- **Per-level lifecycle policy (issue 7)** — `answer_anchored` and `provisional` must not become permanent
  quasi-verified resting states:

  | level | learner badge | cache scope | review | expiry (TTL) |
  |---|---|---|---|---|
  | verified_execution / verified_reproduction | (none / verified) | per invariant (§5) | no | none |
  | corroborated_relationship | sourced, corroborated | relationship (applicability) | optional/domain | source-version |
  | source_attributed | "sourced example" | exact illustration | optional/domain | source-version |
  | answer_anchored (INTERNAL — materializes as provisional-with-endpoint-evidence at shipping, §11) | (as provisional) | exact INSTANCE only | **yes** | fixed TTL |
  | provisional | "under review" | exact artifact only | **mandatory** | shorter TTL |
  | guided | (not an example) | n/a | n/a (queue item) | n/a |
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
`record_lesson_decision` and surfaced by `explain_path.py`. Headline metrics: the three coverage metrics
(Visible, Policy-Satisfied, Verified) + Provisional Exposure (§1.5); per-check confirm/refute/indecisive/unsupported counts; per-escalation-state
distribution; pipeline/cache hit rates; **provisional aging** (median time-to-promotion, correction rate,
expired-provisional count, learner exposures before correction); audited soundness violations (target 0).

---

## 14. Rollout milestones + gates (issues 25, 26, 29, 30, 31)

- **Phase 0 — offline core + adversarial checker corpus. Fixture FRAMEWORK + initial cases IMPLEMENTED; the
  fixture POPULATION is not yet broad enough for G0 sign-off (v0.4-2 issue 5).** `retrieval_verify.py`
  (three-valued reproduction check incl. unit rule; `CheckerCase`/`run_checker_corpus`, 21 adversarial cases),
  `test_retrieval_verify.py`, `scripts/retrieval_repro_gonogo.py`.
  **Gate G0 (precise, issue 29):** report `decision_rate = decisive/total`, `precision = correct_decisive/
  decisive`, `effective_success = correct_decisive/total`, `false_confirmation_rate = wrong_confirmed/
  confirmed`, broken down by domain, with confidence intervals. **False-confirmation rate is the safety metric.**
  G0 requires high precision + a minimum decision rate on the EXPANDED corpus (issue 30).
  **Categorical HARD BLOCKS (issue 10) — any one fails G0 regardless of aggregates:** a false confirmation on a
  wrong-unit fixture; a false confirmation on a wrong-published-answer fixture; any `unsupported` treated as
  `confirm`; any severe quantity-type mismatch confirmed; any missing-evidence or mismatched-fingerprint case
  accepted. (The offline `run_checker_corpus` already blocks on a critical false confirmation; G0 adds the rest.)
  **G0's claim is narrow and declared (issue 11):** *"the existing solver reproduces published answers safely
  enough for V1 to be worth integrating."* G0 authorizes building the **Phase-1A V1 shadow ONLY.** It does NOT
  establish retrieval precision, transcription quality, source independence, V2 equivalence, qualitative
  grounding, catalog safety, or trace-generation correctness — each has its own sub-gate below.
- **Phase 1 — retrieval + checks, SHADOW (issues 12, 25).** Built as **sub-phases with their own acceptance
  gates**, so V2 complexity never blocks useful V1 learning; each is an **async or sampled** observer over
  recorded/production misses, strict time+cost budgets + cancellation, NEVER a synchronous per-miss fan-out;
  shadow overhead measured independently of live latency:
  Each sub-phase has its OWN named gate (v0.4 rollout feedback) so rollback + ownership are clear:
  - **1A** fixture-fed V1 shadow, instance scope only (the only thing G0 authorizes). **G1A:** evidence
    binding + assurance derivation correct on fixtures; `assert_delivery_scope` passes with real records.
  - **1B** immutable source snapshots + secured retrieval. **G1B:** retrieval security + snapshot audit pass.
  - **1C** qualitative source-span / claim-grounding path. **G1C:** claim grounding meets a precision target.
  - **1D** relationship transcription + AST equivalence (V2). **G1D:** ZERO false-equivalence on adversarial
    fixtures.
  - **1E** catalog candidate storage + three-valued applicability lookup. **G1E:** ZERO permissive-`unknown`
    cache hits.
  - **1F** sampled PRODUCTION shadow (after 1A–1E). **G1F:** meets cost + precision + audit thresholds.
  **Gate G1 (issue 31 — the umbrella audit protocol across the sub-gates):** a written review protocol BEFORE
  launch — sample size, stratified selection,
  reviewer qualifications, severity classes, confidence bounds, disagreement handling. Oversample
  `answer_anchored`-only, unit-`unsupported`, cross-source, low-confidence concept resolutions, high-impact
  domains, provisional candidates. Pass = acceptable retrieval precision, useful V1/Mode-B + V2 confirm rates,
  ZERO confirmed-wrong in the audit, infra + independence + licensing + security resolved.
- **Phase 2 — live delivery + escalation.** Flip on; provisional enabled ONLY with the frontend dependency
  (§11/issue 9) shipped; review queue + offline promotion live. Per-path latency budgets enforced (issue 26):
  distinct budgets for V1-cached, V1-network, V2-cached, V2-network+transcription, qualitative-illustrative;
  with fetch concurrency, cancel-after-confirmation, max-sources, model timeout, retry, circuit breaker.
  **Gate G2:** more verified examples, ZERO integrity violations (audited), Policy-Satisfied Coverage up vs.
  baseline, Provisional Exposure bounded, latency within budget.
- **Phase 3 — completeness convergence.** Operate the queue; grow source families; let the cache absorb the
  steady state. **Gate G3 (spec DONE):** Policy-Satisfied Coverage ≥ target, Provisional Exposure small and
  strictly decreasing, `guided` rate near zero, every remaining gap an explicit queue item.

## 15. Minimum vertical slices (deliberately separate — issues 1, 3, 15)

**Slice 1A — assurance-only (no generation).** Isolates evidence/policy from delivery so a failure is
attributable:
```
recorded instance -> reproduction EvidenceRecord -> AssuranceDecision (policy derivation)
-> fingerprint assertion -> report   (NO card generation, NO retrieval, NO cache)
```

**Slice 1B — assured delivery (only after 1A).**
```
assured instance -> Mode A: SAME semantic instance -> card generation -> trace_consistency
-> assert_delivery_scope(...) -> instance-scope cache entry -> repeat request reuses it
```
Mode A preserves the SEMANTIC instance, not the raw text (issue 15): reordering givens, `100 cm`→`1 m`, symbol
renames, sci-notation formatting, prose→diagram are allowed presentation transforms (they change only the
`presentation` fingerprint); canonical inputs, target quantity, assumptions, comparison, and expected
answer+unit are preserved (the `semantic` fingerprint). Does NOT claim a reusable `motional_emf` relationship.

**Slice 2 — relationship-level (only after Slice 1B).**
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
| A16 | qualitative topic WITH span-groundable source | resolve | source_attributed illustrative example; counts separately from guided |
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
| A35 | payload type disagrees with a supplied kind | construct | derived `kind` is authoritative; no way to disagree (issue 9) |
| A36 | same equation, different output symbol | fingerprint | same relation_equivalence, DIFFERENT execution_contract (issue 3) |
| A37 | required rounding rule changes correctness condition | fingerprint | answer_semantics + comparison identity changes (issue 2) |
| A38 | applicability numeric constraint `unknown` | cache | MISS, never a hit (issue 4/9) |
| A39 | profile says execution but no matching execution EvidenceRecord | deliver | `assert_delivery_scope` fails (issue 1) |
| A40 | execution evidence is for an OLD generated instance | deliver | cannot authorize the new instance (subject fingerprint mismatch) |
| A41 | qualitative claim span from a changed source snapshot | audit | old evidence still auditable; new claim needs new evidence (issue 7) |
| A42 | human-reviewed instance, no computational check, high-risk domain | policy | cannot satisfy execution-required threshold (issue 6) |
| A43 | `answer_anchored` below computational threshold | resolve | explicit below-threshold policy → provisional-with-endpoint-evidence (issue 5) |
| A44 | corroborated relationship → deterministically checked new instance | generate | card gets `verified_execution`, not the relationship's level (issue 8) |
| A45 | same formula, different unit system | cache | correct conversion or MISS (execution_contract differs) |
| A46 | predicate `speed << c` cannot be established | applicability | `unknown` → no reuse (issue 4) |
| A47 | assurance references a missing evidence id | derive AND load AND deliver | integrity failure at ALL THREE boundaries (defense in depth, issue 7) — assurance.py refuses to mint it, load refuses/marks invalid, delivery fails closed |
| A48 | matching execution evidence is revoked | derive/deliver | rejected at both |
| A49 | evidence verifier_name/version not exactly bound to the decision's dependency map | derive/deliver | rejected (exact binding, not set-membership) |
| A50 | same relationship, updated independent source evidence | catalog | semantic contract reused; assurance version updated (not a new contract) |
| A51 | arbitrary/unknown predicate subject | construct | schema validation fails (deferred to 1E) |
| A52 | model-proposed property is the only applicability support | applicability | `unknown`; no cache reuse (deferred to 1E) |
| A53 | review approves pedagogy but not numeric correctness | policy | cannot satisfy computational execution threshold |
| A54 | relationship assurance supplied as learner-card assurance | construct | type failure (kind-split, 1A schema freeze) |
| A55 | answer_anchored internal result reaches shipping | ship | materializes as provisional-with-endpoint-evidence |
| A56 | two canonical-serialization impls hash one fixture | fingerprint | identical expected hash (test vectors) |
| A57 | evidence id belongs to another validation run | deliver | derivation/delivery fails (run_id) |
| A58 | trace uses an unsupported operation | trace check | unsupported/escalate, never confirm (deferred to 1B/§9) |
| A59 | cosmetic formatting change | fingerprint | presentation changes; semantic identities unchanged |
| A60 | verification tolerance change | fingerprint | comparison_policy changes; execution/answer semantics unchanged |

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
  `source_attributed` at most). Reproduction (V1) may confirm one instance because the published answer is the
  independent check — but ONLY that instance (fingerprint invariant).
- `answer_anchored` is never written as verified or promoted from cache without stronger evidence/review.
- Assurance levels are writable ONLY by `assurance.py`, from evidence over the matching fingerprint.
- The catalog never persists a verified entry that wasn't confirmed; provisional never auto-promotes.
- Completeness is never bought with soundness (no relabeling unconfirmed as verified); soundness never excuses
  silent absence (an unconfirmable topic escalates and is counted as a `coverage_gap`, never dropped).
- No `eligible_desired` topic exits the resolver without either a delivered example or a logged `coverage_gap`.
- Retrieval never introduces new execution semantics or a second arithmetic engine.

## 18.5 Deferred to named sub-gates — NOT Phase-1A (v0.4 review: stop broad revision before 1A)

The third review's own guidance: stop adding abstractions before Phase 1A; defer catalog/applicability/V2/
qualitative refinements to their sub-gates. Explicitly deferred (drafted-intent only, built when the sub-gate
opens), so Phase 1A is not gated on them:
- **Catalog identity split** — `ContractIdentity` (reusable semantics) vs a separate `CatalogAssuranceVersion`
  (evidence snapshots + verifier deps + policy + validity), so new evidence refreshes assurance without a new
  semantic contract. → **1E** (v0.4 issue 3, A50).
- **Per-kind assurance enums** — split the single `AssuranceLevel` into `RelationshipAssurance` /
  `InstanceAssurance` / `IllustrativeAssurance` / `InternalCheckDisposition` so a card can't hold a relationship
  level. → resolved at the **1A schema freeze** for the instance enum; others at their sub-gates (issue 4, A54).
- **Typed `PropertyKey` registry + `DerivedProperty` provenance/confidence** (model-proposed → `unknown` until
  confirmed). → **1E** (issues 6, 7, A51/A52).
- **Review-check dimensions** on the certificate (`semantic_correctness`/`numeric_execution`/…), so an
  instance-scope review replaces execution only if the reviewer recomputed the trace. → when human review is
  built (issue 5, A53).
- **Capability-based thresholds** (required_evidence capabilities, enum for sorting only). → policy impl (issue 8).
- **`TraceOperation` union** (Substitute/Evaluate/Rearrange/ConvertUnit/ApplyDefinition/Round/Compare) with a
  validator per op, so `trace_consistency` is deterministic not an LLM judge. → **1B/§9** (issue 9, A58).

## 18.6 Privacy (v0.4 issue 10)

Correction/revocation (§10) needs card↔contract dependency links + exposure events, stored with the MINIMUM
necessary identity. Per-user content-exposure tracking is NOT a hidden requirement: prefer lesson/card-level
remediation; store learner identity only where the product explicitly requires user-level correction notices,
with a defined retention limit. This is an Open Decision (§20), not a Phase-1A dependency.

## 19. Non-goals

Finishing GRB Milestone C; open-web retrieval; numeric "proof" of qualitative claims (they get sourced
illustrative examples); symbolic/CAS calculus; making the equivalence DECISION with an LLM.

## 20. Open decisions

Infra (can the backend retrieve at gen time, within budget?); G0 thresholds (precision floor, min decision
rate, false-confirmation ceiling); source whitelist + independence families; equivalence coverage boundary of
the restricted compiler; provisional review SLA (N days); reviewer roster/qualifications.

## 21. Pre-Phase-1 decision checklist (BLOCKS Phase 1)

*v0.2 items (drafted):* 1. What V1 certifies — Mode A vs B. 2. Contract-fingerprint cache keys + applicability.
3. EvidenceCheck vs AssuranceLevel vs Scope separated. 4. `answer_anchored` downgraded. 5. Qualitative-routing
resolved. 6. Frontend provisional badging a Phase-2 dependency. 7. Source independence/snapshots/licensing/
security. 8. Human review async state machine. 9. Answer-comparison policies. 10. Trace-level verification.

*v0.3 REQUIRED additions (the four hard Phase-1 blockers — drafted in §5/§8/§10/§11, tracked for sign-off):*
**11. Typed candidate payloads** (`PublishedInstance|RelationshipArtifact|IllustrativeInstance`, no
`Mapping[str,Any]`). **12. Versioned canonical fingerprint spec** (`FingerprintSet` + documented
canonicalization + hash version). **13. Structured three-valued applicability contract** (`Predicate`
satisfiability, `unknown`=miss, never an LLM boundary judgment). **14. Assurance policy per example KIND and
DOMAIN RISK** (`required_threshold(kind,risk)`, `AssuranceStrength` ordering, `AssuranceProfile`).

*v0.4 executability tightenings (fold into the above blockers' sign-off; §24):* evidence-inspecting
`assert_delivery_scope`; relation-equivalence vs execution-contract fingerprints; predicate AST; orthogonal
review dims (no `HUMAN_REVIEWED` on the strength axis); `corroborated_relationship` = catalog provenance, not
card assurance; `answer_anchored` ships only as provisional-with-endpoint-evidence; enriched `GroundedClaim`
and `AnswerComparison`; derived `kind`.

**FINAL executable Phase-1A checklist (fifth review — the immediate, bounded to-do; §25):**
1. Populate each required G0 fixture class with representative cases (§17).
2. Define G0 hard-block fixture failures + aggregate thresholds (§14).
3. Freeze the five 1A dataclasses: `PublishedInstance`, `AnswerComparison`, `FingerprintSet`, `EvidenceRecord`,
   `AssuranceDecision` (all tagged `[FREEZE FOR 1A]` in §5).
4. Add `assurance_id`, `run_id`, and exact `verifier_name`→version binding (§5 — DONE in schema).
5. Define versioned canonical serialization + publish expected hash vectors (A56).
6. Implement `validate_assurance_decision` (the shared derive/load/deliver authority, §5).
7. Implement scope validation with typed `EvidenceIntegrityError`, not `assert` (§5).
8. Pass A35–A40, A47–A49, A54, A56, A57, A59, A60.
9. Run G0 and record the sign-off result here.
10. Begin fixture-fed Phase-1A shadow (Slice 1A) only.
Each blocker is "signed off" only with a frozen schema + executable §16 test + recorded acceptance.

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

## 23. Second-review disposition (v0.3 — items 1–15 + 4 required)

| Item | Disposition | Section |
|---|---|---|
| 1 payload weakly typed | ADOPTED — typed tagged union | §5 |
| 2 fingerprint underspecified | ADOPTED — FingerprintSet + canonicalization + hash version | §5 |
| 3 slice 1 does too much | ADOPTED — 1A assurance-only / 1B delivery | §15 |
| 4 corroborated flattened into "verified" | ADOPTED — AssuranceStrength ordering | §5,§11 |
| 5 review outranks execution | ADOPTED — AssuranceProfile (multi-dim) | §5 |
| 6 qualitative claim structure | ADOPTED — GroundedClaim; renamed source_attributed | §5,§9 |
| 7 answer_anchored/provisional lifecycle | ADOPTED — per-level lifecycle table | §11 |
| 8 invalidation deps | ADOPTED — dependency manifest | §5,§10 |
| 9 applicability formal boundary | ADOPTED — three-valued predicate satisfiability | §10 |
| 10 independence concept-specific | ADOPTED — independence dimensions + heuristic caveat | §6 |
| 11 G0 over-broad | ADOPTED — narrowed to authorize 1A V1 only | §14 |
| 12 Phase 1 too coarse | ADOPTED — 1A–1F sub-gates | §14 |
| 13 PendingAcquisition as output | ADOPTED — ResolutionResult metadata | §5 |
| 14 Resolved Coverage for qualitative | ADOPTED — Policy-Satisfied Coverage per kind | §1.5,§11 |
| 15 exact instance = semantic not textual | ADOPTED — allowed presentation transforms | §5,§15 |
| REQUIRED typed payloads | ADOPTED | §5 |
| REQUIRED versioned fingerprint spec | ADOPTED | §5 |
| REQUIRED three-valued applicability | ADOPTED | §10 |
| REQUIRED per-kind/domain assurance | ADOPTED | §11 |
| delivery invariant → executable assertion | ADOPTED — assert_delivery_scope | §5 |

## 24. Third-review disposition (v0.4 — executability & consistency, items 1–10 + rollout + docs)

| Item | Disposition | Section |
|---|---|---|
| 1 assert_delivery_scope inspects labels not records | ADOPTED — inspects real deterministic_execution EvidenceRecords bound to THIS instance | §5 |
| 2 fingerprint/rounding contradiction | ADOPTED — answer_semantics vs comparison_policy vs presentation split | §5 |
| 3 relation-equiv vs execution-contract | ADOPTED — separate fingerprints; cache/gen key on execution_contract | §5,§10 |
| 4 Predicate too narrow | ADOPTED — restricted predicate AST (operator/subject/value/tolerance) | §5,§10 |
| 5 policy/shipping misalignment | ADOPTED — answer_anchored internal-only; ships as provisional-with-endpoint-evidence | §11 |
| 6 HUMAN_REVIEWED in linear enum | ADOPTED — removed; review orthogonal (automated_strength + review_status/scope) | §5,§11 |
| 7 claim span identity weak | ADOPTED — snapshot hash + offsets + extraction_version + support_kind | §5 |
| 8 relationship vs instance assurance | ADOPTED — corroborated_relationship is catalog provenance, not card assurance | §8,§11,§15 |
| 9 tag/payload can disagree | ADOPTED — kind DERIVED from payload type | §5 |
| 10 AnswerComparison lacks quantity semantics | ADOPTED — quantity_kind/unit_dimension/unit_semantics/frame/allowed_units | §5 |
| rollout: named sub-gates | ADOPTED — G1A–G1F | §14 |
| A35–A46 | ADOPTED | §16 |
| doc: coverage-metric naming | ADOPTED — Policy-Satisfied Coverage throughout; metrics named precisely | §1.5,§1.7,§13,§14 |
| doc: define "sign-off" | ADOPTED — schema + executable test + recorded acceptance | status |

**v0.4 consistency-pass (fourth review — corrections only, broad revision CLOSED):**
| Item | Disposition | Section |
|---|---|---|
| evidence lookup fails open | FIXED — fail-closed on missing/incompatible/revoked (EvidenceRecord gains policy_version/run_id/revoked) | §5 |
| semantic = string concat | FIXED — canonical hash + required test vectors (A56) | §5 |
| §13 duplicated "Provisional Exposure" | FIXED | §13 |
| §1.6 stale online-output diagram | FIXED — ResolutionResult{learner_output, acquisition_state} | §1.6 |
| §11 answer_anchored lifecycle row | FIXED — marked internal, materializes as provisional | §11 |
| catalog id split / per-kind enums / PropertyKey / DerivedProperty / review-checks / capability thresholds / TraceOperation | DEFERRED to named sub-gates (not Phase-1A) | §18.5 |
| privacy / data-retention | ADDED — minimum-identity, open decision, not a 1A dependency | §18.6 |
| A47–A60 | ADOPTED | §16 |
| "stop broad revision" | ADOPTED — status declares revision closed; only 5 concrete 1A blockers remain | status |

**Fifth review — "approve as Phase-1A baseline"; final freeze-prep corrections:**
| Item | Disposition | Section |
|---|---|---|
| 1 run_id documented but not checked | FIXED — AssuranceDecision gains assurance_id + run_id; delivery enforces r.run_id == run_id (A57) | §5 |
| 2 verifier-version set-membership too weak | FIXED — EvidenceRecord.verifier_name; exact dependencies[name]==version | §5 |
| 3 same-subject fast path skips level validation | FIXED — shared `validate_assurance_decision` called at derive/load/deliver | §5 |
| 4 freeze scope not marked in §5 | FIXED — [FREEZE FOR 1A]/[DRAFT — 1x]/[DEFERRED] tags on every schema | §5 |
| 5 "Phase 0 implemented" vs "expand fixtures" | FIXED — framework+initial cases done; population not yet G0-broad | §14 |
| 6 assert as enforcement | FIXED — production raises EvidenceIntegrityError; assert is spec shorthand | §5 |
| 7 A47–A49 delivery-only | FIXED — test derive+load+deliver (defense in depth) | §16 |
| 8 policy-version conflation | FIXED — evidence check_contract_version vs assurance_policy_version vs active shipping policy | §5 |
| 9 evidence_subject construction for V1 | FIXED — solver/model/prompt version in evidence context, NOT the semantic fingerprint | §5 |
| 10 G0 aggregate-only | FIXED — categorical hard-block rules | §14 |
| final Phase-1A checklist | ADOPTED — executable 10-item set | §21 |
```
