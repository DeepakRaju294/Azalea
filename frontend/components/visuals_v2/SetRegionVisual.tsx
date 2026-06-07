"use client";

/**
 * Set / region visual (v2).
 *
 * Renders Venn-style set circles, shaded regions, and elements in regions.
 */

import { motion } from "framer-motion";
import type { SelectableElement, VisualFrame, VisualModel } from "@/lib/visual_v2_types";
import { useInteractivity } from "@/components/visuals_v2/InteractivityLayer";
import { useMotionTransitionProps } from "@/components/visuals_v2/TransitionLayer";

type SetCircle = {
  id: string;
  label: string;
  x: number;
  y: number;
  r: number;
};

type RegionElement = {
  id: string;
  label: string;
  x: number;
  y: number;
  regions?: string[];
};

type SetRegionBase = {
  sets?: SetCircle[];
  elements?: RegionElement[];
  caption?: string;
};

type SetRegionState = {
  active_set?: string | null;
  active_region?: string | null;
  shaded_regions?: string[];
  active_element?: string | null;
};

type Props = {
  model: VisualModel;
  frame: VisualFrame;
  onElementClick?: (el: SelectableElement) => void;
  selectedElementId?: string | null;
};

const COLORS = ["#7C4EF0", "#2FB67E", "#F6B73C", "#4C7DF0"];

function displayMode(mode?: string) {
  return (mode || "set region").replace(/_/g, " ");
}

function regionMatchesSet(region: string, setId: string) {
  return region === setId || region.split("_").includes(setId);
}

export function SetRegionVisual({
  model,
  frame,
  onElementClick,
  selectedElementId,
}: Props) {
  const base = model.base as SetRegionBase;
  const state = frame.state as SetRegionState;
  const motionProps = useMotionTransitionProps(frame.transitions || []);
  const sets = base.sets || [];
  const elements = base.elements || [];
  const shadedRegions = state.shaded_regions || [];
  const interactivity = useInteractivity({
    selectableElements: frame.selectable_elements || [],
    selectedElementId: selectedElementId ?? null,
    onElementClick,
  });
  const { ariaLabelFor, tabIndexFor } = interactivity;

  const handleClick = (elementId: string) => {
    interactivity.handleClick(elementId)?.();
  };

  if (sets.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-[#D5CFE2] bg-[#F9F6FF] p-5 text-sm font-semibold text-[#5B2EE0]">
        Set data is not available for this step.
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
        {(state.active_set || state.active_region || state.active_element) && (
          <span className="rounded-full border border-[#D5CFE2] bg-[#F4ECFF] px-3 py-1 text-xs font-bold text-[#5B2EE0]">
            active
          </span>
        )}
      </div>

      <div className="rounded-2xl border border-[#E5DFEE] bg-[#FBFAFF] p-4">
        <svg viewBox="0 0 100 100" className="h-[360px] w-full" role="img">
          <rect x="2" y="2" width="96" height="96" rx="12" fill="#FFFFFF" stroke="#E5DFEE" />
          {sets.map((setItem, index) => {
            const color = COLORS[index % COLORS.length];
            const active = state.active_set === setItem.id;
            const selected = selectedElementId === setItem.id;
            const shaded = shadedRegions.some((region) => regionMatchesSet(region, setItem.id));
            return (
              <g
                key={setItem.id}
                role="button"
                aria-label={ariaLabelFor(setItem.id, `Set ${setItem.label}`)}
                tabIndex={onElementClick ? tabIndexFor(setItem.id) : -1}
                onClick={() => handleClick(setItem.id)}
                onKeyDown={interactivity.handleKeyDown(setItem.id)}
                className={onElementClick ? "cursor-pointer" : "cursor-default"}
              >
                <motion.circle
                  cx={setItem.x}
                  cy={setItem.y}
                  r={setItem.r}
                  fill={color}
                  fillOpacity={shaded ? 0.22 : 0.1}
                  stroke={active || selected ? "#5B2EE0" : color}
                  strokeWidth={active || selected ? 2.4 : 1.6}
                  {...motionProps[setItem.id]}
                />
                {(active || selected) && (
                  <motion.circle cx={setItem.x} cy={setItem.y} r={setItem.r + 3} fill="none" stroke="#7C4EF0" strokeOpacity="0.24" strokeWidth="4" {...motionProps[setItem.id]} />
                )}
                <text x={setItem.x} y={setItem.y - setItem.r + 7} textAnchor="middle" className="fill-[#2E283A] text-[4px] font-black">
                  {setItem.label}
                </text>
              </g>
            );
          })}

          {elements.map((element) => {
            const active = state.active_element === element.id;
            const selected = selectedElementId === element.id;
            return (
              <g
                key={element.id}
                role="button"
                aria-label={ariaLabelFor(element.id, `Element ${element.label}`)}
                tabIndex={onElementClick ? tabIndexFor(element.id) : -1}
                onClick={() => handleClick(element.id)}
                onKeyDown={interactivity.handleKeyDown(element.id)}
                className={onElementClick ? "cursor-pointer" : "cursor-default"}
              >
                {(active || selected) && <motion.circle cx={element.x} cy={element.y} r="4.6" fill="#7C4EF0" opacity="0.2" {...motionProps[element.id]} />}
                <motion.circle
                  cx={element.x}
                  cy={element.y}
                  r="2.3"
                  fill={active ? "#7C4EF0" : selected ? "#FFD25F" : "#FFFFFF"}
                  stroke="#5B2EE0"
                  strokeWidth="0.8"
                  {...motionProps[element.id]}
                />
                <text x={element.x + 3.2} y={element.y + 1.2} className="fill-[#2E283A] text-[3.8px] font-black">
                  {element.label}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-xs font-bold">
        <span className="rounded-full bg-[#7C4EF0] px-3 py-1 text-white">active</span>
        <span className="rounded-full border border-[#D5CFE2] bg-[#F4ECFF] px-3 py-1 text-[#5B2EE0]">
          shaded set
        </span>
        <span className="rounded-full border border-[#D5CFE2] bg-white px-3 py-1 text-[#5B526D]">
          element
        </span>
      </div>
    </div>
  );
}
