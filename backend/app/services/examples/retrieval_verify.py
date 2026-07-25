"""Phase 0 of retrieval-grounded worked-example verification — the OFFLINE verification core, no retrieval.

The bet behind the retrieval direction (Option 3 + verification) rests on one measurable question: when our
pipeline is handed a REAL problem whose published answer we already know, does it reproduce that answer? If it
does often enough, retrieval-of-known-examples + reproduction-check is a viable accuracy gate for no-adapter
topics; if it doesn't, no amount of retrieval plumbing helps. This module provides:

  * `reproduction_check` — the deterministic decision "does our produced final answer match a known answer",
    with numeric tolerance + scientific-notation/percent-convention normalization (reusing answer_anchor's
    tolerance philosophy so a display-rounding difference passes but a real error fails);
  * `KNOWN_ANSWER_FIXTURES` — hand-authored (problem, canonical formula, published answer) triples across
    formula domains that have NO live adapter, so the go/no-go can be measured offline against real content.

The checker is intentionally pure and API-key-free so it is unit-testable in isolation. Measuring the actual
reproduction HIT RATE requires running the live solver over the fixtures' problems (needs an API key) — that
is the Phase 0 go/no-go run, done separately; this module supplies both halves it compares.

Deliberately NOT here (they arrive with the retrieval wiring in Phase 1): source fetch, prose->expression
transcription, cross-source corroboration, and the span-grounding LLM verifier.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# "1.6 x 10^-19", "1.6 * 10 ** -19", "1.6X10^19" -> "1.6e-19" so ONE numeric regex handles sci notation.
# ASCII-only source (encoding-fragility rule): no unicode multiplication sign / superscripts.
_SCI_TO_E = re.compile(r"(?<=\d)\s*[xX*]\s*10\s*(?:\^|\*\*)\s*([-+]?\d+)")
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")
# a trailing unit token after the magnitude (V, J, s, Pa, N, A, ...) — recorded, not yet hard-enforced in v0.
# ASCII-only by rule; SI symbols with non-ASCII glyphs (ohm, degrees) are spelled out upstream, not matched here.
_UNIT = re.compile(r"-?\d[\d.,eE^*x+\- ]*\s*([A-Za-z][A-Za-z/^0-9]*)")


@dataclass(frozen=True)
class ReproResult:
    matched: Optional[bool]        # True/False, or None when a magnitude couldn't be extracted from one side
    known_value: Optional[float]
    produced_value: Optional[float]
    known_unit: str
    produced_unit: str
    detail: str

    @property
    def decisive(self) -> bool:
        return self.matched is not None


def _to_e_notation(s: str) -> str:
    return _SCI_TO_E.sub(lambda m: f"e{m.group(1)}", str(s))


def extract_magnitude(s: str) -> Optional[float]:
    """First numeric magnitude in a free-form answer string, scientific-notation aware. '1.6 x 10^-19 C',
    '100 V', '9.98e4 Pa', '1,102.50' -> the float. None when there is no number."""
    if s is None:
        return None
    txt = _to_e_notation(str(s).replace(",", ""))
    m = _NUMBER.search(txt)
    return float(m.group()) if m else None


def extract_unit(s: str) -> str:
    if s is None:
        return ""
    m = _UNIT.search(_to_e_notation(str(s)))
    return m.group(1).strip() if m else ""


def _close_rel(x: float, y: float, rel_tol: float, abs_floor: float) -> bool:
    # 1% relative with a small absolute floor (answer_anchor's convention): tolerant of DISPLAY rounding
    # (99768 vs 9.98e4) but not of a real error (100 V vs 90 V).
    return abs(x - y) <= max(rel_tol * max(abs(x), abs(y)), abs_floor)


def reproduction_check(
    known_answer: str,
    produced_answer: str,
    *,
    rel_tol: float = 0.01,
    abs_floor: float = 0.01,
) -> ReproResult:
    """Does `produced_answer` reproduce the published `known_answer`? Magnitude comparison with relative
    tolerance, accepting the percent<->fraction convention (8.33 vs 0.0833) the answer anchor already accepts.
    matched=None (not False) when either side has no extractable number — an INDECISIVE result, so a caller
    that abstains-on-uncertainty never treats "couldn't compare" as "confirmed wrong"."""
    kv, pv = extract_magnitude(known_answer), extract_magnitude(produced_answer)
    ku, pu = extract_unit(known_answer), extract_unit(produced_answer)
    if kv is None or pv is None:
        which = "known" if kv is None else "produced"
        return ReproResult(None, kv, pv, ku, pu, f"no numeric magnitude in {which} answer")
    # same quantity under a different unit convention (percent vs fraction) counts as a match.
    matched = any(_close_rel(pv, kv * scale, rel_tol, abs_floor) for scale in (1.0, 100.0, 0.01))
    detail = ("within tolerance" if matched
              else f"magnitude mismatch: produced {pv} vs known {kv}")
    if matched and ku and pu and ku.lower() != pu.lower():
        detail = f"magnitude matched but UNIT differs (known {ku!r} vs produced {pu!r})"
    return ReproResult(matched, kv, pv, ku, pu, detail)


@dataclass(frozen=True)
class KnownAnswerFixture:
    concept: str
    domain: str
    problem: str
    canonical_formula: str
    known_answer: str


# Real, hand-verified (problem, formula, published answer) triples in formula domains with NO live adapter.
# Each answer is arithmetic-checkable from the stated inputs; the spread (EM / mechanics / finance / chem)
# is deliberate so the go/no-go hit rate isn't measured on one narrow family.
KNOWN_ANSWER_FIXTURES: tuple[KnownAnswerFixture, ...] = (
    KnownAnswerFixture(
        "motional_emf", "electromagnetism",
        "A conducting rod of length 0.2 m moves at 10 m/s perpendicular to a 0.5 T magnetic field. "
        "Find the induced EMF.",
        "emf = B * L * v", "1.0 V"),
    KnownAnswerFixture(
        "faraday_emf", "electromagnetism",
        "A 200-turn coil experiences a magnetic flux change of 0.05 Wb over 0.1 s. "
        "Find the magnitude of the induced EMF.",
        "emf = N * dPhi / dt", "100 V"),
    KnownAnswerFixture(
        "inductor_energy", "electromagnetism",
        "How much energy is stored in a 2 H inductor carrying a steady current of 3 A?",
        "E = 0.5 * L * I**2", "9 J"),
    KnownAnswerFixture(
        "rl_time_constant", "electromagnetism",
        "A series RL circuit has L = 10 H and R = 5 ohm. Find its time constant.",
        "tau = L / R", "2 s"),
    KnownAnswerFixture(
        "capacitor_energy", "electromagnetism",
        "Find the energy stored in a 2 F capacitor charged to 3 V.",
        "E = 0.5 * C * V**2", "9 J"),
    KnownAnswerFixture(
        "coulomb_force", "electromagnetism",
        "Two point charges of 1 C each are separated by 1 m in vacuum. Find the electrostatic force "
        "(k = 8.99e9 N m^2/C^2).",
        "F = k * q1 * q2 / r**2", "8.99e9 N"),
    KnownAnswerFixture(
        "kinetic_energy", "mechanics",
        "Find the kinetic energy of a 2 kg object moving at 3 m/s.",
        "KE = 0.5 * m * v**2", "9 J"),
    KnownAnswerFixture(
        "ohms_law", "circuits",
        "A 12 V source drives a 4 ohm resistor. Find the current.",
        "I = V / R", "3 A"),
    KnownAnswerFixture(
        "compound_interest", "finance",
        "1000 dollars is invested at 5% annual interest compounded yearly. Find the balance after 2 years.",
        "A = P * (1 + r)**t", "1102.50"),
    KnownAnswerFixture(
        "ideal_gas_pressure", "chemistry",
        "One mole of an ideal gas occupies 0.025 m^3 at 300 K (R = 8.314 J/mol/K). Find the pressure.",
        "P = n * R * T / Vol", "9.98e4 Pa"),
)
