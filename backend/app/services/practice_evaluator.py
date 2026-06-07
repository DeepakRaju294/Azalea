import json
from typing import Optional

from openai import OpenAI

from app.prompts.practice_prompts import (
    PRACTICE_HINT_SYSTEM_PROMPT,
    PRACTICE_SUBMIT_SYSTEM_PROMPT,
)

client = OpenAI()


def _safe_json_loads(raw_text: str) -> dict:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        start = raw_text.find("{")
        end = raw_text.rfind("}")

        if start != -1 and end != -1 and end > start:
            return json.loads(raw_text[start : end + 1])

        raise ValueError("LLM did not return valid JSON.")


def _normalize_quick_practice_question(
    data: dict,
    prompt: str,
    desired_type: str = "short_answer",
) -> dict:
    allowed_types = {
        "short_answer",
        "multiple_choice",
        "select_all",
        "math",
        "math_input",
        "coding",
        "coding_environment",
        "visual_labeling",
        "ordering",
        "debugging",
        "debugging_scenario",
        "decision_scenario",
    }
    allowed_difficulties = {"Easy", "Medium", "Hard"}
    question_type = data.get("question_type", desired_type)
    difficulty = data.get("difficulty", "Medium")

    if question_type not in allowed_types:
        question_type = desired_type

    if difficulty not in allowed_difficulties:
        difficulty = "Medium"

    return {
        "question_type": question_type,
        "topic": data.get("topic") or prompt[:120],
        "skill_target": data.get("skill_target") or "Focused practice",
        "difficulty": difficulty,
        "question_text": data.get("question_text") or data.get("question", ""),
        "choices": data.get("choices") if isinstance(data.get("choices"), list) else [],
        "given": data.get("given") if isinstance(data.get("given"), list) else [],
        "starter_code": data.get("starter_code"),
        "language": data.get("language"),
        "test_cases": (
            data.get("test_cases") if isinstance(data.get("test_cases"), list) else []
        ),
        "hidden_test_cases": (
            data.get("hidden_test_cases")
            if isinstance(data.get("hidden_test_cases"), list)
            else []
        ),
        "correct_answer": data.get("correct_answer"),
        "explanation": data.get("explanation"),
        "source_reference": data.get("source_reference"),
        "reason": data.get(
            "reason",
            "This question matches the requested quick practice focus.",
        ),
    }


def _detect_quick_practice_type(prompt: str) -> str:
    desired_type = "short_answer"
    lowered_prompt = prompt.lower()

    if any(word in lowered_prompt for word in ["multiple choice", "mcq", "quiz"]):
        desired_type = "multiple_choice"
    elif any(
        word in lowered_prompt
        for word in [
            "code",
            "coding",
            "program",
            "leetcode",
            "function",
            "algorithm",
            "debug",
        ]
    ):
        desired_type = "coding"
    elif any(
        word in lowered_prompt
        for word in [
            "math",
            "calculate",
            "equation",
            "solve",
            "probability",
            "expected value",
            "payoff",
            "cdf",
            "pdf",
            "integral",
            "derivative",
            "prove",
            "theorem",
        ]
    ):
        desired_type = "math"

    return desired_type


def generate_exact_problem_practice_question(prompt: str) -> dict:
    desired_type = _detect_quick_practice_type(prompt)

    user_prompt = f"""
The student pasted one specific problem and wants to solve it themselves.

Problem:
{prompt}

Classify the problem and prepare one practice environment for this exact problem.

Return JSON with this exact structure:
{{
  "question_type": "short_answer | multiple_choice | select_all | math | math_input | coding | coding_environment | visual_labeling | ordering | debugging | debugging_scenario | decision_scenario",
  "topic": "The topic being practiced.",
  "skill_target": "The precise skill this problem checks.",
  "difficulty": "Easy | Medium | Hard",
  "question_text": "The clean visible question statement shown to the student.",
  "given": ["Useful givens for math questions."],
  "starter_code": "Only for coding questions, otherwise null.",
  "language": "Only for coding questions, otherwise null.",
  "test_cases": [
    {{
      "input": "Visible test input for coding questions.",
      "expected": "Expected output."
    }}
  ],
  "hidden_test_cases": [
    {{
      "input": "Hidden stdin test input for coding questions.",
      "expected": "Expected hidden stdout."
    }}
  ],
  "correct_answer": "Private answer key for evaluation support.",
  "explanation": "Private concise solution explanation.",
  "reason": "Why this environment fits the pasted problem."
}}

Rules:
- Preserve the exact problem intent, but for coding questions turn it into a clean platform-style problem statement with task, input/output expectations, and examples.
- For non-coding questions, keep the pasted question visible unless a clearer question statement is needed.
- Preferred type from keyword detection: {desired_type}.
- Use math for probability, algebra, calculus, proofs, statistics, optimization, or game/payoff problems.
- Use coding/coding_environment only when the problem asks for code, an algorithm implementation, debugging, or test cases.
- For coding/coding_environment, include starter_code, language, exactly three visible test_cases when possible, and seven hidden_test_cases for backend grading.
- Coding starter_code should be LeetCode-style: expose the class/function the student implements, and omit main/stdin boilerplate unless the problem specifically requires it.
- Use these default signatures when possible: Python solve(data: str), JavaScript solve(input), TypeScript solve(input: string): string, Java class Solution with solve(String input), C++ class Solution with solve(const string& input), C solve(const char* input).
- Coding test_cases must provide stdin-style input and the exact stdout expected after stripping whitespace.
- For math, include the important givens but do not reveal the answer in the visible problem.
- The private correct_answer and explanation can contain the solution because they are used only for feedback.
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": PRACTICE_SUBMIT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.25,
    )

    content = response.choices[0].message.content
    data = _safe_json_loads(content)
    normalized = _normalize_quick_practice_question(data, prompt, desired_type)
    if normalized["question_type"] not in {"coding", "coding_environment"}:
        normalized["question_text"] = normalized["question_text"] or prompt.strip()
    else:
        visible_cases = normalized.get("test_cases", [])
        hidden_cases = normalized.get("hidden_test_cases", [])
        normalized["hidden_test_cases"] = [
            *visible_cases[3:],
            *hidden_cases,
        ][:7]
        normalized["test_cases"] = visible_cases[:3]
    if normalized["question_type"] not in {"multiple_choice", "select_all"}:
        normalized["choices"] = []
    return normalized


def generate_practice_hint(
    question: str,
    user_partial_answer: Optional[str] = None,
    lesson_context: Optional[str] = None,
) -> dict:
    user_prompt = f"""
Practice question:
{question}

Student's partial answer:
{user_partial_answer or "No partial answer provided."}

Lesson context:
{lesson_context or "No lesson context provided."}

Return JSON with this exact structure:
{{
  "hint": "A concise hint that does not give away the full answer.",
  "guiding_question": "A question that helps the student take the next step.",
  "concept_to_review": "The specific concept the student should review, or null."
}}
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": PRACTICE_HINT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.4,
    )

    content = response.choices[0].message.content
    data = _safe_json_loads(content)

    return {
        "hint": data.get("hint", ""),
        "guiding_question": data.get("guiding_question", ""),
        "concept_to_review": data.get("concept_to_review"),
    }


def evaluate_practice_answer(
    question: str,
    user_answer: str,
    lesson_context: Optional[str] = None,
    hint_used: bool = False,
) -> dict:
    user_prompt = f"""
Practice question:
{question}

Student answer:
{user_answer}

Did the student use a hint?
{hint_used}

Lesson context:
{lesson_context or "No lesson context provided."}

Return JSON with this exact structure:
{{
  "is_correct": true,
  "performance_level": "strong",
  "mistake_type": null,
  "feedback": "Specific feedback based on the student's answer.",
  "follow_up_question": "A targeted follow-up question, or null if the student should move on.",
  "next_action": "move_on | edge_case_check | targeted_follow_up | minimal_repair"
}}

Rules:
- performance_level must be one of: strong, fragile, minor_mistake, weak.
- next_action must be one of: move_on, edge_case_check, targeted_follow_up, minimal_repair.
- If performance_level is strong, next_action should usually be move_on.
- If performance_level is fragile, next_action should usually be edge_case_check.
- If performance_level is minor_mistake, next_action should usually be targeted_follow_up.
- If performance_level is weak, next_action should usually be minimal_repair.
- mistake_type should be specific when there is a mistake.
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": PRACTICE_SUBMIT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )

    content = response.choices[0].message.content
    data = _safe_json_loads(content)

    performance_level = data.get("performance_level", "weak")
    next_action = data.get("next_action", "minimal_repair")

    allowed_performance_levels = {
        "strong",
        "fragile",
        "minor_mistake",
        "weak",
    }

    allowed_next_actions = {
        "move_on",
        "edge_case_check",
        "targeted_follow_up",
        "minimal_repair",
    }

    if performance_level not in allowed_performance_levels:
        performance_level = "weak"

    if next_action not in allowed_next_actions:
        next_action = "minimal_repair"

    return {
        "is_correct": bool(data.get("is_correct", False)),
        "performance_level": performance_level,
        "mistake_type": data.get("mistake_type"),
        "feedback": data.get("feedback", ""),
        "follow_up_question": data.get("follow_up_question"),
        "next_action": next_action,
    }


def generate_weak_area_question(
    mistake_type: str,
    lesson_context: Optional[str] = None,
) -> dict:
    user_prompt = f"""
The student has repeatedly made this mistake type:
{mistake_type}

Lesson context:
{lesson_context or "No lesson context provided."}

Create one short-answer practice question that specifically tests whether the student has fixed this mistake.

Return JSON with this exact structure:
{{
  "question": "A targeted short-answer practice question focused on this mistake type.",
  "target_mistake_type": "{mistake_type}",
  "reason": "Why this question tests the repeated mistake."
}}

Rules:
- The question should be focused and answerable in a few sentences.
- Do not make the question too broad.
- Do not reveal the answer.
- If the mistake is about edge cases, make the question test an edge case.
- If the mistake is about setup, make the question require setting up the problem correctly.
- If the mistake is about assumptions, make the question test when that assumption does or does not apply.
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": PRACTICE_SUBMIT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.5,
    )

    content = response.choices[0].message.content
    data = _safe_json_loads(content)

    return {
        "question": data.get("question", ""),
        "target_mistake_type": data.get("target_mistake_type", mistake_type),
        "reason": data.get(
            "reason",
            "This question checks whether the repeated mistake has been fixed.",
        ),
    }


def generate_spaced_review_question(
    topic_title: str,
    topic_purpose: Optional[str] = None,
    review_reason: Optional[str] = None,
    lesson_context: Optional[str] = None,
) -> dict:
    user_prompt = f"""
The student is due for a spaced review check on this topic:
{topic_title}

Topic purpose:
{topic_purpose or "No topic purpose provided."}

Reason this review was scheduled:
{review_reason or "No review reason provided."}

Lesson context:
{lesson_context or "No lesson context provided."}

Create one short-answer spaced review question.

Return JSON with this exact structure:
{{
  "question": "A focused short-answer review question that checks durable understanding.",
  "reason": "Why this question is a good spaced review check."
}}

Rules:
- Do not reveal the answer.
- Do not ask for rote recall only.
- Prefer a question that requires applying the topic to a small case.
- Keep it answerable in 2-5 sentences.
- If the review reason says the student was fragile, include a small variation or edge case.
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": PRACTICE_SUBMIT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.5,
    )

    content = response.choices[0].message.content
    data = _safe_json_loads(content)

    return {
        "question": data.get("question", ""),
        "reason": data.get(
            "reason",
            "This question checks whether the topic is still understood after a delay.",
        ),
    }


def generate_quick_practice_question(
    prompt: str,
    source_text: Optional[str] = None,
    previous_attempts_context: Optional[str] = None,
) -> dict:
    desired_type = _detect_quick_practice_type(prompt)

    user_prompt = f"""
The student wants quick practice on:
{prompt}

Optional uploaded source material:
{source_text[:6000] if source_text else "No uploaded source material provided."}

Previous attempts or feedback:
{previous_attempts_context or "No previous attempts yet."}

Create one practice question focused only on what the student asked to practice.
Preferred question_type: {desired_type}

Return JSON with this exact structure:
{{
  "question_type": "short_answer | multiple_choice | select_all | math | math_input | coding | coding_environment | visual_labeling | ordering | debugging | debugging_scenario | decision_scenario",
  "topic": "The topic being practiced.",
  "skill_target": "The precise skill this question checks.",
  "difficulty": "Easy | Medium | Hard",
  "question_text": "The practice question shown to the student.",
  "choices": ["Only for multiple_choice. Four answer choices."],
  "given": ["Useful givens for math questions."],
  "starter_code": "Only for coding questions, otherwise null.",
  "language": "Only for coding questions, otherwise null.",
  "test_cases": [
    {{
      "input": "Visible test input for coding questions.",
      "expected": "Expected output."
    }}
  ],
  "correct_answer": "Brief private answer key for evaluation support.",
  "explanation": "Brief private explanation.",
  "source_reference": "Uploaded filename or source section if available, otherwise null.",
  "reason": "Why this question matches the requested practice."
}}

Rules:
- Do not create a study plan.
- Do not reveal the answer.
- Use question_type exactly one of: short_answer, multiple_choice, select_all, math, math_input, coding, coding_environment, visual_labeling, ordering, debugging, debugging_scenario, decision_scenario.
- Keep short_answer questions answerable in a few sentences.
- For multiple_choice or select_all, include plausible choices and do not mark which is correct in the question text.
- Use math or math_input for numeric/symbolic work; include givens when useful.
- Use visual_labeling when the user should identify a node, region, stage, component, or diagram label.
- Use ordering when the user should order stages, steps, operations, or algorithm states.
- Use debugging/debugging_scenario when the user should diagnose a bug, symptom, error, or flawed solution.
- Use decision_scenario when the user should choose between options under constraints.
- For coding/coding_environment, include starter_code, language, and at least two visible test cases.
- Coding starter_code should be LeetCode-style: expose the class/function the student implements, and omit main/stdin boilerplate unless the problem specifically requires it.
- Use these default signatures when possible: Python solve(data: str), JavaScript solve(input), TypeScript solve(input: string): string, Java class Solution with solve(String input), C++ class Solution with solve(const string& input), C solve(const char* input).
- Coding test_cases must provide stdin-style input and the exact stdout expected after stripping whitespace.
- If uploaded material exists, use it as the main source of context.
- If there are previous weak attempts, target the next question at the weakness.
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": PRACTICE_SUBMIT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.5,
    )

    content = response.choices[0].message.content
    data = _safe_json_loads(content)

    return _normalize_quick_practice_question(data, prompt, desired_type)


def generate_quick_practice_question_set(
    prompt: str,
    source_text: Optional[str],
    count: int = 8,
) -> list[dict]:
    desired_type = _detect_quick_practice_type(prompt)
    safe_count = max(1, min(count, 20))

    user_prompt = f"""
The student wants a focused quick-practice session on:
{prompt}

Uploaded practice/source material:
{source_text[:12000] if source_text else "No uploaded source material provided."}

Create {safe_count} practice questions for this session.

Return JSON with this exact structure:
{{
  "questions": [
    {{
      "question_type": "short_answer | multiple_choice | select_all | math | math_input | coding | coding_environment | visual_labeling | ordering | debugging | debugging_scenario | decision_scenario",
      "topic": "The topic being practiced.",
      "skill_target": "The precise skill this question checks.",
      "difficulty": "Easy | Medium | Hard",
      "question_text": "The practice question shown to the student.",
      "choices": ["Only for multiple_choice. Four answer choices."],
      "given": ["Useful givens for math questions."],
      "starter_code": "Only for coding questions, otherwise null.",
      "language": "Only for coding questions, otherwise null.",
      "test_cases": [
        {{
          "input": "Visible test input for coding questions.",
          "expected": "Expected output."
        }}
      ],
      "correct_answer": "Brief private answer key for evaluation support.",
      "explanation": "Brief private explanation.",
      "source_reference": "Where this came from in the uploaded material, otherwise null.",
      "reason": "Why this question belongs in the set."
    }}
  ]
}}

Rules:
- Do not create a study path or lesson plan.
- If the uploaded material contains existing practice questions, preserve their intent and convert them into the best supported question_type.
- If the uploaded material is notes rather than a practice exam, generate questions from the important concepts.
- Use question_type exactly one of: short_answer, multiple_choice, select_all, math, math_input, coding, coding_environment, visual_labeling, ordering, debugging, debugging_scenario, decision_scenario.
- Prefer the student's requested type when clear: {desired_type}.
- Do not reveal answers in question_text.
- For multiple_choice or select_all, include plausible choices and do not mark the correct one in the visible question text.
- Use visual_labeling for diagram/component labeling, ordering for step sequencing, debugging/debugging_scenario for diagnosis, and decision_scenario for tradeoff-based choices.
- For coding/coding_environment, include starter_code, language, and visible test cases.
- Coding starter_code should be LeetCode-style: expose the class/function the student implements, and omit main/stdin boilerplate unless the problem specifically requires it.
- Use these default signatures when possible: Python solve(data: str), JavaScript solve(input), TypeScript solve(input: string): string, Java class Solution with solve(String input), C++ class Solution with solve(const string& input), C solve(const char* input).
- Coding test_cases must provide stdin-style input and the exact stdout expected after stripping whitespace.
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": PRACTICE_SUBMIT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.45,
    )

    content = response.choices[0].message.content
    data = _safe_json_loads(content)
    raw_questions = data.get("questions", [])

    if not isinstance(raw_questions, list):
        raw_questions = []

    return [
        _normalize_quick_practice_question(question, prompt, desired_type)
        for question in raw_questions[:safe_count]
        if isinstance(question, dict)
    ]
