from dataclasses import dataclass, field
from typing import Any


KnowledgeLevel = int


LEVEL_LABELS: dict[KnowledgeLevel, str] = {
    1: "I have no knowledge",
    2: "I recognize the terms",
    3: "I understand the basics",
    4: "I can solve standard problems",
    5: "I need review or edge cases",
}


STARTING_MODE_TO_LEVEL: dict[str, KnowledgeLevel] = {
    "full_teach": 1,
    "compressed_refresher": 2,
    "nuance_first": 3,
    "edge_cases": 5,
    "transfer_practice": 4,
}


ESTIMATED_STATE_TO_LEVEL: dict[str, KnowledgeLevel] = {
    "unknown": 1,
    "familiar": 2,
    "fragile": 3,
    "stable": 4,
    "transferable": 4,
}


SELF_REPORT_TO_LEVEL: dict[int, KnowledgeLevel] = {
    0: 1,
    1: 2,
    2: 3,
    3: 4,
    4: 4,
    5: 5,
}


@dataclass(frozen=True)
class KnowledgeLevelResult:
    level: KnowledgeLevel
    label: str
    source: str
    confidence: float = 0.5
    reasons: list[str] = field(default_factory=list)


def clamp_knowledge_level(level: int | None) -> KnowledgeLevel:
    if level is None:
        return 1
    return max(1, min(5, int(level)))


def normalize_signal(value: Any) -> str:
    return str(value or "").strip().lower()


def starting_mode_to_knowledge_level(starting_mode: str | None) -> KnowledgeLevel | None:
    mode = normalize_signal(starting_mode)
    return STARTING_MODE_TO_LEVEL.get(mode)


def estimated_state_to_knowledge_level(estimated_state: str | None) -> KnowledgeLevel | None:
    state = normalize_signal(estimated_state)
    return ESTIMATED_STATE_TO_LEVEL.get(state)


def self_report_to_knowledge_level(self_report: int | str | None) -> KnowledgeLevel | None:
    if self_report is None or self_report == "":
        return None

    if isinstance(self_report, str) and not self_report.isdigit():
        text = normalize_signal(self_report)
        if any(phrase in text for phrase in ["no knowledge", "from scratch", "new"]):
            return 1
        if any(phrase in text for phrase in ["recognize", "heard", "terms"]):
            return 2
        if any(phrase in text for phrase in ["basics", "basic", "some understanding"]):
            return 3
        if any(phrase in text for phrase in ["standard problems", "solve", "comfortable"]):
            return 4
        if any(phrase in text for phrase in ["review", "edge case", "refresh"]):
            return 5
        return None

    try:
        return SELF_REPORT_TO_LEVEL.get(int(self_report))
    except (TypeError, ValueError):
        return None


def infer_goal_knowledge_level(user_goal: str | None) -> KnowledgeLevel | None:
    goal = normalize_signal(user_goal)
    if not goal:
        return None

    level_5_markers = [
        "review",
        "refresh",
        "edge case",
        "edge cases",
        "tricky cases",
        "common mistakes",
        "exam prep",
        "interview prep",
    ]
    level_4_markers = [
        "hard problems",
        "advanced",
        "transfer",
        "variations",
        "standard problems",
        "i can solve",
    ]
    level_3_markers = [
        "basics",
        "i know the basics",
        "understand the basics",
        "somewhat",
    ]
    level_2_markers = [
        "recognize",
        "heard of",
        "heard the term",
        "terms",
        "familiar with the words",
    ]
    level_1_markers = [
        "no knowledge",
        "from scratch",
        "brand new",
        "beginner",
        "teach me",
        "learn",
    ]

    marker_groups = [
        (5, level_5_markers),
        (4, level_4_markers),
        (3, level_3_markers),
        (2, level_2_markers),
        (1, level_1_markers),
    ]

    for level, markers in marker_groups:
        if any(marker in goal for marker in markers):
            return level

    return None


def estimate_level_from_attempts(prior_attempts: list[dict[str, Any]] | None) -> KnowledgeLevel | None:
    attempts = prior_attempts or []
    if not attempts:
        return None

    recent = attempts[-8:]
    levels: list[str] = [
        normalize_signal(attempt.get("performance_level"))
        for attempt in recent
        if attempt.get("performance_level")
    ]

    if not levels:
        return None

    strong_count = levels.count("strong")
    weak_count = levels.count("weak")
    fragile_count = levels.count("fragile")
    minor_count = levels.count("minor_mistake")
    hint_count = sum(1 for attempt in recent if attempt.get("hint_used"))

    if weak_count >= 2:
        return 2
    if weak_count == 1 or fragile_count >= 2 or hint_count >= 2:
        return 3
    if strong_count >= 3 and fragile_count == 0 and minor_count == 0:
        return 4
    if strong_count >= 2 and minor_count <= 1:
        return 3

    return 3


def estimate_knowledge_level(
    explicit_knowledge_level: int | None = None,
    user_goal: str | None = None,
    topic_title: str | None = None,
    prior_attempts: list[dict[str, Any]] | None = None,
    qna_history: list[dict[str, Any]] | None = None,
    self_report: int | str | None = None,
    starting_mode: str | None = None,
    estimated_state: str | None = None,
    fragile_concepts: list[str] | None = None,
    review_concepts: list[str] | None = None,
    stable_concepts: list[str] | None = None,
    transferable_concepts: list[str] | None = None,
    concepts_to_skip: list[str] | None = None,
    concepts_to_briefly_repair: list[str] | None = None,
) -> KnowledgeLevel:
    return estimate_knowledge_level_result(
        explicit_knowledge_level=explicit_knowledge_level,
        user_goal=user_goal,
        topic_title=topic_title,
        prior_attempts=prior_attempts,
        qna_history=qna_history,
        self_report=self_report,
        starting_mode=starting_mode,
        estimated_state=estimated_state,
        fragile_concepts=fragile_concepts,
        review_concepts=review_concepts,
        stable_concepts=stable_concepts,
        transferable_concepts=transferable_concepts,
        concepts_to_skip=concepts_to_skip,
        concepts_to_briefly_repair=concepts_to_briefly_repair,
    ).level


def estimate_knowledge_level_result(
    explicit_knowledge_level: int | None = None,
    user_goal: str | None = None,
    topic_title: str | None = None,
    prior_attempts: list[dict[str, Any]] | None = None,
    qna_history: list[dict[str, Any]] | None = None,
    self_report: int | str | None = None,
    starting_mode: str | None = None,
    estimated_state: str | None = None,
    fragile_concepts: list[str] | None = None,
    review_concepts: list[str] | None = None,
    stable_concepts: list[str] | None = None,
    transferable_concepts: list[str] | None = None,
    concepts_to_skip: list[str] | None = None,
    concepts_to_briefly_repair: list[str] | None = None,
) -> KnowledgeLevelResult:
    reasons: list[str] = []
    fragile_concepts = fragile_concepts or []
    review_concepts = review_concepts or []
    stable_concepts = stable_concepts or []
    transferable_concepts = transferable_concepts or []
    concepts_to_skip = concepts_to_skip or []
    concepts_to_briefly_repair = concepts_to_briefly_repair or []
    qna_history = qna_history or []

    if explicit_knowledge_level is not None:
        level = clamp_knowledge_level(explicit_knowledge_level)
        reasons.append(f"Explicit Azalea knowledge level set to Level {level}.")
        return build_result(level, "explicit_knowledge_level", 0.95, reasons)

    explicit_level = self_report_to_knowledge_level(self_report)
    if explicit_level is not None:
        reasons.append(f"Self-report mapped to Level {explicit_level}.")
        return build_result(explicit_level, "self_report", 0.9, reasons)

    mode_level = starting_mode_to_knowledge_level(starting_mode)
    if mode_level is not None:
        reasons.append(f"Starting mode '{starting_mode}' mapped to Level {mode_level}.")
    state_level = estimated_state_to_knowledge_level(estimated_state)
    if state_level is not None:
        reasons.append(f"Estimated state '{estimated_state}' mapped to Level {state_level}.")
    attempt_level = estimate_level_from_attempts(prior_attempts)
    if attempt_level is not None:
        reasons.append(f"Recent practice attempts mapped to Level {attempt_level}.")
    goal_level = infer_goal_knowledge_level(user_goal or topic_title)
    if goal_level is not None:
        reasons.append(f"Goal wording mapped to Level {goal_level}.")

    candidates = [
        ("starting_mode", mode_level, 0.72),
        ("estimated_state", state_level, 0.7),
        ("practice_history", attempt_level, 0.78),
        ("goal", goal_level, 0.55),
    ]
    candidates = [(source, level, confidence) for source, level, confidence in candidates if level]

    if candidates:
        weighted_sum = sum(level * confidence for _, level, confidence in candidates)
        weight_total = sum(confidence for _, _, confidence in candidates)
        level = clamp_knowledge_level(round(weighted_sum / weight_total))
        source = "+".join(source for source, _, _ in candidates)
        confidence = min(0.85, max(confidence for _, _, confidence in candidates))
    else:
        level = 1
        source = "default"
        confidence = 0.35
        reasons.append("No learner signal was provided, so Azalea starts from Level 1.")

    if review_concepts or normalize_signal(starting_mode) == "edge_cases":
        level = max(level, 5)
        reasons.append("Review or edge-case mode moves the lesson to Level 5.")
    elif transferable_concepts:
        level = max(level, 4)
        reasons.append("Transferable prior concepts support Level 4 treatment.")
    elif stable_concepts or concepts_to_skip:
        level = max(level, 3)
        reasons.append("Stable known concepts allow basics to be compressed.")

    if fragile_concepts or concepts_to_briefly_repair:
        level = min(level, 3)
        reasons.append("Fragile concepts keep the lesson from skipping repair.")

    if qna_history and any(normalize_signal(item.get("confusion")) for item in qna_history):
        level = min(level, 3)
        reasons.append("Recent Q&A confusion keeps the lesson in repair/application mode.")

    return build_result(level, source, confidence, reasons)


def build_result(
    level: int,
    source: str,
    confidence: float,
    reasons: list[str],
) -> KnowledgeLevelResult:
    clamped = clamp_knowledge_level(level)
    return KnowledgeLevelResult(
        level=clamped,
        label=LEVEL_LABELS[clamped],
        source=source,
        confidence=confidence,
        reasons=reasons,
    )


def knowledge_level_to_generation_guidance(level: int | None) -> str:
    level = clamp_knowledge_level(level)

    guidance = {
        1: """
Knowledge Level 1: I have no knowledge.
Use the full course-type blueprint. Include context, definition, components, how it works, comprehensive examples, more microchecks, prerequisite popups, and guided practice before harder practice.
""",
        2: """
Knowledge Level 2: I recognize the terms.
Compress broad context, keep precise definitions and core components, bridge recognition into usable understanding, include misconception checks, and use examples that force correct use of the term.
""",
        3: """
Knowledge Level 3: I understand the basics.
Skip obvious basics, keep important precision, focus on edge cases, non-obvious steps, misconceptions, and application. Use harder examples and fewer but sharper microchecks.
""",
        4: """
Knowledge Level 4: I can solve standard problems.
Skip basic context and definitions unless precision matters. Prioritize hard variations, transfer, invalid solutions, debugging, tradeoffs, complexity, and nuanced practice.
""",
        5: """
Knowledge Level 5: I need review or edge cases.
Use review/edge-case treatment. Start with compressed recall or high-yield rule, focus on traps, weak-area repair, hard examples, and targeted practice. Do not fully reteach unless the user shows weakness.
""",
    }

    return (
        guidance[level].strip()
        + "\n\nScope rule: Knowledge level changes depth, pacing, scaffolding, examples, and practice difficulty. It does not change the topic scope. Compress or skip prerequisites when appropriate, but fully explain the new idea this card is responsible for."
    )
