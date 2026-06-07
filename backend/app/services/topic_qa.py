from typing import Any

from app.models.content_chunk import ContentChunk
from app.models.topic import Topic
from app.services.llm_client import generate_class_qa_response


SYSTEM_PROMPT = """
You are Azalea, an AI study assistant.

Answer student questions about the current study path topic.

Use:
- the current topic
- the current lesson context, if provided
- the uploaded class source chunks

Rules:
- Stay grounded in the provided lesson/source material.
- If highlighted/selected text is provided, focus the answer on that passage first.
- Answer in the context of the current topic and current section.
- Before giving the explanation, briefly anchor the answer to what the learner is currently learning.
- Help the learner return to the lesson with more clarity. Avoid disconnected generic explanations.
- If the provided material does not contain enough information, say what is missing.
- Explain clearly and simply.
- Do not invent unsupported details.
- If useful, cite source numbers naturally in the answer.
- Classify the confusion so Azalea can adapt future cards.
- If the learner says they are still confused, change explanation mode instead of repeating the prior answer.
- Return only valid JSON.
"""

CONFUSION_TYPES = {
    "undefined_term",
    "skipped_step",
    "formula_confusion",
    "notation_confusion",
    "example_confusion",
    "prerequisite_gap",
    "misconception",
    "application_confusion",
    "why_it_matters",
    "general_question",
}

CLARIFICATION_MODES = {
    "direct_answer",
    "simpler_explanation",
    "worked_example",
    "step_by_step",
    "prerequisite_review",
    "misconception_correction",
    "formula_symbol_explanation",
    "edge_case_explanation",
    "mini_practice_check",
}


def answer_topic_question(
    question: str,
    topic: Topic,
    chunks: list[ContentChunk],
    lesson_context: str | None = None,
    selected_text: str | None = None,
    current_section: str | None = None,
    clarification_mode: str | None = None,
    prior_confusion_context: str | None = None,
) -> dict[str, Any]:
    source_text = ""

    for source_number, chunk in enumerate(chunks, start=1):
        material_title = chunk.material.title if chunk.material else "Unknown material"
        material_filename = chunk.material.filename if chunk.material else None

        source_text += f"""
--- SOURCE {source_number} ---
Material: {material_title}
Filename: {material_filename or "No filename"}
Material id: {chunk.material_id}
Chunk id: {chunk.id}
Chunk index: {chunk.chunk_index}

{chunk.text}
"""

    user_prompt = f"""
Student question:
{question}

Current topic:
Title: {topic.title}
Purpose: {topic.purpose or "No purpose provided."}

Current lesson context:
{lesson_context or "No lesson context provided."}

Current section:
{current_section or "No current section provided."}

Highlighted / selected lesson text:
{selected_text or "No highlighted text provided."}

Requested clarification mode:
{clarification_mode or "Choose the best mode from the question."}

Prior confusion context:
{prior_confusion_context or "No prior confusion context provided."}

Uploaded class source material:
{source_text}

Return JSON with this exact structure:
{{
  "answer": "A clear answer grounded in the topic, lesson context, and source material.",
  "used_chunk_indexes": [1, 2],
  "confusion_type": "one of: undefined_term, skipped_step, formula_confusion, notation_confusion, example_confusion, prerequisite_gap, misconception, application_confusion, why_it_matters, general_question",
  "concept_name": "the specific concept being clarified, not a whole sentence",
  "clarification_mode": "one of: direct_answer, simpler_explanation, worked_example, step_by_step, prerequisite_review, misconception_correction, formula_symbol_explanation, edge_case_explanation, mini_practice_check",
  "concepts_involved": ["specific concept names"],
  "suggested_actions": ["Got it", "Still confused", "Show example", "Test me"],
  "follow_up_prompts": ["one short follow-up button", "another short follow-up button"]
}}

Rules:
- used_chunk_indexes should contain the SOURCE numbers that were most relevant, not the Chunk index values.
- Start by briefly anchoring the answer to the current topic and current section when possible.
- If highlighted text is provided, answer the student's question about that exact passage before broadening to the rest of the lesson or sources.
- The answer should help the learner return to the lesson flow, not feel like a separate generic chat.
- If the confusion_type is misconception, include what the learner may be assuming, why it fails, the correct mental model, and a tiny check.
- If the question asks "how did we get this?", use step_by_step.
- If the question asks "what does this mean?", use simpler_explanation or prerequisite_review.
- If the question asks "why?", use direct reasoning and connect it to the current card.
- If the learner is still confused, switch modes and use a concrete example.
- If the lesson context alone answers the question, used_chunk_indexes can be an empty list.
- If no source or lesson context answers the question, use an empty list and explain what is missing.
"""

    data = generate_class_qa_response(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    confusion_type = clean_choice(
        data.get("confusion_type"),
        CONFUSION_TYPES,
        "general_question",
    )
    resolved_mode = clean_choice(
        data.get("clarification_mode"),
        CLARIFICATION_MODES,
        clarification_mode or "direct_answer",
    )

    return {
        "answer": data.get("answer", ""),
        "used_chunk_indexes": data.get("used_chunk_indexes", []),
        "confusion_type": confusion_type,
        "concept_name": clean_text(data.get("concept_name"), topic.title or "overall_topic"),
        "clarification_mode": resolved_mode,
        "concepts_involved": clean_list(data.get("concepts_involved")),
        "suggested_actions": clean_list(
            data.get("suggested_actions"),
            fallback=["Got it", "Still confused", "Show example", "Test me"],
        )[:5],
        "follow_up_prompts": clean_list(
            data.get("follow_up_prompts"),
            fallback=["Explain simpler", "Show example"],
        )[:4],
    }


def clean_choice(value: Any, allowed: set[str], fallback: str) -> str:
    if isinstance(value, str):
        normalized = value.strip().lower().replace(" ", "_")
        if normalized in allowed:
            return normalized
    return fallback if fallback in allowed else next(iter(allowed))


def clean_text(value: Any, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()[:255]
    return fallback


def clean_list(value: Any, fallback: list[str] | None = None) -> list[str]:
    if not isinstance(value, list):
        return list(fallback or [])

    cleaned: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            cleaned.append(item.strip()[:180])

    return cleaned or list(fallback or [])
