import { Send } from "lucide-react";
import { useState } from "react";
import type { PracticeLayoutProps } from "../types";
import PracticeActionButtons from "../shared/PracticeActionButtons";

const PRACTICE_TYPE_LABELS: Record<string, string> = {
  short_answer: "Short Answer",
  visual_labeling: "Visual Labeling",
  ordering: "Ordering",
  debugging: "Debugging",
  debugging_scenario: "Debugging Scenario",
  decision_scenario: "Decision Scenario",
};

const PRACTICE_PLACEHOLDERS: Record<string, string> = {
  visual_labeling: "Name the requested label/component and briefly justify it...",
  ordering: "Write the correct order, one step per line...",
  debugging: "Identify the issue, evidence, and fix...",
  debugging_scenario: "Identify the likely cause, next check, and fix...",
  decision_scenario: "Choose the best option and cite the deciding constraint...",
};

export default function SimpleAnswerPracticeLayout({
  question,
  onHint,
  onSubmitAnswer,
  onAskClarification,
  isHintLoading = false,
  isSubmitLoading = false,
}: PracticeLayoutProps) {
  const [answer, setAnswer] = useState("");
  const [hint, setHint] = useState("");
  const [feedback, setFeedback] = useState("");

  async function requestHint() {
    const result = await onHint(answer);

    if (result) {
      setHint(result);
    }
  }

  async function submitAnswer() {
    if (!answer.trim()) {
      setFeedback("Write an answer before submitting.");
      return;
    }

    if (!onSubmitAnswer) {
      setFeedback("Submit is not available for this practice question yet.");
      return;
    }

    const result = await onSubmitAnswer(answer);

    if (result) {
      setFeedback(result);
    }
  }

  return (
    <section className="flex h-[calc(100vh-80px)] items-center justify-center p-6">
      <div className="azalea-surface-strong w-full max-w-4xl rounded-3xl border p-8 shadow-sm">
        <div className="mb-6 flex items-center justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-zinc-400">
              {PRACTICE_TYPE_LABELS[question.type] || "Short Answer"}
            </p>
            <h2 className="mt-2 text-2xl font-semibold text-zinc-950">
              {question.skillTarget}
            </h2>
          </div>

          <PracticeActionButtons
            onHint={requestHint}
            onAskClarification={onAskClarification}
            isHintLoading={isHintLoading}
          />
        </div>

        <div className="azalea-tint rounded-3xl p-6">
          <p className="text-lg leading-8 text-zinc-800">
            {question.questionText}
          </p>
        </div>

        {question.given && question.given.length > 0 && (
          <div className="mt-5 rounded-2xl border border-[#E7E1EF] bg-white/70 p-4">
            <p className="text-sm font-semibold text-zinc-950">Given</p>
            <ul className="mt-2 space-y-1 text-sm leading-6 text-zinc-600">
              {question.given.map((item) => (
                <li key={item}>- {item}</li>
              ))}
            </ul>
          </div>
        )}

        {hint && (
          <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
            {hint}
          </div>
        )}

        <textarea
          value={answer}
          onChange={(event) => setAnswer(event.target.value)}
          placeholder={
            PRACTICE_PLACEHOLDERS[question.type] || "Write your answer here..."
          }
          className="mt-6 min-h-52 w-full resize-none rounded-3xl border border-[#E7E1EF] bg-white/80 p-5 text-sm leading-6 outline-none focus:border-violet-300"
        />

        <div className="mt-5 flex justify-end">
          <button
            onClick={submitAnswer}
            disabled={isSubmitLoading}
            className="inline-flex items-center gap-2 rounded-2xl bg-violet-600 px-5 py-3 text-sm font-semibold text-white shadow-sm hover:bg-violet-500"
          >
            <Send className="h-4 w-4" />
            {isSubmitLoading ? "Submitting..." : "Submit"}
          </button>
        </div>

        {feedback && (
          <div className="azalea-tint mt-5 whitespace-pre-wrap rounded-2xl border p-4 text-sm leading-6 text-zinc-600">
            {feedback}
          </div>
        )}
      </div>
    </section>
  );
}
