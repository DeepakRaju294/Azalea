"""Free-text content validation (Q24 — FREE_TEXT_CONTENT_VALIDATION_SPEC.md).

Vertical slice (§6): a math `concept_intuition` span "Squaring both sides of x² = −4 gives x² = 0" is a class-3
DECLARED-operation transformation; L2 refutes it on target conformance (square_both_sides(x²=−4) → x⁴=16, not the
declared target x²=0), an optional span is deterministically DELETED after failed repair, and no fallback restores
it. This package is additive + pure; nothing here is wired into generation until the rollout gate enables it.

Modules:
- `relations`     — the closed deterministic algebra: a single-variable polynomial relation parser/normalizer +
                    the registered operation registry (canonical application). No LLM, no sympy.
- `binding`       — OperationBinding: surfaced-prose extraction + backend-provenance metadata → operation/relation
                    conformance + the gate that stops canonical application after any binding failure (§3).
- `transformation`— L2 class-3 validation (canonical output → target conformance) over a built binding.
- `validator`     — segmentation + slice-minimal ownership routing + disposition (retry → delete/withhold).
"""
