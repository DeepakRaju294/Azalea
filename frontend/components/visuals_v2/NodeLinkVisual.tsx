"use client";

/**
 * Node-link visual (v2) — SVG renderer for tree/graph/linked-list/state-machine.
 *
 * Reads VisualModel.base (nodes + edges) and VisualFrame.state (active_node,
 * node_state_map, completed_nodes, active_edge_from/to, completed_edges,
 * runtime_state.call_stack/output). CSS transitions animate state changes.
 *
 * Style and layout match the existing legacy renderer's visual language
 * (purple = current, lavender = completed, neutral = unvisited) but are
 * implemented standalone — no dependency on the legacy file.
 */

import { motion } from "framer-motion";
import type { VisualModel, VisualFrame, SelectableElement } from "@/lib/visual_v2_types";
import { useInteractivity } from "@/components/visuals_v2/InteractivityLayer";
import { useMotionTransitionProps } from "@/components/visuals_v2/TransitionLayer";

type NodeLinkBase = {
  mode?: string;
  nodes: NodeLinkNode[];
  edges: NodeLinkEdge[];
  visual_blueprint?: string;
  purpose?: string;
};

type NodeLinkNode = {
  id: string;
  label: string;
  relation: string;
  description?: string;
  x: number;
  y: number;
  state?: string;
};

type NodeLinkEdge = {
  from: string;
  to: string;
  label?: string;
  style?: string;
  state?: string;
};

type NodeLinkFrameState = {
  active_node?: string;
  completed_nodes?: string[];
  node_state_map?: { node_id: string; state: string }[];
  active_edge_from?: string;
  active_edge_to?: string;
  completed_edges?: [string, string][];
  runtime_state?: {
    call_stack?: string[];
    output?: string[];
    frontier?: string[];
    frontier_kind?: string;
    variables?: { name?: string; value?: string | string[] | number | number[] | null }[];
  };
};

type Props = {
  model: VisualModel;
  frame: VisualFrame;
  onElementClick?: (el: SelectableElement) => void;
  selectedElementId?: string | null;
};

type ResolvedNodeState =
  | "unvisited"
  | "discovered"
  | "newly_discovered"
  | "current"
  | "completed"
  | "skipped";

function resolveNodeState(nodeId: string, frameState: NodeLinkFrameState): ResolvedNodeState {
  const map = (frameState.node_state_map || []).find((entry) => entry.node_id === nodeId);
  if (map) return map.state as ResolvedNodeState;
  if (frameState.active_node === nodeId) return "current";
  if ((frameState.completed_nodes || []).includes(nodeId)) return "completed";
  return "unvisited";
}

function nodeStyle(state: ResolvedNodeState) {
  switch (state) {
    case "current":
      return { fill: "#7C4EF0", stroke: "#5B2EE0", textFill: "#FFFFFF" };
    case "completed":
      return { fill: "#E8DEFF", stroke: "#7C4EF0", textFill: "#3A2870" };
    case "newly_discovered":
      return { fill: "#FFD96B", stroke: "#E0A800", textFill: "#3A2870" };
    case "discovered":
      return { fill: "#F4ECFF", stroke: "#C1A8FF", textFill: "#3A2870" };
    case "skipped":
      return { fill: "#E5E5E5", stroke: "#999", textFill: "#666" };
    default:
      return { fill: "#FFFFFF", stroke: "#D5CFE2", textFill: "#3A2870" };
  }
}

type ResolvedEdgeState = "unchecked" | "active" | "traversed" | "completed";

function resolveEdgeState(
  from: string,
  to: string,
  frameState: NodeLinkFrameState,
): ResolvedEdgeState {
  if (frameState.active_edge_from === from && frameState.active_edge_to === to) {
    return "active";
  }
  if ((frameState.completed_edges || []).some(([f, t]) => f === from && t === to)) {
    return "traversed";
  }
  return "unchecked";
}

function edgeStyle(state: ResolvedEdgeState) {
  switch (state) {
    case "active":
      return { stroke: "#7C4EF0", strokeWidth: 0.9, opacity: 1 };
    case "traversed":
      return { stroke: "#7C4EF0", strokeWidth: 0.7, opacity: 0.9 };
    case "completed":
      return { stroke: "#A88BF0", strokeWidth: 0.7, opacity: 0.85 };
    default:
      return { stroke: "#9A8FB0", strokeWidth: 0.5, opacity: 0.55 };
  }
}

// Human labels for each node/edge state, in display order. The legend shows ONLY the
// states actually present in the current frame, so it stays accurate and uncluttered.
const NODE_LEGEND: { state: ResolvedNodeState; label: string }[] = [
  { state: "current", label: "Current" },
  { state: "newly_discovered", label: "Just discovered" },
  { state: "discovered", label: "In frontier" },
  { state: "completed", label: "Visited" },
  { state: "skipped", label: "Skipped" },
  { state: "unvisited", label: "Unvisited" },
];

function NodeLinkLegend({
  base,
  frameState,
}: {
  base: NodeLinkBase;
  frameState: NodeLinkFrameState;
}) {
  const presentNodeStates = new Set(base.nodes.map((n) => resolveNodeState(n.id, frameState)));
  const nodeItems = NODE_LEGEND.filter((it) => presentNodeStates.has(it.state));

  const presentEdgeStates = new Set(
    base.edges.map((e) => resolveEdgeState(e.from, e.to, frameState)),
  );
  const edgeItems: { state: ResolvedEdgeState; label: string }[] = [];
  if (presentEdgeStates.has("active")) edgeItems.push({ state: "active", label: "Edge in focus" });
  if (presentEdgeStates.has("traversed") || presentEdgeStates.has("completed")) {
    edgeItems.push({ state: "traversed", label: "Selected edge" });
  }

  if (nodeItems.length === 0 && edgeItems.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 px-1 text-[11px] text-slate-500">
      <span className="font-semibold uppercase tracking-wide text-slate-400">Key</span>
      {nodeItems.map((it) => {
        const s = nodeStyle(it.state);
        return (
          <span key={`n-${it.state}`} className="inline-flex items-center gap-1.5">
            <span
              className="inline-block h-3 w-3 shrink-0 rounded-full"
              style={{ backgroundColor: s.fill, border: `1.5px solid ${s.stroke}` }}
            />
            {it.label}
          </span>
        );
      })}
      {edgeItems.map((it) => {
        const s = edgeStyle(it.state);
        return (
          <span key={`e-${it.state}`} className="inline-flex items-center gap-1.5">
            <span
              className="inline-block h-[3px] w-4 shrink-0 rounded"
              style={{ backgroundColor: s.stroke, opacity: s.opacity }}
            />
            {it.label}
          </span>
        );
      })}
    </div>
  );
}

export function NodeLinkVisual({ model, frame, onElementClick, selectedElementId }: Props) {
  const base = model.base as NodeLinkBase;
  const frameState = frame.state as NodeLinkFrameState;
  const motionProps = useMotionTransitionProps(frame.transitions || []);
  const runtime = frameState.runtime_state || {};
  const callStack = runtime.call_stack || [];
  const output = runtime.output || [];
  const frontier = runtime.frontier || [];
  const frontierKind = runtime.frontier_kind || "frontier";
  const variables = Array.isArray(runtime.variables) ? runtime.variables : [];
  const activeNode = frameState.active_node || "";
  const shouldShowRuntimePanel =
    Boolean(activeNode) ||
    callStack.length > 0 ||
    output.length > 0 ||
    frontier.length > 0 ||
    Boolean(frontierKind && frontierKind !== "frontier" && activeNode) ||
    variables.length > 0;

  const nodeById = new Map(base.nodes.map((n) => [n.id, n]));

  // Fit the viewBox to the actual node bounds instead of a fixed 0 0 100 80.
  // The LLM often clusters nodes in part of the canvas (e.g. the lower half),
  // which left large empty margins and made the diagram "start too low". Fitting
  // to content keeps nodes and labels in the same proportion (radius and font
  // are in the same units) while filling the frame for any layout.
  const contentViewBox = (() => {
    if (base.nodes.length === 0) return "0 0 100 80";
    const xs = base.nodes.map((n) => n.x);
    const ys = base.nodes.map((n) => n.y);
    const pad = 8;
    const minX = Math.min(...xs) - pad;
    const minY = Math.min(...ys) - pad;
    const width = Math.max(Math.max(...xs) + pad - minX, 1);
    const height = Math.max(Math.max(...ys) + pad - minY, 1);
    return `${minX} ${minY} ${width} ${height}`;
  })();

  // Shared click + keyboard + a11y wiring from the v2 interactivity hook.
  // Replaces what used to be 4 inline helpers (handleClickElement,
  // ariaLabelFor, tabIndexFor, handleKeyDown).
  const interactivity = useInteractivity({
    selectableElements: frame.selectable_elements || [],
    selectedElementId: selectedElementId ?? null,
    onElementClick,
  });
  const handleClickElement = (elementId: string) =>
    interactivity.handleClick(elementId)?.();
  const ariaLabelFor = interactivity.ariaLabelFor;
  const tabIndexFor = interactivity.tabIndexFor;
  const handleKeyDown = interactivity.handleKeyDown;

  return (
    <div className="flex flex-col gap-3 md:flex-row md:items-stretch">
      <div className="flex flex-1 flex-col gap-2">
        <div
          className="relative overflow-hidden bg-transparent"
          style={{ height: "min(52vh, 440px)" }}
        >
        <svg
          viewBox={contentViewBox}
          preserveAspectRatio="xMidYMid meet"
          className="h-full w-full"
          role="img"
          aria-label="Node-link diagram"
        >
          {/* Edges first so nodes render on top */}
          {base.edges.map((edge) => {
            const fromNode = nodeById.get(edge.from);
            const toNode = nodeById.get(edge.to);
            if (!fromNode || !toNode) return null;
            const state = resolveEdgeState(edge.from, edge.to, frameState);
            const s = edgeStyle(state);
            const edgeId = `${edge.from}->${edge.to}`;
            const selected = selectedElementId === edgeId;
            return (
              <g
                key={edgeId}
                role={onElementClick ? "button" : undefined}
                tabIndex={onElementClick ? tabIndexFor(edgeId) : -1}
                aria-label={ariaLabelFor(edgeId, `Edge from ${edge.from} to ${edge.to}`)}
                aria-pressed={selected}
                onKeyDown={handleKeyDown(edgeId)}
                className="focus:outline-none focus-visible:[outline:2px_solid_#FFD96B]"
              >
                <motion.line
                  x1={fromNode.x}
                  y1={fromNode.y}
                  x2={toNode.x}
                  y2={toNode.y}
                  stroke={s.stroke}
                  strokeWidth={s.strokeWidth}
                  opacity={s.opacity}
                  className="motion-safe:transition-all duration-300 ease-in-out"
                  {...motionProps[edgeId]}
                />
                {/* Only render meaningful weight labels (those containing a
                    digit). Generic relationship words like "connects" are noise
                    on the edge and clutter the diagram. */}
                {edge.label && /\d/.test(edge.label) && (
                  <text
                    x={(fromNode.x + toNode.x) / 2}
                    y={(fromNode.y + toNode.y) / 2 - 1}
                    fontSize={2.4}
                    fill="#5B2EE0"
                    textAnchor="middle"
                  >
                    {edge.label}
                  </text>
                )}
                {/* Hit target for clicks */}
                <line
                  x1={fromNode.x}
                  y1={fromNode.y}
                  x2={toNode.x}
                  y2={toNode.y}
                  stroke="transparent"
                  strokeWidth={3}
                  style={{ cursor: onElementClick ? "pointer" : "default" }}
                  onClick={() => handleClickElement(edgeId)}
                />
                {selected && (
                  <line
                    x1={fromNode.x}
                    y1={fromNode.y}
                    x2={toNode.x}
                    y2={toNode.y}
                    stroke="#FFD96B"
                    strokeWidth={1.4}
                    opacity={0.6}
                  />
                )}
              </g>
            );
          })}
          {/* Nodes */}
          {base.nodes.map((node) => {
            const state = resolveNodeState(node.id, frameState);
            const ns = nodeStyle(state);
            const radius = state === "current" ? 4.5 : 4;
            const selected = selectedElementId === node.id;
            const label = node.label.length > 4 ? node.label.slice(0, 4) : node.label;
            return (
              <g
                key={node.id}
                role={onElementClick ? "button" : undefined}
                tabIndex={onElementClick ? tabIndexFor(node.id) : -1}
                aria-label={ariaLabelFor(
                  node.id,
                  `Node ${node.label}, state ${state}${
                    node.relation ? `, role ${node.relation}` : ""
                  }`,
                )}
                aria-pressed={selected}
                onKeyDown={handleKeyDown(node.id)}
                style={{
                  cursor: onElementClick ? "pointer" : "default",
                  transition: "transform 400ms ease-in-out",
                }}
                className="focus:outline-none focus-visible:[outline:2px_solid_#FFD96B]"
                onClick={() => handleClickElement(node.id)}
              >
                {selected && (
                  <motion.circle
                    cx={node.x}
                    cy={node.y}
                    r={radius + 1.8}
                    fill="none"
                    stroke="#FFD96B"
                    strokeWidth={0.6}
                    {...motionProps[node.id]}
                  />
                )}
                {state === "current" && (
                  <motion.circle
                    cx={node.x}
                    cy={node.y}
                    r={radius + 2}
                    fill="#7C4EF0"
                    opacity={0.18}
                    className="motion-safe:transition-all duration-300"
                    {...motionProps[node.id]}
                  />
                )}
                <motion.circle
                  cx={node.x}
                  cy={node.y}
                  r={radius}
                  fill={ns.fill}
                  stroke={ns.stroke}
                  strokeWidth={0.5}
                  className="motion-safe:transition-all duration-300 ease-in-out"
                  {...motionProps[node.id]}
                />
                <text
                  x={node.x}
                  y={node.y + 1.2}
                  fontSize={label.length <= 2 ? 3.4 : 2.6}
                  fontWeight={800}
                  fill={ns.textFill}
                  textAnchor="middle"
                  pointerEvents="none"
                >
                  {label}
                </text>
                {state === "completed" && (
                  <g pointerEvents="none">
                    <circle cx={node.x + radius * 0.65} cy={node.y - radius * 0.65} r={1.6} fill="#7C4EF0" />
                    <text
                      x={node.x + radius * 0.65}
                      y={node.y - radius * 0.65 + 0.8}
                      fontSize={2}
                      fontWeight={900}
                      fill="#fff"
                      textAnchor="middle"
                    >
                      ✓
                    </text>
                  </g>
                )}
              </g>
            );
          })}
        </svg>
        </div>
        <NodeLinkLegend base={base} frameState={frameState} />
      </div>
      {/* Side panel: current runtime variables */}
      {shouldShowRuntimePanel && (
        <div className="flex flex-col gap-2 md:w-56">
          {activeNode && (
            <SidePanel title="Current">
              <PanelChip
                label={activeNode}
                elementId="runtime_current"
                selected={selectedElementId === "runtime_current"}
                onClick={onElementClick ? () => handleClickElement("runtime_current") : undefined}
              />
            </SidePanel>
          )}
          {callStack.length > 0 && (
            <SidePanel title="Call stack">
              {callStack.map((item, i) => (
                <PanelChip
                  key={`stack_item_${i}`}
                  label={item}
                  elementId={`stack_item_${i}`}
                  selected={selectedElementId === `stack_item_${i}`}
                  onClick={onElementClick ? () => handleClickElement(`stack_item_${i}`) : undefined}
                />
              ))}
            </SidePanel>
          )}
          {(frontier.length > 0 || (frontierKind && frontierKind !== "frontier" && activeNode)) && (
            <SidePanel title={frontierKind.charAt(0).toUpperCase() + frontierKind.slice(1)}>
              {frontier.length > 0 ? (
                frontier.map((item, i) => (
                  <PanelChip
                    key={`frontier_item_${i}`}
                    label={item}
                    elementId={`frontier_item_${i}`}
                    selected={selectedElementId === `frontier_item_${i}`}
                    onClick={onElementClick ? () => handleClickElement(`frontier_item_${i}`) : undefined}
                  />
                ))
              ) : (
                <PanelChip
                  label="[]"
                  elementId="frontier_empty"
                  selected={selectedElementId === "frontier_empty"}
                  onClick={onElementClick ? () => handleClickElement("frontier_empty") : undefined}
                />
              )}
            </SidePanel>
          )}
          {(output.length > 0 || activeNode) && (
            <SidePanel title="Output">
              <div className="flex flex-wrap gap-1">
                {output.length > 0 ? (
                  output.map((item, i) => (
                    <PanelChip
                      key={`output_item_${i}`}
                      label={item}
                      elementId={`output_item_${i}`}
                      selected={selectedElementId === `output_item_${i}`}
                      onClick={
                        onElementClick ? () => handleClickElement(`output_item_${i}`) : undefined
                      }
                    />
                  ))
                ) : (
                  <PanelChip
                    label="[]"
                    elementId="output_empty"
                    selected={selectedElementId === "output_empty"}
                    onClick={onElementClick ? () => handleClickElement("output_empty") : undefined}
                  />
                )}
              </div>
            </SidePanel>
          )}
          {variables
            .filter((variable) => {
              const name = String(variable?.name || "").trim().toLowerCase();
              return name && !["current", "output", "result", "call_stack", "call stack", "frontier"].includes(name);
            })
            .map((variable, variableIndex) => {
              const name = String(variable.name || `Variable ${variableIndex + 1}`);
              const values = normalizeRuntimeVariableValue(variable.value);
              return (
                <SidePanel key={`${name}_${variableIndex}`} title={name}>
                  <div className="flex flex-wrap gap-1">
                    {values.map((value, valueIndex) => {
                      const elementId = `runtime_variable_${variableIndex}_${valueIndex}`;
                      return (
                        <PanelChip
                          key={elementId}
                          label={value}
                          elementId={elementId}
                          selected={selectedElementId === elementId}
                          onClick={onElementClick ? () => handleClickElement(elementId) : undefined}
                        />
                      );
                    })}
                  </div>
                </SidePanel>
              );
            })}
        </div>
      )}
    </div>
  );
}

function normalizeRuntimeVariableValue(value: unknown) {
  if (Array.isArray(value)) {
    return value.length > 0 ? value.map((item) => String(item)) : ["[]"];
  }
  if (value === null || value === undefined || value === "") return ["[]"];
  return [String(value)];
}

function SidePanel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-[#E5DFEE] bg-white p-3 shadow-sm">
      <p className="text-[10px] font-bold uppercase tracking-wide text-[#7C4EF0]">{title}</p>
      <div className="mt-2 flex flex-wrap items-center gap-1">{children}</div>
    </div>
  );
}

function PanelChip({
  label,
  elementId,
  selected,
  onClick,
  ariaLabel,
}: {
  label: string;
  elementId: string;
  selected: boolean;
  onClick?: () => void;
  ariaLabel?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!onClick}
      data-element-id={elementId}
      aria-label={ariaLabel || label}
      aria-pressed={selected}
      className={[
        "rounded-md px-2 py-0.5 text-xs font-bold motion-safe:transition-all",
        selected
          ? "border border-[#FFD96B] bg-[#FFF6DA] text-[#3A2870]"
          : "border border-[#D5CFE2] bg-[#F4ECFF] text-[#3A2870] hover:bg-[#E8DEFF]",
        onClick ? "cursor-pointer" : "cursor-default",
        "focus:outline-none focus-visible:ring-2 focus-visible:ring-[#FFD96B]",
      ].join(" ")}
    >
      {label}
    </button>
  );
}
