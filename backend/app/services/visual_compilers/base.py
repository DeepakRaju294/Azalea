"""Abstract VisualCompiler interface.

Every concrete compiler in this package subclasses VisualCompiler and
overrides four methods:
    - compile(): produce a VisualModel from intent + plan + context
    - selectable_elements(): per-frame clickable element list
    - transitions(): per-frame transition list (animation specs)
    - synthesize_plan_from_legacy_cards(): fallback when LLM nulled the plan

The base class provides default implementations for selectable_elements +
transitions that return empty lists. Compilers that don't override these
will produce static, non-interactive visuals — fine for stub compilers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.schemas.visual_v2 import (
    CompileContext,
    SelectableElement,
    Transition,
    TransitionHint,
    VisualIntent,
    VisualModel,
    WorkedExamplePlan,
)


class VisualCompiler(ABC):
    """Abstract base for all visual compilers.

    Subclass and set `base_type` at the class level. Implement compile()
    at minimum; override selectable_elements() and transitions() for
    interactivity and animation support.
    """

    base_type: str = ""  # subclass MUST override

    def __init__(self) -> None:
        if not self.base_type:
            raise ValueError(
                f"{type(self).__name__} must set base_type at class level"
            )

    # ---- main entrypoint ---------------------------------------------------

    @abstractmethod
    def compile(
        self,
        intent: VisualIntent,
        plan: WorkedExamplePlan | None,
        context: CompileContext,
    ) -> VisualModel:
        """Produce a VisualModel.

        For static visuals (background, components_terms, etc.): emit one
        frame with the base structure and no transitions.

        For worked examples (plan is not None): emit one frame per
        plan.steps[i], with state, selectable_elements, and transitions
        keyed to that step.
        """
        ...

    # ---- interactivity -----------------------------------------------------

    def selectable_elements(
        self,
        frame_state: dict[str, Any],
        base: dict[str, Any],
        mode: str,
    ) -> list[SelectableElement]:
        """Return the clickable elements for a given frame state.

        Default: no clickable elements (fully passive visual). Override
        for compilers that support click-to-ask.
        """
        return []

    # ---- animation ---------------------------------------------------------

    def transitions(
        self,
        prev_frame_state: dict[str, Any] | None,
        curr_frame_state: dict[str, Any],
        base: dict[str, Any],
        mode: str,
        hints: list[TransitionHint],
    ) -> list[Transition]:
        """Compute the transitions that animate the previous frame's state
        into the current frame's state.

        Default: no transitions (snap-change). Override to emit `move`,
        `style_change`, `appear`, `fade_in`, etc.

        Called with prev_frame_state=None for the first frame (no animation
        on entry).
        """
        return []

    # ---- LLM-compliance fallback ------------------------------------------

    def synthesize_plan_from_legacy_cards(
        self,
        legacy_cards: list[dict[str, Any]],
        context: CompileContext,
    ) -> WorkedExamplePlan | None:
        """When the LLM emits per-step worked_example cards instead of a
        plan, reconstruct an equivalent plan from those cards.

        Default: no synthesis (returns None). Override for compilers that
        can reconstruct a plan from cards (e.g. node_link can use the
        background card's tree as base_state).

        This is the v2 home for the synthesizer pattern currently in
        lean_lesson_generator._synthesize_node_link_plan_from_lean_cards.
        """
        return None


# ---------------------------------------------------------------------------
# UTILITY: a stub compiler that emits a 1-frame placeholder.
# Used by Phase 2 to register placeholders for the 9 not-yet-implemented
# base types so the orchestrator doesn't crash on them.
# ---------------------------------------------------------------------------


class StubCompiler(VisualCompiler):
    """Placeholder compiler for base_types whose real compiler hasn't been
    built yet. Emits a single frame with a `placeholder=True` flag the
    frontend renderer can use to show 'compiler not yet implemented'."""

    def __init__(self, base_type: str) -> None:
        # bypass abstract enforcement by setting base_type before super
        self.base_type = base_type
        super().__init__()

    def compile(
        self,
        intent: VisualIntent,
        plan: WorkedExamplePlan | None,
        context: CompileContext,
    ) -> VisualModel:
        return {
            "id": f"{self.base_type}_stub",
            "base_type": self.base_type,
            "mode": intent["mode"],
            "base": {
                "placeholder": True,
                "intended_description": intent["description"],
                "intended_purpose": intent["purpose"],
            },
            "frames": [
                {
                    "index": 0,
                    "state": {"placeholder": True},
                    "highlights": {},
                    "annotations": [
                        {
                            "id": "stub-note",
                            "text": (
                                f"Compiler for '{self.base_type}' is not "
                                "yet implemented. Falling back to text."
                            ),
                            "attached_to_element_id": None,
                            "appears_in_frame": 0,
                        }
                    ],
                    "selectable_elements": [],
                    "transitions": [],
                }
            ],
            "element_catalog": [],
        }
