"use client";

/**
 * Real-world illustration visual (v2).
 *
 * Deterministic scene card with semantic hotspots. This is intentionally not
 * a generated bitmap; it keeps v2 rendering fast and stable.
 */

import { motion } from "framer-motion";
import type { SelectableElement, VisualFrame, VisualModel } from "@/lib/visual_v2_types";
import { useInteractivity } from "@/components/visuals_v2/InteractivityLayer";
import { useMotionTransitionProps } from "@/components/visuals_v2/TransitionLayer";

type Hotspot = {
  id: string;
  label: string;
  x: number;
  y: number;
  description?: string;
};

type IllustrationBase = {
  scene_title?: string;
  description?: string;
  hotspots?: Hotspot[];
  caption?: string;
};

type IllustrationState = {
  active_hotspot?: string | null;
  visible_hotspots?: string[] | null;
};

type Props = {
  model: VisualModel;
  frame: VisualFrame;
  onElementClick?: (el: SelectableElement) => void;
  selectedElementId?: string | null;
};

function displayMode(mode?: string) {
  return (mode || "illustration").replace(/_/g, " ");
}

function isVisible(id: string, visible?: string[] | null) {
  return !visible || visible.length === 0 || visible.includes(id);
}

export function ImageIllustrationVisual({
  model,
  frame,
  onElementClick,
  selectedElementId,
}: Props) {
  const base = model.base as IllustrationBase;
  const state = frame.state as IllustrationState;
  const motionProps = useMotionTransitionProps(frame.transitions || []);
  const hotspots = (base.hotspots || []).filter((hotspot) => isVisible(hotspot.id, state.visible_hotspots));
  const interactivity = useInteractivity({
    selectableElements: frame.selectable_elements || [],
    selectedElementId: selectedElementId ?? null,
    onElementClick,
  });
  const { ariaLabelFor, tabIndexFor } = interactivity;

  const handleClick = (elementId: string) => {
    interactivity.handleClick(elementId)?.();
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
        {state.active_hotspot && (
          <span className="rounded-full border border-[#D5CFE2] bg-[#F4ECFF] px-3 py-1 text-xs font-bold text-[#5B2EE0]">
            active
          </span>
        )}
      </div>

      <div className="relative overflow-hidden rounded-2xl border border-[#E5DFEE] bg-[#FBFAFF]">
        <svg viewBox="0 0 100 64" className="h-[340px] w-full" role="img">
          <defs>
            <linearGradient id={`${model.id}_scene`} x1="0" x2="1" y1="0" y2="1">
              <stop offset="0%" stopColor="#F4ECFF" />
              <stop offset="60%" stopColor="#FFFFFF" />
              <stop offset="100%" stopColor="#EEF8F3" />
            </linearGradient>
          </defs>
          <rect x="0" y="0" width="100" height="64" fill={`url(#${model.id}_scene)`} />
          <circle cx="18" cy="14" r="9" fill="#7C4EF0" opacity="0.12" />
          <circle cx="82" cy="50" r="14" fill="#2FB67E" opacity="0.12" />
          <path d="M 10 48 C 25 38, 36 44, 48 34 S 74 20, 90 28" fill="none" stroke="#D5CFE2" strokeWidth="1.2" strokeDasharray="4 4" />

          <foreignObject x="8" y="8" width="84" height="28">
            <div className="flex h-full flex-col justify-center rounded-2xl border border-[#E5DFEE] bg-white/80 p-4 shadow-sm">
              <p className="text-lg font-black text-[#12111A]">{base.scene_title || "Real-world illustration"}</p>
              {base.description && (
                <p className="mt-1 line-clamp-2 text-sm leading-5 text-[#5B526D]">{base.description}</p>
              )}
            </div>
          </foreignObject>

          {hotspots.map((hotspot, index) => {
            const active = state.active_hotspot === hotspot.id || selectedElementId === hotspot.id;
            return (
              <g
                key={hotspot.id}
                role="button"
                aria-label={ariaLabelFor(hotspot.id, `Hotspot ${hotspot.label}`)}
                tabIndex={onElementClick ? tabIndexFor(hotspot.id) : -1}
                onClick={() => handleClick(hotspot.id)}
                onKeyDown={interactivity.handleKeyDown(hotspot.id)}
                className={onElementClick ? "cursor-pointer" : "cursor-default"}
              >
                {active && <motion.circle cx={hotspot.x} cy={hotspot.y} r="5.8" fill="#7C4EF0" opacity="0.18" {...motionProps[hotspot.id]} />}
                <motion.circle cx={hotspot.x} cy={hotspot.y} r="3.3" fill={active ? "#7C4EF0" : "#FFFFFF"} stroke="#7C4EF0" strokeWidth="1" {...motionProps[hotspot.id]} />
                <text x={hotspot.x} y={hotspot.y + 1.4} textAnchor="middle" className={active ? "fill-white text-[3px] font-black" : "fill-[#5B2EE0] text-[3px] font-black"}>
                  {index + 1}
                </text>
                <text x={hotspot.x + 5} y={hotspot.y + 1.5} className="fill-[#2E283A] text-[3.5px] font-black">
                  {hotspot.label}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {hotspots.length > 0 && (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {hotspots.map((hotspot) => (
            <motion.button
              key={`${hotspot.id}_card`}
              type="button"
              onClick={() => handleClick(hotspot.id)}
              disabled={!onElementClick}
              aria-label={ariaLabelFor(hotspot.id, `Hotspot ${hotspot.label}`)}
              tabIndex={onElementClick ? tabIndexFor(hotspot.id) : -1}
              className={[
                "rounded-xl border px-3 py-2 text-left text-sm motion-safe:transition-all",
                selectedElementId === hotspot.id || state.active_hotspot === hotspot.id
                  ? "border-[#7C4EF0] bg-[#F4ECFF] text-[#3A2870]"
                  : "border-[#E5DFEE] bg-white text-[#5B526D]",
                onElementClick ? "cursor-pointer hover:border-[#C1A8FF]" : "cursor-default",
              ].join(" ")}
              layout
              {...motionProps[hotspot.id]}
            >
              <span className="font-black text-[#2E283A]">{hotspot.label}</span>
              {hotspot.description && <span className="ml-2">{hotspot.description}</span>}
            </motion.button>
          ))}
        </div>
      )}
    </div>
  );
}
