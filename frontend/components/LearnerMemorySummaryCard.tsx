"use client";

import type { ClassMemorySummary, GlobalMemorySummary } from "@/lib/api";

type LearnerMemorySummaryCardProps = {
  memorySummary: ClassMemorySummary | GlobalMemorySummary | null;
  isLoading?: boolean;
  title?: string;
};

export default function LearnerMemorySummaryCard({
  memorySummary,
  isLoading = false,
  title = "What Azalea remembers",
}: LearnerMemorySummaryCardProps) {
  if (isLoading) {
    return (
      <div className="rounded-3xl border border-border bg-background p-5 shadow-sm">
        <p className="text-sm font-semibold text-foreground">{title}</p>
        <p className="mt-2 text-sm text-muted-foreground">
          Reading learner memory...
        </p>
      </div>
    );
  }

  if (!memorySummary) {
    return (
      <div className="rounded-3xl border border-border bg-background p-5 shadow-sm">
        <p className="text-sm font-semibold text-foreground">{title}</p>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          Not enough learning history yet. Azalea will build this as you answer,
          review, and practice.
        </p>
      </div>
    );
  }

  const isClassMemory = "class_id" in memorySummary;

  if (!isClassMemory) {
    return (
      <div className="rounded-3xl border border-border bg-background p-5 shadow-sm">
        <p className="text-sm font-semibold text-foreground">{title}</p>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          {memorySummary.recommended_guidance}
        </p>

        <div className="mt-5 grid gap-3 md:grid-cols-2">
          <MemoryMiniPanel
            label="Stable patterns"
            value={
              memorySummary.stable_patterns.slice(0, 4).join(", ") ||
              "Not enough stable patterns yet"
            }
          />

          <MemoryMiniPanel
            label="Fragile patterns"
            value={
              memorySummary.fragile_patterns.slice(0, 4).join(", ") ||
              "No fragile patterns right now"
            }
          />
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-3xl border border-border bg-background p-5 shadow-sm">
      <p className="text-sm font-semibold text-foreground">{title}</p>

      <p className="mt-2 text-sm leading-6 text-muted-foreground">
        {memorySummary.recommended_guidance}
      </p>

      <div className="mt-5 grid gap-3 md:grid-cols-2">
        <MemoryMiniPanel
          label="Stable"
          value={
            memorySummary.concepts_to_skip.slice(0, 4).join(", ") ||
            "Not enough stable concepts yet"
          }
        />

        <MemoryMiniPanel
          label="Needs light repair"
          value={
            memorySummary.concepts_to_briefly_repair.slice(0, 4).join(", ") ||
            "No fragile concepts right now"
          }
        />
      </div>
    </div>
  );
}

function MemoryMiniPanel({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border bg-muted/30 p-4">
      <p className="text-xs font-bold uppercase tracking-wide text-primary">
        {label}
      </p>
      <p className="mt-2 text-sm leading-6 text-foreground">{value}</p>
    </div>
  );
}
