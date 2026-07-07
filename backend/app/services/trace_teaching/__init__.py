"""Trace → Teaching contract (Q23 — TRACE_TO_TEACHING_CONTRACT_SPEC.md).

The trace defines truth; prose may only surface, derive from, or remain consistent with it. This package is the
deterministic correctness gate (C1–C6) that lets a family move shadow_validate → on_enforced with explanatory
prose. It is additive/pure and imports no routes.

Modules:
- `grammar`  — the real trace step grammar (§2): Step / Output / Trace + typed required_facts (§6),
               forbidden_claims (§7), operation contract (§8), allowed_quantities (§10.1).
- `numeric`  — numeric normalization (§5): canonical number parse + value/unit pair extraction (fail-closed on an
               unrecognized numeric-like token).
- `checks`   — C1 value containment · C2 forbidden claims · C3 required facts · C4 unit fidelity · C5 operation/
               order · C6 bounded judge (reject-only, injectable).
- `validator`— run C1–C5, collect ALL failures, run C6 only if clean, compute decision + layered result (§10).

Sibling: `free_text` (Q24) reuses C1/C2/C4/C5 for its L3 sibling-trace rung.
"""
