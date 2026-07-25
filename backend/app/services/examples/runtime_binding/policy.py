"""Versioned Milestone A policy identities and deterministic execution-input hashing."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from fractions import Fraction
from typing import Mapping

NUMERIC_UNIT_POLICY = {
    "version": "rational_multiplicative_units_v1",
    "numeric": "Fraction",
    "max_ast_nodes": 128,
    "max_ast_depth": 24,
    "max_abs_integer": 10**12,
    "max_power": 12,
    "max_fraction_bits": 4096,
    "affine_units": False,
    "percentage_input_convention": "legacy_percentage_points",
}


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def numeric_unit_policy_digest() -> str:
    return hashlib.sha256(_canonical_json(NUMERIC_UNIT_POLICY).encode("utf-8")).hexdigest()


def _exact(value: int | str | Decimal | Fraction) -> dict[str, str]:
    fraction = value if isinstance(value, Fraction) else Fraction(value)
    return {"numerator": str(fraction.numerator), "denominator": str(fraction.denominator)}


def execution_input_digest(
    relationship_id: str,
    inputs: Mapping[str, int | str | Decimal | Fraction],
) -> str:
    payload = {
        "relationship_id": relationship_id,
        "inputs": {name: _exact(inputs[name]) for name in sorted(inputs)},
        "numeric_unit_policy_digest": numeric_unit_policy_digest(),
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
