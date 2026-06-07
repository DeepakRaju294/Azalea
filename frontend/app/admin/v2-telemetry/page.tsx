"use client";

import { useEffect, useState } from "react";

import {
  getV2TelemetrySummary,
  type V2TelemetryPipelineSummary,
  type V2TelemetrySummary,
} from "@/lib/api_v2";

function pct(value: number | undefined) {
  if (value == null || Number.isNaN(value)) return "0%";
  return `${Math.round(value * 1000) / 10}%`;
}

function seconds(value: number | undefined) {
  if (value == null || Number.isNaN(value)) return "0.0s";
  return `${value.toFixed(1)}s`;
}

function PipelineCard({
  name,
  summary,
}: {
  name: string;
  summary: V2TelemetryPipelineSummary;
}) {
  const baseTypes = Object.entries(summary.base_type_counts || {}).sort(
    (a, b) => b[1] - a[1],
  );
  return (
    <section className="rounded-2xl border border-[#E5DFEE] bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-black uppercase tracking-wide text-[#7C4EF0]">
            pipeline
          </p>
          <h2 className="mt-1 text-2xl font-black text-[#12111A]">{name}</h2>
        </div>
        <span
          className={[
            "rounded-full px-3 py-1 text-xs font-black",
            (summary.error_rate || 0) > 0.05
              ? "bg-[#FFEBEE] text-[#B71C1C]"
              : "bg-[#E8F5E9] text-[#1B5E20]",
          ].join(" ")}
        >
          {pct(summary.error_rate)} errors
        </span>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <Metric label="Runs" value={String(summary.count ?? 0)} />
        <Metric label="Avg Duration" value={seconds(summary.avg_duration_seconds)} />
        <Metric label="Success" value={String(summary.success ?? 0)} />
        <Metric label="Failure" value={String(summary.failure ?? 0)} />
      </div>
      <div className="mt-4 rounded-xl border border-[#E5DFEE] bg-[#FBFAFF] p-3">
        <p className="text-xs font-black uppercase tracking-wide text-[#7C4EF0]">
          validator averages
        </p>
        <p className="mt-1 text-sm text-[#5B526D]">
          Errors: {(summary.validator_errors_per_lesson ?? 0).toFixed(2)} ·
          Warnings: {(summary.validator_warnings_per_lesson ?? 0).toFixed(2)}
        </p>
      </div>
      {baseTypes.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {baseTypes.map(([baseType, count]) => (
            <span
              key={baseType}
              className="rounded-full border border-[#D5CFE2] bg-[#F4ECFF] px-3 py-1 text-xs font-bold text-[#5B2EE0]"
            >
              {baseType.replace(/_/g, " ")} · {count}
            </span>
          ))}
        </div>
      )}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[#E5DFEE] bg-[#FBFAFF] p-3">
      <p className="text-[10px] font-black uppercase tracking-wide text-[#7C4EF0]">
        {label}
      </p>
      <p className="mt-1 text-lg font-black text-[#12111A]">{value}</p>
    </div>
  );
}

export default function V2TelemetryPage() {
  const [summary, setSummary] = useState<V2TelemetrySummary | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const data = await getV2TelemetrySummary();
        if (!cancelled) setSummary(data);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load telemetry");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const pipelines = Object.entries(summary?.by_pipeline || {});

  return (
    <main className="min-h-screen bg-[#FBF8FF] p-8">
      <div className="mx-auto max-w-6xl">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-black uppercase tracking-wide text-[#7C4EF0]">
              Visual system v2
            </p>
            <h1 className="mt-2 text-4xl font-black text-[#12111A]">
              Telemetry Dashboard
            </h1>
            <p className="mt-2 text-sm text-[#5B526D]">
              {summary
                ? `${summary.rows_read} telemetry rows read${summary.log_path ? ` from ${summary.log_path}` : ""}.`
                : "Loading generation health, alerts, and visual usage."}
            </p>
          </div>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="rounded-full border border-[#D5CFE2] bg-white px-4 py-2 text-sm font-bold text-[#3A2870] hover:bg-[#F4ECFF]"
          >
            Refresh
          </button>
        </div>

        {loading && (
          <div className="mt-8 rounded-2xl border border-[#E5DFEE] bg-white p-5 text-sm font-semibold text-[#5B2EE0]">
            Loading telemetry...
          </div>
        )}

        {error && (
          <div className="mt-8 rounded-2xl border border-[#F4B4B4] bg-[#FFEBEE] p-5 text-sm font-semibold text-[#B71C1C]">
            {error}
          </div>
        )}

        {!loading && !error && summary && (
          <>
            {(summary.alerts || []).length > 0 ? (
              <section className="mt-8 rounded-2xl border border-[#FFD96B] bg-[#FFF6DA] p-5">
                <p className="text-xs font-black uppercase tracking-wide text-[#7C4EF0]">
                  active alerts
                </p>
                <ul className="mt-3 flex flex-col gap-2 text-sm font-semibold text-[#3A2870]">
                  {(summary.alerts || []).map((alert, index) => (
                    <li key={`${alert}_${index}`}>{alert}</li>
                  ))}
                </ul>
              </section>
            ) : (
              <section className="mt-8 rounded-2xl border border-[#D5E8D4] bg-[#E8F5E9] p-5 text-sm font-bold text-[#1B5E20]">
                No active v2 alert thresholds are firing.
              </section>
            )}

            <div className="mt-6 grid gap-5 lg:grid-cols-2">
              {pipelines.length > 0 ? (
                pipelines.map(([name, pipelineSummary]) => (
                  <PipelineCard key={name} name={name} summary={pipelineSummary} />
                ))
              ) : (
                <div className="rounded-2xl border border-dashed border-[#D5CFE2] bg-white p-5 text-sm font-semibold text-[#5B2EE0]">
                  No telemetry rows are available yet.
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </main>
  );
}
