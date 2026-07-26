"""AnswerComparison-driven comparison engine (§5 issue 14).

`reproduction_check` (Phase 0) is magnitude + unit only. This honors the answer's full comparison CONTRACT:
the comparison KIND (exact / relative / absolute tolerance), unit semantics + allowed units, and SAFE handling
of the forms v1 cannot yet judge (set / interval / symbolic / vector / complex / angle-mod-2pi) — those return
INDECISIVE, never a false confirm. Three-valued throughout (confirm | refute | indecisive), unit rule from
§reproduction issue 13 (numeric+unit_mismatch => refute).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.services.examples.retrieval.model import AnswerComparison
from app.services.examples.retrieval_verify import _close_rel, extract_magnitude, extract_unit

ComparisonStatus = Literal["confirm", "refute", "indecisive"]

# forms the v1 numeric engine cannot safely judge -> indecisive (a stronger verifier handles them later)
_UNSUPPORTED_KINDS = {"symbolic_equivalence", "unordered_set", "interval", "textual_enum", "vector",
                      "complex", "angle_mod_2pi"}


@dataclass(frozen=True)
class ComparisonOutcome:
    status: ComparisonStatus
    detail: str


def _unit_ok(produced_unit: str, comparison: AnswerComparison) -> Literal["match", "mismatch", "unknown"]:
    if comparison.unit_semantics == "dimensionless" or comparison.unit_dimension == "":
        return "match"                       # no unit expected
    if not produced_unit:
        return "unknown"
    accepted = {u.lower() for u in comparison.allowed_units} | {comparison.unit_dimension.lower()}
    return "match" if produced_unit.lower() in accepted else "mismatch"


def compare_answer(published: str, produced: str, comparison: AnswerComparison) -> ComparisonOutcome:
    """Judge `produced` against `published` under the comparison contract. Never a false confirm: any form or
    input it can't decide returns `indecisive`."""
    if comparison.kind in _UNSUPPORTED_KINDS:
        return ComparisonOutcome("indecisive", f"comparison kind {comparison.kind!r} not judged by v1 engine")

    pub_mag, prod_mag = extract_magnitude(published), extract_magnitude(produced)
    if pub_mag is None or prod_mag is None:
        return ComparisonOutcome("indecisive", "a magnitude could not be extracted")

    if comparison.kind == "absolute_tolerance":
        try:
            tol = float(comparison.tolerance) if comparison.tolerance else 0.0
        except (TypeError, ValueError):
            tol = 0.0
        mag_ok = abs(prod_mag - pub_mag) <= tol
    else:  # exact_numeric | relative_tolerance
        try:
            rel = float(comparison.tolerance) if (comparison.kind == "relative_tolerance"
                                                  and comparison.tolerance) else 0.0
        except (TypeError, ValueError):
            rel = 0.0
        # exact_numeric -> rel 0 with a tiny absolute floor; relative -> the stated tolerance + percent/fraction
        mag_ok = any(_close_rel(prod_mag, pub_mag * s, rel, 1e-9 if comparison.kind == "exact_numeric" else 0.01)
                     for s in ((1.0,) if comparison.kind == "exact_numeric" else (1.0, 100.0, 0.01)))

    if not mag_ok:
        return ComparisonOutcome("refute", f"magnitude mismatch: produced {prod_mag} vs published {pub_mag}")

    unit = _unit_ok(extract_unit(produced), comparison)
    if unit == "mismatch":
        return ComparisonOutcome("refute", "magnitude agrees but unit is wrong")
    if unit == "unknown":
        return ComparisonOutcome("indecisive", "magnitude agrees but produced unit is unknown")
    return ComparisonOutcome("confirm", "within comparison contract")
