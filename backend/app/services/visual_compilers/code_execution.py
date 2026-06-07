"""Code execution compiler — modes: code_walkthrough_growing,
code_execution_trace, debug_trace, recursive_execution, loop_trace,
condition_evaluation, input_output_trace.

Phase 2 status: SKELETON with growing-mode + execution-mode dispatch.
Full per-frame transitions for variable changes / call_stack push-pop
will be filled in during Phase 6 alongside the renderer.
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


_GROWING_MODES = frozenset({"code_walkthrough_growing"})


class CodeExecutionCompiler(VisualCompiler):
    base_type = "code_execution_panel"

    def compile(
        self,
        intent: VisualIntent,
        plan: WorkedExamplePlan | None,
        context: CompileContext,
    ) -> VisualModel:
        mode = intent["mode"]
        base_code, language = self._extract_base_code(plan, intent, context)
        line_count = base_code.count("\n") + 1 if base_code else 0

        base = {
            "code": base_code,
            "language": language,
            "line_count": line_count,
            "mode": mode,
        }

        if not base_code:
            return self._empty_model(intent)

        if plan is None:
            return self._compile_static(intent, base, context)

        if mode in _GROWING_MODES:
            return self._compile_growing(intent, plan, base, context)
        return self._compile_execution(intent, plan, base, context)

    def _extract_base_code(
        self,
        plan: WorkedExamplePlan | None,
        intent: VisualIntent,
        context: CompileContext,
    ) -> tuple[str, str]:
        if plan is not None:
            base_state = plan.get("base_state") or {}
            return (
                str(base_state.get("code") or "").strip(),
                str(base_state.get("language") or "python").strip(),
            )
        # Cross-card reuse: pull the code from a previously-compiled
        # code_execution model on the same lesson (e.g. a worked_example
        # card without its own plan reusing the code_walkthrough's source).
        for prior in context["already_compiled_models"].values():
            if (
                prior["base_type"] == self.base_type
                and prior["base"].get("code")
            ):
                prior_base = prior["base"]
                return (
                    str(prior_base.get("code") or "").strip(),
                    str(prior_base.get("language") or "python").strip(),
                )
        return ("", "python")

    def _empty_model(self, intent: VisualIntent) -> VisualModel:
        return {
            "id": "empty_code_execution",
            "base_type": self.base_type,
            "mode": intent["mode"],
            "base": {"code": "", "language": "python", "line_count": 0, "mode": intent["mode"]},
            "frames": [],
            "element_catalog": [],
        }

    def _compile_static(
        self,
        intent: VisualIntent,
        base: dict[str, Any],
        context: CompileContext,
    ) -> VisualModel:
        frame_state = {
            "visible_until_line": base["line_count"],
            "highlight_lines": [0, 0],
            "variables": [],
            "call_stack": [],
            "output": [],
        }
        frame: VisualFrame = {
            "index": 0,
            "state": frame_state,
            "highlights": {"line_range": [0, 0]},
            "annotations": [],
            "selectable_elements": self.selectable_elements(frame_state, base, intent["mode"]),
            "transitions": [],
        }
        return {
            "id": f"code_static_{context['topic_id']}",
            "base_type": self.base_type,
            "mode": intent["mode"],
            "base": base,
            "frames": [frame],
            "element_catalog": self._catalog(base, [frame]),
        }

    def _compile_growing(
        self,
        intent: VisualIntent,
        plan: WorkedExamplePlan,
        base: dict[str, Any],
        context: CompileContext,
    ) -> VisualModel:
        """Growing mode: each frame reveals more lines."""
        frames: list[VisualFrame] = []
        prev_state: dict[str, Any] | None = None
        for index, step in enumerate(plan["steps"]):
            state = self._normalize_state(step.get("state_after") or {}, base)
            transitions = self.transitions(prev_state, state, base, intent["mode"], step.get("transition_hints") or [])
            frame: VisualFrame = {
                "index": index,
                "state": state,
                "highlights": {"line_range": state["highlight_lines"]},
                "annotations": [],
                "selectable_elements": self.selectable_elements(state, base, intent["mode"]),
                "transitions": transitions,
            }
            frames.append(frame)
            prev_state = state
        return {
            "id": f"code_growing_{context['topic_id']}_{plan['id']}",
            "base_type": self.base_type,
            "mode": intent["mode"],
            "base": base,
            "frames": frames,
            "element_catalog": self._catalog(base, frames),
        }

    def _compile_execution(
        self,
        intent: VisualIntent,
        plan: WorkedExamplePlan,
        base: dict[str, Any],
        context: CompileContext,
    ) -> VisualModel:
        """Execution mode: full code visible from frame 1, highlight moves."""
        frames: list[VisualFrame] = []
        prev_state: dict[str, Any] | None = None
        for index, step in enumerate(plan["steps"]):
            state = self._normalize_state(step.get("state_after") or {}, base)
            # Force full code visible in execution mode
            state["visible_until_line"] = base["line_count"]
            transitions = self.transitions(prev_state, state, base, intent["mode"], step.get("transition_hints") or [])
            frame: VisualFrame = {
                "index": index,
                "state": state,
                "highlights": {"line_range": state["highlight_lines"]},
                "annotations": [],
                "selectable_elements": self.selectable_elements(state, base, intent["mode"]),
                "transitions": transitions,
            }
            frames.append(frame)
            prev_state = state
        return {
            "id": f"code_exec_{context['topic_id']}_{plan['id']}",
            "base_type": self.base_type,
            "mode": intent["mode"],
            "base": base,
            "frames": frames,
            "element_catalog": self._catalog(base, frames),
        }

    def _normalize_state(self, raw: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
        line_count = base["line_count"]
        visible = raw.get("visible_until_line")
        try:
            visible_int = int(visible) if visible is not None else line_count
        except (TypeError, ValueError):
            visible_int = line_count
        visible_int = max(0, min(visible_int, line_count))

        highlight = raw.get("highlight_lines") or [0, 0]
        if isinstance(highlight, list) and len(highlight) == 2:
            try:
                hi = (int(highlight[0]), int(highlight[1]))
            except (TypeError, ValueError):
                hi = (0, 0)
        else:
            hi = (0, 0)

        return {
            "visible_until_line": visible_int,
            "highlight_lines": list(hi),
            "variables": raw.get("variables") or [],
            "call_stack": [str(x) for x in (raw.get("call_stack") or [])],
            "output": [str(x) for x in (raw.get("output") or [])],
        }

    def selectable_elements(
        self,
        frame_state: dict[str, Any],
        base: dict[str, Any],
        mode: str,
    ) -> list[SelectableElement]:
        elements: list[SelectableElement] = []
        keyboard_index = 0
        visible = int(frame_state.get("visible_until_line") or 0)
        for line_num in range(1, visible + 1):
            line_text = str((base.get("code") or "").splitlines()[line_num - 1]) if line_num <= len((base.get("code") or "").splitlines()) else ""
            elements.append({
                "element_id": f"code_line_{line_num}",
                "element_type": "code_line",
                "semantic_label": f"line {line_num}",
                "bounds": {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0},
                "aria_label": localize_aria("code_line", line_number=line_num, content=line_text),
                "keyboard_index": keyboard_index,
                "payload": {"line_number": line_num},
            })
            keyboard_index += 1
        for i, var in enumerate(frame_state.get("variables") or []):
            if not isinstance(var, dict):
                continue
            name = str(var.get("name") or f"var_{i}")
            value = str(var.get("value") or "")
            elements.append({
                "element_id": f"code_variable_{name}",
                "element_type": "code_variable",
                "semantic_label": f"variable {name} = {value}",
                "bounds": {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0},
                "aria_label": localize_aria("code_variable", name=name, value=value),
                "keyboard_index": keyboard_index,
                "payload": {"name": name, "value": value},
            })
            keyboard_index += 1
        return elements

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
        transitions: list[Transition] = []

        # Highlight line range moves
        prev_hi = prev_frame_state.get("highlight_lines") or [0, 0]
        curr_hi = curr_frame_state.get("highlight_lines") or [0, 0]
        if list(prev_hi) != list(curr_hi):
            # Use the first line of the new range as the target element
            target_line = curr_hi[0] if curr_hi else 0
            transitions.append({
                "kind": "move",
                "target_element_id": f"highlight_bar",
                "duration_ms": 250,
                "delay_ms": 0,
                "easing": "ease_in_out",
                "spec": {"from_range": list(prev_hi), "to_range": list(curr_hi)},
            })

        # Variable value changes
        prev_vars = {
            str(v.get("name")): str(v.get("value") or "")
            for v in (prev_frame_state.get("variables") or [])
            if isinstance(v, dict) and v.get("name")
        }
        curr_vars = {
            str(v.get("name")): str(v.get("value") or "")
            for v in (curr_frame_state.get("variables") or [])
            if isinstance(v, dict) and v.get("name")
        }
        for name, curr_value in curr_vars.items():
            prev_value = prev_vars.get(name)
            # debug_trace mode: pulse changed variables for extra attention
            # (the variable change is the main thing the learner is tracking).
            pulse = mode == "debug_trace"
            if prev_value is None:
                transitions.append({
                    "kind": "appear",
                    "target_element_id": f"code_variable_{name}",
                    "duration_ms": 250,
                    "delay_ms": 200,
                    "easing": "ease_out",
                    "spec": {"value": curr_value},
                })
            elif prev_value != curr_value:
                transitions.append({
                    "kind": "value_change",
                    "target_element_id": f"code_variable_{name}",
                    "duration_ms": 300,
                    "delay_ms": 200,
                    "easing": "ease_in_out",
                    "spec": {"from_value": prev_value, "to_value": curr_value},
                })
                if pulse:
                    transitions.append({
                        "kind": "highlight_pulse",
                        "target_element_id": f"code_variable_{name}",
                        "duration_ms": 400,
                        "delay_ms": 200,
                        "easing": "ease_out",
                        "spec": {"color": "#D32F2F", "cycles": 2},
                    })
        # Variables removed from scope (loop ended, function returned)
        for name in prev_vars.keys() - curr_vars.keys():
            transitions.append({
                "kind": "disappear",
                "target_element_id": f"code_variable_{name}",
                "duration_ms": 200,
                "delay_ms": 0,
                "easing": "ease_in",
                "spec": {},
            })

        # Call stack push/pop visualization for recursive_execution mode.
        if mode == "recursive_execution":
            prev_stack = prev_frame_state.get("call_stack") or []
            curr_stack = curr_frame_state.get("call_stack") or []
            if len(curr_stack) > len(prev_stack):
                transitions.append({
                    "kind": "appear",
                    "target_element_id": f"code_frame_{len(curr_stack) - 1}",
                    "duration_ms": 250,
                    "delay_ms": 0,
                    "easing": "ease_out",
                    "spec": {"frame_label": str(curr_stack[-1])},
                })
            elif len(curr_stack) < len(prev_stack):
                transitions.append({
                    "kind": "disappear",
                    "target_element_id": f"code_frame_{len(prev_stack) - 1}",
                    "duration_ms": 250,
                    "delay_ms": 0,
                    "easing": "ease_in",
                    "spec": {},
                })

        return transitions

    def _catalog(self, base: dict[str, Any], frames: list[VisualFrame]) -> list:
        catalog: list = []
        for line_num in range(1, base["line_count"] + 1):
            catalog.append({
                "element_id": f"code_line_{line_num}",
                "element_type": "code_line",
                "first_frame": 0,
                "last_frame": -1,
                "initial_bounds": {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0},
            })
        return catalog

    # ---- LLM-compliance fallback ------------------------------------------

    def synthesize_plan_from_legacy_cards(
        self,
        legacy_cards: list[dict[str, Any]],
        context: CompileContext,
    ) -> WorkedExamplePlan | None:
        """Reconstruct a code_execution plan from legacy lean cards.

        Pulls base_state.code from the last code_walkthrough card's
        accumulated `code_snippet` (legacy code_walkthrough cards grow
        the snippet across the topic). Per-step state_after derived from
        each worked_example card's `highlight_lines_per_step` and points
        text (variable mentions).
        """
        import re

        # Find the longest code_snippet across code_walkthrough cards —
        # legacy code_walkthrough cards grow the snippet, so the last
        # (longest) one is the complete implementation.
        canonical_code = ""
        canonical_language = "python"
        for card in legacy_cards:
            blueprint = str(card.get("blueprint_key") or "").strip().lower()
            if blueprint not in ("code_walkthrough", "coding_implementation", "worked_example"):
                continue
            snippet = str(card.get("code_snippet") or "").strip()
            if len(snippet) > len(canonical_code):
                canonical_code = snippet
                canonical_language = str(card.get("code_language") or "python").strip() or "python"
        if not canonical_code:
            return None

        line_count = canonical_code.count("\n") + 1

        walkthrough_cards = [
            c for c in legacy_cards
            if str(c.get("blueprint_key") or "").strip().lower() == "code_walkthrough"
        ]
        worked_cards = [
            c for c in legacy_cards
            if str(c.get("blueprint_key") or "").strip().lower() == "worked_example"
        ]
        trace_cards = walkthrough_cards or worked_cards
        if not trace_cards:
            return None

        steps: list[dict[str, Any]] = []
        for index, card in enumerate(trace_cards):
            highlight: list[int] = []
            raw_highlight = card.get("highlight_lines_per_step") or []
            if (
                isinstance(raw_highlight, list)
                and raw_highlight
                and isinstance(raw_highlight[0], list)
                and len(raw_highlight[0]) == 2
            ):
                first = raw_highlight[0]
                try:
                    a, b = int(first[0]), int(first[1])
                    if 1 <= a <= line_count and 1 <= b <= line_count and a <= b:
                        highlight = [a, b]
                except (TypeError, ValueError):
                    pass
            if not highlight:
                # Try to parse "line N" from text
                text = " ".join(str(p) for p in (card.get("points") or []))
                match = re.search(r"\bline\s+(\d+)\b", text, re.IGNORECASE)
                if match:
                    n = int(match.group(1))
                    if 1 <= n <= line_count:
                        highlight = [n, n]
            card_code = str(card.get("code_snippet") or "").strip("\n")
            visible_until_line = len(card_code.splitlines()) if card_code else line_count
            visual_plan = card.get("visual_plan")
            if isinstance(visual_plan, dict):
                try:
                    planned_max = int(visual_plan.get("max_line") or 0)
                except (TypeError, ValueError):
                    planned_max = 0
                if planned_max > 0:
                    visible_until_line = planned_max
            visible_until_line = max(1, min(visible_until_line, line_count))
            if not highlight and walkthrough_cards:
                highlight = [visible_until_line, visible_until_line]
            # Variable trace from text: "<name>=<value>"
            text = " ".join(str(p) for p in (card.get("points") or []))
            variables: list[dict[str, str]] = []
            seen_names: set[str] = set()
            for match in re.finditer(r"\b([A-Za-z_]\w{0,15})\s*=\s*([\-\d\w\[\]., ]{1,30})", text):
                name = match.group(1).strip()
                value = match.group(2).strip().rstrip(",.")
                if name and name not in seen_names and name.lower() not in ("if", "for", "while", "return", "def", "and", "or", "in"):
                    variables.append({"name": name, "value": value})
                    seen_names.add(name)
                    if len(variables) >= 6:
                        break
            action = str(card.get("title") or "").strip()
            if not action:
                action = (
                    f"Code Walkthrough: Line {visible_until_line}"
                    if walkthrough_cards
                    else f"Step {index + 1}"
                )
            reason = str(card.get("learning_job") or "").strip()
            steps.append({
                "step_number": index + 1,
                "action": action,
                "reason": reason,
                "text_points": [
                    str(p).rstrip() for p in (card.get("points") or []) if str(p).strip()
                ],
                "state_after": {
                    "visible_until_line": visible_until_line,
                    "highlight_lines": highlight or [0, 0],
                    "variables": variables,
                    "call_stack": [],
                    "output": [],
                },
                "transition_hints": [],
            })

        if not steps:
            return None

        visual_intent = {
            "base_type": self.base_type,
            "mode": "code_execution_trace",
            "description": "Synthesized from legacy cards.",
            "purpose": "Reconstructed code execution trace.",
            "static_or_dynamic": "dynamic",
        }
        return {
            "id": f"synth_code_execution_{context.get('topic_id', 'unknown')}",
            "visual_intent": visual_intent,
            "problem_setup": "Trace the code line by line.",
            "terminal_state": "Trace complete.",
            "base_state": {
                "code": canonical_code,
                "language": canonical_language,
            },
            "steps": steps,
        }


register(CodeExecutionCompiler())
