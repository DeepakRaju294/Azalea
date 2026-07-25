"""Canonical serialization + fingerprint construction (§5, §5.1).

`hash_canonical` is the versioned, collision-resistant hash the whole safety model depends on. Rules (spec §5):
a SCHEMA NAMESPACE + version in the preimage (so two different object kinds with identical fields never
collide); canonical JSON; UTF-8; Unicode NFC; sorted object keys; decimal STRINGS not binary floats; canonical
negative zero; NaN/Infinity forbidden; type-tagged values; named hash algorithm.

Identity policy (which changes preserve vs change identity) is realized in `build_instance_fingerprints`:
- PRESERVES the semantic identities: reordering givens, whitespace, cosmetic number formatting (0.50==0.5).
- CHANGES them: a different target quantity or assumptions (execution_contract); a changed expected value or
  REQUIRED rounding (answer_semantics); a changed tolerance (comparison_policy).
- `presentation` captures RAW wording/formatting, so a cosmetic change moves presentation while the semantic
  identities stay put (A59). A tolerance change moves comparison_policy (hence evidence_subject) but not the
  execution/answer semantics (A60).
Symbol renaming normalized by ROLE is DEFERRED (needs the role model, 1D/1E); until then a rename changes
execution_contract (the safe direction: a miss, never a false reuse).
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from app.services.examples.retrieval.model import PublishedInstance
from app.services.examples.retrieval_verify import extract_magnitude, extract_unit

HASH_VERSION = "rge-hash/v1"


class CanonicalizationError(ValueError):
    pass


def _num_str(x: float | int | Decimal) -> str:
    try:
        d = Decimal(str(x))
    except InvalidOperation as exc:  # noqa: BLE001
        raise CanonicalizationError(f"not a number: {x!r}") from exc
    if d.is_nan() or d.is_infinite():
        raise CanonicalizationError("NaN/Infinity not encodable")
    if d == 0:
        d = Decimal(0)                 # canonical zero, kills -0
    d = d.normalize()
    s = format(d, "f")                 # fixed-point, no exponent form
    return "-0" if s == "-0" else s    # belt-and-suspenders


def _canon(v: Any) -> Any:
    """Type-tagged canonical form so a string never collides with an equal-looking number, etc."""
    if isinstance(v, bool):
        return ["b", v]
    if isinstance(v, (int, float, Decimal)):
        return ["n", _num_str(v)]
    if isinstance(v, str):
        return ["s", unicodedata.normalize("NFC", v)]
    if v is None:
        return ["null"]
    if isinstance(v, (list, tuple)):
        return ["a", [_canon(x) for x in v]]
    if isinstance(v, dict):
        return ["o", [[unicodedata.normalize("NFC", str(k)), _canon(v[k])] for k in sorted(v)]]
    raise CanonicalizationError(f"uncanonicalizable type {type(v).__name__}")


def hash_canonical(obj: Any, *, schema: str, version: str = HASH_VERSION) -> str:
    """SHA-256 hex of the canonical serialization, namespaced by (schema, version)."""
    preimage = ["o", [["body", _canon(obj)], ["schema", ["s", schema]], ["version", ["s", version]]]]
    blob = json.dumps(preimage, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class InstanceFingerprintSet:
    execution_contract: str
    answer_semantics: str
    comparison_policy: str
    evidence_subject: str
    presentation: str
    hash_version: str = HASH_VERSION

    @property
    def semantic(self) -> str:
        return hash_canonical({"execution_contract": self.execution_contract,
                               "answer_semantics": self.answer_semantics},
                              schema="instance-semantic/v1", version=self.hash_version)


def make_evidence_subject(fp: InstanceFingerprintSet, check_contract_version: str) -> str:
    """Bind instance + comparison policy + check contract (§5.1 issue 6): the same number under exact vs 5%
    tolerance can check differently, and the check contract defines what 'confirm' means."""
    return hash_canonical({"instance": fp.semantic, "comparison_policy": fp.comparison_policy,
                           "check_contract": check_contract_version},
                          schema="evidence-subject/v1", version=fp.hash_version)


def _canonical_inputs(inst: PublishedInstance) -> list[list[Any]]:
    # sort by name (reordering givens preserves identity); numbers pass through _num_str via _canon at hash time.
    return [[n, v] for n, v in sorted(inst.inputs, key=lambda p: p[0])]


def _sorted_assumptions(inst: PublishedInstance) -> list[list[Any]]:
    return [[a.key, a.value] for a in sorted(inst.assumptions, key=lambda a: a.key)]


def build_instance_fingerprints(inst: PublishedInstance, *, check_contract_version: str,
                                narration: str = "", version: str = HASH_VERSION) -> InstanceFingerprintSet:
    """Construct the instance fingerprint set from a PublishedInstance, realizing the identity policy above."""
    execution_contract = hash_canonical(
        {"target": inst.target, "inputs": [n for n, _ in sorted(inst.inputs, key=lambda p: p[0])],
         "unit_dimension": inst.comparison.unit_dimension, "assumptions": _sorted_assumptions(inst)},
        schema="execution-contract/v1", version=version)

    # cosmetic number formatting (0.50 vs 0.5) collapses: parse the published answer's magnitude to a number.
    ans_mag = extract_magnitude(inst.published_answer)
    ans_unit = extract_unit(inst.published_answer)
    answer_semantics = hash_canonical(
        {"inputs": _canonical_inputs(inst), "target": inst.target, "assumptions": _sorted_assumptions(inst),
         "answer_magnitude": ans_mag, "answer_unit": ans_unit,
         "required_rounding": inst.comparison.rounding_rule},
        schema="answer-semantics/v1", version=version)

    comparison_policy = hash_canonical(
        {"kind": inst.comparison.kind, "tolerance": inst.comparison.tolerance,
         "unit_semantics": inst.comparison.unit_semantics, "quantity_kind": inst.comparison.quantity_kind},
        schema="comparison-policy/v1", version=version)

    # presentation is RAW (no normalization) so any cosmetic change moves it while the semantics stay put (A59).
    presentation = hash_canonical({"problem_statement": inst.problem_statement, "narration": narration},
                                  schema="presentation/v1", version=version)

    fp = InstanceFingerprintSet(execution_contract=execution_contract, answer_semantics=answer_semantics,
                                comparison_policy=comparison_policy, evidence_subject="",
                                presentation=presentation, hash_version=version)
    # evidence_subject depends on semantic + comparison + check contract
    evidence_subject = make_evidence_subject(fp, check_contract_version)
    return InstanceFingerprintSet(execution_contract=execution_contract, answer_semantics=answer_semantics,
                                  comparison_policy=comparison_policy, evidence_subject=evidence_subject,
                                  presentation=presentation, hash_version=version)
