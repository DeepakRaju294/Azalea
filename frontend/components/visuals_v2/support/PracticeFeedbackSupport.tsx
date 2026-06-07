"use client";

/**
 * Practice-feedback support visual (v2).
 *
 * Two-phase: prediction prompt → reveal correct + comparison.
 * Today's minimal version just shows the prompt; the practice flow lives
 * on the learn-v2 page which manages the answer state.
 */

import type { SupportVisualPayload, SelectableElement } from "@/lib/visual_v2_types";

type Props = {
  payload: SupportVisualPayload;
  onElementClick?: (el: SelectableElement) => void;
  selectedElementId?: string | null;
};

export function PracticeFeedbackSupport({ payload, onElementClick, selectedElementId }: Props) {
  const description = String(payload.data?.description || "");
  const purpose = String(payload.data?.purpose || "");

  return (
    <div className="rounded-2xl border border-[#FFD96B] bg-[#FFF6DA] p-5 shadow-sm">
      <p className="text-xs font-bold uppercase tracking-wide text-[#7C4EF0]">
        Predict, then check
      </p>
      <ol className="mt-3 flex flex-col gap-2 text-sm leading-6 text-[#3A2870]">
        <li>1. Read the prompt.</li>
        <li>2. Choose your answer before revealing the solution.</li>
        <li>3. Compare. Repair any mismatch.</li>
      </ol>
      {description && (
        <p className="mt-3 rounded-xl border border-[#E5DFEE] bg-white p-3 text-sm text-[#3A2870]">
          {description}
        </p>
      )}
      {purpose && (
        <p className="mt-2 text-xs italic text-[#5B2EE0]">{purpose}</p>
      )}
      {payload.selectable_elements.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1">
          {payload.selectable_elements.map((el) => (
            <button
              key={el.element_id}
              type="button"
              onClick={() => onElementClick?.(el)}
              disabled={!onElementClick}
              className={[
                "rounded-md border px-2 py-0.5 text-xs font-bold motion-safe:transition-all",
                selectedElementId === el.element_id
                  ? "border-[#FFD96B] bg-white"
                  : "border-[#D5CFE2] bg-white hover:bg-[#E8DEFF]",
              ].join(" ")}
            >
              {el.semantic_label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
