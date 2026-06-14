"use client";

/**
 * Visual renderer dispatcher (v2).
 *
 * Reads (model, frame_index) and routes to the correct base-type renderer.
 * Also handles support visuals (step_flow, practice_feedback, etc.) via
 * SupportVisualPayload — those bypass the model/frame contract.
 */

import type {
  SelectableElement,
  SupportVisualPayload,
  VisualModel,
} from "@/lib/visual_v2_types";
import { NodeLinkVisual } from "@/components/visuals_v2/NodeLinkVisual";
import { CodeExecutionPanel } from "@/components/visuals_v2/CodeExecutionPanel";
import { IndexedSequenceVisual } from "@/components/visuals_v2/IndexedSequenceVisual";
import { GridMatrixVisual } from "@/components/visuals_v2/GridMatrixVisual";
import { FormulaVisual } from "@/components/visuals_v2/FormulaVisual";
import { TableVisual } from "@/components/visuals_v2/TableVisual";
import { CoordinateGraphVisual } from "@/components/visuals_v2/CoordinateGraphVisual";
import { MemoryLayoutVisual } from "@/components/visuals_v2/MemoryLayoutVisual";
import { SetRegionVisual } from "@/components/visuals_v2/SetRegionVisual";
import { TimelineSequenceVisual } from "@/components/visuals_v2/TimelineSequenceVisual";
import { GeometricVisual } from "@/components/visuals_v2/GeometricVisual";
import { ImageIllustrationVisual } from "@/components/visuals_v2/ImageIllustrationVisual";
import { StepFlowSupport } from "@/components/visuals_v2/support/StepFlowSupport";
import { PracticeFeedbackSupport } from "@/components/visuals_v2/support/PracticeFeedbackSupport";
import { PathProgressSupport } from "@/components/visuals_v2/support/PathProgressSupport";
import { TopicSnapshotSupport } from "@/components/visuals_v2/support/TopicSnapshotSupport";
import { SourceAnnotationSupport } from "@/components/visuals_v2/support/SourceAnnotationSupport";
import {
  SHOW_VISUAL_DATA_INSTEAD_OF_RENDER,
  VisualDataPanel,
  modelDebugSections,
} from "@/lib/visualDebug";

type Props = {
  model?: VisualModel | null;
  frameIndex?: number | null;
  supportVisual?: SupportVisualPayload | null;
  onElementClick?: (el: SelectableElement) => void;
  selectedElementId?: string | null;
};

const SUPPORT_VISUAL_RENDERERS: Record<
  string,
  React.ComponentType<{
    payload: SupportVisualPayload;
    onElementClick?: (el: SelectableElement) => void;
    selectedElementId?: string | null;
  }>
> = {
  step_flow: StepFlowSupport,
  practice_feedback: PracticeFeedbackSupport,
  path_progress: PathProgressSupport,
  source_annotation: SourceAnnotationSupport,
  topic_snapshot: TopicSnapshotSupport,
};

export function VisualRenderer({
  model,
  frameIndex,
  supportVisual,
  onElementClick,
  selectedElementId,
}: Props) {
  // Visual DEBUG mode: show the data that WOULD generate this visual, not the drawing. The
  // caller's conditions for whether a visual renders are unchanged — only the output swaps.
  if (SHOW_VISUAL_DATA_INSTEAD_OF_RENDER) {
    if (supportVisual) {
      return (
        <VisualDataPanel
          title={`support · ${supportVisual.support_type}`}
          sections={[
            { label: "Support type", value: supportVisual.support_type },
            { label: "Full payload", value: supportVisual },
          ]}
        />
      );
    }
    if (!model) {
      return null;
    }
    return (
      <VisualDataPanel
        title={`${model.base_type} · ${model.mode}`}
        sections={modelDebugSections(model, frameIndex)}
      />
    );
  }

  // Support visual path (bypasses compilation)
  if (supportVisual) {
    const SupportRenderer = SUPPORT_VISUAL_RENDERERS[supportVisual.support_type];
    if (SupportRenderer) {
      return (
        <SupportRenderer
          payload={supportVisual}
          onElementClick={onElementClick}
          selectedElementId={selectedElementId}
        />
      );
    }
    // Unsupported support visual — minimal placeholder
    return (
      <div className="rounded-2xl border border-dashed border-[#D5CFE2] bg-[#F9F6FF] p-4 text-sm text-[#5B2EE0]">
        Support visual <code>{supportVisual.support_type}</code> not yet implemented.
      </div>
    );
  }

  if (!model || frameIndex == null) {
    return null;
  }

  const frame = model.frames[frameIndex];
  if (!frame) {
    return null;
  }

  // Dispatch by base_type
  switch (model.base_type) {
    case "node_link_diagram":
      return (
        <NodeLinkVisual
          model={model}
          frame={frame}
          onElementClick={onElementClick}
          selectedElementId={selectedElementId}
        />
      );
    case "code_execution_panel":
      return (
        <CodeExecutionPanel
          model={model}
          frame={frame}
          onElementClick={onElementClick}
          selectedElementId={selectedElementId}
        />
      );
    case "indexed_sequence_diagram":
      return (
        <IndexedSequenceVisual
          model={model}
          frame={frame}
          onElementClick={onElementClick}
          selectedElementId={selectedElementId}
        />
      );
    case "grid_matrix_diagram":
      return (
        <GridMatrixVisual
          model={model}
          frame={frame}
          onElementClick={onElementClick}
          selectedElementId={selectedElementId}
        />
      );
    case "formula_symbolic_expression":
      return (
        <FormulaVisual
          model={model}
          frame={frame}
          onElementClick={onElementClick}
          selectedElementId={selectedElementId}
        />
      );
    case "table_diagram":
      return (
        <TableVisual
          model={model}
          frame={frame}
          onElementClick={onElementClick}
          selectedElementId={selectedElementId}
        />
      );
    case "coordinate_graph":
      return (
        <CoordinateGraphVisual
          model={model}
          frame={frame}
          onElementClick={onElementClick}
          selectedElementId={selectedElementId}
        />
      );
    case "memory_layout_diagram":
      return (
        <MemoryLayoutVisual
          model={model}
          frame={frame}
          onElementClick={onElementClick}
          selectedElementId={selectedElementId}
        />
      );
    case "set_region_diagram":
      return (
        <SetRegionVisual
          model={model}
          frame={frame}
          onElementClick={onElementClick}
          selectedElementId={selectedElementId}
        />
      );
    case "timeline_sequence_interaction":
      return (
        <TimelineSequenceVisual
          model={model}
          frame={frame}
          onElementClick={onElementClick}
          selectedElementId={selectedElementId}
        />
      );
    case "geometric_diagram":
      return (
        <GeometricVisual
          model={model}
          frame={frame}
          onElementClick={onElementClick}
          selectedElementId={selectedElementId}
        />
      );
    case "image_real_world_illustration":
      return (
        <ImageIllustrationVisual
          model={model}
          frame={frame}
          onElementClick={onElementClick}
          selectedElementId={selectedElementId}
        />
      );
    default:
      return (
        <div className="rounded-2xl border border-dashed border-[#D5CFE2] bg-[#F9F6FF] p-4 text-sm text-[#5B2EE0]">
          Unknown base_type: <code>{model.base_type}</code>
        </div>
      );
  }
}
