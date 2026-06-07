# V2 Visual Components

One React component per base visual type, plus support visuals, plus a dispatcher.

The page that drives these is at `frontend/app/study-paths/[studyPathId]/learn-v2/page.tsx`. The contract types are mirrored from the backend at `frontend/lib/visual_v2_types.ts`.

## Files

| File | Renderer | Status |
|------|----------|--------|
| `VisualRenderer.tsx` | Dispatcher, routes by `model.base_type` | full |
| `NodeLinkVisual.tsx` | Trees, graphs, linked lists, state machines | full, Framer-enabled |
| `IndexedSequenceVisual.tsx` | Arrays, strings, pointers, ranges | full, Framer-enabled |
| `CodeExecutionPanel.tsx` | Code panel with line numbers, variables, call stack | full, Framer-enabled |
| `GridMatrixVisual.tsx` | DP tables, matrices, adjacency, K-maps | full, Framer-enabled |
| `FormulaVisual.tsx` | Symbolic expressions, derivations | full, Framer-enabled |
| `TableVisual.tsx` | Comparison, truth, variable trace, routing | full, Framer-enabled |
| `CoordinateGraphVisual.tsx` | Function curves, distributions, ROC | full, Framer-enabled |
| `MemoryLayoutVisual.tsx` | Stack/heap, pointers, allocation | full, Framer-enabled |
| `GeometricVisual.tsx` | Triangles, vectors, regions | full, Framer-enabled |
| `TimelineSequenceVisual.tsx` | Protocol, race condition, OAuth | full, Framer-enabled |
| `SetRegionVisual.tsx` | Venn diagrams, probability regions | full, Framer-enabled |
| `ImageIllustrationVisual.tsx` | Analogy and real-world scenes | full, Framer-enabled |
| `StubVisual.tsx` | Placeholder for future base types | unused |
| `InteractivityLayer.tsx` | `useInteractivity` hook + render-prop component | active — adopted by all 12 base renderers |
| `TransitionLayer.tsx` | `useMotionTransitionProps` (Framer Motion path) + `useTransitionStyles` (CSS fallback, currently unused) | `useMotionTransitionProps` is consumed by all 12 renderers; `useTransitionStyles` is kept as a fallback for renderers that don't want a Framer dependency |

Support visuals live in `support/` and bypass compilation: StepFlow, PracticeFeedback, PathProgress, SourceAnnotation, and TopicSnapshot.

## Renderer Contract

Every base-type renderer accepts:

```tsx
type Props = {
  model: VisualModel;
  frame: VisualFrame;
  onElementClick?: (el: SelectableElement) => void;
  selectedElementId?: string | null;
};
```

The renderer reads `model.base` for structure, `frame.state` for per-frame overlays, `frame.selectable_elements` for click targets, and `frame.transitions` for animation specs.

## Click-To-Ask

The learn-v2 page maintains the current selected element and sticky chat threads per `(step, element_id)`.

When a learner clicks an element:

1. The renderer calls `onElementClick(el)`.
2. The page opens the chat sidebar.
3. The structured `VisualContextPayload` includes the clicked element, frame state, base type, and mode.
4. The backend `VisualContextFormatter` turns that into context for the chat model.

## Animation Strategy

Framer Motion is the active transition path for base visual renderers.

Renderers call `useMotionTransitionProps(frame.transitions)` from `TransitionLayer.tsx`, then spread returned props onto matching `motion.g`, `motion.div`, `motion.button`, `motion.circle`, and related elements.

The backend remains the source of truth for transitions. The frontend does not infer algorithm state; it only animates transition specs attached to the destination frame.

`useTransitionStyles` remains available as a lightweight CSS fallback for support visuals or future renderers.

For reduced motion, Framer is wired through `useReducedMotion()` inside `TransitionLayer.tsx`; CSS-only animations should continue using Tailwind `motion-safe:` variants.
