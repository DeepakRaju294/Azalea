"use client";

/**
 * Coordinate graph visual (v2).
 *
 * Renders axes, curves, plotted points, shaded regions, and tangent/secant
 * overlays from the compiled VisualModel contract.
 */

import { motion } from "framer-motion";
import type { SelectableElement, VisualFrame, VisualModel } from "@/lib/visual_v2_types";
import { useInteractivity } from "@/components/visuals_v2/InteractivityLayer";
import { useMotionTransitionProps } from "@/components/visuals_v2/TransitionLayer";

type AxisBase = {
  x_min: number;
  x_max: number;
  y_min: number;
  y_max: number;
  x_label?: string;
  y_label?: string;
};

type Curve = {
  id: string;
  label?: string;
  color?: string;
  points: { x: number; y: number }[];
};

type PlotPoint = {
  id: string;
  label?: string;
  x: number;
  y: number;
};

type CoordinateBase = {
  axes?: AxisBase;
  curves?: Curve[];
  points?: PlotPoint[];
  caption?: string;
};

type ShadedRegion = {
  curve_id: string;
  x_start: number;
  x_end: number;
  label?: string;
};

type LineOverlay = {
  id: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  label?: string;
};

type CurveSegment = {
  curve_id: string;
  x_start: number;
  x_end: number;
};

type CoordinateState = {
  active_point?: string | null;
  active_curve?: string | null;
  shaded_region?: ShadedRegion | null;
  tangent_secant_line?: LineOverlay | null;
  active_curve_segment?: CurveSegment | null;
};

type Props = {
  model: VisualModel;
  frame: VisualFrame;
  onElementClick?: (el: SelectableElement) => void;
  selectedElementId?: string | null;
};

const DEFAULT_AXES: AxisBase = {
  x_min: -5,
  x_max: 5,
  y_min: 0,
  y_max: 1,
  x_label: "x",
  y_label: "y",
};

const VIEWBOX = { width: 640, height: 360 };
const PADDING = { left: 56, right: 28, top: 28, bottom: 48 };

function displayMode(mode?: string) {
  return (mode || "coordinate graph").replace(/_/g, " ");
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function makeProjector(axes: AxisBase) {
  const plotWidth = VIEWBOX.width - PADDING.left - PADDING.right;
  const plotHeight = VIEWBOX.height - PADDING.top - PADDING.bottom;
  return (x: number, y: number) => {
    const xRatio = (x - axes.x_min) / (axes.x_max - axes.x_min);
    const yRatio = (y - axes.y_min) / (axes.y_max - axes.y_min);
    return {
      x: PADDING.left + clamp(xRatio, -0.2, 1.2) * plotWidth,
      y: PADDING.top + (1 - clamp(yRatio, -0.2, 1.2)) * plotHeight,
    };
  };
}

function pathFromPoints(points: { x: number; y: number }[], project: (x: number, y: number) => { x: number; y: number }) {
  return points
    .map((point, index) => {
      const projected = project(point.x, point.y);
      return `${index === 0 ? "M" : "L"} ${projected.x.toFixed(2)} ${projected.y.toFixed(2)}`;
    })
    .join(" ");
}

function sampleRegionPath(
  curve: Curve,
  region: ShadedRegion,
  axes: AxisBase,
  project: (x: number, y: number) => { x: number; y: number },
) {
  const sampled = curve.points.filter((point) => point.x >= region.x_start && point.x <= region.x_end);
  if (sampled.length < 2) return "";
  const baselineY = Math.max(axes.y_min, 0);
  const firstBase = project(sampled[0].x, baselineY);
  const topPath = sampled.map((point) => project(point.x, point.y));
  const lastBase = project(sampled[sampled.length - 1].x, baselineY);
  return [
    `M ${firstBase.x.toFixed(2)} ${firstBase.y.toFixed(2)}`,
    ...topPath.map((point) => `L ${point.x.toFixed(2)} ${point.y.toFixed(2)}`),
    `L ${lastBase.x.toFixed(2)} ${lastBase.y.toFixed(2)}`,
    "Z",
  ].join(" ");
}

function pointInSegment(point: { x: number; y: number }, segment?: CurveSegment | null) {
  if (!segment) return false;
  return point.x >= segment.x_start && point.x <= segment.x_end;
}

export function CoordinateGraphVisual({
  model,
  frame,
  onElementClick,
  selectedElementId,
}: Props) {
  const base = model.base as CoordinateBase;
  const state = frame.state as CoordinateState;
  const motionProps = useMotionTransitionProps(frame.transitions || []);
  const axes = { ...DEFAULT_AXES, ...(base.axes || {}) };
  const curves = base.curves || [];
  const points = base.points || [];
  const project = makeProjector(axes);
  const interactivity = useInteractivity({
    selectableElements: frame.selectable_elements || [],
    selectedElementId: selectedElementId ?? null,
    onElementClick,
  });
  const { ariaLabelFor, tabIndexFor } = interactivity;

  const axisOrigin = project(
    axes.x_min <= 0 && axes.x_max >= 0 ? 0 : axes.x_min,
    axes.y_min <= 0 && axes.y_max >= 0 ? 0 : axes.y_min,
  );
  const xAxisStart = project(axes.x_min, axes.y_min <= 0 && axes.y_max >= 0 ? 0 : axes.y_min);
  const xAxisEnd = project(axes.x_max, axes.y_min <= 0 && axes.y_max >= 0 ? 0 : axes.y_min);
  const yAxisStart = project(axes.x_min <= 0 && axes.x_max >= 0 ? 0 : axes.x_min, axes.y_min);
  const yAxisEnd = project(axes.x_min <= 0 && axes.x_max >= 0 ? 0 : axes.x_min, axes.y_max);

  const handleClick = (elementId: string) => {
    interactivity.handleClick(elementId)?.();
  };

  if (curves.length === 0 && points.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-[#D5CFE2] bg-[#F9F6FF] p-5 text-sm font-semibold text-[#5B2EE0]">
        Graph data is not available for this step.
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
        {(state.active_point || state.shaded_region || state.tangent_secant_line) && (
          <span className="rounded-full border border-[#D5CFE2] bg-[#F4ECFF] px-3 py-1 text-xs font-bold text-[#5B2EE0]">
            active
          </span>
        )}
      </div>

      <div className="rounded-2xl border border-[#E5DFEE] bg-[#FBFAFF] p-3">
        <svg viewBox={`0 0 ${VIEWBOX.width} ${VIEWBOX.height}`} className="h-[360px] w-full" role="img">
          <defs>
            <linearGradient id={`${model.id}_area`} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#7C4EF0" stopOpacity="0.28" />
              <stop offset="100%" stopColor="#7C4EF0" stopOpacity="0.04" />
            </linearGradient>
          </defs>

          <rect
            x={PADDING.left}
            y={PADDING.top}
            width={VIEWBOX.width - PADDING.left - PADDING.right}
            height={VIEWBOX.height - PADDING.top - PADDING.bottom}
            rx="14"
            fill="#FFFFFF"
            stroke="#E5DFEE"
          />

          {[0.25, 0.5, 0.75].map((ratio) => {
            const y = PADDING.top + ratio * (VIEWBOX.height - PADDING.top - PADDING.bottom);
            return (
              <line
                key={`grid_y_${ratio}`}
                x1={PADDING.left}
                x2={VIEWBOX.width - PADDING.right}
                y1={y}
                y2={y}
                stroke="#ECE7F4"
                strokeDasharray="4 6"
              />
            );
          })}

          <line x1={xAxisStart.x} y1={xAxisStart.y} x2={xAxisEnd.x} y2={xAxisEnd.y} stroke="#9A8FB0" strokeWidth="2" />
          <line x1={yAxisStart.x} y1={yAxisStart.y} x2={yAxisEnd.x} y2={yAxisEnd.y} stroke="#9A8FB0" strokeWidth="2" />
          <circle cx={axisOrigin.x} cy={axisOrigin.y} r="3" fill="#9A8FB0" />

          <g
            role="button"
            aria-label={ariaLabelFor("x_axis", `x axis: ${axes.x_label || "x"}`)}
            tabIndex={onElementClick ? tabIndexFor("x_axis") : -1}
            onClick={() => handleClick("x_axis")}
            onKeyDown={interactivity.handleKeyDown("x_axis")}
            className={onElementClick ? "cursor-pointer" : "cursor-default"}
          >
            <text x={VIEWBOX.width - PADDING.right + 8} y={xAxisEnd.y + 4} className="fill-[#5B526D] text-xs font-black">
              {axes.x_label}
            </text>
          </g>
          <g
            role="button"
            aria-label={ariaLabelFor("y_axis", `y axis: ${axes.y_label || "y"}`)}
            tabIndex={onElementClick ? tabIndexFor("y_axis") : -1}
            onClick={() => handleClick("y_axis")}
            onKeyDown={interactivity.handleKeyDown("y_axis")}
            className={onElementClick ? "cursor-pointer" : "cursor-default"}
          >
            <text x={yAxisEnd.x - 8} y={PADDING.top - 10} className="fill-[#5B526D] text-xs font-black">
              {axes.y_label}
            </text>
          </g>

          {state.shaded_region && curves.map((curve) => {
            if (curve.id !== state.shaded_region?.curve_id) return null;
            const regionPath = sampleRegionPath(curve, state.shaded_region, axes, project);
            if (!regionPath) return null;
            return (
              <g
                key="shaded_region"
                role="button"
                aria-label={ariaLabelFor("shaded_region", state.shaded_region.label || "Shaded region")}
                tabIndex={onElementClick ? tabIndexFor("shaded_region") : -1}
                onClick={() => handleClick("shaded_region")}
                onKeyDown={interactivity.handleKeyDown("shaded_region")}
                className={onElementClick ? "cursor-pointer" : "cursor-default"}
              >
                <motion.path
                  d={regionPath}
                  fill={`url(#${model.id}_area)`}
                  stroke="#7C4EF0"
                  strokeOpacity="0.24"
                  className={selectedElementId === "shaded_region" ? "drop-shadow-md" : ""}
                  {...motionProps.shaded_region}
                />
              </g>
            );
          })}

          {curves.map((curve) => {
            const active = state.active_curve === curve.id;
            const selected = selectedElementId === curve.id;
            const activeSegment = state.active_curve_segment?.curve_id === curve.id ? state.active_curve_segment : null;
            return (
              <g key={curve.id}>
                <g
                  role="button"
                  aria-label={ariaLabelFor(curve.id, `Curve ${curve.label || curve.id}`)}
                  tabIndex={onElementClick ? tabIndexFor(curve.id) : -1}
                  onClick={() => handleClick(curve.id)}
                  onKeyDown={interactivity.handleKeyDown(curve.id)}
                  className={onElementClick ? "cursor-pointer" : "cursor-default"}
                >
                  <motion.path
                    d={pathFromPoints(curve.points, project)}
                    fill="none"
                    stroke={curve.color || "#7C4EF0"}
                    strokeWidth={active || selected ? 5 : 3}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    opacity={active || selected ? 1 : 0.85}
                    className="motion-safe:transition-all duration-300"
                    {...motionProps[curve.id]}
                  />
                </g>
                {activeSegment && (
                  <motion.path
                    d={pathFromPoints(curve.points.filter((point) => pointInSegment(point, activeSegment)), project)}
                    fill="none"
                    stroke="#FFD25F"
                    strokeWidth="7"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    opacity="0.9"
                    {...motionProps[`${curve.id}_segment`]}
                  />
                )}
              </g>
            );
          })}

          {state.tangent_secant_line && (() => {
            const line = state.tangent_secant_line;
            const start = project(line.x1, line.y1);
            const end = project(line.x2, line.y2);
            return (
              <g
                role="button"
                aria-label={ariaLabelFor(line.id, line.label || "Tangent or secant line")}
                tabIndex={onElementClick ? tabIndexFor(line.id) : -1}
                onClick={() => handleClick(line.id)}
                onKeyDown={interactivity.handleKeyDown(line.id)}
                className={onElementClick ? "cursor-pointer" : "cursor-default"}
              >
                <motion.line
                  x1={start.x}
                  y1={start.y}
                  x2={end.x}
                  y2={end.y}
                  stroke="#24202F"
                  strokeWidth="3"
                  strokeDasharray="8 6"
                  className={selectedElementId === line.id ? "drop-shadow-md" : ""}
                  {...motionProps[line.id]}
                />
              </g>
            );
          })()}

          {points.map((point) => {
            const projected = project(point.x, point.y);
            const active = state.active_point === point.id;
            const selected = selectedElementId === point.id;
            return (
              <g
                key={point.id}
                role="button"
                aria-label={ariaLabelFor(point.id, `Point ${point.label || point.id}: x ${point.x}, y ${point.y}`)}
                tabIndex={onElementClick ? tabIndexFor(point.id) : -1}
                onClick={() => handleClick(point.id)}
                onKeyDown={interactivity.handleKeyDown(point.id)}
                className={onElementClick ? "cursor-pointer" : "cursor-default"}
              >
                <g className="transition-transform duration-300">
                  {(active || selected) && (
                    <circle cx={projected.x} cy={projected.y} r="14" fill="#7C4EF0" opacity="0.18" />
                  )}
                  <motion.circle
                    cx={projected.x}
                    cy={projected.y}
                    r={active ? 7 : 5}
                    fill={active ? "#7C4EF0" : selected ? "#FFD25F" : "#FFFFFF"}
                    stroke={active ? "#5B2EE0" : "#7C4EF0"}
                    strokeWidth="3"
                    {...motionProps[point.id]}
                  />
                  <text x={projected.x + 10} y={projected.y - 8} className="fill-[#2E283A] text-xs font-black">
                    {point.label || point.id}
                  </text>
                </g>
              </g>
            );
          })}
        </svg>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-xs font-bold">
        <span className="rounded-full bg-[#7C4EF0] px-3 py-1 text-white">active point</span>
        <span className="rounded-full border border-[#D5CFE2] bg-[#F4ECFF] px-3 py-1 text-[#5B2EE0]">
          curve
        </span>
        <span className="rounded-full border border-[#D5CFE2] bg-white px-3 py-1 text-[#5B526D]">
          shaded area
        </span>
      </div>
    </div>
  );
}
