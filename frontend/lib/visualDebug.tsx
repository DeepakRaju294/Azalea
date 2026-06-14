"use client";

// VISUAL DEBUG MODE.
// While we get the worked-example / code-walkthrough TEXT content right, we do NOT draw card
// visuals. Every condition that decides WHETHER a card has a visual is unchanged — only the
// drawn output is swapped for the underlying data that WOULD generate it (model, current-frame
// state, code, plan, description), so we can see exactly what the system is producing.
// Set to false to restore real visual rendering.
export const SHOW_VISUAL_DATA_INSTEAD_OF_RENDER = true;

export interface VisualDataSection {
  label: string;
  value: unknown;
}

export function VisualDataPanel({
  title,
  sections,
}: {
  title: string;
  sections: VisualDataSection[];
}) {
  return (
    <div className="w-full rounded-2xl border border-dashed border-[#C9BEEA] bg-[#FBFAFF] p-4 text-left shadow-sm shadow-purple-100/30">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-[10px] font-black uppercase tracking-widest text-primary">
          Visual data (debug)
        </span>
        <span className="text-sm font-bold text-foreground">{title}</span>
      </div>
      <div className="space-y-3">
        {sections.map((section, i) => (
          <div key={i}>
            <div className="text-[11px] font-black uppercase tracking-wider text-muted-foreground">
              {section.label}
            </div>
            {typeof section.value === "string" ? (
              <div className="mt-0.5 whitespace-pre-wrap break-words font-mono text-[12px] leading-relaxed text-foreground">
                {section.value || "—"}
              </div>
            ) : (
              <pre className="mt-0.5 max-h-[440px] overflow-auto rounded-lg bg-[#F1ECFB] p-2 text-[11px] leading-snug text-foreground">
                {(() => {
                  try {
                    return JSON.stringify(section.value, null, 2);
                  } catch {
                    return String(section.value);
                  }
                })()}
              </pre>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// A model/frame visual's debug sections — used by the v2 renderer and any model-based slot.
export function modelDebugSections(
  model: unknown,
  frameIndex?: number | null,
): VisualDataSection[] {
  const m = (model ?? {}) as {
    base_type?: string;
    mode?: string;
    id?: string;
    description?: string;
    frames?: { state?: unknown }[];
  };
  const frames = m.frames ?? [];
  const idx = frameIndex ?? 0;
  const sections: VisualDataSection[] = [
    { label: "Model", value: `${m.base_type} / ${m.mode}  (id: ${m.id})` },
  ];
  if (m.description) sections.push({ label: "Description", value: String(m.description) });
  sections.push({
    label: `Current frame (${idx + 1} / ${frames.length})`,
    value: frames[idx]?.state ?? frames[0]?.state ?? {},
  });
  sections.push({ label: "Full model", value: model });
  return sections;
}
