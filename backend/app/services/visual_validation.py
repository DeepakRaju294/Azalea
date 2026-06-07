from __future__ import annotations

from typing import Any


TEXT_ONLY_VISUAL_TYPES = {
    "concept_table",
    "comparison_table",
    "formula_card",
    "formula_breakdown",
    "source_annotation",
    "learning_path",
    "path_map",
    "practice_feedback",
}


def validate_and_repair_lesson_visuals(
    lesson_json: dict[str, Any],
) -> dict[str, Any]:
    visuals = lesson_json.get("visual_plan")
    if not isinstance(visuals, list):
        lesson_json["visual_plan"] = []
        return build_report(
            removed_count=0,
            repaired_card_count=0,
            issues=["visual_plan was not a list; reset to empty list."],
        )

    valid_visuals: list[dict[str, Any]] = []
    index_map: dict[int, int] = {}
    issues: list[str] = []

    for old_index, visual in enumerate(visuals):
        if not isinstance(visual, dict):
            issues.append(f"Removed visual {old_index}: visual item was not an object.")
            continue

        issue = visual_rejection_reason(visual)
        if issue:
            issues.append(f"Removed visual {old_index}: {issue}")
            continue

        index_map[old_index] = len(valid_visuals)
        valid_visuals.append(visual)

    lesson_json["visual_plan"] = valid_visuals
    repaired_card_count = repair_card_visual_references(
        lesson_json=lesson_json,
        index_map=index_map,
        issues=issues,
    )

    report = build_report(
        removed_count=len(visuals) - len(valid_visuals),
        repaired_card_count=repaired_card_count,
        issues=issues,
    )
    lesson_json["visual_validation_report"] = report

    return report


def repair_card_visual_references(
    lesson_json: dict[str, Any],
    index_map: dict[int, int],
    issues: list[str],
) -> int:
    cards = lesson_json.get("lesson_cards")
    if not isinstance(cards, list):
        return 0

    repaired_count = 0
    valid_visual_count = len(lesson_json.get("visual_plan") or [])

    for card_index, card in enumerate(cards):
        if not isinstance(card, dict):
            continue

        visual_index = coerce_int(card.get("visual_index"), -1)
        if visual_index >= 0:
            if visual_index in index_map:
                new_index = index_map[visual_index]
                if new_index != visual_index:
                    card["visual_index"] = new_index
                    repaired_count += 1
            else:
                card["visual_index"] = -1
                repaired_count += 1
                issues.append(
                    f"Cleared visual_index on card {card_index}: referenced removed or missing visual {visual_index}."
                )

        if card.get("visual_index", -1) >= valid_visual_count:
            card["visual_index"] = -1
            repaired_count += 1
            issues.append(
                f"Cleared visual_index on card {card_index}: reference exceeded visual_plan length."
            )

        card_visual = card.get("visual_plan")
        if isinstance(card_visual, dict):
            issue = visual_rejection_reason(card_visual, per_card=True)
            if issue:
                card["visual_plan"] = {}
                repaired_count += 1
                issues.append(f"Removed per-card visual on card {card_index}: {issue}")

    return repaired_count


def visual_rejection_reason(visual: dict[str, Any], per_card: bool = False) -> str | None:
    visual_type = normalize_type(visual.get("type") or visual.get("kind"))

    if not visual_type:
        return "missing visual type."

    if is_text_only_visual_type(visual_type):
        return (
            f"{visual_type} is styled/text content, not a non-text visual; render it with lesson cards, LaTeX, or styled UI."
        )

    if is_formula_visual_type(visual_type):
        return "formulas/equations must be rendered as LaTeX, not visual_plan items."

    if is_table_visual_type(visual_type):
        return "tables/comparison grids must be rendered as styled UI, not visual_plan items."

    if is_concept_map_visual_type(visual_type):
        return "concept maps are text-first visuals; use styled content unless this is a real node-link structure."

    if is_node_link_visual_type(visual_type) and not has_node_link_data(visual):
        return "node-link visual has no renderable nodes/edges."

    if is_graph_visual_type(visual_type) and not has_graph_data(visual):
        return "graph visual has fewer than two data_points."

    if is_circuit_visual_type(visual_type) and not has_circuit_data(visual):
        return "circuit visual has no renderable components or wires."

    if is_code_trace_visual_type(visual_type) and not has_code_trace_data(visual):
        return "code trace visual has no code."

    if not per_card and is_blank_visual(visual):
        return "visual has no meaningful renderable data."

    return None


def normalize_type(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")


def is_text_only_visual_type(visual_type: str) -> bool:
    return visual_type in TEXT_ONLY_VISUAL_TYPES


def is_formula_visual_type(visual_type: str) -> bool:
    return "formula" in visual_type or "equation" in visual_type


def is_table_visual_type(visual_type: str) -> bool:
    return (
        "table" in visual_type
        or "matrix" in visual_type
        or "checklist" in visual_type
        or "comparison" in visual_type
    )


def is_concept_map_visual_type(visual_type: str) -> bool:
    return "concept_map" in visual_type or "concept_structure" in visual_type


def is_node_link_visual_type(visual_type: str) -> bool:
    markers = (
        "node_link",
        "tree",
        "bst",
        "binary_tree",
        "graph_diagram",
        "linked_node",
        "traversal_diagram",
    )
    return any(marker in visual_type for marker in markers)


def is_graph_visual_type(visual_type: str) -> bool:
    markers = (
        "graph",
        "chart",
        "plot",
        "curve",
        "distribution",
        "histogram",
        "scatter",
        "growth_rate",
        "area_under_curve",
        "runtime_growth",
        "loss_curve",
    )
    return any(marker in visual_type for marker in markers) and not is_node_link_visual_type(visual_type)


def is_circuit_visual_type(visual_type: str) -> bool:
    markers = ("circuit", "logic_gate", "schematic", "digital_logic", "hardware")
    return any(marker in visual_type for marker in markers)


def is_code_trace_visual_type(visual_type: str) -> bool:
    markers = ("code_trace", "code_block", "coding_visual", "dry_run")
    return any(marker in visual_type for marker in markers)


# Backward-compatible alias for callers that still use the old name.
is_code_block_visual_type = is_code_trace_visual_type


def has_node_link_data(visual: dict[str, Any]) -> bool:
    nodes = visual.get("nodes")
    edges = visual.get("edges")
    return isinstance(nodes, list) and len(nodes) > 0 and isinstance(edges, list)


def has_graph_data(visual: dict[str, Any]) -> bool:
    data_points = visual.get("data_points")
    return isinstance(data_points, list) and len(data_points) >= 2


def has_circuit_data(visual: dict[str, Any]) -> bool:
    components = visual.get("components")
    wires = visual.get("wires")
    return (
        isinstance(components, list)
        and len(components) > 0
        and isinstance(wires, list)
        and len(wires) > 0
    )


def has_code_trace_data(visual: dict[str, Any]) -> bool:
    code = str(visual.get("code") or "").strip()
    return bool(code)


# Backward-compatible alias for callers that still use the old name.
has_code_block_data = has_code_trace_data


def is_blank_visual(visual: dict[str, Any]) -> bool:
    meaningful_keys = (
        "nodes",
        "edges",
        "data_points",
        "key_points",
        "components",
        "wires",
        "code",
        "columns",
        "rows",
        "steps",
        "elements",
        "labels",
        "interactive_parameter",
        "spatial_diagram",
    )
    for key in meaningful_keys:
        value = visual.get(key)
        if isinstance(value, list) and value:
            return False
        if isinstance(value, str) and value.strip():
            return False
        if isinstance(value, dict) and value:
            return False
    return True


def coerce_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def build_report(
    removed_count: int,
    repaired_card_count: int,
    issues: list[str],
) -> dict[str, Any]:
    return {
        "passed": not issues,
        "removed_visual_count": removed_count,
        "repaired_card_count": repaired_card_count,
        "issues": issues,
        "requires_regeneration": any(is_regeneration_worthy(issue) for issue in issues),
    }


def is_regeneration_worthy(issue: str) -> bool:
    return any(
        marker in issue
        for marker in (
            "node-link visual has no renderable",
            "graph visual has fewer",
            "circuit visual has no renderable",
        )
    )
