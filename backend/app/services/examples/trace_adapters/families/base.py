"""Shared base for trace-adapter families (WORKED_EXAMPLE_ACCURACY_SPEC §15.3).

The bits identical across every algorithm — `version`, the provenance block, and the C1 raw->teaching /
policy layer (ADAPTER_CONTRACT.md §A items 3/4/5/9) — live here once. Each FAMILY file adds the machinery
shared within that family (instance generators, state normalizers, visual mappers); each ALGORITHM subclass
owns only its semantics contract (reference run, required cases, facts).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class TeachingTracePolicy:
    """ADAPTER_CONTRACT.md §A item 5 — the object that makes completeness NON-arbitrary: which instances are
    acceptable as a teaching trace, which transitions one instance MUST exercise, and the legal stage
    sequence. It REFERENCES the §0 grammar (it never duplicates it)."""
    accepts: Callable[[Any], bool]                 # the Stage-0 teaching-instance gate (is_teaching_trace)
    must_exercise: list[str] = field(default_factory=list)   # per-instance required transitions
    must_cover: list[str] = field(default_factory=list)      # per-suite coverage (across instances)
    must_avoid: list[str] = field(default_factory=list)      # degenerate anti-cases
    structure: str = ""                            # the legal stage sequence (the §0 grammar string)


class FamilyAdapterBase:
    version: int = 1

    def _provenance(self, *, seed: int, candidate_id: str, example_input: dict[str, Any],
                    attempt: int) -> dict[str, Any]:
        return {"source": "adapter_reference", "adapter": self.slug, "adapter_version": self.version,
                "verification_level": "hard", "candidate_seed": seed,
                "candidate_id": candidate_id or example_input.get("_id", ""), "selection_attempt": attempt}

    # --- C1 raw->teaching layer (ADAPTER_CONTRACT.md §A items 3/4/9) ---------------------------------
    # The current adapters emit ONLY learner-facing transitions (there are no internal-only events to
    # suppress), so the reference run already IS both the raw log and the teaching trace. The base provides
    # the split as identity; an adapter whose executor emits raw internal events overrides build_teaching_trace.

    def run_reference(self, example_input: dict[str, Any], **kwargs: Any) -> Any:
        """§A item 3 — the raw execution log (the only source of step values; no LLM)."""
        return self.reference(example_input, **kwargs)        # type: ignore[attr-defined]

    def build_teaching_trace(self, raw: Any) -> Any:
        """§A item 4 — curate raw -> learner-facing transitions. Identity here (nothing internal to suppress)."""
        return raw

    def required_transition_ids(self) -> list[str]:
        """§A item 9 — the stable must-show transition ids (the declarative per-instance required cases)."""
        spec = getattr(self, "example_spec", None)
        return list(getattr(spec, "must_exercise", []) or [])

    @property
    def teaching_trace_policy(self) -> TeachingTracePolicy:
        """§A item 5 — the policy that makes completeness non-arbitrary, derived from the §0 ExampleSpec +
        the adapter's own Stage-0 gate. References the grammar; never duplicates it."""
        spec = getattr(self, "example_spec", None)
        accepts: Callable[[Any], bool] = getattr(self, "is_teaching_trace", lambda _t: True)  # type: ignore[arg-type]
        return TeachingTracePolicy(
            accepts=accepts,
            must_exercise=list(getattr(spec, "must_exercise", []) or []),
            must_cover=list(getattr(spec, "must_cover", []) or []),
            must_avoid=list(getattr(spec, "must_avoid", []) or []),
            structure=str(getattr(spec, "structure", "") or ""))
