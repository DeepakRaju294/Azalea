import contextlib
import contextvars
import csv
import json
import logging
import os
import time
from pathlib import Path
from threading import Lock
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set in .env")

# max_retries=2 lets the SDK retry transient failures (5xx, network, and — most
# importantly under parallel pregeneration — 429 rate-limits) twice with
# exponential backoff before surfacing the error. Parallel topic generation
# (ThreadPoolExecutor, up to 6 concurrent) makes concurrent 429s the dominant
# transient failure; a single retry was not enough to ride them out, leaving
# topics stuck in the terminal "failed" state and showing as locked. Two retries
# absorbs the common rate-limit blip. A genuinely failing call still surfaces
# after the retries, and the user can regenerate.
client = OpenAI(api_key=OPENAI_API_KEY, max_retries=2)

_usage_logger = logging.getLogger("azalea.llm_usage")

# The logical name of the in-flight LLM call, so EVERY `responses.create` (including ones on
# `client.with_options(...)` copies and callers that bypass `_create_with_usage`) is logged with a
# meaningful label. Thread-/async-safe (each worker thread has its own context).
_current_call: contextvars.ContextVar[str] = contextvars.ContextVar("llm_call_name", default="uncategorized")


@contextlib.contextmanager
def llm_call(name: str):
    """Label every `responses.create` made inside this block (for the usage CSV).

    Use around direct `client.responses.create(...)` calls that don't go through
    `_create_with_usage`, so they show up named instead of 'uncategorized'.
    """
    token = _current_call.set(name)
    try:
        yield
    finally:
        _current_call.reset(token)


# CSV usage log so we can compute spend / cache hit-rate / latency offline.
# Set AZALEA_LLM_USAGE_LOG=0 in .env to disable. Default: backend/logs/llm_usage.csv.
_USAGE_LOG_ENABLED = os.getenv("AZALEA_LLM_USAGE_LOG", "1") != "0"
_USAGE_LOG_PATH = Path(
    os.getenv(
        "AZALEA_LLM_USAGE_LOG_PATH",
        str(Path(__file__).resolve().parents[2] / "logs" / "llm_usage.csv"),
    )
)
_USAGE_LOG_LOCK = Lock()
_USAGE_LOG_FIELDS = (
    "ts",
    "call",
    "model",
    "wall_ms",
    "prompt_tokens",
    "cached_tokens",
    "completion_tokens",
    "total_tokens",
    "cache_hit_pct",
)


def _ensure_usage_log_header() -> None:
    if not _USAGE_LOG_ENABLED:
        return
    try:
        _USAGE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not _USAGE_LOG_PATH.exists():
            with _USAGE_LOG_PATH.open("w", newline="", encoding="utf-8") as fh:
                csv.writer(fh).writerow(_USAGE_LOG_FIELDS)
    except OSError:
        pass


def _extract_usage(response: Any) -> dict[str, int]:
    """Pull prompt/cached/completion/total token counts off a Responses API
    response. Returns zeros if the SDK didn't populate them (older versions
    or non-streaming variants).
    """
    usage = getattr(response, "usage", None) or {}

    def _get(name: str) -> int:
        if isinstance(usage, dict):
            val = usage.get(name)
        else:
            val = getattr(usage, name, None)
        try:
            return int(val) if val is not None else 0
        except (TypeError, ValueError):
            return 0

    # The Responses API exposes input_tokens / output_tokens / total_tokens.
    # input_tokens_details.cached_tokens reports cache hits.
    prompt = _get("input_tokens") or _get("prompt_tokens")
    completion = _get("output_tokens") or _get("completion_tokens")
    total = _get("total_tokens") or (prompt + completion)
    cached = 0
    details = None
    if isinstance(usage, dict):
        details = usage.get("input_tokens_details") or usage.get("prompt_tokens_details")
    else:
        details = getattr(usage, "input_tokens_details", None) or getattr(
            usage, "prompt_tokens_details", None
        )
    if details is not None:
        if isinstance(details, dict):
            cached = int(details.get("cached_tokens") or 0)
        else:
            cached = int(getattr(details, "cached_tokens", 0) or 0)
    return {
        "prompt_tokens": prompt,
        "cached_tokens": cached,
        "completion_tokens": completion,
        "total_tokens": total,
    }


def _log_usage(call_name: str, response: Any, wall_ms: int) -> None:
    """Log token usage + wall time for one LLM call.

    Writes a structured logger line AND a CSV row so we can read either
    interactively (tail the log) or offline (load the CSV in pandas)."""
    if not _USAGE_LOG_ENABLED:
        return
    tk = _extract_usage(response)
    cache_pct = (
        round(100 * tk["cached_tokens"] / tk["prompt_tokens"], 1)
        if tk["prompt_tokens"] > 0
        else 0.0
    )
    _usage_logger.info(
        "llm_call call=%s model=%s wall_ms=%d in=%d cached=%d (%.1f%%) out=%d total=%d",
        call_name,
        OPENAI_MODEL,
        wall_ms,
        tk["prompt_tokens"],
        tk["cached_tokens"],
        cache_pct,
        tk["completion_tokens"],
        tk["total_tokens"],
    )
    try:
        _ensure_usage_log_header()
        with _USAGE_LOG_LOCK, _USAGE_LOG_PATH.open(
            "a", newline="", encoding="utf-8"
        ) as fh:
            csv.writer(fh).writerow(
                [
                    int(time.time()),
                    call_name,
                    OPENAI_MODEL,
                    wall_ms,
                    tk["prompt_tokens"],
                    tk["cached_tokens"],
                    tk["completion_tokens"],
                    tk["total_tokens"],
                    cache_pct,
                ]
            )
    except OSError:
        pass


# Patch `Responses.create` ONCE so EVERY call — including ones on `client.with_options(...)` copies
# and direct callers that never touch `_create_with_usage` (the worked-example solver, gen_foundation,
# code repair/walkthrough, review/repair/transfer generators) — is logged to the usage CSV exactly
# once, labelled by the `_current_call` context var. This is what makes "track ALL text content"
# true regardless of the call site. Guarded: if the SDK shape ever changes, we fall back to per-call
# logging in `_create_with_usage` and nothing breaks.
_PATCH_APPLIED = False
try:
    from openai.resources.responses import Responses as _Responses  # type: ignore

    _orig_responses_create = _Responses.create

    def _logged_responses_create(self, *args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        response = _orig_responses_create(self, *args, **kwargs)
        wall_ms = int((time.perf_counter() - started) * 1000)
        try:
            _log_usage(_current_call.get(), response, wall_ms)
        except Exception:  # noqa: BLE001 — the response is the expensive thing; the log is disposable
            _usage_logger.exception("llm_call usage-log failed (patched)")
        return response

    _Responses.create = _logged_responses_create  # type: ignore[assignment]
    _PATCH_APPLIED = True
except Exception:  # noqa: BLE001
    _usage_logger.exception("could not patch Responses.create; per-call logging only")


def _create_with_usage(
    call_name: str, *, timeout: Any = None, max_retries: Any = None, **kwargs: Any
) -> Any:
    """Make an LLM call labelled `call_name` for the usage CSV.

    With the class patch active, logging happens there (via `_current_call`); this just sets the
    label and applies optional per-call timeout/max_retries. If the patch isn't active, it logs
    here as a fallback. Logging never breaks the response.
    """
    token = _current_call.set(call_name)
    try:
        target = client
        if timeout is not None or max_retries is not None:
            opts: dict[str, Any] = {}
            if timeout is not None:
                opts["timeout"] = timeout
            if max_retries is not None:
                opts["max_retries"] = max_retries
            target = client.with_options(**opts)
        if _PATCH_APPLIED:
            return target.responses.create(**kwargs)  # logged by the patch
        started = time.perf_counter()
        response = target.responses.create(**kwargs)
        wall_ms = int((time.perf_counter() - started) * 1000)
        try:
            _log_usage(call_name, response, wall_ms)
        except Exception:  # noqa: BLE001
            _usage_logger.exception("llm_call usage-log failed call=%s", call_name)
        return response
    finally:
        _current_call.reset(token)

VISUAL_STEP_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "kind": {"type": "string"},
        "label": {"type": "string"},
        "step_title": {"type": "string"},
        "visual_label": {"type": "string"},
        "description": {"type": "string"},
        "step_detail": {"type": "string"},
        "mini_visual": {"type": "string"},
        "formula": {"type": "string"},
        "cases": {"type": "array", "items": {"type": "string"}},
        "active": {"type": "boolean"},
    },
    "required": [
        "kind",
        "label",
        "step_title",
        "visual_label",
        "description",
        "step_detail",
        "mini_visual",
        "formula",
        "cases",
        "active",
    ],
    "additionalProperties": False,
}

VISUAL_ARRAY_POINTER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "label": {"type": "string"},
        "index": {"type": "integer"},
        "side": {"type": "string"},
    },
    "required": ["label", "index", "side"],
    "additionalProperties": False,
}

VISUAL_ARRAY_RANGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "label": {"type": "string"},
        "start": {"type": "integer"},
        "end": {"type": "integer"},
    },
    "required": ["label", "start", "end"],
    "additionalProperties": False,
}

VISUAL_ARRAY_ROW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "label": {"type": "string"},
        "values": {"type": "array", "items": {"type": "string"}},
        "emphasis": {"type": "boolean"},
    },
    "required": ["label", "values", "emphasis"],
    "additionalProperties": False,
}

VISUAL_SYMBOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "symbol": {"type": "string"},
        "meaning": {"type": "string"},
    },
    "required": ["symbol", "meaning"],
    "additionalProperties": False,
}

VISUAL_NODE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "label": {"type": "string"},
        "relation": {"type": "string"},
        "description": {"type": "string"},
        "state": {"type": "string"},
        "x": {"type": "number"},
        "y": {"type": "number"},
    },
    "required": ["id", "label", "relation", "description", "state", "x", "y"],
    "additionalProperties": False,
}

VISUAL_EDGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "from": {"type": "string"},
        "to": {"type": "string"},
        "label": {"type": "string"},
        "style": {"type": "string"},
        "state": {"type": "string"},
    },
    "required": ["from", "to", "label", "style", "state"],
    "additionalProperties": False,
}

VISUAL_COMPONENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "type": {"type": "string"},
        "label": {"type": "string"},
        "value": {"type": "string"},
        "x": {"type": "number"},
        "y": {"type": "number"},
    },
    "required": ["id", "type", "label", "value", "x", "y"],
    "additionalProperties": False,
}

VISUAL_KEY_POINT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "x": {"type": "number"},
        "y": {"type": "number"},
        "label": {"type": "string"},
    },
    "required": ["x", "y", "label"],
    "additionalProperties": False,
}

VISUAL_DATA_POINT_SCHEMA: dict[str, Any] = {
    "type": "array",
    "items": {"type": "number"},
}

VISUAL_LABEL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "target": {"type": "string"},
        "text": {"type": "string"},
    },
    "required": ["target", "text"],
    "additionalProperties": False,
}

LEAN_VISUAL_NODE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "label": {"type": "string"},
        "relation": {"type": "string"},
        "description": {"type": "string"},
        "state": {"type": "string"},
        "x": {"type": "number"},
        "y": {"type": "number"},
    },
    "required": ["id", "label", "relation", "description", "state", "x", "y"],
    "additionalProperties": False,
}

# Full schema for top-level visual_plan items (node_link, graph, circuit, code_trace, etc.)
# "kind", "description", "elements", "highlight" removed — not used by the renderer.
VISUAL_PLAN_SCHEMA_PROPERTIES: dict[str, Any] = {
    "type": {"type": "string"},
    "title": {"type": "string"},
    "purpose": {"type": "string"},
    "placement": {"type": "string"},
    "what_to_notice": {"type": "string"},
    "common_mistake": {"type": "string"},
    # graph / graph_chart
    "x_label": {"type": "string"},
    "y_label": {"type": "string"},
    "data_points": {"type": "array", "items": VISUAL_DATA_POINT_SCHEMA},
    "key_points": {"type": "array", "items": VISUAL_KEY_POINT_SCHEMA},
    # node_link_diagram
    "nodes": {"type": "array", "items": VISUAL_NODE_SCHEMA},
    "edges": {"type": "array", "items": VISUAL_EDGE_SCHEMA},
    "traversal_path": {"type": "array", "items": {"type": "string"}},
    # circuit_diagram
    "components": {"type": "array", "items": VISUAL_COMPONENT_SCHEMA},
    "wires": {"type": "array", "items": VISUAL_EDGE_SCHEMA},
    # code_trace / state_change
    "code": {"type": "string"},
    "language": {"type": "string"},
    "columns": {"type": "array", "items": {"type": "string"}},
    "rows": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
    "highlight_row": {"type": "integer"},
    # step_flow / causal_chain
    "steps": {"type": "array", "items": VISUAL_STEP_SCHEMA},
    # spatial_diagram / concept_map
    "center": {"type": "string"},
    "labels": {"type": "array", "items": VISUAL_LABEL_SCHEMA},
    # formula_card (avoid, but keep for schema compat)
    "formula": {"type": "string"},
    "symbols": {"type": "array", "items": VISUAL_SYMBOL_SCHEMA},
    "when_to_use": {"type": "string"},
    # misconception / practice_feedback
    "wrong": {"type": "string"},
    "correct": {"type": "string"},
    "wrong_label": {"type": "string"},
    "correct_label": {"type": "string"},
    "why": {"type": "string"},
    "counterexample": {"type": "string"},
}

VISUAL_PLAN_OBJECT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": VISUAL_PLAN_SCHEMA_PROPERTIES,
    "required": list(VISUAL_PLAN_SCHEMA_PROPERTIES.keys()),
    "additionalProperties": False,
}

# Lightweight per-card visual hint — only for inline code_trace visuals.
# Complex visuals (node_link, graph, circuit) belong in the top-level visual_plan
# array and are referenced from the card via visual_index.
CARD_VISUAL_HINT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "type": {"type": "string"},
        "title": {"type": "string"},
        "purpose": {"type": "string"},
        "code": {"type": "string"},
        "language": {"type": "string"},
        "columns": {"type": "array", "items": {"type": "string"}},
        "rows": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
        "highlight_row": {"type": "integer"},
    },
    "required": ["type", "title", "purpose", "code", "language", "columns", "rows", "highlight_row"],
    "additionalProperties": False,
}

CONCEPT_SUPPORT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "concept": {"type": "string"},
        "state_hint": {"type": "string"},
        "support": {"type": "string"},
        "hover_explanation": {"type": "string"},
    },
    "required": ["concept", "state_hint", "support", "hover_explanation"],
    "additionalProperties": False,
}

INTERACTIVE_LINK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "explanation": {"type": "string"},
        "why_it_matters_here": {"type": "string"},
        "action": {
            "type": "string",
            "enum": [
                "popup_only",
                "open_study_path",
                "review_earlier_topic",
                "ask_question",
            ],
        },
        "target": {"type": "string"},
    },
    "required": [
        "text",
        "explanation",
        "why_it_matters_here",
        "action",
        "target",
    ],
    "additionalProperties": False,
}

STYLED_ELEMENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "type": {
            "type": "string",
            "enum": [
                "table",
                "comparison",
                "comparison_table",
                "checklist",
                "timeline",
                "formula_steps",
                "proof_skeleton",
                "decision_matrix",
                "workflow_map",
                "glossary_table",
                "input_output_table",
                "stage_map",
                "term_map",
                "code_trace",
            ],
        },
        "title": {"type": "string"},
        "data": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "description": {"type": "string"},
                        },
                        "required": ["label", "description"],
                        "additionalProperties": False,
                    },
                },
                "headers": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "rows": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "description": {"type": "string"},
                            "formula": {"type": "string"},
                        },
                        "required": ["label", "description", "formula"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["items", "headers", "columns", "rows", "steps"],
            "additionalProperties": False,
        },
    },
    "required": ["type", "title", "data"],
    "additionalProperties": False,
}

CARD_VISUAL_HINT_SCHEMA: dict[str, Any] = VISUAL_PLAN_OBJECT_SCHEMA


LESSON_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "intro": {"type": "string"},
        "purpose": {"type": "string"},
        "context": {"type": "string"},
        "learning_objective": {"type": "string"},
        "components": {"type": "array", "items": {"type": "string"}},
        "concepts": {"type": "array", "items": {"type": "string"}},
        "process": {"type": "array", "items": {"type": "string"}},
        "limitations": {"type": "array", "items": {"type": "string"}},
        "worked_examples": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "steps": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["title", "steps"],
                "additionalProperties": False,
            },
        },
        "edge_cases": {"type": "array", "items": {"type": "string"}},
        "practice": {"type": "array", "items": {"type": "string"}},
        "lesson_cards": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "blueprint_key": {"type": "string"},
                    "card_type": {
                        "type": "string",
                        "enum": [
                            "intro",
                            "purpose",
                            "purpose_context",
                            "core_idea",
                            "definition",
                            "intuition",
                            "visual",
                            "method_process",
                            "process_step",
                            "worked_example",
                            "example",
                            "formula",
                            "comparison",
                            "edge_case",
                            "common_mistake",
                            "quick_practice",
                            "micro_check",
                            "summary",
                            "bridge_to_next_topic",
                        ],
                    },
                    "title": {"type": "string"},
                    "body": {"type": "array", "items": {"type": "string"}},
                    "bullets": {"type": "array", "items": {"type": "string"}},
                    "points": {"type": "array", "items": {"type": "string"}},
                    "main_concept": {"type": "string"},
                    "new_concepts": {"type": "array", "items": {"type": "string"}},
                    "review_concepts": {"type": "array", "items": {"type": "string"}},
                    "prerequisite_concepts": {"type": "array", "items": {"type": "string"}},
                    "related_formulas": {"type": "array", "items": {"type": "string"}},
                    "related_symbols": {"type": "array", "items": {"type": "string"}},
                    "common_misconceptions": {"type": "array", "items": {"type": "string"}},
                    "concept_support": {
                        "type": "array",
                        "items": CONCEPT_SUPPORT_SCHEMA,
                    },
                    "interactive_links": {
                        "type": "array",
                        "items": INTERACTIVE_LINK_SCHEMA,
                    },
                    "styled_elements": {
                        "type": "array",
                        "items": STYLED_ELEMENT_SCHEMA,
                    },
                    "visual_plan": CARD_VISUAL_HINT_SCHEMA,
                    "annotations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string"},
                                "explanation": {"type": "string"},
                            },
                            "required": ["label", "explanation"],
                            "additionalProperties": False,
                        },
                    },
                    "example": {"type": "string"},
                    "micro_check": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "prompt": {"type": "string"},
                            "answer": {"type": "string"},
                        },
                        "required": ["type", "prompt", "answer"],
                        "additionalProperties": False,
                    },
                    "deeper_explanation": {"type": "string"},
                    "what_to_notice": {"type": "string"},
                    "next_transition": {"type": "string"},
                    "quality_score": {"type": "integer"},
                    "estimated_seconds": {"type": "integer"},
                    "transition_text": {"type": "string"},
                    "next_card_label": {"type": "string"},
                    "practice_question_index": {"type": "integer"},
                    "visual_index": {"type": "integer"},
                },
                "required": [
                    "id",
                    "blueprint_key",
                    "card_type",
                    "title",
                    "body",
                    "bullets",
                    "points",
                    "main_concept",
                    "new_concepts",
                    "review_concepts",
                    "prerequisite_concepts",
                    "related_formulas",
                    "related_symbols",
                    "common_misconceptions",
                    "concept_support",
                    "interactive_links",
                    "styled_elements",
                    "visual_plan",
                    "annotations",
                    "example",
                    "micro_check",
                    "deeper_explanation",
                    "what_to_notice",
                    "next_transition",
                    "quality_score",
                    "estimated_seconds",
                    "transition_text",
                    "next_card_label",
                    "practice_question_index",
                    "visual_index",
                ],
                "additionalProperties": False,
            },
        },
        "practice_questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question_type": {
                        "type": "string",
                        "enum": [
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
                        ],
                    },
                    "topic": {"type": "string"},
                    "skill_target": {"type": "string"},
                    "difficulty": {
                        "type": "string",
                        "enum": ["Easy", "Medium", "Hard"],
                    },
                    "question_text": {"type": "string"},
                    "concept_tested": {"type": "string"},
                    "related_section": {"type": "string"},
                    "why_this_matters": {"type": "string"},
                    "choices": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "given": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "starter_code": {"type": "string"},
                    "language": {"type": "string"},
                    "test_cases": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "input": {"type": "string"},
                                "expected": {"type": "string"},
                            },
                            "required": ["input", "expected"],
                            "additionalProperties": False,
                        },
                    },
                    "correct_answer": {"type": "string"},
                    "explanation": {"type": "string"},
                },
                "required": [
                    "question_type",
                    "topic",
                    "skill_target",
                    "difficulty",
                    "question_text",
                    "concept_tested",
                    "related_section",
                    "why_this_matters",
                    "choices",
                    "given",
                    "starter_code",
                    "language",
                    "test_cases",
                    "correct_answer",
                    "explanation",
                ],
                "additionalProperties": False,
            },
        },
        "key_takeaways": {"type": "array", "items": {"type": "string"}},
        "visual_plan": {
            "type": "array",
            "items": VISUAL_PLAN_OBJECT_SCHEMA,
        },
        "source_preview": {"type": "string"},
        "adaptation_metadata": {
            "type": "object",
            "properties": {
                "starting_mode": {"type": "string"},
                "estimated_state": {"type": "string"},
                "adaptation_summary": {"type": "string"},
                "teaching_strategy": {"type": "string"},
            },
            "required": [
                "starting_mode",
                "estimated_state",
                "adaptation_summary",
                "teaching_strategy",
            ],
            "additionalProperties": False,
        },
    },
    "required": [
        "intro",
        "purpose",
        "context",
        "learning_objective",
        "components",
        "concepts",
        "process",
        "limitations",
        "worked_examples",
        "edge_cases",
        "practice",
        "lesson_cards",
        "practice_questions",
        "key_takeaways",
        "visual_plan",
        "source_preview",
        "adaptation_metadata",
    ],
    "additionalProperties": False,
}


TOPICS_JSON_SCHEMA: dict[str, Any] = {
    # Dead fields removed: difficulty_focus, boundary_reason, topic_type_reason,
    # card_blueprint_hint, source_coverage_notes, visual_description (topic-level).
    # None are read by any downstream consumer — they were ~30% of output tokens
    # on the topic call wasted on fields that go straight to the DB and never
    # come back. See the topic field audit for the trace evidence.
    "type": "object",
    "properties": {
        "topics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "unit_title": {"type": "string"},
                    "learner_outcome": {"type": "string"},
                    "purpose": {"type": "string"},
                    "in_scope": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "out_of_scope": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "prerequisite_topics": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "assumed_prerequisites": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "source_refs": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "topic_type": {"type": "string"},
                    "estimated_minutes": {"type": "integer"},
                    "practice_target": {"type": "string"},
                    "practice_format": {"type": "string"},
                    "modifiers": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "title",
                    "unit_title",
                    "learner_outcome",
                    "purpose",
                    "in_scope",
                    "out_of_scope",
                    "prerequisite_topics",
                    "assumed_prerequisites",
                    "source_refs",
                    "topic_type",
                    "estimated_minutes",
                    "practice_target",
                    "practice_format",
                    "modifiers",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["topics"],
    "additionalProperties": False,
}


CLASS_QA_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "used_chunk_indexes": {
            "type": "array",
            "items": {"type": "integer"},
        },
    },
    "required": ["answer", "used_chunk_indexes"],
    "additionalProperties": False,
}


LESSON_SEGMENT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "adaptation_message": {"type": "string"},
        "replacement_cards": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "blueprint_key": {"type": "string"},
                    "card_type": {
                        "type": "string",
                        "enum": [
                            "intro",
                            "purpose",
                            "purpose_context",
                            "core_idea",
                            "definition",
                            "intuition",
                            "visual",
                            "method_process",
                            "process_step",
                            "worked_example",
                            "example",
                            "formula",
                            "comparison",
                            "edge_case",
                            "common_mistake",
                            "quick_practice",
                            "micro_check",
                            "summary",
                            "bridge_to_next_topic",
                        ],
                    },
                    "title": {"type": "string"},
                    "body": {"type": "array", "items": {"type": "string"}},
                    "bullets": {"type": "array", "items": {"type": "string"}},
                    "points": {"type": "array", "items": {"type": "string"}},
                    "main_concept": {"type": "string"},
                    "new_concepts": {"type": "array", "items": {"type": "string"}},
                    "review_concepts": {"type": "array", "items": {"type": "string"}},
                    "prerequisite_concepts": {"type": "array", "items": {"type": "string"}},
                    "related_formulas": {"type": "array", "items": {"type": "string"}},
                    "related_symbols": {"type": "array", "items": {"type": "string"}},
                    "common_misconceptions": {"type": "array", "items": {"type": "string"}},
                    "concept_support": {
                        "type": "array",
                        "items": CONCEPT_SUPPORT_SCHEMA,
                    },
                    "interactive_links": {
                        "type": "array",
                        "items": INTERACTIVE_LINK_SCHEMA,
                    },
                    "styled_elements": {
                        "type": "array",
                        "items": STYLED_ELEMENT_SCHEMA,
                    },
                    "visual_plan": CARD_VISUAL_HINT_SCHEMA,
                    "annotations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string"},
                                "explanation": {"type": "string"},
                            },
                            "required": ["label", "explanation"],
                            "additionalProperties": False,
                        },
                    },
                    "example": {"type": "string"},
                    "micro_check": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "prompt": {"type": "string"},
                            "answer": {"type": "string"},
                        },
                        "required": ["type", "prompt", "answer"],
                        "additionalProperties": False,
                    },
                    "deeper_explanation": {"type": "string"},
                    "what_to_notice": {"type": "string"},
                    "next_transition": {"type": "string"},
                    "quality_score": {"type": "integer"},
                    "estimated_seconds": {"type": "integer"},
                    "transition_text": {"type": "string"},
                    "next_card_label": {"type": "string"},
                    "practice_question_index": {"type": "integer"},
                    "visual_index": {"type": "integer"},
                },
                "required": [
                    "id",
                    "blueprint_key",
                    "card_type",
                    "title",
                    "body",
                    "bullets",
                    "points",
                    "main_concept",
                    "new_concepts",
                    "review_concepts",
                    "prerequisite_concepts",
                    "related_formulas",
                    "related_symbols",
                    "common_misconceptions",
                    "concept_support",
                    "interactive_links",
                    "styled_elements",
                    "visual_plan",
                    "annotations",
                    "example",
                    "micro_check",
                    "deeper_explanation",
                    "what_to_notice",
                    "next_transition",
                    "quality_score",
                    "estimated_seconds",
                    "transition_text",
                    "next_card_label",
                    "practice_question_index",
                    "visual_index",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["adaptation_message", "replacement_cards"],
    "additionalProperties": False,
}


def generate_structured_lesson(
    system_prompt: str,
    user_prompt: str,
) -> dict[str, Any]:
    response = _create_with_usage(
        "structured_lesson",
        model=OPENAI_MODEL,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "azalea_lesson",
                "schema": LESSON_JSON_SCHEMA,
                "strict": True,
            }
        },
    )

    try:
        return json.loads(response.output_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("OpenAI returned invalid lesson JSON") from exc


def generate_structured_topics(
    system_prompt: str,
    user_prompt: str,
) -> list[dict[str, Any]]:
    response = _create_with_usage(
        "structured_topics",
        model=OPENAI_MODEL,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "azalea_topics",
                "schema": TOPICS_JSON_SCHEMA,
                "strict": True,
            }
        },
    )

    try:
        parsed = json.loads(response.output_text)
        return parsed["topics"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise RuntimeError("OpenAI returned invalid topic JSON") from exc


def generate_class_qa_response(
    system_prompt: str,
    user_prompt: str,
) -> dict[str, Any]:
    response = _create_with_usage(
        "class_qa",
        model=OPENAI_MODEL,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "azalea_class_qa",
                "schema": CLASS_QA_JSON_SCHEMA,
                "strict": True,
            }
        },
    )

    try:
        return json.loads(response.output_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("OpenAI returned invalid class Q&A JSON") from exc


def generate_title(prompt: str) -> str:
    """Return a concise 2-5 word topic title derived from the user's prompt."""
    try:
        response = _create_with_usage(
            "title",
            model=OPENAI_MODEL,
            input=[
                {
                    "role": "system",
                    "content": (
                        "Generate a concise 2-5 word title that captures the core topic of the user's learning goal. "
                        "Write it as a topic name, not a question or sentence. Use title case. "
                        "Examples: 'React Component Fundamentals', 'Quadratic Functions', "
                        "'Binary Search Trees', 'SQL Window Functions', 'Photosynthesis'. "
                        "Return only the title — no punctuation, no quotes, nothing else."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_output_tokens=20,
        )
        title = response.output_text.strip().strip('"').strip("'")
        return title if title else prompt[:80]
    except Exception:
        return prompt[:80]


def generate_lesson_segment(
    system_prompt: str,
    user_prompt: str,
) -> dict[str, Any]:
    response = _create_with_usage(
        "lesson_segment",
        model=OPENAI_MODEL,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "azalea_lesson_segment",
                "schema": LESSON_SEGMENT_JSON_SCHEMA,
                "strict": True,
            }
        },
    )

    try:
        return json.loads(response.output_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("OpenAI returned invalid lesson segment JSON") from exc


TOPIC_TYPE_CLASSIFICATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "topic_type": {"type": "string"},
        "secondary_topic_types": {"type": "array", "items": {"type": "string"}},
        "knowledge_level": {"type": ["integer", "null"]},
        "reason": {"type": "string"},
    },
    "required": [
        "topic_type",
        "secondary_topic_types",
        "knowledge_level",
        "reason",
    ],
    "additionalProperties": False,
}


COURSE_TYPE_CLASSIFICATION_SCHEMA = TOPIC_TYPE_CLASSIFICATION_SCHEMA


def generate_course_type_classification(
    system_prompt: str,
    user_prompt: str,
) -> dict[str, Any]:
    response = _create_with_usage(
        "course_type_classification",
        model=OPENAI_MODEL,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "azalea_topic_type_classification",
                "schema": TOPIC_TYPE_CLASSIFICATION_SCHEMA,
                "strict": True,
            }
        },
    )

    try:
        return json.loads(response.output_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("OpenAI returned invalid classification JSON") from exc


# ---------------------------------------------------------------------------
# Lean lesson schema (v2) — 6 card types, 11 fields per card, no visuals
# ---------------------------------------------------------------------------

EXAMPLE_PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "core_mechanism_example": {"type": "string"},
        "structural_variation_example": {"type": "string"},
        "edge_case_examples": {"type": "array", "items": {"type": "string"}},
        "misconception_example": {"type": "string"},
        "transfer_example": {"type": "string"},
        "coverage_dimensions": {"type": "array", "items": {"type": "string"}},
        "excluded_edge_cases_with_reason": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": [
        "core_mechanism_example",
        "structural_variation_example",
        "edge_case_examples",
        "misconception_example",
        "transfer_example",
        "coverage_dimensions",
        "excluded_edge_cases_with_reason",
    ],
    "additionalProperties": False,
}


LEAN_CARD_SCHEMA: dict[str, Any] = {
    # Type-specific visual_* and code_* fields are NULLABLE so the LLM can
    # return null instead of "" / [] for fields that don't apply to this
    # card's chosen visual_type. OpenAI's strict-JSON mode requires every
    # property to remain in `required`, so "optional" is expressed as
    # ["X", "null"] type unions rather than by removing from required.
    # Result: ~6% output-token reduction per card plus a clearer signal to
    # the model that empty fields are intentional, not pending. Fields that
    # apply to ALL cards (id, blueprint_key, title, points, visual_type,
    # visual_description, visual_focus, etc.) stay strictly typed.
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "blueprint_key": {"type": "string"},
        "card_type": {"type": "string"},
        "title": {"type": "string"},
        "learning_job": {"type": "string"},
        "example_type": {"type": "string"},
        "visual_type": {"type": "string"},
        # Table-shape visuals (comparison_table, state_change). Nullable on every other card.
        "visual_columns": {"type": ["array", "null"], "items": {"type": "string"}},
        "visual_rows": {
            "type": ["array", "null"],
            "items": {"type": "array", "items": {"type": "string"}},
        },
        "visual_highlight_row": {"type": ["integer", "null"]},
        # Step-shape visuals (step_flow, progressive_step_flow, causal_chain, path_progress, practice_feedback).
        "visual_steps": {
            "type": ["array", "null"],
            "items": VISUAL_STEP_SCHEMA,
        },
        # Formula card only.
        "visual_formula": {"type": ["string", "null"]},
        "visual_symbols": {
            "type": ["array", "null"],
            "items": VISUAL_SYMBOL_SCHEMA,
        },
        "visual_when_to_use": {"type": ["string", "null"]},
        # Concept/node-link shapes (node_link_diagram, concept_map, relationship_map, snapshots).
        "visual_center": {"type": ["string", "null"]},
        "visual_nodes": {
            "type": ["array", "null"],
            "items": LEAN_VISUAL_NODE_SCHEMA,
        },
        "visual_edges": {"type": ["array", "null"], "items": VISUAL_EDGE_SCHEMA},
        # Misconception only.
        "visual_wrong": {"type": ["string", "null"]},
        "visual_correct": {"type": ["string", "null"]},
        "visual_wrong_label": {"type": ["string", "null"]},
        "visual_correct_label": {"type": ["string", "null"]},
        "visual_why": {"type": ["string", "null"]},
        # Graph chart only.
        "visual_x_label": {"type": ["string", "null"]},
        "visual_y_label": {"type": ["string", "null"]},
        "visual_data_points": {
            "type": ["array", "null"],
            "items": VISUAL_DATA_POINT_SCHEMA,
        },
        "visual_key_points": {
            "type": ["array", "null"],
            "items": VISUAL_KEY_POINT_SCHEMA,
        },
        # Array-state diagrams only.
        "visual_array_values": {"type": ["array", "null"], "items": {"type": "string"}},
        "visual_array_rows": {"type": ["array", "null"], "items": VISUAL_ARRAY_ROW_SCHEMA},
        "visual_array_pointers": {
            "type": ["array", "null"],
            "items": VISUAL_ARRAY_POINTER_SCHEMA,
        },
        "visual_array_ranges": {
            "type": ["array", "null"],
            "items": VISUAL_ARRAY_RANGE_SCHEMA,
        },
        "visual_array_annotations": {"type": ["array", "null"], "items": {"type": "string"}},
        # Universal teaching fields.
        "points": {"type": "array", "items": {"type": "string"}},
        "explanation": {"type": "string"},
        "visual_description": {"type": "string"},
        "example": {"type": "string"},
        "example_text": {"type": "string"},
        # Code-related fields (only coding_implementation cards).
        "code_snippet": {"type": ["string", "null"]},
        "code_language": {"type": ["string", "null"]},
        "highlight_lines_per_step": {
            "type": ["array", "null"],
            "items": {
                "type": "array",
                "items": {"type": "integer"},
            },
        },
        # Continuation fields (only present when this card is part of a continuation).
        "continuation_group_id": {"type": ["string", "null"]},
        "continuation_index": {"type": ["integer", "null"]},
        "continuation_total": {"type": ["integer", "null"]},
        "continuation_reason": {"type": ["string", "null"]},
        "continues_from_previous": {"type": ["boolean", "null"]},
        # Practice fields (only present on practice cards).
        "practice_question": {"type": ["string", "null"]},
        "practice_answer": {"type": ["string", "null"]},
        "practice_choices": {"type": ["array", "null"], "items": {"type": "string"}},
        "estimated_seconds": {"type": "integer"},
        "visual_focus": {
            "type": "object",
            "properties": {
                "active_nodes": {"type": "array", "items": {"type": "string"}},
                "highlight_path": {"type": "array", "items": {"type": "string"}},
                "active_step": {"type": "integer"},
                "attention_note": {"type": "string"},
            },
            "required": ["active_nodes", "highlight_path", "active_step", "attention_note"],
            "additionalProperties": False,
        },
    },
    "required": [
        "id",
        "blueprint_key",
        "card_type",
        "title",
        "learning_job",
        "example_type",
        "visual_type",
        "visual_columns",
        "visual_rows",
        "visual_highlight_row",
        "visual_steps",
        "visual_formula",
        "visual_symbols",
        "visual_when_to_use",
        "visual_center",
        "visual_nodes",
        "visual_edges",
        "visual_wrong",
        "visual_correct",
        "visual_wrong_label",
        "visual_correct_label",
        "visual_why",
        "visual_x_label",
        "visual_y_label",
        "visual_data_points",
        "visual_key_points",
        "visual_array_values",
        "visual_array_rows",
        "visual_array_pointers",
        "visual_array_ranges",
        "visual_array_annotations",
        "points",
        "explanation",
        "visual_description",
        "example",
        "example_text",
        "code_snippet",
        "code_language",
        "highlight_lines_per_step",
        "continuation_group_id",
        "continuation_index",
        "continuation_total",
        "continuation_reason",
        "continues_from_previous",
        "practice_question",
        "practice_answer",
        "practice_choices",
        "estimated_seconds",
        "visual_focus",
    ],
    "additionalProperties": False,
}

# Worked example PLAN — pilot architecture for MATH_FORMULA_METHOD topics
# (and any future topic families we extend it to).
#
# The current per-card worked_example pattern has the LLM re-emit the full
# visual on every step card, which is slow, expensive, and frequently
# inconsistent. The plan pattern is: ONE solved problem revealed across
# multiple step cards that all SHARE the same base visual; only highlights
# and trackers change between steps.
#
# Field ORDER is intentional and acts as a planning forcing function under
# strict JSON: the LLM must commit to problem_setup + terminal_state +
# the full solution_steps array BEFORE returning, which encourages
# solve-first behavior even in a single LLM call.
#
# `worked_example_plan` is OPTIONAL (nullable). The LLM emits it INSTEAD OF
# per-step worked_example cards for the pilot topic types. Non-pilot topics
# return null and continue using the existing per-card worked_example flow.
WORKED_EXAMPLE_STEP_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "step_number": {
            "type": "integer",
            "description": "1-based step index, starting at 1.",
        },
        "step_label": {
            "type": "string",
            "description": (
                "1-4 word concrete verb-phrase naming this step's action "
                "(e.g. 'Identify variables', 'Substitute values', "
                "'Apply formula', 'Compute result', 'Interpret answer'). "
                "Drives the persistent step-flow visual chip for this step."
            ),
        },
        "mini_visual": {
            "type": "string",
            "description": (
                "2-6 word state/action cue shown in the visual when this "
                "step is active (e.g. 'a=3, b=4', 'sqrt(9 + 16)', "
                "'result = 5'). Concrete; not a paraphrase of step_label."
            ),
        },
        "action": {
            "type": "string",
            "description": (
                "One sentence stating what THIS step does in the solve. "
                "Imperative voice ('Substitute a=3 and b=4 into the "
                "formula'). Not a label; a complete action."
            ),
        },
        "reason": {
            "type": "string",
            "description": (
                "One sentence stating why the action is valid or chosen "
                "here. Names the rule, formula property, or invariant "
                "being applied."
            ),
        },
        "current_expression": {
            "type": ["string", "null"],
            "description": (
                "The expression/state AFTER this step runs, in the form "
                "the learner should hold in their head. For formula "
                "topics, the substituted/simplified expression; for "
                "procedural math, the new state. Use null when the step "
                "doesn't change the expression."
            ),
        },
        "intermediate_result": {
            "type": ["string", "null"],
            "description": (
                "A short computed value or output, if any (e.g. 'mid=4', "
                "'distance=5', 'sum=21'). Use null when this step "
                "produces no numeric/symbolic output."
            ),
        },
        "text_points": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Bullet content for the learner-facing card representing "
                "this step. Main bullet + 1-3 sub-bullets max. Use "
                "two-space + '- ' prefix for sub-bullets. Same format as "
                "regular card.points."
            ),
        },
    },
    "required": [
        "step_number",
        "step_label",
        "mini_visual",
        "action",
        "reason",
        "current_expression",
        "intermediate_result",
        "text_points",
    ],
    "additionalProperties": False,
}

WORKED_EXAMPLE_PLAN_SCHEMA: dict[str, Any] = {
    "type": ["object", "null"],
    "description": (
        "OPTIONAL plan for the worked example, currently used only for "
        "MATH_FORMULA_METHOD topics. When emitted, this REPLACES the per-step "
        "worked_example cards in the cards array — the backend materializes "
        "them from solution_steps so they all share one base visual. When "
        "null, the worked example uses the regular per-card flow. Field "
        "ORDER (problem_setup → terminal_state → solution_steps) forces "
        "solve-first commitment under strict JSON."
    ),
    "properties": {
        "problem_setup": {
            "type": "string",
            "description": (
                "One paragraph stating the concrete input/problem the "
                "worked example will solve. For math: the given values "
                "and the quantity to find. Concrete numbers — no "
                "placeholders."
            ),
        },
        "terminal_state_description": {
            "type": "string",
            "description": (
                "One sentence stating what 'done' looks like for this "
                "example (e.g. 'Computed distance d = 5 with units "
                "labeled and interpretation stated.'). Used to verify "
                "the solution_steps run to completion."
            ),
        },
        "solution_steps": {
            "type": "array",
            "items": WORKED_EXAMPLE_STEP_SCHEMA,
            "description": (
                "Ordered sequence of solve steps. Minimum 5 for "
                "non-boundary topics; each step is a complete state "
                "transition with action, reason, and (when applicable) "
                "intermediate result. The LAST step must reach the "
                "terminal state described above."
            ),
        },
    },
    "required": [
        "problem_setup",
        "terminal_state_description",
        "solution_steps",
    ],
    "additionalProperties": False,
}


# Node-link worked example — second pilot of the new visual architecture.
#
# This is the v2 visual schema for any topic where the worked example traces
# through a graph/tree/state machine/circuit. Same persistent-base-plus-deltas
# pattern as worked_example_plan, but for node_link visuals.
#
# Architecture layers (field order = strict-mode planning forcing function):
#   1. visual_type = "node_link"            ← base family
#   2. mode                                 ← discriminator (tree | graph | state_machine | ...)
#   3. purpose                              ← 1-sentence learning intent
#   4. visual_blueprint                     ← 1-3 sentence structural spec
#   5. nodes / edges                        ← structural data
#   6. addons                               ← which side panels render
#   7. solution_steps                       ← per-step deltas (visual + runtime state)
#
# The LLM commits to type → mode → purpose → blueprint → data BEFORE writing
# any step. Each step then only emits what CHANGES (active node, completed
# edges, current call_stack contents). The backend converter materializes
# one card per step; all cards share the same nodes/edges and only the
# state overlay differs.
NODE_LINK_NODE_V2_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "label": {"type": "string"},
        "relation": {"type": "string"},          # "root" | "node" | "leaf" | "state" | "component" ...
        "x": {"type": ["number", "null"]},
        "y": {"type": ["number", "null"]},
        # Mode-specific optional fields (nullable; only some modes use them):
        "parent_id": {"type": ["string", "null"]},           # tree mode
        "is_start": {"type": ["boolean", "null"]},           # state_machine
        "is_accepting": {"type": ["boolean", "null"]},       # state_machine
        "component_kind": {"type": ["string", "null"]},      # circuit (resistor/capacitor/...)
        "container_of": {"type": ["array", "null"], "items": {"type": "string"}},  # architecture
    },
    "required": [
        "id", "label", "relation",
        "x", "y",
        "parent_id", "is_start", "is_accepting", "component_kind", "container_of",
    ],
    "additionalProperties": False,
}

NODE_LINK_EDGE_V2_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "from": {"type": "string"},
        "to": {"type": "string"},
        "label": {"type": "string"},
        "style": {"type": "string"},               # "solid" | "dashed" | "traversal" | "active" | "completed"
        # Mode-specific optional fields (nullable):
        "transition_label": {"type": ["string", "null"]},    # state_machine
        "polarity": {"type": ["string", "null"]},            # circuit
        "flow_kind": {"type": ["string", "null"]},           # architecture (data/control/dependency)
        "weight": {"type": ["string", "null"]},              # weighted graphs
    },
    "required": [
        "from", "to", "label", "style",
        "transition_label", "polarity", "flow_kind", "weight",
    ],
    "additionalProperties": False,
}

NODE_LINK_BASE_VISUAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "visual_type": {
            "type": "string",
            "description": "Always 'node_link' for this base family.",
        },
        "mode": {
            "type": "string",
            "description": (
                "Discriminator within node_link. Allowed values: 'graph' "
                "(free layout, generic graph), 'tree' (hierarchical, "
                "parent_id required on nodes), 'state_machine' (is_start "
                "and is_accepting on nodes, transition_label on edges), "
                "'circuit' (component_kind on nodes), 'architecture' "
                "(container_of on nodes, flow_kind on edges)."
            ),
        },
        "purpose": {
            "type": "string",
            "description": (
                "ONE sentence (8-20 words) stating what the learner should "
                "UNDERSTAND from this visual. Banned verbs: 'shows', "
                "'displays', 'represents'. Use specific verbs like 'compare', "
                "'trace the order of', 'predict the next', 'identify which'."
            ),
        },
        "visual_blueprint": {
            "type": "string",
            "description": (
                "1-3 sentences describing the STRUCTURE of the visual with "
                "concrete values. Name the node count, the root/start node, "
                "the shape characteristics (asymmetric, balanced, dense, "
                "sparse), and any structural irregularity. For BSTs: name "
                "the integer values. For state machines: name the start "
                "and accepting states. For circuits: name the components."
            ),
        },
        "nodes": {
            "type": "array",
            "items": NODE_LINK_NODE_V2_SCHEMA,
        },
        "edges": {
            "type": "array",
            "items": NODE_LINK_EDGE_V2_SCHEMA,
        },
    },
    "required": ["visual_type", "mode", "purpose", "visual_blueprint", "nodes", "edges"],
    "additionalProperties": False,
}

NODE_LINK_STEP_VISUAL_DELTA_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "active_node": {"type": ["string", "null"]},
        "active_edge_from": {"type": ["string", "null"]},
        "active_edge_to": {"type": ["string", "null"]},
        "completed_nodes": {"type": "array", "items": {"type": "string"}},
        "completed_edges_from": {"type": "array", "items": {"type": "string"}},
        "completed_edges_to": {"type": "array", "items": {"type": "string"}},
        "node_state_map": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "node_id": {"type": "string"},
                    "state": {
                        "type": "string",
                        "description": (
                            "One of: unvisited, discovered, newly_discovered, "
                            "current, completed, skipped."
                        ),
                    },
                },
                "required": ["node_id", "state"],
                "additionalProperties": False,
            },
        },
        "attention_note": {"type": "string"},
    },
    "required": [
        "active_node",
        "active_edge_from", "active_edge_to",
        "completed_nodes", "completed_edges_from", "completed_edges_to",
        "node_state_map",
        "attention_note",
    ],
    "additionalProperties": False,
}

NODE_LINK_STEP_RUNTIME_STATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "call_stack": {
            "type": ["array", "null"],
            "items": {"type": "string"},
        },
        "output": {
            "type": ["array", "null"],
            "items": {"type": "string"},
        },
        "frontier": {
            "type": ["array", "null"],
            "items": {"type": "string"},
            "description": "Queue, stack, or wavefront contents.",
        },
        "frontier_kind": {
            "type": ["string", "null"],
            "description": "queue | stack | priority_queue",
        },
        "variables": {
            "type": ["array", "null"],
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "value": {"type": "string"},
                },
                "required": ["name", "value"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["call_stack", "output", "frontier", "frontier_kind", "variables"],
    "additionalProperties": False,
}

NODE_LINK_SOLUTION_STEP_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "step_number": {"type": "integer"},
        "action": {
            "type": "string",
            "description": (
                "One-sentence imperative naming the action this step takes "
                "in the trace (e.g. 'Pop node 30 from the stack and visit it')."
            ),
        },
        "reason": {
            "type": "string",
            "description": (
                "One sentence stating WHY this action happens now (rule "
                "applied, invariant maintained)."
            ),
        },
        "visual_delta": NODE_LINK_STEP_VISUAL_DELTA_SCHEMA,
        "runtime_state": NODE_LINK_STEP_RUNTIME_STATE_SCHEMA,
        "text_points": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Bullet content for the learner-facing card representing "
                "this step. Main bullet + 1-3 sub-bullets max."
            ),
        },
    },
    "required": [
        "step_number",
        "action", "reason",
        "visual_delta", "runtime_state",
        "text_points",
    ],
    "additionalProperties": False,
}

NODE_LINK_WORKED_EXAMPLE_SCHEMA: dict[str, Any] = {
    "type": ["object", "null"],
    "description": (
        "OPTIONAL plan for the worked example when the topic uses a node_link "
        "visual (BST traversals, graph BFS/DFS, state machine traces, etc.). "
        "Currently used for algorithm_walkthrough and data_structure_operation "
        "topics. When emitted, REPLACES the per-step worked_example cards in "
        "the cards array — the backend materializes them so all cards share "
        "the same base_visual (nodes/edges) and only state changes between "
        "steps. Field ORDER (problem_setup → terminal → base_visual → "
        "solution_steps) forces solve-first commitment under strict JSON."
    ),
    "properties": {
        "problem_setup": {
            "type": "string",
            "description": (
                "One paragraph stating the concrete input the worked example "
                "will trace through. For a BST inorder traversal: state the "
                "tree values. For graph BFS: state the start vertex."
            ),
        },
        "terminal_state_description": {
            "type": "string",
            "description": (
                "One sentence stating what 'done' looks like (e.g. 'Output "
                "list contains all 7 values in sorted ascending order'; "
                "'All reachable nodes have been visited and the queue is "
                "empty')."
            ),
        },
        "base_visual": NODE_LINK_BASE_VISUAL_SCHEMA,
        "addons": {
            "type": "array",
            "items": {
                "type": "string",
                "description": (
                    "Side panels the renderer will display alongside the "
                    "node_link visual. Allowed: 'call_stack', 'output_list', "
                    "'variable_table', 'pointer_table', 'frontier_view'."
                ),
            },
        },
        "solution_steps": {
            "type": "array",
            "items": NODE_LINK_SOLUTION_STEP_SCHEMA,
            "description": (
                "Ordered sequence of state transitions. The LLM solves the "
                "problem first then emits the resulting trace. At least 5 "
                "for non-boundary topics; the last step must match the "
                "terminal_state_description."
            ),
        },
    },
    "required": [
        "problem_setup",
        "terminal_state_description",
        "base_visual",
        "addons",
        "solution_steps",
    ],
    "additionalProperties": False,
}


LEAN_LESSON_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "topic_summary": {"type": "string"},
        "estimated_minutes": {"type": "integer"},
        "example_plan": EXAMPLE_PLAN_SCHEMA,
        "worked_example_plan": WORKED_EXAMPLE_PLAN_SCHEMA,
        "node_link_worked_example": NODE_LINK_WORKED_EXAMPLE_SCHEMA,
        "cards": {
            "type": "array",
            "items": LEAN_CARD_SCHEMA,
        },
    },
    "required": [
        "title",
        "topic_summary",
        "estimated_minutes",
        "example_plan",
        "worked_example_plan",
        "node_link_worked_example",
        "cards",
    ],
    "additionalProperties": False,
}


VISUAL_ONLY_CARD_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "card_id": {"type": "string"},
        "visual_type": {"type": "string"},
        "visual_description": {"type": "string"},
        "visual_columns": {"type": "array", "items": {"type": "string"}},
        "visual_rows": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
        "visual_highlight_row": {"type": "integer"},
        "visual_steps": {"type": "array", "items": VISUAL_STEP_SCHEMA},
        "visual_formula": {"type": "string"},
        "visual_symbols": {"type": "array", "items": VISUAL_SYMBOL_SCHEMA},
        "visual_when_to_use": {"type": "string"},
        "visual_center": {"type": "string"},
        "visual_nodes": {"type": "array", "items": LEAN_VISUAL_NODE_SCHEMA},
        "visual_edges": {"type": "array", "items": VISUAL_EDGE_SCHEMA},
        "visual_wrong": {"type": "string"},
        "visual_correct": {"type": "string"},
        "visual_wrong_label": {"type": "string"},
        "visual_correct_label": {"type": "string"},
        "visual_why": {"type": "string"},
        "visual_x_label": {"type": "string"},
        "visual_y_label": {"type": "string"},
        "visual_data_points": {"type": "array", "items": VISUAL_DATA_POINT_SCHEMA},
        "visual_key_points": {"type": "array", "items": VISUAL_KEY_POINT_SCHEMA},
        "visual_array_values": {"type": "array", "items": {"type": "string"}},
        "visual_array_rows": {"type": "array", "items": VISUAL_ARRAY_ROW_SCHEMA},
        "visual_array_pointers": {"type": "array", "items": VISUAL_ARRAY_POINTER_SCHEMA},
        "visual_array_ranges": {"type": "array", "items": VISUAL_ARRAY_RANGE_SCHEMA},
        "visual_array_annotations": {"type": "array", "items": {"type": "string"}},
        "visual_focus": {
            "type": "object",
            "properties": {
                "active_nodes": {"type": "array", "items": {"type": "string"}},
                "highlight_path": {"type": "array", "items": {"type": "string"}},
                "active_step": {"type": "integer"},
                "attention_note": {"type": "string"},
            },
            "required": ["active_nodes", "highlight_path", "active_step", "attention_note"],
            "additionalProperties": False,
        },
    },
    "required": [
        "card_id", "visual_type", "visual_description",
        "visual_columns", "visual_rows", "visual_highlight_row",
        "visual_steps", "visual_formula", "visual_symbols", "visual_when_to_use",
        "visual_center", "visual_nodes", "visual_edges",
        "visual_wrong", "visual_correct", "visual_wrong_label", "visual_correct_label", "visual_why",
        "visual_x_label", "visual_y_label", "visual_data_points", "visual_key_points",
        "visual_array_values", "visual_array_rows", "visual_array_pointers", "visual_array_ranges", "visual_array_annotations",
        "visual_focus",
    ],
    "additionalProperties": False,
}

VISUAL_PATCHES_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "patches": {"type": "array", "items": VISUAL_ONLY_CARD_SCHEMA},
    },
    "required": ["patches"],
    "additionalProperties": False,
}


def generate_visual_patches(card_summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Generate structured visual data for a batch of lesson cards without changing their text."""
    system_prompt = (
        "You are an AI that generates structured visual data for educational lesson cards. "
        "Each card has: card_id, title, card_type, blueprint_key, allowed_visual_type, visual_description (storyboard), and points (bullet content). "
        "Your job: populate the visual DATA fields for the given allowed_visual_type. Rules:\n"
        "- For every visual_steps item, set kind, step_title, visual_label, and step_detail in addition to label/description. "
        "visual_label is for the diagram only: 1-4 words, no trailing punctuation, and not a sliced/truncated explanation. "
        "Use clean visual_label values like Start, Loop, Pop, Check, Push, Update, Done, Stack Ready, or Pop + Explore. "
        "visual_label values in the same visual must be unique unless the exact same action intentionally repeats.\n"
        "- Set visual_type = allowed_visual_type exactly. This is mandatory — never choose a different type.\n"
        "- UNIVERSAL VISUAL TEXT LIMIT: every individual visual block — node label, step label, step description, mini_visual, path label, annotation, edge label — must be 7 words or fewer. Shorten any phrase that exceeds this. Visuals identify and cue; they never explain.\n"
        "- step_flow / causal_chain: fill visual_steps with 2-5 steps. "
        "  label: 2-4 words (verb phrase only, e.g. 'Push to stack'); description: 3-6 words MAX — one short phrase, not a sentence; "
        "  ALWAYS set mini_visual as a 2-5 word cue describing the key data change at this step (e.g. 'stack: [A,B,C]' or 'ptr moves right'). "
        "  For process/overview cards (blueprint_key='process'), set active_step=-1 so all steps appear as an overview with no highlight.\n"
        "- progressive_step_flow: fill visual_steps with 3-6 steps exactly like step_flow. "
        "  label: 2-4 words; description: leave EMPTY ''; ALWAYS set mini_visual as a 2-5 word cue for that step (e.g. 'stack: [A]'). "
        "  Set active=true only on the step being taught in this card. All other steps: active=false.\n"
        "- comparison_table / state_change: fill visual_columns (2-3 headers), visual_rows (each same length as columns), visual_highlight_row (-1 if none).\n"
        "- formula_card: fill visual_formula, visual_symbols (symbol + meaning per token), visual_when_to_use.\n"
        "- misconception: fill visual_wrong, visual_correct, visual_wrong_label, visual_correct_label, visual_why.\n"
        "- concept_map: fill visual_center (1-3 words = topic name) and visual_nodes (2-4 nodes MAXIMUM). "
        "  Each node: id, label (1-2 words ONLY), relation (1 word e.g. 'uses'/'has'/'is'), description='', x, y. "
        "  x/y in 0-100 range, arrange satellites around center at x=50,y=50. Leave description EMPTY — labels only.\n"
        "- topic_snapshot: fill visual_center (1-3 words = topic name) and visual_nodes (1-3 nodes MAXIMUM). "
        "  Each node: id, label (1-2 words ONLY — structural or role label, e.g. 'sorted order' or 'left<root'), relation (1 word), description='', x, y. "
        "  STRICT LIMIT: 3 nodes maximum. Leave description EMPTY.\n"
        "- concept_snapshot: fill visual_center (1-3 words = concept/structure name) and visual_nodes (3-5 nodes). "
        "  Each node: id, label (1-2 words = key anatomical part name, e.g. 'Header', 'Payload', 'Checksum', 'Bucket'), relation (1 word e.g. 'has'), description='', x, y. "
        "  Show the internal structure parts only — no definitions. STRICT LIMIT: 5 nodes maximum.\n"
        "- edge_case_snapshot: fill visual_center (2-4 words = edge case name, e.g. 'Empty BST') and visual_nodes (0-2 nodes MAXIMUM). "
        "  If empty structure: 0 nodes. If single element: 1 node with label only. description='' always. "
        "  STRICT LIMIT: 2 nodes maximum — this must look nearly empty.\n"
        "- relationship_map: fill visual_center (1-3 words = parent concept) and visual_nodes (3-6 nodes). "
        "  Each node: id, label (1-2 words = child term), relation (1 word role e.g. 'has'/'is'/'uses'/'calls'), description='', x, y. "
        "  Arrange children around the parent. Leave description EMPTY — labels and relations only.\n"
        "- relationship_map for roadmap cards (blueprint_key='roadmap'): set visual_center='What you will learn'. "
        "  Fill visual_nodes with one node per study path topic — label = topic name shortened to 3-5 words, relation='', description=''. "
        "  No descriptions, no relation badges.\n"
        "- node_link_diagram for background cards (blueprint_key='background'): generate a DENSE, COMPLEX visual — 8-10 nodes minimum — showing the complete system filled with realistic simulation data. "
        "  Node labels must be short data values of at most 3-4 characters: 1-3 digit integers for trees, single/double letters for graphs (A, B, C, D, E, F, G), small integers for linked lists. "
        "  Set id = label (e.g. if label is a number, id is the same number as a string) and use those data values in edge from/to fields. "
        "  For BST topics: PICK YOUR OWN unique 1-3 digit integer values for the 7-10 nodes. The tree MUST be asymmetric — at least one internal node has only one child, avoid perfectly balanced/complete trees. BST property: every node's left subtree values are smaller, right subtree values are larger. Use different value sets across different lessons; do NOT default to the same numbers. "
        "  For weighted graph algorithms (MST / Dijkstra / Bellman-Ford / shortest path / A*): show a dense graph with 6-8 lettered nodes and 7-10 weighted edges. "
        "  For unweighted graph algorithms (BFS / DFS / topological sort): show a dense graph with 6-8 lettered nodes and 7-10 edges, NO edge labels. "
        "  NEVER use structural descriptions as labels (never 'Root', 'Left Child', 'Right Child', 'Node', 'Leaf', 'Parent' — those are descriptions, not data). "
        "  Do not begin a traversal; show the structure at rest. All edges style='solid', no node marked active.\n"
        "- ANTI-PATTERN — FORBIDDEN for node_link_diagram: do NOT produce hub-and-spoke conceptual diagrams. "
        "  For a card titled 'What is BST Traversal?' or similar intro topic, FORBIDDEN nodes are [{label:'BST'},{label:'Traversal'},{label:'Inorder'},{label:'Preorder'},{label:'Postorder'},{label:'Level-order'}] — these are concept/category labels, not data values. "
        "  IGNORE the visual_description if it suggests a 'central concept connected to types' layout — that is a concept_map pattern, not a node_link_diagram. "
        "  For node_link_diagram, always render the actual underlying data structure (a real BST holding integers, an actual graph with lettered vertices, an actual linked list of integer cells) — never a meta-diagram about what the topic is.\n"
        "- node_link_diagram label validity check: every visual_nodes[i].label MUST be 1-4 characters total AND must be a number, single letter, or short code. If a candidate label is a word like 'BST', 'Tree', 'Root', 'Inorder', 'Traversal', 'Node', 'Leaf' — REJECT IT and use a data value instead.\n"
        "- node_link_diagram for non-background cards: fill visual_nodes (5-10 nodes: id, label, relation='node'/'root'/'leaf'/'current'/'active', description, x, y). "
        "  Node labels must be short data values of at most 3-4 characters (integers for trees, letters for graphs) — never topic names, structural descriptions, or concept labels. "
        "  For trees/BSTs, use a tree layout with root near x=50 y=10 and children spread below. For graph algorithms/MST/shortest path, spread nodes around the canvas. "
        "  Fill visual_edges (one per link: from, to, label='', style='solid'; for graph algorithms include edge weights in label and set style='traversal' on the current edge).\n"
        "- traversal node/edge states: every node_link_diagram node must set state to one of unvisited, discovered, newly_discovered, current, completed, skipped. "
        "Every edge must set state to one of unchecked, active, traversed, checked, skipped, completed. "
        "Use current only for the node being processed; discovered for reached/waiting nodes; completed for fully processed nodes; newly_discovered for the node just added this step. "
        "Use active for the edge being explored now, traversed for an edge that discovered a node, checked/skipped for an inspected edge that did not add a new node, and unchecked for untouched edges.\n"
        "- array_state_diagram: fill visual_array_values for a single array OR visual_array_rows for multi-row array systems. "
        "  visual_array_rows items need label, values, emphasis. Use rows for split/merge overviews like merge sort. "
        "  To show multiple sub-arrays side-by-side within one row, insert \"|\" as a separator in the values list "
        "  (e.g. values=[\"38\",\"27\",\"43\",\"3\",\"|\",\"9\",\"82\",\"10\"] shows two groups side by side). "
        "  For divide-and-conquer background cards, generate 4 rows: Original (emphasis=true), Split (use | separator), "
        "  Sorted halves (use | separator), Merged (emphasis=true). "
        "  Also fill visual_array_pointers (label, index, side='top'/'bottom'), visual_array_ranges (label, start, end), "
        "  visual_array_annotations (e.g. 'mid=4', 'target=7'). "
        "  Use 4-10 cells. Derive values from the visual_description and card points.\n"
        "- path_progress (roadmap/upcoming-topics cards): fill visual_steps with ONLY topic names as labels (2-6 words each). "
        "  description MUST be empty string '' for every step — topic names only, no extra text.\n"
        "- For all unused fields: use empty string or empty array.\n"
        "- Keep data simple and accurate to the card's content. Do NOT invent unrelated information.\n"
        "- Also set visual_focus for each card:\n"
        "  - active_nodes: list of node IDs (matching visual_nodes ids) that are the focal point of this card; [] if no node_link/concept_map visual\n"
        "  - highlight_path: for traversal cards, ordered list of node IDs visited/considered so far; [] otherwise\n"
        "  - active_step: for step_flow/causal_chain, 0-based index of the current step being taught; -1 otherwise\n"
        "  - attention_note: one sentence (max 20 words) naming the specific node, edge, or step to look at and what it shows; use \"\" if no visual\n"
        "- Return one patch object per input card, preserving the card_id."
    )
    cards_text = json.dumps(card_summaries, indent=2)
    response = _create_with_usage(
        "visual_patches",
        model=OPENAI_MODEL,
        input=[{"role": "user", "content": f"Generate visual patches for these cards:\n\n{cards_text}"}],
        text={
            "format": {
                "type": "json_schema",
                "name": "azalea_visual_patches",
                "schema": VISUAL_PATCHES_SCHEMA,
                "strict": True,
            }
        },
        instructions=system_prompt,
    )
    try:
        result = json.loads(response.output_text)
        return result.get("patches") or []
    except (json.JSONDecodeError, AttributeError) as exc:
        raise RuntimeError("OpenAI returned invalid visual patches JSON") from exc


# The lean system prompt is ~18k IDENTICAL tokens (~60% of every call's input). OpenAI auto-caches
# such a prefix at half price + faster TTFT, but under parallel bulk generation identical-prefix
# requests scatter across cache shards and miss (observed ~12% hit). A stable prompt_cache_key pins
# them to one shard so the prefix is actually reused. Both lean entry points share the same prefix,
# so they MUST share the key. Bump the suffix whenever LEAN_SYSTEM_PROMPT changes materially.
_LEAN_CACHE_KEY = "azalea_lean_lesson_v1"


def generate_lean_structured_lesson(
    system_prompt: str,
    user_prompt: str,
) -> dict[str, Any]:
    # The lean lesson is the slowest call (huge strict schema). Bound it so a truly HUNG call fails in
    # minutes instead of blocking a worker for hours (observed anomalies: 977s-8790s). BUT the default
    # must clear LEGITIMATE slow coding leans (measured up to ~352s) or they fail to generate — so the
    # timeout is 600s (well above real leans, well below the hang cluster). One retry absorbs a
    # transient blip; with the two-phase background commit, a later topic's lean failure never blanks
    # earlier topics. Tune via env.
    response = _create_with_usage(
        "lean_lesson",
        timeout=float(os.getenv("AZALEA_LEAN_TIMEOUT_SECONDS", "600")),
        max_retries=max(0, int(os.getenv("AZALEA_LEAN_MAX_RETRIES", "1"))),
        model=OPENAI_MODEL,
        prompt_cache_key=_LEAN_CACHE_KEY,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "azalea_lean_lesson",
                "schema": LEAN_LESSON_JSON_SCHEMA,
                "strict": True,
            }
        },
    )

    # A truncated response (output hit the model's max output tokens) produces
    # cut-off JSON that fails to parse. Detect it explicitly so the failure is
    # diagnosable as "lesson too large" rather than a generic parse error.
    status = getattr(response, "status", None)
    if status == "incomplete":
        details = getattr(response, "incomplete_details", None)
        reason = None
        if details is not None:
            reason = details.get("reason") if isinstance(details, dict) else getattr(details, "reason", None)
        raise RuntimeError(
            "OpenAI lean lesson response was truncated "
            f"(status=incomplete, reason={reason}); the lesson exceeded the model's "
            "max output tokens. Reduce lesson size (fewer/leaner cards)."
        )

    try:
        return json.loads(response.output_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("OpenAI returned invalid lean lesson JSON") from exc


class _StreamingCardExtractor:
    """Incrementally pull complete `lesson_cards` objects out of a streaming
    strict-JSON lesson response. feed(chunk) returns the cards that completed in
    this chunk. Brace/quote aware, so braces and quotes inside string values are
    handled correctly. Stops collecting once the lesson_cards array closes.
    """

    def __init__(self) -> None:
        self.buf = ""
        self.started = False
        self.done = False
        self.depth = 0
        self.in_string = False
        self.escape = False
        self.card_start = -1
        self.scan = 0

    def feed(self, chunk: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        self.buf += chunk
        if self.done:
            return out
        if not self.started:
            k = self.buf.find('"lesson_cards"')
            if k < 0:
                return out
            b = self.buf.find("[", k)
            if b < 0:
                return out
            self.started = True
            self.scan = b + 1
        i = self.scan
        while i < len(self.buf):
            ch = self.buf[i]
            if self.escape:
                self.escape = False
            elif self.in_string and ch == "\\":
                self.escape = True
            elif ch == '"':
                self.in_string = not self.in_string
            elif not self.in_string:
                if ch == "{":
                    if self.depth == 0:
                        self.card_start = i
                    self.depth += 1
                elif ch == "}":
                    self.depth -= 1
                    if self.depth == 0 and self.card_start >= 0:
                        try:
                            out.append(json.loads(self.buf[self.card_start:i + 1]))
                        except json.JSONDecodeError:
                            pass
                        self.card_start = -1
                elif ch == "]" and self.depth == 0:
                    self.done = True
                    self.scan = i + 1
                    return out
            i += 1
        self.scan = i
        return out


def generate_lean_structured_lesson_streaming(
    system_prompt: str,
    user_prompt: str,
):
    """Stream a lean lesson. Yields ("card", card_dict) as each lesson card
    completes, then ("lesson", full_lean_json) once the response finishes.

    Used to render early cards to the learner while later cards are still being
    generated. Callers MUST treat this as best-effort and fall back to the
    blocking generator on any exception, so a streaming hiccup never blocks a
    lesson from being produced.
    """
    extractor = _StreamingCardExtractor()
    parts: list[str] = []
    stream = client.responses.create(
        model=OPENAI_MODEL,
        prompt_cache_key=_LEAN_CACHE_KEY,  # same 18k prefix as the blocking path — share the shard
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "azalea_lean_lesson",
                "schema": LEAN_LESSON_JSON_SCHEMA,
                "strict": True,
            }
        },
        stream=True,
    )
    for event in stream:
        etype = str(getattr(event, "type", "") or "")
        if etype.endswith("output_text.delta"):
            delta = getattr(event, "delta", "")
            if isinstance(delta, str) and delta:
                parts.append(delta)
                for card in extractor.feed(delta):
                    yield ("card", card)
        elif etype.endswith("response.completed") and not parts:
            resp = getattr(event, "response", None)
            txt = getattr(resp, "output_text", None) if resp is not None else None
            if isinstance(txt, str) and txt:
                parts.append(txt)

    full_text = "".join(parts)
    try:
        lesson = json.loads(full_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("OpenAI returned invalid lean lesson JSON (stream)") from exc
    yield ("lesson", lesson)


# Focused single-card slot generation (EXAMPLE_SYSTEM_SPEC §6/§8.1). One tiny call
# per card slot — the model writes only that card's prose, never the structure.
CARD_SLOT_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "points": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "points"],
    "additionalProperties": False,
}


def generate_card_slot(system_prompt: str, user_prompt: str) -> dict[str, Any]:
    """Generate one card's {title, points} from a focused prompt."""
    response = _create_with_usage(
        "card_slot",
        model=OPENAI_MODEL,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        text={"format": {"type": "json_schema", "name": "azalea_card_slot",
                          "schema": CARD_SLOT_JSON_SCHEMA, "strict": True}},
    )
    return json.loads(response.output_text)
