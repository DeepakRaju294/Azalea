"""Validators for v2 visual artifacts.

Five validators, all pure functions. Each returns a list of ValidationIssue;
the orchestrator decides whether to drop the visual, log a warning, or
continue rendering as text-only.

Coexists with all legacy code; never modifies it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.visual_ontology_v2 import (
    BASE_VISUAL_TYPES,
    MODES_BY_BASE_TYPE,
    SUPPORT_VISUALS,
    is_valid_base_type,
    is_valid_mode,
    is_valid_support_visual,
)


# ---------------------------------------------------------------------------
# Issue model
# ---------------------------------------------------------------------------


@dataclass
class ValidationIssue:
    severity: str            # "error" | "warning" | "info"
    code: str                # short stable identifier
    message: str
    location: str = ""       # e.g. "card[2].visual_intent" or "plan-1.steps[3]"


@dataclass
class ValidationReport:
    is_valid: bool = True
    issues: list[ValidationIssue] = field(default_factory=list)

    def add(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)
        if issue.severity == "error":
            self.is_valid = False

    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]


# ---------------------------------------------------------------------------
# VisualIntent
# ---------------------------------------------------------------------------


def validate_visual_intent(
    intent: dict[str, Any] | None,
    location: str = "",
) -> ValidationReport:
    """Check VisualIntent. Intent may legitimately be None for text-only
    cards; that's not an error here."""
    report = ValidationReport()
    if intent is None:
        return report
    if not isinstance(intent, dict):
        report.add(ValidationIssue("error", "intent_not_object", "visual_intent must be an object", location))
        return report

    base_type = str(intent.get("base_type") or "")
    mode = str(intent.get("mode") or "")
    description = str(intent.get("description") or "").strip()
    purpose = str(intent.get("purpose") or "").strip()
    static_or_dynamic = str(intent.get("static_or_dynamic") or "")

    if not base_type:
        report.add(ValidationIssue("error", "intent_missing_base_type", "visual_intent.base_type is empty", location))
    elif not (is_valid_base_type(base_type) or is_valid_support_visual(base_type)):
        report.add(ValidationIssue(
            "error", "intent_unknown_base_type",
            f"base_type='{base_type}' is not a recognized base_type or support_visual",
            location,
        ))
    elif is_valid_base_type(base_type) and not is_valid_mode(base_type, mode):
        report.add(ValidationIssue(
            "warning", "intent_unknown_mode",
            f"mode='{mode}' is not declared under base_type='{base_type}'; "
            "allowed modes: " + ", ".join(MODES_BY_BASE_TYPE.get(base_type, ())),
            location,
        ))

    if not description:
        report.add(ValidationIssue("warning", "intent_empty_description", "visual_intent.description is empty", location))
    if not purpose:
        report.add(ValidationIssue("warning", "intent_empty_purpose", "visual_intent.purpose is empty", location))
    if static_or_dynamic not in ("static", "dynamic"):
        report.add(ValidationIssue(
            "error", "intent_bad_static_or_dynamic",
            f"static_or_dynamic must be 'static' or 'dynamic', got '{static_or_dynamic}'",
            location,
        ))

    return report


# ---------------------------------------------------------------------------
# WorkedExamplePlan
# ---------------------------------------------------------------------------


# Minimum steps allowed for non-boundary topics. Boundary topics (single-node
# trees, empty arrays) may legitimately have 1-2 steps.
_BOUNDARY_KEYWORDS = ("empty", "single", "boundary", "degenerate", "one-node", "one node")


def _is_boundary_plan(plan: dict[str, Any]) -> bool:
    setup = str(plan.get("problem_setup") or "").lower()
    return any(k in setup for k in _BOUNDARY_KEYWORDS)


def validate_worked_example_plan(
    plan: dict[str, Any] | None,
    location: str = "",
) -> ValidationReport:
    report = ValidationReport()
    if plan is None:
        return report
    if not isinstance(plan, dict):
        report.add(ValidationIssue("error", "plan_not_object", "plan must be an object", location))
        return report

    plan_id = str(plan.get("id") or "")
    if not plan_id:
        report.add(ValidationIssue("error", "plan_missing_id", "plan.id is empty", location))

    intent_report = validate_visual_intent(plan.get("visual_intent"), f"{location}.visual_intent")
    for issue in intent_report.issues:
        report.add(issue)

    if not str(plan.get("problem_setup") or "").strip():
        report.add(ValidationIssue("warning", "plan_empty_setup", "plan.problem_setup is empty", location))
    if not str(plan.get("terminal_state") or "").strip():
        report.add(ValidationIssue("warning", "plan_empty_terminal", "plan.terminal_state is empty", location))

    base_state = plan.get("base_state")
    if not isinstance(base_state, dict):
        report.add(ValidationIssue("error", "plan_missing_base_state", "plan.base_state must be an object", location))

    steps = plan.get("steps")
    if not isinstance(steps, list):
        report.add(ValidationIssue("error", "plan_missing_steps", "plan.steps must be an array", location))
        return report
    if not steps:
        report.add(ValidationIssue("error", "plan_no_steps", "plan.steps is empty", location))
        return report

    min_steps = 1 if _is_boundary_plan(plan) else 5
    if len(steps) < min_steps:
        report.add(ValidationIssue(
            "warning", "plan_too_few_steps",
            f"plan has {len(steps)} steps; expected at least {min_steps} for non-boundary topics",
            location,
        ))

    for index, step in enumerate(steps):
        step_loc = f"{location}.steps[{index}]"
        if not isinstance(step, dict):
            report.add(ValidationIssue("error", "step_not_object", "step must be an object", step_loc))
            continue
        if not str(step.get("action") or "").strip():
            report.add(ValidationIssue("warning", "step_empty_action", "step.action is empty", step_loc))
        if not isinstance(step.get("state_after"), dict):
            report.add(ValidationIssue("error", "step_bad_state_after", "step.state_after must be an object", step_loc))

    return report


# ---------------------------------------------------------------------------
# VisualModel
# ---------------------------------------------------------------------------


def validate_visual_model(
    model: dict[str, Any] | None,
    location: str = "",
) -> ValidationReport:
    report = ValidationReport()
    if model is None:
        report.add(ValidationIssue("error", "model_missing", "model is None", location))
        return report
    if not isinstance(model, dict):
        report.add(ValidationIssue("error", "model_not_object", "model must be an object", location))
        return report

    if not str(model.get("id") or ""):
        report.add(ValidationIssue("error", "model_missing_id", "model.id is empty", location))

    base_type = str(model.get("base_type") or "")
    if not is_valid_base_type(base_type):
        report.add(ValidationIssue("error", "model_unknown_base_type", f"model.base_type='{base_type}' is unknown", location))

    frames = model.get("frames")
    if not isinstance(frames, list):
        report.add(ValidationIssue("error", "model_missing_frames", "model.frames must be an array", location))
        return report

    catalog = model.get("element_catalog") or []
    catalog_ids = {str(e.get("element_id") or "") for e in catalog if isinstance(e, dict)}

    # Coordinate stability + element-id consistency check
    seen_element_positions: dict[str, tuple[float, float]] = {}
    for frame_index, frame in enumerate(frames):
        frame_loc = f"{location}.frames[{frame_index}]"
        if not isinstance(frame, dict):
            report.add(ValidationIssue("error", "frame_not_object", "frame must be an object", frame_loc))
            continue
        selectable = frame.get("selectable_elements") or []
        for el in selectable:
            if not isinstance(el, dict):
                continue
            element_id = str(el.get("element_id") or "")
            if not element_id:
                continue
            if catalog_ids and element_id not in catalog_ids:
                # Not an error; catalog may be incomplete. Warning only.
                report.add(ValidationIssue(
                    "info", "selectable_not_in_catalog",
                    f"element_id='{element_id}' on selectable_elements not in element_catalog",
                    frame_loc,
                ))
            # Coordinate stability: same element_id should keep same position
            # across frames. Pointer-style elements legitimately move, so we
            # only warn for nodes/cells/code_lines (types that should be fixed).
            element_type = str(el.get("element_type") or "")
            if element_type in ("node", "cell", "code_line"):
                bounds = el.get("bounds") or {}
                pos = (float(bounds.get("x") or 0.0), float(bounds.get("y") or 0.0))
                if element_id in seen_element_positions:
                    prev = seen_element_positions[element_id]
                    if abs(prev[0] - pos[0]) > 0.5 or abs(prev[1] - pos[1]) > 0.5:
                        report.add(ValidationIssue(
                            "warning", "element_position_unstable",
                            f"element_id='{element_id}' position changed from {prev} to {pos} "
                            "without an explicit move transition (coordinate stability invariant)",
                            frame_loc,
                        ))
                else:
                    seen_element_positions[element_id] = pos

        # Transitions: every target must exist in catalog (if catalog is populated)
        if catalog_ids:
            for t_index, transition in enumerate(frame.get("transitions") or []):
                if not isinstance(transition, dict):
                    continue
                target = str(transition.get("target_element_id") or "")
                if target and target not in catalog_ids:
                    # element_catalog may genuinely lack synthetic ids (highlight_bar etc.) — info only
                    report.add(ValidationIssue(
                        "info", "transition_target_not_in_catalog",
                        f"transition[{t_index}] targets element_id='{target}' not in element_catalog",
                        frame_loc,
                    ))

    return report


# ---------------------------------------------------------------------------
# Cross-source consistency (node_link)
# ---------------------------------------------------------------------------


def validate_node_link_consistency(
    model: dict[str, Any] | None,
    expected_values: set[str] | None = None,
    location: str = "",
) -> ValidationReport:
    """Cross-source consistency check for node_link visual models.

    Structural validators pass a model whose every frame is internally
    well-formed. They do NOT catch the failure mode where the rendered
    structure (`base.nodes`) was drawn from a different source than the trace
    text / problem setup — e.g. a stale background tree holding value 40 while
    the trace visits 5..11. That contradiction only surfaces when you compare
    the base node values against (a) the values each frame references and
    (b) the values declared in the problem setup.

    - `node_link_trace_references_unknown_nodes`: a frame's active/completed/
      runtime value names a node id absent from `base.nodes`.
    - `node_link_base_values_mismatch`: the base node label set is not equal to
      `expected_values` (the problem-setup values). Only checked when
      `expected_values` is provided and non-empty.
    """
    report = ValidationReport()
    if not isinstance(model, dict):
        report.add(ValidationIssue("error", "node_link_model_not_object", "model must be an object", location))
        return report
    if str(model.get("base_type") or "") != "node_link_diagram":
        return report  # not applicable to other base types

    base = model.get("base") or {}
    base_nodes = base.get("nodes") or [] if isinstance(base, dict) else []
    base_ids = {str(n.get("id")) for n in base_nodes if isinstance(n, dict) and n.get("id")}
    base_labels = {
        str(n.get("label") or n.get("id"))
        for n in base_nodes
        if isinstance(n, dict) and (n.get("label") or n.get("id"))
    }
    if not base_ids:
        report.add(ValidationIssue("error", "node_link_base_empty", "model.base.nodes is empty", location))
        return report

    referenced: set[str] = set()
    for frame in model.get("frames") or []:
        if not isinstance(frame, dict):
            continue
        state = frame.get("state") or {}
        if not isinstance(state, dict):
            continue
        active = str(state.get("active_node") or "").strip()
        if active:
            referenced.add(active)
        for node_id in state.get("completed_nodes") or []:
            referenced.add(str(node_id))
        runtime = state.get("runtime_state") or {}
        if isinstance(runtime, dict):
            for key in ("call_stack", "output", "frontier"):
                for value in runtime.get(key) or []:
                    referenced.add(str(value))
    orphans = sorted(referenced - base_ids)
    if orphans:
        report.add(ValidationIssue(
            "error", "node_link_trace_references_unknown_nodes",
            f"trace references node id(s) {orphans} absent from base.nodes "
            f"(base ids: {sorted(base_ids)})",
            location,
        ))

    if expected_values:
        expected = {str(v) for v in expected_values}
        if base_labels != expected:
            report.add(ValidationIssue(
                "error", "node_link_base_values_mismatch",
                f"base node values {sorted(base_labels)} do not match the problem "
                f"setup values {sorted(expected)} "
                f"(missing={sorted(expected - base_labels)}, "
                f"extra={sorted(base_labels - expected)})",
                location,
            ))

    return report


# ---------------------------------------------------------------------------
# RenderStep
# ---------------------------------------------------------------------------


def validate_render_steps(
    render_steps: list[dict[str, Any]],
    visual_models: list[dict[str, Any]],
    location: str = "",
) -> ValidationReport:
    report = ValidationReport()
    if not isinstance(render_steps, list):
        report.add(ValidationIssue("error", "render_steps_not_array", "render_steps must be an array", location))
        return report

    model_by_id = {
        str(m.get("id") or ""): m
        for m in (visual_models or [])
        if isinstance(m, dict)
    }

    for index, step in enumerate(render_steps):
        step_loc = f"{location}.render_steps[{index}]"
        if not isinstance(step, dict):
            report.add(ValidationIssue("error", "render_step_not_object", "step must be an object", step_loc))
            continue

        if not str(step.get("id") or ""):
            report.add(ValidationIssue("error", "render_step_missing_id", "step.id is empty", step_loc))

        visual_model_id = step.get("visual_model_id")
        frame_index = step.get("frame_index")
        support_visual = step.get("support_visual")

        if visual_model_id is not None:
            if visual_model_id not in model_by_id:
                report.add(ValidationIssue(
                    "error", "render_step_unresolved_model",
                    f"visual_model_id='{visual_model_id}' not found in visual_models",
                    step_loc,
                ))
            else:
                model = model_by_id[visual_model_id]
                frames = model.get("frames") or []
                if not isinstance(frame_index, int):
                    report.add(ValidationIssue(
                        "error", "render_step_missing_frame_index",
                        "step.frame_index is required when visual_model_id is set",
                        step_loc,
                    ))
                elif frame_index < 0 or frame_index >= len(frames):
                    report.add(ValidationIssue(
                        "error", "render_step_frame_out_of_range",
                        f"frame_index={frame_index} out of range for model "
                        f"'{visual_model_id}' with {len(frames)} frames",
                        step_loc,
                    ))

        if support_visual is not None:
            support_type = str(support_visual.get("support_type") if isinstance(support_visual, dict) else "")
            if not is_valid_support_visual(support_type):
                report.add(ValidationIssue(
                    "warning", "render_step_unknown_support",
                    f"support_visual.support_type='{support_type}' is not a recognized support visual",
                    step_loc,
                ))

    return report


# ---------------------------------------------------------------------------
# Lesson-level validator (composes the above)
# ---------------------------------------------------------------------------


_VALID_TRANSITION_KINDS = frozenset({
    "move", "fade_in", "fade_out", "appear", "disappear",
    "style_change", "value_change", "swap", "highlight_pulse", "stagger_group",
})

_VALID_TRANSITION_EASING = frozenset({
    "ease", "ease_in", "ease_out", "ease_in_out", "linear", "spring",
})

_VALID_ELEMENT_TYPES = frozenset({
    "node", "edge", "edge_label", "stack_item", "output_item", "frontier_item",
    "cell", "pointer", "range", "code_line", "code_variable", "code_frame",
    "subexpression", "symbol_definition", "row", "column", "row_header", "column_header",
    "axis_label", "curve_segment", "plotted_point", "shaded_region", "tangent_line",
    "shape", "side", "angle", "measurement_label",
    "message", "actor_lane", "time_tick",
    "memory_frame", "heap_object", "pointer_arrow", "variable_binding",
    "set", "region", "element_in_region",
    "hotspot", "support_step",
})


def validate_selectable_elements(
    model: dict[str, Any],
    location: str = "",
) -> ValidationReport:
    """Per-frame SelectableElement structural + identity checks.

    Errors:
      - element_id duplicated within a single frame
      - element_type not in the v2 ontology
      - bounds object missing required fields

    Warnings:
      - keyboard_index sequence not contiguous (Tab order would jump)
      - aria_label empty (screen readers fall back to semantic_label)
    """
    report = ValidationReport()
    frames = model.get("frames") or []
    if not isinstance(frames, list):
        return report

    for frame_index, frame in enumerate(frames):
        if not isinstance(frame, dict):
            continue
        elements = frame.get("selectable_elements") or []
        frame_loc = f"{location}.frames[{frame_index}]"
        seen_ids: set[str] = set()
        keyboard_indices: list[int] = []
        for el in elements:
            if not isinstance(el, dict):
                report.add(ValidationIssue(
                    "error", "selectable_not_object", "selectable element must be an object", frame_loc,
                ))
                continue
            element_id = str(el.get("element_id") or "")
            element_type = str(el.get("element_type") or "")
            if not element_id:
                report.add(ValidationIssue(
                    "error", "selectable_missing_id", "selectable_element.element_id is empty", frame_loc,
                ))
                continue
            if element_id in seen_ids:
                report.add(ValidationIssue(
                    "error", "selectable_duplicate_id",
                    f"element_id '{element_id}' duplicated on this frame",
                    frame_loc,
                ))
            seen_ids.add(element_id)
            if element_type and element_type not in _VALID_ELEMENT_TYPES:
                report.add(ValidationIssue(
                    "warning", "selectable_unknown_type",
                    f"element_type='{element_type}' not in the v2 ontology",
                    frame_loc,
                ))
            bounds = el.get("bounds") or {}
            if not isinstance(bounds, dict):
                report.add(ValidationIssue(
                    "error", "selectable_bad_bounds",
                    "selectable_element.bounds must be an object",
                    frame_loc,
                ))
            else:
                for key in ("x", "y", "width", "height"):
                    if not isinstance(bounds.get(key), (int, float)):
                        report.add(ValidationIssue(
                            "warning", "selectable_bad_bounds_field",
                            f"bounds.{key} missing or non-numeric on element '{element_id}'",
                            frame_loc,
                        ))
                        break
            if not str(el.get("aria_label") or ""):
                report.add(ValidationIssue(
                    "warning", "selectable_empty_aria",
                    f"aria_label empty on element '{element_id}'",
                    frame_loc,
                ))
            ki = el.get("keyboard_index")
            if isinstance(ki, int):
                keyboard_indices.append(ki)

        # Keyboard nav warning: contiguous indices help Tab order
        if keyboard_indices and len(set(keyboard_indices)) < len(keyboard_indices):
            report.add(ValidationIssue(
                "info", "selectable_duplicate_keyboard_index",
                "duplicate keyboard_index values on the same frame (Tab order may behave oddly)",
                frame_loc,
            ))

    return report


def validate_transitions(
    model: dict[str, Any],
    location: str = "",
) -> ValidationReport:
    """Per-frame Transition structural + reference checks.

    Errors:
      - transition.kind not in the v2 kind list
      - transition references an element_id not present in this frame's
        selectable_elements OR the model's element_catalog
      - duration_ms or delay_ms negative

    Warnings:
      - move transition without {from, to} in spec
      - stagger_group with empty group_element_ids
    """
    report = ValidationReport()
    frames = model.get("frames") or []
    if not isinstance(frames, list):
        return report

    catalog_ids = {
        str(entry.get("element_id") or "")
        for entry in (model.get("element_catalog") or [])
        if isinstance(entry, dict)
    }
    catalog_ids.discard("")

    for frame_index, frame in enumerate(frames):
        if not isinstance(frame, dict):
            continue
        transitions = frame.get("transitions") or []
        frame_loc = f"{location}.frames[{frame_index}]"
        frame_element_ids = {
            str(el.get("element_id") or "")
            for el in (frame.get("selectable_elements") or [])
            if isinstance(el, dict)
        }
        frame_element_ids.discard("")
        all_known = catalog_ids | frame_element_ids

        for t_idx, transition in enumerate(transitions):
            if not isinstance(transition, dict):
                report.add(ValidationIssue(
                    "error", "transition_not_object", "transition must be an object", frame_loc,
                ))
                continue
            kind = str(transition.get("kind") or "")
            if kind not in _VALID_TRANSITION_KINDS:
                report.add(ValidationIssue(
                    "error", "transition_unknown_kind",
                    f"transition[{t_idx}].kind='{kind}' is not a valid transition kind",
                    frame_loc,
                ))
            easing = str(transition.get("easing") or "")
            if easing and easing not in _VALID_TRANSITION_EASING:
                report.add(ValidationIssue(
                    "warning", "transition_unknown_easing",
                    f"transition[{t_idx}].easing='{easing}' is not a known easing curve",
                    frame_loc,
                ))
            target = str(transition.get("target_element_id") or "")
            if not target:
                report.add(ValidationIssue(
                    "error", "transition_missing_target",
                    f"transition[{t_idx}].target_element_id is empty",
                    frame_loc,
                ))
            elif all_known and target not in all_known:
                # Some renderer-synthesized overlays (e.g. highlight_bar) may
                # legitimately not appear in the catalog. Info, not error.
                report.add(ValidationIssue(
                    "info", "transition_target_not_in_catalog",
                    f"transition[{t_idx}] target '{target}' not in element_catalog "
                    "or this frame's selectable_elements",
                    frame_loc,
                ))
            for ms_field in ("duration_ms", "delay_ms"):
                value = transition.get(ms_field)
                if isinstance(value, (int, float)) and value < 0:
                    report.add(ValidationIssue(
                        "error", f"transition_negative_{ms_field}",
                        f"transition[{t_idx}].{ms_field}={value} is negative",
                        frame_loc,
                    ))
            spec = transition.get("spec") or {}
            if kind == "move" and isinstance(spec, dict):
                if "from" not in spec or "to" not in spec:
                    report.add(ValidationIssue(
                        "warning", "transition_move_missing_endpoints",
                        f"transition[{t_idx}] is a move but spec lacks from/to",
                        frame_loc,
                    ))
            if kind == "stagger_group" and isinstance(spec, dict):
                if not (spec.get("group_element_ids") or []):
                    report.add(ValidationIssue(
                        "warning", "transition_stagger_empty",
                        f"transition[{t_idx}] is a stagger_group with no group_element_ids",
                        frame_loc,
                    ))

    return report


def validate_lesson_v2(lesson: dict[str, Any]) -> ValidationReport:
    """Run every validator against a compiled LessonV2 and collate issues.

    The orchestrator calls this after compile_lesson_v2 returns. Errors
    cause the orchestrator to log + degrade the lesson (drop offending
    visuals); warnings + info pass through.
    """
    report = ValidationReport()
    if not isinstance(lesson, dict):
        report.add(ValidationIssue("error", "lesson_not_object", "lesson must be an object"))
        return report

    visual_models = lesson.get("visual_models") or []
    for index, model in enumerate(visual_models):
        loc = f"visual_models[{index}]"
        for sub_report in (
            validate_visual_model(model, location=loc),
            validate_selectable_elements(model, location=loc),
            validate_transitions(model, location=loc),
        ):
            for issue in sub_report.issues:
                report.add(issue)

    render_step_report = validate_render_steps(
        lesson.get("render_steps") or [],
        visual_models,
    )
    for issue in render_step_report.issues:
        report.add(issue)

    return report
