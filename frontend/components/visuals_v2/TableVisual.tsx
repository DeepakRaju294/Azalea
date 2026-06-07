"use client";

/**
 * Table visual (v2).
 *
 * Renders comparison tables, truth tables, variable traces, and decision
 * tables from the compiled VisualModel contract.
 */

import { motion } from "framer-motion";
import type { SelectableElement, VisualFrame, VisualModel } from "@/lib/visual_v2_types";
import { useInteractivity } from "@/components/visuals_v2/InteractivityLayer";
import { useMotionTransitionProps } from "@/components/visuals_v2/TransitionLayer";

type TableBase = {
  columns?: string[];
  rows?: string[][];
  row_labels?: string[];
  caption?: string;
  mode?: string;
};

type TableFrameState = {
  active_row?: number | null;
  active_cell?: [number, number] | null;
  changed_cells?: [number, number][];
  cell_values?: Record<string, string>;
};

type Props = {
  model: VisualModel;
  frame: VisualFrame;
  onElementClick?: (el: SelectableElement) => void;
  selectedElementId?: string | null;
};

function displayMode(mode?: string) {
  return (mode || "table").replace(/_/g, " ");
}

function cellKey(rowIndex: number, columnIndex: number) {
  return `${rowIndex},${columnIndex}`;
}

function isSameCell(a: unknown, rowIndex: number, columnIndex: number) {
  return Array.isArray(a) && a.length === 2 && a[0] === rowIndex && a[1] === columnIndex;
}

function hasCell(cells: [number, number][] | undefined, rowIndex: number, columnIndex: number) {
  return (cells || []).some((cell) => cell[0] === rowIndex && cell[1] === columnIndex);
}

export function TableVisual({
  model,
  frame,
  onElementClick,
  selectedElementId,
}: Props) {
  const base = model.base as TableBase;
  const state = frame.state as TableFrameState;
  const motionProps = useMotionTransitionProps(frame.transitions || []);
  const columns = base.columns || [];
  const rows = base.rows || [];
  const rowLabels = base.row_labels || [];
  const cellValues = state.cell_values || {};
  const hasRowLabels = rowLabels.length > 0;
  const interactivity = useInteractivity({
    selectableElements: frame.selectable_elements || [],
    selectedElementId: selectedElementId ?? null,
    onElementClick,
  });
  const { ariaLabelFor, tabIndexFor } = interactivity;

  const handleClick = (elementId: string) => {
    interactivity.handleClick(elementId)?.();
  };

  if (rows.length === 0 && columns.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-[#D5CFE2] bg-[#F9F6FF] p-5 text-sm font-semibold text-[#5B2EE0]">
        Table data is not available for this step.
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-[#E5DFEE] bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-black uppercase tracking-wide text-[#7C4EF0]">
            {displayMode(model.mode)}
          </p>
          {base.caption && (
            <p className="mt-1 max-w-2xl text-sm leading-6 text-[#5B526D]">
              {base.caption}
            </p>
          )}
        </div>
        {(state.active_row != null || state.active_cell) && (
          <span className="rounded-full border border-[#D5CFE2] bg-[#F4ECFF] px-3 py-1 text-xs font-bold text-[#5B2EE0]">
            active
          </span>
        )}
      </div>

      <div className="overflow-x-auto rounded-2xl border border-[#E5DFEE]">
        <table className="min-w-full border-collapse text-left text-sm">
          <thead>
            <tr className="bg-[#F4ECFF] text-[#3A2870]">
              {hasRowLabels && (
                <th className="min-w-[120px] border-b border-r border-[#E5DFEE] px-4 py-3 text-xs font-black uppercase tracking-wide">
                  Focus
                </th>
              )}
              {columns.map((column, columnIndex) => {
                const elementId = `column_${columnIndex}`;
                return (
                  <th
                    key={elementId}
                    className={[
                      "min-w-[140px] border-b border-[#E5DFEE] px-4 py-3 text-xs font-black uppercase tracking-wide motion-safe:transition-colors",
                      selectedElementId === elementId ? "bg-[#FFF6DA] text-[#3A2870]" : "",
                    ].join(" ")}
                  >
                    <motion.button
                      type="button"
                      onClick={() => handleClick(elementId)}
                      disabled={!onElementClick}
                      aria-label={ariaLabelFor(elementId, `Column ${columnIndex + 1}: ${column}`)}
                      tabIndex={onElementClick ? tabIndexFor(elementId) : -1}
                      className={[
                        "w-full text-left",
                        onElementClick ? "cursor-pointer hover:text-[#5B2EE0]" : "cursor-default",
                      ].join(" ")}
                      layout
                      {...motionProps[elementId]}
                    >
                      {column}
                    </motion.button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => {
              const rowActive = state.active_row === rowIndex;
              const rowElementId = `row_${rowIndex}`;
              return (
                <tr
                  key={rowElementId}
                  className={[
                    "motion-safe:transition-colors duration-300",
                    rowActive ? "bg-[#FBF7FF]" : "bg-white",
                  ].join(" ")}
                >
                  {hasRowLabels && (
                    <th
                      className={[
                        "border-r border-t border-[#E5DFEE] px-4 py-3 font-black text-[#2E283A]",
                        selectedElementId === rowElementId ? "bg-[#FFF6DA]" : "",
                      ].join(" ")}
                    >
                      <motion.button
                        type="button"
                        onClick={() => handleClick(rowElementId)}
                        disabled={!onElementClick}
                        aria-label={ariaLabelFor(rowElementId, `Row ${rowIndex + 1}`)}
                        tabIndex={onElementClick ? tabIndexFor(rowElementId) : -1}
                        className={[
                          "w-full text-left",
                          onElementClick ? "cursor-pointer hover:text-[#5B2EE0]" : "cursor-default",
                        ].join(" ")}
                        layout
                        {...motionProps[rowElementId]}
                      >
                        {rowLabels[rowIndex] || `Row ${rowIndex + 1}`}
                      </motion.button>
                    </th>
                  )}
                  {row.map((baseValue, columnIndex) => {
                    const elementId = `cell_${rowIndex}_${columnIndex}`;
                    const active = isSameCell(state.active_cell, rowIndex, columnIndex);
                    const changed = hasCell(state.changed_cells, rowIndex, columnIndex);
                    const selected = selectedElementId === elementId;
                    const value = cellValues[cellKey(rowIndex, columnIndex)] ?? baseValue;
                    return (
                      <td
                        key={elementId}
                        className={[
                          "border-t border-[#E5DFEE] px-2 py-2 align-top motion-safe:transition-all duration-300",
                          selected ? "bg-[#FFF6DA]" : "",
                        ].join(" ")}
                      >
                        <motion.button
                          type="button"
                          onClick={() => handleClick(elementId)}
                          disabled={!onElementClick}
                          aria-label={ariaLabelFor(elementId, `Cell ${rowIndex + 1}, ${columnIndex + 1}: ${value || "empty"}`)}
                          tabIndex={onElementClick ? tabIndexFor(elementId) : -1}
                          className={[
                            "min-h-[48px] w-full rounded-xl border px-3 py-2 text-left leading-6 motion-safe:transition-all duration-300",
                            active
                              ? "scale-[1.01] border-[#5B2EE0] bg-[#7C4EF0] font-bold text-white shadow-lg shadow-[#7C4EF0]/15"
                              : changed
                                ? "border-[#FFD96B] bg-[#FFF6DA] font-bold text-[#3A2870]"
                                : rowActive
                                  ? "border-[#D5CFE2] bg-white text-[#2E283A]"
                                  : "border-transparent bg-transparent text-[#2E283A] hover:border-[#D5CFE2] hover:bg-[#FBFAFF]",
                            onElementClick ? "cursor-pointer" : "cursor-default",
                          ].join(" ")}
                          layout
                          {...motionProps[elementId]}
                        >
                          {value || "-"}
                        </motion.button>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-xs font-bold">
        <span className="rounded-full bg-[#7C4EF0] px-3 py-1 text-white">active cell</span>
        <span className="rounded-full border border-[#FFD96B] bg-[#FFF6DA] px-3 py-1 text-[#6B4A00]">
          changed
        </span>
        <span className="rounded-full border border-[#D5CFE2] bg-[#FBF7FF] px-3 py-1 text-[#5B526D]">
          active row
        </span>
      </div>
    </div>
  );
}
