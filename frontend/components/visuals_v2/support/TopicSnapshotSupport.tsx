"use client";

/**
 * Topic-snapshot support visual (v2). Ultra-light intro preview when the
 * visual_domain is "generic" and no concrete base type fits.
 */

import type { SupportVisualPayload } from "@/lib/visual_v2_types";

type Props = {
  payload: SupportVisualPayload;
};

export function TopicSnapshotSupport({ payload }: Props) {
  const description = String(payload.data?.description || "");
  const purpose = String(payload.data?.purpose || "");

  return (
    <div className="rounded-2xl border border-[#E5DFEE] bg-gradient-to-br from-[#F4ECFF] to-[#FBF8FF] p-5 text-center shadow-sm">
      {description && (
        <p className="text-sm font-semibold text-[#3A2870]">{description}</p>
      )}
      {purpose && (
        <p className="mt-2 text-xs text-[#5B2EE0]">{purpose}</p>
      )}
    </div>
  );
}
