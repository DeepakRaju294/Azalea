"""Prompt assembly for the single-pass / audit / repair calls (spec §3, §8, §9.2).

Pure string assembly from the deterministic pre-pass config (§2) + spec rules. No
LLM call here — these build the ``{"system", "user"}`` payload the injected solver
consumes (mirroring the existing ``_default_solver`` payload contract).
"""
from __future__ import annotations

import json
from typing import Any

from .prepass import PrepassConfig

_FIRST_PASS_SYSTEM = (
    "You generate ONE complete, renderable worked example in a single pass — a CONCRETE execution on a "
    "specific input, NOT a mini-lesson. Emit final cards, not a plan. RULES, all mandatory:\n"
    "0. `problem` is a CONCRETE, self-contained problem statement that NAMES THE ACTUAL INPUT the example "
    "runs on and what to do with it — e.g. 'Sort the array [3, 6, 8, 10, 1, 2, 1] using quick sort, "
    "showing each partition.' It must contain real values. NEVER use the topic title, and never a vague "
    "objective like 'Understanding X' or 'Learn how X works'. The input named here MUST be the same input "
    "the first step operates on, and `initial_resolved_state` must reflect it.\n"
    "0b. INPUT: if the user payload provides `example_input`, use EXACTLY those values (do not change, "
    "shorten, or re-order them) as the example input — this includes a provided `tree` (level-order "
    "node list, null = missing child) or `graph` (an adjacency map, OR a `{nodes, edges:[[u, v, "
    "weight], ...]}` WEIGHTED graph for MST / shortest-path — run the algorithm on the graph's EDGES, "
    "never treat it as a binary tree). Otherwise choose an input with AT "
    "LEAST `min_example_array_size` elements: for an array/list use >= that many elements; for a TREE or "
    "GRAPH example use >= that many NODES — never a tiny 3-4 element/node structure, which hides the "
    "algorithm's behaviour.\n"
    "1. EVERY card is a concrete step: `work` is a NON-EMPTY list of action lines with ACTUAL values "
    "from the example input, and `result` is a NON-EMPTY string. Never emit a card with empty work or "
    "null result. Do NOT include 'introduction'/'concept'/'base case definition' cards — only steps that "
    "actually run on the input.\n"
    "1b. CODING work lines = VERBATIM code + what it DOES: for a coding_implementation card, each `work` "
    "line BEGINS with the exact code line from the shown code, character-for-character WITH ITS VARIABLE "
    "NAMES (e.g. `queue = [start]`, `visited.add(neighbor)`), THEN — REQUIRED on EVERY line — ` // "
    "<plain-English description of what this line DOES in the algorithm right now, naming the concrete "
    "value(s)>`. A coding work line with NO ` // ` explanation is INVALID. Do NOT substitute values "
    "into the code itself; put the value inside the explanation. Write `visited.add(neighbor) // mark "
    "neighbor B as visited so it is not processed again`, NEVER `visited.add('B')`; write "
    "`queue.append(neighbor) // add B to the back of the queue`, NEVER `queue.append('B')`; write "
    "`queue = [start] // start the queue with the start node A`, NEVER `queue = ['A']`. The verbatim line "
    "anchors the highlight; the `//` part teaches what the line accomplishes for THIS input.\n"
    "1c. This `code //` form is ONLY for coding_implementation cards. For EVERY OTHER example type "
    "(algorithm_walkthrough, data_structure_operation, math, concept, proof) the `work` is PLAIN LANGUAGE "
    "/ math notation describing the operation with the concrete values — NEVER source code and NEVER a "
    "`//` code comment. Write 'Sort the edges by weight: (A,B,1), (B,C,2), (A,C,3)' NOT "
    "`edges.sort(key=lambda x: x[2])`; write 'Add edge (A,B,1) to the MST' NOT `mst_edges.append(edges[0])`.\n"
    "2. One card = one coherent TEACHING transition (group its actions into `work`; split only if `work` "
    "would exceed ~6 lines). Show a bounded, representative projection — do NOT narrate every symmetric "
    "recursive call.\n"
    "3. `state_delta` is EITHER null (when state_relevance is 'static' or 'none') OR exactly "
    "{\"ops\":[{\"op\":\"set|append|push|add|remove|pop|move|clear\",\"path\":\"<a path from "
    "state_schema_paths>\",\"value\":<for set/push/add>,\"values\":[<for append>]}]}. Use ONLY paths "
    "listed in state_schema_paths. Never invent free-form delta keys.\n"
    "4. FORMAT — every card is Goal / Reasoning / Work / Result: a NON-EMPTY `goal` (the subproblem this "
    "step resolves) and a NON-EMPTY `result` ALWAYS. For the justification field: coding cards MUST give "
    "`how` (which construct/line does it + what it does) + `code_refs`; every other card MUST give a "
    "NON-EMPTY `reasoning` (the decisive reason this step is valid or why it is taken). Exactly one of "
    "{how, reasoning} per card — never both, never neither. Do NOT omit reasoning even when it seems "
    "obvious.\n"
    "5. Cover every required_case (tag each card's `cases_covered`) and reach the final answer within the "
    "card cap.\n"
    "6. ACCURACY IS MANDATORY: the example must be CORRECT. `final_answer` is the true result of applying "
    "the method to the stated input, and EVERY input element must be accounted for in the output (same "
    "multiset — do not drop or duplicate values). Use the method's REAL mechanics: e.g. quicksort "
    "partitions IN PLACE around a pivot and recurses — it does NOT 'merge' sorted halves like merge sort. "
    "If unsure of a step's result, recompute it; never invent a plausible-looking but wrong value.\n"
    "7. ORDER: present steps in TRUE EXECUTION ORDER. For recursion, FULLY resolve a recursive sub-call "
    "(sort the sub-partition / reach its base case) BEFORE the step that uses its result. A later card "
    "must NEVER show a less-complete or earlier state than an earlier card — progress is monotonic — and "
    "the FINAL card shows the terminal result with nothing after it. Do not show the finished array and "
    "then go back to sorting a piece of it.\n"
    "Return a single JSON object with the keys in must_emit."
)

_AUDIT_SYSTEM = (
    "You audit a rendered worked example and return ONLY bounded patches (<=5 edits, <=2 structural, "
    "<=1 insert). Never re-author the lesson. Prefer `pass_no_edits` unless there is a concrete "
    "correctness, completeness, clarity, density, continuity, or text-state mismatch. Do not edit "
    "merely to express a different writing style. For coding cards check that `how` explains the "
    "implementation mechanism; for math/proof/concept cards check that `reasoning` gives the decisive "
    "justification. Return JSON {status, edits[]}."
)

_REPAIR_SYSTEM = (
    "You repair an INVALID worked example given the concrete validation errors. Return the FULL artifact "
    "with the SAME `cards` array (same shape: title/goal/work[]/result/state_delta/state_relevance/"
    "cases_covered, coding cards also how/code_refs), fixing ONLY the listed errors. Never drop the "
    "`cards` array, never return prose. `work` and `result` must be non-empty; `state_delta` is null or "
    "the {\"ops\":[...]} form. Return the corrected JSON object."
)


def _schema_paths(config: PrepassConfig) -> list[str]:
    if not config.state_schema:
        return []
    try:
        from .state import get_schema
        return sorted(get_schema(config.state_schema).paths)
    except Exception:
        return []


def build_first_pass_payload(config: PrepassConfig, topic: dict[str, Any]) -> dict[str, str]:
    paths = _schema_paths(config)
    user = {
        "instruction": "Generate the complete worked example as cards within these fixed constraints.",
        "config": config.as_dict(),
        "topic": {
            "title": topic.get("title") or topic.get("name"),
            "summary": topic.get("summary") or topic.get("description"),
            "code": topic.get("code"),
        },
        "example_input": config.example_input,           # backend-chosen input (array families) — use EXACTLY
        "min_example_array_size": config.min_example_array_size,
        "state_schema_paths": paths,
        "state_delta_form": (
            {"ops": [{"op": "append", "path": (paths[0] if paths else "<path>"), "values": ["<value>"]},
                     {"op": "set", "path": (paths[1] if len(paths) > 1 else "<path>"), "value": "<value>"}]}
            if paths else "null (no state_schema for this topic; use state_relevance none/static)"
        ),
        "card_shape": {
            "base": ["title", "goal[NON-EMPTY]", "reasoning[NON-EMPTY]", "work[NON-EMPTY]",
                     "result[NON-EMPTY]", "state_delta|null", "state_relevance", "cases_covered[]"],
            "coding": ["title", "goal", "how", "work[NON-EMPTY]", "result[NON-EMPTY]",
                       "state_delta|null", "state_relevance", "cases_covered[]", "primary_kind",
                       "subkinds[]", "explanation_mode='implementation_how'", "code_refs[int]"],
        },
        "caps": {
            "min_cards": config.minimum_example_cards,
            "max_cards": config.maximum_example_cards,
            "max_work_lines_per_card": 6,
        },
        "must_emit": ["problem", "initial_resolved_state", "cards", "final_answer"],
    }
    return {"system": _FIRST_PASS_SYSTEM, "user": json.dumps(user, ensure_ascii=False)}


def build_audit_payload(rendered: dict[str, Any], validation_report: list[str]) -> dict[str, str]:
    user = {
        "rendered_example": rendered,
        "deterministic_validation_report": validation_report,
        "edit_budget": {"max_edits": 5, "max_structural": 2, "max_insert": 1},
        "allowed_ops": [
            "replace_field", "replace_fields", "merge_cards", "split_card", "delete_card",
            "insert_card", "update_state", "update_code_refs", "update_case_coverage", "pass_no_edits",
        ],
    }
    return {"system": _AUDIT_SYSTEM, "user": json.dumps(user, ensure_ascii=False)}


def build_repair_payload(invalid_artifact: dict[str, Any], errors: list[str]) -> dict[str, str]:
    user = {"invalid_artifact": invalid_artifact, "validation_errors": errors}
    return {"system": _REPAIR_SYSTEM, "user": json.dumps(user, ensure_ascii=False)}
