"use client";

/**
 * Step flow support visual (v2).
 *
 * Renders the intent description as a simple process map. Used when no
 * concrete base_type fits (general procedures, "how this algorithm works"
 * style cards). Each step is clickable.
 */

import type { SupportVisualPayload, SelectableElement } from "@/lib/visual_v2_types";

type Props = {
  payload: SupportVisualPayload;
  onElementClick?: (el: SelectableElement) => void;
  selectedElementId?: string | null;
};

export function StepFlowSupport({ payload, onElementClick, selectedElementId }: Props) {
  const description = String(payload.data?.description || "");
  const purpose = String(payload.data?.purpose || "");

  // For the support visual, the steps come from selectable_elements when
  // present. Otherwise just render the description as one panel.
  const steps = payload.selectable_elements.filter((el) => el.element_type === "support_step");

  return (
    <div className="rounded-2xl border border-[#E5DFEE] bg-white p-5 shadow-sm">
      {description && (
        <p className="text-sm leading-6 text-[#3A2870]">{description}</p>
      )}
      {purpose && (
        <p className="mt-2 text-xs text-[#5B2EE0]">{purpose}</p>
      )}
      {steps.length > 0 && (
        <ol className="mt-4 flex flex-col gap-2">
          {steps.map((step, i) => {
            const selected = selectedElementId === step.element_id;
            return (
              <li key={step.element_id}>
                <button
                  type="button"
                  onClick={() => onElementClick?.(step)}
                  disabled={!onElementClick}
                  className={[
                    "flex w-full items-start gap-3 rounded-xl border px-3 py-2 text-left text-sm motion-safe:transition-all",
                    selected
                      ? "border-[#FFD96B] bg-[#FFF6DA]"
                      : "border-[#D5CFE2] bg-[#F4ECFF] hover:bg-[#E8DEFF]",
                    onElementClick ? "cursor-pointer" : "cursor-default",
                  ].join(" ")}
                >
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#7C4EF0] text-xs font-bold text-white">
                    {i + 1}
                  </span>
                  <span className="text-[#3A2870]">{step.semantic_label}</span>
                </button>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
