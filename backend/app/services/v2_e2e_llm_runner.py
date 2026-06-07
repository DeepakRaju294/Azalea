"""Real-LLM verification runner for the v2 pipeline.

Synthetic smoke (v2_e2e_smoke.py) checks the compiler chain without an
LLM. This runner actually calls the LLM for one synthetic topic per
base_type, runs the resulting JSON through the compiler + validators,
and reports pass/fail per base_type.

Useful for:
  - Pre-cutover proofs that the prompt + compiler combination works
    against a real model for every base_type
  - Detecting prompt drift (the model started emitting a different shape)
  - Regression coverage on prompt changes

Run:
    python -m app.services.v2_e2e_llm_runner

Requires:
  - OPENAI_API_KEY (or whatever your llm_client is configured with)
  - Network access
  - Costs roughly one chat completion per base_type (~12 small calls)

Outputs JSON to stdout. Exit code 0 iff every base_type returns a
validator-clean lesson.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

from app.core.visual_ontology_v2 import (
    BASE_VISUAL_TYPES,
    DOMAIN_TO_BASE_TYPE,
    DOMAIN_TO_DEFAULT_MODE,
    MODES_BY_BASE_TYPE,
)
from app.services.lean_lesson_generator_v2 import compile_lesson_v2
from app.services.visual_validators_v2 import validate_lesson_v2


# Synthetic topics, one per base_type. Picked to be unambiguous and to
# steer the LLM into the right plan format.
_TOPICS: dict[str, dict[str, str]] = {
    "node_link_diagram": {
        "title": "Inorder Traversal of a BST",
        "summary": "Inorder (left, node, right) traversal of a binary search tree.",
        "domain": "tree",
    },
    "indexed_sequence_diagram": {
        "title": "Binary Search on a Sorted Array",
        "summary": "Find target in sorted array with l, r, m pointers.",
        "domain": "array",
    },
    "code_execution_panel": {
        "title": "Implement Recursive Fibonacci",
        "summary": "Trace through fib(5) with recursion stack.",
        "domain": "code",
    },
    "grid_matrix_diagram": {
        "title": "Longest Common Subsequence DP Table",
        "summary": "Fill the 2D DP table for LCS.",
        "domain": "matrix",
    },
    "formula_symbolic_expression": {
        "title": "Bayes Theorem Derivation",
        "summary": "Derive P(A|B) from joint probability.",
        "domain": "formula",
    },
    "table_diagram": {
        "title": "BFS vs DFS Comparison",
        "summary": "Compare BFS and DFS by data structure, order, and shortest-path support.",
        "domain": "table",
    },
    "coordinate_graph": {
        "title": "Normal Distribution Density",
        "summary": "Plot the standard normal curve and shade tail probabilities.",
        "domain": "coordinate_math",
    },
    "memory_layout_diagram": {
        "title": "Stack Frames in Recursive Factorial",
        "summary": "Show stack frame push/pop during factorial(3).",
        "domain": "memory",
    },
    "geometric_diagram": {
        "title": "Pythagorean Theorem",
        "summary": "Triangle with sides a, b, c and a^2 + b^2 = c^2.",
        "domain": "geometry",
    },
    "timeline_sequence_interaction": {
        "title": "TCP Three-Way Handshake",
        "summary": "Client and server exchange SYN, SYN-ACK, ACK.",
        "domain": "timeline_protocol",
    },
    "set_region_diagram": {
        "title": "Venn Diagram of Set Union and Intersection",
        "summary": "Show A union B, A intersect B, and A complement.",
        "domain": "set_logic",
    },
    "image_real_world_illustration": {
        "title": "Cache as a Desk Drawer",
        "summary": "Analogy: small fast desk drawer vs large filing cabinet.",
        "domain": "real_world",
    },
}


def _call_llm(base_type: str, topic: dict[str, str]) -> dict[str, Any]:
    """Make one LLM call for the given topic. Returns the parsed lesson_v2
    JSON. Raises on any failure."""
    from app.prompts.lean_lesson_prompt_v2 import (
        SYSTEM_PROMPT_V2,
        build_lesson_v2_prompt,
    )
    from app.services.llm_client import client
    from app.services.llm_schemas_v2 import LESSON_V2_SCHEMA

    domain = topic["domain"]
    user_prompt = build_lesson_v2_prompt(
        topic_title=topic["title"],
        topic_summary=topic["summary"],
        topic_type="algorithm_walkthrough",
        visual_domain=domain,
        visual_mode_hint=DOMAIN_TO_DEFAULT_MODE.get(domain, "tree_hierarchy"),
        knowledge_level=None,
        chunks_text="",
    )
    response = client.responses.create(
        model="gpt-4o-mini",
        input=[
            {"role": "system", "content": SYSTEM_PROMPT_V2},
            {"role": "user", "content": user_prompt},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "lesson_v2",
                # strict=False: base_state and state_after are polymorphic;
                # see comment in lessons_v2.generate_lesson_v2.
                "strict": False,
                "schema": LESSON_V2_SCHEMA,
            },
        },
    )
    return json.loads(response.output_text)


def _run_one(base_type: str, topic: dict[str, str]) -> dict[str, Any]:
    """Run the full real-LLM pipeline for one base_type. Returns a result
    dict with validator counts + base_type distribution. Never raises;
    failures become an `error` field on the result."""
    start = time.monotonic()
    result: dict[str, Any] = {"base_type": base_type, "topic": topic["title"]}
    try:
        lesson_v2_raw = _call_llm(base_type, topic)
        lesson = compile_lesson_v2(
            lesson_v2_raw=lesson_v2_raw,
            topic_id=f"llm_smoke_{base_type}",
            topic_hint=topic["title"],
            topic_type="algorithm_walkthrough",
            visual_domain=topic["domain"],
            source_chunks_excerpt="",
            source_chunk_ids=[],
            source_summary="",
        )
        report = validate_lesson_v2(lesson)
        result["visual_models_count"] = len(lesson["visual_models"])
        result["render_steps_count"] = len(lesson["render_steps"])
        result["validator_errors"] = len(report.errors())
        result["validator_warnings"] = len(report.warnings())
        result["base_type_distribution"] = sorted({
            m["base_type"] for m in lesson["visual_models"]
        })
        # Pass criterion: validator clean AND at least one visual model
        # of the requested base_type appeared in the output.
        result["passed"] = (
            result["validator_errors"] == 0
            and base_type in result["base_type_distribution"]
        )
    except Exception as exc:  # noqa: BLE001
        result["passed"] = False
        result["error"] = f"{type(exc).__name__}: {exc}"
    result["duration_seconds"] = round(time.monotonic() - start, 2)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        help="Run only these base_types (repeatable). Default: all 12.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of the human summary",
    )
    args = parser.parse_args()

    selected = set(args.only) or set(BASE_VISUAL_TYPES)
    results: list[dict[str, Any]] = []
    for base_type in BASE_VISUAL_TYPES:
        if base_type not in selected:
            continue
        topic = _TOPICS.get(base_type)
        if topic is None:
            results.append({
                "base_type": base_type,
                "passed": False,
                "error": "no topic fixture",
            })
            continue
        results.append(_run_one(base_type, topic))

    passed = sum(1 for r in results if r.get("passed"))
    total = len(results)
    summary = {"passed": passed, "total": total, "results": results}

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"Real-LLM smoke: {passed}/{total} base_types passed")
        for r in results:
            status = "PASS" if r.get("passed") else "FAIL"
            extra = r.get("error") or (
                f"models={r.get('visual_models_count')} "
                f"steps={r.get('render_steps_count')} "
                f"errs={r.get('validator_errors')} "
                f"warns={r.get('validator_warnings')} "
                f"dist={r.get('base_type_distribution')} "
            )
            print(f"  {status:4} {r['base_type']:36} ({r.get('duration_seconds', 0)}s) {extra}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
