# Domain Renderer Spike — Phase 2A (§7)

> **Deliverable of §7:** the bounded three-fixture renderer spike, concluding with **exactly one decision per
> affected card type** — no production rendering changes ship as part of the spike.

## Method (and its one caveat)

The spike was run as a **capability analysis against the actual `visuals_v2` renderer source** (compile the render
model → check the target renderer's contract fields → classify the gap), rather than a live screenshot pass. The
compile-and-inspect half is authoritative; the **one remaining manual confirmation** is a visual screenshot in a
running frontend, which is a follow-up check, not a decision blocker — the field-level capability is
determinable from the component contracts below.

Fixtures: **completing the square** (math) · **Newton's second law** (science) · **DFS walkthrough** (coding).

## Renderer inventory (relevant components)

- `components/visuals_v2/FormulaVisual.tsx` — `expression`, `symbols[{symbol, meaning, value}]`, `assumptions`,
  and frame state `active_expression` · `substitution` · **`transformed_expression`** · **`equivalence_chain`**.
- `components/visuals_v2/CodeExecutionPanel.tsx` — code + execution state.
- `components/visuals_v2/{CoordinateGraph,Geometric,GridMatrix,NodeLink,Table,MemoryLayout}Visual.tsx`.
- `VisualRenderer.tsx` dispatches by visual type.

## Per-card-type decision

| Fixture | Card type | Target renderer | Capability finding | **Decision** |
|---|---|---|---|---|
| Completing the square | `formula_breakdown` | `FormulaVisual` | `expression` + `symbols{meaning}` + `transformed_expression` + `equivalence_chain` express the derivation (x²+bx → (x+b/2)² − (b/2)²) and each part's role. | **(1) existing renderer sufficient** |
| Completing the square | `worked_example` (step) | `FormulaVisual` | `active_expression`/`substitution`/`transformed_expression` cover per-step math framing (§3 math fields). | **(1) existing renderer sufficient** |
| Completing the square | `process` (Setup→Operation→Result→Why) | step/text scaffold (`StepFlowSupport`) | scaffold is a titled step list; no math-specific layout needed. | **(1) existing renderer sufficient** |
| Newton's second law | `worked_example` result (value **+ units**) | `FormulaVisual` | `symbols[].value` exists but there is **no `units` field**, and no interpretation line. | **(2) extend `FormulaVisual`** — add `units` on `symbols[]`/result (named field). Interpretation stays **omitted** (audit §4 gap) → science remains `shadow_validate`. |
| Newton's second law | `process` (Principle→Apply→Interpret) | step/text scaffold | sufficient as a titled scaffold; interpretation prose gated by §4. | **(1) existing renderer sufficient** (interpretation omitted) |
| DFS | `code_walkthrough` / `worked_example` | `CodeExecutionPanel` + `NodeLinkVisual` | existing verified-trace coding path; regression baseline. | **(1) existing renderer sufficient** |

## Conclusion → rollout impact

- **Math (`math_formula_method`, completing the square)** — renderer **sufficient today**; combined with the now-
  `defined` `formula_breakdown(math)` contract, the math slice is renderer-unblocked. Remaining gate to
  `on_enforced`: fact-source availability at runtime (math derivation-adapter audit, still pending) + live visual
  confirmation.
- **Science (`Newton`)** — needs a **bounded `FormulaVisual` units extension** (one named field) before display;
  interpretation is omitted per §4. Stays in `shadow_validate` until units metadata + the extension land — matches
  the D2 rollout order (science calculation after math).
- **Coding** — sufficient; regression baseline only.
- **No new renderer component** is required for the first slice; **no `defer that card type`** outcomes.

No production rendering changed as part of this spike.
