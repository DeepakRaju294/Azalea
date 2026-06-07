from __future__ import annotations

from typing import Any


ALLOWED_QUESTION_TYPES = {
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

COURSE_TYPE_PRACTICE_REQUIREMENTS = {
    "concept_intuition": {
        "allowed": {"short_answer", "multiple_choice", "visual_labeling"},
        "skills": ("apply concept", "predict behavior", "diagnose misconception"),
    },
    "terminology_components": {
        "allowed": {"multiple_choice", "short_answer", "visual_labeling"},
        "skills": ("match term", "label example", "detect misuse"),
    },
    "process_walkthrough": {
        "allowed": {"multiple_choice", "short_answer", "ordering", "math", "math_input"},
        "skills": ("choose next step", "apply process", "identify invalid step"),
    },
    "algorithm_walkthrough": {
        "allowed": {"short_answer", "multiple_choice", "ordering", "visual_labeling"},
        "skills": ("trace algorithm", "predict next state", "produce final output"),
    },
    "coding_implementation": {
        "allowed": {"coding", "coding_environment", "debugging"},
        "skills": ("write code", "fix bug", "dry run code", "handle edge case"),
    },
    "data_structure_operation": {
        "allowed": {"short_answer", "multiple_choice", "visual_labeling", "coding", "coding_environment"},
        "skills": ("perform operation", "choose final structure", "check invariant"),
    },
    "math_formula_method": {
        "allowed": {"math", "math_input", "multiple_choice"},
        "skills": ("set up formula", "solve step", "check condition", "interpret result"),
    },
    "proof_reasoning": {
        "allowed": {"short_answer", "multiple_choice", "math", "math_input", "ordering"},
        "skills": ("choose strategy", "fill proof step", "identify invalid reasoning"),
    },
    "compare_distinguish": {
        "allowed": {"multiple_choice", "short_answer", "decision_scenario"},
        "skills": ("classify scenario", "identify key difference", "detect mix-up"),
    },
    "problem_solving_application": {
        "allowed": {"multiple_choice", "short_answer", "coding", "coding_environment", "debugging", "math", "math_input"},
        "skills": ("recognize pattern", "choose strategy", "solve variation"),
    },
    "problem_solving_pattern": {
        "allowed": {"multiple_choice", "short_answer", "coding", "coding_environment", "debugging"},
        "skills": ("recognize pattern", "choose strategy", "trace state"),
    },
    "review_refresh": {
        "allowed": {
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
        },
        "skills": ("quick recall", "edge-case check", "identify forgotten rule"),
    },
    "science_mechanism": {
        "allowed": {"short_answer", "multiple_choice", "visual_labeling", "math", "math_input"},
        "skills": ("predict effect", "trace cause-effect", "interpret graph"),
    },
    "system_architecture": {
        "allowed": {"short_answer", "multiple_choice", "visual_labeling", "decision_scenario"},
        "skills": ("trace flow", "identify responsibility", "diagnose failure"),
    },
    "debugging_diagnosis": {
        "allowed": {"multiple_choice", "short_answer", "coding", "coding_environment", "debugging", "debugging_scenario"},
        "skills": ("map symptom to cause", "choose diagnostic check", "choose fix"),
    },
    "tool_workflow": {
        "allowed": {"multiple_choice", "short_answer", "ordering", "debugging"},
        "skills": ("choose next action", "order steps", "interpret output"),
    },
    "design_decision": {
        "allowed": {"multiple_choice", "short_answer", "decision_scenario"},
        "skills": ("choose option", "identify criterion", "detect flawed reasoning"),
    },
    "case_study_application": {
        "allowed": {"short_answer", "multiple_choice", "visual_labeling", "decision_scenario"},
        "skills": ("map abstract to real", "trace application", "predict outcome"),
    },
    "historical_development": {
        "allowed": {"multiple_choice", "short_answer", "ordering"},
        "skills": ("order developments", "identify limitation", "compare old and new"),
    },
    "process_lifecycle": {
        "allowed": {"multiple_choice", "short_answer", "ordering", "visual_labeling"},
        "skills": ("identify stage", "predict next stage", "diagnose broken process"),
    },
    "terminology_vocabulary": {
        "allowed": {"multiple_choice", "short_answer", "visual_labeling"},
        "skills": ("match term", "label example", "detect misuse"),
    },
    "exam_interview_prep": {
        "allowed": {
            "multiple_choice",
            "short_answer",
            "math",
            "math_input",
            "coding",
            "coding_environment",
            "debugging",
            "decision_scenario",
        },
        "skills": ("identify question type", "choose approach", "detect trap"),
    },
}


def validate_and_repair_practice(
    lesson_json: dict[str, Any],
    course_type: str | None = None,
) -> dict[str, Any]:
    resolved_course_type = course_type or str(lesson_json.get("course_type") or "concept_intuition")
    requirements = COURSE_TYPE_PRACTICE_REQUIREMENTS.get(
        resolved_course_type,
        COURSE_TYPE_PRACTICE_REQUIREMENTS["concept_intuition"],
    )
    questions = lesson_json.get("practice_questions")
    issues: list[str] = []
    repaired_count = 0

    if not isinstance(questions, list):
        lesson_json["practice_questions"] = []
        lesson_json["practice"] = []
        report = build_report(
            passed=False,
            requires_regeneration=True,
            repaired_count=1,
            issues=["practice_questions was not a list."],
            actual_question_types=[],
            expected_question_types=sorted(requirements["allowed"]),
        )
        lesson_json["practice_quality_report"] = report
        return report

    normalized_questions: list[dict[str, Any]] = []
    for index, question in enumerate(questions):
        if not isinstance(question, dict):
            issues.append(f"Removed invalid practice question {index}.")
            repaired_count += 1
            continue

        normalized, changed = normalize_practice_question(
            question=question,
            index=index,
            course_type=resolved_course_type,
        )
        if changed:
            repaired_count += 1
        normalized_questions.append(normalized)

    lesson_json["practice_questions"] = normalized_questions
    lesson_json["practice"] = [
        question.get("question_text", "")
        for question in normalized_questions
        if question.get("question_text")
    ]

    actual_question_types = {
        str(question.get("question_type") or "").strip()
        for question in normalized_questions
    }
    expected_question_types = set(requirements["allowed"])

    if not normalized_questions:
        issues.append("Lesson has no usable practice questions.")

    if not actual_question_types.intersection(expected_question_types):
        issues.append(
            f"{resolved_course_type} needs practice type from {sorted(expected_question_types)}, got {sorted(actual_question_types)}."
        )

    for index, question in enumerate(normalized_questions):
        question_type = question.get("question_type")
        if question_type not in ALLOWED_QUESTION_TYPES:
            issues.append(f"Practice question {index} has unsupported type {question_type}.")

        if question_type in {"multiple_choice", "select_all"} and len(question.get("choices") or []) < 2:
            issues.append(f"Choice question {index} does not have at least two choices.")

        if question_type in {"coding", "coding_environment"}:
            if not str(question.get("starter_code") or "").strip():
                issues.append(f"Coding question {index} is missing starter_code.")
            if not question.get("test_cases"):
                issues.append(f"Coding question {index} is missing test_cases.")

        if question_type in {"math", "math_input"} and not question.get("given"):
            issues.append(f"Math question {index} is missing given values or assumptions.")

    report = build_report(
        passed=not issues,
        requires_regeneration=should_regenerate_practice(issues),
        repaired_count=repaired_count,
        issues=issues,
        actual_question_types=sorted(actual_question_types),
        expected_question_types=sorted(expected_question_types),
    )
    lesson_json["practice_quality_report"] = report
    return report


def normalize_practice_question(
    question: dict[str, Any],
    index: int,
    course_type: str,
) -> tuple[dict[str, Any], bool]:
    original = dict(question)
    normalized = dict(question)

    question_type = str(normalized.get("question_type") or "short_answer").strip()
    if question_type not in ALLOWED_QUESTION_TYPES:
        question_type = "short_answer"
    normalized["question_type"] = question_type

    normalized["topic"] = clean_text(normalized.get("topic")) or course_type.replace("_", " ")
    normalized["skill_target"] = clean_text(normalized.get("skill_target")) or default_skill_target(course_type)
    normalized["difficulty"] = clean_text(normalized.get("difficulty")) or "Medium"
    normalized["question_text"] = clean_text(normalized.get("question_text")) or (
        f"Apply {normalized['skill_target']} to a concrete case."
    )
    normalized["concept_tested"] = clean_text(normalized.get("concept_tested")) or normalized["skill_target"]
    normalized["related_section"] = clean_text(normalized.get("related_section")) or related_section_for_type(question_type)
    normalized["why_this_matters"] = clean_text(normalized.get("why_this_matters")) or (
        f"This checks whether you can use {normalized['concept_tested']} rather than only recognize it."
    )
    normalized["correct_answer"] = clean_text(normalized.get("correct_answer"))
    normalized["explanation"] = clean_text(normalized.get("explanation"))

    normalized["choices"] = normalize_string_list(normalized.get("choices"))
    normalized["given"] = normalize_string_list(normalized.get("given"))
    normalized["starter_code"] = clean_text(normalized.get("starter_code"))
    normalized["language"] = clean_text(normalized.get("language"))
    normalized["test_cases"] = normalize_test_cases(normalized.get("test_cases"))

    if question_type not in {"multiple_choice", "select_all"}:
        normalized["choices"] = []
    if question_type not in {"math", "math_input"}:
        normalized["given"] = (
            normalized["given"]
            if question_type
            in {"short_answer", "visual_labeling", "ordering", "debugging", "debugging_scenario", "decision_scenario"}
            else []
        )
    if question_type not in {"coding", "coding_environment"}:
        normalized["starter_code"] = ""
        normalized["language"] = ""
        normalized["test_cases"] = []

    return normalized, normalized != original


def default_skill_target(course_type: str) -> str:
    requirements = COURSE_TYPE_PRACTICE_REQUIREMENTS.get(
        course_type,
        COURSE_TYPE_PRACTICE_REQUIREMENTS["concept_intuition"],
    )
    return requirements["skills"][0]


def related_section_for_type(question_type: str) -> str:
    if question_type in {"coding", "coding_environment"}:
        return "Coding Implementation"
    if question_type in {"math", "math_input"}:
        return "Formula / Method"
    if question_type in {"multiple_choice", "select_all"}:
        return "Reasoning Check"
    if question_type in {"debugging", "debugging_scenario"}:
        return "Debugging / Error Diagnosis"
    if question_type == "decision_scenario":
        return "Decision Scenario"
    if question_type == "ordering":
        return "Ordering / Process Trace"
    if question_type == "visual_labeling":
        return "Visual Labeling"
    return "Practice"


def normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def normalize_test_cases(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    cases: list[dict[str, str]] = []
    for item in value[:10]:
        if not isinstance(item, dict):
            continue
        cases.append(
            {
                "input": clean_text(item.get("input")),
                "expected": clean_text(item.get("expected")),
            }
        )
    return cases


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def should_regenerate_practice(issues: list[str]) -> bool:
    return any(
        marker in issue
        for issue in issues
        for marker in (
            "no usable practice",
            "needs practice type",
            "missing starter_code",
            "missing test_cases",
            "does not have at least two choices",
            "missing given",
        )
    )


def build_report(
    passed: bool,
    requires_regeneration: bool,
    repaired_count: int,
    issues: list[str],
    actual_question_types: list[str],
    expected_question_types: list[str],
) -> dict[str, Any]:
    return {
        "passed": passed,
        "requires_regeneration": requires_regeneration,
        "repaired_question_count": repaired_count,
        "issues": issues,
        "actual_question_types": actual_question_types,
        "expected_question_types": expected_question_types,
    }
