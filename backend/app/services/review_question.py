import json
from typing import Any

from app.services.llm_client import OPENAI_MODEL, client


REVIEW_QUESTION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "target_concept": {"type": "string"},
        "question": {"type": "string"},
        "reason": {"type": "string"},
        "expected_focus": {"type": "string"},
    },
    "required": [
        "target_concept",
        "question",
        "reason",
        "expected_focus",
    ],
    "additionalProperties": False,
}


REVIEW_ANSWER_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "correctness": {"type": "number"},
        "reasoning_quality": {"type": "number"},
        "feedback": {"type": "string"},
        "next_action": {
            "type": "string",
            "enum": [
                "mark_stable",
                "keep_in_review",
                "targeted_repair",
                "schedule_later",
            ],
        },
    },
    "required": [
        "correctness",
        "reasoning_quality",
        "feedback",
        "next_action",
    ],
    "additionalProperties": False,
}


REVIEW_QUESTION_SYSTEM_PROMPT = """
You are Azalea, an adaptive learning platform.

Your job is to generate one short spaced-review question for a concept that may be fragile.

Rules:
- Ask exactly one question.
- The question should test whether the learner still understands the target concept.
- Prefer application, edge-case, or explanation checks over pure definition recall.
- Keep it short and learner-facing.
- Do not make it feel like a formal exam.
- Stay grounded in the provided lesson context when available.
- Use supportive, non-judgmental wording.
"""


REVIEW_ANSWER_SYSTEM_PROMPT = """
You are Azalea, an adaptive learning platform.

Your job is to evaluate a learner's answer to a spaced-review question.

Rules:
- Return correctness from 0 to 1.
- Return reasoning_quality from 0 to 1.
- Give concise, supportive feedback.
- Choose next_action:
  - mark_stable: answer is correct and confident enough
  - schedule_later: answer is correct but confidence/reasoning is not fully stable
  - keep_in_review: answer shows partial understanding
  - targeted_repair: answer reveals a clear gap or misconception
- Use alignment language, not grading language.
"""


def generate_review_question(
    concept_name: str,
    lesson_context: str | None = None,
    review_reason: str | None = None,
) -> dict[str, Any]:
    user_prompt = f"""
Generate one spaced-review question.

Target concept:
{concept_name}

Review reason:
{review_reason or "not provided"}

Lesson context:
{lesson_context or "not provided"}

Return:
- target_concept
- question
- reason
- expected_focus
"""

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {"role": "system", "content": REVIEW_QUESTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "azalea_review_question",
                "schema": REVIEW_QUESTION_JSON_SCHEMA,
                "strict": True,
            }
        },
    )

    try:
        return json.loads(response.output_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("OpenAI returned invalid review question JSON") from exc


def evaluate_review_answer(
    concept_name: str,
    question: str,
    answer: str,
    confidence: int | None = None,
    review_reason: str | None = None,
) -> dict[str, Any]:
    confidence_text = (
        f"{confidence}/5"
        if confidence is not None
        else "not provided"
    )

    user_prompt = f"""
Evaluate this spaced-review answer.

Target concept:
{concept_name}

Review reason:
{review_reason or "not provided"}

Review question:
{question}

Learner answer:
{answer}

Learner confidence:
{confidence_text}

Return:
- correctness
- reasoning_quality
- feedback
- next_action
"""

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {"role": "system", "content": REVIEW_ANSWER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "azalea_review_answer",
                "schema": REVIEW_ANSWER_JSON_SCHEMA,
                "strict": True,
            }
        },
    )

    try:
        result = json.loads(response.output_text)
        result["correctness"] = max(0.0, min(1.0, float(result["correctness"])))
        result["reasoning_quality"] = max(
            0.0,
            min(1.0, float(result["reasoning_quality"])),
        )
        return result
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("OpenAI returned invalid review answer JSON") from exc