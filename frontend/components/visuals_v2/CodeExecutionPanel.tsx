"use client";

/**
 * Code execution panel (v2).
 *
 * Renders model.base.code with line numbers; highlights the active line
 * range from frame.state.highlight_lines; shows variables + call_stack +
 * output in a side panel. Supports growing mode (visible_until_line caps
 * rendered lines) and execution mode (full code visible).
 */

import { motion } from "framer-motion";
import type { VisualModel, VisualFrame, SelectableElement } from "@/lib/visual_v2_types";
import { useInteractivity } from "@/components/visuals_v2/InteractivityLayer";
import { useMotionTransitionProps } from "@/components/visuals_v2/TransitionLayer";

type CodeBase = {
  code: string;
  language: string;
  line_count: number;
  mode: string;
};

type CodeFrameState = {
  visible_until_line: number;
  highlight_lines: [number, number];
  variables?: { name: string; value: string }[];
  call_stack?: string[];
  output?: string[];
};

type Props = {
  model: VisualModel;
  frame: VisualFrame;
  onElementClick?: (el: SelectableElement) => void;
  selectedElementId?: string | null;
};

export function CodeExecutionPanel({ model, frame, onElementClick, selectedElementId }: Props) {
  const base = model.base as CodeBase;
  const state = frame.state as CodeFrameState;
  const motionProps = useMotionTransitionProps(frame.transitions || []);
  const allLines = base.code.split("\n");
  const visibleCount = Math.min(state.visible_until_line ?? allLines.length, allLines.length);
  const visibleLines = allLines.slice(0, visibleCount);
  const [hStart, hEnd] = state.highlight_lines ?? [0, 0];

  // Shared click + keyboard + a11y wiring from the v2 interactivity hook.
  const interactivity = useInteractivity({
    selectableElements: frame.selectable_elements || [],
    selectedElementId: selectedElementId ?? null,
    onElementClick,
  });
  const handleClickLine = (lineNumber: number) =>
    interactivity.handleClick(`code_line_${lineNumber}`)?.();
  const handleClickVariable = (name: string) =>
    interactivity.handleClick(`code_variable_${name}`)?.();
  const ariaLabelFor = interactivity.ariaLabelFor;
  const tabIndexFor = interactivity.tabIndexFor;
  const handleLineKey = (lineNumber: number) =>
    interactivity.handleKeyDown(`code_line_${lineNumber}`);

  return (
    <div className="flex flex-col gap-3 md:flex-row md:items-stretch">
      <div
        className="flex-1 overflow-hidden rounded-2xl border border-[#343434] bg-[#1f1f1f] shadow-sm"
        role="group"
        aria-label={`Code panel: ${base.language}, ${visibleCount} lines visible`}
      >
        <div className="flex items-center justify-between border-b border-[#343434] bg-[#252525] px-4 py-3">
          <span className="text-sm font-black text-[#f4f4f4]">Code</span>
          <span className="rounded-full bg-white/10 px-2.5 py-1 text-[11px] font-black uppercase tracking-wide text-[#b9b9b9]">
            {base.language}
          </span>
        </div>
        <pre className="max-h-[28rem] overflow-auto p-4 font-mono text-sm leading-6">
          <code>
            {visibleLines.map((line, idx) => {
              const lineNum = idx + 1;
              const isHighlighted = hStart > 0 && lineNum >= hStart && lineNum <= hEnd;
              const isSelected = selectedElementId === `code_line_${lineNum}`;
              const elementId = `code_line_${lineNum}`;
              return (
                <motion.span
                  key={elementId}
                  data-element-id={elementId}
                  onClick={() => handleClickLine(lineNum)}
                  onKeyDown={handleLineKey(lineNum)}
                  role={onElementClick ? "button" : undefined}
                  aria-label={ariaLabelFor(
                    elementId,
                    `Code line ${lineNum}${isHighlighted ? ", currently executing" : ""}: ${line || "empty"}`,
                  )}
                  aria-pressed={isSelected}
                  tabIndex={onElementClick ? tabIndexFor(elementId) : -1}
                  className={[
                    "block border-l-2 py-0.5 pl-3 motion-safe:transition-all duration-300",
                    isHighlighted
                      ? "border-[#AEBBFF] bg-[#6B7DFF]/18 text-[#FFFDF7]"
                      : "border-transparent text-[#EAEAEA]",
                    isSelected ? "ring-1 ring-[#FFD96B]/70" : "",
                    onElementClick ? "cursor-pointer hover:bg-white/5 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#FFD96B]" : "",
                  ].join(" ")}
                  layout
                  {...motionProps[elementId]}
                >
                  <span className="mr-3 inline-block w-6 text-right text-[#777]">{lineNum}</span>
                  {line || " "}
                </motion.span>
              );
            })}
          </code>
        </pre>
      </div>
      {(state.variables?.length || state.call_stack?.length || state.output?.length) && (
        <div className="flex flex-col gap-2 md:w-56">
          {state.variables && state.variables.length > 0 && (
            <SidePanel title="Variables">
              {state.variables.map((v) => {
                const elementId = `code_variable_${v.name}`;
                const selected = selectedElementId === elementId;
                return (
                  <motion.button
                    key={elementId}
                    type="button"
                    onClick={() => handleClickVariable(v.name)}
                    disabled={!onElementClick}
                    aria-label={ariaLabelFor(
                      elementId,
                      `Variable ${v.name} equals ${v.value}`,
                    )}
                    aria-pressed={selected}
                    tabIndex={onElementClick ? tabIndexFor(elementId) : -1}
                    className={[
                      "flex items-center justify-between rounded-md px-2 py-1 text-xs motion-safe:transition-all",
                      selected
                        ? "border border-[#FFD96B] bg-[#FFF6DA]"
                        : "border border-[#D5CFE2] bg-[#F4ECFF] hover:bg-[#E8DEFF]",
                      onElementClick ? "cursor-pointer" : "cursor-default",
                      "focus:outline-none focus-visible:ring-2 focus-visible:ring-[#FFD96B]",
                    ].join(" ")}
                    layout
                    {...motionProps[elementId]}
                  >
                    <span className="font-bold text-[#3A2870]">{v.name}</span>
                    <span className="font-mono text-[#5B2EE0]">{v.value}</span>
                  </motion.button>
                );
              })}
            </SidePanel>
          )}
          {state.call_stack && state.call_stack.length > 0 && (
            <SidePanel title="Call stack">
              {state.call_stack.map((item, i) => (
                <span
                  key={`code_frame_${i}`}
                  className="rounded-md border border-[#D5CFE2] bg-[#F4ECFF] px-2 py-0.5 text-xs font-bold text-[#3A2870]"
                >
                  {item}
                </span>
              ))}
            </SidePanel>
          )}
          {state.output && state.output.length > 0 && (
            <SidePanel title="Output">
              <pre className="whitespace-pre-wrap font-mono text-xs text-[#3A2870]">
                {state.output.join("\n")}
              </pre>
            </SidePanel>
          )}
        </div>
      )}
    </div>
  );
}

function SidePanel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-[#E5DFEE] bg-white p-3 shadow-sm">
      <p className="text-[10px] font-bold uppercase tracking-wide text-[#7C4EF0]">{title}</p>
      <div className="mt-2 flex flex-wrap items-center gap-1">{children}</div>
    </div>
  );
}
