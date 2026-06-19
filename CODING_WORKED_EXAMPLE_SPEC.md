# Coding Implementation Worked Example — Blueprint Spec

Status: Final draft (four review passes incorporated — ready to implement)
Scope: applies **only** when `topic_type == "coding_implementation"`. **Replaces** the current coding
worked-example path (the line-execution trace + the `_group_coding_steps` grouping hack). The base
worked-example contract (Goal / Reasoning / Work / Result) used by math, algorithm-walkthrough,
proof, and concept topics is **unchanged** — this is a specialization layer, not a second system.

---

## 1. Purpose

A coding implementation worked example solves the **same kind of high-level problem** any worked
example solves, and is divided into the **same natural problem-solving steps** a learner would write
by hand. The one difference: every card explains **how the CODE accomplishes that step** (the
mechanics), instead of **what happens** conceptually (which is what every other example type does).

This exists to fix the failure mode of the current path: tracing the code's *execution* line-by-line
produces ~80 cards for a 7-element merge sort (recursion + loops re-run the 18 lines dozens of times),
which is repetitive, degrades into filler, runs ~6 minutes, and doesn't finish.

## 2. Core principle — same division, code explanation

Two layers, cleanly separated:

1. **Division (shared with the base contract).** Split the example into the natural worked-example
   steps for the algorithm — the structural steps, not line-executions:
   - Binary search → **one card per pass** (compute mid → compare to target → adjust the bounds).
   - Merge sort → one card per **split**, **meaningful recursive descent**, **immediate base-case
     return**, **merge selection**, and **tail-copy phase** (never one opaque card for a whole merge —
     see §3).
   - BFS / DFS → one card per **visit / dequeue**.
   - Step count matches a normal worked example (binary search ~3–5; merge sort ~8–24 depending on
     input size — only larger inputs approach 30, and the setup-selection rule §7.1 prefers small
     ones), **never** the ~80 of a runtime trace.

2. **Explanation (coding-specific).** Within each step, the card explains the **code** that performs
   it — the lines that run, the condition evaluated, the slice/call/return, and the runtime state.

**The distinction from every other example type:**
- Other examples — the card says *what* happens: "27 < 43, so we search the right half."
- Coding — the card says *how the code does it*: "`nums[mid]` is 27; `nums[mid] < target` evaluates
  `27 < 43` → True, so `low = mid + 1` moves the window to indices 4–6."

## 3. Step granularity — one card per STRUCTURAL transition

**One card = one structural implementation transition** — the smallest code-level unit a learner
reasons about as a single move. The code lines of that transition go in the card's `work` (a list of
actions); we never make a card per assignment or per repeated line-execution, and we never collapse
multiple independent decisions into one card.

Each outline action declares a `kind`, which both defines the unit and drives the gate (§7):

| `kind` | one card covers… |
|--------|------------------|
| `pass` | one loop iteration **when it has a single central decision/update** (binary search: mid + compare + adjust). Split only if the iteration has multiple independent decisions or mutations. |
| `split` | one divide operation (compute mid, slice into two halves). |
| `recursive_call` | one recursive call that does **meaningful work after entering** (see §4). |
| `base_case` | a call that immediately reaches the terminating condition and returns — the call **and** its return in **one** card (never a separate "check base case" card; §4). |
| `merge_selection` | one selection phase of a merge: compare the fronts, choose, append, advance the pointer. A small merge (1–2 comparisons) may be one card; a larger merge splits into one card per selection. |
| `merge_tail` | copying a remaining (already-sorted) tail after one side empties. |
| `visit` | one traversal visit / dequeue / enqueue cycle. |
| `return_resume` | a return/resume event **when it changes what the parent frame can do** next. |
| `other` | anything not above (used sparingly). |

Forbidden granularities (the gate rejects these):
- **per-assignment** (`i = 0` / `j = 0` / `k = 0` as three cards) or **per-line-execution**
  (`if len(arr) > 1:` as its own card each time it runs) — i.e. a `kind` of `assignment` /
  `condition_check` / `line_execution` is not allowed.
- **coarse** — collapsing a whole sub-algorithm into one card ("sort the left half").
- **opaque merge** — collapsing a multi-comparison merge into one card; it must split into
  `merge_selection` / `merge_tail` phases.
- **over-split merge** — separate cards for compare, choose, append, and pointer-advance. Those four
  are **one** `merge_selection`.

**Card boundary rule (do not confuse `work` length with card count).** A card boundary is chosen by
**structural transition**, not by number of code actions. A single card may carry **3–6 `work`
actions** when they together implement one transition (the binary-search pass in §6 is one card with
five `work` lines). The gate validates **card-level** granularity (the `kind` and the count of cards),
**never** the number of `work` lines inside a card — enforcing "one work action = one card" would
recreate the 80-card explosion.

## 4. Recursion — each recursive call is its own card (explicit, for clarity)

Recursion is shown at the **call / split / base-case / merge level**, each as its own card, so the
learner sees the descent and the return clearly. The "which call we're in" / call-stack lives in
`result` (or `prior_state`) so depth is trackable.

**Call + immediate base case = one card.** Give a recursive call its own descent card only when the
call does meaningful work after entering (it splits and recurses further). When the call immediately
hits the base case (a single-element input), **combine the call and its base-case return into one
card** — `Recursively sort [27] → return [27]`. This rule is what stops recursion from re-exploding
into filler pairs of "entered call" / "hit base case" cards.

**What counts as "meaningful recursive work."** A `recursive_call` earns its own card only if the
called input has **size > base-case size** *and* the called frame will perform **at least one
structural action after entry** (split, recurse, loop, or merge). Otherwise it is a base case and folds
into one call+return card:
```
merge_sort([38, 27])  → meaningful recursive_call (it will split + recurse + merge)  → own card
merge_sort([38])      → call + base_case in one card
```

**`return_resume` is the filler trap — restrict it hard.** A `return_resume` card is allowed **only
when the return enables a new structural action** in the parent (e.g. both halves have returned, so the
parent can now merge them). It is **rejected** when its `result` only says "parent frame resumes" /
"return to the parent" without enabling that next action — in those cases the return folds into the
**`result`** of the previous card, not its own card.
```
GOOD (own card): "Left and right halves have both returned; the parent can now merge [27,38] and [3,43]."
BAD  (rejected): "Return to the parent frame."   → fold into the prior card's result instead.
```

**Anti-filler recursion rule (gate-enforced).** Never create a card whose only purpose is "enter
frame", "check base case", or "return to parent". Those details merge into the nearest meaningful
`recursive_call` / `base_case` / `merge_selection`, or into a `result` field.

Merge sort, `[38, 27, 43, 3]`:
```
Split [38, 27, 43, 3] into [38, 27] and [43, 3]        ← split card
Recursively sort the left half [38, 27]                ← the CALL (descent) — its own card
   Split [38, 27] into [38] and [27]                       ← split card
   Recursively sort [38] → len([38]) == 1 → return [38]    ← call + immediate base case (one card)
   Recursively sort [27] → len([27]) == 1 → return [27]    ← call + immediate base case (one card)
   Merge [38] and [27] → [27, 38]                          ← merge selection + tail-copy
Recursively sort the right half [43, 3]                ← the CALL — its own card
   … (split, calls, base cases, merge) …
Top-level merge [27, 38] and [3, 43] → splits into selection/tail-copy cards:
   compare 27 vs 3  → append 3                          ← merge_selection
   compare 27 vs 43 → append 27                         ← merge_selection
   compare 38 vs 43 → append 38                         ← merge_selection
   right exhausted  → copy remaining [43]               ← merge_tail
```
(A two-element merge like `[38]`+`[27]` is small enough to be one card; the top-level merge has several
comparisons, so it splits — never one opaque merge card. See §3.)

## 5. Card fields (specialized meaning)

| field | meaning for a coding implementation step |
|-------|------------------------------------------|
| `goal` | the structural step being accomplished, phrased as a normal example would ("First pass: examine the middle element", "Merge the two sorted halves"). |
| `reasoning` | which code construct implements this step and why (the condition / loop / slice / recursive call / return). |
| `work` | the code that runs **for this step** + its evaluation with actual values, as a list of lines (code/trace) — **not** prose. Each entry is one **action**. |
| `result` | the runtime state after this step: variables, pointers, call stack / current frame, branch taken, returned value, mutated structure. |

**Per-action code anchor (best-effort).** Each action (each entry in `work`) carries the line(s) in
the displayed code snippet it correlates to, stored as a parallel `code_lines` list in the step's
metadata (§9). An action may map to **one or several** source lines (a multi-line statement, or a
trace line like `27 < 43 → True` derived from a condition line), so each entry is a **list of 1-based
integers** — `[]` when there is no single source line. It stays cheap (just integers) and lets a later
UI highlight the right line(s) as each action is read. Treat the mapping as **best-effort**: line
numbers can drift if the snippet is reformatted and the model can miscount, so it is an aid for
highlighting, **not** a hard correctness dependency — a wrong/empty anchor degrades the highlight, it
never invalidates the example.

## 6. Worked example drafts

### Binary search — find `85` in `[2, 5, 8, 12, 17, 23, 31, 38, 44, 51, 60, 72, 85, 91, 99]` (4 passes)
Seeded to need ≥3 passes so it clears the minimum without padding (§7.1).
```
STEP 1 — First pass
  goal:      Examine the middle of the whole array.
  reasoning: The loop computes the midpoint, then the comparison decides which half to keep.
  work:      low = 0, high = 14            # code_lines [2]
             mid = (0 + 14) // 2 = 7       # code_lines [3]
             nums[7] = 38                  # code_lines [4]
             nums[mid] < target → 38 < 85 → True   # code_lines [4]
             low = mid + 1 = 8             # code_lines [5]
  result:    Left half discarded. Search window = indices 8–14.

STEP 2 — Second pass
  work:      mid = (8 + 14) // 2 = 11        # code_lines [3]
             nums[11] = 72                   # code_lines [4]
             nums[mid] < target → 72 < 85 → True   # code_lines [4]
             low = mid + 1 = 12             # code_lines [5]
  result:    Search window = indices 12–14.

STEP 3 — Third pass
  work:      mid = (12 + 14) // 2 = 13       # code_lines [3]
             nums[13] = 91                   # code_lines [4]
             nums[mid] < target → 91 < 85 → False  # code_lines [4]
             high = mid - 1 = 12            # code_lines [7]
  result:    Search window = index 12.

STEP 4 — Fourth pass
  goal:      Examine the middle of the one-element window.
  work:      mid = (12 + 12) // 2 = 12       # code_lines [3]
             nums[12] = 85                   # code_lines [4]
             nums[mid] == target → 85 == 85 → True  # code_lines [6]
  result:    Match found at index 12. Return 12.
```

### Merge sort — `[38, 27, 43, 3]` (abbreviated; see §4 for the full descent)
```
STEP — Split the array
  goal:      Divide the array into two halves to sort independently.
  reasoning: mid splits the list; the slices create the two recursive inputs.
  work:      mid = len([38, 27, 43, 3]) // 2 = 2
             L = arr[:mid] = [38, 27]
             R = arr[mid:] = [43, 3]
  result:    Two halves: L = [38, 27], R = [43, 3]. Recurse on L first.

STEP — Recursively sort the left half [38, 27]
  goal:      Sort the left half before merging.
  reasoning: merge_sort(L) is called; control descends into a new frame with arr = [38, 27].
  work:      merge_sort([38, 27])
  result:    Entered the call for [38, 27]; parent frame paused, waiting for its return.

STEP — Merge [38] and [27]
  goal:      Combine the two sorted single-element halves.
  reasoning: the while loop compares the fronts and appends the smaller, then copies the leftover tail.
  work:      i = 0, j = 0, merged = []
             L[i] = 38 vs R[j] = 27 → 38 > 27 → append R[j]
             merged = [27], j = 1
             R exhausted → copy remaining L[i:] = [38]
  result:    merged = [27, 38]; return to the parent frame for [38, 27].
```

## 7. Generation flow (what the solver does)

1. **Ensure code exists, then freeze it.** If the lean pass produced no code, generate the clean
   implementation (`generate_clean_code`) and hand the solver **that exact snippet**, so `code_lines`
   anchor to the same numbering the lesson displays. The snippet is **frozen** once anchoring begins:
   it must not be reformatted, regenerated, or line-wrapped afterward. If the code ever changes,
   discard the anchors and regenerate them — otherwise highlighting drifts.
2. **Outline call** (cheap): produce the problem + a **structural-step** plan. Each action declares
   `{kind, description, cases_covered}` (§3), in this shape:
   ```json
   {
     "problem": "Find 85 in [2, 5, 8, 12, 17, 23, 31, 38, 44, 51, 60, 72, 85, 91, 99]",
     "expected_final_answer": "index 12",
     "required_cases": ["midpoint_calculation", "lower_bound_update",
                        "upper_bound_update", "found_return"],
     "solution_plan": [
       {"kind": "pass",
        "description": "First pass: compute mid = 7, compare 38 < 85, update low to 8",
        "cases_covered": ["midpoint_calculation", "lower_bound_update"]}
     ]
   }
   ```
   The `problem` and `required_cases` must be for the **same** algorithm (here, binary search — not
   merge-sort cases). The plan is at the structural level, **never** line-executions.

   A recursive example shows how `recursive_call` / `split` / `base_case` look (abbreviated — not the
   full plan):
   ```json
   {
     "problem": "Sort [38, 27, 43, 3] with merge_sort",
     "expected_final_answer": "[3, 27, 38, 43]",
     "required_cases": ["split_with_slicing", "immediate_base_case_return",
                        "parent_receives_recursive_result", "merge_selection", "tail_copy"],
     "solution_plan": [
       {"kind": "split", "description": "Split [38, 27, 43, 3] into [38, 27] and [43, 3]",
        "cases_covered": ["split_with_slicing"]},
       {"kind": "recursive_call",
        "description": "Call merge_sort([38, 27]); the child frame will split and merge before returning",
        "cases_covered": []},
       {"kind": "split", "description": "Inside merge_sort([38, 27]), split into [38] and [27]",
        "cases_covered": ["split_with_slicing"]},
       {"kind": "base_case", "description": "Call merge_sort([38]); len([38]) <= 1, so return [38]",
        "cases_covered": ["immediate_base_case_return"]}
     ]
   }
   ```
3. **Gate the outline — HARD, before any card generation:**
   - **count within the topic's `[min, max]` range** (§7.1). **Over `max` is a hard rejection** — an
     over-limit plan is never sent to the expensive cards call (that is exactly the 80-card cost this
     blueprint removes).
   - **no line-level kinds** (`assignment` / `condition_check` / `line_execution`).
   - **no coarse action** ("sort the left half") and **no over-long `merge_selection`** bundling many
     comparisons.
   - **`other` is capped *and* must justify itself** — reject when `other_count > max(1, int(0.2 *
     len(plan)))`, and every `other` action must carry a short `reason` saying why no existing kind
     applies (so `other` is auditable, not a junk drawer). The model can't dodge the stricter kinds by
     labelling weak actions `other`.
   - **no duplicate-filler runs** — reject when **3+ consecutive cards share the same `kind` and
     near-identical descriptions** without a distinct concrete input / variable state / returned value.
     (`Recursively sort [38] → return [38]` then `… [27] → return [27]` is fine — distinct inputs;
     three identical "check if array length is 1" is not.)
   - **every `required_case` covered.**
   On failure, **regenerate the outline** (bounded retries). If it still fails, **abandon the solver
   result** and keep the fallback (§10) — never generate cards from a rejected plan.
   **The gate runs after every outline retry and again after any deterministic normalization/expansion
   of the plan.** No transformed plan may reach the cards call unless it passes this final gate — so a
   future normalization step can never silently push the count back over `max`.

   **Deterministic helpers (don't make the LLM self-police "coarse"/"opaque").** The gate is mostly
   string/enum checks; reserve LLM judgement for the genuinely fuzzy cases only:
   ```python
   LINE_LEVEL_KINDS = {"assignment", "condition_check", "line_execution"}   # hard reject by kind
   COARSE_PATTERNS  = ["sort the left half", "sort the right half", "merge the halves",
                       "process the array", "run the loop", "complete recursion"]
   FILLER_PATTERNS  = ["enter frame", "check base case", "return to parent", "parent resumes"]
   ```
   A `COARSE`/`FILLER` pattern match raises a **suspected** issue, not an automatic reject — a valid
   action can legitimately contain the phrase ("Recursively sort the left half [38, 27] **by entering a
   frame that splits into [38] and [27]**"). **Reject only if** the action *also* lacks a distinct
   concrete input / state *and* doesn't name the next structural operation. `LINE_LEVEL_KINDS` is the
   exception — a hard reject by kind, no confirmation needed.
4. **Cards call** (expensive): one Goal / Reasoning / Work / Result card per accepted action, each
   code-anchored per §5, carrying `work`, `result`, and best-effort `code_lines`.
5. **No `_group_coding_steps` pass** — there is no line-trace to group, because the outline never
   asked for one.

### 7.1 Structural-step ranges (per topic)

A single universal min/max fails across algorithms (binary search is short, merge sort is long), so the
gate reads a per-topic `[min, max]`, with a default for unlisted topics. **This table is the long-term
range model (paired with the input-size-aware merge-sort ranges below); for v1, use the safer flat
teaching defaults in §13 — notably `merge_sort: (8, 18)`, not `(12, 30)`.**

```python
CODING_STEP_RANGES = {           # long-term model — for v1 defaults see §13
    "binary_search": (3, 6),
    "merge_sort": (12, 30),     # paired with the input-size-aware ranges below; v1 uses (8, 18)
    "dfs": (5, 12),
    "bfs": (5, 12),
    "linked_list_operation": (4, 10),
    "dynamic_programming": (8, 20),
    "default": (5, 25),
}
```

**`max` is a ceiling, not a target.** The model must not treat the upper bound as the goal — it should
emit the *natural* number of structural steps and is only rejected for exceeding `max`.

**Input-size-aware ranges** for algorithms whose step count scales with input (recursion/divide-and-
conquer), so a flat `(12, 30)` doesn't let a 7-element merge sort drift toward 30:
```python
merge_sort:  n <= 4 → (8, 16);  n <= 7 → (14, 24);  n <= 10 → (18, 30)
```

**Setup-selection rule (choose input size *before* resolving the range).** The setup generator picks
the **smallest concrete input that still covers the topic's required cases**, *then* the range is
resolved from that size — never generate an input, outline it, and retroactively pick a range. For
merge sort prefer **n = 4 or 5** unless the lesson specifically needs more; this keeps the example
educational instead of exhaustive, and avoids the gate rejecting a 28-card 7-element plan that a
4-element input would have taught better.

Not every topic needs an entry on day one — the `default` covers the rest — but the table prevents one
universal bound from breaking across algorithms. Iterative searches should additionally be **seeded
with an input/target that needs ≥3 passes** (e.g. a 15-element array, target mid-deep) so they clear
the minimum naturally instead of padding.

**Range resolution** (topics are titled inconsistently — "Merge Sort Implementation", "Implement
merge_sort", "Sorting with recursion"): resolve the range by **normalized topic slug first, then a
title keyword match, then `default`**. This keeps merge sort from silently falling into `(5, 25)` when
it should use `(12, 30)`.

### 7.2 `required_cases` must stay minimal and structural

`required_cases` are the **minimum essential implementation behaviors — usually 3–6 items**, never
every branch / assignment / line-level event. Unbounded required cases are themselves a card-explosion
source (each forces a step), so the outline gate **rejects a list longer than ~6** or one containing
line-level entries.

**Supply them deterministically by topic, don't let the model invent them.** Define the required cases
up front keyed by topic slug; the model's only job is to map plan actions to them (via
`cases_covered`). This is safer than asking the model to produce both the cases *and* the plan.

```python
REQUIRED_CASES_BY_TOPIC = {
    "binary_search": ["midpoint_calculation", "lower_bound_update",
                      "upper_bound_update", "found_return"],   # focus on the mutation, not the comparison category
    "merge_sort":    ["split_with_slicing", "immediate_base_case_return",
                      "parent_receives_recursive_result",   # coverable inside a base-case/call/merge result — NOT a standalone return_resume card
                      "merge_selection", "tail_copy"],
    "bfs":           ["queue_dequeue", "visited_mark", "neighbor_iteration", "enqueue_unvisited"],
    "dfs":           ["stack_or_recursive_visit", "visited_mark", "neighbor_order",
                      "backtrack_or_stack_update"],
}
```
For an unlisted topic, the model may propose a minimal list (still capped at ~6, still structural —
the line-level list below is rejected):
```python
# bad (line-level — rejected): ["compute mid at top level", "compute mid in left call",
#                               "compare first pair", "increment i", "increment j", ...]
```

## 8. Validation contract (coding branch)

**Three distinct failure tiers — don't conflate them** (the "diagnostic, never raises" rule below
applies *only* to the third):
1. **Generation-gate failures (§7)** — block card generation (regenerate the outline, then fall back).
2. **Schema-invariant failures (§9)** — block *rendering* of a malformed card / trigger fallback. A card
   missing `work` or `result` must never reach the UI.
3. **Quality-validation failures (this section)** — **telemetry-first, never raise.** They stamp
   `example_status` and only trigger a re-solve when the backstop is enabled; they never block a
   structurally valid card.

The quality checks (tier 3), in addition to the shared checks (setup, completeness, coverage, finished):
- `missing_code_mechanics` — a step whose `work` is prose with no code / trace.
- `algorithmic_not_implementation` — a step that could appear unchanged in the algorithm walkthrough
  (no code, no runtime values).
- `coding_step_below_mechanics_floor` — the operational quality floor. Every coding card must include
  **at least one code-mechanics signal AND at least one runtime-state signal** (requiring "any 2 of 6"
  is too permissive — "the list is now [27, 38]" would slip through on two runtime signals with no
  code). The detector is simple text/metadata matching — no semantic classifier needed:
  | group | signal — detect by |
  |-------|--------------------|
  | **code-mechanics** (≥1) | source-code expression/call (`()` `[]` `=` or a keyword `return`/`if`/`while`/`for`/`append`/`pop`/`mid` …); branch outcome (`True`/`False`/"branch taken"); variable/pointer update (`x = value`, `x: old → new`); `return …` |
  | **runtime-state** (≥1) | concrete runtime value (number, list/set literal, string, boolean); updated variable/pointer *value*; return value; call/frame state ("parent paused" / "frame receives" / "call returns") |
  ```
  REJECT: "The algorithm searches the right half because the target is larger."  (no code signal)
  REJECT: "The list is now [27, 38]."                                            (runtime only, no code)
  ACCEPT: "nums[mid] < target → 38 < 85 → True, so low = mid + 1 sets low to 8." (code: expr/branch/update + runtime: 38,85,8)
  ```
- `missing_runtime_state` — **checks the `result` field first.** Flag when `result` doesn't state the
  concrete state after the step (vars / pointers / return / branch taken) **even if `work` contains
  runtime values** — `work: …low = 8` with `result: "Continue searching."` is still flagged, because the
  visible post-step state is vague. This preserves the purpose of the `result` field.
- `runtime_trace_explosion` — step count exceeds the topic's `max` (§7.1). **Primarily enforced as the
  hard gate on the outline (§7, step 3) before card generation;** this telemetry entry only records the
  case where an over-limit plan slips through — the plan should never reach the cards call over-limit.
- `code_line_anchor_missing` — `code_lines` absent or `len(code_lines) != len(work)`. **Soft /
  telemetry only** — the anchor is best-effort (§5), so this never blocks or invalidates the example;
  it just flags that highlighting will degrade.

These flag into `example_status` (telemetry). Re-solve on them only if the backstop is enabled.

## 9. Metadata (coding-only, lightweight — required first)

```python
metadata = {
    "prior_state": {...},          # required where meaningful
    "cases_covered": [...],        # required
    "code_lines": [[int, ...], ...],  # best-effort: one entry per `work` action, each a list of
                                      #   1-based source-line numbers it correlates to ([] if none).
                                      #   len(code_lines) == len(work).
    "runtime_state": {...},        # optional: variables / call stack / branch / return after the step
}
```
The visible `work` (code) and `result` (runtime state) carry the substance. `code_lines` is the cheap
best-effort per-action anchor (§5) that ties each action to its source line(s) for later highlighting;
the structured `runtime_state` object is optional and may be deferred until a visual layer needs it.

**Card-level schema invariant** (cheap structural guard so malformed cards never reach the UI — not a
quality judgement):
- `len(work) >= 1` and `result` is non-empty. (These two are the only **render-blocking** invariants —
  a card failing them triggers fallback, tier 2 in §8.)
- `code_lines`: if **absent**, log `code_line_anchor_missing` (soft) and render without highlighting. If
  **present but mismatched** (`len(code_lines) != len(work)`), **discard `code_lines` for that card**,
  log `code_line_anchor_missing`, and still render the card (no highlighting). A bad anchor never
  blocks rendering or crashes the UI — anchors are useful, not correctness-critical.
- `cases_covered` is non-empty for at least the cards that satisfy a `required_case`.

## 10. What this replaces

- The current `_CODING_SYSTEM` line-execution framing ("walk the execution… one runtime move").
- The `_CODING_OUTLINE_SYSTEM` line-level outline.
- The `_group_coding_steps` deterministic grouping pass (no longer needed).

The base contract, the non-coding solver path, and the math/algorithm/concept examples are untouched.

**Fallback on failure.** When the structural coding solver fails (the outline can't pass the gate
within retries, or the cards call errors), fall back to the **base worked example** or leave the
existing cards unchanged. The old line-execution trace / `_group_coding_steps` path is **deleted, not a
fallback** — it must never reappear as the failure path, or the 80-card mode returns. When fallback is
used for a `coding_implementation` topic, record **both the status and the specific failure reason** so
telemetry shows *why* the structural solver failed (outline vs. gate vs. cards call), not just that it
did:
```python
example_status = {"status": "coding_fallback_used",
                  "reason": "outline_over_max" | "missing_required_cases" |
                            "duplicate_filler" | "cards_call_error" | ...}
```

## 11. Required vs deferred

**Required now:** the structural-step outline + gate; the code-anchored card contract; **basic coding
validation telemetry** (e.g. `missing_code_mechanics`, `missing_runtime_state`) + the render-blocking
schema invariant; ensure-code-exists (already done); the per-action `code_lines` anchor (§5/§9). To be
precise about the apparent "required but never invalidates" tension: **the solver must attempt to emit
`code_lines` for every `work` action** (it's captured at generation time because deriving it later is
far costlier); **validation records missing/mismatched anchors but never fails the example for anchors
alone.** Required to *produce*, soft to *validate*.

**Deferred:** the full two-group `coding_step_below_mechanics_floor` detector and the fuzzy gate checks
(near-duplicate / suspected coarse-filler) — v1 uses the simpler checks (§13); structured `runtime_state`
metadata object (enforce via the visible `result` first); the **UI** that consumes `code_lines` to
highlight the live line in the code panel as each action is read (the data is captured now; wiring the
panel is later); an optional **source-substring** alongside each anchor (`{"lines": [3], "text": "mid =
(low + high) // 2"}`) so the UI/validator can recover the line by matching text if numbering drifts —
low-cost future-proofing, not needed for v1.

## 12. Net effect

The 80-card explosion dissolves at the source: the outline asks for **structural** steps within the
topic's range (a 4–5-element merge sort is ~8–18, not ~80 line-executions), so the model authors that
many cards directly — which fixes granularity **and** the ~6-minute generation time, while keeping
recursion explicit and every card anchored to the code.

## 13. Implementation order (don't overbuild the first pass)

§11 says *what* is required vs deferred; this says *what to build first*. The spec is large — implement
**v1** as a clean, working path, then layer **v1.1** refinements. Don't try to land everything at once.

**v1 (required — the path that fixes the 80-card failure):**
- new coding **outline prompt** + structural-step `kind`s
- per-topic **step ranges** — flat tuples, but use a **lower merge-sort default so v1 can't reopen the
  long-example door** before size-aware parsing exists:
  ```python
  CODING_STEP_RANGES = {           # v1 flat tuples
      "binary_search": (3, 6),
      "merge_sort": (8, 18),       # v1 teaching default for n = 4–5 (NOT (12, 30) yet)
      "dfs": (5, 12), "bfs": (5, 12),
      "linked_list_operation": (4, 10),
      "dynamic_programming": (8, 20),
      "default": (5, 25),
  }
  ```
- the **hard outline gate** — v1 hard-rejects on: banned **line-level kinds**, **over-`max`** count,
  **missing required-case coverage**, **`other` over cap**. (The fuzzy checks — near-duplicate
  descriptions, coarse/filler pattern *suspicion* — are explicitly v1.1.)
- **deterministic `REQUIRED_CASES_BY_TOPIC`**
- a **minimal setup-selection prompt instruction** (not full deterministic selection): "use a small
  teaching input — merge sort prefer **4 elements**; binary search use enough elements that the target
  takes **≥3 passes**." Enough to stop a 10-element merge sort or a first-pass binary search hit.
- **delete `_group_coding_steps`**; old line-trace is **not** a fallback
- **card generation** from the accepted outline (Goal/Reasoning/Work/Result + best-effort `code_lines`)
- **basic validation telemetry** + the render-blocking schema invariant (`work`/`result` non-empty)
- `coding_fallback_used` status with reason

**v1.1 (refinements — layer in once v1 is green):**
- input-**size-aware** ranges (the `n<=4 → (8,16)`, `n<=7 → (14,24)`, `n<=10 → (18,30)` table) + the
  full deterministic setup-selection rule
- **fuzzy duplicate-filler** detection (near-duplicate descriptions)
- **suspected** coarse/filler pattern logic (the "match → confirm" path; v1 hard-skips these)
- the full `coding_step_below_mechanics_floor` two-group detector (v1 can use `missing_code_mechanics`)
- optional `runtime_state` object; **source-substring** anchors + line-anchor recovery
