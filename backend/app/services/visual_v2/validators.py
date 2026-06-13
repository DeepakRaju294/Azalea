"""Validator stages (VISUAL_SYSTEM_SPEC §6.4) — the deterministic ones.

Pre-trace example invariants live in example_invariants.py. Here: the TRACE
validator (structural state invariants), the MODEL validator (frontend-shape), and
the PedagogicalVisualValidator (teaching gates), plus the repair→warn→reject
ladder verdict. TextVisualSyncValidator (prose) arrives with Slice 4.
"""
from __future__ import annotations

from typing import Any

from .delta_fold import DeltaFoldEngine, InvalidDeltaError
from .profiles import delta_vocabulary

GENERIC_LABELS = {"node", "edge", "step", "concept", "item", "thing", "element"}


def validate_trace(trace: dict[str, Any], valid_ids: set[str], mode: str) -> list[str]:
    """Structural invariants that hold for ANY trace (§3.5)."""
    errors: list[str] = []
    steps = list(trace.get("steps") or [])
    for i, step in enumerate(steps):
        delta = step.get("delta") or {}
        if not delta:
            errors.append(f"step {i}: empty delta (use an explicit no_op with a reason)")

    try:
        frames = DeltaFoldEngine().fold(
            trace.get("initial_state") or {}, steps, valid_ids, delta_vocabulary(mode)
        )
    except InvalidDeltaError as exc:
        errors.append(str(exc))
        return errors

    prev_visited: set[str] = set(((trace.get("initial_state") or {}).get("visited")) or [])
    for frame in frames:
        current = set(frame["state_after"].get("visited") or [])
        if not prev_visited <= current:
            errors.append(f"step {frame['step_index']}: visited set shrank (not monotonic)")
        active = frame["state_after"].get("active")
        if active is not None and active not in valid_ids:
            errors.append(f"step {frame['step_index']}: active {active!r} is not a real node")
        prev_visited = current
    return errors


def validate_model(model: dict[str, Any]) -> list[str]:
    """FrontendContract-shape: a renderer can consume this without inferring. The
    node-stability checks are node_link-specific; other base types get the common
    shape check (has a base + at least one frame with a state)."""
    errors: list[str] = []
    base = model.get("base") or {}
    frames = model.get("frames") or []
    if not frames:
        errors.append("model has no frames")

    # Absent base_type defaults to the node_link (strict) path — preserves the
    # original contract; only an EXPLICIT non-graph base_type takes the light path.
    if str(model.get("base_type") or "node_link_diagram") != "node_link_diagram":
        if not base:
            errors.append("model.base is empty")
        if any("state" not in (f or {}) for f in frames):
            errors.append("a frame is missing its state")
        return errors

    nodes = base.get("nodes") or []
    if not nodes:
        errors.append("model.base has no nodes")
    if any("id" not in n for n in nodes):
        errors.append("a base node is missing an id")
    node_id_sets = []
    for fi, frame in enumerate(frames):
        state = frame.get("state") or {}
        if "active_node" not in state or "node_state_map" not in state:
            errors.append(f"frame {fi}: missing active_node/node_state_map")
            continue
        node_id_sets.append(frozenset(e["node_id"] for e in state["node_state_map"]))
    # Element ids must be stable across frames (no invented/dropped nodes).
    if node_id_sets and len(set(node_id_sets)) > 1:
        errors.append("unstable node ids across frames")
    return errors


def pedagogical_check(model: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    """§5.6 — rejects schema-valid-but-useless visuals. Returns a ladder verdict.

    The node-richness/label checks are node_link-specific; for other base types the
    pre-trace ExampleInvariantValidator already enforced richness (min_length /
    min_cells), so this returns ok rather than re-judging a different shape."""
    if str(model.get("base_type") or "node_link_diagram") != "node_link_diagram":
        return {"verdict": "ok", "issues": []}

    issues: list[tuple[str, str]] = []  # (severity, message); severity in repair|warn|reject
    nodes = (model.get("base") or {}).get("nodes") or []

    min_nodes = int((profile.get("richness") or {}).get("min_nodes", 0))
    if len(nodes) < min_nodes:
        issues.append(("reject", f"too trivial: {len(nodes)} nodes < floor {min_nodes}"))
    if len(nodes) == 1:
        issues.append(("reject", "single-node structural visual"))

    for n in nodes:
        label = str(n.get("label", "")).strip().lower()
        if label in GENERIC_LABELS:
            issues.append(("reject", f"generic label {label!r} instead of a data value"))
            break

    severities = {sev for sev, _ in issues}
    verdict = "reject" if "reject" in severities else ("warn" if "warn" in severities else "ok")
    return {"verdict": verdict, "issues": issues}


# ---------------------------------------------------------------------------
# Projector guardrail (PROJECTOR_SYSTEM_SPEC §6.1, §6.4 INV-RENDER/INV-COMPLETE).
# These run on the COMPUTED path (Path A) so a node_link worked example can never
# render with empty/static/malformed/truncated state. They apply only to node_link
# models; other shapes return [] (their richness is gated pre-trace).
# ---------------------------------------------------------------------------

_TRIVIAL_NODE_STATES = {"", "unvisited"}


def _is_node_link(model: dict[str, Any]) -> bool:
    return str(model.get("base_type") or "node_link_diagram") == "node_link_diagram"


def validate_node_link_state(model: dict[str, Any]) -> list[str]:
    """§6.1 — per-step node state must be non-empty, reference real nodes, and change
    across the sequence (a static highlight means there is no real trace)."""
    if not _is_node_link(model):
        return []
    errors: list[str] = []
    node_ids = {str(n.get("id")) for n in (model.get("base") or {}).get("nodes") or []}
    frames = model.get("frames") or []
    signatures: list[tuple] = []
    any_nonempty = False
    for fi, frame in enumerate(frames):
        state = frame.get("state") or {}
        nsm = state.get("node_state_map") or []
        active = str(state.get("active_node") or "")
        if active and active not in node_ids:
            errors.append(f"frame {fi}: active_node {active!r} is not a real node")
        live = {str(e.get("node_id")) for e in nsm if str(e.get("state") or "") not in _TRIVIAL_NODE_STATES}
        for e in nsm:
            if str(e.get("node_id")) not in node_ids:
                errors.append(f"frame {fi}: node_state_map references unknown node {e.get('node_id')!r}")
        if active:
            live.add(active)
        if live:
            any_nonempty = True
        signatures.append((active, frozenset((str(e.get("node_id")), str(e.get("state"))) for e in nsm)))
    if frames and not any_nonempty:
        errors.append("empty_node_state: no node is ever active/visited across the worked example")
    if len(frames) > 1 and len(set(signatures)) == 1:
        errors.append("static_state: per-step node state never changes across frames")
    return errors


def validate_node_link_render(model: dict[str, Any]) -> list[str]:
    """INV-RENDER — structural & label correctness of the rendered graph: real,
    uniquely-labelled nodes and edges that reference existing nodes."""
    if not _is_node_link(model):
        return []
    errors: list[str] = []
    base = model.get("base") or {}
    nodes = base.get("nodes") or []
    edges = base.get("edges") or []
    node_ids: set[str] = set()
    labels: list[str] = []
    for n in nodes:
        nid = str(n.get("id") or "")
        if not nid:
            errors.append("INV-RENDER: a node has no id")
            continue
        if nid in node_ids:
            errors.append(f"INV-RENDER: duplicate node id {nid!r}")
        node_ids.add(nid)
        label = str(n.get("label") or "").strip()
        if not label:
            errors.append(f"INV-RENDER: node {nid!r} has a blank label")
        elif label.lower() in GENERIC_LABELS:
            errors.append(f"INV-RENDER: node {nid!r} has placeholder label {label!r}")
        labels.append(label)
    dupes = sorted({lbl for lbl in labels if lbl and labels.count(lbl) > 1})
    if dupes:
        errors.append(f"INV-RENDER: duplicate node labels {dupes}")
    seen: set[frozenset] = set()
    for e in edges:
        a, b = str(e.get("from") or ""), str(e.get("to") or "")
        if a not in node_ids or b not in node_ids:
            errors.append(f"INV-RENDER: edge {a!r}->{b!r} references a node not in the graph")
        key = frozenset((a, b))
        if key in seen:
            errors.append(f"INV-RENDER: duplicate edge {a!r}-{b!r}")
        seen.add(key)
    return errors


def validate_completeness(model: dict[str, Any], expected_output: Any) -> list[str]:
    """INV-COMPLETE — the worked example reaches a terminal state; it never stops
    "midway" with nothing. When `expected_output` names graph nodes, the terminal set
    must cover the ones present in the graph. (The strong per-shape equality check for
    code/sequence lands with the projector route; here we guard node_link.)"""
    if not _is_node_link(model):
        return []
    frames = model.get("frames") or []
    if len(frames) <= 1:
        return []
    final = frames[-1].get("state") or {}
    # The terminal set is everything the final frame "owns": completed + output + the
    # still-active node (the last-visited node is usually `current`, not yet completed).
    terminal: set[str] = {str(x) for x in (final.get("completed_nodes") or [])}
    terminal |= {str(x) for x in ((final.get("runtime_state") or {}).get("output") or [])}
    if final.get("active_node"):
        terminal.add(str(final["active_node"]))
    if not terminal:
        return ["INV-COMPLETE: worked example ends with no terminal state (truncated before completion)"]
    if isinstance(expected_output, (list, tuple, set)):
        base_ids = {str(n.get("id")) for n in (model.get("base") or {}).get("nodes") or []}
        want = {str(x) for x in expected_output} & base_ids
        missing = want - terminal
        if want and missing:
            return [f"INV-COMPLETE: terminal state missing expected nodes {sorted(missing)}"]
    return []


def validate_visual_invariants(model: dict[str, Any], expected_output: Any = None) -> list[str]:
    """Run the full computed-path guardrail (§6.1 + INV-RENDER + INV-COMPLETE) and
    return all errors, each prefixed by its invariant. Empty list ⇒ the model is safe
    to render."""
    return (
        validate_node_link_state(model)
        + validate_node_link_render(model)
        + validate_completeness(model, expected_output)
    )


def validate_dual_slot(card: dict[str, Any]) -> list[str]:
    """INV-DUAL-SLOT (PROJECTOR_SYSTEM_SPEC §6.4): a CODE worked example must also fill
    the diagram slot, and if both slots name an `event_id` they must match (sync is by
    event, not frame index). No-op for non-code or non-worked-example cards."""
    if str(card.get("blueprint_key") or card.get("card_type") or "").lower() != "worked_example":
        return []
    is_code = bool(card.get("code_snippet")) or card.get("visual_type") in ("code_trace", "code_execution_panel")
    if not is_code:
        return []
    errors: list[str] = []
    diagram_ref = card.get("diagram_v2_ref") or {}
    if not diagram_ref.get("visual_model_id"):
        errors.append("INV-DUAL-SLOT: code worked example has no supporting diagram slot")
    code_ev = (card.get("visual_v2_ref") or {}).get("event_id")
    diagram_ev = diagram_ref.get("event_id")
    if code_ev and diagram_ev and code_ev != diagram_ev:
        errors.append(f"INV-DUAL-SLOT: code/diagram slots desynced ({code_ev} != {diagram_ev})")
    return errors


def node_link_state_is_empty(model: dict[str, Any]) -> bool:
    """§6.2 detection — True when a node_link model has NO non-trivial per-step state
    across all frames (the MST-style "nothing highlights" failure). Used by the legacy
    bridge to flag + apply the T5 text-only display policy."""
    if not _is_node_link(model):
        return False
    frames = model.get("frames") or []
    if not frames:
        return True
    for frame in frames:
        state = frame.get("state") or {}
        if str(state.get("active_node") or ""):
            return False
        for e in state.get("node_state_map") or []:
            if str(e.get("state") or "") not in _TRIVIAL_NODE_STATES:
                return False
    return True
