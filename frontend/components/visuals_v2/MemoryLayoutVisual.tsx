"use client";

/**
 * Memory layout visual (v2).
 *
 * Renders stack frames, heap objects, variable bindings, and pointer arrows.
 */

import { motion } from "framer-motion";
import type { SelectableElement, VisualFrame, VisualModel } from "@/lib/visual_v2_types";
import { useInteractivity } from "@/components/visuals_v2/InteractivityLayer";
import { useMotionTransitionProps } from "@/components/visuals_v2/TransitionLayer";

type VariableBinding = {
  id: string;
  name: string;
  value?: string;
  target?: string;
};

type MemoryFrameBase = {
  id: string;
  label: string;
  variables?: VariableBinding[];
};

type HeapObjectBase = {
  id: string;
  label: string;
  fields?: { name: string; value?: string; target?: string }[];
};

type PointerBase = {
  id: string;
  from: string;
  to: string;
  label?: string;
};

type MemoryBase = {
  frames?: MemoryFrameBase[];
  objects?: HeapObjectBase[];
  pointers?: PointerBase[];
  caption?: string;
};

type MemoryState = {
  active_frame?: string | null;
  active_object?: string | null;
  active_pointer?: string | null;
  changed_bindings?: string[];
  visible_frames?: string[] | null;
  visible_objects?: string[] | null;
};

type Props = {
  model: VisualModel;
  frame: VisualFrame;
  onElementClick?: (el: SelectableElement) => void;
  selectedElementId?: string | null;
};

type BoxPosition = {
  x: number;
  y: number;
  width: number;
  height: number;
};

const BOX_WIDTH = 220;
const ROW_HEIGHT = 34;
const GAP = 18;

function displayMode(mode?: string) {
  return (mode || "memory layout").replace(/_/g, " ");
}

function isVisible(id: string, visible?: string[] | null) {
  return !visible || visible.length === 0 || visible.includes(id);
}

export function MemoryLayoutVisual({
  model,
  frame,
  onElementClick,
  selectedElementId,
}: Props) {
  const base = model.base as MemoryBase;
  const state = frame.state as MemoryState;
  const motionProps = useMotionTransitionProps(frame.transitions || []);
  const frames = (base.frames || []).filter((item) => isVisible(item.id, state.visible_frames));
  const objects = (base.objects || []).filter((item) => isVisible(item.id, state.visible_objects));
  const pointers = base.pointers || [];
  const changedBindings = new Set(state.changed_bindings || []);
  const interactivity = useInteractivity({
    selectableElements: frame.selectable_elements || [],
    selectedElementId: selectedElementId ?? null,
    onElementClick,
  });
  const { ariaLabelFor, tabIndexFor } = interactivity;

  const framePositions = new Map<string, BoxPosition>();
  const objectPositions = new Map<string, BoxPosition>();

  frames.forEach((item, index) => {
    const height = 62 + (item.variables || []).length * ROW_HEIGHT;
    framePositions.set(item.id, { x: 0, y: index * (height + GAP), width: BOX_WIDTH, height });
    (item.variables || []).forEach((variable, variableIndex) => {
      framePositions.set(variable.id, {
        x: 12,
        y: index * (height + GAP) + 48 + variableIndex * ROW_HEIGHT,
        width: BOX_WIDTH - 24,
        height: ROW_HEIGHT - 8,
      });
    });
  });

  objects.forEach((item, index) => {
    const height = 62 + (item.fields || []).length * ROW_HEIGHT;
    objectPositions.set(item.id, { x: 340, y: index * (height + GAP), width: BOX_WIDTH, height });
  });

  const totalHeight = Math.max(
    220,
    ...Array.from(framePositions.values()).map((position) => position.y + position.height),
    ...Array.from(objectPositions.values()).map((position) => position.y + position.height),
  );

  const handleClick = (elementId: string) => {
    interactivity.handleClick(elementId)?.();
  };

  const renderBox = (
    id: string,
    label: string,
    position: BoxPosition,
    kind: "frame" | "object",
    rows: { id?: string; name: string; value?: string; target?: string }[],
  ) => {
    const active = (kind === "frame" && state.active_frame === id) || (kind === "object" && state.active_object === id);
    const selected = selectedElementId === id;
    return (
      <motion.g
        key={id}
        role="button"
        aria-label={ariaLabelFor(id, `${kind === "frame" ? "Stack frame" : "Heap object"} ${label}`)}
        tabIndex={onElementClick ? tabIndexFor(id) : -1}
        onClick={() => handleClick(id)}
        onKeyDown={interactivity.handleKeyDown(id)}
        className={onElementClick ? "cursor-pointer" : "cursor-default"}
        layout
        {...motionProps[id]}
      >
        {(active || selected) && (
          <motion.rect
            x={position.x - 8}
            y={position.y - 8}
            width={position.width + 16}
            height={position.height + 16}
            rx="22"
            fill="#7C4EF0"
            opacity="0.14"
            {...motionProps[id]}
          />
        )}
        <motion.rect
          x={position.x}
          y={position.y}
          width={position.width}
          height={position.height}
          rx="16"
          fill={active ? "#F4ECFF" : "#FFFFFF"}
          stroke={active ? "#7C4EF0" : "#E5DFEE"}
          strokeWidth={active ? 3 : 2}
          {...motionProps[id]}
        />
        <text x={position.x + 16} y={position.y + 28} className="fill-[#2E283A] text-sm font-black">
          {label}
        </text>
        <text x={position.x + position.width - 16} y={position.y + 28} textAnchor="end" className="fill-[#7C4EF0] text-[10px] font-black uppercase">
          {kind === "frame" ? "stack" : "heap"}
        </text>
        {rows.map((row, rowIndex) => {
          const rowId = row.id || `${id}.${row.name}`;
          const rowY = position.y + 48 + rowIndex * ROW_HEIGHT;
          const changed = changedBindings.has(rowId);
          return (
            <motion.g
              key={rowId}
              role="button"
              aria-label={ariaLabelFor(rowId, `Variable ${row.name}: ${row.target || row.value || "empty"}`)}
              tabIndex={onElementClick ? tabIndexFor(rowId) : -1}
              onClick={(event) => {
                event.stopPropagation();
                handleClick(rowId);
              }}
              onKeyDown={interactivity.handleKeyDown(rowId)}
              className={onElementClick ? "cursor-pointer" : "cursor-default"}
              layout
              {...motionProps[rowId]}
            >
              <rect
                x={position.x + 12}
                y={rowY}
                width={position.width - 24}
                height={ROW_HEIGHT - 8}
                rx="10"
                fill={changed || selectedElementId === rowId ? "#FFF6DA" : "#FBFAFF"}
                stroke={changed || selectedElementId === rowId ? "#FFD96B" : "#E5DFEE"}
              />
              <text x={position.x + 24} y={rowY + 18} className="fill-[#2E283A] text-xs font-bold">
                {row.name}
              </text>
              <text x={position.x + position.width - 24} y={rowY + 18} textAnchor="end" className="fill-[#5B526D] text-xs font-bold">
                {row.target || row.value || "-"}
              </text>
            </motion.g>
          );
        })}
      </motion.g>
    );
  };

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
        {(state.active_frame || state.active_object || state.active_pointer) && (
          <span className="rounded-full border border-[#D5CFE2] bg-[#F4ECFF] px-3 py-1 text-xs font-bold text-[#5B2EE0]">
            active
          </span>
        )}
      </div>

      <div className="overflow-x-auto rounded-2xl border border-[#E5DFEE] bg-[#FBFAFF] p-4">
        <svg viewBox={`0 0 560 ${totalHeight}`} className="min-h-[260px] w-full">
          <defs>
            <marker id={`${model.id}_arrow`} markerHeight="8" markerWidth="8" orient="auto" refX="7" refY="4">
              <path d="M 0 0 L 8 4 L 0 8 z" fill="#7C4EF0" />
            </marker>
          </defs>
          <text x="0" y="14" className="fill-[#7C4EF0] text-[11px] font-black uppercase tracking-wide">
            stack frames
          </text>
          <text x="340" y="14" className="fill-[#7C4EF0] text-[11px] font-black uppercase tracking-wide">
            heap objects
          </text>
          <g transform="translate(0 28)">
            {frames.map((item) => {
              const position = framePositions.get(item.id);
              if (!position) return null;
              return renderBox(item.id, item.label, position, "frame", item.variables || []);
            })}
            {objects.map((item) => {
              const position = objectPositions.get(item.id);
              if (!position) return null;
              return renderBox(item.id, item.label, position, "object", item.fields || []);
            })}
            {pointers.map((pointer) => {
              const from = framePositions.get(pointer.from) || objectPositions.get(pointer.from);
              const to = objectPositions.get(pointer.to) || framePositions.get(pointer.to);
              if (!from || !to) return null;
              const active = state.active_pointer === pointer.id;
              return (
                <g
                  key={pointer.id}
                  role="button"
                  aria-label={ariaLabelFor(pointer.id, `Pointer ${pointer.label || pointer.id}`)}
                  tabIndex={onElementClick ? tabIndexFor(pointer.id) : -1}
                  onClick={() => handleClick(pointer.id)}
                  onKeyDown={interactivity.handleKeyDown(pointer.id)}
                  className={onElementClick ? "cursor-pointer" : "cursor-default"}
                >
                  <motion.path
                    d={`M ${from.x + from.width} ${from.y + from.height / 2} C 275 ${from.y + from.height / 2}, 285 ${to.y + to.height / 2}, ${to.x} ${to.y + to.height / 2}`}
                    fill="none"
                    stroke={active || selectedElementId === pointer.id ? "#7C4EF0" : "#9A8FB0"}
                    strokeWidth={active ? 4 : 2}
                    strokeDasharray={active ? "0" : "8 7"}
                    markerEnd={`url(#${model.id}_arrow)`}
                    {...motionProps[pointer.id]}
                  />
                  {pointer.label && (
                    <text x="280" y={(from.y + to.y + from.height / 2 + to.height / 2) / 2 - 8} textAnchor="middle" className="fill-[#5B2EE0] text-xs font-black">
                      {pointer.label}
                    </text>
                  )}
                </g>
              );
            })}
          </g>
        </svg>
      </div>
    </div>
  );
}
