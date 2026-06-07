"use client";

/**
 * Geometric diagram visual (v2).
 *
 * Renders points, segments, polygon regions, and measurement labels.
 */

import { motion } from "framer-motion";
import type { SelectableElement, VisualFrame, VisualModel } from "@/lib/visual_v2_types";
import { useInteractivity } from "@/components/visuals_v2/InteractivityLayer";
import { useMotionTransitionProps } from "@/components/visuals_v2/TransitionLayer";

type GeoPoint = {
  id: string;
  label: string;
  x: number;
  y: number;
};

type GeoSegment = {
  id: string;
  from: string;
  to: string;
  label?: string;
};

type GeoRegion = {
  id: string;
  label: string;
  points: string[];
};

type GeometricBase = {
  points?: GeoPoint[];
  segments?: GeoSegment[];
  regions?: GeoRegion[];
  caption?: string;
};

type GeometricState = {
  active_point?: string | null;
  active_segment?: string | null;
  active_region?: string | null;
  shaded_regions?: string[];
  measurements?: Record<string, string>;
};

type Props = {
  model: VisualModel;
  frame: VisualFrame;
  onElementClick?: (el: SelectableElement) => void;
  selectedElementId?: string | null;
};

function displayMode(mode?: string) {
  return (mode || "geometry").replace(/_/g, " ");
}

function centroid(points: GeoPoint[]) {
  if (points.length === 0) return { x: 50, y: 50 };
  return {
    x: points.reduce((sum, point) => sum + point.x, 0) / points.length,
    y: points.reduce((sum, point) => sum + point.y, 0) / points.length,
  };
}

export function GeometricVisual({
  model,
  frame,
  onElementClick,
  selectedElementId,
}: Props) {
  const base = model.base as GeometricBase;
  const state = frame.state as GeometricState;
  const motionProps = useMotionTransitionProps(frame.transitions || []);
  const points = base.points || [];
  const pointById = new Map(points.map((point) => [point.id, point]));
  const segments = base.segments || [];
  const regions = base.regions || [];
  const shaded = new Set(state.shaded_regions || []);
  const measurements = state.measurements || {};
  const interactivity = useInteractivity({
    selectableElements: frame.selectable_elements || [],
    selectedElementId: selectedElementId ?? null,
    onElementClick,
  });
  const { ariaLabelFor, tabIndexFor } = interactivity;

  const handleClick = (elementId: string) => {
    interactivity.handleClick(elementId)?.();
  };

  if (points.length === 0 && regions.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-[#D5CFE2] bg-[#F9F6FF] p-5 text-sm font-semibold text-[#5B2EE0]">
        Geometry data is not available for this step.
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
        {(state.active_point || state.active_segment || state.active_region) && (
          <span className="rounded-full border border-[#D5CFE2] bg-[#F4ECFF] px-3 py-1 text-xs font-bold text-[#5B2EE0]">
            active
          </span>
        )}
      </div>

      <div className="rounded-2xl border border-[#E5DFEE] bg-[#FBFAFF] p-4">
        <svg viewBox="0 0 100 100" className="h-[360px] w-full" role="img">
          <rect x="2" y="2" width="96" height="96" rx="12" fill="#FFFFFF" stroke="#E5DFEE" />
          {regions.map((region) => {
            const regionPoints = region.points.map((pointId) => pointById.get(pointId)).filter(Boolean) as GeoPoint[];
            if (regionPoints.length < 3) return null;
            const pointsString = regionPoints.map((point) => `${point.x},${point.y}`).join(" ");
            const active = state.active_region === region.id || selectedElementId === region.id;
            const center = centroid(regionPoints);
            return (
              <g
                key={region.id}
                role="button"
                aria-label={ariaLabelFor(region.id, `Region ${region.label}`)}
                tabIndex={onElementClick ? tabIndexFor(region.id) : -1}
                onClick={() => handleClick(region.id)}
                onKeyDown={interactivity.handleKeyDown(region.id)}
                className={onElementClick ? "cursor-pointer" : "cursor-default"}
              >
                <motion.polygon
                  points={pointsString}
                  fill="#7C4EF0"
                  fillOpacity={shaded.has(region.id) || active ? 0.16 : 0.05}
                  stroke={active ? "#7C4EF0" : "#D5CFE2"}
                  strokeWidth={active ? 1.4 : 0.8}
                  {...motionProps[region.id]}
                />
                <text x={center.x} y={center.y} textAnchor="middle" className="fill-[#5B2EE0] text-[4px] font-black">
                  {region.label}
                </text>
              </g>
            );
          })}

          {segments.map((segment) => {
            const from = pointById.get(segment.from);
            const to = pointById.get(segment.to);
            if (!from || !to) return null;
            const active = state.active_segment === segment.id || selectedElementId === segment.id;
            const label = measurements[segment.id] || segment.label;
            return (
              <g
                key={segment.id}
                role="button"
                aria-label={ariaLabelFor(segment.id, `Segment ${segment.label || segment.id}`)}
                tabIndex={onElementClick ? tabIndexFor(segment.id) : -1}
                onClick={() => handleClick(segment.id)}
                onKeyDown={interactivity.handleKeyDown(segment.id)}
                className={onElementClick ? "cursor-pointer" : "cursor-default"}
              >
                <motion.line
                  x1={from.x}
                  y1={from.y}
                  x2={to.x}
                  y2={to.y}
                  stroke={active ? "#7C4EF0" : "#2E283A"}
                  strokeWidth={active ? 2.4 : 1.4}
                  strokeLinecap="round"
                  {...motionProps[segment.id]}
                />
                {label && (
                  <text x={(from.x + to.x) / 2} y={(from.y + to.y) / 2 - 3} textAnchor="middle" className="fill-[#5B2EE0] text-[3.8px] font-black">
                    {label}
                  </text>
                )}
              </g>
            );
          })}

          {points.map((point) => {
            const active = state.active_point === point.id || selectedElementId === point.id;
            return (
              <g
                key={point.id}
                role="button"
                aria-label={ariaLabelFor(point.id, `Point ${point.label}`)}
                tabIndex={onElementClick ? tabIndexFor(point.id) : -1}
                onClick={() => handleClick(point.id)}
                onKeyDown={interactivity.handleKeyDown(point.id)}
                className={onElementClick ? "cursor-pointer" : "cursor-default"}
              >
                {active && <motion.circle cx={point.x} cy={point.y} r="4.8" fill="#7C4EF0" opacity="0.2" {...motionProps[point.id]} />}
                <motion.circle cx={point.x} cy={point.y} r={active ? 2.8 : 2.2} fill={active ? "#7C4EF0" : "#FFFFFF"} stroke="#5B2EE0" strokeWidth="0.8" {...motionProps[point.id]} />
                <text x={point.x + 3} y={point.y - 2} className="fill-[#2E283A] text-[4px] font-black">
                  {point.label}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
