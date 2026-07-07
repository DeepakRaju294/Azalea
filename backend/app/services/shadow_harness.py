"""Shadow measurement driver — enroll families, run the Q23/Q24 shadow hooks over card-plans, aggregate.

Two uses:
- Offline/CI: pass fixture card-plans (and, for trace, an adapted steps_by_id) → get a `ShadowReport` deterministically,
  no LLM/API key. This is how a family's violation rate is measured on a curated set before flipping to on_enforced.
- Production: run real generation (the hooks write their JSONL sinks), then `shadow_metrics.aggregate_files(...)`.

Enrollment mutates the global rollout family table; this harness saves/restores it and suppresses the JSONL sinks
by default so a measurement run never pollutes production logs.
"""
from __future__ import annotations

import contextlib
import os
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from app.services import shadow_metrics
from app.services.free_text import shadow as _ft_shadow
from app.services.narration import rollout
from app.services.trace_teaching import grammar as _tt_grammar
from app.services.trace_teaching import shadow as _tt_shadow

# A free-text plan: (topic_type, cards). A trace plan: (topic_id, cards, steps_by_id[, gate_domain, gate_card_type]).
FreeTextPlan = Tuple[str, List[dict]]
TracePlan = Tuple


@contextlib.contextmanager
def _measurement_context(enroll: Sequence[Tuple], write: bool):
    saved_modes = dict(rollout._FAMILY_MODES)
    saved_ft_path, saved_tt_path = _ft_shadow._TELEMETRY_PATH, _tt_shadow._TELEMETRY_PATH
    try:
        for fam in enroll:
            key = (fam[0], fam[1], fam[2] if len(fam) > 2 else None)
            rollout._FAMILY_MODES[key] = rollout.SHADOW_VALIDATE
        if not write:
            _ft_shadow._TELEMETRY_PATH = os.devnull
            _tt_shadow._TELEMETRY_PATH = os.devnull
        yield
    finally:
        rollout._FAMILY_MODES.clear()
        rollout._FAMILY_MODES.update(saved_modes)
        _ft_shadow._TELEMETRY_PATH = saved_ft_path
        _tt_shadow._TELEMETRY_PATH = saved_tt_path


def evaluate(
    *,
    free_text_plans: Iterable[FreeTextPlan] = (),
    trace_plans: Iterable[TracePlan] = (),
    enroll: Sequence[Tuple] = (("math", "concept_intuition"),),
    write: bool = False,
) -> shadow_metrics.ShadowReport:
    """Run the shadow hooks over the given plans and return the aggregated violation-rate report."""
    pairs: List[Tuple[str, dict]] = []
    with _measurement_context(enroll, write):
        for topic_type, cards in free_text_plans:
            rep = _ft_shadow.evaluate_card_plan(topic_type, cards)
            if rep:
                pairs.append((shadow_metrics.FREE_TEXT, rep))
        for plan in trace_plans:
            topic_id, cards, steps_by_id = plan[0], plan[1], plan[2]
            gate_domain = plan[3] if len(plan) > 3 else "coding"
            gate_card_type = plan[4] if len(plan) > 4 else "worked_example"
            rep = _tt_shadow.evaluate(cards, steps_by_id, topic_id=topic_id,
                                      gate_domain=gate_domain, gate_card_type=gate_card_type)
            if rep:
                pairs.append((shadow_metrics.TRACE_TEACHING, rep))
    return shadow_metrics.aggregate(pairs)
