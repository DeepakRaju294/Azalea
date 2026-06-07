"use client";

/**
 * Indexed sequence visual (v2) — arrays, strings, binary search, sliding
 * window, two pointers, sorting passes.
 *
 * Reads model.base.values + frame.state.pointers / ranges / highlighted_cells.
 * Pointer movement is animated via CSS transform.
 */

import { motion } from "framer-motion";
import type { VisualModel, VisualFrame, SelectableElement } from "@/lib/visual_v2_types";
import { useInteractivity } from "@/components/visuals_v2/InteractivityLayer";
import { useMotionTransitionProps } from "@/components/visuals_v2/TransitionLayer";

type SequenceBase = {
  values: string[];
  indices: number[];
  pointer_definitions?: { id: string; label: string }[];
  mode?: string;
};

type SequenceFrameState = {
  pointers: { id: string; position: number; label: string }[];
  ranges: { id: string; start: number; end: number; label: string }[];
  highlighted_cells: number[];
  swapped_cells: [number, number] | null;
  sorted_prefix_end: number | null;
};

type Props = {
  model: VisualModel;
  frame: VisualFrame;
  onElementClick?: (el: SelectableElement) => void;
  selectedElementId?: string | null;
};

const CELL_WIDTH_PCT = 100 / 12; // ~12 cells fit; auto-scales otherwise

export function IndexedSequenceVisual({
  model,
  frame,
  onElementClick,
  selectedElementId,
}: Props) {
  const base = model.base as SequenceBase;
  const state = frame.state as SequenceFrameState;
  const motionProps = useMotionTransitionProps(frame.transitions || []);
  const cellPct = Math.min(CELL_WIDTH_PCT, 100 / Math.max(base.values.length, 1));

  // Shared click + a11y wiring from the v2 interactivity hook.
  const interactivity = useInteractivity({
    selectableElements: frame.selectable_elements || [],
    selectedElementId: selectedElementId ?? null,
    onElementClick,
  });
  const handleClick = (elementId: string) =>
    interactivity.handleClick(elementId)?.();
  const ariaLabelFor = interactivity.ariaLabelFor;
  const tabIndexFor = interactivity.tabIndexFor;

  return (
    <div className="rounded-2xl border border-[#E5DFEE] bg-white p-5 shadow-sm">
      <div
        className="relative overflow-x-auto"
        role="group"
        aria-label={`Indexed sequence: ${base.values.length} cells`}
      >
        {/* Pointers row */}
        <div className="relative h-8">
          {(state.pointers || []).map((ptr) => {
            const left = ptr.position * cellPct;
            const elementId = `pointer_${ptr.id}`;
            const selected = selectedElementId === elementId;
            return (
              <motion.button
                key={elementId}
                type="button"
                onClick={() => handleClick(elementId)}
                disabled={!onElementClick}
                aria-label={ariaLabelFor(
                  elementId,
                  `Pointer ${ptr.label || ptr.id} at index ${ptr.position}`,
                )}
                aria-pressed={selected}
                tabIndex={onElementClick ? tabIndexFor(elementId) : -1}
                className={[
                  "absolute top-0 flex flex-col items-center text-xs font-bold motion-safe:transition-all duration-400 ease-in-out",
                  onElementClick ? "cursor-pointer hover:scale-110" : "cursor-default",
                  "focus:outline-none focus-visible:ring-2 focus-visible:ring-[#FFD96B]",
                ].join(" ")}
                style={{ left: `${left}%`, width: `${cellPct}%` }}
                {...motionProps[elementId]}
              >
                <span
                  className={[
                    "rounded-md px-2 py-0.5 text-[10px]",
                    selected
                      ? "bg-[#FFD96B] text-[#3A2870]"
                      : "bg-[#7C4EF0] text-white",
                  ].join(" ")}
                >
                  {ptr.label}
                </span>
                <span aria-hidden="true" className="text-[#7C4EF0]">▼</span>
              </motion.button>
            );
          })}
        </div>
        {/* Cells row */}
        <div className="flex" role="row">
          {base.values.map((value, i) => {
            const elementId = `cell_${i}`;
            const isHighlighted = (state.highlighted_cells || []).includes(i);
            const isSelected = selectedElementId === elementId;
            const inRange = (state.ranges || []).some((r) => i >= r.start && i <= r.end);
            const isSortedPrefix =
              state.sorted_prefix_end !== null &&
              state.sorted_prefix_end !== undefined &&
              i <= state.sorted_prefix_end;
            const isSwap =
              state.swapped_cells != null &&
              (i === state.swapped_cells[0] || i === state.swapped_cells[1]);
            return (
              <motion.button
                key={elementId}
                type="button"
                onClick={() => handleClick(elementId)}
                disabled={!onElementClick}
                aria-label={ariaLabelFor(
                  elementId,
                  `Cell at index ${i}, value ${value}${
                    isHighlighted ? " (active)" : ""
                  }`,
                )}
                aria-pressed={isSelected}
                tabIndex={onElementClick ? tabIndexFor(elementId) : -1}
                className={[
                  "relative flex flex-col items-center justify-center border-y border-r border-[#D5CFE2] py-3 motion-safe:transition-all duration-300",
                  i === 0 ? "border-l rounded-l-md" : "",
                  i === base.values.length - 1 ? "rounded-r-md" : "",
                  isSelected
                    ? "ring-2 ring-[#FFD96B]"
                    : isHighlighted
                      ? "bg-[#FFD96B]/60"
                      : inRange
                        ? "bg-[#F4ECFF]"
                        : isSortedPrefix
                          ? "bg-[#E8DEFF]/50"
                          : "bg-white",
                  isSwap ? "motion-safe:animate-pulse" : "",
                  onElementClick ? "cursor-pointer hover:bg-[#E8DEFF]" : "cursor-default",
                  "focus:outline-none focus-visible:ring-2 focus-visible:ring-[#FFD96B]",
                ].join(" ")}
                style={{ width: `${cellPct}%` }}
                layout
                {...motionProps[elementId]}
              >
                <span className="font-mono text-sm font-bold text-[#3A2870]">{value}</span>
                <span className="mt-1 text-[10px] text-[#9A8FB0]">{i}</span>
              </motion.button>
            );
          })}
        </div>
        {/* Range labels */}
        {(state.ranges || []).length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {(state.ranges || []).map((r) => (
              <span
                key={r.id}
                className="rounded-md border border-[#D5CFE2] bg-[#F4ECFF] px-2 py-0.5 text-xs font-bold text-[#3A2870]"
              >
                {r.label || r.id}: [{r.start}–{r.end}]
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
