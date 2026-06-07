"use client";

/**
 * Print / export view for a v2 lesson.
 *
 * URL: /study-paths/[studyPathId]/learn-v2/print?topic=<topicId>
 *
 * Renders the full lesson in a static, print-friendly layout:
 *   - All render_steps in document order (no Next/Back)
 *   - Each step shows its title, bullets, and the visual at the step's
 *     frame_index — no animation, no click handlers, no chat sidebar
 *   - Worked-example steps are shown frame-by-frame inline
 *   - Practice cards show the question + correct answer up front
 *
 * Use the browser's "Print to PDF" to export. The Tailwind `@media print`
 * stylesheet hides page chrome (header progress bar, navigation, etc.).
 */

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import { getStoredLessonV2 } from "@/lib/api_v2";
import type { LessonV2, VisualModel } from "@/lib/visual_v2_types";
import { VisualRenderer } from "@/components/visuals_v2/VisualRenderer";

export default function PrintV2Page() {
  const searchParams = useSearchParams();
  const topicIdParam = searchParams.get("topic");
  const [lesson, setLesson] = useState<LessonV2 | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    if (!topicIdParam) return;
    let cancelled = false;
    async function load() {
      try {
        const cached = await getStoredLessonV2(topicIdParam!);
        if (cancelled) return;
        if (cached?.lesson_json) {
          setLesson(cached.lesson_json);
        } else {
          setError("No cached v2 lesson found for this topic. Generate it first via /learn-v2.");
        }
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load lesson");
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [topicIdParam]);

  const modelsById = useMemo(() => {
    const m = new Map<string, VisualModel>();
    for (const model of lesson?.visual_models || []) m.set(model.id, model);
    return m;
  }, [lesson]);

  if (!topicIdParam) {
    return (
      <div className="mx-auto max-w-2xl p-8 text-sm">
        Provide a topic id via <code>?topic=&lt;id&gt;</code>.
      </div>
    );
  }

  if (error) {
    return <div className="mx-auto max-w-2xl p-8 text-sm text-red-600">{error}</div>;
  }

  if (!lesson) {
    return <div className="mx-auto max-w-2xl p-8 text-sm">Loading…</div>;
  }

  return (
    <div className="mx-auto max-w-4xl bg-white p-8 print:p-4">
      {/* Print stylesheet */}
      <style jsx global>{`
        @media print {
          body { background: white; }
          .no-print { display: none !important; }
        }
      `}</style>

      <header className="mb-6 border-b border-[#E5DFEE] pb-4">
        <h1 className="text-2xl font-black text-[#3A2870]">{lesson.title}</h1>
        <p className="mt-1 text-sm text-[#5B2EE0]">{lesson.topic_summary}</p>
        <button
          type="button"
          onClick={() => window.print()}
          className="no-print mt-3 rounded-full bg-[#7C4EF0] px-4 py-2 text-sm font-semibold text-white"
        >
          🖨 Print / Save as PDF
        </button>
      </header>

      <main className="flex flex-col gap-6">
        {lesson.render_steps.map((step, i) => {
          const model =
            step.visual_model_id != null
              ? modelsById.get(step.visual_model_id) || null
              : null;
          const question =
            step.role === "practice" && step.practice_question_id
              ? lesson.practice_questions.find((q) => q.id === step.practice_question_id) ?? null
              : null;
          return (
            <section
              key={step.id}
              className="break-inside-avoid rounded-2xl border border-[#E5DFEE] bg-white p-5 shadow-sm print:break-after-auto print:shadow-none"
            >
              <p className="text-xs font-bold uppercase tracking-wide text-[#7C4EF0]">
                Step {i + 1} · {step.role.replace(/_/g, " ")}
              </p>
              <h2 className="mt-1 text-lg font-bold text-[#3A2870]">{step.title}</h2>
              {step.notes && (
                <p className="mt-1 text-sm italic text-[#5B2EE0]">{step.notes}</p>
              )}
              {step.points.length > 0 && (
                <ul className="mt-3 flex flex-col gap-1 text-sm leading-6 text-[#3A2870]">
                  {step.points.map((point, j) => (
                    <li key={j}>{point.replace(/^\s*-\s*/, "")}</li>
                  ))}
                </ul>
              )}
              {(model || step.support_visual) && (
                <div className="mt-4">
                  <VisualRenderer
                    model={model}
                    frameIndex={step.frame_index}
                    supportVisual={step.support_visual}
                    onElementClick={undefined}
                    selectedElementId={null}
                  />
                </div>
              )}
              {question && (
                <div className="mt-4 rounded-xl border border-[#FFD96B] bg-[#FFF6DA] p-3">
                  <p className="text-xs font-bold uppercase tracking-wide text-[#7C4EF0]">
                    Practice
                  </p>
                  <p className="mt-1 text-sm font-semibold text-[#3A2870]">
                    {question.question_text}
                  </p>
                  {question.correct_answer && (
                    <p className="mt-2 text-sm text-[#1B5E20]">
                      <span className="font-bold">Answer:</span> {question.correct_answer}
                    </p>
                  )}
                </div>
              )}
            </section>
          );
        })}
      </main>
    </div>
  );
}
