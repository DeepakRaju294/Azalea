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
_DECISION_CMP = re.compile(r"(<=|>=|==|<|>)")

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
    "continue": "skip to the next node on the stack",
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

    # --- GRAPH TRAVERSAL (BFS/DFS) — checked first, before the sort templates. Node labels (not ints); the
    # settrace snapshot is BEFORE the line runs, so the just-popped node comes from the verified step ("visit X"),
    # and neighbour writes are aggregated over the inner loop. ---
    if any(k in code for k in ("graph[", "visited", "queue", "stack", "popleft",
                               "node", "neighbor", "order", "frontier")):
        node = None
        mnode = re.match(r"visit\s+(\w+)", str(getattr(step, "decision", "") or ""))
        if mnode:
            node = mnode.group(1)
        nbrs = list(dict.fromkeys(s.get("neighbor") for s in snaps if s.get("neighbor") is not None))
        if ".popleft()" in code:
            return f"take {node} from the front of the queue" if node else "take the next node from the queue"
        if re.match(r"^\w+\s*=\s*\w+\.pop\(\)$", code):
            return f"take {node} off the top of the stack" if node else "take the next node off the stack"
        if re.match(r"^\w+\.append\(\s*node\s*\)$", code):                    # order.append(node)
            return f"visit {node} — record it in the output order" if node else "record this node as visited"
        if _LOOP.match(code) and "graph[" in code:                           # for neighbor in graph[node]:
            return f"look at each neighbour of {node}" if node else "look at each neighbour of this node"
        if code.startswith("while "):                                        # while queue: / while stack:
            return "keep going while there are still nodes waiting to be explored"
        if code.startswith("if ") and "not in visited" in code:
            return "for each neighbour, act only on the ones NOT visited yet"
        if code.startswith("if ") and "in visited" in code:                  # if node in visited: (dup skip)
            return "if this node was already visited, skip it — a stale duplicate left on the stack"
        if re.match(r"^visited\.(add|append)\(\s*node\s*\)", code):          # visited.add(node) — the popped node
            return f"mark {node} visited" if node else "mark the current node visited"
        if re.match(r"^visited\.(add|append)\(", code):                      # visited.add(neighbor) — aggregate
            return f"mark {', '.join(map(str, nbrs))} visited" if nbrs else "mark this neighbour visited"
        if re.match(r"^(queue|stack|frontier)\.append\(", code):
            dest = code.split(".", 1)[0]
            return f"add {', '.join(map(str, nbrs))} to the {dest}" if nbrs else f"add this neighbour to the {dest}"
        if re.match(r"^visited\s*=\s*set\(\)\s*$", code):                    # visited = set() (mark-on-pop)
            return "start with nothing marked visited yet"
        if re.match(r"^visited\s*=\s*\{", code):                             # visited = {start}
            return "mark the start node as already visited"
        if re.match(r"^(order|result)\s*=\s*\[\]$", code):
            return "the output order starts empty"
        if re.match(r"^(queue|stack)\s*=\s*(deque\()?\[", code):
            return "seed the frontier with the start node"

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

    # A comparison INSIDE a loop runs once per iteration — summarize the loop's OUTCOME from the verified
    # step, don't replay one snapshot ("arr[0]=3"). Polish item: loop-body comparison summary.
    if code.startswith("if ") and "[" in code and _DECISION_CMP.search(code):
        if "pivot" in inp:
            sm = inp.get("smaller") or []
            return (f"values below the pivot {inp['pivot']} ({', '.join(map(str, sm))}) move to the left"
                    if sm else f"no value in this slice is below the pivot {inp['pivot']}")
        if step.operation == "select":
            parts = str(getattr(step, "decision", "")).split()          # "select X into position Y"
            return f"keep the smallest seen so far — it turns out to be {parts[1] if len(parts) > 1 else 'the minimum'}"
        if "left" in code and "right" in code:                          # merge front-of-run compare
            return "compare the two front values and emit the smaller one"
        if step.operation in ("bubble", "sweep") or "bubble" in str(getattr(step, "decision", "")):
            return "swap this adjacent pair only when the left value is the larger"

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
        if (_SWAP.match(code) or _SHIFT.match(code) or _APPEND.match(code)
                or re.match(r"^\w+\[[^\]]+\]\s*=", code)                        # arr[i] = …
                or re.match(r"^\w+\.(append|add|push|extend)\(", code)):        # queue.append / visited.add …
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


def _collapse_repeated_structure(cards: list) -> list:
    """Polish item: after a loop has been shown IN FULL once, later cards that re-run it should not repeat the
    unchanged bookkeeping. A work line whose // annotation is IDENTICAL to the first time that code line
    appeared is structural (min_idx = i, i = lo, for j …) and is dropped on repeat; a line whose annotation
    CHANGED carries this step's decision/values and is kept. Never drops a card's only content, and the FIRST
    occurrence of every line stays — so the decision loop is always shown in full once (CP9 non-omission)."""
    seen: dict = {}
    for c in cards:
        kept_w, kept_cl, dropped = [], [], False
        for w, cl in zip(c.get("work") or [], c.get("code_lines") or [[]] * len(c.get("work") or [])):
            code, _, ann = str(w).partition("//")
            code, ann = code.strip(), ann.strip()
            if code not in seen:
                seen[code] = ann
                kept_w.append(w); kept_cl.append(cl)
            elif ann != seen[code]:                                       # value/decision line — keep
                kept_w.append(w); kept_cl.append(cl)
            else:                                                         # unchanged bookkeeping — drop on repeat
                dropped = True
        if kept_w and dropped:
            kept_w = ["…the loop runs as shown above; this round:"] + kept_w
            kept_cl = [[]] + kept_cl
        if kept_w:
            c["work"], c["code_lines"] = kept_w, kept_cl
    return cards


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
    # Language guard: this path annotates the EXECUTED (Python) canonical and anchors each work line to the
    # DISPLAYED code by exact stripped-text match. When the display is a translation (java/cpp), no executed
    # line matches any displayed line, so `line_map` is empty — every `code_lines` would be `[]`, an
    # unrenderable card with no anchors. An empty map means the display isn't the Python we ran: defer to the
    # LLM path, which translates faithfully. (A real Python display always matches its own body lines.)
    if not line_map:
        return None
    out = []
    for card, (a, b), step in zip(base_cards, regions, getattr(trace, "steps", [])):
        work, code_lines = _work_from_slice(exec_steps[a:b + 1], exec_lines, step, line_map)
        if not work:
            return None                                                      # empty slice -> don't ship a blank card
        out.append({**card, "work": work, "code_lines": code_lines})
    # Content-quality backstop: a weak fallback annotation means this code shape isn't fully templated — don't
    # ship robotic content, fall back to the LLM (defends future whitelist additions, not just the current set).
    if any("carry out this step" in w for c in out for w in (c.get("work") or [])):
        return None
    return _collapse_repeated_structure(out)
