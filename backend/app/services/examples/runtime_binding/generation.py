"""Deterministic seeded instance generation (spec §5.8).

The reviewed grammar owns instance generation; no model chooses authoritative values. Sampling is seeded and
reproducible: the same (binding_digest, seed) yields the same instance. Instance generation owns only
value-level quality — domain validity, nontriviality, readability, rounding stability — because the visible
problem statement does not exist yet (solvability/fitness against the assembled problem are later stages).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
from typing import Literal

from app.services.examples.runtime_binding.binding import ValidatedBinding
from app.services.examples.runtime_binding.executor import ExecutionError, ExecutionResult, execute_descriptor
from app.services.examples.runtime_binding.pedagogy import (
    DEFAULT_PEDAGOGICAL_POLICY,
    PedagogicalPolicy,
    nontrivial_inputs,
    readable_result,
)


class GenerationError(ValueError):
    pass


@dataclass(frozen=True)
class GenerationPolicy:
    policy_id: str = "direct_formula_seeded_v1"
    version: int = 1
    max_generation_attempts: int = 64


@dataclass(frozen=True)
class InstanceQualityResult:
    domain_validity: Literal["passed", "failed"]
    nontriviality: Literal["passed", "failed"]
    visible_number_readability: Literal["passed", "failed"]
    rounding_stability: Literal["passed", "failed"]
    failures: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.failures


@dataclass(frozen=True)
class GeneratedInstance:
    binding_digest: str
    seed: int
    generation_policy_id: str
    generation_policy_version: int
    pedagogical_policy_version: int
    visible_values: tuple[tuple[str, str], ...]     # (symbol, exact fraction string) — sorted
    numeric_policy_ref: str
    expected_result: str                            # exact fraction string of the output value
    result_display: str                             # rounded decimal display of the output
    quality: InstanceQualityResult
    instance_digest: str

    def visible_fractions(self) -> dict[str, Fraction]:
        return {name: Fraction(value) for name, value in self.visible_values}


def _seeded_int(binding_digest: str, seed: int, symbol: str, lo: int, hi: int) -> int:
    if hi < lo:
        raise GenerationError(f"empty domain for {symbol}: [{lo}, {hi}]")
    digest = hashlib.sha256(f"{binding_digest}|{seed}|{symbol}".encode("utf-8")).hexdigest()
    span = hi - lo + 1
    return lo + (int(digest, 16) % span)


def _display(value: Fraction, places: int = 6) -> str:
    """Round to `places` decimals at the display boundary only, trimming trailing zeros. Exact arithmetic
    stays in Fraction; this is the single display-rounding point (spec §5.7 numeric policy)."""
    quantized = (Decimal(value.numerator) / Decimal(value.denominator)).quantize(Decimal(10) ** -places)
    text = format(quantized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _sample_values(binding: ValidatedBinding, seed: int) -> dict[str, Fraction]:
    values: dict[str, Fraction] = {}
    for symbol in binding.contract.input_symbols:
        lo = int(symbol.domain_min) if symbol.domain_min is not None else 1
        hi = int(symbol.domain_max) if symbol.domain_max is not None else max(lo, 12)
        values[symbol.symbol] = Fraction(_seeded_int(binding.binding_digest, seed, symbol.symbol, lo, hi))
    return values


def _assess_quality(
    binding: ValidatedBinding,
    visible: dict[str, Fraction],
    execution: ExecutionResult | None,
    ped: PedagogicalPolicy,
    exec_error: str | None,
) -> InstanceQualityResult:
    failures: list[str] = []
    domain = "passed"
    if exec_error is not None:
        domain = "failed"
        failures.append(f"domain:{exec_error}")
    nontrivial = "passed" if nontrivial_inputs(ped, visible) else "failed"
    if nontrivial == "failed":
        failures.append("nontriviality")
    readable = "passed"
    rounding = "passed"
    if execution is not None:
        if not readable_result(ped, execution.value):
            readable = "failed"
            failures.append("readability")
        # rounding stability: displayed value re-parses to within 1e-6 of exact
        disp = _display(execution.value)
        if abs(Fraction(Decimal(disp)) - execution.value) > Fraction(1, 10**6):
            rounding = "failed"
            failures.append("rounding_stability")
    return InstanceQualityResult(domain, nontrivial, readable, rounding, tuple(failures))


def _instance_digest(
    binding: ValidatedBinding,
    seed: int,
    gen: GenerationPolicy,
    ped: PedagogicalPolicy,
    visible: dict[str, Fraction],
    expected: Fraction,
    quality: InstanceQualityResult,
) -> str:
    payload = {
        "binding_digest": binding.binding_digest,
        "execution_environment": binding.descriptor.numeric_policy_ref,
        "seed": seed,
        "generation_policy": [gen.policy_id, gen.version],
        "pedagogical_policy_version": ped.version,
        "visible_values": {k: [str(v.numerator), str(v.denominator)] for k, v in sorted(visible.items())},
        "expected_result": [str(expected.numerator), str(expected.denominator)],
        "quality_passed": quality.passed,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def generate_instance(
    binding: ValidatedBinding,
    seed: int,
    *,
    generation_policy: GenerationPolicy | None = None,
    pedagogical_policy: PedagogicalPolicy | None = None,
) -> GeneratedInstance:
    """Deterministically generate the first quality-passing instance at or after `seed`. Reproducible:
    same (binding_digest, seed) -> identical instance. Raises if no attempt within the policy budget passes."""
    gen = generation_policy or GenerationPolicy()
    ped = pedagogical_policy or DEFAULT_PEDAGOGICAL_POLICY
    for attempt in range(gen.max_generation_attempts):
        candidate_seed = seed + attempt
        visible = _sample_values(binding, candidate_seed)
        execution: ExecutionResult | None = None
        exec_error: str | None = None
        try:
            execution = execute_descriptor(binding.descriptor, {k: v for k, v in visible.items()})
        except ExecutionError as exc:
            exec_error = str(exc)
        quality = _assess_quality(binding, visible, execution, ped, exec_error)
        if quality.passed and execution is not None:
            expected = execution.value
            return GeneratedInstance(
                binding_digest=binding.binding_digest,
                seed=candidate_seed,
                generation_policy_id=gen.policy_id,
                generation_policy_version=gen.version,
                pedagogical_policy_version=ped.version,
                visible_values=tuple(sorted((k, str(v)) for k, v in visible.items())),
                numeric_policy_ref=binding.descriptor.numeric_policy_ref,
                expected_result=str(expected),
                result_display=_display(expected),
                quality=quality,
                instance_digest=_instance_digest(binding, candidate_seed, gen, ped, visible, expected, quality),
            )
    raise GenerationError(
        f"{binding.contract.contract_id}: no quality-passing instance within {gen.max_generation_attempts} attempts"
    )
