"""Executed-reference worked examples — the GENERAL, non-hardcoded ground truth for walkthroughs.

A walkthrough has no user code to trace, and the model can't reliably hand-simulate an algorithm
(it truncates, picks wrong edges, loses global state). Instead of hand-coding a reference per
algorithm (which doesn't scale and is the hardcoding we want to avoid), we:

  1. ask the model to WRITE a clean reference implementation of the algorithm (models are reliable at
     standard algorithms, far more than at hand-simulating them),
  2. EXECUTE it on the real input,
  3. build the worked example from the REAL execution trace, rendered conceptually (no code shown).

Flexible (works for ANY algorithm the model can implement) + correct (execution, not a guess) + no
per-algorithm code from us. The model call is injectable, so this is fully testable offline.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from .executor import run_trace
from .trace_first import build_cards_from_trace

ModelFn = Callable[[dict[str, str]], Optional[dict[str, Any]]]
ExecInputFn = Callable[[Any, Any], Any]

# Topic types for which an executable algorithmic reference makes sense (not plain concepts/definitions).
ALGORITHMIC_TOPIC_TYPES = frozenset({
    "algorithm_walkthrough", "coding_implementation", "data_structure_operation",
})

_REF_SYSTEM = (
    "You write ONE clean, correct Python reference implementation of the algorithm named in the prompt. "
    "It will be EXECUTED to produce a worked example — it is NOT shown to a learner, so optimise for "
    "correctness and runnability, not pedagogy. Rules: a single entry function named for the algorithm; "
    "any helpers as TOP-LEVEL functions (never nested, never a custom class PARAMETER); accept the input "
    "as plain built-in data — a list for sequence algorithms, or for a graph a `(num_vertices, edges)` "
    "pair (edges as `(u, v, weight)`) or an adjacency map `{node: [(neighbour, weight), ...]}` — so the "
    "function runs on the data as given. Return the algorithm's REAL result (an MST as the list of "
    "`(u, v, weight)` edges connecting ALL vertices; a sorted list; a traversal order; a found index; "
    "etc.). Use only the standard library (heapq/collections/math/itertools/bisect/functools). "
    'Return ONLY JSON: {"code": "<the python implementation>"}.'
)


def _build_prompt(topic: dict[str, Any], example_input: Any) -> dict[str, str]:
    return {
        "system": _REF_SYSTEM,
        "user": (f"Algorithm / topic: {topic.get('title') or topic.get('name')}\n"
                 f"Input it must run on: {example_input}\n"
                 f"Write the reference implementation."),
    }


def _collections(card: dict[str, Any]) -> dict[str, Any]:
    """Collection-valued state on a card (lists/dicts/sets) — the algorithm's PROGRESS, as opposed to
    scalar loop variables (i, u, w) which are execution noise in a conceptual walkthrough."""
    return {k: v for k, v in (card.get("state") or {}).items() if isinstance(v, (list, dict, set))}


def _result_accumulator(cards: list[dict[str, Any]], final_answer: Any) -> Optional[str]:
    """The collection-valued variable that BUILDS the final answer (mst / order / dp table) — identified
    as the one whose final value matches the executed return. That's the teaching-relevant state; every
    other variable (union-find `parent`, loop edge `e`) is internal machinery we hide."""
    if not cards or final_answer is None:
        return None
    fa = repr(final_answer)
    fa_sorted = repr(sorted(map(repr, final_answer))) if isinstance(final_answer, (list, tuple)) else None
    last = _collections(cards[-1])
    for k, v in last.items():
        if repr(v) == fa:
            return k
        if fa_sorted is not None and isinstance(v, (list, tuple)) and repr(sorted(map(repr, v))) == fa_sorted:
            return k
    return None


def _conceptualize(cards: list[dict[str, Any]], final_answer: Any = None) -> list[dict[str, Any]]:
    """Turn executed-code trace cards into CONCEPTUAL walkthrough cards: a walkthrough shows no code and
    no raw variable dumps, so we surface the algorithm's RESULT ACCUMULATOR (the collection that builds
    the answer) and how it grows, and drop code refs + internal machinery. A downstream LLM narration
    pass (applied by the pipeline) polishes the prose around these REAL, verified states; never alters
    them. Falls back to any dynamic collection when the accumulator can't be pinpointed."""
    if not cards:
        return cards
    focus = _result_accumulator(cards, final_answer)
    if focus is None:  # fallback: the collection that changes the most across the run
        all_keys: set[str] = set().union(*(set(_collections(c)) for c in cards))
        dynamic = [k for k in all_keys if len({repr(_collections(c).get(k)) for c in cards}) > 1]
        focus = dynamic[0] if dynamic else None
    if focus is None:
        for c in cards:
            c["code_refs"] = []
        return cards
    # Keep only cards where the accumulator is in scope (drops helper-frame internals like a union-find
    # find()'s parent/x), collapsing no-op repeats (cycle-skipped iterations) to keep it tight.
    kept: list[dict[str, Any]] = []
    prev = object()
    for c in cards:
        coll = _collections(c)
        if focus not in coll:
            continue
        val = coll[focus]
        if kept and repr(val) == repr(prev):
            continue
        c["work"] = [f"{focus} is now {val!r}"]
        c["result"] = f"{focus} = {val!r}"
        c["code_refs"] = []
        kept.append(c)
        prev = val
    for i, c in enumerate(kept, start=1):
        c["goal"] = f"Step {i}: build {focus}" if i < len(kept) else f"Final {focus}"
    return kept or cards


def build_executed_reference(
    topic: dict[str, Any],
    example_input: Any,
    *,
    generate: ModelFn,
    executable_input: ExecInputFn,
    executor: Callable[[str, str, Any], Optional[list]] = run_trace,
    node_labels: Optional[list[str]] = None,
    conceptual: bool = True,
) -> dict[str, Any]:
    """Build a worked example by generating a reference implementation, executing it, and tracing the
    real run. Returns {cards, final_answer, source: 'executed_reference', code} or {} on any miss
    (no input, model unavailable, code won't run) — caller then falls back to the model narration."""
    if not example_input:
        return {}
    out = generate(_build_prompt(topic, example_input))
    code = (out or {}).get("code")
    if not code or not isinstance(code, str):
        return {}
    exec_input = executable_input(code, example_input)
    trace = executor(code, "python", exec_input)
    if not trace:
        return {}
    tf = build_cards_from_trace(trace, code=code, node_labels=node_labels)
    if not tf.get("cards"):
        return {}
    if conceptual:
        tf["cards"] = _conceptualize(tf["cards"], tf.get("final_answer"))
    tf["source"] = "executed_reference"
    tf["code"] = code
    return tf
