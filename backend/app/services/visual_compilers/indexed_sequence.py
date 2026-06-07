"""Indexed sequence compiler — modes: array_state, string_state,
binary_search_range, sliding_window, two_pointer, sorting_pass,
merge_partition, token_sequence, prefix_sum.

Phase 2 status: SKELETON with pointer-move + cell-swap transitions.
Full per-mode logic ports during Phase 6.
"""

from __future__ import annotations

from typing import Any

from app.schemas.visual_v2 import (
    CompileContext,
    SelectableElement,
    Transition,
    TransitionHint,
    VisualFrame,
    VisualIntent,
    VisualModel,
    WorkedExamplePlan,
)
from app.services.v2_aria_localization import localize_aria
from app.services.visual_compilers import register
from app.services.visual_compilers.base import VisualCompiler


class IndexedSequenceCompiler(VisualCompiler):
    base_type = "indexed_sequence_diagram"

    def compile(
        self,
        intent: VisualIntent,
        plan: WorkedExamplePlan | None,
        context: CompileContext,
    ) -> VisualModel:
        values, pointer_definitions = self._extract_base(plan, intent, context)
        if not values:
            return self._empty_model(intent)

        base = {
            "values": values,
            "indices": list(range(len(values))),
            "pointer_definitions": pointer_definitions,
            "mode": intent["mode"],
        }

        if plan is None:
            return self._compile_static(intent, base, context)

        return self._compile_dynamic(intent, plan, base, context)

    def _extract_base(
        self,
        plan: WorkedExamplePlan | None,
        intent: VisualIntent,
        context: CompileContext,
    ) -> tuple[list[str], list[dict[str, Any]]]:
        if plan is not None:
            base_state = plan.get("base_state") or {}
            values = [str(v) for v in (base_state.get("values") or [])]
            ptr_defs = list(base_state.get("pointer_definitions") or [])
            return values, ptr_defs
        # Cross-card reuse: when this card has no plan, inherit the array
        # values + pointer definitions from a previously-compiled
        # indexed_sequence model on the same lesson. Prevents per-card
        # array hallucinations.
        for prior in context["already_compiled_models"].values():
            if (
                prior["base_type"] == self.base_type
                and prior["base"].get("values")
            ):
                prior_base = prior["base"]
                return (
                    [str(v) for v in (prior_base.get("values") or [])],
                    list(prior_base.get("pointer_definitions") or []),
                )
        return [], []

    def _empty_model(self, intent: VisualIntent) -> VisualModel:
        return {
            "id": "empty_indexed_sequence",
            "base_type": self.base_type,
            "mode": intent["mode"],
            "base": {"values": [], "indices": [], "pointer_definitions": [], "mode": intent["mode"]},
            "frames": [],
            "element_catalog": [],
        }

    def _compile_static(
        self,
        intent: VisualIntent,
        base: dict[str, Any],
        context: CompileContext,
    ) -> VisualModel:
        state = {
            "pointers": [],
            "ranges": [],
            "highlighted_cells": [],
            "swapped_cells": None,
            "sorted_prefix_end": None,
        }
        frame: VisualFrame = {
            "index": 0,
            "state": state,
            "highlights": {},
            "annotations": [],
            "selectable_elements": self.selectable_elements(state, base, intent["mode"]),
            "transitions": [],
        }
        return {
            "id": f"sequence_static_{context['topic_id']}",
            "base_type": self.base_type,
            "mode": intent["mode"],
            "base": base,
            "frames": [frame],
            "element_catalog": self._catalog(base),
        }

    def _compile_dynamic(
        self,
        intent: VisualIntent,
        plan: WorkedExamplePlan,
        base: dict[str, Any],
        context: CompileContext,
    ) -> VisualModel:
        frames: list[VisualFrame] = []
        prev_state: dict[str, Any] | None = None
        for index, step in enumerate(plan["steps"]):
            state = self._normalize_state(step.get("state_after") or {}, base)
            transitions = self.transitions(prev_state, state, base, intent["mode"], step.get("transition_hints") or [])
            frame: VisualFrame = {
                "index": index,
                "state": state,
                "highlights": {},
                "annotations": [],
                "selectable_elements": self.selectable_elements(state, base, intent["mode"]),
                "transitions": transitions,
            }
            frames.append(frame)
            prev_state = state
        return {
            "id": f"sequence_{context['topic_id']}_{plan['id']}",
            "base_type": self.base_type,
            "mode": intent["mode"],
            "base": base,
            "frames": frames,
            "element_catalog": self._catalog(base),
        }

    def _normalize_state(self, raw: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
        n = len(base["values"])
        pointers = []
        for p in (raw.get("pointers") or []):
            if not isinstance(p, dict):
                continue
            ptr_id = str(p.get("id") or p.get("name") or "").strip()
            try:
                pos = int(p.get("position"))
            except (TypeError, ValueError):
                continue
            if ptr_id and 0 <= pos < n:
                pointers.append({"id": ptr_id, "position": pos, "label": str(p.get("label") or ptr_id)})

        ranges = []
        for r in (raw.get("ranges") or []):
            if not isinstance(r, dict):
                continue
            try:
                start = int(r.get("start"))
                end = int(r.get("end"))
            except (TypeError, ValueError):
                continue
            if 0 <= start <= end < n:
                ranges.append({
                    "id": str(r.get("id") or f"range_{start}_{end}"),
                    "start": start,
                    "end": end,
                    "label": str(r.get("label") or ""),
                })

        return {
            "pointers": pointers,
            "ranges": ranges,
            "highlighted_cells": [int(c) for c in (raw.get("highlighted_cells") or []) if isinstance(c, int) and 0 <= c < n],
            "swapped_cells": raw.get("swapped_cells"),
            "sorted_prefix_end": raw.get("sorted_prefix_end"),
        }

    def selectable_elements(
        self,
        frame_state: dict[str, Any],
        base: dict[str, Any],
        mode: str,
    ) -> list[SelectableElement]:
        elements: list[SelectableElement] = []
        keyboard_index = 0
        # Cells
        for i, value in enumerate(base["values"]):
            elements.append({
                "element_id": f"cell_{i}",
                "element_type": "cell",
                "semantic_label": f"cell at index {i}, value {value}",
                "bounds": {"x": float(i) * 10.0, "y": 50.0, "width": 10.0, "height": 10.0},
                "aria_label": localize_aria("cell", index=i, value=value),
                "keyboard_index": keyboard_index,
                "payload": {"index": i, "value": value},
            })
            keyboard_index += 1
        # Pointers
        for ptr in (frame_state.get("pointers") or []):
            elements.append({
                "element_id": f"pointer_{ptr['id']}",
                "element_type": "pointer",
                "semantic_label": f"pointer {ptr.get('label') or ptr['id']} at position {ptr['position']}",
                "bounds": {"x": float(ptr["position"]) * 10.0, "y": 40.0, "width": 10.0, "height": 10.0},
                "aria_label": localize_aria(
                    "pointer",
                    label=ptr.get("label") or ptr["id"],
                    position=ptr["position"],
                ),
                "keyboard_index": keyboard_index,
                "payload": {"id": ptr["id"], "position": ptr["position"]},
            })
            keyboard_index += 1
        return elements

    def _mode_palette(self, mode: str) -> dict[str, Any]:
        """Per-mode accent + pointer dwell. Different array algorithms get
        recognizable color cues so the learner knows what they're tracing.
        """
        if mode == "binary_search_range":
            return {"accent": "#7C4EF0", "pointer_duration_ms": 450, "range_pulse_color": "#7C4EF0"}
        if mode == "sliding_window":
            return {"accent": "#1976D2", "pointer_duration_ms": 350, "range_pulse_color": "#1976D2"}
        if mode == "two_pointer":
            return {"accent": "#2E7D32", "pointer_duration_ms": 380, "range_pulse_color": "#2E7D32"}
        if mode == "sorting_pass":
            return {"accent": "#E76F51", "pointer_duration_ms": 400, "range_pulse_color": "#E76F51"}
        if mode == "merge_partition":
            return {"accent": "#5B2EE0", "pointer_duration_ms": 400, "range_pulse_color": "#5B2EE0"}
        if mode == "prefix_sum":
            return {"accent": "#7C4EF0", "pointer_duration_ms": 300, "range_pulse_color": "#7C4EF0"}
        # array_state, string_state, token_sequence — generic default
        return {"accent": "#7C4EF0", "pointer_duration_ms": 400, "range_pulse_color": "#7C4EF0"}

    def transitions(
        self,
        prev_frame_state: dict[str, Any] | None,
        curr_frame_state: dict[str, Any],
        base: dict[str, Any],
        mode: str,
        hints: list[TransitionHint],
    ) -> list[Transition]:
        if prev_frame_state is None:
            return []
        palette = self._mode_palette(mode)
        transitions: list[Transition] = []

        prev_pointers = {p["id"]: p for p in (prev_frame_state.get("pointers") or [])}
        curr_pointers = {p["id"]: p for p in (curr_frame_state.get("pointers") or [])}

        # Pointer moves
        for ptr_id, curr in curr_pointers.items():
            prev = prev_pointers.get(ptr_id)
            if prev is None:
                transitions.append({
                    "kind": "appear",
                    "target_element_id": f"pointer_{ptr_id}",
                    "duration_ms": 250,
                    "delay_ms": 0,
                    "easing": "ease_out",
                    "spec": {"position": curr["position"]},
                })
            elif prev["position"] != curr["position"]:
                transitions.append({
                    "kind": "move",
                    "target_element_id": f"pointer_{ptr_id}",
                    "duration_ms": palette["pointer_duration_ms"],
                    "delay_ms": 100,
                    "easing": "ease_in_out",
                    "spec": {
                        "from": {"x": float(prev["position"]) * 10.0, "y": 40.0},
                        "to": {"x": float(curr["position"]) * 10.0, "y": 40.0},
                    },
                })
        for ptr_id in prev_pointers:
            if ptr_id not in curr_pointers:
                transitions.append({
                    "kind": "disappear",
                    "target_element_id": f"pointer_{ptr_id}",
                    "duration_ms": 200,
                    "delay_ms": 0,
                    "easing": "ease_in",
                    "spec": {},
                })

        # Cell swaps
        prev_swap = prev_frame_state.get("swapped_cells")
        curr_swap = curr_frame_state.get("swapped_cells")
        if curr_swap and curr_swap != prev_swap and isinstance(curr_swap, list) and len(curr_swap) == 2:
            transitions.append({
                "kind": "swap",
                "target_element_id": f"cell_{curr_swap[0]}",
                "duration_ms": 400,
                "delay_ms": 0,
                "easing": "ease_in_out",
                "spec": {"other_element_id": f"cell_{curr_swap[1]}"},
            })

        # Mode-specific: range expansion/contraction for sliding_window +
        # binary_search_range. Pulse the range start/end pointers so the
        # learner sees the window resize.
        if mode in ("sliding_window", "binary_search_range", "two_pointer"):
            prev_ranges = {r.get("id", ""): r for r in (prev_frame_state.get("ranges") or [])}
            curr_ranges = {r.get("id", ""): r for r in (curr_frame_state.get("ranges") or [])}
            for range_id, curr_range in curr_ranges.items():
                prev_range = prev_ranges.get(range_id)
                if prev_range and (
                    prev_range.get("start") != curr_range.get("start")
                    or prev_range.get("end") != curr_range.get("end")
                ):
                    # Range shrunk / grew — pulse the bounding cells.
                    for endpoint in (curr_range.get("start"), curr_range.get("end")):
                        if endpoint is not None:
                            transitions.append({
                                "kind": "highlight_pulse",
                                "target_element_id": f"cell_{endpoint}",
                                "duration_ms": 350,
                                "delay_ms": 150,
                                "easing": "ease_out",
                                "spec": {"color": palette["range_pulse_color"], "cycles": 1},
                            })

        # Mode-specific: sorting_pass grows the sorted prefix from the left.
        # Pulse the newly-sorted cell so the learner sees the prefix advance.
        if mode in ("sorting_pass", "merge_partition"):
            prev_sorted = prev_frame_state.get("sorted_prefix_end")
            curr_sorted = curr_frame_state.get("sorted_prefix_end")
            if isinstance(curr_sorted, int) and (
                not isinstance(prev_sorted, int) or curr_sorted > prev_sorted
            ):
                start = (prev_sorted + 1) if isinstance(prev_sorted, int) else 0
                ids = [f"cell_{i}" for i in range(start, curr_sorted + 1)]
                if len(ids) > 1:
                    transitions.append({
                        "kind": "stagger_group",
                        "target_element_id": ids[0],
                        "duration_ms": 250 * len(ids),
                        "delay_ms": 0,
                        "easing": "ease_out",
                        "spec": {"group_element_ids": ids, "stagger_ms": 100},
                    })
                else:
                    for cid in ids:
                        transitions.append({
                            "kind": "style_change",
                            "target_element_id": cid,
                            "duration_ms": 300,
                            "delay_ms": 50,
                            "easing": "ease_out",
                            "spec": {"from_style": "unsorted", "to_style": "sorted"},
                        })

        return transitions

    def _catalog(self, base: dict[str, Any]) -> list:
        return [
            {
                "element_id": f"cell_{i}",
                "element_type": "cell",
                "first_frame": 0,
                "last_frame": -1,
                "initial_bounds": {"x": float(i) * 10.0, "y": 50.0, "width": 10.0, "height": 10.0},
            }
            for i in range(len(base["values"]))
        ]

    # ---- LLM-compliance fallback ------------------------------------------

    def synthesize_plan_from_legacy_cards(
        self,
        legacy_cards: list[dict[str, Any]],
        context: CompileContext,
    ) -> WorkedExamplePlan | None:
        """Reconstruct an indexed_sequence plan from legacy lean cards.

        Pulls base_state.values + pointer_definitions from the background
        card's `visual_array_values` / `visual_array_pointers`. Per-step
        state_after extracted from each worked_example card's text
        (l=N, r=N, m=N patterns; cell highlights from visual_focus).
        """
        import re

        # Find background card with array values
        bg_values: list[str] = []
        bg_pointer_defs: list[dict[str, Any]] = []
        for card in legacy_cards:
            if str(card.get("blueprint_key") or "").strip().lower() != "background":
                continue
            visual_type = str(card.get("visual_type") or "").strip().lower()
            if "array" not in visual_type and "sequence" not in visual_type:
                continue
            raw_values = card.get("visual_array_values") or []
            bg_values = [str(v) for v in raw_values if str(v).strip()]
            # Pointer definitions inferred from visual_array_pointers
            raw_pointers = card.get("visual_array_pointers") or []
            for p in raw_pointers:
                if not isinstance(p, dict):
                    continue
                pid = str(p.get("id") or p.get("name") or p.get("label") or "").strip()
                if pid:
                    bg_pointer_defs.append({"id": pid, "label": str(p.get("label") or pid)})
            if bg_values:
                break
        if not bg_values:
            return None

        worked_cards = [
            c for c in legacy_cards
            if str(c.get("blueprint_key") or "").strip().lower() == "worked_example"
        ]
        if not worked_cards:
            return None

        # Discover pointer ids from text if background didn't list them
        inferred_ids: set[str] = set()
        if not bg_pointer_defs:
            text_blob = " ".join(
                str(p) for card in worked_cards for p in (card.get("points") or [])
            ).lower()
            for match in re.finditer(r"\b([lrmijk])\s*=\s*\d", text_blob):
                inferred_ids.add(match.group(1))
            bg_pointer_defs = [{"id": pid, "label": pid} for pid in sorted(inferred_ids)]

        n_values = len(bg_values)
        steps: list[dict[str, Any]] = []
        for index, card in enumerate(worked_cards):
            text = " ".join(str(p) for p in (card.get("points") or []))
            pointers: list[dict[str, Any]] = []
            for ptr_def in bg_pointer_defs:
                pid = ptr_def["id"]
                match = re.search(
                    rf"\b{re.escape(pid)}\s*=\s*(\d+)\b",
                    text,
                    re.IGNORECASE,
                )
                if match:
                    pos = int(match.group(1))
                    if 0 <= pos < n_values:
                        pointers.append({
                            "id": pid,
                            "position": pos,
                            "label": ptr_def["label"],
                        })
            highlighted: list[int] = []
            for match in re.finditer(r"(?:check|highlight|active)\s+(?:index|position|cell)\s+(\d+)", text, re.IGNORECASE):
                idx = int(match.group(1))
                if 0 <= idx < n_values and idx not in highlighted:
                    highlighted.append(idx)
            action = str(card.get("title") or "").strip() or f"Step {index + 1}"
            reason = str(card.get("learning_job") or "").strip()
            steps.append({
                "step_number": index + 1,
                "action": action,
                "reason": reason,
                "text_points": [
                    str(p).rstrip() for p in (card.get("points") or []) if str(p).strip()
                ],
                "state_after": {
                    "pointers": pointers,
                    "ranges": [],
                    "highlighted_cells": highlighted,
                    "swapped_cells": None,
                    "sorted_prefix_end": None,
                },
                "transition_hints": [],
            })

        if not steps:
            return None

        visual_intent = {
            "base_type": self.base_type,
            "mode": context.get("visual_domain") or "array_state",
            "description": "Synthesized from legacy cards.",
            "purpose": "Reconstructed trace.",
            "static_or_dynamic": "dynamic",
        }
        return {
            "id": f"synth_indexed_sequence_{context.get('topic_id', 'unknown')}",
            "visual_intent": visual_intent,
            "problem_setup": f"Trace through {n_values}-element sequence.",
            "terminal_state": "Trace complete.",
            "base_state": {
                "values": bg_values,
                "pointer_definitions": bg_pointer_defs,
            },
            "steps": steps,
        }


register(IndexedSequenceCompiler())
