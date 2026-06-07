"""Formula / symbolic expression compiler.

Supports formula breakdowns, substitutions, algebraic transformations,
calculus derivations, recurrence expansions, and similar symbolic flows.

State shape:
  base.expression              : str
  base.symbols                 : list[{symbol, meaning, value?}]
  state_after.active_symbol    : str | null
  state_after.active_expression: str | null
  state_after.substitution     : dict[str, str]
  state_after.transformed_expression : str
  state_after.equivalence_chain: list[str]
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


class FormulaCompiler(VisualCompiler):
    base_type = "formula_symbolic_expression"

    def compile(
        self,
        intent: VisualIntent,
        plan: WorkedExamplePlan | None,
        context: CompileContext,
    ) -> VisualModel:
        base = self._build_base(plan, intent, context)
        if not base.get("expression") and not base.get("symbols"):
            return self._empty_model(intent)
        if plan is None:
            return self._compile_static(intent, base, context)
        return self._compile_dynamic(intent, plan, base, context)

    # ---- base -----------------------------------------------------------

    def _build_base(
        self,
        plan: WorkedExamplePlan | None,
        intent: VisualIntent,
        context: CompileContext,
    ) -> dict[str, Any]:
        base_state = plan.get("base_state") if plan is not None else {}
        if not isinstance(base_state, dict):
            base_state = {}
        symbols = []
        for index, raw in enumerate(base_state.get("symbols") or []):
            if not isinstance(raw, dict):
                continue
            symbol = str(raw.get("symbol") or raw.get("name") or "").strip()
            if not symbol:
                continue
            symbols.append(
                {
                    "symbol": symbol,
                    "meaning": str(raw.get("meaning") or raw.get("description") or "").strip(),
                    "value": str(raw.get("value") or "").strip(),
                    "element_id": str(raw.get("element_id") or f"symbol_{symbol}"),
                }
            )
        built = {
            "mode": intent["mode"],
            "expression": str(base_state.get("expression") or "").strip(),
            "symbols": symbols,
            "assumptions": [str(x) for x in (base_state.get("assumptions") or [])],
            "purpose": intent["purpose"],
        }
        # Cross-card reuse: when this card has no plan and no symbols/expression
        # of its own, inherit from a previously-compiled formula model (e.g. an
        # edge-case card reusing the background card's formula structure).
        if plan is None and not built["expression"] and not built["symbols"]:
            for prior in context["already_compiled_models"].values():
                if prior["base_type"] == self.base_type and (
                    prior["base"].get("expression") or prior["base"].get("symbols")
                ):
                    import copy as _copy
                    return _copy.deepcopy(prior["base"])
        return built

    def _empty_model(self, intent: VisualIntent) -> VisualModel:
        return {
            "id": "empty_formula",
            "base_type": self.base_type,
            "mode": intent["mode"],
            "base": {
                "expression": "",
                "symbols": [],
                "assumptions": [],
                "mode": intent["mode"],
            },
            "frames": [],
            "element_catalog": [],
        }

    # ---- static ---------------------------------------------------------

    def _compile_static(
        self,
        intent: VisualIntent,
        base: dict[str, Any],
        context: CompileContext,
    ) -> VisualModel:
        state = self._normalize_state({}, base)
        frame: VisualFrame = {
            "index": 0,
            "state": state,
            "highlights": {},
            "annotations": [],
            "selectable_elements": self.selectable_elements(state, base, intent["mode"]),
            "transitions": [],
        }
        return {
            "id": f"formula_static_{context['topic_id']}",
            "base_type": self.base_type,
            "mode": intent["mode"],
            "base": base,
            "frames": [frame],
            "element_catalog": self._catalog(base),
        }

    # ---- dynamic --------------------------------------------------------

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
            frame: VisualFrame = {
                "index": index,
                "state": state,
                "highlights": {
                    "active_symbol": state.get("active_symbol"),
                    "active_expression": state.get("active_expression"),
                },
                "annotations": [
                    {
                        "id": f"formula_note_{index}",
                        "text": str(step.get("reason") or ""),
                        "attached_to_element_id": self._active_element_id(state),
                        "appears_in_frame": index,
                    }
                ],
                "selectable_elements": self.selectable_elements(state, base, intent["mode"]),
                "transitions": self.transitions(
                    prev_state,
                    state,
                    base,
                    intent["mode"],
                    step.get("transition_hints") or [],
                ),
            }
            frames.append(frame)
            prev_state = state
        return {
            "id": f"formula_{context['topic_id']}_{plan['id']}",
            "base_type": self.base_type,
            "mode": intent["mode"],
            "base": base,
            "frames": frames,
            "element_catalog": self._catalog(base),
        }

    # ---- state ----------------------------------------------------------

    def _normalize_state(self, raw: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
        substitution = raw.get("substitution") or {}
        if not isinstance(substitution, dict):
            substitution = {}
        chain = raw.get("equivalence_chain") or []
        if not isinstance(chain, list):
            chain = []
        return {
            "active_symbol": str(raw.get("active_symbol") or "").strip(),
            "active_expression": str(raw.get("active_expression") or "").strip(),
            "substitution": {str(k): str(v) for k, v in substitution.items()},
            "transformed_expression": str(
                raw.get("transformed_expression") or base.get("expression") or ""
            ).strip(),
            "equivalence_chain": [str(x) for x in chain],
        }

    # ---- selectable elements -------------------------------------------

    def selectable_elements(
        self,
        frame_state: dict[str, Any],
        base: dict[str, Any],
        mode: str,
    ) -> list[SelectableElement]:
        elements: list[SelectableElement] = []
        keyboard_index = 0
        expression = str(base.get("expression") or "")
        if expression:
            elements.append(
                {
                    "element_id": "expression_base",
                    "element_type": "subexpression",
                    "semantic_label": f"base expression: {expression}",
                    "bounds": {"x": 0.0, "y": 0.0, "width": 100.0, "height": 18.0},
                    "aria_label": localize_aria("subexpression", text=expression),
                    "keyboard_index": keyboard_index,
                    "payload": {"expression": expression, "role": "base"},
                }
            )
            keyboard_index += 1

        for index, symbol in enumerate(base.get("symbols") or []):
            element_id = str(symbol.get("element_id") or f"symbol_{index}")
            label = str(symbol.get("symbol") or "")
            meaning = str(symbol.get("meaning") or "")
            value = str(symbol.get("value") or "")
            elements.append(
                {
                    "element_id": element_id,
                    "element_type": "symbol_definition",
                    "semantic_label": f"{label}: {meaning or value or 'symbol'}",
                    "bounds": {
                        "x": float(index % 3) * 33.0,
                        "y": 24.0 + float(index // 3) * 14.0,
                        "width": 31.0,
                        "height": 12.0,
                    },
                    "aria_label": localize_aria(
                        "symbol",
                        symbol=label,
                        meaning=meaning or value,
                    ),
                    "keyboard_index": keyboard_index,
                    "payload": {"symbol": label, "meaning": meaning, "value": value},
                }
            )
            keyboard_index += 1

        for index, expression_value in enumerate(frame_state.get("equivalence_chain") or []):
            elements.append(
                {
                    "element_id": f"equation_{index}",
                    "element_type": "subexpression",
                    "semantic_label": f"equation step {index + 1}: {expression_value}",
                    "bounds": {
                        "x": 0.0,
                        "y": 58.0 + float(index) * 10.0,
                        "width": 100.0,
                        "height": 9.0,
                    },
                    "aria_label": f"Equation step {index + 1}: {expression_value}",
                    "keyboard_index": keyboard_index,
                    "payload": {"expression": expression_value, "step": index + 1},
                }
            )
            keyboard_index += 1
        return elements

    # ---- transitions ----------------------------------------------------

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
        prev_active = prev_frame_state.get("active_symbol") or prev_frame_state.get("active_expression")
        curr_active = curr_frame_state.get("active_symbol") or curr_frame_state.get("active_expression")
        if curr_active and curr_active != prev_active:
            # `move`: the active-symbol highlight slides from prev to curr
            # (gives the learner a visual handhold on which symbol just
            # changed focus). Falls back to `appear` when there was no
            # prior active symbol.
            target_id = self._active_element_id(curr_frame_state)
            if prev_active:
                prev_target = self._element_id_for(str(prev_active))
                transitions.append(
                    {
                        "kind": "move",
                        "target_element_id": target_id,
                        "duration_ms": 300,
                        "delay_ms": 0,
                        "easing": "ease_in_out",
                        "spec": {
                            "from": {"element_id": prev_target},
                            "to": {"element_id": target_id},
                        },
                    }
                )
            else:
                transitions.append(
                    {
                        "kind": "appear",
                        "target_element_id": target_id,
                        "duration_ms": 250,
                        "delay_ms": 0,
                        "easing": "ease_out",
                        "spec": {"target": curr_active},
                    }
                )
            transitions.append(
                {
                    "kind": "highlight_pulse",
                    "target_element_id": target_id,
                    "duration_ms": 450,
                    "delay_ms": 200,
                    "easing": "ease_out",
                    "spec": {"color": "#7C4EF0", "target": curr_active},
                }
            )

        # Substitution: when a symbol gains a value, emit a value_change so
        # the learner sees the symbol literally become its value.
        prev_subs = prev_frame_state.get("substitution") or {}
        curr_subs = curr_frame_state.get("substitution") or {}
        if isinstance(curr_subs, dict) and isinstance(prev_subs, dict):
            for symbol, value in curr_subs.items():
                prior = prev_subs.get(symbol)
                if str(prior) != str(value):
                    transitions.append(
                        {
                            "kind": "value_change",
                            "target_element_id": self._element_id_for(symbol),
                            "duration_ms": 350,
                            "delay_ms": 250,
                            "easing": "ease_in_out",
                            "spec": {
                                "from_value": str(prior or symbol),
                                "to_value": str(value),
                            },
                        }
                    )

        # Equivalence chain: cascade the new equations in as a stagger group
        # so the learner sees them appear sequentially, not all at once.
        prev_chain_len = len(prev_frame_state.get("equivalence_chain") or [])
        curr_chain_len = len(curr_frame_state.get("equivalence_chain") or [])
        new_indices = list(range(prev_chain_len, curr_chain_len))
        if len(new_indices) > 1:
            transitions.append(
                {
                    "kind": "stagger_group",
                    "target_element_id": f"equation_{new_indices[0]}",
                    "duration_ms": 250 * len(new_indices),
                    "delay_ms": 100,
                    "easing": "ease_out",
                    "spec": {
                        "group_element_ids": [f"equation_{i}" for i in new_indices],
                        "stagger_ms": 150,
                    },
                }
            )
        else:
            for index in new_indices:
                transitions.append(
                    {
                        "kind": "appear",
                        "target_element_id": f"equation_{index}",
                        "duration_ms": 250,
                        "delay_ms": 100,
                        "easing": "ease_out",
                        "spec": {"index": index},
                    }
                )
        return transitions

    def _element_id_for(self, symbol: str) -> str:
        return f"symbol_{symbol}" if symbol else "expression_base"

    def _active_element_id(self, state: dict[str, Any]) -> str:
        active_symbol = str(state.get("active_symbol") or "").strip()
        if active_symbol:
            return f"symbol_{active_symbol}"
        if state.get("active_expression"):
            return "expression_base"
        return "expression_base"

    def _catalog(self, base: dict[str, Any]) -> list:
        catalog = [
            {
                "element_id": "expression_base",
                "element_type": "subexpression",
                "first_frame": 0,
                "last_frame": -1,
                "initial_bounds": {"x": 0.0, "y": 0.0, "width": 100.0, "height": 18.0},
            }
        ]
        for index, symbol in enumerate(base.get("symbols") or []):
            element_id = str(symbol.get("element_id") or f"symbol_{index}")
            catalog.append(
                {
                    "element_id": element_id,
                    "element_type": "symbol_definition",
                    "first_frame": 0,
                    "last_frame": -1,
                    "initial_bounds": {
                        "x": float(index % 3) * 33.0,
                        "y": 24.0 + float(index // 3) * 14.0,
                        "width": 31.0,
                        "height": 12.0,
                    },
                }
            )
        return catalog


register(FormulaCompiler())
