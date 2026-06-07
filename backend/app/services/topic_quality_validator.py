from __future__ import annotations

from typing import Any

from app.core.course_blueprints import get_course_blueprint
from app.core.course_stage_rules import STAGE_RULES


BLUEPRINT_KEY_HINTS: dict[str, tuple[str, ...]] = {
    "context_first_impression": ("context", "first impression", "purpose", "why"),
    "definition": ("definition", "meaning", "what is"),
    "components_parts": ("component", "part", "vocabulary"),
    "how_it_works": ("how it works", "works", "mechanism"),
    "comprehensive_example": ("example", "worked", "concrete"),
    "practice": ("practice", "check", "problem"),
    "algorithm_rule_main_idea": ("algorithm rule", "main idea", "rule"),
    "state_components": ("state", "queue", "stack", "visited", "component"),
    "comprehensive_walkthrough_example": ("walkthrough", "trace", "step"),
    "final_result_output": ("final", "output", "result"),
    "algorithm_analysis": ("analysis", "complexity", "runtime", "space"),
    "function_goal_first_impression": ("function goal", "goal", "input", "output"),
    "inputs_outputs_expected_behavior": ("input", "output", "expected"),
    "key_idea_from_previous_topic": ("key idea", "previous", "refresher"),
    "variables_state_needed": ("variable", "state"),
    "edge_cases_base_cases": ("edge", "base case"),
    "code_build_up": ("code build", "line", "implementation"),
    "full_code": ("full code", "solution", "implementation"),
    "code_walkthrough_dry_run": ("dry run", "walkthrough", "trace"),
    "complexity": ("complexity", "runtime", "space", "big-o"),
    "structure_refresh_first_impression": ("structure", "refresh", "property"),
    "operation_goal": ("operation goal", "goal"),
    "cases_scenarios": ("case", "scenario"),
    "how_operation_works": ("operation works", "how", "step"),
    "comprehensive_operation_example": ("operation example", "example"),
    "validity_invariant_check": ("valid", "invariant", "property"),
    "benefits_limitations_complexity": ("benefit", "limitation", "complexity"),
    "formula_method_meaning": ("formula", "meaning", "method"),
    "symbols_inputs_conditions": ("symbol", "condition", "input"),
    "step_by_step_method": ("step", "method"),
    "comprehensive_worked_example": ("worked example", "example"),
    "edge_cases_conditions": ("edge", "condition", "domain"),
    "proof_goal_first_impression": ("proof goal", "prove"),
    "given_information": ("given", "know"),
    "definitions_allowed_facts": ("definition", "fact", "theorem"),
    "proof_strategy": ("strategy", "proof method"),
    "proof_skeleton": ("skeleton", "outline"),
    "step_by_step_proof": ("proof step", "step"),
    "validity_why_steps_work": ("valid", "why"),
    "invalid_reasoning_common_trap": ("invalid", "trap", "mistake"),
    "comparison_first_impression": ("compare", "difference"),
    "idea_a_separately": ("idea a", "first"),
    "idea_b_separately": ("idea b", "second"),
    "shared_features": ("shared", "common"),
    "key_differences": ("difference", "contrast"),
    "same_example_applied_to_both": ("same example", "both"),
    "when_to_use_each": ("when to use", "use each"),
    "common_mixups_misconceptions": ("mix", "misconception", "mistake"),
    # ── Problem-Solving Pattern ──────────────────────────────────────────────
    "pattern_first_impression": ("pattern", "problem type", "approach"),
    "when_pattern_applies": ("when", "applies", "recogni"),
    "pattern_signals": ("signal", "indicator", "cue", "recogni"),
    "core_template": ("template", "pseudo", "structure"),
    "state_or_invariant": ("invariant", "state", "maintain"),
    "comprehensive_pattern_example": ("pattern example", "trace", "step"),
    "variations_and_edge_cases": ("variation", "edge", "adapt"),
    "similar_patterns_to_avoid": ("similar", "avoid", "confuse"),
    # ── Review / Refresh ─────────────────────────────────────────────────────
    "quick_diagnostic_first_check": ("diagnostic", "first check", "probe"),
    "compressed_recall_card": ("recall", "compressed", "high-yield"),
    "key_rule_procedure_refresh": ("key rule", "procedure", "refresh"),
    "high_yield_example": ("high-yield", "sharp", "quick example"),
    "targeted_repair_if_needed": ("repair", "weak", "reteach"),
    "practice_weak_area_check": ("weak area", "check", "practice"),
    "return_to_flow_bridge": ("bridge", "return", "continue"),
    # ── Science Mechanism ────────────────────────────────────────────────────
    "definition_core_mechanism": ("mechanism", "core", "definition"),
    "cause_effect_chain_process_steps": ("cause", "effect", "chain", "process"),
    "comprehensive_mechanism_example": ("mechanism example", "trace", "concrete"),
    "variable_change_perturbation": ("perturbation", "variable", "change"),
    "graph_data_model_interpretation": ("graph", "data", "interpretation", "model"),
    "benefits_limitations_scope": ("benefit", "limitation", "scope"),
    # ── System / Architecture ────────────────────────────────────────────────
    "system_first_impression": ("system", "architecture", "overview"),
    "system_goal_responsibility": ("goal", "responsibility", "purpose"),
    "major_components": ("component", "major", "module"),
    "connections_interfaces": ("connection", "interface", "contract"),
    "end_to_end_flow": ("end-to-end", "flow", "request", "trace"),
    "component_deep_dive": ("deep dive", "internal", "detail"),
    "failure_points_bottlenecks": ("failure", "bottleneck", "break"),
    "design_choices_tradeoffs": ("design choice", "tradeoff", "decision"),
    "comprehensive_system_example": ("system example", "realistic", "trace"),
    # ── Debugging / Error Diagnosis ──────────────────────────────────────────
    "symptom_first_impression": ("symptom", "error", "observe"),
    "expected_vs_actual_behavior": ("expected", "actual", "gap"),
    "error_context_system_area": ("context", "system area", "layer"),
    "possible_causes": ("cause", "hypothesis", "possible"),
    "diagnostic_checks": ("diagnostic", "check", "narrow"),
    "comprehensive_debugging_walkthrough": ("debugging walkthrough", "trace", "session"),
    "fix": ("fix", "patch", "resolve"),
    "verification": ("verify", "confirm", "test"),
    "prevention": ("prevent", "avoid", "recur"),
    # ── Tool / Workflow ──────────────────────────────────────────────────────
    "workflow_first_impression": ("workflow", "tool", "pipeline"),
    "setup_requirements": ("setup", "requirement", "prerequisite"),
    "files_commands_ui_parts": ("command", "file", "ui", "control"),
    "step_by_step_workflow": ("workflow step", "step-by-step", "action"),
    "verification_steps": ("verification", "success", "confirm"),
    "common_breakpoints_troubleshooting": ("breakpoint", "troubleshoot", "error"),
    "comprehensive_workflow_example": ("workflow example", "realistic", "complete"),
    "best_practices_safety_notes": ("best practice", "safety", "note"),
    # ── Design / Decision ────────────────────────────────────────────────────
    "decision_context_first_impression": ("decision", "context", "option"),
    "options_overview": ("option", "overview", "choice"),
    "decision_criteria": ("criterion", "criteria", "evaluate"),
    "tradeoff_breakdown": ("tradeoff", "gain", "sacrifice"),
    "scenario_based_decision_walkthrough": ("scenario", "decision walkthrough", "eliminate"),
    "when_decision_changes": ("changes", "flip", "constraint"),
    "common_wrong_decision_misconception": ("wrong decision", "misconception", "flaw"),
    "benefits_limitations_final_choice": ("final choice", "benefit", "limit"),
    # ── Case Study / Application ─────────────────────────────────────────────
    "real_scenario_first_impression": ("real scenario", "application", "context"),
    "concept_refresh_if_needed": ("refresh", "recall", "compact"),
    "concept_to_scenario_mapping": ("mapping", "abstract", "real"),
    "scenario_components_roles": ("scenario component", "role", "actor"),
    "step_by_step_application": ("application step", "apply", "step"),
    "result_impact": ("result", "impact", "outcome"),
    "variation_failure_case": ("variation", "failure case", "misapply"),
    "benefits_limitations_in_this_scenario": ("limitation", "scenario", "context"),
    # ── Historical / Development ─────────────────────────────────────────────
    "starting_context_first_impression": ("starting context", "history", "origin"),
    "initial_model_early_approach": ("initial model", "early", "first approach"),
    "limitations_pressure_for_change": ("limitation", "pressure", "problem"),
    "major_development_timeline": ("timeline", "development", "milestone"),
    "turning_point_cards": ("turning point", "breakthrough", "shift"),
    "cause_effect_development_chain": ("cause", "effect", "development chain"),
    "modern_version_current_understanding": ("modern", "current", "today"),
    "what_stayed_vs_changed": ("stayed", "changed", "stable"),
    "benefits_limitations_modern_version": ("modern version", "benefit", "limit"),
    # ── Process / Lifecycle ──────────────────────────────────────────────────
    "process_first_impression": ("process", "lifecycle", "cycle"),
    "stage_overview": ("stage", "overview", "phases"),
    "stage_by_stage_cards": ("stage", "input", "output", "handoff"),
    "transitions_handoffs": ("transition", "handoff", "pass"),
    "feedback_loops_repeats": ("feedback loop", "repeat", "cycle back"),
    "comprehensive_process_example": ("process example", "trace", "realistic"),
    # ── Terminology / Vocabulary ─────────────────────────────────────────────
    "term_set_first_impression": ("term", "vocabulary", "language"),
    "term_map_grouping": ("term map", "group", "relationship"),
    "core_term_cluster_cards": ("term cluster", "definition", "role"),
    "same_example_with_labels": ("label", "same example", "annotate"),
    "similar_confusing_terms": ("confusing", "similar term", "distinguish"),
    "usage_in_context": ("usage", "context", "sentence"),
    # ── Exam / Interview Prep ────────────────────────────────────────────────
    "assessment_first_impression": ("assessment", "exam", "interview", "format"),
    "scope_high_yield_topics": ("scope", "high-yield", "topic list"),
    "question_types": ("question type", "format", "variant"),
    "strategy_selection": ("strategy", "first move", "approach"),
    "timed_or_realistic_example": ("timed", "realistic", "problem"),
    "common_traps": ("trap", "common mistake", "pitfall"),
    "weak_area_repair": ("weak area", "repair", "reteach"),
    "mixed_practice": ("mixed practice", "set", "review"),
    "review_plan": ("review plan", "study", "schedule"),
}


GENERIC_FALLBACK_TITLES = {
    "starting point check",
    "why this topic matters",
    "big-picture intuition",
    "core vocabulary / components",
    "how the idea works",
    "step-by-step method",
    "visual or concrete example",
    "common mistakes / edge cases",
    "guided practice",
    "adaptive follow-up",
    "real problem/application",
    "summary / mental model",
    "mastery check",
    "review-later recommendation",
}


COURSE_TYPE_REQUIRED_PRACTICE = {
    "terminology_components": {"short_answer", "multiple_choice", "visual_labeling"},
    "process_walkthrough": {"short_answer", "multiple_choice", "ordering", "math", "math_input"},
    "coding_implementation": {"coding", "coding_environment", "debugging"},
    "math_formula_method": {"math", "math_input"},
    "proof_reasoning": {"short_answer", "multiple_choice", "math", "math_input", "ordering"},
    "compare_distinguish": {"short_answer", "multiple_choice", "decision_scenario"},
    "problem_solving_application": {
        "short_answer",
        "multiple_choice",
        "coding",
        "coding_environment",
        "debugging",
        "math",
        "math_input",
    },
    "algorithm_walkthrough": {"short_answer", "multiple_choice", "ordering", "visual_labeling"},
    "data_structure_operation": {
        "short_answer",
        "multiple_choice",
        "visual_labeling",
        "coding",
        "coding_environment",
    },
    "debugging_diagnosis": {
        "multiple_choice",
        "short_answer",
        "coding",
        "coding_environment",
        "debugging",
        "debugging_scenario",
    },
}


def validate_generated_topic(
    lesson_json: dict[str, Any],
    course_type: str | None = None,
    user_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    text_only_core_mode = lesson_json.get("generation_mode") == "text_only_core"
    resolved_course_type = course_type or str(
        lesson_json.get("course_type") or "concept_intuition"
    )
    blueprint = get_course_blueprint(resolved_course_type)
    expected_sequence = blueprint.get("default_card_sequence", [])
    cards = lesson_json.get("lesson_cards")
    issues: list[dict[str, Any]] = []

    if not isinstance(cards, list) or not cards:
        issues.append(error("missing_cards", "Lesson has no lesson_cards."))
        report = build_report(issues)
        lesson_json["topic_quality_report"] = report
        return report

    if not lesson_json.get("course_type"):
        issues.append(warning("missing_course_type", "Lesson JSON is missing course_type metadata."))

    coverage = calculate_blueprint_coverage(cards, expected_sequence)
    if expected_sequence and coverage["ratio"] < required_coverage_ratio(resolved_course_type):
        issues.append(
            error(
                "blueprint_sequence_gap",
                (
                    f"Lesson only covers {coverage['matched_count']} of "
                    f"{coverage['expected_count']} expected blueprint sections."
                ),
                details={"missing_blueprint_keys": coverage["missing_keys"]},
            )
        )

    generic_count = count_generic_fallback_cards(cards)
    if resolved_course_type != "concept_intuition" and generic_count >= max(5, len(cards) // 2):
        issues.append(
            error(
                "generic_fallback_overuse",
                "Course-type lesson appears to use the generic fallback card sequence too heavily.",
                details={"generic_card_count": generic_count},
            )
        )

    validate_card_density(cards, issues)
    validate_stage_rule_compliance(
        cards,
        expected_sequence,
        resolved_course_type,
        issues,
        require_microchecks_and_visuals=not text_only_core_mode,
    )
    validate_practice(lesson_json, resolved_course_type, issues)
    validate_practice_quality_report(lesson_json, issues)
    if not text_only_core_mode:
        validate_microcheck_report(lesson_json, issues)
    validate_existing_reports(lesson_json, issues)

    report = build_report(issues)
    report["blueprint_coverage"] = coverage
    report["generic_fallback_card_count"] = generic_count
    lesson_json["topic_quality_report"] = report
    return report


def calculate_blueprint_coverage(
    cards: list[Any],
    expected_sequence: list[str],
) -> dict[str, Any]:
    if not expected_sequence:
        return {
            "expected_count": 0,
            "matched_count": 0,
            "ratio": 1.0,
            "missing_keys": [],
        }

    card_objects = [card for card in cards if isinstance(card, dict)]
    card_texts = [card_search_text(card) for card in card_objects]
    explicit_keys = {
        normalize_text(card.get("blueprint_key"))
        for card in card_objects
        if normalize_text(card.get("blueprint_key"))
    }
    missing_keys: list[str] = []
    matched_count = 0

    for key in expected_sequence:
        hints = BLUEPRINT_KEY_HINTS.get(key) or tuple(key.replace("_", " ").split())
        if key in explicit_keys or any(any(hint in text for hint in hints) for text in card_texts):
            matched_count += 1
        else:
            missing_keys.append(key)

    return {
        "expected_count": len(expected_sequence),
        "matched_count": matched_count,
        "ratio": matched_count / len(expected_sequence),
        "missing_keys": missing_keys,
    }


def card_search_text(card: dict[str, Any]) -> str:
    pieces: list[str] = []
    for key in ("title", "card_type", "main_concept", "what_to_notice"):
        pieces.append(str(card.get(key) or ""))
    for key in ("points", "body", "bullets", "new_concepts", "review_concepts"):
        value = card.get(key)
        if isinstance(value, list):
            pieces.extend(str(item) for item in value)
    return " ".join(pieces).lower()


def required_coverage_ratio(course_type: str) -> float:
    if course_type in {"coding_implementation", "algorithm_walkthrough", "math_formula_method"}:
        return 0.7
    if course_type == "review_refresh":
        return 0.55
    return 0.62


def count_generic_fallback_cards(cards: list[Any]) -> int:
    count = 0
    for card in cards:
        if not isinstance(card, dict):
            continue
        title = normalize_text(card.get("title"))
        if title in GENERIC_FALLBACK_TITLES:
            count += 1
    return count


def validate_card_density(cards: list[Any], issues: list[dict[str, Any]]) -> None:
    for index, card in enumerate(cards):
        if not isinstance(card, dict):
            issues.append(error("invalid_card", f"Card {index} is not an object."))
            continue

        points = normalize_list(card.get("points"))
        body = normalize_list(card.get("body"))
        title = str(card.get("title") or "").strip()
        main_concept = str(card.get("main_concept") or "").strip()

        if not title:
            issues.append(error("missing_card_title", f"Card {index} is missing a title."))
        if not main_concept:
            issues.append(warning("missing_main_concept", f"Card {index} is missing main_concept."))
        if not points and not body:
            issues.append(error("empty_card", f"Card {index} has no visible points or body."))
        if len(points) > 4:
            issues.append(warning("dense_card", f"Card {index} has more than 4 points."))
        if any(len(point.split()) > 26 for point in points):
            issues.append(warning("long_point", f"Card {index} has a very long point."))
        if any(len(paragraph.split()) > 80 for paragraph in body):
            issues.append(error("text_wall", f"Card {index} has a body paragraph over 80 words."))


def validate_stage_rule_compliance(
    cards: list[Any],
    expected_sequence: list[str],
    course_type: str,
    issues: list[dict[str, Any]],
    require_microchecks_and_visuals: bool = True,
) -> None:
    stage_rules = STAGE_RULES.get(course_type)
    if not stage_rules or not expected_sequence:
        return

    card_map = map_cards_to_stage_keys(cards, expected_sequence)
    gap_count = 0

    for stage_key in expected_sequence:
        rule = stage_rules.get(stage_key)
        matched_cards = card_map.get(stage_key) or []
        if not rule or not matched_cards:
            continue

        combined_text = " ".join(card_search_text(card) for card in matched_cards)
        missing_content = missing_critical_stage_content(rule, combined_text)
        if len(missing_content) >= 2:
            gap_count += 1
            issues.append(
                warning(
                    "stage_content_gap",
                    f"{stage_key} card may not cover required stage details.",
                    details={
                        "blueprint_key": stage_key,
                        "missing_content_expectations": missing_content[:3],
                    },
                )
            )

        if require_microchecks_and_visuals:
            microcheck = str(rule.get("microcheck") or "").strip()
            if microcheck and not any(card_has_microcheck(card) for card in matched_cards):
                gap_count += 1
                issues.append(
                    warning(
                        "stage_microcheck_missing",
                        f"{stage_key} expects a lightweight microcheck, but none was found.",
                        details={
                            "blueprint_key": stage_key,
                            "expected_microcheck": microcheck,
                        },
                    )
                )

            visual = str(rule.get("visual") or "").strip()
            if stage_requires_actual_visual(visual) and not any(card_has_visual(card) for card in matched_cards):
                gap_count += 1
                issues.append(
                    warning(
                        "stage_visual_missing",
                        f"{stage_key} expects a concrete visual, but no visual was found.",
                        details={
                            "blueprint_key": stage_key,
                            "expected_visual": visual,
                        },
                    )
                )

    if gap_count >= max(5, (len(expected_sequence) // 2) + 1):
        issues.append(
            error(
                "stage_rule_compliance_gap",
                "Several cards exist but do not appear to follow their per-stage blueprint rules.",
                details={
                    "gap_count": gap_count,
                    "course_type": course_type,
                },
            )
        )


def map_cards_to_stage_keys(
    cards: list[Any],
    expected_sequence: list[str],
) -> dict[str, list[dict[str, Any]]]:
    card_objects = [card for card in cards if isinstance(card, dict)]
    mapped: dict[str, list[dict[str, Any]]] = {key: [] for key in expected_sequence}
    used_indexes: set[int] = set()

    for card_index, card in enumerate(card_objects):
        blueprint_key = normalize_text(card.get("blueprint_key"))
        if blueprint_key in mapped:
            mapped[blueprint_key].append(card)
            used_indexes.add(card_index)

    for sequence_index, stage_key in enumerate(expected_sequence):
        if mapped[stage_key]:
            continue

        hints = BLUEPRINT_KEY_HINTS.get(stage_key) or tuple(stage_key.replace("_", " ").split())
        matched_index = None

        for card_index, card in enumerate(card_objects):
            if card_index in used_indexes:
                continue
            text = card_search_text(card)
            if any(hint in text for hint in hints):
                matched_index = card_index
                break

        if matched_index is None and sequence_index < len(card_objects):
            matched_index = sequence_index

        if matched_index is not None and matched_index not in used_indexes:
            mapped[stage_key].append(card_objects[matched_index])
            used_indexes.add(matched_index)

    return mapped


CRITICAL_STAGE_TERMS = {
    "action",
    "assumption",
    "case",
    "condition",
    "constraint",
    "component",
    "complexity",
    "edge",
    "failure",
    "input",
    "invariant",
    "limitation",
    "output",
    "reason",
    "result",
    "state",
    "step",
    "symbol",
    "tradeoff",
    "variable",
}

STAGE_STOPWORDS = {
    "about",
    "after",
    "before",
    "correct",
    "each",
    "every",
    "important",
    "meaningful",
    "normal",
    "only",
    "specific",
    "their",
    "there",
    "these",
    "this",
    "what",
    "when",
    "where",
    "which",
    "while",
    "with",
    "without",
}


def missing_critical_stage_content(rule: dict[str, Any], card_text: str) -> list[str]:
    missing: list[str] = []
    for expectation in rule.get("content") or []:
        expectation_text = normalize_text(expectation)
        if not expectation_has_critical_term(expectation_text):
            continue

        keywords = content_keywords(expectation_text)
        if keywords and not any(keyword in card_text for keyword in keywords):
            missing.append(str(expectation))

    return missing


def expectation_has_critical_term(expectation_text: str) -> bool:
    words = set(expectation_text.replace("/", " ").replace("-", " ").split())
    return bool(words.intersection(CRITICAL_STAGE_TERMS))


def content_keywords(expectation_text: str) -> list[str]:
    words = [
        word.strip(".,:;()[]")
        for word in expectation_text.replace("/", " ").replace("-", " ").split()
    ]
    return [
        word
        for word in words
        if len(word) >= 5
        and word not in STAGE_STOPWORDS
        and word not in {"concept", "lesson", "learner"}
    ][:8]


def card_has_microcheck(card: dict[str, Any]) -> bool:
    micro_check = card.get("micro_check")
    if not isinstance(micro_check, dict):
        return False
    return bool(str(micro_check.get("prompt") or "").strip() and str(micro_check.get("answer") or "").strip())


def card_has_visual(card: dict[str, Any]) -> bool:
    visual_index = card.get("visual_index")
    if isinstance(visual_index, int) and visual_index >= 0:
        return True
    visual_plan = card.get("visual_plan")
    return isinstance(visual_plan, dict) and bool(visual_plan)


def stage_requires_actual_visual(visual: str) -> bool:
    if not visual:
        return False

    lower_visual = visual.lower()
    optional_markers = (
        "if applicable",
        "if useful",
        "if needed",
        "if helpful",
        "if a visual",
        "only if",
    )
    styled_markers = (
        "styled ui",
        "not a visual_plan",
        "code block",
        "syntax-highlighted",
        "table",
        "checklist",
        "latex",
    )
    actual_visual_markers = (
        "architecture",
        "before/after",
        "cause-effect",
        "circuit",
        "diagram",
        "graph",
        "highlight",
        "lifecycle",
        "map",
        "node",
        "per-step",
        "process visual",
        "structure diagram",
        "timeline",
        "visual per step",
    )

    if any(marker in lower_visual for marker in optional_markers):
        return False
    if any(marker in lower_visual for marker in styled_markers):
        return False
    return any(marker in lower_visual for marker in actual_visual_markers)


def validate_practice(
    lesson_json: dict[str, Any],
    course_type: str,
    issues: list[dict[str, Any]],
) -> None:
    practice_questions = lesson_json.get("practice_questions")
    if not isinstance(practice_questions, list) or not practice_questions:
        issues.append(error("missing_practice", "Lesson has no practice_questions."))
        return

    question_types = {
        str(question.get("question_type") or "").strip()
        for question in practice_questions
        if isinstance(question, dict)
    }
    expected_types = COURSE_TYPE_REQUIRED_PRACTICE.get(course_type)
    if expected_types and not question_types.intersection(expected_types):
        issues.append(
            error(
                "practice_type_mismatch",
                f"{course_type} practice should include one of: {', '.join(sorted(expected_types))}.",
                details={"actual_question_types": sorted(question_types)},
            )
        )

    for index, question in enumerate(practice_questions):
        if not isinstance(question, dict):
            continue
        if not str(question.get("concept_tested") or "").strip():
            issues.append(warning("practice_missing_concept", f"Practice question {index} is missing concept_tested."))
        if not str(question.get("why_this_matters") or "").strip():
            issues.append(warning("practice_missing_purpose", f"Practice question {index} is missing why_this_matters."))


def validate_practice_quality_report(lesson_json: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    report = lesson_json.get("practice_quality_report")
    if not isinstance(report, dict):
        return

    if report.get("requires_regeneration"):
        issues.append(
            error(
                "practice_quality_regeneration_required",
                "Practice quality validation requires regeneration.",
                details={
                    "practice_issues": report.get("issues", []),
                    "expected_question_types": report.get("expected_question_types", []),
                    "actual_question_types": report.get("actual_question_types", []),
                },
            )
        )
    elif report.get("issues"):
        issues.append(
            warning(
                "practice_quality_warnings",
                "Practice quality validation found minor issues.",
                details={"practice_issues": report.get("issues", [])[:8]},
            )
        )


def validate_existing_reports(lesson_json: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    visual_report = lesson_json.get("visual_validation_report")
    if isinstance(visual_report, dict) and visual_report.get("requires_regeneration"):
        issues.append(
            error(
                "visual_regeneration_still_required",
                "Visual validation still requires regeneration.",
                details={"visual_issues": visual_report.get("issues", [])},
            )
        )


def validate_microcheck_report(lesson_json: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    report = lesson_json.get("microcheck_report")
    if not isinstance(report, dict):
        return

    removed_count = int(report.get("removed_microcheck_count") or 0)
    if removed_count > 3:
        issues.append(
            warning(
                "many_microchecks_removed",
                "Microcheck cleanup removed several incomplete checks.",
                details={"microcheck_issues": report.get("issues", [])[:8]},
            )
        )

    link_report = lesson_json.get("interactive_link_report")
    if isinstance(link_report, dict) and link_report.get("removed_link_count", 0) > 8:
        issues.append(
            warning(
                "many_interactive_links_removed",
                "Interactive link cleanup removed many links, suggesting over-linking.",
                details={"link_issues": link_report.get("issues", [])[:8]},
            )
        )


def build_quality_retry_feedback(report: dict[str, Any]) -> str:
    issues = report.get("issues")
    if not isinstance(issues, list):
        issues = []

    lines = []
    for issue in issues[:10]:
        if not isinstance(issue, dict):
            continue
        detail = issue.get("message") or issue.get("code") or "Unknown issue."
        details = issue.get("details")
        if isinstance(details, dict) and details.get("missing_blueprint_keys"):
            detail += f" Missing blueprint keys: {', '.join(details['missing_blueprint_keys'])}."
        if isinstance(details, dict) and details.get("blueprint_key"):
            detail += f" Blueprint key: {details['blueprint_key']}."
        if isinstance(details, dict) and details.get("missing_content_expectations"):
            detail += " Missing expectations: " + "; ".join(
                details["missing_content_expectations"][:2]
            ) + "."
        lines.append(f"- {detail}")

    return f"""
TOPIC QUALITY REGENERATION REQUIRED

The previous lesson did not sufficiently follow the selected Azalea course blueprint.

Specific issues:
{chr(10).join(lines) if lines else "- The topic quality validator requested a retry."}

Regenerate the lesson with these fixes:
- Follow the selected course blueprint as the primary lesson_cards backbone.
- Add missing blueprint sections explicitly as learner-facing cards.
- Do not use the generic fallback card sequence unless the topic is truly a generic Concept + Intuition lesson.
- Each card must teach one main idea or one meaningful step.
- Keep points compact, but complete enough to explain the reasoning.
- Include practice_questions that match the course type and test application, edge cases, or implementation as appropriate.
- Preserve valid visuals and links, but do not add placeholder visuals.
""".strip()


def quality_report_score(report: dict[str, Any]) -> int:
    issues = report.get("issues")
    if not isinstance(issues, list):
        issues = []

    score = 100
    for issue in issues:
        if not isinstance(issue, dict):
            score -= 6
            continue
        severity = issue.get("severity")
        if severity == "error":
            score -= 14
        elif severity == "warning":
            score -= 6
        else:
            score -= 2

    coverage = report.get("blueprint_coverage")
    if isinstance(coverage, dict):
        score += int(float(coverage.get("ratio") or 0) * 20)

    if report.get("requires_regeneration"):
        score -= 35

    return score


def build_report(issues: list[dict[str, Any]]) -> dict[str, Any]:
    error_count = sum(1 for issue in issues if issue.get("severity") == "error")
    warning_count = sum(1 for issue in issues if issue.get("severity") == "warning")
    return {
        "passed": error_count == 0,
        "issues": issues,
        "error_count": error_count,
        "warning_count": warning_count,
        "requires_regeneration": any(
            issue.get("severity") == "error" and issue.get("code") in {
                "missing_cards",
                "blueprint_sequence_gap",
                "generic_fallback_overuse",
                "missing_practice",
                "practice_type_mismatch",
                "text_wall",
                "visual_regeneration_still_required",
                "stage_rule_compliance_gap",
            }
            for issue in issues
        ),
    }


def error(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "severity": "error",
        "code": code,
        "message": message,
        "details": details or {},
    }


def warning(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "severity": "warning",
        "code": code,
        "message": message,
        "details": details or {},
    }


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def normalize_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
