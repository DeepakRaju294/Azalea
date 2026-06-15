"""Attach v2 VisualModels to legacy lesson_cards.

The legacy lesson shape remains the source of truth for topic/card order,
transitions, continuation cards, and topic-to-topic navigation. This bridge
adds the newer compiled visual payloads alongside that shape:

    lesson_json["visual_models"] = [...]
    card["visual_v2_ref"] = {"visual_model_id": "...", "frame_index": N}

If a v2 compiler cannot produce a model, the legacy card visual_plan remains
untouched and the frontend can continue rendering the older visual.
"""

from __future__ import annotations

import copy
import re
from typing import Any

# Bump when the bridge/gate/diagram logic improves, so cached lessons re-enrich on read
# (lessons.py `lesson_json_needs_hybrid_visual_refresh`). v3 = broadened input extraction
# + drop-reason telemetry + suppress the misleading legacy array_state worked-example guess.
# v4 = re-stamp so lessons stamped at v3 BEFORE the broadened extraction landed (intermediate
# dev-session state) re-run the trace path — the merge-sort worked example was stuck at v3
# with the LLM's divide-only cards because the version wasn't bumped alongside the extraction fix.
# v5 = combine ALL code_snippets so a helper in a separate card (merge sort's `merge`) is
# traceable, + use the real return value for "Final result" (was reading a hardcoded-name
# accumulator that missed `sorted_array`, shipping "Final result: []").
# v6 = worked examples are authored by the problem-first LLM solver (non-code) / code trace
# (code); the example-type/fixture/ontology routing is dropped. Re-enrich so cached
# non-code lessons pick up the solved start-to-finish text breakdown.
# v7 = solver rules strengthened (comprehensive high-level example that exercises the edge
# cases, >5 steps, every decision shown, card structure followed exactly) — re-solve so
# existing non-code lessons pick up the improved text breakdown.
# v8 = solver now authors a RICH per-card visual_description (explicit spec of what each
# step's figure should show) — the Phase-2 visual foundation. Re-solve to populate it.
# v9 = ALL worked examples go through the LLM solver (the line-by-line code-execution trace
# is retired). Coding examples explain execution conceptually (no line numbers) with the code
# shown in an IDE panel. Re-solve so coding lessons drop the old "line N executes" trace cards.
# v10 = setup card states the actual problem (Problem: <concrete input/values>) instead of
# generic filler; generated code is the clean algorithm with no main/driver. Re-solve.
# v11 = collection literals (e.g. [38, 27, 43]) are never split across sub-bullets. Re-solve
# so cached worked examples drop the shredded-array bullets.
# v12 = coding-implementation code is validated; broken code (undefined vars from the
# incremental walkthrough transforms) is replaced by one clean, validated LLM regeneration.
# v13 = solver states the COMPLETE problem (actual values, like a test question) and explains
# EVERY step explicitly — no glossing over recursion/sub-processes. Re-solve to pick it up.
# v14 = code_repair UNIFIES every code card to the longest VALID snippet (fixes a broken
# code_walkthrough when the worked example's code is correct); coding worked example explains
# HOW THE CODE implements each step (loop conditions, branches, appends), not a vague label.
# v15 = solver completeness retry: a too-short worked example (skipped the work, e.g. split ->
# answer) is re-solved once with explicit feedback to walk EVERY step start-to-finish.
# v16 = example blueprint: per-card role + step index/total metadata, and an example_status
# flagging skipped/unfinished examples. Also re-enrichment on the STREAMING read path now keys
# on bridge version (was gated on the retired ontology refresh -> cached lessons never updated).
# v17 = blueprint v2: solver emits a transition per step (prior/decision/action/resulting) +
# expected_final_answer (hidden) + required_cases + expected_steps; validation checks transition
# structure (missing/no-op) and topic-aware step count, not just a global minimum.
# v18 = blueprint v3: decision required in every transition; COVERAGE validation (each step tags
# cases_covered; required_cases must all be exercised); structured final-answer match (the
# blueprint verifies + stamps reaches_final_answer); enforce_transition_contract; visual_delta in
# the contract; full setup metadata; nested example_status.
# v19 = code_repair COMBINES snippets (merge_sort + merge split across cards now validate
# together -> complete code, not a partial valid `merge`); code_walkthrough groups by logical
# block (not <=3 lines) and shows the complete code; per-bullet code highlighting restored.
VISUAL_BRIDGE_VERSION = 19

from app.core.course_blueprints import get_topic_blueprint
from app.schemas.visual_v2 import CompileContext, VisualIntent, VisualModel, WorkedExamplePlan
from app.services.visual_compilers import get_compiler
from app.services.visual_validators_v2 import (
    validate_node_link_consistency,
    validate_visual_model,
)


_SUPPORTED_LEGACY_VISUAL_TYPES: dict[str, tuple[str, str]] = {
    "node_link_diagram": ("node_link_diagram", "tree_hierarchy"),
    "array_state_diagram": ("indexed_sequence_diagram", "array_state"),
    "grid_matrix_diagram": ("grid_matrix_diagram", "matrix"),
    "code_block": ("code_execution_panel", "code_execution_trace"),
    "code_trace": ("code_execution_panel", "code_execution_trace"),
}


_BLUEPRINT_VISUAL_TYPE_MAP: dict[str, tuple[str, str]] = {
    "node_link_diagram": ("node_link_diagram", "tree_hierarchy"),
    "array_state_diagram": ("indexed_sequence_diagram", "array_state"),
    "graph_chart": ("coordinate_graph", "function_curve"),
    "coordinate_graph": ("coordinate_graph", "function_curve"),
    "formula_card": ("formula_symbolic_expression", "formula_breakdown"),
    "comparison_table": ("table_diagram", "comparison_table"),
    "table_diagram": ("table_diagram", "comparison_table"),
    "grid_matrix_diagram": ("grid_matrix_diagram", "matrix"),
    "code_trace": ("code_execution_panel", "code_execution_trace"),
    "code_block": ("code_execution_panel", "code_execution_trace"),
}


_DYNAMIC_TRACE_BASE_TYPES = {
    "node_link_diagram",
    "indexed_sequence_diagram",
    "grid_matrix_diagram",
    "code_execution_panel",
}


def _apply_node_link_empty_state_policy(
    lesson_json: dict[str, Any], context: "CompileContext"
) -> None:
    """§6.2 + T5 display policy (PROJECTOR_SYSTEM_SPEC). A node_link worked-example
    card whose model has empty per-step state (no node ever active/visited — the
    MST-style bug) is (a) recorded as `empty_node_state` telemetry and (b) rendered
    **text-only**: its broken progressive diagram ref is dropped rather than shipped.
    A known-broken visual is worse than none. Failure-safe."""
    try:
        from app.services.visual_v2.invariant_metrics import GLOBAL as INV
        from app.services.visual_v2.validators import node_link_state_is_empty

        models = {
            str(m.get("id")): m
            for m in (lesson_json.get("visual_models") or [])
            if isinstance(m, dict)
        }
        application = str(context.get("topic_hint") or "") or None
        for card in lesson_json.get("lesson_cards") or []:
            if not isinstance(card, dict):
                continue
            if str(card.get("blueprint_key") or card.get("card_type") or "").lower() != "worked_example":
                continue
            ref = card.get("visual_v2_ref") or {}
            model = models.get(str(ref.get("visual_model_id") or ""))
            if model is None or not node_link_state_is_empty(model):
                continue
            INV.record_empty_node_state(application=application)
            card.pop("visual_v2_ref", None)
            meta = card.setdefault("metadata", {})
            if isinstance(meta, dict):
                meta["v2_visual_suppressed"] = "empty_node_state"
    except Exception:  # noqa: BLE001 — telemetry/policy must never break a lesson
        pass


def attach_v2_visuals_to_legacy_lesson(
    lesson_json: dict[str, Any],
    *,
    topic_id: str,
    topic_title: str,
    topic_type: str | None = None,
    visual_domain: str | None = None,
) -> dict[str, Any]:
    """Mutate and return `lesson_json` with v2 visuals attached.

    This is intentionally best-effort. It never removes legacy visual data,
    and it never raises for malformed visual content.
    """
    cards = lesson_json.get("lesson_cards")
    if not isinstance(cards, list) or not cards:
        return lesson_json

    visual_models: list[VisualModel] = []
    already_compiled: dict[str, VisualModel] = {}
    context: CompileContext = {
        "topic_id": str(topic_id),
        "topic_hint": topic_title or "",
        "topic_type": topic_type or "concept_intuition",
        "visual_domain": visual_domain or "general",
        "locale": "en",
        "source_chunks_excerpt": "",
        "already_compiled_models": already_compiled,
    }
    visual_card_rules = _visual_card_rules_for_topic(context["topic_type"])
    _backfill_missing_node_link_structure(cards, context, visual_card_rules)
    _normalize_bst_node_link_visuals(cards, context, visual_card_rules)
    _normalize_node_link_worked_example_scenarios(cards, context, visual_card_rules)
    _attach_shared_problem_setups(cards, context, visual_card_rules)
    blueprint_visual_card_count = sum(
        1
        for card in cards
        if isinstance(card, dict)
        and _blueprint_visual_types_for_card(card, visual_card_rules)
    )

    # Static per-card visuals are the safety net for every visual-bearing
    # legacy card. Dynamic traces can overwrite these refs below, but we do not
    # pre-skip worked examples because synthesis is intentionally best-effort.
    for index, card in enumerate(cards):
        if not isinstance(card, dict):
            continue
        if _has_v2_ref(card):
            continue
        model = _compile_static_card_visual(card, index, context, visual_card_rules)
        if not model:
            continue
        visual_models.append(model)
        already_compiled[model["id"]] = model
        card["visual_v2_ref"] = {
            "visual_model_id": model["id"],
            "frame_index": 0,
            "source": "legacy_static_card",
        }

    # Dynamic visual traces reconstructed from continuation cards.
    dynamic_status_by_base_type: dict[str, str] = {}
    for base_type in (
        "node_link_diagram",
        "indexed_sequence_diagram",
        "grid_matrix_diagram",
        "code_execution_panel",
    ):
        if not _has_blueprint_cards_for_base_type(cards, visual_card_rules, base_type):
            continue
        compiler = get_compiler(base_type)
        if compiler is None:
            dynamic_status_by_base_type[base_type] = "compiler_missing"
            continue
        try:
            plan = compiler.synthesize_plan_from_legacy_cards(cards, context)
        except Exception:
            plan = None
            dynamic_status_by_base_type[base_type] = "plan_exception"
        if not plan:
            dynamic_status_by_base_type.setdefault(base_type, "plan_missing")
            continue

        intent = _intent_from_plan(plan, base_type)
        try:
            model = compiler.compile(intent, plan, context)
        except Exception:
            dynamic_status_by_base_type[base_type] = "compile_exception"
            continue
        if not _is_usable_model(model):
            dynamic_status_by_base_type[base_type] = "model_unusable"
            continue

        # Cross-source consistency: the dynamic node_link base is synthesized
        # from the background card, while the trace text + problem setup were
        # derived from the canonical scenario. If those two provenances have
        # diverged (e.g. a stale background tree holding value 40), drop the
        # dynamic model so cards fall back to the canonicalized static visual
        # rather than rendering a structure that contradicts the trace.
        if base_type == "node_link_diagram":
            consistency = validate_node_link_consistency(
                model,
                expected_values=_expected_node_link_values(cards, visual_card_rules),
                location=f"dynamic.{base_type}",
            )
            if consistency.errors():
                dynamic_status_by_base_type[base_type] = (
                    "consistency_failed:" + consistency.errors()[0].code
                )
                continue

        _enrich_dynamic_model_with_problem_setup(
            model,
            cards,
            base_type,
            visual_card_rules,
        )
        model["id"] = _unique_model_id(model["id"], already_compiled)
        visual_models.append(model)
        already_compiled[model["id"]] = model
        _attach_dynamic_refs(cards, model, base_type, visual_card_rules)
        dynamic_status_by_base_type[base_type] = "attached"

    if visual_models:
        # Provenance (§10.1): anything the legacy bridge built is the T5 `legacy_raw`
        # source. `stamp_if_absent` never relabels a model already stamped by the
        # computed path (e.g. an example-ontology model carried in on the lesson).
        from app.services.visual_v2.provenance import make_provenance, stamp_if_absent

        legacy_provenance = make_provenance("legacy_raw")
        for model in visual_models:
            stamp_if_absent(model, legacy_provenance)

        existing_models = [
            model
            for model in (lesson_json.get("visual_models") or [])
            if isinstance(model, dict)
        ]
        lesson_json["visual_models"] = _filter_referenced_models(
            _dedupe_models(existing_models),
            _dedupe_models(visual_models),
            cards=cards,
        )
        # §6.2 + T5 display policy: a node_link worked example that resolves to empty
        # per-step state (the MST-style "nothing highlights" bug) is flagged AND its
        # broken progressive diagram is suppressed (text-only) rather than shipped.
        _apply_node_link_empty_state_policy(lesson_json, context)
    if visual_models or blueprint_visual_card_count:
        lesson_json.setdefault("metadata", {})
        if isinstance(lesson_json["metadata"], dict):
            lesson_json["metadata"]["visual_v2_bridge"] = {
                "enabled": True,
                "version": VISUAL_BRIDGE_VERSION,
                "model_count": len(lesson_json.get("visual_models") or []),
                "blueprint_visual_card_count": blueprint_visual_card_count,
                "cards_with_v2_ref_count": sum(
                    1
                    for card in cards
                    if isinstance(card, dict) and _has_v2_ref(card)
                ),
                "note": (
                    "Legacy lesson_cards remain canonical; v2 visual_models "
                    "are attached per card according to blueprint visual rules."
                ),
                "dynamic_status_by_base_type": dynamic_status_by_base_type,
                "diagnostics": _diagnose_visual_bridge_cards(
                    cards,
                    visual_card_rules,
                    lesson_json.get("visual_models") or [],
                    dynamic_status_by_base_type,
                ),
            }
            # Opt-in dump of the exact structured payload the frontend renders
            # into each diagram — base nodes/edges + per-frame trace state.
            # Enable with AZALEA_VISUAL_DEBUG=1.
            if _visual_debug_enabled():
                lesson_json["metadata"]["visual_v2_bridge"]["models_debug"] = [
                    _visual_model_debug(model)
                    for model in (lesson_json.get("visual_models") or [])
                    if isinstance(model, dict)
                ]

    return lesson_json


def _compile_static_card_visual(
    card: dict[str, Any],
    index: int,
    context: CompileContext,
    visual_card_rules: dict[str, dict[str, Any]],
) -> VisualModel | None:
    visual_plan = card.get("visual_plan")
    if not isinstance(visual_plan, dict):
        return None

    base_type, mode = _preferred_v2_base_type_for_card(card, visual_card_rules)
    if not base_type:
        return None

    compiler = get_compiler(base_type)
    if compiler is None:
        return None

    plan = _single_frame_plan_from_card(
        card=card,
        visual_plan=visual_plan,
        card_index=index,
        base_type=base_type,
        mode=mode,
    )
    if not plan:
        return None

    intent = _intent_from_plan(plan, base_type)
    try:
        model = compiler.compile(intent, plan, context)
    except Exception:
        return None
    if not _is_usable_model(model):
        return None
    _enrich_model_with_card_problem_setup(model, card)
    model["id"] = f"{base_type}_{context['topic_id']}_card_{index + 1}"
    return model


def _single_frame_plan_from_card(
    *,
    card: dict[str, Any],
    visual_plan: dict[str, Any],
    card_index: int,
    base_type: str,
    mode: str,
) -> WorkedExamplePlan | None:
    description = str(
        visual_plan.get("description")
        or card.get("visual_description")
        or card.get("what_to_notice")
        or card.get("title")
        or ""
    )
    problem_setup = _problem_setup_for_card(card)
    problem_setup_text = _problem_setup_text(problem_setup)
    enriched_description = "\n".join(
        part for part in (problem_setup_text, description) if part.strip()
    )
    intent: VisualIntent = {
        "base_type": base_type,
        "mode": mode,
        "description": enriched_description or description,
        "purpose": str(card.get("learning_goal") or card.get("main_concept") or description),
        "static_or_dynamic": "dynamic",
    }

    if base_type == "node_link_diagram":
        nodes = copy.deepcopy(visual_plan.get("nodes") or [])
        edges = copy.deepcopy(visual_plan.get("edges") or [])
        if not nodes:
            return None
        active_nodes = _string_list((card.get("visual_focus") or {}).get("active_nodes"))
        active_node = active_nodes[0] if active_nodes else ""
        completed = _string_list((card.get("visual_focus") or {}).get("highlight_path"))
        node_state_map = [
            {"node_id": node_id, "state": "completed"}
            for node_id in completed
            if node_id != active_node
        ]
        if active_node:
            node_state_map.append({"node_id": active_node, "state": "current"})
        base_state = {
            "nodes": nodes,
            "edges": edges,
            "visual_blueprint": "",
            "problem_setup": problem_setup,
        }
        # Output/result panel: the traversal result as it grows — every node
        # visited so far (the completed set) plus the current node, shown by value
        # (label) rather than id. Without this the panel stays empty across steps.
        _label_by_id = {
            str(node.get("id")): str(node.get("label") or node.get("id"))
            for node in nodes
            if isinstance(node, dict)
        }
        _output = [_label_by_id.get(node_id, node_id) for node_id in completed]
        if active_node:
            _output.append(_label_by_id.get(active_node, active_node))
        state_after = {
            "active_node": active_node,
            "completed_nodes": completed,
            "node_state_map": node_state_map,
            "active_edge_from": "",
            "active_edge_to": "",
            "completed_edges_from": [],
            "completed_edges_to": [],
            "runtime_state": {"call_stack": [], "output": _output, "frontier": [], "variables": []},
            "attention_note": str(card.get("what_to_notice") or description),
        }
    elif base_type == "indexed_sequence_diagram":
        values = visual_plan.get("array_values") or []
        rows = visual_plan.get("array_rows") or []
        if not values and rows and isinstance(rows, list):
            first_row = rows[0] if rows else []
            values = first_row.get("values") if isinstance(first_row, dict) else first_row
        values = [str(v) for v in (values or []) if str(v).strip()]
        if not values:
            return None
        pointers = []
        for pointer in visual_plan.get("array_pointers") or []:
            if not isinstance(pointer, dict):
                continue
            pid = str(pointer.get("id") or pointer.get("label") or pointer.get("name") or "")
            pos = pointer.get("index", pointer.get("position"))
            if isinstance(pos, int) and 0 <= pos < len(values):
                pointers.append({"id": pid or f"p{len(pointers) + 1}", "position": pos, "label": pid or "p"})
        base_state = {
            "values": values,
            "pointer_definitions": [
                {"id": p["id"], "label": p["label"]}
                for p in pointers
            ],
            "problem_setup": problem_setup,
        }
        state_after = {
            "pointers": pointers,
            "ranges": visual_plan.get("array_ranges") or [],
            "highlighted_cells": [],
            "swapped_cells": None,
            "sorted_prefix_end": None,
        }
    elif base_type == "grid_matrix_diagram":
        rows = visual_plan.get("rows") or []
        columns = visual_plan.get("columns") or []
        normalized_rows = [
            [str(value) for value in row]
            for row in rows
            if isinstance(row, list)
        ]
        if not normalized_rows:
            return None
        # A ragged matrix (rows of differing lengths) misaligns every cell after
        # the short row. Pad to the widest row so the grid is rectangular.
        normalized_rows = _rectangular_rows(normalized_rows)
        base_state = {
            "cells": normalized_rows,
            "column_labels": [str(c) for c in columns],
            "row_labels": [],
            "problem_setup": problem_setup,
        }
        state_after = {
            "active_cell": None,
            "completed_cells": [],
            "dependency_arrows": [],
            "highlighted_row": None,
            "highlighted_column": None,
            "cell_values": {},
        }
    elif base_type == "code_execution_panel":
        code = str(visual_plan.get("code") or card.get("code_snippet") or "").strip()
        if not code:
            return None
        line_count = code.count("\n") + 1
        visible_until_line = _code_visible_until_line(card, visual_plan, line_count)
        base_state = {
            "code": code,
            "language": str(visual_plan.get("language") or card.get("code_language") or "python"),
            "problem_setup": problem_setup,
        }
        state_after = {
            "visible_until_line": visible_until_line,
            "highlight_lines": _first_highlight_range(card, line_count),
            "variables": [],
            "call_stack": [],
            "output": [],
        }
    elif base_type == "formula_symbolic_expression":
        expression = str(visual_plan.get("formula") or visual_plan.get("expression") or "").strip()
        symbols = []
        for raw_symbol in visual_plan.get("symbols") or []:
            if not isinstance(raw_symbol, dict):
                continue
            symbol = str(raw_symbol.get("symbol") or raw_symbol.get("name") or "").strip()
            if not symbol:
                continue
            symbols.append(
                {
                    "symbol": symbol,
                    "meaning": str(
                        raw_symbol.get("meaning")
                        or raw_symbol.get("description")
                        or raw_symbol.get("label")
                        or ""
                    ).strip(),
                    "value": str(raw_symbol.get("value") or "").strip(),
                }
            )
        if not expression and not symbols:
            return None
        base_state = {
            "expression": expression,
            "symbols": symbols,
            "assumptions": [str(item) for item in (visual_plan.get("when_to_use") or [])]
            if isinstance(visual_plan.get("when_to_use"), list)
            else [],
            "problem_setup": problem_setup,
        }
        state_after = {
            "active_symbol": "",
            "active_expression": expression,
            "substitution": {},
            "transformed_expression": expression,
            "equivalence_chain": [expression] if expression else [],
        }
    elif base_type == "table_diagram":
        columns = [str(column) for column in (visual_plan.get("columns") or [])]
        rows = [
            [str(value) for value in row]
            for row in (visual_plan.get("rows") or [])
            if isinstance(row, list)
        ]
        if not columns and not rows:
            return None
        # Force every row to match the column count (pad short, truncate long)
        # so a miscounted row can't shift the table out of alignment.
        if rows:
            rows = _rectangular_rows(rows, width=(len(columns) or None))
        base_state = {
            "columns": columns,
            "rows": rows,
            "row_labels": [],
            "caption": description,
            "problem_setup": problem_setup,
        }
        state_after = {
            "active_row": None,
            "active_cell": None,
            "changed_cells": [],
            "cell_values": {},
        }
    elif base_type == "coordinate_graph":
        points = _coordinate_points(visual_plan)
        curves = _coordinate_curves(visual_plan)
        if not points and not curves:
            return None
        base_state = {
            "axes": {
                "x_min": _float_or_default(visual_plan.get("x_min"), -5.0),
                "x_max": _float_or_default(visual_plan.get("x_max"), 5.0),
                "y_min": _float_or_default(visual_plan.get("y_min"), 0.0),
                "y_max": _float_or_default(visual_plan.get("y_max"), 1.0),
                "x_label": str(visual_plan.get("x_label") or "x"),
                "y_label": str(visual_plan.get("y_label") or "y"),
            },
            "curves": curves,
            "points": points,
            "caption": description,
            "problem_setup": problem_setup,
        }
        active_point = points[0]["id"] if points else None
        active_curve = curves[0]["id"] if curves else None
        state_after = {
            "active_point": active_point,
            "active_curve": active_curve,
            "shaded_region": None,
            "tangent_secant_line": None,
            "active_curve_segment": None,
        }
    else:
        return None

    return {
        "id": f"legacy_card_{card_index + 1}",
        "visual_intent": intent,
        "problem_setup": problem_setup_text or str(card.get("title") or ""),
        "terminal_state": "Card visual complete.",
        "base_state": base_state,
        "steps": [
            {
                "step_number": 1,
                "action": _card_action_title(card, card_index, state_after),
                "reason": str(card.get("learning_job") or ""),
                "text_points": [str(p) for p in (card.get("points") or [])],
                "state_after": state_after,
                "transition_hints": [],
            }
        ],
    }


def _code_visible_until_line(
    card: dict[str, Any],
    visual_plan: dict[str, Any],
    line_count: int,
) -> int:
    value = visual_plan.get("max_line")
    try:
        planned = int(value or 0)
    except (TypeError, ValueError):
        planned = 0
    if planned <= 0:
        snippet = str(card.get("code_snippet") or "").strip("\n")
        planned = len(snippet.splitlines()) if snippet else line_count
    return max(1, min(planned, line_count))


def _card_action_title(
    card: dict[str, Any],
    card_index: int,
    state_after: dict[str, Any],
) -> str:
    title = str(card.get("title") or "").strip()
    if title and not re.fullmatch(r"card\s+\d+", title, flags=re.IGNORECASE):
        return title
    blueprint_key = str(card.get("blueprint_key") or "").strip().lower()
    if blueprint_key == "code_walkthrough":
        line_number = state_after.get("visible_until_line")
        try:
            line_int = int(line_number)
        except (TypeError, ValueError):
            line_int = card_index + 1
        return f"Code Walkthrough: Line {line_int}"
    return f"Step {card_index + 1}"


def _attach_dynamic_refs(
    cards: list[dict[str, Any]],
    model: VisualModel,
    base_type: str,
    visual_card_rules: dict[str, dict[str, Any]],
) -> None:
    preferred_blueprint = (
        "code_walkthrough" if base_type == "code_execution_panel" else "worked_example"
    )
    target_cards = [
        card
        for card in cards
        if isinstance(card, dict)
        and _blueprint_card_allows_base_type(card, visual_card_rules, base_type)
        and str(card.get("blueprint_key") or "").strip().lower() == preferred_blueprint
        and not _is_worked_example_setup_card(card)
    ]
    if not target_cards:
        target_cards = [
            card
            for card in cards
            if isinstance(card, dict)
            and _blueprint_card_allows_base_type(card, visual_card_rules, base_type)
            and not _is_worked_example_setup_card(card)
        ]
        if base_type == "code_execution_panel":
            # Code-execution traces belong on code_walkthrough cards. Never let
            # them fall back onto worked_example cards — those show the
            # data-structure visual (tree/array trace) with the code available
            # on the Diagram/Code toggle. Without this guard, a coding topic with
            # no code_walkthrough cards would attach the code model to the worked
            # example and clobber the node_link tree (rendering code in Diagram).
            target_cards = [
                card
                for card in target_cards
                if str(card.get("blueprint_key") or "").strip().lower() != "worked_example"
            ]
    frames = model.get("frames") or []
    for index, card in enumerate(target_cards[: len(frames)]):
        card["visual_v2_ref"] = {
            "visual_model_id": model["id"],
            "frame_index": index,
            "source": "legacy_dynamic_trace",
        }


def _enrich_dynamic_model_with_problem_setup(
    model: VisualModel,
    cards: list[Any],
    base_type: str,
    visual_card_rules: dict[str, dict[str, Any]],
) -> None:
    preferred_blueprint = (
        "code_walkthrough" if base_type == "code_execution_panel" else "worked_example"
    )
    candidate = next(
        (
            card
            for card in cards
            if isinstance(card, dict)
            and str(card.get("blueprint_key") or "").strip().lower() == preferred_blueprint
            and _blueprint_card_allows_base_type(card, visual_card_rules, base_type)
            and not _is_worked_example_setup_card(card)
            and isinstance(card.get("example_problem"), dict)
        ),
        None,
    )
    if not candidate:
        candidate = next(
            (
                card
                for card in cards
                if isinstance(card, dict)
                and _blueprint_card_allows_base_type(card, visual_card_rules, base_type)
                and not _is_worked_example_setup_card(card)
                and isinstance(card.get("example_problem"), dict)
            ),
            None,
        )
    if not candidate:
        return
    base = model.setdefault("base", {})
    if isinstance(base, dict):
        base["problem_setup"] = copy.deepcopy(candidate["example_problem"])


def _enrich_model_with_card_problem_setup(
    model: VisualModel,
    card: dict[str, Any],
) -> None:
    problem_setup = card.get("example_problem")
    if not isinstance(problem_setup, dict):
        return
    base = model.setdefault("base", {})
    if isinstance(base, dict):
        base["problem_setup"] = copy.deepcopy(problem_setup)


def _should_skip_static_visual_for_dynamic_trace(
    card: dict[str, Any],
    visual_card_rules: dict[str, dict[str, Any]],
) -> bool:
    blueprint_key = str(card.get("blueprint_key") or "").strip().lower()
    if blueprint_key not in {"worked_example", "code_walkthrough"}:
        return False
    return any(
        base_type in _DYNAMIC_TRACE_BASE_TYPES
        for base_type, _ in _allowed_v2_base_types_for_card(card, visual_card_rules)
    )


def _diagnose_visual_bridge_cards(
    cards: list[Any],
    visual_card_rules: dict[str, dict[str, Any]],
    visual_models: list[Any],
    dynamic_status_by_base_type: dict[str, str],
) -> list[dict[str, Any]]:
    model_ids = {
        str(model.get("id"))
        for model in visual_models
        if isinstance(model, dict) and model.get("id")
    }
    diagnostics: list[dict[str, Any]] = []
    for index, card in enumerate(cards):
        if not isinstance(card, dict):
            continue
        allowed = _allowed_v2_base_types_for_card(card, visual_card_rules)
        if not allowed:
            continue

        ref = card.get("visual_v2_ref") if isinstance(card.get("visual_v2_ref"), dict) else {}
        ref_model_id = str(ref.get("visual_model_id") or "")
        base_types = [base_type for base_type, _ in allowed]
        status = "v2_attached" if ref_model_id and ref_model_id in model_ids else "fallback_legacy"
        reason = "attached" if status == "v2_attached" else _fallback_reason_for_card(
            card,
            allowed,
            dynamic_status_by_base_type,
        )
        entry = {
            "card_index": index,
            "card_id": str(card.get("id") or index + 1),
            "blueprint_key": str(card.get("blueprint_key") or ""),
            "title": str(card.get("title") or ""),
            "expected_base_types": base_types,
            "status": status,
            "reason": reason,
            "visual_model_id": ref_model_id,
            "frame_index": ref.get("frame_index") if isinstance(ref, dict) else None,
        }
        diagnostics.append(entry)

        metadata = card.setdefault("metadata", {})
        if isinstance(metadata, dict):
            metadata["visual_v2_bridge"] = {
                "status": status,
                "reason": reason,
                "expected_base_types": base_types,
                "visual_model_id": ref_model_id,
            }
    return diagnostics


def _attach_shared_problem_setups(
    cards: list[Any],
    context: CompileContext,
    visual_card_rules: dict[str, dict[str, Any]],
) -> None:
    """Attach one visible/compiler-readable problem setup per visual card."""
    card_dicts = [card for card in cards if isinstance(card, dict)]
    tree_scenario = _shared_tree_scenario(card_dicts, context, visual_card_rules)

    for card in card_dicts:
        if not _blueprint_visual_types_for_card(card, visual_card_rules):
            continue

        base_type, _ = _preferred_v2_base_type_for_card(card, visual_card_rules)
        if not base_type:
            continue

        if base_type == "node_link_diagram" and tree_scenario:
            setup: dict[str, Any] | None = {
                "kind": "tree_traversal_problem",
                "title": f"{_traversal_label(tree_scenario['traversal'])} Problem",
                "summary": (
                    f"Use the same tree for every step: values "
                    f"{', '.join(tree_scenario['values'])}; root "
                    f"{tree_scenario['root']}."
                ),
                "values": tree_scenario["values"],
                "parameters": {
                    "root": tree_scenario["root"],
                    "traversal": tree_scenario["traversal"],
                    "source": tree_scenario["source"],
                },
                "state": {
                    "visit_order": tree_scenario["order"],
                },
            }
        else:
            setup = _generic_problem_setup_for_card(card, base_type)

        if not setup:
            continue
        card["example_problem"] = setup
        metadata = card.setdefault("metadata", {})
        if isinstance(metadata, dict):
            metadata["example_problem"] = setup


def _shared_tree_scenario(
    cards: list[dict[str, Any]],
    context: CompileContext,
    visual_card_rules: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if not _looks_like_tree_traversal(context):
        return None
    worked_cards = [
        card
        for card in cards
        if str(card.get("blueprint_key") or "").strip().lower() == "worked_example"
        and _blueprint_card_allows_base_type(card, visual_card_rules, "node_link_diagram")
    ]
    visual_cards = [
        card
        for card in cards
        if _blueprint_card_allows_base_type(card, visual_card_rules, "node_link_diagram")
    ]
    scenario = _canonical_tree_scenario(cards, worked_cards or visual_cards, context)
    if not scenario:
        return None
    traversal = _detect_traversal_kind(context, cards)
    order = _tree_visit_order(
        scenario["nodes"],
        scenario["edges"],
        scenario["root_id"],
        traversal,
    )
    return {
        "source": scenario["source"],
        "root": scenario["root_id"],
        "values": [str(node["label"]) for node in scenario["nodes"]],
        "traversal": traversal,
        "order": order,
    }


def _generic_problem_setup_for_card(
    card: dict[str, Any],
    base_type: str,
) -> dict[str, Any] | None:
    visual_plan = card.get("visual_plan") if isinstance(card.get("visual_plan"), dict) else {}
    values: list[str] = []
    parameters: dict[str, Any] = {}

    if base_type == "indexed_sequence_diagram":
        raw_values = visual_plan.get("array_values") or []
        values = [str(value) for value in raw_values if str(value).strip()]
        if visual_plan.get("array_ranges"):
            parameters["ranges"] = visual_plan.get("array_ranges")
        if visual_plan.get("array_pointers"):
            parameters["pointers"] = visual_plan.get("array_pointers")
    elif base_type == "grid_matrix_diagram":
        rows = visual_plan.get("rows") or []
        values = [f"{len(rows)} row grid"] if isinstance(rows, list) and rows else []
        parameters["columns"] = visual_plan.get("columns") or []
    elif base_type == "code_execution_panel":
        parameters["language"] = str(
            visual_plan.get("language") or card.get("code_language") or "python"
        )
        if card.get("example"):
            values = [str(card.get("example"))]
    elif base_type == "formula_symbolic_expression":
        expression = str(
            visual_plan.get("formula") or visual_plan.get("expression") or ""
        ).strip()
        values = [expression] if expression else []
        parameters["symbols"] = visual_plan.get("symbols") or []
    elif base_type == "coordinate_graph":
        parameters["x_label"] = visual_plan.get("x_label") or "x"
        parameters["y_label"] = visual_plan.get("y_label") or "y"
        values = [
            str(point)
            for point in (visual_plan.get("data_points") or visual_plan.get("key_points") or [])
        ][:8]

    summary = _best_problem_summary(card, visual_plan)
    if not summary and not values and not parameters:
        return None

    return {
        "kind": f"{base_type}_problem",
        "title": str(card.get("title") or "Problem setup"),
        "summary": summary,
        "values": values,
        "parameters": parameters,
        "state": {},
    }


def _best_problem_summary(card: dict[str, Any], visual_plan: dict[str, Any]) -> str:
    body = card.get("body")
    if isinstance(body, list):
        for item in body:
            text = str(item).strip()
            if text:
                return text
    visual_description = str(card.get("visual_description") or "").strip()
    if visual_description:
        return visual_description
    for source, key in (
        (visual_plan, "description"),
        (card, "what_to_notice"),
        (card, "main_concept"),
        (card, "learning_goal"),
    ):
        text = str(source.get(key) or "").strip()
        if text:
            return text
    return str(card.get("title") or "").strip()


def _problem_setup_for_card(card: dict[str, Any]) -> dict[str, Any]:
    raw = card.get("example_problem")
    return copy.deepcopy(raw) if isinstance(raw, dict) else {}


def _problem_setup_text(problem_setup: dict[str, Any]) -> str:
    if not problem_setup:
        return ""
    title = str(problem_setup.get("title") or "").strip()
    summary = str(problem_setup.get("summary") or "").strip()
    values = problem_setup.get("values")
    values_text = ""
    if isinstance(values, list) and values:
        values_text = "Values: " + ", ".join(str(value) for value in values[:16])
    parameters = problem_setup.get("parameters")
    parameter_bits: list[str] = []
    if isinstance(parameters, dict):
        for key in ("root", "traversal", "language", "x_label", "y_label"):
            value = parameters.get(key)
            if value not in (None, ""):
                parameter_bits.append(f"{key}={value}")
    parameters_text = "Parameters: " + ", ".join(parameter_bits) if parameter_bits else ""
    return "\n".join(
        part for part in (title, summary, values_text, parameters_text) if part
    )


def _fallback_reason_for_card(
    card: dict[str, Any],
    allowed: list[tuple[str, str]],
    dynamic_status_by_base_type: dict[str, str],
) -> str:
    blueprint_key = str(card.get("blueprint_key") or "").strip().lower()
    base_types = [base_type for base_type, _ in allowed]

    dynamic_base_types = [base_type for base_type in base_types if base_type in _DYNAMIC_TRACE_BASE_TYPES]
    if blueprint_key in {"worked_example", "code_walkthrough"} and dynamic_base_types:
        statuses = [
            dynamic_status_by_base_type.get(base_type)
            for base_type in dynamic_base_types
            if dynamic_status_by_base_type.get(base_type)
        ]
        if statuses:
            return "dynamic_trace_" + statuses[0]
        return "dynamic_trace_not_attempted"

    visual_plan = card.get("visual_plan")
    if not isinstance(visual_plan, dict):
        return "missing_visual_plan"

    if not base_types:
        return "blueprint_visual_type_unmapped"

    if all(get_compiler(base_type) is None for base_type in base_types):
        return "compiler_missing"

    detected = _detect_visual_base_type_from_card_data(card, visual_plan)
    if not detected:
        return _missing_structural_data_reason(base_types[0])
    if detected not in base_types:
        return f"visual_data_shape_mismatch_detected_{detected}"
    return "compile_failed_or_model_unusable"


def _missing_structural_data_reason(base_type: str) -> str:
    return {
        "node_link_diagram": "missing_nodes",
        "indexed_sequence_diagram": "missing_array_values",
        "grid_matrix_diagram": "missing_grid_rows",
        "code_execution_panel": "missing_code",
        "formula_symbolic_expression": "missing_formula_or_symbols",
        "table_diagram": "missing_table_rows",
        "coordinate_graph": "missing_points_or_curves",
    }.get(base_type, "missing_structural_data")


def _visual_card_rules_for_topic(topic_type: str | None) -> dict[str, dict[str, Any]]:
    try:
        blueprint = get_topic_blueprint(topic_type)
    except Exception:
        blueprint = get_topic_blueprint("concept_intuition")
    rules = blueprint.get("visual_card_rules") or {}
    return rules if isinstance(rules, dict) else {}


def _blueprint_visual_rule_for_card(
    card: dict[str, Any],
    visual_card_rules: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    blueprint_key = str(card.get("blueprint_key") or "").strip().lower()
    rule = visual_card_rules.get(blueprint_key) or {}
    return rule if isinstance(rule, dict) else {}


def _blueprint_visual_types_for_card(
    card: dict[str, Any],
    visual_card_rules: dict[str, dict[str, Any]],
) -> list[str]:
    rule = _blueprint_visual_rule_for_card(card, visual_card_rules)
    raw_visual_type = str(rule.get("visual_type") or "").strip()
    if not raw_visual_type or raw_visual_type.lower() == "none":
        return []
    return [
        part.strip().lower()
        for part in raw_visual_type.split("|")
        if part.strip() and part.strip().lower() != "none"
    ]


def _allowed_v2_base_types_for_card(
    card: dict[str, Any],
    visual_card_rules: dict[str, dict[str, Any]],
) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    seen: set[str] = set()
    for visual_type in _blueprint_visual_types_for_card(card, visual_card_rules):
        mapped = _map_blueprint_visual_type(visual_type)
        if not mapped[0] or mapped[0] in seen:
            continue
        result.append(mapped)
        seen.add(mapped[0])
    return result


def _preferred_v2_base_type_for_card(
    card: dict[str, Any],
    visual_card_rules: dict[str, dict[str, Any]],
) -> tuple[str, str]:
    allowed = _allowed_v2_base_types_for_card(card, visual_card_rules)
    if not allowed:
        return ("", "")
    if len(allowed) == 1:
        return allowed[0]

    visual_plan = card.get("visual_plan") if isinstance(card.get("visual_plan"), dict) else {}
    detected = _detect_visual_base_type_from_card_data(card, visual_plan)
    for base_type, mode in allowed:
        if base_type == detected:
            return (base_type, mode)

    for base_type, mode in allowed:
        if get_compiler(base_type) is not None:
            return (base_type, mode)
    return allowed[0]


def _detect_visual_base_type_from_card_data(
    card: dict[str, Any],
    visual_plan: dict[str, Any],
) -> str:
    if visual_plan.get("nodes"):
        return "node_link_diagram"
    if visual_plan.get("array_values") or visual_plan.get("array_rows"):
        return "indexed_sequence_diagram"
    if visual_plan.get("formula") or visual_plan.get("symbols"):
        return "formula_symbolic_expression"
    if visual_plan.get("columns") and visual_plan.get("rows"):
        return "table_diagram"
    if visual_plan.get("data_points") or visual_plan.get("key_points"):
        return "coordinate_graph"
    if visual_plan.get("code") or card.get("code_snippet"):
        return "code_execution_panel"
    return ""


def _blueprint_card_allows_base_type(
    card: dict[str, Any],
    visual_card_rules: dict[str, dict[str, Any]],
    base_type: str,
) -> bool:
    return any(
        allowed_base_type == base_type
        for allowed_base_type, _ in _allowed_v2_base_types_for_card(card, visual_card_rules)
    )


def _has_blueprint_cards_for_base_type(
    cards: list[dict[str, Any]],
    visual_card_rules: dict[str, dict[str, Any]],
    base_type: str,
) -> bool:
    return any(
        isinstance(card, dict)
        and _blueprint_card_allows_base_type(card, visual_card_rules, base_type)
        for card in cards
    )


def _expected_node_link_values(
    cards: list[Any],
    visual_card_rules: dict[str, dict[str, Any]],
) -> set[str]:
    """The canonical value set for node_link cards, taken from the shared
    problem setup that `_attach_shared_problem_setups` stamped onto each visual
    card. Used to assert the rendered structure matches the stated problem.
    """
    for card in cards:
        if not isinstance(card, dict):
            continue
        if not _blueprint_card_allows_base_type(card, visual_card_rules, "node_link_diagram"):
            continue
        problem = card.get("example_problem")
        if isinstance(problem, dict):
            values = problem.get("values")
            if isinstance(values, list) and values:
                return {str(value) for value in values if str(value).strip()}
    return set()


def _backfill_missing_node_link_structure(
    cards: list[Any],
    context: CompileContext,
    visual_card_rules: dict[str, dict[str, Any]],
) -> None:
    """Give a structureless node_link card the graph from another card.

    The background card's visual is built only from structural data the LLM
    emits on that card. When the LLM returns a background card with no nodes
    (diagnostics: `fallback_legacy` / `missing_nodes`), the card renders
    text-only — and for graph topics it also starves the worked-example dynamic
    trace, which reads its base structure from the background card.

    Unlike trees, a graph cannot be rebuilt from node values, so the fix is to
    copy the structure from the richest node_link card that DOES have one
    (preferring a worked_example, which carries the full node + edge list). The
    copy is reset to an at-rest state (every node unvisited, every edge a plain
    solid connector) so the background shows the structure before any traversal.
    This runs before the tree/BST normalizers, so a backfilled tree background is
    still canonicalized downstream.
    """
    card_dicts = [card for card in cards if isinstance(card, dict)]
    node_link_cards = [
        card
        for card in card_dicts
        if _blueprint_card_allows_base_type(card, visual_card_rules, "node_link_diagram")
    ]
    if len(node_link_cards) < 2:
        return

    def _node_count(card: dict[str, Any]) -> int:
        visual_plan = card.get("visual_plan") if isinstance(card.get("visual_plan"), dict) else {}
        nodes = visual_plan.get("nodes") or card.get("visual_nodes") or []
        return len(nodes) if isinstance(nodes, list) else 0

    def _edge_count(card: dict[str, Any]) -> int:
        visual_plan = card.get("visual_plan") if isinstance(card.get("visual_plan"), dict) else {}
        edges = visual_plan.get("edges") or card.get("visual_edges") or []
        return len(edges) if isinstance(edges, list) else 0

    # A node_link card needs repair when it has no nodes OR has nodes but NO edges
    # (a graph of disconnected dots — the MST-background bug). A valid donor must
    # have BOTH nodes and edges so the copy actually carries the connectivity.
    cards_with_structure = [
        card for card in node_link_cards if _node_count(card) > 0 and _edge_count(card) > 0
    ]
    if not cards_with_structure:
        return
    worked_donors = [
        card
        for card in cards_with_structure
        if str(card.get("blueprint_key") or "").strip().lower() == "worked_example"
    ]
    donor = max(worked_donors or cards_with_structure, key=_node_count)

    donor_plan = donor.get("visual_plan") if isinstance(donor.get("visual_plan"), dict) else {}
    donor_nodes = donor_plan.get("nodes") or donor.get("visual_nodes") or []
    donor_edges = donor_plan.get("edges") or donor.get("visual_edges") or []
    rest_nodes = _normalized_tree_nodes(donor_nodes)
    for node in rest_nodes:
        node["relation"] = _relation_without_state(node.get("relation"))
        node["state"] = "unvisited"
    rest_edges = _normalized_tree_edges(donor_edges, rest_nodes)
    for edge in rest_edges:
        edge["state"] = "unchecked"
        edge["style"] = "solid"
    if not rest_nodes:
        return

    for card in node_link_cards:
        # Repair cards missing connectivity: no nodes, or nodes-but-no-edges. A card
        # that already has edges is left alone (it's its own valid graph).
        if _edge_count(card) > 0:
            continue
        if card is donor:
            continue
        visual_plan = card.get("visual_plan")
        if not isinstance(visual_plan, dict):
            visual_plan = {}
            card["visual_plan"] = visual_plan
        visual_plan["type"] = "node_link_diagram"
        visual_plan["nodes"] = copy.deepcopy(rest_nodes)
        visual_plan["edges"] = copy.deepcopy(rest_edges)
        card["visual_type"] = "node_link_diagram"
        card["visual_nodes"] = copy.deepcopy(rest_nodes)
        card["visual_edges"] = copy.deepcopy(rest_edges)
        metadata = card.setdefault("metadata", {})
        if isinstance(metadata, dict):
            metadata["node_link_structure_backfilled_from"] = str(donor.get("id") or "")


def _normalize_node_link_worked_example_scenarios(
    cards: list[Any],
    context: CompileContext,
    visual_card_rules: dict[str, dict[str, Any]],
) -> None:
    """Use one canonical tree scenario for node-link worked examples.

    Legacy generation can mention values in prose that are different from
    the visual nodes. Before compiling v2 visuals, lock the visual-bearing
    worked-example cards to a single tree and rewrite their visible state
    bullets from the computed trace.
    """
    if not _looks_like_tree_traversal(context):
        return

    card_dicts = [card for card in cards if isinstance(card, dict)]

    def _is_node_link_worked(card: dict[str, Any]) -> bool:
        return (
            str(card.get("blueprint_key") or "").strip().lower() == "worked_example"
            and _blueprint_card_allows_base_type(card, visual_card_rules, "node_link_diagram")
        )

    worked_cards = [
        card
        for card in card_dicts
        if _is_node_link_worked(card) and not _is_worked_example_setup_card(card)
    ]
    if not worked_cards:
        # The LLM gave no trace-step cards — it may have framed the whole worked
        # example as a single setup-like "tracing" card. If this is still a tree
        # traversal with a valid scenario, treat any node_link worked_example
        # card(s) as trace seeds and synthesize the full multi-step trace below,
        # rather than bailing and leaving the lone (often code-trace) card. This
        # also makes the worked card a node_link tree (so the Diagram view shows
        # the tree, with the code on the toggle).
        seeds = [card for card in card_dicts if _is_node_link_worked(card)]
        if not seeds:
            return
        for card in seeds:
            card["example_type"] = ""
            metadata = card.get("metadata")
            if isinstance(metadata, dict):
                metadata.pop("worked_example_setup", None)
        worked_cards = seeds

    scenario = _canonical_tree_scenario(card_dicts, worked_cards, context)
    if not scenario:
        return

    order = _tree_visit_order(
        scenario["nodes"],
        scenario["edges"],
        scenario["root_id"],
        _detect_traversal_kind(context, card_dicts),
    )
    if not order:
        return

    _ensure_tree_worked_example_setup_card(
        cards,
        worked_cards,
        scenario,
        context,
        card_dicts,
    )

    # The output-order trace has exactly one step per visited node. If the LLM
    # emitted more worked_example cards than there are nodes, the surplus cards
    # used to clamp onto the last node — repeating e.g. "Visit 35" several times
    # at the tail. Drop the surplus so every step visits a distinct node and the
    # trace ends cleanly at the terminal node.
    if len(worked_cards) > len(order):
        surplus_ids = {id(card) for card in worked_cards[len(order):]}
        worked_cards = worked_cards[: len(order)]
        cards[:] = [
            card
            for card in cards
            if not (isinstance(card, dict) and id(card) in surplus_ids)
        ]
    elif len(worked_cards) < len(order):
        _append_missing_tree_worked_example_cards(
            cards=cards,
            card_dicts=card_dicts,
            worked_cards=worked_cards,
            order=order,
        )

    lesson_meta = cards[0].setdefault("_scenario_anchor", {}) if isinstance(cards[0], dict) else {}
    if isinstance(lesson_meta, dict):
        lesson_meta["tree_values"] = [node["id"] for node in scenario["nodes"]]

    traversal_kind = _detect_traversal_kind(context, card_dicts)
    for index, card in enumerate(worked_cards):
        active = order[min(index, len(order) - 1)]
        previous_output = order[: min(index, len(order))]
        next_output = order[: min(index + 1, len(order))]
        next_active = order[index + 1] if index + 1 < len(order) else ""
        # DFS orders are recursive: the active frames are the root→current path.
        # Level-order is queue-based, so it has no call stack.
        call_stack = (
            _root_to_node_path(scenario, active)
            if traversal_kind in ("inorder", "preorder", "postorder")
            else []
        )

        visual_plan = card.get("visual_plan")
        if not isinstance(visual_plan, dict):
            visual_plan = {}
            card["visual_plan"] = visual_plan
        visual_plan["type"] = "node_link_diagram"
        visual_plan["nodes"] = _nodes_with_state(
            scenario["nodes"],
            active=active,
            completed=previous_output,
        )
        visual_plan["edges"] = copy.deepcopy(scenario["edges"])
        visual_plan["description"] = _tree_step_description(
            active=active,
            previous_output=previous_output,
            next_output=next_output,
            traversal=_detect_traversal_kind(context, card_dicts),
            next_active=next_active,
        )
        visual_plan["what_to_notice"] = visual_plan["description"]

        card["visual_type"] = "node_link_diagram"
        card["visual_description"] = str(visual_plan["description"])
        card["what_to_notice"] = str(visual_plan["description"])
        card["title"] = f"{_traversal_label(_detect_traversal_kind(context, card_dicts))} Step {index + 1}: Visit {active}"
        code_snippet = card.get("code_snippet")
        if isinstance(code_snippet, str) and code_snippet.strip():
            # Coding worked example: describe what the CODE does for this node,
            # one state bullet + per-line code-action bullets, and advance the
            # code highlight per bullet via highlight_lines_per_step.
            code_lines = _detect_traversal_code_lines(code_snippet)
            code_points, code_highlights = _coding_trace_bullets(
                active=active,
                previous_output=previous_output,
                next_output=next_output,
                next_active=next_active,
                traversal=traversal_kind,
                code_lines=code_lines,
            )
            card["points"] = code_points
            card["highlight_lines_per_step"] = code_highlights
        else:
            card["points"] = _tree_trace_points(
                active=active,
                previous_output=previous_output,
                next_output=next_output,
                next_active=next_active,
                traversal=traversal_kind,
                call_stack=call_stack,
            )
        card["body"] = [
            (
                f"Trace the same tree throughout the example: "
                f"{', '.join(node['label'] for node in scenario['nodes'])}."
            )
        ]
        card["visual_focus"] = {
            "active_nodes": [active],
            "highlight_path": list(previous_output),
            "active_step": index,
            "attention_note": str(visual_plan["description"]),
        }
        metadata = card.setdefault("metadata", {})
        if isinstance(metadata, dict):
            metadata["canonical_visual_scenario"] = {
                "scenario_id": scenario["scenario_id"],
                "source": scenario["source"],
                "traversal": _detect_traversal_kind(context, card_dicts),
                "root": scenario["root_id"],
                "values": [node["id"] for node in scenario["nodes"]],
                "active": active,
                "output_before": previous_output,
                "output_after": next_output,
            }

    # Unify every OTHER node-link-bearing card (background, components, …) to
    # the SAME canonical scenario. The dynamic-trace synthesizer reads its base
    # structure from the background card; if that card keeps a different tree
    # than the one the worked-example trace and problem setup were built from,
    # the rendered diagram contradicts the trace (e.g. a node labelled 40 in a
    # 5..11 traversal). Rewriting these cards from the scenario at rest makes
    # the structure single-sourced across the whole lesson.
    rest_nodes = _nodes_with_state(scenario["nodes"], active="", completed=[])
    rest_edges = copy.deepcopy(scenario["edges"])
    for card in card_dicts:
        if card in worked_cards:
            continue
        if _is_worked_example_setup_card(card):
            continue
        if not _blueprint_card_allows_base_type(card, visual_card_rules, "node_link_diagram"):
            continue
        visual_plan = card.get("visual_plan")
        if not isinstance(visual_plan, dict) or not visual_plan.get("nodes"):
            continue
        visual_plan["type"] = "node_link_diagram"
        visual_plan["nodes"] = copy.deepcopy(rest_nodes)
        visual_plan["edges"] = copy.deepcopy(rest_edges)
        card["visual_type"] = "node_link_diagram"
        # The synthesizer prefers card-level visual_nodes/visual_edges, so keep
        # them in lockstep with visual_plan.
        if card.get("visual_nodes") is not None:
            card["visual_nodes"] = copy.deepcopy(rest_nodes)
        if card.get("visual_edges") is not None:
            card["visual_edges"] = copy.deepcopy(rest_edges)
        metadata = card.setdefault("metadata", {})
        if isinstance(metadata, dict):
            metadata["canonical_visual_scenario"] = {
                "scenario_id": scenario["scenario_id"],
                "source": scenario["source"],
                "root": scenario["root_id"],
                "values": [
                    str(node.get("label") or node.get("id")) for node in scenario["nodes"]
                ],
            }


def _append_missing_tree_worked_example_cards(
    *,
    cards: list[Any],
    card_dicts: list[dict[str, Any]],
    worked_cards: list[dict[str, Any]],
    order: list[str],
) -> None:
    """Extend deterministic tree traces when the LLM emitted too few cards."""
    if not worked_cards or len(worked_cards) >= len(order):
        return

    existing_ids = {
        str(card.get("id") or "")
        for card in cards
        if isinstance(card, dict)
    }
    template = copy.deepcopy(worked_cards[-1])
    last_index = next(
        (
            index
            for index in range(len(cards) - 1, -1, -1)
            if isinstance(cards[index], dict) and cards[index] in worked_cards
        ),
        -1,
    )
    if last_index < 0:
        return

    for trace_index in range(len(worked_cards), len(order)):
        new_card = copy.deepcopy(template)
        base_id = str(template.get("id") or "worked-example")
        candidate_id = f"{base_id}-trace-{trace_index + 1}"
        suffix = 2
        while candidate_id in existing_ids:
            candidate_id = f"{base_id}-trace-{trace_index + 1}-{suffix}"
            suffix += 1
        existing_ids.add(candidate_id)

        new_card["id"] = candidate_id
        new_card["blueprint_key"] = "worked_example"
        new_card["card_type"] = "worked_example"
        new_card["example_type"] = "state_trace_example"
        new_card["title"] = f"Tree Traversal Step {trace_index + 1}"
        new_card["points"] = []
        new_card["body"] = []
        new_card["visual_type"] = "node_link_diagram"
        new_card["visual_description"] = ""
        new_card["what_to_notice"] = ""
        new_card.pop("visual_v2_ref", None)
        new_card["visual_focus"] = {
            "active_nodes": [],
            "highlight_path": [],
            "active_step": trace_index,
            "attention_note": "",
        }
        metadata = new_card.setdefault("metadata", {})
        if isinstance(metadata, dict):
            metadata["deterministic_trace_backfilled"] = True

        insert_at = last_index + 1
        cards.insert(insert_at, new_card)
        card_dicts.append(new_card)
        worked_cards.append(new_card)
        last_index = insert_at


def _ensure_tree_worked_example_setup_card(
    cards: list[Any],
    worked_cards: list[dict[str, Any]],
    scenario: dict[str, Any],
    context: CompileContext,
    card_dicts: list[dict[str, Any]],
) -> None:
    if not worked_cards:
        return
    first_card = worked_cards[0]
    first_index = next(
        (
            index
            for index, card in enumerate(cards)
            if isinstance(card, dict) and card is first_card
        ),
        -1,
    )
    if first_index < 0:
        return
    previous_card = cards[first_index - 1] if first_index > 0 else None
    if isinstance(previous_card, dict) and _is_worked_example_setup_card(previous_card):
        return

    traversal = _detect_traversal_kind(context, card_dicts)
    root_id = str(scenario.get("root_id") or "")
    values = [
        str(node.get("label") or node.get("id"))
        for node in scenario.get("nodes") or []
        if isinstance(node, dict)
    ]
    visual_description = (
        f"Initial state before the first {_traversal_label(traversal).lower()} step. "
        f"The current focus starts at root {root_id}; no output has been recorded yet."
    )

    # For coding worked examples, carry the implementation onto the setup card so
    # it gets the Diagram/Code toggle, and describe the problem + every setup line
    # (base case, container inits, queue/stack seed, outer function calling its
    # helper) with the matching code line highlighted per bullet.
    setup_code_snippet = ""
    setup_code_language = ""
    for worked in worked_cards:
        snippet = worked.get("code_snippet")
        if isinstance(snippet, str) and snippet.strip():
            setup_code_snippet = snippet
            setup_code_language = str(worked.get("code_language") or "python")
            break

    if setup_code_snippet:
        setup_points, setup_highlights = _coding_setup_bullets(
            code_snippet=setup_code_snippet,
            traversal=traversal,
            root_id=root_id,
        )
    else:
        setup_points = [
            "Problem:",
            f"  - Trace {_traversal_label(traversal).lower()} on this tree.",
            "Initial state:",
            f"  - current={root_id}",
            "  - result=[]",
            "Goal:",
            "  - Follow the same structure until the traversal output is complete.",
        ]
        setup_highlights = []

    setup_card = {
        "id": f"{first_card.get('id') or first_index + 1}-setup",
        "blueprint_key": "worked_example",
        "card_type": "worked_example",
        "title": f"{_traversal_label(traversal)} Setup",
        "points": setup_points,
        "body": [
            (
                "This setup card locks the example input before any step runs: "
                f"values {', '.join(values)}."
            )
        ],
        "bullets": [],
        "main_concept": "Understand the starting state for the worked example.",
        "learning_goal": "Understand the starting state for the worked example.",
        "example_type": "problem_setup",
        "visual_type": "node_link_diagram",
        "new_concepts": [],
        "review_concepts": [],
        "prerequisite_concepts": [],
        "common_misconceptions": [],
        "concept_support": [],
        "interactive_links": [],
        "styled_elements": [],
        "visual_plan": {
            "type": "node_link_diagram",
            "title": "Initial State",
            "purpose": "Show the example before the first operation.",
            "description": visual_description,
            "placement": "card",
            "what_to_notice": visual_description,
            "nodes": _nodes_with_state(
                scenario["nodes"],
                active=root_id,
                completed=[],
            ),
            "edges": copy.deepcopy(scenario["edges"]),
        },
        "visual_description": visual_description,
        "visual_index": -1,
        "annotations": [],
        "example": "",
        "micro_check": {"type": "", "prompt": "", "answer": ""},
        "what_to_notice": visual_description,
        "next_transition": "",
        "estimated_seconds": 35,
        "transition_text": "",
        "next_card_label": "Next",
        "practice_question_index": None,
        "code_snippet": setup_code_snippet,
        "code_language": setup_code_language,
        "highlight_lines_per_step": setup_highlights,
        "continuation_group_id": "worked_example_setup",
        "continuation_index": 0,
        "continuation_total": len(worked_cards) + 1,
        "continuation_reason": "problem_setup",
        "continues_from_previous": False,
        "visual_focus": {
            "active_nodes": [root_id] if root_id else [],
            "highlight_path": [],
            "active_step": -1,
            "attention_note": visual_description,
        },
        "metadata": {
            "worked_example_setup": True,
            "canonical_visual_scenario": {
                "scenario_id": scenario["scenario_id"],
                "source": scenario["source"],
                "traversal": traversal,
                "root": root_id,
                "values": [node["id"] for node in scenario["nodes"]],
            },
        },
    }
    cards.insert(first_index, setup_card)
    card_dicts.insert(
        card_dicts.index(first_card) if first_card in card_dicts else len(card_dicts),
        setup_card,
    )


def _looks_like_tree_traversal(context: CompileContext) -> bool:
    text = " ".join(
        str(value)
        for value in (
            context.get("topic_hint"),
            context.get("topic_type"),
            context.get("visual_domain"),
        )
    ).lower()
    if any(token in text for token in ("bst", "binary search tree", "tree")):
        return True
    return any(
        token in text
        for token in (
            "inorder",
            "in-order",
            "preorder",
            "pre-order",
            "postorder",
            "post-order",
            "level-order",
            "level order",
        )
    )


def _normalize_bst_node_link_visuals(
    cards: list[Any],
    context: CompileContext,
    visual_card_rules: dict[str, dict[str, Any]],
) -> None:
    """Force BST visual cards to use BST-valid edges before v2 compilation.

    The LLM sometimes emits a generic tree with BST wording, for example
    placing 35 as a direct child of 40 even when values imply it belongs below
    25. Since v2 faithfully renders provided edges, the bridge canonicalizes
    node-link BST cards from their node values/root before any compiler sees
    them.
    """
    card_dicts = [card for card in cards if isinstance(card, dict)]
    if not _looks_like_bst(context, card_dicts):
        return

    for card in card_dicts:
        if not _blueprint_card_allows_base_type(card, visual_card_rules, "node_link_diagram"):
            continue
        visual_plan = card.get("visual_plan")
        if not isinstance(visual_plan, dict) or not visual_plan.get("nodes"):
            continue
        scenario = _canonical_tree_scenario([card], [card], context)
        if not scenario:
            continue
        visual_plan["type"] = "node_link_diagram"
        visual_plan["nodes"] = copy.deepcopy(scenario["nodes"])
        visual_plan["edges"] = copy.deepcopy(scenario["edges"])
        card["visual_type"] = "node_link_diagram"
        metadata = card.setdefault("metadata", {})
        if isinstance(metadata, dict):
            metadata["bst_visual_canonicalized"] = True
            metadata["canonical_visual_scenario"] = {
                "scenario_id": scenario["scenario_id"],
                "source": scenario["source"],
                "root": scenario["root_id"],
                "values": [str(node.get("label") or node.get("id")) for node in scenario["nodes"]],
            }


def _looks_like_bst(
    context: CompileContext,
    cards: list[dict[str, Any]] | None = None,
) -> bool:
    pieces = [
        str(context.get("topic_hint") or ""),
        str(context.get("topic_type") or ""),
        str(context.get("visual_domain") or ""),
    ]
    for card in (cards or [])[:8]:
        pieces.extend(
            [
                str(card.get("title") or ""),
                str(card.get("main_concept") or ""),
                str(card.get("learning_goal") or ""),
                " ".join(str(point) for point in (card.get("points") or [])),
                " ".join(str(body) for body in (card.get("body") or [])),
            ]
        )
    text = " ".join(pieces).lower()
    return "bst" in text or "binary search tree" in text


# Minimum node count for a traversal worked-example tree. Below this the example
# is too thin to teach the order (one trace step per node), so the bridge
# substitutes a richer canonical BST.
_MIN_TRACE_TREE_NODES = 6


def _canonical_tree_scenario(
    cards: list[dict[str, Any]],
    worked_cards: list[dict[str, Any]],
    context: CompileContext | None = None,
) -> dict[str, Any] | None:
    candidates: list[tuple[int, str, dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]] = []
    for card in cards:
        blueprint_key = str(card.get("blueprint_key") or "").strip().lower()
        visual_plan = card.get("visual_plan") if isinstance(card.get("visual_plan"), dict) else {}
        nodes = _normalized_tree_nodes(visual_plan.get("nodes") or card.get("visual_nodes") or [])
        edges = _normalized_tree_edges(visual_plan.get("edges") or card.get("visual_edges") or [], nodes)
        if not nodes:
            continue
        score = len(nodes) * 10
        if blueprint_key == "background":
            score += 100
        elif card in worked_cards:
            score += 50
        candidates.append((score, blueprint_key, card, nodes, edges))

    if not candidates:
        # No card carried a usable tree. This is common on coding topics where
        # the background and worked cards are CODE visuals — there is nothing to
        # trace. For a tree-traversal topic we still need a tree, so synthesize a
        # deterministic BST. Without this the bridge bails, the worked example
        # keeps its code visual, and the Diagram/Code toggle shows code in BOTH
        # views. With it, the worked example always renders as a tree (Diagram)
        # with the code on the toggle (Code).
        if context is not None and _looks_like_tree_traversal(context):
            fallback = _fallback_bst_scenario(context)
            if fallback:
                f_nodes, f_edges, f_root = fallback
                return {
                    "scenario_id": f"tree_{_safe_id(str(getattr(context, 'topic_id', '') or 'scenario'))}",
                    "source": "fallback",
                    "nodes": f_nodes,
                    "edges": f_edges,
                    "root_id": f_root,
                }
        return None
    _, source, card, nodes, edges = max(candidates, key=lambda item: item[0])
    root_id = _root_node_id(nodes, edges)
    if not root_id:
        return None
    if context is not None and _looks_like_bst(context, cards):
        rebuilt = _rebuild_bst_scenario(nodes, edges, root_id)
        if not rebuilt:
            # The LLM's tree can't be canonicalized as a BST — e.g. a non-numeric
            # node label like "WITH", or a single stray node. Rather than render
            # that broken structure, substitute a clean, deterministic BST seeded
            # by the topic. It uses the same value set the prompt told the model
            # to use, so the prose still lines up when the model complied.
            rebuilt = _fallback_bst_scenario(context)
        if rebuilt:
            nodes, edges, root_id = rebuilt

    # Enforce a minimum example size. A 3-node tree makes a thin, unconvincing
    # traversal worked example (one step per node). When the LLM's tree is too
    # small, substitute a richer deterministic BST so the trace has enough steps
    # to actually teach the order. The whole lesson is unified to this scenario
    # downstream, so the background and trace stay consistent.
    if context is not None and len(nodes) < _MIN_TRACE_TREE_NODES:
        fallback = _fallback_bst_scenario(context)
        if fallback and len(fallback[0]) >= len(nodes):
            nodes, edges, root_id = fallback

    return {
        "scenario_id": f"tree_{_safe_id(str(card.get('id') or source or 'scenario'))}",
        "source": source,
        "nodes": nodes,
        "edges": edges,
        "root_id": root_id,
    }


def _rebuild_bst_scenario(
    nodes: list[dict[str, Any]],
    edges_in: list[dict[str, Any]] | None,
    preferred_root_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str] | None:
    values: dict[str, float] = {}
    for node in nodes:
        value = _numeric_tree_value(node)
        if value is None:
            return None
        values[str(node["id"])] = value
    if len(values) < 2:
        return None

    # If the incoming edges already encode a valid BST with explicit child sides
    # (i.e. they came from a prior canonicalization pass), reproduce that exact
    # structure instead of re-inserting. The rebuild is otherwise NOT idempotent:
    # the first pass lays nodes out in inorder, and re-inserting inorder-sorted
    # values builds a spine, which the degeneracy check can just barely miss.
    rebuilt_from_edges = _bst_children_from_sided_edges(values, edges_in)
    if rebuilt_from_edges is not None:
        root_id, children = rebuilt_from_edges
    else:
        # Keep the stated/median root, then build each subtree balanced from the
        # sorted values on that side. The LLM's own structure is unreliable — it
        # tends to emit spindly near-spine subtrees that read like edge cases —
        # and the bridge discards the LLM's edges anyway, so we render the clean,
        # textbook-shaped BST instead. The root is preserved so it still matches
        # the card prose ("root 59"); only the shape is tidied.
        ordered_ids = sorted(values, key=lambda node_id: values[node_id])
        root_id = (
            preferred_root_id
            if preferred_root_id in values
            else ordered_ids[len(ordered_ids) // 2]
        )
        children = _balanced_bst_children_with_root(values, root_id)

    edges: list[dict[str, Any]] = []
    for parent_id in children:
        for side in ("left", "right"):
            child_id = children[parent_id].get(side)
            if child_id:
                edges.append(
                    {
                        "from": parent_id,
                        "to": child_id,
                        "label": "",
                        "style": "solid",
                        "state": "unchecked",
                        # Explicit child side so traversal order doesn't have to
                        # be re-inferred from coordinates downstream.
                        "side": side,
                    }
                )

    laid_out_nodes = _layout_bst_nodes(nodes, children, root_id)
    return laid_out_nodes, edges, root_id


def _fallback_bst_scenario(
    context: CompileContext | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str] | None:
    """Build a clean BST from a deterministic per-topic value set.

    Used when the LLM's tree can't be canonicalized (non-numeric labels, too few
    nodes). Seeded by the topic so it matches the values the prompt asked the
    model to write, and so regenerations are stable.
    """
    if context is None:
        return None
    from app.services.tree_value_set import generate_bst_value_set

    seed = f"{context.get('topic_id') or ''}|{context.get('topic_hint') or ''}"
    values, root = generate_bst_value_set(seed)
    raw_nodes = [
        {"id": str(value), "label": str(value), "relation": "node", "x": 50.0, "y": 20.0}
        for value in values
    ]
    return _rebuild_bst_scenario(_normalized_tree_nodes(raw_nodes), None, str(root))


def _bst_children_from_sided_edges(
    values: dict[str, float],
    edges_in: list[dict[str, Any]] | None,
) -> tuple[str, dict[str, dict[str, str]]] | None:
    """Reconstruct the left/right child map from edges that carry explicit
    `side` info, validating that they form one acyclic BST over `values`.

    Returns (root_id, children) when the edges fully and validly encode the
    tree, else None (so the caller rebuilds from values). This is what makes a
    second canonicalization pass idempotent — the first pass emits side-tagged
    edges, and this reproduces that exact structure rather than re-inserting.
    """
    if not isinstance(edges_in, list) or not edges_in:
        return None
    node_ids = set(values)
    children: dict[str, dict[str, str]] = {node_id: {} for node_id in node_ids}
    incoming: set[str] = set()
    for raw in edges_in:
        if not isinstance(raw, dict):
            return None
        parent = str(raw.get("from") or "")
        child = str(raw.get("to") or "")
        side = str(raw.get("side") or "").strip().lower()
        if parent not in node_ids or child not in node_ids:
            return None
        if side not in ("left", "right"):
            return None  # require a fully side-annotated edge set
        if side in children[parent]:
            return None  # two children on the same side
        if side == "left" and not values[child] < values[parent]:
            return None  # side contradicts BST ordering
        if side == "right" and not values[child] > values[parent]:
            return None
        if child in incoming:
            return None  # a node with two parents
        children[parent][side] = child
        incoming.add(child)

    roots = [node_id for node_id in node_ids if node_id not in incoming]
    if len(roots) != 1:
        return None
    root_id = roots[0]

    # Every node reachable from the root exactly once (connected + acyclic).
    seen: set[str] = set()
    stack = [root_id]
    while stack:
        current = stack.pop()
        if current in seen:
            return None  # cycle
        seen.add(current)
        for side in ("left", "right"):
            child = children[current].get(side)
            if child:
                stack.append(child)
    if seen != node_ids:
        return None  # not all nodes covered

    return root_id, children


def _balanced_bst_children_with_root(
    values: dict[str, float],
    root_id: str,
) -> dict[str, dict[str, str]]:
    """Build a BST that keeps `root_id` as the root but lays each side out as a
    balanced subtree (median-of-range recursion over the sorted values on that
    side). Result has no spines — left/right subtree sizes differ only because of
    where the root sits in the value order, which is the expected, common BST
    silhouette."""
    children: dict[str, dict[str, str]] = {node_id: {} for node_id in values}
    root_value = values[root_id]
    left_ids = sorted(
        (node_id for node_id in values if values[node_id] < root_value),
        key=lambda node_id: values[node_id],
    )
    right_ids = sorted(
        (node_id for node_id in values if values[node_id] > root_value),
        key=lambda node_id: values[node_id],
    )

    def build(ordered: list[str]) -> str | None:
        if not ordered:
            return None
        mid = len(ordered) // 2
        node_id = ordered[mid]
        left_child = build(ordered[:mid])
        right_child = build(ordered[mid + 1 :])
        if left_child:
            children[node_id]["left"] = left_child
        if right_child:
            children[node_id]["right"] = right_child
        return node_id

    left_root = build(left_ids)
    right_root = build(right_ids)
    if left_root:
        children[root_id]["left"] = left_root
    if right_root:
        children[root_id]["right"] = right_root
    return children


def _numeric_tree_value(node: dict[str, Any]) -> float | None:
    for raw in (node.get("label"), node.get("id")):
        text = str(raw or "").strip()
        if not text:
            continue
        try:
            return float(text)
        except ValueError:
            continue
    return None


def _layout_bst_nodes(
    nodes: list[dict[str, Any]],
    children: dict[str, dict[str, str]],
    root_id: str,
) -> list[dict[str, Any]]:
    node_by_id = {str(node["id"]): copy.deepcopy(node) for node in nodes}
    inorder_ids: list[str] = []
    depths: dict[str, int] = {}

    def walk(node_id: str, depth: int) -> None:
        depths[node_id] = depth
        left = children.get(node_id, {}).get("left")
        right = children.get(node_id, {}).get("right")
        if left:
            walk(left, depth + 1)
        inorder_ids.append(node_id)
        if right:
            walk(right, depth + 1)

    walk(root_id, 0)
    if not inorder_ids:
        return nodes

    span_start = 12.0
    span_width = 76.0
    denominator = max(len(inorder_ids) - 1, 1)
    x_by_id = {
        node_id: span_start + span_width * (index / denominator)
        for index, node_id in enumerate(inorder_ids)
    }

    # Spread levels evenly across a fixed vertical band rather than a fixed
    # per-level gap with a hard cap. Even spacing keeps shallow trees from
    # looking stretched and stops deep trees from colliding at the capped
    # bottom row; the band is kept wider-than-tall so the tree reads like a
    # balanced diagram instead of a tall column.
    max_depth = max(depths.values()) if depths else 0
    y_top = 14.0
    y_span = 44.0

    laid_out: list[dict[str, Any]] = []
    for node_id in inorder_ids:
        node = node_by_id[node_id]
        left = children.get(node_id, {}).get("left")
        right = children.get(node_id, {}).get("right")
        depth = depths.get(node_id, 0)
        node["x"] = x_by_id[node_id]
        node["y"] = (
            y_top + (depth / max_depth) * y_span if max_depth > 0 else y_top + y_span / 2.0
        )
        node["relation"] = "root" if node_id == root_id else ("node" if left or right else "leaf")
        node["state"] = str(node.get("state") or "unvisited")
        laid_out.append(node)
    return laid_out


def _normalized_tree_nodes(raw_nodes: Any) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    seen: set[str] = set()
    if not isinstance(raw_nodes, list):
        return nodes
    for index, raw in enumerate(raw_nodes):
        if not isinstance(raw, dict):
            continue
        node_id = str(raw.get("id") or raw.get("label") or "").strip()
        if not node_id or node_id in seen:
            continue
        seen.add(node_id)
        nodes.append(
            {
                "id": node_id,
                "label": str(raw.get("label") or node_id),
                "relation": str(raw.get("relation") or "node"),
                "description": str(raw.get("description") or ""),
                "state": "unvisited",
                "x": float(raw.get("x")) if isinstance(raw.get("x"), (int, float)) else 50.0,
                "y": float(raw.get("y")) if isinstance(raw.get("y"), (int, float)) else 20.0 + index * 12.0,
            }
        )
    return nodes


def _normalized_tree_edges(
    raw_edges: Any,
    nodes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    valid = {str(node["id"]) for node in nodes}
    edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    if not isinstance(raw_edges, list):
        return edges
    for raw in raw_edges:
        if not isinstance(raw, dict):
            continue
        source = str(raw.get("from") or "").strip()
        target = str(raw.get("to") or "").strip()
        if source not in valid or target not in valid or (source, target) in seen:
            continue
        seen.add((source, target))
        edge: dict[str, Any] = {
            "from": source,
            "to": target,
            "label": str(raw.get("label") or ""),
            "style": str(raw.get("style") or "solid"),
            "state": str(raw.get("state") or "unchecked"),
        }
        # Preserve explicit BST child side so a canonicalized tree can be
        # reproduced exactly on a second pass (keeps the rebuild idempotent).
        side = str(raw.get("side") or "").strip().lower()
        if side in ("left", "right"):
            edge["side"] = side
        edges.append(edge)
    return edges


def _root_node_id(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> str:
    for node in nodes:
        if "root" in str(node.get("relation") or "").lower():
            return str(node["id"])
    children = {str(edge["to"]) for edge in edges}
    roots = [str(node["id"]) for node in nodes if str(node["id"]) not in children]
    if roots:
        return min(
            roots,
            key=lambda node_id: next(
                (float(node.get("y") or 0) for node in nodes if str(node["id"]) == node_id),
                0.0,
            ),
        )
    return str(nodes[0]["id"]) if nodes else ""


def _detect_traversal_kind(
    context: CompileContext,
    cards: list[dict[str, Any]],
) -> str:
    text = " ".join(
        [
            str(context.get("topic_hint") or ""),
            str(context.get("topic_type") or ""),
            *[
                str(card.get("title") or "") + " " + " ".join(str(p) for p in (card.get("points") or []))
                for card in cards[:8]
            ],
        ]
    ).lower()
    if "preorder" in text or "pre-order" in text:
        return "preorder"
    if "postorder" in text or "post-order" in text:
        return "postorder"
    if "level-order" in text or "level order" in text or "breadth" in text or "bfs" in text:
        return "level_order"
    return "inorder"


def _tree_visit_order(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    root_id: str,
    traversal: str,
) -> list[str]:
    children: dict[str, list[str]] = {str(node["id"]): [] for node in nodes}
    node_by_id = {str(node["id"]): node for node in nodes}
    side_by_child: dict[str, str] = {}
    for edge in edges:
        source = str(edge["from"])
        target = str(edge["to"])
        if source in children and target in node_by_id:
            children[source].append(target)
            side = str(edge.get("side") or "").strip().lower()
            if side in ("left", "right"):
                side_by_child[target] = side

    def _by_x(child_id: str) -> float:
        return float(node_by_id[child_id].get("x") or 0.0)

    def split_children(node_id: str) -> tuple[list[str], list[str]]:
        """Partition a node's children into (left, right).

        Prefer explicit BST `side` metadata; when absent (generic trees) fall
        back to x-position RELATIVE TO THE PARENT. The previous logic treated
        the first child as left regardless of side, which inverted inorder on
        any node whose only child is a right child (e.g. a right spine).
        """
        kids = children.get(node_id) or []
        if not kids:
            return [], []
        if all(child in side_by_child for child in kids):
            left = [child for child in kids if side_by_child[child] == "left"]
            right = [child for child in kids if side_by_child[child] == "right"]
        else:
            parent_x = float(node_by_id[node_id].get("x") or 0.0)
            left = [child for child in kids if _by_x(child) < parent_x]
            right = [child for child in kids if _by_x(child) >= parent_x]
        left.sort(key=_by_x)
        right.sort(key=_by_x)
        return left, right

    if traversal == "level_order":
        order: list[str] = []
        queue = [root_id]
        seen: set[str] = set()
        while queue:
            node_id = queue.pop(0)
            if node_id in seen:
                continue
            seen.add(node_id)
            order.append(node_id)
            left, right = split_children(node_id)
            queue.extend(child_id for child_id in left + right if child_id not in seen)
        return order

    visited: set[str] = set()

    def walk(node_id: str) -> list[str]:
        if node_id not in node_by_id or node_id in visited:
            return []
        visited.add(node_id)
        left, right = split_children(node_id)
        if traversal == "preorder":
            return [node_id] + [v for child in left + right for v in walk(child)]
        if traversal == "postorder":
            return [v for child in left + right for v in walk(child)] + [node_id]
        return (
            [v for child in left for v in walk(child)]
            + [node_id]
            + [v for child in right for v in walk(child)]
        )

    return walk(root_id)


def _nodes_with_state(
    nodes: list[dict[str, Any]],
    *,
    active: str,
    completed: list[str],
) -> list[dict[str, Any]]:
    completed_set = set(completed)
    result = copy.deepcopy(nodes)
    for node in result:
        node_id = str(node.get("id") or "")
        if node_id == active:
            node["state"] = "current"
            node["relation"] = _relation_with_state(node.get("relation"), "current")
        elif node_id in completed_set:
            node["state"] = "completed"
            node["relation"] = _relation_with_state(node.get("relation"), "completed")
        else:
            node["state"] = "unvisited"
            node["relation"] = _relation_without_state(node.get("relation"))
    return result


def _relation_with_state(raw_relation: Any, state: str) -> str:
    base = _relation_without_state(raw_relation)
    return f"{base} {state}".strip()


def _relation_without_state(raw_relation: Any) -> str:
    tokens = [
        token
        for token in str(raw_relation or "node").split()
        if token.lower() not in {"current", "completed", "visited", "discovered"}
    ]
    return " ".join(tokens) or "node"


def _tree_trace_points(
    *,
    active: str,
    previous_output: list[str],
    next_output: list[str],
    next_active: str,
    traversal: str,
    call_stack: list[str] | None = None,
) -> list[str]:
    action = _tree_action_sentence(active, next_active, traversal)
    currently = [
        "Currently:",
        f"  - current={active}",
    ]
    # For the recursive DFS orders, surface the call stack (the active recursion
    # frames = the path from the root down to the current node). This matches the
    # recursive code's state, so the worked example and the code discuss the same
    # components instead of a stale explicit `stack` from an iterative version.
    if call_stack:
        currently.append(f"  - Call stack: [{' → '.join(call_stack)}]")
    currently.append(f"  - result=[{', '.join(previous_output)}]")
    return currently + [
        action,
        "Now:",
        f"  - current={next_active or 'done'}",
        f"  - result=[{', '.join(next_output)}]",
    ]


def _root_to_node_path(scenario: dict[str, Any], node_id: str) -> list[str]:
    """The path of node ids from the root down to `node_id` — i.e. the recursion
    frames active when a DFS traversal visits that node (root at the bottom of
    the stack, the visited node at the top)."""
    parent: dict[str, str] = {}
    for edge in scenario.get("edges") or []:
        if isinstance(edge, dict):
            parent[str(edge.get("to"))] = str(edge.get("from"))
    path = [str(node_id)]
    seen = {str(node_id)}
    current = str(node_id)
    while current in parent:
        current = parent[current]
        if current in seen:  # malformed edges; stop rather than loop
            break
        seen.add(current)
        path.append(current)
    path.reverse()
    return path


def _tree_action_sentence(active: str, next_active: str, traversal: str) -> str:
    label = _traversal_label(traversal)
    if next_active:
        return f"Visit node {active}; the next {label.lower()} focus is node {next_active}."
    return f"Visit node {active}; this completes the {label.lower()} trace."


def _tree_step_description(
    *,
    active: str,
    previous_output: list[str],
    next_output: list[str],
    traversal: str,
    next_active: str,
) -> str:
    before = f"[{', '.join(previous_output)}]"
    after = f"[{', '.join(next_output)}]"
    if next_active:
        return (
            f"Node {active} is current. Output changes from {before} to {after}; "
            f"next focus is {next_active}."
        )
    return f"Node {active} is current. Output changes from {before} to {after}; the {traversal.replace('_', ' ')} trace is complete."


def _traversal_label(traversal: str) -> str:
    return {
        "preorder": "Preorder Traversal",
        "postorder": "Postorder Traversal",
        "level_order": "Level-Order Traversal",
        "inorder": "Inorder Traversal",
    }.get(traversal, "Tree Traversal")


def _detect_traversal_code_lines(code_snippet: str) -> dict[str, int]:
    """Locate the key action lines in a traversal implementation (1-indexed).

    Heuristic and formatting-tolerant; relies on the one-statement-per-line
    house style (see the coding prompt) so each action sits on its own line.
    Returns any subset of: base_case, visit, recurse_left, recurse_right,
    dequeue, enqueue_left, enqueue_right.
    """
    found: dict[str, int] = {}
    for idx, raw in enumerate(code_snippet.split("\n")):
        line = raw.strip()
        low = line.lower()
        n = idx + 1
        is_append = bool(re.search(r"\.append\s*\(", line))
        has_left = ".left" in low
        has_right = ".right" in low
        queue_ctx = "queue" in low or ".popleft" in low or re.search(r"\bq\.", low) is not None
        value_token = bool(re.search(r"\.(val|value|data|key)\b", low))
        bracket_visit = bool(re.search(r"\[\s*\w+\.(val|value|data|key)\b", low))
        # Base-case guard: an `if` on the root/node that returns early. Matches all
        # common forms — `if not node:`, `if node:`, `if node is None:`,
        # `if node == None:`, `if root is None:` — so the check line highlights even
        # when the node exists (the condition is evaluated, just not taken).
        is_base_guard = (
            re.match(r"if\b", low) is not None
            and ("root" in low or "node" in low)
            and (
                "none" in low
                or " not " in f" {low} "
                or re.search(r"\bif\s+\w+\s*:", line) is not None
            )
        )
        if "base_case" not in found and is_base_guard and not is_append:
            found["base_case"] = n
        if "dequeue" not in found and re.search(r"\.popleft\s*\(|\.pop\s*\(\s*0\s*\)", low):
            found["dequeue"] = n
        if (
            "visit" not in found
            and (is_append or bracket_visit)
            and value_token
            and not queue_ctx
            and not has_left
            and not has_right
        ):
            found["visit"] = n
        if has_left:
            found.setdefault("enqueue_left" if is_append else "recurse_left", n)
        if has_right:
            found.setdefault("enqueue_right" if is_append else "recurse_right", n)
    return found


def _coding_trace_bullets(
    *,
    active: str,
    previous_output: list[str],
    next_output: list[str],
    next_active: str,
    traversal: str,
    code_lines: dict[str, int],
) -> tuple[list[str], list[list[int]]]:
    """Code-centric worked-example bullets for a coding traversal step.

    One state bullet (no code line) followed by code-action bullets, each tied
    to the executing line. The aligned per-bullet line list is returned as
    highlight_lines_per_step so the worked example advances the code highlight
    as the learner reveals each bullet.
    """
    before = "[" + ", ".join(previous_output) + "]"
    after = "[" + ", ".join(next_output) + "]"
    label = _traversal_label(traversal).replace(" Traversal", "").lower()
    points: list[str] = []
    highlights: list[list[int]] = []

    def add(point: str, line: int | None) -> None:
        points.append(point)
        highlights.append([line, line] if line else [])

    is_bfs = traversal in ("level_order", "levelorder", "bfs")
    if is_bfs:
        add(f"State: now processing {active} — result goes from {before} to {after}.", None)
        add(f"{active} is removed from the front of the queue (dequeued) to be processed.", code_lines.get("dequeue"))
        add(f"{active}'s value is appended to the result list, giving {after}.", code_lines.get("visit"))
        enqueue = code_lines.get("enqueue_left") or code_lines.get("enqueue_right")
        if enqueue:
            add(f"{active}'s children are added to the back of the queue to be visited on later passes.", enqueue)
    else:
        visit_line = code_lines.get("visit")
        left_line = code_lines.get("recurse_left")
        right_line = code_lines.get("recurse_right")
        add(f"State: current node is {active} — result goes from {before} to {after}.", None)
        add(f"{active} is a real node, so the base-case check evaluates to false and the body runs.", code_lines.get("base_case"))
        # Cover the recursion lines in the order they execute for this traversal,
        # so every line of the function is highlighted across the trace.
        if traversal == "preorder":
            add(f"{active}'s value is appended to the result — the preorder visit — giving {after}.", visit_line)
            if left_line:
                add("The function then recurses into the left child first.", left_line)
            if right_line:
                add("After the left subtree finishes, it recurses into the right child.", right_line)
        elif traversal == "postorder":
            if left_line:
                add("First the function recurses into the left subtree.", left_line)
            if right_line:
                add("Then it recurses into the right subtree.", right_line)
            add(f"Only after both children does {active}'s value get appended — the postorder visit — giving {after}.", visit_line)
        else:  # inorder
            if left_line:
                add("The left subtree is visited first — the recursive left call returns before this node is touched.", left_line)
            add(f"{active}'s value is appended to the result — the inorder visit — giving {after}.", visit_line)
            if right_line:
                add("The function then recurses into the right subtree to continue the traversal.", right_line)
    return points, highlights


def _coding_setup_bullets(
    *,
    code_snippet: str,
    traversal: str,
    root_id: str,
) -> tuple[list[str], list[list[int]]]:
    """Setup-card bullets for a coding worked example: the problem statement plus
    each initialization/setup line — the entry method's container inits, the
    queue/stack seed, and the call into the helper — with the matching code line
    highlighted as that bullet is discussed. Handles the LeetCode `class Solution`
    shape: it covers the FIRST (entry) method and stops at the SECOND `def` (the
    helper). For inorder it also previews the implicit descent to the leftmost node
    (the recursive left call that runs before anything is visited).
    """
    label = _traversal_label(traversal).replace(" Traversal", "").lower()
    points: list[str] = []
    highlights: list[list[int]] = []
    seen_result_init = False
    def_count = 0
    code_lines = _detect_traversal_code_lines(code_snippet)

    def add(point: str, line: int | None) -> None:
        points.append(point)
        highlights.append([line, line] if line else [])

    add(f"Problem: trace {label} traversal on this tree, starting from root {root_id}.", None)
    for idx, raw in enumerate(code_snippet.split("\n")):
        line = raw.strip()
        low = line.lower()
        n = idx + 1
        if not line:
            continue
        if re.match(r"class\s+\w+", line):
            continue  # the class wrapper is not itself a setup action line
        if re.match(r"def\s+\w+", line):
            def_count += 1
            if def_count >= 2:
                break  # the helper begins — setup is the entry method only
            add("Define the entry method, which receives the tree's root and returns the collected result.", n)
            continue
        # Inside the entry method. Stop once the traversal work proper begins.
        if re.search(r"\bwhile\b|\bfor\b", low) or ".left" in low or ".right" in low:
            break
        if re.search(r"\.append\s*\(", low) and re.search(r"\.(val|value|data|key)\b", low):
            break
        if re.search(r"=\s*\[\s*\]", line) and not seen_result_init:
            seen_result_init = True
            add("Initialize an empty list to collect the traversal output before any node is visited.", n)
        elif re.search(r"=\s*(\[|deque\()", low) and ("root" in low or "start" in low):
            container = "queue" if ("queue" in low or "deque" in low) else ("stack" if "stack" in low else "container")
            add(f"Seed the {container} with the root node so the traversal has a starting point.", n)
        elif re.search(r"\bif\b.*\b(none|root|node)\b", low) and "return" not in low:
            add("Base case: if the tree or subtree is empty, return immediately with an empty result.", n)
        elif re.match(r"(self\.)?\w+\s*\(", line) and "return" not in low and "append" not in low:
            add("The entry method calls the helper to perform the traversal and fill the result list.", n)

    # Preview the implicit first move so the descent is not a silent jump from the
    # setup to the first visited node.
    if traversal == "inorder" and code_lines.get("recurse_left"):
        add(
            "When the helper runs, inorder recurses left as far as possible first — "
            "so the very first node actually visited is the tree's smallest (leftmost) value.",
            code_lines.get("recurse_left"),
        )
    elif traversal in ("level_order", "levelorder", "bfs") and code_lines.get("dequeue"):
        add(
            "The loop then repeatedly takes the front node off the queue to process it, "
            "level by level.",
            code_lines.get("dequeue"),
        )
    return points, highlights


def _safe_id(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_") or "scenario"


def _map_blueprint_visual_type(visual_type: str) -> tuple[str, str]:
    lowered = visual_type.strip().lower()
    if lowered in _BLUEPRINT_VISUAL_TYPE_MAP:
        return _BLUEPRINT_VISUAL_TYPE_MAP[lowered]
    return ("", "")


def _map_legacy_visual_type(legacy_type: str) -> tuple[str, str]:
    lowered = legacy_type.strip().lower()
    if lowered in _SUPPORTED_LEGACY_VISUAL_TYPES:
        return _SUPPORTED_LEGACY_VISUAL_TYPES[lowered]
    if "node_link" in lowered or lowered in {"tree", "graph"}:
        return ("node_link_diagram", "tree_hierarchy")
    if "array" in lowered or "sequence" in lowered:
        return ("indexed_sequence_diagram", "array_state")
    if "grid" in lowered or "matrix" in lowered:
        return ("grid_matrix_diagram", "matrix")
    if "code" in lowered:
        return ("code_execution_panel", "code_execution_trace")
    return ("", "")


def _coordinate_points(visual_plan: dict[str, Any]) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for index, raw_point in enumerate(
        visual_plan.get("data_points")
        or visual_plan.get("key_points")
        or visual_plan.get("points")
        or []
    ):
        x_value: Any = None
        y_value: Any = None
        label = f"P{index + 1}"
        if isinstance(raw_point, dict):
            x_value = raw_point.get("x")
            y_value = raw_point.get("y")
            label = str(raw_point.get("label") or raw_point.get("id") or label)
        elif isinstance(raw_point, (list, tuple)) and len(raw_point) >= 2:
            x_value = raw_point[0]
            y_value = raw_point[1]
        try:
            points.append(
                {
                    "id": f"point_{index + 1}",
                    "label": label,
                    "x": float(x_value),
                    "y": float(y_value),
                }
            )
        except (TypeError, ValueError):
            continue
    return points


def _coordinate_curves(visual_plan: dict[str, Any]) -> list[dict[str, Any]]:
    raw_curves = visual_plan.get("curves") or []
    curves: list[dict[str, Any]] = []
    for index, raw_curve in enumerate(raw_curves):
        if not isinstance(raw_curve, dict):
            continue
        curve_points = []
        for raw_point in raw_curve.get("points") or []:
            if isinstance(raw_point, dict):
                x_value = raw_point.get("x")
                y_value = raw_point.get("y")
            elif isinstance(raw_point, (list, tuple)) and len(raw_point) >= 2:
                x_value = raw_point[0]
                y_value = raw_point[1]
            else:
                continue
            try:
                curve_points.append({"x": float(x_value), "y": float(y_value)})
            except (TypeError, ValueError):
                continue
        if curve_points:
            curves.append(
                {
                    "id": str(raw_curve.get("id") or f"curve_{index + 1}"),
                    "label": str(raw_curve.get("label") or f"Curve {index + 1}"),
                    "points": curve_points,
                    "color": str(raw_curve.get("color") or "#7C4EF0"),
                }
            )
    return curves


def _float_or_default(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _intent_from_plan(plan: WorkedExamplePlan, base_type: str) -> VisualIntent:
    raw_intent = plan.get("visual_intent") or {}
    return {
        "base_type": base_type,
        "mode": str(raw_intent.get("mode") or "default"),
        "description": str(raw_intent.get("description") or plan.get("problem_setup") or ""),
        "purpose": str(raw_intent.get("purpose") or plan.get("terminal_state") or ""),
        "static_or_dynamic": "dynamic",
    }


def _is_usable_model(model: Any) -> bool:
    if not isinstance(model, dict):
        return False
    if not model.get("frames"):
        return False
    report = validate_visual_model(model, location="visual_model")
    return not report.errors()


def _first_highlight_range(card: dict[str, Any], line_count: int) -> list[int]:
    raw = card.get("highlight_lines_per_step") or []
    if raw and isinstance(raw, list):
        first = raw[0]
        if isinstance(first, list) and len(first) == 2:
            try:
                a, b = int(first[0]), int(first[1])
                if 1 <= a <= line_count and 1 <= b <= line_count and a <= b:
                    return [a, b]
            except (TypeError, ValueError):
                pass
    return [0, 0]


def needs_visual_refresh(lesson_json: Any) -> bool:
    """A cached lesson should re-enrich on read when it has no bridge metadata or was
    stamped by an OLDER `VISUAL_BRIDGE_VERSION` — so existing lessons pick up the latest
    fixes (real-content extraction, diagram/code separation, the gate, completion audit)
    without manual regeneration. Pure; importable without DB deps."""
    if not isinstance(lesson_json, dict) or not isinstance(lesson_json.get("lesson_cards"), list):
        return False
    metadata = lesson_json.get("metadata")
    if not isinstance(metadata, dict):
        return True
    bridge = metadata.get("visual_v2_bridge")
    if not isinstance(bridge, dict):
        return True
    return int(bridge.get("version") or 1) < VISUAL_BRIDGE_VERSION


def _has_v2_ref(card: dict[str, Any]) -> bool:
    ref = card.get("visual_v2_ref")
    return isinstance(ref, dict) and bool(ref.get("visual_model_id"))


_CODE_BASE_TYPES = ("code_execution_panel", "code_trace")


def _legacy_visual_is_degenerate(model: dict[str, Any]) -> bool:
    """Shape-agnostic validity gate (PROJECTOR_SYSTEM_SPEC INV-RENDER, applied to the
    legacy/static path which the projector pipeline never sees). True = malformed and
    should not ship: a graph with <2 nodes or dangling/duplicate/blank-label edges (the
    phantom-ring background bug), an empty array, or an empty grid."""
    if not isinstance(model, dict):
        return True
    base = model.get("base") or {}
    base_type = str(model.get("base_type") or "")
    if base_type == "node_link_diagram":
        nodes = base.get("nodes") or []
        if len([n for n in nodes if isinstance(n, dict)]) < 2:
            return True  # a "graph" of one node is not a graph
        try:
            from app.services.visual_v2.validators import validate_node_link_render
            return bool(validate_node_link_render(model))  # dangling edges, blank/dupe labels
        except Exception:  # noqa: BLE001 — never let the gate break a lesson
            return False
    if base_type == "indexed_sequence_diagram":
        return not (base.get("values"))
    if base_type == "grid_matrix_diagram":
        rows = base.get("rows") or base.get("cells") or base.get("grid") or []
        return not rows
    return False


def gate_legacy_visuals(lesson_json: dict[str, Any]) -> None:
    """Final, shape-agnostic guardrail over EVERY visual model in the lesson (so the
    legacy/static path is gated like the computed one). Drops (a) malformed/degenerate
    visuals and (b) a diagram slot that points at a CODE model (never show code as the
    'Diagram'). Cards whose visual is dropped simply render without it. Failure-safe."""
    import logging
    _gate_log = logging.getLogger(__name__)
    try:
        if not isinstance(lesson_json, dict):
            return
        models = {
            str(m.get("id")): m
            for m in (lesson_json.get("visual_models") or [])
            if isinstance(m, dict) and m.get("id")
        }
        bad: set[str] = {mid for mid, m in models.items() if _legacy_visual_is_degenerate(m)}

        for card in lesson_json.get("lesson_cards") or []:
            if not isinstance(card, dict):
                continue
            # A diagram slot must hold a DIAGRAM, never a code model (INV-DUAL-SLOT).
            dref = card.get("diagram_v2_ref")
            if isinstance(dref, dict):
                dm = models.get(str(dref.get("visual_model_id") or ""))
                if dm is not None and str(dm.get("base_type") or "") in _CODE_BASE_TYPES:
                    card.pop("diagram_v2_ref", None)
            # A LEGACY `array_state` guess on a worked example (the bridge's static
            # `_card_N` model) is misleading for sorting/array code — it shows one static
            # array, often the sorted output, with arbitrary pointers. The trace path
            # produces the real visual; when it didn't run, drop the guess (code-only)
            # rather than ship a wrong array. Fixture/projector models (non-`_card_`) are
            # left untouched.
            if str(card.get("blueprint_key") or card.get("card_type") or "").lower() == "worked_example":
                vref = card.get("visual_v2_ref")
                vm = models.get(str((vref or {}).get("visual_model_id") or "")) if isinstance(vref, dict) else None
                if (
                    vm is not None
                    and str(vm.get("base_type") or "") == "indexed_sequence_diagram"
                    and str(vm.get("mode") or "") == "array_state"
                    and "_card_" in str(vm.get("id") or "")
                ):
                    card.pop("visual_v2_ref", None)
                    bad.add(str(vm.get("id")))
            for ref_key in ("visual_v2_ref", "diagram_v2_ref"):
                ref = card.get(ref_key)
                if isinstance(ref, dict) and str(ref.get("visual_model_id") or "") in bad:
                    card.pop(ref_key, None)

        if bad:
            lesson_json["visual_models"] = [
                m for m in (lesson_json.get("visual_models") or [])
                if isinstance(m, dict) and str(m.get("id")) not in bad
            ]
            _gate_log.info("visual gate: dropped %d malformed visual(s)", len(bad))
    except Exception as exc:  # noqa: BLE001 — the gate must never break a lesson
        _gate_log.warning("visual gate failed: %s", exc)


def _is_worked_example_setup_card(card: dict[str, Any]) -> bool:
    if str(card.get("blueprint_key") or "").strip().lower() != "worked_example":
        return False
    metadata = card.get("metadata") if isinstance(card.get("metadata"), dict) else {}
    if metadata.get("worked_example_setup") is True:
        return True
    example_type = str(card.get("example_type") or "").strip().lower()
    if example_type in {"problem_setup", "initial_state", "worked_example_setup"}:
        return True
    title = str(card.get("title") or "").strip().lower()
    return "setup" in title or "initial state" in title or title.startswith("problem:")


def _dedupe_models(models: list[VisualModel]) -> list[VisualModel]:
    result: list[VisualModel] = []
    seen: set[str] = set()
    for model in models:
        model_id = str(model.get("id") or "")
        if not model_id or model_id in seen:
            continue
        result.append(model)
        seen.add(model_id)
    return result


def _filter_referenced_models(
    *model_groups: list[VisualModel],
    cards: list[Any],
) -> list[VisualModel]:
    """Keep only models currently referenced by cards.

    Static v2 refs are compiled before dynamic traces. When a dynamic trace
    attaches successfully it overwrites the static refs for those cards, so the
    earlier static models become unreachable and should not inflate the payload.
    """
    referenced_ids = {
        str(ref.get("visual_model_id"))
        for card in cards
        if isinstance(card, dict)
        for ref in [card.get("visual_v2_ref")]
        if isinstance(ref, dict) and ref.get("visual_model_id")
    }
    result: list[VisualModel] = []
    seen: set[str] = set()
    for models in model_groups:
        for model in models:
            model_id = str(model.get("id") or "")
            if not model_id or model_id in seen:
                continue
            if referenced_ids and model_id not in referenced_ids:
                continue
            result.append(model)
            seen.add(model_id)
    return result


def _unique_model_id(model_id: str, existing: dict[str, VisualModel]) -> str:
    if model_id not in existing:
        return model_id
    index = 2
    while f"{model_id}_{index}" in existing:
        index += 1
    return f"{model_id}_{index}"


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _rectangular_rows(
    rows: list[list[Any]],
    width: int | None = None,
    fill: str = "",
) -> list[list[str]]:
    """Force a 2-D value grid to be rectangular.

    A single short or over-long row from the LLM otherwise shifts every cell
    after it and breaks the renderer's column alignment (the tabular analogue
    of a degenerate tree). Short rows are padded with `fill`; over-long rows are
    truncated to `width`. When `width` is None the target is the widest row, so
    padding is lossless and nothing is dropped.
    """
    grid = [[str(value) for value in row] for row in rows if isinstance(row, list)]
    if not grid:
        return grid
    target = width if isinstance(width, int) and width > 0 else max(len(row) for row in grid)
    rectangular: list[list[str]] = []
    for row in grid:
        if len(row) < target:
            row = row + [fill] * (target - len(row))
        elif len(row) > target:
            row = row[:target]
        rectangular.append(row)
    return rectangular


def _visual_debug_enabled() -> bool:
    import os

    return os.environ.get("AZALEA_VISUAL_DEBUG", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _visual_model_debug(model: dict[str, Any]) -> dict[str, Any]:
    """Compact, human-readable view of a compiled VisualModel — the structured
    payload the frontend turns into a diagram. For node_link models this shows
    the base structure plus the per-frame trace state so a value mismatch (like
    a node labelled 40 in a 5..11 traversal) is visible at a glance.
    """
    base = model.get("base") or {}
    nodes = base.get("nodes") or [] if isinstance(base, dict) else []
    edges = base.get("edges") or [] if isinstance(base, dict) else []

    frames_debug: list[dict[str, Any]] = []
    for frame in model.get("frames") or []:
        if not isinstance(frame, dict):
            continue
        state = frame.get("state") or {}
        runtime = state.get("runtime_state") or {} if isinstance(state, dict) else {}
        frames_debug.append(
            {
                "index": frame.get("index"),
                "active_node": state.get("active_node") if isinstance(state, dict) else None,
                "completed_nodes": state.get("completed_nodes") if isinstance(state, dict) else None,
                "output": runtime.get("output") if isinstance(runtime, dict) else None,
                "call_stack": runtime.get("call_stack") if isinstance(runtime, dict) else None,
            }
        )

    return {
        "id": model.get("id"),
        "base_type": model.get("base_type"),
        "mode": model.get("mode"),
        "base_node_labels": [
            str(node.get("label") or node.get("id"))
            for node in nodes
            if isinstance(node, dict)
        ],
        "base_edges": [
            f"{edge.get('from')}->{edge.get('to')}"
            for edge in edges
            if isinstance(edge, dict)
        ],
        "frame_count": len(model.get("frames") or []),
        "frames": frames_debug,
    }
