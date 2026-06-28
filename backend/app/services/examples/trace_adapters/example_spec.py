"""ExampleSpec / StageSpec — the declarative envelope each adapter ships (ADAPTER_CONTRACT.md §0).

The adapter declares ONE `ExampleSpec` that constrains the *shape* of every example without fixing a value:
the instance shape, the stage grammar (what one card is + how stages sequence), per-instance coverage, the
terminal. `trace_adapters/contract.py` validates a produced trace against it (every `Step.operation` must be
a declared *surfaced* stage id).

This is the C1 layer. The 8 existing adapters declare single-stage grammars matching their current one-op-
per-step behavior (the "repetitive algorithm = single stage" case); finer stage splits (e.g. Dijkstra
settle vs relax) are an iteration once effectiveness is evaluated — the spec is the place that split lands.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class StageSpec:
    id: str                                   # == Step.operation for surfaced stages
    primary_decision: str                     # the ONE learner decision this stage is
    teaching_focus: str = ""                  # constrained pedagogical label (non-truth-bearing)
    cardinality: str = "one_or_more"          # exactly_once | zero_or_once | one_or_more | zero_or_more
    primary_entity_limit: int = 1
    required_if_triggered: bool = False
    surfaced: bool = True                     # non-card phase markers = False (not a Step / no card)
    contains: dict[str, str] = field(default_factory=dict)   # semantic op -> required|aggregated_supporting|optional_supporting|internal
    state_effects: list[str] = field(default_factory=list)   # before/after the learner must reconstruct (declarative for now)


@dataclass
class InstanceShape:
    value_type: str = ""                                     # "integers" | "letters" | "weighted_graph" | ...
    count: Optional[tuple[int, int]] = None                  # (min, max) elements / nodes
    value_range: Optional[tuple[int, int]] = None            # (min, max) of values / weights
    structure: list[str] = field(default_factory=list)       # ["connected","distinct","sorted_ascending",...]


@dataclass
class ExampleSpec:
    input: InstanceShape
    stages: dict[str, StageSpec]                              # stage id -> spec
    structure: str = ""                                      # the legal stage sequence (grammar)
    must_exercise: list[str] = field(default_factory=list)   # per-INSTANCE coverage (aligns with required_cases)
    must_cover: list[str] = field(default_factory=list)      # per-ADAPTER-SUITE coverage
    must_avoid: list[str] = field(default_factory=list)      # degenerate anti-cases
    terminal: str = ""                                       # what "complete" is
    output_shape: str = ""                                   # the answer's shape
    size_tier: str = "small"
    tie_break: str = ""

    @property
    def transition(self) -> dict[str, Any]:
        """The view the contract checker reads: surfaced stage ids + the sequence grammar."""
        return {"stages": {sid: s for sid, s in self.stages.items() if s.surfaced},
                "structure": self.structure}

    @property
    def surfaced_stage_ids(self) -> set[str]:
        return {sid for sid, s in self.stages.items() if s.surfaced}
