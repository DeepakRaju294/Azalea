"""V2 lesson generator — orchestrates the new pipeline.

Pipeline:
    1. LLM produces a lesson_v2 JSON (cards[] with intent only +
       worked_example_plans[] + practice_questions[]). Done elsewhere
       (api/routes/lessons_v2.py).
    2. For each card with a visual_intent, dispatch to the right compiler.
       Compilers produce VisualModels (with frames + selectable_elements +
       transitions).
    3. Build RenderSteps that point to (visual_model_id, frame_index).
    4. Assemble LessonV2.

This module coexists with `lean_lesson_generator.py`. It does NOT modify
the legacy pipeline.
"""

from __future__ import annotations

from typing import Any

from app.core.visual_ontology_v2 import (
    BASE_VISUAL_TYPES,
    SUPPORT_VISUALS,
    visual_behavior_for_role,
)
from app.schemas.visual_v2 import (
    CompileContext,
    LessonV2,
    RenderStep,
    SupportVisualPayload,
    VisualIntent,
    VisualModel,
    WorkedExamplePlan,
)
from app.services.visual_compilers import get_compiler, registered_base_types


def compile_lesson_v2(
    lesson_v2_raw: dict[str, Any],
    topic_id: str,
    topic_hint: str,
    topic_type: str,
    visual_domain: str,
    source_chunks_excerpt: str,
    source_chunk_ids: list[str],
    source_summary: str,
) -> LessonV2:
    """Convert LLM-emitted lesson_v2 JSON into a fully compiled LessonV2.

    Inputs:
      lesson_v2_raw: matches LESSON_V2_SCHEMA from llm_schemas_v2.py
      topic_*: topic metadata
      visual_domain: from the v2 topic classifier
      source_*: PDF/material grounding

    Output: LessonV2 with visual_models[] + render_steps[] ready for the
    frontend learn-v2 page.
    """
    cards = list(lesson_v2_raw.get("cards") or [])
    plans_by_id = {
        plan["id"]: plan
        for plan in (lesson_v2_raw.get("worked_example_plans") or [])
        if isinstance(plan, dict) and plan.get("id")
    }

    visual_models: list[VisualModel] = []
    render_steps: list[RenderStep] = []
    already_compiled: dict[str, VisualModel] = {}
    metadata = lesson_v2_raw.get("metadata") if isinstance(lesson_v2_raw.get("metadata"), dict) else {}
    locale = str(lesson_v2_raw.get("locale") or metadata.get("locale") or "en")

    # Compile background cards FIRST so worked-example compilers can reuse
    # their structures via CompileContext.already_compiled_models.
    background_cards = [c for c in cards if str(c.get("role") or "") == "background"]
    other_cards = [c for c in cards if str(c.get("role") or "") != "background"]
    ordered_cards = background_cards + other_cards

    for card in ordered_cards:
        intent = card.get("visual_intent")
        role = str(card.get("role") or "")
        card_id = str(card.get("id") or "")

        # Build the compile context
        context: CompileContext = {
            "topic_id": topic_id,
            "topic_hint": topic_hint,
            "topic_type": topic_type,
            "visual_domain": visual_domain,
            "locale": locale,
            "source_chunks_excerpt": source_chunks_excerpt,
            "already_compiled_models": already_compiled,
        }

        # Resolve the linked worked_example_plan (if any)
        plan = None
        plan_id = card.get("worked_example_plan_id")
        if plan_id and plan_id in plans_by_id:
            plan = plans_by_id[plan_id]

        # Build the render steps for this card
        if intent is None:
            # Text-only card
            render_steps.append(_text_only_render_step(card))
            continue

        base_type = str(intent.get("base_type") or "")

        # Support visuals bypass compilation
        if base_type in SUPPORT_VISUALS:
            render_steps.append(_support_render_step(card, intent))
            continue

        if base_type not in BASE_VISUAL_TYPES:
            # Unknown base_type — fall back to text-only
            render_steps.append(_text_only_render_step(card))
            continue

        # Dispatch to compiler
        compiler = get_compiler(base_type)
        if compiler is None:
            # No compiler registered (shouldn't happen — stubs cover all 12)
            render_steps.append(_text_only_render_step(card))
            continue

        visual_model = compiler.compile(intent, plan, context)

        # Empty / stub model — render text-only
        if not visual_model.get("frames"):
            render_steps.append(_text_only_render_step(card))
            continue

        # Register the model
        visual_models.append(visual_model)
        already_compiled[visual_model["id"]] = visual_model

        # Build render_steps — one per frame for dynamic plans, one frame
        # only for static visuals.
        is_dynamic = (
            plan is not None
            and intent.get("static_or_dynamic") == "dynamic"
        )
        if is_dynamic and len(visual_model["frames"]) > 1:
            # One render_step per step in the plan
            for index, plan_step in enumerate(plan["steps"]):
                step_id = f"{card_id}_step_{index + 1}"
                render_steps.append({
                    "id": step_id,
                    "card_id": card_id,
                    "title": str(plan_step.get("action") or card.get("title") or ""),
                    "points": list(plan_step.get("text_points") or []),
                    "role": role,
                    "visual_model_id": visual_model["id"],
                    "frame_index": index,
                    "code_model_id": None,
                    "code_frame_index": None,
                    "support_visual": None,
                    "animate_into": index > 0,
                    "notes": _attention_from_frame(visual_model, index),
                    "practice_question_id": _practice_question_id_for(card),
                })
        else:
            # Static visual — single render_step
            render_steps.append({
                "id": f"{card_id}_step",
                "card_id": card_id,
                "title": str(card.get("title") or ""),
                "points": list(card.get("points") or []),
                "role": role,
                "visual_model_id": visual_model["id"],
                "frame_index": 0,
                "code_model_id": None,
                "code_frame_index": None,
                "support_visual": None,
                "animate_into": False,
                "notes": _attention_from_frame(visual_model, 0),
                "practice_question_id": _practice_question_id_for(card),
            })

    # Resolve any `__index__:N` placeholders against the LLM-emitted
    # practice_questions array. Done before lesson assembly so the validator
    # sees fully-resolved render_steps.
    _resolve_practice_question_ids(
        render_steps,
        list(lesson_v2_raw.get("practice_questions") or []),
    )

    lesson: LessonV2 = {
        "lesson_version": 2,
        "title": str(lesson_v2_raw.get("title") or ""),
        "topic_summary": str(lesson_v2_raw.get("topic_summary") or ""),
        "estimated_minutes": int(lesson_v2_raw.get("estimated_minutes") or 8),
        "visual_models": visual_models,
        "render_steps": render_steps,
        "practice_questions": list(lesson_v2_raw.get("practice_questions") or []),
        "source_chunk_ids": list(source_chunk_ids),
        "source_summary": source_summary,
        "metadata": {
            "starting_mode": "default",
            "estimated_state": "not_provided",
            "adaptation_summary": "V2 lesson (intent + compiled visuals).",
            "teaching_strategy": "v2_default",
        },
    }

    # Validate + degrade gracefully on errors. Validation errors cause
    # the offending render_step to drop its visual_model_id reference
    # (rendered as text-only) rather than crashing the whole lesson.
    _validate_and_degrade(lesson)

    return lesson


def _validate_and_degrade(lesson: dict[str, Any]) -> None:
    """Run the v2 validators in-place against a compiled lesson.

    On error: drop the visual_model_id reference from offending
    render_steps (they become text-only).
    On warning/info: log via the lesson's metadata.adaptation_summary.
    """
    from app.services.visual_validators_v2 import validate_lesson_v2

    report = validate_lesson_v2(lesson)
    if not report.issues:
        return

    # Drop unresolved-model render steps
    invalid_step_ids: set[str] = set()
    for issue in report.errors():
        if issue.code in {
            "render_step_unresolved_model",
            "render_step_frame_out_of_range",
            "render_step_missing_frame_index",
        }:
            # location is "render_steps[N]" — extract N
            try:
                idx_str = issue.location.split("render_steps[", 1)[1].split("]", 1)[0]
                idx = int(idx_str)
                step = lesson["render_steps"][idx]
                step["visual_model_id"] = None
                step["frame_index"] = None
                invalid_step_ids.add(step["id"])
            except (IndexError, ValueError, KeyError):
                pass

    # Annotate metadata with a one-line summary so the frontend can show it
    if report.errors() or report.warnings():
        summary_bits = []
        if report.errors():
            summary_bits.append(f"{len(report.errors())} validator errors (degraded)")
        if report.warnings():
            summary_bits.append(f"{len(report.warnings())} warnings")
        lesson["metadata"]["adaptation_summary"] = (
            "V2 lesson (intent + compiled visuals). "
            + "; ".join(summary_bits)
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _text_only_render_step(card: dict[str, Any]) -> RenderStep:
    return {
        "id": f"{card.get('id') or 'card'}_step",
        "card_id": str(card.get("id") or ""),
        "title": str(card.get("title") or ""),
        "points": list(card.get("points") or []),
        "role": str(card.get("role") or ""),
        "visual_model_id": None,
        "frame_index": None,
        "code_model_id": None,
        "code_frame_index": None,
        "support_visual": None,
        "animate_into": False,
        "notes": "",
        "practice_question_id": _practice_question_id_for(card),
    }


def _practice_question_id_for(card: dict[str, Any]) -> str | None:
    """Resolve which practice_question this card references.

    Accepts either an explicit `practice_question_id` (string) or the
    legacy `practice_question_index` (int). When index-based, the
    orchestrator resolves it against the lesson's practice_questions in
    a second pass (see _resolve_practice_question_ids below).
    """
    if str(card.get("role") or "") != "practice":
        return None
    explicit_id = card.get("practice_question_id")
    if isinstance(explicit_id, str) and explicit_id:
        return explicit_id
    # Mark as index-encoded so the post-pass can resolve it
    index = card.get("practice_question_index")
    if isinstance(index, int):
        return f"__index__:{index}"
    return None


def _resolve_practice_question_ids(
    render_steps: list[RenderStep],
    practice_questions: list[dict[str, Any]],
) -> None:
    """Second pass: turn `__index__:N` placeholders into the real id of
    practice_questions[N], or null when N is out of range. Mutates in place.
    """
    for step in render_steps:
        pqid = step.get("practice_question_id")
        if not isinstance(pqid, str) or not pqid.startswith("__index__:"):
            continue
        try:
            n = int(pqid.split(":", 1)[1])
        except (IndexError, ValueError):
            step["practice_question_id"] = None
            continue
        if 0 <= n < len(practice_questions):
            question = practice_questions[n]
            if isinstance(question, dict) and question.get("id"):
                step["practice_question_id"] = str(question["id"])
                continue
        step["practice_question_id"] = None


def _support_render_step(card: dict[str, Any], intent: VisualIntent) -> RenderStep:
    payload: SupportVisualPayload = {
        "support_type": intent["base_type"],
        "mode": intent["mode"],
        "data": {
            "description": intent["description"],
            "purpose": intent["purpose"],
        },
        "selectable_elements": [],
    }
    return {
        "id": f"{card.get('id') or 'card'}_step",
        "card_id": str(card.get("id") or ""),
        "title": str(card.get("title") or ""),
        "points": list(card.get("points") or []),
        "role": str(card.get("role") or ""),
        "visual_model_id": None,
        "frame_index": None,
        "code_model_id": None,
        "code_frame_index": None,
        "support_visual": payload,
        "animate_into": False,
        "notes": "",
        "practice_question_id": _practice_question_id_for(card),
    }


def _attention_from_frame(model: VisualModel, frame_index: int) -> str:
    if frame_index < 0 or frame_index >= len(model["frames"]):
        return ""
    frame = model["frames"][frame_index]
    for ann in frame.get("annotations") or []:
        if ann.get("text"):
            return str(ann["text"])
    return ""


def list_supported_base_types() -> tuple[str, ...]:
    """Diagnostic helper: which base_types have registered compilers."""
    return registered_base_types()
