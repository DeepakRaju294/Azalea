"""Shared base for trace-adapter families (WORKED_EXAMPLE_ACCURACY_SPEC §15.3).

The bits identical across every algorithm — `version` and the provenance block — live here once. Each
FAMILY file adds the machinery shared within that family (instance generators, state normalizers, visual
mappers); each ALGORITHM subclass owns only its semantics contract (reference run, required cases, facts).
"""
from __future__ import annotations

from typing import Any


class FamilyAdapterBase:
    version: int = 1

    def _provenance(self, *, seed: int, candidate_id: str, example_input: dict[str, Any],
                    attempt: int) -> dict[str, Any]:
        return {"source": "adapter_reference", "adapter": self.slug, "adapter_version": self.version,
                "verification_level": "hard", "candidate_seed": seed,
                "candidate_id": candidate_id or example_input.get("_id", ""), "selection_attempt": attempt}
