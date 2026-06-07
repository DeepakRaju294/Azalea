import json
from typing import Any

from app.services.llm_client import client, OPENAI_MODEL


TARGETED_REPAIR_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "target_concept": {"type": "string"},
        "repair_explanation": {"type": "string"},
        "why_this_matters": {"type": "string"},
        "follow_up_question": {"type": "string"},
        "next_action": {"type": "string"},
    },
    "required": [
        "target_concept",
        "repair_explanation",
        "why_this_matters",
        "follow_up_question",
        "next_action",
    ],
    "additionalProperties": False,
}


TARGETED_REPAIR_FOLLOW_UP_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "correctness": {"type": "number"},
        "reasoning_quality": {"type": "number"},
        "feedback": {"type": "string"},
        "next_action": {"type": "string"},
    },
    "required": [
        "correctness",
        "reasoning_quality",
        "feedback",
        "next_action",
    ],
    "additionalProperties": False,
}


SYSTEM_PROMPT = """
You are Azalea, an adaptive learning platform.

Your job is to generate the smallest useful repair after a learner makes a mistake.

Rules:
- Do not reteach the whole topic unless repeated failure requires it.
- Repair only the missing concept.
- Be direct, supportive, and concise.
- Use alignment language, not grading language.
- Give exactly one follow-up question.
- The follow-up question should test the repaired concept.
- If the learner's mistake is unclear, repair the most likely missing piece.
- Stay grounded in the provided lesson context when available.
"""


FOLLOW_UP_SYSTEM_PROMPT = """
You are Azalea, an adaptive learning platform.

Your job is to evaluate a learner's answer to a targeted repair follow-up question.

Rules:
- Judge whether the learner understood the repaired concept.
- Return correctness between 0 and 1.
- Return reasoning_quality between 0 and 1.
- Give concise feedback.
- Choose next_action from:
  - repair_complete
  - give_simpler_example
  - mini_reteach
- Use supportive alignment language, not grading language.
"""


def choose_repair_level(prior_repair_count: int) -> str:
    if prior_repair_count <= 0:
        return "targeted_repair"

    if prior_repair_count == 1:
        return "simpler_example"

    return "mini_reteach"


def generate_targeted_repair(
    concept_name: str,
    mistake_type: str | None = None,
    question: str | None = None,
    user_answer: str | None = None,
    lesson_context: str | None = None,
    feedback: str | None = None,
    prior_repair_count: int = 0,
) -> dict[str, Any]:
    repair_level = choose_repair_level(prior_repair_count)

    user_prompt = f"""
Generate a targeted repair.

Target concept:
{concept_name}

Mistake type:
{mistake_type or "not provided"}

Original question:
{question or "not provided"}

Learner answer:
{user_answer or "not provided"}

Practice feedback:
{feedback or "not provided"}

Prior repair count for this concept:
{prior_repair_count}

Repair level:
{repair_level}

Lesson context:
{lesson_context or "not provided"}

Repair level behavior:
- targeted_repair: repair only the exact missing piece.
- simpler_example: use a smaller concrete example before the follow-up question.
- mini_reteach: give a brief mini-reteach of the concept, but still avoid reteaching the whole topic.

Return:
- target_concept
- repair_explanation
- why_this_matters
- follow_up_question
- next_action

The repair_explanation should be short and focused.
The follow_up_question should be one question only.
"""

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "azalea_targeted_repair",
                "schema": TARGETED_REPAIR_JSON_SCHEMA,
                "strict": True,
            }
        },
    )

    try:
        repair = json.loads(response.output_text)
        repair["repair_level"] = repair_level
        repair["prior_repair_count"] = prior_repair_count
        return repair
    except json.JSONDecodeError as exc:
        raise RuntimeError("OpenAI returned invalid targeted repair JSON") from exc


def evaluate_targeted_repair_follow_up(
    target_concept: str,
    repair_explanation: str,
    follow_up_question: str,
    learner_answer: str,
) -> dict[str, Any]:
    user_prompt = f"""
Evaluate this targeted repair follow-up answer.

Target concept:
{target_concept}

Repair explanation shown to learner:
{repair_explanation}

Follow-up question:
{follow_up_question}

Learner answer:
{learner_answer}

Return:
- correctness
- reasoning_quality
- feedback
- next_action
"""

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {"role": "system", "content": FOLLOW_UP_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "azalea_targeted_repair_follow_up",
                "schema": TARGETED_REPAIR_FOLLOW_UP_SCHEMA,
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
        raise RuntimeError("OpenAI returned invalid targeted repair follow-up JSON") from exc