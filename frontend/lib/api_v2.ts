/**
 * V2 API client. Calls the parallel /lessons-v2 backend routes and
 * returns the LessonV2 contract.
 *
 * Coexists with frontend/lib/api.ts; does not import or modify it.
 */

import { supabase } from "@/lib/supabaseClient";
import type { LessonV2, VisualContextPayload } from "@/lib/visual_v2_types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

async function getAuthHeadersV2(): Promise<Record<string, string>> {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function requestV2<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  const authHeaders = await getAuthHeadersV2();
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
      ...(options?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${path} ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export type GenerateLessonV2Response = {
  topic_id: string;
  classification: {
    topic_type: string;
    visual_domain: string;
    visual_mode_hint: string;
    reason: string;
  };
  lesson: LessonV2;
};

export function generateLessonV2(topicId: string): Promise<GenerateLessonV2Response> {
  return requestV2(`/lessons-v2/topics/${topicId}/generate`, {
    method: "POST",
  });
}

export type StoredLessonV2Response = {
  id: string;
  topic_id: string;
  title: string;
  lesson_json: LessonV2;
  source_chunk_ids: string[] | null;
  source_summary: string | null;
  generation_status: string;
  created_at: string;
};

export async function getStoredLessonV2(
  topicId: string,
): Promise<StoredLessonV2Response | null> {
  try {
    const lesson = await requestV2<StoredLessonV2Response>(
      `/topics/${topicId}/lesson`,
    );
    if (lesson.lesson_json?.lesson_version === 2) {
      return lesson;
    }
    return null;
  } catch (error) {
    const message = error instanceof Error ? error.message : "";
    if (message.includes(" 404:")) {
      return null;
    }
    throw error;
  }
}

export function classifyTopicV2(topicId: string) {
  return requestV2(`/lessons-v2/topics/${topicId}/classify`);
}

export type SubmitPracticeAttemptArgs = {
  topicId: string;
  lessonId?: string | null;
  practiceQuestionId: string;
  question: string;
  userAnswer: string;
  isCorrect: boolean;
  selfRating?: "got_it" | "needs_review" | null;
};

export type SubmitPracticeAttemptResponse = {
  attempt_id: string;
  is_correct: boolean;
  performance_level: string | null;
};

export function submitPracticeAttemptV2(
  args: SubmitPracticeAttemptArgs,
): Promise<SubmitPracticeAttemptResponse> {
  return requestV2(`/lessons-v2/practice/submit`, {
    method: "POST",
    body: JSON.stringify({
      topic_id: args.topicId,
      lesson_id: args.lessonId ?? null,
      practice_question_id: args.practiceQuestionId,
      question: args.question,
      user_answer: args.userAnswer,
      is_correct: args.isCorrect,
      self_rating: args.selfRating ?? "",
    }),
  });
}

export type VisualQAResponse = {
  answer: string;
  visual_context_summary: string;
};

export function askVisualQuestionV2(
  question: string,
  visualContext: VisualContextPayload,
): Promise<VisualQAResponse> {
  return requestV2(`/lessons-v2/visual-qa`, {
    method: "POST",
    body: JSON.stringify({
      question,
      visual_context: visualContext,
    }),
  });
}

export type V2TelemetryPipelineSummary = {
  count?: number;
  success?: number;
  failure?: number;
  avg_duration_seconds?: number;
  error_rate?: number;
  validator_errors_per_lesson?: number;
  validator_warnings_per_lesson?: number;
  base_type_counts?: Record<string, number>;
};

export type V2TelemetrySummary = {
  rows_read: number;
  log_path?: string;
  alerts?: string[];
  by_pipeline?: Record<string, V2TelemetryPipelineSummary>;
};

export function getV2TelemetrySummary(limitRows = 1000): Promise<V2TelemetrySummary> {
  return requestV2(`/lessons-v2/telemetry/summary?limit_rows=${limitRows}`);
}
