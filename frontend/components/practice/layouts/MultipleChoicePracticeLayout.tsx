import { Send } from "lucide-react";
import { useState } from "react";
import type { PracticeLayoutProps } from "../types";
import PracticeActionButtons from "../shared/PracticeActionButtons";

export default function MultipleChoicePracticeLayout({
  question,
  onHint,
  onSubmitAnswer,
  onAskClarification,
  isHintLoading = false,
  isSubmitLoading = false,
}: PracticeLayoutProps) {
  const [selectedChoice, setSelectedChoice] = useState<string>("");
  const [selectedChoices, setSelectedChoices] = useState<string[]>([]);
  const [hint, setHint] = useState("");
  const [feedback, setFeedback] = useState("");

  const isSelectAll = question.type === "select_all";
  const choices = question.choices || [
    "Choice A",
    "Choice B",
    "Choice C",
    "Choice D",
  ];

  async function requestHint() {
    const result = await onHint(
      isSelectAll
        ? selectedChoices.join("\n") || undefined
        : selectedChoice || undefined,
    );

    if (result) {
      setHint(result);
    }
  }

  async function submitChoice() {
    const answer = isSelectAll ? selectedChoices.join("\n") : selectedChoice;

    if (!answer) {
      setFeedback(
        isSelectAll
          ? "Select at least one answer before submitting."
          : "Select an answer before submitting.",
      );
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
              {isSelectAll ? "Select All That Apply" : "Multiple Choice"}
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

        {hint && (
          <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
            {hint}
          </div>
        )}

        <div className="mt-6 space-y-3">
          {choices.map((choice, index) => {
            const label = String.fromCharCode(65 + index);
            const isSelected = isSelectAll
              ? selectedChoices.includes(choice)
              : selectedChoice === choice;

            return (
              <button
                key={choice}
                onClick={() => {
                  if (isSelectAll) {
                    setSelectedChoices((current) =>
                      current.includes(choice)
                        ? current.filter((item) => item !== choice)
                        : [...current, choice],
                    );
                    return;
                  }
                  setSelectedChoice(choice);
                }}
                className={`flex w-full items-start gap-4 rounded-2xl border p-4 text-left transition ${
                  isSelected
                    ? "border-violet-300 bg-violet-50"
                    : "border-[#E7E1EF] bg-white/75 hover:bg-[#F3ECFF]"
                }`}
              >
                <span
                  className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold ${
                    isSelected
                      ? "bg-violet-600 text-white"
                      : "bg-zinc-100 text-zinc-600"
                  }`}
                >
                  {isSelectAll && isSelected ? "x" : label}
                </span>

                <span className="pt-1 text-sm leading-6 text-zinc-700">
                  {choice}
                </span>
              </button>
            );
          })}
        </div>

        <div className="mt-5 flex justify-end">
          <button
            onClick={submitChoice}
            disabled={isSubmitLoading}
            className="inline-flex items-center gap-2 rounded-2xl bg-violet-600 px-5 py-3 text-sm font-semibold text-white shadow-sm hover:bg-violet-500 disabled:opacity-60"
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
