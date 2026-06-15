"""
Lean lesson generator (LEGACY — deprecated).

The "v2" in the original name refers to the previous lean schema generation,
not the new Visual System V2 pipeline. Slated for removal in Phase 8 once
the new pipeline at app/services/lean_lesson_generator_v2.py becomes the
default. Removal blocked on: see PHASE_8_DECOMMISSION.md (project root).

While deprecated, this module continues to power the default
`?use_v2=false` path of POST /study-paths/{id}/generate-initial. Do not
add new features here — add them to the v2 generator instead.

Generates lessons with a compact schema and prompt.
No validation retries. Visuals use lightweight visual_type + visual_description.
Converts lean JSON to the legacy lesson_json format the frontend expects.
"""
from __future__ import annotations

import ast
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Any

from app.core.topic_assumptions import normalize_assumption_phrase
from app.prompts.lean_lesson_prompt import LEAN_SYSTEM_PROMPT, build_lean_user_prompt
from app.services.assumption_ledger_service import build_assumption_ledger
from app.services.llm_client import generate_lean_structured_lesson
from app.services.lesson_generator import (
    build_source_chunk_ids,
    build_source_summary,
    build_lesson_source_metadata,
)

if TYPE_CHECKING:
    from app.models.content_chunk import ContentChunk
    from app.models.topic import Topic

logger = logging.getLogger(__name__)

# Lean card types → existing frontend card types
_LEAN_TYPE_MAP: dict[str, str] = {
    "background": "purpose_context",
    "components_terms": "definition",
    "core_idea": "core_idea",
    "process": "method_process",
    "worked_example": "worked_example",
    "comparison": "comparison",
    "common_mistake": "common_mistake",
    "edge_case": "edge_case",
    "code_walkthrough": "worked_example",
    "formula_breakdown": "formula",
    "proof_plan": "method_process",
    "practice": "quick_practice",
    "takeaway": "summary",
}

_EMPTY_VISUAL_PLAN: dict[str, Any] = {
    "type": "",
    "title": "",
    "purpose": "",
    "code": "",
    "language": "",
    "columns": [],
    "rows": [],
    "highlight_row": -1,
}

_EMPTY_MICRO_CHECK: dict[str, str] = {"type": "", "prompt": "", "answer": ""}

_VISUAL_TYPE_ALIASES: dict[str, str] = {
    "comparison_table": "comparison_table",
    "state_change": "state_change",
    "spatial": "spatial_diagram",
    "interactive": "interactive_parameter",
    "code_block": "code_trace",
    "node_link": "node_link_diagram",
    "concept_map_diagram": "concept_map",
    "array_state": "array_state_diagram",
    "step_flow_diagram": "step_flow",
}

_CLAUSE_SPLIT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\s+because\s+", re.IGNORECASE), "because"),
    (re.compile(r"\s+so\s+", re.IGNORECASE), "so"),
    (re.compile(r"\s+which\s+", re.IGNORECASE), "which"),
    (re.compile(r"\s+when\s+", re.IGNORECASE), "when"),
)


def _normalize_example_plan(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        value = {}

    return {
        "core_mechanism_example": str(
            value.get("core_mechanism_example") or ""
        ).strip(),
        "structural_variation_example": str(
            value.get("structural_variation_example") or ""
        ).strip(),
        "edge_case_examples": _string_list(value.get("edge_case_examples")),
        "misconception_example": str(value.get("misconception_example") or "").strip(),
        "transfer_example": str(value.get("transfer_example") or "").strip(),
        "coverage_dimensions": _string_list(value.get("coverage_dimensions")),
        "excluded_edge_cases_with_reason": _string_list(
            value.get("excluded_edge_cases_with_reason")
        ),
    }


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    return [str(item).strip() for item in value if str(item).strip()]


def _code_snippet_or_point_code(card: dict[str, Any]) -> str:
    snippet = str(card.get("code_snippet") or "").strip()
    if snippet:
        return snippet
    return _extract_code_snippet_from_points(
        [str(point).rstrip() for point in (card.get("points") or []) if str(point).strip()]
    )


def _normalize_bullet_shape(points: list[str]) -> list[str]:
    """Convert compressed bullets into frame + subpoint shape where safe."""
    normalized: list[str] = []

    for raw_point in points:
        raw_text = str(raw_point or "").rstrip()
        point = raw_text.strip()
        if not point:
            continue
        if raw_text.lstrip().startswith("- "):
            leading_spaces = len(raw_text) - len(raw_text.lstrip(" "))
            sublevel = max(1, leading_spaces // 2)
            normalized.append(f"{'  ' * sublevel}- {raw_text.lstrip()[2:].strip()}")
            continue

        expanded = _expand_main_point(point)
        normalized.extend(expanded)

    return normalized


def _expand_main_point(point: str) -> list[str]:
    math_expanded = _expand_math_point(point)
    if math_expanded is not None:
        return math_expanded

    colon_expanded = _expand_colon_point(point)
    if colon_expanded is not None:
        return colon_expanded

    clause_expanded = _expand_clause_point(point)
    if clause_expanded is not None:
        return clause_expanded

    return [point]


def _expand_math_point(point: str) -> list[str] | None:
    """Move an equation embedded in prose into a subpoint."""
    text = point.strip()
    if not text:
        return None

    match = re.search(
        r"(\\\[[\s\S]+?\\\]|\\\([\s\S]+?\\\)|\$\$[\s\S]+?\$\$)",
        text,
    )
    if match is None:
        match = re.search(
            r"(\\int(?:_\{[^{}]+\}|\s*_[A-Za-z0-9+\-]+)?(?:\^\{[^{}]+\}|\s*\^[A-Za-z0-9+\-]+)?\s+[^.;]+|∫\s*[^.;]+)",
            text,
        )
    if match is None:
        return None

    equation = match.group(1).strip()
    before = text[:match.start()].strip(" ,;:")
    after = text[match.end():].strip(" ,;:.")
    prose = " ".join(part for part in (before, after) if part).strip()

    if not prose or len(prose.split()) < 3:
        return None

    prose = prose.rstrip(".")
    if not prose.endswith(":"):
        prose = f"{prose}:"

    return [prose, f"  - {equation}"]


def _expand_colon_point(point: str) -> list[str] | None:
    if ": " not in point:
        return None

    frame, detail = point.split(": ", 1)
    frame = frame.strip()
    detail = detail.strip()
    if not frame or not detail:
        return None
    if len(detail) < 12:
        return None

    subpoints = _split_detail_units(detail)
    if not subpoints:
        return None

    return [frame.rstrip(":")] + [
        f"  - {_clean_subpoint_text(item)}"
        for item in subpoints
    ]


def _expand_clause_point(point: str) -> list[str] | None:
    if len(point) < 90 and not any(marker in point.lower() for marker in (" because ", " so ", " which ", " when ")):
        return None

    for pattern, marker in _CLAUSE_SPLIT_PATTERNS:
        parts = pattern.split(point, maxsplit=1)
        if len(parts) != 2:
            continue

        frame, detail = (part.strip() for part in parts)
        if not frame or not detail or len(detail) < 18:
            continue

        frame = frame.rstrip(".")
        detail = detail.rstrip(".")
        if marker == "because":
            detail = f"because {detail}"
        elif marker == "so":
            detail = f"so {detail}"
        elif marker == "which":
            detail = f"which {detail}"
        elif marker == "when":
            detail = f"when {detail}"

        return [frame.rstrip(":")] + [
            f"  - {_clean_subpoint_text(item)}"
            for item in _split_detail_units(detail)
        ]

    return None


def _has_bracketed_commas(text: str) -> bool:
    """True if any comma sits INSIDE [], {}, or () — i.e. it's part of a collection
    (an array/set/dict/tuple), not a separator between list items. Splitting on those
    commas shreds `[38, 27, 43]` into `[38` / `27` / `43]`."""
    depth = 0
    for ch in text:
        if ch in "[{(":
            depth += 1
        elif ch in "]})":
            depth = max(0, depth - 1)
        elif ch == "," and depth > 0:
            return True
    return False


def _split_detail_units(detail: str) -> list[str]:
    text = detail.strip().rstrip(".")
    if not text:
        return []
    # Never break apart a collection literal — its internal commas are not item separators.
    if _has_bracketed_commas(text):
        return [text]

    ordered_parts = re.split(
        r",\s*(?=(?:first|second|third|next|then|finally),\s+)",
        text,
        flags=re.IGNORECASE,
    )
    if len(ordered_parts) > 1:
        return [part.strip() for part in ordered_parts if part.strip()]

    if re.search(r",\s*(then|and finally|finally)\s+", text, re.IGNORECASE):
        first_split = re.split(r",\s*(?=then|and finally|finally)", text, flags=re.IGNORECASE)
        return [part.strip() for part in first_split if part.strip()]

    if ";" in text:
        return [part.strip() for part in text.split(";") if part.strip()]

    and_parts = [part.strip() for part in re.split(r"\s+and\s+", text, maxsplit=1, flags=re.IGNORECASE)]
    if len(and_parts) == 2 and len(text) > 70 and all(len(part) >= 20 for part in and_parts):
        return and_parts

    comma_parts = [part.strip() for part in text.split(",") if part.strip()]
    if 2 <= len(comma_parts) <= 4 and all(len(part.split()) <= 8 for part in comma_parts):
        return comma_parts

    return [text]


_CONTINUATION_WORDS = frozenset({
    # Subordinating conjunctions / prepositions that almost always continue
    # a thought from the previous bullet rather than start a new idea.
    "to", "by", "in", "on", "at", "for", "with", "of", "from", "into", "onto",
    "as", "than", "via", "per", "without",
    # Coordinating fragments and continuations
    "and", "or", "but", "yet", "nor", "so",
    # Subordinators
    "because", "since", "while", "when", "where", "whereas", "whenever",
    "until", "unless", "though", "although", "before", "after", "if",
    "that", "which", "who", "whom", "whose",
    # Adverbial continuations
    "then", "thus", "therefore", "thereby", "hence", "also", "additionally",
    "however", "moreover", "furthermore", "meanwhile",
})


def _is_fragment_continuation(text: str) -> bool:
    """A sub-bullet text reads as a continuation of the previous one when it
    starts lowercase with a conjunction/preposition, lacks a verb at the
    start, or is just a short trailing clause."""
    stripped = text.strip()
    if not stripped:
        return True
    first_char = stripped[0]
    if not first_char.isalpha():
        return False
    # Allow code-like sub-bullets (e.g. "low=0", "i++") — they start lowercase
    # but contain operators/equals that mark them as self-contained.
    if re.search(r"[=<>+\-*/(){}\[\]]", stripped) and len(stripped.split()) <= 4:
        return False
    if not first_char.islower():
        return False
    first_word = re.split(r"[\s,;:.]", stripped, maxsplit=1)[0].lower()
    return first_word in _CONTINUATION_WORDS


_CALL_STACK_VARIABLE_PATTERN = re.compile(
    # Matches: call_stack=[...], call_stack: [...], call stack=[...]
    # (case-insensitive). The body inside [...] is captured for the rewrite.
    r"\bcall[\s_-]?stack\s*[=:]\s*(\[[^\]]*\])",
    re.IGNORECASE,
)


def _rewrite_call_stack_syntax(points: list[str]) -> list[str]:
    """Rewrite misleading variable-assignment syntax for the call stack.

    The LLM sometimes writes `call_stack=[40, 30]` in worked-example bullets
    for recursive implementations, which reads like a user-defined Python
    variable — but in recursive code there is no such variable; the call
    stack is the interpreter's implicit frame stack. Title-cased plain
    English ("Call stack: [40 → 30]") communicates that without misleading
    the learner into searching for a `call_stack` variable in the source.

    We only rewrite when the bullet uses `call_stack` / `callstack` /
    `call-stack` / `call stack` followed by `=` or `:`. The real user
    variable in iterative impls is plain `stack=[...]` and is NOT touched.
    """
    if not points:
        return points
    result: list[str] = []
    for point in points:
        # Replace `call_stack=[...]` with `Call stack: [...]`
        rewritten = _CALL_STACK_VARIABLE_PATTERN.sub(
            lambda m: f"Call stack: {m.group(1)}",
            str(point),
        )
        result.append(rewritten)
    return result


def _sentence_case_bullet_starts(points: list[str]) -> list[str]:
    """Capitalize prose bullet starts while preserving code/variable meaning.

    A bullet like `current=30` or `queue = [A]` must stay lowercase because
    capitalization would change the variable name. Plain prose like
    `the queue starts empty` should render as `The queue starts empty`.
    """
    result: list[str] = []
    for raw in points:
        point = str(raw or "")
        match = re.match(r"^(\s*-\s+)?(.*)$", point)
        if not match:
            result.append(point)
            continue
        prefix = match.group(1) or ""
        body = match.group(2)
        result.append(f"{prefix}{_sentence_case_text_start(body)}")
    return result


def _sentence_case_text_start(text: str) -> str:
    value = str(text or "")
    leading = re.match(r"^(\s*)(.*)$", value)
    if not leading:
        return value
    whitespace, body = leading.group(1), leading.group(2)
    if not body:
        return value
    if _should_preserve_bullet_start_case(body):
        return value
    for index, char in enumerate(body):
        if char.isalpha():
            return f"{whitespace}{body[:index]}{char.upper()}{body[index + 1:]}"
        if not char.isspace() and char not in {'"', "'", "(", "[", "{", "`"}:
            return value
    return value


def _should_preserve_bullet_start_case(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if stripped.startswith(("`", "$", "\\(", "\\[", "{", "[", "(")):
        return True
    if _looks_like_code_line(stripped.strip("`")):
        return True
    if re.match(r"^[a-z_][A-Za-z0-9_]*(?:\[[^\]]+\])?\s*(?:=|:)\s*", stripped):
        return True
    first_word = re.split(r"[\s,;:.=()[\]{}]", stripped, maxsplit=1)[0]
    if "_" in first_word:
        return True
    return False


def _merge_bullet_fragments(points: list[str]) -> list[str]:
    """Merge sub-bullets that are sentence fragments back into the previous
    bullet so each rendered bullet is a complete clause/idea.

    Trigger: a sub-bullet (leading whitespace + dash) whose visible text
    starts with lowercase AND a known continuation word."""
    if not points:
        return points
    merged: list[str] = []
    for raw in points:
        point = str(raw)
        sub_match = re.match(r"^(\s+-\s+)(.*)$", point)
        if not sub_match or not merged:
            merged.append(point)
            continue
        prefix, body = sub_match.group(1), sub_match.group(2)
        if not _is_fragment_continuation(body):
            merged.append(point)
            continue
        # Merge body into the previous bullet.
        prev = merged[-1].rstrip(".,;:")
        # Strip leading lowercase + connector if the connector is already
        # implied (avoid "blah, and, foo"). Keep "to/by/for/with" type words
        # since they're the joiner.
        merged[-1] = f"{prev} {body.strip()}"
    return merged


def _clean_subpoint_text(text: str) -> str:
    value = text.strip().rstrip(".")
    if not value:
        return value
    if len(value) >= 2 and value[:2].isupper():
        return value
    return value[:1].lower() + value[1:]


def _lean_card_to_legacy(
    lean_card: dict[str, Any],
    card_index: int,
    practice_questions: list[dict[str, Any]],
    topic_hint: str = "",
) -> dict[str, Any]:
    """Convert a single lean card to the LessonFlowCard shape the frontend expects."""
    raw_type = str(lean_card.get("card_type") or "concept")
    card_type = _LEAN_TYPE_MAP.get(raw_type, raw_type)
    blueprint_key = str(lean_card.get("blueprint_key") or raw_type).strip() or raw_type
    example_type = str(lean_card.get("example_type") or "none").strip() or "none"
    title = _normalize_card_title(
        value=lean_card.get("title"),
        blueprint_key=blueprint_key,
        card_index=card_index,
    )

    raw_points = [
        str(p).rstrip()
        for p in (lean_card.get("points") or [])
        if str(p).strip()
    ]
    points = _normalize_bullet_shape(raw_points)
    points = _merge_bullet_fragments(points)
    points = _rewrite_call_stack_syntax(points)
    points = _sentence_case_bullet_starts(points)

    # Build styled_elements for code snippet
    styled_elements: list[dict[str, Any]] = []
    code_snippet = str(lean_card.get("code_snippet") or "").strip()
    if blueprint_key == "code_walkthrough" and not code_snippet:
        code_snippet = _extract_code_snippet_from_points(points)
        if code_snippet:
            filtered_points = _remove_code_only_points(points)
            if filtered_points:
                points = filtered_points
    code_language = str(lean_card.get("code_language") or "python").strip() or "python"
    highlight_lines_per_step = _validated_highlight_lines_per_step(
        lean_card.get("highlight_lines_per_step"),
        code_snippet=code_snippet,
    )
    # Normalize the snippet's layout (helper indented into the class, two blank
    # lines between sibling functions) and remap highlight ranges to the new line
    # numbers. Deterministic, so worked-example cards keep identical snippets.
    if code_snippet and blueprint_key in ("code_walkthrough", "worked_example"):
        # Repair indentation first (a body line wrongly at column 0) so the AST-based
        # passes below can run, then fix missing main / broken recursion. These change
        # line numbers, so the LLM's highlights are cleared (recomputed downstream).
        _dedented = _fix_dedented_body_lines(code_snippet)
        if _dedented != code_snippet:
            code_snippet = _dedented
            highlight_lines_per_step = []
        _stripped = _strip_driver_code(code_snippet)
        if _stripped != code_snippet:
            code_snippet = _stripped
            highlight_lines_per_step = []
        # NOTE: the _synthesize_main_for_helper / _split_accumulator_recursion transforms are
        # RETIRED — they mutated the AST to "fix" code and instead corrupted valid algorithms
        # (e.g. merge sort shipped using left/right that were never assigned). Correctness is
        # now enforced by code_repair (validate parse + undefined names -> clean regeneration),
        # so we keep the LLM's own code and only do benign layout cleanup here.
        code_snippet, _layout_line_map = _fix_code_layout(code_snippet)
        highlight_lines_per_step = _remap_line_ranges(highlight_lines_per_step, _layout_line_map)
    if code_snippet:
        styled_elements.append({
            "type": "code_trace",
            "title": "",
            "data": {
                "code": code_snippet,
                "language": code_language,
            },
        })

    # example_text renders via card.example (shown in "Example" box below points)
    example_text = str(
        lean_card.get("example")
        or lean_card.get("example_text")
        or ""
    ).strip()
    explanation = str(lean_card.get("explanation") or "").strip()
    visual_description = str(lean_card.get("visual_description") or "").strip()
    visual_type = _normalize_visual_type(lean_card.get("visual_type"))
    if blueprint_key == "code_walkthrough" and code_snippet:
        visual_type = "code_trace"
    visual_plan = _build_visual_plan(
        visual_type=visual_type,
        title=title,
        purpose=str(lean_card.get("learning_job") or ""),
        blueprint_key=blueprint_key,
        topic_hint=topic_hint,
        visual_description=visual_description,
        visual_columns=lean_card.get("visual_columns") or [],
        visual_rows=lean_card.get("visual_rows") or [],
        visual_highlight_row=lean_card.get("visual_highlight_row"),
        visual_steps=lean_card.get("visual_steps") or [],
        visual_formula=lean_card.get("visual_formula"),
        visual_symbols=lean_card.get("visual_symbols") or [],
        visual_when_to_use=lean_card.get("visual_when_to_use"),
        visual_center=lean_card.get("visual_center"),
        visual_nodes=lean_card.get("visual_nodes") or [],
        visual_edges=lean_card.get("visual_edges") or [],
        visual_wrong=lean_card.get("visual_wrong"),
        visual_correct=lean_card.get("visual_correct"),
        visual_wrong_label=lean_card.get("visual_wrong_label"),
        visual_correct_label=lean_card.get("visual_correct_label"),
        visual_why=lean_card.get("visual_why"),
        visual_x_label=lean_card.get("visual_x_label"),
        visual_y_label=lean_card.get("visual_y_label"),
        visual_data_points=lean_card.get("visual_data_points") or [],
        visual_key_points=lean_card.get("visual_key_points") or [],
        visual_array_values=lean_card.get("visual_array_values") or [],
        visual_array_rows=lean_card.get("visual_array_rows") or [],
        visual_array_pointers=lean_card.get("visual_array_pointers") or [],
        visual_array_ranges=lean_card.get("visual_array_ranges") or [],
        visual_array_annotations=lean_card.get("visual_array_annotations") or [],
        points=points,
        code_snippet=code_snippet,
        code_language=code_language,
    )
    body: list[str] = [explanation] if explanation else []

    practice_question_index = -1
    if card_type == "quick_practice":
        q_text = str(lean_card.get("practice_question") or "").strip()
        q_answer = str(lean_card.get("practice_answer") or "").strip()
        choices = [str(c).strip() for c in (lean_card.get("practice_choices") or []) if str(c).strip()]

        if q_text:
            q_type = "multiple_choice" if len(choices) >= 2 else "short_answer"
            practice_question_index = len(practice_questions)
            practice_questions.append({
                "id": f"q-{card_index + 1}",
                "question_type": q_type,
                "question_text": q_text,
                "correct_answer": q_answer,
                "expected_answer": q_answer,
                "explanation": q_answer,
                "choices": choices,
                "options": choices,
                "skill_target": "",
                "concept_tested": "",
                "related_section": "",
                "why_this_matters": "",
                "difficulty": "standard",
                "given": [],
                "starter_code": "",
                "language": "",
                "test_cases": [],
                "visual_feedback_plan": {},
                "edge_cases_tested": [],
                "misconceptions_tested": [],
                "metadata": {},
                "rubric": {},
            })

    return {
        "id": str(lean_card.get("id") or f"card-{card_index + 1}"),
        "blueprint_key": blueprint_key,
        "card_type": card_type,
        "title": title,
        "points": points,
        "body": body,
        "bullets": [],
        "main_concept": str(lean_card.get("learning_job") or title or ""),
        "learning_goal": str(lean_card.get("learning_job") or ""),
        "example_type": example_type,
        "visual_type": visual_type,
        "new_concepts": [],
        "review_concepts": [],
        "prerequisite_concepts": [],
        "common_misconceptions": [],
        "concept_support": [],
        "interactive_links": [],
        "styled_elements": styled_elements,
        "visual_plan": visual_plan,
        "visual_description": visual_description,
        "visual_index": -1,
        "annotations": [],
        "example": example_text,
        "micro_check": _EMPTY_MICRO_CHECK.copy(),
        "what_to_notice": (lean_card.get("visual_focus") or {}).get("attention_note") or visual_description,
        "next_transition": "",
        "estimated_seconds": int(lean_card.get("estimated_seconds") or 45),
        "transition_text": "",
        "next_card_label": "Next",
        "practice_question_index": practice_question_index,
        "code_snippet": code_snippet,
        "code_language": code_language,
        "highlight_lines_per_step": highlight_lines_per_step,
        "continuation_group_id": str(lean_card.get("continuation_group_id") or ""),
        "continuation_index": int(lean_card.get("continuation_index") or 0),
        "continuation_total": int(lean_card.get("continuation_total") or 0),
        "continuation_reason": str(lean_card.get("continuation_reason") or ""),
        "continues_from_previous": bool(lean_card.get("continues_from_previous") or False),
        "visual_focus": lean_card.get("visual_focus"),
    }


def _count_main_points(lean_card: dict[str, Any]) -> int:
    normalized_points = _normalize_bullet_shape([
        str(point).rstrip()
        for point in (lean_card.get("points") or [])
        if str(point).strip()
    ])
    return sum(
        1
        for point in normalized_points
        if str(point).strip() and not str(point).lstrip().startswith("- ")
    )


def _is_components_terms_card(lean_card: dict[str, Any]) -> bool:
    return _lean_card_key(lean_card) == "components_terms"


def _group_main_point_blocks(points: list[str]) -> list[list[str]]:
    groups: list[list[str]] = []
    current_group: list[str] = []

    for point in points:
        is_subpoint = str(point).lstrip().startswith("- ")
        if not is_subpoint:
            if current_group:
                groups.append(current_group)
            current_group = [point]
            continue

        if current_group:
            current_group.append(point)
        else:
            current_group = [point]

    if current_group:
        groups.append(current_group)

    return groups


def _term_label(point: str) -> str:
    return re.sub(r"^\s*-\s*", "", point).strip().rstrip(":").strip()


def _is_forbidden_key_term(term: str, forbidden_terms: set[str]) -> bool:
    normalized = normalize_assumption_phrase(term)
    if not normalized:
        return True

    if normalized in forbidden_terms:
        return True

    words = normalized.split()
    for forbidden in forbidden_terms:
        if not forbidden:
            continue
        forbidden_words = forbidden.split()
        if normalized == forbidden:
            return True
        if len(forbidden_words) == 1 and forbidden in words:
            return True
        if len(forbidden_words) > 1 and (
            forbidden in normalized or normalized in forbidden
        ):
            return True

    return False


def _filter_assumed_components_terms(
    lean_card: dict[str, Any],
    forbidden_terms: set[str],
) -> dict[str, Any]:
    if not forbidden_terms or not _is_components_terms_card(lean_card):
        return lean_card

    normalized_points = _normalize_bullet_shape([
        str(point).rstrip()
        for point in (lean_card.get("points") or [])
        if str(point).strip()
    ])
    filtered_points: list[str] = []

    for group in _group_main_point_blocks(normalized_points):
        main = _term_label(group[0] if group else "")
        if _is_forbidden_key_term(main, forbidden_terms):
            continue
        filtered_points.extend(group)

    filtered_card = dict(lean_card)
    filtered_card["points"] = filtered_points
    return filtered_card


_EDGE_CASE_CLASSIFICATION_PATTERNS = (
    "edge case",
    "boundary case",
    "special case",
    "single node",
    "one node",
    "only root",
    "single element",
    "one element",
    "empty tree",
    "empty input",
    "empty structure",
    "null root",
    "null tree",
    "no children",
    "no child",
    "minimal tree",
    "minimal structure",
    "degenerate case",
)


def _looks_like_edge_case_card(lean_card: dict[str, Any]) -> bool:
    key = _lean_card_key(lean_card)
    card_type = str(lean_card.get("card_type") or "").strip()
    if key != "worked_example" and card_type != "worked_example":
        return False

    text = " ".join(
        [
            str(lean_card.get("title") or ""),
            str(lean_card.get("learning_job") or ""),
            str(lean_card.get("example") or ""),
            str(lean_card.get("example_text") or ""),
            " ".join(str(point or "") for point in (lean_card.get("points") or [])),
        ]
    )
    normalized = normalize_assumption_phrase(text)
    if not normalized:
        return False

    return any(pattern in normalized for pattern in _EDGE_CASE_CLASSIFICATION_PATTERNS)


def _normalize_lean_card_classification(
    cards: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for card in cards:
        if _looks_like_edge_case_card(card):
            fixed_card = dict(card)
            fixed_card["blueprint_key"] = "edge_case"
            fixed_card["card_type"] = "edge_case"
            if not str(fixed_card.get("example_type") or "").strip():
                fixed_card["example_type"] = "boundary_or_irregular_state_example"
            normalized.append(fixed_card)
        else:
            normalized.append(card)
    return normalized


def _normalize_visual_type(value: Any) -> str:
    raw = str(value or "").strip().lower().replace(" ", "_")
    if not raw or raw == "none":
        return "none"
    raw = raw.split("|", maxsplit=1)[0].strip()
    return _VISUAL_TYPE_ALIASES.get(raw, raw)


def _choose_allowed_visual_type(allowed_value: Any, card: dict[str, Any]) -> str:
    """Pick one visual_type from a pipe-separated allowed-types list.

    Strategy (cleaned up):
      1. If the LLM already chose a visual_type that's in the allowed list,
         honor it. Don't second-guess via regex inference — the LLM has the
         card content; we only have keyword heuristics that misfire on
         broader topics (e.g. "left/right" matches array_state_diagram even
         for tree branches; "graph" matches graph_chart for a graph data
         structure).
      2. If the allowed list has only one option, return it.
      3. Otherwise, fall back to the first option in the list. The blueprint
         author orders options by likelihood; the first option is the safest
         default.

    We deliberately REMOVED the previous keyword-regex inference path that
    chose between options based on card text. It was a frequent source of
    wrong-visual-for-topic bugs (e.g. a BST topic with "left/right" in the
    text picking array_state_diagram). If the LLM's pick isn't sufficient,
    the fix belongs in the prompt or schema, not in regex-based override.
    """
    # Split on pipe with surrounding whitespace tolerated. Strip whitespace
    # AND stray underscores (the previous implementation used `.replace(" ",
    # "_")` which produced leaked underscores like "node_link_diagram_" on
    # options adjacent to a pipe-separator).
    raw_options = [
        item.strip().strip("_").strip()
        for item in re.split(r"\s*\|\s*", str(allowed_value or "none").lower())
        if item.strip()
    ]
    options = [_normalize_visual_type(item) for item in raw_options]
    options = [item for item in options if item != "none"]
    if not options:
        return "none"

    # Trust the LLM's pick when it's in the allowed list.
    llm_choice = _normalize_visual_type(card.get("visual_type"))
    if llm_choice and llm_choice in options:
        return llm_choice

    # Single-option list — no decision to make.
    if len(options) == 1:
        return options[0]

    # Multi-option list with no usable LLM pick — fall back to the first
    # option (the blueprint author's preferred default).
    return options[0]


def _normalize_card_title(
    *,
    value: Any,
    blueprint_key: str,
    card_index: int,
) -> str:
    # Strip only TRAILING colons (LLM artifact like "Initial State:"), keep
    # mid-title colons such as "Step 1: Initial State".
    title = str(value or "").strip().rstrip(":").rstrip()
    is_generic = not title or re.fullmatch(r"card\s+\d+", title, flags=re.IGNORECASE)

    # Every blueprint key gets a sensible default when the LLM leaves the title
    # empty (or emits a generic "Card N"), so a card can never render as
    # "Card 3" in the UI. Keys not listed fall back to the generic default below.
    if is_generic:
        default_title = {
            "roadmap": "Where this path goes",
            "components_terms": "Key terms",
            "background": "What this topic is",
            "process": "How it works",
            "method_process": "How it works",
            "code_walkthrough": "Code walkthrough",
            "worked_example": "Worked example",
            "edge_case": "Edge case",
            "comparison": "Comparison",
            "practice": "Practice",
            "takeaway": "Takeaway",
        }.get(blueprint_key)
        if default_title:
            return default_title

    # For step-numbered titles ("Step 1 Initial State", "Step 2 Compute Mid"),
    # insert a colon between the step number and the descriptor if missing.
    if title:
        title = re.sub(
            r"^(Step\s+\d+)\s+(?=\S)(?!:)",
            r"\1: ",
            title,
            flags=re.IGNORECASE,
        )

    return title or f"Card {card_index + 1}"


def _build_visual_plan(
    *,
    visual_type: str,
    title: str,
    purpose: str,
    blueprint_key: str = "",
    topic_hint: str = "",
    visual_description: str = "",
    visual_columns: Any,
    visual_rows: Any,
    visual_highlight_row: Any,
    visual_steps: Any,
    visual_formula: Any,
    visual_symbols: Any,
    visual_when_to_use: Any,
    visual_center: Any,
    visual_nodes: Any,
    visual_edges: Any,
    visual_wrong: Any,
    visual_correct: Any,
    visual_wrong_label: Any,
    visual_correct_label: Any,
    visual_why: Any,
    visual_x_label: Any,
    visual_y_label: Any,
    visual_data_points: Any,
    visual_key_points: Any,
    visual_array_values: Any,
    visual_array_rows: Any,
    visual_array_pointers: Any,
    visual_array_ranges: Any,
    visual_array_annotations: Any,
    points: list[str],
    code_snippet: str,
    code_language: str,
) -> dict[str, Any]:
    if visual_type == "none":
        return _EMPTY_VISUAL_PLAN.copy()

    description = visual_description or purpose or title
    if not description and visual_type != "code_trace":
        return _EMPTY_VISUAL_PLAN.copy()

    visual_plan: dict[str, Any] = {
        "type": visual_type,
        "title": title,
        "purpose": purpose,
        "description": description,
        "placement": "card",
        "what_to_notice": description,
        "common_mistake": "",
        "x_label": "",
        "y_label": "",
        "data_points": [],
        "key_points": [],
        "array_values": [],
        "array_rows": [],
        "array_pointers": [],
        "array_ranges": [],
        "array_annotations": [],
        "nodes": [],
        "edges": [],
        "traversal_path": [],
        "components": [],
        "wires": [],
        "code": "",
        "language": "",
        "columns": [],
        "rows": [],
        "highlight_row": -1,
        "steps": [],
        "center": "",
        "labels": [],
        "formula": "",
        "symbols": [],
        "when_to_use": "",
        "wrong": "",
        "correct": "",
        "wrong_label": "",
        "correct_label": "",
        "why": "",
        "counterexample": "",
    }

    if visual_type in {"step_flow", "causal_chain", "path_progress", "progressive_step_flow"}:
        steps = _validated_visual_steps(visual_steps)
        if visual_type == "progressive_step_flow":
            steps = _sanitize_progressive_step_flow(
                steps, card_title=title, topic_hint=topic_hint
            )
        if len(steps) >= 1:
            visual_plan["steps"] = steps

    if visual_type == "practice_feedback":
        steps = _validated_visual_steps(visual_steps)
        if len(steps) >= 1:
            visual_plan["steps"] = steps
        else:
            visual_plan["steps"] = _points_to_visual_steps(points, description)[:3]

    if visual_type == "comparison_table":
        columns, rows, highlight_row = _validated_visual_table(
            columns=visual_columns,
            rows=visual_rows,
            highlight_row=visual_highlight_row,
        )
        if columns and rows:
            visual_plan["columns"] = columns
            visual_plan["rows"] = rows
            visual_plan["highlight_row"] = highlight_row

    if visual_type == "state_change":
        columns, rows, highlight_row = _validated_visual_table(
            columns=visual_columns,
            rows=visual_rows,
            highlight_row=visual_highlight_row,
        )
        if columns and rows:
            visual_plan["columns"] = columns
            visual_plan["rows"] = rows
            visual_plan["highlight_row"] = highlight_row
        else:
            steps = _validated_visual_steps(visual_steps)
            if len(steps) >= 1:
                visual_plan["steps"] = steps

    if visual_type == "code_trace":
        if code_snippet:
            visual_plan["code"] = code_snippet
            visual_plan["language"] = code_language
        steps = _points_to_visual_steps(points, description)
        if steps:
            visual_plan["steps"] = steps[:6]

    if visual_type == "formula_card":
        formula = str(visual_formula or "").strip() or code_snippet or _first_math_like_text(points)
        symbols = _validated_symbols(visual_symbols)
        if formula or symbols:
            visual_plan["formula"] = formula
            visual_plan["symbols"] = symbols
            visual_plan["when_to_use"] = str(visual_when_to_use or "").strip() or purpose

    if visual_type == "concept_map":
        nodes = _validated_concept_nodes(visual_nodes)
        center = str(visual_center or "").strip() or title
        if center and nodes:
            visual_plan["center"] = center
            visual_plan["nodes"] = nodes

    if visual_type == "node_link_diagram":
        nodes = _validated_node_link_nodes(visual_nodes)
        edges = _validated_visual_edges(visual_edges)
        if not nodes:
            nodes, edges = _infer_node_link_from_description(visual_description)
        # No synthetic fallback: if the LLM didn't supply usable node data and
        # the description didn't yield enough to infer from, leave the visual
        # plan empty. The frontend's tightened `isLessonVisualRenderable` will
        # hide the empty visual cleanly.
        if nodes:
            visual_plan["nodes"] = nodes
            visual_plan["edges"] = edges

    if visual_type == "spatial_diagram":
        visual_plan["center"] = title
        visual_plan["labels"] = [{"target": "center", "text": visual_description}]

    if visual_type == "misconception":
        wrong = str(visual_wrong or "").strip()
        correct = str(visual_correct or "").strip()
        if wrong and correct:
            visual_plan["wrong_label"] = str(visual_wrong_label or "").strip() or "Tempting idea"
            visual_plan["correct_label"] = str(visual_correct_label or "").strip() or "Correct idea"
            visual_plan["wrong"] = wrong
            visual_plan["correct"] = correct
            visual_plan["why"] = str(visual_why or "").strip() or purpose

    if visual_type == "graph_chart":
        data_points = _validated_data_points(visual_data_points)
        key_points = _validated_key_points(visual_key_points)
        if len(data_points) >= 2:
            visual_plan["x_label"] = str(visual_x_label or "").strip()
            visual_plan["y_label"] = str(visual_y_label or "").strip()
            visual_plan["data_points"] = data_points
            visual_plan["key_points"] = key_points

    if visual_type == "array_state_diagram":
        array_values = _validated_array_values(visual_array_values)
        array_rows = _validated_array_rows(visual_array_rows)
        if array_rows:
            visual_plan["array_rows"] = array_rows
        if array_values:
            visual_plan["array_values"] = array_values
            visual_plan["array_pointers"] = _validated_array_pointers(
                visual_array_pointers,
                max_index=len(array_values) - 1,
            )
            visual_plan["array_ranges"] = _validated_array_ranges(
                visual_array_ranges,
                max_index=len(array_values) - 1,
            )
            visual_plan["array_annotations"] = _string_list(visual_array_annotations)[:6]
        # No synthetic fallback: empty array_state_diagram visuals are hidden
        # by the frontend's `isLessonVisualRenderable` check.

    return visual_plan


def _points_to_visual_steps(points: list[str], fallback: str) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for point in points:
        cleaned = re.sub(r"^\s*-\s*", "", point).strip()
        if not cleaned:
            continue
        if ":" in cleaned:
            label, description = cleaned.split(":", maxsplit=1)
            steps.append(_visual_step_entry(label.strip(), description.strip(), index=len(steps)))
        else:
            steps.append(_visual_step_entry(f"Step {len(steps) + 1}", cleaned, index=len(steps)))

    if not steps and fallback:
        steps.append(_visual_step_entry("Visual state", fallback, index=0))
    return _ensure_unique_visual_step_labels(steps)


def _progressive_steps_from_card_points(card: dict[str, Any]) -> list[dict[str, Any]]:
    """Build visual steps that mirror the card's top-level bullet groups.

    Progressive step-flow visuals are a cognitive anchor for the right-panel
    text. If the visual decomposes an algorithm into hidden micro-steps while
    the card text uses broader frames, the two feel disconnected. This keeps
    one visual step per main bullet group.
    """
    groups = _group_main_point_blocks([
        str(point).rstrip()
        for point in (card.get("points") or [])
        if str(point).strip()
    ])
    steps: list[dict[str, Any]] = []
    for index, group in enumerate(groups):
        main = next((point for point in group if not str(point).lstrip().startswith("- ")), "")
        if not main:
            continue
        subpoint = next((point for point in group if str(point).lstrip().startswith("- ")), "")
        main_text = _clean_visual_bullet_text(main)
        sub_text = _clean_visual_bullet_text(subpoint)
        label = _compact_visual_step_label(main_text, index)
        mini_visual = _compact_visual_step_mini_visual(sub_text or main_text or label)
        kind = _infer_visual_step_kind(label, sub_text, main_text, mini_visual)
        visual_label = _fallback_visual_step_label(kind, label, sub_text or main_text, mini_visual, index)
        step = _visual_step_entry(
            label,
            "",
            mini_visual,
            index=index,
            active=index == 0,
            kind=kind,
        )
        step["visual_label"] = visual_label
        steps.append(step)
    return _ensure_unique_visual_step_labels(steps)


def _clean_visual_bullet_text(value: str) -> str:
    return re.sub(r"^\s*-\s*", "", str(value or "")).strip().rstrip(".;")


def _compact_visual_step_label(text: str, index: int) -> str:
    source = (text.split(":", maxsplit=1)[0] or text).strip()
    if not source:
        return f"Step {index + 1}"
    words = source.split()
    if len(words) <= 4:
        return source
    # Preserve common process frames instead of truncating into vague fragments.
    lowered = source.lower()
    for prefix in (
        "starting state",
        "each iteration",
        "repeated action",
        "state update",
        "stopping condition",
        "stop when",
        "output rule",
        "output",
        "currently",
        "now",
    ):
        if lowered.startswith(prefix):
            return prefix.title() if prefix not in {"currently", "now"} else prefix.capitalize()
    return " ".join(words[:4])


def _compact_visual_step_mini_visual(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if not cleaned:
        return ""
    patterns = [
        r"\bstack\s*(?:is\s*)?=\s*[^,.;]+",
        r"\bqueue\s*(?:is\s*)?=\s*[^,.;]+",
        r"\bvisited\s*(?:is\s*)?=\s*[^,.;]+",
        r"\bresult\s*(?:is\s*)?=\s*[^,.;]+",
        r"\boutput\s*(?:is\s*)?=\s*[^,.;]+",
        r"\bcurrent\s*(?:is\s*)?=\s*[^,.;]+",
        r"\bstack is empty\b",
        r"\bqueue is empty\b",
        r"\bmark it as visited\b",
        r"\bpush it onto the stack\b",
        r"\bpop [^,.;]+",
        r"\bpush [^,.;]+",
    ]
    for pattern in patterns:
        match = re.search(pattern, cleaned, flags=re.IGNORECASE)
        if match:
            return _limit_visual_words(match.group(0), 5)
    return _limit_visual_words(cleaned, 5)


_VISUAL_STEP_LABEL_BY_KIND: dict[str, str] = {
    "start": "Start",
    "starting_state": "Start",
    "initialize": "Initialize",
    "initialize_stack": "Stack Ready",
    "initialize_queue": "Queue Ready",
    "loop": "Loop",
    "repeat": "Repeat",
    "pop": "Pop",
    "pop_current": "Pop Node",
    "dequeue": "Dequeue",
    "dequeue_current": "Dequeue",
    "select_current": "Pick Node",
    "visit": "Visit",
    "visit_current": "Visit",
    "check_neighbors": "Check",
    "push": "Push",
    "push_unvisited": "Push New",
    "enqueue": "Enqueue",
    "enqueue_unvisited": "Enqueue New",
    "mark_visited": "Mark",
    "update_state": "Update",
    "compare": "Compare",
    "swap": "Swap",
    "choose_mid": "Midpoint",
    "discard_left": "Move Right",
    "discard_right": "Move Left",
    "recurse": "Recurse",
    "recurse_left": "Go Left",
    "recurse_right": "Go Right",
    "return_value": "Return",
    "output": "Output",
    "complete": "Done",
}


def _normalize_visual_step_kind(value: str) -> str:
    return re.sub(r"(^_+|_+$)", "", re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()))


def _infer_visual_step_kind(*values: str) -> str:
    text = " ".join(str(value or "").lower() for value in values)
    checks: list[tuple[str, tuple[str, ...]]] = [
        ("dequeue_current", ("dequeue",)),
        ("pop_current", ("pop",)),
        ("check_neighbors", ("neighbor",)),
        ("push_unvisited", ("push",)),
        ("enqueue_unvisited", ("enqueue",)),
        ("mark_visited", ("visited", "mark")),
        ("choose_mid", ("mid",)),
        ("compare", ("compare",)),
        ("swap", ("swap",)),
        ("recurse_left", ("recurse", "left")),
        ("recurse_right", ("recurse", "right")),
        ("recurse", ("recurse",)),
        ("update_state", ("update",)),
        ("loop", ("each iteration",)),
        ("loop", ("repeat",)),
        ("loop", ("while",)),
        ("output", ("output",)),
        ("complete", ("done",)),
        ("complete", ("complete",)),
        ("initialize_stack", ("initialize", "stack")),
        ("initialize_stack", ("stack", "empty")),
        ("initialize_queue", ("initialize", "queue")),
        ("initialize_queue", ("queue", "empty")),
        ("starting_state", ("starting",)),
        ("starting_state", ("currently",)),
    ]
    for kind, required_terms in checks:
        if all(term in text for term in required_terms):
            return kind
    return ""


def _clean_visual_step_label(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip()
    cleaned = re.sub(r"^[A-Za-z]+\s*[-–—]\s*", "", cleaned).strip()
    return cleaned.rstrip(",:.;")


def _is_valid_visual_step_label(label: str, detail: str = "") -> bool:
    cleaned = _clean_visual_step_label(label)
    if not cleaned:
        return False
    if len(cleaned) > 24:
        return False
    if len(cleaned.split()) > 4:
        return False
    if cleaned.lower() in {"currently", "now", "action", "state update"}:
        return cleaned.lower() == "state update"
    detail_words = str(detail or "").lower().split()
    label_words = cleaned.lower().split()
    if len(detail_words) > len(label_words) + 2 and detail_words[: len(label_words)] == label_words:
        return False
    return True


def _fallback_visual_step_label(kind: str, label: str, description: str, mini_visual: str, index: int) -> str:
    normalized = _normalize_visual_step_kind(kind) or _infer_visual_step_kind(label, description, mini_visual)
    if normalized in _VISUAL_STEP_LABEL_BY_KIND:
        return _VISUAL_STEP_LABEL_BY_KIND[normalized]
    if _is_valid_visual_step_label(label, description):
        return _clean_visual_step_label(label)
    compact = _compact_visual_step_label(label or description or mini_visual, index)
    if _is_valid_visual_step_label(compact, description):
        return _clean_visual_step_label(compact)
    return f"Step {index + 1}"


def _visual_step_entry(
    label: str,
    description: str = "",
    mini_visual: str = "",
    *,
    index: int = 0,
    active: bool = False,
    kind: str = "",
) -> dict[str, Any]:
    step_title = str(label or f"Step {index + 1}").strip()
    step_detail = str(description or "").strip()
    mini_visual = str(mini_visual or "").strip()
    normalized_kind = _normalize_visual_step_kind(kind) or _infer_visual_step_kind(
        step_title,
        step_detail,
        mini_visual,
    )
    visual_label = _fallback_visual_step_label(
        normalized_kind,
        step_title,
        step_detail,
        mini_visual,
        index,
    )
    step: dict[str, Any] = {
        "kind": normalized_kind,
        "label": step_title,
        "step_title": step_title,
        "visual_label": visual_label,
        "description": step_detail,
        "step_detail": step_detail,
        "mini_visual": mini_visual,
    }
    if active:
        step["active"] = True
    return step


def _ensure_unique_visual_step_labels(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(steps) < 2:
        return steps

    used: set[str] = set()
    for index, step in enumerate(steps):
        current = _clean_visual_step_label(str(step.get("visual_label") or ""))
        key = current.lower()
        if current and key not in used:
            used.add(key)
            step["visual_label"] = current
            continue

        candidates = [
            _VISUAL_STEP_LABEL_BY_KIND.get(_normalize_visual_step_kind(str(step.get("kind") or "")), ""),
            _clean_visual_step_label(str(step.get("step_title") or step.get("label") or "")),
            _compact_visual_step_label(str(step.get("step_title") or step.get("label") or ""), index),
            _compact_visual_step_mini_visual(str(step.get("mini_visual") or "")),
            f"Step {index + 1}",
        ]
        for candidate in candidates:
            cleaned = _clean_visual_step_label(candidate)
            candidate_key = cleaned.lower()
            if (
                _is_valid_visual_step_label(cleaned, str(step.get("step_detail") or step.get("description") or ""))
                and candidate_key not in used
            ):
                step["visual_label"] = cleaned
                used.add(candidate_key)
                break
        else:
            fallback = f"Step {index + 1}"
            step["visual_label"] = fallback
            used.add(fallback.lower())

    return steps


def _limit_visual_words(text: str, limit: int) -> str:
    words = str(text or "").split()
    return " ".join(words[:limit])


def _validated_visual_steps(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    steps: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if isinstance(item, dict):
            raw_kind = str(item.get("kind") or "").strip()
            label = str(item.get("label") or f"Step {index + 1}").strip()
            step_title = str(item.get("step_title") or "").strip()
            description = str(item.get("description") or "").strip()
            step_detail = str(item.get("step_detail") or "").strip()
            visual_label = str(item.get("visual_label") or "").strip()
            mini_visual = str(item.get("mini_visual") or "").strip()
            formula = str(item.get("formula") or "").strip()
            cases = [
                str(case).strip()
                for case in (item.get("cases") or [])
                if str(case).strip()
            ][:3]
            active = bool(item.get("active"))
        else:
            raw_kind = ""
            label = f"Step {index + 1}"
            step_title = label
            description = str(item or "").strip()
            step_detail = description
            visual_label = ""
            mini_visual = ""
            formula = ""
            cases = []
            active = False

        step_title = step_title or label or f"Step {index + 1}"
        step_detail = step_detail or description
        kind = _normalize_visual_step_kind(raw_kind) or _infer_visual_step_kind(
            step_title,
            label,
            step_detail,
            mini_visual,
        )
        if not _is_valid_visual_step_label(visual_label, step_detail):
            visual_label = _fallback_visual_step_label(kind, step_title, step_detail, mini_visual, index)
        else:
            visual_label = _clean_visual_step_label(visual_label)

        # Keep the step if EITHER description, mini_visual, OR a non-default label is present.
        # progressive_step_flow specifically tells the LLM to leave description empty.
        has_default_label = not label or label == f"Step {index + 1}"
        if step_detail or mini_visual or formula or cases or not has_default_label:
            step: dict[str, Any] = {
                "kind": kind,
                "label": step_title,
                "step_title": step_title,
                "visual_label": visual_label,
                "description": step_detail,
                "step_detail": step_detail,
            }
            if mini_visual:
                step["mini_visual"] = mini_visual
            if formula:
                step["formula"] = formula
            if cases:
                step["cases"] = cases
            if active:
                step["active"] = True
            steps.append(step)

    return steps


def _validated_highlight_lines_per_step(
    value: Any,
    *,
    code_snippet: str,
) -> list[list[int]]:
    if not isinstance(value, list):
        return []

    max_line = len(code_snippet.splitlines()) if code_snippet else 0
    ranges: list[list[int]] = []
    for item in value:
        if not isinstance(item, list) or len(item) != 2:
            continue
        try:
            start = int(item[0])
            end = int(item[1])
        except (TypeError, ValueError):
            continue
        if start <= 0 or end <= 0:
            continue
        if end < start:
            start, end = end, start
        if max_line:
            start = min(start, max_line)
            end = min(end, max_line)
        ranges.append([start, end])
    return ranges


class _AccumulatorRewriter(ast.NodeTransformer):
    """Rewrites a broken single-function recursion into the helper body: renames the
    structure param to `node`, turns `self`-discarded recursive calls into
    `helper(x, acc)`, and strips the value from base-case returns."""

    def __init__(self, fname: str, helper: str, struct: str, node: str, acc: str) -> None:
        self.fname, self.helper, self.struct, self.node, self.acc = fname, helper, struct, node, acc

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if node.id == self.struct:
            return ast.copy_location(ast.Name(id=self.node, ctx=node.ctx), node)
        return node

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        if isinstance(node.func, ast.Name) and node.func.id == self.fname:
            node.func = ast.Name(id=self.helper, ctx=ast.Load())
            node.args = list(node.args) + [ast.Name(id=self.acc, ctx=ast.Load())]
        return node

    def visit_Return(self, node: ast.Return) -> ast.AST:
        return ast.copy_location(ast.Return(value=None), node)


def _fix_dedented_body_lines(code: str) -> str:
    """Repair the common LLM indentation error: a statement wrongly placed at column
    0 that belongs to the preceding function body (e.g. `mid = (low + high) // 2`
    flush-left between indented lines). Only runs when the code does NOT parse, and
    only keeps the repair if the result parses — so it can never worsen valid code.
    """
    try:
        ast.parse(code)
        return code
    except SyntaxError:
        pass
    out: list[str] = []
    prev_indent = 0
    for line in code.split("\n"):
        stripped = line.strip()
        if not stripped:
            out.append(line)
            continue
        cur_indent = len(line) - len(line.lstrip(" "))
        is_header = re.match(r"(def|class|async|import|from|@|#)\b", stripped) is not None
        if cur_indent == 0 and not is_header and prev_indent > 0:
            out.append(" " * prev_indent + stripped)  # pull into the enclosing block
        else:
            out.append(line)
        prev_indent = len(out[-1]) - len(out[-1].lstrip(" "))
    fixed = "\n".join(out)
    try:
        ast.parse(fixed)
        return fixed
    except SyntaxError:
        return code


def _strip_module_level_strays(code: str) -> str:
    """Remove stray module-level statements (e.g. a bare `traverse(node.left, result)`
    call left OUTSIDE the functions) that the walkthrough accumulation can append
    after the function bodies. Keeps defs / classes / imports / `if __name__` blocks.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code
    keep_types = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom, ast.If)
    kept = [n for n in tree.body if isinstance(n, keep_types)]
    if len(kept) == len(tree.body) or not kept:
        return code
    new_tree = ast.Module(body=kept, type_ignores=[])
    ast.fix_missing_locations(new_tree)
    try:
        return ast.unparse(new_tree)
    except Exception:  # noqa: BLE001
        return code


def _strip_driver_code(code: str) -> str:
    """Drop driver/example scaffolding the model sometimes appends so the snippet is ONLY
    the algorithm's functions: an `if __name__ == "__main__"` guard and bare module-level
    expression statements (example calls / `print(...)`). A clean merge-sort answer is just
    `merge_sort` + `merge`, not a runnable script."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code
    kept: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, ast.If) and isinstance(node.test, ast.Compare) \
                and isinstance(node.test.left, ast.Name) and node.test.left.id == "__name__":
            continue  # `if __name__ == "__main__":` driver
        if isinstance(node, ast.Expr):
            continue  # bare example/usage/print call at module level (or a stray docstring)
        kept.append(node)
    if len(kept) == len(tree.body) or not kept:
        return code  # nothing to strip — preserve original formatting
    new_tree = ast.Module(body=kept, type_ignores=[])
    ast.fix_missing_locations(new_tree)
    try:
        return ast.unparse(new_tree)
    except Exception:  # noqa: BLE001
        return code


def _ast_args(names: list[str]) -> "ast.arguments":
    return ast.arguments(posonlyargs=[], args=[ast.arg(arg=n) for n in names], vararg=None,
                         kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[])


def _synthesize_main_for_helper(code: str) -> str:
    """When the code is ONLY a standalone recursive helper taking an accumulator
    (e.g. `def postorder_helper(node, result): ... result.append(...)`) with no main
    entry point, synthesize the main that creates the accumulator, calls the helper,
    and returns it. Targets a single self-recursive 2-arg function whose 2nd param is
    an accumulator. Leaves correct main+helper / OOP / non-matching code untouched.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code
    if any(isinstance(n, ast.ClassDef) for n in tree.body):
        return code
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    if len(funcs) != 1:
        return code
    fn = funcs[0]
    if len(fn.args.args) != 2:
        return code
    if not any(isinstance(s, ast.Call) and isinstance(s.func, ast.Name) and s.func.id == fn.name for s in ast.walk(fn)):
        return code  # not self-recursive

    params = [a.arg for a in fn.args.args]
    acc_param, uses_set = None, False
    for p in params:
        for s in ast.walk(fn):
            if (isinstance(s, ast.Call) and isinstance(s.func, ast.Attribute)
                    and isinstance(s.func.value, ast.Name) and s.func.value.id == p
                    and s.func.attr in ("append", "add")):
                acc_param = p
                uses_set = s.func.attr == "add"
    if acc_param is None:
        return code
    node_param = next((p for p in params if p != acc_param), params[0])

    name = fn.name
    if name.endswith("_helper"):
        main_name = name[: -len("_helper")]
    elif name.lower().endswith("helper"):
        main_name = name[: -len("helper")].rstrip("_") or "solve"
    else:
        main_name = f"{name}_main"
    root_param = "root" if node_param != "root" else "tree"
    acc_value = ast.Call(func=ast.Name(id="set", ctx=ast.Load()), args=[], keywords=[]) if uses_set else ast.List(elts=[], ctx=ast.Load())

    main_fn = ast.FunctionDef(
        name=main_name, args=_ast_args([root_param]),
        body=[
            ast.Assign(targets=[ast.Name(id=acc_param, ctx=ast.Store())], value=acc_value),
            ast.Expr(value=ast.Call(func=ast.Name(id=name, ctx=ast.Load()),
                                    args=[ast.Name(id=root_param, ctx=ast.Load()), ast.Name(id=acc_param, ctx=ast.Load())], keywords=[])),
            ast.Return(value=ast.Name(id=acc_param, ctx=ast.Load())),
        ], decorator_list=[])
    new_tree = ast.Module(body=[main_fn, fn], type_ignores=[])
    ast.fix_missing_locations(new_tree)
    try:
        return ast.unparse(new_tree)
    except Exception:  # noqa: BLE001
        return code


def _split_accumulator_recursion(code: str) -> str:
    """Fix the broken single-function accumulator-recursion pattern by splitting it
    into a correct main + helper. Targets ONLY: one top-level function taking one
    structure arg, with a local `acc = []`, that calls ITSELF with the recursive
    results discarded and does `acc.append(...)`. Leaves correct functional/concat
    styles and existing main+helper code untouched. Best-effort; returns the input
    on any anomaly.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code
    if any(isinstance(n, ast.ClassDef) for n in tree.body):
        return code  # OOP code is intentional — leave it
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    if len(funcs) != 1:
        return code
    fn = funcs[0]
    if len(fn.args.args) != 1:
        return code
    struct = fn.args.args[0].arg

    acc, acc_stmt = None, None
    for stmt in fn.body:
        if (isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.List) and not stmt.value.elts
                and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name)):
            acc, acc_stmt = stmt.targets[0].id, stmt
            break
    if acc is None:
        return code

    self_recursive = any(
        isinstance(s, ast.Call) and isinstance(s.func, ast.Name) and s.func.id == fn.name
        for s in ast.walk(fn)
    )
    has_append = any(
        isinstance(s, ast.Call) and isinstance(s.func, ast.Attribute) and s.func.attr == "append"
        and isinstance(s.func.value, ast.Name) and s.func.value.id == acc
        for s in ast.walk(fn)
    )
    has_discarded_recursion = any(
        isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)
        and isinstance(stmt.value.func, ast.Name) and stmt.value.func.id == fn.name
        for stmt in ast.walk(fn)
    )
    if not (self_recursive and has_append and has_discarded_recursion):
        return code  # correct concatenation style or not the broken pattern

    helper = "traverse" if fn.name != "traverse" else "visit"
    node = "node" if struct != "node" else "cur"
    rewriter = _AccumulatorRewriter(fn.name, helper, struct, node, acc)
    helper_body = [rewriter.visit(stmt) for stmt in fn.body if stmt is not acc_stmt] or [ast.Pass()]

    def _args(names: list[str]) -> ast.arguments:
        return ast.arguments(posonlyargs=[], args=[ast.arg(arg=n) for n in names], vararg=None,
                             kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[])

    main_fn = ast.FunctionDef(
        name=fn.name, args=_args([struct]),
        body=[
            ast.Assign(targets=[ast.Name(id=acc, ctx=ast.Store())], value=ast.List(elts=[], ctx=ast.Load())),
            ast.Expr(value=ast.Call(
                func=ast.Name(id=helper, ctx=ast.Load()),
                args=[ast.Name(id=struct, ctx=ast.Load()), ast.Name(id=acc, ctx=ast.Load())], keywords=[])),
            ast.Return(value=ast.Name(id=acc, ctx=ast.Load())),
        ], decorator_list=[])
    helper_fn = ast.FunctionDef(name=helper, args=_args([node, acc]), body=helper_body, decorator_list=[])

    new_tree = ast.Module(body=[main_fn, helper_fn], type_ignores=[])
    ast.fix_missing_locations(new_tree)
    try:
        return ast.unparse(new_tree)
    except Exception:  # noqa: BLE001
        return code


def _fix_code_layout(code: str) -> tuple[str, dict[int, int]]:
    """Normalize a coding snippet's layout: pull a stray module-level `self` method
    back INSIDE the class above it, and put exactly two blank lines between sibling
    functions/methods. Returns (new_code, line_map) mapping each original 1-indexed
    line to its new 1-indexed line so highlight ranges can be remapped. Layout-only
    (never edits tokens); deterministic so identical input yields identical output.
    """
    if not code.strip():
        return code, {}
    lines = code.split("\n")
    has_class = any(re.match(r"class\s+\w+", l.strip()) for l in lines)

    # Pass 1: indent a stray top-level `def f(self, ...)` (and its body) into the
    # class. Line-preserving — only leading indentation changes.
    work = list(lines)
    if has_class:
        i = 0
        while i < len(work):
            stripped = work[i].lstrip(" ")
            indent = len(work[i]) - len(stripped)
            if indent == 0 and re.match(r"def\s+\w+\s*\(\s*self\b", stripped):
                work[i] = "    " + work[i]
                j = i + 1
                while j < len(work):
                    body = work[j]
                    if body.strip() == "":
                        j += 1
                        continue
                    if len(body) - len(body.lstrip(" ")) == 0:
                        break  # back at top level — this function ended
                    work[j] = "    " + body
                    j += 1
                i = j
            else:
                i += 1

    # Pass 2: exactly two blank lines before each sibling def/class; build the map.
    result: list[str] = []
    line_map: dict[int, int] = {}
    for idx, line in enumerate(work, start=1):
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if re.match(r"(def|class)\b", stripped) and result:
            while result and result[-1].strip() == "":
                result.pop()
            prev = next((r for r in reversed(result) if r.strip()), "")
            prev_indent = len(prev) - len(prev.lstrip(" "))
            prev_is_header = bool(re.match(r"(def|class)\b", prev.strip()))
            # First member directly under its class/def header gets no blank lines;
            # a sibling that follows a previous body gets two.
            if not (prev_is_header and prev_indent < indent):
                result.extend(["", ""])
        line_map[idx] = len(result) + 1
        result.append(line)
    return "\n".join(result), line_map


def _remap_line_ranges(ranges: list[list[int]], line_map: dict[int, int]) -> list[list[int]]:
    if not line_map:
        return ranges
    out: list[list[int]] = []
    for r in ranges:
        if isinstance(r, list) and len(r) == 2:
            out.append([line_map.get(r[0], r[0]), line_map.get(r[1], r[1])])
        else:
            out.append(r)
    return out


def _validated_visual_table(
    *,
    columns: Any,
    rows: Any,
    highlight_row: Any,
) -> tuple[list[str], list[list[str]], int]:
    if not isinstance(columns, list) or not isinstance(rows, list):
        return [], [], -1

    clean_columns = [str(column).strip() for column in columns if str(column).strip()]
    if not clean_columns:
        return [], [], -1

    clean_rows: list[list[str]] = []
    for row in rows:
        if not isinstance(row, list) or len(row) != len(clean_columns):
            return [], [], -1
        clean_row = [str(cell).strip() for cell in row]
        if any(clean_row):
            clean_rows.append(clean_row)

    if not clean_rows:
        return [], [], -1

    try:
        clean_highlight_row = int(highlight_row)
    except (TypeError, ValueError):
        clean_highlight_row = -1

    if clean_highlight_row < 0 or clean_highlight_row >= len(clean_rows):
        clean_highlight_row = -1

    return clean_columns, clean_rows, clean_highlight_row


def _validated_symbols(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []

    symbols: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol") or "").strip()
        meaning = str(item.get("meaning") or "").strip()
        if symbol and meaning:
            symbols.append({"symbol": symbol, "meaning": meaning})
    return symbols


def _validated_concept_nodes(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    nodes: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        if not label:
            continue
        nodes.append({
            "id": str(item.get("id") or f"node-{index + 1}").strip(),
            "label": label,
            "relation": str(item.get("relation") or "").strip(),
            "description": str(item.get("description") or "").strip(),
        })
    return nodes[:8]


_FORBIDDEN_NODE_LABEL_WORDS = {
    "root", "leaf", "node", "parent", "child", "children",
    "left", "right", "tree", "bst", "graph", "edge", "vertex",
    "traversal", "inorder", "preorder", "postorder", "level-order", "levelorder", "level",
    "concept", "topic", "type", "types", "kind", "kinds", "category", "categories",
    "central", "center", "core", "main",
    "array", "list", "stack", "queue", "heap", "deque",
    "input", "output", "data", "value", "values",
}

_STRUCTURAL_NODE_LABEL_WORDS = {
    "root", "leaf", "node", "parent", "child", "children",
    "left", "right", "tree", "bst", "graph", "edge", "vertex",
    "traversal", "inorder", "preorder", "postorder", "levelorder",
    "level", "current", "active",
}


_NODE_STATES = {"unvisited", "discovered", "newly_discovered", "current", "completed", "skipped"}
_EDGE_STATES = {"unchecked", "active", "traversed", "checked", "skipped", "completed"}


def _normalize_node_state(value: str) -> str:
    state = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    if state in {"visited", "seen", "queued", "stacked", "waiting"}:
        return "discovered"
    if state in {"active", "processing", "selected"}:
        return "current"
    if state in {"done", "finished", "processed"}:
        return "completed"
    if state in {"new", "newly_added", "just_discovered"}:
        return "newly_discovered"
    return state if state in _NODE_STATES else "unvisited"


def _normalize_edge_state(value: str) -> str:
    state = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    if state in {"traversal", "current", "selected"}:
        return "active"
    if state in {"used", "tree", "tree_edge"}:
        return "traversed"
    if state in {"ignored", "already_visited"}:
        return "skipped"
    if state in {"done", "finished", "processed"}:
        return "completed"
    return state if state in _EDGE_STATES else "unchecked"


_CODE_LINE_STARTS = (
    "def ",
    "class ",
    "if ",
    "elif ",
    "else:",
    "for ",
    "while ",
    "return ",
    "import ",
    "from ",
    "try:",
    "except ",
    "finally:",
    "with ",
    "break",
    "continue",
    "pass",
    "yield ",
)


def _extract_code_snippet_from_points(points: list[str]) -> str:
    """Recover a code snippet when the model put code in bullets.

    This is a fallback for code_walkthrough cards. It intentionally accepts
    only code-like lines and ignores explanatory bullets so the left panel
    renders code, not prose.
    """
    code_lines: list[str] = []
    for raw_point in points:
        raw_text = str(raw_point or "").rstrip()
        leading_spaces = len(raw_text) - len(raw_text.lstrip(" "))
        text = re.sub(r"^\s*-\s*", "", raw_text.strip()).strip()
        if not text:
            continue

        # Strip lightweight Markdown code fences/ticks if the model used them.
        text = text.strip("`")
        if not _looks_like_code_line(text):
            continue

        # Code that appears as a first-level subbullet is usually the code
        # being discussed by the main bullet, not an indented block. Deeper
        # subbullets can represent nested code blocks.
        indent_level = max(0, leading_spaces // 2 - 1)
        code_lines.append(f"{'    ' * indent_level}{text}")

    return "\n".join(code_lines).strip()


def _remove_code_only_points(points: list[str]) -> list[str]:
    """Remove raw code bullets after recovering them into code_snippet."""
    cleaned: list[str] = []
    for raw_point in points:
        raw_text = str(raw_point or "").rstrip()
        text = re.sub(r"^\s*-\s*", "", raw_text.strip()).strip().strip("`")
        if _looks_like_code_line(text):
            continue
        cleaned.append(raw_point)
    return cleaned


def _looks_like_code_line(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if stripped.startswith(_CODE_LINE_STARTS):
        return True
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]+\])?\s*(=|\+=|-=|\*=|/=)", stripped):
        return True
    if re.match(r"^[A-Za-z_][A-Za-z0-9_\.]*\s*\(.*\)\s*:?\s*$", stripped):
        return True
    if re.match(r"^[A-Za-z_][A-Za-z0-9_\.]*\.[A-Za-z_][A-Za-z0-9_]*\(.*\)\s*$", stripped):
        return True
    if stripped in {"}", "{", "};"}:
        return True
    return False


def _is_valid_data_label(label: str) -> bool:
    """A node_link label should be a short data value (integer, letter, code) — not a concept name."""
    cleaned = _normalize_node_data_label(label)
    if not cleaned or len(cleaned) > 4:
        return False
    lowered = cleaned.lower()
    if lowered in _FORBIDDEN_NODE_LABEL_WORDS:
        return False
    if any(ch.isspace() for ch in cleaned):
        return False
    return True


def _normalize_node_data_label(label: str) -> str:
    """Reduce LLM node labels to the data value that fits inside a node.

    The model often emits labels like "Node A" or "Root 50". The renderer's
    node circles are intended for the stored value only: "A" or "50".
    Structural role belongs in relation/description, not in label.
    """
    cleaned = str(label or "").strip()
    if not cleaned:
        return ""

    cleaned = re.sub(r"[_-]+", " ", cleaned)
    if re.sub(r"[^a-z0-9]+", "", cleaned.lower()) in _STRUCTURAL_NODE_LABEL_WORDS:
        return ""
    cleaned = re.sub(
        r"^(?:node|vertex|root|leaf|parent|child|left|right)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    cleaned = cleaned.strip("()[]{}:;,")
    if re.sub(r"[^a-z0-9]+", "", cleaned.lower()) in _STRUCTURAL_NODE_LABEL_WORDS:
        return ""

    token_match = re.search(r"\b[A-Za-z]{1,2}\b|\b\d{1,4}\b", cleaned)
    if token_match:
        token = token_match.group(0)
        if token.lower() in _STRUCTURAL_NODE_LABEL_WORDS:
            return ""
        return token.upper() if token.isalpha() else token

    if re.fullmatch(r"[A-Za-z0-9]{1,4}", cleaned):
        if cleaned.lower() in _STRUCTURAL_NODE_LABEL_WORDS:
            return ""
        return cleaned.upper() if cleaned.isalpha() else cleaned

    return ""


_DEFAULT_BST_BACKGROUND_NODES: list[dict[str, Any]] = [
    {"id": "50", "label": "50", "relation": "root", "description": "", "x": 50.0, "y": 16.0},
    {"id": "30", "label": "30", "relation": "node", "description": "", "x": 28.0, "y": 42.0},
    {"id": "70", "label": "70", "relation": "node", "description": "", "x": 72.0, "y": 42.0},
    {"id": "20", "label": "20", "relation": "leaf", "description": "", "x": 17.0, "y": 68.0},
    {"id": "40", "label": "40", "relation": "leaf", "description": "", "x": 39.0, "y": 68.0},
    {"id": "60", "label": "60", "relation": "leaf", "description": "", "x": 61.0, "y": 68.0},
    {"id": "80", "label": "80", "relation": "leaf", "description": "", "x": 83.0, "y": 68.0},
]

_DEFAULT_BST_BACKGROUND_EDGES: list[dict[str, str]] = [
    {"from": "50", "to": "30", "label": "", "style": "solid"},
    {"from": "50", "to": "70", "label": "", "style": "solid"},
    {"from": "30", "to": "20", "label": "", "style": "solid"},
    {"from": "30", "to": "40", "label": "", "style": "solid"},
    {"from": "70", "to": "60", "label": "", "style": "solid"},
    {"from": "70", "to": "80", "label": "", "style": "solid"},
]

_BST_TRAVERSAL_ORDERS: dict[str, list[str]] = {
    "inorder": ["20", "30", "40", "50", "60", "70", "80"],
    "preorder": ["50", "30", "20", "40", "70", "60", "80"],
    "postorder": ["20", "40", "30", "60", "80", "70", "50"],
    "level_order": ["50", "30", "70", "20", "40", "60", "80"],
}


_VAGUE_STEP_LABEL_FRAGMENTS = (
    "trace the steps",
    "process step",
    "first step",
    "second step",
    "third step",
    "next step",
    "step one",
    "step two",
    "step three",
    "general step",
    "the steps of",
    "traversal process",
    "process steps",
    "algorithm step",
)


_CANONICAL_STEP_FLOWS: dict[str, list[tuple[str, str]]] = {
    "preorder": [
        ("Visit current", "result += val"),
        ("Recurse left", "go to node.left"),
        ("Recurse right", "go to node.right"),
    ],
    "inorder": [
        ("Recurse left", "go to node.left"),
        ("Visit current", "result += val"),
        ("Recurse right", "go to node.right"),
    ],
    "postorder": [
        ("Recurse left", "go to node.left"),
        ("Recurse right", "go to node.right"),
        ("Visit current", "result += val"),
    ],
    "level_order": [
        ("Dequeue front", "queue.popleft()"),
        ("Visit node", "result += val"),
        ("Enqueue children", "queue += children"),
    ],
    "binary_search": [
        ("Set bounds", "low=0, high=n-1"),
        ("Compute mid", "mid=(low+high)//2"),
        ("Compare to target", "arr[mid] vs target"),
        ("Shrink range", "low=mid+1 or high=mid-1"),
        ("Stop", "found or low>high"),
    ],
    "bst_search": [
        ("Start at root", "node=root"),
        ("Compare to key", "key vs node.val"),
        ("Go left or right", "node=node.left or .right"),
        ("Stop", "found or node=null"),
    ],
    "bst_insert": [
        ("Start at root", "node=root"),
        ("Compare to key", "key vs node.val"),
        ("Walk to leaf", "node=node.left or .right"),
        ("Attach new node", "parent.left/right = new"),
    ],
    "bfs": [
        ("Initialize queue", "queue=[start]"),
        ("Dequeue front", "node=queue.popleft()"),
        ("Visit node", "result += node"),
        ("Enqueue neighbors", "queue += unvisited"),
        ("Stop", "queue empty"),
    ],
    "dfs": [
        ("Initialize stack", "stack=[start]"),
        ("Pop top", "node=stack.pop()"),
        ("Visit node", "result += node"),
        ("Push neighbors", "stack += unvisited"),
        ("Stop", "stack empty"),
    ],
    "sliding_window": [
        ("Initialize window", "left=0, right=0"),
        ("Expand right", "right += 1"),
        ("Update state", "track window sum/count"),
        ("Shrink left", "left += 1 if invalid"),
        ("Record best", "answer = max/min(answer, ...)"),
    ],
    "merge_sort": [
        ("Split", "divide array in half"),
        ("Sort halves", "recurse on each half"),
        ("Merge", "combine sorted halves"),
    ],
}


def _detect_canonical_algorithm(hint: str) -> str:
    """Return a canonical algorithm key for the topic, if known."""
    h = (hint or "").lower()
    bst = _detect_bst_traversal(h)
    if bst:
        return bst
    if "binary search tree" in h or ("bst" in h and "search" in h):
        return "bst_search"
    if "bst insert" in h or ("bst" in h and "insert" in h):
        return "bst_insert"
    if "binary search" in h or h.strip() == "binary search":
        return "binary_search"
    if "bfs" in h or "breadth-first" in h or "breadth first" in h:
        return "bfs"
    if "dfs" in h or "depth-first" in h or "depth first" in h:
        return "dfs"
    if "sliding window" in h or "two pointer" in h:
        return "sliding_window"
    if "merge sort" in h:
        return "merge_sort"
    return ""


def _is_bad_step_label(label: str, *, card_title: str, topic_hint: str) -> bool:
    cleaned = (label or "").strip()
    if not cleaned:
        return True
    lowered = cleaned.lower()
    words = lowered.split()
    if len(words) > 5:
        return True
    if any(fragment in lowered for fragment in _VAGUE_STEP_LABEL_FRAGMENTS):
        return True
    ct_lower = (card_title or "").strip().lower()
    if ct_lower:
        if lowered == ct_lower:
            return True
        # Reject if the label is a prefix/substring of the card title (e.g.
        # "Binary Search Steps Starting" is a prefix of "Binary Search Steps
        # Starting State") — that's a truncated title, not a step action.
        if len(words) >= 3 and (ct_lower.startswith(lowered) or lowered.startswith(ct_lower[:len(lowered)])):
            return True
        # Reject if 3+ consecutive words from the label appear in the title.
        title_lower = ct_lower
        for i in range(len(words) - 2):
            triplet = " ".join(words[i : i + 3])
            if triplet in title_lower:
                return True
    if topic_hint:
        hint_lower = topic_hint.strip().lower()
        if hint_lower and (lowered == hint_lower or lowered in hint_lower):
            if len(words) >= 3:
                return True
    return False


def _sanitize_progressive_step_flow(
    steps: list[dict[str, Any]],
    *,
    card_title: str,
    topic_hint: str,
) -> list[dict[str, Any]]:
    """Replace bad step labels (topic name, duplicates, vague placeholders) with
    canonical algorithm steps when the topic is a known traversal/search/sort."""
    if not steps:
        return steps

    seen_labels: set[str] = set()
    bad_indices: list[int] = []
    for i, step in enumerate(steps):
        label = str(step.get("label") or "")
        lowered = label.strip().lower()
        if _is_bad_step_label(label, card_title=card_title, topic_hint=topic_hint):
            bad_indices.append(i)
            continue
        if lowered in seen_labels:
            bad_indices.append(i)
            continue
        seen_labels.add(lowered)

    # Detect canonical flow to substitute from
    traversal = _detect_bst_traversal(topic_hint)
    canonical = _CANONICAL_STEP_FLOWS.get(traversal) if traversal else None

    # If majority of step labels are bad and we have a canonical flow, swap the entire visual
    if canonical and bad_indices and len(bad_indices) >= max(1, len(steps) // 2):
        active_idx = next((i for i, s in enumerate(steps) if s.get("active")), -1)
        replaced: list[dict[str, Any]] = []
        for i, (lbl, mv) in enumerate(canonical):
            entry = _visual_step_entry(
                lbl,
                "",
                mv,
                index=i,
                active=i == active_idx or (active_idx < 0 and i == 0),
            )
            replaced.append(entry)
        return replaced

    # Otherwise: drop bad individual steps in-place but keep good ones
    if bad_indices:
        kept = [s for i, s in enumerate(steps) if i not in set(bad_indices)]
        if kept:
            return kept

    return steps


def _detect_bst_traversal(hint: str) -> str:
    h = (hint or "").lower()
    if "inorder" in h or "in-order" in h or "in order" in h:
        return "inorder"
    if "preorder" in h or "pre-order" in h or "pre order" in h:
        return "preorder"
    if "postorder" in h or "post-order" in h or "post order" in h:
        return "postorder"
    if "level-order" in h or "level order" in h or "levelorder" in h or "bfs" in h or "breadth" in h:
        return "level_order"
    return ""


_DEFAULT_ARRAYS_BY_ALGORITHM: dict[str, list[str]] = {
    "binary_search": ["1", "3", "5", "8", "10", "12", "15", "18"],
    "merge_sort": ["38", "27", "43", "3", "9", "82", "10"],
    "sliding_window": ["2", "1", "5", "1", "3", "2", "4", "1"],
    "two_pointer": ["1", "2", "3", "4", "5", "6", "7", "8"],
    "prefix_sum": ["3", "1", "4", "1", "5", "9", "2", "6"],
    "quicksort": ["7", "2", "9", "1", "5", "8", "3", "6"],
}

_POINTER_LABEL_PATTERNS: list[tuple[str, str]] = [
    ("low", "top"),
    ("high", "top"),
    ("mid", "bottom"),
    ("left", "top"),
    ("right", "top"),
    ("l", "top"),
    ("r", "top"),
    ("i", "top"),
    ("j", "bottom"),
    ("k", "bottom"),
    ("slow", "bottom"),
    ("fast", "top"),
    ("start", "top"),
    ("end", "top"),
]


def _extract_int_for_label(text: str, label: str) -> int | None:
    """Find the numeric value associated with a pointer label in card text.
    Matches 'low=0', 'low: 0', 'low (0)', 'low is 0'."""
    label_re = re.escape(label)
    for pat in (
        rf"\b{label_re}\s*[=:]\s*(-?\d+)\b",
        rf"\b{label_re}\s*\((-?\d+)\)",
        rf"\b{label_re}\s+(?:is|=|to)\s+(-?\d+)\b",
    ):
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                continue
    return None


def _detect_array_algorithm(hint: str) -> str:
    h = (hint or "").lower()
    if "merge sort" in h:
        return "merge_sort"
    if "quicksort" in h or "quick sort" in h:
        return "quicksort"
    if "sliding window" in h:
        return "sliding_window"
    if "two pointer" in h or "two-pointer" in h:
        return "two_pointer"
    if "prefix sum" in h or "prefix-sum" in h:
        return "prefix_sum"
    if "binary search" in h or re.search(r"search(?:ing)?\s+for\s+\d+\s+in\s+\[", h):
        return "binary_search"
    # Final fallback for any array topic — use the generic sorted array.
    if re.search(r"\[\s*\d+(?:\s*,\s*\d+){1,}\s*\]", hint or ""):
        return "binary_search"
    return ""


def _synthesize_array_state_fallback(
    *,
    topic_hint: str,
    card_points: list[str],
    visual_description: str,
) -> dict[str, Any]:
    """Build default array data when the LLM left array_state_diagram fields
    empty. Pulls pointer positions from the card's text so the visual stays
    aligned with what the bullets describe."""
    algo = _detect_array_algorithm(topic_hint)
    if not algo:
        return {"array_values": [], "array_pointers": [], "array_ranges": [], "array_annotations": []}

    values = list(_DEFAULT_ARRAYS_BY_ALGORITHM[algo])
    max_idx = len(values) - 1

    # Combine all text that might mention pointer positions.
    text = " ".join(card_points) + " " + (visual_description or "")

    pointers: list[dict[str, Any]] = []
    seen_labels: set[str] = set()
    for label, side in _POINTER_LABEL_PATTERNS:
        if label in seen_labels:
            continue
        value = _extract_int_for_label(text, label)
        if value is None:
            continue
        idx = max(0, min(value, max_idx))
        pointers.append({"label": label, "index": idx, "side": side})
        seen_labels.add(label)

    # Compute a sensible range from low/high (or left/right) if both exist.
    ranges: list[dict[str, Any]] = []
    low = next((p["index"] for p in pointers if p["label"] in ("low", "left", "l", "start")), None)
    high = next((p["index"] for p in pointers if p["label"] in ("high", "right", "r", "end")), None)
    if low is not None and high is not None and low <= high:
        ranges.append({"label": "search range", "start": low, "end": high})

    return {
        "array_values": values,
        "array_pointers": pointers[:4],
        "array_ranges": ranges,
        "array_annotations": [],
    }


def _synthesize_node_link_fallback(
    topic_hint: str,
) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[str], str]:
    """Last-resort: produce a sensible structure when LLM labels are unusable.

    Returns (nodes, edges, traversal_path, kind). kind is "bst" or "graph"
    so the caller can write a consistent description and not accidentally
    trigger the frontend's graph-layout heuristic on BST data.
    traversal_path is non-empty only for BST traversal variants.
    """
    # RETIRED (accuracy: never invent a structure). Returning empty makes every caller drop
    # to "no visual" instead of fabricating a graph/tree from keywords. The body below is kept
    # for reference but is unreachable.
    return [], [], [], "none"
    hint = (topic_hint or "").lower()
    graph_kw = any(
        kw in hint
        for kw in ("graph", "mst", "kruskal", "prim", "dijkstra", "shortest", "topological")
    )
    tree_kw = any(kw in hint for kw in ("tree", "bst", "binary search tree", "heap", "trie"))
    is_graph_topic = graph_kw and not tree_kw
    if is_graph_topic:
        # Only include numeric edge labels (weights) for algorithms where the
        # weight is part of the concept. For BFS / DFS / topological sort,
        # leave edges unlabeled — the algorithm operates on the structure,
        # not on weights, and labels would be misread as weights.
        is_weighted_algo = any(
            kw in hint
            for kw in (
                "mst", "minimum spanning tree", "spanning tree",
                "kruskal", "prim", "dijkstra", "shortest path",
                "bellman", "floyd", "a*", "weighted",
            )
        )
        nodes: list[dict[str, Any]] = [
            {"id": "A", "label": "A", "relation": "node", "description": "", "x": 30.0, "y": 25.0},
            {"id": "B", "label": "B", "relation": "node", "description": "", "x": 70.0, "y": 25.0},
            {"id": "C", "label": "C", "relation": "node", "description": "", "x": 18.0, "y": 55.0},
            {"id": "D", "label": "D", "relation": "node", "description": "", "x": 50.0, "y": 55.0},
            {"id": "E", "label": "E", "relation": "node", "description": "", "x": 82.0, "y": 55.0},
            {"id": "F", "label": "F", "relation": "node", "description": "", "x": 35.0, "y": 82.0},
            {"id": "G", "label": "G", "relation": "node", "description": "", "x": 65.0, "y": 82.0},
        ]
        weights = ["4", "2", "5", "3", "1", "6", "2", "4"] if is_weighted_algo else [""] * 8
        edges: list[dict[str, str]] = [
            {"from": "A", "to": "B", "label": weights[0], "style": "solid"},
            {"from": "A", "to": "C", "label": weights[1], "style": "solid"},
            {"from": "B", "to": "D", "label": weights[2], "style": "solid"},
            {"from": "B", "to": "E", "label": weights[3], "style": "solid"},
            {"from": "C", "to": "D", "label": weights[4], "style": "solid"},
            {"from": "D", "to": "F", "label": weights[5], "style": "solid"},
            {"from": "D", "to": "G", "label": weights[6], "style": "solid"},
            {"from": "E", "to": "G", "label": weights[7], "style": "solid"},
        ]
        return nodes, edges, [], "graph"

    # BST fallback. Tree edges stay unlabeled — BSTs are unweighted, so any
    # numeric label on an edge is misread as a weight. The visit_order is
    # still returned and rendered as the "Traversal order" text below the
    # diagram for traversal topics.
    nodes = [dict(n) for n in _DEFAULT_BST_BACKGROUND_NODES]
    traversal = _detect_bst_traversal(topic_hint)
    visit_order = _BST_TRAVERSAL_ORDERS.get(traversal, [])
    edges = [dict(e) for e in _DEFAULT_BST_BACKGROUND_EDGES]
    return nodes, edges, visit_order, "bst"


def _validated_node_link_nodes(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    nodes: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        raw_label = str(item.get("label") or item.get("id") or "").strip()
        label = _normalize_node_data_label(raw_label)
        if not label:
            continue
        nodes.append({
            "id": label,
            "label": label,
            "relation": str(item.get("relation") or "node").strip(),
            "description": str(item.get("description") or "").strip(),
            "state": _normalize_node_state(str(item.get("state") or "")),
            "x": float(item["x"]) if isinstance(item.get("x"), (int, float)) else 50.0,
            "y": float(item["y"]) if isinstance(item.get("y"), (int, float)) else 20.0 + index * 12,
        })
    return nodes[:12]


def _validated_visual_edges(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    edges: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        from_id = _normalize_node_data_label(str(item.get("from") or "").strip())
        to_id = _normalize_node_data_label(str(item.get("to") or "").strip())
        if not from_id or not to_id:
            continue
        edges.append({
            "from": from_id,
            "to": to_id,
            "label": str(item.get("label") or "").strip(),
            "style": str(item.get("style") or "solid").strip(),
            "state": _normalize_edge_state(str(item.get("state") or "")),
        })
    return edges[:20]


def _infer_node_link_from_description(
    description: str,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    text = str(description or "").strip()
    if not text:
        return [], []

    natural_nodes, natural_edges = _infer_tree_from_natural_description(text)
    if natural_nodes and natural_edges:
        return natural_nodes, natural_edges

    root_match = re.search(
        r"\broot\s*[=:]\s*([A-Za-z0-9_.-]+)",
        text,
        flags=re.IGNORECASE,
    )
    root_label = _normalize_node_data_label(root_match.group(1)) if root_match else ""

    relationships: list[tuple[str, list[str]]] = []

    if root_label:
        root_children_match = re.search(
            r"\broot\s*[=:]\s*"
            + re.escape(root_label)
            + r"\s*\([^)]*?\bchildren\s+([^)]+)\)",
            text,
            flags=re.IGNORECASE,
        )
        if root_children_match:
            children = [
                _normalize_node_data_label(child)
                for child in _parse_child_labels(root_children_match.group(1))
            ]
            children = [child for child in children if child]
            if children:
                relationships.append((root_label, children))

    for match in re.finditer(
        r"\b([A-Za-z0-9_.-]+)\s+(?:has\s+)?children\s+([A-Za-z0-9_.\-,\s]+)",
        text,
        flags=re.IGNORECASE,
    ):
        parent = _normalize_node_data_label(match.group(1).strip())
        children = [
            _normalize_node_data_label(child)
            for child in _parse_child_labels(match.group(2))
        ]
        children = [child for child in children if child]
        if parent and children:
            relationships.append((parent, children))

    if not relationships and root_label:
        relationships.append((root_label, []))

    if not relationships:
        return [], []

    labels: list[str] = []
    edges: list[dict[str, str]] = []

    def add_label(label: str) -> None:
        if label and label not in labels:
            labels.append(label)

    for parent, children in relationships:
        add_label(parent)
        for child in children:
            add_label(child)
            edges.append({
                "from": parent,
                "to": child,
                "label": "",
                "style": "solid",
            })

    if not root_label:
        root_label = relationships[0][0]

    levels: dict[str, int] = {root_label: 0}
    changed = True
    while changed:
        changed = False
        for parent, children in relationships:
            parent_level = levels.get(parent)
            if parent_level is None:
                continue
            for child in children:
                child_level = parent_level + 1
                if child not in levels or levels[child] > child_level:
                    levels[child] = child_level
                    changed = True

    for label in labels:
        levels.setdefault(label, 1 if label != root_label else 0)

    labels_by_level: dict[int, list[str]] = {}
    for label in labels[:12]:
        labels_by_level.setdefault(levels.get(label, 0), []).append(label)

    positions: dict[str, tuple[float, float]] = {}
    for level, level_labels in labels_by_level.items():
        count = len(level_labels)
        for index, label in enumerate(level_labels):
            x = 50.0 if count == 1 else 18.0 + (64.0 * index / max(1, count - 1))
            y = min(88.0, 14.0 + level * 22.0)
            positions[label] = (x, y)

    child_ids = {edge["to"] for edge in edges}
    parent_ids = {edge["from"] for edge in edges}
    nodes: list[dict[str, Any]] = []
    for label in labels[:12]:
        node_id = label
        x, y = positions.get(label, (50.0, 20.0 + len(nodes) * 12.0))
        relation = (
            "root"
            if label == root_label
            else "leaf"
            if label not in parent_ids
            else "node"
        )
        nodes.append({
            "id": node_id,
            "label": label,
            "relation": relation,
            "description": "",
            "x": x,
            "y": y,
        })

    valid_node_ids = {node["id"] for node in nodes}
    edges = [
        edge
        for edge in edges[:20]
        if edge["from"] in valid_node_ids and edge["to"] in valid_node_ids
    ]
    if len(nodes) == 1 and not edges:
        return nodes, []
    return nodes, edges


def _infer_tree_from_natural_description(
    text: str,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Recover tree/BST data from prose using the model's concrete values.

    This avoids canonical fallback when the LLM wrote a valid verbal scene but
    malformed visual_nodes, such as labels "right"/"left" instead of values.
    """
    if not re.search(r"\b(bst|tree|root|child|children)\b", text, flags=re.IGNORECASE):
        return [], []

    root = ""
    for pattern in (
        r"\b(\d{1,4})\s*\(\s*root\s*\)",
        r"\b(\d{1,4})\s+root\b",
        r"\broot\s+(?:node\s+|value\s+)?(\d{1,4})\b",
        r"\broot\s*[=:]\s*(\d{1,4})\b",
    ):
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            root = _normalize_node_data_label(match.group(1))
            if root:
                break

    relationships: list[tuple[str, list[str]]] = []

    if root:
        left_match = re.search(r"\b(\d{1,4})\s*\(\s*left\s+child\s*\)", text, flags=re.IGNORECASE)
        right_match = re.search(r"\b(\d{1,4})\s*\(\s*right\s+child\s*\)", text, flags=re.IGNORECASE)
        root_children = [
            _normalize_node_data_label(match.group(1))
            for match in (left_match, right_match)
            if match
        ]
        root_children = [child for child in root_children if child]
        if root_children:
            relationships.append((root, root_children))

    for match in re.finditer(
        r"\b(?:with\s+)?(\d{1,4})\s+(?:having|has)\s+(?:left\s+and\s+right\s+)?children\s+(\d{1,4})\s*(?:,|and)?\s*(?:and\s+)?(\d{1,4})",
        text,
        flags=re.IGNORECASE,
    ):
        parent = _normalize_node_data_label(match.group(1))
        children = [
            _normalize_node_data_label(match.group(2)),
            _normalize_node_data_label(match.group(3)),
        ]
        children = [child for child in children if child]
        if parent and children:
            relationships.append((parent, children))

    if not root and relationships:
        root = relationships[0][0]
    if not root or not relationships:
        return [], []

    labels: list[str] = []
    edges: list[dict[str, str]] = []

    def add_label(value: str) -> None:
        if value and value not in labels:
            labels.append(value)

    for parent, children in relationships:
        add_label(parent)
        for child in children:
            add_label(child)
            edge = {"from": parent, "to": child, "label": "", "style": "solid"}
            if edge not in edges:
                edges.append(edge)

    if len(labels) < 3 or not edges:
        return [], []

    return _layout_tree_nodes_from_edges(labels=labels, edges=edges, root=root), edges


def _layout_tree_nodes_from_edges(
    *,
    labels: list[str],
    edges: list[dict[str, str]],
    root: str,
) -> list[dict[str, Any]]:
    children_by_parent: dict[str, list[str]] = {}
    for edge in edges:
        children_by_parent.setdefault(edge["from"], []).append(edge["to"])

    levels: dict[str, int] = {root: 0}
    queue: list[str] = [root]
    while queue:
        parent = queue.pop(0)
        for child in children_by_parent.get(parent, []):
            if child not in levels:
                levels[child] = levels[parent] + 1
                queue.append(child)

    for label in labels:
        levels.setdefault(label, 1 if label != root else 0)

    labels_by_level: dict[int, list[str]] = {}
    for label in labels[:12]:
        labels_by_level.setdefault(levels[label], []).append(label)

    parent_ids = {edge["from"] for edge in edges}
    nodes: list[dict[str, Any]] = []
    for level, level_labels in sorted(labels_by_level.items()):
        count = len(level_labels)
        for index, label in enumerate(level_labels):
            x = 50.0 if count == 1 else 16.0 + (68.0 * index / max(1, count - 1))
            y = min(88.0, 15.0 + level * 24.0)
            nodes.append({
                "id": label,
                "label": label,
                "relation": "root" if label == root else "node" if label in parent_ids else "leaf",
                "description": "",
                "x": x,
                "y": y,
            })
    return nodes


def _parse_child_labels(value: str) -> list[str]:
    cleaned = re.split(r"[.;]", str(value or ""), maxsplit=1)[0]
    parts = re.split(r",|\band\b", cleaned, flags=re.IGNORECASE)
    labels: list[str] = []
    for part in parts:
        label = part.strip().strip("()[]{}")
        if not label:
            continue
        label = re.sub(r"^(left|right|child|children)\s*[:=]?\s*", "", label, flags=re.IGNORECASE).strip()
        label = re.sub(r"\s+.*$", "", label).strip()
        if label:
            labels.append(label)
    return labels[:4]


def _node_id(label: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", str(label or "").strip()).strip("_")
    return f"node_{cleaned or 'x'}"


def _validated_data_points(value: Any) -> list[list[float]]:
    if not isinstance(value, list):
        return []

    points: list[list[float]] = []
    for item in value:
        if not isinstance(item, list) or len(item) < 2:
            continue
        try:
            x = float(item[0])
            y = float(item[1])
        except (TypeError, ValueError):
            continue
        points.append([x, y])
    return points[:20]


def _validated_key_points(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    key_points: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        try:
            x = float(item.get("x"))
            y = float(item.get("y"))
        except (TypeError, ValueError):
            continue
        label = str(item.get("label") or "").strip()
        if label:
            key_points.append({"x": x, "y": y, "label": label})
    return key_points[:6]


def _validated_array_values(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()][:16]


def _validated_array_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    rows: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        values = _validated_array_values(item.get("values"))
        if not values:
            continue
        label = str(item.get("label") or f"Level {index + 1}").strip()
        rows.append({
            "label": label,
            "values": values,
            "emphasis": bool(item.get("emphasis")),
        })
    return rows[:8]


def _validated_array_pointers(value: Any, *, max_index: int) -> list[dict[str, Any]]:
    if not isinstance(value, list) or max_index < 0:
        return []

    pointers: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        try:
            index = int(item.get("index"))
        except (TypeError, ValueError):
            continue
        if not label or index < 0 or index > max_index:
            continue
        raw_side = str(item.get("side") or "top").strip().lower()
        side = raw_side if raw_side in {"top", "bottom"} else "top"
        pointers.append({"label": label, "index": index, "side": side})
    return pointers[:6]


def _validated_array_ranges(value: Any, *, max_index: int) -> list[dict[str, Any]]:
    if not isinstance(value, list) or max_index < 0:
        return []

    ranges: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        try:
            start = int(item.get("start"))
            end = int(item.get("end"))
        except (TypeError, ValueError):
            continue
        if end < start:
            start, end = end, start
        start = max(0, min(start, max_index))
        end = max(0, min(end, max_index))
        ranges.append({"label": label, "start": start, "end": end})
    return ranges[:4]


def _first_clean_point(points: list[str]) -> str:
    for point in points:
        cleaned = re.sub(r"^\s*-\s*", "", point).strip()
        if cleaned:
            return cleaned
    return ""


def _first_math_like_text(points: list[str]) -> str:
    for point in points:
        cleaned = re.sub(r"^\s*-\s*", "", point).strip()
        if any(token in cleaned for token in ("=", "+", "-", "*", "/", "^", "(", ")")):
            return cleaned
    return ""


def _should_keep_lean_card(lean_card: dict[str, Any]) -> bool:
    blueprint_key = str(lean_card.get("blueprint_key") or "").strip()
    card_type = str(lean_card.get("card_type") or "").strip()

    if blueprint_key == "components_terms" or card_type == "components_terms":
        return _count_main_points(lean_card) >= 3

    return True


_COMPONENTS_AFTER_BACKGROUND_TOPIC_TYPES = {
    "concept_intuition",
    "terminology_components",
    "process_walkthrough",
    "algorithm_walkthrough",
    "data_structure_operation",
    "math_formula_method",
    "proof_reasoning",
    "compare_distinguish",
    "science_mechanism",
    "study_path_introduction",
}


_WALKTHROUGH_TYPES_FOR_CODING_SKIP = frozenset({
    "algorithm_walkthrough",
    "data_structure_operation",
})


def _topic_type_key(topic: Topic) -> str:
    return str(
        getattr(topic, "topic_type", None)
        or getattr(topic, "course_type", None)
        or ""
    ).strip()


def _is_coding_continuation(topic: Topic) -> bool:
    """True when this coding_implementation topic immediately follows an algorithm walkthrough or data structure operation."""
    if _topic_type_key(topic) != "coding_implementation":
        return False
    study_path = getattr(topic, "study_path", None)
    topics = getattr(study_path, "topics", None) if study_path is not None else None
    if not topics:
        return False
    current_id = str(getattr(topic, "id", "") or "").strip()
    if not current_id:
        return False
    ordered = sorted(list(topics), key=lambda t: int(getattr(t, "order_index", 0) or 0))
    prev = None
    for item in ordered:
        if str(getattr(item, "id", "") or "") == current_id:
            break
        prev = item
    else:
        return False
    if prev is None:
        return False
    prev_type = str(
        getattr(prev, "topic_type", None) or getattr(prev, "course_type", None) or ""
    ).strip()
    return prev_type in _WALKTHROUGH_TYPES_FOR_CODING_SKIP


def _lean_card_key(lean_card: dict[str, Any]) -> str:
    return str(
        lean_card.get("blueprint_key")
        or lean_card.get("card_type")
        or ""
    ).strip()


def _move_first_card_with_key(
    cards: list[dict[str, Any]],
    key: str,
    target_index: int,
) -> list[dict[str, Any]]:
    current_index = next(
        (index for index, card in enumerate(cards) if _lean_card_key(card) == key),
        -1,
    )
    if current_index < 0:
        return cards

    target_index = max(0, min(target_index, len(cards) - 1))
    if current_index == target_index:
        return cards

    reordered = list(cards)
    card = reordered.pop(current_index)
    if current_index < target_index:
        target_index -= 1
    reordered.insert(target_index, card)
    return reordered


def _normalize_lean_card_order(
    cards: list[Any],
    topic: Topic,
) -> list[dict[str, Any]]:
    """Repair common model ordering drift while preserving repeated-card order."""
    normalized = [card for card in cards if isinstance(card, dict)]
    if not normalized:
        return []

    normalized = _normalize_lean_card_classification(normalized)
    topic_type = _topic_type_key(topic)

    # Coding implementation topics that immediately follow their algorithm walkthrough
    # must never show a background card — the learner just finished that walkthrough.
    # Strip before any reordering so a model-hallucinated background card is never surfaced.
    if _is_coding_continuation(topic):
        normalized = [c for c in normalized if _lean_card_key(c) != "background"]

    # Background is the learner's first anchor. If the model emits it late, move
    # only the first background card to the front and leave continuations stable.
    normalized = _move_first_card_with_key(normalized, "background", 0)

    if topic_type in _COMPONENTS_AFTER_BACKGROUND_TOPIC_TYPES:
        background_index = next(
            (
                index
                for index, card in enumerate(normalized)
                if _lean_card_key(card) == "background"
            ),
            -1,
        )
        components_index = next(
            (
                index
                for index, card in enumerate(normalized)
                if _lean_card_key(card) == "components_terms"
            ),
            -1,
        )
        if background_index >= 0 and components_index >= 0:
            normalized = _move_first_card_with_key(
                normalized,
                "components_terms",
                background_index + 1,
            )

    # Enforce the topic type's blueprint card set: drop any card whose blueprint_key
    # is not part of this topic type's structure (e.g. a worked_example/edge_case/
    # components card in a study-path intro, which the blueprint forbids).
    normalized = _enforce_blueprint_cards(normalized, topic_type)

    if topic_type == "study_path_introduction":
        # Intro = background(s) then roadmap(s); everything else has been filtered out.
        backgrounds = [c for c in normalized if _lean_card_key(c) == "background"]
        roadmaps = [c for c in normalized if _lean_card_key(c) == "roadmap"]
        others = [c for c in normalized if _lean_card_key(c) not in ("background", "roadmap")]
        normalized = [*backgrounds, *others, *roadmaps]

    return normalized


def _enforce_blueprint_cards(cards: list[dict[str, Any]], topic_type: str) -> list[dict[str, Any]]:
    """Keep only cards whose blueprint_key belongs to this topic type's blueprint
    (default + optional + continuation sequences). Returns the original list if the
    blueprint is unavailable or the filter would remove everything."""
    try:
        from app.core.course_blueprints import get_topic_blueprint

        blueprint = get_topic_blueprint(topic_type)
    except Exception:  # noqa: BLE001
        return cards
    allowed: set[str] = set()
    for key in ("default_card_sequence", "optional_cards", "continuation_card_sequence", "continuation_optional_cards"):
        allowed |= set(blueprint.get(key) or [])
    if not allowed:
        return cards
    filtered = [c for c in cards if _lean_card_key(c) in allowed]
    return filtered if filtered else cards


def _forbidden_key_terms_for_topic(topic: Topic) -> set[str]:
    ledger = build_assumption_ledger(topic=topic)
    forbidden_values = [
        *(ledger.get("assumed_prerequisites") or []),
        *(ledger.get("prior_taught_content") or []),
        *(ledger.get("do_not_reteach") or []),
    ]
    return {
        normalize_assumption_phrase(value)
        for value in forbidden_values
        if normalize_assumption_phrase(value)
    }


_MAX_MAIN_BULLETS_PER_PROCESS_CARD = 4

def _is_main_bullet(point: str) -> bool:
    """True if the point is a top-level (main) bullet, not an indented sub-bullet."""
    return not re.match(r"^\s+-\s+", str(point or ""))


def _count_main_bullets(points: list[str]) -> int:
    return sum(1 for p in points if _is_main_bullet(p))


def _merge_overslit_process_cards(legacy_cards: list[dict[str, Any]]) -> None:
    """If process cards are over-split (1 main bullet per card), merge them
    so each card holds up to _MAX_MAIN_BULLETS_PER_PROCESS_CARD main bullets.
    Groups consecutive process cards together to preserve algorithm ordering.

    Mutates legacy_cards in place.
    """
    # Find contiguous runs of process cards (preserves order so we group
    # consecutive ideas — Starting → Repeated → Stopping → Output stays in order).
    i = 0
    while i < len(legacy_cards):
        key = str(legacy_cards[i].get("blueprint_key") or legacy_cards[i].get("card_type") or "").lower()
        if key != "process":
            i += 1
            continue
        # Scan forward to collect a contiguous run of process cards.
        run_start = i
        while i < len(legacy_cards) and str(
            legacy_cards[i].get("blueprint_key") or legacy_cards[i].get("card_type") or ""
        ).lower() == "process":
            i += 1
        run_end = i
        run = legacy_cards[run_start:run_end]
        if len(run) < 2:
            continue

        total_main = sum(_count_main_bullets(card.get("points") or []) for card in run)
        if total_main <= _MAX_MAIN_BULLETS_PER_PROCESS_CARD:
            # Merge entire run into ONE card.
            merged = _merge_process_card_run(run)
            legacy_cards[run_start:run_end] = [merged]
            i = run_start + 1
            continue

        # Multiple cards needed. Decide a target card count so each card holds
        # roughly _MAX main bullets (rounded up).
        target_cards = max(2, -(-total_main // _MAX_MAIN_BULLETS_PER_PROCESS_CARD))
        if target_cards >= len(run):
            # Already split fine enough; leave alone.
            continue
        # Partition the run greedily — pack main bullets up to the max per card,
        # always cutting on card boundaries to preserve sub-bullet grouping.
        new_run: list[dict[str, Any]] = []
        bucket: list[dict[str, Any]] = []
        bucket_main = 0
        for card in run:
            card_main = _count_main_bullets(card.get("points") or [])
            if bucket and bucket_main + card_main > _MAX_MAIN_BULLETS_PER_PROCESS_CARD:
                new_run.append(_merge_process_card_run(bucket))
                bucket = []
                bucket_main = 0
            bucket.append(card)
            bucket_main += card_main
        if bucket:
            new_run.append(_merge_process_card_run(bucket))
        if len(new_run) < len(run):
            legacy_cards[run_start:run_end] = new_run
            i = run_start + len(new_run)


def _merge_process_card_run(cards: list[dict[str, Any]]) -> dict[str, Any]:
    """Combine a sequence of consecutive process cards into one card by
    concatenating their points. Keeps the first card's title and meta fields."""
    if len(cards) == 1:
        return cards[0]
    base = dict(cards[0])
    combined_points: list[str] = []
    for card in cards:
        for point in (card.get("points") or []):
            combined_points.append(str(point))
    base["points"] = combined_points
    # Carry over visual from the first card (it gets re-unified below anyway).
    return base


def _ensure_progressive_step_flow_steps(
    legacy_cards: list[dict[str, Any]],
    *,
    topic_hint: str,
) -> None:
    """Backstop: for ANY card whose visual is `progressive_step_flow` with empty
    `steps`, inject the canonical step flow for the detected algorithm. This
    prevents the frontend from inferring labels off the description text — which
    truncates mid-phrase (e.g. 'the edge with the') and locks the active
    step to 0 (because every inferred step gets active=stepIndex===0).
    """
    algo = _detect_canonical_algorithm(topic_hint)
    canonical = _CANONICAL_STEP_FLOWS.get(algo) if algo else None
    if not canonical:
        return
    for card in legacy_cards:
        visual = card.get("visual_plan")
        if not isinstance(visual, dict):
            continue
        if visual.get("type") != "progressive_step_flow":
            continue
        if visual.get("steps"):
            continue
        visual["steps"] = [
            _visual_step_entry(lbl, "", mv, index=i, active=(i == 0))
            for i, (lbl, mv) in enumerate(canonical)
        ]


def _apply_canonical_steps_to_single_process_card(
    card: dict[str, Any],
    *,
    topic_hint: str,
) -> None:
    """Align a single process card's visual_steps with its main bullets.

    Canonical algorithm steps are only a fallback. The primary rule is that
    the visual should track the learner-facing text frames on the card.
    """
    point_steps = _progressive_steps_from_card_points(card)
    algo = _detect_canonical_algorithm(topic_hint)
    canonical = _CANONICAL_STEP_FLOWS.get(algo) if algo else None
    if not point_steps and not canonical:
        return
    steps = point_steps or [
        _visual_step_entry(lbl, "", mv, index=i, active=i == 0)
        for i, (lbl, mv) in enumerate(canonical or [])
    ]
    visual = card.get("visual_plan")
    if not isinstance(visual, dict):
        return
    visual["type"] = "progressive_step_flow"
    visual["steps"] = steps
    focus = card.get("visual_focus")
    if not isinstance(focus, dict):
        focus = {}
        card["visual_focus"] = focus
    focus["active_step"] = 0


_EDGE_CASE_TRACE_MARKERS = ("call stack", "current:", "output:", "stack:", "queue:", "call stack:")


def _strip_misplaced_code_visuals(legacy_cards: list[dict[str, Any]]) -> None:
    """Remove code-trace visuals from cards that must not show code — only
    code_walkthrough and worked_example cards carry one. Fixes components_terms /
    process / background cards rendering an empty code panel. Mutates in place.
    """
    for card in legacy_cards:
        key = str(card.get("blueprint_key") or card.get("card_type") or "").lower()
        if key in ("code_walkthrough", "worked_example"):
            continue
        visual = card.get("visual_plan") if isinstance(card.get("visual_plan"), dict) else {}
        vtype = str(card.get("visual_type") or "").lower()
        plan_type = str(visual.get("type") or "").lower()
        if not (vtype in ("code_trace", "code") or plan_type in ("code_trace", "code") or visual.get("code")):
            continue
        card["visual_type"] = "none"
        card["code_snippet"] = ""
        card["highlight_lines_per_step"] = []
        if isinstance(card.get("visual_plan"), dict):
            card["visual_plan"] = {}
        card["styled_elements"] = [
            e for e in (card.get("styled_elements") or [])
            if str((e or {}).get("type") if isinstance(e, dict) else "").lower() != "code_trace"
        ]


def _drop_trace_style_edge_cases(legacy_cards: list[dict[str, Any]]) -> None:
    """Remove edge_case cards that are actually worked-example TRACE STEPS — a
    running-state bullet (call stack / current / output) or a "Visit N" / "Reaching
    … Node N" / "Step N" title. These violate the edge-case card shape (an edge case
    DESCRIBES a boundary, it does not trace it) and duplicate a step the worked
    example already showed. Mutates in place.
    """
    def key(card: dict[str, Any]) -> str:
        return str(card.get("blueprint_key") or card.get("card_type") or "").lower()

    kept: list[dict[str, Any]] = []
    for card in legacy_cards:
        if key(card) == "edge_case":
            title = str(card.get("title") or "").lower()
            points_text = " ".join(str(p) for p in (card.get("points") or [])).lower()
            is_trace_step = (
                re.search(r"\bstep\s+\d+\b", title) is not None
                or re.search(r"\bvisit\s+\w+", title) is not None
                or re.search(r"reaching\b.*\bnode\b", title) is not None
                or any(marker in points_text for marker in _EDGE_CASE_TRACE_MARKERS)
            )
            if is_trace_step:
                continue  # redundant trace masquerading as an edge case — drop it
        kept.append(card)
    legacy_cards[:] = kept


def _group_edge_cases_after_worked_examples(legacy_cards: list[dict[str, Any]]) -> None:
    """Edge-case cards must come AFTER the complete worked example, never spliced
    BETWEEN its step cards. Moves any edge_case card that sits before the last
    worked_example card to just after the worked-example block. Mutates in place.
    """
    def key(card: dict[str, Any]) -> str:
        return str(card.get("blueprint_key") or card.get("card_type") or "").lower()

    worked_indices = [i for i, c in enumerate(legacy_cards) if key(c) == "worked_example"]
    if not worked_indices:
        return
    last_we = worked_indices[-1]
    moved = [c for i, c in enumerate(legacy_cards) if key(c) == "edge_case" and i < last_we]
    if not moved:
        return
    kept = [c for i, c in enumerate(legacy_cards) if not (key(c) == "edge_case" and i < last_we)]
    insert_at = max(i for i, c in enumerate(kept) if key(c) == "worked_example") + 1
    legacy_cards[:] = kept[:insert_at] + moved + kept[insert_at:]


def _unify_process_card_steps(
    legacy_cards: list[dict[str, Any]],
    *,
    topic_hint: str,
) -> None:
    """Make all process cards in a topic share the SAME visual_steps array so
    the step-flow visual stays connected as the learner navigates between cards.
    Each card highlights a different step via visual_focus.active_step.

    Mutates legacy_cards in place.
    """
    # First, merge any over-split process cards (1-bullet-per-card situations).
    _merge_overslit_process_cards(legacy_cards)

    process_cards = [
        c for c in legacy_cards
        if str(c.get("blueprint_key") or c.get("card_type") or "").lower() == "process"
    ]
    if len(process_cards) < 2:
        # After merging there may be a single process card. Still unify its
        # visual_steps to use canonical labels when we can detect the algorithm.
        if len(process_cards) == 1:
            _apply_canonical_steps_to_single_process_card(process_cards[0], topic_hint=topic_hint)
        return

    # Prefer learner-facing main bullet groups. Canonical algorithm steps are
    # only a fallback when the card text has no usable main bullets.
    point_steps: list[dict[str, Any]] = []
    for card in process_cards:
        point_steps.extend(_progressive_steps_from_card_points(card))

    algo = _detect_canonical_algorithm(topic_hint)
    canonical = _CANONICAL_STEP_FLOWS.get(algo) if algo else None

    unified_steps: list[dict[str, Any]]
    if point_steps:
        unified_steps = [
            _visual_step_entry(
                str(step.get("label") or "").strip(),
                "",
                str(step.get("mini_visual") or "").strip(),
                index=step_index,
                kind=str(step.get("kind") or ""),
            )
            for step_index, step in enumerate(point_steps)
            if str(step.get("label") or "").strip()
        ]
    elif canonical:
        unified_steps = [
            _visual_step_entry(lbl, "", mv, index=i)
            for i, (lbl, mv) in enumerate(canonical)
        ]
    else:
        seen: set[str] = set()
        unified_steps = []
        for card in process_cards:
            visual = card.get("visual_plan") or {}
            for step in (visual.get("steps") or []):
                label = str(step.get("label") or "").strip()
                if not label:
                    continue
                key = label.lower()
                if key in seen:
                    continue
                seen.add(key)
                unified_steps.append(
                    _visual_step_entry(
                        label,
                        "",
                        str(step.get("mini_visual") or "").strip(),
                        index=len(unified_steps),
                        kind=str(step.get("kind") or ""),
                    )
                )
        if not unified_steps:
            return

    # Assign each process card a starting visual-step index based on how many
    # main bullets the previous cards covered. The frontend then advances the
    # active step from this offset as main bullets reveal within the card.
    last_index = len(unified_steps) - 1
    cumulative_main = 0
    for card in process_cards:
        active_index = min(cumulative_main, last_index)
        steps_copy = [
            {**step, "active": (i == active_index)}
            for i, step in enumerate(unified_steps)
        ]
        visual = card.get("visual_plan")
        if not isinstance(visual, dict):
            continue
        # Force the type to progressive_step_flow so the connected step-flow
        # renderer is used (not an isolated chip strip).
        visual["type"] = "progressive_step_flow"
        visual["steps"] = steps_copy
        # Update visual_focus.active_step too so the highlight is consistent
        # whether the frontend reads from focus or from step.active.
        focus = card.get("visual_focus")
        if not isinstance(focus, dict):
            focus = {}
            card["visual_focus"] = focus
        focus["active_step"] = active_index
        # Advance the running counter by this card's main-bullet count so the
        # next card picks up where this one left off in the unified step flow.
        cumulative_main += max(1, _count_main_bullets(card.get("points") or []))


_COMPLETION_OVERLAY_TOPIC_TYPES = frozenset({
    "algorithm_walkthrough",
    "coding_implementation",
    "science_mechanism",
    "study_path_introduction",
    "data_structure_operation",
    "process_walkthrough",
})


# Default visit orders on the synthesizer's canonical 7-node graph
# (edges A-B, A-C, B-D, B-E, C-D, D-F, D-G, E-G).
_GRAPH_BFS_FROM_A: list[str] = ["A", "B", "C", "D", "E", "F", "G"]
_GRAPH_DFS_FROM_A: list[str] = ["A", "B", "D", "F", "G", "E", "C"]

# Sample paths through the synthesizer's 7-node BST 50/30/70/20/40/60/80.
_BST_SEARCH_PATH = ["50", "30", "40"]   # search for 40
_BST_INSERT_PATH = ["50", "70", "80"]   # path walked while inserting a leaf


def _graph_traversal_kind(topic_hint: str) -> str:
    h = (topic_hint or "").lower()
    if any(token in h for token in ("bst", "binary search tree", "binary tree", "tree traversal", " tree")):
        return ""
    is_graphish = any(token in h for token in ("graph", "vertex", "vertices", "neighbor", "edge"))
    if not is_graphish and not any(token in h for token in ("dfs", "bfs", "depth-first", "breadth-first", "depth first", "breadth first")):
        return ""
    if "bfs" in h or "breadth-first" in h or "breadth first" in h:
        return "bfs"
    if "dfs" in h or "depth-first" in h or "depth first" in h:
        return "dfs"
    return ""


def _replace_graph_traversal_worked_examples_with_trace(
    legacy_cards: list[dict[str, Any]],
    *,
    topic_hint: str,
) -> None:
    """Use code-generated graph traversal states for BFS/DFS examples.

    The LLM is good at explaining a state, but it is unreliable as the state
    execution engine. For graph traversal, generate the stack/queue/visited
    states deterministically, then render text and visuals from that trace.
    """
    kind = _graph_traversal_kind(topic_hint)
    if kind not in {"dfs", "bfs"}:
        return

    worked_indices = [
        index for index, card in enumerate(legacy_cards)
        if _legacy_card_key(card) == "worked_example"
    ]
    if not worked_indices:
        return

    nodes, edges = _graph_trace_structure_from_cards(
        [legacy_cards[index] for index in worked_indices],
        topic_hint=topic_hint,
    )
    trace = _simulate_graph_traversal(kind, nodes=nodes, edges=edges)
    if len(trace) < 5:
        fallback_nodes, fallback_edges, _, graph_kind = _synthesize_node_link_fallback(topic_hint)
        if graph_kind != "graph":
            return
        nodes, edges = fallback_nodes, fallback_edges
        trace = _simulate_graph_traversal(kind, nodes=nodes, edges=edges)
    if not trace:
        return

    first_index = worked_indices[0]
    last_index = worked_indices[-1]
    replacement_cards = [
        _graph_trace_card(
            step,
            step_index=index,
            kind=kind,
            nodes=nodes,
            edges=edges,
            topic_hint=topic_hint,
        )
        for index, step in enumerate(trace)
    ]
    legacy_cards[first_index : last_index + 1] = replacement_cards


def _graph_trace_structure_from_cards(
    cards: list[dict[str, Any]],
    *,
    topic_hint: str,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    for card in cards:
        visual = card.get("visual_plan")
        if not isinstance(visual, dict) or visual.get("type") != "node_link_diagram":
            continue
        nodes = _validated_node_link_nodes(visual.get("nodes") or [])
        edges = _validated_visual_edges(visual.get("edges") or [])
        if len(nodes) >= 5 and len(edges) >= 4:
            return nodes, edges

    nodes, edges, _, graph_kind = _synthesize_node_link_fallback(topic_hint)
    if graph_kind == "graph":
        return nodes, edges
    return [], []


def _simulate_graph_traversal(
    kind: str,
    *,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, str]],
) -> list[dict[str, Any]]:
    labels = sorted({
        str(node.get("label") or node.get("id") or "").strip()
        for node in nodes
        if str(node.get("label") or node.get("id") or "").strip()
    })
    if not labels:
        return []
    adjacency = _graph_adjacency(labels=labels, edges=edges)
    start = "A" if "A" in labels else labels[0]

    if kind == "bfs":
        return _simulate_bfs_trace(start=start, adjacency=adjacency)
    return _simulate_dfs_trace(start=start, adjacency=adjacency)


def _graph_adjacency(
    *,
    labels: list[str],
    edges: list[dict[str, str]],
) -> dict[str, list[str]]:
    adjacency: dict[str, set[str]] = {label: set() for label in labels}
    valid = set(labels)
    for edge in edges:
        source = _normalize_node_data_label(str(edge.get("from") or ""))
        target = _normalize_node_data_label(str(edge.get("to") or ""))
        if source not in valid or target not in valid:
            continue
        adjacency[source].add(target)
        adjacency[target].add(source)
    return {label: sorted(neighbors) for label, neighbors in adjacency.items()}


def _simulate_dfs_trace(
    *,
    start: str,
    adjacency: dict[str, list[str]],
) -> list[dict[str, Any]]:
    stack = [start]
    visited = {start}
    output: list[str] = []
    steps: list[dict[str, Any]] = []

    while stack:
        stack_before = list(stack)
        current = stack.pop()
        stack_after_pop = list(stack)
        neighbors = list(adjacency.get(current, []))
        newly_discovered = [node for node in neighbors if node not in visited]
        newly_pushed = list(reversed(newly_discovered))
        for node in newly_discovered:
            visited.add(node)
        stack.extend(newly_pushed)
        output.append(current)
        steps.append({
            "action": "pop",
            "frontier_name": "stack",
            "frontier_top": "right",
            "current": current,
            "popped": current,
            "stack_before": stack_before,
            "stack_after_pop": stack_after_pop,
            "neighbors_checked": neighbors,
            "newly_pushed": newly_pushed,
            "stack_after": list(stack),
            "visited_after": sorted(visited),
            "output_after": list(output),
        })
    return steps


def _simulate_bfs_trace(
    *,
    start: str,
    adjacency: dict[str, list[str]],
) -> list[dict[str, Any]]:
    queue = [start]
    visited = {start}
    output: list[str] = []
    steps: list[dict[str, Any]] = []

    while queue:
        queue_before = list(queue)
        current = queue.pop(0)
        queue_after_dequeue = list(queue)
        neighbors = list(adjacency.get(current, []))
        newly_enqueued = [node for node in neighbors if node not in visited]
        for node in newly_enqueued:
            visited.add(node)
        queue.extend(newly_enqueued)
        output.append(current)
        steps.append({
            "action": "dequeue",
            "frontier_name": "queue",
            "frontier_top": "left",
            "current": current,
            "dequeued": current,
            "queue_before": queue_before,
            "queue_after_dequeue": queue_after_dequeue,
            "neighbors_checked": neighbors,
            "newly_enqueued": newly_enqueued,
            "queue_after": list(queue),
            "visited_after": sorted(visited),
            "output_after": list(output),
        })
    return steps


def _graph_trace_card(
    step: dict[str, Any],
    *,
    step_index: int,
    kind: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, str]],
    topic_hint: str,
) -> dict[str, Any]:
    current = str(step.get("current") or "")
    title = f"Visit Node {current}" if current else f"Trace Step {step_index + 1}"
    points = _graph_trace_points(step, kind=kind)
    completed_nodes = {str(item) for item in (step.get("output_after") or []) if str(item) != current}
    visited_nodes = {str(item) for item in (step.get("visited_after") or [])}
    newly_discovered = {
        str(item)
        for item in (step.get("newly_pushed") or step.get("newly_enqueued") or [])
    }
    graph_nodes = []
    for node in nodes:
        copied = dict(node)
        label = str(copied.get("label") or copied.get("id") or "")
        relation = str(copied.get("relation") or "node")
        relation = re.sub(r"\b(current|active)\b", "", relation, flags=re.IGNORECASE).strip() or "node"
        if label == current:
            relation = f"{relation} current".strip()
            copied["state"] = "current"
        elif label in newly_discovered:
            copied["state"] = "newly_discovered"
        elif label in completed_nodes:
            copied["state"] = "completed"
        elif label in visited_nodes:
            copied["state"] = "discovered"
        else:
            copied["state"] = "unvisited"
        copied["relation"] = relation
        graph_nodes.append(copied)

    output_after = [str(item) for item in (step.get("output_after") or [])]
    graph_edges = [
        _graph_trace_edge_with_state(edge, step=step, current=current)
        for edge in edges
    ]
    visual_plan = {
        "type": "node_link_diagram",
        "title": title,
        "purpose": f"Verified {kind.upper()} state step {step_index + 1}.",
        "description": _graph_trace_visual_description(step, kind=kind),
        "placement": "card",
        "what_to_notice": _graph_trace_visual_description(step, kind=kind),
        "common_mistake": "",
        "x_label": "",
        "y_label": "",
        "data_points": [],
        "key_points": [],
        "array_values": [],
        "array_rows": [],
        "array_pointers": [],
        "array_ranges": [],
        "array_annotations": [],
        "nodes": graph_nodes,
        "edges": graph_edges,
        "traversal_path": output_after,
        "components": [],
        "wires": [],
        "code": "",
        "language": "",
        "columns": [],
        "rows": [],
        "highlight_row": -1,
        "steps": [],
        "center": "",
        "labels": [],
        "formula": "",
        "symbols": [],
        "when_to_use": "",
        "wrong": "",
        "correct": "",
        "wrong_label": "",
        "correct_label": "",
        "why": "",
        "counterexample": "",
    }

    focus = {
        "active_nodes": [current] if current else [],
        "highlight_path": output_after,
        "attention_note": _graph_trace_visual_description(step, kind=kind),
        "active_step": 0,
    }
    return {
        "id": f"graph-{kind}-trace-{step_index + 1}",
        "blueprint_key": "worked_example",
        "card_type": "worked_example",
        "title": title,
        "points": points,
        "body": [],
        "bullets": [],
        "main_concept": f"{kind.upper()} verified trace step",
        "learning_goal": f"Trace {kind.upper()} with consistent state updates.",
        "example_type": "state_trace_example",
        "visual_type": "node_link_diagram",
        "new_concepts": [],
        "review_concepts": [],
        "prerequisite_concepts": [],
        "common_misconceptions": [],
        "concept_support": [],
        "interactive_links": [],
        "styled_elements": [],
        "visual_plan": visual_plan,
        "visual_description": _graph_trace_visual_description(step, kind=kind),
        "visual_index": -1,
        "annotations": [],
        "example": "",
        "micro_check": _EMPTY_MICRO_CHECK.copy(),
        "what_to_notice": focus["attention_note"],
        "next_transition": "",
        "estimated_seconds": 45,
        "transition_text": "",
        "next_card_label": "Next",
        "practice_question_index": -1,
        "code_snippet": "",
        "code_language": "python",
        "highlight_lines_per_step": [],
        "visual_focus": focus,
        "execution_trace": {
            "example_type": f"{kind}_graph_traversal",
            "convention": _graph_trace_convention(kind),
            "step": step_index + 1,
            "state": step,
            "topic_hint": topic_hint,
        },
    }


def _graph_trace_edge_with_state(
    edge: dict[str, str],
    *,
    step: dict[str, Any],
    current: str,
) -> dict[str, str]:
    copied = dict(edge)
    source = str(copied.get("from") or "")
    target = str(copied.get("to") or "")
    endpoints = {source, target}
    newly_discovered = {
        str(item)
        for item in (step.get("newly_pushed") or step.get("newly_enqueued") or [])
    }
    neighbors_checked = {str(item) for item in (step.get("neighbors_checked") or [])}
    completed = {str(item) for item in (step.get("output_after") or []) if str(item) != current}

    if current and current in endpoints:
        other = target if source == current else source
        if other in newly_discovered:
            copied["state"] = "active"
            copied["style"] = "traversal"
        elif other in neighbors_checked:
            copied["state"] = "checked"
            copied["style"] = "checked"
        else:
            copied["state"] = "unchecked"
            copied["style"] = str(copied.get("style") or "solid")
    elif source in completed and target in completed:
        copied["state"] = "completed"
        copied["style"] = "completed"
    else:
        copied["state"] = _normalize_edge_state(str(copied.get("state") or copied.get("style") or ""))
        copied["style"] = str(copied.get("style") or "solid")

    return copied


def _graph_trace_convention(kind: str) -> dict[str, str]:
    if kind == "bfs":
        return {
            "queue_front": "left",
            "visited_when": "enqueued",
            "neighbor_order": "alphabetical",
            "enqueue_order": "alphabetical",
        }
    return {
        "stack_top": "right",
        "visited_when": "pushed",
        "neighbor_order": "alphabetical",
        "push_order": "reverse_alphabetical",
    }


def _graph_trace_points(step: dict[str, Any], *, kind: str) -> list[str]:
    if kind == "bfs":
        current = step["current"]
        return [
            "Currently:",
            f"  - queue before dequeue: {_format_trace_list(step.get('queue_before'))} (front=left)",
            f"  - visited before update: {_format_trace_set(_visited_before_from_step(step, 'newly_enqueued'))}",
            f"Dequeue {current} from the queue:",
            "  - the leftmost item is the queue front, so it is processed next",
            f"Check {current}'s neighbors:",
            f"  - considered in alphabetical order: {_format_trace_list(step.get('neighbors_checked'))}",
            f"  - newly enqueued: {_format_trace_list(step.get('newly_enqueued'))}",
            "Now:",
            f"  - queue={_format_trace_list(step.get('queue_after'))}",
            f"  - visited={_format_trace_set(step.get('visited_after'))}",
            f"  - output={_format_trace_list(step.get('output_after'))}",
        ]

    current = step["current"]
    return [
        "Currently:",
        f"  - stack before pop: {_format_trace_list(step.get('stack_before'))} (top=right)",
        f"  - visited before update: {_format_trace_set(_visited_before_from_step(step, 'newly_pushed'))}",
        f"Pop {current} from the stack:",
        "  - the rightmost item is the stack top, so it is processed next",
        f"Check {current}'s neighbors:",
        f"  - considered in alphabetical order: {_format_trace_list(step.get('neighbors_checked'))}",
        f"  - newly pushed in reverse order: {_format_trace_list(step.get('newly_pushed'))}",
        "Now:",
        f"  - stack={_format_trace_list(step.get('stack_after'))}",
        f"  - visited={_format_trace_set(step.get('visited_after'))}",
        f"  - output={_format_trace_list(step.get('output_after'))}",
    ]


def _visited_before_from_step(step: dict[str, Any], pushed_key: str) -> list[str]:
    visited_after = set(str(item) for item in (step.get("visited_after") or []))
    newly_pushed = set(str(item) for item in (step.get(pushed_key) or []))
    return sorted(visited_after - newly_pushed)


def _format_trace_list(value: Any) -> str:
    items = [str(item) for item in (value or [])]
    return "[" + ", ".join(items) + "]"


def _format_trace_set(value: Any) -> str:
    items = [str(item) for item in (value or [])]
    return "{" + ", ".join(items) + "}"


def _graph_trace_visual_description(step: dict[str, Any], *, kind: str) -> str:
    current = str(step.get("current") or "")
    if kind == "bfs":
        return f"Node {current} is dequeued; queue becomes {_format_trace_list(step.get('queue_after'))}."
    return f"Node {current} is popped; stack becomes {_format_trace_list(step.get('stack_after'))}."


def _add_completion_state_to_background_cards(
    legacy_cards: list[dict[str, Any]],
    *,
    topic_hint: str,
    topic_type: str,
) -> None:
    """Overlay the FINAL/converged state of an algorithm on the background
    card's visual.

    POLICY: this overlay only fires when the card EXPLICITLY OPTS IN by
    setting `visual_focus.show_completion = true` OR `visual_plan.show_completion = true`.

    Why this is now opt-in: showing the converged state on a background
    card can spoil the worked example below it. For binary search, marking
    "found at index 4" on the intro visual removes the surprise from the
    trace. For graph traversal, putting the visit order on the static graph
    makes the worked_example feel like a re-read. Background visuals
    USUALLY work best when they show the input structure at rest — the
    process's effect belongs in the worked_example or a "completion" card.

    Cards that genuinely want the completed-state overlay (a "what does
    this algorithm produce?" intro that summarizes the output) can request
    it by emitting the show_completion flag.

    Coverage when enabled:
      - array_state_diagram: binary_search, two_pointer, sliding_window,
        quicksort, merge_sort (annotation only — multi-row already shows progress)
      - node_link_diagram: BST inorder/preorder/postorder/level_order,
        BFS, DFS, BST search, BST insert
    Skips when the LLM already supplied pointers / edge labels.
    """
    if topic_type not in _COMPLETION_OVERLAY_TOPIC_TYPES:
        return

    background_cards = [
        c for c in legacy_cards
        if str(c.get("blueprint_key") or "").lower() == "background"
    ]
    if not background_cards:
        return

    for card in background_cards:
        visual = card.get("visual_plan")
        if not isinstance(visual, dict):
            continue

        # Opt-in check: skip cards that didn't explicitly request the
        # completion overlay. This prevents spoiling the worked_example
        # by giving away the final state on the intro card.
        focus = card.get("visual_focus") or {}
        if not (
            bool(focus.get("show_completion")) if isinstance(focus, dict) else False
        ) and not bool(visual.get("show_completion")):
            continue

        vtype = visual.get("type")
        if vtype == "array_state_diagram":
            _overlay_array_completion(visual, topic_hint=topic_hint)
        elif vtype == "node_link_diagram":
            _overlay_node_link_completion(visual, card, topic_hint=topic_hint)


def _overlay_array_completion(visual: dict[str, Any], *, topic_hint: str) -> None:
    """Dispatcher for array algorithms — picks per-algorithm overlay or
    falls back to a generic 'process complete' annotation."""
    if visual.get("array_pointers"):
        return
    algo = _detect_array_algorithm(topic_hint)
    if algo == "binary_search":
        _overlay_binary_search_completion(visual)
    elif algo == "two_pointer":
        _overlay_two_pointer_completion(visual)
    elif algo == "sliding_window":
        _overlay_sliding_window_completion(visual)
    elif algo == "quicksort":
        _overlay_quicksort_completion(visual)
    elif algo == "merge_sort":
        # Merge sort backgrounds use array_rows (before/split/merged), which
        # already shows the progression. Just add an explanatory annotation.
        _add_annotation(visual, "Bottom row shows the fully merged result")
    elif algo == "prefix_sum":
        _add_annotation(visual, "Prefix sums computed across the array")


def _overlay_node_link_completion(
    visual: dict[str, Any],
    card: dict[str, Any],
    *,
    topic_hint: str,
) -> None:
    """Dispatcher for node-link algorithms — picks per-algorithm overlay."""
    edges = visual.get("edges") or []
    nodes = visual.get("nodes") or []
    if not edges or not nodes:
        return
    # Skip if every edge already labeled.
    if all(str(e.get("label") or "").strip() for e in edges):
        return

    # 1. BST traversals (inorder/preorder/postorder/level_order)
    bst_trav = _detect_bst_traversal(topic_hint)
    if bst_trav:
        _overlay_traversal_completion(visual, card, traversal=bst_trav)
        return

    # 2. Detect graph / BST operation
    h = (topic_hint or "").lower()
    is_graph = "graph" in h and "bst" not in h and "tree" not in h
    visit_order: list[str] = []
    note_template = ""

    if is_graph and ("bfs" in h or "breadth" in h):
        visit_order = list(_GRAPH_BFS_FROM_A)
        note_template = "The order shows when each vertex is visited by BFS from A."
    elif is_graph and ("dfs" in h or "depth" in h):
        visit_order = list(_GRAPH_DFS_FROM_A)
        note_template = "The order shows when each vertex is visited by DFS from A."
    elif "bst" in h and ("search" in h or "find" in h or "lookup" in h):
        visit_order = list(_BST_SEARCH_PATH)
        note_template = "Bottom path traces the search route from root to the found node."
    elif "bst" in h and ("insert" in h or "add" in h):
        visit_order = list(_BST_INSERT_PATH)
        note_template = "Bottom path traces the route walked while inserting the leaf."
    else:
        return

    # Show the visit/path order as the bottom text, but DON'T add numeric edge
    # labels — these algorithms operate on unweighted structures and edge
    # numbers would be misread as weights.
    if not visual.get("traversal_path"):
        node_labels = {str(n.get("label") or "") for n in nodes}
        visual["traversal_path"] = [v for v in visit_order if v in node_labels]
    focus = card.get("visual_focus")
    if not isinstance(focus, dict):
        focus = {}
        card["visual_focus"] = focus
    if not focus.get("attention_note"):
        focus["attention_note"] = note_template


def _label_edges_with_visit_order(
    visual: dict[str, Any],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    visit_order: list[str],
) -> None:
    """Label each edge with the visit number of its child node, preserving any
    label the LLM already set."""
    visit_pos = {value: i + 1 for i, value in enumerate(visit_order)}
    node_labels = {str(n.get("label") or "") for n in nodes}
    for edge in edges:
        if str(edge.get("label") or "").strip():
            continue
        child = str(edge.get("to") or "")
        if child in visit_pos and child in node_labels:
            edge["label"] = str(visit_pos[child])


def _add_annotation(visual: dict[str, Any], text: str) -> None:
    annotations = list(visual.get("array_annotations") or [])
    if text not in annotations:
        annotations.insert(0, text)
    visual["array_annotations"] = annotations[:6]


def _overlay_two_pointer_completion(visual: dict[str, Any]) -> None:
    """Pointers converged from both ends meeting in the middle."""
    array_values = list(visual.get("array_values") or [])
    if not array_values and visual.get("array_rows"):
        array_values = list((visual.get("array_rows") or [{}])[0].get("values") or [])
        if array_values:
            visual["array_values"] = array_values
    if not array_values:
        return
    mid = len(array_values) // 2
    visual["array_pointers"] = [
        {"label": "left", "index": mid, "side": "top"},
        {"label": "right", "index": mid, "side": "bottom"},
    ]
    _add_annotation(visual, "Pointers met — pair search complete")


def _overlay_sliding_window_completion(visual: dict[str, Any]) -> None:
    """Window settled at its best position covering ~3 consecutive elements
    in the middle of the array."""
    array_values = list(visual.get("array_values") or [])
    if not array_values and visual.get("array_rows"):
        array_values = list((visual.get("array_rows") or [{}])[0].get("values") or [])
        if array_values:
            visual["array_values"] = array_values
    if not array_values:
        return
    n = len(array_values)
    width = max(2, min(3, n // 2))
    start = max(0, (n - width) // 2)
    end = min(n - 1, start + width - 1)
    visual["array_pointers"] = [
        {"label": "left", "index": start, "side": "top"},
        {"label": "right", "index": end, "side": "top"},
    ]
    visual["array_ranges"] = [
        {"label": "best window", "start": start, "end": end},
    ]
    _add_annotation(visual, "Window stopped at the best valid position")


def _overlay_quicksort_completion(visual: dict[str, Any]) -> None:
    """Array sorted in place after all partitions — pivot landed at its
    final index (centre)."""
    array_values = list(visual.get("array_values") or [])
    if not array_values and visual.get("array_rows"):
        array_values = list((visual.get("array_rows") or [{}])[0].get("values") or [])
        if array_values:
            visual["array_values"] = array_values
    if not array_values:
        return
    pivot_idx = len(array_values) // 2
    visual["array_pointers"] = [
        {"label": "pivot", "index": pivot_idx, "side": "bottom"},
    ]
    _add_annotation(visual, "Array sorted in place — pivots fixed at final indices")


def _overlay_binary_search_completion(visual: dict[str, Any]) -> None:
    """For a binary-search background visual, place low/mid/high pointers at
    the same target index (representing the converged state at completion)
    and annotate "Found target X". Skips if the LLM already supplied pointers."""
    array_values = list(visual.get("array_values") or [])
    if not array_values and visual.get("array_rows"):
        first_row = (visual.get("array_rows") or [None])[0] or {}
        array_values = list(first_row.get("values") or [])
        if array_values:
            visual["array_values"] = array_values
    if not array_values:
        return
    # Skip if the LLM already provided pointers — don't overwrite intent.
    if visual.get("array_pointers"):
        return

    # Pick a target index that's mid-ish but not exactly the centre so it
    # looks like an actual converged search result, not the initial mid.
    target_idx = min(len(array_values) - 1, max(0, len(array_values) // 2))
    visual["array_pointers"] = [
        {"label": "low", "index": target_idx, "side": "top"},
        {"label": "high", "index": target_idx, "side": "top"},
        {"label": "mid", "index": target_idx, "side": "bottom"},
    ]
    visual["array_ranges"] = [
        {"label": "found", "start": target_idx, "end": target_idx},
    ]
    annotations = list(visual.get("array_annotations") or [])
    target_value = array_values[target_idx]
    annotations.insert(0, f"Found target {target_value}")
    visual["array_annotations"] = annotations[:6]


def _overlay_traversal_completion(
    visual: dict[str, Any],
    card: dict[str, Any],
    *,
    traversal: str,
) -> None:
    """For a tree-traversal background visual, populate traversal_path so the
    bottom 'Traversal order' text shows the visit sequence FOR THE TREE THE
    LLM ACTUALLY EMITTED.

    Previous bug: this function read `_BST_TRAVERSAL_ORDERS[traversal]` —
    a hardcoded list of values for the canonical 50/30/70/20/40/60/80 BST.
    Since we now require the LLM to pick its own values per lesson, that
    canonical list almost NEVER matches the displayed tree. The result was a
    bottom strip like "50 → 30 → 20 → 40 → 70 → 60 → 80" rendered under a
    tree whose nodes were 25/30/35/40/45/50/60.

    Fix: read the actual node labels from `visual["nodes"]`, sort them
    numerically, and compute the traversal visit order from THOSE values via
    `_bst_visit_order_for_values`. Fall back to the canonical list only when
    we genuinely cannot recover the LLM's values (e.g. fewer than 7 numeric
    labels), and even then only as a last resort.

    We also deliberately do NOT label tree edges with visit numbers — BSTs
    are unweighted, and adding numeric labels to their edges makes readers
    misread them as edge weights."""
    if visual.get("traversal_path"):
        # Already populated upstream; leave it alone.
        return

    # Pull the LLM's actual numeric labels from the tree.
    nodes = visual.get("nodes") or []
    numeric_labels: list[str] = []
    for n in nodes:
        if not isinstance(n, dict):
            continue
        label = str(n.get("label") or n.get("id") or "").strip()
        if label.isdigit() or (label.startswith("-") and label[1:].isdigit()):
            numeric_labels.append(label)

    visit_order: list[str] = []
    if len(numeric_labels) >= 7:
        sorted_vals = sorted(numeric_labels, key=lambda s: int(s))
        visit_order = _bst_visit_order_for_values(sorted_vals, traversal)

    # Last-resort fallback to the canonical list — only when the LLM gave us
    # no usable values and only for the 4 standard tree traversal types.
    if not visit_order:
        visit_order = list(_BST_TRAVERSAL_ORDERS.get(traversal) or [])

    if not visit_order:
        return

    visual["traversal_path"] = visit_order

    # Add a focus note explaining what the visit numbers mean.
    focus = card.get("visual_focus")
    if not isinstance(focus, dict):
        focus = {}
        card["visual_focus"] = focus
    if not focus.get("attention_note"):
        focus["attention_note"] = (
            f"Edge labels are the visit number under {traversal.replace('_', '-')}."
        )


_TARGET_VALUE_PATTERN = re.compile(
    r"\btarget\s*[=:(]\s*(-?\d+)|"
    r"\bfind(?:ing)?\s+(?:value\s+)?(-?\d+)\b|"
    r"\bsearch(?:ing)?\s+for\s+(?:target\s+)?(-?\d+)\b",
    re.IGNORECASE,
)


def _extract_target_from_cards(cards: list[dict[str, Any]]) -> str | None:
    """Scan card points + descriptions for a target/search value reference."""
    for card in cards:
        text = " ".join(card.get("points") or []) + " " + str(card.get("visual_description") or "")
        match = _TARGET_VALUE_PATTERN.search(text)
        if match:
            value = next((g for g in match.groups() if g), None)
            if value:
                return value
    return None


_SCENARIO_LEADING_WORDS = (
    "find", "search", "compute", "sort", "traverse", "run",
    "goal", "target", "given", "starting",
)


def _looks_like_scenario(text: str) -> bool:
    """True if a visual_description already reads as a scenario header."""
    cleaned = (text or "").strip().lower()
    if not cleaned:
        return False
    if any(cleaned.startswith(word) for word in _SCENARIO_LEADING_WORDS):
        return True
    if "expected" in cleaned and ("output" in cleaned or "result" in cleaned):
        return True
    return False


def _build_scenario_text(
    algo: str,
    array_values: list[str],
    bst_values: list[str],
    target: str | None,
) -> str:
    """Construct a scenario header tailored to the algorithm family."""
    if algo == "binary_search":
        arr = "[" + ", ".join(array_values) + "]" if array_values else "the sorted array"
        if not target and array_values:
            target = array_values[min(len(array_values) - 1, len(array_values) // 2 + 1)]
        target_str = target or "a target value"
        return (
            f"Find target {target_str} in the sorted array {arr} using binary search; "
            f"expected result: index of the target or -1 if not found."
        )
    if algo == "merge_sort":
        arr = "[" + ", ".join(array_values) + "]" if array_values else "the array"
        return f"Sort the array {arr} using merge sort; expected output: sorted ascending."
    if algo == "quicksort":
        arr = "[" + ", ".join(array_values) + "]" if array_values else "the array"
        return f"Sort the array {arr} using quicksort; expected output: sorted ascending."
    if algo == "sliding_window":
        arr = "[" + ", ".join(array_values) + "]" if array_values else "the array"
        return f"Apply the sliding-window technique over {arr} to find the optimal window."
    if algo == "two_pointer":
        arr = "[" + ", ".join(array_values) + "]" if array_values else "the array"
        return f"Use two pointers on {arr} to satisfy the search condition."
    # Tree traversals
    bst_arr = ", ".join(bst_values) if bst_values else "the BST"
    if algo in ("inorder", "preorder", "postorder"):
        return (
            f"Compute the {algo.replace('_', ' ')} traversal of the BST containing values "
            f"{bst_arr}; expected output: nodes in visit order."
        )
    if algo == "level_order":
        return (
            f"Compute the level-order (BFS) traversal of the BST containing values "
            f"{bst_arr}; expected output: nodes level-by-level."
        )
    return ""


def _add_scenario_to_worked_examples(
    legacy_cards: list[dict[str, Any]],
    *,
    topic_hint: str,
) -> None:
    """Ensure the first worked_example card states the scenario (what we're
    solving and on what input). If the LLM didn't add it, synthesize one from
    the array/BST values present on the card and any target value mentioned
    in later cards."""
    worked = [
        c for c in legacy_cards
        if str(c.get("blueprint_key") or c.get("card_type") or "").lower() == "worked_example"
    ]
    if not worked:
        return
    first = worked[0]

    # Skip when the LLM already wrote a scenario.
    if _looks_like_scenario(str(first.get("visual_description") or "")):
        return

    array_algo = _detect_array_algorithm(topic_hint)
    bst_algo = _detect_bst_traversal(topic_hint)
    algo = array_algo or bst_algo
    if not algo:
        return

    visual = first.get("visual_plan") or {}
    array_values = list(visual.get("array_values") or [])
    if not array_values:
        rows = visual.get("array_rows") or []
        if rows:
            array_values = list(rows[0].get("values") or [])
    bst_values: list[str] = []
    if visual.get("type") == "node_link_diagram":
        bst_values = [str(n.get("label") or "") for n in (visual.get("nodes") or []) if n.get("label")]

    target = _extract_target_from_cards(worked)
    scenario = _build_scenario_text(algo, array_values, bst_values, target)
    if not scenario:
        return

    first["visual_description"] = scenario
    first["what_to_notice"] = scenario


# Permutations from sorted-value positions (v0..v6, left-to-right by value)
# to the traversal visit order, for a balanced canonical-position BST where
# v3 is the root, v1/v5 are inner nodes, and v0/v2/v4/v6 are leaves.
_BST_POSITION_TO_VISIT_ORDER_INDICES: dict[str, list[int]] = {
    "inorder":     [0, 1, 2, 3, 4, 5, 6],
    "preorder":    [3, 1, 0, 2, 5, 4, 6],
    "postorder":   [0, 2, 1, 4, 6, 5, 3],
    "level_order": [3, 1, 5, 0, 2, 4, 6],
}


def _bst_visit_order_for_values(sorted_values: list[str], traversal: str) -> list[str]:
    if len(sorted_values) < 7:
        return []
    indices = _BST_POSITION_TO_VISIT_ORDER_INDICES.get(traversal, [])
    return [sorted_values[idx] for idx in indices]


_ROOT_VALUE_PATTERNS = (
    re.compile(r"\broot\s+(?:node\s+|value\s+)?(\d{1,3})\b", re.IGNORECASE),
    re.compile(r"\broot\s*[=:]\s*(\d{1,3})\b", re.IGNORECASE),
    re.compile(r"\bnode\s+(\d{1,3})\s+is\s+the\s+root\b", re.IGNORECASE),
    re.compile(r"\b(?:starting at|begin at|start at)\s+(?:the\s+)?root\s+(\d{1,3})\b", re.IGNORECASE),
    re.compile(r"\bbst\s+with\s+root\s+(\d{1,3})\b", re.IGNORECASE),
)


def _extract_root_value_from_cards(cards: list[dict[str, Any]]) -> str | None:
    """Find an explicit 'root N' mention in any card. The LLM's choice of
    root is the strongest signal we have about the intended tree."""
    for card in cards:
        text = " ".join([
            str(card.get("title") or ""),
            str(card.get("visual_description") or ""),
            " ".join(str(p) for p in (card.get("points") or [])),
        ])
        for pat in _ROOT_VALUE_PATTERNS:
            m = pat.search(text)
            if m:
                return m.group(1)
    return None


def _supplement_to_seven(values: list[int], root_int: int) -> list[int]:
    """Given some integers and a known root, supplement with synthesized
    neighbors until we have at least 7 unique values with root_int as the
    middle (BST root position). Synthesizes values in steps of 10 to stay
    in 'textbook range' and avoid collisions."""
    unique = sorted(set(values + [root_int]))
    smaller = [v for v in unique if v < root_int]
    larger = [v for v in unique if v > root_int]

    # Need 3 smaller and 3 larger to fit canonical positions
    step = 10
    while len(smaller) < 3:
        candidate = (smaller[0] if smaller else root_int) - step
        if candidate < 0:
            step = max(1, step // 2)
            candidate = (smaller[0] if smaller else root_int) - step
        if candidate in smaller or candidate == root_int or candidate < 0:
            step += 5
            continue
        smaller.insert(0, candidate)
    while len(larger) < 3:
        candidate = (larger[-1] if larger else root_int) + step
        if candidate > 999:
            step = max(1, step // 2)
            candidate = (larger[-1] if larger else root_int) + step
        if candidate in larger or candidate == root_int:
            step += 5
            continue
        larger.append(candidate)

    # Take the 3 smaller closest to root, and 3 larger closest to root,
    # so the BST shape stays balanced visually.
    smaller = smaller[-3:]
    larger = larger[:3]
    return sorted(smaller + [root_int] + larger)


def _extract_bst_values_from_background_card(
    legacy_cards: list[dict[str, Any]],
    n_needed: int = 7,
) -> list[str] | None:
    """Pull the BST integer values from the background card's visual_plan.

    The background card establishes the canonical structure for the topic
    (the prompt instructs the LLM to commit to ONE tree there). When the
    worked-example cards later hallucinate a different tree, this gives us
    a reliable source of truth.
    """
    for card in legacy_cards:
        if str(card.get("blueprint_key") or "").strip().lower() != "background":
            continue
        visual = card.get("visual_plan") or {}
        if visual.get("type") != "node_link_diagram":
            continue
        labels: list[str] = []
        for node in (visual.get("nodes") or []):
            label = str(node.get("label") or "").strip()
            if re.fullmatch(r"-?\d{1,3}", label):
                labels.append(label)
        if len(labels) >= n_needed:
            unique = list(dict.fromkeys(labels))
            return sorted(unique[:n_needed], key=int)
    return None


def _extract_bst_values_from_worked_cards(
    worked_cards: list[dict[str, Any]],
    n_needed: int = 7,
) -> list[str] | None:
    """Collect numeric labels the LLM put on visual nodes (preferred) or
    mentioned in card text (fallback) across every worked-example card.
    Returns 7 unique sorted values to slot into canonical BST positions.

    Strategy:
      1. Aggregate every numeric label from visual_nodes + every standalone
         integer mention in title/description/bullets.
      2. If we have 7+ candidates ≥ 5, use them directly.
      3. If the LLM explicitly named a ROOT value (e.g. 'BST with root 40'),
         build the tree around THAT root — supplementing with synthesized
         neighbors as needed so the visual's root value matches what the
         bullets say. This avoids the recurring bug where text mentions
         'root 40' but the visual ends up with root 50 (the canonical
         default).
      4. Otherwise return None and let the caller fall back to the
         hardcoded canonical defaults.
    """
    from collections import Counter

    counter: Counter[str] = Counter()
    for card in worked_cards:
        visual = card.get("visual_plan") or {}
        for node in (visual.get("nodes") or []):
            label = str(node.get("label") or "").strip()
            if re.fullmatch(r"-?\d{1,3}", label):
                counter[label] += 3
        text = " ".join([
            str(card.get("title") or ""),
            str(card.get("visual_description") or ""),
            " ".join(str(p) for p in (card.get("points") or [])),
        ])
        for match in re.finditer(r"\b(\d{1,3})\b", text):
            counter[match.group(1)] += 1

    candidates = [v for v, _ in counter.most_common()]
    high_value = [v for v in candidates if int(v) >= 5]
    if len(high_value) >= n_needed:
        return sorted(high_value[: n_needed * 2], key=int)[:n_needed]
    if len(candidates) >= n_needed:
        return sorted(candidates[: n_needed * 2], key=int)[:n_needed]

    # Not enough values for a clean 7-value set. Check if the LLM gave us
    # an explicit root — if so, we can still build the right tree by
    # supplementing around that root.
    root_value = _extract_root_value_from_cards(worked_cards)
    if root_value:
        root_int = int(root_value)
        # Use any candidates we DID find as supplementary tree values.
        other_ints = [int(v) for v in candidates if v.isdigit() and int(v) != root_int]
        supplemented = _supplement_to_seven(other_ints, root_int)
        return [str(v) for v in supplemented]

    return None


def _build_canonical_bst_with_values(
    sorted_values: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Slot 7 sorted values into canonical BST positions:
            v3
           /  \
          v1   v5
         / \  / \
        v0 v2 v4 v6
    Returns (nodes, edges) matching _DEFAULT_BST_BACKGROUND_NODES/EDGES coords.
    """
    v = sorted_values
    nodes = [
        {"id": v[3], "label": v[3], "relation": "root", "description": "", "x": 50.0, "y": 16.0},
        {"id": v[1], "label": v[1], "relation": "node", "description": "", "x": 28.0, "y": 42.0},
        {"id": v[5], "label": v[5], "relation": "node", "description": "", "x": 72.0, "y": 42.0},
        {"id": v[0], "label": v[0], "relation": "leaf", "description": "", "x": 17.0, "y": 68.0},
        {"id": v[2], "label": v[2], "relation": "leaf", "description": "", "x": 39.0, "y": 68.0},
        {"id": v[4], "label": v[4], "relation": "leaf", "description": "", "x": 61.0, "y": 68.0},
        {"id": v[6], "label": v[6], "relation": "leaf", "description": "", "x": 83.0, "y": 68.0},
    ]
    edges = [
        {"from": v[3], "to": v[1], "label": "", "style": "solid"},
        {"from": v[3], "to": v[5], "label": "", "style": "solid"},
        {"from": v[1], "to": v[0], "label": "", "style": "solid"},
        {"from": v[1], "to": v[2], "label": "", "style": "solid"},
        {"from": v[5], "to": v[4], "label": "", "style": "solid"},
        {"from": v[5], "to": v[6], "label": "", "style": "solid"},
    ]
    return nodes, edges


def _extract_current_node_from_card(
    card: dict[str, Any],
    valid_labels: set[str],
) -> str | None:
    """Scan title + description + bullets for the node this step is about.

    The LLM frequently mentions both the current node AND the next node in
    the same card ("current=30 ... next recurse left to visit node 25"). We
    PREFER the most explicit "current=X" / "at root X" / "now at X" form
    when present; only fall back to "visit/output/add/node X" patterns when
    no explicit-current marker exists. Within the explicit set, the FIRST
    match wins (forward-looking text mentioning the next node comes later).
    """
    text = " ".join([
        str(card.get("title") or ""),
        str(card.get("visual_description") or ""),
        " ".join(str(p) for p in (card.get("points") or [])),
    ])
    explicit_patterns = [
        r"\bcurrent\s*[=:]\s*(\d{1,3})\b",
        r"\bat\s+(?:root\s+|node\s+)?(\d{1,3})\b",
        r"\bnow\s+at\s+(?:node\s+)?(\d{1,3})\b",
        r"\bfocusing\s+on\s+(?:the\s+)?(?:root\s+|left\s+child\s+|right\s+child\s+|node\s+)?(\d{1,3})\b",
    ]
    for pat in explicit_patterns:
        for match in re.finditer(pat, text, re.IGNORECASE):
            value = match.group(1)
            if value in valid_labels:
                return value
    weak_patterns = [
        r"\bvisit(?:ing)?\s+(?:node\s+)?(\d{1,3})\b",
        r"\boutput(?:ting)?\s+(\d{1,3})\b",
        r"\badd(?:ing)?\s+(\d{1,3})\b",
        r"\bnode\s+(\d{1,3})\b",
    ]
    found: list[str] = []
    for pat in weak_patterns:
        for match in re.finditer(pat, text, re.IGNORECASE):
            value = match.group(1)
            if value in valid_labels:
                found.append(value)
    return found[0] if found else None


def _extract_call_stack_from_card(
    card: dict[str, Any],
    valid_labels: set[str],
) -> list[str]:
    """Parse the call stack the LLM wrote in the card bullets.

    The prompt instructs the LLM to render the active call stack inline as
    "Call stack: [50→30]" or "Call stack: [50, 30]". When present, this is
    the most accurate source of "which nodes are on the recursion path
    right now" — better than any visit-order heuristic. Prefer the LATEST
    call stack in the card (the 'Now:' bullet, which describes the post-
    transition state).
    """
    text = " ".join(str(p) for p in (card.get("points") or []))
    matches = list(
        re.finditer(
            r"call\s*stack\s*[:=]\s*\[([^\]]+)\]",
            text,
            flags=re.IGNORECASE,
        )
    )
    if not matches:
        return []
    inner = matches[-1].group(1)
    tokens = re.findall(r"\d{1,3}", inner)
    cleaned: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if token in valid_labels and token not in seen:
            cleaned.append(token)
            seen.add(token)
    return cleaned


def _apply_traversal_highlights_to_worked_examples(
    legacy_cards: list[dict[str, Any]],
    *,
    topic_hint: str,
) -> None:
    """For BST traversal topics where the worked-example trace uses a
    node_link_diagram, populate per-card visual_focus.active_nodes and
    highlight_path so the SAME node gets emphasized that the bullets are
    describing. Also rewrite the corresponding node's `relation` to include
    "current" so the frontend's inferActiveNode fallback works even if
    visual_focus is ignored downstream.

    Why this is needed: when the safety net swaps in synthetic BST nodes,
    any visual_focus.active_nodes the LLM wrote (e.g. ["Root node"]) no
    longer matches the new node IDs ("50", "30"...), so the highlight
    silently breaks. We rebuild visual_focus here using the canonical visit
    order for the detected traversal.
    """
    traversal = _detect_bst_traversal(topic_hint)
    if not traversal:
        return

    worked_cards = [
        c for c in legacy_cards
        if str(c.get("blueprint_key") or c.get("card_type") or "").lower() == "worked_example"
    ]
    if not worked_cards:
        return

    # Step 1: extract the canonical BST values.
    # PRIORITY: the BACKGROUND card's visual_plan nodes (the structure the
    # learner saw before the worked example started). The LLM frequently
    # hallucinates a DIFFERENT tree in the worked_example cards — text says
    # "current=50" but the visual has 50 as a leaf under 60. Sourcing from
    # the background card forces visual continuity: the same tree the
    # learner already saw is the one we trace through.
    # FALLBACK: aggregate from the worked-example cards themselves
    # (existing behavior). FINAL FALLBACK: hardcoded defaults.
    bst_values = _extract_bst_values_from_background_card(legacy_cards)
    if not bst_values:
        bst_values = _extract_bst_values_from_worked_cards(worked_cards)
    if bst_values:
        canonical_nodes, canonical_edges = _build_canonical_bst_with_values(bst_values)
        visit_order = _bst_visit_order_for_values(bst_values, traversal)
    else:
        canonical_nodes = [dict(n) for n in _DEFAULT_BST_BACKGROUND_NODES]
        canonical_edges = [dict(e) for e in _DEFAULT_BST_BACKGROUND_EDGES]
        visit_order = list(_BST_TRAVERSAL_ORDERS.get(traversal, []))

    valid_labels = {n["label"] for n in canonical_nodes}
    if not visit_order:
        return

    # Step 2: figure out which node is "current" on each card. Try to extract
    # from the card's text first (title + description + bullets) so the
    # highlight matches what the bullets describe. Fall back to a
    # card-index → visit_order mapping when extraction fails.
    n_cards = len(worked_cards)
    n_visits = len(visit_order)

    for i, card in enumerate(worked_cards):
        visual = card.get("visual_plan")
        if not isinstance(visual, dict):
            visual = {}
            card["visual_plan"] = visual
        if visual.get("type") not in {"node_link_diagram", None, ""}:
            continue

        # Assign canonical structure (same tree across every card; only the
        # active highlight + cumulative path varies).
        visual["type"] = "node_link_diagram"
        visual["nodes"] = [dict(n) for n in canonical_nodes]
        visual["edges"] = [dict(e) for e in canonical_edges]
        nodes = visual["nodes"]
        edges = visual["edges"]

        # Try to derive the current node from this card's text.
        current_value = _extract_current_node_from_card(card, valid_labels)
        if current_value and current_value in visit_order:
            visit_idx = visit_order.index(current_value)
        else:
            if n_cards >= n_visits:
                visit_idx = min(i, n_visits - 1)
            else:
                visit_idx = (i + 1) * n_visits // n_cards - 1
                visit_idx = max(0, min(visit_idx, n_visits - 1))
            current_value = visit_order[visit_idx]

        # For highlight_path: prefer the call_stack the LLM wrote in the
        # bullets ("Call stack: [50→30]"). This is the recursion-trace
        # semantic — exactly what the frontend's call_stack panel shows
        # and what the user expects to see lit up on the tree. Only fall
        # back to "visit_order so far" (the cumulative-output semantic)
        # when no call stack appears in text; that's a worse default but
        # better than nothing.
        call_stack = _extract_call_stack_from_card(card, valid_labels)
        if call_stack:
            covered = call_stack
        else:
            covered = visit_order[: visit_idx + 1]

        focus = card.get("visual_focus")
        if not isinstance(focus, dict):
            focus = {}
            card["visual_focus"] = focus
        focus["active_nodes"] = [current_value]
        focus["highlight_path"] = list(covered)
        if not focus.get("attention_note"):
            focus["attention_note"] = f"Node {current_value} is the focus of this step."

        all_node_ids = {str(n.get("id") or n.get("label") or "") for n in nodes}
        incoming_ids = {str(e.get("to") or "") for e in edges if e.get("to")}
        root_ids = all_node_ids - incoming_ids

        for node in nodes:
            label = str(node.get("label") or "")
            node_id = str(node.get("id") or label)
            relation = str(node.get("relation") or "")
            cleaned = re.sub(r"\b(current|active)\b\s*", "", relation, flags=re.IGNORECASE).strip()
            if node_id in root_ids and "root" not in cleaned.lower():
                cleaned = (cleaned + " root").strip()
            if label == current_value:
                node["relation"] = (cleaned + " current").strip()
            else:
                node["relation"] = cleaned or "node"

    # Step 3: inject a setup card at the start of the trace for traversals
    # where the root is NOT the first visit (inorder/postorder). Without
    # this, learners see the trace begin at the leftmost leaf and assume
    # that's where the algorithm started — when it actually started at the
    # root and only got there by descending left first.
    _inject_traversal_setup_card(
        legacy_cards,
        traversal=traversal,
        visit_order=visit_order,
        canonical_nodes=canonical_nodes,
        canonical_edges=canonical_edges,
    )


def _inject_traversal_setup_card(
    legacy_cards: list[dict[str, Any]],
    *,
    traversal: str,
    visit_order: list[str],
    canonical_nodes: list[dict[str, Any]],
    canonical_edges: list[dict[str, str]],
) -> None:
    """For traversals that start above the first visit (inorder/postorder),
    insert a setup card that highlights the root and explains the trace
    hasn't visited anything yet. Skipped for preorder/level_order where
    the root IS the first visit."""
    if traversal not in ("inorder", "postorder"):
        return
    if not visit_order:
        return

    # Identify the root from the canonical nodes
    root_value = next(
        (n["label"] for n in canonical_nodes if "root" in str(n.get("relation") or "").lower()),
        None,
    )
    if not root_value:
        return

    leftmost = visit_order[0]
    if root_value == leftmost:
        return

    # Find the first worked_example card. Skip if it already reads as a
    # setup/initial-state card so we don't double-stack.
    first_we_idx = next(
        (
            i for i, c in enumerate(legacy_cards)
            if str(c.get("blueprint_key") or c.get("card_type") or "").lower() == "worked_example"
        ),
        -1,
    )
    if first_we_idx < 0:
        return
    first_we = legacy_cards[first_we_idx]
    existing_title = str(first_we.get("title") or "").lower()
    if any(marker in existing_title for marker in ("setup", "start at root", "initial state", "begin at")):
        return

    import copy
    setup = copy.deepcopy(first_we)
    setup["id"] = str(first_we.get("id") or "we-0") + "-setup"
    setup["title"] = f"Start at Root {root_value}"
    traversal_label = traversal.replace("_", "-")
    setup["points"] = [
        f"Currently: at root {root_value}, result=[], no nodes visited yet",
        f"{traversal_label.capitalize()} rule: visit the entire left subtree before the current node",
        f"Now: descending left from {root_value} — the first node visited will be {leftmost}, not {root_value}",
    ]
    setup["visual_description"] = (
        f"Trace begins at root {root_value}. No nodes have been visited yet — "
        f"the first node visited will be the leftmost leaf {leftmost}."
    )
    setup["body"] = []
    setup["bullets"] = []
    setup["visual_focus"] = {
        "active_nodes": [root_value],
        "highlight_path": [root_value],
        "active_step": 0,
        "attention_note": (
            f"Start at root {root_value}. We will descend left until reaching "
            f"{leftmost}, which is the first node actually visited."
        ),
    }
    setup_visual: dict[str, Any] = dict(first_we.get("visual_plan") or {})
    setup_visual["type"] = "node_link_diagram"
    setup_visual["nodes"] = [dict(n) for n in canonical_nodes]
    setup_visual["edges"] = [dict(e) for e in canonical_edges]
    # Mark root as the current/active node for this setup card.
    for node in setup_visual["nodes"]:
        label = str(node.get("label") or "")
        rel = str(node.get("relation") or "")
        cleaned = re.sub(r"\b(current|active)\b\s*", "", rel, flags=re.IGNORECASE).strip()
        if label == root_value:
            if "root" not in cleaned.lower():
                cleaned = (cleaned + " root").strip()
            node["relation"] = (cleaned + " current").strip()
        else:
            node["relation"] = cleaned or "node"
    setup["visual_plan"] = setup_visual

    legacy_cards.insert(first_we_idx, setup)


_MAIN_BULLET_FROM_CODE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("), "Define the {0} function:"),
    (re.compile(r"^return\b"), "Return the result:"),
    (re.compile(r"^if\s+(.+?):\s*$"), "Check {0}:"),
    (re.compile(r"^elif\s+(.+?):\s*$"), "Otherwise check {0}:"),
    (re.compile(r"^else\s*:\s*$"), "Otherwise:"),
    (re.compile(r"^for\s+[A-Za-z_][A-Za-z0-9_]*\s+in\s+(.+?):\s*$"), "Iterate over {0}:"),
    (re.compile(r"^while\s+(.+?):\s*$"), "Loop while {0}:"),
    (re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(set|dict|list)\s*\(\s*\)\s*$"), "Create the {0} {1}:"),
    (re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\[\s*\]\s*$"), "Create the empty {0} list:"),
    (re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{\s*\}\s*$"), "Create the empty {0} dict:"),
    (re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\["), "Initialize {0}:"),
    (re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{"), "Initialize {0}:"),
    (re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([A-Za-z_][A-Za-z0-9_]*)\s*$"), "Set {0} to {1}:"),
    (re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*.+\.(pop|popleft|top|peek)\s*\("), "Pop the next item into {0}:"),
    (re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"), "Compute {0}:"),
    (re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\.(append|add|push)\s*\("), "Add to {0}:"),
    (re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\.(extend)\s*\("), "Extend {0} with new items:"),
    (re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*\("), "Call {0}:"),
]


def _derive_main_bullet_from_code(code_line: str) -> str:
    """Synthesize a short natural-language main-bullet label from a code line.

    Used when the LLM put multiple code-shaped sub-bullets under one umbrella
    main bullet (a granularity violation); we promote each code sub-bullet to
    its own main bullet and need a human-readable title for it. Falls back to
    "Run this line:" when no pattern matches.
    """
    text = (code_line or "").strip().strip("`")
    for pat, template in _MAIN_BULLET_FROM_CODE_PATTERNS:
        m = pat.match(text)
        if m:
            try:
                return template.format(*m.groups())
            except (IndexError, KeyError):
                continue
    return "Run this line:"


_EXPLANATION_FROM_CODE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"^def\s+([A-Za-z_]\w*)\s*\("),
        "Defines the {0} function — the entry point that receives the inputs and orchestrates the work below.",
    ),
    (
        re.compile(r"^return\s+(.+)$"),
        "Returns the final result back to the caller, ending this function.",
    ),
    (
        re.compile(r"^return\s*$"),
        "Exits the function without producing a value when the work is done.",
    ),
    (
        re.compile(r"^([A-Za-z_]\w*)\s*=\s*set\s*\(\s*\)\s*$"),
        "Empty set chosen for O(1) membership lookups; tracks {0} so duplicates and cycles can be skipped cheaply.",
    ),
    (
        re.compile(r"^([A-Za-z_]\w*)\s*=\s*dict\s*\(\s*\)\s*$"),
        "Empty dict that the algorithm will fill as keys become known; lookups stay O(1) on average.",
    ),
    (
        re.compile(r"^([A-Za-z_]\w*)\s*=\s*list\s*\(\s*\)\s*$"),
        "Empty list that the algorithm appends to as it makes progress; preserves insertion order.",
    ),
    (
        re.compile(r"^([A-Za-z_]\w*)\s*=\s*\[\s*\]\s*$"),
        "Empty list that the algorithm appends to as it makes progress; preserves insertion order.",
    ),
    (
        re.compile(r"^([A-Za-z_]\w*)\s*=\s*\{\s*\}\s*$"),
        "Empty dict that the algorithm will fill as keys become known; lookups stay O(1) on average.",
    ),
    (
        re.compile(r"^([A-Za-z_]\w*)\s*=\s*\[\s*([A-Za-z_]\w*)\s*\]\s*$"),
        "Seeds the waiting list with the start node so the loop has work to do on its very first iteration.",
    ),
    (
        re.compile(r"^([A-Za-z_]\w*)\s*=\s*\{\s*([A-Za-z_]\w*)\s*\}\s*$"),
        "Records the start node as already discovered before the loop begins so it cannot be added a second time.",
    ),
    (
        re.compile(r"^([A-Za-z_]\w*)\s*=\s*deque\s*\("),
        "Uses a deque so popping from the front is O(1); a plain list would make front-removal O(n) per step.",
    ),
    (
        re.compile(r"^([A-Za-z_]\w*)\s*=\s*.+\.popleft\s*\("),
        "Takes the next item from the front of the queue so the loop processes nodes in discovery order — this is the heart of BFS.",
    ),
    (
        re.compile(r"^([A-Za-z_]\w*)\s*=\s*.+\.pop\s*\("),
        "Takes the most recently added item off the top so the loop processes it next — this is what makes the traversal depth-first.",
    ),
    (
        re.compile(r"^([A-Za-z_]\w*)\.append\s*\(\s*([A-Za-z_]\w*)\s*\)"),
        "Adds the new item to the back of the waiting list so it gets processed in a future iteration.",
    ),
    (
        re.compile(r"^([A-Za-z_]\w*)\.add\s*\(\s*([A-Za-z_]\w*)\s*\)"),
        "Records the item as discovered so the algorithm will not re-process it later.",
    ),
    (
        re.compile(r"^([A-Za-z_]\w*)\.extend\s*\("),
        "Adds several items to the waiting list at once for later processing.",
    ),
    (
        re.compile(r"^while\s+(.+?):\s*$"),
        "Keeps the loop running while the condition holds; exits cleanly the moment it becomes false.",
    ),
    (
        re.compile(r"^for\s+([A-Za-z_]\w*)\s+in\s+(.+?):\s*$"),
        "Iterates so the body runs once per element of the collection, with the loop variable bound to each item in turn.",
    ),
    (
        re.compile(r"^if\s+(.+?):\s*$"),
        "Branches based on whether the condition holds; controls whether the body below runs.",
    ),
    (
        re.compile(r"^elif\s+(.+?):\s*$"),
        "Tries the alternative condition when the earlier branches did not apply.",
    ),
    (
        re.compile(r"^else\s*:\s*$"),
        "Runs the fallback branch when none of the earlier conditions held.",
    ),
    (
        re.compile(r"^([A-Za-z_]\w*)\s*=\s*([A-Za-z_]\w*)\s*$"),
        "Copies the value from the source into the destination so later steps can read the new state.",
    ),
    (
        re.compile(r"^([A-Za-z_]\w*)\s*=\s*"),
        "Updates the value so later steps can read the new state.",
    ),
]


def _derive_explanation_from_code(code_line: str) -> str:
    """Synthesize a plain-English description of a code line.

    Used by the splitter and the code-strip validator when a bullet must be
    replaced because it contained raw code with no explanation. Falls back to
    a generic sentence when no pattern matches.
    """
    text = (code_line or "").strip().strip("`")
    for pat, template in _EXPLANATION_FROM_CODE_PATTERNS:
        m = pat.match(text)
        if m:
            try:
                return template.format(*m.groups())
            except (IndexError, KeyError):
                continue
    return "Carries out the next step of the algorithm and updates the runtime state accordingly."


_EXPLANATION_JOINER_PATTERN = re.compile(
    r"(?:\s[—–-]\s|\s+(?:so|because|since|which|that|when)\s|:\s+[A-Za-z])"
)


def _is_pure_code_restatement(sub_text: str) -> bool:
    """True if a sub-bullet is JUST a raw code line with no explanation text.

    Pure restatements look like `visited = set()` or `stack = [start_node]`.
    Explanatory sub-bullets that happen to lead with code are NOT pure
    restatements — they contain a joiner (em-dash, colon-prose, "so", etc.)
    followed by a plain-English explanation, e.g. `visited = set() — sets give
    O(1) membership`.
    """
    body = re.sub(r"^\s*-\s*", "", str(sub_text).strip()).strip().strip("`")
    if not body or not _looks_like_code_line(body):
        return False
    # An explanatory tail makes it not a pure restatement.
    if _EXPLANATION_JOINER_PATTERN.search(body):
        return False
    # Short and code-shaped with no narrative joiner ⇒ pure restatement.
    return len(body) <= 60


def _split_coarse_code_walkthrough_bullets(legacy_cards: list[dict[str, Any]]) -> None:
    """Split coarse code_walkthrough main bullets so each code line gets at
    least one explanation in the bullet tree.

    Failure mode this fixes (the broken case): the LLM bundles multiple code
    lines under one umbrella main bullet ("Initialize the visited set and
    stack:") with the actual code lines as PURE-CODE sub-bullets (no
    explanation text). That leaves N code lines with zero plain-English
    coverage — exactly what the every-line explanation mandate forbids.

    Properly explained grouped patterns (Pattern B control-flow block and
    Pattern C init cluster from the prompt) have sub-bullets that NAME the
    code line AND explain it (e.g. "`visited = set()` — sets give O(1)
    membership"). Those are LEFT ALONE — they already satisfy the mandate.

    Detection: a main bullet is "coarse" only when it has 2+ sub-bullets that
    are pure-code restatements per `_is_pure_code_restatement`. We promote
    each such sub-bullet to its own main bullet (label synthesized from the
    code) so the line has at least one bullet of its own. Non-code sub-bullets
    on the original group are kept on the first promoted main bullet so the
    parent's intent isn't lost.

    Runs BEFORE `_accumulate_code_walkthrough_visuals` so the bullet count is
    final when per-card highlight ranges are written.
    """
    for card in legacy_cards:
        key = str(card.get("blueprint_key") or card.get("card_type") or "").lower()
        if key != "code_walkthrough":
            continue
        points = list(card.get("points") or [])
        if not points:
            continue

        # Parse points into (main_text, [sub_lines]) groups.
        groups: list[tuple[str, list[str]]] = []
        for p in points:
            if _is_main_bullet(p):
                groups.append((str(p), []))
            elif groups:
                groups[-1][1].append(str(p))
            else:
                groups.append((str(p), []))

        new_points: list[str] = []
        changed = False
        for main_text, subs in groups:
            # Identify PURE-CODE-RESTATEMENT sub-bullets (the broken case).
            # Sub-bullets that contain both code AND an explanation joiner
            # are NOT counted — they already satisfy the every-line mandate.
            pure_code_indices: list[int] = [
                i for i, sub in enumerate(subs) if _is_pure_code_restatement(sub)
            ]

            if len(pure_code_indices) < 2:
                # Group is either fine (explanatory sub-bullets) or only has
                # one bare code line — keep as-is.
                new_points.append(main_text)
                new_points.extend(subs)
                continue

            changed = True
            non_code_subs = [
                subs[i] for i in range(len(subs)) if i not in pure_code_indices
            ]

            for j, ci in enumerate(pure_code_indices):
                code_body = re.sub(r"^\s*-\s*", "", subs[ci].strip()).strip().strip("`")
                derived_label = _derive_main_bullet_from_code(code_body)
                derived_explanation = _derive_explanation_from_code(code_body)
                new_points.append(derived_label)
                # Emit a plain-English explanation as the sub-bullet — NEVER
                # re-emit the raw code line. The code is already visible in
                # the code panel; the bullet tree teaches what it means.
                new_points.append(f"  - {derived_explanation}")
                if j == 0 and non_code_subs:
                    # Carry the parent's explanatory sub-bullets onto the first
                    # promoted main so their context isn't lost.
                    for nc in non_code_subs:
                        nc_str = str(nc)
                        if not re.match(r"^\s+-\s+", nc_str):
                            nc_str = f"  - {nc_str.lstrip('- ').strip()}"
                        new_points.append(nc_str)

        if changed:
            card["points"] = new_points


_BACKTICK_CONTENT_PATTERN = re.compile(r"`([^`]+)`")


_CODE_PUNCT_PATTERN = re.compile(r"[=\(\)\[\]\{\}:]|->|=>")
_PROSE_WORD_COUNT_THRESHOLD = 4


def _is_bullet_mostly_code(body: str) -> bool:
    """True if the bullet body is primarily a code statement (with or without
    backticks), as opposed to plain-English prose that happens to mention a
    variable name.

    We consider a bullet "mostly code" when:
      - The whole body looks like a code line (e.g. `visited = set()`); or
      - The body is a backticked region containing code punctuation and the
        prose tail is too short to be a real explanation; or
      - The body is fully backtick-wrapped content with code punctuation,
        even if it doesn't parse as a clean statement (e.g. malformed
        fragments like `start): queue = [start]` from line-wrap splits).

    Single-identifier backtick references inside prose (e.g. "tracks `visited`
    so duplicates are skipped") are NOT considered code — they have plenty
    of plain-English tail.
    """
    cleaned = body.strip()
    if not cleaned:
        return False

    unwrapped = cleaned.strip("`").strip()
    # Empty after unwrapping ⇒ nothing meaningful.
    if not unwrapped:
        return False

    # Case 1: parseable code line.
    if _looks_like_code_line(unwrapped) and len(unwrapped) > 5:
        tail_match = _EXPLANATION_JOINER_PATTERN.search(cleaned)
        if not tail_match:
            return True
        tail_text = cleaned[tail_match.end():].strip()
        if len(tail_text) < 8:
            return True

    # Case 2: backtick-wrapped fragment with code punctuation. Triggers on
    # malformed splits and on cases _looks_like_code_line misses.
    starts_with_tick = cleaned.startswith("`")
    ends_with_tick = cleaned.endswith("`")
    if (starts_with_tick or ends_with_tick) and _CODE_PUNCT_PATTERN.search(unwrapped):
        # Count prose-shaped words (alphabetic tokens of length ≥ 2 with no
        # code-y characters). If the whole bullet has fewer than the
        # threshold, it's code-dominant.
        prose_tokens = re.findall(r"\b[A-Za-z]{2,}\b", cleaned)
        prose_tokens = [
            t for t in prose_tokens
            if t.lower() not in {"def", "return", "if", "elif", "else",
                                  "for", "while", "in", "not", "and", "or",
                                  "is", "true", "false", "none", "class",
                                  "from", "import", "as", "try", "except"}
        ]
        if len(prose_tokens) < _PROSE_WORD_COUNT_THRESHOLD:
            return True

    return False


def _strip_code_only_bullets_from_code_walkthrough(
    legacy_cards: list[dict[str, Any]],
) -> None:
    """Safety net: rewrite any code_walkthrough bullet that is mostly raw code
    into a plain-English description.

    Runs AFTER the splitter so any code-shaped bullets the splitter chose to
    leave (or that the LLM emitted as MAIN bullets) get cleaned up before the
    UI ever sees them.

    For each bullet we determine the underlying code line (the bullet itself
    if it is pure code, or the backticked content), feed it through
    `_derive_explanation_from_code`, and replace the bullet with the
    explanation. Indentation (main vs sub-bullet marker) is preserved so the
    bullet tree structure stays intact.
    """
    for card in legacy_cards:
        key = str(card.get("blueprint_key") or card.get("card_type") or "").lower()
        if key != "code_walkthrough":
            continue
        points = list(card.get("points") or [])
        if not points:
            continue

        new_points: list[str] = []
        for raw in points:
            text = str(raw)
            indent_match = re.match(r"^(\s*-\s*)(.*)$", text)
            if indent_match:
                marker, body = indent_match.group(1), indent_match.group(2)
            else:
                marker, body = "", text

            if not _is_bullet_mostly_code(body):
                new_points.append(text)
                continue

            # Extract the actual code statement.
            code_line = body.strip().strip("`").strip().rstrip(":")
            # If the body had a leading "label:" then a backticked code line,
            # prefer the inner code text.
            inner = _BACKTICK_CONTENT_PATTERN.search(body)
            if inner and _looks_like_code_line(inner.group(1).strip()):
                code_line = inner.group(1).strip()

            explanation = _derive_explanation_from_code(code_line)
            # Sub-bullets stay as sub-bullets; main bullets get a colon tail
            # only if they were already framed as a label.
            if marker:
                new_points.append(f"{marker}{explanation}")
            else:
                new_points.append(explanation)

        card["points"] = new_points


def _flatten_nested_functions(code: str) -> str:
    """Move helper functions defined INSIDE another function to module level.

    Coding lessons must not nest function definitions (a `def` inside a `def`) —
    the helper is hoisted to a top-level function and any local it closed over
    (e.g. an accumulator `result`) becomes an explicit parameter, with all call
    sites updated to pass it. Best-effort and side-effect-free on failure: if the
    code can't be parsed or transformed, the original is returned unchanged.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code

    hoisted: list[ast.AST] = []
    changed = False
    for outer in list(tree.body):
        if not isinstance(outer, ast.FunctionDef):
            continue
        nested = [s for s in outer.body if isinstance(s, ast.FunctionDef)]
        if not nested:
            continue
        outer_locals = {a.arg for a in outer.args.args}
        for stmt in outer.body:
            for sub in ast.walk(stmt):
                if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                    outer_locals.add(sub.id)
        free_by_name: dict[str, list[str]] = {}
        for inner in nested:
            inner_params = {a.arg for a in inner.args.args}
            inner_assigned: set[str] = set()
            used: set[str] = set()
            for sub in ast.walk(inner):
                if isinstance(sub, ast.Name):
                    (inner_assigned if isinstance(sub.ctx, ast.Store) else used).add(sub.id)
            free = [
                v for v in sorted(used & outer_locals)
                if v not in inner_params and v not in inner_assigned and v != inner.name
            ]
            free_by_name[inner.name] = free
            for v in free:
                inner.args.args.append(ast.arg(arg=v))
            # Update recursive calls inside the helper to pass the new params.
            for sub in ast.walk(inner):
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id == inner.name:
                    sub.args = sub.args + [ast.Name(id=v, ctx=ast.Load()) for v in free]
            hoisted.append(inner)
        # Drop the nested defs from the outer body, then update the outer's calls
        # to the (now top-level) helpers to pass the closed-over locals.
        outer.body = [s for s in outer.body if not isinstance(s, ast.FunctionDef)]
        for sub in ast.walk(outer):
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id in free_by_name:
                sub.args = sub.args + [ast.Name(id=v, ctx=ast.Load()) for v in free_by_name[sub.func.id]]
        changed = True

    if not changed:
        return code
    tree.body = tree.body + hoisted
    try:
        ast.fix_missing_locations(tree)
        out = ast.unparse(tree)
        ast.parse(out)  # validate the transform produced runnable code
        return out
    except Exception:  # noqa: BLE001 — never emit broken code; keep the original
        return code


def _is_bare_helper(code: str) -> bool:
    """True when `code` is a single self-recursive function that takes an
    accumulator parameter (e.g. `def traverse(node, result): ... traverse(...)`) —
    i.e. a helper with no main entry point that creates the accumulator."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    if not funcs and len(classes) == 1:
        funcs = [n for n in classes[0].body if isinstance(n, ast.FunctionDef)]
    if len(funcs) != 1:
        return False
    fn = funcs[0]
    if len(fn.args.args) < 2:  # needs an accumulator beyond the node/self arg
        return False
    for sub in ast.walk(fn):
        if isinstance(sub, ast.Call):
            target = sub.func
            if isinstance(target, ast.Name) and target.id == fn.name:
                return True
            if isinstance(target, ast.Attribute) and target.attr == fn.name:
                return True
    return False


def _complete_code_from_worked_examples(legacy_cards: list[dict[str, Any]]) -> str | None:
    """The most complete code_snippet carried by a worked_example card (which
    reliably holds the full main+helper program), or None."""
    best = ""
    for card in legacy_cards:
        if str(card.get("blueprint_key") or card.get("card_type") or "").lower() == "worked_example":
            snippet = str(card.get("code_snippet") or "").strip()
            if len(snippet) > len(best):
                best = snippet
    return best or None


def _accumulate_code_walkthrough_visuals(legacy_cards: list[dict[str, Any]]) -> None:
    """Make code_walkthrough cards show CUMULATIVE code growing across the
    topic, with each card highlighting the lines it newly introduces.

    Strategy (handles both LLM output patterns):
      - LLM emits each card's `code_snippet` as the FULL implementation-so-far
        and fills `highlight_lines_per_step` with the line ranges introduced
        on each card (per prompt rules) → use the LLM's ranges to drive
        per-card max_line.
      - LLM emits each card's `code_snippet` as ONLY the new lines (no
        highlight ranges) → concatenate snippets to build the full code,
        and max_line per card = cumulative line count through that card.

    Either way, every card ends up with:
      - visual.code = the COMPLETE program (longest snippet OR concatenation)
      - visual.max_line = how many lines should be visible on this card
        (renderer slices code to lines 1..max_line)
      - visual.highlight_lines = the range of lines newly introduced

    The frontend's VisualCodeBlock honors all three.
    """
    walkthrough_cards = [
        c for c in legacy_cards
        if str(c.get("blueprint_key") or c.get("card_type") or "").lower() == "code_walkthrough"
    ]
    if not walkthrough_cards:
        return

    # Step 1: determine the canonical FULL code. If any card's snippet is
    # longer than the cumulative concatenation, the LLM is already emitting
    # full-so-far snippets and the longest one IS the complete program.
    # Otherwise we concatenate per-card snippets.
    snippets: list[list[str]] = []
    for card in walkthrough_cards:
        raw = str(card.get("code_snippet") or "")
        lines = raw.split("\n") if raw else []
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        snippets.append(lines)

    longest_snippet = max(snippets, key=len, default=[])

    # Cumulative concatenation. Used as the full code if longest_snippet
    # turns out to be a per-card new-lines-only emit pattern.
    #
    # Important: do NOT dedupe every repeated line globally. Repeated lines
    # such as "else:", "return ...", "}", or repeated recursive calls can be
    # legitimate code. Only remove overlap when the next snippet starts with
    # lines already at the end of the accumulated snippet, or when the next
    # snippet is itself a cumulative full-so-far snippet.
    concatenated: list[str] = []
    cumulative_per_card: list[int] = []
    for lines in snippets:
        if not lines:
            cumulative_per_card.append(len(concatenated))
            continue
        if _line_prefix_matches(concatenated, lines):
            concatenated = list(lines)
            cumulative_per_card.append(len(concatenated))
            continue
        overlap = _suffix_prefix_overlap(concatenated, lines)
        concatenated.extend(lines[overlap:])
        cumulative_per_card.append(len(concatenated))

    # If two or more cards emit a snippet that starts with the SAME first line
    # (e.g. `def inorder(root):`), those snippets are cumulative full-program
    # REWRITES of the same program, not disjoint new-line fragments. The
    # suffix/prefix overlap check above can't detect that (the rewrites differ
    # in comments/placeholders), so `concatenated` stacks 2-3 duplicate copies
    # of the whole function. In that case the longest single snippet IS the
    # complete program — never the concatenation.
    first_lines = [lines[0].strip() for lines in snippets if lines]
    _def_starts = ("def ", "class ", "func ", "function ", "public ", "private ", "void ", "int ")
    cumulative_full_rewrites = (
        len(first_lines) >= 2
        and first_lines[0].startswith(_def_starts)
        and first_lines.count(first_lines[0]) >= 2
    )

    # Pick whichever is longer as the canonical full implementation. When
    # the LLM emits cumulative snippets, longest_snippet === concatenated
    # (modulo whitespace). When it emits new-lines-only per card,
    # concatenated is longer.
    if cumulative_full_rewrites or len(longest_snippet) >= len(concatenated):
        full_lines = longest_snippet
    else:
        full_lines = concatenated

    if not full_lines:
        return
    full_code = "\n".join(full_lines)
    # Enforce no nested function definitions: hoist any helper defined inside the
    # main function to module level. Runs on the canonical full code, so both the
    # code_walkthrough cards (set below) and the worked-example toggle (synced to
    # this code afterward) show the flattened, separated-helper form.
    flattened = _flatten_nested_functions(full_code)
    if flattened != full_code:
        full_code = flattened
        full_lines = full_code.split("\n")
    total_lines = len(full_lines)

    # Guard: a code_walkthrough must show the MAIN entry function, not only the
    # helper. If the assembled code collapsed to a bare self-recursive helper but a
    # worked_example carries the complete main+helper program containing this
    # helper, adopt the complete program so both functions are walked through.
    if _is_bare_helper(full_code):
        complete = _complete_code_from_worked_examples(legacy_cards)
        helper_sig = next((l.strip() for l in full_lines if l.strip().startswith("def ")), "")
        if (
            complete
            and helper_sig
            and helper_sig in complete
            and not _is_bare_helper(complete)
            and len(complete.split("\n")) > total_lines
        ):
            full_code = _fix_code_layout(complete)[0]
            full_lines = full_code.split("\n")
            total_lines = len(full_lines)

    # Step 2: compute per-card max_line.
    #
    # We can't trust the LLM's highlight_lines_per_step naively — the common
    # failure mode is the LLM emits the full code on card 1 along with a
    # range like [[1, N]] (or no ranges at all), which says "this card
    # introduces the whole function". Using that directly makes card 1
    # show the complete program.
    #
    # Strategy:
    #   1. Read each card's LLM-supplied ranges. Compute per-card max_end.
    #   2. Check if those values show meaningful progression: monotonically
    #      non-decreasing AND first card covers less than ~60% of the code.
    #   3. If yes, use them.
    #   4. If no (or any card missing ranges), enforce an EVEN DISTRIBUTION:
    #      card i gets max_line = ceil(i * total / N). The last card always
    #      reveals the complete program.
    #
    # This guarantees a gradual reveal regardless of LLM compliance, while
    # still honoring the LLM's intent when it actually does emit progressive
    # ranges.

    n_cards = len(walkthrough_cards)

    llm_max_lines: list[int | None] = []
    for card in walkthrough_cards:
        ranges_raw = card.get("highlight_lines_per_step") or []
        ends: list[int] = []
        if isinstance(ranges_raw, list):
            for item in ranges_raw:
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    try:
                        e = max(1, min(total_lines, int(item[1])))
                        ends.append(e)
                    except (TypeError, ValueError):
                        continue
        llm_max_lines.append(max(ends) if ends else None)

    # Detect whether the LLM's ranges show genuine progression.
    use_llm_ranges = False
    if all(m is not None for m in llm_max_lines) and llm_max_lines:
        first_max = llm_max_lines[0] or 0
        first_small = first_max <= max(1, (total_lines * 6) // 10)
        is_monotonic = all(
            (llm_max_lines[i] or 0) >= (llm_max_lines[i - 1] or 0)
            for i in range(1, n_cards)
        )
        ends_at_total = (llm_max_lines[-1] or 0) >= total_lines or n_cards == 1
        use_llm_ranges = first_small and is_monotonic and ends_at_total

    if use_llm_ranges:
        per_card_max_line: list[int] = [int(m or 1) for m in llm_max_lines]
    else:
        # Even distribution. Each card i (1-indexed) shows lines 1..ceil(i*M/N).
        per_card_max_line = [
            max(1, min(total_lines, -(-((i + 1) * total_lines) // n_cards)))
            for i in range(n_cards)
        ]

    # Enforce monotonic non-decreasing and ensure final card has the full code.
    prev = 0
    for i in range(n_cards):
        per_card_max_line[i] = max(per_card_max_line[i], prev)
        prev = per_card_max_line[i]
    per_card_max_line[-1] = total_lines

    # Compute the per-card highlight = lines newly introduced by this card.
    per_card_highlight: list[list[int] | None] = []
    prev_max = 0
    for max_line in per_card_max_line:
        if max_line > prev_max:
            per_card_highlight.append([prev_max + 1, max_line])
        else:
            # No growth — flag the previously last-added range so the panel
            # still has a visible highlight rather than nothing.
            per_card_highlight.append([max(1, max_line), max_line])
        prev_max = max_line

    # Step 3: apply.
    for card, max_line, highlight in zip(walkthrough_cards, per_card_max_line, per_card_highlight):
        card["code_snippet"] = full_code
        if highlight is not None:
            main_groups = max(1, _count_main_bullets(card.get("points") or []))
            card["highlight_lines_per_step"] = [highlight for _ in range(main_groups)]
        card["visual_type"] = "code_trace"
        visual = card.get("visual_plan")
        if not isinstance(visual, dict):
            visual = {}
            card["visual_plan"] = visual
        visual["type"] = "code_trace"
        visual["code"] = full_code
        visual["language"] = str(card.get("code_language") or visual.get("language") or "python")
        visual["max_line"] = max_line
        if highlight is not None:
            visual["highlight_lines"] = highlight


def _expand_coding_code_walkthroughs_to_one_line_cards(
    legacy_cards: list[dict[str, Any]],
) -> None:
    """For coding topics, make each code_walkthrough card introduce one line.

    The regular accumulator supports grouped "functional blocks" per card.
    Coding implementation topics need a stricter teaching rhythm: card 1 shows
    line 1, card 2 shows lines 1-2, and so on until the final card shows the
    completed implementation. This pass runs after accumulation so we can use
    the finalized implementation as the source of truth.
    """
    i = 0
    while i < len(legacy_cards):
        if _legacy_card_key(legacy_cards[i]) != "code_walkthrough":
            i += 1
            continue

        run_start = i
        while i < len(legacy_cards) and _legacy_card_key(legacy_cards[i]) == "code_walkthrough":
            i += 1
        run_end = i
        run = legacy_cards[run_start:run_end]
        if not run:
            continue

        code_candidates = [
            str(card.get("code_snippet") or "").strip("\n")
            for card in run
            if str(card.get("code_snippet") or "").strip()
        ]
        for card in run:
            visual = card.get("visual_plan")
            if isinstance(visual, dict) and str(visual.get("code") or "").strip():
                code_candidates.append(str(visual.get("code") or "").strip("\n"))
        if not code_candidates:
            continue

        full_code = max(code_candidates, key=lambda code: len(code.splitlines()))
        # Clean the canonical code before expanding: repair indentation, drop stray
        # module-level lines, synthesize a missing main, split broken recursion.
        full_code = _fix_dedented_body_lines(full_code)
        full_code = _strip_module_level_strays(full_code)
        full_code = _strip_driver_code(full_code)
        # _synthesize_main_for_helper / _split_accumulator_recursion RETIRED — they corrupted
        # valid code. code_repair validates + cleanly regenerates broken code at enrichment.
        # Iterate one real (non-blank) line per card; blank separators are restored
        # in the displayed cumulative code via _fix_code_layout below.
        full_lines = [line for line in full_code.splitlines() if line.strip()]
        if not full_lines:
            continue

        template = run[0]
        language = str(template.get("code_language") or "").strip()
        if not language:
            for card in run:
                language = str(card.get("code_language") or "").strip()
                if language:
                    break
        language = language or "python"

        base_title = _code_walkthrough_base_title(template)
        group_id = (
            str(template.get("continuation_group_id") or "").strip()
            or _slugify_continuation_id(base_title)
            or "code-walkthrough"
        )
        total = len(full_lines)
        expanded_cards: list[dict[str, Any]] = []

        for line_index, code_line in enumerate(full_lines, start=1):
            line_title = _derive_main_bullet_from_code(code_line).strip()
            if not line_title:
                line_title = f"Line {line_index}"
            line_title = line_title.rstrip(":")
            explanation = _derive_explanation_from_code(code_line)
            # Restore 2-blank-line separation between functions in the displayed code,
            # and remap this card's highlight to the (shifted) line number.
            cumulative_code, _layout_map = _fix_code_layout("\n".join(full_lines[:line_index]))
            highlight_line = _layout_map.get(line_index, line_index)

            card = dict(template)
            card["id"] = f"{str(template.get('id') or 'code')}-line-{line_index}"
            card["title"] = f"{base_title}: {line_title}" if base_title else line_title
            card["body"] = []
            card["points"] = [
                f"{line_title}:",
                f"  - {explanation}",
            ]
            card["main_concept"] = explanation
            card["learning_goal"] = explanation
            card["code_snippet"] = cumulative_code
            card["code_language"] = language
            card["visual_type"] = "code_trace"
            card["highlight_lines_per_step"] = [[highlight_line, highlight_line]]
            card["continuation_group_id"] = group_id
            card["continuation_index"] = line_index
            card["continuation_total"] = total
            card["continuation_reason"] = "one_code_line_per_card"
            card["continues_from_previous"] = line_index > 1

            visual = card.get("visual_plan")
            if not isinstance(visual, dict):
                visual = {}
            else:
                visual = dict(visual)
            visual["type"] = "code_trace"
            visual["title"] = card["title"]
            visual["purpose"] = explanation
            visual["description"] = explanation
            visual["what_to_notice"] = explanation
            visual["code"] = "\n".join(full_lines)
            visual["language"] = language
            visual["max_line"] = line_index
            visual["highlight_lines"] = [line_index, line_index]
            card["visual_plan"] = visual
            card["visual_description"] = explanation
            card["what_to_notice"] = explanation
            expanded_cards.append(card)

        legacy_cards[run_start:run_end] = expanded_cards
        i = run_start + len(expanded_cards)


def _code_walkthrough_base_title(card: dict[str, Any]) -> str:
    title = str(card.get("title") or "").strip()
    if not title:
        return "Code Walkthrough"
    title = re.sub(r"\s*:\s*(?:line\s*)?\d+\s*$", "", title, flags=re.IGNORECASE)
    return title.strip() or "Code Walkthrough"


def _slugify_continuation_id(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return slug[:80]


def _sync_coding_worked_examples_to_final_code(legacy_cards: list[dict[str, Any]]) -> None:
    """Give coding worked examples the complete final implementation.

    Code walkthrough cards intentionally reveal code progressively. Coding
    worked_example cards do the opposite: they run the completed program on a
    concrete input and highlight whichever line/block is executing. If the LLM
    emits a partial snippet on a worked example, use the final walkthrough code
    as the source of truth so the frontend can render a full code trace.
    """
    walkthrough_codes = [
        str(card.get("code_snippet") or "").strip("\n")
        for card in legacy_cards
        if _legacy_card_key(card) == "code_walkthrough"
        and str(card.get("code_snippet") or "").strip()
    ]
    if not walkthrough_codes:
        return

    final_code = max(walkthrough_codes, key=lambda code: len(code.splitlines()))
    final_line_count = len(final_code.splitlines())
    if final_line_count <= 0:
        return

    for card in legacy_cards:
        if _legacy_card_key(card) != "worked_example":
            continue

        current_code = str(card.get("code_snippet") or "").strip("\n")
        current_line_count = len(current_code.splitlines()) if current_code else 0
        if current_line_count < final_line_count:
            card["code_snippet"] = final_code

        language = str(card.get("code_language") or "").strip()
        if not language:
            for source_card in reversed(legacy_cards):
                if _legacy_card_key(source_card) == "code_walkthrough":
                    language = str(source_card.get("code_language") or "").strip()
                    if language:
                        break
            card["code_language"] = language or "python"

        group_count = max(1, _count_main_bullets(card.get("points") or []))
        ranges = _validated_highlight_lines_per_step(
            card.get("highlight_lines_per_step"),
            code_snippet=str(card.get("code_snippet") or final_code),
        )
        ranges = _sanitize_coding_worked_example_highlights(
            ranges,
            card=card,
            final_code=final_code,
            group_count=group_count,
        )
        if ranges:
            card["highlight_lines_per_step"] = ranges
        else:
            card["highlight_lines_per_step"] = _infer_coding_worked_example_highlights(
                card,
                final_code=final_code,
                group_count=group_count,
            )


def _sanitize_coding_worked_example_highlights(
    ranges: list[list[int]],
    *,
    card: dict[str, Any],
    final_code: str,
    group_count: int,
) -> list[list[int]]:
    """Reject broad worked-example highlights that make the whole code panel glow.

    Coding worked examples should show the complete implementation, but each
    example step should highlight the line/block currently executing. If the
    LLM emits [1, N] for every group, the UI loses that connection.
    """
    total_lines = len(final_code.splitlines())
    if not ranges or total_lines <= 0:
        return []

    broad_ranges = [
        item for item in ranges
        if len(item) == 2 and item[0] <= 1 and item[1] >= total_lines
    ]
    if broad_ranges and len(broad_ranges) >= max(1, len(ranges) // 2):
        return []

    cleaned: list[list[int]] = []
    for start, end in ranges[:group_count]:
        width = end - start + 1
        if total_lines > 4 and width >= total_lines:
            continue
        cleaned.append([start, end])

    if len(cleaned) < group_count:
        inferred = _infer_coding_worked_example_highlights(
            card,
            final_code=final_code,
            group_count=group_count,
        )
        return inferred

    return cleaned


def _infer_coding_worked_example_highlights(
    card: dict[str, Any],
    *,
    final_code: str,
    group_count: int,
) -> list[list[int]]:
    code_lines = final_code.splitlines()
    if not code_lines:
        return []

    groups = _group_main_point_blocks([str(point) for point in (card.get("points") or [])])
    if not groups:
        groups = [[""] for _ in range(group_count)]

    ranges: list[list[int]] = []
    for index in range(group_count):
        group = groups[index] if index < len(groups) else [""]
        text = " ".join(str(item) for item in group).lower()
        line_number = _infer_code_line_for_worked_example_text(text, code_lines)
        if line_number is None:
            # Last-resort fallback: one line, not the entire function.
            line_number = min(len(code_lines), index + 1)
        ranges.append([line_number, line_number])

    return ranges


def _infer_code_line_for_worked_example_text(
    text: str,
    code_lines: list[str],
) -> int | None:
    normalized_lines = [line.strip().lower() for line in code_lines]

    def first_line_matching(*needles: str) -> int | None:
        for line_index, line in enumerate(normalized_lines, start=1):
            if any(needle in line for needle in needles):
                return line_index
        return None

    def first_line_matching_all(*needles: str) -> int | None:
        for line_index, line in enumerate(normalized_lines, start=1):
            if all(needle in line for needle in needles):
                return line_index
        return None

    if any(word in text for word in ("dequeue", "pop front", "queue front", "remove from queue")):
        return first_line_matching("popleft(", "pop(0)")
    if any(word in text for word in ("enqueue", "add to queue", "queue after", "neighbor", "neighbour")):
        return (
            first_line_matching("queue.append", "queue.append(")
            or first_line_matching("visited.add")
            or first_line_matching("for neighbor", "for neighbour")
        )
    if any(word in text for word in ("record", "output", "order", "result", "append to traversal")):
        return first_line_matching("order.append", "result.append", "output.append")
    if "visited" in text or "discovered" in text:
        return first_line_matching("visited.add", "visited =")
    if "queue" in text:
        return first_line_matching("queue =", "deque(", "queue.append", "popleft(", "pop(0)")
    if "stack" in text:
        return first_line_matching("stack =", "stack.append", "stack.pop")
    if any(word in text for word in ("loop", "while", "continue")):
        return first_line_matching("while ")
    if any(word in text for word in ("iterate", "check", "inspect")):
        return first_line_matching("for ")
    if any(word in text for word in ("return", "final")):
        return first_line_matching("return ")
    if any(word in text for word in ("function", "define", "parameter")):
        return first_line_matching("def ")

    return first_line_matching_all("if ", "not in") or first_line_matching("if ")


def _ensure_coding_graph_worked_example_visuals(
    legacy_cards: list[dict[str, Any]],
    *,
    topic_hint: str,
) -> None:
    """Ensure graph BFS/DFS coding examples have a renderable graph visual.

    The code panel is the source of truth for coding worked examples, but the
    learner still needs the runtime structure on the left. If the LLM gives a
    graph-BFS/DFS coding example with an empty visual or a BST/tree visual,
    replace it with a small canonical graph instead of dropping the visual.
    """
    kind = _graph_traversal_kind(topic_hint)
    if kind not in {"bfs", "dfs"}:
        return

    fallback_nodes, fallback_edges, _, graph_kind = _synthesize_node_link_fallback(topic_hint)
    if graph_kind != "graph" or not fallback_nodes or not fallback_edges:
        return

    for card in legacy_cards:
        if _legacy_card_key(card) != "worked_example":
            continue
        visual = card.get("visual_plan")
        if not isinstance(visual, dict):
            visual = {}
            card["visual_plan"] = visual
        visual_text = " ".join(
            [
                str(visual.get("title") or ""),
                str(visual.get("purpose") or ""),
                str(visual.get("description") or ""),
                str(card.get("visual_description") or ""),
            ]
        ).lower()
        node_labels = [
            str(node.get("label") or "")
            for node in (visual.get("nodes") or [])
            if isinstance(node, dict)
        ]
        numeric_node_count = sum(1 for label in node_labels if label.strip().isdigit())
        looks_like_tree = any(term in visual_text for term in ("bst", "binary search tree", "tree", "root"))
        has_renderable_graph = (
            visual.get("type") == "node_link_diagram"
            and len(_validated_node_link_nodes(visual.get("nodes") or [])) >= 4
            and len(_validated_visual_edges(visual.get("edges") or [])) >= 3
            and not looks_like_tree
            and numeric_node_count < 4
        )
        source_nodes = _validated_node_link_nodes(visual.get("nodes") or []) if has_renderable_graph else fallback_nodes
        source_edges = _validated_visual_edges(visual.get("edges") or []) if has_renderable_graph else fallback_edges

        text = " ".join(
            [
                str(card.get("title") or ""),
                str(card.get("visual_description") or ""),
                str(card.get("what_to_notice") or ""),
                " ".join(str(point) for point in (card.get("points") or [])),
            ]
        )
        current = _extract_graph_trace_current_node(text) or "A"
        visited = _extract_graph_trace_set(text, "visited")
        frontier_name = "queue" if kind == "bfs" else "stack"
        frontier = _extract_graph_trace_list(text, frontier_name)
        discovered = set(visited) | set(frontier)
        newly_discovered = _extract_graph_trace_new_nodes(text, current=current)

        graph_nodes: list[dict[str, Any]] = []
        for node in source_nodes:
            copied = dict(node)
            label = _normalize_node_data_label(str(copied.get("label") or copied.get("id") or ""))
            if not label:
                continue
            copied["id"] = label
            copied["label"] = label
            if label == current:
                copied["state"] = "current"
            elif label in newly_discovered:
                copied["state"] = "newly_discovered"
            elif label in discovered:
                copied["state"] = "discovered"
            else:
                copied["state"] = "unvisited"
            copied["relation"] = "node"
            graph_nodes.append(copied)

        graph_edges: list[dict[str, str]] = []
        for edge in source_edges:
            copied = dict(edge)
            source = _normalize_node_data_label(str(copied.get("from") or ""))
            target = _normalize_node_data_label(str(copied.get("to") or ""))
            if not source or not target:
                continue
            copied["from"] = source
            copied["to"] = target
            endpoints = {source, target}
            if current in endpoints and (endpoints - {current}) & newly_discovered:
                copied["state"] = "active"
                copied["style"] = "traversal"
            elif source in discovered and target in discovered:
                copied["state"] = "traversed"
                copied["style"] = "traversal"
            else:
                copied["state"] = "unchecked"
                copied["style"] = str(copied.get("style") or "solid")
            graph_edges.append(copied)

        description = str(card.get("visual_description") or visual.get("description") or f"Trace {kind.upper()} on the current graph state.").strip()
        visual.update({
            "type": "node_link_diagram",
            "title": str(card.get("title") or visual.get("title") or f"{kind.upper()} graph state"),
            "purpose": description,
            "description": description,
            "placement": "card",
            "what_to_notice": description,
            "nodes": graph_nodes,
            "edges": graph_edges,
            "traversal_path": list(dict.fromkeys([*visited, current] if current else visited)),
        })
        card["visual_type"] = "node_link_diagram"
        card["visual_plan"] = visual
        card["visual_description"] = description
        focus = card.get("visual_focus")
        if not isinstance(focus, dict):
            focus = {}
            card["visual_focus"] = focus
        focus["active_nodes"] = [current] if current else []
        focus["attention_note"] = description


def _extract_graph_trace_current_node(text: str) -> str:
    patterns = (
        r"\bvisit(?:ing)?\s+node\s+([A-Z])\b",
        r"\bprocess(?:ing)?\s+node\s+([A-Z])\b",
        r"\bdequeue\s+([A-Z])\b",
        r"\bpop\s+([A-Z])\b",
        r"\bcurrent(?:\s+node)?\s*[=:]\s*([A-Z])\b",
        r"\bnode\s+([A-Z])\s+is\s+being\s+processed\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).upper()
    return ""


def _extract_graph_trace_set(text: str, name: str) -> list[str]:
    pattern = rf"\b{name}\s*=\s*(?:set\()?[\{{\[]([^}}\]\)]*)[\}}\]]?\)?"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return []
    return _extract_graph_trace_labels(match.group(1))


def _extract_graph_trace_list(text: str, name: str) -> list[str]:
    pattern = rf"\b{name}\s*=\s*\[([^\]]*)\]"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return []
    return _extract_graph_trace_labels(match.group(1))


def _extract_graph_trace_new_nodes(text: str, *, current: str) -> set[str]:
    new_nodes: set[str] = set()
    for pattern in (
        r"\b(?:neighbors?|neighbours?)\s+([A-Z](?:\s*(?:,|and)\s*[A-Z])*)",
        r"\b(?:enqueue|add|push)\s+([A-Z](?:\s*(?:,|and)\s*[A-Z])*)",
    ):
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            new_nodes.update(_extract_graph_trace_labels(match.group(1)))
    if current:
        new_nodes.discard(current)
    return new_nodes


def _extract_graph_trace_labels(text: str) -> list[str]:
    labels: list[str] = []
    for label in re.findall(r"\b[A-Z]\b", text.upper()):
        if label not in labels:
            labels.append(label)
    return labels


_MAX_CODE_WALKTHROUGH_CARD_LINES = 6
_MAX_CODE_WALKTHROUGH_MAIN_IDEAS = 3


def _merge_tiny_code_walkthrough_cards(legacy_cards: list[dict[str, Any]]) -> None:
    """Group adjacent tiny code walkthrough cards into coherent code-block cards.

    The LLM often responds to "one functional block per card" by making one
    card per tiny line. That is too choppy for learners. This pass keeps code
    walkthrough order intact, but packs adjacent small cards together when the
    combined bullet trees still fit a code walkthrough card.
    """
    i = 0
    while i < len(legacy_cards):
        if _legacy_card_key(legacy_cards[i]) != "code_walkthrough":
            i += 1
            continue

        run_start = i
        while i < len(legacy_cards) and _legacy_card_key(legacy_cards[i]) == "code_walkthrough":
            i += 1
        run_end = i
        run = legacy_cards[run_start:run_end]
        if len(run) < 2:
            continue

        merged_run: list[dict[str, Any]] = []
        bucket: list[dict[str, Any]] = []
        bucket_lines = 0
        bucket_main = 0

        for card in run:
            card_points = [str(point) for point in (card.get("points") or [])]
            card_lines = max(1, len(card_points))
            card_main = max(1, _count_main_bullets(card_points))

            would_overflow = (
                bucket
                and (
                    bucket_lines + card_lines > _MAX_CODE_WALKTHROUGH_CARD_LINES
                    or bucket_main + card_main > _MAX_CODE_WALKTHROUGH_MAIN_IDEAS
                )
            )
            if would_overflow:
                merged_run.append(_merge_code_walkthrough_bucket(bucket))
                bucket = []
                bucket_lines = 0
                bucket_main = 0

            bucket.append(card)
            bucket_lines += card_lines
            bucket_main += card_main

        if bucket:
            merged_run.append(_merge_code_walkthrough_bucket(bucket))

        if len(merged_run) < len(run):
            legacy_cards[run_start:run_end] = merged_run
            i = run_start + len(merged_run)


def _legacy_card_key(card: dict[str, Any]) -> str:
    return str(card.get("blueprint_key") or card.get("card_type") or "").strip().lower()


def _merge_code_walkthrough_bucket(cards: list[dict[str, Any]]) -> dict[str, Any]:
    if len(cards) == 1:
        return cards[0]

    merged = dict(cards[0])
    points: list[str] = []
    code_parts: list[str] = []

    for card in cards:
        points.extend(str(point) for point in (card.get("points") or []))
        snippet = str(card.get("code_snippet") or "").strip("\n")
        if snippet:
            code_parts.append(snippet)

    merged["points"] = points
    if code_parts:
        # If snippets are cumulative, the last one is the best implementation
        # so far. If they are fragments, keep every piece; the accumulator will
        # stitch and normalize the complete sequence in the next pass.
        last_lines = code_parts[-1].splitlines()
        prior_lines = "\n".join(code_parts[:-1]).splitlines()
        if _line_prefix_matches(prior_lines, last_lines):
            merged["code_snippet"] = code_parts[-1]
        else:
            # Snippets aren't a clean cumulative prefix chain. The lean-lesson
            # convention is that each card's code_snippet is the
            # implementation-so-far (cumulative), so the most complete snippet is
            # the right one. JOINING them here duplicated code — e.g. a helper
            # function body reappearing dedented below the main function. Pick the
            # longest snippet instead of concatenating.
            merged["code_snippet"] = max(code_parts, key=lambda part: len(part.splitlines()))
    merged["highlight_lines_per_step"] = []
    merged["visual_plan"] = {}
    merged["visual_type"] = "code_trace"
    return merged


def _line_prefix_matches(prefix: list[str], candidate: list[str]) -> bool:
    if not prefix or len(candidate) < len(prefix):
        return False
    return candidate[: len(prefix)] == prefix


def _suffix_prefix_overlap(existing: list[str], incoming: list[str]) -> int:
    max_overlap = min(len(existing), len(incoming))
    for size in range(max_overlap, 0, -1):
        if existing[-size:] == incoming[:size]:
            return size
    return 0


def _materialize_worked_example_plan_to_cards(
    plan: dict[str, Any] | None,
    topic_hint: str,
) -> list[dict[str, Any]]:
    """Convert a worked_example_plan into a sequence of legacy worked_example
    cards that all share ONE base visual.

    PILOT: math_formula_method only. The LLM emits a single plan with
    problem_setup + solution_steps; this converter materializes one
    worked_example card per step. All cards reference the SAME shared
    progressive_step_flow visual; only `visual_focus.active_step` changes
    between cards. That gives the learner "movement through one visual"
    instead of "new image, new image, new image" — addressing the core
    rendering issue this architecture was designed to fix.

    Step text becomes the card points:
      main bullet: "Step <N> of <M>: <action>"
      sub-bullets: <text_points>, plus "Result: <intermediate_result>" if
                   present, plus "Now: <current_expression>" if present
    Each card's title is "Step <N> of <M>: <step_label>".

    Returns [] when no plan is supplied or solution_steps is empty.
    """
    if not isinstance(plan, dict):
        return []
    steps = plan.get("solution_steps") or []
    if not isinstance(steps, list) or not steps:
        return []

    total = len(steps)
    problem_setup = str(plan.get("problem_setup") or "").strip()
    terminal_desc = str(plan.get("terminal_state_description") or "").strip()

    # Build the SHARED progressive_step_flow visual that every materialized
    # card will reference. visual_steps[i] = {label, mini_visual} from
    # solution_steps[i]. The per-card visual is the same object; we only
    # vary active_step on visual_focus.
    visual_steps: list[dict[str, Any]] = []
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        label = str(step.get("step_label") or "").strip() or f"Step {i + 1}"
        mini = str(step.get("mini_visual") or "").strip()
        visual_steps.append({
            "kind": "step",
            "label": label,
            "step_title": label,
            "visual_label": label,
            "description": "",
            "step_detail": "",
            "mini_visual": mini,
            "formula": "",
            "cases": [],
            "active": False,  # per-card visual_focus.active_step picks the live one
        })

    shared_base_visual = {
        "type": "progressive_step_flow",
        "title": problem_setup or "Worked example",
        "purpose": terminal_desc or "Trace through the solution",
        "description": problem_setup,
        "placement": "card",
        "what_to_notice": "",
        "steps": visual_steps,
    }

    cards: list[dict[str, Any]] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        n = int(step.get("step_number") or (len(cards) + 1))
        label = str(step.get("step_label") or "").strip() or f"Step {n}"
        action = str(step.get("action") or "").strip()
        reason = str(step.get("reason") or "").strip()
        current_expr = str(step.get("current_expression") or "").strip()
        intermediate = str(step.get("intermediate_result") or "").strip()
        text_points = step.get("text_points") or []
        if not isinstance(text_points, list):
            text_points = []

        title = f"Step {n} of {total}: {label}"

        # Bullet structure for the materialized card:
        #   main bullet: the action (with terminal colon if there are subs)
        #   sub-bullets: reason + text_points + result/expression trackers
        points: list[str] = []
        main_bullet = action.rstrip(":") + ":" if action else f"Step {n} of {total}:"
        points.append(main_bullet)
        if reason:
            points.append(f"  - Why: {reason}")
        for tp in text_points:
            tp_str = str(tp).rstrip()
            if not tp_str:
                continue
            # Promote to a sub-bullet if it isn't already
            if not tp_str.lstrip().startswith("- ") and not tp_str.startswith("  "):
                tp_str = "  - " + tp_str.lstrip("- ").lstrip()
            points.append(tp_str)
        if current_expr:
            points.append(f"  - Now: {current_expr}")
        if intermediate:
            points.append(f"  - Result: {intermediate}")

        # The card's visual is the SHARED base visual (deep-copied so each
        # card can carry its own active_step on visual_focus without
        # mutating the others). The shared structure is intentional —
        # frontend renders the same step_flow across every step card.
        import copy
        visual_for_card = copy.deepcopy(shared_base_visual)

        cards.append({
            "card_type": "worked_example",
            "blueprint_key": "worked_example",
            "example_type": "setup_calculation_interpretation_example",
            "id": "",
            "title": title,
            "learning_job": label,
            "body": [],
            "points": points,
            "visual_type": "progressive_step_flow",
            "visual_plan": visual_for_card,
            "visual_description": (
                f"Step-flow showing the solve in progress. Active step: "
                f"{label}. {intermediate or current_expr or ''}".strip()
            ),
            "visual_index": -1,
            "annotations": [],
            "example": "",
            "micro_check": _EMPTY_MICRO_CHECK.copy(),
            "what_to_notice": (
                f"Step {n} of {total} is active: {label}. "
                f"{intermediate or current_expr or ''}"
            ).strip(),
            "next_transition": "",
            "estimated_seconds": 35,
            "transition_text": "",
            "next_card_label": "Next",
            "practice_question_index": None,
            "code_snippet": "",
            "code_language": "",
            "highlight_lines_per_step": [],
            "continuation_group_id": "math_worked_example_plan",
            "continuation_index": n,
            "continuation_total": total,
            "continuation_reason": "worked_example_plan",
            "continues_from_previous": n > 1,
            "visual_focus": {
                "active_nodes": [],
                "highlight_path": [],
                "active_step": n - 1,  # 0-based: drives which step lights up
                "attention_note": (
                    f"Step {n} of {total} — {action}".strip(" —")
                ),
            },
        })

    return cards


_NODE_LINK_WORKED_EXAMPLE_TOPIC_TYPES = frozenset({
    "algorithm_walkthrough",
    "data_structure_operation",
})

_NODE_STATE_TO_RELATION_OVERLAY = {
    "current": "current",
    "newly_discovered": "newly_discovered",
    "discovered": "discovered",
    "completed": "completed",
    "skipped": "skipped",
    "unvisited": "unvisited",
}


def _extract_output_values_from_card(
    card: dict[str, Any],
    valid_labels: set[str],
) -> list[str]:
    """Parse the output/result list the LLM wrote in card bullets.

    Patterns: 'result=[20, 30]', 'output=[20]', 'result: [20, 30]'.
    Returns the latest such list (so 'Now: result=[20,30]' wins over an
    earlier 'Currently: result=[]'), filtered to valid node labels.
    """
    text = " ".join(str(p) for p in (card.get("points") or []))
    matches = list(
        re.finditer(
            r"(?:result|output)\s*[:=]\s*\[([^\]]*)\]",
            text,
            flags=re.IGNORECASE,
        )
    )
    if not matches:
        return []
    inner = matches[-1].group(1)
    tokens = re.findall(r"\d{1,3}", inner)
    return [t for t in tokens if t in valid_labels]


def _synthesize_node_link_plan_from_lean_cards(
    lean_cards: list[dict[str, Any]],
    topic_hint: str,
) -> dict[str, Any] | None:
    """Reconstruct a node_link_worked_example plan from raw LLM cards.

    When the LLM emits per-step `worked_example` cards with node_link
    visuals INSTEAD OF the top-level `node_link_worked_example` plan, the
    materializer never fires and the learner sees the LLM's hallucinated
    per-card trees. This synthesizer rebuilds an equivalent plan so the
    materializer can run anyway:

      - base_visual.nodes/edges    ← background card's visual_nodes/edges
        (the canonical structure the prompt forced the LLM to commit to)
      - solution_steps[i].action   ← worked_example card title
      - .visual_delta.active_node  ← explicit 'current=X' in card text
      - .runtime_state.call_stack  ← 'Call stack: [50→30]' in card text
      - .runtime_state.output      ← 'result=[20, 30]' in card text
      - .visual_delta.completed_nodes ← cumulative output across steps

    Returns None when there's no background node_link visual or no
    worked_example cards.
    """
    # RETIRED (accuracy: don't reconstruct/guess a graph plan). Returning None makes the caller
    # skip plan synthesis; the worked example is authored by the solver instead. Body kept below.
    return None
    base_nodes: list[dict[str, Any]] = []
    base_edges: list[dict[str, Any]] = []
    for card in lean_cards:
        blueprint = str(card.get("blueprint_key") or "").strip().lower()
        if blueprint != "background":
            continue
        vt = _normalize_visual_type(card.get("visual_type"))
        if vt != "node_link_diagram":
            continue
        nodes = _validated_node_link_nodes(card.get("visual_nodes") or [])
        edges = _validated_visual_edges(card.get("visual_edges") or [])
        if len(nodes) >= 4:
            base_nodes = [dict(n) for n in nodes]
            base_edges = [dict(e) for e in edges]
            break

    if not base_nodes:
        return None

    worked_cards = [
        c for c in lean_cards
        if str(c.get("blueprint_key") or "").strip().lower() == "worked_example"
    ]
    if not worked_cards:
        return None

    valid_labels = {str(n.get("label") or n.get("id") or "") for n in base_nodes}
    valid_labels.discard("")

    bst_traversal = _detect_bst_traversal(topic_hint)
    topic_lower = (topic_hint or "").lower()
    if bst_traversal or "bst" in topic_lower or "tree" in topic_lower:
        mode = "tree"
    elif "graph" in topic_lower or "bfs" in topic_lower or "dfs" in topic_lower:
        mode = "graph"
    else:
        mode = "tree"

    solution_steps: list[dict[str, Any]] = []
    cumulative_output: list[str] = []

    for i, card in enumerate(worked_cards):
        action = str(card.get("title") or "").strip() or f"Step {i + 1}"
        reason = str(card.get("learning_job") or card.get("main_concept") or "").strip()
        text_points = [
            str(p).rstrip()
            for p in (card.get("points") or [])
            if str(p).strip()
        ]

        active_node = _extract_current_node_from_card(card, valid_labels) or ""
        call_stack = _extract_call_stack_from_card(card, valid_labels)
        output_now = _extract_output_values_from_card(card, valid_labels)

        for v in output_now:
            if v not in cumulative_output:
                cumulative_output.append(v)

        focus = card.get("visual_focus") or {}
        attention_note = (
            str(focus.get("attention_note") or "").strip()
            if isinstance(focus, dict)
            else ""
        )
        if not attention_note:
            attention_note = str(card.get("what_to_notice") or "").strip()
        if not attention_note and active_node:
            attention_note = f"Currently at node {active_node}."

        node_state_map: list[dict[str, str]] = []
        for v in cumulative_output:
            if v == active_node:
                continue
            node_state_map.append({"node_id": v, "state": "completed"})
        if active_node:
            node_state_map.append({"node_id": active_node, "state": "current"})

        solution_steps.append({
            "step_number": i + 1,
            "action": action,
            "reason": reason,
            "text_points": text_points,
            "visual_delta": {
                "active_node": active_node,
                "active_edge_from": "",
                "active_edge_to": "",
                "completed_nodes": list(cumulative_output),
                "completed_edges_from": [],
                "completed_edges_to": [],
                "node_state_map": node_state_map,
                "attention_note": attention_note,
            },
            "runtime_state": {
                "call_stack": call_stack,
                "output": list(cumulative_output),
                "frontier": [],
                "frontier_kind": "",
                "variables": [],
            },
        })

    if not solution_steps:
        return None

    addons = (
        ["call_stack", "output_list"]
        if mode == "tree"
        else ["frontier_view", "output_list"]
    )

    traversal_name = bst_traversal or "traversal"
    return {
        "problem_setup": (
            f"Trace {traversal_name} on the BST with {len(base_nodes)} nodes."
            if mode == "tree"
            else f"Trace {traversal_name} on the graph."
        ),
        "terminal_state_description": (
            "All nodes have been visited; the output list contains every value."
        ),
        "base_visual": {
            "visual_type": "node_link",
            "mode": mode,
            "purpose": (
                f"Trace the {traversal_name} progression through the structure "
                "as the active node advances."
            ),
            "visual_blueprint": (
                f"{mode.capitalize()} with {len(base_nodes)} nodes; structure "
                "is the same as the background card."
            ),
            "nodes": base_nodes,
            "edges": base_edges,
        },
        "addons": addons,
        "solution_steps": solution_steps,
    }


def _materialize_node_link_worked_example_to_cards(
    plan: dict[str, Any] | None,
    topic_hint: str,
) -> list[dict[str, Any]]:
    """Convert a node_link_worked_example plan into per-step worked_example
    cards that all share ONE base visual.

    Architecture this implements:
      - base_visual (nodes/edges) is built ONCE by the LLM
      - each card deep-copies it so per-card state overlays don't mutate
        the shared structure
      - per-step visual_delta is applied to the card's copy: active_node
        gets relation="current", node_state_map updates per-node relations,
        completed_edges get style="completed", active_edge gets style="active"
      - runtime_state (call_stack, output, frontier, variables) is rendered
        as bullets and/or visual_focus content; addons[] declares which
        side panels the frontend should display
      - all cards carry the visual_blueprint and purpose from the base_visual
        so the renderer + validator can read the LLM's design intent

    The current frontend renderer for node_link_diagram reads nodes/edges/
    relations directly, so the materialized cards work without a frontend
    rebuild — the persistent-base pattern is implemented entirely backend-side
    by deep-copying the base into each card and varying only the overlays.
    """
    if not isinstance(plan, dict):
        return []
    steps = plan.get("solution_steps") or []
    if not isinstance(steps, list) or not steps:
        return []
    base_visual = plan.get("base_visual") or {}
    if not isinstance(base_visual, dict):
        return []
    base_nodes = base_visual.get("nodes") or []
    base_edges = base_visual.get("edges") or []
    if not base_nodes:
        # No structure to render against; skip the materialization rather
        # than emit empty visuals.
        return []

    total = len(steps)
    problem_setup = str(plan.get("problem_setup") or "").strip()
    terminal_desc = str(plan.get("terminal_state_description") or "").strip()
    addons = plan.get("addons") or []
    if not isinstance(addons, list):
        addons = []

    # Validate against the visual_blueprint / purpose intent. These don't
    # block — they attach as warnings so generation always completes — but
    # they create a hook for the LLM's design commitment to be checked.
    purpose = str(base_visual.get("purpose") or "").strip()
    blueprint = str(base_visual.get("visual_blueprint") or "").strip()
    mode = str(base_visual.get("mode") or "graph").strip().lower()

    import copy

    cards: list[dict[str, Any]] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        n = int(step.get("step_number") or (len(cards) + 1))
        action = str(step.get("action") or "").strip()
        reason = str(step.get("reason") or "").strip()
        text_points = step.get("text_points") or []
        if not isinstance(text_points, list):
            text_points = []

        # ---- Build the per-card visual: deep-copy of the shared base ----
        # then apply the step's visual_delta as overlays.
        delta = step.get("visual_delta") or {}
        active_node = str(delta.get("active_node") or "").strip()
        active_edge_from = str(delta.get("active_edge_from") or "").strip()
        active_edge_to = str(delta.get("active_edge_to") or "").strip()
        completed_nodes = set(
            str(x) for x in (delta.get("completed_nodes") or []) if str(x).strip()
        )
        completed_edges_from = delta.get("completed_edges_from") or []
        completed_edges_to = delta.get("completed_edges_to") or []
        # Build a set of completed (from, to) edge pairs.
        completed_edge_pairs = set()
        if isinstance(completed_edges_from, list) and isinstance(completed_edges_to, list):
            for f, t in zip(completed_edges_from, completed_edges_to):
                completed_edge_pairs.add((str(f), str(t)))

        # Build node_id → state lookup from the state map.
        node_state_overrides: dict[str, str] = {}
        node_state_map = delta.get("node_state_map") or []
        if isinstance(node_state_map, list):
            for entry in node_state_map:
                if not isinstance(entry, dict):
                    continue
                node_id = str(entry.get("node_id") or "").strip()
                state = str(entry.get("state") or "").strip()
                if node_id and state in _NODE_STATE_TO_RELATION_OVERLAY:
                    node_state_overrides[node_id] = state

        per_card_nodes: list[dict[str, Any]] = []
        for base_node in base_nodes:
            node_copy = copy.deepcopy(base_node) if isinstance(base_node, dict) else {}
            node_id = str(node_copy.get("id") or node_copy.get("label") or "").strip()
            # Apply state precedence: explicit state map > active_node > completed.
            if node_id in node_state_overrides:
                node_copy["relation"] = node_state_overrides[node_id]
                node_copy["state"] = node_state_overrides[node_id]
            elif node_id == active_node and active_node:
                node_copy["relation"] = "current"
                node_copy["state"] = "current"
            elif node_id in completed_nodes:
                node_copy["relation"] = "completed"
                node_copy["state"] = "completed"
            per_card_nodes.append(node_copy)

        per_card_edges: list[dict[str, Any]] = []
        for base_edge in base_edges:
            edge_copy = copy.deepcopy(base_edge) if isinstance(base_edge, dict) else {}
            ef = str(edge_copy.get("from") or "").strip()
            et = str(edge_copy.get("to") or "").strip()
            if active_edge_from and active_edge_to and ef == active_edge_from and et == active_edge_to:
                edge_copy["style"] = "active"
                edge_copy["state"] = "active"
            elif (ef, et) in completed_edge_pairs:
                edge_copy["style"] = "traversal"
                edge_copy["state"] = "traversed"
            per_card_edges.append(edge_copy)

        visual_for_card: dict[str, Any] = {
            "type": "node_link_diagram",
            "mode": mode,
            "title": problem_setup or "Worked example",
            "purpose": purpose,
            "description": blueprint,
            "visual_blueprint": blueprint,
            "placement": "card",
            "what_to_notice": str(delta.get("attention_note") or "").strip(),
            "nodes": per_card_nodes,
            "edges": per_card_edges,
            "addons": list(addons),
        }

        # ---- Build the runtime_state addon bullets ----
        runtime = step.get("runtime_state") or {}
        runtime_bullet_lines: list[str] = []
        call_stack = runtime.get("call_stack")
        if isinstance(call_stack, list) and call_stack:
            runtime_bullet_lines.append(
                f"  - Call stack: [{' → '.join(str(x) for x in call_stack)}]"
            )
        frontier = runtime.get("frontier")
        frontier_kind = runtime.get("frontier_kind") or "frontier"
        if isinstance(frontier, list) and frontier:
            runtime_bullet_lines.append(
                f"  - {str(frontier_kind).capitalize()}: [{', '.join(str(x) for x in frontier)}]"
            )
        output = runtime.get("output")
        if isinstance(output, list) and output:
            runtime_bullet_lines.append(
                f"  - Output: [{', '.join(str(x) for x in output)}]"
            )
        variables = runtime.get("variables")
        if isinstance(variables, list) and variables:
            for var in variables:
                if isinstance(var, dict):
                    n_name = str(var.get("name") or "").strip()
                    n_val = str(var.get("value") or "").strip()
                    if n_name and n_val:
                        runtime_bullet_lines.append(f"  - {n_name}={n_val}")

        # ---- Build the card points ----
        points: list[str] = []
        main_bullet = action.rstrip(":") + ":" if action else f"Step {n} of {total}:"
        points.append(main_bullet)
        if reason:
            points.append(f"  - Why: {reason}")
        for tp in text_points:
            tp_str = str(tp).rstrip()
            if not tp_str:
                continue
            if not tp_str.lstrip().startswith("- ") and not tp_str.startswith("  "):
                tp_str = "  - " + tp_str.lstrip("- ").lstrip()
            points.append(tp_str)
        points.extend(runtime_bullet_lines)

        # ---- Build visual_focus for the persistent overlay layer ----
        # active_nodes carries the current node so the frontend can
        # highlight; highlight_path carries the cumulative completed nodes
        # so a trail can be shown.
        ordered_completed = [
            str(n_) for n_ in (delta.get("completed_nodes") or [])
            if isinstance(n_, (str, int)) and str(n_).strip()
        ]
        attention = (
            str(delta.get("attention_note") or "").strip()
            or (f"Step {n} of {total}: {action}".strip(" :"))
        )

        title = f"Step {n} of {total}: {action.rstrip('.')}" if action else f"Step {n} of {total}"

        cards.append({
            "card_type": "worked_example",
            "blueprint_key": "worked_example",
            "example_type": "state_trace_example",
            "id": "",
            "title": title,
            "learning_job": action[:80],
            "body": [],
            "points": points,
            "visual_type": "node_link_diagram",
            "visual_plan": visual_for_card,
            "visual_description": blueprint or f"Trace step {n}/{total}.",
            "visual_index": -1,
            "annotations": [],
            "example": "",
            "micro_check": _EMPTY_MICRO_CHECK.copy(),
            "what_to_notice": attention,
            "next_transition": "",
            "estimated_seconds": 35,
            "transition_text": "",
            "next_card_label": "Next",
            "practice_question_index": None,
            "code_snippet": "",
            "code_language": "",
            "highlight_lines_per_step": [],
            "continuation_group_id": "node_link_worked_example",
            "continuation_index": n,
            "continuation_total": total,
            "continuation_reason": "node_link_worked_example",
            "continues_from_previous": n > 1,
            "visual_focus": {
                "active_nodes": [active_node] if active_node else [],
                "highlight_path": ordered_completed + ([active_node] if active_node else []),
                "active_step": n - 1,
                "attention_note": attention,
            },
        })

    return cards


def _convert_lean_to_legacy(
    lean_json: dict[str, Any],
    topic: Topic,
    chunks: list[ContentChunk],
) -> dict[str, Any]:
    """Convert lean lesson JSON to the legacy lesson_json format."""
    practice_questions: list[dict[str, Any]] = []
    legacy_cards: list[dict[str, Any]] = []
    lean_cards = _normalize_lean_card_order(lean_json.get("cards") or [], topic)
    forbidden_key_terms = _forbidden_key_terms_for_topic(topic)
    topic_hint = f"{topic.title} {getattr(topic, 'description', None) or ''}".strip()
    topic_type_for_routing = _topic_type_key(topic)

    # PILOT: worked_example_plan architecture for math_formula_method topics.
    # If the LLM emitted a worked_example_plan, materialize it into shared-
    # base-visual cards BEFORE converting the lean_cards. Any per-step
    # worked_example cards the LLM also emitted are dropped — the plan
    # supersedes them.
    materialized_we_cards: list[dict[str, Any]] = []
    if topic_type_for_routing == "math_formula_method":
        materialized_we_cards = _materialize_worked_example_plan_to_cards(
            lean_json.get("worked_example_plan"),
            topic_hint=topic_hint,
        )

    # PILOT v2: node_link_worked_example for algorithm/data-structure topics.
    # Same persistent-base-plus-deltas architecture, but the base visual is
    # a node_link (tree/graph/state-machine). The LLM commits to base nodes
    # + edges + purpose + visual_blueprint ONCE; each step only emits the
    # visual_delta + runtime_state. The materializer deep-copies the base
    # onto every card and applies the step's overlays.
    if (
        not materialized_we_cards
        and topic_type_for_routing in _NODE_LINK_WORKED_EXAMPLE_TOPIC_TYPES
    ):
        materialized_we_cards = _materialize_node_link_worked_example_to_cards(
            lean_json.get("node_link_worked_example"),
            topic_hint=topic_hint,
        )
        # SAFETY NET: when the LLM ignored the plan path and emitted per-step
        # worked_example cards instead, synthesize a plan from those cards +
        # the background card's visual structure, then run the materializer
        # on the synthesized plan. This forces the persistent-base-plus-deltas
        # rendering regardless of LLM compliance.
        if not materialized_we_cards:
            synthesized_plan = _synthesize_node_link_plan_from_lean_cards(
                lean_cards=lean_cards,
                topic_hint=topic_hint,
            )
            if synthesized_plan:
                materialized_we_cards = _materialize_node_link_worked_example_to_cards(
                    synthesized_plan,
                    topic_hint=topic_hint,
                )

    we_plan_inserted = False
    for i, lean_card in enumerate(lean_cards):
        lean_card = _filter_assumed_components_terms(
            lean_card=lean_card,
            forbidden_terms=forbidden_key_terms,
        )
        if not _should_keep_lean_card(lean_card):
            continue

        # When the plan path is active, drop LLM-emitted worked_example
        # cards (the plan replaces them) and insert the materialized cards
        # at the first worked_example slot we would otherwise have emitted.
        if materialized_we_cards:
            blueprint_key = str(
                lean_card.get("blueprint_key") or lean_card.get("card_type") or ""
            ).strip().lower()
            if blueprint_key == "worked_example":
                if not we_plan_inserted:
                    legacy_cards.extend(materialized_we_cards)
                    we_plan_inserted = True
                continue

        legacy_cards.append(_lean_card_to_legacy(lean_card, i, practice_questions, topic_hint=topic_hint))

    # If we have materialized cards but never hit a worked_example slot in
    # the LLM output (LLM emitted the plan only, no worked_example cards),
    # append them at the end of the lesson.
    if materialized_we_cards and not we_plan_inserted:
        legacy_cards.extend(materialized_we_cards)

    # NOTE: the old `_retry_missing_visuals` second-LLM pass has been removed.
    # When a card's visual fields come out empty, the frontend's tightened
    # `isLessonVisualRenderable` now hides the empty visual cleanly instead
    # of synthesizing a fallback. Saves one LLM call per ~22% of lessons.

    # Make code_walkthrough cards accumulate code across the topic so the
    # learner sees the implementation grow line-by-line and the final card
    # has the complete program. The LLM frequently emits only the NEW lines
    # per card, so the visual would otherwise show disjoint snippets.
    _merge_tiny_code_walkthrough_cards(legacy_cards)
    _split_coarse_code_walkthrough_bullets(legacy_cards)
    _strip_code_only_bullets_from_code_walkthrough(legacy_cards)
    _accumulate_code_walkthrough_visuals(legacy_cards)
    topic_type_key = topic_type_for_routing  # used by the guards below
    # The coding-specific rebuilders are RETIRED: the per-line walkthrough rebuilder corrupted
    # valid code (merge sort's left/right), worked examples are now authored by the solver, and
    # the graph-visual synthesis was retired. We keep the LLM's own code_walkthrough cards and
    # render the code in an IDE panel — trust the model, don't re-derive.

    # When the node_link_worked_example plan path produced cards, those
    # cards already carry per-step visual state (active nodes, completed
    # edges, etc.) materialized from the LLM's solution_steps. Skip the
    # legacy graph-traversal replacement and BST overlay passes — they
    # were written to repair LLM-emitted per-card visuals, which the new
    # path doesn't produce.
    node_link_we_path_active = bool(
        materialized_we_cards
        and topic_type_for_routing in _NODE_LINK_WORKED_EXAMPLE_TOPIC_TYPES
        and any(
            c.get("continuation_group_id") == "node_link_worked_example"
            for c in legacy_cards
        )
    )

    if topic_type_key != "coding_implementation" and not node_link_we_path_active:
        _replace_graph_traversal_worked_examples_with_trace(legacy_cards, topic_hint=topic_hint)
    _unify_process_card_steps(legacy_cards, topic_hint=topic_hint)
    _ensure_progressive_step_flow_steps(legacy_cards, topic_hint=topic_hint)
    if topic_type_key != "coding_implementation" and not node_link_we_path_active:
        _apply_traversal_highlights_to_worked_examples(legacy_cards, topic_hint=topic_hint)
        _add_scenario_to_worked_examples(legacy_cards, topic_hint=topic_hint)
    _add_completion_state_to_background_cards(
        legacy_cards,
        topic_hint=topic_hint,
        topic_type=_topic_type_key(topic),
    )
    _ensure_generic_worked_example_setup_cards(legacy_cards)
    # Non-code cards (components_terms / process / background) must not carry a code
    # visual — strip any empty/misplaced code panels.
    _strip_misplaced_code_visuals(legacy_cards)
    # Edge cases must DESCRIBE a boundary, not re-trace the example: drop trace-style
    # edge cases, then group the rest AFTER the worked example (never between steps).
    _drop_trace_style_edge_cases(legacy_cards)
    _group_edge_cases_after_worked_examples(legacy_cards)

    empty_report = {"is_valid": True, "requires_regeneration": False, "issues": []}

    return {
        "lesson_version": 2,
        "title": str(lean_json.get("title") or topic.title),
        "topic_summary": str(lean_json.get("topic_summary") or ""),
        "estimated_minutes": int(lean_json.get("estimated_minutes") or 8),
        "example_plan": _normalize_example_plan(lean_json.get("example_plan")),
        "lesson_cards": legacy_cards,
        "practice_questions": practice_questions,
        "visual_plan": [],
        "key_takeaways": [],
        "source_chunk_ids": build_source_chunk_ids(chunks),
        "source_summary": build_source_summary(chunks),
        "adaptation_metadata": {
            "starting_mode": "default",
            "estimated_state": "not_provided",
            "adaptation_summary": "Lean lesson (v2).",
            "teaching_strategy": "lean_default",
        },
        "scope_validation_report": empty_report,
        "visual_validation_report": empty_report,
        "topic_quality_report": empty_report,
        "validation_report": empty_report,
        "microcheck_validation_report": empty_report,
        "interactive_link_validation_report": empty_report,
    }


def _ensure_generic_worked_example_setup_cards(cards: list[dict[str, Any]]) -> None:
    """Add EXACTLY ONE problem/setup card, immediately before the FIRST worked-example card —
    never between steps, never for a later run. A worked-example setup states the problem and
    belongs only at the very start of the example.
    """
    first = next(
        (i for i, c in enumerate(cards)
         if isinstance(c, dict) and str(c.get("blueprint_key") or "").strip().lower() == "worked_example"),
        None,
    )
    if first is None:
        return
    first_card = cards[first]
    # Already a setup, or the card immediately before it is one -> nothing to add.
    if _is_generic_worked_example_setup_card(first_card):
        return
    if first > 0 and isinstance(cards[first - 1], dict) and _is_generic_worked_example_setup_card(cards[first - 1]):
        return
    # Node-link/tree traces get a structured visual setup from the bridge instead.
    visual_plan = first_card.get("visual_plan") if isinstance(first_card.get("visual_plan"), dict) else {}
    if _normalize_visual_type(first_card.get("visual_type")) == "node_link_diagram" or visual_plan.get("nodes"):
        return
    cards.insert(first, _generic_worked_example_setup_card(first_card, first))


def _is_generic_worked_example_setup_card(card: dict[str, Any]) -> bool:
    metadata = card.get("metadata") if isinstance(card.get("metadata"), dict) else {}
    if metadata.get("worked_example_setup") is True:
        return True
    example_type = str(card.get("example_type") or "").strip().lower()
    if example_type in {"problem_setup", "initial_state", "worked_example_setup"}:
        return True
    title = str(card.get("title") or "").strip().lower()
    return "setup" in title or "initial state" in title or title.startswith("problem:")


def _generic_worked_example_setup_card(first_card: dict[str, Any], index: int) -> dict[str, Any]:
    title = str(first_card.get("title") or "Worked Example").strip()
    body = [
        str(item)
        for item in (first_card.get("body") or [])
        if str(item).strip()
    ]
    visual_description = str(
        first_card.get("visual_description")
        or first_card.get("what_to_notice")
        or first_card.get("learning_goal")
        or first_card.get("main_concept")
        or title
    ).strip()
    setup_summary = body[0] if body else visual_description

    # Inherit a structural visual (graph/tree node_link) from the first worked
    # card so the setup card SHOWS the example structure at rest instead of being
    # a text-only "none" card. This is what makes graph BFS/DFS (and any other
    # node_link) worked examples open on the diagram, matching the tree path.
    # Purely procedural/math worked examples (no node_link) keep no visual.
    import copy as _copy

    src_plan = first_card.get("visual_plan") if isinstance(first_card.get("visual_plan"), dict) else {}
    src_type = str(first_card.get("visual_type") or src_plan.get("type") or "").strip().lower()
    src_nodes = src_plan.get("nodes") or first_card.get("visual_nodes")
    # Inherit the first worked card's visual so the setup SHOWS the problem at rest
    # (the array, grid, graph, etc.) instead of being a text-only card — for EVERY
    # visual type, not just node_link.
    has_visual = bool(src_type) and src_type != "none" and bool(src_plan or src_nodes)
    if has_visual:
        is_node_link = "node_link" in src_type
        setup_visual_type = "node_link_diagram" if is_node_link else src_type
        setup_visual_plan = _copy.deepcopy(src_plan) if src_plan else {}
        if is_node_link:
            setup_visual_plan = setup_visual_plan if setup_visual_plan.get("nodes") else {
                "type": "node_link_diagram",
                "nodes": _copy.deepcopy(first_card.get("visual_nodes") or []),
                "edges": _copy.deepcopy(first_card.get("visual_edges") or []),
            }
            setup_visual_plan["type"] = "node_link_diagram"
        setup_visual_nodes = _copy.deepcopy(setup_visual_plan.get("nodes") or first_card.get("visual_nodes") or [])
        setup_visual_edges = _copy.deepcopy(setup_visual_plan.get("edges") or first_card.get("visual_edges") or [])
        setup_visual_desc = "The problem at rest, before the first step runs."
    else:
        setup_visual_type = "none"
        setup_visual_plan = {}
        setup_visual_nodes = None
        setup_visual_edges = None
        setup_visual_desc = ""

    return {
        "id": f"{first_card.get('id') or index + 1}-setup",
        "blueprint_key": "worked_example",
        "card_type": "worked_example",
        "title": "Worked Example Setup",
        "points": [
            "Problem:",
            f"  - {setup_summary}",
        ],
        "body": [setup_summary] if setup_summary else [],
        "bullets": [],
        "main_concept": "Understand the starting point for the worked example.",
        "learning_goal": "Understand the starting point for the worked example.",
        "example_type": "problem_setup",
        "visual_type": setup_visual_type,
        "new_concepts": [],
        "review_concepts": [],
        "prerequisite_concepts": [],
        "common_misconceptions": [],
        "concept_support": [],
        "interactive_links": [],
        "styled_elements": [],
        "visual_plan": setup_visual_plan,
        "visual_nodes": setup_visual_nodes,
        "visual_edges": setup_visual_edges,
        "visual_description": setup_visual_desc,
        "visual_index": -1,
        "annotations": [],
        "example": "",
        "micro_check": _EMPTY_MICRO_CHECK.copy(),
        "what_to_notice": setup_summary,
        "next_transition": "",
        "estimated_seconds": 25,
        "transition_text": "",
        "next_card_label": "Next",
        "practice_question_index": None,
        "code_snippet": "",
        "code_language": "",
        "highlight_lines_per_step": [],
        "continuation_group_id": "worked_example_setup",
        "continuation_index": 0,
        "continuation_total": 0,
        "continuation_reason": "problem_setup",
        "continues_from_previous": False,
        "visual_focus": {
            "active_nodes": [],
            "highlight_path": [],
            "active_step": -1,
            "attention_note": setup_summary,
        },
        "metadata": {"worked_example_setup": True},
    }


def patch_lesson_visuals(lesson_json: dict[str, Any], topic_type: str) -> dict[str, Any]:
    """Re-generate structured visual_plan data for qualifying cards without touching text content."""
    import copy
    from app.core.course_blueprints import get_topic_blueprint
    from app.services.llm_client import generate_visual_patches

    blueprint = get_topic_blueprint(topic_type)
    visual_card_rules: dict[str, Any] = blueprint.get("visual_card_rules") or {}

    cards: list[dict[str, Any]] = lesson_json.get("lesson_cards") or []

    card_summaries: list[dict[str, Any]] = []
    allowed_type_by_id: dict[str, str] = {}
    for card in cards:
        blueprint_key = str(card.get("blueprint_key") or "")
        visual_rule = visual_card_rules.get(blueprint_key) or {}
        allowed_visual_type = _choose_allowed_visual_type(
            visual_rule.get("visual_type") or "none",
            card,
        )
        if allowed_visual_type == "none":
            continue
        card_id = str(card.get("id") or "")
        allowed_type_by_id[card_id] = allowed_visual_type
        card_summaries.append({
            "card_id": card_id,
            "title": str(card.get("title") or ""),
            "card_type": str(card.get("card_type") or blueprint_key),
            "blueprint_key": blueprint_key,
            "allowed_visual_type": allowed_visual_type,
            "visual_description": str(card.get("visual_description") or ""),
            "points": [str(p) for p in (card.get("points") or []) if str(p).strip()],
        })

    if not card_summaries:
        return lesson_json

    patches = generate_visual_patches(card_summaries)
    patch_by_id = {str(p.get("card_id") or ""): p for p in patches}

    updated_json = copy.deepcopy(lesson_json)
    for card in updated_json.get("lesson_cards") or []:
        card_id = str(card.get("id") or "")
        patch = patch_by_id.get(card_id)
        if not patch:
            continue
        # Pin the visual type from the blueprint — don't let the AI override it.
        forced_visual_type = allowed_type_by_id.get(card_id) or _normalize_visual_type(patch.get("visual_type"))

        points = [str(p) for p in (card.get("points") or []) if str(p).strip()]
        visual_plan = _build_visual_plan(
            visual_type=forced_visual_type,
            title=str(card.get("title") or ""),
            purpose=str(card.get("visual_description") or ""),
            visual_description=str(patch.get("visual_description") or card.get("visual_description") or ""),
            visual_columns=patch.get("visual_columns"),
            visual_rows=patch.get("visual_rows"),
            visual_highlight_row=patch.get("visual_highlight_row"),
            visual_steps=patch.get("visual_steps"),
            visual_formula=patch.get("visual_formula"),
            visual_symbols=patch.get("visual_symbols"),
            visual_when_to_use=patch.get("visual_when_to_use"),
            visual_center=patch.get("visual_center"),
            visual_nodes=patch.get("visual_nodes"),
            visual_edges=patch.get("visual_edges"),
            visual_wrong=patch.get("visual_wrong"),
            visual_correct=patch.get("visual_correct"),
            visual_wrong_label=patch.get("visual_wrong_label"),
            visual_correct_label=patch.get("visual_correct_label"),
            visual_why=patch.get("visual_why"),
            visual_x_label=patch.get("visual_x_label"),
            visual_y_label=patch.get("visual_y_label"),
            visual_data_points=patch.get("visual_data_points"),
            visual_key_points=patch.get("visual_key_points"),
            visual_array_values=patch.get("visual_array_values"),
            visual_array_rows=patch.get("visual_array_rows"),
            visual_array_pointers=patch.get("visual_array_pointers"),
            visual_array_ranges=patch.get("visual_array_ranges"),
            visual_array_annotations=patch.get("visual_array_annotations"),
            points=points,
            code_snippet="",
            code_language="",
        )
        card["visual_plan"] = visual_plan
        card["visual_type"] = forced_visual_type
        if patch.get("visual_focus"):
            card["visual_focus"] = patch["visual_focus"]
            if patch["visual_focus"].get("attention_note"):
                card["what_to_notice"] = patch["visual_focus"]["attention_note"]

    return updated_json


def build_lean_lesson_from_topic_and_chunks(
    topic: Topic,
    chunks: list[ContentChunk],
    feedback: str | None = None,
) -> dict[str, Any]:
    """Generate a lean lesson in a single LLM call.

    The previous version ran an `_example_quality_issues` check and triggered
    a full second LLM call when thresholds (e.g. "fewer than 5 worked-example
    steps", "fewer than 7 traversal nodes") weren't met. In practice the
    retry fired ~42% of the time, doubling per-topic latency and spend for a
    quality bump that was marginal. The thresholds are now enforced by the
    prompt's QUALITY GATES section; the second-pass safety net is gone.
    """
    user_prompt = build_lean_user_prompt(topic=topic, chunks=chunks, feedback=feedback)
    lean_json = generate_lean_structured_lesson(
        system_prompt=LEAN_SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )
    legacy = _convert_lean_to_legacy(lean_json=lean_json, topic=topic, chunks=chunks)
    _assert_lesson_is_renderable(legacy, topic)
    return legacy


def build_lean_lesson_streaming(
    topic: Topic,
    chunks: list[ContentChunk],
    feedback: str | None = None,
):
    """Streaming variant of build_lean_lesson_from_topic_and_chunks.

    Yields ("card", raw_card) for each lesson card as the model produces it (a
    lightweight text preview so the learner can start reading early cards), then
    ("complete", legacy_lesson_json) once the full lesson has been generated and
    run through the SAME post-processing (_convert_lean_to_legacy) as the
    blocking path. The preview cards are pre-post-processing, so the final
    lesson is the source of truth — callers replace the preview on "complete".
    """
    from app.services.llm_client import generate_lean_structured_lesson_streaming

    user_prompt = build_lean_user_prompt(topic=topic, chunks=chunks, feedback=feedback)
    lean_json: dict[str, Any] | None = None
    for kind, payload in generate_lean_structured_lesson_streaming(
        system_prompt=LEAN_SYSTEM_PROMPT,
        user_prompt=user_prompt,
    ):
        if kind == "card" and isinstance(payload, dict):
            yield ("card", payload)
        elif kind == "lesson" and isinstance(payload, dict):
            lean_json = payload
    if lean_json is None:
        raise RuntimeError("streaming lean lesson produced no final JSON")
    legacy = _convert_lean_to_legacy(lean_json=lean_json, topic=topic, chunks=chunks)
    _assert_lesson_is_renderable(legacy, topic)
    yield ("complete", legacy)


def _assert_lesson_is_renderable(lesson_json: dict[str, Any], topic: Topic) -> None:
    """Reject structurally-broken generations so they're saved as "failed"
    (the learner gets the Regenerate UI) instead of silently shipping a lesson
    with no cards, which the frontend masks behind the legacy intro fallback.

    Raising here is intentional: every generation caller wraps this in a
    try/except that records generation_status="failed".
    """
    cards = lesson_json.get("lesson_cards") if isinstance(lesson_json, dict) else None
    card_list = cards if isinstance(cards, list) else []
    if len(card_list) < 2:
        raise RuntimeError(
            f"Lean generation for topic {getattr(topic, 'id', '?')} produced "
            f"{len(card_list)} card(s) — treating as a failed generation."
        )

    # Soft signal: record any REQUIRED (non-optional) blueprint cards the LLM
    # skipped. Not a hard failure — a partial lesson still renders — but it's
    # tracked so we can see how often the card plan is being honored.
    try:
        from app.core.course_blueprints import get_topic_blueprint

        topic_type = str(
            getattr(topic, "topic_type", None)
            or getattr(topic, "course_type", None)
            or "concept_intuition"
        )
        blueprint = get_topic_blueprint(topic_type)
        optional = set(blueprint.get("optional_cards") or [])
        required = [
            key
            for key in (blueprint.get("default_card_sequence") or [])
            if key not in optional
        ]
        present = {
            str(card.get("blueprint_key") or "").strip().lower()
            for card in card_list
            if isinstance(card, dict)
        }
        missing = [key for key in required if key not in present]
        if missing:
            metadata = lesson_json.setdefault("metadata", {})
            if isinstance(metadata, dict):
                quality = metadata.setdefault("quality", {})
                if isinstance(quality, dict):
                    quality["missing_required_cards"] = missing
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Parallel pre-generation for all remaining topics in the study path
# ---------------------------------------------------------------------------

def pregenerate_all_study_path_topics(current_topic_id: str) -> None:
    """
    Background task: generate lean lessons for ALL remaining topics in the study path
    in parallel using a thread pool. Each thread gets its own DB session.

    This replaces the old sequential _pregenerate_pipeline(lookahead=2).
    With the lean generator (~10-15s per topic) and parallel execution,
    a 10-topic study path completes in ~15s instead of 10+ minutes.
    """
    from datetime import datetime, timedelta

    from app.db.database import SessionLocal
    from app.models.lesson import Lesson
    from app.models.topic import Topic as TopicModel
    from app.services.legacy_v2_visual_bridge import attach_v2_visuals_to_legacy_lesson
    from sqlalchemy.orm.attributes import flag_modified

    # A topic under a fresh "generating" claim is being handled by another
    # worker (e.g. the create-flow background job); don't double-generate it.
    # Older claims are treated as abandoned (crashed/restarted) and re-claimed.
    _claim_ttl = timedelta(minutes=10)

    def _needs_hybrid_visual_refresh(lesson_json: Any) -> bool:
        if not isinstance(lesson_json, dict):
            return False
        if not isinstance(lesson_json.get("lesson_cards"), list):
            return False
        metadata = lesson_json.get("metadata") or {}
        if not isinstance(metadata, dict):
            return True
        return not isinstance(metadata.get("visual_v2_bridge"), dict)

    def _attach_hybrid_visuals(topic: TopicModel, lesson_json: dict[str, Any]) -> dict[str, Any]:
        attach_v2_visuals_to_legacy_lesson(
            lesson_json,
            topic_id=str(topic.id),
            topic_title=topic.title or "",
            topic_type=str(getattr(topic, "course_type", None) or "concept_intuition"),
            visual_domain=None,
        )
        return lesson_json

    db = SessionLocal()
    try:
        current = db.query(TopicModel).filter(TopicModel.id == current_topic_id).first()
        if not current:
            return

        remaining = (
            db.query(TopicModel)
            .filter(
                TopicModel.study_path_id == current.study_path_id,
                TopicModel.order_index > current.order_index,
            )
            .order_by(TopicModel.order_index.asc())
            .all()
        )

        topics_to_generate: list[str] = []
        for t in remaining:
            existing = db.query(Lesson).filter(Lesson.topic_id == t.id).first()
            # Skip topics already in a terminal state. "ready" means we have
            # a usable lesson; "failed" means a previous attempt already
            # exhausted its one shot — re-attempting silently on every
            # background pass burns tokens for the same likely-broken topic.
            # The user can hit the regenerate button to try again explicitly.
            if existing and existing.generation_status == "ready":
                if _needs_hybrid_visual_refresh(existing.lesson_json):
                    _attach_hybrid_visuals(t, existing.lesson_json)
                    flag_modified(existing, "lesson_json")
                    db.commit()
                continue
            if existing and existing.generation_status == "failed":
                continue
            if (
                existing
                and existing.generation_status == "generating"
                and existing.created_at is not None
                and datetime.utcnow() - existing.created_at < _claim_ttl
            ):
                continue  # another worker holds a fresh claim
            if not existing:
                placeholder = Lesson(
                    topic_id=str(t.id),
                    title=t.title,
                    lesson_json={},
                    generation_status="generating",
                )
                db.add(placeholder)
            else:
                existing.generation_status = "generating"
            topics_to_generate.append(str(t.id))

        if topics_to_generate:
            db.commit()
    finally:
        db.close()

    if not topics_to_generate:
        return

    def _generate_one(topic_id: str) -> None:
        from app.db.database import SessionLocal as _SL
        from app.models.lesson import Lesson as _Lesson
        from app.models.topic import Topic as _Topic

        tdb = _SL()
        try:
            topic = tdb.query(_Topic).filter(_Topic.id == topic_id).first()
            if not topic:
                return

            from app.api.routes.lessons import (
                build_legacy_lesson_with_v2_visuals,
                get_source_chunks_for_topic,
            )
            chunks = get_source_chunks_for_topic(topic=topic, db=tdb)

            lesson_json = build_legacy_lesson_with_v2_visuals(
                topic=topic,
                chunks=chunks,
            )
            source_chunk_ids, source_summary = build_lesson_source_metadata(chunks)

            lesson = tdb.query(_Lesson).filter(_Lesson.topic_id == topic_id).first()
            if lesson:
                if lesson.generation_status == "ready" and lesson.lesson_json:
                    return
                lesson.lesson_json = lesson_json
                lesson.source_chunk_ids = source_chunk_ids
                lesson.source_summary = source_summary
                lesson.generation_status = "ready"
                tdb.commit()
        except Exception:
            logger.exception("Lean pre-generation failed for topic %s", topic_id)
            try:
                lesson = tdb.query(_Lesson).filter(_Lesson.topic_id == topic_id).first()
                if lesson:
                    lesson.generation_status = "failed"
                    tdb.commit()
            except Exception:
                pass
        finally:
            tdb.close()

    max_workers = min(len(topics_to_generate), 6)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_generate_one, tid): tid
            for tid in topics_to_generate
        }
        for future in as_completed(futures):
            try:
                future.result()
            except Exception:
                pass
