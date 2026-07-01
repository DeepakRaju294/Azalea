"""Tier-2 of the coverage ladder (ADAPTER_AND_GENERATION_SYSTEM_SPEC §3): the INDEPENDENT ANSWER ANCHOR.

When a topic is computational but has NO adapter (so the STEPS can't be hard-verified), we can still guard the
one thing that most matters: the FINAL ANSWER. An INDEPENDENT derivation of the answer — a deterministic
oracle where a domain has one, else one focused, isolated LLM computation that never sees the worked-example
narration — is compared to the answer the example claims:

  * agree     -> `answer_anchored`  (the answer is guaranteed; the steps are model-authored but the endpoint holds)
  * disagree  -> `guided_fallback`  (DOWNGRADE — never ship a wrong answer as verified)
  * no oracle -> `model_only`       (honest: we could not anchor it)

This sits BELOW Tier-1 (`trace_verified`, adapter) and ABOVE unguarded model output. The oracle is injectable
so a domain with a deterministic checker plugs one in (preferred); the default is the isolated LLM call."""
from __future__ import annotations

import json
import os
import re
from typing import Any, Callable, Optional

VERIFICATION_TRACE = "trace_verified"        # Tier-1 (adapter) — for reference
VERIFICATION_ANSWER_ANCHORED = "answer_anchored"
VERIFICATION_GUIDED = "guided_fallback"
VERIFICATION_MODEL_ONLY = "model_only"

# (topic, problem) -> the independently-derived final answer as a string, or None if it can't be derived.
AnswerOracle = Callable[[dict[str, Any], str], Optional[str]]


def _num(s: str) -> Optional[float]:
    m = re.search(r"-?\d+(?:\.\d+)?", str(s))
    return float(m.group()) if m else None


def _answers_match(a: Any, b: Any) -> bool:
    na, nb = _num(a), _num(b)
    if na is not None and nb is not None:
        return abs(na - nb) < 1e-9                     # numeric endpoints compare by value
    return re.sub(r"\s+", " ", str(a).strip().lower()) == re.sub(r"\s+", " ", str(b).strip().lower())


def _default_oracle(topic: dict[str, Any], problem: str) -> Optional[str]:
    """One focused, ISOLATED computation of ONLY the final answer — it never sees the worked-example steps, so
    agreement is a genuine second opinion. Offline / on failure returns None."""
    key = os.getenv("OPENAI_API_KEY")
    if not key or key.strip().lower() == "dummy" or not str(problem or "").strip():
        return None
    try:
        from app.services.llm_client import OPENAI_MODEL, client, llm_call

        system = ("Compute ONLY the final answer to the problem. Do not show steps or explanation. "
                  'Return ONLY JSON: {"answer": "<the final answer>"}.')
        with llm_call("answer_anchor"):
            resp = client.with_options(timeout=45, max_retries=2).responses.create(
                model=OPENAI_MODEL,
                input=[{"role": "system", "content": system},
                       {"role": "user", "content": str(problem)}],
                text={"format": {"type": "json_object"}},
            )
        ans = str((json.loads(resp.output_text) or {}).get("answer") or "").strip()
        return ans or None
    except Exception:  # noqa: BLE001
        return None


_oracle: AnswerOracle = _default_oracle


def set_answer_oracle(fn: AnswerOracle) -> None:
    """Override the independent oracle (tests, or a deterministic domain checker)."""
    global _oracle
    _oracle = fn


def anchor_final_answer(topic: dict[str, Any], problem: str, claimed_answer: Any) -> tuple[str, Optional[str], Optional[bool]]:
    """Independently derive the final answer and compare it to `claimed_answer`. Returns
    (verification_level, expected_answer, agree). Use this for a COMPUTATIONAL topic with no adapter."""
    try:
        expected = _oracle(topic, problem)
    except Exception:  # noqa: BLE001
        expected = None
    if not expected:
        return VERIFICATION_MODEL_ONLY, None, None
    agree = _answers_match(expected, claimed_answer)
    return (VERIFICATION_ANSWER_ANCHORED if agree else VERIFICATION_GUIDED), expected, agree
