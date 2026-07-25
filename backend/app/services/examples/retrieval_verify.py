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
    matched: Optional[bool]        # True (confirm) / False (refute) / None (indecisive — cannot judge)
    known_value: Optional[float]
    produced_value: Optional[float]
    known_unit: str
    produced_unit: str
    unit_status: str               # "match" | "mismatch" | "unknown"  (external review issue 13)
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


def _unit_status(known_unit: str, produced_unit: str) -> str:
    if not known_unit or not produced_unit:
        return "unknown"
    return "match" if known_unit.lower() == produced_unit.lower() else "mismatch"


def reproduction_check(
    known_answer: str,
    produced_answer: str,
    *,
    rel_tol: float = 0.01,
    abs_floor: float = 0.01,
    require_unit_match: bool = True,
) -> ReproResult:
    """Does `produced_answer` reproduce the published `known_answer`? Magnitude comparison with relative
    tolerance, accepting the percent<->fraction convention (8.33 vs 0.0833) the answer anchor already accepts.

    Three-valued by design (external review issue 13 — a magnitude match with the WRONG unit is not a
    reproduction: 1 J vs 1 W, 1 m vs 1 cm, 20% vs 0.20 rad/s vs Hz):
      * matched=True  (CONFIRM)   magnitudes agree AND (unit matches OR unit unknown-and-not-required)
      * matched=False (REFUTE)    magnitudes disagree, OR magnitudes agree but units KNOWN-MISMATCH
      * matched=None  (INDECISIVE) a magnitude can't be extracted, or a required unit is UNKNOWN
    `require_unit_match=True` (default, safe) treats an unknown unit as indecisive rather than a silent pass;
    a caller with a trusted unit-free numeric context can relax it. INDECISIVE is never treated as confirmed
    or refuted, so "couldn't compare" never becomes "confirmed" nor "confirmed wrong"."""
    kv, pv = extract_magnitude(known_answer), extract_magnitude(produced_answer)
    ku, pu = extract_unit(known_answer), extract_unit(produced_answer)
    ustat = _unit_status(ku, pu)
    if kv is None or pv is None:
        which = "known" if kv is None else "produced"
        return ReproResult(None, kv, pv, ku, pu, ustat, f"no numeric magnitude in {which} answer")
    mag_ok = any(_close_rel(pv, kv * scale, rel_tol, abs_floor) for scale in (1.0, 100.0, 0.01))
    if not mag_ok:
        return ReproResult(False, kv, pv, ku, pu, ustat, f"magnitude mismatch: produced {pv} vs known {kv}")
    # magnitude agrees — now the unit decides confirm vs refute vs indecisive.
    if ustat == "mismatch":
        return ReproResult(False, kv, pv, ku, pu, ustat,
                           f"magnitude agrees but UNIT differs (known {ku!r} vs produced {pu!r}) -> refuted")
    if ustat == "unknown" and require_unit_match:
        return ReproResult(None, kv, pv, ku, pu, ustat,
                           "magnitude agrees but a unit is unknown; require_unit_match -> indecisive")
    return ReproResult(True, kv, pv, ku, pu, ustat, "within tolerance; unit " + ustat)


@dataclass(frozen=True)
class KnownAnswerFixture:
    concept: str
    domain: str
    problem: str
    canonical_formula: str
    known_answer: str


# --- adversarial CHECKER corpus (spec §17, external-review "fixture classes") -------------------------------
# These test reproduction_check's DECISION on hard inputs OFFLINE (no solver, no API key): a (published,
# produced) pair with the status the checker must return. The safety-critical property is asymmetric — a false
# REJECT (refuting/indecisive on a truly-correct answer) only costs coverage, but a false CONFIRM (confirming a
# WRONG answer) is the failure the whole system exists to prevent. `produced_is_correct=False` marks a pair
# whose produced value is genuinely wrong for the published quantity; if the checker CONFIRMS such a pair that
# is a false confirmation, and a `critical`-severity one must block G0 even if aggregate numbers look fine.
CheckStatus = str  # "confirm" | "refute" | "indecisive"


@dataclass(frozen=True)
class CheckerCase:
    case_id: str
    fixture_class: str
    published: str
    produced: str
    produced_is_correct: bool
    expected: CheckStatus
    severity: str                 # "low" | "medium" | "high" | "critical"
    require_unit_match: bool = True


CHECKER_CASES: tuple[CheckerCase, ...] = (
    CheckerCase("clean_ok", "clean_numeric", "100 V", "100 V", True, "confirm", "low"),
    CheckerCase("clean_round", "clean_numeric", "9.98e4 Pa", "99768 Pa", True, "confirm", "low"),
    CheckerCase("sci_form", "multiple_valid_forms", "8.99e9 N", "8.99 x 10^9 N", True, "confirm", "low"),
    CheckerCase("pct_frac", "multiple_valid_forms", "8.33", "0.0833", True, "confirm", "low", require_unit_match=False),
    # wrong ANSWER — must refute (a false confirm here = shipping a wrong number)
    CheckerCase("wrong_value", "wrong_answer", "100 V", "90 V", False, "refute", "critical"),
    CheckerCase("off_by_one", "wrong_answer", "42", "41", False, "refute", "high", require_unit_match=False),
    # same dimensions, WRONG coefficient (the dimensional check can't catch this — reproduction must)
    CheckerCase("wrong_coeff", "same_dims_wrong_coefficient", "9 J", "18 J", False, "refute", "critical"),
    # wrong QUANTITY, right magnitude — must refute (1 J vs 1 W, issue 13)
    CheckerCase("wrong_unit_power", "wrong_unit", "1 J", "1 W", False, "refute", "critical"),
    CheckerCase("wrong_unit_freq", "wrong_unit", "1 rad/s", "1 Hz", False, "refute", "high"),
    # unit CONVERSION the v0 checker does NOT perform — the SAFE direction is to refuse, not to guess-confirm.
    # produced IS correct, so this is an accepted (tracked) false REJECT, never a false confirm.
    CheckerCase("unit_conv_m_cm", "unit_conversion", "1 m", "100 cm", True, "refute", "low"),
    # unknown unit on the produced side -> indecisive under the safe default (never a silent pass)
    CheckerCase("unknown_unit", "ambiguous", "100 V", "100", True, "indecisive", "medium"),
    # non-numeric produced -> indecisive
    CheckerCase("non_numeric", "ambiguous", "100 V", "see the explanation", True, "indecisive", "low"),
)


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


@dataclass(frozen=True)
class CheckerResult:
    case: CheckerCase
    observed: CheckStatus
    matched_expectation: bool
    false_confirmation: bool       # confirmed a pair whose produced value is genuinely WRONG


def _status_of(matched: Optional[bool]) -> CheckStatus:
    return "confirm" if matched is True else ("refute" if matched is False else "indecisive")


def run_checker_corpus(cases: tuple[CheckerCase, ...] = CHECKER_CASES) -> dict[str, Any]:
    """Run the adversarial corpus through reproduction_check OFFLINE and report (spec §17 / external review
    issue 30): the confusion matrix of expected-vs-observed, per-class and per-severity tallies, and — the
    safety gate — every FALSE CONFIRMATION (a `confirm` on a genuinely-wrong pair). `blocking` is True if any
    CRITICAL-severity false confirmation exists; a caller (test or go/no-go) must fail when it is, regardless
    of how good the aggregate looks."""
    results: list[CheckerResult] = []
    confusion: dict[tuple[str, str], int] = {}
    for c in cases:
        r = reproduction_check(c.published, c.produced, require_unit_match=c.require_unit_match)
        observed = _status_of(r.matched)
        false_conf = (observed == "confirm") and (not c.produced_is_correct)
        results.append(CheckerResult(c, observed, observed == c.expected, false_conf))
        confusion[(c.expected, observed)] = confusion.get((c.expected, observed), 0) + 1
    false_confirmations = [x for x in results if x.false_confirmation]
    critical = [x for x in false_confirmations if x.case.severity == "critical"]
    return {
        "results": results,
        "confusion": confusion,
        "total": len(results),
        "matched": sum(1 for x in results if x.matched_expectation),
        "false_confirmations": false_confirmations,
        "critical_false_confirmations": critical,
        "blocking": bool(critical),
    }
