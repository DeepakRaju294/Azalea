"""Small reviewed multiplicative unit registry for the Milestone A scalar substrate."""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping


class UnitError(ValueError):
    pass


@dataclass(frozen=True)
class Unit:
    scale_to_canonical: Fraction
    dimensions: tuple[tuple[str, Fraction], ...]
    display_symbol: str = ""

    @classmethod
    def make(cls, scale: Fraction | int, dimensions: Mapping[str, Fraction | int], symbol: str = "") -> "Unit":
        normalized = tuple(sorted((key, Fraction(value)) for key, value in dimensions.items() if value))
        return cls(Fraction(scale), normalized, symbol)

    def _dims(self) -> dict[str, Fraction]:
        return dict(self.dimensions)

    def multiply(self, other: "Unit") -> "Unit":
        dims = self._dims()
        for key, value in other.dimensions:
            dims[key] = dims.get(key, Fraction()) + value
        return Unit.make(self.scale_to_canonical * other.scale_to_canonical, dims)

    def divide(self, other: "Unit") -> "Unit":
        dims = self._dims()
        for key, value in other.dimensions:
            dims[key] = dims.get(key, Fraction()) - value
        return Unit.make(self.scale_to_canonical / other.scale_to_canonical, dims)

    def power(self, exponent: int) -> "Unit":
        return Unit.make(
            self.scale_to_canonical**exponent,
            {key: value * exponent for key, value in self.dimensions},
        )


DIMENSIONLESS = Unit.make(1, {})
_BASE = {
    "kg": Unit.make(1, {"mass": 1}),
    "m": Unit.make(1, {"length": 1}),
    "s": Unit.make(1, {"time": 1}),
    "A": Unit.make(1, {"current": 1}),
    "K": Unit.make(1, {"temperature": 1}),
    "mol": Unit.make(1, {"amount": 1}),
    "$": Unit.make(1, {"currency": 1}),
}
_REGISTRY = {
    **_BASE,
    "g": Unit.make(Fraction(1, 1000), {"mass": 1}),
    "L": Unit.make(Fraction(1, 1000), {"length": 3}),
    "mL": Unit.make(Fraction(1, 1_000_000), {"length": 3}),
    "Hz": Unit.make(1, {"time": -1}),
    "N": Unit.make(1, {"mass": 1, "length": 1, "time": -2}),
    "J": Unit.make(1, {"mass": 1, "length": 2, "time": -2}),
    "W": Unit.make(1, {"mass": 1, "length": 2, "time": -3}),
    "Pa": Unit.make(1, {"mass": 1, "length": -1, "time": -2}),
    "V": Unit.make(1, {"mass": 1, "length": 2, "time": -3, "current": -1}),
    "ohm": Unit.make(1, {"mass": 1, "length": 2, "time": -3, "current": -2}),
    "atm": Unit.make(101325, {"mass": 1, "length": -1, "time": -2}),
    "yr": Unit.make(31557600, {"time": 1}),
    "hr": Unit.make(3600, {"time": 1}),
    # Existing formulas represent percentages as percentage points and explicitly divide/multiply by 100.
    "%": DIMENSIONLESS,
    "deg": DIMENSIONLESS,
    "unit": DIMENSIONLESS,
    "units": DIMENSIONLESS,
    "sides": DIMENSIONLESS,
}
_TOKEN = re.compile(r"([A-Za-z$%]+)(?:\^(-?\d+))?")


def parse_unit(source: str) -> Unit:
    text = source.strip()
    if not text:
        return Unit.make(1, {}, source)
    if text in {"deg C", "deg F"}:
        raise UnitError(f"affine unit is outside Wave-0: {text}")
    text = text.replace("sq units", "units^2").replace("cubic units", "units^3")
    if "(" in text or ")" in text:
        # Parentheses are only needed by reviewed constant metadata; remove a single grouping layer.
        text = text.replace("(", "").replace(")", "")
    result = DIMENSIONLESS
    operation = "multiply"
    position = 0
    for match in _TOKEN.finditer(text):
        separator = text[position:match.start()]
        if separator:
            if separator not in {"*", "/"}:
                raise UnitError(f"unsupported unit syntax: {source!r}")
            operation = "divide" if separator == "/" else "multiply"
        token, exponent_text = match.groups()
        try:
            unit = _REGISTRY[token]
        except KeyError as exc:
            raise UnitError(f"unknown unit token: {token}") from exc
        exponent = int(exponent_text or "1")
        unit = unit.power(exponent)
        result = result.divide(unit) if operation == "divide" else result.multiply(unit)
        operation = "multiply"
        position = match.end()
    if position != len(text):
        raise UnitError(f"unsupported unit syntax: {source!r}")
    return Unit(result.scale_to_canonical, result.dimensions, source)
