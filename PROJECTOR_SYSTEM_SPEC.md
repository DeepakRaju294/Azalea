# Projector System Spec — Generic State Projection & Graceful Degradation

**Status:** Draft v4 — implementation-ready (third-round refinements incorporated)
**Owns:** how *any* topic gets correct, computed per-step visual state without a bespoke per-topic simulator — and how user feedback re-derives that state instead of re-prompting.
**Companion specs:** `VISUAL_SYSTEM_SPEC.md` (the trace→fold→compile→validate pipeline) and `EXAMPLE_SYSTEM_SPEC.md` (declaration → fixture → handoff). This spec adds a layer *between* a runtime trace and a visual model, plus a tiered fallback that replaces today's hard cliff.

---

## §0 Motivation — the two-system cliff

Today every lesson takes one of two paths, and the path decides whether visual state is **computed** or **asserted**:

- **Path A (computed, trace-authoritative).** A topic with the full chain — application pattern + profile + hand-authored fixture + a *registered per-algorithm simulator* — runs the V2 pipeline. The simulator computes per-step state; five validators gate it. State is *verified, never asserted*. Highlighting is always correct.

- **Path B (asserted, legacy).** Everything else keeps whatever the LLM emitted. Node highlighting comes from `card.visual_focus.active_nodes` / `highlight_path` (`legacy_v2_visual_bridge.py:303-312`). If the LLM didn't emit it, the per-step `node_state_map` is empty and **nothing highlights**. The only place legacy computes state is gated behind `_looks_like_tree_traversal` (`legacy_v2_visual_bridge.py:1624`).

The gap is a **binary cliff**, not a gradient. To move a topic onto the computed path you must hand-author **four coupled artifacts**, the heaviest being a per-algorithm simulator. That architecture *forces* per-topic hardcoding: every new graph algorithm (MST, Prim, Kruskal, Dijkstra, topological sort) needs its own simulator, or it falls to Path B and renders empty. Adding an "MST fixture" makes MST green and leaves the rest of the family equally broken — passing tests without improving the system.

**This spec removes the cliff.** The unit of extension becomes the **visual shape** (node_link, sequence, grid), not the topic. One projector per shape, written once, turns a runtime trace into per-step visual state for *every* algorithm of that shape.

---

## §1 Principles

1. **Derive, never assert.** Per-step visual state is computed from a runtime source of truth (the executed code's variables), never read from an LLM-emitted `visual_focus`.
2. **Extend the shape, not the topic.** New coverage = improving a shape's projector/validator, which improves every topic of that shape at once. Adding a per-topic instance is the anti-pattern this spec exists to prevent.
3. **One delta vocabulary.** The projector emits the *same* deltas the existing compilers already consume. No parallel render format.
4. **Every tier is validated.** A model that can't prove non-empty, well-formed per-step state is rejected before render. "Renders empty silently" becomes impossible.
5. **Graceful degradation, not a cliff.** Computed → projected → inferred → LLM-authored-but-validated → legacy raw. Each tier is gated; the system always lands somewhere safe.
6. **Feedback re-derives.** A correction targets the projection contract or the input and re-runs the deterministic derivation — it does not re-prompt freeform visual state.

---

## §2 Architecture overview

```
        topic ─► declare ─► choose tier ────────────────────────────────────┐
                                                                             │
  ┌──────────────────────────────────────────────────────────────────────┐ │
  │ TIER LADDER (§10) — first tier that VALIDATES wins                     │ │
  │                                                                        │ │
  │  T1 registered simulator ──┐                                           │ │
  │  T2 code + projection   ───┤                                           │ │
  │  T3 code + inferred proj ──┤── run ─► trace ─► PROJECTOR(§4) ─► deltas ─┼─┤
  │  T4 LLM-authored+validated ┘                                           │ │
  │  T5 legacy raw (last resort, flagged by §6 validator)                  │ │
  └──────────────────────────────────────────────────────────────────────┘ │
                                                                             ▼
   deltas ─► DeltaFoldEngine ─► compiler ─► validate_model + §6 state gate ─► visual model
```

The new pieces this spec introduces are **the projector (§4)**, **the projection contract (§3)**, **the per-step state validator (§6)**, the **inference + Tier-3** paths (§8, §9), the **tier ladder (§10)**, and the **regeneration interface (§11)**. Everything downstream of "deltas" already exists.

---

## §2.5 Relationship to the Example System Spec

`EXAMPLE_SYSTEM_SPEC.md` owns *which example, and what is authoritative*: declaration, fixture selection, `resolved_example_type`, `resolved_visual`, the card skeleton, and ProseSlots. This spec owns *how visual state is derived once a trace exists*. **Projectors do not replace fixtures or simulators — they sit between a trace and the visual model.** The handoff:

```
DeclaredExample / CanonicalFixture                 (Example Spec)
  → code + base_structure + projection contract     (this spec, §3)
  → runtime trace                                    (existing tracer / simulator)
  → projector                                        (§4)
  → deltas → fold → compile → visual model           (Visual Spec)
  → ProseSlots built from the SAME projected frames  (§6.4 INV-PROSE-SYNC)
  → feedback edits contract/input/code → deterministic re-run (§11)
```

This prevents the future confusion of "do projectors replace fixtures?" — they do not. A fixture/declaration still chooses *what* example runs; the projector decides *how its state is read*.

**Shared key — `event_id`.** The `event_id` minted by the projector (§4 step 5) is a *cross-spec* join key, so `EXAMPLE_SYSTEM_SPEC.md` must adopt it too: when a visual model is built from projected or simulated trace steps, ProseSlots are keyed by `event_id` when available, and code-walkthrough cards + supporting diagrams join on `event_id`, **not frame index**. ProseSlot context additionally carries `state_source` / `tier` (§6.4 INV-PROSE-SYNC). This keeps the two specs in agreement about what "the same step" means.

## §2.6 Scope boundary — a projector reads a trace, it never creates one

A projector contains **no algorithm logic**. It does not know how Dijkstra works; it knows how to read `current` / `visited` / `selected_edges` / `frontier` out of a trace. Truth always flows:

```
algorithm truth source → runtime trace → projector → visual state
```

never `projector → trace`. The "truth source" is one of: a registered simulator, executable code run through the tracer, a deterministic fixture trace, or LLM-authored code that executes and validates (§9). A *conceptual* worked example with no code still needs one of those trace sources — **the projector replaces per-topic visual-state simulators, not trace sources.**

---

## §3 The projection contract — `GraphProjection`

A projection contract is the **only per-topic artifact** the projected tiers need: a tiny descriptor naming which runtime variables hold which pieces of graph state. The reader logic that *uses* it (§4) is written once.

```python
@dataclass(frozen=True)
class GraphProjection:
    # Each *_from is the name of a local variable in the traced code.
    current_from: str            # scalar: the node being processed this step (e.g. "u", "node", "current")
    visited_from: str | None     # set/list: membership of done nodes (e.g. "visited", "seen", "in_mst")
    visit_order_from: str | None # ordered list: insertion order, when membership order matters (e.g. "order", "result")
    selected_edges_from: str | None  # list of pairs: chosen edges (e.g. "mst", "tree_edges", "path")
    frontier_from: str | None    # list/heap: the queue / stack / priority frontier (e.g. "pq", "stack", "queue")
    # How a runtime node value maps to a node id in base_structure.nodes.
    node_key: str = "identity"   # "identity" | "val" (TreeNode.val) | "index"
    edge_key: str = "identity"   # how an edge value maps to (from, to): "identity" | "index:0,1" | "attr:u,v"
    # Priority-queue items are often tuples like (distance, node), so the node is
    # NOT the whole frontier item. These say where the node / priority live inside it.
    frontier_node_key: str | None = None      # "identity" | "index:1" | "attr:node"
    frontier_priority_key: str | None = None  # "index:0" | "attr:priority"
```

Semantics:
- **`current_from`** is mandatory — every step must have an active node, else there is nothing to highlight.
- **`visited_from`** OR **`visit_order_from`** must be present (membership comes from one or the other). If both are present, `visit_order_from` is authoritative for display order and `visited_from` is the membership cross-check.
- **`selected_edges_from`** is optional and used by edge-selection algorithms (MST, shortest-path trees). When absent, the projector emits node-only state (traversals).
- **`frontier_from`** is optional; it drives the frontier panel (queue/stack/PQ contents) but is never required for highlighting. For priority-queue algorithms (Dijkstra, Prim) the frontier holds `(priority, node)` tuples, so **`frontier_node_key`** / **`frontier_priority_key`** say where the node and priority live inside each item; without them the projector treats the whole item as the node (correct for plain BFS/DFS queues).
- A contract is **validated** (§6.3) before use: named variables must exist in the trace, and the values they reference must resolve to node ids / edges present in `base_structure`.

> **Note on extensibility:** `GraphProjection` is the node_link shape's contract. Each future shape (§13) defines its own contract dataclass (e.g. `SequenceProjection` naming pointer/range variables). The projector pattern — *contract + reader + validator* — is identical across shapes.

---

## §4 The projector — `project_node_link`

**File:** `backend/app/services/visual_v2/projectors/node_link.py`

**Signature:**
```python
def project_node_link(
    trace_steps: list[dict],        # the code-execution trace's per-line steps (set_locals etc.)
    base_graph: dict,               # {"nodes": [...], "edges": [...]} from base_structure
    projection: GraphProjection,
) -> ProjectionResult:              # deltas + provenance/debug metadata (§4.2)
```

`ProjectionResult.deltas` is the `list[TraceStep]` that drops straight into the existing compiler; the surrounding metadata (§4.2) carries provenance, the collapse ratio, and warnings that telemetry (§14) and feedback (§11) need.

**Algorithm:**
1. Walk the code-execution steps in order. Each step carries the structured `set_locals` snapshot (the tracer already serializes sets→sorted lists, lists-of-tuples→lists-of-pairs — see §5).
2. Track the *previously emitted* node state (active, visited set, selected edges).
3. At each step, read the projected variables:
   - `active = locals[current_from]`, mapped through `node_key` to a node id.
   - `visited = set(locals[visit_order_from or visited_from])`, mapped through `node_key`.
   - `selected = [normalize_edge(e) for e in locals[selected_edges_from]]` when present.
4. Emit a node_link `TraceStep` **only when the projected state changes** (so 600 raw line-steps collapse to one step per meaningful graph event — the same milestone idea handoff already uses). The emitted delta uses the existing node_link vocabulary:
   - `set_active`: the new active node.
   - `newly_visited`: nodes that entered `visited` since the previous emitted step.
   - `add_to_frontier` / `remove_from_frontier`: frontier deltas (when `frontier_from` is set).
   - `append_to_output`: active node by label (mirrors traversal output panel).
   - **`set_active_edge` / `add_selected_edge`** (new ops, §4.1): the edge chosen this step and the growing selected-edge set, for edge-selection algorithms.
5. Each emitted step carries a **semantic `event_id`** and a **`step_role`** (e.g. `step_role="visit"` / `"commit_edge"`). These ids are the join key for dual-slot sync (§6.4 INV-DUAL-SLOT), ProseSlot grounding (§6.4 INV-PROSE-SYNC), feedback targeting (§11), and debugging — one event, named once, referenced everywhere. **Uniqueness rule:** within one visual model, `event_id` must be **stable and unique per emitted event**. Because algorithms revisit/reconsider the same node or edge, the id is structured and carries the emitted index so repeats never collide:
   ```
   event_id = f"{event_kind}:{entity_key}:{emitted_index}"   # e.g. "visit:C:03", "select_edge:B-C:07"
   ```
   A human-readable label (`"Visit C"`) is for display only; the structured id is the internal join key. Two visits of C produce `visit:C:03` and `visit:C:07`, so code/diagram/prose never join to the wrong frame.
6. Initial state mirrors `graph.py`'s: `{"active": None, "frontier": {...}, "visited": [], "output": [], "selected_edges": []}`.

The `deltas` are a list of `TraceStep`s **identical in shape** to what `simulate_bfs` produces — so `DeltaFoldEngine` + `compilers/node_link.py` consume them unchanged.

### §4.1 New delta ops for edge selection

Traversal (BFS/DFS) needs only node state, which `delta_fold` + the node_link compiler already support. Edge-selection algorithms (MST, Dijkstra tree) need two additive ops:
- `set_active_edge: [from, to]` — the edge under consideration / just chosen this step.
- `add_selected_edge: [from, to]` — append to the committed (highlighted) edge set.

These fold into the model's per-frame state as `active_edge_from/to` and `completed_edges_from/to` — the **same fields the legacy bridge already emits** (`legacy_v2_visual_bridge.py:334-337`), so the frontend contract is unchanged. Adding them is a small, additive extension to `delta_fold.py` and `compilers/node_link.py`; no existing op changes.

### §4.2 `ProjectionResult` — deltas + provenance

The projector returns metadata alongside the deltas, because feedback (§11), telemetry (§14), and debugging all need to know *what the projection did*:

```python
@dataclass(frozen=True)
class ProjectionResult:
    shape: str                       # "node_link"
    projection_source: str           # "authored" | "inferred" | "llm_authored"
    projection_contract: dict        # the GraphProjection actually used (asdict)
    deltas: list[TraceStep]          # drop-in for DeltaFoldEngine + compiler
    raw_step_count: int              # trace steps in
    emitted_step_count: int          # visual steps out
    dropped_step_count: int          # raw - emitted (the collapse ratio)
    warnings: list[str]              # e.g. "frontier_from unresolved; frontier panel empty"
    debug: dict                      # per-event {event_id, active, newly_visited, selected_edge}
    projector_version: str           # bump when project_node_link logic changes
    inference_version: str | None    # set when projection_source == "inferred"
    state_entity_map: dict           # event_id -> {nodes:[...], edges:[[a,b]...], variables:[...]}
```

`state_entity_map` records which graph entities (and source variables) each event touched. It is what makes click-to-correct feedback possible: a user clicking node C on a frame resolves frame → `event_id` → the entities/variables that produced it → the `correction_target` (§11.2).

This lets telemetry log human-readable lines like *"inferred current_from='u', visited_from='seen', selected_edges_from=None; 18 raw steps → 6 visual steps"* and gives the regeneration UI (§11) the contract to edit. The version fields are critical for regeneration of *old* lessons: when the projector improves, provenance (§10.1) records which projector produced a now-stale model, so telemetry can attribute "v1 had many wrong_frontier issues; v2 fixed them" and re-derivation knows it is upgrading, not just re-running.

---

## §5 Reading runtime state — the tracer contract (verified)

The projector depends on the existing universal tracer (`simulators/code_tracer.py`). **This dependency is already satisfied** — no tracer change is required for node_link:

- `serialize_value` (`code_tracer.py:68-82`) preserves structure: `set → sorted list`, `list/tuple → list`, `dict → dict`, objects with `.val`/`.value` → that value, scalars unchanged.
- Therefore a traced `visited` set arrives as a sorted list (membership intact), an `mst`/`tree_edges` list of tuples arrives as a list of `[u, v]` pairs, and a `current`/`u` scalar arrives as-is.
- Each trace step exposes these under `set_locals` (`code_tracer.py:142-148`).

**One known limitation:** a Python `set` is serialized *sorted*, so insertion order is lost. When visit *order* matters for display, the contract must point `visit_order_from` at an ordered accumulator (a `list`/`result`/`order`), not the set. Membership-only highlighting is unaffected. This is documented in the contract semantics (§3) and enforced by inference (§8).

---

## §6 Validation — the per-step state gate

Three checks, all additive. The first is the immediate guardrail that makes the MST-style failure impossible to ship.

### §6.1 `node_link` model state validator (Path A)
Extend `validators.py`. A node_link model is **rejected** when any worked-example step:
- has an empty `node_state_map` (no active and no completed node), or
- references a node id absent from the model's node set, or
- never changes across the whole step sequence (static highlight ⇒ no real trace).

### §6.2 Legacy detect-and-flag + T5 display policy (Path B)
In `legacy_v2_visual_bridge.py`, after building `node_state_map` (line ~333), if a node_link worked-example card resolves to empty per-step state, record a metric (`empty_node_state`) and log it.

**T5 display policy:** observability is necessary but not sufficient — a known-broken visual is worse than none. For a **required progressive worked-example visual**, T5 may render *only if it has non-empty per-step state*. If the state is empty, the card falls back to **text-only (or omits the visual)** rather than shipping an empty/broken diagram. (Low-stakes *static* visuals may still render at T5.) So legacy is a real fallback, but it can never put a visibly-broken progressive diagram in front of a learner.

### §6.3 Projection validator (the projected tiers)
Before a `GraphProjection` is used, assert:
- every `*_from` names a variable that appears in the trace,
- the values resolve to node ids present in `base_structure.nodes`,
- every projected/selected edge exists in `base_structure.edges`,
- the projected state is **non-empty and changes** across ≥ `min_steps` steps.

A projection that fails any check is discarded and the ladder (§10) drops to the next tier. "Verified, never asserted" applies to the contract itself.

### §6.4 Systemwide rendering & completeness invariants

These are recurring defects observed *across* topics — a class of bug, not one instance. Each becomes a **named invariant** enforced by the §6 gate for the relevant shape, so a single fix covers every topic of that shape (the anti-hardcoding rule applied to rendering, not just state).

- **INV-DUAL-SLOT — a coding worked example fills *both* slots, each with the right content, on the *same* step.** A `code_execution_trace` worked example must carry (a) the code view in the **code slot** (`visual_v2_ref` → `code_trace`) **and** (b) a supporting diagram in the **diagram slot** (`diagram_v2_ref` → the *projected* node_link / sequence model from §4). The gate **rejects or repairs** when: either slot is empty, the code is rendered in the diagram slot or the diagram in the code slot, or the two slots disagree on which step they show. Synchronization is by **shared `event_id`** (§4 step 5), not by frame index — each card step is a `DualSlotStep` joining the two views on one event:

  ```python
  @dataclass(frozen=True)
  class DualSlotStep:
      shared_event_id: str   # e.g. "visit_node_C" — the join key
      code_frame_index: int  # the trace line where C is popped
      diagram_frame_index: int  # the projected frame where C becomes active/visited
      step_role: str         # from the projected step (§4)
  ```

  This kills the common "both slots exist but show slightly different moments" bug. The diagram half is *projected*, not LLM-drawn. Holistic: applies to every coding worked example, never authored per topic. (Today's `_attach_supporting_diagram` in `handoff.py:612` does this only for binary-search-shaped code, and aligns by `mid`-change rather than a shared event; the invariant generalizes both.)

- **INV-RENDER — node_link structural & label correctness.** Every rendered node_link model must satisfy: each node has a non-empty label that matches its id/value (no blank, duplicate, or placeholder labels); every edge references two nodes that exist; weighted-graph edges carry their weight; no orphaned or duplicated nodes/edges. This **generalizes the one-off edge backfill** (`_backfill_missing_node_link_structure`) into a *standing* validator that repairs or rejects — so "improperly labeled nodes" and "missing/dangling edges" are caught for all graph topics, not patched per lesson.

  **Repair boundary (so "repair" never becomes a hidden assertion path):** repairs may only fix *structural presentation* from the authoritative `base_structure` — they may **never** modify per-step algorithm state. Concretely:
  - *Allowed:* fill a missing label from the node id; backfill an edge weight from `base_structure`; drop a visual-only duplicate node whose id already exists; normalize edge direction for an undirected graph.
  - *Forbidden:* invent a missing node or edge; infer or alter `active` / `visited` / `selected_edges` state; change which step shows what.

  The one-line rule: **repairs fix presentation from `base_structure`; they do not touch per-step state.** Anything that would require inventing state is a *reject*, which drops the topic down the ladder (§10).

- **INV-COMPLETE — the example runs to completion.** A worked example must reach the algorithm's **terminal state**: the final milestone's state equals `expected_output` — binary search returns the index, a traversal's output lists every reachable node, MST selects |V|−1 edges. The gate **rejects a trace that truncates before the terminal state**, so an example can never stop "midway." Concretely, milestone selection (§4 step 4; handoff `_milestone_frame_indices`) must *always* include the terminal frame, and the last card must narrate the final answer. Holistic: a completeness check keyed on `expected_output`, identical across shapes.

- **INV-PROSE-SYNC — prose explains the same state the visual shows.** Every ProseSlot claim on a card must reference facts from the **same projected frame / `event_id`** as that card's visual. When a visual is built through a projector, `ProseSlot.current_frame_delta` is derived from the *emitted projection delta*, not from raw code-trace text — so the bullet "C is removed from the queue, becomes active, and is now marked visited" is generated from `{set_active: C, newly_visited: [C], remove_from_frontier: [C]}`, guaranteeing agreement. The gate rejects a card whose prose cites a node/edge/value absent from its frame's state. This is the bridge back to `EXAMPLE_SYSTEM_SPEC.md`'s ProseValidator — the projector makes its `allowed_facts` the projected frame. **The ProseSlot context also carries `state_source` / `tier` / `event_id`**, so the prose policy can be confident for T1–T4 (narrate the projected delta precisely) and conservative for T5 (avoid precise step-state claims unless validated facts exist).

These invariants are enforced by the same §6 gate that blocks empty per-step state, run at every tier of the ladder (§10).

---

## §7 Pipeline integration — the computed node_link route

**File:** `pipeline.py`, a new branch in `_compile_for_mode` / `run_for_registered`.

A new logical mode **`graph_projection`**: given an example carrying `code` + `entry_function` + a `graph_projection` contract + `base_structure` (the graph):
1. Run the universal tracer (`simulate_code_execution`) on the real code → code-execution trace.
2. Validate the projection (§6.3) against that trace + base graph.
3. `project_node_link(trace.steps, base_graph, projection)` → node_link deltas.
4. `DeltaFoldEngine().fold(...)` with the node_link delta vocabulary → frames.
5. `compilers/node_link.py` → node_link model.
6. `validate_model` + the §6.1 state gate + `pedagogical_check`.

The output is a fully computed, validated node_link worked example built from **code + a 3-line contract** — no per-algorithm simulator. MST, Prim, Kruskal, Dijkstra, topological sort all route here.

`CanonicalFixture` (`example_fixtures.py`) gains an optional `graph_projection` field; `fixture_to_canonical_example` (`handoff.py:68`) carries it onto the CanonicalExample.

---

## §8 Projection inference — `infer_projection`

So a topic needs **zero** hand-authored contract, the projector can derive one from the trace.

**File:** `projectors/node_link.py`.

```python
def infer_projection(trace_steps: list[dict], base_graph: dict) -> InferredProjectionCandidate | None:

@dataclass(frozen=True)
class InferredProjectionCandidate:
    projection: GraphProjection
    confidence: float          # 0..1, from how cleanly each role's evidence matched
    confidence_band: str       # "high" | "medium" | "low" (for ladder + telemetry)
    evidence: dict             # per-role: why this var was chosen (for logs + feedback)
```

Each role is chosen with a confidence and a recorded reason, so inference is debuggable and feedback-targetable — e.g. *"visited_from inferred as 'seen' (0.9): set of node ids growing monotonically over 7 steps."* A **low-confidence-but-validating** candidate is still accepted (validated deterministic inference beats an LLM round-trip) but is flagged for telemetry and may trigger review if a user later complains — it does **not** auto-escalate to Tier-3 (§10).

**No-branch-on-application rule (testable):** `infer_projection` and `project_node_link` may branch only on *shape*, *contract fields*, *runtime value types*, and *validated structure* — **never on the application/algorithm name.** Algorithm-specific knowledge lives only in the profile/fixture as data (e.g. a Dijkstra fixture sets `frontier_node_key="index:1"`), never as `if application == "dijkstra"` in projector or inference code. A test asserts no application-name branch exists in these modules.

Heuristics (typed, name-hinted, then validated):
- **`visited_from`**: a variable whose value is a set/list of node ids that grows monotonically and never shrinks; name hints `visited|seen|explored|in_mst|done` break ties.
- **`current_from`**: a scalar reassigned (to a node id) on most loop iterations; name hints `u|v|node|current|cur`.
- **`selected_edges_from`**: a list of 2-tuples of node ids that grows monotonically; name hints `mst|tree|edges|path|result`.
- **`visit_order_from`**: an ordered list of node ids growing monotonically; name hints `order|result|path|output`.
- **`frontier_from`**: a list/heap whose membership churns (adds and removes); name hints `queue|stack|pq|heap|frontier`.

The candidate is accepted **only if it passes §6.3** against the actual trace. Inference never asserts; it proposes and the validator disposes. If no candidate validates, the ladder drops to the next tier.

The anti-hardcoding guarantee: inference is purely structural/type-based with name hints as tie-breakers — there are **no per-algorithm branches**.

---

## §9 Tier-3 — LLM-authored, validated

When neither a registered simulator nor an inferable contract exists, the LLM supplies the missing *inputs*, and the deterministic core still owns the *truth*.

**File:** `backend/app/services/examples/tier3.py`.

The LLM provides, as a typed JSON payload:
- the algorithm's **real code** + `entry_function`,
- the **graph** (`base_structure`),
- a **proposed `GraphProjection`** (which variable is which).

The system then:
1. **Runs** the code (`simulate_code_execution`) and checks it produces the declared `expected_output` (the algorithm is real, not hallucinated).
2. **Validates** the proposed projection (§6.3).
3. Projects + compiles + validates exactly as §7.

Only a payload that *executes correctly and projects validly* is accepted. The LLM proposes; the tracer and validators dispose. This is the path that makes the system "responsive to regeneration inputs" (§11) without ever trusting freeform visual state.

---

## §10 The graceful-degradation ladder

Replaces the binary cliff. For a topic + shape, try tiers in order; **the first that validates wins**:

| Tier | `state_source` name | Per-topic artifacts | When it applies |
|------|-----------------|---------------------|-----------------|
| **T1** | `registered_simulator` | 4 (app, profile, fixture, simulator) | Algorithms already in the registry (BFS, DFS, binary search). Unchanged. |
| **T2** | `authored_projection` | 1 (code + contract in a fixture) | Hand-verified graph algorithms (MST, Dijkstra) without a bespoke simulator. |
| **T3** | `inferred_projection` | 0 | Any graph code whose contract `infer_projection` recovers + validates. |
| **T4** | `llm_validated_projection` | 0 | Novel topics; LLM supplies code + contract, system verifies (§9). |
| **T5** | `legacy_raw` | 0 | Last resort. Now **flagged** by §6.2 so it's measured, never silent. |

Every tier above T5 emits the *same* node_link deltas, so the entire downstream is shared. The ladder is implemented in `examples/tiers.py` (or inline in `handoff.py`), with per-tier metrics (§14) so we can see what fraction of topics land where — and watch the legacy tail shrink over time.

**T3-vs-T4 ordering nuance:** a *validating* T3 inferred projection always beats T4, even at low confidence — deterministic-and-validated is more trustworthy than LLM-authored, and we do not want to overuse the LLM. Low confidence does **not** demote to T4; it only sets `confidence_band="low"`, which is logged and may trigger review if user feedback arrives (§11). T4 is reached only when no projection *validates* at all.

### §10.1 Provenance — every visual model declares its tier

So a bad visual can be diagnosed without guesswork, **every** visual model carries provenance stamped at compile time:

```python
state_source: Literal[
    "registered_simulator", "authored_projection",
    "inferred_projection", "llm_validated_projection", "legacy_raw",
]
tier: Literal["T1", "T2", "T3", "T4", "T5"]
shape_projector_status: Literal["implemented", "planned", "unsupported"]  # why a shape can/can't project
projection_source: str | None     # "authored" | "inferred" | "llm_authored" (from ProjectionResult)
projection_contract: dict | None  # the GraphProjection used, when projected
projector_version: str | None     # which projector built this (regen-of-old-lessons)
inference_version: str | None     # which inference, when projection_source == "inferred"
confidence_band: str | None       # "high" | "medium" | "low" for inferred projections
code_source: str | None           # T2: "inline_fixture" | "canonical_code_id"
canonical_code_id: str | None     # set when code_source == "canonical_code_id" (§17 Q3 migration)
validation_summary: dict          # which §6 invariants passed, collapse ratio, warnings
```

`shape_projector_status` makes a T5 fallback self-explaining: a `grid_matrix` topic with `projector_status="planned"` fell to legacy because *the shape has no projector yet*, not because the projection failed — a different fix (build the shape) than a bad contract. The matching legacy fallback reason is **`unsupported_projector_shape`** (§14).

This makes triage mechanical: if a visual is wrong **and** `tier == "T5"`, the fix is not to tweak the renderer — it's to move that topic up the ladder to T2/T3. Provenance is also what lets §14 telemetry and §11 feedback attribute a problem to the right layer.

---

## §11 Regeneration / feedback interface

The future goal: user feedback improves the system. For that, a correction must re-run a *deterministic derivation*, not re-roll an LLM. This section designs the data shapes now (UI wiring later).

### §11.1 Correction targets — what feedback may edit

```python
@dataclass(frozen=True)
class RegenerationRequest:
    topic_id: str
    shape: str                      # "node_link" | ...
    correction_target: str          # "projection" | "input" | "code" | "milestone_policy" | "prose"
    correction: dict                # e.g. {"current_from": "u"} or a new base_structure
```

Resolution:
- `projection` → override the inferred/authored contract and re-project (§4). Deterministic, instant.
- `input` → swap `base_structure` (a different graph) and re-run the trace + projection.
- `code` → re-run the tracer on corrected code (Tier-3 re-validate).
- `milestone_policy` → adjust which events become cards / the dual-slot mapping (§6.4 INV-DUAL-SLOT).
- `prose` → adjust ProseSlot policy (still grounded to the same frame, §6.4 INV-PROSE-SYNC).

Feedback targets a **contract, input, code, or policy** — never per-step visual state directly. That is the invariant (§18) that keeps a single fix holistic and prevents re-introducing asserted state.

### §11.2 Issue taxonomy — what users actually report

Users don't say "projection"; they say "the wrong node is highlighted." Normalize free-text into a closed set, each mapped to the likely correction target:

```python
ProjectionIssueType = Literal[
    "wrong_active_node",        # → projection.current_from or node_key
    "missing_visited_node",     # → projection.visited_from / visit_order_from
    "wrong_visit_order",        # → projection.visit_order_from
    "missing_selected_edge",    # → projection.selected_edges_from
    "wrong_selected_edge",      # → projection.selected_edges_from or edge_key
    "missing_frontier",         # → projection.frontier_from / frontier_node_key
    "wrong_base_structure",     # → input / base_structure
    "trace_truncated",          # → code or expected_output (INV-COMPLETE)
    "code_visual_step_mismatch",# → milestone_policy / dual-slot event mapping
    "empty_state",              # → projection (nothing resolved) or tier promotion
    "prose_visual_mismatch",    # → prose / ProseSlot (INV-PROSE-SYNC)
]
```

The mapping is a lookup, so the UI (§11.6) can pre-fill the most likely `correction_target` and the system proposes a concrete edit.

### §11.3 `FeedbackRecord` — every flag/regeneration is logged

```python
@dataclass(frozen=True)
class FeedbackRecord:
    topic_id: str; application: str | None; pattern: str | None
    shape: str; tier: str; fixture_id: str | None
    visual_model_id: str; frame_index: int | None
    issue_type: str                  # from §11.2 (or "user_reported")
    user_text: str
    severity: str                    # "minor" | "major" | "blocking"
    user_confidence: str             # "low" | "medium" | "high"
    system_confidence: float         # how sure the system is the issue is real
    correction_target: str
    accepted_correction: dict
    post_regen_validation_status: str  # validated | failed:<stage>
    targeted_change_observed: bool     # did the model actually change in the targeted way?
```

This is what turns feedback into product direction — it answers *which invariant fails most, which shape drives the most regenerations, which topics fall to legacy, which corrections succeed.* Severity prioritizes review ("wrong highlighted node" and "stops too early" are blocking; "label looks weird" is minor).

**Definition of a *successful* regeneration.** A regeneration counts as successful only when **all four** hold:
1. the correction was applied,
2. the pipeline re-ran,
3. the validators (§6) passed, **and**
4. the resulting model differs from the prior model *in the targeted way* (`targeted_change_observed == True`).

Requirement 4 is what stops a "successful" regeneration that validates but doesn't actually fix what the user reported (e.g. re-running and getting the same empty diagram). The targeted change is verified against a `RegenerationDiff`:

```python
@dataclass(frozen=True)
class RegenerationDiff:
    before_tier: str; after_tier: str
    before_projection_contract: dict | None; after_projection_contract: dict | None
    before_event_ids: list[str]; after_event_ids: list[str]
    changed_frames: list[int]
    changed_nodes: list[str]; changed_edges: list[tuple[str, str]]
```

e.g. *"changed `current_from` 'node'→'u'; frames 2–5 now highlight B, C, D instead of empty state."* The diff drives both the UI confirmation and patch promotion.

### §11.4 `ProjectionPatch` — corrections that should outlive one lesson

A correction that fixes a projection should be able to improve *future* generations, not just the current lesson. The decisive field is **`scope`**:

```python
@dataclass(frozen=True)
class ProjectionPatch:
    patch_id: str
    shape: str; application: str | None; pattern: str | None
    issue_type: str
    correction_target: str
    correction: dict
    scope: Literal["fixture", "application_profile", "shape_projector", "inference_rule"]
    created_from_topic_id: str
    validation_result: str
```

Scope examples:
- `fixture` — only this Dijkstra fixture had the wrong edge.
- `application_profile` — *all* Dijkstra examples should use `selected_edges_from="shortest_path_edges"`.
- `shape_projector` — the node_link projector should also accept `TreeNode.value`, not just `.val`.
- `inference_rule` — variables named `included` often mean visited/in_mst.

This is the ladder by which a one-off correction climbs to a system-wide improvement.

### §11.5 Review / approval — promotion is not automatic

A user correction must **not** silently alter global behavior. Two stages:

- **Stage 1 (local):** apply the correction to *this* lesson, re-run the pipeline, re-validate (§6). The learner only ever sees a re-validated result (§18 rule 7).
- **Stage 2 (promotion):** when telemetry shows the *same* `issue_type` + `application`/`pattern` + a *successful* correction (per the four-part definition above) recurring across regenerations or users, the system **proposes** a `ProjectionPatch` at the appropriate `scope` for human approval — e.g. "promote this correction from fixture-level to application-profile-level." Nothing wider than fixture-scope is applied without approval.

**Promotion golden gate.** A `ProjectionPatch` above `fixture` scope must, before it is accepted, pass: (a) the original failing lesson, (b) the existing golden tests for that shape, **and** (c) at least one *unrelated* fixture of the same shape. This stops a correction that fixes one Dijkstra example from silently breaking Prim or BFS — a shape-wide change must prove it's shape-wide-safe.

**Low-confidence-T3 caution.** A `confidence_band="low"` inferred projection (§8) may render (it validated), but it must **not** seed a global patch promotion unless corroborated by user feedback or goldens — otherwise low-confidence guesses would generate noisy patch suggestions. Low-confidence inference is a render source, not a promotion source.

### §11.6 Constrained regeneration UI (future)

Replace blind "regenerate" with a fixed menu that maps to deterministic targets:

| User picks | Maps to |
|------------|---------|
| Wrong highlighted node | `projection` (current_from / node_key) |
| Wrong highlighted edge | `projection` (selected_edges_from / edge_key) |
| Wrong graph/diagram structure | `input` / base_structure |
| Code and diagram out of sync | `milestone_policy` / dual-slot event mapping |
| Example stops too early | `code` / `expected_output` (INV-COMPLETE) |
| Explanation doesn't match visual | `prose` (INV-PROSE-SYNC) |

Each choice re-runs the deterministic core, never a freeform redraw.

---

## §12 Retiring the tree-traversal special case

Proof that the generalization is real, not additive: tree traversal is a graph walk with `visited` + `current`. Once the projector handles it, the gated `_looks_like_tree_traversal` normalization (`legacy_v2_visual_bridge.py:1201, 1624`) becomes a *privileged* computed path we can delete.

- Express inorder/preorder/postorder/level-order through the same projector (the tree is a graph; `node_key="val"`).
- Remove the bespoke tree normalization.
- The **existing BST/traversal golden tests must stay green with the special case removed** — the strongest possible proof we generalized instead of accumulating.

This phase is the litmus test: if deleting the special case breaks nothing, the projector is genuinely holistic.

---

## §13 Generalizing to other shapes (future)

The contract + reader + validator pattern is per-shape. After node_link proves out:
- **`SequenceProjection`** (indexed_sequence): `pointers_from`, `range_from`, `window_from` → reuses `compilers/indexed_sequence.py`.
- **`GridProjection`** (grid_table): `active_cell_from`, `filled_from` → reuses `compilers/grid_matrix.py`.

Each is an independent, later unit of work. The pipeline route (§7), validator pattern (§6), inference (§8), Tier-3 (§9), ladder (§10), and feedback (§11) are all shape-parameterized, so adding a shape adds a projector + a contract, not a new subsystem.

---

## §14 Telemetry

Extend `examples/metrics.py`. The point is to make projector work **data-driven** — telemetry says where the system bleeds, and that prioritizes the next improvement.
- **Per-tier counters**: how many topics resolved at T1…T5 (watch the T5/legacy tail shrink).
- **`empty_node_state`** reason (§6.2): legacy cards that rendered empty — the bug's prevalence, now measured.
- **`unsupported_projector_shape`** reason: fell to T5 because the shape has no projector yet (`shape_projector_status="planned"`), distinct from a projection that failed — it points at "build the shape," not "fix the contract."
- **Projection outcome**: inferred-accepted / inferred-rejected (with reason) / authored / llm-authored, per application.
- **Inference rejection reasons**: which role failed to resolve (e.g. `selected_edges_from` un-inferable) — directly tells us which heuristic to improve.
- **Invariant failures**: counts per INV-* (§6.4), by shape/application — which invariant fails most.
- **Regeneration**: `FeedbackRecord` rollups — top `issue_type`, top `correction_target`, correction success rate, top applications with projector failures.

Concretely, this lets future work be chosen from data: *many graph topics failing because `selected_edges_from` can't be inferred → improve edge-list inference; many trees failing `node_key` → improve node-key normalization; Dijkstra frontier confusing → add `frontier_priority_key` support.* Surface via the existing `/v2-metrics` endpoint.

---

## §15 Testing strategy — the anti-hardcoding guarantee

Every test asserts behavior for a **family**, never a single topic. The suite is designed so you *cannot* make it green by hardcoding an instance.

1. **State validator (§6.1):** synthetic node_link models — good / empty / static — asserted by *defect shape*, not topic name.
2. **Projector (§4):** hand-written traces for **BFS, Dijkstra, Prim** with natural variable names; one `project_node_link` must produce correct highlight sequences for all three.
3. **Computed route (§7):** one fixture each for **MST/Prim and Dijkstra** supplying *only code + a contract* (no simulator); both must yield validated node_link worked examples with correct highlighting — same machinery, two algorithms.
4. **Inference (§8):** run `infer_projection` over traces from **5+ graph algorithms** (BFS, DFS, Dijkstra, Prim, Kruskal); recover a valid contract for each with no per-algorithm branches in the test or the code.
5. **Ladder (§10):** a registered topic uses T1; a code-only graph topic uses T2/T3; a topic with neither still never renders empty (drops to T5 *and* trips the §6.2 flag).
6. **Retirement (§12):** the existing BST/traversal goldens stay green with the bespoke normalization deleted.
7. **Dual-slot (INV-DUAL-SLOT):** a coding worked example (binary_search, and one graph-code topic) yields a non-empty *code* slot **and** a non-empty *diagram* slot, each holding the right kind of model — asserted by slot/content, not topic.
8. **Render correctness (INV-RENDER):** malformed node_link models — blank/duplicate label, dangling edge, missing weight — are repaired-or-rejected for *any* graph, with no topic-specific branch.
9. **Completion (INV-COMPLETE):** traces for binary search, BFS, and MST each reach their terminal state (`expected_output`); a deliberately truncated trace is rejected.

---

## §16 Rollout

Additive, flag-gated, reversible — matching the existing `AZALEA_VISUAL_V2_MODES` / `AZALEA_FIXTURE_GENERATORS` pattern:
- **`AZALEA_PROJECTORS`** (default OFF): enables T2/T3 projected routes. With it off, behavior is exactly today's (T1 + legacy).
- Tier-3 (§9) gated additionally behind a live-LLM flag, as `skeleton_fill` is.
- The §6.1/§6.2 validators ship **on** from the start — they only reject genuinely-broken state and flag genuinely-empty legacy cards; nothing regresses.
- `APPLY_VERSION` bumps so cached lessons re-enrich onto the projected path on read.

Build order (each independently shippable):
1. **§10.1 provenance fields on every visual model** — `state_source` / `tier` / `validation_summary` first, so every later piece is attributable from day one.
2. **§6.1 + §6.2 validators + `empty_node_state` telemetry + T5 display policy, plus INV-RENDER + INV-COMPLETE (§6.4)** — the guardrail. (INV-DUAL-SLOT + INV-PROSE-SYNC wait on the projector.)
3. **§3 `GraphProjection` + §6.3 projection validator.**
4. **§4 projector (`ProjectionResult` + versions + `event_id`) + §4.1 edge-selection ops** in fold/compiler — the reader.
5. **§7 `graph_projection` route (T2)** + the **Dijkstra/Prim T2 fixtures**.
6. **§6.4 INV-DUAL-SLOT (`event_id` sync) + INV-PROSE-SYNC** — coding diagram slot filled + synced.
7. **§8 inference (with confidence band)** — T3, zero artifacts.
8. **§14 telemetry rollups** — invariant-failure + inference-rejection + FeedbackRecord counters.
9. **§9 Tier-3** — regeneration-ready LLM authoring.
10. **§11 feedback interface** — `FeedbackRecord` → local re-derive → `RegenerationDiff` → `ProjectionPatch` proposal (§11.5), later promotion.
11. **§12 retire tree special case** — prove holistic-ness.

---

## §17 Open questions resolved for v4

1. **Node identity across shapes.** **Resolved for v1:** support `identity | index | val | value | attr:<name> | index:<n>` as string keys; this covers trees (`val`), graphs (`identity`), and tuple/object nodes (`attr:` / `index:`). Arbitrary callable normalizers are deferred — they're harder to serialize, validate, and surface in the feedback UI. Revisit only if a real node representation escapes the string keys.
2. **Frontier semantics for priority queues.** **Resolved:** display the frontier sorted by priority *only when* `frontier_priority_key` is set; otherwise show raw heap order labeled "heap order." Cautious by default, precise when the contract supplies the key.
3. **Where does T2 code live?** **Direction set:** short-term a `graph_projection` fixture may inline `code`; long-term a fixture references a `canonical_code_id` into a small verified code library keyed by algorithm family (mirroring the Example Spec's move toward canonical code as the application definition, not an LLM artifact). Build inline first, migrate to `canonical_code_id` once ≥2 families exist.
4. **Multi-loop milestone collapse.** **Direction set:** ship "collapse on projected-state-change" with no per-algorithm logic; validate against a *real Dijkstra/Prim trace* (§15 test 2). Add an optional `milestone_hint` field **only if** Dijkstra's inner relaxation reads poorly — never a per-algorithm branch.

---

## §18 System consistency rules

The invariants that hold across `EXAMPLE_SYSTEM_SPEC.md`, `VISUAL_SYSTEM_SPEC.md`, and this spec. They are the enforceable contract that keeps examples and visuals consistent and improvable.

1. **A visual model must declare its `state_source` / `tier`** (§10.1). No model is anonymous about where its state came from.
2. **A worked-example visual must be derived from the same trace as its prose** (§6.4 INV-PROSE-SYNC). One trace, one truth, both panels.
3. **A code worked example with a diagram must share `event_id`s between code and diagram** (§6.4 INV-DUAL-SLOT). Sync is by event, not frame index.
4. **LLM output may fill prose, code/input proposals for validated tiers, or projection proposals — never per-frame visual state.** The model proposes; the tracer and validators dispose (§9).
5. **User feedback may patch projection / input / code / milestone or prose policy — never raw frame highlights** (§11.1). This is what keeps a fix holistic.
6. **Every fallback to legacy (T5) is observable through telemetry** (§6.2, §14) and marked `legacy_raw` — allowed, never considered "validated."
7. **Every accepted regeneration must re-run the validators before it reaches the learner** (§11.5 Stage 1). No correction ships unverified.
8. **Projector and inference code may not branch on the application/algorithm name** (§8). Algorithm-specific knowledge is data in the profile/fixture, never control flow in shape code.
9. **One name per invariant, everywhere.** The names `INV-DUAL-SLOT` / `INV-RENDER` / `INV-COMPLETE` / `INV-PROSE-SYNC` (and `state_source` / `tier` / `event_id`) are used verbatim in validator errors, telemetry keys, `FeedbackRecord.issue_type` mapping, and test names — never aliased (`prose_mismatch`, `text_sync`, …).

**State-ownership rule (the root invariant):** visual state may come only from (1) a registered simulator, (2) traced code + projection, (3) an inferred projection validated against traced code, or (4) LLM-authored code/input/contract that executes and validates. It may **never** come directly from LLM-authored per-frame highlights. T5 legacy raw is the sole exception, and only as a flagged, never-validated fallback.
