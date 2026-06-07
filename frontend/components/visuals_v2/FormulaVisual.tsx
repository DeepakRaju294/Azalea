"use client";

/**
 * Formula / symbolic expression visual (v2).
 *
 * Lightweight dependency-free renderer for formula breakdowns and symbolic
 * worked examples. It renders expressions as source text for now; KaTeX can
 * be layered in later without changing the compiler contract.
 */

import { motion } from "framer-motion";
import type { SelectableElement, VisualFrame, VisualModel } from "@/lib/visual_v2_types";
import { useInteractivity } from "@/components/visuals_v2/InteractivityLayer";
import { useMotionTransitionProps } from "@/components/visuals_v2/TransitionLayer";

type FormulaBase = {
  expression?: string;
  symbols?: {
    symbol: string;
    meaning?: string;
    value?: string;
    element_id?: string;
  }[];
  assumptions?: string[];
  mode?: string;
};

type FormulaFrameState = {
  active_symbol?: string;
  active_expression?: string;
  substitution?: Record<string, string>;
  transformed_expression?: string;
  equivalence_chain?: string[];
};

type Props = {
  model: VisualModel;
  frame: VisualFrame;
  onElementClick?: (el: SelectableElement) => void;
  selectedElementId?: string | null;
};

function displayMode(mode?: string) {
  return (mode || "formula").replace(/_/g, " ");
}

function symbolElementId(symbol: string, fallback?: string) {
  return fallback || `symbol_${symbol}`;
}

export function FormulaVisual({
  model,
  frame,
  onElementClick,
  selectedElementId,
}: Props) {
  const base = model.base as FormulaBase;
  const state = frame.state as FormulaFrameState;
  const motionProps = useMotionTransitionProps(frame.transitions || []);
  const symbols = base.symbols || [];
  const assumptions = base.assumptions || [];
  const chain = state.equivalence_chain || [];
  const substitutions = state.substitution || {};
  const transformed = state.transformed_expression || base.expression || "";
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
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-black uppercase tracking-wide text-[#7C4EF0]">
            {displayMode(model.mode)}
          </p>
          <p className="mt-1 text-sm text-[#5B526D]">
            Symbols and active transformations are selectable.
          </p>
        </div>
        {Object.keys(substitutions).length > 0 && (
          <span className="rounded-full border border-[#D5CFE2] bg-[#F4ECFF] px-3 py-1 text-xs font-bold text-[#5B2EE0]">
            substitution
          </span>
        )}
      </div>

      <motion.button
        type="button"
        onClick={() => handleClick("expression_base")}
        disabled={!onElementClick}
        aria-label={ariaLabelFor("expression_base", `Base expression ${transformed || base.expression || "formula"}`)}
        tabIndex={onElementClick ? tabIndexFor("expression_base") : -1}
        className={[
          "w-full rounded-2xl border p-5 text-center motion-safe:transition-all",
          selectedElementId === "expression_base" || state.active_expression
            ? "border-[#7C4EF0] bg-[#F4ECFF] shadow-sm"
            : "border-[#E5DFEE] bg-[#FBFAFF]",
          onElementClick ? "cursor-pointer hover:border-[#C1A8FF]" : "cursor-default",
        ].join(" ")}
        layout
        {...motionProps.expression_base}
      >
        <p className="font-mono text-lg font-black leading-relaxed text-[#3A2870]">
          {transformed || base.expression || "Formula"}
        </p>
      </motion.button>

      {symbols.length > 0 && (
        <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {symbols.map((item, index) => {
            const elementId = symbolElementId(item.symbol, item.element_id);
            const active = state.active_symbol === item.symbol;
            const selected = selectedElementId === elementId;
            const substitutionValue = substitutions[item.symbol];
            return (
              <motion.button
                key={`${elementId}_${index}`}
                type="button"
                onClick={() => handleClick(elementId)}
                disabled={!onElementClick}
                aria-label={ariaLabelFor(elementId, `Symbol ${item.symbol}: ${item.meaning || item.value || ""}`)}
                tabIndex={onElementClick ? tabIndexFor(elementId) : -1}
                className={[
                  "rounded-xl border p-3 text-left motion-safe:transition-all duration-300",
                  active
                    ? "scale-[1.02] border-[#5B2EE0] bg-[#7C4EF0] text-white shadow-lg shadow-[#7C4EF0]/15"
                    : selected
                      ? "border-[#FFD96B] bg-[#FFF6DA] text-[#3A2870]"
                      : "border-[#E5DFEE] bg-white text-[#3A2870] hover:bg-[#F4ECFF]",
                  onElementClick ? "cursor-pointer" : "cursor-default",
                ].join(" ")}
                layout
                {...motionProps[elementId]}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-base font-black">{item.symbol}</span>
                  {(item.value || substitutionValue) && (
                    <span
                      className={[
                        "rounded-full px-2 py-0.5 text-xs font-bold",
                        active ? "bg-white/20 text-white" : "bg-[#F4ECFF] text-[#5B2EE0]",
                      ].join(" ")}
                    >
                      {substitutionValue || item.value}
                    </span>
                  )}
                </div>
                {item.meaning && (
                  <p className={["mt-1 text-xs leading-5", active ? "text-white/85" : "text-[#5B526D]"].join(" ")}>
                    {item.meaning}
                  </p>
                )}
              </motion.button>
            );
          })}
        </div>
      )}

      {chain.length > 0 && (
        <div className="mt-4 rounded-2xl border border-[#E5DFEE] bg-[#FBFAFF] p-4">
          <p className="text-xs font-black uppercase tracking-wide text-[#7C4EF0]">
            derivation
          </p>
          <div className="mt-3 flex flex-col gap-2">
            {chain.map((expression, index) => {
              const elementId = `equation_${index}`;
              return (
                <motion.button
                  key={elementId}
                  type="button"
                  onClick={() => handleClick(elementId)}
                  disabled={!onElementClick}
                  aria-label={ariaLabelFor(elementId, `Equation step ${index + 1}: ${expression}`)}
                  tabIndex={onElementClick ? tabIndexFor(elementId) : -1}
                  className={[
                    "rounded-xl border px-4 py-3 text-left font-mono text-sm font-bold motion-safe:transition-all",
                    selectedElementId === elementId
                      ? "border-[#FFD96B] bg-[#FFF6DA] text-[#3A2870]"
                      : "border-[#E5DFEE] bg-white text-[#3A2870] hover:bg-[#F4ECFF]",
                    onElementClick ? "cursor-pointer" : "cursor-default",
                  ].join(" ")}
                  layout
                  {...motionProps[elementId]}
                >
                  <span className="mr-3 text-[#9A8FB0]">{index + 1}</span>
                  {expression}
                </motion.button>
              );
            })}
          </div>
        </div>
      )}

      {assumptions.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {assumptions.map((assumption, index) => (
            <span
              key={`${assumption}_${index}`}
              className="rounded-full border border-[#D5CFE2] bg-white px-3 py-1 text-xs font-bold text-[#5B526D]"
            >
              {assumption}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
