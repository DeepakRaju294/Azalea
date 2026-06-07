import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, ArrowRight, CheckCircle2, Sparkles } from "lucide-react";

import type {
  DiagnosticMode,
  DiagnosticQuestion,
  StartingMode,
  StartDiagnosticResult,
  SubmitDiagnosticResult,
} from "@/lib/api";
import { startDiagnostic, submitDiagnostic } from "@/lib/api";

type DiagnosticMiniFlowProps = {
  topicId: string;
  mode?: DiagnosticMode;
  selfReportLevel?: number | null;
  onBack: () => void;
  onComplete: (result: {
    source: "diagnostic";
    estimatedState: string;
    recommendedStartingMode: StartingMode;
    resultSummary: string;
  }) => void;
};

export default function DiagnosticMiniFlow({
  topicId,
  mode = "topic_start",
  selfReportLevel = null,
  onBack,
  onComplete,
}: DiagnosticMiniFlowProps) {
  const [diagnostic, setDiagnostic] = useState<StartDiagnosticResult | null>(
    null
  );
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [confidence, setConfidence] = useState<Record<string, number>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadDiagnostic() {
      try {
        setIsLoading(true);

        const result = await startDiagnostic(topicId, {
          mode,
          self_report_level: selfReportLevel,
        });

        if (!cancelled) {
          setDiagnostic(result);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    loadDiagnostic();

    return () => {
      cancelled = true;
    };
  }, [topicId, mode, selfReportLevel]);

  const questions = diagnostic?.questions ?? [];
  const currentQuestion: DiagnosticQuestion | undefined =
    questions[currentIndex];

  const progressLabel = useMemo(() => {
    if (!questions.length) return "0 / 0";
    return `${currentIndex + 1} / ${questions.length}`;
  }, [currentIndex, questions.length]);

  function updateAnswer(value: string) {
    if (!currentQuestion) return;

    setAnswers((previous) => ({
      ...previous,
      [currentQuestion.id]: value,
    }));
  }

  function updateConfidence(value: number) {
    if (!currentQuestion) return;

    setConfidence((previous) => ({
      ...previous,
      [currentQuestion.id]: value,
    }));
  }

  function goNext() {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex((index) => index + 1);
    }
  }

  function goBackQuestion() {
    if (currentIndex > 0) {
      setCurrentIndex((index) => index - 1);
    } else {
      onBack();
    }
  }

  async function handleSubmit() {
    if (!diagnostic) return;

    setIsSubmitting(true);

    try {
      const result: SubmitDiagnosticResult = await submitDiagnostic(
        diagnostic.diagnostic_id,
        questions.map((question) => ({
          question_id: question.id,
          answer: answers[question.id] ?? "",
          confidence: confidence[question.id] ?? 3,
        }))
      );

      onComplete({
        source: "diagnostic",
        estimatedState: result.estimated_state,
        recommendedStartingMode: result.recommended_starting_mode,
        resultSummary: result.result_summary,
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isLoading) {
    return (
      <div className="mx-auto flex min-h-[70vh] w-full max-w-3xl items-center justify-center px-4">
        <div className="rounded-3xl border border-zinc-200 bg-white px-6 py-5 text-sm text-zinc-600 shadow-sm">
          Setting up a quick check...
        </div>
      </div>
    );
  }

  if (!diagnostic || !currentQuestion) {
    return (
      <div className="mx-auto flex min-h-[70vh] w-full max-w-3xl items-center justify-center px-4">
        <div className="rounded-3xl border border-zinc-200 bg-white p-6 shadow-sm">
          <p className="text-sm text-zinc-600">
            Could not start the quick check.
          </p>

          <button
            type="button"
            onClick={onBack}
            className="mt-4 rounded-2xl bg-zinc-900 px-4 py-2 text-sm font-medium text-white"
          >
            Go back
          </button>
        </div>
      </div>
    );
  }

  const currentAnswer = answers[currentQuestion.id] ?? "";
  const isLastQuestion = currentIndex === questions.length - 1;

  return (
    <div className="mx-auto flex min-h-[70vh] w-full max-w-3xl items-center justify-center px-4 py-10">
      <div className="w-full rounded-[2rem] border border-zinc-200 bg-white p-6 shadow-sm">
        <div className="mb-5 flex items-center justify-between">
          <button
            type="button"
            onClick={goBackQuestion}
            className="flex items-center gap-2 rounded-2xl border border-zinc-200 px-3 py-2 text-sm font-medium text-zinc-700 transition hover:bg-zinc-50"
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </button>

          <div className="rounded-full bg-purple-50 px-3 py-1 text-xs font-medium text-purple-700">
            {progressLabel}
          </div>
        </div>

        <div className="mb-6">
          <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-2xl bg-purple-50 text-purple-700">
            <Sparkles className="h-5 w-5" />
          </div>

          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-purple-700">
            {formatQuestionType(currentQuestion.type)}
          </p>

          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-zinc-950">
            {currentQuestion.question}
          </h2>

          <p className="mt-2 text-sm leading-6 text-zinc-600">
            This is only to find the right starting point. It is not graded.
          </p>
        </div>

        <textarea
          value={currentAnswer}
          onChange={(event) => updateAnswer(event.target.value)}
          placeholder="Write what you know..."
          className="min-h-36 w-full resize-none rounded-3xl border border-zinc-200 bg-zinc-50/70 p-4 text-sm leading-6 text-zinc-900 outline-none transition placeholder:text-zinc-400 focus:border-purple-300 focus:bg-white"
        />

        <div className="mt-5 rounded-3xl border border-zinc-200 bg-zinc-50/70 p-4">
          <p className="text-sm font-medium text-zinc-900">
            How confident are you?
          </p>

          <div className="mt-3 flex flex-wrap gap-2">
            {[1, 2, 3, 4, 5].map((value) => {
              const selected = (confidence[currentQuestion.id] ?? 3) === value;

              return (
                <button
                  key={value}
                  type="button"
                  onClick={() => updateConfidence(value)}
                  className={`rounded-2xl px-3 py-2 text-sm font-medium transition ${
                    selected
                      ? "bg-purple-700 text-white"
                      : "border border-zinc-200 bg-white text-zinc-700 hover:bg-purple-50"
                  }`}
                >
                  {value}
                </button>
              );
            })}
          </div>
        </div>

        <div className="mt-6 flex justify-end">
          {isLastQuestion ? (
            <button
              type="button"
              onClick={handleSubmit}
              disabled={isSubmitting}
              className="flex items-center gap-2 rounded-2xl bg-purple-700 px-5 py-3 text-sm font-medium text-white shadow-sm transition hover:bg-purple-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <CheckCircle2 className="h-4 w-4" />
              {isSubmitting ? "Aligning..." : "Find my starting point"}
            </button>
          ) : (
            <button
              type="button"
              onClick={goNext}
              className="flex items-center gap-2 rounded-2xl bg-purple-700 px-5 py-3 text-sm font-medium text-white shadow-sm transition hover:bg-purple-800"
            >
              Next
              <ArrowRight className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function formatQuestionType(type: DiagnosticQuestion["type"]) {
  if (type === "recall") return "Recall check";
  if (type === "application") return "Application check";
  if (type === "edge_case") return "Edge-case check";
  if (type === "transfer") return "Transfer check";
  return "Confidence check";
}
