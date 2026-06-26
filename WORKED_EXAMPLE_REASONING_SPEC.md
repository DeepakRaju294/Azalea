# Worked-Example Reasoning Spec (Reason → Format → Check)

**Status:** Draft v2 — design only, not implemented.
**Scope:** WORKED EXAMPLES ONLY. Not code walkthroughs, lesson bodies, visuals, or topic decomposition.
**Disposition:** **Additive and flag-gated.** A NEW worked-example generation strategy that ships
*alongside* the existing systems (the legacy one-shot solver and the gen_foundation
execution/reference path). It deletes/overwrites nothing. One env variable selects it
(`AZALEA_WORKED_EXAMPLE_REASON_FIRST`, default **off**), so it can be A/B-tested against current output
on the same topics, then promoted or dropped without touching the other paths.

---

# Part I — Concept

## 1. Why this exists

The worked example is produced today by **one constrained call** (`solver.py` `_SYSTEM`) that asks the
model to do everything at once — invent the problem, compute the final answer, estimate step count, and
emit `cards[]` (up to 8 fields each) as a single `json_object`, with a hard rule that the last card
reaches the final answer.

So the model must **compute the multi-step trace AND format it into a rigid schema simultaneously**,
with no room to work the problem out. That is the opposite of how the same model succeeds when prompted
directly ("trace Kruskal's on this graph step by step") — there it **reasons first, then presents.**
Constrained, answer-first, structured output suppresses the chain-of-thought the model needs, which is
why it loses global state (a disconnected MST) and declares an answer the steps never reach.

**Hypothesis under test:** the examples are wrong mostly because we prompt in a reasoning-hostile way,
not because the model lacks the ability. Let it reason freely first and format second, and accuracy
comes from the model — a light check almost never has to act. This is the **lighter, general**
alternative to the per-algorithm execution/reference machinery: no hardcoded references, any topic.

## 2. Core principle

> **Never make the model compute and format in the same constrained breath.**
> Reason first (free-form), format second (mechanical), check last (rare).

## 3. The three passes

```
Pass A — REASON  : free-form, ChatGPT-style. Solve the concrete problem fully + self-check. No schema.
        ↓  ReasoningResult{ problem, solution_text, final_answer }
Pass B — FORMAT  : reshape the verified solution into the EXISTING card schema. May not change any value.
        ↓  cards[]  (existing worked-example card shape)
Pass C — CHECK   : deterministic. Cards stay faithful to A's answer + family invariants hold. Rare fail.
```

Accuracy lives in **A**. **B**'s errors are cosmetic. **C** is a consistency guard, not a corrector.

---

# Part II — Implementation Design (detailed)

## 4. Module layout

```
app/services/examples/reason_first.py     NEW — the only new file with logic
    ReasoningResult / ReasonFirstResult   dataclasses (contracts between passes)
    build_reason_prompt(...)              Pass A prompt
    parse_reasoning(...)                  Pass A output → ReasoningResult
    build_format_prompt(...)              Pass B prompt
    normalize_cards(...)                  Pass B output → existing card list
    check_faithful(...)                   Pass C (reuses property_checks)
    solve_reason_first(...)               orchestration (A→B→C + bounded retries)
    _reason_first_enabled()               reads AZALEA_WORKED_EXAMPLE_REASON_FIRST

app/services/examples/solver.py           ONE added branch at the solve hook (§9). No other edits.
app/tests/test_reason_first.py            NEW — offline tests with stub passes
```

Reused, unchanged: `property_checks`, `trace_quality.worked_example_correctness_violations`, the card
schema + `_WORKED_EXAMPLE_RULES`, the renderer/blueprint.

## 5. Contracts (dataclasses)

```python
ModelFn = Callable[[dict[str, str]], Optional[Any]]   # {"system","user"} -> text or parsed json | None

@dataclass(frozen=True)
class ReasoningResult:
    problem: str          # the concrete problem actually solved (from backend input or Pass A)
    solution_text: str    # the full free-form worked reasoning, start to finish
    final_answer: str     # the explicit final answer (parsed from the FINAL ANSWER marker)

@dataclass(frozen=True)
class ReasonFirstResult:
    problem: str
    cards: list[dict[str, Any]]   # EXISTING worked-example card shape (title/goal/reasoning/work/result…)
    final_answer: str
    source: str = "reason_first"  # stamped to metadata for A/B identification
```

Both `reason_fn` and `format_fn` are **injected** (production = the real OpenAI call; tests = stubs), so
the whole path is deterministic offline.

## 6. Pass A — Reason (prompt + parsing)

**Input selection:** if the backend already chose a concrete `example_input` (the array/graph/etc. the
other systems use), pass it verbatim so the instance is fixed and varied; else let Pass A invent one.

**Prompt (`build_reason_prompt`):** plain tutor, **no JSON, no card schema**.
```
SYSTEM: You are a precise, rigorous tutor. Solve ONE concrete problem completely and correctly, the way
you would explain it to a student. Think step by step and show your work — take the space you need.
Do not summarize; actually carry out each step. When done, on the final two lines output exactly:
    PROBLEM: <the concrete problem you solved, as a self-contained statement>
    FINAL ANSWER: <the final answer only>
Before those lines, VERIFY your answer satisfies the defining property of the task (e.g. an MST connects
every vertex with exactly V-1 edges; a sorted list is non-decreasing). If it fails, fix the work first.

USER: Topic: <title>.  <If example_input: "Solve it for this exact input: <example_input>".>
      <topic_type-specific one-liner, e.g. "Find the MST and show each edge decision.">
```

**Output:** free-form markdown text. Use a reasoning-permissive model/mode here if available.

**`parse_reasoning(text, example_input)`** → `ReasoningResult | None`:
- `final_answer` = regex-capture after the last `FINAL ANSWER:` marker (required; `None` → Pass A failed,
  fall through to existing systems).
- `problem` = `example_input`-derived statement if supplied, else capture after `PROBLEM:`.
- `solution_text` = everything before the marker block.
- No marker / empty answer → return `None` (do **not** ship; §8 fallback).

## 7. Pass B — Format (prompt + normalization)

**Prompt (`build_format_prompt`):** the ONLY structured call. Feeds Pass A's verified text + the
existing schema/rules, with a hard "don't change the math" constraint.
```
SYSTEM: You are formatting an ALREADY-CORRECT worked solution into step cards. You MUST NOT change any
number, value, intermediate state, step order, or the final answer — only split the solution into steps,
title them, and phrase the fields. <inline: _WORKED_EXAMPLE_RULES (atomic step, field semantics)>.
Return ONLY JSON: {"cards":[{"title","goal","reasoning","work":[...],"result"}, ...]}.
The last card's `result` MUST equal the final answer below.

USER: PROBLEM: <reasoning.problem>
      SOLUTION (verified, do not alter values):
      <reasoning.solution_text>
      FINAL ANSWER: <reasoning.final_answer>
```

**`normalize_cards(raw)`** → `list[dict] | None`:
- Coerce to the existing card shape (reuse the same normalization solver.py already applies:
  `work` is a list of strings; missing optional fields default empty; legacy key aliases mapped).
- Prepend the standard **setup card** (problem statement) exactly as the existing solver does, so the
  output is byte-compatible with the renderer/blueprint.
- `< 1` step card → `None`.

## 8. Pass C — Check + orchestration (with bounded retries)

`check_faithful(cards, reasoning, topic, example_input)` → `list[str]` (empty = pass). Deterministic,
no LLM:
1. **Answer fidelity** — the last card's `result` reaches `reasoning.final_answer` (reuse
   `completeness.card_reaches_final` / numeric-signature match). Flags a B drift.
2. **No contradiction** — no card asserts a value inconsistent with the final answer (cheap numeric scan).
3. **Family invariants** — run the EXISTING guard on `final_answer`:
   `worked_example_correctness_violations(cards, topic)` and, when applicable,
   `property_checks` (MST connects all + V-1; sorted output ordered; …). This should almost never trip,
   because Pass A self-checked.

`solve_reason_first(topic, example_input, *, reason_fn, format_fn)` → `ReasonFirstResult | None`:
```python
r = parse_reasoning(reason_fn(build_reason_prompt(topic, example_input)), example_input)
if r is None: return None                       # Pass A unusable -> caller falls through to existing
for _ in range(_MAX_FORMAT_ATTEMPTS):           # default 2: B + one re-format
    cards = normalize_cards(format_fn(build_format_prompt(r)))
    if cards and not (errs := check_faithful(cards, r, topic, example_input)):
        return ReasonFirstResult(r.problem, cards, r.final_answer)
    last_errs = errs
# If only fidelity/format failed -> B couldn't transcribe; if an INVARIANT failed -> A was wrong.
if _invariant_failed(last_errs) and _MAX_REASON_RETRY:   # one re-reason with the violation fed back
    r2 = parse_reasoning(reason_fn(build_reason_prompt(topic, example_input, prior_violation=last_errs)),
                         example_input)
    if r2 and (cards := normalize_cards(format_fn(build_format_prompt(r2)))) \
            and not check_faithful(cards, r2, topic, example_input):
        return ReasonFirstResult(r2.problem, cards, r2.final_answer)
return None                                     # WITHHOLD — never ship a failing example; caller decides
```
Budgets via env: `AZALEA_REASON_FIRST_MAX_FORMAT_ATTEMPTS` (default 2), `..._MAX_REASON_RETRY` (0/1,
default 1). Worst case = 1 reason + 2 format + (1 reason + 1 format) = bounded, no loops.

## 9. Wiring (one branch, additive)

Hook = the existing worked-example solve entry. Reason-first runs **before** the gen_foundation shadow
and legacy paths and only when its flag is on; otherwise control flows exactly as today.

```python
# in solve_worked_example(topic, *, code, solver):   (the ONLY edit to solver.py)
if _reason_first_enabled():                                  # AZALEA_WORKED_EXAMPLE_REASON_FIRST
    rf = solve_reason_first(topic, _example_input_for(topic),
                            reason_fn=default_reasoner, format_fn=default_formatter)
    if rf is not None:
        return _reason_first_to_solve_result(rf)             # {problem, cards, final_answer, generated_by:"reason_first"}
    # rf is None -> fall through unchanged to the existing systems below
if _gf_flags.is_shadow_enabled():
    ... existing gen_foundation path ...
... existing legacy path ...
```
`_reason_first_to_solve_result` maps `ReasonFirstResult` onto the exact dict `solve_worked_example`
already returns (so `apply_llm_solved_worked_example` and everything downstream are untouched), stamping
`generated_by="reason_first"` and `metadata.worked_example_source="reason_first"`.

## 10. Flag matrix

| `REASON_FIRST` | `GEN_FOUNDATION_SHADOW` | Worked-example source |
|---|---|---|
| on | (any) | **reason-first**; falls through to the row below only if it returns `None` |
| off | on | gen_foundation (trace-first / reference / executed-reference), unchanged |
| off | off | legacy one-shot solver, unchanged |

Reason-first never *blocks* — a `None` (Pass A unusable, or withhold after retries) cleanly defers to
whatever is enabled beneath it. So turning the flag on can only *replace* an example with a reason-first
one or defer; it can never break a topic that worked before.

## 11. Tests (`test_reason_first.py`, offline, stubs)

- **Pass B never alters the answer:** stub `reason_fn` → a known solution + answer; stub `format_fn` that
  echoes; assert last card `result` == final answer; assert no value introduced that wasn't in A.
- **Parsing:** `parse_reasoning` extracts `final_answer`/`problem`; missing marker → `None`.
- **Check fires correctly:** fabricate cards whose last result ≠ A's answer → fidelity error; fabricate a
  disconnected-MST `final_answer` → invariant error (reuses `property_checks`).
- **Retry/withhold:** format stub fails once then succeeds → result returned; always fails → `None`.
- **Flag-off no-op:** with the flag unset, `solve_worked_example` behaves byte-for-byte as before
  (assert reason-first code is never entered).
- **Shape compatibility:** `_reason_first_to_solve_result` output validates against the existing
  worked-example card contract / `apply_llm_solved_worked_example`.

## 12. A/B + rollout

1. Build §4 module + tests (no wiring) — green offline.
2. Add the single hook branch (§9) behind the flag.
3. **A/B:** same topic set, flag on vs off. Metrics: Pass C invariant pass-rate (correctness), card count
   (conciseness vs the old long model examples), latency + call count. **Success bar:** ≥ ground-truth
   correctness on covered algorithms AND ≥ current on the long tail, with Pass C tripping on a small
   minority.
4. Promote (default-on) only after the bar is met; otherwise keep flag-off and iterate prompts.

## 13. Cost & failure posture

- **Calls:** 2 (A + B) + rare retries. Comparable to today's solve+audit; far cheaper than the
  execution/reference machinery; correctness no longer hinges on one constrained call.
- **Failure is safe:** any unrecoverable case returns `None` → defers to the existing systems (or
  withholds), never ships a known-wrong example, never falls into a regenerate loop.

## 14. Open decisions

- **Pass A model:** start prompt-only on the standard model; switch to a reasoning/extended-thinking
  model only if hard-tail accuracy is short.
- **One-call scratchpad variant:** a fallback if latency dominates — a single call whose JSON begins with
  a free-form `working` field before `cards[]`. Less reliable than two calls; not the default.
- **Coverage of `required_cases`:** if the existing blueprint demands specific cases, pass them into Pass
  A's prompt as "your trace must exercise: …" and verify in Pass C.

---

## 15. Non-goals

Deleting/replacing any existing system; changing the card schema or renderer; the per-algorithm
execution/reference path; anything outside worked examples. If reason-first proves out, the
reason-then-format pattern is a *future* candidate for code walkthroughs / lesson body / topic
decomposition — each a separate change, out of scope here.
