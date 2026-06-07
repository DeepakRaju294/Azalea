"use client";

/**
 * Timeline / sequence interaction visual (v2).
 *
 * Renders actor lanes and message arrows for protocols, thread schedules,
 * and request-response flows.
 */

import { motion } from "framer-motion";
import type { SelectableElement, VisualFrame, VisualModel } from "@/lib/visual_v2_types";
import { useInteractivity } from "@/components/visuals_v2/InteractivityLayer";
import { useMotionTransitionProps } from "@/components/visuals_v2/TransitionLayer";

type Actor = {
  id: string;
  label: string;
};

type Message = {
  id: string;
  from: string;
  to: string;
  label: string;
  time: number;
};

type TimelineBase = {
  actors?: Actor[];
  messages?: Message[];
  caption?: string;
};

type TimelineState = {
  active_actor?: string | null;
  active_message?: string | null;
  visible_messages?: string[] | null;
  actor_states?: Record<string, string>;
};

type Props = {
  model: VisualModel;
  frame: VisualFrame;
  onElementClick?: (el: SelectableElement) => void;
  selectedElementId?: string | null;
};

const LEFT_PAD = 56;
const TOP_PAD = 58;
const LANE_GAP = 160;
const STEP_GAP = 58;

function displayMode(mode?: string) {
  return (mode || "timeline").replace(/_/g, " ");
}

export function TimelineSequenceVisual({
  model,
  frame,
  onElementClick,
  selectedElementId,
}: Props) {
  const base = model.base as TimelineBase;
  const state = frame.state as TimelineState;
  const motionProps = useMotionTransitionProps(frame.transitions || []);
  const actors = base.actors || [];
  const visibleMessages = new Set(state.visible_messages || (base.messages || []).map((message) => message.id));
  const messages = (base.messages || []).filter((message) => visibleMessages.has(message.id));
  const width = Math.max(420, LEFT_PAD * 2 + Math.max(actors.length - 1, 1) * LANE_GAP);
  const height = Math.max(280, TOP_PAD + Math.max(messages.length, 1) * STEP_GAP + 70);
  const actorX = new Map<string, number>();
  actors.forEach((actor, index) => actorX.set(actor.id, LEFT_PAD + index * LANE_GAP));
  const interactivity = useInteractivity({
    selectableElements: frame.selectable_elements || [],
    selectedElementId: selectedElementId ?? null,
    onElementClick,
  });
  const { ariaLabelFor, tabIndexFor } = interactivity;

  const handleClick = (elementId: string) => {
    interactivity.handleClick(elementId)?.();
  };

  if (actors.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-[#D5CFE2] bg-[#F9F6FF] p-5 text-sm font-semibold text-[#5B2EE0]">
        Timeline data is not available for this step.
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
        {(state.active_actor || state.active_message) && (
          <span className="rounded-full border border-[#D5CFE2] bg-[#F4ECFF] px-3 py-1 text-xs font-bold text-[#5B2EE0]">
            active
          </span>
        )}
      </div>

      <div className="overflow-x-auto rounded-2xl border border-[#E5DFEE] bg-[#FBFAFF] p-4">
        <svg viewBox={`0 0 ${width} ${height}`} className="min-h-[320px] w-full">
          <defs>
            <marker id={`${model.id}_arrow`} markerHeight="8" markerWidth="8" orient="auto" refX="7" refY="4">
              <path d="M 0 0 L 8 4 L 0 8 z" fill="#7C4EF0" />
            </marker>
          </defs>
          {actors.map((actor) => {
            const x = actorX.get(actor.id) || LEFT_PAD;
            const active = state.active_actor === actor.id;
            const actorState = state.actor_states?.[actor.id];
            return (
              <g
                key={actor.id}
                role="button"
                aria-label={ariaLabelFor(actor.id, `Actor ${actor.label}`)}
                tabIndex={onElementClick ? tabIndexFor(actor.id) : -1}
                onClick={() => handleClick(actor.id)}
                onKeyDown={interactivity.handleKeyDown(actor.id)}
                className={onElementClick ? "cursor-pointer" : "cursor-default"}
              >
                <motion.rect
                  x={x - 50}
                  y="8"
                  width="100"
                  height="34"
                  rx="14"
                  fill={active || selectedElementId === actor.id ? "#7C4EF0" : "#FFFFFF"}
                  stroke={active || selectedElementId === actor.id ? "#5B2EE0" : "#E5DFEE"}
                  strokeWidth="2"
                  {...motionProps[actor.id]}
                />
                <text x={x} y="30" textAnchor="middle" className={active || selectedElementId === actor.id ? "fill-white text-xs font-black" : "fill-[#2E283A] text-xs font-black"}>
                  {actor.label}
                </text>
                {actorState && (
                  <text x={x} y="54" textAnchor="middle" className="fill-[#7C4EF0] text-[10px] font-bold">
                    {actorState}
                  </text>
                )}
                <line x1={x} y1={TOP_PAD} x2={x} y2={height - 24} stroke="#D5CFE2" strokeDasharray="8 7" strokeWidth="2" />
              </g>
            );
          })}

          {messages.map((message, index) => {
            const fromX = actorX.get(message.from) || LEFT_PAD;
            const toX = actorX.get(message.to) || LEFT_PAD;
            const y = TOP_PAD + index * STEP_GAP + 28;
            const active = state.active_message === message.id || selectedElementId === message.id;
            const direction = toX >= fromX ? 1 : -1;
            return (
              <g
                key={message.id}
                role="button"
                aria-label={ariaLabelFor(message.id, `Message ${message.label}`)}
                tabIndex={onElementClick ? tabIndexFor(message.id) : -1}
                onClick={() => handleClick(message.id)}
                onKeyDown={interactivity.handleKeyDown(message.id)}
                className={onElementClick ? "cursor-pointer" : "cursor-default"}
              >
                {(active) && (
                  <motion.rect x={Math.min(fromX, toX) - 16} y={y - 20} width={Math.abs(toX - fromX) + 32} height="34" rx="16" fill="#7C4EF0" opacity="0.12" {...motionProps[message.id]} />
                )}
                <motion.line
                  x1={fromX}
                  y1={y}
                  x2={toX - direction * 10}
                  y2={y}
                  stroke={active ? "#7C4EF0" : "#5B526D"}
                  strokeWidth={active ? 4 : 2}
                  markerEnd={`url(#${model.id}_arrow)`}
                  {...motionProps[message.id]}
                />
                <text x={(fromX + toX) / 2} y={y - 9} textAnchor="middle" className="fill-[#2E283A] text-xs font-black">
                  {message.label}
                </text>
                <text x="12" y={y + 4} className="fill-[#9A8FB0] text-[10px] font-black">
                  {index + 1}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
