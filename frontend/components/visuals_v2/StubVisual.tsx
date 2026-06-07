"use client";

/**
 * Stub visual renderer (v2).
 *
 * STATUS: DEAD CODE — slated for removal in Phase 8.
 *
 * Was used for base_types whose real frontend renderer hadn't been built
 * yet. As of Phase 6 completion, all 12 base_types have real renderers
 * and VisualRenderer no longer routes here. Kept temporarily in case a
 * future base_type is added without a paired renderer.
 *
 * Removal blocked on: see PHASE_8_DECOMMISSION.md (project root).
 */

import type { VisualModel, VisualFrame } from "@/lib/visual_v2_types";

type Props = {
  model: VisualModel;
  frame: VisualFrame;
};

const FRIENDLY_NAMES: Record<string, string> = {
  formula_symbolic_expression: "Formula",
  table_diagram: "Table",
  grid_matrix_diagram: "Matrix / DP table",
  coordinate_graph: "Coordinate graph",
  memory_layout_diagram: "Memory layout",
  geometric_diagram: "Geometric diagram",
  timeline_sequence_interaction: "Timeline / sequence",
  set_region_diagram: "Set / region",
  image_real_world_illustration: "Illustration",
};

export function StubVisual({ model, frame }: Props) {
  const base = model.base as Record<string, unknown>;
  const friendlyName = FRIENDLY_NAMES[model.base_type] || model.base_type;
  const description = String(base.intended_description || "");
  const purpose = String(base.intended_purpose || "");
  const annotation = frame.annotations?.[0]?.text || "";

  return (
    <div className="rounded-2xl border border-dashed border-[#D5CFE2] bg-[#F9F6FF] p-6 text-center shadow-sm">
      <p className="text-xs font-bold uppercase tracking-wide text-[#7C4EF0]">
        {friendlyName} — placeholder
      </p>
      {description && (
        <p className="mt-3 text-sm font-semibold text-[#3A2870]">{description}</p>
      )}
      {purpose && (
        <p className="mt-2 text-xs text-[#5B2EE0]">{purpose}</p>
      )}
      {annotation && (
        <p className="mt-3 text-xs italic text-[#9A8FB0]">{annotation}</p>
      )}
      <p className="mt-4 text-[10px] uppercase tracking-wide text-[#9A8FB0]">
        Compiler not yet implemented for {model.base_type} / {model.mode}
      </p>
    </div>
  );
}
