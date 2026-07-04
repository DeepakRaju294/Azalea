"""CP10 — deterministic coding-walkthrough generation (WORKED_EXAMPLE_ACCURACY_SPEC §18.4).

The coding topic's cards are generated from the EXECUTED REFERENCE, not the LLM: for each trace step we take
its slice of the real run (`map_step_regions`), show the source lines that actually ran, and annotate each
with values read from the real `vars`. So the min-scan is shown *and* correct by construction — no omission
(CP9 core-decision nudge) and no wrong value / inverted comparison (CP9 per-adapter guards) is possible.

Scope: the array sorts + search whose execution maps cleanly (`provides_narration` + `map_step_regions`
returns a mapping); anything else returns None and the caller keeps the LLM path. Title/reason/result come
from the already-correct deterministic narration; this module only authors the code `work` + `code_lines`.
"""
from __future__ import annotations

import re
from collections import OrderedDict
from typing import Any, Optional

from .code_execution_check import _execute_on_instance, map_step_regions

# line shapes we annotate readably; anything else falls back to naming the concrete subscript values
_SWAP = re.compile(r"^(\w+)\[([^\]]+)\]\s*,\s*(\w+)\[([^\]]+)\]\s*=\s*\w+\[[^\]]+\]\s*,\s*\w+\[[^\]]+\]$")
_ASSIGN_SUB = re.compile(r"^(\w+)\s*=\s*(\w+)\s*\[\s*([^\]]+?)\s*\]$")          # key = arr[i]
_SHIFT = re.compile(r"^(\w+)\[([^\]]+)\]\s*=\s*(\w+)\[([^\]]+)\]$")            # arr[j+1] = arr[j]
_PLACE = re.compile(r"^(\w+)\[\s*([^\]]+?)\s*\]\s*=\s*(\w+)$")                 # arr[j+1] = key
_APPEND = re.compile(r"^(\w+)\.append\(\s*(\w+)\s*\[\s*([^\]]+?)\s*\]\s*\)$")  # merged.append(left[i])
_LOOP = re.compile(r"^(for|while)\b.*:$")
_COMMENT = re.compile(r"\s*#.*$")

# short bookkeeping lines with no data subscript — normalized (spaces removed) -> a plain-English note
_BOOKKEEP = {
    "min_idx=i": "assume position i holds the smallest for now",
    "min_idx=j": "j is smaller — make it the new running minimum",
    "i=lo": "start the boundary at the slice's left end",
    "j=i-1": "start comparing just left of the new element",
    "j-=1": "keep walking left",
    "j+=1": "keep walking right",
    "i+=1": "extend the boundary of placed values",
    "swapped=True": "record that a swap happened this pass",
    "swapped=False": "assume the pass makes no swaps until one does",
    "left=runs.popleft()": "take the next run as the left input",
    "right=runs.popleft()": "take the next run as the right input",
    "merged=[]": "start an empty merged run",
    "i=j=0": "two read cursors, one per input run",
    "runs=deque([x]forxinarr)": "each element starts as its own length-1 sorted run",
    "break": "stop early — the array is already sorted",
}


def _index(expr: str, v: dict) -> Optional[int]:
    expr = expr.strip()
    m = re.fullmatch(r"(\w+)\s*([+-])\s*(\d+)", expr)
    if m:
        base = v.get(m.group(1))
        return None if not isinstance(base, int) else base + (int(m.group(3)) if m.group(2) == "+" else -int(m.group(3)))
    return int(expr) if expr.isdigit() else (v.get(expr) if isinstance(v.get(expr), int) else None)


def _read(name: str, idx: str, v: dict) -> Any:
    seq, i = v.get(name), _index(idx, v)
    return seq[i] if isinstance(seq, list) and isinstance(i, int) and 0 <= i < len(seq) else None


def _annotate(code: str, snaps: list, step: Any) -> str:
    """A readable, ALWAYS-correct comment for `code`, using the real `vars` snapshots at that line (and the
    verified trace step for the loop's outcome). `snaps` has one entry per execution of the line in the slice."""
    v0 = snaps[0]
    inp = getattr(step, "inputs", {}) or {}

    book = _BOOKKEEP.get(code.replace(" ", ""))                              # short bookkeeping lines
    if book:
        return book

    m = _PLACE.match(code)                                                    # arr[j+1] = key  (drop the value in)
    if m and not m.group(3).isdigit():
        val = v0.get(m.group(3))
        if isinstance(val, int):
            return f"drop {val} into its slot"

    m = _SWAP.match(code)                                                     # arr[i], arr[k] = arr[k], arr[i]
    if m:
        a, b = _read(m.group(1), m.group(2), v0), _read(m.group(3), m.group(4), v0)
        if a is not None and b is not None:
            return "already in place — this swap leaves the value untouched" if a == b else f"swap {a} and {b} into place"

    m = _ASSIGN_SUB.match(code)                                               # key = arr[i]
    if m:
        val = _read(m.group(2), m.group(3), v0)
        if val is not None:
            return f"{m.group(1)} = {val} (the value to place this round)"

    m = _APPEND.match(code)                                                   # merged.append(left[i])
    if m:
        vals = [_read(m.group(2), m.group(3), v) for v in snaps]
        vals = [x for x in vals if x is not None]
        if vals:
            return f"append {', '.join(map(str, vals))} to the merged run" if len(vals) > 1 else f"append {vals[0]} to the merged run"

    m = _SHIFT.match(code)                                                    # arr[j+1] = arr[j] (loop body)
    if m and m.group(1) == m.group(3):
        vals = [_read(m.group(3), m.group(4), v) for v in snaps]
        vals = [x for x in vals if x is not None]
        if vals:
            return f"shift {', '.join(map(str, vals))} one position right to open a slot"

    if _LOOP.match(code):                                                     # loop header — say what it scans
        is_while = code.startswith("while")
        if "pivot" in inp:
            return f"scan the slice, moving values below the pivot {inp['pivot']} to the left"
        if is_while:                                                          # insertion's INNER walk-left loop
            return (f"walk left through the sorted prefix while it is larger than {inp['key']}"
                    if "key" in inp else "walk left through the sorted prefix")
        if step.operation == "insert":                                       # the OUTER for-loop (not the while)
            return "take each element after the first and insert it into the sorted prefix"
        if step.operation == "select":
            return "scan the unsorted part for the smallest value"
        if step.operation in ("bubble", "sweep") or "bubble" in str(getattr(step, "decision", "")):
            return "sweep adjacent pairs left to right, swapping any that are out of order"
        return "scan the current range"

    # comparison / condition body pieces get the outcome from the verified step, not a per-iteration replay
    if code.startswith("if ") and step.operation == "select":
        return f"track the smallest seen so far — it is {inp.get('position') is not None and step.expected_visible_result.split()[1] or 'found'}"

    if code.startswith("return"):
        return "return the finished array"
    if code.startswith("if not swapped"):
        return "if this whole pass made no swaps, the array is already sorted"
    if code.startswith("if len(") and "<= 1" in code:
        return "a run of 0 or 1 element is already sorted — hand it back unchanged"
    if ".extend(" in code:
        side = "left" if "left" in code.split(".extend(", 1)[1] else "right"
        return f"copy whatever remains of the {side} run onto the end"
    if re.match(r"^\w+\.append\(\w+\)$", code):                              # runs.append(merged)
        return "put the finished merged run back among the runs"

    # fallback: name the concrete subscript values this line read (still always correct)
    reads = re.findall(r"(\w+)\s*\[\s*([^\]]+?)\s*\]", code)
    parts = [f"{n}[{_index(i, v0)}]={_read(n, i, v0)}" for n, i in reads if _read(n, i, v0) is not None]
    return ", ".join(parts) if parts else "carry out this step"


def _line_map(exec_src: str, display_code: str) -> dict:
    """Map EXECUTED-code line numbers → DISPLAYED-code line numbers. The display strips imports, so the code
    that ran (canonical, imports intact) has extra leading lines; the displayed body is a subsequence, aligned
    here by matching stripped text so a card's `code_lines` anchor points at the line the LEARNER sees."""
    disp = [l.strip() for l in (display_code or "").splitlines()]
    out, di = {}, 0
    for ei, line in enumerate(exec_src.splitlines(), 1):
        if di < len(disp) and line.strip() == disp[di]:
            out[ei] = di + 1
            di += 1
    return out


def _work_from_slice(events: list, exec_lines: list, step: Any, line_map: dict) -> tuple:
    """Distinct source lines that ran in this step's slice, in first-appearance order, each annotated. Trailing
    control-flow (the next iteration's loop re-check, `return`) after the step's last state change is dropped.
    Work text is the EXECUTED source; `code_lines` are mapped to the DISPLAYED code the learner sees."""
    per: "OrderedDict[int, list]" = OrderedDict()
    for ev in events:
        per.setdefault(ev["line"], []).append(ev.get("vars") or {})
    lines = [(ln, sn) for ln, sn in per.items() if 1 <= ln <= len(exec_lines)]
    # truncate after the last COMMIT (an assignment whose target is a subscript / a swap / an append)
    last_commit = -1
    for k, (ln, _snaps) in enumerate(lines):
        code = _COMMENT.sub("", exec_lines[ln - 1]).strip()
        if _SWAP.match(code) or _SHIFT.match(code) or _APPEND.match(code) or re.match(r"^\w+\[[^\]]+\]\s*=", code):
            last_commit = k
    if last_commit >= 0:
        lines = lines[:last_commit + 1]
    work, code_lines = [], []
    for ln, snaps in lines:
        code = _COMMENT.sub("", exec_lines[ln - 1]).strip()
        if not code:
            continue
        work.append(f"{code}  // {_annotate(code, snaps, step)}")
        code_lines.append([line_map[ln]] if ln in line_map else [])
    return work, code_lines


def generate_coding_cards(trace: Any, code: Optional[str], base_cards: list) -> Optional[list]:
    """Author each coding card's `work` + `code_lines` from the executed reference; reuse `base_cards`'
    (deterministic-narration) title/reason/result. None when the run can't be mapped — caller keeps the LLM."""
    if not code or not base_cards:
        return None
    run = _execute_on_instance(code, trace)
    if run is None:
        return None
    exec_steps, _, exec_src = run                                            # exec_src = the code that RAN
    regions = map_step_regions(exec_steps, trace)
    if regions is None or len(regions) != len(base_cards):
        return None
    exec_lines = exec_src.splitlines()
    line_map = _line_map(exec_src, code)                                      # runtime line -> displayed line
    out = []
    for card, (a, b), step in zip(base_cards, regions, getattr(trace, "steps", [])):
        work, code_lines = _work_from_slice(exec_steps[a:b + 1], exec_lines, step, line_map)
        if not work:
            return None                                                      # empty slice -> don't ship a blank card
        out.append({**card, "work": work, "code_lines": code_lines})
    return out
