"""Shared base for trace-adapter families (WORKED_EXAMPLE_ACCURACY_SPEC §15.3).

The bits identical across every algorithm — `version`, the provenance block, and the C1 raw->teaching /
policy layer (ADAPTER_CONTRACT.md §A items 3/4/5/9) — live here once. Each FAMILY file adds the machinery
shared within that family (instance generators, state normalizers, visual mappers); each ALGORITHM subclass
owns only its semantics contract (reference run, required cases, facts).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ..artifacts import (AdapterDiagnostics, AdapterOutput, TeachingCheckpoint, TeachingObjectives,
                         TeachingProjection)


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

    # --- artifact chain (§2.3, §2.5.2, §2.6, §2.7) --------------------------------------------------
    label_convention: str = ""                         # "letters" (A–F) | "ints" (0–3); adapters set it

    def estimate_teaching_step_band(self, trace: Any) -> dict[str, int]:
        """§2.3 — predict the teaching STEP COUNT from the ACTUAL trace (owned by the adapter, not sampled in
        the solver). Drives the count gate + pacing. Default: the trace's own transition count with a small
        narration-grouping band; an adapter with known pacing overrides."""
        n = len(getattr(trace, "steps", []) or [])
        return {"min": max(1, n - 1), "target": n, "max": n + 2}

    @property
    def teaching_objectives(self) -> TeachingObjectives:
        """§2.7 — adapter-owned QUALITY. Default surfaces the declared required transitions; adapters override
        to add the misconception they preempt + the intended pacing."""
        spec = getattr(self, "example_spec", None)
        return TeachingObjectives(surfaces=list(getattr(spec, "must_exercise", []) or []))

    def select_teaching_checkpoints(self, trace: Any) -> list[str]:
        """ADAPTER-OWNED, DETERMINISTIC selection of which trace steps the learner sees (spec §7.1 / review).
        The ADAPTER decides which transitions are grouped/collapsed — NEVER the generator, which would be
        selectively omitting truth-bearing transitions. Default surfaces EVERY step (identity); an adapter
        whose raw trace runs long overrides this to group support steps, ALWAYS keeping every required-case
        step + the terminal."""
        return [s.id for s in (getattr(trace, "steps", []) or [])]

    def teaching_checkpoints(self, trace: Any) -> list["TeachingCheckpoint"]:
        """§7.3 — the ADAPTER-owned checkpoints WITH provenance. Default: one checkpoint per selected step
        (identity provenance). An adapter that groups supporting events (e.g. Dijkstra folding several
        no-improvement edge checks into one 'settle + relax neighbours' card) overrides this, and MUST cite the
        complete contiguous `source_step_ids` range plus the state-before/state-after anchors bounding it, so
        every card is traceable back to verified steps."""
        steps = list(getattr(trace, "steps", []) or [])
        evidence = getattr(trace, "case_evidence", {}) or {}
        chosen = set(self.select_teaching_checkpoints(trace))
        covered = {sid: [c for c, ids in evidence.items() if sid in ids] for sid in {s.id for s in steps}}
        out: list[TeachingCheckpoint] = []
        for s in steps:
            if s.id not in chosen:
                continue
            out.append(TeachingCheckpoint(
                checkpoint_id=s.id, source_step_ids=[s.id],
                visible_transition=str(getattr(s, "operation", "") or ""),
                state_before_step_id=s.id, state_after_step_id=s.id,
                required_cases_covered=covered.get(s.id, [])))
        return out

    def teaching_projection(self, trace: Any) -> TeachingProjection:
        """§2.5.2 — project the verified trace into the teaching interface (the adapter-selected checkpoints in
        order, the required set, the terminal, each transition's step kind)."""
        steps = list(getattr(trace, "steps", []) or [])
        checkpoints = self.select_teaching_checkpoints(trace)
        chosen = set(checkpoints)
        by_id = {s.id: s for s in steps}
        # required-case + terminal steps are ALWAYS surfaced, regardless of the checkpoint selection
        required_ids = {sid for ids in (getattr(trace, "case_evidence", {}) or {}).values() for sid in ids}
        ids = [s.id for s in steps if s.id in chosen or s.id in required_ids] or [s.id for s in steps]
        return TeachingProjection(
            transition_ids=ids,
            required_transition_ids=list(getattr(trace, "required_cases", []) or []),
            terminal_transition_id=steps[-1].id if steps else "",
            step_kinds={sid: str(getattr(by_id.get(sid), "operation", "") or "") for sid in ids},
            label_convention=self.label_convention)

    def build_adapter_output(self, trace: Any, *, seed: int = 0, candidate_id: str = "",
                             rejected_candidates: int = 0, instance_accepted: bool = True) -> AdapterOutput:
        """§2.6 — assemble the SINGLE standardized AdapterOutput from a verified trace: projection + step band
        + objectives + diagnostics. This is the one return contract everything downstream should consume."""
        steps = list(getattr(trace, "steps", []) or [])
        rendered = {s.id for s in steps}
        evidence = getattr(trace, "case_evidence", {}) or {}
        required = list(getattr(trace, "required_cases", []) or [])
        missing = [rc for rc in required if not (set(evidence.get(rc, [])) & rendered)]
        try:
            from ..contract import adapter_contract_violations  # cheap re-use to flag structural issues
            structural_ok = trace is not None and bool(steps)
            _ = adapter_contract_violations  # (kept import-light; deep structural check lives in the pipeline)
        except Exception:  # noqa: BLE001
            structural_ok = bool(steps)
        diagnostics = AdapterDiagnostics(
            adapter=str(getattr(self, "slug", "?")), adapter_version=self.version, seed=seed,
            candidate_id=candidate_id, instance_accepted=instance_accepted,
            rejected_candidates=rejected_candidates, required_cases=required,
            missing_required_cases=missing, structural_ok=structural_ok)
        return AdapterOutput(
            trace=trace, projection=self.teaching_projection(trace),
            step_band=self.estimate_teaching_step_band(trace),
            objectives=self.teaching_objectives, diagnostics=diagnostics)
