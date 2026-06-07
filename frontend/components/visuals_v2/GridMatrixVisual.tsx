"use client";

/**
 * Grid / matrix visual (v2).
 *
 * Renders DP tables, adjacency matrices, K-maps, and generic matrix-style
 * worked examples from the compiled grid_matrix_diagram VisualModel.
 */

import { motion } from "framer-motion";
import type { SelectableElement, VisualFrame, VisualModel } from "@/lib/visual_v2_types";
import { useInteractivity } from "@/components/visuals_v2/InteractivityLayer";
import { useMotionTransitionProps } from "@/components/visuals_v2/TransitionLayer";

type GridMatrixBase = {
  cells: string[][];
  row_labels?: string[];
  column_labels?: string[];
  mode?: string;
};

type GridMatrixFrameState = {
  active_cell?: [number, number] | null;
  completed_cells?: [number, number][];
  dependency_arrows?: { from: [number, number]; to: [number, number] }[];
  highlighted_row?: number | null;
  highlighted_column?: number | null;
  cell_values?: Record<string, string>;
};

type Props = {
  model: VisualModel;
  frame: VisualFrame;
  onElementClick?: (el: SelectableElement) => void;
  selectedElementId?: string | null;
};

function displayMode(mode?: string) {
  return (mode || "grid").replace(/_/g, " ");
}

function coordKey(row: number, column: number) {
  return `${row},${column}`;
}

function elementIdForCell(row: number, column: number) {
  return `cell_${row}_${column}`;
}

function isSameCell(a: [number, number] | null | undefined, row: number, column: number) {
  return Array.isArray(a) && a[0] === row && a[1] === column;
}

function cellInList(cells: [number, number][] | undefined, row: number, column: number) {
  return (cells || []).some((cell) => cell[0] === row && cell[1] === column);
}

export function GridMatrixVisual({
  model,
  frame,
  onElementClick,
  selectedElementId,
}: Props) {
  const base = model.base as GridMatrixBase;
  const state = frame.state as GridMatrixFrameState;
  const motionProps = useMotionTransitionProps(frame.transitions || []);
  const rows = base.cells || [];
  const rowLabels = base.row_labels || [];
  const columnLabels = base.column_labels || [];
  const cellValues = state.cell_values || {};
  const hasRowLabels = rowLabels.length > 0;
  const hasColumnLabels = columnLabels.length > 0;
  const columnCount = Math.max(...rows.map((row) => row.length), columnLabels.length, 1);
  const completedCells = state.completed_cells || [];
  const dependencyArrows = state.dependency_arrows || [];

  // Shared click + a11y wiring from the v2 interactivity hook.
  const interactivity = useInteractivity({
    selectableElements: frame.selectable_elements || [],
    selectedElementId: selectedElementId ?? null,
    onElementClick,
  });
  const handleClick = (elementId: string) =>
    interactivity.handleClick(elementId)?.();

  return (
    <div className="rounded-2xl border border-[#E5DFEE] bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-black uppercase tracking-wide text-[#7C4EF0]">
            {displayMode(model.mode)}
          </p>
          <p className="mt-1 text-sm text-[#5B526D]">
            Active cells are purple; completed cells are lavender.
          </p>
        </div>
        {dependencyArrows.length > 0 && (
          <span className="rounded-full border border-[#D5CFE2] bg-[#F4ECFF] px-3 py-1 text-xs font-bold text-[#5B2EE0]">
            {dependencyArrows.length} dependencies
          </span>
        )}
      </div>

      <div className="overflow-auto rounded-2xl border border-[#E5DFEE] bg-[#FBFAFF] p-4">
        <div
          className="grid min-w-max gap-1"
          style={{
            gridTemplateColumns: `${hasRowLabels ? "minmax(4rem, max-content) " : ""}repeat(${columnCount}, minmax(4.5rem, 1fr))`,
          }}
        >
          {hasColumnLabels && hasRowLabels && <div aria-hidden="true" />}
          {hasColumnLabels &&
            Array.from({ length: columnCount }).map((_, column) => {
              const label = columnLabels[column] ?? String(column);
              const selected = selectedElementId === `col_header_${column}`;
              return (
                <motion.button
                  key={`col_header_${column}`}
                  type="button"
                  onClick={() => handleClick(`col_header_${column}`)}
                  disabled={!onElementClick}
                  className={[
                    "rounded-lg border px-3 py-2 text-center text-xs font-black motion-safe:transition-all",
                    selected
                      ? "border-[#FFD96B] bg-[#FFF6DA] text-[#3A2870]"
                      : "border-[#E5DFEE] bg-white text-[#7C4EF0]",
                    onElementClick ? "cursor-pointer hover:bg-[#F4ECFF]" : "cursor-default",
                  ].join(" ")}
                  layout
                  {...motionProps[`col_header_${column}`]}
                >
                  {label}
                </motion.button>
              );
            })}

          {rows.map((row, rowIndex) => (
            <RowFragment key={`row_${rowIndex}`}>
              {hasRowLabels && (
                <motion.button
                  type="button"
                  onClick={() => handleClick(`row_header_${rowIndex}`)}
                  disabled={!onElementClick}
                  className={[
                    "rounded-lg border px-3 py-2 text-left text-xs font-black motion-safe:transition-all",
                    selectedElementId === `row_header_${rowIndex}`
                      ? "border-[#FFD96B] bg-[#FFF6DA] text-[#3A2870]"
                      : "border-[#E5DFEE] bg-white text-[#7C4EF0]",
                    onElementClick ? "cursor-pointer hover:bg-[#F4ECFF]" : "cursor-default",
                  ].join(" ")}
                  layout
                  {...motionProps[`row_header_${rowIndex}`]}
                >
                  {rowLabels[rowIndex] ?? rowIndex}
                </motion.button>
              )}
              {Array.from({ length: columnCount }).map((_, columnIndex) => {
                const baseValue = row[columnIndex] ?? "";
                const value = cellValues[coordKey(rowIndex, columnIndex)] ?? baseValue;
                const active = isSameCell(state.active_cell, rowIndex, columnIndex);
                const completed = cellInList(completedCells, rowIndex, columnIndex);
                const highlighted =
                  state.highlighted_row === rowIndex ||
                  state.highlighted_column === columnIndex;
                const selected = selectedElementId === elementIdForCell(rowIndex, columnIndex);
                const empty = value === "";

                return (
                  <motion.button
                    key={elementIdForCell(rowIndex, columnIndex)}
                    type="button"
                    onClick={() => handleClick(elementIdForCell(rowIndex, columnIndex))}
                    disabled={!onElementClick}
                    className={[
                      "relative flex min-h-16 items-center justify-center rounded-lg border px-3 py-3 font-mono text-sm font-black motion-safe:transition-all duration-300",
                      active
                        ? "scale-[1.03] border-[#5B2EE0] bg-[#7C4EF0] text-white shadow-lg shadow-[#7C4EF0]/20"
                        : selected
                          ? "border-[#FFD96B] bg-[#FFF6DA] text-[#3A2870] ring-2 ring-[#FFD96B]/70"
                          : completed
                            ? "border-[#C1A8FF] bg-[#E8DEFF] text-[#3A2870]"
                            : highlighted
                              ? "border-[#D5CFE2] bg-[#F4ECFF] text-[#3A2870]"
                              : "border-[#E5DFEE] bg-white text-[#3A2870]",
                      empty && !active ? "text-[#B7ADC7]" : "",
                      onElementClick ? "cursor-pointer hover:border-[#C1A8FF] hover:bg-[#F4ECFF]" : "cursor-default",
                    ].join(" ")}
                    aria-label={`Cell ${rowIndex}, ${columnIndex}${value ? ` value ${value}` : ""}`}
                    layout
                    {...motionProps[elementIdForCell(rowIndex, columnIndex)]}
                  >
                    <span>{value || "-"}</span>
                    {completed && !active && (
                      <span className="absolute right-1.5 top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-[#7C4EF0] text-[10px] leading-none text-white">
                        ok
                      </span>
                    )}
                  </motion.button>
                );
              })}
            </RowFragment>
          ))}
        </div>
      </div>

      {dependencyArrows.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {dependencyArrows.map((arrow, index) => (
            <span
              key={`${arrow.from.join("_")}_${arrow.to.join("_")}_${index}`}
              className="rounded-full border border-[#D5CFE2] bg-white px-3 py-1 text-xs font-bold text-[#5B526D]"
            >
              ({arrow.from[0]}, {arrow.from[1]}) -&gt; ({arrow.to[0]}, {arrow.to[1]})
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function RowFragment({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
