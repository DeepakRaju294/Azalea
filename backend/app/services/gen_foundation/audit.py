"""Bounded patch-only audit application (spec §8).

The auditor returns ``{status, edits[]}`` — only bounded patches, never a re-author.
This module applies those patches deterministically, enforces the edit budget (<=5
edits, <=2 structural, <=1 insert), rejects forbidden ops, and emits patch telemetry.
Re-validation of the patched artifact is the pipeline's job (§9): a patch that fails
post-audit validation is rejected and the first-pass output ships (never a 3rd pass).
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

ALLOWED_OPS: frozenset[str] = frozenset({
    "replace_field", "replace_fields", "merge_cards", "split_card",
    "delete_card", "insert_card", "update_state", "update_code_refs",
    "update_case_coverage", "pass_no_edits",
})
STRUCTURAL_OPS: frozenset[str] = frozenset({"merge_cards", "split_card", "delete_card", "insert_card"})

MAX_EDITS = 5
MAX_STRUCTURAL = 2
MAX_INSERT = 1


class PatchBudgetError(ValueError):
    """A patch set exceeds the §8 edit budget or uses a forbidden op."""


@dataclass
class AuditTelemetry:
    audit_status: str = "pass_no_edits"
    audit_trigger: str = "worked_example_required"
    patches_proposed: int = 0
    patches_applied: int = 0
    patches_rejected: int = 0
    rejection_reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "audit_status": self.audit_status,
            "audit_trigger": self.audit_trigger,
            "patches_proposed": self.patches_proposed,
            "patches_applied": self.patches_applied,
            "patches_rejected": self.patches_rejected,
            "rejection_reason": self.rejection_reason,
        }


def _check_budget(edits: list[dict[str, Any]]) -> None:
    if len(edits) > MAX_EDITS:
        raise PatchBudgetError(f"{len(edits)} edits > max {MAX_EDITS}")
    structural = sum(1 for e in edits if e.get("op") in STRUCTURAL_OPS)
    if structural > MAX_STRUCTURAL:
        raise PatchBudgetError(f"{structural} structural edits > max {MAX_STRUCTURAL}")
    inserts = sum(1 for e in edits if e.get("op") == "insert_card")
    if inserts > MAX_INSERT:
        raise PatchBudgetError(f"{inserts} inserts > max {MAX_INSERT}")
    for e in edits:
        if e.get("op") not in ALLOWED_OPS:
            raise PatchBudgetError(f"forbidden op {e.get('op')!r}")


def _index_by_id(cards: list[dict[str, Any]], card_id: Any) -> int:
    for i, c in enumerate(cards):
        if c.get("card_id") == card_id:
            return i
    raise PatchBudgetError(f"patch references unknown card_id {card_id!r}")


def _apply_one(cards: list[dict[str, Any]], edit: dict[str, Any]) -> None:
    op = edit["op"]
    if op == "pass_no_edits":
        return
    if op in ("replace_field", "update_state", "update_code_refs", "update_case_coverage"):
        i = _index_by_id(cards, edit.get("card_id"))
        field_name = {
            "update_state": "state_delta",
            "update_code_refs": "code_refs",
            "update_case_coverage": "cases_covered",
        }.get(op, edit.get("field"))
        if not field_name:
            raise PatchBudgetError("replace_field requires 'field'")
        cards[i][field_name] = copy.deepcopy(edit.get("value"))
    elif op == "replace_fields":
        i = _index_by_id(cards, edit.get("card_id"))
        for k, v in (edit.get("fields") or {}).items():
            cards[i][k] = copy.deepcopy(v)
    elif op == "delete_card":
        i = _index_by_id(cards, edit.get("card_id"))
        cards.pop(i)
    elif op == "insert_card":
        new_card = copy.deepcopy(edit.get("card") or {})
        after = edit.get("after_card_id")
        at = (_index_by_id(cards, after) + 1) if after is not None else len(cards)
        cards.insert(at, new_card)
    elif op == "merge_cards":
        i = _index_by_id(cards, edit.get("card_id"))
        j = _index_by_id(cards, edit.get("with_card_id"))
        if abs(i - j) != 1:
            raise PatchBudgetError("merge_cards only merges adjacent cards")
        lo, hi = sorted((i, j))
        merged = copy.deepcopy(edit.get("card") or cards[lo])
        cards[lo] = merged
        cards.pop(hi)
    elif op == "split_card":
        i = _index_by_id(cards, edit.get("card_id"))
        parts = edit.get("into") or []
        if len(parts) != 2:
            raise PatchBudgetError("split_card must produce exactly 2 cards")
        cards[i] = copy.deepcopy(parts[0])
        cards.insert(i + 1, copy.deepcopy(parts[1]))
    else:  # pragma: no cover - guarded by _check_budget
        raise PatchBudgetError(f"unhandled op {op!r}")


def apply_patch(
    cards: list[dict[str, Any]], patch: dict[str, Any], *, trigger: str = "worked_example_required"
) -> tuple[list[dict[str, Any]], AuditTelemetry]:
    """Apply an audit patch to a copy of ``cards``. Returns (new_cards, telemetry).

    Raises :class:`PatchBudgetError` if the budget/ops are violated (the pipeline then
    keeps the first-pass cards). ``pass_no_edits`` returns the cards unchanged.
    """
    status = patch.get("status", "pass_no_edits")
    edits = list(patch.get("edits") or [])
    tele = AuditTelemetry(audit_status=status, audit_trigger=trigger, patches_proposed=len(edits))

    if status == "pass_no_edits" or not edits:
        tele.audit_status = "pass_no_edits"
        return copy.deepcopy(cards), tele

    _check_budget(edits)
    working = copy.deepcopy(cards)
    for edit in edits:
        _apply_one(working, edit)
    tele.audit_status = "pass_with_edits"
    tele.patches_applied = len(edits)
    return working, tele
