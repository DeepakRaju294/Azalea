# STUDY_PATH_SCOPE_SPEC — the authoritative path plan (Draft v3.2, design only)

Status: **FROZEN — implementation baseline** (4 review rounds → 9.8/10; architecture locked. Changes only from
a failing fixture, an impossible data-model constraint, or a concrete integration blocker — never another
design pass). Flag: `AZALEA_STUDY_PATH_SCOPE` (dark until Phase 3). First milestone: **Phase 1A** (§10);
pre-coding guardrails, exit criteria, and code-time decisions in **§12**.

> **v3.2 pre-implementation edits (3rd review's "final five" + cheap drift-preventers). No redesign.**
> 1. **Planning vs certification invariants are separate sets** (§4) — the one necessary fix: Phase 1A runs
>    *planning* invariants only; grounding-minimum / assertion-honesty are *certification* invariants (with a
>    `not_applicable` audit status pre-grounding).
> 2. **`RequirementPrereqMapping` split from `RequirementConceptMapping`** (§1.4) — concept relations are
>    `direct|bridge|enrichment`; prerequisites map separately (they are never concepts).
> 3. **`cardinality.policy` is derived** from `section_plan` length; only `split_reason` is authored (§1.6).
> 4. **Section-type enum aligned to instructional roles** (foundation/walkthrough/proof/complexity/edge_cases…)
>    (§1.6).
> 5. **Derivation chain + invalidation + versioning notes** (§11) — one owner per derived value; explicit
>    recompute boundaries; simple migration policy.
> Cheap drift-preventers folded in: `SelectionEvidence.evidence_ref` points at a `ConceptSelectionSource` (no
> duplicated spans, §1.4); `selection_status` aggregates (strongest justifies existence, but a blocking mapping
> still counts) via `mapping_health` (§1.4); exact-alias merge is `normalization`, not `semantic` (§7);
> production shadow uses **counts/distances**, not "precision/recall" (reserved for labelled fixtures) (§10).

> **v3.1 clarifications (3rd review — contract tightening, no redesign).**
> 1. **Dual status model** (§7): `planning_status` ⟂ `certification_status`; a structurally-valid ungrounded
>    Phase-1A scope is now a first-class state. This was the most consequential gap.
> 2. Grounding union has a `ConceptGroundingBase`; Phase 1A permits **skeletal variants** — concrete artifact
>    validation only for adapter grammars first (§1.3).
> 3. `SourceGrounding` split into **`ConceptSelectionSource`** (curriculum: why selected) vs
>    **`ArtifactSourceEvidence`** (grounding: factual) (§1.4).
> 4. **`RequirementConceptMapping`** with `relation` (direct/prerequisite/bridge/enrichment) — selection is
>    per requirement×concept, not one concept-level label (§1.4).
> 5. **`ConceptIdentity`** (canonical key + facet) — duplication reasons over facets, not normalized strings (§1.4/§4.2).
> 6. **`LessonSectionPlan`** — section-level objectives + required artifacts; the scope owns the section plan (§1.6).
> 7. **Policy precedence** `AssertionPolicy → DegradationPolicy → RiskCeiling → lifecycle` + a finite action
>    vocabulary (§1.5).
> 8. "Fill minimum grounding" is **not** a structural repair — it creates factual content ⇒ `semantic` (§7).
> 9. **Semantic-audit severity** (info/warning/high/blocking); "semantic" no longer means "always warn-only" (§4).
> 10. **`source_alignment_mode`** (canonical_truth / course_faithful / compare_and_correct); default
>     course_faithful for uploads (§6.4).
> Plus Phase 1A success **metrics + comparison classes** (§10) and new acceptance tests (§8).

> **v3 changelog (2nd design review).** Architecture is settled; these are tightenings.
> 1. **Modular aggregate** (§1): `StudyPathScope` is an aggregate root of independently-updatable sub-models
>    (identity / intent / curriculum / grounding / notation / verification / validation), not one deep object.
> 2. **Grounding completeness ≠ correctness** (§1.3): minimum-viable grounding per topic type + a
>    `completeness` axis, separate from verification `status`.
> 3. `GeneralConceptGrounding` is a **guarded fallback** (`fallback_reason` required); `intuition_anchors`
>    removed from factual grounding — intuition lives in the prose layer.
> 4. **Explicit unit hierarchy** (§1.6): Concept → one Topic → LessonSection → Card, with stable ids.
> 5. **Selection evidence** (§1.4): decomposition is *evidenced* (`SelectionEvidence`), not a bare confidence.
> 6. **Contextual source authority** (§6.4): `factual` vs `instructional`/`convention` authority — a user's
>    course notes can be authoritative for notation/scope while a textbook wins on facts.
> 7. **Repair severity** (§7): normalization / structural / semantic; semantic repairs can't silently pass.
> 8. **Lifecycle transition table** (§7); `partially_certified` is never consumable.
> 9. **Assertion policy** (§1.5): `(domain, dimension, status) → action`; `consistent` alone never authorizes a
>    technical factual assertion.
> 10. **Audit feasibility classes** (§4): structural / executable audits block; semantic audits warn until
>     stronger verifiers exist — so the contradiction audit isn't presented as uniformly deterministic.

## 0. Why this exists

Almost every generation bug this cycle is the same bug in a different hat: **decisions are made locally and
late, per card and per topic, with no shared authoritative plan.** We kept bolting on deterministic backstops
(intro guarantee, de-conflation, prereq folding, ordering nudge, formula grounding, notation patch), each
catching one instance of "a topic did its own thing."

A **StudyPathScope** is that missing plan: one typed object computed **once** before any lesson is generated,
that every downstream generator is *constrained by* rather than free to re-derive. Non-negotiable invariant:

> **Lessons conform to the scope; the scope is never weakened to match a lesson.**

It carries, per concept, the **best available ground truth and how each dimension was certified** — explicitly
**not "adapter or nothing."** A non-adapter concept is routed *per fact* to the strongest applicable verifier
(adapter / symbolic / code-exec / reference / consensus); any dimension nothing can certify **degrades by an
explicit rule** (§6.1) rather than being asserted.

### 0.1 Issue → resolution (the inventory this must fix)

| Recurring issue | Root (local/late decision) | Scope resolution |
|---|---|---|
| Missing / conflated / mis-typed intro | intro synthesized after the fact | Intro is **derived** from `prerequisites` + `concepts` roadmap + `glossary`. |
| Prereqs taught as their own topic | prereq vs concept decided per topic | `prerequisites` and `concepts` are **separate typed lists**; a prereq never yields a teaching topic. |
| Understand/apply split; dropped/dup concepts | topic granularity chosen by the LLM | concepts map to a scope-owned **section plan** (cardinality *derived* from it, §1.6); coverage/dup are invariants over evidenced mappings (§1.4). |
| Wrong ordering | alphabetical tie-break | `ordering_constraints`: hard DAG + soft prefs + stable fallback (§6.3). |
| Notation clash | each card picks symbols | **scoped** notation registry (§6.2). |
| Wrong formula in the formula card | formula card free-written | grounding artifact + its own `EvidenceRecord`. |
| Wrong / off-concept worked examples | worked example self-graded | `worked_instance` from the verifier + a **selection** check it tests the intended concept (§1.4). |
| Muddled edge cases | edge behavior guessed | come from the verifier; unverifiable ones degrade (§6.1). |
| Hollow / empty takeaways | derived ad hoc | derivation unchanged, over consistent cards; intro carries none. |
| Cross-topic overlap; terms redefined | each topic defines terms | `glossary` (intro-owned) vs concept-local `key_terms`; ownership declared. Per-*concept* layer above the charter's per-*card* layer. |
| Coding topics in a math path | type from wording | `domain` authoritative; `topic_type` validated legal for it. |
| **Non-adapter topics inaccurate** | no ground truth for the long tail | per-dimension verifier routing (§1.5); verified where possible, **honestly degraded** otherwise. |
| **Right facts for the WRONG concept** | verification runs after selection | `SelectionEvidence` (§1.4) separates *selection* from *content* correctness. |

---

## 1. The object — a modular aggregate root (refinement #1)

`StudyPathScope` is the externally-unified aggregate; internally it is independent sub-models with different
update semantics (decomposition can change without re-verifying; evidence regenerates independently; notation
re-unifies after grounding; validation is derived).

```text
StudyPathScope
├─ identity:      ScopeIdentity      { scope_id, scope_version, input_hash, source_revision,
│                                      builder_version, validator_version, certifier_versions{},
│                                      created_at, planning_status, certification_status,
│                                      source_alignment_mode }            # §7, §6.4
├─ intent:        ScopeIntent        { goal, goal_requirements: GoalRequirement[], target_depth, exclusions[] }
├─ classification: { domain, domain_provenance }                          # authoritative
├─ curriculum:    CurriculumGraph    { prerequisites: Prereq[], concepts: Concept[],
│                                      ordering_constraints: {hard_edges: Edge[], soft_preferences: str[]},
│                                      glossary: GlossaryTerm[], decomposition_record: DecompositionRecord }
├─ grounding:     GroundingBundle    { concept_id → ConceptGrounding, concept_id → GroundingSummary }   # §1.3
├─ notation:      NotationRegistry   { entries: NotationEntry[] }                                        # §6.2
├─ verification:  VerificationBundle { concept_id → { selection: SelectionEvidence[],                    # §1.4/1.5
│                                                     dimensions: {dimension → DimensionEvidence} } }
├─ validation:    ValidationReport   { invariants: AuditRecord[], repair_history: RepairRecord[] }       # §4/§7
└─ provenance:    ScopeProvenance    { emitted_by, model_ref }

Concept  (curriculum-level; its facts live in grounding[], its evidence in verification[])
├─ identity   ConceptIdentity  { concept_id, topic_id, name, topic_type,
│                                canonical_concept_key, facet, parent_concept_key: str|null, aliases[] }  # §1.4
├─ prerequisite_concept_ids: str[]
├─ key_terms: str[]
├─ learning_objectives: Objective[]                             # what level to reach
├─ section_plan: LessonSectionPlan[]                            # §1.6 — scope owns depth/structure
├─ selection_sources: ConceptSelectionSource[]                  # WHY selected (curriculum only)
├─ cardinality: { split_reason: str|null }                     # §1.6 — .policy is DERIVED from section_plan
├─ selection_status: confirmed | supported | ambiguous | unsupported     # derived (§1.4)
└─ mapping_health:   clean | contains_warning | contains_blocking        # derived (§1.4)

GoalRequirement { requirement_id, description, source, required: bool, priority, depth }
Prereq          { id, name, anchor, future_path_ref: str|null }
GlossaryTerm    { term, gloss, owner: "intro" }
Objective       { objective_id, statement, target_depth, excluded_depth: str|null }
ConceptSelectionSource { selection_source_id, source_id, chunk_id, span, role }   # role: scope|prerequisite|dependency_selection
# (factual ArtifactSourceEvidence — definition|formula|example|invariant — lives with the grounding artifact, §1.4)
```

### 1.3 `ConceptGrounding` — trace-grammar variants; completeness ≠ correctness (refinements #2, #3)

Factual payload is **one variant** mirroring the adapter trace grammars, so non-formula concepts are grounded
natively. Fields are **optional**, with a **minimum-viable contract** per variant; a separate `completeness`
axis is orthogonal to per-artifact verification `status` (a grounding can be *minimal-but-verified* or
*comprehensive-but-partly-unverified*).

```text
ConceptGroundingBase { grammar, schema_version, artifacts: {name → Artifact} }   # stable interface
ConceptGrounding =
    FormulaGrounding | DerivationGrounding | AlgorithmGrounding | OperationGrounding
  | ProofGrounding   | MechanismGrounding  | NumericalGrounding | TableGrounding
  | ComparisonGrounding | GeneralConceptGrounding
```
The **union interface is fixed now** (so downstream renderers bind to it), but variants may be **skeletal in
Phase 1A** — implement concrete artifact validation for the adapter grammars you already support first; the
others are forward-compatible stubs. Do not perfect `ProofGrounding`/`MechanismGrounding` before scope
*planning* is tested (§10).

| Variant | Minimum-viable artifacts | Optional |
|---|---|---|
| Formula | canonical_formula, worked_instance | symbol_definitions, edge_conditions |
| Derivation | statement, steps, result | edge_conditions |
| Algorithm | input_contract, transition_rules, worked_trace | invariants, termination, complexity_claims |
| Operation | pre_state, operation, post_state, worked_trace | structural_invariants |
| Proof | assumptions, claim, strategy, obligations | edge_cases |
| Mechanism | entities, causal_links, observable_outcomes | conditions, worked_scenario |
| Numerical | recurrence, convergence_criterion, worked_iterations | tolerance |
| Table | columns, rows, exhaustiveness_invariant | — |
| Comparison | dimensions, distinguishing_cases | — |
| GeneralConcept | definition, key_relationships | — (see below) |

```text
GroundingSummary { completeness: minimal|standard|comprehensive,
                   required_artifacts_present: str[], missing_optional_artifacts: str[] }
```

**`GeneralConceptGrounding` is a guarded fallback**, not an escape hatch. Selecting it **requires**
`fallback_reason ∈ {non_procedural, non_formal, unsupported_trace_grammar, insufficient_source}`, and the
validator **rejects** it when a more specific trace grammar applies (test §8). It holds only `definition` +
`key_relationships` — **`intuition_anchors` are removed from factual grounding**; intuition/analogy live in
the free-prose layer unless a specific relationship is itself grounded.

Every artifact (`*` in the taxonomy) carries an `EvidenceRecord` (§1.5).

### 1.4 Selection correctness — evidenced, not asserted (refinement #5; mandatory-2 retained)

Selection (right concept?) and content (facts right for it?) are **independent signals**. Selection is backed
by evidence, so `selection_confidence` is *derived*, not a bare label.

Coverage is a list of **evidenced requirement×concept mappings**, not a bare `requirement→concept[]` map — one
concept may serve several requirements with different relations/strengths.

Concepts and prerequisites map **separately** (a prerequisite is never a concept):

```text
DecompositionRecord { goal_claims: GoalRequirement[],
                      concept_coverage: RequirementConceptMapping[], prereq_coverage: RequirementPrereqMapping[],
                      decomposition_method: goal_only|source_driven|curriculum, unresolved_ambiguities[] }

RequirementConceptMapping { requirement_id, concept_id, relation: direct | bridge | enrichment,
                            evidence: SelectionEvidence[], status }
RequirementPrereqMapping  { requirement_id, prereq_id, evidence: SelectionEvidence[], status }

SelectionEvidence { method: explicit_goal | source_heading | source_span | curriculum_graph | concept_catalog
                            | model_consensus | user_confirmed,
                    evidence_ref: selection_source_id,        # points at a ConceptSelectionSource (no dup spans)
                    status, confidence }
```
Ranked strength: explicitly named in goal > source structure > trusted curriculum/catalog > model inference.
`selection_status` is an **aggregate**, not just the strongest mapping: the strongest inclusion mapping
*justifies existence*, but a blocking mapping conflict still counts — expose both:
`selection_status ∈ {confirmed, supported, ambiguous, unsupported}` **and** `mapping_health ∈ {clean,
contains_warning, contains_blocking}`. An `enrichment` concept is invalid unless `target_depth`/`exclusions`
permit it (test §8). An `unresolved_ambiguity` blocks a consumable scope. **Symbolic execution certifying a
correct answer never upgrades selection** — it verifies content for whatever concept was chosen
(executable-but-wrong-concept test, §8).

**Identity for duplication (§4.2):** each concept carries a `canonical_concept_key` + `facet ∈
{core, method, derivation, correctness, implementation, application}` (+ `parent_concept_key`, `aliases`).
Duplication reasons over *(canonical_key, facet)*, so "Bayes' theorem" vs "Bayes' rule" merge (aliases), while
"Bayes' theorem" (core) vs "derivation of Bayes' theorem" (derivation facet) become **one concept with a
derivation section**, not a deleted duplicate. Adapter slugs + curated keys seed this; normalized text is only
the fallback.

**Factual source evidence** (definition/formula/example/invariant supported by a source span) lives on the
grounding **artifact** as `ArtifactSourceEvidence { source_id, span, claim_supported, role }`, keeping the
curriculum layer (why-selected) and the grounding layer (factual support) cleanly separated.

### 1.5 Verification — per dimension, per artifact, policy-gated (mandatory-3 + refinement #9)

No single concept tier. Each artifact carries evidence; concept `dimensions[dim]` is *derived*.

```text
EvidenceRecord { method: adapter|symbolic|code_exec|reference|model_consensus|none,
                 status: verified|anchored|consistent|unverified,        # anchored = reference-supported
                 source_ref, verifier_version, input_hash, output_hash, diagnostics }
DimensionEvidence { method, status, artifact_refs[] }
```
Routing is **per dimension** (strength depends on the dimension, not a fixed order): `definition`→reference;
`formula`(which-formula)→adapter>reference; `worked_answer`→symbolic>code_exec>adapter; `complexity`→
reference/adapter-proof (code-exec verifies one instance, not the bound); `invariants/transitions`→adapter
trace. `model_consensus` is a **signal, not verification** — it can reach `consistent`, never `verified`.

**Assertion is policy-gated, not status-gated alone.** A card may assert a dimension only if
`AssertionPolicy(domain, dimension, status)` allows it:

| domain · dimension · status | action |
|---|---|
| math · formula · `consistent` (only) | **block** (require verified/anchored) |
| any · worked_answer · `verified` | allow |
| science · definition · `consistent` | require `reference` (→ anchored) or degrade |
| humanities · interpretation · `consistent` | allow **with interpretive framing** (not a factual claim) |
| any · analogy/intuition | allow (prose layer; not a scope fact) |

So `consistent` alone never authorizes a technical factual assertion.

**Precedence (deterministic decision order):** `AssertionPolicy` decides *whether* an artifact may be asserted
→ if not, `DegradationPolicy` (§6.1) chooses the *replacement* → `RiskCeiling` may block the whole topic/scope
if no permitted replacement exists → the result feeds `lifecycle`. The renderer's finite action vocabulary is
exactly: `assert | frame_as_interpretation | render_as_illustrative | omit | block_topic | block_scope`.

### 1.6 Unit hierarchy — explicit, one topic per concept (refinement #4)

```text
Concept  → exactly one Topic  → one or more LessonSection  → one or more Card
concept_id            topic_id              section_id                 card_id
```
`cardinality.policy` is **derived** (`len(section_plan)==1 → atomic`, else `multi_section`); only
`split_reason` is authored. The **scope owns the section plan** so depth/structure is authoritative (the card
charter owns card-level realization *within* a section):

```text
LessonSectionPlan { section_id, section_type, objective_ids: str[],
                    required_grounding_artifact_ids: str[], optional: bool, order }
# section_type ∈ { foundation, intuition, mechanism, walkthrough, derivation, proof,
#                  implementation, application, comparison, complexity, edge_cases }
#   — instructional ROLE, aligned to the card-content charter's vocabulary, not broad pedagogy buckets.
```
`multi_section` requires a `split_reason`; each section is a typed part of the **same** topic and maps
`learning_objectives` to sections (so the Dijkstra objectives "explain greedy frontier / trace / implement /
analyze complexity" land in distinct sections, not distributed by the card generator). Tightly-coupled
micro-concepts (push/pop, precision/recall) are **one** concept with multiple `key_terms`. Duplication is
judged by identity facet (§1.4/§4.2), not string match.

---

## 2. Source-of-truth contract

**Scope owns:** which concepts exist; prereq-vs-concept; concept→topic map; ordering; notation; every
grounding artifact; glossary; domain and each `topic_type`. **LLM authors ONLY** motivation/intuition/
phrasing — the narrative *around* a verified artifact. **MUST-NOT:** a generator is never the source of truth
for a formula/number/edge/definition, a topic's existence/type/order, or prereq-vs-concept. Missing facts
**degrade by §6.1**, never invent.

---

## 3. Production — decompose → certify → validate (two independent signals)

```
goal + source
   │  decomposition (TOPIC_DECOMPOSITION_SPEC) → GoalRequirement[] + draft concepts + SelectionEvidence
   ▼
draft scope (SELECTION signal: coverage, ambiguities, selection_status)
   │  per-concept, per-dimension certification (route each artifact to its best verifier)
   ▼
certified scope (CONTENT signal: EvidenceRecord per artifact; notation unified §6.2)
   │  deterministic validator (§4) → repairs recorded with severity (§7)
   ▼
enforced scope   # planning_status + certification_status set (§7); only a CONSUMABLE scope reaches lessons
```
(Phase 1A stops at the SELECTION signal: `structurally_valid` + `certification_status: not_started` — shadow
only, not consumed.)

---

## 4. Invariants — two sets, feasibility classes (necessary fix + refinement #10)

Invariants split into **PlanningValidator** (runs at Phase 1A over the ungrounded plan → gates
`planning_status`) and **CertificationValidator** (runs once grounding exists → gates `certification_status`).
A certification invariant evaluated before grounding is `status: not_applicable`, not a failure.

Each audit is typed **structural** (deterministic) / **executable** (runs a check) / **semantic** (hard);
`audit_type` says *what kind*, **`severity` says the effect** — "semantic" ≠ "always warn-only."

```text
AuditRecord { invariant, validator: planning|certification, audit_type: structural|executable|semantic,
              severity: info|warning|high|blocking, status: pass|fail|not_applicable,
              confidence, affected_dimension, fallback_action, evidence }
```

**Planning invariants** (Phase 1A):
1. **Coverage** *(blocking)*: every required `GoalRequirement` covered; no orphan concept.
2. **No duplication** *(blocking)*: no two concepts share a *(canonical_concept_key, facet)* (§1.4) — not a string.
3. **Prereq/concept disjoint; prereqs untaught** *(blocking)*.
4. **Order acyclic** *(blocking)*: a cycle is a `RepairRecord` decision or rejection — never auto-broken.
5. **Glossary ownership** *(blocking)*: each term defined once; `key_terms` disjoint from glossary.
6. **Domain legality** *(blocking)*: every `topic_type` legal for `domain`.
7. **Section structure** *(blocking)*: `cardinality` consistent with `section_plan`; objectives map to sections.
8. **Exclusions honoured** *(blocking)*: no concept/section violates `exclusions`; enrichment permitted by depth.
9. **Selection honesty** *(blocking)*: no `unresolved_ambiguity` in a consumable scope.

**Certification invariants** (Phase 1B+; `not_applicable` in 1A):
10. **Grounding minimum** *(structural, high)*: each concept meets its variant's minimum-viable contract or degrades.
11. **Notation scoped** *(structural, blocking)*: no conflicting meaning within a scope; aliases declared (§6.2).
12. **Formula ↔ worked_instance; notation ↔ symbols; DAG ↔ deps** *(executable, blocking)*.
13. **Semantic audits, per-invariant severity**: worked_instance-tests-the-concept → **high/blocking**;
    proof obligations ⊢ claim → **block the proof claim, degrade the topic**; reference ↔ adapter → **high**;
    definition ↔ formula wording → **warning**.
14. **Assertion honesty** *(structural, blocking)*: nothing rendered against `AssertionPolicy` (§1.5). (In 1A,
    only that policies are *configured*, not that cards comply — no cards render yet.)

---

## 5. Consumption

- **Intro:** fully derived — background, prerequisites, glossary terms, roadmap (concepts in order). No worked
  example / practice / takeaways. No synthesis/de-conflation/fold step remains.
- **Concept topic:** receives its `Concept` + `grounding` + path `notation` + `glossary`. Renders the grounding
  variant's artifacts, uses scoped notation, references (never redefines) glossary terms, teaches only its
  `key_terms`, hits `learning_objectives`. Prose is free.
- **Ordering:** stable sort per §6.3. **Takeaways / estimated_minutes:** unchanged derivation, consistent inputs.

---

## 6. Concrete behavior contracts

### 6.1 Degradation by missing dimension
| Unverified | Behavior |
|---|---|
| formula | omit the formula card, or a conceptual-relationship card (no equation) |
| worked_answer | **exploratory, unscored** example, labelled "illustrative" |
| definition | quote/retrieve source; else plain description, no formal-definition framing |
| edge_conditions | omit dedicated edge-case cards (never guess boundaries) |
| notation | plain-language description until grounded |
| algorithm trace/invariants | pseudocode *shape*; no exact-state-transition claims |

Unverified cards are **allowed in production but labelled + logged for regeneration**; a per-domain
`risk_ceiling` may **block** them (math formulas) while allowing them elsewhere. **Withhold beats waffle** —
never "this formula may be…".

### 6.2 Scoped notation
`NotationEntry { notation_id, rendered_form, semantic_role, scope: path|concept|instance, concept_id?,
aliases[], source }`. No conflicting meaning within a scope; concept compatible with path; **instance
variables coexist without replacing canonical notation** (canonical `P(A|B)` at path scope; `P(D|pos)` only
inside a worked instance); multiple canonical forms as declared aliases (`f'(x)`↔`dy/dx`); source-derived code
identifiers are **not** normalized.

### 6.3 Ordering tie-break (deterministic)
Stable topological sort honouring: (1) hard prereq edges; (2) explicit user/goal mention order; (3) source
order; (4) declared soft preferences (e.g. difficulty); (5) stable `concept_id`.

### 6.4 Source authority — contextual (refinement #6)
Split three authorities; resolve per claim type, record conflicts (never silent replacement):

| Claim type | Authority order |
|---|---|
| **factual** (is this correct?) | adapter / trusted reference **>** user upload |
| **convention** (notation, naming, method style) | user's course source **>** generic corpus |
| **scope** (what's in/out of the path) | user source / goal **>** generic curriculum |

```text
ReferenceEvidence { source_id, source_type, factual_authority, instructional_authority, convention_authority,
                    source_span, claim_supported: bool, entailment_status, retrieval_score, conflict_set_ids[] }
```
A fact becomes `anchored` only if the span **entails the precise claim**. When a course source is factually
wrong, record the conflict; use the course's *convention* but the trusted *fact*.

A path-level **`source_alignment_mode`** selects the posture (default **`course_faithful`** for uploaded class
materials): `canonical_truth` (correct source mistakes, teach standard conventions); `course_faithful`
(preserve the course's notation/naming/method constraints, correct only factual errors); `compare_and_correct`
(surface disagreements explicitly). This drives *how* the factual-vs-convention split renders, not just how it
resolves in data.

---

## 7. Lifecycle & repair (dual status — refinement #1, #7, #8)

Planning and certification are **orthogonal workflows**, so a structurally-valid *ungrounded* Phase-1A scope is
a first-class state instead of an awkward "draft/partial." **Consumability is derived** from both fields.

```text
planning_status:      draft | structurally_valid | rejected
certification_status: not_started | partial | complete | complete_with_degradation | failed

consumable  ⇔  planning_status == structurally_valid
               AND certification_status ∈ { complete, complete_with_degradation }
```
| planning | certification | meaning | consumable? |
|---|---|---|---|
| `draft` | `not_started` | plan being built | no |
| `structurally_valid` | `not_started` | **Phase-1A shadow scope** — plan is sound, no facts yet | no (shadow-comparable) |
| `structurally_valid` | `partial` | some required dimensions unresolved | **no** |
| `structurally_valid` | `complete` | facts verified, no blocking degradation | **yes** |
| `structurally_valid` | `complete_with_degradation` | only *allowed* degradations | **yes** |
| `rejected` | any | coverage failure, cycle, unresolved ambiguity, or risk-ceiling | no |

```text
RepairRecord { invariant, repair_class: normalization|structural|semantic, original, repaired,
               method, severity, requires_review: bool, lifecycle_effect, evidence }
```
Repair class follows the **evidence behind it**, not just the operation:
- **normalization** (identifier tidy, stable sort, **exact-alias merge** where the canonical key/alias registry
  already proves equivalence) → may still yield `structurally_valid`.
- **structural** (derive section_ids, add a reverse mapping, attach an *existing* artifact to its slot,
  catalog-confirmed facet consolidation) → `structurally_valid` if invariants pass. **Shape only — never
  creates a fact.**
- **semantic** (reclassify prereq↔concept, a **model-inferred** merge, drop a concept, break a cycle, resolve
  an ambiguous meaning, **or fill a missing grounding artifact — that creates factual content**) →
  `requires_review: true`, at most `complete_with_degradation`; unresolved high-impact → `rejected`.

---

## 8. Acceptance tests (goal → expected scope)

Structural (retained): Bayes+total-probability (both grounded, TP→Bayes, unified path notation `P(A|B)`, intro
names conditional probability, teaches none); single-concept + prereq-only; completing-the-square (atomic).

Content/selection: **ambiguous selection** ("expected value" → `unresolved_ambiguity`, never silently certified);
**independent order** ("quicksort and mergesort" → goal-mention order, not alphabetical); **notation aliases**
(prime ↔ Leibniz coexist); **partial verification** (definition anchored, worked_answer verified, edge omitted;
not globally "verified"); **executable-but-wrong-concept** (symbolic certifies content, selection flags the
mismatch, not shipped as verified); **source disagreement** (recorded, resolved by authority, `RepairRecord`);
**cyclic dependency** (RepairRecord or reject, never auto-broken); **non-formula grounding** ("Dijkstra" →
`AlgorithmGrounding`).

Added in v3: **minimal-vs-comprehensive grounding** (Dijkstra with a worked_trace but no complexity proof →
valid, walkthrough renders, complexity card **omitted** not inferred); **course-convention conflict** (course
notes' nonstandard-but-valid notation → trusted source keeps *factual* authority, course keeps *convention*
authority, lesson uses course notation with a declared alias); **general-grounding abuse** (a procedural
concept assigned `GeneralConceptGrounding` → validator rejects; a specific trace grammar is required);
**semantic repair severity** (builder turns a prereq into a taught concept → logged `semantic`, cannot silently
be `valid`); **status authorization** (math formula with only `model_consensus→consistent` → **blocked**; a
philosophical interpretation with `consistent` → renders with interpretive framing).

Added in v3.1: **bridge concept** ("Bayes' theorem", source assumes total probability → total probability
appears as a `bridge` mapping with evidence *or* as a prerequisite, never an unexplained orphan);
**exclusion enforcement** ("derivatives without proofs" → proof sections excluded; no enrichment violates
`exclusions[]`); **depth-driven cardinality** ("quick review of Dijkstra" → `atomic`; "master Dijkstra incl.
implementation and correctness" → `multi_section` with objectives mapped to walkthrough/implementation/
correctness sections); **alias vs facet** (Bayes' theorem + Bayes' rule → merge as aliases; Bayes' theorem +
derivation-of-Bayes → one concept with a derivation *section*, not a deletion); **planning lifecycle** (a
Phase-1A scope passing all structural checks with no grounding → `planning_status: structurally_valid`,
`certification_status: not_started`, shadow-comparable, **not** consumable).

## 9. Named fixtures
`scope_bayes_total_prob` · `scope_prereq_only` · `scope_ambiguous_expected_value` ·
`scope_independent_order_sorts` · `scope_notation_aliases` · `scope_partial_verification` ·
`scope_wrong_concept_executable` · `scope_source_conflict` · `scope_cyclic_dependency` ·
`scope_algorithm_grounding` · `scope_minimal_grounding` · `scope_course_convention` ·
`scope_general_grounding_abuse` · `scope_semantic_repair` · `scope_status_authorization` ·
`scope_bridge_concept` · `scope_exclusion_enforcement` · `scope_depth_cardinality` ·
`scope_alias_vs_facet` · `scope_planning_lifecycle`.

---

## 10. Implementation surface & rollout — start narrow

The reviewer's warning stands: the danger now is **overbuilding the first implementation**. Phase 1 is split
so schema + planning ship before any factual grounding.

**New:** `app/core/study_path_scope/` **(a package, not one file — §12)** (aggregate + sub-models);
`app/services/scope/` (decomposition→
`DecompositionRecord`/`SelectionEvidence`, per-dimension certifier over existing verifiers + a new sympy
oracle, notation unifier, degradation renderer); validator extensions (§4).

**Changed to read the scope:** intro gen, per-concept lean gen, ordering, the domain gate (→ planning
invariant "Domain legality", §4.6).

**Retired at Phase 3 (after shadow parity):** `_ensure_intro_topic`, de-conflation, prereq-fold, ordering
nudge, `_ground_formula_card`, notation patching. **Kept as evidence producers:** adapter catalog;
`answer_anchor`+`arithmetic_check`+`probability_bounds`; `guided_explanation` (= §6.1 renderer).

- **Phase 1A — scope planning only (the first milestone).** identity (planning_status), intent +
  `GoalRequirement` + `RequirementConceptMapping`, prerequisites, concepts (with `ConceptIdentity`),
  topic mapping, hard dependencies, deterministic ordering, cardinality + `section_plan`, selection_sources,
  the **PlanningValidator** invariants (§4.1–4.9) → a `structurally_valid` scope with `certification_status:
  not_started`. **No factual grounding** (grounding variants are skeletal stubs, §1.3). Emit in **shadow**;
  diff the *plan* against today's output.

  **Success is measured, not "exact parity"** — the current pipeline is what the scope exists to fix, so
  differences are not automatically regressions. `precision/recall` require a gold reference, so they are
  reserved for the **labelled fixture set** (§9). **Production shadow** uses neutral counts/distances:
  `concept_added/removed_count`, `concept_overlap_ratio`, `prereq_added/removed_count`,
  `order: {exact_match: bool, pairwise_distance, hard_edge_violation_count}` (hard-edge violations are the
  load-bearing signal; reordering *independent* concepts is usually harmless), `topic_type_diff_count`,
  `orphan_concept_count`, `unresolved_ambiguity_count`, `semantic_repair_count`. Classify each diff
  `same | scope_improvement | scope_regression | needs_review`. The **gate is the fixture set**, not
  production parity.
- **Phase 1B — adapter-backed grounding.** typed grounding variants (adapter evidence only), notation
  unification, formula↔worked-instance + trace **executable** audits (§4.12). Shadow diff of grounded facts.
- **Phase 2 — consume deterministic wins.** intro + ordering + formula/notation read the scope; retire the
  matching backstops behind the flag. Lesson prose still current.
- **Phase 3 — full certification + consumption.** sympy oracle, code-exec, reference grounding, mixed
  per-dimension evidence, degradation, semantic audits with **initially conservative per-invariant severity**
  (§4.13). Flip the flag after parity; delete retired backstops.

**MUST NOT:** the drafting LLM is not the source of truth for any §2 field; the scope is never weakened to a
lesson; an unverified dimension is never a confident fact; `model_consensus` never yields `verified`; a cycle,
unresolved ambiguity, or semantic repair is never silently passed.

---

## 11. Implementation notes (pre-coding — refinement #5, #1, #12, #13)

**One owner per derived value** (builders/validators/renderers never recompute their own version, so the
authoritative scope can't hold internal disagreements):
```text
SelectionEvidence[]           → RequirementConceptMapping.status
RequirementConceptMapping[]   → Concept.selection_status + mapping_health
section_plan                  → cardinality.policy
grounding artifacts (presence)→ GroundingSummary        ┐ parallel — a grounding can be COMPREHENSIVE
artifact evidence (support)   → DimensionEvidence       ┘ yet weakly supported; not sequential
planning invariants           → planning_status
certification invariants + policy → certification_status
planning_status + certification_status → consumable
```

**Invalidation boundaries** (the modular aggregate's "independently updatable" made concrete):
```text
goal change            → intent + curriculum + everything downstream
ordering change        → curriculum + intro;   grounding stays valid
notation change        → notation + rendered cards;   grounding stays valid
adapter/verifier bump  → affected grounding + verification + validation only
```

**Versioning/migration** (matters once shadow data accumulates): major `scope_version` bump → rebuild;
minor additive → backward-compatible; a grounding `schema_version` change → invalidate *only* the affected
concept's grounding; an unknown grounding variant → rejected (not silently ignored).

**Phase 1A build order:** schemas/ids → `GoalRequirement` extraction → concept/prereq decomposition →
requirement mappings + `SelectionEvidence` → canonical identity + alias/facet consolidation → dependency graph
+ stable ordering → objectives + section plans → **PlanningValidator** → dual-status derivation → shadow
serialization + diff telemetry → fixture suite → production shadow logging.

## 12. Phase 1A — implementation guardrails & exit criteria (pre-coding checklist)

These are **implementation discipline, not architecture** (the reviewer's pre-coding cautions turned into a
checklist). They gate the code, not the design.

**Structure & typing**
- `app/core/study_path_scope/` is a **package** (models / intent / curriculum / identity / grounding /
  verification / validation / lifecycle / serialization), not one file.
- Grounding artifacts are **typed fields** per variant exposing a common `iter_artifacts()` view — *not* an
  unrestricted `{name→Artifact}` dict (prevents `worked_trace` / `worked_traces` drift).
- **Referential integrity:** `SelectionEvidence.evidence_ref` must resolve to an existing
  `ConceptSelectionSource` (right owner, method matches the source, non-empty span, no dangling refs).
- **Stable IDs** derive from `canonical_concept_key` + deterministic namespaces, **never** the mutable display
  title (renaming "Bayes Rule" → "Bayes' Theorem" preserves identity).

**Build-order guarantees**
- Alias/facet consolidation runs **before** the dependency graph (else dangling/duplicate edges, artificial cycles).
- `split_reason` required **iff** `len(section_plan) > 1` (null when atomic).
- **Every required objective maps to ≥1 non-optional section** — an optional section may enrich, never solely own, a required objective.
- **Bridge concepts** inserted only if: dependency-evidenced, necessary for a required concept, not already a prereq, depth-permitted, minimal vs alternatives — never merely "helpful."
- `scope_hard_edge_violations == 0` for any `structurally_valid` scope (report separately from `current_pipeline_hard_edge_violations`).
- *(certification, later)* `course_faithful` preserves notation/naming/method **only where still valid** — factual authority overrides a broken method.

**PR-sized units:** (1) schema + identity · (2) decomposition + mappings · (3) plan construction
(deps/ordering/objectives/sections/exclusions/glossary) · (4) planning validation + shadow telemetry.

**Exit criteria before Phase 1B — ALL must hold:** (1) every named planning fixture passes; (2) a
structurally-valid scope round-trips (serialize↔deserialize) identically; (3) rebuild → stable
concept/topic/section ids; (4) no valid scope has an orphan / ambiguity / cycle / exclusion violation; (5)
alias consolidation doesn't change required coverage; (6) every required objective → a non-optional section;
(7) every concept & prereq justified by ≥1 evidenced mapping; (8) production shadow = zero user-visible change;
(9) pipeline diffs classifiable without treating current output as truth; (10) **no** sympy / code-exec /
grounding / rendering changes in 1A.

**Watch during implementation** (4th-review notes — discipline, not design changes):
- **Single source ownership:** either a scope-level source registry referenced by id, *or* concepts own
  sources and mappings reference them — never copy a `ConceptSelectionSource` into both `selection_sources`
  and a mapping's evidence.
- **`Objective.required`** is explicit (or: concept objectives are required by default, enrichment objectives
  a separate type) — the "every required objective → a non-optional section" criterion needs the field.
- **`selection_status`/`mapping_health` is ONE pure, table-tested function** — validators and serializers
  never re-derive it independently.
- **Phase-1A grounding is `{grounding_status: not_started, planned_grammar, grounding: null}`**, not an empty
  `AlgorithmGrounding` — trace-grammar *selection* is planning; grounding *content* is Phase 1B. Don't imply
  confident content by serializing an empty variant.
- **ID scope is explicit:** `canonical_concept_key` = GLOBAL semantic identity; `concept_id` / `topic_id` /
  `section_id` / `objective_id` = scope-local occurrence — two paths never reuse ids for structurally
  different topics.
- **Exact-alias normalization needs a trusted, versioned alias registry** — a model-generated or source-local
  alias relation is `semantic`, not `normalization` (provenance decides the repair class, §7).

**Property tests** (synthetic scopes, alongside the named fixtures §9): reordering non-mention-order inputs
doesn't change final order; renaming titles doesn't change ids; adding an exact alias doesn't change coverage;
adding an optional section doesn't change required-objective coverage; every `structurally_valid` scope has
zero hard-edge violations; round-trip preserves all references; deleting a selection source → referential-
integrity failure; no mapping targets a missing concept/prereq.

**Code-time decisions (4th review — resolve in the PR, not by revising this frozen spec):**
- **Source registry** (PR2): a scope-level `SelectionSourceRegistry {selection_source_id → ConceptSelectionSource}`;
  `evidence_ref` points into it (one span can justify several mappings) — not per-concept ownership.
- **Objectives are required by default** (PR1): drop the idea of `Objective.required`; enrichment is an
  *optional section* / enrichment mapping, so objectives stay pure commitments.
- **`planned_grammar` is provisional** (PR1): carry `{grammar, selection_method, confidence,
  status: proposed|catalog_supported|confirmed}` — Phase 1A validates *legality*, never asserts the grammar is
  definitively right.
- **Stable ids on every record** (PR1): `mapping_id / audit_id / repair_id / evidence_id` — needed to diff
  shadow scopes and tell new vs resolved vs unchanged warnings apart.
- **`resolved_concept_order: concept_id[]` is an owned derived value** (PR3): the ordering service computes it
  once (per §11); intro + shadow-diff *read* it, never re-run the sort.
- (Optional, deferred) split `planning_status` `rejected` into `invalid` (no valid plan yet) vs `rejected`
  (a completed plan cannot proceed) — not needed for 1A; a failed audit report + `rejected` suffices.
- **Phase-1A sub-aggregate** (PR1): implement a smaller `StudyPathScopePlan` (identity/intent/classification/
  curriculum/planned_grammars/planning_validation/provenance); the full `StudyPathScope` later *wraps* it —
  so 1A code cannot touch certification fields. External architecture unchanged.
- **Centralized facet→section consolidation** (PR3): one function `consolidate_facets(canonical_concept_key,
  discovered_facets, target_depth, exclusions) → (Concept, LessonSectionPlan[])` that decides, per facet,
  whether it becomes a section of the concept, a genuinely independent concept, an already-covered section, or
  is excluded by depth — never handled ad hoc across builders.

## 13. Open questions (deferred)
- Auto-generating `ConceptGrounding` specs (LLM proposes → gate certifies) as a coverage multiplier — needs
  the selection/content split (§1.4) so it can't promote a confidently-wrong grounding.
- The reference corpus (§6.4) — until one exists, non-adapter `definition` sits at `model_consensus`/
  `unverified` (honest, not silently wrong).
- Depth/`learning_objectives` → card-blueprint depth wiring (interaction with CARD_CONTENT_CHARTER_SPEC).
