# Worked-Example Accuracy Spec — Routing + the Verification Ladder

**Status:** **v6 — FROZEN** (design only; not implemented) — *review rounds 1–5 incorporated; froze after r5's two consistency edits (integration-table interface + Tier-2-needs-anchor in the decision flow) + the explicit-slug build order. v6 = explicit `raw_log → teaching_trace → cards` interfaces with stable transition IDs, terminal-vs-endpoint split, `guided_fallback` as a first-class treatment, prose-validator hard/soft boundary, `TeachingTracePolicy` as a first-class adapter property, Phase-A1 self-floor-replacement invariant.*
**Central invariant:** *No computational worked example may use the old generator's own output, estimated step count, or declared cases as the standard for whether it is correct or complete.*
**Owner:** worked-example generation
**Extends:** `WORKED_EXAMPLE_REASONING_SPEC.md` (the trace pipeline is the Tier-1 engine)
**Consumes:** `app/core/visual_ontology_v2.py` (12 base visual types × ~105 modes)
**Supersedes:** the self-grading / self-referential completeness parts of `CODING_WORKED_EXAMPLE_SPEC.md`
**Flag:** `AZALEA_WORKED_EXAMPLE_ACCURACY_LADDER` (default off; additive; off = byte-for-byte unchanged)

This one spec covers **both** halves: (A) **routing** — which of four treatments a topic's worked example
gets; and (B) the **verification ladder** — how a verifiable example is made correct.

---

## 0. One-paragraph summary

Every worked example that *has a determinate answer* is judged against that answer, computed
**independently** — never against the generator's own output. When an **executable adapter** exists, the
example is held to a **hard** guarantee (the adapter runs the real algorithm and verifies the trace); else a
**soft** answer-anchored guarantee; and if neither can reach the verified answer, it is **withheld** rather
than shipped. Examples with **no determinate answer** (illustration / structural / comparison / metaphor)
take a separate **non-verified illustrative** track — a normal card the visual system renders, carrying
`verification_level: none`, never entering the ladder. The adapter is an **executable referee, not an
author**: it stores **zero sample values, zero step text, zero canned examples** — the LLM still authors a
unique instance and all prose for every study path; the adapter only guarantees what the LLM produced is
*genuinely correct*.

---

## 1. Why this spec exists (the failures it closes)

### 1.1 The self-referential completeness bug (observed)
A Prim *coding* worked example shipped with **one step** ("initialize the graph") and never ran the
algorithm. Root cause, traced in code:
- The post-cards validator is called with `expected_min_steps = sol["expected_steps"]`, and
  `expected_steps = len(cards)` (`solver.py:671`) or the LLM's own estimate (`:177`, `:862`). So
  **"expected minimum" = "what the solver produced"** → the completeness check is vacuous.
- The real topic floor (`CODING_STEP_RANGES`) is consulted **only** by the pre-cards outline gate and is
  **never plumbed into the post-cards validator**; and it has **no entry for Prim/Kruskal/Dijkstra** (→
  `default` + borrowed Kruskal "handling cycles" cases).
- The validator *correctly detected* the problem (`missing_required_case`, `did_not_finish`) but only
  **annotated** the card and shipped it (`attempts: 1`).

### 1.2 The static-example anti-pattern (historical)
A prior "hardcoding" attempt stored **finished examples** — same array/node values and same step text every
study path. **Forbidden.** Hardcode the *algorithm*; never the *example* (§7).

### 1.3 The distinction that orders everything
- **Step-level correctness** — are the values/transitions in each step right?
- **Completeness** — does it reach the right answer and cover the required cases?

Cheap fixes (step-count tables, case tables) fix only *completeness* while leaving the LLM free to generate
*wrong steps*. Only an executable reference fixes **both**.

---

## 2. Principles

1. **Answer-anchored, never self-graded.** Completeness and correctness are measured against an
   independently-computed answer. Delete every path where the floor is the example's own length or the
   model's self-estimate.
2. **Adapter = executable referee, not author.** Executable logic + criteria, **no stored values or text**.
   The LLM authors the instance and all prose.
3. **Tiered guarantee, mutually exclusive.** Exactly one treatment per slot (§3).
4. **Never ship a stub.** A verifiable example we can't verify is **withheld**, not shipped. The from-scratch
   self-graded solver leaves the truth flow.
5. **Don't fake rigor where there's none.** Examples with no determinate answer take the non-verified track
   and make no correctness claim — they never fabricate computed "results."
6. **Variety by construction.** Uniqueness = fresh **instance per study path** + **LLM-authored prose**;
   correctness is the only thing pinned. (For a fixed input a correct algorithm has exactly one correct
   trace — variety lives in the instance and the wording.)
7. **Honest provenance + observability.** Each example records its treatment and `verification_level`;
   telemetry exposes regressions and the adapter backlog.
8. **Route by task, not by picture.** What an example *is* epistemically (execution / closed-form /
   derivation / proof / illustration / comparison) is a **task contract**, decided independently of how it
   is *drawn*. Visual mode is supporting evidence, never the source of verification policy (§3.2).
9. **Three layers, not two.** `raw execution log → teaching trace → cards`. The adapter — not the runtime —
   decides which raw events are *required*, *supporting* (mergeable), or *internal* (never learner-facing).
   Completeness is over the **teaching trace**, never the raw log (§5).
10. **Fail safe, not silent.** A Tier-1 failure that indicates a *bug* (reference crash, invariant break,
    trace≠reference) **withholds**; only *benign* failures (not-applicable, no-teaching-instance) may fall
    to Tier 2 (§3.4). The hard guarantee must never disappear quietly.
11. **Soft ≠ verified.** Tier 2 has graded confidence; a single model that reasons, extracts, *and* critiques
    itself is **weak soft**, not "independently verified" (§7.1).
12. **Non-verified ≠ unchecked.** Illustrative examples make no single-answer claim but still get
    factual-integrity checks (no fabricated values, no claims contradicting canonical facts) (§8.1).

---

## 3. Routing — the four treatments

| Treatment | Determinate answer? | What is actually guaranteed | Produced by |
|---|---|---|---|
| **Tier 1 — HARD-TRACE** | yes, adapter applies | trace + state transitions derived from a validated reference, required teaching transitions present in order, prose does not contradict adapter-checked facts | code-anchored adapter |
| **Tier 2 — ANSWER-ANCHORED** | yes, no adapter | **the final answer only** is independently checked; intermediate steps + completeness are **not** guaranteed | answer-anchored generic + critic |
| **Non-verified — ILLUSTRATIVE** | **no** | factual-integrity checked; **no** single-answer proof (`verification_level: none`) | normal LLM card path + visual system |
| **Withheld → GUIDED_FALLBACK** | yes, but unverifiable here | computational topic we couldn't verify → a bounded **guided-explanation** card (no claimed answer, no specific unverified transitions) | guided-explanation fallback (§8b) |
| **Withheld (no card)** | yes, but even the fallback failed its own quality/safety gate | nothing shipped | nobody |

`guided_fallback` is its own treatment, **distinct from illustrative**: illustrative = "this was genuinely
conceptual"; guided_fallback = "this was computational but we couldn't verify a trace." Keeping them
separate is what lets coverage analytics tell real Tier-1/2 reach from gaps (§10).

**Precise guarantees (do not overstate):**
- **Tier 1 is `hard_trace`, not "everything proven."** The trace/state transitions are hard-verified against
  the reference under declared conventions; the **prose** is a *constrained* check
  (`prose_validation_level: adapter_fact_checked`, §6.3), not a proof that arbitrary natural language is
  perfectly correct.
- **Tier 2 verifies the endpoint, full stop.** A sort can reach the right array via a wrong comparison; a
  Dijkstra run can show right final distances while misdescribing a relaxation; a proof can reach a true
  result through invalid reasoning. Provenance records this explicitly (§7.1).

**Two distinctions that must not blur:**
- **Backup (Tier 2) ≠ non-verified.** Tier 2 is *only* for verifiable computations without a hard adapter.
  Non-verified examples have no answer, so Tier 2 has nothing to anchor — routing them there would fabricate
  a fake answer to "verify."
- **Non-verified ≠ withhold.** Withhold is for a computation we *failed* to verify. Non-verified content is
  legitimately shippable illustration — withholding it would strip real teaching value.

### 3.1 The routing decision (per worked-example slot)
```
has worked-example slot?                         (blueprint / card role)
  └─ no  → nothing to route.
  └─ yes → is the example a DETERMINATE COMPUTATION?     (§3.2 predicate)
            ├─ NO  → NON-VERIFIED ILLUSTRATIVE track     (§8)   [or unsupported → GUIDED_FALLBACK]
            └─ YES → applicable hard adapter?            (§3.3)
                      ├─ yes → TIER 1 (hard)  ── fails (bug-class) → WITHHELD/GUIDED (§3.4)
                      └─ no  → independent endpoint source exists? (§7.1)
                                ├─ yes → TIER 2 (soft, answer-anchored) ── can't reach answer → GUIDED_FALLBACK
                                └─ no  → GUIDED_FALLBACK (§8b)
```
**Tier 2 is not the automatic "no adapter" bucket** — it requires a *real independent answer anchor* (§7.1).
A determinate computation with no adapter **and** no anchor → `guided_fallback`, never an unverified
"Tier 2" example. (This is exactly the Phase-A1 invariant: verified-trace ∨ verified-endpoint ∨
guided_fallback — §13.)
Mutually exclusive. Tier-1 *attempt* failure is **classified** (§3.4): benign categories (`not_applicable`)
fall to Tier 2 at INFO; bug categories withhold + alert. Tier-2 endpoint failure → withheld. The
non-verified branch never withholds on correctness (there is none) — only on the normal card-quality gate.

### 3.2 The task contract decides the treatment (NOT the visual mode)
Visual mode is a **presentation choice**, not a statement of what the example is doing — a `graph_network`
visual can host "what is a graph?" (illustrative), "run Prim here" (determinate), or "BFS vs DFS"
(comparison); a `formula` visual can host Ohm's-law substitution (determinate), "why derivatives measure
local change" (conceptual), or a multi-route identity (soft). So routing reads an explicit
**worked-example task contract**, with visual mode as one input among several.

```python
class WorkedExampleTask:
    task_kind: Literal["deterministic_execution", "closed_form_computation",
                       "multi_path_derivation", "proof_or_reasoning",
                       "conceptual_illustration", "comparison"]
    # capability vs concreteness are distinct (review r3): "we can make an example"
    # is NOT "this example has a defined input".
    can_construct_valid_instance: bool          # could a valid bounded instance be produced? (pre-Stage-0)
    instance_is_fixed: bool                     # THIS example already has a concrete input (post-Stage-0)
    has_executable_terminal_condition: bool     # execution-style "done" (an algorithm halts) — for the trace
    has_independently_checkable_endpoint: bool  # the CONCLUSION can be checked (proof conclusion, symbolic equiv) even with no execution
    has_unique_or_equivalent_answer: bool       # one answer, or an equivalence class?
    requested_learning_goal: str
    classification_status: Literal["resolved", "ambiguous", "unsupported"]   # §3.2.1
    task_contract_confidence: float        # §3.5.5 (evidence-derived, not LLM self-report)
    classification_source: Literal["explicit_topic_metadata","deterministic_rule","llm_classifier","fallback_heuristic"]
```
`can_construct_valid_instance` is the determinacy signal *before* Stage 0 (e.g. Kruskal: true);
`instance_is_fixed` becomes true *after* instance selection. Determinacy routing keys off
`can_construct_valid_instance` (+ terminal + answer); the trace then fixes the instance.

The contract is produced by the **task-kind classifier (§3.5)** — the same pass that sets the visual domain
— from: **task contract + topic metadata + available reference/adapter + visual mode (supporting evidence)
→ treatment.** Its booleans are the primary routing key; `task_kind` only refines within a tier (§3.5.1).

| Example type | exec. terminal | checkable endpoint | Treatment |
|---|---|---|---|
| algorithm execution (BFS, Kruskal) | yes | yes | **Tier 1** if adapter, else **Tier 2** |
| formula substitution | not necessarily | yes | **Tier 1/2** (depends on evaluator) |
| symbolic derivation | no | often yes | **Tier 2** |
| proof | no | sometimes | **Tier 2**, else **guided** |
| conceptual explanation | no | no | **Illustrative** (§8) |
| ambiguous / `unsupported` | unknown | unknown | **guided-explanation (§8b)**, never illustrative |

So `has_executable_terminal_condition` drives whether a *trace* can be run (Tier-1 eligibility);
`has_independently_checkable_endpoint` drives whether the *conclusion* can be soft-verified (Tier-2
eligibility). The two are distinct — a proof has the latter without the former. "Terminal condition" is no
longer a vague catch-all for "has an answer."

**Conservative default:** Tier 1 needs `has_executable_terminal_condition` + `has_unique_or_equivalent_answer`
(+ an applicable adapter); Tier 2 needs `has_independently_checkable_endpoint`; if neither holds it is
non-verified (or `unsupported` → guided). Visual mode + the §15 tier table only *corroborate* the contract (and flag mismatches in
telemetry, §10) — they never override it.

### 3.2.1 Classification uncertainty is first-class — three states, not a threshold
A confident-but-wrong classifier causes the exact routing error we're preventing. So the contract carries an
explicit **`classification_status`**, because "low confidence" hides two very different situations:

| `classification_status` | Meaning | Route |
|---|---|---|
| **resolved** | evidence clearly decides it | route normally (§3.1) |
| **ambiguous** | plausible evidence *both* ways | bias to verification: **possibly-computational → Tier 2 / withhold**; only **clearly-conceptual → illustrative** |
| **unsupported** | not enough information to know whether a valid worked computation even exists | **guided-explanation (§8b)** — **NOT** illustrative — unless the blueprint *explicitly* declares conceptual instruction |

The `unsupported` state is the key r3 addition: it prevents the trap where the classifier *can't tell* and
defaults to illustrative, which then ships an **invented** trace.
```
Topic: "Analyze the cache replacement behavior."   (policy/inputs unclear)
  bad:  illustrative card that accidentally contains a made-up trace
  safe: Key-process guided explanation, no computed claims (§8b)
```
**The asymmetry rule still governs:** mislabeling conceptual-as-computational costs a withhold (safe);
mislabeling computational-as-illustrative ships an unverified "answer" (unsafe) — ties break toward the
ladder, and "don't know" breaks toward guided-explanation, never illustrative.

### 3.3 The Tier-1 applicability predicate
Route to **Tier 1** iff `adapter_exists(topic) AND canonical_reference_fits(topic)`:
- `adapter_exists` — the topic resolves (explicit, non-fuzzy; `trace_pipeline.route_adapter`) to a
  registered adapter slug.
- `canonical_reference_fits` — a **standard implementation**, not a deliberate variant ("Kruskal with path
  compression", a bespoke structure) whose code/line-map wouldn't match the canonical reference.

If an adapter *exists* but isn't applicable → Tier 2. **This replaces** the temporary `coding_implementation`
guard in `route_adapter` (which blanket-deferred coding topics because the conceptual trace lacked
highlighting) — with code-anchoring, coding topics *should* enter Tier 1.

### 3.4 Tier-1 failure is classified — not a blanket fall-through
"Tier-1 fails → Tier 2" is unsafe as a blanket rule: a **reference bug** must not quietly downgrade while the
lesson still ships looking normal (the hard guarantee would vanish invisibly). Every Tier-1 failure is
categorized and routed by category:

```python
class Tier1Failure:
    category: Literal["not_applicable", "instance_rejected", "no_teaching_instance",
                      "reference_runtime_failure", "reference_invariant_failure",
                      "trace_disagrees_with_reference", "mapping_failure"]
```

| Category | Meaning | Action |
|---|---|---|
| `not_applicable` | topic isn't this canonical variant | **→ Tier 2** |
| `instance_rejected` | LLM instance malformed/non-teaching | **retry instance / seeded fallback** (stay Tier 1) |
| `no_teaching_instance` | adapter found no good instance | → Tier 2 **if** an independent answer exists, else **withhold** |
| `reference_runtime_failure` | the reference crashed | **WITHHOLD** (likely a bug) |
| `reference_invariant_failure` | structural invariants broke | **WITHHOLD** (likely a bug) |
| `trace_disagrees_with_reference` | verification mismatch | **WITHHOLD** — do **not** trust Tier 2 here |
| `mapping_failure` | step→line map missing | ship the **verified trace without highlighting**, or withhold the code anchoring only |

Only `not_applicable` (and conditionally `no_teaching_instance`) are normal soft degradation. Bug-class
failures **withhold and alert** — they never silently downgrade. (`instance_rejected` is benign churn, not a
downgrade.)

**`mapping_failure` is NOT a correctness failure.** A missing step→line map is a *highlighting* (UI/enhance-
ment) gap, not a trace gap. It ships the fully-verified worked example with a separate **capability state**,
and must **not** count against hard-tier correctness telemetry (else an enhancement bug deflates the
correctness success rate):
```json
{ "worked_example_verified": true, "code_anchor_available": false, "highlighting_status": "unavailable" }
```

---

## 3.5 The task-kind classifier — deriving the contract (the routing keystone)

The whole ladder keys off the `WorkedExampleTask` contract (§3.2), so its derivation is the most load-bearing
input in the system. Two commitments make it robust *despite* imperfect classification.

### 3.5.1 The booleans are primary; `task_kind` is descriptive
The booleans (`can_construct_valid_instance`, `has_executable_terminal_condition`,
`has_independently_checkable_endpoint`, `has_unique_or_equivalent_answer`) are far more **decidable** than the
6-way label, and they are what actually gates the tier:
- executable terminal + unique/equiv answer (+ adapter) → **Tier 1**;
- checkable endpoint, no executable terminal or no adapter → **Tier 2 / soft**;
- neither → **non-verified** (or `unsupported` → guided).

`task_kind` only **refines within** a tier (e.g. `multi_path_derivation` vs `proof_or_reasoning` both sit in
Tier 2 but get different critic prompts). **A wrong label with right booleans still routes correctly** — so
effort goes into the booleans first.

### 3.5.2 Layered derivation — highest-confidence source wins
| Layer | Source | Fires when | Base confidence |
|---|---|---|---|
| **L1** | explicit metadata | blueprint/topic declares the kind, or `coding_implementation` + a resolved algorithm slug | 1.0 |
| **L2** | deterministic rules | structured signals decide it (course_type + adapter presence + visual domain + instance/code present) | 0.9 |
| **L3** | LLM classifier | ambiguous; the LLM reads title + learning goal + lesson content, emits the contract + self-confidence | 0.4–0.7 |
| **L4** | fallback heuristic | nothing else fired | 0.3 |

Layers short-circuit top-down; a lower layer never overrides a higher one. `classification_source` records
which layer decided.

### 3.5.3 Inputs (reuse existing classifiers — do not duplicate)
`course_type` (from `course_type_classifier`: coding_implementation / algorithm_walkthrough /
study_path_introduction / …) · visual domain + mode (`visual_ontology_v2`) · adapter availability
(`route_adapter`) · the worked-example card's blueprint role + learning goal · the lesson's actual
content/code when present (is there a concrete instance? a terminating procedure?).

### 3.5.4 Deriving each boolean from *evidence* (not a guess)
- `can_construct_valid_instance` ← a valid bounded instance *could* be produced (adapter `candidates`, or
  the topic names a specific case). `instance_is_fixed` is set later, after Stage-0 selection.
- `has_executable_terminal_condition` ← an execution-style "done" (the procedure terminates; a loop ends).
- `has_independently_checkable_endpoint` ← the conclusion can be checked without execution (a proof's
  conclusion verified, a symbolic equivalence, a numeric evaluator) — true for proofs/derivations that have
  no executable terminal.
- `has_unique_or_equivalent_answer` ← the answer is unique or a well-defined equivalence class (an MST
  up to equal-weight ties = **yes**; "discuss the trade-offs" = **no**).

Each boolean carries a short `evidence` string (for telemetry/debug and for explaining a route).

### 3.5.5 Conflict & confidence — from *evidence*, not the model's self-report
- **L1 wins outright.** If L2 didn't fully decide and L3 is consulted and they **disagree** → mark
  `classification_status = ambiguous`, take the conservative side (§3.2.1).
- **Confidence is computed from observable evidence, not "the LLM says 82%".** The L3 model *produces the
  contract*; the system *scores it*:
```python
task_contract_confidence = (
    metadata_score              # +explicit algorithm slug / declared kind
  + deterministic_signal_score  # +concrete code supplied, +adapter match, +recognizable I/O structure
  + cross_source_agreement      # +deterministic-rule and LLM label agree
  - conflict_penalty            # −conflicting signals, −vague learning goal, −no clear terminal condition
)
```
This is auditable and tunable in a way a model's stated confidence is not. The §3.2.1 `classification_status`
(`resolved`/`ambiguous`/`unsupported`) is derived from this score + whether *any* determinacy evidence
exists at all (none → `unsupported`).

### 3.5.6 The asymmetric safety objective (what we tune for)
The two error directions are **not** equal cost:
- **false-illustrative** — a real computation labeled conceptual → ships unverified (`verification_level:
  none`): **dangerous** (the exact Prim-class failure).
- **false-computational** — a conceptual topic labeled computational → withheld / Tier-2: **safe** (at worst
  an §8b guided-explanation card).

So the classifier and thresholds are tuned to **minimize false-illustrative**, accepting more
false-computational: any non-trivial computational signal forces *at least* Tier-2 consideration before
illustrative is permitted.

### 3.5.7 Validation (the part that makes the keystone trustworthy)
- **Gold set built around *dangerous confusions*,** not generic topics — the borderline pairs where mistakes
  happen:
  | Confusable pair | Distinction at risk |
  |---|---|
  | "Run Dijkstra" vs "Explain Dijkstra" | computation vs conceptual |
  | "Solve this recurrence" vs "Explain recurrence expansion" | determinate vs illustrative |
  | "Implement BFS" vs "Compare BFS and DFS" | execution vs comparison |
  | "Calculate circuit current" vs "Explain current flow" | closed-form vs conceptual |
  | "Prove a statement" vs "Apply a theorem to fixed values" | soft reasoning vs deterministic |
  | "Trace linked-list insertion" vs "Describe linked-list insertion" | state trace vs explanation |
- **Two safety metrics, both driven near zero:**
  - **false-illustrative** — truly-computational slot routed to illustrative (ships *unverified* computation). The headline metric.
  - **false-hard** — routed Tier 1 when the adapter/reference semantics don't actually apply (ships a *confidently wrong* trace via the wrong adapter). Guarded by §3.3 `canonical_reference_fits` + §3.4 `trace_disagrees_with_reference` → withhold.
- **Cross-source agreement** logged (L2-vs-L3 disagreement rate = a standing health signal).
- **Runtime feedback loop:** §10 telemetry feeds recalibration — a spike means a mis-route; rules/gold-set
  update.
- **Gate:** Phase A3 does **not** trust the classifier for *determinacy* until both safety metrics clear a
  bar on the gold set; until then conservative defaults (ambiguous → Tier-2/withhold; unsupported →
  guided-explanation; never illustrative).

### 3.5.8 Output
```python
WorkedExampleTask(
    task_kind=...,                       # descriptive refinement (§3.5.1)
    can_construct_valid_instance=..., instance_is_fixed=...,
    has_executable_terminal_condition=..., has_independently_checkable_endpoint=..., has_unique_or_equivalent_answer=...,
    requested_learning_goal=...,
    classification_status="resolved|ambiguous|unsupported",                    # §3.2.1
    task_contract_confidence=0.0..1.0,                                         # §3.5.5 (evidence-derived)
    classification_source="explicit_topic_metadata|deterministic_rule|llm_classifier|fallback_heuristic",
    evidence={"instance": "...", "terminal": "...", "answer": "..."},          # for telemetry + debug
)
```

---

## 4. The accuracy contract — adapter vs LLM

| Concern | ADAPTER (referee) | LLM (author) |
|---|---|---|
| Algorithm logic / correct transitions | ✅ executable reference | ✗ |
| Required cases, invariants, equivalence, completeness floor | ✅ derived from the trace | ✗ |
| Canonical code + step→line map (Tier 1) | ✅ | ✗ |
| **The instance (graph / array / values)** | ✗ (validates it) | ✅ proposes it |
| **All learner-facing prose** | ✗ | ✅ |

**The adapter ships no finished learner examples.** The hard line against §1.2 is precise, not absolute:
| Forbidden | Allowed (adapter-owned) |
|---|---|
| stored finished learner examples with fixed prose + static values surfaced every path | test fixtures, regression graphs/arrays, **seeded candidate templates**, property-test generators, canonical counterexamples used only to validate the adapter |

The precise rule: **no canned *finished learner example*, fixed trace, or stored prose is surfaced
directly.** Seeded instance generators and candidate templates may supply valid *inputs*, but **every
learner-facing trace is freshly executed and every explanation freshly authored.** A seeded graph template
is fine; a fixed graph + fixed step text repeated to every learner is not.

### 4.1 Instance source — hybrid, not LLM-first
LLM-proposed instances add variety but, as the *default* truth source, cause rejection churn (propose →
disconnected/trivial → reject → retry → latency). Use a **hybrid policy**:
- **Default:** the adapter's **seeded candidate pool** (`candidates(seed)`) — always valid, fast,
  reproducible.
- **Optional:** the LLM proposes an instance when domain flavor / user context matters; the adapter
  `accept_instance`-validates it (teaching-quality, well-formed); on reject, retry-bounded then fall to
  seeded.
- **LLM-within-bounds always:** even on a seeded structure, the LLM may set **labels, scenario framing, and
  values within validated bounds** — e.g. nodes labeled `Detroit, Chicago, Toronto` vs `A, B, C, D` per
  lesson context.

So **instance *validity* never depends on LLM retries**, while variety (structure when entropy allows, plus
labels/framing always) is preserved. Then: adapter runs the real algorithm → canonical trace → prose-only
formatter narrates → backend attaches verified state → Stage-4/4b guards reject misstated values. Result per
path: **unique instance + unique wording + guaranteed-correct trace.**

---

## 5. Completeness model (answer-anchored, over the *teaching trace*)

Stop asking *"did you produce ≥ N steps?"* (N is guessed and self-sourced). But also do **not** swing to the
opposite failure — *"every runtime event must become a card"* — which recreates the old 80-card over-long
example (Prim's stale heap entries, Kruskal's every rejected edge, Dijkstra's every non-improving
relaxation, merge sort's tiny internal actions). The answer is the **three-layer model**:

```
raw execution log   →   teaching trace   →   cards
   (the reference)      (adapter-curated)     (one per teaching transition)
```

The adapter classifies each raw event:
- **required** — must be shown (a defining transition).
- **supporting** — may be merged into a nearby teaching transition.
- **internal** — necessary to execute, never learner-facing.

### 5.1 The core completeness rule (replaces the old floor)
> **A computational example is complete when a validated reference execution reaches its terminal
> condition, and every *required teaching transition* derived from that execution is represented in the
> learner-facing trace, in order. Raw runtime events may be grouped or omitted only according to the
> adapter's teaching-trace contract.**

This avoids both failure modes — too weak ("the model produced enough cards") and too rigid ("every runtime
event is a card").

### 5.1.1 `TeachingTracePolicy` — the required set, declared and *testable*
`required_transitions(trace)` is where the core educational judgment lives; if it's vague the system still
has gaps. Each adapter declares a **machine-checkable** policy (evaluated directly against a trace, not
described in prose):
```python
class TeachingTracePolicy:
    terminal_transition_required: bool = True
    representative_branch_rules: list[Rule]   # "≥1 of branch X if any occurs"
    minimum_decision_diversity: list[Rule]    # e.g. ≥1 accept AND ≥1 reject
    grouping_rules: list[Rule]                 # which supporting events merge into a transition
    suppressible_event_types: set[str]         # internal events never shown
    # the policy ALSO governs instance selection (r3) — a perfect required-set is useless if Stage 0
    # picks an instance that never triggers the transitions, or one far too large for a card budget:
    instance_acceptance_rules: list[Rule]      # what a valid teaching instance must be able to produce
    minimum_trace_transitions: int             # reject trivial instances
    maximum_trace_transitions: int             # PACING cap — solve length at Stage 0, not by compression
```
Rules use **"required if observed"** semantics — instance selection does **not** fail because a graph has no
tie; but if the *chosen* instance produces one and the declared convention resolves it, that transition is
required to be shown.

Example — **Prim** (`instance_acceptance_rules`): connected graph · ≥(V−1) valid tree-expanding selections ·
≥1 frontier update · bounded node/edge count · no excessive tie ambiguity *unless* tie-breaking is a stated
lesson goal. **Required-set:** initialization · each accepted tree-expanding edge · ≥1 frontier update ·
completion. **Required if observed:** a stale/internal candidate skip · a tie-break. **Supporting (merge):**
repeated candidate insertions after the same new vertex. **Internal (suppress):** heap bookkeeping.

**Pacing is a Stage-0 problem, not a compression problem.** "Each accepted tree-expanding edge" is right for
a 6-node graph but becomes an 11-step slog for a 12-node one. The fix is **not** to compress accepted
transitions later (risky) — it is to **not select** an instance that needs 11 meaningful expansions:
`maximum_trace_transitions` makes Stage 0 reject it. Don't compress accepted transitions in one trace unless
the adapter declares a pedagogically safe `grouping_rule`. Example — **binary search** acceptance: ≥3 probes
· ≥1 bound movement · no immediate hit unless a direct hit is the goal · bounded array. **Kruskal:** enough
accepts to reach V−1 · ≥1 representative cycle-rejection · component-update evidence · completion.
"≥1 representative", never "every" — representativeness, not exhaustiveness.

### 5.2 Concrete changes
- Delete `expected_min_steps = sol["expected_steps"]` (`solver.py:1426`) and the `len(cards)`/`len(plan)`
  self-sources (`:671`, `:862`).
- The required teaching-transition set + completeness come from the **adapter's teaching-trace contract over
  the reference** (Tier 1) or the **independent reference** (Tier 2) — never the produced cards.
- **Re-gate after card-building** (an approved plan can collapse below the required set during construction).
- The resolve loop exits on **"all required teaching transitions present, terminal reached"**, else
  **withhold**.

---

## 6. Tier 1 — the code-anchored adapter (HARD)

### 6.1 Canonical code (the make-or-break detail)
One **canonical reference implementation** per algorithm. For a Tier-1 coding topic, the **code walkthrough**
and the **worked example** both display that code (one source of truth → they finally agree), and each
`Step` carries a **step→line map** into it, so highlighting is exact, not inferred from arbitrary LLM code.
> Do **not** map a verified trace onto LLM-generated code by guesswork — highlights would land on wrong
> lines and the guarantee would leak. Tier 1 pins the code; varied code is a Tier-2 concern.

`Step` gains: `code_lines: list[int]` (canonical lines this step executes), `code_anchor: str` (stable
semantic anchor, e.g. `"select_min_edge"`, surviving reformatting).

### 6.2 Adapter surface — the three layers are explicit interfaces
The `raw_log → teaching_trace → cards` model (§5) must be **real method boundaries**, not a blurred single
`reference()` — otherwise the system slips back into treating raw runtime events as cards or a partial trace
as complete. `TeachingTracePolicy` is a **first-class property** (so its rules aren't scattered across
`candidates`/`is_teaching_trace`/`required_transitions`/prompts):
```python
class TraceAdapter(Protocol):
    canonical_code: str
    teaching_trace_policy: TeachingTracePolicy           # §5.1.1 — owns acceptance, min/max, required-if-observed, grouping, suppression

    def candidates(self, seed) -> Iterable[dict]: ...    # seeded instance pool (default source, §4.1)
    def accept_instance(self, proposed: dict) -> Optional[dict]: ...   # validate LLM instance; None = reject
    def run_reference(self, instance: dict) -> RawExecutionLog: ...    # LAYER 1: the raw log (the truth)
    def build_teaching_trace(self, raw_log: RawExecutionLog) -> ContractTrace: ...  # LAYER 2: apply the policy
    def required_transition_ids(self, trace: ContractTrace) -> list[str]: ...       # must-show set (stable IDs)
    def step_code_lines(self, step: Step) -> list[int]: ...            # verified step -> canonical lines (C2)
    def prose_fact_contract(self, step: Step) -> ProseFactContract: ... # §6.3
```
Teaching transitions carry **stable IDs** linking back to raw events, so completeness is an exact set check,
not a heuristic:
```python
TeachingTransition(id="kruskal_accept_3", source_event_ids=["raw_18","raw_19"],
                   kind="accept_edge", required=True, prior_state={...}, state_after={...})
# completeness:  required_transition_ids(trace)  ⊆  {t.id for t rendered into cards}
```

### 6.3 The prose fact contract (formal, per teaching step)
Backend-attached state guarantees the *machine* values are right; the learner reads *prose*, which can still
teach something false even when metadata is correct. So each teaching step carries a formal contract the
formatter is held to across **all** prose fields (`goal`, `reasoning`, `work`, `result`) — not just the final
result:
```python
class ProseFactContract:
    required_facts: list[Fact]     # structured (below) — must be entailed
    allowed_entities: set[str]     # nodes/edges/vars this step may mention
    allowed_values: set[int|str]   # values this step may mention
    prohibited_claims: list[Fact]  # facts that would be FALSE at this step
```
**Facts are structured, not strings** (so the backend never infers schema from prose, and validation +
formatter-instructions share one source). Each carries a human string for prompt readability:
```python
{"predicate": "equals",       "left": "mid", "right": 5,                  "text": "mid = 5"}
{"predicate": "comparison",   "left": "arr[mid]", "op": "<", "right": "target", "text": "19 < 43"}
{"predicate": "state_change", "field": "low", "from": 0, "to": 6,         "text": "low changes from 0 to 6"}
```
Example — **Kruskal** cycle-reject step: required `consider (B,C,4)` · `reject` · `both endpoints in one
component`; prohibited `add edge` · `increase MST weight` · `merge components`.

**The validator's real boundary (don't overstate NL entailment).** Structured facts make the check far
stronger, but natural language can still paraphrase or imply — so the validator is a **bounded compliance
checker**, not an entailment prover:
- **Hard checks (block):** no value outside `allowed_values` · no entity outside `allowed_entities` · no
  `prohibited_claims` present · no incorrect state-change · no invalid accept/reject decision · no wrong
  edge/node/index named.
- **Soft checks (advisory):** all `required_facts` clearly expressed · explanation pedagogically sufficient.

This is why the guarantee is split: `hard_trace` (the state/transition trace is correct) +
`adapter_fact_checked` (the prose passed the **bounded** contradiction checks above) — never "the prose is
proven entailed." Stage-4b is promoted from a loose string validator to this adapter-owned structured
contract — the last hole where machine state is correct but the wording teaches a falsehood.

### 6.4 Flow (the three layers, explicit)
```
inst     = adapter.candidates(seed).pick()              # DEFAULT seeded (§4.1); optional accept_instance(llm)
raw_log  = adapter.run_reference(inst)                  # LAYER 1 — the truth
assert validate_raw_log(raw_log, adapter).ok
trace    = adapter.build_teaching_trace(raw_log)        # LAYER 2 — apply TeachingTracePolicy
req_ids  = adapter.required_transition_ids(trace)
assert structural_invariants(trace, adapter) == []      # §5 hard gate
cards    = format_prose(trace)                          # LAYER 3 — LLM narrates; backend attaches state
assert {t.id for t in rendered(cards)} ⊇ set(req_ids)   # §5 completeness — exact set check on stable IDs
assert validate_fidelity(cards, trace, adapter).ok and validate_prose(cards, trace, adapter) == []
attach_code(cards, adapter.canonical_code, adapter.step_code_lines)   # C2; mapping_failure -> ship w/o highlight
ship(cards, treatment="hard", verification_level="hard_trace", tier=1)
```

---

## 7. Tier 2 — answer-anchored generic (SOFT)

For verifiable computations without an applicable adapter.

> **Guarantee:** the **final answer** is independently checked.
> **No guarantee:** that every intermediate operation is correct, or that every required teaching transition
> is shown.

Mandatory:
1. **Independent answer** (§7.1) — *not* from the LLM's own steps.
2. **Withhold-on-fail** if the final state ≠ verified answer after the resolve budget.
3. **Dimensional provenance** — say exactly what was checked, so telemetry and any future UI stay honest:
```json
{ "verification_level": "soft", "tier": 2, "confidence": "moderate_soft",
  "verified_dimensions": ["final_answer"],
  "unverified_dimensions": ["intermediate_transition_correctness", "teaching_trace_completeness"] }
```

### 7.1 The answer must be *truly* independent — graded confidence
`reason → extract + verify` is still self-referential if the *same* model/prompt family produces both the
candidate walkthrough and the answer anchor. Tier 2 records which it used:

| Confidence | Source of the anchor |
|---|---|
| **strong_soft** | closed-form / symbolic solver, a unit-tested generic executor, or an **independent second implementation** |
| **moderate_soft** | two **independent** model generations that agree **+** invariant/property checks |
| **weak_soft** | one model reasons, extracts, **and** critiques itself |

`weak_soft` must **not** be labeled "independently verified" — it is better than the old path but still
probabilistic. Prefer the strongest available: symbolic/numeric evaluators for algebra; a generic graph
executor for graph problems expressible in a known family; for proofs/mechanisms call it `soft_critic`
plainly (not "answer-verified"). Optional per-step soft checks: monotonic progress, no step contradicts the
answer, optional critic (`verify_via_critic`, off by default).

---

## 8. The NON-VERIFIED illustrative track

For out-of-scope modes (and conceptual overrides), the worked-example slot is filled by the **normal
LLM-authored card path**, rendered by the visual system — **not** an adapter, **not** the ladder.

### 8.1 Contract
- **Provenance:** `verification_level: "none"`, `treatment: "illustrative"`. **No single-answer claim**;
  never presented as machine-verified.
- **Completeness is structural, not answer-based.** No answer to reach → "complete" = *covers the
  blueprint's required teaching points*, checked by the existing card-quality gate, **not** the (deleted)
  self-referential floor.
- **`verification_level: none` ≠ unchecked.** No single-answer machine proof, but conceptual cards can still
  state falsehoods ("DFS always finds the shortest path", "voltage is consumed by a component", "an index
  stores the full row"). So a **lightweight factual-integrity layer** still applies:
  - topic-definition consistency · contradiction detection · source-grounding when course material exists ·
    **no fabricated computed values** · no claims that conflict with provided canonical facts.
- **No fabricated rigor.** Must not invent numeric "results" it can't justify (the failure that made the
  Prim stub *look* computational). Conceptual content stays conceptual.
- **Visual:** handled entirely by the visual system for that mode (e.g. the ER compiler draws the ER
  diagram). The accuracy machinery is bypassed; the factual layer is not.

> The distinction is *"no machine proof of a single answer"*, **not** *"no quality or factual checking"*.

### 8.2 The out-of-scope set (from `visual_ontology_v2`)
- **`image_real_world_illustration`** — ALL modes (analogy/scene/physical_intuition/topic_motivation/
  system_metaphor). Pure illustration.
- **Structural/design** — `er_diagram`, `architecture_container`, `data_pipeline`.
- **Data-display** — `heatmap`, `confusion_matrix`, `scatter_plot`.
- **Pure comparison** — `comparison_table`, `sql_table`.
- **All support visuals** — `step_flow`, `practice_feedback`, `path_progress`, `source_annotation`,
  `topic_snapshot`.

### 8.3 What it is NOT
Not the Tier-2 backup (no answer to anchor), not a withhold (it ships), not subject to answer-derived step
floors or required-case coverage (there is no answer).

## 8b. Withheld → guided-explanation fallback (no blank gaps)

Withhold means "don't ship a *worked computation* we can't verify" — **not** "leave a hole." Especially in
Phase A (before Tier 1/2 coverage lands), many determinate topics would otherwise lose their example. The
product fallback:

- The lesson shows a compact **guided-explanation** card (labeled e.g. **"Key process"**, *not* "Worked
  Example") that walks the idea **without claiming a verified computed trace** — no fabricated numeric
  results, `verification_level: none`.
- The lesson **continues normally**; the learner never sees an error state.
- A **backlog event** is logged for the topic (this is the §10 adapter-priority signal).
- **Provenance** distinguishes it from illustrative and from a true blank:
  ```json
  { "treatment": "guided_fallback", "worked_example_status": "withheld",
    "verification_level": "none", "withhold_reason": "no_independent_answer_anchor" }
  ```
  Only if the guided card itself fails its quality/safety gate is the slot left empty (`treatment: withheld`,
  no card).

So the integrity rule holds (never present an unverified trace *as* a verified worked example) while the UX
stays whole. This is distinct from §8 illustrative (which is for topics that were *never* computational);
§8b is for computational topics we *chose to withhold*.

### 8b.1 `GuidedExplanationContract` — defined as tightly as Tier 1
A loose fallback would just relabel an unverified computation "Key process" while still inventing state
transitions — re-opening the hole. So the guided card has a hard output contract:
```python
class GuidedExplanationContract:
    forbidden = [
        "specific unverified state transitions",        # "next choose edge B–D (4)"
        "a claimed final numeric / computational answer",
        '"after step 4 ..." claims with no reference trace',
        "assertions that a particular branch is taken",
    ]
    allowed = [
        "general algorithm phases / structure",
        "invariant-style explanations",
        "the conditions that determine the next action",
        "abstract pseudocode-level explanation",
        "a request for learner prediction / reflection",
    ]
```
So Prim's guided card may say *"maintain a set of in-tree vertices; at each stage pick the lowest-weight edge
connecting the tree to a new vertex"* — but **not** *"next choose edge B–D with weight 4"* unless that
transition is independently verified. The contract is validated like §6.3 (no concrete unverified facts ship).

---

## 9. Variety — a diversity policy, not an absolute rule

The goal (no static canned examples) is right, but "always different values" is too brittle: some teaching-
instance spaces are small, and forcing difference can manufacture bad or artificially complex inputs. Use a
**diversity policy**:
- deterministic seed from the **unique topic id** (not the title, which collides);
- a candidate pool with bounded retries;
- avoid recently-used *equivalent* instances;
- require **distinct instances only when the family has adequate entropy**; where semantics force a small
  space, permit equivalent structure with **varied labels/values**;
- prose is always LLM-authored; no step text is stored or replayed.

**CI test the right thing:** assert the **instance differs** and the **seed/prompt differs** across two topic
ids — do **not** assert exact prose inequality (a model can independently produce similar wording; prose
variation is *encouraged*, not a correctness assertion).

---

## 10. Provenance & telemetry

Each example records `{ treatment ∈ {hard, soft, illustrative, guided_fallback, withheld}, verification_level,
adapter, adapter_version, instance_source ∈ {llm_proposed, seeded}, withhold_reason }`. The three "no worked
example" outcomes are **kept distinct**: *illustrative* (genuinely conceptual) · *guided_fallback*
(computational but unverifiable — the coverage gap) · *withheld-no-card* (even the fallback failed).
- **Tier-2 hit-rate by algorithm** = the prioritized adapter backlog (writing one promotes that algorithm to
  hard, no regression elsewhere).
- **Tier-1 → Tier-2 fall-throughs by category (§3.4).** `not_applicable` (a deliberate variant) is **normal**
  — tracked at INFO, not warned. Reserve WARNING/ERROR for *unexpected* categories (`reference_*`,
  `trace_disagrees_*`) — the actual regressions.
- **Illustrative spike on a *computational* subject** = the classifier mis-routed a determinate topic as
  non-verified (a routing bug — the mirror of the Tier-1 regression signal).
- **Withhold rate** (→ §8b guided-explanation) = topics needing an adapter or a better independent reference.
- **Kept OUT of the correctness success rate:** `highlighting_status: unavailable` (a `mapping_failure` is a
  UI/enhancement gap, §3.4) and Tier-2 `confidence` (tracked, but a `weak_soft` is not a correctness defect).
  Correctness telemetry counts only verified-vs-withheld on the trace, never enhancement state.

---

## 11. Integration with current code

| Current | Change |
|---|---|
| worked-example entrypoint (`solve_worked_example`) | front it with the §3.1 router |
| topic classifier | also emit the `WorkedExampleTask` contract per worked-example card via the **task-kind classifier (§3.5)** — layered (metadata→rule→LLM→fallback), reusing `course_type_classifier` + visual domain; booleans-from-evidence |
| determinate predicate | new pure fn over (**task contract** primary, visual mode + §15 tier corroborating) |
| Tier-1 failure handling | classify (§3.4); bug-class → withhold+alert, benign → Tier 2 / retry |
| illustrative cards | apply the §8.1 factual-integrity layer (not just the card-quality gate) |
| `route_adapter` coding guard | **replace** with the §3.3 applicability predicate |
| `solve_worked_example` self-graded coding path | demote to dead-code-behind-flag; truth flow = ladder |
| `expected_min_steps = sol["expected_steps"]` (`:1426`) | **delete**; floor from trace/reference (§5) |
| `CODING_STEP_RANGES` / `REQUIRED_CASES_BY_TOPIC` | no longer load-bearing; at most a Tier-2 hint |
| incomplete example ships with a status flag | **withhold** instead |
| out-of-scope modes run through answer-derived floors | route to non-verified; stop applying floors (kills false "incomplete" flags on conceptual cards) |
| `trace_contract.Step` | add `code_lines`, `code_anchor`; `TeachingTransition` (id + source_event_ids) |
| `TraceAdapter` (the §6.2 interface — **not** the old blurred `reference()`) | `teaching_trace_policy` (property) · `candidates` / `accept_instance` · **`run_reference`** (layer 1) · **`build_teaching_trace`** (layer 2) · **`required_transition_ids`** · `prose_fact_contract` · `canonical_code` / `step_code_lines` (Phase C2) |

Reuses unchanged: `ContractTrace`, `structural_invariants`, `validate_fidelity`, `validate_prose`, the
prose-only formatter + backend state-attach, `state_normalizers`, the 7 existing adapters, `reason_extract`,
`verifiers`.

---

## 12. Module layout
```
app/services/examples/
  task_classifier.py        # NEW: §3.5 — emits WorkedExampleTask (layered, booleans-from-evidence, confidence)
  accuracy_ladder.py        # NEW: the §3.1 router + determinate predicate + Tier 1->2->withhold/illustrative
  trace_adapters/           # + canonical_code, accept_instance, step_code_lines, completeness_contract
  trace_pipeline.py         # routing -> ladder; LLM-propose-instance hook; treatment provenance
  trace_contract.py         # Step += code_lines/code_anchor
  reason_extract.py / verifiers.py   # Tier-2 independent answer + soft critic (exist)
```

---

## 13. Rollout (all additive, behind the flag; off = unchanged)
**Phase A is split** (r3) so the highest-value fix ships without waiting on the riskiest subsystem (the
classifier, which can change the treatment of *every* slot):
- **Phase A1 — de-self-grade the safe cases only.** Delete the self-referential floor for **clearly-
  identified** topics — `coding_implementation` + a resolved algorithm slug, `algorithm_walkthrough` + a
  registered adapter, recognized formula-substitution. These need **no LLM classifier** to know they're
  computations. *Stops the Prim-class stub immediately,* with near-zero routing risk.
  **State exactly what replaces the deleted floor** (else an implementer might remove the weak floor and let
  the legacy solver ship unchecked): a recognized computation with **no Tier-1 adapter and no Tier-2
  endpoint source yet → `guided_fallback` + backlog event.** The binding invariant:
  > **No computational worked example reaches the learner through the old self-graded path once
  > `AZALEA_WORKED_EXAMPLE_ACCURACY_LADDER` is on.** The legacy self-graded path is a verification source for
  > *nothing* — it is replaced by (verified trace) ∨ (verified endpoint) ∨ (guided_fallback), never by
  > "ship it unchecked."
- **Phase A2 — task-contract routing for everything else, conservative defaults.** Add the §3.1 router + the
  §8 non-verified track (out-of-scope modes → `verification_level: none`, stop answer-derived floors) + the
  §8b guided-explanation fallback. Default ambiguous → Tier-2/withhold, unsupported → guided-explanation —
  **without** trusting the classifier for determinacy yet.
- **Phase A3 — enable classifier-driven determinacy** only after the §3.5.7 gold-set safety bar
  (false-illustrative **and** false-hard) is met.
- **Phase B — Tier 2.** Answer-anchored generic path + confidence levels (§7.1) + soft flag.
- **Phase C1 — Tier 1 core (no code anchoring).** Per the §15.5 capability audit, upgrade each adapter
  (`TeachingTracePolicy`, structured `ProseFactContract`, `accept_instance`), then: instance → reference
  trace → teaching trace → prose cards → completeness + prose-fact validation. **This delivers the core
  correction** independent of any line-mapping work — do **not** let highlighting block it. Kruskal first
  (§16).
- **Phase C2 — Tier 1 code anchoring.** Add canonical code + step→line map → exact highlighting, as an
  enhancement on top of C1. A `mapping_failure` here degrades to "verified trace, no highlight" (§3.4), never
  blocks C1's guarantee.
- **Phase D — retire** the legacy self-graded path.

**Build order — vertical slices around an explicit algorithm slug, NOT the generalized classifier first**
(the ladder stays flag-gated, activating only on explicit metadata/adapter match until Phase A3):
1. **binary search** — easiest technical slice: `run_reference → build_teaching_trace → prose-contradiction`.
2. **Kruskal** — strategically valuable (the original MST failure): proves accept *and* reject transitions,
   stateful component changes, completion, and graph visual state in one adapter.
3. **Prim** — frontier semantics + stale-candidate handling + pacing rules (`maximum_trace_transitions`).
4. **BFS / iterative DFS** — queue/stack conventions and traversal ordering.
5. **merge sort** — recursive structure + merge-level teaching transitions.

Then by §10 backlog hit-rate.

---

## 14. Open decisions
1. **Conceptual override granularity** — per-topic vs per-card. Recommend **per-card** (only the
   worked-example card needs the predicate).
2. **Canonical vs varied code** on coding topics — recommend **canonical** (exact highlighting; values/
   steps/prose still vary). Varied code → semantic-anchor highlighting (`code_anchor`), deferred.
3. **Instance source default** — **seeded adapter candidate pool by default**; LLM-proposed instances
   optional when contextual flavor matters (§4.1). Record `instance_source`. *(Resolved r3: seeded-default,
   not LLM-first — instance validity must never depend on LLM retries.)*
4. **Soft critic** on Tier 2 / illustrative — default **off** (cost; weak signal).
5. **Comparison vs decision/truth tables** — same base type, different verifiability (`decision_table`/
   `truth_table` = Tier 1; `comparison_table` = non-verified). Ensure the classifier separates them.
6. **Gold-set curation (§3.5.7)** — who labels it, how big, refresh cadence. It's the bar Phase A's
   determinacy trust gates on; recommend seeding from real generated topics across subjects, weighted toward
   computational ones (where false-illustrative is dangerous).

---

## 15. Adapter coverage — driven by the full visual ontology

**Source of truth:** `app/core/visual_ontology_v2.py` — **12 base visual types × ~105 modes** (+ 5 support
visuals). NOT `visual_v2/profiles.py` (only the render-wired slice). The ontology is keyed by **visual
structure, not subject** — so "science" is not a separate type: a circuit is `node_link_diagram/circuit`,
stoichiometry is `formula_symbolic_expression/substitution`, a titration curve is
`coordinate_graph/function_curve`. Science/engineering is **covered, distributed across structural modes.**

### 15.1 Tiering rule (by computability, not subject)
- **Tier 1 (HARD)** — the example is a computation/execution with a single correct trace.
- **Tier 2 (SOFT)** — endpoint verifiable, path open (symbolic algebra with many routes, qualitative
  protocols, some proofs).
- **Out (non-verified, §8)** — illustration, structural, data-display, pure comparison, support visuals.

### 15.2 Coverage by base type
| Base type | Tier-1 (hard) modes — computations to hardcode | Tier 2 / out |
|---|---|---|
| `node_link_diagram` | graph_network (BFS/DFS/Dijkstra/Kruskal/**Prim**/Bellman-Ford/SCC/bipartite), tree_hierarchy (BST/heap), linked_list_chain, recursion_tree, state_machine, automata, dependency_graph (topo), resource_graph (deadlock), **circuit** (Ohm/Kirchhoff/logic-gate) | er_diagram, architecture_container, data_pipeline → out |
| `indexed_sequence_diagram` | array_state, string_state, binary_search_range, sliding_window, two_pointer, sorting_pass, merge_partition, token_sequence, prefix_sum | — |
| `grid_matrix_diagram` | matrix (lin-alg), dp_table, adjacency_matrix, grid_traversal (path/flood-fill), karnaugh_map, cell_dependency | heatmap, confusion_matrix → out |
| `memory_layout_diagram` | stack_heap, call_stack, pointer_reference, object_layout, array_memory, virtual_memory, page_table, cache_lines, buffer_layout | — |
| `code_execution_panel` | ALL (walkthrough_growing, execution_trace, debug_trace, recursive_execution, loop_trace, condition_evaluation, input_output_trace) via a real executor | — |
| `formula_symbolic_expression` | substitution, calculus_derivation, recurrence_expansion, big_o_expression, boolean_expression, matrix_formula, loss_function | algebraic_transformation (multi-path) → 2 |
| `coordinate_graph` | function_curve, area_under_curve, tangent_secant, runtime_growth, regression_plot, vector_field, phase_portrait, distribution_curve, roc_curve | scatter_plot → out |
| `geometric_diagram` | triangle/circle/vector/projection/3d_solid/integration_region/related_rates/linear_algebra/optimization | — |
| `table_diagram` | truth_table, variable_trace_table, distance_table, symbol_table, routing_table, page_table, decision_table | comparison_table, sql_table → out |
| `set_region_diagram` | venn/union/intersection/complement, sample_space, probability_region, logic_region, classification_overlap | — |
| `timeline_sequence_interaction` | thread_schedule, lock_acquisition, race_condition, transaction_timeline | protocol_sequence, request_response, oauth_flow, message_passing → 2 |
| `image_real_world_illustration` | — | ALL → **out (illustration)** |

### 15.3 The planning unit is the algorithm/operation *family*, not the mode cell
A visual mode is **not** an algorithmic-semantics contract: `graph_network` alone spans BFS, DFS, Dijkstra,
Prim, Kruskal, Bellman-Ford, topological sort, SCC, max-flow, bipartite — each a *different* contract;
`matrix` spans Gaussian elimination, multiplication, determinants, eigenvectors, DP, adjacency ops. So the
ontology bounds the *universe* and supplies shared rendering, but **plan and prioritize by family**:

> search-and-bound · graph-traversal · shortest-path · minimum-spanning-tree · sort · heap-operation ·
> linked-list-operation · linear-system · symbolic-substitution · matrix-transformation · …

Within a family, **share** state normalizers, trace-event vocabulary, instance generators, and visual
mappers; each distinct algorithm still needs its own semantics contract. The §15.2 table is therefore the
*render* map; the **backlog is measured in high-use algorithm contracts**, and is larger than "one per mode"
(the earlier "~70–80 mode×computation" framing understates it — many modes host many contracts).

**Highest-leverage gaps:** `memory_layout` (linked lists / heaps / BST / recursion), `dp_table`, and the
`formula`/`geometric` science+math families. Existing 7 cover search-and-bound (binary search), graph
families (BFS/DFS/Dijkstra/Kruskal), symbolic-substitution (arithmetic), and sort (merge).

### 15.4 The code executor is a *state* source, not a *completeness* contract
A generic executor gives trustworthy **runtime events** (variable state, control flow, output) for arbitrary
code — but it does **not** by itself decide *which* events are pedagogically required, what a complete
teaching trace is, or which branches matter for the concept. So:

> A code executor unlocks generic runtime-trace capture for many coding topics. It becomes **hard-tier
> teaching verification only when paired with a validated completeness contract** (§5) — either owned per
> family, or generated and unit-tested.

It is a powerful Tier-1 *foundation* (step-level factual state for free), not an instant "every coding topic
solved." The `execution trace` (facts) and the `teaching-complete trace` (pedagogy, §5) stay distinct.

### 15.5 Existing adapters are NOT assumed Tier-1-ready — audit by capability
The 7 existing adapters (binary_search, bfs, dfs_iter, kruskal, merge_sort, arithmetic_eval, dijkstra) were
built for the *conceptual* trace pipeline. They are **not** automatically Tier-1-ready; each is scored on the
v4 capabilities before the rollout counts it as reuse:

| Capability | from `WORKED_EXAMPLE_REASONING_SPEC` | new in v4 |
|---|---|---|
| reference execution · teaching-instance selection · state normalizer · terminal validation · raw-state per step | ✅ mostly present | — |
| **`TeachingTracePolicy`** (raw→teaching, §5.1.1) | ✗ (trace ≈ raw today) | **upgrade** |
| **structured `ProseFactContract`** (§6.3) | partial (`Step.facts` strings) | **upgrade** |
| **`accept_instance`** hybrid-source hook (§4.1) | partial (`candidates`/`is_teaching_trace`) | **upgrade** |
| **`canonical_code` + `step_code_lines`** (C2) | ✗ | **add** |

Illustrative readiness (fill in per adapter before Phase C1):
| Adapter | Reference run | Teaching trace | Prose contract | Code map | Tier-1 readiness |
|---|---|---|---|---|---|
| binary_search | yes | partial | strings→struct | none | upgrade needed |
| bfs / dfs | yes | partial | strings→struct | none | upgrade needed |
| kruskal | yes | partial | strings→struct | none | upgrade needed |

Rollout plans by **measured capability**, not by adapter existence — "it exists" ≠ "it's Tier-1 ready."

---

## 16. Worked example — Kruskal coding, end-to-end (Tier 1)

1. **Topic** "Implementing Kruskal's Algorithm" (`coding_implementation`). Determinate (graph_network, tier
   1) + applicable → **Tier 1**.
2. **Instance — seeded by default.** The adapter draws a 6-node weighted graph from its candidate pool whose
   `instance_acceptance_rules` hold (connected, non-trivial MST, a genuine cycle-skip, within
   `maximum_trace_transitions`). *Optional:* if lesson flavor matters, the LLM proposes one and
   `accept_instance` validates it; on reject, fall back to seeded. (LLM may relabel nodes within bounds.)
3. **Referee (adapter)** confirms the instance is a teaching instance per the policy.
4. **Execute** `reference(inst)` runs real Kruskal → `ContractTrace`: edges in non-decreasing weight order,
   each accept/skip with union-find state, `required_cases = {accept, cycle_skip, completion}`,
   `final_answer = {mst_edges, total_weight}`; each `Step` gets `code_lines` into the canonical code.
5. **Verify** `structural_invariants == []` (V−1 accepts, every skip a real cycle, weights sorted).
6. **Narrate (LLM)** fresh prose; backend attaches `prior_state`/`result_state`; Stage-4b rejects any prose
   that misstates a weight or edge.
7. **Attach code + highlight:** worked example and code walkthrough show the same canonical code; each step
   highlights its `code_lines`.
8. **Ship** `{treatment:"hard", tier:1, verification_level:"hard_trace", adapter:"kruskal",
   instance_source:"seeded"}`.

Next study path, same topic, different id → **different graph, different numbers, freshly-written steps**,
same hard guarantee. The adapter stored none of it.

---

## 17. Design invariants (do not regress)

1. **Route by task contract, not visual mode.** Visual mode corroborates; `WorkedExampleTask` decides (§3.2).
   The contract separates `has_executable_terminal_condition` (Tier-1 eligibility) from
   `has_independently_checkable_endpoint` (Tier-2 eligibility) — a proof has the latter without the former.
2. **`raw log → teaching trace → cards` are explicit interfaces**, not a blurred `reference()`:
   `run_reference` → `build_teaching_trace` → cards, with **stable transition IDs** so completeness is an
   exact set check (§6.2). Completeness is over the adapter's *required teaching transitions*, never the raw
   log — representative, not exhaustive. `TeachingTracePolicy` (a first-class adapter property) also owns
   **instance acceptance + a pacing cap**: length is solved at Stage 0, not by compression (§5.1.1).
3. **Classified Tier-1 failure.** Bug-class failures (reference crash/invariant/trace-mismatch) **withhold +
   alert**; only benign failures degrade to Tier 2 (§3.4).
4. **Graded Tier-2 confidence.** strong/moderate/weak soft, recorded; `weak_soft` is never called
   "independently verified" (§7.1).
5. **Plan by algorithm family, not ontology cell;** the executor is a state source, not a completeness
   contract (§15.3–15.4).
6. **Precise per-dimension guarantees.** Tier 1 = `hard_trace` + `adapter_fact_checked` prose — where the
   prose check is a **bounded compliance checker** (hard: no out-of-set values/entities/prohibited claims/
   wrong decisions; soft: required facts expressed) — *not* a proof of NL entailment (§6.3). Tier 2 = **final
   answer only**, with `verified/unverified_dimensions` recorded (§3, §7).
7. **`required_transitions` is a declared, testable `TeachingTracePolicy`** — never ad-hoc prose (§5.1.1).
8. **Classification uncertainty biases toward verification.** The task-kind classifier (§3.5) is the routing
   keystone: **booleans-from-evidence are primary, `task_kind` is descriptive**; **confidence is computed
   from evidence, not the model's self-report**; three states — `resolved` / `ambiguous` / **`unsupported`**
   (the "don't know" state → guided-explanation, never illustrative). Tuned to the **asymmetric safety
   objective**, gated on **two** gold-set metrics: *false-illustrative* AND *false-hard* (§3.2.1, §3.5.5–7).
9. **Hybrid instance source** — adapter seeded pool is the default truth; LLM proposal optional; instance
   *validity* never depends on LLM retries (§4.1).
10. **No blank gaps, no relabeled fakes.** A withheld computation → `guided_fallback` (a first-class
    treatment, distinct from illustrative and from withheld-no-card) bound by the strict
    **`GuidedExplanationContract`** (no specific unverified transitions, no claimed answer) (§8b.1).
    **`mapping_failure` is a capability state, not a correctness failure** (§3.4).
11. **Ship the safe fix first, and the legacy path verifies nothing.** Phase A is split A1/A2/A3; A1's
    binding invariant: once the flag is on, **no computational worked example reaches the learner through the
    old self-graded path** — it's replaced by verified-trace ∨ verified-endpoint ∨ guided_fallback (§13).

**Preserved from v2/v3 unchanged:** answer-anchored never self-graded · adapter = referee not author · fresh
instances + prose, no *canned learner* text (internal fixtures OK, §4) · withhold-but-don't-fake · illustra-
tive separated from soft fallback · provenance/telemetry per treatment · model-owned step counts removed as
a correctness source · Tier-1 reference trace as the source of required cases.
