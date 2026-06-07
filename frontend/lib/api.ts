import { supabase } from "@/lib/supabaseClient";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export type AzaleaClass = {
  id: string;
  name: string;
  description: string | null;
  deadline: string | null;
  daily_goal_minutes: number | null;
  weekly_goal_minutes: number | null;
  created_at: string;
};

export type ClassUpdatePayload = {
  name?: string;
  description?: string | null;
  deadline?: string | null;
  daily_goal_minutes?: number | null;
  weekly_goal_minutes?: number | null;
};

export type StudyPath = {
  id: string;
  title: string;
  goal: string | null;
  progress_percent: number;
  estimated_minutes_remaining: number | null;
  created_at: string;
};

export type TopicStatus =
  | "not_started"
  | "in_progress"
  | "completed"
  | "needs_review";

export type CourseType =
  | "concept_intuition"
  | "algorithm_walkthrough"
  | "coding_implementation"
  | "data_structure_operation"
  | "math_formula_method"
  | "proof_reasoning"
  | "compare_distinguish"
  | "problem_solving_pattern"
  | "review_refresh"
  | "science_mechanism"
  | "system_architecture"
  | "debugging_diagnosis"
  | "tool_workflow"
  | "design_decision"
  | "case_study_application"
  | "historical_development"
  | "process_lifecycle"
  | "terminology_vocabulary"
  | "exam_interview_prep";

export type Topic = {
  id: string;
  study_path_id: string;
  title: string;
  purpose: string | null;

  unit_title: string | null;
  prerequisite_topics: string | null;
  source_refs: string | null;

  order_index: number;
  estimated_minutes: number | null;
  course_type?: CourseType | null;
  secondary_course_types?: CourseType[] | null;
  knowledge_level?: number | null;
  status: TopicStatus | string;
  review_due_at: string | null;
  review_reason: string | null;
  created_at: string;
};

export type Lesson = {
  id: string;
  topic_id: string;
  title: string;
  lesson_json: Record<string, unknown>;

  source_chunk_ids: string[] | null;
  source_summary: string | null;

  generation_status: "pending" | "generating" | "ready" | "failed" | string;

  created_at: string;
};

export type LearningMaterial = {
  id: string;
  class_id: string | null;
  study_path_id: string | null;
  title: string;
  material_type: string;
  filename: string | null;
  created_at: string;
};

export type ContentChunk = {
  id: string;
  material_id: string;
  chunk_index: number;
  text: string;
  created_at: string;
};

export type PracticeHintRequest = {
  study_path_id: string;
  topic_id: string;
  lesson_id?: string | null;
  question: string;
  user_partial_answer?: string | null;
  lesson_context?: string | null;
  current_section?: string | null;
};

export type PracticeHintResponse = {
  hint: string;
  guiding_question: string;
  concept_to_review?: string | null;
};

export type PracticeSubmitRequest = {
  study_path_id: string;
  topic_id: string;
  lesson_id?: string | null;
  question: string;
  user_answer: string;
  lesson_context?: string | null;
  current_section?: string | null;
  concept_tested?: string | null;
  related_section?: string | null;
  hint_used: boolean;
};

export type PracticeSubmitResponse = {
  attempt_id: string;
  is_correct: boolean;
  performance_level: "strong" | "fragile" | "minor_mistake" | "weak";
  mistake_type?: string | null;
  feedback: string;
  follow_up_question?: string | null;
  next_action:
    | "move_on"
    | "edge_case_check"
    | "targeted_follow_up"
    | "minimal_repair";
  adaptive_response?: {
    message?: string;
    performance_level?: "strong" | "fragile" | "minor_mistake" | "weak";
    next_action?: "move_on" | "edge_case_check" | "targeted_follow_up" | "minimal_repair";
    suggested_mode?: string;
    should_continue?: boolean;
    should_generate_repair?: boolean;
    concept_to_review?: string | null;
    follow_up_question?: string | null;
    review_scheduled_at?: string | null;
    review_reason?: string | null;
    topic_status?: string | null;
  };
  created_at: string;
};

export type PracticeAttempt = {
  id: string;
  study_path_id: string;
  topic_id: string;
  lesson_id?: string | null;

  question: string;
  user_answer: string;

  is_correct?: boolean | null;
  performance_level?: "strong" | "fragile" | "minor_mistake" | "weak" | null;
  mistake_type?: string | null;

  feedback?: string | null;
  hint_used: boolean;

  follow_up_question?: string | null;
  next_action?:
    | "move_on"
    | "edge_case_check"
    | "targeted_follow_up"
    | "minimal_repair"
    | null;

  created_at: string;
};

export type QuickPracticeSession = {
  id: string;
  prompt: string;
  title?: string | null;
  source_filename?: string | null;
  current_question?: string | null;
  exact_problem?: boolean;
  created_at: string;
};

export type QuickPracticeQuestionType =
  | "short_answer"
  | "multiple_choice"
  | "select_all"
  | "math"
  | "math_input"
  | "coding"
  | "coding_environment"
  | "visual_labeling"
  | "ordering"
  | "debugging"
  | "debugging_scenario"
  | "decision_scenario";

export type QuickPracticeQuestion = {
  id: string;
  session_id: string;
  question_type: QuickPracticeQuestionType | string;
  topic?: string | null;
  skill_target?: string | null;
  difficulty?: "Easy" | "Medium" | "Hard" | string | null;
  question_text: string;
  choices: string[];
  given: string[];
  starter_code?: string | null;
  language?: string | null;
  test_cases: {
    input: string;
    expected: string;
  }[];
  source_reference?: string | null;
  reason?: string | null;
  order_index: number;
  created_at: string;
};

export type QuickPracticeAttempt = {
  id: string;
  session_id: string;
  question_id?: string | null;
  question: string;
  question_type?: QuickPracticeQuestionType | string | null;
  user_answer: string;
  is_correct?: boolean | null;
  performance_level?: "strong" | "fragile" | "minor_mistake" | "weak" | null;
  mistake_type?: string | null;
  feedback?: string | null;
  hint_used: boolean;
  follow_up_question?: string | null;
  next_action?:
    | "move_on"
    | "edge_case_check"
    | "targeted_follow_up"
    | "minimal_repair"
    | null;
  created_at: string;
};

export type TopicScheduleReviewPayload = {
  review_due_at: string | null;
  review_reason?: string | null;
};

export type WeakArea = {
  mistake_type: string;
  count: number;
  latest_feedback: string | null;
  recommended_action: string;
};

export type WeakAreaSummary = {
  scope_id: string;
  scope_type: string;
  weak_areas: WeakArea[];
};

export type StudySessionActivityType =
  | "lesson"
  | "practice"
  | "qa"
  | "review"
  | "regeneration";

export type StudySession = {
  id: string;
  class_id?: string | null;
  study_path_id?: string | null;
  topic_id?: string | null;
  minutes_spent: number;
  activity_type: StudySessionActivityType | string;
  created_at: string;
};

export type StudySessionCreate = {
  class_id?: string | null;
  study_path_id?: string | null;
  topic_id?: string | null;
  minutes_spent: number;
  activity_type: StudySessionActivityType;
};

export type ClassDailyPlanTask = {
  task_type: string;
  title: string;
  reason: string;
  study_path_id: string;
  study_path_title: string;
  topic_id: string;
  topic_status: string;
  estimated_minutes: number;
};

export type ClassDailyPlan = {
  class_id: string;
  today_minutes: number;
  daily_goal_minutes: number | null;
  remaining_today_minutes: number;
  tasks: ClassDailyPlanTask[];
};

export type HomeRecommendationType =
  | "review_due"
  | "weak_area"
  | "in_progress"
  | "not_started";

export type HomeRecommendation = {
  type: HomeRecommendationType | string;
  title: string;
  reason: string;

  class_id?: string | null;
  class_name?: string | null;

  study_path_id?: string | null;
  study_path_title?: string | null;

  topic_id?: string | null;
  topic_title?: string | null;

  review_due_at?: string | null;
  review_reason?: string | null;

  minutes_estimate?: number | null;
};

export type StudySessionSummary = {
  total_minutes: number;
  lesson_minutes: number;
  practice_minutes: number;
  qa_minutes: number;
  review_minutes: number;
  regeneration_minutes: number;
  session_count: number;
};

export type ClassQASource = {
  chunk_id: string;
  material_id: string;
  material_title: string;
  material_filename?: string | null;
  chunk_index: number;
  source_label: string;
  preview: string;
};

export type ClassQAResponse = {
  answer: string;
  sources: ClassQASource[];
};

export type TopicQASource = {
  chunk_id: string;
  material_id: string;
  material_title: string;
  material_filename?: string | null;
  chunk_index: number;
  source_label: string;
  preview: string;
};

export type TopicQAResponse = {
  answer: string;
  sources: TopicQASource[];
  confusion_event_id?: string | null;
  confusion_type: string;
  concept_name: string;
  clarification_mode: string;
  suggested_actions: string[];
  follow_up_prompts: string[];
};

export type ConfusionEvent = {
  id: string;
  topic_id: string;
  study_path_id?: string | null;
  lesson_id?: string | null;
  card_id?: string | null;
  card_title?: string | null;
  current_section?: string | null;
  highlighted_text?: string | null;
  user_question: string;
  answer_generated: string;
  confusion_type: string;
  concept_name: string;
  clarification_mode: string;
  resolved: boolean;
  still_confused_count: number;
  follow_up_count: number;
  suggested_actions: string[];
  created_at: string;
};

export type CodeRunTestCase = {
  input: string;
  expected: string;
};

export type CodeRunCaseResult = {
  case_number: number;
  input: string;
  expected: string;
  actual: string;
  stderr: string;
  passed: boolean;
  status: string;
};

export type CodeRunResponse = {
  language: string;
  passed: number;
  total: number;
  all_passed: boolean;
  error?: string | null;
  hidden_passed?: number;
  hidden_total?: number;
  cases: CodeRunCaseResult[];
};

export type RecommendedTopic = {
  id: string;
  title: string;
  status: string;
  purpose?: string | null;
  estimated_minutes?: number | null;
};

export type StudyPathRecommendation = {
  message: string;
  topic: RecommendedTopic | null;
  is_complete: boolean;
};

export type ClassRecommendedTopic = {
  id: string;
  title: string;
  status: string;
  estimated_minutes?: number | null;
};

export type ClassRecommendedStudyPath = {
  id: string;
  title: string;
};

export type ClassRecommendation = {
  message: string;
  topic: ClassRecommendedTopic | null;
  study_path: ClassRecommendedStudyPath | null;
  is_complete: boolean;

  today_minutes: number;
  daily_goal_minutes: number | null;
  remaining_today_minutes: number;

  week_minutes: number;
  weekly_goal_minutes: number | null;
  remaining_week_minutes: number;

  deadline: string | null;
};

export type WeakAreaQuestionRequest = {
  mistake_type: string;
  lesson_context?: string | null;
};

export type WeakAreaQuestionResponse = {
  question: string;
  target_mistake_type: string;
  reason: string;
};

export type SpacedReviewQuestionRequest = {
  lesson_context?: string | null;
};

export type SpacedReviewQuestionResponse = {
  question: string;
  reason: string;
  review_due_at?: string | null;
};

export type KnowledgeState =
  | "unknown"
  | "familiar"
  | "fragile"
  | "stable"
  | "transferable";

export type DiagnosticMode =
  | "topic_start"
  | "refresh"
  | "review"
  | "final_review";

export type StartingMode =
  | "full_teach"
  | "compressed_refresher"
  | "nuance_first"
  | "edge_cases"
  | "transfer_practice";

export type SelfReportResult = {
  topic_id: string;
  self_report_level: number;
  estimated_state: KnowledgeState;
  recommended_starting_mode: StartingMode;
  explanation_density: string;
  should_offer_diagnostic: boolean;
};

export type DiagnosticQuestion = {
  id: string;
  type: "recall" | "application" | "edge_case" | "transfer" | "confidence";
  question: string;
  concept_name?: string | null;
};

export type StartDiagnosticResult = {
  diagnostic_id: number;
  topic_id: string;
  mode: DiagnosticMode;
  questions: DiagnosticQuestion[];
};

export type DiagnosticAnswer = {
  question_id: string;
  answer: string;
  confidence?: number | null;
};

export type SubmitDiagnosticResult = {
  diagnostic_id: number;
  topic_id: string;
  estimated_state: KnowledgeState;
  recommended_starting_mode: StartingMode;
  result_summary: string;
  concept_states: {
    concept_name: string;
    knowledge_state: KnowledgeState;
    review_due_at?: string | null;
    review_reason?: string | null;
  }[];
};

export type LearnerSignalPayload = {
  topic_id: string;
  concept_name: string;
  signal_type:
    | "self_report"
    | "diagnostic"
    | "practice"
    | "lesson_micro_check"
    | "question"
    | "hint"
    | "reread"
    | "time_on_slide"
    | "confidence";
  correctness?: number | null;
  reasoning_quality?: number | null;
  hint_used?: boolean;
  confidence?: number | null;
  transfer_success?: number | null;
  edge_case_success?: number | null;
  time_seconds?: number | null;
  mistake_type?: string | null;
  summary?: string | null;
  metadata?: Record<string, unknown>;
};

export type LearnerConceptState = {
  id: number;
  topic_id: string;
  concept_name: string;
  knowledge_state: KnowledgeState;

  familiarity_score: number;
  conceptual_score: number;
  procedural_score: number;
  transfer_score: number;
  confidence_score: number;
  stability_score: number;

  total_attempts: number;
  correct_attempts: number;
  hint_count: number;
  misconception_count: number;
  recurring_mistakes: unknown[];

  review_due_at?: string | null;
  review_reason?: string | null;
};

export type AlignmentSummary = {
  topic_id: string;
  strongest_concepts: LearnerConceptState[];
  fragile_concepts: LearnerConceptState[];
  review_queue: LearnerConceptState[];
  recommended_starting_mode: StartingMode;
  adaptation_note: string;
};

async function getAuthHeaders(): Promise<Record<string, string>> {
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const accessToken = session?.access_token;

  if (!accessToken) {
    return {};
  }

  return {
    Authorization: `Bearer ${accessToken}`,
  };
}

async function handleUnauthorized() {
  await supabase.auth.signOut();

  if (typeof window !== "undefined") {
    window.location.assign("/login");
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  const authHeaders = await getAuthHeaders();

  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
      ...(options?.headers ?? {}),
    },
  });

  if (res.status === 401) {
    await handleUnauthorized();
  }

  if (!res.ok) {
    const errorText = await res.text();

    console.error("API request failed:", {
      url,
      status: res.status,
      statusText: res.statusText,
      body: errorText,
    });

    throw new Error(errorText || `Request failed with status ${res.status}`);
  }

  return res.json();
}

export function submitSelfReport(
  topicId: string,
  payload: {
    level: number;
    mode?: DiagnosticMode;
  }
) {
  return request<SelfReportResult>(
    `/learner-state/topics/${topicId}/self-report`,
    {
      method: "POST",
      body: JSON.stringify({
        level: payload.level,
        mode: payload.mode ?? "topic_start",
      }),
    }
  );
}

export function startDiagnostic(
  topicId: string,
  payload: {
    mode?: DiagnosticMode;
    self_report_level?: number | null;
  } = {}
) {
  return request<StartDiagnosticResult>(
    `/learner-state/topics/${topicId}/diagnostic/start`,
    {
      method: "POST",
      body: JSON.stringify({
        mode: payload.mode ?? "topic_start",
        self_report_level: payload.self_report_level ?? null,
      }),
    }
  );
}

export function submitDiagnostic(
  diagnosticId: number,
  answers: DiagnosticAnswer[]
) {
  return request<SubmitDiagnosticResult>(
    `/learner-state/diagnostic/${diagnosticId}/submit`,
    {
      method: "POST",
      body: JSON.stringify({ answers }),
    }
  );
}

export function submitLearnerSignal(payload: LearnerSignalPayload) {
  return request<{
    id: number;
    topic_id: string;
    concept_name: string;
    knowledge_state: KnowledgeState;
    review_due_at?: string | null;
    review_reason?: string | null;
  }>("/learner-state/signals", {
    method: "POST",
    body: JSON.stringify({
      hint_used: false,
      metadata: {},
      ...payload,
    }),
  });
}

export function getTopicLearnerState(topicId: string) {
  return request<LearnerConceptState[]>(`/learner-state/topics/${topicId}`);
}

export function getTopicAlignment(topicId: string) {
  return request<AlignmentSummary>(
    `/learner-state/topics/${topicId}/alignment`
  );
}

export function generateWeakAreaQuestion(
  topicId: string,
  payload: WeakAreaQuestionRequest
) {
  return request<WeakAreaQuestionResponse>(
    `/practice/topic/${topicId}/weak-area-question`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export function generateSpacedReviewQuestion(
  topicId: string,
  payload: SpacedReviewQuestionRequest
) {
  return request<SpacedReviewQuestionResponse>(
    `/practice/topic/${topicId}/review-question`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export function getClassWeakAreas(classId: string) {
  return request<WeakAreaSummary>(`/practice/class/${classId}/weak-areas`);
}

export function askTopicQuestion(
  topicId: string,
  question: string,
  lessonContext?: string,
  selectedText?: string,
  currentSection?: string,
  studyPathId?: string,
  lessonId?: string | null,
  options: {
    card_id?: string | null;
    card_title?: string | null;
    clarification_mode?: string | null;
    prior_confusion_event_id?: string | null;
  } = {}
) {
  return request<TopicQAResponse>(`/topics/${topicId}/qa`, {
    method: "POST",
    body: JSON.stringify({
      question,
      study_path_id: studyPathId ?? null,
      lesson_id: lessonId ?? null,
      current_section: currentSection ?? null,
      lesson_context: lessonContext ?? null,
      selected_text: selectedText ?? null,
      highlighted_text: selectedText ?? null,
      card_id: options.card_id ?? null,
      card_title: options.card_title ?? null,
      clarification_mode: options.clarification_mode ?? null,
      prior_confusion_event_id: options.prior_confusion_event_id ?? null,
    }),
  });
}

export function getTopicConfusionEvents(topicId: string) {
  return request<ConfusionEvent[]>(`/topics/${topicId}/confusion-events`);
}

export function updateConfusionEvent(
  eventId: string,
  payload: {
    resolved?: boolean | null;
    still_confused?: boolean;
    follow_up?: boolean;
    practice_check_correctness?: number | null;
  }
) {
  return request<ConfusionEvent>(`/confusion-events/${eventId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function getTopicWeakAreas(topicId: string) {
  return request<WeakAreaSummary>(`/practice/topic/${topicId}/weak-areas`);
}

export function getStudyPathWeakAreas(studyPathId: string) {
  return request<WeakAreaSummary>(
    `/practice/study-path/${studyPathId}/weak-areas`
  );
}

export function scheduleTopicReview(
  topicId: string,
  payload: TopicScheduleReviewPayload
) {
  return request<Topic>(`/topics/${topicId}/schedule-review`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function getStudyPathRecommendation(studyPathId: string) {
  return request<StudyPathRecommendation>(
    `/study-paths/${studyPathId}/recommendation`
  );
}

export function getClassRecommendation(classId: string) {
  return request<ClassRecommendation>(`/classes/${classId}/recommendation`);
}

export function getHomeRecommendations() {
  return request<HomeRecommendation[]>("/recommendations/home");
}

export async function getPracticeHint(
  payload: PracticeHintRequest
): Promise<PracticeHintResponse> {
  return request<PracticeHintResponse>("/practice/hint", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function submitPracticeAnswer(
  payload: PracticeSubmitRequest
): Promise<PracticeSubmitResponse> {
  return request<PracticeSubmitResponse>("/practice/submit", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getTopicPracticeAttempts(topicId: string) {
  return request<PracticeAttempt[]>(`/practice/topic/${topicId}/attempts`);
}

export function createQuickPracticeSession(payload: {
  prompt: string;
  exact_problem?: boolean;
}) {
  return request<QuickPracticeSession>("/quick-practice/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function runPracticeCode(payload: {
  code: string;
  language?: string | null;
  test_cases: CodeRunTestCase[];
}): Promise<CodeRunResponse> {
  return request<CodeRunResponse>("/practice/run-code", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function runQuickPracticeCode(
  sessionId: string,
  payload: {
    question_id?: string | null;
    code: string;
    language?: string | null;
    test_cases: CodeRunTestCase[];
  }
): Promise<CodeRunResponse> {
  return request<CodeRunResponse>(`/quick-practice/${sessionId}/run-code`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getQuickPracticeSession(sessionId: string) {
  return request<QuickPracticeSession>(`/quick-practice/${sessionId}`);
}

export function getQuickPracticeSessions() {
  return request<QuickPracticeSession[]>("/quick-practice/");
}

export async function uploadQuickPracticePdf(sessionId: string, file: File) {
  const formData = new FormData();
  formData.append("file", file);

  const authHeaders = await getAuthHeaders();

  const res = await fetch(
    `${API_BASE_URL}/quick-practice/${sessionId}/materials/pdf`,
    {
      method: "POST",
      headers: {
        ...authHeaders,
      },
      body: formData,
    }
  );

  if (res.status === 401) {
    await handleUnauthorized();
  }

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(errorText || "Quick practice PDF upload failed");
  }

  return res.json() as Promise<QuickPracticeSession>;
}

export function generateQuickPracticeQuestion(sessionId: string) {
  return request<QuickPracticeQuestion>(
    `/quick-practice/${sessionId}/question`,
    {
      method: "POST",
    }
  );
}

export function generateQuickPracticeQuestionSet(
  sessionId: string,
  payload: {
    count?: number;
    replace_existing?: boolean;
  } = {}
) {
  return request<QuickPracticeQuestion[]>(
    `/quick-practice/${sessionId}/questions/generate-set`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export function getQuickPracticeQuestions(sessionId: string) {
  return request<QuickPracticeQuestion[]>(
    `/quick-practice/${sessionId}/questions`
  );
}

export function regenerateTopicVisuals(topicId: string) {
  return request<{ status: string }>(`/topics/${topicId}/regenerate-visuals`, {
    method: "POST",
  });
}

export function getTopicLessonStatus(topicId: string) {
  return request<{ generation_status: string }>(`/topics/${topicId}/lesson-status`);
}

export function getQuickPracticeHint(
  sessionId: string,
  payload: {
    question_id?: string | null;
    question?: string | null;
    user_partial_answer?: string | null;
  }
) {
  return request<PracticeHintResponse>(`/quick-practice/${sessionId}/hint`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function submitQuickPracticeAnswer(
  sessionId: string,
  payload: {
    question_id?: string | null;
    question?: string | null;
    user_answer: string;
    hint_used: boolean;
  }
) {
  return request<PracticeSubmitResponse>(
    `/quick-practice/${sessionId}/submit`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export function getQuickPracticeAttempts(sessionId: string) {
  return request<QuickPracticeAttempt[]>(
    `/quick-practice/${sessionId}/attempts`
  );
}

export function updateTopicStatus(topicId: string, status: TopicStatus) {
  return request<Topic>(`/topics/${topicId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export function createStudySession(payload: StudySessionCreate) {
  return request<StudySession>("/study-sessions/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getStudyPathSessions(studyPathId: string) {
  return request<StudySession[]>(`/study-sessions/study-path/${studyPathId}`);
}

export function getStudyPathSessionSummary(studyPathId: string) {
  return request<StudySessionSummary>(
    `/study-sessions/study-path/${studyPathId}/summary`
  );
}

export function getClassSessions(classId: string) {
  return request<StudySession[]>(`/study-sessions/class/${classId}`);
}

export function getClassSessionSummary(classId: string) {
  return request<StudySessionSummary>(
    `/study-sessions/class/${classId}/summary`
  );
}

export function getClassTodaySessionSummary(classId: string) {
  return request<StudySessionSummary>(
    `/study-sessions/class/${classId}/today`
  );
}

export function getClassWeekSessionSummary(classId: string) {
  return request<StudySessionSummary>(`/study-sessions/class/${classId}/week`);
}

export function getTopicSessions(topicId: string) {
  return request<StudySession[]>(`/study-sessions/topic/${topicId}`);
}

export function askClassQuestion(classId: string, question: string) {
  return request<ClassQAResponse>(`/classes/${classId}/qa`, {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}

export function generateStudyPathLessons(studyPathId: string) {
  return request<Lesson[]>(`/study-paths/${studyPathId}/generate-lessons`, {
    method: "POST",
  });
}

export function generateInitialStudyPath(
  studyPathId: string,
  options: { useV2?: boolean; regenerate?: boolean } = {},
) {
  // Hybrid visual cutover (default ON, 2026-06-04):
  //   normal generation uses legacy lesson_cards enriched with v2 visuals.
  //   pass useV2:true only for the standalone /learn-v2 experiment.
  //   regenerate:true wipes any existing cached first-topic lesson and
  //     re-rolls it — useful after a schema migration or to test the
  //     v2 pipeline on a path with cached legacy lessons.
  // lesson_version in the response tells the caller which /learn route
  // to redirect to.
  const params = new URLSearchParams();
  if (options.useV2 === true) params.set("use_v2", "true");
  if (options.useV2 === false) params.set("use_v2", "false");
  if (options.regenerate) params.set("regenerate", "true");
  const query = params.toString() ? `?${params.toString()}` : "";
  return request<{
    first_topic_id: string;
    first_lesson_id: string;
    background_generation_started: boolean;
    message: string;
    lesson_version: number;
  }>(`/study-paths/${studyPathId}/generate-initial${query}`, {
    method: "POST",
  });
}

export function regenerateStudyPath(
  studyPathId: string,
  feedback: string,
  overwriteExisting = false
) {
  return request<Lesson[]>(`/study-paths/${studyPathId}/regenerate`, {
    method: "POST",
    body: JSON.stringify({
      feedback,
      overwrite_existing: overwriteExisting,
    }),
  });
}

export function generateStudyPathTopics(
  studyPathId: string,
  overwriteExisting = false
) {
  return request<Topic[]>(`/study-paths/${studyPathId}/generate-topics`, {
    method: "POST",
    body: JSON.stringify({
      overwrite_existing: overwriteExisting,
    }),
  });
}

export type GenerateTopicLessonPayload = {
  starting_mode?: StartingMode | null;
  explanation_density?: string | null;
  estimated_state?: KnowledgeState | null;
  adaptation_note?: string | null;
  fragile_concepts?: string[];
  review_concepts?: string[];
  stable_concepts?: string[];
  transferable_concepts?: string[];
  concepts_to_skip?: string[];
  concepts_to_briefly_repair?: string[];
  memory_guidance?: string | null;
};

export type LessonSegmentRegeneratePayload = {
  lesson_id: string;
  current_card_index: number;
  completed_card_ids: string[];
  trigger: string;
  target_adjustment: string;
  learner_evidence: Record<string, unknown>;
};

export type LessonSegmentRegenerateResponse = {
  lesson: Lesson;
  replacement_cards: Record<string, unknown>[];
  adaptation_message: string;
};

export type TargetedRepairRequest = {
  concept_name: string;
  mistake_type?: string | null;
  question?: string | null;
  user_answer?: string | null;
  lesson_context?: string | null;
  feedback?: string | null;
};

export type TargetedRepairResponse = {
  repair_attempt_id: number;
  target_concept: string;
  repair_explanation: string;
  why_this_matters: string;
  follow_up_question: string;
  next_action: string;
  repair_level: string;
  prior_repair_count: number;
};

export type TargetedRepairFollowUpSubmitResponse = {
  repair_attempt_id: number;
  is_complete: boolean;
  correctness: number;
  reasoning_quality: number;
  feedback: string;
  next_action: string;
  created_at?: string | null;
};

export type ReviewQueueItem = {
  concept_state_id: number;
  topic_id: string;
  topic_title: string;
  concept_name: string;
  knowledge_state: KnowledgeState;
  review_due_at: string | null;
  review_reason: string | null;
  recommended_action: string;
  estimated_minutes: number;
};

export type ReviewQuestionRequest = {
  concept_name: string;
  lesson_context?: string | null;
  review_reason?: string | null;
};

export type ReviewQuestionResponse = {
  target_concept: string;
  question: string;
  reason: string;
  expected_focus: string;
};

export type ReviewAnswerSubmitRequest = {
  topic_id: string;
  concept_name: string;
  question: string;
  answer: string;
  confidence?: number | null;
  review_reason?: string | null;
};

export type ReviewAnswerSubmitResponse = {
  topic_id: string;
  concept_name: string;
  correctness: number;
  reasoning_quality: number;
  feedback: string;
  next_action:
    | "mark_stable"
    | "keep_in_review"
    | "targeted_repair"
    | "schedule_later";
  review_due_at?: string | null;
  review_reason?: string | null;
};


export type StudyPathMemorySummary = {
  study_path_id: string;
  stable_concepts: LearnerMemoryConcept[];
  fragile_concepts: LearnerMemoryConcept[];
  transferable_concepts: LearnerMemoryConcept[];
  unknown_concepts: LearnerMemoryConcept[];
  concepts_to_skip: string[];
  concepts_to_briefly_repair: string[];
  recommended_lesson_guidance: string;

  behavior_guidance?: string | null;
  possible_overteaching_signals?: string[];
  possible_underteaching_signals?: string[];
};

export type AlignmentMetricConcept = {
  concept_name: string;
  topic_id: string;
  topic_title: string;
  knowledge_state: string;
  review_due_at?: string | null;
  review_reason?: string | null;
};

export type StudyPathAlignmentMetrics = {
  study_path_id: string;
  overteaching_score: number;
  underteaching_score: number;
  time_to_alignment_score: number;
  confidence_calibration_score: number;
  transfer_success_rate: number;
  delayed_recall_success_rate: number;
  edge_case_success_rate: number;
  repair_success_rate: number;
  total_concepts_tracked: number;
  stable_or_transferable_concepts: number;
  fragile_or_unknown_concepts: number;
  total_behavior_events: number;
  fast_skip_count: number;
  long_dwell_count: number;
  revisit_count: number;
  hint_count: number;
  practice_count: number;
  targeted_repair_count: number;
  completed_repair_follow_up_count: number;
  concepts_needing_support: AlignmentMetricConcept[];
  concepts_moving_fast: AlignmentMetricConcept[];
  summary: string;
};

export type AdaptivePlanTask = {
  task_type:
    | "review"
    | "fragile_concept_check"
    | "repair_follow_up"
    | "continue_topic"
    | "next_topic"
    | "transfer_challenge"
    | string;
  title: string;
  reason: string;
  topic_id?: string | null;
  topic_title?: string | null;
  concept_name?: string | null;
  estimated_minutes: number;
  priority: number;
  route_mode?: "review" | "learn" | "practice" | string | null;
};

export type AdaptivePlan = {
  study_path_id: string;
  recommended_minutes: number;
  summary: string;
  tasks: AdaptivePlanTask[];
};

export type ClassAdaptivePlanTask = {
  task_type:
    | "review"
    | "fragile_concept_check"
    | "repair_follow_up"
    | "continue_topic"
    | "next_topic"
    | "transfer_challenge"
    | string;
  title: string;
  reason: string;
  class_id?: string | null;
  study_path_id?: string | null;
  study_path_title?: string | null;
  topic_id?: string | null;
  topic_title?: string | null;
  concept_name?: string | null;
  estimated_minutes: number;
  priority: number;
  route_mode?: "review" | "learn" | "practice" | string | null;
};

export type ClassAdaptivePlan = {
  class_id: string;
  recommended_minutes: number;
  summary: string;
  tasks: ClassAdaptivePlanTask[];
};

export type LearnerMemoryConcept = {
  concept_name: string;
  topic_id: string;
  topic_title: string;
  knowledge_state: KnowledgeState | string;
  familiarity_score: number;
  conceptual_score: number;
  procedural_score: number;
  transfer_score: number;
  confidence_score: number;
  stability_score: number;
  review_due_at?: string | null;
  review_reason?: string | null;
};

export type ClassMemorySummary = {
  class_id: string;
  stable_concepts: LearnerMemoryConcept[];
  fragile_concepts: LearnerMemoryConcept[];
  transferable_concepts: LearnerMemoryConcept[];
  unknown_concepts: LearnerMemoryConcept[];
  concepts_to_skip: string[];
  concepts_to_briefly_repair: string[];
  recommended_guidance: string;
};

export type GlobalMemorySummary = {
  stable_patterns: string[];
  fragile_patterns: string[];
  preferred_learning_patterns: string[];
  confidence_patterns: string[];
  recommended_guidance: string;
};

export type AlignmentMetrics = {
  scope_id: string;
  scope_type: string;
  overteaching_score: number;
  underteaching_score: number;
  confidence_calibration_score: number;
  transfer_success_rate: number;
  delayed_recall_success_rate: number;
  edge_case_success_rate: number;
  repair_success_rate: number;
  summary: string;
};

export type TransferChallengeRequest = {
  concept_name: string;
  lesson_context?: string | null;
  prior_context?: string | null;
};

export type TransferChallengeResponse = {
  challenge_id?: number | null;
  target_concept: string;
  challenge: string;
  reason: string;
  expected_focus: string;
};

export type TransferChallengeSubmitResponse = {
  target_concept: string;
  correctness: number;
  reasoning_quality: number;
  feedback: string;
  next_action: "mark_transferable" | "keep_stable" | "targeted_repair" | string;
};

export function getClassAdaptivePlan(
  classId: string,
  params: {
    target_minutes?: number | null;
  } = {}
) {
  const searchParams = new URLSearchParams();

  if (params.target_minutes) {
    searchParams.set("target_minutes", String(params.target_minutes));
  }

  const queryString = searchParams.toString();

  return request<ClassAdaptivePlan>(
    `/learner-state/classes/${classId}/adaptive-plan${
      queryString ? `?${queryString}` : ""
    }`
  );
}

export function getClassMemorySummary(classId: string) {
  return request<ClassMemorySummary>(
    `/learner-state/classes/${classId}/memory-summary`
  );
}

export function getClassAlignmentMetrics(classId: string) {
  return request<AlignmentMetrics>(
    `/learner-state/classes/${classId}/alignment-metrics`
  );
}

export function getGlobalMemorySummary() {
  return request<GlobalMemorySummary>("/learner-state/global-memory-summary");
}

export function generateTransferChallenge(
  topicId: string,
  payload: TransferChallengeRequest
) {
  return request<TransferChallengeResponse>(
    `/learner-state/topics/${topicId}/transfer-challenge`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export function submitTransferChallenge(payload: {
  topic_id: string;
  concept_name: string;
  challenge: string;
  answer: string;
  confidence?: number | null;
}) {
  return request<TransferChallengeSubmitResponse>(
    "/learner-state/transfer-challenge/submit",
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export function getStudyPathAdaptivePlan(
  studyPathId: string,
  params: {
    target_minutes?: number | null;
  } = {}
) {
  const searchParams = new URLSearchParams();

  if (params.target_minutes) {
    searchParams.set("target_minutes", String(params.target_minutes));
  }

  const queryString = searchParams.toString();

  return request<AdaptivePlan>(
    `/learner-state/study-paths/${studyPathId}/adaptive-plan${
      queryString ? `?${queryString}` : ""
    }`
  );
}

export function getStudyPathAlignmentMetrics(studyPathId: string) {
  return request<StudyPathAlignmentMetrics>(
    `/learner-state/study-paths/${studyPathId}/alignment-metrics`,
  );
}

export function getStudyPathMemorySummary(studyPathId: string) {
  return request<StudyPathMemorySummary>(
    `/learner-state/study-paths/${studyPathId}/memory-summary`
  );
}

export function getReviewQueue(params: {
  study_path_id?: string | null;
  topic_id?: string | null;
  limit?: number;
} = {}) {
  const searchParams = new URLSearchParams();

  if (params.study_path_id) {
    searchParams.set("study_path_id", params.study_path_id);
  }

  if (params.topic_id) {
    searchParams.set("topic_id", params.topic_id);
  }

  if (params.limit) {
    searchParams.set("limit", String(params.limit));
  }

  const queryString = searchParams.toString();

  return request<ReviewQueueItem[]>(
    `/learner-state/review-queue${queryString ? `?${queryString}` : ""}`
  );
}

export function generateReviewQuestion(
  topicId: string,
  payload: ReviewQuestionRequest
) {
  return request<ReviewQuestionResponse>(
    `/learner-state/topics/${topicId}/review-question`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export function submitReviewAnswer(payload: ReviewAnswerSubmitRequest) {
  return request<ReviewAnswerSubmitResponse>(
    `/learner-state/review-question/submit`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export function submitTargetedRepairFollowUp(
  repairAttemptId: number,
  payload: {
    answer: string;
    confidence?: number | null;
  }
) {
  return request<TargetedRepairFollowUpSubmitResponse>(
    `/learner-state/targeted-repair/${repairAttemptId}/follow-up`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export function generateTargetedRepair(
  topicId: string,
  payload: TargetedRepairRequest
) {
  return request<TargetedRepairResponse>(
    `/learner-state/topics/${topicId}/targeted-repair`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export function generateTopicLesson(
  topicId: string,
  payload: GenerateTopicLessonPayload = {}
) {
  return request<Lesson>(`/topics/${topicId}/generate-lesson`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function regenerateTopicLesson(topicId: string, feedback: string) {
  return request<Lesson>(`/topics/${topicId}/regenerate-lesson`, {
    method: "POST",
    body: JSON.stringify({ feedback }),
  });
}

export function regenerateTopicLessonSegment(
  topicId: string,
  payload: LessonSegmentRegeneratePayload
) {
  return request<LessonSegmentRegenerateResponse>(
    `/topics/${topicId}/regenerate-lesson-segment`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export function getClassMaterials(classId: string) {
  return request<LearningMaterial[]>(`/classes/${classId}/materials`);
}

export function getStudyPathMaterials(studyPathId: string) {
  return request<LearningMaterial[]>(`/study-paths/${studyPathId}/materials`);
}

export function createTextMaterial(
  classId: string,
  payload: {
    title: string;
    text: string;
  }
) {
  return request<LearningMaterial>(`/classes/${classId}/materials/text`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createStudyPathTextMaterial(
  studyPathId: string,
  payload: {
    title: string;
    text: string;
  }
) {
  return request<LearningMaterial>(`/study-paths/${studyPathId}/materials/text`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function uploadPdfMaterial(classId: string, file: File) {
  const formData = new FormData();
  formData.append("file", file);

  const authHeaders = await getAuthHeaders();

  const res = await fetch(`${API_BASE_URL}/classes/${classId}/materials/pdf`, {
    method: "POST",
    headers: {
      ...authHeaders,
    },
    body: formData,
  });

  if (res.status === 401) {
    await handleUnauthorized();
  }

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(errorText || "PDF upload failed");
  }

  return res.json() as Promise<LearningMaterial>;
}

export function getMaterialChunks(materialId: string) {
  return request<ContentChunk[]>(`/materials/${materialId}/chunks`);
}

export function getStudyPathTopics(studyPathId: string) {
  return request<Topic[]>(`/study-paths/${studyPathId}/topics`);
}

export async function uploadPdfMaterialToStudyPath(
  studyPathId: string,
  file: File
) {
  const formData = new FormData();
  formData.append("file", file);

  const authHeaders = await getAuthHeaders();

  const res = await fetch(
    `${API_BASE_URL}/study-paths/${studyPathId}/materials/pdf`,
    {
      method: "POST",
      headers: {
        ...authHeaders,
      },
      body: formData,
    }
  );

  if (res.status === 401) {
    await handleUnauthorized();
  }

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(errorText || "Study path PDF upload failed");
  }

  return res.json() as Promise<LearningMaterial>;
}

export function getTopicLesson(topicId: string) {
  return request<Lesson>(`/topics/${topicId}/lesson`);
}

export type LessonStreamEvent =
  | { type: "card"; card: Record<string, unknown> }
  | { type: "complete"; lesson?: unknown }
  | { type: "busy" }
  | { type: "error"; message?: string };

/**
 * Stream a lesson as newline-delimited JSON so early cards can be previewed
 * while later ones generate. Best-effort: callers should fall back to the
 * blocking generate/poll flow if this throws or emits `busy`/`error`.
 */
export async function streamTopicLesson(
  topicId: string,
  onEvent: (event: LessonStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE_URL}/topics/${topicId}/lesson-stream`, {
    method: "GET",
    headers: { ...authHeaders },
    signal,
  });
  if (res.status === 401) {
    await handleUnauthorized();
    throw new Error("unauthorized");
  }
  if (!res.ok || !res.body) {
    throw new Error(`lesson stream failed: ${res.status}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  const drain = (flush = false) => {
    let nl: number;
    while ((nl = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, nl).trim();
      buf = buf.slice(nl + 1);
      if (line) {
        try {
          onEvent(JSON.parse(line) as LessonStreamEvent);
        } catch {
          /* ignore a malformed/partial line */
        }
      }
    }
    if (flush) {
      const tail = buf.trim();
      if (tail) {
        try {
          onEvent(JSON.parse(tail) as LessonStreamEvent);
        } catch {
          /* ignore */
        }
      }
    }
  };
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    drain();
  }
  drain(true);
}

export function getClass(classId: string) {
  return request<AzaleaClass>(`/classes/${classId}`);
}

export function getClasses() {
  return request<AzaleaClass[]>("/classes/");
}

export function createClass(payload: {
  name: string;
  description?: string;
  deadline?: string | null;
  daily_goal_minutes?: number | null;
  weekly_goal_minutes?: number | null;
}) {
  return request<AzaleaClass>("/classes/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateClass(classId: string, payload: ClassUpdatePayload) {
  return request<AzaleaClass>(`/classes/${classId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function getStudyPath(studyPathId: string) {
  return request<StudyPath>(`/study-paths/${studyPathId}`);
}

export function getStudyPaths() {
  return request<StudyPath[]>("/study-paths/");
}

export function createStudyPath(payload: {
  title: string;
  goal?: string;
  estimated_minutes_remaining?: number;
}) {
  return request<StudyPath>("/study-paths/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function addStudyPathToClass(classId: string, studyPathId: string) {
  return request<AzaleaClass>(`/classes/${classId}/study-paths/${studyPathId}`, {
    method: "POST",
  });
}

export function getClassDailyPlan(classId: string) {
  return request<ClassDailyPlan>(`/classes/${classId}/daily-plan`);
}

export function getClassStudyPaths(classId: string) {
  return request<StudyPath[]>(`/classes/${classId}/study-paths`);
}
