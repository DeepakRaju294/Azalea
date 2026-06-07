"use client";

/**
 * Learn V2 page — consumes the v2 lesson contract.
 *
 * URL: /study-paths/[studyPathId]/learn-v2?topic=<topicId>
 *
 * Minimal layout: title, render-step text (title + bullets), visual area
 * (compiled VisualModel + frame_index), Next/Back navigation, and a
 * placeholder for the chat sidebar that opens when an element is clicked.
 *
 * Coexists with /study-paths/[studyPathId]/learn (legacy). Both routes
 * remain functional during migration.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

import {
  askVisualQuestionV2,
  generateLessonV2,
  getStoredLessonV2,
  submitPracticeAttemptV2,
} from "@/lib/api_v2";
import type {
  LessonV2,
  RenderStep,
  SelectableElement,
  VisualContextPayload,
  VisualModel,
} from "@/lib/visual_v2_types";
import { VisualRenderer } from "@/components/visuals_v2/VisualRenderer";

const AUTO_PLAY_DWELL_MS = 4500;
const MAX_CHAT_THREADS_PER_LESSON = 100;

export default function LearnV2Page({
  params,
}: {
  params: Promise<{ studyPathId: string }>;
}) {
  const searchParams = useSearchParams();
  const topicIdParam = searchParams.get("topic");

  const [_studyPathId, setStudyPathId] = useState<string>("");
  useEffect(() => {
    params.then((p) => setStudyPathId(p.studyPathId));
  }, [params]);

  const [lesson, setLesson] = useState<LessonV2 | null>(null);
  const [classification, setClassification] = useState<{
    topic_type: string;
    visual_domain: string;
    visual_mode_hint: string;
  } | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string>("");
  const [stepIndex, setStepIndex] = useState(0);
  const [replayNonce, setReplayNonce] = useState(0);

  // Visual selection (clicked element → chat sidebar context)
  const [selectedElement, setSelectedElement] = useState<SelectableElement | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatQuestion, setChatQuestion] = useState("");
  const [chatLoading, setChatLoading] = useState(false);

  // Sticky chat thread per (step, element_id). Each turn = {question, answer}.
  // Persists across re-asks within the same selection but clears when the
  // learner navigates to a different step.
  const [chatThreads, setChatThreads] = useState<
    Record<string, { question: string; answer: string }[]>
  >({});

  function threadKey(stepId: string, elementId: string): string {
    return `${stepId}::${elementId}`;
  }

  // Fetch lesson
  useEffect(() => {
    if (!topicIdParam) return;
    let cancelled = false;
    async function load() {
      setIsLoading(true);
      setError("");
      try {
        const cached = await getStoredLessonV2(topicIdParam!);
        if (cancelled) return;
        if (cached?.lesson_json) {
          setLesson(cached.lesson_json);
          setClassification(null);
        } else {
          const res = await generateLessonV2(topicIdParam!);
          if (cancelled) return;
          setLesson(res.lesson);
          setClassification(res.classification);
        }
        setStepIndex(0);
        setSelectedElement(null);
        // Lesson changed → reset accumulated chat memory.
        setChatThreads({});
      } catch (err) {
        if (cancelled) return;
        console.error(err);
        setError(err instanceof Error ? err.message : "Failed to load lesson");
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [topicIdParam]);

  const modelsById = useMemo(() => {
    const map = new Map<string, VisualModel>();
    for (const m of lesson?.visual_models || []) {
      map.set(m.id, m);
    }
    return map;
  }, [lesson]);

  const currentStep: RenderStep | undefined = lesson?.render_steps?.[stepIndex];
  const currentModel = currentStep?.visual_model_id
    ? modelsById.get(currentStep.visual_model_id) || null
    : null;
  const currentFrame =
    currentModel && currentStep?.frame_index != null
      ? currentModel.frames[currentStep.frame_index] ?? null
      : null;

  const currentThreadKey =
    currentStep?.id && selectedElement
      ? threadKey(currentStep.id, selectedElement.element_id)
      : null;
  const currentThread = currentThreadKey ? chatThreads[currentThreadKey] || [] : [];
  const latestChatAnswer =
    currentThread.length > 0 ? currentThread[currentThread.length - 1]?.answer || "" : "";

  const handleElementClick = useCallback((el: SelectableElement) => {
    setSelectedElement(el);
    setChatOpen(true);
    setChatQuestion("");
  }, []);

  // Whole-visual context: synthesizes a "container" SelectableElement
  // representing the entire visual. Opens chat with that context so the
  // learner can ask high-level questions ("what is this showing me?").
  const handleExplainWholeVisual = useCallback(() => {
    if (!currentModel || !currentFrame) return;
    const whole: SelectableElement = {
      element_id: `__whole_visual__${currentModel.id}`,
      element_type: "hotspot",
      semantic_label: `the entire ${currentModel.base_type.replace(/_/g, " ")} visual (mode: ${currentModel.mode})`,
      bounds: { x: 0, y: 0, width: 100, height: 100 },
      aria_label: `Whole visual: ${currentModel.base_type}`,
      keyboard_index: 0,
      payload: {
        whole_visual: true,
        base_type: currentModel.base_type,
        mode: currentModel.mode,
        frame_index: currentFrame.index,
      },
    };
    setSelectedElement(whole);
    setChatOpen(true);
    setChatQuestion("Explain this whole visual.");
  }, [currentModel, currentFrame]);

  const handleAskQuestion = useCallback(async () => {
    if (!chatQuestion.trim() || !selectedElement || !currentModel || !currentFrame || !currentStep) {
      return;
    }
    const payload: VisualContextPayload = {
      visual_model_id: currentModel.id,
      frame_index: currentFrame.index,
      element: selectedElement,
      surrounding_state: currentFrame.state,
      base_type: currentModel.base_type,
      mode: currentModel.mode,
      formatted_context: "",
    };
    const question = chatQuestion;
    setChatQuestion("");
    setChatLoading(true);
    const key = threadKey(currentStep.id, selectedElement.element_id);
    try {
      const res = await askVisualQuestionV2(question, payload);
      setChatThreads((prev) => {
        const existing = prev[key] || [];
        const next = { ...prev, [key]: [...existing, { question, answer: res.answer }] };
        const keys = Object.keys(next);
        if (keys.length <= MAX_CHAT_THREADS_PER_LESSON) return next;
        const trimmed = { ...next };
        for (const oldKey of keys.slice(0, keys.length - MAX_CHAT_THREADS_PER_LESSON)) {
          delete trimmed[oldKey];
        }
        return trimmed;
      });
    } catch (err) {
      const errorMessage =
        err instanceof Error
          ? `Failed: ${err.message}`
          : "Failed to ask question.";
      setChatThreads((prev) => {
        const existing = prev[key] || [];
        const next = {
          ...prev,
          [key]: [...existing, { question, answer: errorMessage }],
        };
        const keys = Object.keys(next);
        if (keys.length <= MAX_CHAT_THREADS_PER_LESSON) return next;
        const trimmed = { ...next };
        for (const oldKey of keys.slice(0, keys.length - MAX_CHAT_THREADS_PER_LESSON)) {
          delete trimmed[oldKey];
        }
        return trimmed;
      });
    } finally {
      setChatLoading(false);
    }
  }, [chatQuestion, selectedElement, currentModel, currentFrame, currentStep]);

  // Lesson-level chat memory: threads accumulate across step changes
  // within the same lesson. The chat sidebar shows the thread for the
  // currently-selected element; threads for OTHER elements stay in
  // memory and reappear when the learner reselects them (within this
  // lesson session). Threads are wiped when the lesson itself changes
  // (handled by the lesson-fetch useEffect resetting state).
  // Previous behavior cleared threads on Next/Back; we keep that
  // function as a no-op for compatibility but it no longer wipes.
  function clearThreadsForStep(_stepId: string | undefined) {
    // Threads are now lesson-scoped; intentionally no longer per-step.
  }

  const handleNext = useCallback(() => {
    if (!lesson) return;
    clearThreadsForStep(currentStep?.id);
    setStepIndex((idx) => Math.min(idx + 1, lesson.render_steps.length - 1));
    setReplayNonce(0);
    setSelectedElement(null);
    setChatOpen(false);
  }, [lesson, currentStep?.id]);

  const handleBack = useCallback(() => {
    clearThreadsForStep(currentStep?.id);
    setStepIndex((idx) => Math.max(idx - 1, 0));
    setReplayNonce(0);
    setSelectedElement(null);
    setChatOpen(false);
  }, [currentStep?.id]);

  const handleReplay = useCallback(() => {
    setReplayNonce((value) => value + 1);
    setSelectedElement(null);
    setChatOpen(false);
  }, []);

  // Auto-play: advances through render_steps on a timer. Pauses when the
  // learner clicks an element (so a question doesn't get cut off) and
  // stops at the last step.
  const [autoPlay, setAutoPlay] = useState(false);
  const [autoPlayRemainingMs, setAutoPlayRemainingMs] = useState(AUTO_PLAY_DWELL_MS);
  const atLastStep = lesson
    ? stepIndex >= lesson.render_steps.length - 1
    : false;
  useEffect(() => {
    if (!autoPlay || !lesson || chatOpen || atLastStep) {
      return;
    }
    const startedAt = Date.now();
    const tick = window.setInterval(() => {
      setAutoPlayRemainingMs(Math.max(0, AUTO_PLAY_DWELL_MS - (Date.now() - startedAt)));
    }, 100);
    const timer = window.setTimeout(() => {
      clearThreadsForStep(currentStep?.id);
      setStepIndex((idx) => Math.min(idx + 1, lesson.render_steps.length - 1));
      setReplayNonce(0);
      setSelectedElement(null);
    }, AUTO_PLAY_DWELL_MS);
    return () => {
      window.clearInterval(tick);
      window.clearTimeout(timer);
    };
  }, [autoPlay, chatOpen, stepIndex, lesson, currentStep?.id, atLastStep]);
  // Stop auto-play when we reach the last step. Toggle handler reads
  // `atLastStep` directly; this drives the disabled prop on the button.

  const handleToggleAutoPlay = useCallback(() => {
    if (atLastStep) return;
    setAutoPlay((prev) => !prev);
  }, [atLastStep]);

  // Global keyboard shortcuts:
  //   ←  back one step
  //   →  next step
  //   Space (when not focused in textarea/input)  pause/resume auto-play
  //   Esc  deselect + close chat
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      const isTextInput =
        target && (
          target.tagName === "TEXTAREA" ||
          target.tagName === "INPUT" ||
          (target as HTMLElement).isContentEditable
        );
      if (isTextInput) return;

      if (e.key === "ArrowLeft") {
        e.preventDefault();
        handleBack();
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        handleNext();
      } else if (e.key === " ") {
        e.preventDefault();
        handleToggleAutoPlay();
      } else if (e.key === "Escape") {
        e.preventDefault();
        setSelectedElement(null);
        setChatOpen(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [handleBack, handleNext, handleToggleAutoPlay]);

  // Deselection on outside-click. Listens for clicks anywhere that aren't
  // inside the visual container or the chat sidebar.
  const visualContainerRef = useRef<HTMLDivElement | null>(null);
  const chatSidebarRef = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (!selectedElement) return;
    function onClickOutside(e: MouseEvent) {
      const target = e.target as Node | null;
      if (!target) return;
      const insideVisual = visualContainerRef.current?.contains(target);
      const insideChat = chatSidebarRef.current?.contains(target);
      if (!insideVisual && !insideChat) {
        setSelectedElement(null);
        setChatOpen(false);
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [selectedElement]);

  if (!topicIdParam) {
    return (
      <div className="mx-auto max-w-2xl p-8 text-sm">
        Provide a topic id via <code>?topic=&lt;id&gt;</code> on this URL.
      </div>
    );
  }

  if (isLoading || !lesson) {
    return (
      <div className="mx-auto max-w-2xl p-8 text-sm text-[#5B2EE0]">
        {error ? `Error: ${error}` : "Generating v2 lesson…"}
      </div>
    );
  }

  const progressPct = Math.round(
    ((stepIndex + 1) / lesson.render_steps.length) * 100,
  );

  return (
    <div className="min-h-screen bg-[#FBF8FF]">
      <header className="border-b border-[#E5DFEE] bg-white px-6 py-3">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <div>
            <h1 className="text-lg font-black text-[#3A2870]">{lesson.title}</h1>
            {classification && (
              <p className="text-xs text-[#5B2EE0]">
                {classification.topic_type} • {classification.visual_domain} •
                mode hint: {classification.visual_mode_hint}
              </p>
            )}
          </div>
          <div className="flex items-center gap-3 text-xs text-[#5B2EE0]">
            <a
              href={`/study-paths/${_studyPathId}/learn-v2/print?topic=${topicIdParam}`}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-full border border-[#D5CFE2] bg-white px-3 py-1 text-[11px] font-semibold text-[#5B2EE0] hover:bg-[#F4ECFF]"
              aria-label="Open print view (opens in new tab)"
            >
              🖨 Print
            </a>
            <span>
              {stepIndex + 1} / {lesson.render_steps.length}
            </span>
            <div className="h-2 w-40 overflow-hidden rounded-full bg-[#E8DEFF]">
              <div
                className="h-full bg-[#7C4EF0] transition-all"
                style={{ width: `${progressPct}%` }}
              />
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto flex max-w-6xl gap-6 p-6">
        <div className="flex-1">
          {currentStep && (
            <div className="rounded-3xl border border-[#E5DFEE] bg-white p-6 shadow-sm">
              <p className="text-xs font-bold uppercase tracking-wide text-[#7C4EF0]">
                {currentStep.role.replace(/_/g, " ")}
              </p>
              <h2 className="mt-2 text-2xl font-bold text-[#3A2870]">
                {currentStep.title}
              </h2>
              {currentStep.notes && (
                <p className="mt-2 text-sm italic text-[#5B2EE0]">
                  {currentStep.notes}
                </p>
              )}
              {currentStep.points.length > 0 && (
                <ul className="mt-4 flex flex-col gap-2 text-sm leading-6 text-[#3A2870]">
                  {currentStep.points.map((point, i) => {
                    const isSub = point.startsWith("  - ") || point.startsWith("- ");
                    return (
                      <li
                        key={i}
                        className={isSub ? "ml-4 text-[#5B2EE0]" : "font-semibold"}
                      >
                        {point.replace(/^\s*-\s*/, "")}
                      </li>
                    );
                  })}
                </ul>
              )}

              {(currentModel || currentStep.support_visual) && (
                <div className="mt-6" ref={visualContainerRef}>
                  <VisualRenderer
                    key={`${currentStep.id}_${currentStep.frame_index ?? "support"}_${replayNonce}`}
                    model={currentModel}
                    frameIndex={currentStep.frame_index}
                    supportVisual={currentStep.support_visual}
                    onElementClick={handleElementClick}
                    selectedElementId={selectedElement?.element_id ?? null}
                  />
                  {currentModel && currentFrame && (
                    <div className="mt-2 flex justify-end">
                      <button
                        type="button"
                        onClick={() => handleExplainWholeVisual()}
                        className="rounded-full border border-[#D5CFE2] bg-white px-3 py-1 text-[11px] font-semibold text-[#5B2EE0] hover:bg-[#F4ECFF]"
                        aria-label="Ask about the whole visual"
                      >
                        ✨ Explain this whole visual
                      </button>
                    </div>
                  )}
                </div>
              )}

              {currentStep.role === "practice" && currentStep.practice_question_id && (
                <PracticeCard
                  question={
                    lesson.practice_questions.find(
                      (q) => q.id === currentStep.practice_question_id,
                    ) ?? null
                  }
                  topicId={topicIdParam ?? ""}
                  key={currentStep.id}
                />
              )}
            </div>
          )}

          <div className="mt-4 flex items-center justify-between">
            <button
              type="button"
              onClick={handleBack}
              disabled={stepIndex === 0}
              className="rounded-full border border-[#D5CFE2] bg-white px-4 py-2 text-sm font-semibold text-[#3A2870] disabled:opacity-50"
            >
              ← Back
            </button>
            <div className="flex items-center gap-2">
              {autoPlay && !atLastStep && (
                <div
                  className="hidden w-28 overflow-hidden rounded-full bg-[#E8DEFF] sm:block"
                  aria-label={`Auto-play advances in ${Math.ceil(autoPlayRemainingMs / 1000)} seconds`}
                  title={`Auto-play advances in ${Math.ceil(autoPlayRemainingMs / 1000)} seconds`}
                >
                  <div
                    className="h-2 bg-[#FFD96B] transition-[width]"
                    style={{
                      width: `${Math.max(0, Math.min(100, (autoPlayRemainingMs / AUTO_PLAY_DWELL_MS) * 100))}%`,
                    }}
                  />
                </div>
              )}
              <button
                type="button"
                onClick={handleReplay}
                disabled={!currentStep || (!currentModel && !currentStep.support_visual)}
                className="rounded-full border border-[#D5CFE2] bg-white px-4 py-2 text-sm font-semibold text-[#3A2870] disabled:opacity-50"
              >
                Replay
              </button>
              <button
                type="button"
                onClick={handleToggleAutoPlay}
                disabled={stepIndex >= lesson.render_steps.length - 1}
                aria-pressed={autoPlay}
                className={[
                  "rounded-full border px-4 py-2 text-sm font-semibold disabled:opacity-50",
                  autoPlay
                    ? "border-[#FFD96B] bg-[#FFF6DA] text-[#3A2870]"
                    : "border-[#D5CFE2] bg-white text-[#3A2870]",
                ].join(" ")}
              >
                {autoPlay ? "⏸ Pause" : "▶ Auto-play"}
              </button>
            </div>
            <button
              type="button"
              onClick={handleNext}
              disabled={stepIndex >= lesson.render_steps.length - 1}
              className="rounded-full bg-[#7C4EF0] px-6 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              Next →
            </button>
          </div>
        </div>

        {/* Chat sidebar */}
        {chatOpen && selectedElement && (
          <aside ref={chatSidebarRef} className="w-96 shrink-0 rounded-3xl border border-[#E5DFEE] bg-white p-5 shadow-sm">
            <div className="sr-only" aria-live="polite" aria-atomic="true">
              {latestChatAnswer ? `Visual chat answered: ${latestChatAnswer}` : ""}
            </div>
            <div className="flex items-center justify-between">
              <p className="text-xs font-bold uppercase tracking-wide text-[#7C4EF0]">
                Ask about this
              </p>
              <button
                type="button"
                onClick={() => {
                  setChatOpen(false);
                  setSelectedElement(null);
                }}
                className="text-sm text-[#9A8FB0] hover:text-[#3A2870]"
              >
                ✕
              </button>
            </div>
            <div className="mt-3 rounded-2xl border border-[#FFD96B] bg-[#FFF6DA] p-3">
              <p className="text-[10px] uppercase tracking-wide text-[#7C4EF0]">
                Visual context
              </p>
              <p className="mt-1 text-sm font-semibold text-[#3A2870]">
                {selectedElement.semantic_label}
              </p>
              <p className="mt-1 text-xs text-[#5B2EE0]">
                {selectedElement.element_type} • id: {selectedElement.element_id}
              </p>
            </div>
            {/* Sticky thread: every Q&A on this element on this step */}
            {currentThread.length > 0 && (
              <div className="mt-3 flex max-h-64 flex-col gap-2 overflow-y-auto">
                {currentThread.map((turn, idx) => (
                  <div key={idx} className="flex flex-col gap-1">
                    <p className="rounded-xl border border-[#D5CFE2] bg-white px-3 py-2 text-xs font-semibold text-[#3A2870]">
                      {turn.question}
                    </p>
                    <p className="rounded-xl border border-[#E5DFEE] bg-[#F4ECFF] px-3 py-2 text-sm leading-6 text-[#3A2870]">
                      {turn.answer}
                    </p>
                  </div>
                ))}
              </div>
            )}
            <textarea
              value={chatQuestion}
              onChange={(e) => setChatQuestion(e.target.value)}
              rows={3}
              placeholder={
                currentThread.length
                  ? "Follow-up question…"
                  : "What do you want to know about this?"
              }
              className="mt-3 w-full rounded-xl border border-[#D5CFE2] bg-[#FBF8FF] p-3 text-sm text-[#3A2870] focus:border-[#7C4EF0] focus:outline-none"
            />
            <button
              type="button"
              onClick={handleAskQuestion}
              disabled={chatLoading || !chatQuestion.trim()}
              className="mt-2 w-full rounded-xl bg-[#7C4EF0] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              {chatLoading ? "Asking…" : currentThread.length ? "Send" : "Ask"}
            </button>
          </aside>
        )}
      </main>
    </div>
  );
}


// ---------------------------------------------------------------------------
// PracticeCard — minimal v2 practice flow.
// Reads PracticeQuestion shape from the v2 lesson contract.
// MVP behaviors:
//   - short_answer: text input → reveal correct → mark "Got it" / "Need review"
//   - multiple_choice: choice buttons → reveal correct on selection
//   - other types fall back to "show prompt + reveal answer"
// ---------------------------------------------------------------------------

type PracticeCardProps = {
  question: import("@/lib/visual_v2_types").PracticeQuestion | null;
  topicId: string;
};

function PracticeCard({ question, topicId }: PracticeCardProps) {
  const [answer, setAnswer] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [selfRating, setSelfRating] = useState<"" | "got_it" | "needs_review">("");
  const [persistStatus, setPersistStatus] = useState<"" | "saving" | "saved" | "error">("");
  const submittedAttemptRef = useRef(false);

  // Persist the attempt once when first submitted, then again when
  // self-rating changes. We avoid double-persist by tracking what was
  // already sent.
  const persistAttempt = useCallback(
    async (currentAnswer: string, isCorrect: boolean, rating: typeof selfRating) => {
      if (!question || !topicId) return;
      setPersistStatus("saving");
      try {
        await submitPracticeAttemptV2({
          topicId,
          practiceQuestionId: question.id,
          question: question.question_text,
          userAnswer: currentAnswer,
          isCorrect,
          selfRating: rating === "" ? null : rating,
        });
        setPersistStatus("saved");
      } catch (err) {
        console.error("persist practice attempt failed:", err);
        setPersistStatus("error");
      }
    },
    [question, topicId],
  );

  if (!question) {
    return (
      <div className="mt-6 rounded-2xl border border-dashed border-[#D5CFE2] bg-[#F9F6FF] p-5 text-sm text-[#5B2EE0]">
        Practice question is missing or could not be resolved. (Step has
        role=&quot;practice&quot; but no matching question in
        lesson.practice_questions.)
      </div>
    );
  }

  const isMultipleChoice =
    question.question_type === "multiple_choice" &&
    Array.isArray(question.choices) &&
    question.choices.length > 0;

  return (
    <div className="mt-6 rounded-2xl border border-[#FFD96B] bg-[#FFF6DA] p-5 shadow-sm">
      <p className="text-xs font-bold uppercase tracking-wide text-[#7C4EF0]">
        Practice
      </p>
      <p className="mt-2 text-sm font-semibold text-[#3A2870]">
        {question.question_text}
      </p>

      {isMultipleChoice ? (
        <div className="mt-3 flex flex-col gap-2">
          {question.choices.map((choice, i) => {
            const isCorrect =
              submitted && choice.trim() === (question.correct_answer || "").trim();
            const isPicked = submitted && choice === answer;
            return (
              <button
                key={i}
                type="button"
                onClick={() => {
                  setAnswer(choice);
                  setSubmitted(true);
                  if (!submittedAttemptRef.current) {
                    submittedAttemptRef.current = true;
                    const isCorrect =
                      choice.trim() === (question.correct_answer || "").trim();
                    void persistAttempt(choice, isCorrect, "");
                  }
                }}
                disabled={submitted}
                className={[
                  "rounded-xl border px-3 py-2 text-left text-sm transition-colors",
                  isCorrect
                    ? "border-[#2E7D32] bg-[#E8F5E9] text-[#1B5E20]"
                    : isPicked
                      ? "border-[#D32F2F] bg-[#FFEBEE] text-[#B71C1C]"
                      : "border-[#D5CFE2] bg-white text-[#3A2870] hover:bg-[#F4ECFF]",
                  submitted ? "" : "cursor-pointer",
                ].join(" ")}
                aria-label={`Choice: ${choice}`}
              >
                {choice}
              </button>
            );
          })}
        </div>
      ) : (
        <div className="mt-3 flex flex-col gap-2">
          <textarea
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            rows={3}
            disabled={submitted}
            placeholder="Type your answer…"
            className="w-full rounded-xl border border-[#D5CFE2] bg-white p-3 text-sm text-[#3A2870] focus:border-[#7C4EF0] focus:outline-none disabled:opacity-70"
            aria-label="Practice answer"
          />
          <button
            type="button"
            onClick={() => {
              setSubmitted(true);
              if (!submittedAttemptRef.current) {
                submittedAttemptRef.current = true;
                const isCorrect =
                  answer.trim().toLowerCase() ===
                  (question.correct_answer || "").trim().toLowerCase();
                void persistAttempt(answer, isCorrect, "");
              }
            }}
            disabled={submitted || !answer.trim()}
            className="self-start rounded-xl bg-[#7C4EF0] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            Check
          </button>
        </div>
      )}

      {submitted && question.correct_answer && (
        <div className="mt-4 rounded-xl border border-[#E5DFEE] bg-white p-3">
          <p className="text-xs font-bold uppercase tracking-wide text-[#7C4EF0]">
            Correct answer
          </p>
          <p className="mt-1 text-sm leading-6 text-[#3A2870]">
            {question.correct_answer}
          </p>
        </div>
      )}

      {persistStatus === "saving" && (
        <p className="mt-2 text-[10px] text-[#5B2EE0]">Saving attempt…</p>
      )}
      {persistStatus === "saved" && (
        <p className="mt-2 text-[10px] text-[#1B5E20]">Attempt saved.</p>
      )}
      {persistStatus === "error" && (
        <p className="mt-2 text-[10px] text-[#B71C1C]">
          Could not save attempt; your answer is shown but not persisted.
        </p>
      )}

      {submitted && (
        <div className="mt-3 flex items-center gap-2">
          <span className="text-xs text-[#5B2EE0]">How did you do?</span>
          <button
            type="button"
            onClick={() => {
              setSelfRating("got_it");
              const isCorrect =
                answer.trim().toLowerCase() ===
                (question.correct_answer || "").trim().toLowerCase();
              void persistAttempt(answer, isCorrect, "got_it");
            }}
            className={[
              "rounded-full border px-3 py-1 text-xs font-semibold transition-colors",
              selfRating === "got_it"
                ? "border-[#2E7D32] bg-[#E8F5E9] text-[#1B5E20]"
                : "border-[#D5CFE2] bg-white text-[#3A2870] hover:bg-[#F4ECFF]",
            ].join(" ")}
          >
            Got it
          </button>
          <button
            type="button"
            onClick={() => {
              setSelfRating("needs_review");
              const isCorrect =
                answer.trim().toLowerCase() ===
                (question.correct_answer || "").trim().toLowerCase();
              void persistAttempt(answer, isCorrect, "needs_review");
            }}
            className={[
              "rounded-full border px-3 py-1 text-xs font-semibold transition-colors",
              selfRating === "needs_review"
                ? "border-[#D32F2F] bg-[#FFEBEE] text-[#B71C1C]"
                : "border-[#D5CFE2] bg-white text-[#3A2870] hover:bg-[#F4ECFF]",
            ].join(" ")}
          >
            Needs review
          </button>
        </div>
      )}
    </div>
  );
}
