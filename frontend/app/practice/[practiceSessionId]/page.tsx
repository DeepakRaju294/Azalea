"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import PracticeHeader from "../../../components/practice/PracticeHeader";
import CodingPracticeLayout from "../../../components/practice/layouts/CodingPracticeLayout";
import MathPracticeLayout from "../../../components/practice/layouts/MathPracticeLayout";
import MultipleChoicePracticeLayout from "../../../components/practice/layouts/MultipleChoicePracticeLayout";
import SimpleAnswerPracticeLayout from "../../../components/practice/layouts/SimpleAnswerPracticeLayout";
import ClarificationSidebar from "../../../components/practice/shared/ClarificationSidebar";
import type {
  PracticeQuestion,
  PracticeQuestionType,
} from "../../../components/practice/types";
import {
  generateQuickPracticeQuestion,
  generateQuickPracticeQuestionSet,
  getQuickPracticeAttempts,
  getQuickPracticeHint,
  getQuickPracticeQuestions,
  getQuickPracticeSession,
  runPracticeCode,
  runQuickPracticeCode,
  submitQuickPracticeAnswer,
  type QuickPracticeAttempt,
  type QuickPracticeQuestion,
  type QuickPracticeSession,
} from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";

const CHOICE_PRACTICE_TYPES = new Set<PracticeQuestionType>([
  "multiple_choice",
  "select_all",
]);

const MATH_PRACTICE_TYPES = new Set<PracticeQuestionType>(["math", "math_input"]);

const CODING_PRACTICE_TYPES = new Set<PracticeQuestionType>([
  "coding",
  "coding_environment",
]);

function normalizePracticeQuestionType(
  value?: string | null,
): PracticeQuestionType {
  const normalized = String(value || "short_answer").trim() as PracticeQuestionType;
  const supported = new Set<PracticeQuestionType>([
    "short_answer",
    "multiple_choice",
    "select_all",
    "math",
    "math_input",
    "coding",
    "coding_environment",
    "visual_labeling",
    "ordering",
    "debugging",
    "debugging_scenario",
    "decision_scenario",
  ]);

  return supported.has(normalized) ? normalized : "short_answer";
}

function formatFeedback(result: {
  is_correct: boolean;
  performance_level: string;
  mistake_type?: string | null;
  feedback: string;
  follow_up_question?: string | null;
  next_action: string;
  adaptive_response?: {
    message?: string;
  };
}) {
  const lines = [
    result.is_correct ? "Correct." : "Needs work.",
    `Performance: ${result.performance_level.replace(/_/g, " ")}`,
    result.mistake_type ? `Mistake type: ${result.mistake_type}` : "",
    "",
    result.feedback,
    result.adaptive_response?.message
      ? `\nRecommended next step: ${result.adaptive_response.message}`
      : "",
    result.follow_up_question ? `\nFollow-up: ${result.follow_up_question}` : "",
    `\nNext action: ${result.next_action.replace(/_/g, " ")}`,
  ];

  return lines.filter(Boolean).join("\n");
}

export default function PracticeSessionPage() {
  const params = useParams<{ practiceSessionId: string }>();
  const practiceSessionId = params.practiceSessionId;
  const router = useRouter();
  const { isCheckingAuth } = useRequireAuth();

  const [session, setSession] = useState<QuickPracticeSession | null>(null);
  const [attempts, setAttempts] = useState<QuickPracticeAttempt[]>([]);
  const [questions, setQuestions] = useState<QuickPracticeQuestion[]>([]);
  const [currentQuestion, setCurrentQuestion] =
    useState<QuickPracticeQuestion | null>(null);
  const [isClarificationOpen, setIsClarificationOpen] = useState(false);
  const [status, setStatus] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isGeneratingQuestion, setIsGeneratingQuestion] = useState(false);
  const [isHintLoading, setIsHintLoading] = useState(false);
  const [isSubmitLoading, setIsSubmitLoading] = useState(false);
  const [hintUsed, setHintUsed] = useState(false);

  const refreshAttempts = useCallback(async () => {
    const attemptData = await getQuickPracticeAttempts(practiceSessionId);
    setAttempts(attemptData);
    return attemptData;
  }, [practiceSessionId]);

  const createQuestion = useCallback(async () => {
    try {
      setIsGeneratingQuestion(true);
      setStatus("Generating a focused practice question...");
      setHintUsed(false);

      const result = await generateQuickPracticeQuestion(practiceSessionId);
      setCurrentQuestion(result);
      setQuestions((currentQuestions) => [...currentQuestions, result]);
      setSession((currentSession) =>
        currentSession
          ? { ...currentSession, current_question: result.question_text }
          : currentSession
      );
      setStatus("");
    } catch (err) {
      console.error(err);
      setStatus("Failed to generate a practice question.");
    } finally {
      setIsGeneratingQuestion(false);
    }
  }, [practiceSessionId]);

  const createQuestionSet = useCallback(
    async (replaceExisting = false) => {
      try {
        setIsGeneratingQuestion(true);
        setStatus("Building a practice set...");
        setHintUsed(false);

        const result = await generateQuickPracticeQuestionSet(practiceSessionId, {
          count: 8,
          replace_existing: replaceExisting,
        });

        setQuestions(result);
        setCurrentQuestion(result[0] ?? null);
        setSession((currentSession) =>
          currentSession && result[0]
            ? { ...currentSession, current_question: result[0].question_text }
            : currentSession
        );
        setStatus("");
      } catch (err) {
        console.error(err);
        setStatus("Failed to build a practice set.");
      } finally {
        setIsGeneratingQuestion(false);
      }
    },
    [practiceSessionId]
  );

  useEffect(() => {
    async function loadPracticeSession() {
      try {
        setIsLoading(true);
        const [sessionData, attemptData, questionData] = await Promise.all([
          getQuickPracticeSession(practiceSessionId),
          getQuickPracticeAttempts(practiceSessionId),
          getQuickPracticeQuestions(practiceSessionId),
        ]);

        setSession(sessionData);
        setAttempts(attemptData);
        setQuestions(questionData);

        if (questionData.length > 0) {
          setCurrentQuestion(questionData[0]);
        } else if (sessionData.current_question) {
          setCurrentQuestion({
            id: "legacy-current-question",
            session_id: sessionData.id,
            question_type: "short_answer",
            topic: sessionData.prompt,
            skill_target: "Focused practice",
            difficulty: "Medium",
            question_text: sessionData.current_question,
            choices: [],
            given: [],
            test_cases: [],
            source_reference: sessionData.source_filename,
            order_index: 1,
            created_at: sessionData.created_at,
          });
        } else if (sessionData.source_filename) {
          await createQuestionSet();
        } else {
          await createQuestion();
        }
      } catch (err) {
        console.error(err);
        setStatus("Failed to load practice session.");
      } finally {
        setIsLoading(false);
      }
    }

    if (!isCheckingAuth && practiceSessionId) {
      loadPracticeSession();
    }
  }, [createQuestion, createQuestionSet, isCheckingAuth, practiceSessionId]);

  useEffect(() => {
    if (
      !status ||
      isLoading ||
      isGeneratingQuestion ||
      isHintLoading ||
      isSubmitLoading
    ) {
      return;
    }

    const timer = window.setTimeout(() => {
      setStatus("");
    }, 4500);

    return () => window.clearTimeout(timer);
  }, [isGeneratingQuestion, isHintLoading, isLoading, isSubmitLoading, status]);

  const currentQuestionIndex = useMemo(() => {
    if (!currentQuestion) {
      return 0;
    }

    const index = questions.findIndex(
      (practiceQuestion) => practiceQuestion.id === currentQuestion.id
    );

    return index === -1 ? 0 : index;
  }, [currentQuestion, questions]);

  const latestAttemptByQuestionId = useMemo(() => {
    const attemptMap = new Map<string, QuickPracticeAttempt>();

    attempts.forEach((attempt) => {
      if (attempt.question_id && !attemptMap.has(attempt.question_id)) {
        attemptMap.set(attempt.question_id, attempt);
      }
    });

    return attemptMap;
  }, [attempts]);

  const answeredCount = useMemo(
    () =>
      questions.filter((practiceQuestion) =>
        latestAttemptByQuestionId.has(practiceQuestion.id)
      ).length,
    [latestAttemptByQuestionId, questions]
  );

  const strongCount = useMemo(
    () =>
      questions.filter(
        (practiceQuestion) =>
          latestAttemptByQuestionId.get(practiceQuestion.id)
            ?.performance_level === "strong"
      ).length,
    [latestAttemptByQuestionId, questions]
  );

  const needsWorkCount = Math.max(answeredCount - strongCount, 0);
  const isIsolatedSolveSession = Boolean(session?.exact_problem);

  const question = useMemo<PracticeQuestion>(() => {
    const latestAttempt = attempts[0];
    const normalizedType = normalizePracticeQuestionType(
      currentQuestion?.question_type,
    );
    const normalizedDifficulty =
      currentQuestion?.difficulty === "Easy" ||
      currentQuestion?.difficulty === "Hard"
        ? currentQuestion.difficulty
        : "Medium";

    return {
      id: currentQuestion?.order_index || 1,
      type: normalizedType,
      topic: currentQuestion?.topic || session?.prompt || "Quick Practice",
      skillTarget: currentQuestion?.skill_target || "Focused practice",
      difficulty: normalizedDifficulty,
      questionNumber: currentQuestionIndex + 1,
      totalQuestions: Math.max(questions.length, 1),
      streak: attempts.filter((attempt) => attempt.performance_level === "strong")
        .length,
      questionText:
        currentQuestion?.question_text ||
        latestAttempt?.question ||
        "Generating your practice question...",
      choices: currentQuestion?.choices || undefined,
      given: currentQuestion?.given || undefined,
      starterCode: currentQuestion?.starter_code || undefined,
      language: currentQuestion?.language || undefined,
      testCases: currentQuestion?.test_cases || undefined,
      sourceReference:
        currentQuestion?.source_reference || session?.source_filename || undefined,
    };
  }, [attempts, currentQuestion, currentQuestionIndex, questions.length, session]);

  async function handleHint(partialAnswer?: string) {
    if (!question.questionText.trim() || isGeneratingQuestion) {
      return null;
    }

    try {
      setIsHintLoading(true);
      const result = await getQuickPracticeHint(practiceSessionId, {
        question_id:
          currentQuestion?.id === "legacy-current-question"
            ? null
            : currentQuestion?.id || null,
        question: question.questionText,
        user_partial_answer: partialAnswer || null,
      });

      setHintUsed(true);

      return [
        result.hint,
        result.guiding_question ? `Guiding question: ${result.guiding_question}` : "",
        result.concept_to_review
          ? `Review: ${result.concept_to_review}`
          : "",
      ]
        .filter(Boolean)
        .join("\n\n");
    } catch (err) {
      console.error(err);
      setStatus("Failed to get a hint.");
      return null;
    } finally {
      setIsHintLoading(false);
    }
  }

  async function handleSubmitAnswer(answer: string) {
    if (!question.questionText.trim()) {
      return null;
    }

    try {
      setIsSubmitLoading(true);
      const result = await submitQuickPracticeAnswer(practiceSessionId, {
        question_id:
          currentQuestion?.id === "legacy-current-question"
            ? null
            : currentQuestion?.id || null,
        question: question.questionText,
        user_answer: answer,
        hint_used: hintUsed,
      });

      const updatedAttempts = await refreshAttempts();
      const latestAttempt = updatedAttempts.find(
        (attempt) => attempt.question_id === currentQuestion?.id
      );
      const shouldMoveForward =
        latestAttempt?.performance_level === "strong" &&
        currentQuestionIndex < questions.length - 1;

      setStatus(
        shouldMoveForward
          ? "Strong answer saved. You can move to the next question."
          : ""
      );

      return formatFeedback(result);
    } catch (err) {
      console.error(err);
      setStatus("Failed to submit your answer.");
      return null;
    } finally {
      setIsSubmitLoading(false);
    }
  }

  async function handleRunCode(
    code: string,
    language: string,
    testCases: { input: string; expected: string }[]
  ) {
    try {
      if (currentQuestion?.id && currentQuestion.id !== "legacy-current-question") {
        return await runQuickPracticeCode(practiceSessionId, {
          question_id: currentQuestion.id,
          code,
          language,
          test_cases: testCases,
        });
      }

      return await runPracticeCode({ code, language, test_cases: testCases });
    } catch (err) {
      console.error(err);
      setStatus("Failed to run code.");
      return null;
    }
  }

  function renderPracticeLayout() {
    const commonProps = {
      question,
      onHint: handleHint,
      onRunCode: handleRunCode,
      onSubmitAnswer: handleSubmitAnswer,
      onAskClarification: () => setIsClarificationOpen(true),
      isHintLoading,
      isSubmitLoading,
    };

    if (CHOICE_PRACTICE_TYPES.has(question.type)) {
      return <MultipleChoicePracticeLayout key={question.questionText} {...commonProps} />;
    }

    if (MATH_PRACTICE_TYPES.has(question.type)) {
      return <MathPracticeLayout key={question.questionText} {...commonProps} />;
    }

    if (CODING_PRACTICE_TYPES.has(question.type)) {
      return <CodingPracticeLayout key={question.questionText} {...commonProps} />;
    }

    return <SimpleAnswerPracticeLayout key={question.questionText} {...commonProps} />;
  }

  function goToQuestion(index: number) {
    const nextQuestion = questions[index];

    if (!nextQuestion) {
      return;
    }

    setHintUsed(false);
    setStatus("");
    setCurrentQuestion(nextQuestion);
  }

  function goToNextUnansweredQuestion() {
    if (questions.length === 0) {
      return;
    }

    const laterUnansweredIndex = questions.findIndex(
      (practiceQuestion, index) =>
        index > currentQuestionIndex &&
        !latestAttemptByQuestionId.has(practiceQuestion.id)
    );

    if (laterUnansweredIndex !== -1) {
      goToQuestion(laterUnansweredIndex);
      return;
    }

    const firstUnansweredIndex = questions.findIndex(
      (practiceQuestion) => !latestAttemptByQuestionId.has(practiceQuestion.id)
    );

    if (firstUnansweredIndex !== -1) {
      goToQuestion(firstUnansweredIndex);
    }
  }

  function getQuestionButtonClass(practiceQuestion: QuickPracticeQuestion) {
    const latestAttempt = latestAttemptByQuestionId.get(practiceQuestion.id);

    if (practiceQuestion.id === currentQuestion?.id) {
      return "border-violet-500 bg-violet-600 text-white";
    }

    if (latestAttempt?.performance_level === "strong") {
      return "border-emerald-200 bg-emerald-50 text-emerald-800 hover:bg-emerald-100";
    }

    if (latestAttempt) {
      return "border-amber-200 bg-amber-50 text-amber-800 hover:bg-amber-100";
    }

    return "border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50";
  }

  function handleExit() {
    router.push("/");
  }

  if (isCheckingAuth || isLoading) {
    return (
      <main className="azalea-page-soft flex min-h-screen items-center justify-center text-zinc-950">
        <div className="azalea-surface-strong rounded-3xl border p-8 text-center shadow-sm">
          <p className="text-sm font-semibold text-zinc-600">
            Loading practice session...
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="azalea-page-soft flex h-screen max-h-screen flex-col overflow-hidden text-zinc-950">
      <PracticeHeader question={question} onExit={handleExit} />

      {status && (
        <div className="azalea-surface mx-4 mt-4 shrink-0 rounded-2xl border px-4 py-3 text-sm text-zinc-600 shadow-sm">
          {status}
        </div>
      )}

      {!isIsolatedSolveSession && (
      <div className="mx-4 mt-4 flex shrink-0 flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            {questions.map((practiceQuestion, index) => (
              <button
                key={practiceQuestion.id}
                onClick={() => goToQuestion(index)}
                className={`h-9 min-w-9 rounded-full border px-3 text-sm font-semibold transition ${getQuestionButtonClass(
                  practiceQuestion
                )}`}
              >
                {index + 1}
              </button>
            ))}
          </div>
          {questions.length > 0 && (
            <p className="mt-2 text-xs font-medium text-zinc-500">
              {answeredCount}/{questions.length} answered / {strongCount} strong ·{" "}
              {needsWorkCount} needs review
            </p>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => goToQuestion(currentQuestionIndex - 1)}
            disabled={currentQuestionIndex <= 0 || questions.length <= 1}
            className="rounded-2xl border border-zinc-200 bg-white px-4 py-2 text-sm font-semibold text-zinc-700 shadow-sm transition hover:bg-zinc-50 disabled:opacity-50"
          >
            Previous
          </button>
          <button
            onClick={() => goToQuestion(currentQuestionIndex + 1)}
            disabled={
              questions.length <= 1 || currentQuestionIndex >= questions.length - 1
            }
            className="rounded-2xl border border-zinc-200 bg-white px-4 py-2 text-sm font-semibold text-zinc-700 shadow-sm transition hover:bg-zinc-50 disabled:opacity-50"
          >
            Next
          </button>
          <button
            onClick={goToNextUnansweredQuestion}
            disabled={answeredCount >= questions.length}
            className="rounded-2xl border border-zinc-200 bg-white px-4 py-2 text-sm font-semibold text-zinc-700 shadow-sm transition hover:bg-zinc-50 disabled:opacity-50"
          >
            Next unanswered
          </button>
          <button
            onClick={createQuestion}
            disabled={isGeneratingQuestion}
            className="rounded-2xl border border-zinc-200 bg-white px-4 py-2 text-sm font-semibold text-zinc-700 shadow-sm transition hover:bg-zinc-50 disabled:opacity-60"
          >
            {isGeneratingQuestion ? "Generating..." : "New question"}
          </button>
          <button
            onClick={() => createQuestionSet(true)}
            disabled={isGeneratingQuestion}
            className="rounded-2xl bg-violet-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-violet-500 disabled:opacity-60"
          >
            {isGeneratingQuestion ? "Generating..." : "Generate set"}
          </button>
        </div>
      </div>
      )}

      <div className="min-h-0 flex-1 overflow-hidden">
        {renderPracticeLayout()}
      </div>

      <ClarificationSidebar
        isOpen={isClarificationOpen}
        onClose={() => setIsClarificationOpen(false)}
        question={question}
      />
    </main>
  );
}
