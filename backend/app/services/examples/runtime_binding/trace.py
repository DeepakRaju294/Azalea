"""Trace-chain integration (spec §17.1 unit 7).

Build the EXISTING adapter trace artifacts from an executed instance — a `ContractTrace` of verified Steps
plus a `TeachingProjection` and `TeachingCheckpoint`s — reusing the shared types (no duplication). Authoritative
intermediates come straight from the substrate execution; nothing is re-derived here, and there is no narration
(Milestone B is pre-narration). A direct-formula example is a three-transition trace:
identify_knowns -> substitute -> compute(terminal).
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from app.services.examples.runtime_binding.binding import ValidatedBinding
from app.services.examples.runtime_binding.generation import GeneratedInstance
from app.services.examples.trace_adapters.artifacts import (
    LessonIntent,
    TeachingCheckpoint,
    TeachingProjection,
)
from app.services.examples.trace_contract import ContractTrace, Step, fact


@dataclass(frozen=True)
class TraceBundle:
    trace: ContractTrace
    projection: TeachingProjection
    checkpoints: tuple[TeachingCheckpoint, ...]


def _substituted_expression(binding: ValidatedBinding, visible: dict[str, Fraction]) -> str:
    """Reviewed relationship source with each input symbol shown as its sampled value (display only)."""
    source = binding.contract.relationship.expression_source
    # longest names first so a short name is not replaced inside a longer one
    for symbol in sorted(visible, key=len, reverse=True):
        source = source.replace(symbol, str(visible[symbol]))
    return source


def build_trace_bundle(
    binding: ValidatedBinding,
    instance: GeneratedInstance,
    intent: LessonIntent | None = None,
) -> TraceBundle:
    contract = binding.contract
    visible = instance.visible_fractions()
    output = contract.output
    result = Fraction(instance.expected_result)
    given_pairs = ", ".join(f"{s.symbol} = {visible[s.symbol]} {s.unit}".rstrip() for s in contract.input_symbols)
    relationship = contract.relationship.expression_source
    substituted = _substituted_expression(binding, visible)

    knowns_state = {s.symbol: str(visible[s.symbol]) for s in contract.input_symbols}
    substituted_state = {**knowns_state, "expression": substituted}
    final_state = {**substituted_state, output.symbol: instance.result_display, "complete": True}

    steps = [
        Step(
            id="s1", operation="identify_knowns",
            prior_state={}, state_after=dict(knowns_state),
            inputs=dict(knowns_state),
            decision=f"knowns: {given_pairs}",
            reason=f"Read the given quantities: {given_pairs}.",
            expected_visible_result=f"Knowns: {given_pairs}.",
            facts={"allowed_values": [], "required_facts": [fact(s.symbol, str(visible[s.symbol])) for s in contract.input_symbols], "forbidden_claims": []},
        ),
        Step(
            id="s2", operation="substitute",
            prior_state=dict(knowns_state), state_after=dict(substituted_state),
            inputs={"relationship": relationship},
            decision=f"{output.symbol} = {substituted}",
            reason=f"Substitute the knowns into {output.symbol} = {relationship}.",
            expected_visible_result=f"{output.symbol} = {substituted}.",
            facts={"allowed_values": [], "required_facts": [fact("expression", substituted)], "forbidden_claims": []},
        ),
        Step(
            id="s3", operation="compute",
            prior_state=dict(substituted_state), state_after=dict(final_state),
            inputs={"expression": substituted},
            decision=f"{output.symbol} = {instance.result_display} {output.unit}".rstrip(),
            reason=f"Evaluate to get {output.symbol} = {instance.result_display} {output.unit}.".rstrip(),
            expected_visible_result=f"{output.symbol} = {instance.result_display} {output.unit}. This is the final result.".rstrip(),
            facts={"allowed_values": [], "required_facts": [fact(output.symbol, instance.result_display)], "forbidden_claims": []},
        ),
    ]

    trace = ContractTrace(
        problem=f"{contract.definition.normalized_value} Find {output.meaning} ({output.symbol}).",
        conventions={c.artifact_id: c.normalized_value for c in contract.conventions},
        initial_state={s.symbol: None for s in contract.input_symbols} | {output.symbol: None, "complete": False},
        final_answer={output.symbol: str(result), "display": instance.result_display, "unit": output.unit},
        steps=steps,
        invariants=[{"id": "result_recomputes", "scope": "terminal_only",
                     "statement": "the displayed result recomputes exactly from the visible givens"}],
        required_cases=["identify_knowns", "substitute", "completion"],
        case_evidence={"identify_knowns": ["s1"], "substitute": ["s2"], "completion": ["s3"]},
        provenance={
            "route": "runtime_binding",
            "contract_id": contract.contract_id,
            "binding_digest": binding.binding_digest,
            "instance_digest": instance.instance_digest,
        },
    )

    projection = TeachingProjection(
        transition_ids=["s1", "s2", "s3"],
        required_transition_ids=["s1", "s3"],
        terminal_transition_id="s3",
        step_kinds={"s1": "identify_knowns", "s2": "substitute", "s3": "compute"},
        label_convention="ints",
    )
    checkpoints = tuple(
        TeachingCheckpoint(
            checkpoint_id=f"cp_{s.id}",
            source_step_ids=[s.id],
            visible_transition=s.operation,
            state_before_step_id=s.id,
            state_after_step_id=s.id,
            source_step_start=s.id,
            source_step_end=s.id,
            required_cases_covered=[c for c, ev in trace.case_evidence.items() if s.id in ev],
        )
        for s in steps
    )
    return TraceBundle(trace=trace, projection=projection, checkpoints=checkpoints)
