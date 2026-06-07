import { Sparkles, BookOpen, Gauge, Brain, ArrowRight } from "lucide-react";

import type {
  DiagnosticMode,
  SelfReportResult,
  StartingMode,
} from "@/lib/api";
import { submitSelfReport } from "@/lib/api";

type TopicCalibrationCardProps = {
  topicId: string;
  mode?: DiagnosticMode;
  onCalibrated: (result: {
    source: "self_report" | "diagnostic";
    estimatedState?: string;
    recommendedStartingMode: StartingMode;
    explanationDensity?: string;
    selfReportLevel?: number;
    shouldOfferDiagnostic?: boolean;
  }) => void;
  onStartDiagnostic: (selfReportLevel?: number) => void;
  onJumpToPractice?: () => void;
};

const options = [
  {
    level: 0,
    title: "Teach from scratch",
    description: "I do not know this yet. Start with the foundation.",
    icon: BookOpen,
  },
  {
    level: 1,
    title: "Fast refresher",
    description: "I have seen this before, but I need the main idea rebuilt.",
    icon: Gauge,
  },
  {
    level: 2,
    title: "Mostly know it",
    description: "Skip the obvious parts and focus on clarifying details.",
    icon: Brain,
  },
  {
    level: 3,
    title: "I am comfortable",
    description: "Start with edge cases, reinforcement, or practice.",
    icon: Sparkles,
  },
];

export default function TopicCalibrationCard({
  topicId,
  mode = "topic_start",
  onCalibrated,
  onStartDiagnostic,
  onJumpToPractice,
}: TopicCalibrationCardProps) {
  async function handleSelect(level: number) {
    const result: SelfReportResult = await submitSelfReport(topicId, {
      level,
      mode,
    });

    onCalibrated({
      source: "self_report",
      estimatedState: result.estimated_state,
      recommendedStartingMode: result.recommended_starting_mode,
      explanationDensity: result.explanation_density,
      selfReportLevel: result.self_report_level,
      shouldOfferDiagnostic: result.should_offer_diagnostic,
    });
  }

  return (
    <div className="mx-auto flex min-h-[70vh] w-full max-w-4xl items-center justify-center px-4 py-10">
      <div className="w-full rounded-[2rem] border border-zinc-200 bg-white p-6 shadow-sm">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-2xl bg-purple-50 text-purple-700">
            <Sparkles className="h-5 w-5" />
          </div>

          <h2 className="text-2xl font-semibold tracking-tight text-zinc-950">
            How should we start?
          </h2>

          <p className="mx-auto mt-2 max-w-2xl text-sm leading-6 text-zinc-600">
            Pick the starting point that feels closest. Azalea will adjust if
            this is too much or too little.
          </p>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          {options.map((option) => {
            const Icon = option.icon;

            return (
              <button
                key={option.level}
                type="button"
                onClick={() => handleSelect(option.level)}
                className="group rounded-3xl border border-zinc-200 bg-zinc-50/70 p-4 text-left transition hover:border-purple-200 hover:bg-purple-50/60"
              >
                <div className="mb-4 flex items-center justify-between">
                  <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-white text-purple-700 shadow-sm">
                    <Icon className="h-5 w-5" />
                  </div>

                  <ArrowRight className="h-4 w-4 text-zinc-400 transition group-hover:translate-x-0.5 group-hover:text-purple-700" />
                </div>

                <h3 className="text-sm font-semibold text-zinc-950">
                  {option.title}
                </h3>

                <p className="mt-1 text-sm leading-6 text-zinc-600">
                  {option.description}
                </p>
              </button>
            );
          })}
        </div>

        <div className="mt-5 rounded-3xl border border-purple-100 bg-purple-50/60 p-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-sm font-medium text-zinc-950">
                Not sure where to start?
              </p>
              <p className="mt-1 text-sm leading-6 text-zinc-600">
                Azalea can ask a few quick questions and skip what you do not
                need.
              </p>
            </div>

            <button
              type="button"
              onClick={() => onStartDiagnostic()}
              className="rounded-2xl bg-purple-700 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-purple-800"
            >
              Check what I know first
            </button>
          </div>
        </div>

        {onJumpToPractice && (
          <div className="mt-4 flex justify-center">
            <button
              type="button"
              onClick={onJumpToPractice}
              className="text-sm font-medium text-zinc-500 transition hover:text-purple-700"
            >
              Skip lesson and jump to practice
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
