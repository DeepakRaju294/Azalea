import json
from typing import Any

from app.services.llm_client import OPENAI_MODEL, client


TRANSFER_CHALLENGE_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "target_concept": {"type": "string"},
        "challenge": {"type": "string"},
        "reason": {"type": "string"},
        "expected_focus": {"type": "string"},
    },
    "required": ["target_concept", "challenge", "reason", "expected_focus"],
    "additionalProperties": False,
}


TRANSFER_CHALLENGE_EVAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "correctness": {"type": "number"},
        "reasoning_quality": {"type": "number"},
        "feedback": {"type": "string"},
        "next_action": {
            "type": "string",
            "enum": ["mark_transferable", "keep_stable", "targeted_repair"],
        },
    },
    "required": ["correctness", "reasoning_quality", "feedback", "next_action"],
    "additionalProperties": False,
}


TRANSFER_CHALLENGE_SYSTEM_PROMPT = """
You are Azalea, an adaptive learning platform.

Your job is to generate one transfer challenge that checks whether the learner can apply a concept flexibly.

Rules:
- Ask exactly one challenge.
- The challenge should not be a direct repeat of the lesson example.
- Prefer a new context, edge case, or applied scenario.
- Keep it short enough to answer in a few minutes.
- Use supportive language.
- Do not include the answer.
"""


TRANSFER_CHALLENGE_EVAL_SYSTEM_PROMPT = """
You are Azalea, an adaptive learning platform.

Your job is to evaluate whether the learner can transfer a concept to a new situation.

Rules:
- correctness is 0 to 1.
- reasoning_quality is 0 to 1.
- next_action must be:
  - mark_transferable
  - keep_stable
  - targeted_repair
- Mark transferable only when the learner applies the concept correctly in the new context.
- Use alignment language, not grading language.
"""


def generate_transfer_challenge(
    concept_name: str,
    lesson_context: str | None = None,
    prior_context: str | None = None,
) -> dict[str, Any]:
    user_prompt = f"""
Generate one transfer challenge.

Target concept:
{concept_name}

Lesson context:
{lesson_context or "not provided"}

Prior learner context:
{prior_context or "not provided"}

Return:
- target_concept
- challenge
- reason
- expected_focus
"""

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {"role": "system", "content": TRANSFER_CHALLENGE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "azalea_transfer_challenge",
                "schema": TRANSFER_CHALLENGE_JSON_SCHEMA,
                "strict": True,
            }
        },
    )

    try:
        return json.loads(response.output_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("OpenAI returned invalid transfer challenge JSON") from exc


def evaluate_transfer_challenge(
    concept_name: str,
    challenge: str,
    answer: str,
    confidence: int | None = None,
) -> dict[str, Any]:
    user_prompt = f"""
Evaluate this transfer challenge answer.

Target concept:
{concept_name}

Transfer challenge:
{challenge}

Learner answer:
{answer}

Learner confidence:
{confidence or "not provided"}/5

Return:
- correctness
- reasoning_quality
- feedback
- next_action
"""

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {"role": "system", "content": TRANSFER_CHALLENGE_EVAL_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "azalea_transfer_challenge_eval",
                "schema": TRANSFER_CHALLENGE_EVAL_SCHEMA,
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
        raise RuntimeError("OpenAI returned invalid transfer challenge evaluation JSON") from exc