import { CheckCircle2, Plus, Send } from "lucide-react";
import { useState, type ReactNode } from "react";
import type { PracticeLayoutProps } from "../types";
import PracticeActionButtons from "../shared/PracticeActionButtons";

type WorkStep = {
  id: number;
  text: string;
  feedback?: string;
};

export default function MathPracticeLayout({
  question,
  onHint,
  onSubmitAnswer,
  onAskClarification,
  isHintLoading = false,
  isSubmitLoading = false,
}: PracticeLayoutProps) {
  const [steps, setSteps] = useState<WorkStep[]>([
    {
      id: 1,
      text: "",
    },
  ]);
  const [finalAnswer, setFinalAnswer] = useState("");
  const [feedback, setFeedback] = useState(
    "Check a step or submit your final answer to get feedback."
  );
  const [hint, setHint] = useState("");

  function updateStep(id: number, text: string) {
    setSteps((currentSteps) =>
      currentSteps.map((step) => (step.id === id ? { ...step, text } : step))
    );
  }

  function addStep() {
    setSteps((currentSteps) => [
      ...currentSteps,
      {
        id: currentSteps.length + 1,
        text: "",
      },
    ]);
  }

  function checkStep() {
    const latestStep = [...steps]
      .reverse()
      .find((step) => step.text.trim().length > 0);

    if (!latestStep) {
      setHint("Start by writing the first operation or formula you think applies.");
      return;
    }

    setSteps((currentSteps) =>
      currentSteps.map((step) =>
        step.id === latestStep.id
          ? {
              ...step,
              feedback:
                "Step check placeholder: later this will call the backend and give targeted feedback on this exact step.",
            }
          : step
      )
    );

    setFeedback(
      "Step check placeholder: this is where Azalea will identify whether the current step is correct, partially correct, or where reasoning breaks."
    );
  }

  async function requestHint() {
    const currentWork = [
      ...steps.map((step, index) =>
        step.text.trim() ? `Step ${index + 1}: ${step.text}` : ""
      ),
      finalAnswer ? `Final answer: ${finalAnswer}` : "",
    ]
      .filter(Boolean)
      .join("\n");
    const result = await onHint(currentWork || undefined);

    if (result) {
      setHint(result);
    }
  }

  async function submitAnswer() {
    if (!finalAnswer.trim()) {
      setFeedback("Enter a final answer before submitting.");
      return;
    }

    if (!onSubmitAnswer) {
      setFeedback("Submit is not available for this practice question yet.");
      return;
    }

    const work = [
      ...steps.map((step, index) =>
        step.text.trim() ? `Step ${index + 1}: ${step.text}` : ""
      ),
      `Final answer: ${finalAnswer}`,
    ]
      .filter(Boolean)
      .join("\n");
    const result = await onSubmitAnswer(work);

    if (result) {
      setFeedback(result);
    }
  }

  return (
    <section className="grid h-[calc(100vh-80px)] grid-cols-[34%_66%] gap-4 p-4">
      <aside className="azalea-surface-strong flex min-h-0 flex-col rounded-3xl border p-5 shadow-sm">
        <div className="mb-5 flex items-center justify-between gap-3">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-zinc-400">
              Problem
            </p>
            <h2 className="mt-1 text-xl font-semibold text-zinc-950">
              {question.skillTarget}
            </h2>
          </div>

          <PracticeActionButtons
            onHint={requestHint}
            onAskClarification={onAskClarification}
            isHintLoading={isHintLoading}
          />
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          <Section title="Question">
            <p>{question.questionText}</p>
          </Section>

          {question.given && question.given.length > 0 && (
            <Section title="Given Information">
              <ul className="space-y-2">
                {question.given.map((item) => (
                  <li key={item} className="flex gap-2">
                    <span className="text-zinc-400">•</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {hint && (
            <div className="mb-5 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
              {hint}
            </div>
          )}

          <Section title="Final Answer">
            <input
              value={finalAnswer}
              onChange={(event) => setFinalAnswer(event.target.value)}
              placeholder="Enter final answer..."
              className="w-full rounded-2xl border border-zinc-200 px-4 py-3 text-sm outline-none focus:border-violet-300"
            />
          </Section>

          <button
            onClick={submitAnswer}
            disabled={isSubmitLoading}
            className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-violet-600 px-5 py-3 text-sm font-semibold text-white shadow-sm hover:bg-violet-500 disabled:opacity-60"
          >
            <Send className="h-4 w-4" />
            {isSubmitLoading ? "Submitting..." : "Submit Answer"}
          </button>

          <div className="azalea-tint mt-5 whitespace-pre-wrap rounded-2xl border p-4 text-sm leading-6 text-zinc-600">
            {feedback}
          </div>
        </div>
      </aside>

      <section className="azalea-surface flex min-h-0 flex-col rounded-3xl border p-5 shadow-sm">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-zinc-400">
              Workspace
            </p>
            <h2 className="mt-1 text-lg font-semibold text-zinc-950">
              Show your work
            </h2>
          </div>

          <button
            onClick={checkStep}
            className="inline-flex items-center gap-2 rounded-2xl border border-zinc-200 bg-white px-4 py-2 text-sm font-medium text-zinc-700 shadow-sm hover:bg-zinc-50"
          >
            <CheckCircle2 className="h-4 w-4" />
            Check Step
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto rounded-3xl border border-dashed border-zinc-300 bg-[linear-gradient(to_right,#e4e4e7_1px,transparent_1px),linear-gradient(to_bottom,#e4e4e7_1px,transparent_1px)] bg-[size:28px_28px] p-4">
          <div className="space-y-3">
            {steps.map((step, index) => (
              <div
                key={step.id}
                className="rounded-2xl border border-[#E7E1EF] bg-white/80 p-4 shadow-sm"
              >
                <p className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-zinc-500">
                  Step {index + 1}
                </p>

                <textarea
                  value={step.text}
                  onChange={(event) => updateStep(step.id, event.target.value)}
                  placeholder="Write your reasoning for this step..."
                  className="min-h-20 w-full resize-none text-sm leading-6 text-zinc-800 outline-none placeholder:text-zinc-400"
                />

                {step.feedback && (
                  <div className="mt-3 rounded-xl bg-violet-50 px-3 py-2 text-xs leading-5 text-violet-800">
                    {step.feedback}
                  </div>
                )}
              </div>
            ))}

            <button
              onClick={addStep}
              className="inline-flex items-center gap-2 rounded-2xl border border-zinc-200 bg-white px-4 py-2 text-sm font-medium text-zinc-700 shadow-sm hover:bg-zinc-50"
            >
              <Plus className="h-4 w-4" />
              Add Step
            </button>
          </div>
        </div>
      </section>
    </section>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="mb-5">
      <h3 className="mb-2 text-sm font-semibold text-zinc-900">{title}</h3>
      <div className="text-sm leading-6 text-zinc-600">{children}</div>
    </section>
  );
}
