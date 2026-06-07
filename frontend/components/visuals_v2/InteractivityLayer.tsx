"use client";

/**
 * InteractivityLayer — shared click + keyboard handling for v2 renderers.
 *
 * Exposes two APIs:
 *
 *   1. useInteractivity(args) hook — returns the helper bundle. Lightest
 *      migration path for an existing renderer: replace inlined helper
 *      functions with one call to this hook and consume `helpers.*`.
 *
 *   2. <InteractivityLayer> component (render-prop) — for greenfield
 *      renderers that want the helpers in JSX without a separate
 *      destructure.
 *
 * Both forms read from `selectable_elements` to provide:
 *   - handleClick(element_id) — invokes onElementClick with the matching el
 *   - handleKeyDown(element_id) — Enter/Space activate
 *   - ariaLabelFor(element_id, fallback) — reads SelectableElement.aria_label
 *   - tabIndexFor(element_id) — reads SelectableElement.keyboard_index
 *   - isSelected(element_id) — matches against selectedElementId
 */

import { useMemo, type KeyboardEvent } from "react";
import type { SelectableElement } from "@/lib/visual_v2_types";

export type InteractivityHelpers = {
  handleClick: (elementId: string) => (() => void) | undefined;
  handleKeyDown: (elementId: string) => ((e: KeyboardEvent) => void) | undefined;
  ariaLabelFor: (elementId: string, fallback: string) => string;
  tabIndexFor: (elementId: string) => number;
  isSelected: (elementId: string) => boolean;
};

type UseInteractivityArgs = {
  selectableElements: readonly SelectableElement[];
  selectedElementId: string | null | undefined;
  onElementClick?: (el: SelectableElement) => void;
};

export function useInteractivity(args: UseInteractivityArgs): InteractivityHelpers {
  const { selectableElements, selectedElementId, onElementClick } = args;

  const lookup = useMemo(() => {
    const map = new Map<string, SelectableElement>();
    for (const el of selectableElements) {
      map.set(el.element_id, el);
    }
    return map;
  }, [selectableElements]);

  return useMemo<InteractivityHelpers>(
    () => ({
      handleClick: (elementId: string) => {
        if (!onElementClick) return undefined;
        return () => {
          const el = lookup.get(elementId);
          if (el) onElementClick(el);
        };
      },
      handleKeyDown: (elementId: string) => {
        if (!onElementClick) return undefined;
        return (e: KeyboardEvent) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            const el = lookup.get(elementId);
            if (el) onElementClick(el);
          }
        };
      },
      ariaLabelFor: (elementId: string, fallback: string) =>
        lookup.get(elementId)?.aria_label || fallback,
      tabIndexFor: (elementId: string) => {
        if (!onElementClick) return -1;
        return lookup.get(elementId)?.keyboard_index ?? 0;
      },
      isSelected: (elementId: string) => selectedElementId === elementId,
    }),
    [lookup, onElementClick, selectedElementId],
  );
}

type Props = UseInteractivityArgs & {
  children: (helpers: InteractivityHelpers) => React.ReactNode;
};

export function InteractivityLayer({ children, ...args }: Props) {
  const helpers = useInteractivity(args);
  return <>{children(helpers)}</>;
}
