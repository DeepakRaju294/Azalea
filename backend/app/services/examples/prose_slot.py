"""Prose slots + the ProseValidator (EXAMPLE_SYSTEM_SPEC.md §4.1, §5.3 #4).

A ProseSlot is the only thing an LLM would ever receive: one grounded, delta-focused
slot per milestone frame. `build_prose_slots` extracts the step's `bullets` and
`allowed_facts` deterministically from the folded frame state (per example type), so
the default `deterministic_points` generator is in-sync by construction. Each
bullet is ONE action (calculate mid / compare to target / move a bound), so a step
reads as its broken-down reasoning moves, not one compressed line. An LLM generator
can be injected later; whatever it returns is gated by `validate_points`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Optional

from app.core.example_fixtures import CanonicalFixture


@dataclass(frozen=True)
class ProseSlot:
    slot_id: str
    frame_index: int
    step_role: str
    previous_frame_summary: str
    current_frame_delta: str          # one-line summary of what CHANGED
    bullets: tuple[str, ...]          # the broken-down reasoning moves (deterministic)
    allowed_facts: tuple[str, ...]    # the ONLY facts the prose may use
    required_mentions: tuple[str, ...] = ()
    forbidden_mentions: tuple[str, ...] = ()


def _arr(fixture: CanonicalFixture) -> list[Any]:
    return list(fixture.base_structure.get("array") or fixture.input.get("array") or [])


def _target(fixture: CanonicalFixture) -> Any:
    return fixture.input.get("target")


def _cmp_word(value: Any, target: Any) -> str:
    try:
        if value == target:
            return "equals"
        return "is greater than" if value > target else "is less than"
    except TypeError:
        return "compares against"


# --- per-example-type extractors → (step_role, bullets, facts) -------------------

def _seq(after: dict, prev: Optional[dict], pos: str, fixture: CanonicalFixture) -> tuple[str, list[str], list[str]]:
    arr, target = _arr(fixture), _target(fixture)
    low, high, mid = after.get("low"), after.get("high"), after.get("mid")
    facts = [f"low={low}", f"high={high}", f"mid={mid}", f"target={target}", f"array_len={len(arr)}"]

    if pos == "first" and mid is None:
        return "setup", [
            f"The array is sorted, so we can search it by halving: {len(arr)} elements, indices 0 to {len(arr) - 1}.",
            f"Set low = 0 and high = {high} — the search range starts as the whole array.",
            f"We are looking for the target value {target}.",
        ], facts

    # The concept simulator emits each probe's OWN bounds on its frame.
    value = arr[mid] if isinstance(mid, int) and 0 <= mid < len(arr) else None
    bullets = [f"Calculate the middle: mid = ({low} (low) + {high} (high)) // 2 = {mid}."]
    facts += [f"mid=({low}+{high})//2={mid}", f"arr[{mid}]={value}"]

    if after.get("found") is not None:
        bullets.append(f"Compare arr[{mid}] = {value} with the target {target}: they are equal.")
        bullets.append(f"Found — the target is at index {mid}. The search ends.")
        return "terminate", bullets, facts

    word = _cmp_word(value, target)
    bullets.append(f"Compare arr[{mid}] = {value} with the target {target}: {value} {word} {target}.")
    try:
        goes_left = value is not None and target is not None and value > target
    except TypeError:
        goes_left = False
    if goes_left:
        bullets.append(f"The target must be LEFT of mid, so discard the right half: high = mid - 1 = {mid - 1}.")
        facts.append(f"new_high={mid - 1}")
    else:
        bullets.append(f"The target must be RIGHT of mid, so discard the left half: low = mid + 1 = {mid + 1}.")
        facts.append(f"new_low={mid + 1}")
    return "update_pointer_or_range", bullets, facts


def _node(after: dict, prev: Optional[dict], pos: str, diff: dict) -> tuple[str, list[str], list[str]]:
    active = after.get("active")
    kind = str((after.get("frontier") or {}).get("kind") or "queue")
    frontier = list((after.get("frontier") or {}).get("items") or [])
    output = list(after.get("output") or [])
    added = list(diff.get("newly_added") or [])

    # Edge-selection narration (MST / shortest-path tree): the meaningful action is the
    # edge added, not a dequeue. Fires whenever the frame carries a selected-edge set.
    selected = [list(e) for e in (after.get("selected_edges") or [])]
    active_edge = list(after.get("active_edge") or [])
    new_edge = diff.get("newly_selected_edge") or (active_edge if (active_edge and active_edge[0]) else None)
    if selected or new_edge:
        return _node_edges(active, selected, new_edge, output, pos)

    facts = [f"active={active}", f"frontier={frontier}", f"output={output}", f"newly_added={added}"]
    is_stack = kind == "stack"
    is_pq = kind == "priority_queue"
    container = "stack" if is_stack else ("priority queue" if is_pq else "queue")

    if pos == "first":
        bullets = [f"Begin at {active} — the start node. Mark it visited."]
        if added:
            bullets.append(f"Discover its neighbours {', '.join(added)} and add them to the {container}: {frontier}.")
        bullets.append(f"Order so far: {output}.")
        return "setup", bullets, facts

    if pos == "last" and not frontier:
        return "terminate", [
            f"The {container} is empty — every reachable node has been finalized.",
            f"Final order: {output}.",
        ], facts

    if is_stack:
        take = f"Pop {active} — the MOST RECENTLY discovered node on the stack (depth-first dives deeper first)."
    elif is_pq:
        take = f"Extract {active} — the closest unfinalized node (smallest tentative distance)."
    else:
        take = f"Dequeue {active} — the oldest node waiting in the queue."
    bullets = [f"{take} Mark it visited."]
    if added:
        verb = "push" if is_stack else ("add" if is_pq else "enqueue")
        bullets.append(f"Discover its unvisited neighbour{'s' if len(added) > 1 else ''} {', '.join(added)} and {verb}: {container} is now {frontier}.")
    else:
        bullets.append(f"All of its neighbours are already visited — nothing new joins the {container} ({frontier}).")
    bullets.append(f"Order so far: {output}.")
    return "visit_complete", bullets, facts


def _node_edges(active, selected: list, new_edge, output: list, pos: str) -> tuple[str, list[str], list[str]]:
    """Edge-selection prose (MST / shortest-path tree) — narrates the edge added and
    the growing tree, grounded in the frame's selected-edge set (INV-PROSE-SYNC)."""
    a, b = (new_edge or (selected[-1] if selected else [None, None]))[:2]
    facts = [f"active={active}", f"new_edge={new_edge}", f"selected={selected}", f"tree_nodes={output}"]
    if pos == "first":
        return "select_active", [
            f"Start the tree from {output[0] if output else active}.",
            f"Add edge {a}–{b}, bringing {active} into the tree.",
            f"The tree now has {len(selected)} edge(s).",
        ], facts
    if pos == "last":
        return "terminate", [
            f"Add the final edge {a}–{b}, bringing {active} in.",
            f"The tree is complete: {len(selected)} edges connect all {len(output)} nodes.",
        ], facts
    return "visit_complete", [
        f"Add edge {a}–{b}, connecting {active} to the growing tree.",
        f"The tree now spans {len(output)} nodes with {len(selected)} edges.",
    ], facts


def _grid(after: dict, prev: Optional[dict], pos: str, fixture: CanonicalFixture, caption: str = "") -> tuple[str, list[str], list[str]]:
    cell = after.get("active_cell")
    values = after.get("cell_values") or {}
    arrows = after.get("dependency_arrows") or []
    key = ",".join(str(c) for c in (cell or []))
    value = values.get(key)
    facts = [f"cell={cell}", f"value={value}", f"caption={caption}"]

    deps = [a for a in arrows if list(a.get("to") or []) == list(cell or [])]
    dep_parts = []
    for a in deps:
        src = list(a.get("from") or [])
        src_val = values.get(",".join(str(c) for c in src))
        dep_parts.append((src, src_val))
        facts.append(f"dep({src[0]},{src[1]})={src_val}")

    # unique_paths keeps its bespoke narration; other DP apps narrate via the
    # simulator's own per-step caption (computed, never asserted).
    if fixture.application != "unique_paths":
        bullets = [f"Select cell {cell[1] if cell else '?'} of the strip." if (cell and cell[0] == 0 and len(values) > 0) else f"Select cell ({cell[0]}, {cell[1]})."]
        if caption:
            bullets.append(caption)
        if pos == "last":
            bullets.append(f"This is the final cell — the answer: {value}.")
            return "read_final_answer", bullets, facts
        return "write_cell", bullets, facts

    if cell and (cell[0] == 0 or cell[1] == 0) and not dep_parts:
        return "initialize_base_case", [
            f"Select cell ({cell[0]}, {cell[1]}) — it sits on the top or left edge.",
            f"Only ONE path can reach an edge cell (straight along the edge), so its value is {value}.",
        ], facts

    bullets = [f"Select cell ({cell[0]}, {cell[1]})."]
    if dep_parts:
        terms = " + ".join(str(v) for _, v in dep_parts)
        srcs = " and ".join(f"({s[0]}, {s[1]}) = {v}" for s, v in dep_parts)
        bullets.append(f"Paths arrive only from above and from the left: {srcs}.")
        bullets.append(f"So this cell = {terms} = {value}.")
    else:
        bullets.append(f"Apply the recurrence to fill it: {value}.")
    if pos == "last":
        bullets.append(f"This is the bottom-right cell — the answer: {value} distinct paths.")
        return "read_final_answer", bullets, facts
    return "write_cell", bullets, facts


def _code(after: dict, prev: Optional[dict], pos: str, fixture: CanonicalFixture) -> tuple[str, list[str], list[str]]:
    arr, target = _arr(fixture), _target(fixture)
    line = (after.get("highlight_lines") or [None])[0]
    variables = after.get("variables") or {}
    output = list(after.get("output") or [])
    prev_vars = (prev or {}).get("variables") or {}
    changed = {k: v for k, v in variables.items() if prev_vars.get(k) != v and k not in ("arr",)}
    facts = [f"line={line}", f"target={target}", f"array_len={len(arr)}"] + [f"{k}={v}" for k, v in changed.items()]

    mid = variables.get("mid")
    if mid is not None and isinstance(mid, int):
        # Iteration cards land on the BRANCH line (the if/elif/else action), where
        # this probe's own bounds and mid are all live in the variables panel.
        low, high = variables.get("low"), variables.get("high")
        value = arr[mid] if 0 <= mid < len(arr) else None
        facts += [f"low={low}", f"high={high}", f"mid=({low}+{high})//2={mid}", f"arr[{mid}]={value}", f"line={line}"]
        bullets = [
            f"The while condition holds ({low} (low) <= {high} (high)), so the loop runs another iteration.",
            f"Compute the middle: mid = ({low} (low) + {high} (high)) // 2 = {mid}.",
        ]
        word = _cmp_word(value, target)
        bullets.append(f"Compare arr[{mid}] = {value} with target {target}: {value} {word} {target}.")
        if value == target:
            bullets.append(f"They match — line {line} runs: return mid. The function returns {mid}, the target's index.")
            facts.append(f"return={mid}")
            return "produce_output", bullets, facts
        try:
            goes_right = value is not None and value < target
        except TypeError:
            goes_right = False
        if goes_right:
            bullets.append(f"The elif branch runs (line {line}): low = mid + 1 = {mid + 1} — the left half is discarded.")
            facts.append(f"new_low={mid + 1}")
        else:
            bullets.append(f"The else branch runs (line {line}): high = mid - 1 = {mid - 1} — the right half is discarded.")
            facts.append(f"new_high={mid - 1}")
        return "evaluate_condition", bullets, facts

    # Linear scan (an index variable walks the array): check, decide, move on.
    idx = variables.get("i")
    if isinstance(idx, int) and "i" in changed and target is not None:
        value = arr[idx] if 0 <= idx < len(arr) else None
        facts += [f"i={idx}", f"arr[{idx}]={value}"]
        if value == target:
            facts.append(f"return={idx}")
            return "produce_output", [
                f"Check arr[{idx}] = {value}: it EQUALS the target {target}.",
                f"Line {line} runs: return i — the function returns {idx}, the first match.",
            ], facts
        return "make_comparison", [
            f"Check arr[{idx}] = {value}: not the target {target}.",
            "Move on to the next index — every element gets the same test.",
        ], facts

    # Accumulator algorithms (recursion / queue loops): one milestone per value the
    # output gains — narrate the visit, the working state, and the running output.
    prev_out = list((prev or {}).get("output") or [])
    if len(output) > len(prev_out):
        new_items = output[len(prev_out):]
        shown = ", ".join(repr(v) for v in new_items)
        bullets = [f"Visit {shown} — it is appended to the output."]
        call_stack = list(after.get("call_stack") or [])
        if len(call_stack) > 1:
            bullets.append(f"The call stack is {len(call_stack)} deep: {' > '.join(call_stack[-4:])}.")
        queue = variables.get("queue")
        if isinstance(queue, list):
            bullets.append(f"The queue now holds {queue}.")
        bullets.append(f"Output so far: {output}.")
        facts += [f"new={shown}", f"output={output}", f"stack_depth={len(call_stack)}", f"queue={queue}"]
        return "produce_output", bullets, facts

    if pos == "last" and output:
        facts.append(f"return={output}")
        return "produce_output", [
            f"Line {line} runs: return — the function returns {output}.",
        ], facts

    # Setup lines before the loop. The frame shows state arriving at `line`, so the
    # CHANGED variable is what the previous line just set.
    if "high" in changed:
        return "update_variable", [
            f"high = {changed['high']} is set — the index of the last element.",
            f"The search range [{variables.get('low', 0)}, {changed['high']}] now spans the whole array; line {line} begins the loop.",
        ], facts
    if "low" in changed:
        return "update_variable", [
            f"low = {changed['low']} is set — the left end of the search range.",
            f"Next, line {line} computes the right end: high = len(arr) - 1.",
        ], facts
    if changed:
        pairs = ", ".join(f"{k} = {v}" for k, v in changed.items())
        return "update_variable", [f"{pairs} is set; execution continues at line {line}."], facts
    return "execute_line", [f"Line {line} executes."], facts


# Only unambiguous code syntax — plain words like "for"/"while"/"return" appear in
# normal English prose ("looking for the target") and must not be banned.
def _symbolic(after: dict, prev: Optional[dict], pos: str, fixture: CanonicalFixture) -> tuple[str, list[str], list[str]]:
    substituted = after.get("substituted")
    computations = list(after.get("computations") or [])
    result = after.get("result")
    prev_n = len((prev or {}).get("computations") or [])
    facts = [f"substituted={substituted}", f"result={result}"] + [f"{c['label']}: {c['calc']}" for c in computations]

    if result is not None:
        return "state_result", [
            f"All the pieces are computed — the solution: {result}.",
            "Check: substituting either root back into the equation makes it balance.",
        ], facts
    if computations and len(computations) > prev_n:
        latest = computations[-1]
        return "apply_rule", [
            f"{latest['label']}: {latest['calc']}.",
        ], facts
    if substituted and not computations:
        params = ", ".join(f"{k} = {v}" for k, v in fixture.input.items())
        return "substitute", [
            f"Substitute the coefficients ({params}) into the formula:",
            f"{substituted}.",
            "Now evaluate it piece by piece, innermost first.",
        ], facts
    return "state_expression", ["The derivation begins from the formula."], facts


def _caption(after: dict, pos: str, caption: str) -> tuple[str, list[str], list[str]]:
    """For reveal-based concept visuals (set/coordinate/memory/timeline/geometric):
    the simulator's step caption IS the grounded teaching sentence."""
    role = "setup" if pos == "first" else ("conclude" if pos == "last" else "step")
    return role, [caption], [caption]


def _proof(after: dict, prev: Optional[dict], pos: str, caption: str) -> tuple[str, list[str], list[str]]:
    substituted = after.get("substituted")
    computations = list(after.get("computations") or [])
    result = after.get("result")
    prev_n = len((prev or {}).get("computations") or [])
    facts = [str(substituted), str(result), caption] + [c["calc"] for c in computations]
    if result is not None:
        return "conclude", [str(result), caption], facts
    if computations and len(computations) > prev_n:
        latest = computations[-1]
        return "derive_step", [f"{latest['label']}: {latest['calc']}"], facts
    if substituted:
        return "state_claim", [str(substituted), caption], facts
    return "state_claim", [caption], facts


_CAPTION_TYPES = frozenset({
    "set_logic_region_reasoning", "coordinate_plot_analysis", "memory_reference_trace",
    "timeline_interaction_trace", "geometric_spatial_construction", "case_comparison_example",
})

_NON_CODE_FORBIDDEN = ("def ", "elif ", "():")


def build_prose_slots(result: dict[str, Any], milestones: list[int], fixture: CanonicalFixture) -> list[ProseSlot]:
    """One grounded, delta-focused ProseSlot per milestone frame (spec §4.1)."""
    frames = result.get("frames") or []
    trace_steps = list((result.get("trace") or {}).get("steps") or [])
    etype = fixture.example_type
    slots: list[ProseSlot] = []
    prev_after: Optional[dict] = None
    for n, fi in enumerate(milestones):
        if fi >= len(frames):
            continue
        after = frames[fi].get("state_after") or {}
        diff = frames[fi].get("diff") or {}
        caption = str((trace_steps[fi] if fi < len(trace_steps) else {}).get("learner_should_notice") or "")
        pos = "first" if n == 0 else ("last" if n == len(milestones) - 1 else "mid")
        if etype == "sequence_state_trace":
            role, bullets, facts = _seq(after, prev_after, pos, fixture)
        elif etype == "node_link_trace":
            role, bullets, facts = _node(after, prev_after, pos, diff)
        elif etype == "grid_table_trace":
            role, bullets, facts = _grid(after, prev_after, pos, fixture, caption)
        elif etype == "code_execution_trace":
            role, bullets, facts = _code(after, prev_after, pos, fixture)
        elif etype == "symbolic_derivation":
            role, bullets, facts = _symbolic(after, prev_after, pos, fixture)
        elif etype == "proof_reasoning_chain":
            role, bullets, facts = _proof(after, prev_after, pos, caption)
        elif etype in _CAPTION_TYPES:
            role, bullets, facts = _caption(after, pos, caption)
        else:
            role, bullets, facts = "step", [f"Step {n + 1}."], []
        forbidden = () if etype == "code_execution_trace" else _NON_CODE_FORBIDDEN
        slots.append(ProseSlot(
            slot_id=f"{fixture.fixture_id}:{n}",
            frame_index=fi,
            step_role=role,
            previous_frame_summary="",
            current_frame_delta=" ".join(bullets),
            bullets=tuple(bullets),
            allowed_facts=tuple(facts),
            required_mentions=(),
            forbidden_mentions=tuple(forbidden),
        ))
        prev_after = after
    return slots


# --- the generators + validator -------------------------------------------------

def deterministic_points(slot: ProseSlot) -> list[str]:
    """In-sync by construction: the broken-down reasoning moves, one per bullet."""
    return list(slot.bullets)


_NUM = re.compile(r"-?\d+")


def validate_points(slot: ProseSlot, points: list[str]) -> list[str]:
    """ProseValidator (spec §5.3 #4): no forbidden mentions; every number that appears
    must be grounded in allowed_facts or the deterministic bullets."""
    errors: list[str] = []
    text = " ".join(points)
    low = text.lower()
    for term in slot.forbidden_mentions:
        if term.strip() and term.lower() in low:
            errors.append(f"forbidden mention {term!r}")
    grounded = " ".join(slot.allowed_facts) + " " + " ".join(slot.bullets)
    allowed_nums = set(_NUM.findall(grounded))
    for num in _NUM.findall(text):
        if num not in allowed_nums:
            errors.append(f"ungrounded number {num!r} (not in allowed_facts)")
    return errors


_WORD = re.compile(r"\b\w+\b")


def validate_prose_sync(points: list[str], after_state: dict, node_ids) -> list[str]:
    """INV-PROSE-SYNC (PROJECTOR_SYSTEM_SPEC §6.4): a bullet may not cite a graph node
    absent from THIS frame's live state — active + visited + frontier + selected-edge
    endpoints. Grounds the prose to the same projected frame the visual shows."""
    live: set[str] = set()
    if after_state.get("active"):
        live.add(str(after_state["active"]))
    live |= {str(x) for x in (after_state.get("visited") or [])}
    live |= {str(x) for x in ((after_state.get("frontier") or {}).get("items") or [])}
    for e in (after_state.get("selected_edges") or []):
        if len(e) >= 2:
            live |= {str(e[0]), str(e[1])}
    ids = {str(n) for n in node_ids}
    errors: list[str] = []
    for point in points:
        for token in _WORD.findall(str(point)):
            if token in ids and token not in live:
                errors.append(f"INV-PROSE-SYNC: bullet cites node {token!r} absent from this frame")
    return list(dict.fromkeys(errors))


def fill_slots(
    slots: list[ProseSlot],
    generator: Optional[Callable[[ProseSlot], list[str]]] = None,
) -> list[list[str]]:
    """Fill each slot, validating the output; fall back to deterministic prose on any
    validation failure (so a card is never empty or ungrounded — spec §6.5)."""
    gen = generator or deterministic_points
    out: list[list[str]] = []
    for slot in slots:
        points = gen(slot)
        if not points or validate_points(slot, points):
            points = deterministic_points(slot)
        out.append(points)
    return out
