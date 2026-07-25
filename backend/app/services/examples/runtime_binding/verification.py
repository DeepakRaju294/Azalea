"""Verification model (spec §6) for offline runtime binding.

Verification is a VECTOR, not a boolean. The v1 assurance profile requires resolution validity
(`reviewed_match`), specification validity, execution validity (independent recomputation via the substrate),
problem solvability (visible givens recompute the answer), pedagogical fitness, and at least one deterministic
property/metamorphic check. Honesty (§6): recomputation catches tampering and executor bugs, NOT a wrong
reviewed formula — conceptual correctness rests on contract review. `narration_fidelity` is `not_run` in this
pre-narration milestone.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from app.services.examples.runtime_binding.binding import ValidatedBinding
from app.services.examples.runtime_binding.executor import ExecutionError, execute_descriptor
from app.services.examples.runtime_binding.generation import GeneratedInstance
from app.services.examples.runtime_binding.pedagogy import DEFAULT_PEDAGOGICAL_POLICY, PedagogicalPolicy
from app.services.examples.runtime_binding.trace import TraceBundle

CheckStatus = Literal["passed", "failed", "not_applicable"]


@dataclass(frozen=True)
class VerificationCheck:
    check_id: str
    check_type: Literal["recomputation", "domain", "property", "metamorphic", "solvability", "fitness", "replay"]
    status: CheckStatus
    detail: str = ""


@dataclass(frozen=True)
class VerificationVector:
    resolution_validity: str
    specification_validity: CheckStatus
    execution_validity: CheckStatus
    conceptual_validity: str
    problem_solvability: CheckStatus
    pedagogical_fitness: CheckStatus
    narration_fidelity: Literal["passed", "failed", "not_run"]
    checks: tuple[VerificationCheck, ...]

    @property
    def passed(self) -> bool:
        return (
            self.resolution_validity == "reviewed_match"
            and self.specification_validity == "passed"
            and self.execution_validity == "passed"
            and self.problem_solvability == "passed"
            and self.pedagogical_fitness == "passed"
            and all(c.status != "failed" for c in self.checks)
        )


def _recompute(binding: ValidatedBinding, visible: dict[str, Fraction]) -> Fraction:
    return execute_descriptor(binding.descriptor, {k: v for k, v in visible.items()}).value


def _proportionality_checks(
    binding: ValidatedBinding, visible: dict[str, Fraction], base: Fraction
) -> list[VerificationCheck]:
    """Deterministic metamorphic: for each input, scaling it must change the output (nontriviality); if
    scaling by 2 and 3 exactly doubles/triples the output, the input is an exact multiplicative factor."""
    checks: list[VerificationCheck] = []
    changed_any = False
    for name in sorted(visible):
        scaled2 = dict(visible)
        scaled2[name] = visible[name] * 2
        try:
            out2 = _recompute(binding, scaled2)
        except ExecutionError as exc:
            checks.append(VerificationCheck(f"perturb:{name}", "metamorphic", "failed", f"scale-2 error: {exc}"))
            continue
        if out2 != base:
            changed_any = True
        if base != 0 and out2 == base * 2:
            scaled3 = dict(visible)
            scaled3[name] = visible[name] * 3
            out3 = _recompute(binding, scaled3)
            status = "passed" if out3 == base * 3 else "failed"
            checks.append(VerificationCheck(f"proportional:{name}", "metamorphic", status,
                                            "output scales exactly with the input"))
    checks.append(VerificationCheck(
        "perturbation_sensitivity", "property",
        "passed" if changed_any else "failed",
        "at least one input perturbation changes the output",
    ))
    return checks


def _solvability(binding: ValidatedBinding, instance: GeneratedInstance, bundle: TraceBundle) -> list[VerificationCheck]:
    contract = binding.contract
    visible = instance.visible_fractions()
    checks: list[VerificationCheck] = []
    # every relationship free symbol resolves to a visible given or a reviewed constant
    from app.services.examples.runtime_binding.restricted_expression import expression_variables
    free = expression_variables(binding.descriptor.expression)
    constants = {c.symbol for c in binding.descriptor.constants}
    unresolved = sorted(free - set(visible) - constants)
    checks.append(VerificationCheck(
        "symbols_visible", "solvability",
        "passed" if not unresolved else "failed",
        "" if not unresolved else f"unresolved symbols: {unresolved}",
    ))
    # display unit present + single requested output
    checks.append(VerificationCheck(
        "output_unambiguous", "solvability",
        "passed" if contract.output.unit is not None and bundle.projection.terminal_transition_id else "failed",
    ))
    # visible givens recompute the displayed answer
    recomputed = _recompute(binding, visible)
    checks.append(VerificationCheck(
        "givens_recompute_answer", "solvability",
        "passed" if recomputed == Fraction(instance.expected_result) else "failed",
    ))
    return checks


def run_verification(
    binding: ValidatedBinding,
    instance: GeneratedInstance,
    bundle: TraceBundle,
    *,
    pedagogical_policy: PedagogicalPolicy | None = None,
) -> VerificationVector:
    ped = pedagogical_policy or DEFAULT_PEDAGOGICAL_POLICY
    visible = instance.visible_fractions()
    checks: list[VerificationCheck] = []

    # specification validity — the descriptor compiled + slots agree with the grammar
    spec_ok = (
        binding.proposal.grammar_id == binding.grammar.grammar_id
        and binding.descriptor.output_symbol == binding.contract.output.symbol
    )

    # execution validity: independent recomputation + deterministic replay + terminal reached
    recomputed = _recompute(binding, visible)
    replay = _recompute(binding, visible)
    exec_ok = recomputed == Fraction(instance.expected_result) and replay == recomputed
    terminal_step = bundle.trace.by_id(bundle.projection.terminal_transition_id)
    terminal_ok = bool(terminal_step and terminal_step.state_after.get("complete") is True)
    checks.append(VerificationCheck("recomputation", "recomputation", "passed" if exec_ok else "failed"))
    checks.append(VerificationCheck("deterministic_replay", "replay", "passed" if replay == recomputed else "failed"))
    checks.append(VerificationCheck("terminal_reached", "domain", "passed" if terminal_ok else "failed"))

    # property + metamorphic
    checks.extend(_proportionality_checks(binding, visible, recomputed))

    # solvability
    solvability_checks = _solvability(binding, instance, bundle)
    checks.extend(solvability_checks)
    solvable = all(c.status == "passed" for c in solvability_checks)

    # pedagogical fitness: instance quality + one-primary-output + difficulty band
    n_inputs = len(binding.contract.input_symbols)
    diff = ped.of_type("difficulty")
    max_inputs = int(diff.get("max_inputs")) if diff and diff.get("max_inputs") else 6
    fitness_ok = instance.quality.passed and n_inputs <= max_inputs
    checks.append(VerificationCheck(
        "pedagogical_fitness", "fitness", "passed" if fitness_ok else "failed",
        "" if fitness_ok else f"quality={instance.quality.passed} inputs={n_inputs}",
    ))

    return VerificationVector(
        resolution_validity=binding.resolution.resolution_validity,
        specification_validity="passed" if spec_ok else "failed",
        execution_validity="passed" if (exec_ok and terminal_ok) else "failed",
        conceptual_validity="reviewed_match",   # reviewed contract; not an independent-oracle claim (§6 honesty)
        problem_solvability="passed" if solvable else "failed",
        pedagogical_fitness="passed" if fitness_ok else "failed",
        narration_fidelity="not_run",
        checks=tuple(checks),
    )
