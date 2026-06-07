from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Iterable

from app.core.course_blueprints import get_course_blueprint, get_course_blueprints

if TYPE_CHECKING:
    from app.models.topic import Topic


REQUEST_VERBS = {
    "explain",
    "teach",
    "show",
    "walk through",
    "walkthrough",
    "implement",
    "code",
    "add",
    "include",
    "cover",
    "go over",
}


def normalize_scope_phrase(value: Any) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", str(value)).lower().strip().split())


def parse_prerequisite_topics(raw_prerequisites: Any) -> list[str]:
    if not raw_prerequisites:
        return []
    if isinstance(raw_prerequisites, str):
        return [
            normalize_scope_phrase(part)
            for part in re.split(r"[,;\n]+", raw_prerequisites)
            if part.strip()
        ]
    if isinstance(raw_prerequisites, dict):
        possible_values = [
            raw_prerequisites.get("title"),
            raw_prerequisites.get("name"),
            raw_prerequisites.get("topic"),
        ]
        return [normalize_scope_phrase(v) for v in possible_values if v and str(v).strip()]
    if isinstance(raw_prerequisites, Iterable) and not isinstance(raw_prerequisites, dict):
        results: list[str] = []
        for item in raw_prerequisites:
            results.extend(parse_prerequisite_topics(item))
        return results
    scalar = str(raw_prerequisites).strip()
    return [normalize_scope_phrase(scalar)] if scalar else []


def normalize_list_field(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [
            part.strip()
            for part in re.split(r"[,;\n]+", value)
            if part.strip()
        ]
    return [str(value).strip()] if str(value).strip() else []


def dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = normalize_scope_phrase(item)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(str(item).strip())
    return result


def get_study_path_topics(topic: Any, study_path: Any = None) -> list:
    sp = study_path or getattr(topic, "study_path", None)
    if sp is None:
        study_paths = getattr(topic, "study_paths", None)
        if study_paths:
            try:
                sp = study_paths[0]
            except (IndexError, TypeError):
                pass
    if sp is None:
        return []
    try:
        return list(sp.topics or [])
    except Exception:
        return []


def get_allowed_card_sequence(
    topic_type: str,
    secondary_topic_types: list[str],
) -> tuple[list[str], list[str]]:
    depth_notes: list[str] = []
    try:
        primary_blueprint = get_course_blueprint(topic_type)
        allowed = list(primary_blueprint.get("default_card_sequence") or [])
        blueprints = get_course_blueprints(topic_type, secondary_topic_types)
        for bp in blueprints[1:]:
            continuation = (
                bp.get("continuation_card_sequence") or bp.get("default_card_sequence") or []
            )
            for key in continuation:
                if key not in allowed:
                    allowed.append(key)
        return allowed, depth_notes
    except Exception:
        depth_notes.append(
            f"Blueprint for topic_type '{topic_type}' not found; generic fallback cards only."
        )
        return [], depth_notes


def build_scope_boundaries_from_siblings(
    topic: Any,
    study_path: Any,
    prior_concept_states: dict[str, str] | None,
) -> tuple[list[str], list[str], list[str], list[str]]:
    """Return (assumed_prerequisites, brief_refresh_prerequisites, out_of_scope_content, depth_notes)."""
    assumed_prerequisites: list[str] = []
    brief_refresh_prerequisites: list[str] = []
    out_of_scope_content: list[str] = []
    depth_notes: list[str] = []

    all_topics = get_study_path_topics(topic, study_path)
    if not all_topics:
        return assumed_prerequisites, brief_refresh_prerequisites, out_of_scope_content, depth_notes

    current_topic_id = str(getattr(topic, "id", "") or "")
    prerequisite_phrases = parse_prerequisite_topics(getattr(topic, "prerequisite_topics", None))

    fragile_or_unknown_concepts: set[str] = set()
    if prior_concept_states:
        fragile_or_unknown_concepts = {
            normalize_scope_phrase(concept)
            for concept, state in prior_concept_states.items()
            if state in {"fragile", "unknown"}
        }

    for sibling in all_topics:
        sibling_id = str(getattr(sibling, "id", "") or "")
        if sibling_id == current_topic_id:
            continue

        sibling_title = str(getattr(sibling, "title", "") or "").strip()
        if not sibling_title:
            continue

        normalized_sibling = normalize_scope_phrase(sibling_title)

        is_prerequisite = any(
            normalized_sibling == prereq
            or prereq in normalized_sibling
            or normalized_sibling in prereq
            for prereq in prerequisite_phrases
        ) if prerequisite_phrases else False

        if is_prerequisite:
            is_fragile = any(
                normalized_sibling in concept or concept in normalized_sibling
                for concept in fragile_or_unknown_concepts
            ) if fragile_or_unknown_concepts else False

            if is_fragile:
                brief_refresh_prerequisites.append(sibling_title)
            else:
                assumed_prerequisites.append(sibling_title)
        else:
            out_of_scope_content.append(sibling_title)

    if out_of_scope_content:
        sample = out_of_scope_content[:5]
        suffix = " and others." if len(out_of_scope_content) > 5 else "."
        depth_notes.append(
            f"Sibling topics are out of scope: {', '.join(sample)}{suffix}"
        )

    return assumed_prerequisites, brief_refresh_prerequisites, out_of_scope_content, depth_notes


def derive_must_not_teach(out_of_scope_content: list[str]) -> list[str]:
    result: list[str] = []
    for phrase in out_of_scope_content:
        if not phrase:
            continue
        result.append(phrase)
        result.append(f"how {phrase} works")
    return result


def infer_target_skill(topic_type: str, topic_title: str) -> str:
    skill_map = {
        "algorithm_walkthrough": "Trace the algorithm state and explain each decision.",
        "coding_implementation": "Implement the focused idea correctly in code.",
        "data_structure_operation": "Perform the operation while preserving the structure invariant.",
        "terminology_components": "Use the key terms and component roles correctly.",
        "process_walkthrough": "Apply the process in the correct order and explain each step.",
        "math_formula_method": "Set up and apply the formula or method accurately.",
        "proof_reasoning": "Choose valid reasoning steps and justify the claim.",
        "compare_distinguish": "Distinguish similar ideas and choose the correct one.",
        "problem_solving_application": "Recognize the problem pattern and apply the strategy.",
        "math_proof_reasoning": "Use the method, formula, or proof step with valid reasoning.",
        "math_formula_method": "Set up and apply the method accurately.",
        "proof_reasoning": "Choose valid reasoning steps and justify the conclusion.",
        "compare_decide": "Choose which idea applies and explain the deciding difference.",
        "compare_distinguish": "Choose which idea applies and explain the deciding difference.",
        "problem_solving_pattern": "Recognize the pattern signal and apply the template correctly.",
        "system_workflow_debugging": "Trace the flow, isolate issues, and verify the result.",
        "debugging_diagnosis": "Isolate the cause, apply the fix, and verify the result.",
        "design_decision": "Choose the best option under constraints and state the deciding criterion.",
        "application_historical": "Map the idea to its use case or development context.",
        "science_mechanism": "Trace the mechanism and predict what changes.",
    }
    return skill_map.get(topic_type, f"Understand and apply {topic_title or 'the current topic'}.")


def build_topic_scope_contract(
    topic: Any,
    study_path: Any = None,
    user_goal: str | None = None,
    prior_concept_states: dict[str, str] | None = None,
) -> dict[str, Any]:
    topic_type = str(
        getattr(topic, "topic_type", None)
        or getattr(topic, "course_type", None)
        or "concept_intuition"
    )
    secondary_topic_types = getattr(topic, "secondary_course_types", None)
    if not isinstance(secondary_topic_types, list):
        secondary_topic_types = []

    topic_title = str(getattr(topic, "title", None) or "Current topic").strip()
    topic_purpose = str(getattr(topic, "purpose", None) or "").strip()
    goal_text = user_goal or topic_purpose or topic_title

    assumed_prerequisites, brief_refresh_prerequisites, out_of_scope_content, sibling_depth_notes = (
        build_scope_boundaries_from_siblings(
            topic=topic,
            study_path=study_path,
            prior_concept_states=prior_concept_states,
        )
    )

    # Merge explicitly listed prerequisites into assumed, avoiding duplicates
    explicit_prerequisites = parse_prerequisite_topics(getattr(topic, "prerequisite_topics", None))
    for prereq in explicit_prerequisites:
        if prereq and prereq not in assumed_prerequisites and prereq not in brief_refresh_prerequisites:
            assumed_prerequisites.insert(0, prereq)

    allowed_sequence, sequence_depth_notes = get_allowed_card_sequence(
        topic_type=topic_type,
        secondary_topic_types=secondary_topic_types,
    )

    explicit_in_scope = normalize_list_field(getattr(topic, "in_scope", None))
    explicit_out_of_scope = normalize_list_field(getattr(topic, "out_of_scope", None))
    explicit_assumed = normalize_list_field(getattr(topic, "assumed_prerequisites", None))

    assumed_prerequisites = dedupe_keep_order(explicit_assumed + assumed_prerequisites)
    out_of_scope_content = dedupe_keep_order(explicit_out_of_scope + out_of_scope_content)
    must_not_teach = derive_must_not_teach(out_of_scope_content)

    depth_notes = [
        "Teach the current topic only — do not expand into sibling topics or the broader parent concept.",
        "Keep prerequisites as assumed, brief refresh, popup-only, or mini-path candidates per the contract.",
        *sibling_depth_notes,
        *sequence_depth_notes,
    ]

    return {
        "current_topic": topic_title,
        "user_goal": goal_text,
        "topic_type": topic_type,
        "course_type": topic_type,
        "secondary_topic_types": secondary_topic_types,
        "secondary_course_types": secondary_topic_types,
        "primary_learning_goal": topic_purpose or f"Learn {topic_title}.",
        "target_skill": infer_target_skill(topic_type, topic_title),
        "assumed_prerequisites": assumed_prerequisites,
        "brief_refresh_prerequisites": brief_refresh_prerequisites,
        "popup_only_prerequisites": [],
        "prerequisite_mini_path_candidates": [],
        "in_scope_content": dedupe_keep_order(
            [
                topic_title,
                getattr(topic, "learner_outcome", None) or "",
                topic_purpose or "The focused learning goal for this topic.",
                *explicit_in_scope,
            ]
        ),
        "out_of_scope_content": out_of_scope_content,
        "must_not_teach": must_not_teach,
        "allowed_card_sequence": allowed_sequence,
        "depth_notes": depth_notes,
    }


def format_scope_contract_for_prompt(contract: dict) -> str:
    if not contract:
        return ""

    lines: list[str] = []

    lines.append(f"current_topic: {contract.get('current_topic', '')}")
    lines.append(f"user_goal: {contract.get('user_goal', '')}")
    lines.append(f"topic_type: {contract.get('topic_type') or contract.get('course_type', '')}")

    secondary = contract.get("secondary_course_types") or []
    if secondary:
        lines.append(f"secondary_topic_types: {', '.join(secondary)}")

    lines.append(f"primary_learning_goal: {contract.get('primary_learning_goal', '')}")
    lines.append(f"target_skill: {contract.get('target_skill', '')}")

    assumed = contract.get("assumed_prerequisites") or []
    if assumed:
        lines.append(f"assumed_prerequisites: {'; '.join(assumed[:10])}")

    brief_refresh = contract.get("brief_refresh_prerequisites") or []
    if brief_refresh:
        lines.append(f"brief_refresh_prerequisites: {'; '.join(brief_refresh[:5])}")

    popup_only = contract.get("popup_only_prerequisites") or []
    if popup_only:
        lines.append(f"popup_only_prerequisites: {'; '.join(popup_only[:5])}")

    mini_path = contract.get("prerequisite_mini_path_candidates") or []
    if mini_path:
        lines.append(f"prerequisite_mini_path_candidates: {'; '.join(str(x) for x in mini_path[:5])}")

    in_scope = contract.get("in_scope_content") or []
    if in_scope:
        lines.append(f"in_scope_content: {'; '.join(in_scope[:10])}")

    out_of_scope = contract.get("out_of_scope_content") or []
    if out_of_scope:
        lines.append(f"out_of_scope_content: {'; '.join(out_of_scope[:10])}")

    must_not = contract.get("must_not_teach") or []
    if must_not:
        lines.append(f"must_not_teach: {'; '.join(must_not[:20])}")

    allowed = contract.get("allowed_card_sequence") or []
    if allowed:
        lines.append(f"allowed_card_sequence: {', '.join(allowed)}")

    depth_notes = contract.get("depth_notes") or []
    for note in depth_notes:
        lines.append(f"depth_note: {note}")

    return "\n".join(lines)


def detect_out_of_scope_feedback_request(
    feedback: str | None,
    topic_scope_contract: dict | None,
) -> dict | None:
    if not feedback or not topic_scope_contract:
        return None

    out_of_scope_phrases = [
        normalize_scope_phrase(phrase)
        for phrase in (topic_scope_contract.get("out_of_scope_content") or [])
        if phrase
    ] + [
        normalize_scope_phrase(phrase)
        for phrase in (topic_scope_contract.get("must_not_teach") or [])
        if phrase
    ]

    if not out_of_scope_phrases:
        return None

    sentences = re.split(r"(?<=[.!?])\s+|(?<=\n)", feedback.strip())

    for sentence in sentences:
        normalized_sentence = normalize_scope_phrase(sentence)
        has_verb = any(verb in normalized_sentence for verb in REQUEST_VERBS)
        if not has_verb:
            continue
        for phrase in out_of_scope_phrases:
            if phrase and phrase in normalized_sentence:
                return {
                    "matched_phrase": phrase,
                    "matched_sentence": sentence.strip(),
                    "note": (
                        f"The feedback requests teaching '{phrase}', which is out of scope "
                        f"for the current topic '{topic_scope_contract.get('current_topic', '')}'."
                    ),
                }

    return None
