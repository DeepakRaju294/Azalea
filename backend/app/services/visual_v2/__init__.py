"""Visual System V2 — the spec-driven, trace-authoritative visual pipeline.

See VISUAL_SYSTEM_SPEC.md (project root). This package is ADDITIVE: nothing here
is wired into lesson generation until a `(mode, algorithm)` is enabled via the
feature flag. The deterministic core (schemas, profiles, simulators, delta-fold)
has no LLM/API dependencies and is unit-tested in isolation.

Slice 1 (this commit): schemas + graph_network profile + BFS/DFS simulators +
ExampleInvariantValidator + DeltaFoldEngine, with the §11 BFS appendix as a
golden test.
"""
