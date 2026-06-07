"use client";

/**
 * Path-progress support visual (v2). Roadmap cards showing where in the
 * study path the learner is.
 */

import type { SupportVisualPayload, SelectableElement } from "@/lib/visual_v2_types";

type Props = {
  payload: SupportVisualPayload;
  onElementClick?: (el: SelectableElement) => void;
  selectedElementId?: string | null;
};

export function PathProgressSupport({ payload, onElementClick, selectedElementId }: Props) {
  const description = String(payload.data?.description || "");
  const steps = payload.selectable_elements.filter((el) => el.element_type === "support_step");

  return (
    <div className="rounded-2xl border border-[#E5DFEE] bg-white p-5 shadow-sm">
      <p className="text-xs font-bold uppercase tracking-wide text-[#7C4EF0]">
        Where you are
      </p>
      {description && (
        <p className="mt-2 text-sm text-[#3A2870]">{description}</p>
      )}
      {steps.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          {steps.map((step, i) => {
            const selected = selectedElementId === step.element_id;
            const isCurrent = Boolean(step.payload?.current);
            return (
              <div key={step.element_id} className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => onElementClick?.(step)}
                  disabled={!onElementClick}
                  className={[
                    "flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-bold motion-safe:transition-all",
                    selected
                      ? "border-[#FFD96B] bg-[#FFF6DA] text-[#3A2870]"
                      : isCurrent
                        ? "border-[#7C4EF0] bg-[#7C4EF0] text-white"
                        : "border-[#D5CFE2] bg-[#F4ECFF] text-[#3A2870] hover:bg-[#E8DEFF]",
                  ].join(" ")}
                >
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-white/90 text-[10px] text-[#3A2870]">
                    {i + 1}
                  </span>
                  {step.semantic_label}
                </button>
                {i < steps.length - 1 && (
                  <span className="text-[#D5CFE2]">→</span>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
