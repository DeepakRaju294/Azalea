from typing import Any

from app.core.course_blueprints import COMMON_COMBINATIONS
from app.core.course_types import TopicType
from app.services.knowledge_level_service import estimate_knowledge_level
from app.services.llm_client import generate_course_type_classification
from app.prompts.course_type_classifier_prompt import (
    SYSTEM_PROMPT as CLASSIFIER_SYSTEM_PROMPT,
    build_course_type_classifier_prompt,
)


# Backward-compatible local alias while callers migrate from course_type to topic_type.
CourseType = TopicType


TOPIC_TYPE_KEYWORDS: list[tuple[TopicType, tuple[str, ...]]] = [
    (
        CourseType.PROBLEM_SOLVING_APPLICATION,
        ("exam", "interview", "prep", "timed", "assessment", "test prep"),
    ),
    (
        CourseType.PROBLEM_SOLVING_APPLICATION,
        ("review", "refresh", "forgot", "recall", "quickly", "weak area"),
    ),
    (
        CourseType.COMPARE_DISTINGUISH,
        (" vs ", "versus", "compare", "distinguish", "difference", "differentiate"),
    ),
    (
        CourseType.COMPARE_DISTINGUISH,
        ("tradeoff", "trade-off", "choose", "when to use", "should i use", "decision"),
    ),
    (
        CourseType.PROCESS_WALKTHROUGH,
        ("debug", "error", "fix", "diagnose", "trace bug", "segfault", "exception"),
    ),
    (
        CourseType.PROCESS_WALKTHROUGH,
        ("setup", "install", "workflow", "command", "git ", "terminal", "environment"),
    ),
    (
        CourseType.CODING_IMPLEMENTATION,
        ("implement", "implementation", "code", "write function", "program", "class solution"),
    ),
    (
        CourseType.DATA_STRUCTURE_OPERATION,
        (
            "insert",
            "delete",
            "deletion",
            "search",
            "update",
            "push",
            "pop",
            "enqueue",
            "dequeue",
            "traversal operation",
        ),
    ),
    (
        CourseType.ALGORITHM_WALKTHROUGH,
        (
            "algorithm",
            "walkthrough",
            "step by step",
            "trace",
            "dry run",
            "bfs",
            "dfs",
            "dijkstra",
            "prim",
            "kruskal",
            "quick sort",
            "quicksort",
            "merge sort",
            "binary search",
        ),
    ),
    (
        CourseType.PROBLEM_SOLVING_APPLICATION,
        (
            "pattern",
            "strategy",
            "two pointers",
            "sliding window",
            "recursion tree",
            "dynamic programming",
            "greedy-choice",
            "invariant",
        ),
    ),
    (
        CourseType.MATH_FORMULA_METHOD,
        (
            "formula",
            "calculate",
            "compute",
            "derive",
            "method",
            "theorem",
            "cdf",
            "pdf",
            "integral",
            "derivative",
            "bayes",
            "probability",
            "matrix",
        ),
    ),
    (
        CourseType.PROOF_REASONING,
        ("prove", "proof", "justify", "why true", "reasoning", "induction", "contradiction"),
    ),
    (
        CourseType.SCIENCE_MECHANISM,
        (
            "mechanism",
            "cause-effect",
            "photosynthesis",
            "cellular respiration",
            "action potential",
            "enzyme",
            "equilibrium",
            "osmosis",
            "diffusion",
            "dna replication",
            "biology",
            "chemistry",
            "physics",
            "neuroscience",
            "cell",
            "molecule",
            "force",
            "field",
        ),
    ),
    (
        CourseType.PROCESS_WALKTHROUGH,
        (
            "system",
            "architecture",
            "components",
            "compiler",
            "database",
            "network",
            "operating system",
            "request flow",
        ),
    ),
    (
        CourseType.PROBLEM_SOLVING_APPLICATION,
        ("case study", "application", "real-world", "real world", "used in", "scenario"),
    ),
    (
        CourseType.PROBLEM_SOLVING_APPLICATION,
        ("history", "historical", "evolved", "development over time", "origin"),
    ),
    (
        CourseType.PROCESS_WALKTHROUGH,
        ("lifecycle", "life cycle", "stages", "process", "pipeline", "cycle"),
    ),
    (
        CourseType.TERMINOLOGY_COMPONENTS,
        (
            "terminology",
            "vocabulary",
            "terms",
            "definitions",
            "glossary",
            "components",
            "parts",
            "labels",
            "notation",
            "nodes",
            "vertices",
            "edges",
            "parent child",
            "parent-child",
            "rows columns",
            "parameters",
            "attributes",
        ),
    ),
    (
        CourseType.CONCEPT_INTUITION,
        ("what is", "understand", "intuition", "concept", "learn", "idea"),
    ),
]

COURSE_TYPE_KEYWORDS = TOPIC_TYPE_KEYWORDS


CODING_SECONDARY_MARKERS = (
    "implement",
    "code",
    "write function",
    "solution class",
    "leetcode",
)

NO_CODING_MARKERS = (
    "no code",
    "without code",
    "don't code",
    "dont code",
    "do not code",
    "no implementation",
    "without implementation",
    "trace only",
    "walkthrough only",
    "concept only",
)

DATA_STRUCTURE_MARKERS = (
    "bst",
    "binary search tree",
    "tree",
    "heap",
    "stack",
    "queue",
    "linked list",
    "hash table",
    "graph",
)

ALGORITHM_MARKERS = (
    "algorithm",
    "bfs",
    "dfs",
    "dijkstra",
    "prim",
    "kruskal",
    "quick sort",
    "quicksort",
    "merge sort",
    "binary search",
    "traversal",
)


def classify_topic_course_type(
    user_goal: str | None,
    topic_title: str,
    topic_purpose: str | None = None,
    source_summary: str | None = None,
    previous_topics: list[str] | None = None,
    user_knowledge_context: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
    text = build_classification_text(
        user_goal=user_goal,
        topic_title=topic_title,
        topic_purpose=topic_purpose,
        source_summary=source_summary,
        user_knowledge_context=user_knowledge_context,
    )

    primary, keyword_matched = choose_primary_course_type(text)

    if not keyword_matched:
        try:
            llm_result = generate_course_type_classification(
                system_prompt=CLASSIFIER_SYSTEM_PROMPT,
                user_prompt=build_course_type_classifier_prompt(
                    user_goal=user_goal,
                    topic_title=topic_title,
                    topic_purpose=topic_purpose,
                    source_summary=source_summary,
                    previous_topics=previous_topics,
                    user_knowledge_context=(
                        " ".join(str(v) for v in user_knowledge_context.values())
                        if isinstance(user_knowledge_context, dict)
                        else str(user_knowledge_context or "")
                    ),
                ),
            )
            return _normalize_llm_classification(
                llm_result=llm_result,
                user_goal=user_goal,
                topic_title=topic_title,
            )
        except Exception:
            pass

    secondary = choose_secondary_course_types(primary, text)
    knowledge_level = estimate_knowledge_level(
        user_goal=user_goal or topic_purpose or topic_title,
        topic_title=topic_title,
    )

    return {
        "topic_type": primary.value,
        "primary_course_type": primary.value,
        "secondary_course_types": [course_type.value for course_type in secondary],
        "knowledge_level": knowledge_level,
        "reason": build_reason(primary, secondary, text),
    }


def enrich_topic_with_course_type(
    topic_data: dict[str, Any],
    user_goal: str | None = None,
    previous_topics: list[str] | None = None,
    source_summary: str | None = None,
) -> dict[str, Any]:
    classification = classify_topic_course_type(
        user_goal=user_goal,
        topic_title=str(topic_data.get("title") or ""),
        topic_purpose=topic_data.get("purpose"),
        source_summary=source_summary or topic_data.get("source_refs"),
        previous_topics=previous_topics,
    )

    enriched = dict(topic_data)
    if not enriched.get("topic_type"):
        enriched["topic_type"] = classification["topic_type"]
    if not enriched.get("course_type"):
        enriched["course_type"] = enriched["topic_type"]
    secondary_course_types = (
        enriched.get("secondary_course_types")
        if isinstance(enriched.get("secondary_course_types"), list)
        else []
    )
    for secondary_type in classification["secondary_course_types"]:
        if (
            secondary_type != enriched["course_type"]
            and secondary_type not in secondary_course_types
        ):
            secondary_course_types.append(secondary_type)
    enriched["secondary_course_types"] = secondary_course_types
    if not enriched.get("knowledge_level"):
        enriched["knowledge_level"] = classification["knowledge_level"]
    if not enriched.get("topic_type_reason"):
        enriched["topic_type_reason"] = classification["reason"]
    if not enriched.get("course_type_reason"):
        enriched["course_type_reason"] = classification["reason"]
    return enriched


def _normalize_llm_classification(
    llm_result: dict[str, Any],
    user_goal: str | None,
    topic_title: str,
) -> dict[str, Any]:
    valid_course_types = {ct.value for ct in CourseType}
    legacy_topic_type_map = {
        "math_proof_reasoning": CourseType.MATH_FORMULA_METHOD.value,
        "compare_decide": CourseType.COMPARE_DISTINGUISH.value,
        "review_refresh": CourseType.PROBLEM_SOLVING_APPLICATION.value,
        "problem_solving_pattern": CourseType.PROBLEM_SOLVING_APPLICATION.value,
        "system_workflow_debugging": CourseType.PROCESS_WALKTHROUGH.value,
        "system_architecture": CourseType.PROCESS_WALKTHROUGH.value,
        "debugging_diagnosis": CourseType.PROCESS_WALKTHROUGH.value,
        "tool_workflow": CourseType.PROCESS_WALKTHROUGH.value,
        "design_decision": CourseType.COMPARE_DISTINGUISH.value,
        "application_historical": CourseType.PROBLEM_SOLVING_APPLICATION.value,
        "case_study_application": CourseType.PROBLEM_SOLVING_APPLICATION.value,
        "historical_development": CourseType.PROBLEM_SOLVING_APPLICATION.value,
        "process_lifecycle": CourseType.PROCESS_WALKTHROUGH.value,
        "terminology_vocabulary": CourseType.TERMINOLOGY_COMPONENTS.value,
        "exam_interview_prep": CourseType.PROBLEM_SOLVING_APPLICATION.value,
    }

    raw_primary = str(
        llm_result.get("topic_type") or llm_result.get("primary_course_type") or ""
    ).strip()
    raw_primary = legacy_topic_type_map.get(raw_primary, raw_primary)
    primary = raw_primary if raw_primary in valid_course_types else CourseType.CONCEPT_INTUITION.value

    raw_secondary = (
        llm_result.get("secondary_topic_types")
        or llm_result.get("secondary_course_types")
        or []
    )
    secondary = [
        ct for ct in (
            legacy_topic_type_map.get(str(item).strip(), str(item).strip())
            for item in raw_secondary
            if item
        )
        if ct in valid_course_types and ct != primary
    ]
    text = f"{user_goal or ''} {topic_title or ''}".lower()
    raw_level = llm_result.get("knowledge_level")
    try:
        knowledge_level = int(raw_level) if raw_level is not None else None
    except (TypeError, ValueError):
        knowledge_level = None

    if knowledge_level is None:
        from app.services.knowledge_level_service import estimate_knowledge_level
        knowledge_level = estimate_knowledge_level(
            user_goal=user_goal or topic_title,
            topic_title=topic_title,
        )

    return {
        "topic_type": primary,
        "primary_course_type": primary,
        "secondary_course_types": secondary,
        "knowledge_level": knowledge_level,
        "reason": str(llm_result.get("reason") or "Classified via LLM fallback."),
    }


def build_classification_text(
    user_goal: str | None,
    topic_title: str,
    topic_purpose: str | None,
    source_summary: str | None,
    user_knowledge_context: dict[str, Any] | str | None,
) -> str:
    context = ""
    if isinstance(user_knowledge_context, dict):
        context = " ".join(str(value) for value in user_knowledge_context.values())
    elif user_knowledge_context:
        context = str(user_knowledge_context)

    return " ".join(
        part.lower()
        for part in [
            user_goal or "",
            topic_title or "",
            topic_purpose or "",
            source_summary or "",
            context,
        ]
        if part
    )


def choose_primary_course_type(text: str) -> tuple[CourseType, bool]:
    opts_out_of_coding = any(marker in text for marker in NO_CODING_MARKERS)

    if any(marker in text for marker in ("prove", "proof", "justify", "why true")):
        return CourseType.PROOF_REASONING, True

    if is_bst_concept_intent(text):
        return CourseType.CONCEPT_INTUITION, True

    if is_bst_traversal_intent(text):
        if (
            any(marker in text for marker in CODING_SECONDARY_MARKERS)
            and not opts_out_of_coding
        ):
            return CourseType.CODING_IMPLEMENTATION, True
        return CourseType.ALGORITHM_WALKTHROUGH, True

    for course_type, keywords in COURSE_TYPE_KEYWORDS:
        if course_type == CourseType.CODING_IMPLEMENTATION and opts_out_of_coding:
            continue
        if any(keyword in text for keyword in keywords):
            return course_type, True

    return CourseType.CONCEPT_INTUITION, False


def choose_secondary_course_types(
    primary: CourseType,
    text: str,
) -> list[CourseType]:
    secondary: list[CourseType] = []

    wants_coding = any(marker in text for marker in CODING_SECONDARY_MARKERS)
    opts_out_of_coding = any(marker in text for marker in NO_CODING_MARKERS)
    has_data_structure = any(marker in text for marker in DATA_STRUCTURE_MARKERS)

    if primary == CourseType.CONCEPT_INTUITION and any(
        marker in text for marker in ("formula", "theorem", "calculate", "method")
    ):
        secondary.append(CourseType.MATH_FORMULA_METHOD)

    if primary == CourseType.COMPARE_DISTINGUISH and any(
        marker in text for marker in ("choose", "when to use", "tradeoff", "should i use")
    ):
        secondary.append(CourseType.PROBLEM_SOLVING_APPLICATION)

    if primary == CourseType.CODING_IMPLEMENTATION and any(
        marker in text for marker in ALGORITHM_MARKERS
    ):
        secondary.append(CourseType.ALGORITHM_WALKTHROUGH)

    if primary == CourseType.CODING_IMPLEMENTATION and has_data_structure:
        secondary.append(CourseType.DATA_STRUCTURE_OPERATION)

    # Use COMMON_COMBINATIONS as an additional signal: if the primary type has
    # known common pairings and the text hints at one of them, add it.
    for common_secondary in COMMON_COMBINATIONS.get(primary.value, []):
        try:
            secondary_type = CourseType(common_secondary)
        except ValueError:
            continue
        if secondary_type in secondary or secondary_type == primary:
            continue
        if secondary_type == CourseType.CODING_IMPLEMENTATION:
            continue
        # Only add if text shows some relevant signal for the secondary type
        secondary_keywords = next(
            (kws for ct, kws in COURSE_TYPE_KEYWORDS if ct == secondary_type),
            (),
        )
        if any(kw in text for kw in secondary_keywords):
            secondary.append(secondary_type)

    return dedupe_course_types(secondary, exclude=primary)


def is_bst_traversal_intent(text: str) -> bool:
    traversal_markers = (
        "bst traversal",
        "bst traversals",
        "binary search tree traversal",
        "binary search tree traversals",
        "inorder traversal",
        "preorder traversal",
        "postorder traversal",
        "level-order traversal",
        "level order traversal",
    )
    return any(marker in text for marker in traversal_markers) or (
        "bst" in text and "traversal" in text
    )


def is_bst_concept_intent(text: str) -> bool:
    has_bst = "bst" in text or "binary search tree" in text
    asks_concept = any(marker in text for marker in ("what is", "what's", "understand", "intuition"))
    operation_markers = (
        "insert",
        "insertion",
        "delete",
        "deletion",
        "traversal",
        "traverse",
        "implement",
        "code",
        "write function",
    )
    return has_bst and asks_concept and not any(marker in text for marker in operation_markers)


def dedupe_course_types(
    course_types: list[CourseType],
    exclude: CourseType | None = None,
) -> list[CourseType]:
    seen: set[CourseType] = set()
    result: list[CourseType] = []
    for course_type in course_types:
        if course_type == exclude or course_type in seen:
            continue
        seen.add(course_type)
        result.append(course_type)
    return result


def build_reason(
    primary: CourseType,
    secondary: list[CourseType],
    text: str,
) -> str:
    secondary_text = (
        f" Secondary course types: {', '.join(course_type.value for course_type in secondary)}."
        if secondary
        else ""
    )
    return (
        f"Classified as {primary.value} because the topic wording and goal match "
        f"that learning intent.{secondary_text}"
    )
