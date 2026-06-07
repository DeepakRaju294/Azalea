"use client";

/**
 * Source-annotation support visual (v2). Quotes a passage from the
 * uploaded material with the relevant annotation highlights.
 */

import type { SupportVisualPayload, SelectableElement } from "@/lib/visual_v2_types";

type Props = {
  payload: SupportVisualPayload;
  onElementClick?: (el: SelectableElement) => void;
  selectedElementId?: string | null;
};

export function SourceAnnotationSupport({ payload, onElementClick, selectedElementId }: Props) {
  const description = String(payload.data?.description || "");
  const sourceText = String(payload.data?.source_text || description);
  const annotations = payload.selectable_elements.filter(
    (el) => el.element_type === "support_step",
  );

  return (
    <div className="rounded-2xl border border-[#E5DFEE] bg-white p-5 shadow-sm">
      <p className="text-xs font-bold uppercase tracking-wide text-[#7C4EF0]">
        From the source material
      </p>
      {sourceText && (
        <blockquote className="mt-3 border-l-4 border-[#7C4EF0] bg-[#FBF8FF] p-3 text-sm italic leading-6 text-[#3A2870]">
          {sourceText}
        </blockquote>
      )}
      {annotations.length > 0 && (
        <div className="mt-3 flex flex-col gap-1">
          {annotations.map((ann) => (
            <button
              key={ann.element_id}
              type="button"
              onClick={() => onElementClick?.(ann)}
              disabled={!onElementClick}
              className={[
                "rounded-md border px-3 py-1 text-left text-xs motion-safe:transition-all",
                selectedElementId === ann.element_id
                  ? "border-[#FFD96B] bg-[#FFF6DA]"
                  : "border-[#D5CFE2] bg-[#F4ECFF] hover:bg-[#E8DEFF]",
              ].join(" ")}
            >
              {ann.semantic_label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
