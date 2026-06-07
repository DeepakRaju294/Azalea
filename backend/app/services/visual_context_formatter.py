"""Visual context formatter.

Takes a VisualContextPayload from the frontend (learner clicked an element
in a visual + their question) and produces a natural-language prefix the
chat LLM receives ahead of the question. The prefix gives the model
enough context to answer specifically about that element.

Pure functions; no LLM call, no DB lookup. The caller injects the
formatted_context into the chat prompt.
"""

from __future__ import annotations

from typing import Any


def format_visual_context(payload: dict[str, Any]) -> str:
    """Produce a one-paragraph context summary the chat LLM can read.

    Input matches VisualContextPayload TypedDict (from visual_v2.py).
    Output is a single paragraph suitable for prepending to the chat prompt.
    """
    element = payload.get("element") or {}
    surrounding_state = payload.get("surrounding_state") or {}
    base_type = str(payload.get("base_type") or "")
    mode = str(payload.get("mode") or "")
    frame_index = int(payload.get("frame_index") or 0)

    element_type = str(element.get("element_type") or "element")
    semantic_label = str(element.get("semantic_label") or "")
    element_payload = element.get("payload") or {}

    parts: list[str] = []

    # Whole-visual question (explicit "explain this whole visual" button)
    if bool(element_payload.get("whole_visual")):
        parts.append(
            f"The learner asked for a high-level explanation of the entire "
            f"{base_type} visual (mode={mode}) at step {frame_index + 1}. "
            f"Explain what this visual is showing, what the structure is, "
            f"and what the learner should be paying attention to right now. "
            f"Do not focus on a single element; describe the whole scene."
        )
        parts.append(_format_surrounding_state_summary(surrounding_state, base_type))
        return " ".join(p for p in parts if p)

    parts.append(
        f"The learner clicked a {element_type} in the {base_type} "
        f"(mode={mode}) visual at step {frame_index + 1}."
    )

    if semantic_label:
        parts.append(f"The {element_type} they clicked: {semantic_label}.")

    # Add base-type-specific context
    if base_type == "node_link_diagram":
        parts.append(_format_node_link_context(element, element_payload, surrounding_state))
    elif base_type == "indexed_sequence_diagram":
        parts.append(_format_indexed_sequence_context(element, element_payload, surrounding_state))
    elif base_type == "code_execution_panel":
        parts.append(_format_code_execution_context(element, element_payload, surrounding_state))
    else:
        # Generic fallback
        if element_payload:
            payload_summary = ", ".join(
                f"{k}={v}" for k, v in element_payload.items()
            )
            parts.append(f"Element data: {payload_summary}.")

    # Surrounding state — short summary so the model knows where in the trace
    parts.append(_format_surrounding_state_summary(surrounding_state, base_type))

    parts.append(
        "Answer the learner's question specifically about this element. "
        "Reference its current state, what role it plays, and what the "
        "algorithm/structure is doing to it right now."
    )

    return " ".join(p for p in parts if p)


def _format_node_link_context(
    element: dict[str, Any],
    payload: dict[str, Any],
    state: dict[str, Any],
) -> str:
    element_type = str(element.get("element_type") or "")
    if element_type == "node":
        node_id = str(payload.get("node_id") or "")
        node_state = str(payload.get("state") or "unvisited")
        relation = str(payload.get("relation") or "")
        active = str(state.get("active_node") or "")
        is_active = node_id == active
        bits = [f"Node {node_id} (label={payload.get('label')})"]
        if relation:
            bits.append(f"role={relation}")
        bits.append(f"state={node_state}")
        if is_active:
            bits.append("currently being processed")
        return ", ".join(bits) + "."
    if element_type == "edge":
        from_id = str(payload.get("from") or "")
        to_id = str(payload.get("to") or "")
        edge_state = str(payload.get("state") or "unchecked")
        return f"Edge from {from_id} to {to_id}, state={edge_state}."
    if element_type == "stack_item":
        depth = payload.get("depth")
        value = payload.get("value")
        return f"Call stack entry at depth {depth}, value={value}."
    if element_type == "output_item":
        index = payload.get("index")
        value = payload.get("value")
        return f"Output entry at position {index}, value={value}."
    return ""


def _format_indexed_sequence_context(
    element: dict[str, Any],
    payload: dict[str, Any],
    state: dict[str, Any],
) -> str:
    element_type = str(element.get("element_type") or "")
    if element_type == "cell":
        index = payload.get("index")
        value = payload.get("value")
        return f"Cell at index {index} holds value {value}."
    if element_type == "pointer":
        pid = str(payload.get("id") or "")
        pos = payload.get("position")
        return f"Pointer '{pid}' currently at position {pos}."
    return ""


def _format_code_execution_context(
    element: dict[str, Any],
    payload: dict[str, Any],
    state: dict[str, Any],
) -> str:
    element_type = str(element.get("element_type") or "")
    if element_type == "code_line":
        line_number = payload.get("line_number")
        highlight = state.get("highlight_lines") or [0, 0]
        is_active = (
            isinstance(highlight, list)
            and len(highlight) == 2
            and highlight[0] <= int(line_number or 0) <= highlight[1]
        )
        return (
            f"Code line {line_number}."
            + (" This line is currently executing." if is_active else "")
        )
    if element_type == "code_variable":
        name = payload.get("name")
        value = payload.get("value")
        return f"Variable '{name}' currently equals {value}."
    return ""


def _format_surrounding_state_summary(
    state: dict[str, Any],
    base_type: str,
) -> str:
    if base_type == "node_link_diagram":
        runtime = state.get("runtime_state") or {}
        stack = runtime.get("call_stack") or []
        output = runtime.get("output") or []
        frontier = runtime.get("frontier") or []
        bits: list[str] = []
        if state.get("active_node"):
            bits.append(f"active_node={state['active_node']}")
        if stack:
            bits.append(f"call_stack=[{', '.join(str(x) for x in stack)}]")
        if frontier:
            kind = runtime.get("frontier_kind") or "frontier"
            bits.append(f"{kind}=[{', '.join(str(x) for x in frontier)}]")
        if output:
            bits.append(f"output=[{', '.join(str(x) for x in output)}]")
        if bits:
            return "Trace state: " + "; ".join(bits) + "."
    if base_type == "indexed_sequence_diagram":
        pointers = state.get("pointers") or []
        if pointers:
            ptr_strs = [f"{p.get('id')}={p.get('position')}" for p in pointers if isinstance(p, dict)]
            return f"Pointers: {', '.join(ptr_strs)}."
    if base_type == "code_execution_panel":
        variables = state.get("variables") or []
        if variables:
            var_strs = [
                f"{v.get('name')}={v.get('value')}"
                for v in variables
                if isinstance(v, dict) and v.get("name")
            ]
            return f"Variables: {', '.join(var_strs)}."
    return ""
