"""Versioned pedagogical policy (spec §5.8).

Every fitness/solvability judgment is a DETERMINISTIC predicate over declared parameters — never a model call
(§6.6). A check whose parameters are absent is dropped from the profile, not delegated. Milestone B ships one
reviewed policy with concrete bounds; its version participates in digests and cache invalidation.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal


@dataclass(frozen=True)
class PedagogicalConstraint:
    constraint_id: str
    check_type: Literal["difficulty", "nontriviality", "readability", "objective_count"]
    parameters: tuple[tuple[str, str], ...]     # canonical (key, str-value) pairs
    severity: Literal["blocking", "warning"] = "blocking"

    def get(self, key: str) -> str | None:
        return dict(self.parameters).get(key)


@dataclass(frozen=True)
class PedagogicalPolicy:
    policy_id: str
    version: int
    constraints: tuple[PedagogicalConstraint, ...]

    def of_type(self, check_type: str) -> PedagogicalConstraint | None:
        return next((c for c in self.constraints if c.check_type == check_type), None)


DEFAULT_PEDAGOGICAL_POLICY = PedagogicalPolicy(
    policy_id="direct_formula_intro_v1",
    version=1,
    constraints=(
        PedagogicalConstraint(
            "nontriviality_v1", "nontriviality",
            (("min_distinct_inputs", "1"), ("forbid_all_unit_inputs", "true")),
        ),
        PedagogicalConstraint(
            "readability_v1", "readability",
            (("max_result_denominator", "1000"), ("max_abs_result_numerator_digits", "9")),
        ),
        PedagogicalConstraint(
            "objective_count_v1", "objective_count", (("max_primary_outputs", "1"),),
        ),
        PedagogicalConstraint(
            "difficulty_v1", "difficulty",
            (("min_inputs_for_deep", "2"), ("max_inputs", "6")),
        ),
    ),
)


def readable_result(policy: PedagogicalPolicy, value: Fraction) -> bool:
    c = policy.of_type("readability")
    if c is None:
        return True
    max_den = int(c.get("max_result_denominator") or "1000")
    max_digits = int(c.get("max_abs_result_numerator_digits") or "9")
    return value.denominator <= max_den and len(str(abs(value.numerator))) <= max_digits


def nontrivial_inputs(policy: PedagogicalPolicy, visible: dict[str, Fraction]) -> bool:
    c = policy.of_type("nontriviality")
    if c is None:
        return True
    if (c.get("forbid_all_unit_inputs") or "").lower() == "true":
        if all(v == 1 for v in visible.values()):
            return False
    min_distinct = int(c.get("min_distinct_inputs") or "1")
    return len({v for v in visible.values()}) >= min_distinct
