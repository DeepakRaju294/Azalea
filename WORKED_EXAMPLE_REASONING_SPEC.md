# Worked-Example Trace Pipeline Spec — v8 (Select → Produce → Verify → Format → Validate)

**Status:** **v8 — review-refined.** (v7 + review pass: Phase-1 `validate_visual_state` flag, structured
fact bundles with hard/missing/soft classes, accurate guarantee wording, fail-source-split retry,
adversarial-prose tests.) **Phase 1 is IMPLEMENTED** (7 deterministic adapters + trace_pipeline, flag-gated);
these refinements are the next implementation pass + the Tier-1 engine for `WORKED_EXAMPLE_ACCURACY_SPEC.md`.
**Scope:** WORKED EXAMPLES ONLY (including their visuals). Not code walkthroughs, lesson bodies, or topic
decomposition. *Visuals are in scope, but Phase 1 carries trace-compatible visual **metadata** only;
visual-fidelity **enforcement** begins in Phase 1.5.*
**Disposition:** **Additive and flag-gated** (`AZALEA_WORKED_EXAMPLE_TRACE_PIPELINE`, default **off**).
Ships alongside the existing systems; deletes/overwrites nothing; off = byte-for-byte unchanged.

**Core shape:** an **authoritative canonical trace** is produced and verified *before* any learner-facing
output; cards and visuals are *derived views* of it. This separates **truth** from **teaching
presentation** and fixes the actual bug class — wrong intermediate values/states while formatting,
coverage, and pacing look fine.

**v5 changes from v4 (review round 5 — final additions before coding):**
0. **Stage 0 — teaching-instance selection** (a perfect executor can't rescue a weak input).
1. **Structured `visual_state` / `visual_delta` derived from the trace** (visual fidelity, not just state).
2. **Two-level adapters:** shared **state normalizers** + algorithm-specific **trace adapters**.
3. **Structured `FidelityResult` / `VerifyResult`** errors, not booleans.
4. **Trace-level required-case evidence** (case → canonical step ids).
5. Three adapter methods: `validate_conventions`, `validate_step_shape`, `to_visual_state`.
6. **Hard guarantee is relative to declared semantics + a *validated* implementation** — and Phase 1
   uses **adapter-owned reference implementations** for the core algorithms (model-written
   `executed_reference` gives a softer "fidelity to declared variant" and is for breadth).

**v6 changes from v5 (review round 6 — final before build):**
- **The formatter writes PROSE ONLY** (`title/goal/reasoning/work/result/teaching_note`); **backend code
  attaches** the truth-bearing fields (`trace_step_ids/prior_state/result_state/visual_state/
  visual_delta`) deterministically after formatting. The model is never responsible for copying state →
  it *cannot* drift it. Stage 4 fidelity becomes a guard, not the primary defense (§11/§12/§13).
- **`ContractTrace.provenance`** block (source, adapter+version, reference_version, verification_level,
  instance_selection_attempt) for A/B + debugging (§5).
- **Debug artifact retention** (internal-only): input, conventions, trace, reference event log, formatter
  raw response, normalized cards, FidelityResult/VerifyResult (§17).
- **Scope/visual clarified:** scope *includes* visuals, but **Phase 1 carries trace-compatible visual
  metadata only; visual-fidelity ENFORCEMENT lands in Phase 1.5** (§Scope/§17).
- **Adapter build order:** binary search → BFS → DFS → Kruskal → merge sort (binary search is the first
  vertical slice) (§17).

**v7 changes from v6 (final review — freeze after these):**
- **Stage 4b — PROSE FIDELITY (new, the last gap).** Backend-attached state is correct, but the
  formatter's *learner-facing prose* (`work`/`reasoning`/`result`) can still state a wrong value. Each
  step carries a **fact bundle** (`allowed_values`/`required_facts`/`forbidden_claims`); Stage 4b checks
  the prose against it and retries/withholds on contradiction. Machine-state fidelity ≠ prose fidelity
  (§5/§11/§12b).
- **Visual split:** Phase 1.5 = *visual-source* fidelity (render directly from `visual_state`); Phase 1.6
  = *rendered-image* fidelity (only if visuals are generated). Core algorithms render structurally from
  `visual_state`, never via an image model recreating them (§17).
- **Reproducible Stage 0:** candidate selection deterministic for `topic + adapter_version + seed`; store
  `candidate_seed`/`candidate_id`/`selection_attempt` in provenance (§5/§8).
- **Explicit (non-fuzzy) routing:** Phase 1 routes only on explicit slug/metadata match for the five
  supported algorithms (tight title aliases, no fuzzy keywords); anything else → `None` → existing path
  (§16).
- **Tightened guarantee wording** (§2).

---

# Part I — Concept

## 1. The bug class this fixes

The old solver asks one model call to invent the instance, solve it, declare the answer, pick required
cases, estimate steps, write every transition, every state, every card, every visual, and certify the
endpoint. There is **no stable computational artifact upstream of the learner-facing output**, so values
and states drift while formatting/coverage/pacing stay good, and a correct endpoint hides wrong
intermediates (merge sort sorts after a wrong merge; binary search finds the target after an illegal
bound update).

The right shape is `authoritative trace → learner-facing explanation`, not
`learner-facing explanation → assumed truth`.

## 2. Core principle & guarantee

> **Produce a canonical, machine-checkable trace BEFORE formatting. Verify it. Then make every card and
> visual a rendering of that trace.** The formatter **cannot alter the authoritative state attached by the
> backend** (it never emits state); its **prose is constrained by trace facts and rejected when it
> contradicts the supported fact checks** (§12b). (It is *not* claimed that the prose is perfectly proven —
> it can still paraphrase or omit; the guard blocks *contradictions*, §12b.)

Guarantee: **every transition is legal from its prior state, and every card (and visual) renders a
verified transition** — *hard* where an executor exists (relative to declared semantics + a validated
implementation), *soft* (invariants + critic) otherwise.

Phase-1 guarantee, stated precisely: *for supported deterministic adapters, the pipeline guarantees the
attached trace state, card ordering, required-case evidence, and final answer faithfully reflect a
validated reference implementation under declared conventions — and the learner-facing prose is
separately checked for trace contradictions (§12b).* Two distinct fidelities: **machine-state fidelity**
(backend-attached, §12) and **prose fidelity** (what the learner reads, §12b).

## 3. The five stages

```
0. SELECT INSTANCE  choose/validate a fixed example_input that produces a teaching-quality trace
                    (right length, required cases exercised, not gratuitously complex). Programmatic for
                    deterministic families. Reject + regenerate BEFORE anything else.
1. PRODUCE TRACE    ContractTrace for that instance. Deterministic → EXECUTOR (primary); else →
                    reason(prose) → extract(trace).
2. VERIFY TRACE     deterministic → execution replay vs declared semantics (HARD); arithmetic → eval;
                    proof/open-ended → scoped invariants + independent critic (SOFT). Fail → feed back the
                    FIRST illegal transition + retry, else WITHHOLD.
3. FORMAT CARDS     render fields + structured visual from verified steps. ONE step = ONE card (v1). Cards
                    cite step ids; may rephrase; may NOT add/drop/reorder/alter any value.
4. VALIDATE FIDELITY deterministic: every card's prior/result state EQUIVALENT (per adapter) to the cited
                    step; chain complete; required-case evidence rendered. `visual_state` is checked ONLY
                    when `validate_visual_state=True` (Phase 1.5+); Phase 1 carries it as metadata.
```

Correctness lives in 0–2. Stage 3 is mechanical rendering. Stage 4 catches drift (text + visual).

## 4. Honest boundaries (binding)

- **Don't re-suppress reasoning** — non-executor classes reason in prose first, then extract.
- **Hard guarantee ≠ "the code ran."** It is **trace fidelity to the chosen, declared algorithm
  semantics, via a validated implementation.** An executor can faithfully run the *wrong variant*
  (visited-on-push vs visited-on-pop). So Phase 1's hard path uses **adapter-owned reference
  implementations** with known conventions; model-written `executed_reference` is for breadth and yields
  a *softer* "fidelity to the model's declared variant" — surface that difference in telemetry.
- **Soft classes are probabilistic** (invariants + critic); never label them "verified" like a hard trace.
- **Unifies with execution/reference, not replaces** — absorbs `trace_first`/`reference_first`/
  `executed_reference` as deterministic trace sources under one pipeline.
- **Bounded per-family code:** shared state normalizers + a small algorithm adapter per algorithm. Not
  zero, not bespoke-per-lesson.
- **Heavier than the original "light" idea — accepted, de-risked by staging** (§17).

---

# Part II — The canonical trace (the contract)

## 5. `ContractTrace` schema

```json
{
  "problem": "Run iterative DFS from A on the graph …",
  "conventions": {                          // REQUIRED (deterministic); trace is truth FOR these
    "algorithm_variant": "iterative_dfs", "neighbor_order": "alphabetical",
    "push_order": "reverse_alphabetical", "visited_when": "on_pop",
    "duplicate_stack_entries": "not_allowed", "trace_granularity": "pop_and_push_sequence"
  },
  "initial_state": { "stack": ["A"], "visited": [] },
  "final_answer": { "visit_order": ["A","B","C","D"] },
  "invariants": [
    { "id": "visited_subset", "scope": "every_step", "statement": "visited ⊆ nodes" },
    { "id": "all_reachable",  "scope": "final_only", "statement": "every reachable node is visited" }
  ],
  "required_cases": ["revisit_prevention", "branch_ordering", "final_completion"],
  "case_evidence": { "branch_ordering": ["s1"], "revisit_prevention": ["s3"], "final_completion": ["s4"] },
  "provenance": { "source": "adapter_reference", "adapter": "dfs_iter", "adapter_version": 1,
                  "reference_version": "2026-06-26", "verification_level": "hard",
                  "candidate_seed": 18472, "candidate_id": "dfs_iter_v1_case_14",
                  "selection_attempt": 3 },          // deterministic for topic+adapter_version+seed
  "steps": [
    { "id": "s1", "operation": "pop_visit_push", "inputs": { "node": "A" },
      "prior_state": { "stack": ["A"], "visited": [] },
      "decision": "visit A; push unvisited neighbours (reverse-alphabetical)", "reason": "…",
      "state_after": { "stack": ["C","B"], "visited": ["A"] },
      "visual_state": { "kind": "stack_graph", "stack": ["C","B"], "stack_top": "right",
                        "visited": ["A"], "active_node": "A" },
      "visual_delta": { "popped": "A", "pushed": ["C","B"], "visited_added": ["A"] },
      "expected_visible_result": "Visit A; stack [C, B]; visited {A}",
      "facts": {                                     // formatter-facing; drives §12b prose fidelity
        "allowed_values": ["A","B","C","D"],
        "required_facts": ["pop A", "visit A", "push C", "push B"],
        "forbidden_claims": ["visit B", "pop C", "A already visited"] } }
  ],
  "solution_text": "<supplementary prose; never the source of values>"
}
```

**Structural invariants (checked pre-Stage-2, adapter-driven, no per-family logic):**
- `states_equivalent(steps[0].prior_state, initial_state)`
- `states_equivalent(steps[i].prior_state, steps[i-1].state_after)` — gap-free chain
- `final_answer_entails(steps[-1].state_after, final_answer)`
- `every_step` invariants hold at every `state_after`; `final_only` at the last only
- each `required_cases` entry has non-empty `case_evidence` step ids

## 6. Topic classes → source + verifier

| Class | Trace source | Verifier | Guarantee |
|---|---|---|---|
| Deterministic algo / DS | **adapter-owned reference** (Phase 1) or `executed_reference` (breadth) | execution replay vs declared semantics + `property_checks` | **Hard** (ref) / **near-hard** (model variant) |
| Arithmetic / formula | reason → extract | numeric / symbolic eval | Hard where evaluable |
| Proof / mechanism | reason → extract | scoped invariants + critic | Soft |
| Open-ended application | reason → extract | invariants + critic + fidelity | Soft |

## 7. Trace granularity — one transition per algorithm (in the algorithm adapter)

| Family | One canonical transition |
|---|---|
| Binary search | one iteration: midpoint → compare → update bounds |
| Merge sort | split / base case / one merge selection / tail copy / return-to-parent |
| BFS | dequeue node + enqueue unvisited neighbours (fixed order) |
| DFS (iterative) | pop+visit one node + its deterministic push sequence |
| Kruskal | consider one edge → accept/reject |
| Linked-list insert | locate / connect predecessor·new·successor (mutation units) |
| Formula / algebra | one equivalence-preserving transformation |
| Proof | one justified inference |

---

# Part III — The five stages (detailed)

## 8. Stage 0 — Select teaching instance (NEW)

A perfect executor can't rescue a weak input: a target found on the first midpoint → one useless card; a
path-shaped graph → no DFS branching/revisit; an all-accept Kruskal graph → no cycle rejection; a tiny
nearly-sorted array → no meaningful merges. For deterministic families this is **programmatic**:
```python
def select_instance(topic, adapter, required_cases):
    for candidate in bounded_candidates(topic, adapter):       # reuse/extend generate_example_input
        trace = run_reference(candidate, adapter)              # the same executor Stage 1 will use
        if adapter.is_teaching_trace(trace, required_cases):   # length in family range + cases hit + not over-complex
            return candidate, trace
    return None                                                # -> caller falls through to existing systems
```
This replaces the current "ask the model to invent an instance with enough steps/cases," which is another
chance to fabricate rather than derive. The reference trace from Stage 0 is reused by Stage 1.
**Reproducibility:** candidate generation is **deterministic for `topic + adapter_version + seed`**; the
chosen `candidate_seed`/`candidate_id`/`selection_attempt` are recorded in `provenance` so any A/B failure
or weak lesson can be regenerated locally byte-for-byte.

## 9. Stage 1 — Produce the trace

**Deterministic:** the Stage-0 reference run *is* the trace; lift recorded states into `ContractTrace.steps`
at the adapter's granularity, attach `visual_state`/`visual_delta` via `adapter.to_visual_state`. No model
narration is trusted for values.

**Non-deterministic (reason → extract):** 1a reason in free prose (solve fully, self-check); 1b extract to
`ContractTrace` under the **derivability rule** (every value derivable from input / conventions / prior
state / an explicit operation — need not appear literally in prose). Critic confirms consistency in Stage 2.

## 10. Stage 2 — Verify

- **Deterministic:** assert the implementation matches the declared conventions (`validate_conventions`),
  re-assert structural invariants + `property_checks`. Hard *for those semantics*.
- **Arithmetic:** evaluate each operation → assert `state_after`.
- **Proof / open-ended:** scoped invariants + independent critic → first illegal step id + reason.

`VerifyResult{ ok, illegal_step{id, reason}, ... }`. Fail → §13 retry with the specific transition; else WITHHOLD.

## 11. Stage 3 — Format cards (one step = one card, v1)

**The formatter writes PROSE ONLY** — `title`, `goal`, `reasoning`, `work`, `result`, `teaching_note` —
one card per verified step, in order. It is given the step's values to *describe* but is **not asked to
emit any machine state**. The model therefore cannot drift the **machine state** (it never produces it) —
but its **learner-facing prose can still misstate a value**, so it's checked in Stage 4b (§12b).
```
SYSTEM: For each verified step, write ONE learner-facing card (title/goal/reasoning/work/result). Use ONLY
the step's facts: state exactly the required_facts, use only allowed_values, and never make a
forbidden_claim. Describe accurately; do not invent or alter values. Return ONLY JSON:
{"cards":[{"title","goal","reasoning","work":[...],"result"}, …]}   (NO state fields)
USER: <ordered verified steps: operation, prior_state, state_after, expected_visible_result, facts{…}>
```
**Backend then attaches the truth-bearing fields deterministically** (not the model):
```python
for card, step in zip(cards, trace.steps):     # one-to-one in v1
    card["trace_step_ids"] = [step.id]
    card["prior_state"]    = step.prior_state
    card["result_state"]   = step.state_after
    card["visual_state"]   = step.visual_state      # Phase 1: carried as metadata; enforced in 1.5
    card["visual_delta"]   = step.visual_delta
```
Setup card derives from `problem`/`initial_state`. Output normalizes to the existing card shape (renderer
unchanged; the prose `result` is learner-facing, `result_state` is backend truth). *Later (not v1):*
splitting only if the trace declares real `substeps`.

## 12. Stage 4 — Validate fidelity (text + visual + cases)

Since the formatter no longer emits state (§11), the per-card `prior_state`/`result_state` checks are now a
cheap **guard** against backend-attach bugs; the substantive checks are **chain completeness, endpoint, and
required-case evidence** — plus a soft check that the prose `result` doesn't numerically contradict
`result_state`. Deterministic, adapter-driven, **structured errors**:
```python
def validate_fidelity(cards, trace, adapter, *, validate_visual_state=False):   # Phase 1: False; Phase 1.5: True
    for i, card in enumerate(cards):
        steps = [trace.by_id(s) for s in card.trace_step_ids]              # v1: exactly one, contiguous
        if not states_equivalent(card.prior_state,  steps[0].prior_state):  return Fidelity("prior_mismatch", i, steps[0].id, …)
        if not states_equivalent(card.result_state, steps[-1].state_after): return Fidelity("result_mismatch", i, steps[-1].id, …)
        if validate_visual_state and not states_equivalent(card.visual_state, steps[-1].visual_state):
            return Fidelity("visual_mismatch", i, steps[-1].id, …)         # ENFORCED only in Phase 1.5+
    # chain + endpoint + required cases:
    assert chain_links(cards); final_answer_entails(cards[-1].result_state, trace.final_answer)
    for case, ids in trace.case_evidence.items():
        assert all(any(sid in c.trace_step_ids for c in cards) for sid in ids)
```
> Phase 1 MUST call with `validate_visual_state=False` — enforcing `visual_state` before the renderer
> consumes it (Phase 1.5) would create spurious Phase-1 failures on a field that is only carried as metadata.
```python
FidelityResult(ok, code, card_index, trace_step_id, expected_state, observed_state)   # not a bool
```
Plus `worked_example_correctness_violations` as a backstop. Any failure → §13.

## 12b. Stage 4b — Prose fidelity (the last gap)

Backend-attached state is correct, but the learner reads the formatter's **prose** (`work`/`reasoning`/
`result`), which can still state a wrong value — e.g. attached `result_state` says `mid=5` while the prose
says "mid = 4, arr[4]=12". `machine-state fidelity ≠ prose fidelity`. Not a full NL prover — a **bounded,
fact-bundle guard** per supported deterministic adapter.

**Facts are structured (predicate objects), not bare strings** — even though the formatter receives readable
text. This lets the guard classify the violation rather than do brittle substring matching:
```python
{"predicate":"action",       "verb":"pop", "entity":"A",                    "text":"Pop A"}
{"predicate":"state_change", "field":"low", "from":0, "to":6,               "text":"Move low from 0 to 6"}
{"predicate":"decision",     "operation":"consider_edge", "edge":["B","C",4],"decision":"reject", "text":"Reject edge (B,C,4)"}
```
Stage 4b sorts each finding into three classes, and **only the first blocks in Phase 1**:
```python
def validate_prose(card, step) -> list[ProseViolation]:
    hard, missing, soft = [], [], []
    # HARD contradiction (BLOCKS) — prose asserts something the trace says is false:
    for n in numbers_in(card):                                  hard += [Prose("value_not_allowed", n)] if n not in step.facts.allowed_values else []
    hard += [Prose("state_change_contradiction", f) for f in step.facts.state_changes if prose_states_other(card, f)]
    hard += [Prose("decision_contradiction", d)     for d in step.facts.decisions     if prose_states_other(card, d)]
    hard += [Prose("forbidden_claim", c)            for c in step.facts.prohibited     if prose_asserts(card, c)]
    # MISSING required fact (advisory in Phase 1) · SOFT wording (advisory):
    missing += [Prose("missing_required_fact", f) for f in step.facts.required if not prose_states(card, f)]
    return hard, missing, soft
```
- **Hard contradiction** (blocks): "low becomes 5" when the trace says 6; "accept" when the trace rejected;
  a number outside `allowed_values`; "visited X" when the trace doesn't show it.
- **Missing required fact** (advisory in Phase 1): the prose never states the comparison that drove a bound
  update. *Do not withhold an otherwise-correct lesson for this in Phase 1.*
- **Soft wording** (advisory): technically correct but vague.

Adapter-specific deepening later: `adapter.validate_prose_claims(card, step)`. **On a HARD violation → re-run
the formatter** (violated facts highlighted) up to the budget; persistent → **withhold**. Missing/soft are
logged, not blocking, in Phase 1. Pass A (reasoning) is untouched.

## 13. Orchestration

```python
inst = select_instance(topic, adapter, required_cases)          # Stage 0
if inst is None: return None                                    # falls through to existing systems
candidate, ref_trace = inst
trace = produce_trace(candidate, ref_trace, adapter, ...)       # Stage 1 + structural gate
v = verify_trace(trace, adapter, topic_class, ...)              # Stage 2
if v.illegal_step:
    trace = produce_trace(..., feedback=v.illegal_step) or trace
    if verify_trace(trace, ...).illegal_step: return None       # WITHHOLD
for _ in range(_MAX_FORMAT_ATTEMPTS):                           # Stage 3 + 4 + 4b
    cards = attach_state(normalize_cards(format_cards(trace)), trace)   # backend attaches state (§11)
    fid = validate_fidelity(cards, trace, adapter, validate_visual_state=False)   # Stage 4 (machine state)
    if not fid.ok:
        log_system_defect(fid); return None                    # BACKEND/TRACE bug — prose retry can't fix it; WITHHOLD now
    hard, missing, soft = validate_prose_all(cards, trace, adapter)     # Stage 4b
    log(missing, soft)                                          # advisory in Phase 1 — not blocking
    if not hard:
        return WorkedExampleResult(trace.problem, cards, trace.final_answer)
    last_feedback = hard                                        # FORMATTER bug — retry with violated facts highlighted
return None                                                     # WITHHOLD — never ship a contradicting example
```
**Distinguish the failure source.** A fidelity failure means a *backend/trace defect* (state-attach
mismatch, broken chain, missing required-case evidence, wrong final entailment) — re-running the *formatter*
cannot fix it, so **withhold immediately and log a system defect** rather than burning format retries. Only a
*hard prose* contradiction is fixable by re-formatting; missing/soft prose is advisory in Phase 1. Targeted
feedback (the exact illegal transition / mismatched card+step / violated fact) is the key reliability + A/B
lever.

---

# Part IV — Implementation

## 14. Module layout
```
app/services/examples/trace_pipeline.py    NEW — stages 0–4 orchestration + _trace_pipeline_enabled()
app/services/examples/trace_contract.py    NEW — ContractTrace/Step + structural gate + fidelity replay
                                                 + FidelityResult/VerifyResult (pure, adapter-driven)
app/services/examples/state_normalizers/   NEW — SHARED data canonicalizers (no algorithm logic)
    graph_state.py  array_state.py  tree_state.py  disjoint_set_state.py  heap_state.py
app/services/examples/trace_adapters/      NEW — ALGORITHM adapters (conventions, granularity, required
    bfs.py  dfs_iter.py  kruskal.py  binary_search.py  merge_sort.py        cases, final-answer semantics,
                                                                            to_visual_state; use a normalizer)
app/services/examples/trace_sources/       NEW — reference_owned.py (Phase 1) / executed_reference.py
                                                 (breadth) / reason_extract.py / arithmetic.py
app/services/examples/verifiers/           NEW — deterministic.py / arithmetic.py / critic.py
app/services/examples/solver.py            ONE added branch at the solve hook (§16). No other edits.
app/tests/test_trace_pipeline.py           NEW — offline tests (stub model fns + fake reference + fake adapter)
```
Reused unchanged: `executor`/`trace_first.build_cards_from_trace`, `reference_first`/`executed_reference`,
`property_checks`, `worked_example_correctness_violations`, the card schema, the renderer.

## 15. Adapters (two levels)
```python
class StateNormalizer(Protocol):                 # SHARED — canonicalize data only
    def normalize(self, state: dict) -> dict: ...
    def equivalent(self, a: dict, b: dict) -> bool: ...

class TraceAdapter(Protocol):                    # ALGORITHM — semantics
    def conventions(self) -> dict: ...
    def validate_conventions(self, conv: dict) -> list[str]: ...     # catch missing visited_when, …
    def granularity_unit(self) -> str: ...
    def required_cases(self) -> list[str]: ...
    def is_teaching_trace(self, trace, required_cases) -> bool: ...   # Stage 0 gate
    def validate_step_shape(self, step) -> list[str]: ...            # pop_visit_push must carry stack+visited
    def normalize_state(self, state: dict) -> dict: ...              # delegates to its StateNormalizer
    def states_equivalent(self, a: dict, b: dict) -> bool: ...
    def final_answer_entails(self, state: dict, answer) -> bool: ...
    def to_visual_state(self, state: dict, step=None) -> dict: ...    # verified visual source
```
The normalizer canonicalizes data (component sets order-independent, visited list-vs-map, heap shape); the
algorithm adapter owns conventions, valid step units, required cases, final-answer + visual semantics — the
only place algorithm knowledge lives.

## 16. Wiring + flag matrix
```python
if _trace_pipeline_enabled():                                  # AZALEA_WORKED_EXAMPLE_TRACE_PIPELINE
    rf = solve_trace_pipeline(topic, ...adapter + injected fns...)
    if rf is not None: return _to_solve_result(rf)             # generated_by="trace_pipeline"
    # None -> fall through unchanged
... existing gen_foundation shadow path ...   ;   ... existing legacy path ...
```
| `TRACE_PIPELINE` | `GF_SHADOW` | Source |
|---|---|---|
| on | any | trace-pipeline; `None` defers below |
| off | on | gen_foundation (unchanged) |
| off | off | legacy one-shot (unchanged) |

`None` always defers — the flag can only replace an example or defer; never break a working topic.

## 17. Phased rollout
- **Phase 1 (text/state):** deterministic only, **adapter-owned reference**, Stage 0 + 1 + structural gate
  + one-card-per-step format (**prose-only; backend attaches state, §11**) + Stage 4 *text/state* fidelity
  + required-case evidence. **Defer `visual_state` ENFORCEMENT to Phase 1.5** (Phase 1 carries the visual
  metadata, doesn't validate it). Build adapters **one at a time, in this order — binary search → BFS →
  iterative DFS → Kruskal → merge sort** (binary search is the first vertical slice: smallest state, easy
  reference, easy teaching-quality gate, easy replay; the rest reuse the pipeline). The first slice answers
  the thesis: *can we make every text/state transition correct while keeping good card quality?*
  **Binary-search Phase-1 flow:** adapter picks array+target → reference runs → adapter rejects trivial
  candidates until ≥3 passes / both bound movements / found-or-absent case → backend builds & verifies the
  ContractTrace + case evidence → LLM writes prose cards only → backend attaches trace_step_ids/states/
  visual_state → backend validates count·order·coverage·fidelity (§12) **AND prose fidelity (§12b)** →
  ship or fall through. **Routing is explicit:** only topics whose slug/metadata (then tight title
  aliases) match one of the five supported algorithms enter the pipeline; everything else → `None` →
  existing path. No fuzzy keyword routing (a broad "graph algorithms" topic must not fall into BFS/DFS).
- **Phase 1 test suite MUST include adversarial-prose stubs** (not only happy-path formatting) — formatter
  stubs that deliberately emit the learner-visible failures Stage 4b exists to catch, asserting it blocks
  each: *binary search* — wrong midpoint / wrong bound update / "found" when absent; *DFS* — visits a node
  not popped / wrong push order / "already visited" when not; *Kruskal* — accepts a cycle edge / "merged" after
  a rejected edge / wrong edge weight; *merge sort* — picks the wrong smaller element / tail-copy before a
  half is empty. These prove Stage 4b catches contradictions, not just that happy-path passes.
- **Phase 1.5 — visual-SOURCE fidelity:** `to_visual_state` + the renderer consumes `visual_state`/
  `visual_delta` **directly**; verify renderer inputs match the trace. Core algorithms render
  structurally (arrays/stacks/queues/graphs/trees) from `visual_state` — never an image model recreating
  them.
- **Phase 1.6 — rendered-IMAGE fidelity:** only if a visual is *generated* (not deterministic) — verify
  the produced image against `visual_state`, preferring structural rendering over image interpretation.
- **Phase 2:** arithmetic/formulas (reason→extract + eval). **Phase 3:** proofs/open-ended (reason→extract
  + critic). **Breadth:** `executed_reference` source for non-core deterministic algorithms.
- A/B each phase vs current (Stage-4 pass-rate, card count, latency/calls); promote default-on per class
  past the bar. Structured `FidelityResult`/`VerifyResult` feed the A/B analysis.

## 18. Cost & failure posture
- Phase-1 deterministic ≈ 1 format call (Stage 0/1/2/4 are code) — *cheaper* than today's solve+audit.
- Non-det = reason+extract+format+critic+rare retries. Any unrecoverable case → `None` → defer/withhold;
  never ships a known-wrong example, never loops.
- **Debug retention (internal-only):** for every trace-pipeline run, persist/log a debug payload — selected
  input, conventions, `ContractTrace`, reference event log, formatter raw response, normalized cards,
  `FidelityResult`/`VerifyResult`. Lets a failure read as "reference trace correct → formatter prose drifted
  at card 6" rather than reconstructing from the final lesson. Not exposed to learners.

---

# Part V — Boundaries

## 19. The required additions, now in the design
Stage 0 instance selection (§8); structured `visual_state`/`visual_delta` from the trace (§5/§11/§12);
two-level adapters (§15); structured `FidelityResult`/`VerifyResult` (§12/§10); trace-level
`required_cases`+`case_evidence` (§5/§12); `validate_conventions`/`validate_step_shape`/`to_visual_state`
(§15); hard guarantee = fidelity to declared semantics via a validated implementation (§4/§10).

## 20. Relationship to existing systems & non-goals
Absorbs `trace_first`/`reference_first`/`executed_reference` as deterministic sources under one pipeline;
nothing deleted; flag-selected; execution primary for deterministic. **Non-goals:** deleting/replacing
existing systems; changing the card schema/renderer; anything outside worked examples. If proven, the
trace-contract pattern is a future candidate for code walkthroughs / lesson body / topic decomposition —
each a separate change.

## 21. Open decisions
- Reference-owned vs `executed_reference` per algorithm (owned for the core five; model-written for breadth).
- 1a/1b one vs two calls for non-executor classes.
- Reasoning model for 1a only if hard-tail accuracy is short.
- Critic strength (start rubric-based single critic).
- Visual prose generation (image prompts) derived strictly from `visual_state`.
