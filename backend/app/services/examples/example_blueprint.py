"""Example blueprint — the GENERATION contract and the VALIDATION contract for worked examples.

Kept deliberately separate (generation is strict, validation is diagnostic), and independent of
the retired example-typing/fixture/ontology system.

GENERATION CONTRACT (what the solver emits)
  - SETUP card: the COMPLETE concrete problem — exact inputs + task + answer FORMAT (NOT the
    answer value). Hidden metadata carries expected_final_answer, required_cases, expected_min_steps.
  - STEP card: ONE transition — prior_state -> decision (why) -> action -> resulting_state — plus
    cases_covered (which required_cases this step exercises) and an optional visual_delta.
  - FINAL step: metadata.final_answer is its conclusion; it must reach expected_final_answer.

VALIDATION CONTRACT (audit_example — flags, never raises)
  - structure : every step has a full transition (prior/decision/action/resulting) and is not a
    no-op (prior == resulting).
  - completeness : step count meets the topic's expected_min_steps; the final step reaches the
    expected_final_answer (structured metadata match, blob fallback).
  - coverage : every required_case is covered by some step's cases_covered.
  The result is stamped on the setup card as `example_status` so failures are inspectable.
"""
from __future__ import annotations

import ast
import logging
import re
from typing import Any, Optional

_log = logging.getLogger(__name__)

# Deterministic accuracy check: a work line of the form "A + B  =>  C" (a merge/concatenation) must
# have C equal to A and B combined (same multiset). Catches "[5,32] + [32,62] => [5,7,23,...]".
_MERGE_RE = re.compile(r"(\[[0-9,\s]*\])\s*\+\s*(\[[0-9,\s]*\])\s*(?:=>|⇒|->|→|=)\s*(\[[0-9,\s]*\])")


def _step_arithmetic_inconsistent(card: dict[str, Any]) -> bool:
    for line in (card.get("work") or []):
        m = _MERGE_RE.search(str(line))
        if not m:
            continue
        try:
            a, b, c = (ast.literal_eval(m.group(i)) for i in (1, 2, 3))
        except (ValueError, SyntaxError):
            continue
        if isinstance(a, list) and isinstance(b, list) and isinstance(c, list) and sorted(a + b) != sorted(c):
            return True
    return False

# Fallback minimum when the solver did not estimate an expected step count. The real floor is the
# outline gate (≥4 FULL steps); this is a coarse card-count backstop.
DEFAULT_MIN_STEPS = 4

# Reference data: exactly what each card role contains (the generation contract).
EXAMPLE_CARD_BLUEPRINT: dict[str, dict[str, str]] = {
    "setup": {
        "role": "setup",
        "contains": "the COMPLETE problem like a test question — exact input values, the task, and "
                    "the expected answer FORMAT (not the value; that is metadata.expected_final_answer)",
        "metadata": "example={role:setup}; expected_final_answer; required_cases; expected_min_steps",
    },
    "step": {
        "role": "step",
        "contains": "ONE transition — prior_state, decision (why), action, resulting_state",
        "metadata": "example={role:step,index,total}; transition={prior_state,decision,action,resulting_state}; "
                    "cases_covered=[...]; visual_delta={...} (optional)",
    },
    "final": {
        "role": "the LAST step",
        "contains": "a step whose resulting_state reaches the expected final answer",
        "metadata": "final_answer=<conclusion>; reaches_final_answer=True (stamped on validation)",
    },
}

# The one rule system for HOW the example problem is posed (shared by the solver prompt).
EXAMPLE_PROBLEM_RULES = """\
HOW TO MAKE THE EXAMPLE PROBLEM:
- Pick ONE concrete, COMPREHENSIVE, canonical instance of the topic — the kind of problem a
  learner must master, NOT a trivial warm-up. It must be rich enough to need several genuine
  decisions and to reach a non-trivial answer.
- SIZE THE INPUT FROM THE STEP COUNT, not from raw size. Choose an instance whose NATURAL solution
  runs through AT LEAST 4 FULL STEPS — complete iterations/cycles of the method (e.g. for binary
  search one full step = compute mid + compare + adjust the bounds; for merge sort one full step =
  merge two runs). Size the input to need ≥4 full steps and NO LARGER. Difficulty must come from
  applying the concept and its decisions/cases — NOT from large inputs, verbose wording, or
  unrelated calculation. Never pick a trivial instance (a 3-node tree, a one-iteration trace) that
  resolves in fewer than 4 full steps.
- State the COMPLETE problem like a TEST QUESTION: the exact input VALUES (write the ACTUAL
  values, e.g. a real list of numbers, never the word "array" or a placeholder), the task, and the
  expected answer FORMAT — so the learner could solve it from the statement alone. Do NOT reveal
  the final answer in the problem text; that goes in `expected_final_answer`.
- INVENT FRESH INPUT VALUES for every example. Do NOT reuse a canonical textbook instance from
  memory (e.g. the merge-sort array [38, 27, 43, 3, 9, 82, 10] from Wikipedia/CLRS) and do NOT
  reuse any numbers shown in these instructions — choose your own randomized values each time.
- List in `required_cases` the key decisions/cases the example MUST exercise (including the tricky
  / boundary / edge ones), and tag each step's `cases_covered` with the ones it addresses — by the
  end EVERY required_case must be covered. Choose the instance so it genuinely hits them all."""


def _is_worked_example(card: Any) -> bool:
    return (
        isinstance(card, dict)
        and str(card.get("blueprint_key") or card.get("card_type") or "").lower() == "worked_example"
    )


def _is_setup(card: dict[str, Any]) -> bool:
    return bool((card.get("metadata") or {}).get("worked_example_setup"))


def _norm(text: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip()


def _step_work_text(card: dict[str, Any]) -> str:
    """The step's concrete work, as text. Reads the `work` field; falls back to the card's
    points so older/free-form cards still validate."""
    work = card.get("work")
    if isinstance(work, list) and work:
        return " ".join(str(w) for w in work).strip()
    if isinstance(work, str) and work.strip():
        return work.strip()
    pts = card.get("points")
    if isinstance(pts, list) and pts:
        return " ".join(str(p) for p in pts).strip()
    return ""


def _step_result_text(card: dict[str, Any]) -> str:
    r = str(card.get("result") or "").strip()
    if r:
        return r
    for p in reversed(card.get("points") or []):
        if str(p).strip():
            return str(p).strip()
    return ""


_VAGUE_WORK = {
    "apply the formula", "continue the algorithm", "update the state", "perform the calculation",
    "repeat the process", "apply the algorithm", "do the next step", "continue",
}

# A coding-implementation step's work must show code/trace, not pure prose. Conservative: flag only
# when the work has NO code token at all (it could appear verbatim in an algorithm walkthrough).
_CODE_TOKEN = re.compile(r"[\[\]()=<>{}]|->|//|\w+\.\w+|\breturn\b|\bappend\b|\bpop\b|\bmid\b")


def _coding_step_algorithmic(card: dict[str, Any]) -> bool:
    blob = " ".join(str(x) for x in (card.get("work") or []))
    return bool(blob.strip()) and not _CODE_TOKEN.search(blob)


def _case_covered(required: str, covered: set[str]) -> bool:
    """A required case is covered if a step tagged it (normalized, lenient substring match)."""
    nr = _norm(required)
    return any(nr and (nr in c or c in nr) for c in covered)


def _tokens(text: str) -> set[str]:
    return {t for t in _norm(text).split() if len(t) >= 2}


def _prior_state_text(card: dict[str, Any]) -> str:
    """The step's declared starting state, as text (for continuity checks). Reads metadata."""
    ps = (card.get("metadata") or {}).get("prior_state")
    if isinstance(ps, dict):
        return " ".join(f"{k} {v}" for k, v in ps.items())
    if isinstance(ps, str):
        return ps
    return ""


def stamp_example_metadata(
    cards: list[Any],
    *,
    expected_final_answer: str = "",
    expected_min_steps: Optional[int] = None,
    required_cases: tuple[str, ...] = (),
    allow_short_example: bool = False,
    enforce_field_contract: bool = True,
    coding: bool = False,
) -> dict[str, Any]:
    """Stamp blueprint metadata on every worked-example card and validate it against the
    Goal/Reasoning/Work/Result contract, returning (and stamping on the setup card) a nested
    example_status. Failure-safe."""
    try:
        we = [c for c in cards if _is_worked_example(c)]
        if not we:
            return {"present": False}

        steps = [c for c in we if not _is_setup(c)]
        total = len(steps)
        has_setup = any(_is_setup(c) for c in we)

        for card in we:
            if _is_setup(card):
                card.setdefault("metadata", {})["example"] = {"role": "setup"}
        for index, card in enumerate(steps, start=1):
            card.setdefault("metadata", {})["example"] = {"role": "step", "index": index, "total": total}

        # --- structure (concrete work + result) + progression (no-op / repeated / continuity) ---
        field_issues: list[dict[str, Any]] = []   # missing_work / missing_result / non_concrete_work
        no_op_steps: list[int] = []
        repeated_steps: list[int] = []
        continuity_steps: list[int] = []
        inconsistent_steps: list[int] = []         # arithmetic the operation could not produce
        algorithmic_steps: list[int] = []          # coding step with no code (reads like algo walkthrough)
        seen_sigs: dict[str, int] = {}
        prev_work = prev_result = prev_end = ""
        if enforce_field_contract:
            for index, card in enumerate(steps, start=1):
                work_text = _step_work_text(card)
                result_text = _step_result_text(card)
                nw, nr = _norm(work_text), _norm(result_text)
                if not work_text:
                    field_issues.append({"step": index, "issue": "missing_work"})
                elif nw in _VAGUE_WORK:
                    field_issues.append({"step": index, "issue": "non_concrete_work"})
                if not result_text:
                    field_issues.append({"step": index, "issue": "missing_result"})
                elif nr and nr == prev_result and nw == prev_work:
                    no_op_steps.append(index)  # adjacent repeat with no state change
                if _step_arithmetic_inconsistent(card):
                    inconsistent_steps.append(index)
                if coding and work_text and _coding_step_algorithmic(card):
                    algorithmic_steps.append(index)
                # repeated: same work+result as a NON-adjacent earlier step (a loop / copy)
                sig = (nw + " | " + nr).strip()
                if sig and sig != " | " and sig in seen_sigs and seen_sigs[sig] != index - 1:
                    repeated_steps.append(index)
                if sig and sig != " | ":
                    seen_sigs.setdefault(sig, index)
                # continuity: this step's declared prior_state shares nothing with where the last ended
                ps_text = _prior_state_text(card)
                if index >= 2 and ps_text and prev_end and len(_tokens(ps_text)) >= 2:
                    if not (_tokens(ps_text) & _tokens(prev_end)):
                        continuity_steps.append(index)
                prev_work, prev_result = nw, nr
                prev_end = (result_text + " " + work_text).strip()

        # --- completeness: reaches the expected final answer (structured metadata, blob fallback) ---
        last = steps[-1] if steps else None
        finished = False
        if last:
            actual_final = (str((last.get("metadata") or {}).get("final_answer") or "").strip()
                            or _step_result_text(last))
            if not expected_final_answer:
                finished = bool((last.get("metadata") or {}).get("reaches_final_answer") or actual_final)
            else:
                ne = _norm(expected_final_answer)
                if actual_final and (ne in _norm(actual_final) or _norm(actual_final) in ne):
                    finished = True
                else:  # fallback: the answer appears in the last step's text
                    blob = _norm(" ".join(str(p) for p in (last.get("points") or []))
                                 + " " + _step_result_text(last))
                    finished = bool(ne) and ne in blob
            if finished:
                last.setdefault("metadata", {})["reaches_final_answer"] = True

        # The visible result of the final step must actually STATE the answer (not just the hidden one).
        visible_conclusion = True
        if last and expected_final_answer:
            ne = _norm(expected_final_answer)
            lr = _norm(_step_result_text(last))
            visible_conclusion = bool(ne) and (ne in lr or (bool(lr) and lr in ne))
        missing_visible = bool(finished and expected_final_answer and not visible_conclusion)

        min_steps = expected_min_steps if (expected_min_steps and expected_min_steps > 0) else DEFAULT_MIN_STEPS
        skipped = (not allow_short_example) and total < min_steps

        # --- coverage: every required_case exercised by some step's cases_covered ---
        covered: set[str] = set()
        for card in steps:
            for case in (card.get("metadata") or {}).get("cases_covered") or []:
                if str(case).strip():
                    covered.add(_norm(case))
        missing_cases = [c for c in required_cases if str(c).strip() and not _case_covered(c, covered)]
        coverage_fails = enforce_field_contract and bool(required_cases) and bool(missing_cases)

        complete = (has_setup and finished and visible_conclusion and not skipped
                    and not field_issues and not inconsistent_steps and not algorithmic_steps
                    and not no_op_steps and not repeated_steps and not continuity_steps
                    and not coverage_fails)

        # Highest-priority primary reason (spec §20); `issues` keeps them all.
        reason = ""
        if not complete:
            if not has_setup:
                reason = "missing_setup"
            elif field_issues:
                reason = field_issues[0]["issue"]
            elif algorithmic_steps:
                reason = "algorithmic_not_implementation"
            elif inconsistent_steps:
                reason = "inconsistent_step"
            elif no_op_steps:
                reason = "no_op_step"
            elif continuity_steps:
                reason = "broken_continuity"
            elif repeated_steps:
                reason = "repeated_step"
            elif skipped:
                reason = "steps_skipped"
            elif coverage_fails:
                reason = "missing_required_case"
            elif not finished:
                reason = "did_not_finish"
            elif missing_visible:
                reason = "missing_visible_conclusion"

        issues: list[dict[str, Any]] = [{"code": i["issue"], "step": i["step"]} for i in field_issues]
        issues += [{"code": "algorithmic_not_implementation", "step": s} for s in algorithmic_steps]
        issues += [{"code": "inconsistent_step", "step": s} for s in inconsistent_steps]
        issues += [{"code": "no_op_step", "step": s} for s in no_op_steps]
        issues += [{"code": "broken_continuity", "step": s} for s in continuity_steps]
        issues += [{"code": "repeated_step", "step": s} for s in repeated_steps]
        if skipped:
            issues.append({"code": "steps_skipped"})
        issues += [{"code": "missing_required_case", "case": c} for c in missing_cases]
        if not finished:
            issues.append({"code": "did_not_finish"})
        elif missing_visible:
            issues.append({"code": "missing_visible_conclusion"})

        status = {
            "present": True,
            "complete": complete,
            "structure": {"has_setup": has_setup, "steps": total, "field_issues": field_issues},
            "progression": {
                "no_op_steps": no_op_steps, "repeated_steps": repeated_steps,
                "continuity_issues": continuity_steps, "inconsistent_steps": inconsistent_steps,
                "algorithmic_steps": algorithmic_steps,
            },
            "completeness": {
                "expected_min_steps": min_steps, "actual_steps": total, "skipped": skipped,
                "finished": finished, "visible_conclusion": visible_conclusion,
            },
            "coverage": {
                "required": list(required_cases),
                "covered": sorted(covered),
                "missing": missing_cases,
            },
            "reason": reason,
            "issues": issues,
        }

        anchor = next((c for c in we if _is_setup(c)), we[0])
        ameta = anchor.setdefault("metadata", {})
        ameta["example_status"] = status
        if expected_final_answer:
            ameta["expected_final_answer"] = expected_final_answer
        if required_cases:
            ameta["required_cases"] = list(required_cases)
        if expected_min_steps is not None:
            ameta["expected_min_steps"] = expected_min_steps

        if not complete:
            _log.warning("example_blueprint: incomplete worked example (%s, steps=%d)", reason, total)
            try:
                from app.services.visual_v2.invariant_metrics import GLOBAL as INV

                INV.record_incomplete_worked_example(regenerations=0)
            except Exception:  # noqa: BLE001 — telemetry is best-effort
                pass
        return status
    except Exception as exc:  # noqa: BLE001 — metadata stamping must never break a lesson
        _log.warning("example_blueprint: stamp failed: %s", exc)
        return {"present": False, "error": True}
