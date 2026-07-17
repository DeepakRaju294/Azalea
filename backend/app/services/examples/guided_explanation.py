"""Guided-explanation fallback (WORKED_EXAMPLE_ACCURACY_SPEC §8b / §8b.1).

When a topic IS a computation but we cannot verify a worked trace (no adapter + no independent endpoint),
we do NOT ship a fake "worked example" and we do NOT leave a blank — we ship a bounded **"Key process"**
card that explains the method's general phases WITHOUT any specific computed transition or claimed answer.
The `GuidedExplanationContract` is enforced like Tier 1: an LLM-written card that smuggles in a concrete
value/transition is rejected and replaced by the safe deterministic template.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

_log = logging.getLogger(__name__)

# §8b.1 forbidden: anything that asserts a specific UNVERIFIED fact (the thing that made the Prim stub look
# computational). Guided cards are value-free: general phases only.
_DIGIT = re.compile(r"\d")                    # any specific number → a concrete (unverified) value
_STEP_N = re.compile(r"\bstep\s+\d+\b", re.I)  # "after step 4 …"


def validate_guided_explanation(card: dict[str, Any]) -> list[str]:
    """Return contract violations (empty = compliant). Conservative: guided cards carry NO concrete values."""
    text = " ".join([str(card.get("goal", "")), str(card.get("reasoning", "")),
                     " ".join(card.get("work") or []), str(card.get("result", ""))])
    bad: list[str] = []
    if _STEP_N.search(text):
        bad.append("step_n_claim")
    if _DIGIT.search(text):
        bad.append("contains_specific_value")   # a guided explanation must not assert computed numbers
    return bad


def _template_card(topic: dict[str, Any]) -> dict[str, Any]:
    concept = str(topic.get("concept") or topic.get("learning_goal") or topic.get("title") or "this method")
    return {
        "title": "Key process", "card_type": "worked_example", "blueprint_key": "worked_example",
        "goal": f"Understand the overall process behind {concept}.",
        "reasoning": "We walk the general phases of the method rather than a specific computed run.",
        "work": ["Identify the inputs and what counts as the goal.",
                 "Apply the method's main steps in order, checking the condition that decides each step.",
                 "Stop when the terminating condition holds, then read off the result."],
        "result": "With these phases in mind, you can reason through a concrete instance yourself.",
        "metadata": {"example": {"role": "guided"}, "verification_level": "none"},
    }


def _llm_card(topic: dict[str, Any]) -> Optional[dict[str, Any]]:
    """A bounded LLM 'Key process' explanation. Offline / on failure → None (caller uses the template)."""
    try:
        from .trace_pipeline import _llm_call
        payload = {
            "system": ("Write a SHORT conceptual 'Key process' explanation of the method this topic teaches. "
                       "Describe GENERAL PHASES only. STRICTLY FORBIDDEN: any specific numeric value, any "
                       "concrete 'next choose/add/visit X' transition, any 'step N' claim, any final computed "
                       'answer. Return JSON {"goal","reasoning","work":["...","..."],"result"}.'),
            "user": f"Topic: {topic.get('title')}\nConcept: {topic.get('concept') or topic.get('learning_goal') or ''}",
        }
        out = _llm_call(payload, "guided_explanation", json_mode=True)
        if not isinstance(out, dict):
            return None
        raw_work = out.get("work")
        if isinstance(raw_work, str):                # a bare string must never be char-iterated
            raw_work = [raw_work]
        return {"title": "Key process", "card_type": "worked_example", "blueprint_key": "worked_example",
                "goal": str(out.get("goal", "")), "reasoning": str(out.get("reasoning", "")),
                "work": [str(x) for x in (raw_work or []) if str(x).strip()],
                "result": str(out.get("result", "")),
                "metadata": {"example": {"role": "guided"}, "verification_level": "none"}}
    except Exception as exc:  # noqa: BLE001
        _log.debug("guided LLM card failed: %s", exc)
        return None


def build_guided_explanation(topic: dict[str, Any], *, reason: str) -> dict[str, Any]:
    """A guided_fallback result. Tries the LLM (contract-checked); any violation → safe template."""
    card = _llm_card(topic)
    if card is None or validate_guided_explanation(card):
        card = _template_card(topic)
    return {
        "problem": str(topic.get("title") or "Key process"),
        "cards": [card],
        "final_answer": "",
        "generated_by": "guided_fallback",
        "metadata": {"treatment": "guided_fallback", "worked_example_status": "withheld",
                     "verification_level": "none", "withhold_reason": reason},
    }
