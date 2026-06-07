"use client";

import type { AlignmentMetrics } from "@/lib/api";

type AlignmentMetricsCardProps = {
  metrics: AlignmentMetrics | null;
  isLoading?: boolean;
};

export default function AlignmentMetricsCard({
  metrics,
  isLoading = false,
}: AlignmentMetricsCardProps) {
  if (isLoading) {
    return (
      <div className="rounded-3xl border border-border bg-background p-5 shadow-sm">
        <p className="text-sm font-semibold text-foreground">
          Learning alignment
        </p>
        <p className="mt-2 text-sm text-muted-foreground">
          Checking teaching depth...
        </p>
      </div>
    );
  }

  if (!metrics) {
    return (
      <div className="rounded-3xl border border-border bg-background p-5 shadow-sm">
        <p className="text-sm font-semibold text-foreground">
          Learning alignment
        </p>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          Not enough activity yet to estimate teaching alignment.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-3xl border border-border bg-background p-5 shadow-sm">
      <p className="text-sm font-semibold text-foreground">
        Learning alignment
      </p>

      <p className="mt-2 text-sm leading-6 text-muted-foreground">
        {metrics.summary}
      </p>

      <div className="mt-5 grid gap-3 md:grid-cols-2">
        <MetricPill
          label="Overteaching risk"
          value={formatScore(metrics.overteaching_score)}
        />
        <MetricPill
          label="Underteaching risk"
          value={formatScore(metrics.underteaching_score)}
        />
        <MetricPill
          label="Confidence calibration"
          value={formatScore(metrics.confidence_calibration_score)}
        />
        <MetricPill
          label="Transfer success"
          value={formatScore(metrics.transfer_success_rate)}
        />
      </div>
    </div>
  );
}

function MetricPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border bg-muted/30 p-4">
      <p className="text-xs font-bold uppercase tracking-wide text-primary">
        {label}
      </p>
      <p className="mt-2 text-lg font-semibold text-foreground">{value}</p>
    </div>
  );
}

function formatScore(value: number) {
  return `${Math.round(value * 100)}%`;
}