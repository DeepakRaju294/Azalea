"use client";

/**
 * LEGACY (deprecated) — slated for removal in Phase 8.
 *
 * Replaced by frontend/app/study-paths/[studyPathId]/learn-v2/page.tsx,
 * which consumes the new VisualModel + RenderStep contract.
 *
 * This file (~12,000 lines) contains the legacy visual resolution chain:
 *   resolveCardVisual → LearningCard.resolvedVisual → isLessonVisualRenderable
 *   → VisualRenderer → ~17 inline typed renderers.
 *
 * Removal blocked on: see PHASE_8_DECOMMISSION.md (project root).
 */

import Image from "next/image";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type MutableRefObject,
  type ReactNode,
  type TouchEvent,
} from "react";
import {
  askTopicQuestion,
  createStudySession,
  generateTargetedRepair,
  generateReviewQuestion,
  generateTransferChallenge,
  generateStudyPathLessons,
  generateStudyPathTopics,
  generateTopicLesson,
  getTopicConfusionEvents,
  getPracticeHint,
  getStudyPath,
  getStudyPathMemorySummary,
  getStudyPathTopics,
  getTopicLesson,
  getTopicLessonStatus,
  streamTopicLesson,
  getStudyPathWeakAreas,
  regenerateStudyPath,
  regenerateTopicLessonSegment,
  regenerateTopicLesson,
  runPracticeCode,
  submitPracticeAnswer,
  submitReviewAnswer,
  submitTransferChallenge,
  submitTargetedRepairFollowUp,
  submitLearnerSignal,
  updateTopicStatus,
  updateConfusionEvent,
  type ConfusionEvent,
  type Lesson,
  type StartingMode,
  type TargetedRepairResponse,
  type TargetedRepairFollowUpSubmitResponse,
  type ReviewAnswerSubmitResponse,
  type ReviewQuestionResponse,
  type TransferChallengeResponse,
  type TransferChallengeSubmitResponse,
  type PracticeHintResponse,
  type PracticeSubmitResponse,
  type StudyPath,
  type StudyPathMemorySummary,
  type StudySessionActivityType,
  type Topic,
  type TopicQAResponse,
  type TopicStatus,
  type WeakAreaSummary,
} from "@/lib/api";
import { askVisualQuestionV2 } from "@/lib/api_v2";
import { useRequireAuth } from "@/lib/auth";
import TopicCalibrationCard from "@/components/TopicCalibrationCard";
import DiagnosticMiniFlow from "@/components/DiagnosticMiniFlow";
import AdaptationExplanationBanner from "@/components/AdaptationExplanationBanner";
import { VisualRenderer as V2VisualRenderer } from "@/components/visuals_v2/VisualRenderer";
import { SHOW_VISUAL_DATA_INSTEAD_OF_RENDER, VisualDataPanel } from "@/lib/visualDebug";
import type {
  LessonV2,
  SelectableElement,
  VisualContextPayload,
  VisualFrame,
  VisualModel,
} from "@/lib/visual_v2_types";
import {
  clearFlowResume,
  saveFlowResume,
  type FlowResumePhase,
} from "@/lib/flowResume";
import {
  CartesianGrid,
  Bar,
  BarChart,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type VisualTableRow = string[];

type VisualStep = {
  kind?: string;
  label?: string;
  step_title?: string;
  visual_label?: string;
  description?: string;
  step_detail?: string;
  mini_visual?: string;
  formula?: string;
  cases?: string[];
  active?: boolean;
};

type VisualSymbol = {
  symbol?: string;
  meaning?: string;
};

type VisualKeyPoint = {
  x?: number;
  y?: number;
  label?: string;
};

type ArrayStatePointer = {
  label?: string;
  index?: number;
  side?: "top" | "bottom" | string;
};

type ArrayStateRange = {
  label?: string;
  start?: number;
  end?: number;
};

type ArrayStateRow = {
  label?: string;
  values?: string[];
  emphasis?: boolean;
};

type ConceptMapNode = {
  id?: string;
  label?: string;
  description?: string;
  relation?: string;
  state?: string;
  x?: number;
  y?: number;
};

type VisualEdge = {
  from?: string;
  to?: string;
  label?: string;
  style?: string;
  state?: string;
};

type CircuitComponent = {
  id?: string;
  type?: string;
  label?: string;
  value?: string;
  x?: number;
  y?: number;
};

type VisualLabel = {
  target?: string;
  text?: string;
};

type VisualPlanItem = {
  kind?: string;
  type?: string;
  title?: string;
  description?: string;
  purpose?: string;
  placement?: string;
  elements?: string[];
  highlight?: string;
  labels?: VisualLabel[];

  columns?: string[];
  rows?: VisualTableRow[];

  steps?: VisualStep[];

  formula?: string;
  symbols?: VisualSymbol[];
  when_to_use?: string;

  center?: string;
  nodes?: ConceptMapNode[];
  edges?: VisualEdge[];
  traversal_path?: string[];
  components?: CircuitComponent[];
  wires?: VisualEdge[];

  x_label?: string;
  y_label?: string;
  data_points?: [number, number][];
  key_points?: VisualKeyPoint[];
  array_values?: string[];
  array_rows?: ArrayStateRow[];
  array_pointers?: ArrayStatePointer[];
  array_ranges?: ArrayStateRange[];
  array_annotations?: string[];
  what_to_notice?: string;

  code?: string;
  language?: string;
  highlight_lines?: [number, number];
  max_line?: number;
  highlight_row?: number;

  wrong?: string;
  correct?: string;
  wrong_label?: string;
  correct_label?: string;
  why?: string;
  counterexample?: string;
  children?: VisualPlanItem[];
};

type LessonPracticeQuestion = {
  question_type?:
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
    | "decision_scenario"
    | string;
  topic?: string;
  skill_target?: string;
  difficulty?: "Easy" | "Medium" | "Hard" | string;
  question_text?: string;
  concept_tested?: string;
  related_section?: string;
  why_this_matters?: string;
  choices?: string[];
  given?: string[];
  starter_code?: string;
  language?: string;
  test_cases?: {
    input?: string;
    expected?: string;
  }[];
  correct_answer?: string;
  explanation?: string;
};

type LessonInteractiveLink = {
  text?: string;
  explanation?: string;
  why_it_matters_here?: string;
  action?: "popup_only" | "open_study_path" | "review_earlier_topic" | "ask_question" | string;
  target?: string;
};

type LessonCardType =
  | "intro"
  | "purpose"
  | "purpose_context"
  | "core_idea"
  | "definition"
  | "intuition"
  | "visual"
  | "method_process"
  | "process_step"
  | "worked_example"
  | "example"
  | "formula"
  | "comparison"
  | "edge_case"
  | "quick_practice"
  | "micro_check"
  | "summary"
  | "bridge_to_next_topic"
  | string;

type LessonFlowCard = {
  id?: string;
  blueprint_key?: string;
  card_type?: LessonCardType;
  title?: string;
  body?: string[];
  bullets?: string[];
  points?: string[];
  main_concept?: string;
  new_concepts?: string[];
  review_concepts?: string[];
  prerequisite_concepts?: string[];
  common_misconceptions?: string[];
  concept_support?: {
    concept?: string;
    state_hint?: string;
    support?: string;
    hover_explanation?: string;
  }[];
  interactive_links?: LessonInteractiveLink[];
  styled_elements?: LessonStyledElement[];
  visual_plan?: VisualPlanItem | Record<string, unknown>;
  visual_type?: string;
  visual_description?: string;
  annotations?: {
    label?: string;
    explanation?: string;
  }[];
  example?: string;
  micro_check?: {
    type?: string;
    prompt?: string;
    answer?: string;
  };
  what_to_notice?: string;
  next_transition?: string;
  estimated_seconds?: number;
  transition_text?: string;
  next_card_label?: string;
  practice_question_index?: number;
  visual_index?: number;
  learning_job?: string;
  explanation?: string;
  code_snippet?: string;
  code_language?: string;
  highlight_lines_per_step?: [number, number][];
  practice_question?: string;
  practice_answer?: string;
  practice_choices?: string[];
  visual_focus?: VisualFocusState;
  example_problem?: ExampleProblem;
  visual_v2_ref?: {
    visual_model_id?: string;
    frame_index?: number;
    // One frame per bullet: as each point reveals, the highlight (and variable
    // panel) advance to the line that point describes.
    frame_index_per_point?: number[];
    source?: string;
  };
  // Optional supporting diagram for code-lens worked examples (the array/pointer
  // view alongside the executing code), shown via the Diagram/Code toggle.
  diagram_v2_ref?: {
    visual_model_id?: string;
    frame_index?: number;
    source?: string;
  };
};

type ExampleProblem = {
  kind?: string;
  title?: string;
  summary?: string;
  values?: unknown[];
  parameters?: Record<string, unknown>;
  state?: Record<string, unknown>;
};

type VisualFocusState = {
  active_nodes: string[];
  highlight_path: string[];
  active_step: number;
  attention_note: string;
};

type LessonStyledElement = {
  type?: string;
  title?: string;
  data?: Record<string, unknown>;
};

type LessonJson = {
  intro?: string;
  purpose?: string;
  context?: string;
  learning_objective?: string;
  components?: string[];
  concepts?: string[];
  process?: string[];
  limitations?: string[] | string;
  worked_examples?: {
    title?: string;
    steps?: string[];
  }[];
  edge_cases?: string[];
  practice?: string[];
  lesson_cards?: LessonFlowCard[];
  visual_models?: VisualModel[];
  practice_questions?: LessonPracticeQuestion[];
  key_takeaways?: string[];
  visual_plan?: VisualPlanItem[];
  source_preview?: string;
  adaptation_metadata?: {
    starting_mode?: string;
    estimated_state?: string;
    adaptation_summary?: string;
    teaching_strategy?: string;
  };
};

type LearningStepBase = {
  cardType?: LessonCardType;
  estimatedSeconds?: number;
  transitionText?: string;
  nextCardLabel?: string;
};

type LearningStep =
  | (LearningStepBase & {
      type: "purpose_context";
      title: string;
      intro: string;
      purpose: string;
      context: string;
      learningObjective: string;
    })
  | (LearningStepBase & {
      type: "flow_card";
      title: string;
      body: string[];
      bullets: string[];
      card?: LessonFlowCard;
      visual?: VisualPlanItem;
      /** For reveal-build steps: index in bullets[] where newly added content begins */
      revealFromIndex?: number;
      /** For code block worked_example steps: which code lines to highlight [start, end] (1-indexed) */
      highlightLines?: [number, number];
      /** For code block worked_example steps: highest line number revealed so far (cumulative max) */
      maxCodeLine?: number;
      /** For reveal-build cards: which visual step index this bullet group corresponds to.
       *  Lets the progressive_step_flow visual advance its highlight as bullets reveal. */
      activeStepOverride?: number;
    })
  | (LearningStepBase & { type: "text"; title: string; content: string })
  | (LearningStepBase & {
      type: "list";
      title: string;
      items: string[];
      ordered?: boolean;
    })
  | (LearningStepBase & {
      type: "visuals";
      title: string;
      visuals: VisualPlanItem[];
    })
  | (LearningStepBase & {
      type: "worked_examples";
      title: string;
      examples: { title?: string; steps?: string[] }[];
    })
  | (LearningStepBase & {
      type: "practice";
      title: string;
      question: LessonPracticeQuestion;
      questionIndex: number;
    })
  | (LearningStepBase & { type: "source_grounding"; title: string })
  | (LearningStepBase & {
      type: "source_preview";
      title: string;
      content: string;
    });

type RightPanel = "index" | "regenerate" | null;
type CalibrationStep = "calibration" | "diagnostic" | "lesson";
type PacingMode = "fast" | "balanced" | "deep";
type FlowMetrics = {
  cardsCompleted: number;
  topicsCompleted: number;
  quickChecks: number;
  quickCheckCorrect: number;
  skips: number;
  questionsAsked: number;
  totalTransitionMs: number;
  transitionCount: number;
  dropOffCardType?: string;
};
type FlowCheckpoint = {
  type: "topic_complete" | "path_complete";
  completedTopicTitle: string;
  nextTopic?: Topic;
};

export default function StudyPathLearnPage() {
  const params = useParams<{ studyPathId: string }>();
  const studyPathId = params.studyPathId;
  const router = useRouter();
  const { isCheckingAuth } = useRequireAuth();

  const searchParams = useSearchParams();
  const topicIdFromUrl = searchParams.get("topicId") ?? searchParams.get("topic");
  const modeFromUrl = searchParams.get("mode");
  const reviewConceptFromUrl = searchParams.get("concept");
  const resumeFromUrl = searchParams.get("resume") === "1";
  const cardIndexFromUrl = Number(searchParams.get("card") ?? "0");
  const pureV2Mode = searchParams.get("v") === "2";

  useEffect(() => {
    // Hybrid cutover (2026-06-04):
    // `/learn` keeps the preferred legacy shell. When a stored lesson is v2,
    // this page renders v2 synced steps + VisualModel in the legacy visual
    // slot. Use `?v=2` only to inspect the standalone v2 page directly.
    if (!pureV2Mode) return;

    const query = new URLSearchParams();
    if (topicIdFromUrl) query.set("topic", topicIdFromUrl);
    const queryString = query.toString();
    router.replace(
      `/study-paths/${studyPathId}/learn-v2${queryString ? `?${queryString}` : ""}`,
    );
  }, [pureV2Mode, router, studyPathId, topicIdFromUrl]);

  const [studyPath, setStudyPath] = useState<StudyPath | null>(null);
  const [memorySummary, setMemorySummary] =
    useState<StudyPathMemorySummary | null>(null);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [selectedTopicId, setSelectedTopicId] = useState("");
  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [topicLessonStatuses, setTopicLessonStatuses] = useState<
    Record<string, string>
  >({});
  // Mirror of the latest statuses for the background poller to read without
  // being a dependency (which would restart the poll on every status change).
  const topicLessonStatusesRef = useRef(topicLessonStatuses);
  topicLessonStatusesRef.current = topicLessonStatuses;

  // Coding worked examples show two synchronized views — the data-structure
  // diagram and the implementation code — toggled by the learner.
  const [workedExampleVisualView, setWorkedExampleVisualView] = useState<
    "diagram" | "code"
  >("diagram");

  const [status, setStatus] = useState("");
  const [isGeneratingTopics, setIsGeneratingTopics] = useState(false);
  const [isGeneratingLesson, setIsGeneratingLesson] = useState(false);
  // Live preview of cards as they stream in during generation (title + first
  // points). Cleared once the full lesson is ready and rendered.
  const [streamingPreviewCards, setStreamingPreviewCards] = useState<
    { title: string; points: string[] }[]
  >([]);
  const [isGeneratingFullPath, setIsGeneratingFullPath] = useState(false);

  const [practiceAnswers, setPracticeAnswers] = useState<
    Record<number, string>
  >({});
  const [practiceHints, setPracticeHints] = useState<
    Record<number, PracticeHintResponse>
  >({});
  const [practiceFeedback, setPracticeFeedback] = useState<
    Record<number, PracticeSubmitResponse>
  >({});
  const [practiceLoadingIndex, setPracticeLoadingIndex] = useState<
    number | null
  >(null);
  const [practiceError, setPracticeError] = useState<string | null>(null);
  const [hintUsedByQuestion, setHintUsedByQuestion] = useState<
    Record<number, boolean>
  >({});
  const [practiceRunOutput, setPracticeRunOutput] = useState<
    Record<number, string>
  >({});
  const [practiceCodeLanguages, setPracticeCodeLanguages] = useState<
    Record<number, string>
  >({});
  const [practiceConfidence, setPracticeConfidence] = useState<
    Record<number, number>
  >({});
  const [targetedRepairs, setTargetedRepairs] = useState<
    Record<number, TargetedRepairResponse>
  >({});
  const [targetedRepairAnswers, setTargetedRepairAnswers] = useState<
    Record<number, string>
  >({});
  const [targetedRepairConfidence, setTargetedRepairConfidence] = useState<
    Record<number, number>
  >({});
  const [targetedRepairFeedback, setTargetedRepairFeedback] = useState<
    Record<number, TargetedRepairFollowUpSubmitResponse>
  >({});
  const [targetedRepairLoadingIndex, setTargetedRepairLoadingIndex] = useState<
    number | null
  >(null);

  const [reviewQuestion, setReviewQuestion] =
    useState<ReviewQuestionResponse | null>(null);
  const [reviewAnswer, setReviewAnswer] = useState("");
  const [reviewConfidence, setReviewConfidence] = useState(3);
  const [reviewFeedback, setReviewFeedback] =
    useState<ReviewAnswerSubmitResponse | null>(null);
  const [isGeneratingReviewQuestion, setIsGeneratingReviewQuestion] =
    useState(false);
  const [isSubmittingReviewAnswer, setIsSubmittingReviewAnswer] =
    useState(false);

  const [transferChallenge, setTransferChallenge] =
    useState<TransferChallengeResponse | null>(null);
  const [transferAnswer, setTransferAnswer] = useState("");
  const [transferConfidence, setTransferConfidence] = useState(3);
  const [transferFeedback, setTransferFeedback] =
    useState<TransferChallengeSubmitResponse | null>(null);
  const [isGeneratingTransferChallenge, setIsGeneratingTransferChallenge] =
    useState(false);
  const [isSubmittingTransferChallenge, setIsSubmittingTransferChallenge] =
    useState(false);

  const [regenerationFeedback, setRegenerationFeedback] = useState("");
  const [isRegeneratingTopic, setIsRegeneratingTopic] = useState(false);
  const [isRegeneratingPath, setIsRegeneratingPath] = useState(false);

  const [topicQuestion, setTopicQuestion] = useState("");
  const [topicQAResponse, setTopicQAResponse] =
    useState<TopicQAResponse | null>(null);
  const [topicQAHistory, setTopicQAHistory] = useState<
    {
      id: string;
      question: string;
      answer: string;
      confusionType: string;
      conceptName: string;
      createdAt: number;
    }[]
  >([]);
  const [_topicConfusionEvents, setTopicConfusionEvents] = useState<
    ConfusionEvent[]
  >([]);
  const [lastConfusionEventId, setLastConfusionEventId] = useState<
    string | null
  >(null);
  const [isAskingTopicQuestion, setIsAskingTopicQuestion] = useState(false);
  const [pendingQuestion, setPendingQuestion] = useState("");
  const [highlightedText, setHighlightedText] = useState("");
  const [selectedTextForQuestion, setSelectedTextForQuestion] = useState("");
  const [activeVisualContext, setActiveVisualContext] =
    useState<VisualContextPayload | null>(null);
  const [activeVisualLabel, setActiveVisualLabel] = useState("");

  const [isLoadingStudyPath, setIsLoadingStudyPath] = useState(false);
  const [preloadingStatus, setPreloadingStatus] = useState("");
  const [autoAdvanceStatus, setAutoAdvanceStatus] = useState("");
  const [segmentAdaptationStatus, setSegmentAdaptationStatus] = useState("");
  const [isRegeneratingSegment, setIsRegeneratingSegment] = useState(false);
  const [flowCheckpoint, setFlowCheckpoint] = useState<FlowCheckpoint | null>(
    null,
  );
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [rightPanel, setRightPanel] = useState<RightPanel>(null);
  const [expandedIndexTopicId, setExpandedIndexTopicId] = useState<
    string | null | undefined
  >(undefined);
  const [isChatPanelOpen, setIsChatPanelOpen] = useState(false);
  const chatScrollRef = useRef<HTMLDivElement>(null);

  const [calibrationStep, setCalibrationStep] =
    useState<CalibrationStep>("lesson");
  const [startingMode, setStartingMode] = useState<StartingMode | null>(null);
  const [adaptationNote, setAdaptationNote] = useState<string | null>(null);
  const [selfReportLevel, setSelfReportLevel] = useState<number | null>(null);
  const [pacingMode, setPacingMode] = useState<PacingMode>(() =>
    getStoredPacingMode(studyPathId),
  );

  const [skipVerification, setSkipVerification] = useState<{
    stepIndex: number;
    answer: string;
    feedback: string | null;
  } | null>(null);
  const [insertedClarification, setInsertedClarification] = useState("");
  const [activeClarificationLabel, setActiveClarificationLabel] = useState("");
  const [pathWeakAreas, setPathWeakAreas] = useState<WeakAreaSummary | null>(
    null,
  );

  const stepStartedAtRef = useRef<number | null>(null);
  const stepVisitCountsRef = useRef<Record<string, number>>({});
  const stepNavigationIntentRef = useRef<
    "initial" | "next" | "previous" | "direct" | "auto"
  >("initial");
  const cardScrollContainerRef = useRef<HTMLDivElement | null>(null);
  const lessonCacheRef = useRef<Record<string, Lesson>>({});
  const touchStartRef = useRef<{ x: number; y: number } | null>(null);
  const lastTransitionAtRef = useRef<number | null>(null);
  const segmentRegenerationCooldownRef = useRef<{
    lastAt: number;
    lastStepIndex: number;
  }>({ lastAt: 0, lastStepIndex: -10 });
  const recentPracticeLevelsRef = useRef<string[]>([]);
  const strongStreakRef = useRef(0);
  const confusionSignalCountRef = useRef(0);

  const lessonJson = useMemo(() => {
    return (lesson?.lesson_json ?? {}) as LessonJson;
  }, [lesson]);
  const v2LessonJson = useMemo(() => {
    return isLessonV2(lesson?.lesson_json) ? lesson.lesson_json : null;
  }, [lesson]);
  const legacyV2ModelsById = useMemo(() => {
    const map = new Map<string, VisualModel>();
    for (const model of lessonJson.visual_models || []) {
      if (model?.id) {
        map.set(model.id, model);
      }
    }
    return map;
  }, [lessonJson.visual_models]);

  const selectedTopic = topics.find((topic) => topic.id === selectedTopicId);

  const groupedTopics = useMemo(() => {
    const groups: { unitTitle: string; topics: Topic[] }[] = [];
    const groupByUnitTitle = new Map<string, Topic[]>();

    topics.forEach((topic) => {
      const unitTitle = topic.unit_title || "Core Concepts";

      if (!groupByUnitTitle.has(unitTitle)) {
        groupByUnitTitle.set(unitTitle, []);
      }

      groupByUnitTitle.get(unitTitle)!.push(topic);
    });

    groupByUnitTitle.forEach((unitTopics, unitTitle) => {
      groups.push({ unitTitle, topics: unitTopics });
    });

    return groups;
  }, [topics]);

  const lessonSteps = useMemo<LearningStep[]>(() => {
    const cardSteps = buildLearningStepsFromCards({
      cards: lessonJson.lesson_cards,
      practiceQuestions: lessonJson.practice_questions,
      visuals: lessonJson.visual_plan,
    });

    if (cardSteps.length > 0) {
      return cardSteps.filter((step) =>
        shouldShowStepForStartingMode(startingMode, step),
      );
    }

    // A lesson that declares lesson_cards but produced no steps is a BROKEN
    // card generation, not a legacy-shaped lesson. Don't fall back to the old
    // intro/purpose/source-grounding scaffolding below — that masks the failure
    // and is exactly the misleading "Purpose & Context / Source Grounding" the
    // learner sees. Surface it as a regenerate prompt instead. (The backend now
    // marks such generations "failed", so this is a safety net for older rows.)
    if (Array.isArray(lessonJson.lesson_cards)) {
      return [
        {
          type: "text",
          title: "This lesson didn't generate correctly",
          content:
            "Something went wrong building this topic. Use Regenerate above to rebuild it.",
        },
      ];
    }

    const steps: LearningStep[] = [];

    const topicTitle = selectedTopic?.title || studyPath?.title || "this topic";
    const topicPurpose =
      selectedTopic?.purpose ||
      "This topic is part of the path because it supports the ideas and practice that come next.";

    steps.push({
      type: "purpose_context",
      title: "Purpose & Context",
      intro: lessonJson.intro || `You are learning ${topicTitle}.`,
      purpose: lessonJson.purpose || topicPurpose,
      context:
        lessonJson.context ||
        `This step fits into the path near ${
          selectedTopic?.unit_title || "the current unit"
        }. It builds on earlier ideas and prepares you for later topics that use ${topicTitle}.`,
      learningObjective:
        lessonJson.learning_objective ||
        `By the end, you should be able to explain and apply ${topicTitle}.`,
    });

    if (lessonJson.components?.length) {
      steps.push({
        type: "list",
        title: "Components / Definitions",
        items: lessonJson.components,
      });
    }

    if (lessonJson.process?.length) {
      steps.push({
        type: "list",
        title: "Process / Method",
        items: lessonJson.process,
        ordered: true,
      });
    }

    if (lessonJson.visual_plan?.length) {
      steps.push({
        type: "visuals",
        title: "Visuals",
        visuals: lessonJson.visual_plan,
      });
    }

    if (lessonJson.limitations) {
      if (Array.isArray(lessonJson.limitations)) {
        steps.push({
          type: "list",
          title: "Edge Cases / Common Mistakes",
          items: lessonJson.limitations,
        });
      } else {
        steps.push({
          type: "text",
          title: "Edge Cases / Common Mistakes",
          content: lessonJson.limitations,
        });
      }
    }

    if (lessonJson.worked_examples?.length) {
      steps.push({
        type: "worked_examples",
        title: "Worked Example",
        examples: lessonJson.worked_examples,
      });
    }

    if (lessonJson.edge_cases?.length) {
      steps.push({
        type: "list",
        title: "Edge Cases",
        items: lessonJson.edge_cases,
      });
    }

    const typedPracticeQuestions =
      lessonJson.practice_questions && lessonJson.practice_questions.length > 0
        ? lessonJson.practice_questions
        : (lessonJson.practice ?? []).map((question) => ({
            question_type: "short_answer",
            question_text: question,
          }));

    typedPracticeQuestions.forEach((question, index) => {
      steps.push({
        type: "practice",
        title: `Practice ${index + 1}`,
        question,
        questionIndex: index,
      });
    });

    if (lessonJson.key_takeaways?.length) {
      steps.push({
        type: "list",
        title: "Key Takeaways",
        items: lessonJson.key_takeaways,
      });
    }

    if (lessonJson.source_preview) {
      steps.push({
        type: "source_preview",
        title: "Source Preview",
        content: lessonJson.source_preview,
      });
    }

    if (lesson) {
      steps.push({ type: "source_grounding", title: "Source Grounding" });
    }

    return steps.filter((step) =>
      shouldShowStepForStartingMode(startingMode, step),
    );
  }, [lesson, lessonJson, selectedTopic, startingMode, studyPath?.title]);

  const safeCurrentStepIndex =
    lessonSteps.length > 0
      ? Math.min(currentStepIndex, lessonSteps.length - 1)
      : 0;
  const currentStep = lessonSteps[safeCurrentStepIndex];
  const nextStep = lessonSteps[safeCurrentStepIndex + 1];

  const currentFocusVisual = useMemo<VisualPlanItem | undefined>(() => {
    if (currentStep?.type === "flow_card") {
      if (shouldSuppressFocusVisual(currentStep.card)) {
        return undefined;
      }

      const codeVisual = codeVisualFromCard(currentStep.card);
      const workedExampleCodeVisual = workedExampleCodeVisualFromCard(currentStep.card);
      const stepVisual =
        currentStep.visual &&
        !shouldSuppressFocusVisual(currentStep.card, currentStep.visual) &&
        isRenderableVisual(currentStep.visual)
          ? currentStep.visual
          : undefined;
      const cardVisual =
        codeVisual ??
        stepVisual ??
        (currentStep.card
          ? resolveCardVisual(currentStep.card, lessonJson.visual_plan)
          : undefined);
      const compositeVisual = workedExampleCodeVisual
        ? codingWorkedExampleCompositeVisual(
            cardVisual && cardVisual !== codeVisual ? cardVisual : stepVisual,
            withCardSynchronizedCodeVisual(workedExampleCodeVisual, currentStep),
          )
        : cardVisual;

      if (compositeVisual && isRenderableVisual(compositeVisual)) {
        return withCardSynchronizedCodeVisual(
          withCardSynchronizedStepFlow(compositeVisual, currentStep),
          currentStep,
        );
      }
    }

    return undefined;
  }, [currentStep, lessonJson.visual_plan]);

  const currentV2FocusVisual = useMemo(() => {
    if (currentStep?.type !== "flow_card") return null;
    const ref = currentStep.card?.visual_v2_ref;
    if (!ref?.visual_model_id) return null;
    const model = legacyV2ModelsById.get(ref.visual_model_id);
    let frameIndex =
      typeof ref.frame_index === "number" && ref.frame_index >= 0
        ? ref.frame_index
        : 0;
    // Per-bullet frames: as each point reveals, advance the frame so the
    // highlighted line (and variables) match the bullet being read.
    const perPoint = ref.frame_index_per_point;
    if (Array.isArray(perPoint) && perPoint.length > 0) {
      const revealed = Array.isArray(currentStep.bullets) ? currentStep.bullets.length : 0;
      const idx = Math.min(perPoint.length - 1, Math.max(0, revealed - 1));
      const candidate = perPoint[idx];
      if (typeof candidate === "number" && candidate >= 0) frameIndex = candidate;
    }
    // Diagnostic: a flow_card that carries a visual_v2_ref but resolves to no
    // renderable model/frame is why a worked-example visual goes blank. Surface
    // the exact failing check rather than silently returning null.
    if (!model) {
      console.warn(
        `[v2-visual] card "${currentStep.card?.id}" references model ` +
          `"${ref.visual_model_id}" which is NOT in visual_models ` +
          `(${legacyV2ModelsById.size} models loaded: ` +
          `${Array.from(legacyV2ModelsById.keys()).join(", ")})`,
      );
      return null;
    }
    if (!model.frames?.[frameIndex]) {
      console.warn(
        `[v2-visual] card "${currentStep.card?.id}" wants frame ${frameIndex} ` +
          `of model "${ref.visual_model_id}" but it has ` +
          `${model.frames?.length ?? 0} frames`,
      );
      return null;
    }
    return { model, frameIndex };
  }, [currentStep, legacyV2ModelsById]);

  // Supporting diagram for code-lens worked examples (e.g. the array + pointer
  // view that accompanies the executing code), resolved like the focus visual.
  const currentV2DiagramVisual = useMemo(() => {
    if (currentStep?.type !== "flow_card") return null;
    const ref = currentStep.card?.diagram_v2_ref;
    if (!ref?.visual_model_id) return null;
    const model = legacyV2ModelsById.get(ref.visual_model_id);
    const frameIndex =
      typeof ref.frame_index === "number" && ref.frame_index >= 0 ? ref.frame_index : 0;
    if (!model || !model.frames?.[frameIndex]) return null;
    return { model, frameIndex };
  }, [currentStep, legacyV2ModelsById]);

  // For coding worked examples: the implementation code + the line(s) active at
  // this step, so the learner can toggle the diagram for the running code.
  const workedExampleCode = useMemo(() => {
    if (currentStep?.type !== "flow_card") return null;
    const card = currentStep.card;
    if (card?.blueprint_key !== "worked_example") return null;
    const code = card?.code_snippet?.trim();
    if (!code) return null;

    // The "active" line for an output-order traversal step is where the current
    // node's value is collected (the visit). Prefer an explicit per-step
    // highlight if the card carries one, else locate the visit line.
    const lines = code.split("\n");
    // Prefer the per-reveal-step highlight: a coding worked example is split into
    // one reveal step per bullet (the isCodingTrace branch), each carrying that
    // bullet's code line, so the highlight advances as the learner reveals
    // bullets. The state bullet intentionally carries no line (no highlight).
    const perStep = card.highlight_lines_per_step;
    const isCodingTrace = Array.isArray(perStep) && perStep.length > 0;
    let highlight: [number, number] | undefined = currentStep.highlightLines;
    if (!highlight && !isCodingTrace) {
      // Legacy fallback (non per-bullet cards): locate the visit line.
      if (Array.isArray(perStep) && perStep.length === 1 && Array.isArray(perStep[0])) {
        highlight = perStep[0] as [number, number];
      } else {
        const idx = lines.findIndex(
          (line) => /\.append\s*\(/.test(line) || /\[\s*[A-Za-z_]\w*\.val\b/.test(line),
        );
        if (idx >= 0) highlight = [idx + 1, idx + 1];
      }
    }
    return {
      code,
      language: card.code_language || "python",
      highlight,
    };
  }, [currentStep]);

  const currentVisualFocus: VisualFocusState | null = useMemo(() => {
    if (currentStep?.type !== "flow_card") return null;
    const baseFocus = currentStep.card?.visual_focus ?? null;
    const override = currentStep.activeStepOverride;
    if (typeof override === "number" && override >= 0) {
      return { ...(baseFocus ?? {}), active_step: override } as VisualFocusState;
    }
    return baseFocus;
  }, [currentStep]);
  const isLastLessonStep =
    lessonSteps.length > 0 && safeCurrentStepIndex >= lessonSteps.length - 1;
  const continueButtonLabel = getContinueLabel({
    currentStep,
    nextStep,
    isLastStep: isLastLessonStep,
  });
  const lessonStepProgress =
    lessonSteps.length > 0
      ? Math.round(((safeCurrentStepIndex + 1) / lessonSteps.length) * 100)
      : 0;
  const firstPracticeStepIndex = useMemo(() => {
    return Math.max(
      lessonSteps.findIndex((step) => step.type === "practice"),
      0,
    );
  }, [lessonSteps]);
  const currentTopicIndex = selectedTopic
    ? topics.findIndex((topic) => topic.id === selectedTopic.id)
    : -1;
  const upcomingTopic =
    currentTopicIndex >= 0 ? topics[currentTopicIndex + 1] : undefined;
  const isTopicLessonReady = useCallback(
    (topicId: string) =>
      Boolean(lessonCacheRef.current[topicId]) ||
      topicLessonStatuses[topicId] === "ready" ||
      (topicId === selectedTopicId &&
        lesson?.topic_id === topicId &&
        lesson.generation_status === "ready"),
    [lesson, selectedTopicId, topicLessonStatuses],
  );
  const nextTopicStatus = upcomingTopic
    ? topicLessonStatuses[upcomingTopic.id]
    : "";
  const hasKnownBlockingNextTopicStatus = Boolean(
    nextTopicStatus &&
      nextTopicStatus !== "ready" &&
      nextTopicStatus !== "complete",
  );
  const isNextTopicKnownButNotReady = Boolean(
    upcomingTopic &&
      hasKnownBlockingNextTopicStatus &&
      !isTopicLessonReady(upcomingTopic.id),
  );
  const isWaitingForNextTopicRecord =
    !upcomingTopic &&
    isLastLessonStep &&
    Boolean(selectedTopic) &&
    (isGeneratingTopics ||
      isGeneratingFullPath ||
      preloadingStatus.trim().length > 0);
  const shouldBlockFinishTopic =
    !flowCheckpoint &&
    isLastLessonStep &&
    Boolean(selectedTopic) &&
    (isNextTopicKnownButNotReady || isWaitingForNextTopicRecord);
  const finishTopicDisabledReason = isNextTopicKnownButNotReady
    ? nextTopicStatus === "failed"
      ? "The next topic failed to generate. Use the index to review generated topics or regenerate from the study path controls."
      : "The next topic is still preparing. You can review this topic or already generated topics from the index while it finishes."
    : isWaitingForNextTopicRecord
      ? "The next topic is still being added. You can review this topic or already generated topics from the index while it finishes."
      : "";
  const checkpointCanContinue = flowCheckpoint
    ? flowCheckpoint.type === "path_complete" ||
      Boolean(
        flowCheckpoint.nextTopic &&
          isTopicLessonReady(flowCheckpoint.nextTopic.id),
      )
    : false;
  const checkpointContinueDisabledReason =
    flowCheckpoint?.type === "topic_complete" && !checkpointCanContinue
      ? "The next topic is still preparing. Use Back to return to the last card, or open the index to revisit any generated topic."
      : "";
  const currentRunEstimatedSeconds = lessonSteps.reduce(
    (total, step) => total + (step.estimatedSeconds ?? 45),
    0,
  );
  const currentRunEstimatedMinutes = Math.max(
    1,
    Math.round(currentRunEstimatedSeconds / 60),
  );
  const pacingInstruction = getPacingInstruction(pacingMode);
  const isPageBusy =
    isGeneratingTopics ||
    isGeneratingLesson ||
    isGeneratingFullPath ||
    isRegeneratingTopic ||
    isRegeneratingPath ||
    isAskingTopicQuestion ||
    isGeneratingReviewQuestion ||
    isSubmittingReviewAnswer ||
    isGeneratingTransferChallenge ||
    isLoadingStudyPath ||
    isRegeneratingSegment ||
    practiceLoadingIndex !== null ||
    targetedRepairLoadingIndex !== null;

  useEffect(() => {
    window.localStorage.setItem(`azalea.pacing.${studyPathId}`, pacingMode);
  }, [pacingMode, studyPathId]);

  useEffect(() => {
    lastTransitionAtRef.current = Date.now();
  }, [studyPathId]);

  useEffect(() => {
    if (
      calibrationStep !== "lesson" ||
      !selectedTopic ||
      !currentStep ||
      lessonSteps.length === 0
    ) {
      return;
    }

    let phase: FlowResumePhase = "lesson";

    if (reviewQuestion) {
      phase = "review";
    } else if (isChatPanelOpen || topicQAResponse) {
      phase = "qa";
    } else if (currentStep.type === "practice") {
      phase = "practice";
    }

    saveFlowResume({
      studyPathId,
      topicId: selectedTopic.id,
      topicTitle: selectedTopic.title,
      cardIndex: safeCurrentStepIndex,
      cardTitle: currentStep.title,
      totalCards: lessonSteps.length,
      phase,
    });
  }, [
    calibrationStep,
    currentStep,
    isChatPanelOpen,
    lessonSteps.length,
    reviewQuestion,
    safeCurrentStepIndex,
    selectedTopic,
    studyPathId,
    topicQAResponse,
  ]);

  useEffect(() => {
    cardScrollContainerRef.current?.scrollTo({ top: 0, behavior: "smooth" });
  }, [safeCurrentStepIndex, selectedTopicId]);

  useEffect(() => {
    async function preloadNextTopicLesson() {
      if (
        !upcomingTopic ||
        lessonSteps.length === 0 ||
        safeCurrentStepIndex < lessonSteps.length - 2 ||
        lessonCacheRef.current[upcomingTopic.id]
      ) {
        return;
      }

      try {
        setPreloadingStatus(
          `Preparing the next concept: ${upcomingTopic.title}`,
        );
        const nextLesson = await getTopicLesson(upcomingTopic.id);
        if (nextLesson.generation_status !== "ready") {
          setTopicLessonStatuses((prev) => ({
            ...prev,
            [upcomingTopic.id]: nextLesson.generation_status || "generating",
          }));
          return;
        }
        lessonCacheRef.current[upcomingTopic.id] = nextLesson;
        setTopicLessonStatuses((prev) => ({
          ...prev,
          [upcomingTopic.id]: "ready",
        }));
      } catch (err) {
        try {
          const statusResult = await getTopicLessonStatus(upcomingTopic.id);
          setTopicLessonStatuses((prev) => ({
            ...prev,
            [upcomingTopic.id]: statusResult.generation_status,
          }));
          if (statusResult.generation_status !== "not_started") {
            return;
          }
        } catch {
          // Fall through to the one allowed preload generation attempt.
        }
        try {
          const generatedLesson = await generateTopicLesson(upcomingTopic.id);
          if (generatedLesson.generation_status === "ready") {
            lessonCacheRef.current[upcomingTopic.id] = generatedLesson;
          }
          setTopicLessonStatuses((prev) => ({
            ...prev,
            [upcomingTopic.id]: generatedLesson.generation_status || "generating",
          }));
        } catch (generationErr) {
          console.error("Failed to preload next topic lesson:", generationErr, err);
        }
      } finally {
        setPreloadingStatus("");
      }
    }

    void preloadNextTopicLesson();
  }, [lessonSteps.length, safeCurrentStepIndex, upcomingTopic]);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const isTyping =
        target?.tagName === "INPUT" ||
        target?.tagName === "TEXTAREA" ||
        target?.isContentEditable;

      if (
        isTyping ||
        calibrationStep !== "lesson" ||
        isPageBusy ||
        Boolean(reviewQuestion || transferChallenge)
      ) {
        return;
      }

      if (event.key === "ArrowRight" || event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        void goToNextStep();
      }

      if (event.key === "ArrowLeft") {
        event.preventDefault();
        goToPreviousStep();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
    // Navigation handlers are function declarations below; these state values
    // are the parts that should refresh the keyboard listener.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    calibrationStep,
    isPageBusy,
    reviewQuestion,
    safeCurrentStepIndex,
    transferChallenge,
  ]);

  useEffect(() => {
    async function fetchStudyPathData() {
      try {
        setIsLoadingStudyPath(true);
        const [pathData, topicData] = await Promise.all([
          getStudyPath(studyPathId),
          getStudyPathTopics(studyPathId),
        ]);

        setStudyPath(pathData);
        setTopics(topicData);

        if (topicData.length > 0) {
          const matchingTopic = topicIdFromUrl
            ? topicData.find((topic) => topic.id === topicIdFromUrl)
            : null;

          setSelectedTopicId(
            matchingTopic ? matchingTopic.id : topicData[0].id,
          );
        }
      } catch (err) {
        console.error(err);
        setStatus("Failed to load study path.");
      } finally {
        setIsLoadingStudyPath(false);
      }
    }

    if (!isCheckingAuth && studyPathId) {
      fetchStudyPathData();
    }
  }, [studyPathId, topicIdFromUrl, isCheckingAuth]);

  useEffect(() => {
    async function loadMemorySummary() {
      try {
        const result = await getStudyPathMemorySummary(studyPathId);
        setMemorySummary(result);
        const weakAreas = await getStudyPathWeakAreas(studyPathId);
        setPathWeakAreas(weakAreas);
      } catch (err) {
        console.error("Failed to load learner memory summary:", err);
        setMemorySummary(null);
        setPathWeakAreas(null);
      }
    }

    if (!isCheckingAuth && studyPathId) {
      void loadMemorySummary();
    }
  }, [studyPathId, isCheckingAuth]);

  useEffect(() => {
    async function fetchLesson() {
      if (!selectedTopicId) {
        setLesson(null);
        return;
      }

      try {
        setPracticeAnswers({});
        setPracticeHints({});
        setPracticeFeedback({});
        setTargetedRepairs({});
        setTargetedRepairAnswers({});
        setTargetedRepairConfidence({});
        setTargetedRepairFeedback({});
        setTargetedRepairLoadingIndex(null);
        setReviewQuestion(null);
        setReviewAnswer("");
        setReviewConfidence(3);
        setReviewFeedback(null);
        setIsGeneratingReviewQuestion(false);
        setIsSubmittingReviewAnswer(false);
        setTransferChallenge(null);
        setTransferAnswer("");
        setTransferConfidence(3);
        setTransferFeedback(null);
        setIsGeneratingTransferChallenge(false);
        setIsSubmittingTransferChallenge(false);
        setPracticeError(null);
        setHintUsedByQuestion({});
        setPracticeConfidence({});
        setPracticeLoadingIndex(null);
        setTopicQAResponse(null);
        setTopicQuestion("");
        setHighlightedText("");
        setSelectedTextForQuestion("");
        setAutoAdvanceStatus("");
        setSegmentAdaptationStatus("");
        setIsRegeneratingSegment(false);
        setFlowCheckpoint(null);
        setSkipVerification(null);
        setInsertedClarification("");
        setActiveClarificationLabel("");
        setCurrentStepIndex(0);
        setCalibrationStep("lesson");
        setStartingMode(null);
        setAdaptationNote(null);
        setSelfReportLevel(null);
        stepStartedAtRef.current = null;
        stepVisitCountsRef.current = {};
        stepNavigationIntentRef.current = "initial";
        recentPracticeLevelsRef.current = [];
        strongStreakRef.current = 0;
        confusionSignalCountRef.current = 0;

        const cachedLesson = lessonCacheRef.current[selectedTopicId];

        if (cachedLesson) {
          setLesson(cachedLesson);
          setTopicLessonStatuses((prev) => ({
            ...prev,
            [selectedTopicId]: "ready",
          }));
          setStatus("");
        }

        const topicId = selectedTopicId;
        const lessonData = await getTopicLesson(topicId);

        if (lessonData.generation_status !== "ready") {
          const pendingStatus = lessonData.generation_status || "generating";
          setLesson(null);
          setTopicLessonStatuses((prev) => ({
            ...prev,
            [topicId]: pendingStatus,
          }));
          setStatus(
            pendingStatus === "failed"
              ? "This topic failed to generate. Use Regenerate Topic to try again."
              : "This topic is still preparing. You can review generated topics from the index while it finishes.",
          );
          return;
        }

        lessonCacheRef.current[topicId] = lessonData;
        setTopicLessonStatuses((prev) => ({
          ...prev,
          [topicId]: "ready",
        }));
        setLesson(lessonData);
        if (resumeFromUrl) {
          setCalibrationStep("lesson");
          setCurrentStepIndex(
            Number.isFinite(cardIndexFromUrl)
              ? Math.max(0, Math.floor(cardIndexFromUrl))
              : 0,
          );
        }
        setStatus("");
      } catch (err) {
        console.error(err);
        const topicId = selectedTopicId;

        try {
          const statusResult = await getTopicLessonStatus(topicId);
          setTopicLessonStatuses((prev) => ({
            ...prev,
            [topicId]: statusResult.generation_status,
          }));
          if (
            statusResult.generation_status === "generating" ||
            statusResult.generation_status === "pending"
          ) {
            setLesson(null);
            setStatus(
              "This topic is still preparing. You can review generated topics from the index while it finishes.",
            );
            return;
          }
          if (statusResult.generation_status === "failed") {
            setLesson(null);
            setStatus("This topic failed to generate. Use Regenerate Topic to try again.");
            return;
          }
          const firstTopicId = topics[0]?.id;
          if (
            statusResult.generation_status === "not_started" &&
            firstTopicId &&
            topicId !== firstTopicId
          ) {
            setLesson(null);
            setStatus(
              "This topic is not generated yet. Finish the current ready topic or choose an already generated topic from the index.",
            );
            return;
          }

          setIsGeneratingLesson(true);
          setStatus("Preparing this topic. This can take a moment...");
          // Try streaming so early cards preview while the rest generate. On any
          // failure / busy / error, fall back to the blocking generate so this
          // is purely additive and never blocks a lesson from being produced.
          let generatedLesson: Lesson | null = null;
          try {
            setStreamingPreviewCards([]);
            let streamCompleted = false;
            let streamUnavailable = false;
            await streamTopicLesson(topicId, (event) => {
              if (event.type === "card") {
                const card = event.card as { title?: unknown; points?: unknown };
                setStreamingPreviewCards((prev) => [
                  ...prev,
                  {
                    title: String(card.title ?? ""),
                    points: Array.isArray(card.points)
                      ? (card.points as unknown[]).map((p) => String(p)).filter(Boolean)
                      : [],
                  },
                ]);
              } else if (event.type === "complete") {
                streamCompleted = true;
              } else if (event.type === "busy" || event.type === "error") {
                streamUnavailable = true;
              }
            });
            if (streamCompleted && !streamUnavailable) {
              generatedLesson = await getTopicLesson(topicId);
            }
          } catch (streamErr) {
            console.error("lesson stream failed; falling back to blocking generate", streamErr);
          } finally {
            setStreamingPreviewCards([]);
          }
          if (!generatedLesson) {
            generatedLesson = await generateTopicLesson(topicId);
          }
          if (generatedLesson.generation_status === "ready") {
            lessonCacheRef.current[topicId] = generatedLesson;
            setLesson(generatedLesson);
            setStatus("Lesson ready.");
          } else {
            setLesson(null);
            setStatus(
              "This topic is still preparing. You can review generated topics from the index while it finishes.",
            );
          }
          setTopicLessonStatuses((prev) => ({
            ...prev,
            [topicId]: generatedLesson.generation_status || "generating",
          }));

          if (generatedLesson.generation_status === "ready" && resumeFromUrl) {
            setCalibrationStep("lesson");
            setCurrentStepIndex(
              Number.isFinite(cardIndexFromUrl)
                ? Math.max(0, Math.floor(cardIndexFromUrl))
                : 0,
            );
          }
        } catch (generationErr) {
          console.error(generationErr);
          setLesson(null);
          setStatus("No lesson found for this topic yet.");
        } finally {
          setIsGeneratingLesson(false);
        }
      }
    }

    if (!isCheckingAuth) {
      fetchLesson();
    }
  }, [cardIndexFromUrl, isCheckingAuth, resumeFromUrl, selectedTopicId, topics]);

  // Poll lesson-generation status for any topic still in flight, so the index
  // reflects background completions WITHOUT a page refresh. Keeps re-checking
  // every few seconds while any topic is non-terminal, then stops. Reads the
  // current statuses from a ref so updating them doesn't restart the poller.
  useEffect(() => {
    if (topics.length === 0 || isCheckingAuth) {
      return;
    }

    const TERMINAL = new Set(["ready", "failed"]);
    let canceled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function pollOnce(): Promise<boolean> {
      const statuses = topicLessonStatusesRef.current;
      const inFlight = topics.filter((topic) => {
        if (lessonCacheRef.current[topic.id]) return false;
        const status = statuses[topic.id];
        return !status || !TERMINAL.has(status);
      });
      if (inFlight.length === 0) return false;

      const entries = await Promise.all(
        inFlight.map(async (topic) => {
          try {
            const result = await getTopicLessonStatus(topic.id);
            return [topic.id, result.generation_status] as const;
          } catch {
            return [topic.id, statuses[topic.id] || "unknown"] as const;
          }
        }),
      );
      if (canceled) return false;
      setTopicLessonStatuses((prev) => ({
        ...prev,
        ...Object.fromEntries(entries),
      }));
      // Keep polling while anything is still generating/pending.
      return entries.some(([, status]) => !TERMINAL.has(status));
    }

    async function loop() {
      const keepGoing = await pollOnce();
      if (keepGoing && !canceled) {
        timer = setTimeout(loop, 4000);
      }
    }

    void loop();

    return () => {
      canceled = true;
      if (timer) clearTimeout(timer);
    };
  }, [isCheckingAuth, topics]);

  useEffect(() => {
    async function loadConfusionEvents() {
      if (!selectedTopicId || isCheckingAuth) {
        setTopicConfusionEvents([]);
        setTopicQAHistory([]);
        setLastConfusionEventId(null);
        return;
      }

      try {
        const events = await getTopicConfusionEvents(selectedTopicId);
        setTopicConfusionEvents(events);
        setTopicQAHistory(
          events
            .slice(0, 12)
            .reverse()
            .map((event) => ({
              id: event.id,
              question: event.user_question,
              answer: event.answer_generated,
              confusionType: event.confusion_type,
              conceptName: event.concept_name,
              createdAt: Date.parse(event.created_at) || Date.now(),
            })),
        );
        setLastConfusionEventId(events[0]?.id ?? null);
      } catch (err) {
        console.error(err);
      }
    }

    void loadConfusionEvents();
  }, [isCheckingAuth, selectedTopicId]);

  useEffect(() => {
    if ((!status && !practiceError) || isPageBusy) return;

    const timer = window.setTimeout(() => {
      setStatus("");
      setPracticeError(null);
    }, 4500);

    return () => window.clearTimeout(timer);
  }, [isPageBusy, practiceError, status]);

  useEffect(() => {
    if ((!segmentAdaptationStatus && !autoAdvanceStatus) || isPageBusy) return;

    const timer = window.setTimeout(() => {
      setSegmentAdaptationStatus("");
      setAutoAdvanceStatus("");
    }, 4200);

    return () => window.clearTimeout(timer);
  }, [autoAdvanceStatus, isPageBusy, segmentAdaptationStatus]);

  useEffect(() => {
    if (calibrationStep !== "lesson" || !selectedTopic || !currentStep) {
      stepStartedAtRef.current = null;
      return;
    }

    const stepKey = `${selectedTopic.id}:${safeCurrentStepIndex}:${currentStep.title}`;
    const visitCount = (stepVisitCountsRef.current[stepKey] ?? 0) + 1;
    const wasRevisit = visitCount > 1;
    const navigationIntent = stepNavigationIntentRef.current;

    stepVisitCountsRef.current[stepKey] = visitCount;
    stepStartedAtRef.current = Date.now();

    if (wasRevisit) {
      void submitLearnerSignal({
        topic_id: selectedTopic.id,
        concept_name:
          currentStep.title || selectedTopic.title || "overall_topic",
        signal_type: "reread",
        summary: `Revisited learning step: ${currentStep.title}`,
        metadata: {
          step_index: safeCurrentStepIndex,
          step_title: currentStep.title,
          step_type: currentStep.type,
          visit_count: visitCount,
          navigation_intent: navigationIntent,
          starting_mode: startingMode,
          behavioral_labels: ["step_revisit", "possible_fragile_attention"],
        },
      });
    }

    return () => {
      const startedAt = stepStartedAtRef.current;
      if (!startedAt) return;

      const timeSeconds = Math.max(
        1,
        Math.round((Date.now() - startedAt) / 1000),
      );

      if (timeSeconds < 3) return;

      const behavioralLabels = getBehavioralLabelsForStep({
        timeSeconds,
        stepType: currentStep.type,
        wasRevisit,
        visitCount,
        navigationIntent,
      });

      recordFlowMetric(studyPathId, (metrics) => {
        metrics.cardsCompleted += 1;
        metrics.dropOffCardType =
          currentStep.cardType ||
          (currentStep.type === "practice" ? "quick_practice" : currentStep.type);
      });

      if (
        timeSeconds > 70 &&
        pacingMode === "fast" &&
        currentStep.type !== "practice"
      ) {
        setPacingMode("balanced");
      }

      void submitLearnerSignal({
        topic_id: selectedTopic.id,
        concept_name:
          currentStep.title || selectedTopic.title || "overall_topic",
        signal_type: "time_on_slide",
        time_seconds: timeSeconds,
        summary: `Spent ${timeSeconds} seconds on learning step: ${currentStep.title}`,
        metadata: {
          step_index: safeCurrentStepIndex,
          step_title: currentStep.title,
          step_type: currentStep.type,
          visit_count: visitCount,
          was_revisit: wasRevisit,
          navigation_intent: navigationIntent,
          starting_mode: startingMode,
          progress_percent: lessonStepProgress,
          behavioral_labels: behavioralLabels,
        },
      });
    };
  }, [
    calibrationStep,
    currentStep,
    lessonStepProgress,
    pacingMode,
    safeCurrentStepIndex,
    selectedTopic,
    startingMode,
    studyPathId,
  ]);

  const buildLessonContext = useCallback(() => {
    const parts = [
      lessonJson.intro,
      lessonJson.purpose,
      lessonJson.context,
      lessonJson.learning_objective,
      Array.isArray(lessonJson.components)
        ? lessonJson.components.join("\n")
        : "",
      Array.isArray(lessonJson.process) ? lessonJson.process.join("\n") : "",
      Array.isArray(lessonJson.limitations)
        ? lessonJson.limitations.join("\n")
        : (lessonJson.limitations ?? ""),
      Array.isArray(lessonJson.edge_cases)
        ? lessonJson.edge_cases.join("\n")
        : "",
      Array.isArray(lessonJson.key_takeaways)
        ? lessonJson.key_takeaways.join("\n")
        : "",
      Array.isArray(lessonJson.practice_questions)
        ? lessonJson.practice_questions
            .map((practiceQuestion) =>
              [
                `Practice type: ${practiceQuestion.question_type ?? "short_answer"}`,
                `Question: ${practiceQuestion.question_text ?? ""}`,
                practiceQuestion.correct_answer
                  ? `Private answer key: ${practiceQuestion.correct_answer}`
                  : "",
                practiceQuestion.explanation
                  ? `Private explanation: ${practiceQuestion.explanation}`
                  : "",
              ]
                .filter(Boolean)
                .join("\n"),
            )
            .join("\n\n")
        : "",
      lessonJson.source_preview,
      lesson?.source_summary,
    ];

    return parts.filter(Boolean).join("\n\n");
  }, [lesson?.source_summary, lessonJson]);

  useEffect(() => {
    async function startReviewMode() {
      if (
        isCheckingAuth ||
        modeFromUrl !== "review" ||
        !selectedTopic ||
        !reviewConceptFromUrl ||
        !lesson
      ) {
        return;
      }

      try {
        setIsGeneratingReviewQuestion(true);
        setStatus("Preparing a quick review check...");

        const result = await generateReviewQuestion(selectedTopic.id, {
          concept_name: reviewConceptFromUrl,
          lesson_context: buildLessonContext(),
          review_reason: "Review due from learner state.",
        });

        setReviewQuestion(result);
        setReviewAnswer("");
        setReviewConfidence(3);
        setReviewFeedback(null);
        setCalibrationStep("lesson");
        setStartingMode("transfer_practice");
        stepNavigationIntentRef.current = "direct";
        setAdaptationNote(
          `Azalea is checking ${result.target_concept} again because it was due for review.`,
        );
        setCurrentStepIndex(firstPracticeStepIndex);
        setStatus("Review check ready.");
      } catch (err) {
        console.error(err);
        setStatus(
          getReadableErrorMessage(err, "Failed to prepare review check."),
        );
      } finally {
        setIsGeneratingReviewQuestion(false);
      }
    }

    void startReviewMode();
  }, [
    isCheckingAuth,
    modeFromUrl,
    selectedTopic,
    reviewConceptFromUrl,
    lesson,
    firstPracticeStepIndex,
    buildLessonContext,
  ]);

  useEffect(() => {
    async function startTransferChallengeMode() {
      if (
        isCheckingAuth ||
        modeFromUrl !== "practice" ||
        !selectedTopic ||
        !lesson
      ) {
        return;
      }

      try {
        setIsGeneratingTransferChallenge(true);
        setStatus("Preparing a transfer challenge...");

        const conceptName =
          reviewConceptFromUrl || selectedTopic.title || "overall_topic";

        const result = await generateTransferChallenge(selectedTopic.id, {
          concept_name: conceptName,
          lesson_context: buildLessonContext(),
          prior_context: memorySummary?.recommended_lesson_guidance ?? null,
        });

        setTransferChallenge(result);
        setTransferAnswer("");
        setTransferConfidence(3);
        setTransferFeedback(null);
        setCalibrationStep("lesson");
        setStartingMode("transfer_practice");
        stepNavigationIntentRef.current = "direct";
        setAdaptationNote(
          "Azalea is checking whether this concept transfers to a new situation.",
        );
        setCurrentStepIndex(firstPracticeStepIndex);
        setStatus("Transfer challenge ready.");
      } catch (err) {
        console.error(err);
        setStatus(
          getReadableErrorMessage(err, "Failed to prepare transfer challenge."),
        );
      } finally {
        setIsGeneratingTransferChallenge(false);
      }
    }

    void startTransferChallengeMode();
  }, [
    isCheckingAuth,
    modeFromUrl,
    selectedTopic,
    lesson,
    reviewConceptFromUrl,
    memorySummary,
    firstPracticeStepIndex,
    buildLessonContext,
  ]);

  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTo({
        top: chatScrollRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [topicQAHistory, pendingQuestion, isAskingTopicQuestion]);

  function resetPracticeState() {
    setPracticeAnswers({});
    setPracticeHints({});
    setPracticeFeedback({});
    setTargetedRepairs({});
    setTargetedRepairAnswers({});
    setTargetedRepairConfidence({});
    setTargetedRepairFeedback({});
    setTargetedRepairLoadingIndex(null);
    setReviewQuestion(null);
    setReviewAnswer("");
    setReviewConfidence(3);
    setReviewFeedback(null);
    setIsGeneratingReviewQuestion(false);
    setIsSubmittingReviewAnswer(false);
    setTransferChallenge(null);
    setTransferAnswer("");
    setTransferConfidence(3);
    setTransferFeedback(null);
    setIsGeneratingTransferChallenge(false);
    setIsSubmittingTransferChallenge(false);
    setPracticeError(null);
    setHintUsedByQuestion({});
    setPracticeConfidence({});
    setPracticeLoadingIndex(null);
  }

  function getReadableErrorMessage(err: unknown, fallback: string) {
    if (err instanceof Error && err.message) {
      try {
        const parsed = JSON.parse(err.message) as {
          detail?: string | { msg?: string }[];
        };

        if (typeof parsed.detail === "string") {
          return parsed.detail;
        }

        if (Array.isArray(parsed.detail)) {
          return parsed.detail
            .map((item: { msg?: string }) => item.msg || JSON.stringify(item))
            .join(", ");
        }

        return err.message;
      } catch {
        return err.message;
      }
    }

    return fallback;
  }

  function handleLessonTextSelection() {
    if (calibrationStep !== "lesson") return;

    const selection = window.getSelection();
    const selectedText = selection?.toString().trim() ?? "";

    if (selectedText.length > 0) {
      setActiveVisualContext(null);
      setActiveVisualLabel("");
      setHighlightedText(selectedText);
      setSelectedTextForQuestion(selectedText);
      setIsChatPanelOpen(true);
    }
  }

  function handleLegacyV2VisualClick(
    element: SelectableElement,
    model: VisualModel,
    frame: VisualFrame,
  ) {
    const payload: VisualContextPayload = {
      visual_model_id: model.id,
      frame_index: frame.index,
      element,
      surrounding_state: frame.state,
      base_type: model.base_type,
      mode: model.mode,
      formatted_context: "",
    };
    const label = element.semantic_label || element.aria_label || element.element_id;
    setActiveVisualContext(payload);
    setActiveVisualLabel(label);
    setHighlightedText(label);
    setSelectedTextForQuestion("");
    setTopicQuestion(`Explain ${label} in this visual.`);
    setIsChatPanelOpen(true);
  }

  function getAdaptationNoteForStartingMode(mode: StartingMode | null) {
    if (mode === "full_teach") {
      return "Azalea will start from the foundation and avoid assuming prior knowledge.";
    }

    if (mode === "compressed_refresher") {
      return "Azalea will start with a compressed refresher and repair gaps only where needed.";
    }

    if (mode === "nuance_first") {
      return "Azalea will skip most basics and focus on nuance, mistakes, and edge cases.";
    }

    if (mode === "edge_cases") {
      return "Azalea will focus on tricky cases, common mistakes, and misconception checks.";
    }

    if (mode === "transfer_practice") {
      return "Azalea will move quickly into application and transfer practice.";
    }

    return "Azalea will adjust the starting point for this topic.";
  }

  function getBehavioralLabelsForStep({
    timeSeconds,
    stepType,
    wasRevisit,
    visitCount,
    navigationIntent,
  }: {
    timeSeconds: number;
    stepType: LearningStep["type"];
    wasRevisit: boolean;
    visitCount: number;
    navigationIntent: "initial" | "next" | "previous" | "direct" | "auto";
  }) {
    const labels: string[] = [];
    const isExplanationStep = [
      "text",
      "list",
      "visuals",
      "worked_examples",
      "source_preview",
    ].includes(stepType);

    if (timeSeconds <= 8 && isExplanationStep && navigationIntent === "next") {
      labels.push("fast_explanation_skip");
    }

    if (timeSeconds >= 90 && isExplanationStep) {
      labels.push("long_explanation_dwell");
    }

    if (timeSeconds >= 120 && stepType === "practice") {
      labels.push("slow_practice_attempt");
    }

    if (wasRevisit || visitCount > 1 || navigationIntent === "previous") {
      labels.push("revisit_or_reread");
    }

    if (timeSeconds <= 10 && stepType === "practice") {
      labels.push("fast_practice_attempt");
    }

    if (labels.length === 0) {
      labels.push("normal_progression");
    }

    return labels;
  }

  function beginLessonWithMode(mode: StartingMode) {
    setStartingMode(mode);
    setAdaptationNote(getAdaptationNoteForStartingMode(mode));
    setCalibrationStep("lesson");

    if (mode === "transfer_practice") {
      stepNavigationIntentRef.current = "direct";
      setCurrentStepIndex(firstPracticeStepIndex);
    } else {
      stepNavigationIntentRef.current = "initial";
      setCurrentStepIndex(0);
    }
  }

  function mapPracticeResultToLearnerSignal(result: PracticeSubmitResponse) {
    if (result.performance_level === "strong") {
      return {
        correctness: 1.0,
        reasoning_quality: 0.9,
      };
    }

    if (result.performance_level === "fragile") {
      return {
        correctness: result.is_correct ? 0.75 : 0.55,
        reasoning_quality: 0.55,
      };
    }

    if (result.performance_level === "minor_mistake") {
      return {
        correctness: result.is_correct ? 0.65 : 0.5,
        reasoning_quality: 0.45,
      };
    }

    return {
      correctness: result.is_correct ? 0.45 : 0.2,
      reasoning_quality: 0.2,
    };
  }

  function getPracticeConceptName(question: LessonPracticeQuestion) {
    return (
      question.concept_tested ||
      question.skill_target ||
      question.topic ||
      selectedTopic?.title ||
      "overall_topic"
    );
  }

  async function logStudySession(
    activityType: StudySessionActivityType,
    minutesSpent = 5,
  ) {
    if (!studyPathId) return;

    try {
      await createStudySession({
        study_path_id: studyPathId,
        topic_id: selectedTopic?.id ?? null,
        minutes_spent: minutesSpent,
        activity_type: activityType,
      });
    } catch (err) {
      console.error("Failed to log study session:", err);
    }
  }

  async function refreshStudyPathAndTopics() {
    const [updatedStudyPath, updatedTopics] = await Promise.all([
      getStudyPath(studyPathId),
      getStudyPathTopics(studyPathId),
    ]);

    setStudyPath(updatedStudyPath);
    setTopics(updatedTopics);
  }

  async function handleGenerateTopics() {
    const overwriteExisting =
      topics.length > 0
        ? window.confirm(
            "This study path already has topics. Replace existing topics and their generated lessons?",
          )
        : false;

    if (topics.length > 0 && !overwriteExisting) {
      setStatus("Topic generation canceled. Existing topics were preserved.");
      return;
    }

    try {
      setIsGeneratingTopics(true);
      setStatus(
        "Generating topics from your goal and any uploaded material...",
      );

      const generatedTopics = await generateStudyPathTopics(
        studyPathId,
        overwriteExisting,
      );

      setTopics(generatedTopics);
      setLesson(null);

      if (generatedTopics.length > 0) {
        const matchingTopic = topicIdFromUrl
          ? generatedTopics.find((topic) => topic.id === topicIdFromUrl)
          : null;

        setSelectedTopicId(
          matchingTopic ? matchingTopic.id : generatedTopics[0].id,
        );
      }

      await refreshStudyPathAndTopics();
      setStatus("Topics generated.");
    } catch (err) {
      console.error(err);
      setStatus(
        getReadableErrorMessage(
          err,
          "Failed to generate topics from this study path goal.",
        ),
      );
    } finally {
      setIsGeneratingTopics(false);
    }
  }

  async function handleGenerateLesson() {
    if (!selectedTopicId) return;

    try {
      setIsGeneratingLesson(true);
      setStatus("Generating adaptive lesson from your starting point...");

      const generatedLesson = await generateTopicLesson(selectedTopicId, {
        starting_mode: startingMode,
        explanation_density: pacingMode,
        adaptation_note: [
          adaptationNote,
          pacingInstruction.lessonGenerationNote,
        ]
          .filter(Boolean)
          .join("\n\n"),
        stable_concepts: memorySummary?.stable_concepts.map(
          (concept) => concept.concept_name,
        ),
        transferable_concepts: memorySummary?.transferable_concepts.map(
          (concept) => concept.concept_name,
        ),
        concepts_to_skip: memorySummary?.concepts_to_skip,
        concepts_to_briefly_repair: memorySummary?.concepts_to_briefly_repair,
        memory_guidance: memorySummary?.recommended_lesson_guidance ?? null,
      });

      if (generatedLesson.generation_status === "ready") {
        setLesson(generatedLesson);
        lessonCacheRef.current[selectedTopicId] = generatedLesson;
      } else {
        setLesson(null);
      }
      setTopicLessonStatuses((prev) => ({
        ...prev,
        [selectedTopicId]: generatedLesson.generation_status || "generating",
      }));
      await logStudySession("lesson", 10);
      setStatus(
        generatedLesson.generation_status === "ready"
          ? "Adaptive lesson generated."
          : "This topic is still preparing. You can review generated topics from the index while it finishes.",
      );
    } catch (err) {
      console.error(err);
      setStatus(
        getReadableErrorMessage(
          err,
          "Failed to generate adaptive lesson from this topic.",
        ),
      );
    } finally {
      setIsGeneratingLesson(false);
    }
  }

  async function handleGenerateFullStudyPath() {
    const overwriteExisting =
      topics.length > 0
        ? window.confirm(
            "This will replace existing topics, lessons, and topic-level practice history for this path. Continue?",
          )
        : false;

    if (topics.length > 0 && !overwriteExisting) {
      setStatus(
        "Full study path generation canceled. Existing path preserved.",
      );
      return;
    }

    try {
      setIsGeneratingFullPath(true);
      setStatus("Generating full study path. This may take 30–90 seconds...");

      const generatedTopics = await generateStudyPathTopics(
        studyPathId,
        overwriteExisting,
      );
      setTopics(generatedTopics);
      setLesson(null);

      const generatedLessons = await generateStudyPathLessons(studyPathId);
      generatedLessons.forEach((item) => {
        lessonCacheRef.current[item.topic_id] = item;
      });
      setTopicLessonStatuses((prev) => ({
        ...prev,
        ...Object.fromEntries(
          generatedLessons.map((item) => [
            item.topic_id,
            item.generation_status || "ready",
          ]),
        ),
      }));

      if (generatedTopics.length > 0) {
        const matchingTopic = topicIdFromUrl
          ? generatedTopics.find((topic) => topic.id === topicIdFromUrl)
          : null;

        const firstTopicId = matchingTopic
          ? matchingTopic.id
          : generatedTopics[0].id;
        setSelectedTopicId(firstTopicId);

        const firstLesson =
          generatedLessons.find((item) => item.topic_id === firstTopicId) ??
          null;

        if (firstLesson) {
          setLesson(firstLesson);
        }
      }

      await logStudySession("lesson", 15);
      await refreshStudyPathAndTopics();
      setStatus("Full study path generated.");
    } catch (err) {
      console.error(err);
      setStatus(
        getReadableErrorMessage(
          err,
          "Failed to generate full study path from this goal.",
        ),
      );
    } finally {
      setIsGeneratingFullPath(false);
    }
  }

  async function handleRegenerateCurrentTopic() {
    if (!selectedTopicId) return;

    try {
      setIsRegeneratingTopic(true);
      setStatus("Regenerating current lesson...");

      const regeneratedLesson = await regenerateTopicLesson(
        selectedTopicId,
        [
          regenerationFeedback,
          pacingInstruction.regenerationNote,
        ]
          .filter(Boolean)
          .join("\n\n"),
      );

      setLesson(regeneratedLesson);
      lessonCacheRef.current[selectedTopicId] = regeneratedLesson;
      setTopicLessonStatuses((prev) => ({
        ...prev,
        [selectedTopicId]: regeneratedLesson.generation_status || "ready",
      }));
      resetPracticeState();
      setTopicQAResponse(null);
      setHighlightedText("");
      setSelectedTextForQuestion("");
      setCurrentStepIndex(0);

      await logStudySession("regeneration", 5);
      setStatus("Current lesson regenerated with feedback.");
    } catch (err) {
      console.error(err);
      setStatus(
        getReadableErrorMessage(err, "Failed to regenerate current lesson."),
      );
    } finally {
      setIsRegeneratingTopic(false);
    }
  }

  async function handleRegeneratePath() {
    const overwriteExisting = window.confirm(
      "Regenerating the whole path will replace existing topics and lessons for this study path. Continue?",
    );

    if (!overwriteExisting) {
      setStatus(
        "Full study path regeneration canceled. Existing path preserved.",
      );
      return;
    }

    try {
      setIsRegeneratingPath(true);
      setStatus("Regenerating full study path with feedback...");

      const generatedLessons = await regenerateStudyPath(
        studyPathId,
        regenerationFeedback,
        overwriteExisting,
      );

      const updatedTopics = await getStudyPathTopics(studyPathId);
      setTopics(updatedTopics);
      setLesson(null);
      generatedLessons.forEach((item) => {
        lessonCacheRef.current[item.topic_id] = item;
      });
      setTopicLessonStatuses(
        Object.fromEntries(
          generatedLessons.map((item) => [
            item.topic_id,
            item.generation_status || "ready",
          ]),
        ),
      );

      if (updatedTopics.length > 0) {
        const matchingTopic = topicIdFromUrl
          ? updatedTopics.find((topic) => topic.id === topicIdFromUrl)
          : null;

        const firstTopicId = matchingTopic
          ? matchingTopic.id
          : updatedTopics[0].id;
        setSelectedTopicId(firstTopicId);

        const firstLesson =
          generatedLessons.find((item) => item.topic_id === firstTopicId) ??
          null;

        if (firstLesson) {
          setLesson(firstLesson);
        }
      }

      await logStudySession("regeneration", 10);
      await refreshStudyPathAndTopics();
      resetPracticeState();
      setRegenerationFeedback("");
      setTopicQAResponse(null);
      setTopicQuestion("");
      setHighlightedText("");
      setSelectedTextForQuestion("");
      setCurrentStepIndex(0);
      setStatus("Full study path regenerated with feedback.");
    } catch (err) {
      console.error(err);
      setStatus(
        getReadableErrorMessage(err, "Failed to regenerate full study path."),
      );
    } finally {
      setIsRegeneratingPath(false);
    }
  }

  async function handleUpdateTopicStatus(nextStatus: TopicStatus) {
    if (!selectedTopic) return;

    try {
      setStatus("Updating topic status...");
      await updateTopicStatus(selectedTopic.id, nextStatus);

      if (nextStatus === "completed" || nextStatus === "in_progress") {
        await logStudySession("lesson", 3);
      }

      await refreshStudyPathAndTopics();
      setStatus(`Topic marked as ${nextStatus.replace(/_/g, " ")}.`);
    } catch (err) {
      console.error(err);
      setStatus(getReadableErrorMessage(err, "Failed to update topic status."));
    }
  }

  function getPracticeQuestionText(question: LessonPracticeQuestion) {
    return question.question_text || "Practice question";
  }

  function formatPracticeQuestionForEvaluation(
    question: LessonPracticeQuestion,
  ) {
    const parts = [
      `Type: ${question.question_type || "short_answer"}`,
      question.concept_tested ? `Concept tested: ${question.concept_tested}` : "",
      question.related_section
        ? `Related section: ${question.related_section}`
        : "",
      question.why_this_matters
        ? `Why this matters: ${question.why_this_matters}`
        : "",
      `Question: ${getPracticeQuestionText(question)}`,
      question.choices?.length
        ? `Choices: ${question.choices.join(" | ")}`
        : "",
      question.given?.length ? `Given: ${question.given.join(" | ")}` : "",
      question.correct_answer
        ? `Private answer key: ${question.correct_answer}`
        : "",
      question.explanation
        ? `Private explanation: ${question.explanation}`
        : "",
    ];

    return parts.filter(Boolean).join("\n");
  }

  function formatHintText(result: PracticeHintResponse) {
    return [
      result.hint,
      result.guiding_question
        ? `Guiding question: ${result.guiding_question}`
        : "",
      result.concept_to_review ? `Review: ${result.concept_to_review}` : "",
    ]
      .filter(Boolean)
      .join("\n\n");
  }

  function formatPracticeFeedbackText(result: PracticeSubmitResponse) {
    return [
      result.is_correct ? "Correct." : "Needs work.",
      `Performance: ${result.performance_level.replace(/_/g, " ")}`,
      result.mistake_type ? `Mistake type: ${result.mistake_type}` : "",
      "",
      result.feedback,
      result.follow_up_question
        ? `\nFollow-up: ${result.follow_up_question}`
        : "",
      `\nNext action: ${result.next_action.replace(/_/g, " ")}`,
    ]
      .filter(Boolean)
      .join("\n");
  }

  function shouldGenerateTargetedRepair(result: PracticeSubmitResponse) {
    return (
      result.performance_level === "weak" ||
      result.performance_level === "minor_mistake" ||
      result.next_action === "minimal_repair" ||
      result.next_action === "targeted_follow_up"
    );
  }

  function renderConfidenceSelector(questionIndex: number) {
    return (
      <div className="rounded-2xl border border-border bg-muted/30 p-4">
        <p className="text-sm font-semibold text-foreground">
          How confident are you?
        </p>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">
          This helps Azalea separate real mastery from shaky confidence.
        </p>

        <div className="mt-3 flex flex-wrap gap-2">
          {[1, 2, 3, 4, 5].map((value) => {
            const selected = (practiceConfidence[questionIndex] ?? 3) === value;

            return (
              <button
                key={value}
                type="button"
                onClick={() =>
                  setPracticeConfidence((prev) => ({
                    ...prev,
                    [questionIndex]: value,
                  }))
                }
                className={`rounded-2xl px-3 py-2 text-sm font-semibold transition ${
                  selected
                    ? "bg-primary text-primary-foreground"
                    : "border border-border bg-background text-foreground hover:bg-muted"
                }`}
              >
                {value}
              </button>
            );
          })}
        </div>
      </div>
    );
  }

  async function handleRunCodingPractice(
    question: LessonPracticeQuestion,
    index: number,
  ) {
    const code = practiceAnswers[index] ?? "";

    if (!code.trim()) {
      setPracticeRunOutput((prev) => ({
        ...prev,
        [index]: "Write code before running tests.",
      }));
      return;
    }

    try {
      setPracticeLoadingIndex(index);
      setPracticeRunOutput((prev) => ({
        ...prev,
        [index]: "Running visible tests...",
      }));

      const result = await runPracticeCode({
        code,
        language: practiceCodeLanguages[index] || question.language || "python",
        test_cases: (question.test_cases || []).map((testCase) => ({
          input: testCase.input || "",
          expected: testCase.expected || "",
        })),
      });

      const lines = [
        result.error ||
          `${result.passed}/${result.total} visible tests passed. ${
            result.all_passed ? "Ready to submit." : "Inspect failed cases below."
          }`,
        "",
        ...result.cases.map((testCase) =>
          [
            `Case ${testCase.case_number}: ${
              testCase.passed ? "Passed" : testCase.status
            }`,
            `Input: ${testCase.input || "(empty)"}`,
            `Expected: ${testCase.expected}`,
            `Actual: ${testCase.actual || "(no stdout)"}`,
            testCase.stderr ? `stderr: ${testCase.stderr}` : "",
          ]
            .filter(Boolean)
            .join("\n"),
        ),
      ];

      setPracticeRunOutput((prev) => ({
        ...prev,
        [index]: lines.join("\n\n"),
      }));
    } catch (err) {
      console.error(err);
      setPracticeRunOutput((prev) => ({
        ...prev,
        [index]: "Failed to run code.",
      }));
    } finally {
      setPracticeLoadingIndex(null);
    }
  }

  function handlePracticeCodeLanguageChange(index: number, language: string) {
    setPracticeCodeLanguages((prev) => ({
      ...prev,
      [index]: language,
    }));
    setPracticeAnswers((prev) => ({
      ...prev,
      [index]: getDefaultCodingStarterCode(language),
    }));
    setPracticeRunOutput((prev) => ({
      ...prev,
      [index]: "Run your code to preview visible test cases here.",
    }));
  }

  async function handleGetPracticeHint(
    question: LessonPracticeQuestion,
    index: number,
    partialAnswer?: string,
  ) {
    if (!selectedTopic) {
      setPracticeError("Select a topic before requesting a hint.");
      return null;
    }

    try {
      setPracticeLoadingIndex(index);
      setPracticeError(null);
      setAutoAdvanceStatus("");

      const result = await getPracticeHint({
        study_path_id: studyPathId,
        topic_id: selectedTopic.id,
        lesson_id: lesson?.id ?? null,
        question: formatPracticeQuestionForEvaluation(question),
        user_partial_answer: partialAnswer || practiceAnswers[index] || null,
        lesson_context: buildLessonContext(),
        current_section: currentStep?.title || question.related_section || null,
      });

      setPracticeHints((prev) => ({ ...prev, [index]: result }));
      setHintUsedByQuestion((prev) => ({ ...prev, [index]: true }));

      await submitLearnerSignal({
        topic_id: selectedTopic.id,
        concept_name:
          result.concept_to_review || getPracticeConceptName(question),
        signal_type: "hint",
        hint_used: true,
        correctness: null,
        reasoning_quality: null,
        confidence: null,
        summary: result.hint,
        metadata: {
          question_index: index,
          question_text: getPracticeQuestionText(question),
          concept_tested: getPracticeConceptName(question),
          related_section: question.related_section || currentStep?.title || null,
          guiding_question: result.guiding_question,
          concept_to_review: result.concept_to_review ?? null,
        },
      });

      return formatHintText(result);
    } catch (err) {
      console.error(err);
      setPracticeError(
        getReadableErrorMessage(err, "Failed to generate hint."),
      );
      return null;
    } finally {
      setPracticeLoadingIndex(null);
    }
  }

  async function handleSubmitPracticeAnswer(
    question: LessonPracticeQuestion,
    index: number,
    submittedAnswer?: string,
  ) {
    if (!selectedTopic) {
      setPracticeError("Select a topic before submitting an answer.");
      return null;
    }

    const userAnswer = (submittedAnswer ?? practiceAnswers[index])?.trim();

    if (!userAnswer) {
      setPracticeError("Type an answer before submitting.");
      return null;
    }

    try {
      setPracticeLoadingIndex(index);
      setPracticeError(null);

      const result = await submitPracticeAnswer({
        study_path_id: studyPathId,
        topic_id: selectedTopic.id,
        lesson_id: lesson?.id ?? null,
        question: formatPracticeQuestionForEvaluation(question),
        user_answer: userAnswer,
        lesson_context: buildLessonContext(),
        current_section: currentStep?.title || question.related_section || null,
        concept_tested:
          question.concept_tested ||
          question.skill_target ||
          selectedTopic.title ||
          null,
        related_section:
          question.related_section || currentStep?.title || null,
        hint_used: hintUsedByQuestion[index] ?? false,
      });

      const learnerSignal = mapPracticeResultToLearnerSignal(result);
      const confidenceValue = practiceConfidence[index] ?? 3;
      updateRecentPracticeLevel(result.performance_level);

      recordFlowMetric(studyPathId, (metrics) => {
        metrics.quickChecks += 1;
        if (result.performance_level === "strong") {
          metrics.quickCheckCorrect += 1;
        }
      });

      if (
        result.performance_level === "strong" &&
        confidenceValue >= 4 &&
        pacingMode !== "fast"
      ) {
        setPacingMode("fast");
      }

      if (
        ["weak", "minor_mistake"].includes(result.performance_level) &&
        pacingMode === "fast"
      ) {
        setPacingMode("balanced");
      }

      await submitLearnerSignal({
        topic_id: selectedTopic.id,
        concept_name: result.mistake_type || getPracticeConceptName(question),
        signal_type: "practice",
        correctness: learnerSignal.correctness,
        reasoning_quality: learnerSignal.reasoning_quality,
        confidence: confidenceValue / 5,
        hint_used: hintUsedByQuestion[index] ?? false,
        mistake_type: result.mistake_type ?? null,
        summary: result.feedback,
        metadata: {
          question_index: index,
          question_text: getPracticeQuestionText(question),
          concept_tested: getPracticeConceptName(question),
          related_section: question.related_section || currentStep?.title || null,
          performance_level: result.performance_level,
          next_action: result.next_action,
          follow_up_question: result.follow_up_question ?? null,
          confidence_raw: confidenceValue,
        },
      });

      if (shouldGenerateTargetedRepair(result)) {
        const repair = await generateTargetedRepair(selectedTopic.id, {
          concept_name: result.mistake_type || getPracticeConceptName(question),
          mistake_type: result.mistake_type ?? null,
          question: getPracticeQuestionText(question),
          user_answer: userAnswer,
          lesson_context: buildLessonContext(),
          feedback: result.feedback,
        });

        setTargetedRepairs((prev) => ({
          ...prev,
          [index]: repair,
        }));
      } else {
        setTargetedRepairs((prev) => {
          const next = { ...prev };
          delete next[index];
          return next;
        });
      }

      setPracticeFeedback((prev) => ({ ...prev, [index]: result }));
      await logStudySession("practice", 5);
      await refreshStudyPathAndTopics();

      if (
        result.performance_level === "strong" &&
        currentStep?.type === "practice" &&
        currentStep.questionIndex === index
      ) {
        setAutoAdvanceStatus("Nice. Moving to the next card...");
        window.setTimeout(() => {
          setAutoAdvanceStatus("");
          void goToNextStep();
        }, 900);
      }

      maybeRegenerateFutureCards({
        trigger: getLevelShiftTrigger(result.performance_level, confidenceValue),
        targetAdjustment: getTargetAdjustmentForPracticeResult(
          result.performance_level,
          confidenceValue,
        ),
        evidence: {
          recent_performance: result.performance_level,
          confidence: confidenceValue,
          mistake_type: result.mistake_type ?? null,
          feedback: result.feedback,
          question: getPracticeQuestionText(question),
          current_card_title: currentStep?.title ?? null,
        },
      });

      return formatPracticeFeedbackText(result);
    } catch (err) {
      console.error(err);
      setPracticeError(
        getReadableErrorMessage(err, "Failed to submit practice answer."),
      );
      return null;
    } finally {
      setPracticeLoadingIndex(null);
    }
  }

  async function handleSubmitTargetedRepairFollowUp(index: number) {
    const repair = targetedRepairs[index];

    if (!repair) return;

    const answer = targetedRepairAnswers[index]?.trim();

    if (!answer) {
      setPracticeError(
        "Type an answer to the repair follow-up before submitting.",
      );
      return;
    }

    try {
      setTargetedRepairLoadingIndex(index);
      setPracticeError(null);

      const result = await submitTargetedRepairFollowUp(
        repair.repair_attempt_id,
        {
          answer,
          confidence: targetedRepairConfidence[index] ?? 3,
        },
      );

      setTargetedRepairFeedback((prev) => ({
        ...prev,
        [index]: result,
      }));

      await logStudySession("practice", 3);

      if (result.is_complete || result.correctness >= 0.8) {
        setAutoAdvanceStatus("Repair landed. Continuing the flow...");
        window.setTimeout(() => {
          setAutoAdvanceStatus("");
          void goToNextStep();
        }, 1100);
      }
    } catch (err) {
      console.error(err);
      setPracticeError(
        getReadableErrorMessage(
          err,
          "Failed to submit targeted repair follow-up.",
        ),
      );
    } finally {
      setTargetedRepairLoadingIndex(null);
    }
  }

  async function handleSubmitReviewAnswer() {
    if (!selectedTopic || !reviewQuestion) {
      setPracticeError("Open a review check before submitting.");
      return;
    }

    if (!reviewAnswer.trim()) {
      setPracticeError("Type an answer before submitting the review check.");
      return;
    }

    try {
      setIsSubmittingReviewAnswer(true);
      setPracticeError(null);

      const result = await submitReviewAnswer({
        topic_id: selectedTopic.id,
        concept_name: reviewQuestion.target_concept,
        question: reviewQuestion.question,
        answer: reviewAnswer,
        confidence: reviewConfidence,
        review_reason: reviewQuestion.reason,
      });

      setReviewFeedback(result);
      await logStudySession("review", 3);
      await refreshStudyPathAndTopics();
    } catch (err) {
      console.error(err);
      setPracticeError(
        getReadableErrorMessage(err, "Failed to submit review answer."),
      );
    } finally {
      setIsSubmittingReviewAnswer(false);
    }
  }

  function getCurrentCardContext() {
    const card = currentStep?.type === "flow_card" ? currentStep.card : undefined;

    return {
      cardId:
        card?.id ??
        (currentStep ? `step-${safeCurrentStepIndex + 1}` : null),
      cardTitle: card?.title ?? currentStep?.title ?? null,
      mainConcept:
        card?.main_concept ??
        currentStep?.title ??
        selectedTopic?.title ??
        "overall_topic",
      conceptSupport: card?.concept_support ?? [],
      newConcepts: card?.new_concepts ?? [],
      reviewConcepts: card?.review_concepts ?? [],
      prerequisiteConcepts: card?.prerequisite_concepts ?? [],
      misconceptions: card?.common_misconceptions ?? [],
    };
  }

  function rememberQA(question: string, response: TopicQAResponse) {
    if (response.confusion_event_id) {
      setLastConfusionEventId(response.confusion_event_id);
    }

    setTopicQAHistory((prev) => [
      ...prev.slice(-11),
      {
        id: response.confusion_event_id ?? `${Date.now()}`,
        question,
        answer: response.answer,
        confusionType: response.confusion_type,
        conceptName: response.concept_name,
        createdAt: Date.now(),
      },
    ]);

    if (response.confusion_event_id && selectedTopic) {
      setTopicConfusionEvents((prev) => [
        {
          id: response.confusion_event_id ?? `${Date.now()}`,
          topic_id: selectedTopic.id,
          study_path_id: studyPathId,
          lesson_id: lesson?.id ?? null,
          card_id: getCurrentCardContext().cardId,
          card_title: getCurrentCardContext().cardTitle,
          current_section: currentStep?.title ?? null,
          highlighted_text: selectedTextForQuestion || highlightedText || null,
          user_question: question,
          answer_generated: response.answer,
          confusion_type: response.confusion_type,
          concept_name: response.concept_name,
          clarification_mode: response.clarification_mode,
          resolved: false,
          still_confused_count: 0,
          follow_up_count: 0,
          suggested_actions: response.suggested_actions,
          created_at: new Date().toISOString(),
        },
        ...prev,
      ]);
    }
  }

  async function handleAskTopicQuestion(e: FormEvent) {
    e.preventDefault();

    if (!selectedTopic) {
      setStatus("Select a topic before asking a question.");
      return;
    }

    const questionText = topicQuestion.trim();
    if (!questionText) return;

    setTopicQuestion("");
    setPendingQuestion(questionText);

    try {
      setIsAskingTopicQuestion(true);
      if (activeVisualContext) {
        setStatus("Asking Azalea about this visual...");
        const visualResponse = await askVisualQuestionV2(
          questionText,
          activeVisualContext,
        );
        const response: TopicQAResponse = {
          answer: visualResponse.answer,
          sources: [],
          confusion_event_id: null,
          confusion_type: "visual_question",
          concept_name: activeVisualLabel || currentStep?.title || "Visual",
          clarification_mode: "visual_context",
          suggested_actions: [],
          follow_up_prompts: [],
        };
        setTopicQAResponse(response);
        rememberQA(questionText, response);
        recordFlowMetric(studyPathId, (metrics) => {
          metrics.questionsAsked += 1;
        });
        setStatus("Visual answer generated.");
        return;
      }

      setStatus("Asking Azalea about this topic...");
      const cardContext = getCurrentCardContext();

      const response = await askTopicQuestion(
        selectedTopic.id,
        questionText,
        buildLessonContext(),
        selectedTextForQuestion || undefined,
        currentStep?.title || "Purpose & Context",
        studyPathId,
        lesson?.id ?? null,
        {
          card_id: cardContext.cardId,
          card_title: cardContext.cardTitle,
          clarification_mode: "direct_answer",
          prior_confusion_event_id: lastConfusionEventId,
        },
      );

      setTopicQAResponse(response);
      rememberQA(questionText, response);
      recordFlowMetric(studyPathId, (metrics) => {
        metrics.questionsAsked += 1;
      });

      await submitLearnerSignal({
        topic_id: selectedTopic.id,
        concept_name: response.concept_name || cardContext.mainConcept,
        signal_type: "question",
        summary: questionText,
        metadata: {
          question: questionText,
          selected_text: selectedTextForQuestion || null,
          current_section: currentStep?.title || null,
          card_id: cardContext.cardId,
          card_title: cardContext.cardTitle,
          confusion_event_id: response.confusion_event_id,
          confusion_type: response.confusion_type,
          clarification_mode: response.clarification_mode,
          study_path_id: studyPathId,
          lesson_id: lesson?.id ?? null,
          answer_preview: response.answer.slice(0, 400),
          source_count: response.sources.length,
        },
      });

      await logStudySession("qa", 5);
      setStatus("Topic answer generated.");
    } catch (err) {
      console.error(err);
      setTopicQuestion(questionText);
      setStatus(
        getReadableErrorMessage(
          err,
          "Failed to answer topic question. Attach material directly to this study path or use class material.",
        ),
      );
    } finally {
      setIsAskingTopicQuestion(false);
      setPendingQuestion("");
    }
  }

  async function handleInstantClarification({
    label,
    question,
    selectedText,
    shouldAdaptFutureCards = true,
  }: {
    label: string;
    question: string;
    selectedText?: string;
    shouldAdaptFutureCards?: boolean;
  }) {
    if (!selectedTopic) {
      setStatus("Select a topic before asking for clarification.");
      return;
    }

    try {
      setIsAskingTopicQuestion(true);
      setActiveClarificationLabel(label);
      setPendingQuestion(question);
      const cardContext = getCurrentCardContext();
      const requestedMode = label.toLowerCase().includes("misconception")
        ? "misconception_correction"
        : label.toLowerCase().includes("example")
          ? "worked_example"
          : label.toLowerCase().includes("slower")
            ? "simpler_explanation"
            : "direct_answer";

      const response = await askTopicQuestion(
        selectedTopic.id,
        question,
        buildLessonContext(),
        selectedText || selectedTextForQuestion || highlightedText || undefined,
        currentStep?.title || "Current step",
        studyPathId,
        lesson?.id ?? null,
        {
          card_id: cardContext.cardId,
          card_title: cardContext.cardTitle,
          clarification_mode: requestedMode,
          prior_confusion_event_id: lastConfusionEventId,
        },
      );

      setTopicQAResponse(response);
      rememberQA(question, response);
      setInsertedClarification(response.answer);
      setIsChatPanelOpen(false);

      confusionSignalCountRef.current += 1;

      recordFlowMetric(studyPathId, (metrics) => {
        metrics.questionsAsked += 1;
      });

      await submitLearnerSignal({
        topic_id: selectedTopic.id,
        concept_name: response.concept_name || cardContext.mainConcept,
        signal_type: "question",
        confidence: 0.35,
        mistake_type:
          response.confusion_type === "misconception" ||
          response.confusion_type === "prerequisite_gap" ||
          response.confusion_type === "skipped_step"
            ? response.confusion_type
            : null,
        summary: question,
        metadata: {
          clarification_label: label,
          question,
          card_id: cardContext.cardId,
          card_title: cardContext.cardTitle,
          main_concept: cardContext.mainConcept,
          new_concepts: cardContext.newConcepts,
          review_concepts: cardContext.reviewConcepts,
          prerequisite_concepts: cardContext.prerequisiteConcepts,
          confusion_event_id: response.confusion_event_id,
          confusion_type: response.confusion_type,
          clarification_mode: response.clarification_mode,
          selected_text:
            selectedText || selectedTextForQuestion || highlightedText || null,
          current_section: currentStep?.title || null,
          current_step_index: safeCurrentStepIndex,
          study_path_id: studyPathId,
          lesson_id: lesson?.id ?? null,
          answer_preview: response.answer.slice(0, 400),
          source_count: response.sources.length,
          confusion_signal_count: confusionSignalCountRef.current,
        },
      });

      if (shouldAdaptFutureCards) {
        maybeRegenerateFutureCards({
          trigger: "learner_confusion_question",
          targetAdjustment: "repair",
          evidence: {
            clarification_label: label,
            question,
            selected_text:
              selectedText || selectedTextForQuestion || highlightedText || null,
            answer_preview: response.answer.slice(0, 400),
            confusion_signal_count: confusionSignalCountRef.current,
          },
        });
      }

      await logStudySession("qa", 3);
      setStatus("Clarification inserted.");
    } catch (err) {
      console.error(err);
      setStatus(
        getReadableErrorMessage(
          err,
          "Failed to generate a clarification for this step.",
        ),
      );
    } finally {
      setIsAskingTopicQuestion(false);
      setPendingQuestion("");
    }
  }

  async function markCurrentClarificationResolved() {
    const eventId = topicQAResponse?.confusion_event_id ?? lastConfusionEventId;
    if (!eventId) {
      setStatus("Great. Moving forward with this fixed.");
      return;
    }

    try {
      const updated = await updateConfusionEvent(eventId, { resolved: true });
      setTopicConfusionEvents((prev) =>
        prev.map((event) => (event.id === updated.id ? updated : event)),
      );
      setInsertedClarification("");
      setActiveClarificationLabel("");
      setStatus("Great. Moving forward with this fixed.");
    } catch (err) {
      console.error(err);
      setStatus("Clarification marked locally.");
    }
  }

  async function askStillConfused() {
    const eventId = topicQAResponse?.confusion_event_id ?? lastConfusionEventId;

    if (eventId) {
      try {
        const updated = await updateConfusionEvent(eventId, {
          still_confused: true,
          follow_up: true,
        });
        setTopicConfusionEvents((prev) =>
          prev.map((event) => (event.id === updated.id ? updated : event)),
        );
      } catch (err) {
        console.error(err);
      }
    }

    void handleInstantClarification({
      label: "Slower clarification",
      question:
        "I am still confused. Do not repeat the same explanation. Re-explain this more slowly, use a concrete example, call out the prerequisite idea I may be missing, and end with one tiny check.",
    });
  }

  function askForClarificationCheck() {
    void handleInstantClarification({
      label: "Test me",
      question:
        "Give me one tiny check for the exact confusion I just had. Make it answerable in one sentence, include what a correct answer should mention, and do not move to a new topic.",
      shouldAdaptFutureCards: false,
    });
  }

  async function handleSubmitTransferChallenge() {
    if (!selectedTopic || !transferChallenge || !transferAnswer.trim()) {
      setPracticeError(
        "Type an answer before submitting the transfer challenge.",
      );
      return;
    }

    try {
      setIsSubmittingTransferChallenge(true);
      setPracticeError(null);

      const result = await submitTransferChallenge({
        topic_id: selectedTopic.id,
        concept_name: transferChallenge.target_concept,
        challenge: transferChallenge.challenge,
        answer: transferAnswer,
        confidence: transferConfidence,
      });

      setTransferFeedback(result);
      await logStudySession("practice", 5);
      await refreshStudyPathAndTopics();
    } catch (err) {
      console.error(err);
      setPracticeError(
        getReadableErrorMessage(err, "Failed to submit transfer challenge."),
      );
    } finally {
      setIsSubmittingTransferChallenge(false);
    }
  }

  function isRenderableVisual(visual: VisualPlanItem) {
    return isLessonVisualRenderable(visual);
  }

  function renderLearningStep(step: LearningStep, hideVisual = false, guidanceMode = false) {
    if (step.type === "purpose_context") {
      return (
        <div className="mx-auto grid max-w-4xl gap-4 text-left md:grid-cols-2">
          <OrientationMiniCard
            label="What you're learning"
            value={step.intro}
          />
          <OrientationMiniCard label="Why it matters" value={step.purpose} />
          <OrientationMiniCard label="How this connects" value={step.context} />
          <OrientationMiniCard
            label="By the end"
            value={step.learningObjective}
          />
        </div>
      );
    }

    if (step.type === "flow_card") {
      const stepFocus = step === currentStep ? currentVisualFocus : (step.card?.visual_focus ?? null);
      return (
        <LearningCard
          step={step}
          visual={
            !hideVisual && step.visual && isRenderableVisual(step.visual) ? step.visual : null
          }
          showVisual={!hideVisual}
          compact={guidanceMode}
          guidanceMode={guidanceMode}
          focusState={stepFocus}
          onAskAboutText={(text) =>
            void handleInstantClarification({
              label: "Card highlight",
              question:
                "Explain this part of the current card plainly, including why it matters and what I might be misunderstanding.",
              selectedText: text,
            })
          }
        />
      );
    }

    if (step.type === "text") {
      return (
        <div className="mx-auto max-w-3xl text-center text-lg leading-9 text-muted-foreground md:text-xl md:leading-10">
          <p>
            <MathText text={step.content} />
          </p>
        </div>
      );
    }

    if (step.type === "list") {
      const ListTag = step.ordered ? "ol" : "ul";

      return (
        <ListTag className="mx-auto max-w-3xl space-y-4 text-left text-base leading-8 text-muted-foreground md:text-lg">
          {step.items.map((item, index) => (
            <li
              key={index}
              className="flex gap-4 rounded-2xl border border-border bg-background/70 p-4"
            >
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-accent text-sm font-bold text-primary">
                {step.ordered ? index + 1 : "•"}
              </span>
              <span>
                <MathText text={item} />
              </span>
            </li>
          ))}
        </ListTag>
      );
    }

    if (step.type === "visuals") {
      const visuals = step.visuals.filter(isRenderableVisual);

      if (visuals.length === 0) {
        return (
          <div className="mx-auto max-w-2xl rounded-2xl border border-dashed border-border bg-muted/30 p-8 text-center text-sm leading-6 text-muted-foreground">
            No renderable visuals were generated for this topic yet.
          </div>
        );
      }

      return (
        <div className="mx-auto max-w-4xl space-y-4">
          {visuals.map((visual, index) => (
            <VisualRenderer
              key={`${visual.type ?? "visual"}-${index}`}
              visual={visual}
              index={index}
            />
          ))}
        </div>
      );
    }

    if (step.type === "worked_examples") {
      return (
        <div className="mx-auto max-w-4xl space-y-4">
          {step.examples.map((example, index) => (
            <div
              key={index}
              className="rounded-3xl border border-border bg-background p-6 shadow-sm"
            >
              <h4 className="text-xl font-bold text-foreground">
                {example.title || `Example ${index + 1}`}
              </h4>

              {example.steps && example.steps.length > 0 && (
                <ol className="mt-5 space-y-3 text-left text-base leading-8 text-muted-foreground">
                  {example.steps.map((exampleStep, stepIndex) => (
                    <li key={stepIndex} className="flex gap-4">
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-accent text-sm font-bold text-primary">
                        {stepIndex + 1}
                      </span>
                      <span>{exampleStep}</span>
                    </li>
                  ))}
                </ol>
              )}
            </div>
          ))}
        </div>
      );
    }

    if (step.type === "practice") {
      const answer = practiceAnswers[step.questionIndex] ?? "";
      const hint = practiceHints[step.questionIndex];
      const feedback = practiceFeedback[step.questionIndex];
      const targetedRepair = targetedRepairs[step.questionIndex];
      const isLoading = practiceLoadingIndex === step.questionIndex;
      const practiceType = step.question.question_type || "short_answer";
      const questionText = getPracticeQuestionText(step.question);
      const practiceTypeLabel =
        {
          short_answer: "short answer",
          multiple_choice: "multiple choice",
          select_all: "select all that apply",
          math: "math input",
          math_input: "math input",
          coding: "coding",
          coding_environment: "coding",
          visual_labeling: "visual labeling",
          ordering: "ordering",
          debugging: "debugging",
          debugging_scenario: "debugging scenario",
          decision_scenario: "decision scenario",
        }[practiceType] || practiceType.replace(/_/g, " ");
      const isMultipleChoice = practiceType === "multiple_choice";
      const isSelectAll = practiceType === "select_all";
      const isChoiceLike = isMultipleChoice || isSelectAll;
      const isCoding =
        practiceType === "coding" || practiceType === "coding_environment";
      const isMath = practiceType === "math" || practiceType === "math_input";
      const isStructuredWritten =
        practiceType === "visual_labeling" ||
        practiceType === "ordering" ||
        practiceType === "debugging" ||
        practiceType === "debugging_scenario" ||
        practiceType === "decision_scenario";
      const output =
        practiceRunOutput[step.questionIndex] ||
        "Run your code to preview visible test cases here.";

      const practiceFooter = (
        <>
          {hint && (
            <div className="mt-6 rounded-2xl border border-border bg-muted/30 p-5">
              <p className="text-sm font-bold text-foreground">Hint</p>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-muted-foreground">
                {formatHintText(hint)}
              </p>
              <p className="mt-4 text-sm font-bold text-foreground">Guiding Question</p>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                {hint.guiding_question}
              </p>
              {hint.concept_to_review && (
                <p className="mt-4 rounded-full bg-accent px-3 py-2 text-xs font-semibold text-primary">
                  Review: {hint.concept_to_review}
                </p>
              )}
            </div>
          )}
          {feedback && (
            <div className="mt-6">
              <PracticeFeedbackCard feedback={feedback} />
            </div>
          )}
          {targetedRepair && (
            <div className="mt-6">
              <TargetedRepairCard
                repair={targetedRepair}
                answer={targetedRepairAnswers[step.questionIndex] ?? ""}
                confidence={targetedRepairConfidence[step.questionIndex] ?? 3}
                feedback={targetedRepairFeedback[step.questionIndex]}
                isLoading={targetedRepairLoadingIndex === step.questionIndex}
                onAnswerChange={(value) =>
                  setTargetedRepairAnswers((prev) => ({
                    ...prev,
                    [step.questionIndex]: value,
                  }))
                }
                onConfidenceChange={(value) =>
                  setTargetedRepairConfidence((prev) => ({
                    ...prev,
                    [step.questionIndex]: value,
                  }))
                }
                onSubmit={() =>
                  handleSubmitTargetedRepairFollowUp(step.questionIndex)
                }
              />
            </div>
          )}
        </>
      );

      if (isCoding) {
        return (
          <div className="mx-auto w-full max-w-7xl text-left">
            <div className="overflow-hidden rounded-3xl border border-[#E5DFEE] bg-white shadow-sm shadow-purple-100/40">
              <div className="border-b border-[#E5DFEE] p-6 md:p-8">
                <div className="mb-4 flex flex-wrap items-center gap-3 text-xs font-black uppercase tracking-wide text-muted-foreground">
                  <span className="rounded-full bg-[#EEE9FF] px-4 py-1.5 text-primary">
                    coding practice
                  </span>
                  {step.question.language && (
                    <span className="text-muted-foreground">{step.question.language}</span>
                  )}
                  {step.question.difficulty && (
                    <span className="text-muted-foreground">{step.question.difficulty}</span>
                  )}
                </div>
                <h2 className="text-center text-[2rem] font-black leading-tight tracking-tight text-foreground md:text-[2.35rem]">
                  {step.question.skill_target || selectedTopic?.title || "Implementation problem"}
                </h2>
                <p className="mt-4 text-lg leading-8 text-muted-foreground">
                  {questionText}
                </p>
                {step.question.given && step.question.given.length > 0 && (
                  <div className="mt-5 rounded-2xl bg-muted/40 p-4">
                    <p className="text-sm font-bold text-foreground">Given</p>
                    <ul className="mt-2 space-y-1 text-sm leading-6 text-muted-foreground">
                      {step.question.given.map((item) => (
                        <li key={item}>• {item}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              <div className="grid h-[min(520px,calc(100vh-340px))] min-h-[380px] grid-cols-[38%_62%]">
                <aside className="flex min-h-0 flex-col border-r border-[#E5DFEE]">
                  <div className="min-h-0 flex-1 overflow-y-auto p-5 space-y-4">
                    {step.question.test_cases && step.question.test_cases.length > 0 && (
                      <section className="rounded-2xl border border-violet-900/50 bg-[#151024] p-4 font-mono text-xs leading-6 text-violet-50 selection:bg-violet-400/40 selection:text-white">
                        <p className="mb-2 text-sm font-bold text-zinc-300">Visible test cases</p>
                        <div className="space-y-3">
                          {step.question.test_cases.map((testCase, index) => (
                            <div key={`${testCase.input}-${index}`} className="rounded-xl border border-white/10 p-3">
                              <p className="text-zinc-400">Case {index + 1}</p>
                              <p>Input: {testCase.input}</p>
                              <p>Expected: {testCase.expected}</p>
                            </div>
                          ))}
                        </div>
                      </section>
                    )}
                    <section className="rounded-2xl border border-violet-200 bg-white p-4">
                      <p className="text-sm font-bold text-foreground">Output</p>
                      <pre className="mt-3 max-h-40 overflow-y-auto whitespace-pre-wrap rounded-2xl border border-violet-900/50 bg-[#151024] p-4 font-mono text-xs leading-6 text-violet-50 selection:bg-violet-400/40 selection:text-white">
                        {output}
                      </pre>
                    </section>
                    {renderConfidenceSelector(step.questionIndex)}
                  </div>
                </aside>

                <section className="flex min-h-0 flex-col overflow-hidden bg-[#151024]">
                  <div className="flex h-12 items-center justify-between border-b border-violet-800/70 bg-[#1d1730] px-4">
                    <select
                      value={practiceCodeLanguages[step.questionIndex] || step.question.language || "python"}
                      onChange={(event) => handlePracticeCodeLanguageChange(step.questionIndex, event.target.value)}
                      className="rounded-xl border border-violet-500/50 bg-[#271f42] px-3 py-1.5 text-sm font-semibold text-violet-50 outline-none transition focus:border-violet-300"
                    >
                      <option>python</option>
                      <option>java</option>
                      <option>javascript</option>
                      <option>typescript</option>
                      <option>cpp</option>
                      <option>c</option>
                    </select>
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleRunCodingPractice(step.question, step.questionIndex)}
                        disabled={isLoading}
                        className="rounded-xl border border-violet-400/40 bg-violet-500/10 px-3 py-1.5 text-sm font-semibold text-violet-100 transition hover:bg-violet-500/20 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        Run Tests
                      </button>
                      <button
                        onClick={() => handleGetPracticeHint(step.question, step.questionIndex, answer)}
                        disabled={isLoading}
                        className="rounded-xl border border-violet-400/40 bg-violet-500/10 px-3 py-1.5 text-sm font-semibold text-violet-100 transition hover:bg-violet-500/20 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {isLoading ? "Working..." : "Get Hint"}
                      </button>
                      <button
                        onClick={() => handleSubmitPracticeAnswer(step.question, step.questionIndex, answer)}
                        disabled={isLoading}
                        className="rounded-xl bg-violet-500 px-3 py-1.5 text-sm font-semibold text-white shadow-sm shadow-violet-950/30 transition hover:bg-violet-400 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {isLoading ? "Checking..." : "Submit"}
                      </button>
                    </div>
                  </div>
                  <div className="grid min-h-0 flex-1 grid-cols-[48px_1fr] bg-[#151024]">
                    <div className="select-none border-r border-violet-900/70 bg-[#120d20] px-3 py-5 text-right font-mono text-sm leading-7 text-violet-500">
                      {answer.split("\n").map((_, index) => (
                        <div key={index}>{index + 1}</div>
                      ))}
                    </div>
                    <textarea
                      value={answer}
                      onChange={(e) => setPracticeAnswers((prev) => ({ ...prev, [step.questionIndex]: e.target.value }))}
                      spellCheck={false}
                      wrap="off"
                      className="min-h-0 flex-1 resize-none overflow-auto whitespace-pre bg-[#151024] p-5 font-mono text-sm leading-7 text-violet-50 caret-violet-300 outline-none selection:bg-violet-400/40 selection:text-white placeholder:text-violet-400/60"
                      style={{ scrollbarColor: "#8b5cf6 #151024" }}
                      placeholder={step.question.starter_code || "Write your solution here..."}
                    />
                  </div>
                </section>
              </div>

              {(hint || feedback || targetedRepair) && (
                <div className="border-t border-[#E5DFEE] px-6 pb-8 pt-6 md:px-8">
                  {practiceFooter}
                </div>
              )}
            </div>
          </div>
        );
      }

      return (
        <div className="mx-auto w-full max-w-4xl text-left">
          <div className="overflow-hidden rounded-3xl border border-[#E5DFEE] bg-white shadow-sm shadow-purple-100/40">
            <div className="p-6 md:p-8">
              <div className="mb-5 flex flex-wrap items-center gap-3 text-xs font-black uppercase tracking-wide text-muted-foreground">
                <span className="rounded-full bg-[#EEE9FF] px-4 py-1.5 text-primary">
                  {practiceTypeLabel} practice
                </span>
                {step.question.difficulty && (
                  <span className="text-muted-foreground">{step.question.difficulty}</span>
                )}
              </div>

              {step.question.skill_target && (
                <p className="mb-3 text-center text-sm font-semibold text-primary/70">
                  {step.question.skill_target}
                </p>
              )}

              <h2 className="mb-7 text-center text-[2rem] font-black leading-tight tracking-tight text-foreground md:text-[2.35rem]">
                {questionText}
              </h2>

              {step.question.given && step.question.given.length > 0 && (
                <div className="mb-6 rounded-2xl bg-muted/40 p-4">
                  <p className="text-sm font-bold text-foreground">Given</p>
                  <ul className="mt-2 space-y-1 text-sm leading-6 text-muted-foreground">
                    {step.question.given.map((item) => (
                      <li key={item}>• {item}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            <div className="border-t border-[#E5DFEE] px-6 pb-8 pt-6 md:px-8">
              {isChoiceLike && step.question.choices?.length ? (
                <div className="space-y-3">
                  {step.question.choices.map((choice, index) => {
                    const selectedChoices = answer
                      .split("\n")
                      .map((item) => item.trim())
                      .filter(Boolean);
                    const isSelected = isSelectAll
                      ? selectedChoices.includes(choice)
                      : answer === choice;
                    return (
                      <button
                        key={choice}
                        onClick={() => {
                          setPracticeAnswers((prev) => {
                            if (!isSelectAll) {
                              return { ...prev, [step.questionIndex]: choice };
                            }
                            const nextChoices = selectedChoices.includes(choice)
                              ? selectedChoices.filter((item) => item !== choice)
                              : [...selectedChoices, choice];
                            return { ...prev, [step.questionIndex]: nextChoices.join("\n") };
                          });
                        }}
                        className={`flex w-full items-start gap-4 rounded-2xl border p-4 text-left transition ${
                          isSelected
                            ? "border-primary bg-accent text-primary"
                            : "border-border bg-background text-foreground hover:bg-muted/40"
                        }`}
                      >
                        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-muted text-sm font-bold">
                          {isSelectAll && isSelected ? "✓" : String.fromCharCode(65 + index)}
                        </span>
                        <span className="text-sm leading-6">{choice}</span>
                      </button>
                    );
                  })}
                </div>
              ) : (
                <textarea
                  value={answer}
                  onChange={(e) =>
                    setPracticeAnswers((prev) => ({
                      ...prev,
                      [step.questionIndex]: e.target.value,
                    }))
                  }
                  spellCheck={true}
                  className={`w-full rounded-3xl border border-border bg-background px-5 py-4 text-base text-foreground outline-none placeholder:text-muted-foreground focus:border-primary ${
                    isMath ? "min-h-48" : isStructuredWritten ? "min-h-44" : "min-h-36"
                  }`}
                  placeholder={
                    isMath
                      ? "Show your work and final answer..."
                      : practiceType === "ordering"
                        ? "Write the correct order, one step per line..."
                        : practiceType === "visual_labeling"
                          ? "Name the requested label/component and justify it..."
                          : practiceType === "debugging" || practiceType === "debugging_scenario"
                            ? "Identify the issue, evidence, and fix..."
                            : practiceType === "decision_scenario"
                              ? "Choose the best option and cite the deciding constraint..."
                              : "Type your answer..."
                  }
                />
              )}

              <div className="mt-5">
                {renderConfidenceSelector(step.questionIndex)}
              </div>

              <div className="mt-4 flex flex-wrap gap-3">
                <button
                  onClick={() => handleGetPracticeHint(step.question, step.questionIndex)}
                  disabled={isLoading}
                  className="rounded-2xl border border-border bg-background px-5 py-3 text-sm font-semibold text-foreground transition hover:border-primary/40 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isLoading ? "Working..." : "Get Hint"}
                </button>
                <button
                  onClick={() => handleSubmitPracticeAnswer(step.question, step.questionIndex)}
                  disabled={isLoading}
                  className="rounded-2xl bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground transition hover:bg-foreground disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isLoading ? "Checking..." : "Submit"}
                </button>
              </div>

              {practiceFooter}
            </div>
          </div>
        </div>
      );
    }

    if (step.type === "source_preview") {
      return (
        <p className="mx-auto max-w-3xl text-center text-lg leading-9 text-muted-foreground">
          {step.content}
        </p>
      );
    }

    if (step.type === "source_grounding" && lesson) {
      return <SourceGroundingCard lesson={lesson} />;
    }

    return null;
  }

  function goToPreviousStep() {
    if (flowCheckpoint) {
      setFlowCheckpoint(null);
      stepNavigationIntentRef.current = "previous";
      setCurrentStepIndex(lessonSteps.length > 0 ? lessonSteps.length - 1 : 0);
      return;
    }
    stepNavigationIntentRef.current = "previous";
    setCurrentStepIndex((index) => Math.max(index - 1, 0));
  }

  async function ensureTopicLessonReadyForFlow(nextTopic: Topic) {
    if (isTopicLessonReady(nextTopic.id)) {
      return true;
    }

    try {
      const statusResult = await getTopicLessonStatus(nextTopic.id);
      setTopicLessonStatuses((prev) => ({
        ...prev,
        [nextTopic.id]: statusResult.generation_status,
      }));
      if (statusResult.generation_status !== "ready") {
        setStatus(
          `Next topic is still preparing: ${nextTopic.title}. You can review this topic or generated topics from the index while it finishes.`,
        );
        return false;
      }

      const nextLesson = await getTopicLesson(nextTopic.id);
      if (nextLesson.generation_status !== "ready") {
        setTopicLessonStatuses((prev) => ({
          ...prev,
          [nextTopic.id]: nextLesson.generation_status || "generating",
        }));
        setStatus(
          `Next topic is still preparing: ${nextTopic.title}. You can review this topic or generated topics from the index while it finishes.`,
        );
        return false;
      }

      lessonCacheRef.current[nextTopic.id] = nextLesson;
      setTopicLessonStatuses((prev) => ({
        ...prev,
        [nextTopic.id]: "ready",
      }));
      return true;
    } catch (err) {
      console.error("Failed to verify next topic readiness:", err);
      setStatus(
        `Next topic is still preparing: ${nextTopic.title}. You can review this topic or generated topics from the index while it finishes.`,
      );
      return false;
    }
  }

  async function goToNextStep() {
    if (flowCheckpoint) {
      return;
    }

    if (shouldBlockFinishTopic) {
      setStatus(finishTopicDisabledReason);
      return;
    }

    if (safeCurrentStepIndex < lessonSteps.length - 1) {
      stepNavigationIntentRef.current = "next";
      recordTransitionMetric(studyPathId, lastTransitionAtRef);
      setCurrentStepIndex((index) => index + 1);
      return;
    }

    if (selectedTopic) {
      await handleUpdateTopicStatus("completed");
      const updatedTopics = await getStudyPathTopics(studyPathId);
      setTopics(updatedTopics);

      const selectedTopicIndex = updatedTopics.findIndex(
        (topic) => topic.id === selectedTopic.id,
      );
      let nextTopic =
        selectedTopicIndex >= 0
          ? updatedTopics[selectedTopicIndex + 1]
          : undefined;

      if (!nextTopic && (isGeneratingTopics || isGeneratingFullPath)) {
        setStatus(
          "The next topic is still being added. You can review this topic or generated topics from the index while it finishes.",
        );
        return;
      }

      if (!nextTopic) {
        try {
          setStatus("Checking whether the next topic still needs to be added...");
          const expandedTopics = await generateStudyPathTopics(
            studyPathId,
            false,
          );
          setTopics(expandedTopics);
          const expandedSelectedTopicIndex = expandedTopics.findIndex(
            (topic) => topic.id === selectedTopic.id,
          );
          nextTopic =
            expandedSelectedTopicIndex >= 0
              ? expandedTopics[expandedSelectedTopicIndex + 1]
              : undefined;
        } catch (err) {
          console.error("Failed to append next topic:", err);
        }
      }

      if (nextTopic) {
        const nextReady = await ensureTopicLessonReadyForFlow(nextTopic);
        if (!nextReady) {
          return;
        }

        setFlowCheckpoint({
          type: "topic_complete",
          completedTopicTitle: selectedTopic.title,
          nextTopic,
        });
        recordFlowMetric(studyPathId, (metrics) => {
          metrics.topicsCompleted += 1;
        });
      } else {
        clearFlowResume(studyPathId);
        setFlowCheckpoint({
          type: "path_complete",
          completedTopicTitle: selectedTopic.title,
        });
        recordFlowMetric(studyPathId, (metrics) => {
          metrics.topicsCompleted += 1;
        });
      }
    }
  }

  async function continueAfterCheckpoint() {
    if (!flowCheckpoint) return;

    if (flowCheckpoint.type === "topic_complete" && flowCheckpoint.nextTopic) {
      const nextTopic = flowCheckpoint.nextTopic;
      try {
        if (!isTopicLessonReady(nextTopic.id)) {
          const statusResult = await getTopicLessonStatus(nextTopic.id);
          setTopicLessonStatuses((prev) => ({
            ...prev,
            [nextTopic.id]: statusResult.generation_status,
          }));
          if (statusResult.generation_status !== "ready") {
            setStatus(
              `Next topic is still preparing: ${nextTopic.title}. You can review generated topics from the index while it finishes.`,
            );
            return;
          }
        }

        if (!lessonCacheRef.current[nextTopic.id]) {
          const nextLesson = await getTopicLesson(nextTopic.id);
          if (nextLesson.generation_status !== "ready") {
            setTopicLessonStatuses((prev) => ({
              ...prev,
              [nextTopic.id]: nextLesson.generation_status || "generating",
            }));
            setStatus(
              `Next topic is still preparing: ${nextTopic.title}. You can review generated topics from the index while it finishes.`,
            );
            return;
          }
          lessonCacheRef.current[nextTopic.id] = nextLesson;
          setTopicLessonStatuses((prev) => ({
            ...prev,
            [nextTopic.id]: "ready",
          }));
        }
      } catch (err) {
        console.error("Failed to verify next topic readiness:", err);
        setStatus(
          `Next topic is still preparing: ${nextTopic.title}. You can review generated topics from the index while it finishes.`,
        );
        return;
      }
      stepNavigationIntentRef.current = "auto";
      recordTransitionMetric(studyPathId, lastTransitionAtRef);
      setSelectedTopicId(nextTopic.id);
      setCurrentStepIndex(0);
      setFlowCheckpoint(null);
      setStatus(`Next up: ${nextTopic.title}.`);
      return;
    }

    router.push(`/study-paths/${studyPathId}`);
  }

  function takeBreakAtCheckpoint() {
    router.push(`/study-paths/${studyPathId}`);
  }

  function updateRecentPracticeLevel(level: string) {
    recentPracticeLevelsRef.current = [
      ...recentPracticeLevelsRef.current.slice(-3),
      level,
    ];

    if (level === "strong") {
      strongStreakRef.current += 1;
    } else {
      strongStreakRef.current = 0;
    }
  }

  function getLevelShiftTrigger(
    performanceLevel: string,
    confidenceValue: number,
  ) {
    const weakLikeCount = recentPracticeLevelsRef.current.filter((level) =>
      ["weak", "minor_mistake"].includes(level),
    ).length;

    if (
      ["weak", "minor_mistake"].includes(performanceLevel) &&
      (weakLikeCount >= 2 || confidenceValue <= 2)
    ) {
      return "weak_quick_check";
    }

    if (strongStreakRef.current >= 3 && confidenceValue >= 4) {
      return "strong_streak";
    }

    return null;
  }

  function getTargetAdjustmentForPracticeResult(
    performanceLevel: string,
    confidenceValue: number,
  ) {
    if (
      ["weak", "minor_mistake"].includes(performanceLevel) ||
      confidenceValue <= 2
    ) {
      return "repair";
    }

    if (strongStreakRef.current >= 3) {
      return "compress";
    }

    return "more_examples";
  }

  function canRegenerateFutureCards() {
    const now = Date.now();
    const cooldown = segmentRegenerationCooldownRef.current;

    return (
      now - cooldown.lastAt > 120000 &&
      safeCurrentStepIndex - cooldown.lastStepIndex >= 3
    );
  }

  function maybeRegenerateFutureCards({
    trigger,
    targetAdjustment,
    evidence,
  }: {
    trigger: string | null;
    targetAdjustment: string;
    evidence: Record<string, unknown>;
  }) {
    if (!trigger || !selectedTopic || !lesson || !canRegenerateFutureCards()) {
      return;
    }

    if (safeCurrentStepIndex >= lessonSteps.length - 2) {
      return;
    }

    void regenerateFutureCards({
      trigger,
      targetAdjustment,
      evidence,
    });
  }

  async function regenerateFutureCards({
    trigger,
    targetAdjustment,
    evidence,
  }: {
    trigger: string;
    targetAdjustment: string;
    evidence: Record<string, unknown>;
  }) {
    if (!selectedTopic || !lesson) return;

    try {
      setIsRegeneratingSegment(true);
      setSegmentAdaptationStatus("Azalea is adjusting the next few cards...");

      const lessonCards = Array.isArray(lessonJson.lesson_cards)
        ? lessonJson.lesson_cards
        : [];
      const completedCardIds = lessonCards
        .slice(0, safeCurrentStepIndex + 1)
        .map((card, index) => card.id || `card-${index + 1}`);

      const result = await regenerateTopicLessonSegment(selectedTopic.id, {
        lesson_id: lesson.id,
        current_card_index: safeCurrentStepIndex,
        completed_card_ids: completedCardIds,
        trigger,
        target_adjustment: targetAdjustment,
        learner_evidence: {
          ...evidence,
          pacing_mode: pacingMode,
          current_card_index: safeCurrentStepIndex,
          current_card_title: currentStep?.title ?? null,
        },
      });

      setLesson(result.lesson);
      lessonCacheRef.current[selectedTopic.id] = result.lesson;
      setSegmentAdaptationStatus(
        result.adaptation_message ||
          "Azalea adjusted the next few cards based on your recent work.",
      );
      segmentRegenerationCooldownRef.current = {
        lastAt: Date.now(),
        lastStepIndex: safeCurrentStepIndex,
      };
    } catch (err) {
      console.error(err);
      setSegmentAdaptationStatus("");
    } finally {
      setIsRegeneratingSegment(false);
    }
  }

  function handleTouchStart(event: TouchEvent<HTMLElement>) {
    const touch = event.touches[0];
    touchStartRef.current = { x: touch.clientX, y: touch.clientY };
  }

  function handleTouchEnd(event: TouchEvent<HTMLElement>) {
    const start = touchStartRef.current;
    touchStartRef.current = null;

    if (
      !start ||
      calibrationStep !== "lesson" ||
      isPageBusy ||
      reviewQuestion ||
      transferChallenge
    ) {
      return;
    }

    const touch = event.changedTouches[0];
    const deltaX = touch.clientX - start.x;
    const deltaY = touch.clientY - start.y;

    if (Math.abs(deltaX) < 60 || Math.abs(deltaX) < Math.abs(deltaY)) {
      return;
    }

    if (deltaX < 0) {
      void goToNextStep();
    } else {
      goToPreviousStep();
    }
  }

  async function handleSubmitSkipVerification() {
    if (!selectedTopic || !currentStep || !skipVerification?.answer.trim()) {
      return;
    }

    const answer = skipVerification.answer.trim();
    const strongAnswer =
      answer.length >= 24 &&
      /\b(because|means|when|so|therefore|example|step)\b/i.test(answer);

    await submitLearnerSignal({
      topic_id: selectedTopic.id,
      concept_name: currentStep.title,
      signal_type: "confidence",
      confidence: strongAnswer ? 0.9 : 0.35,
      summary: strongAnswer
        ? `Confirmed known card: ${currentStep.title}`
        : `Skip check suggested covering card: ${currentStep.title}`,
      metadata: {
        step_index: safeCurrentStepIndex,
        step_title: currentStep.title,
        skip_verification_answer: answer,
        confirmed_known: strongAnswer,
      },
    });

    if (strongAnswer) {
      recordFlowMetric(studyPathId, (metrics) => {
        metrics.skips += 1;
      });
      setSkipVerification(null);
      setAutoAdvanceStatus("Got it. Skipping ahead...");
      window.setTimeout(() => {
        setAutoAdvanceStatus("");
        void goToNextStep();
      }, 700);
      return;
    }

    setSkipVerification((prev) =>
      prev
        ? {
            ...prev,
            feedback: "Almost. This card is worth covering quickly.",
          }
        : prev,
    );
  }

  function insertClarificationFromQA() {
    if (!topicQAResponse) return;

    setInsertedClarification(topicQAResponse.answer);
    setActiveClarificationLabel("Manual question");
    setIsChatPanelOpen(false);
  }

  function renderRightPanel() {
    if (!rightPanel) return null;

    const isIndex = rightPanel === "index";

    return (
      <aside
        className={`fixed inset-y-0 z-40 w-full max-w-md bg-background shadow-xl transition-transform duration-200 ${
          isIndex
            ? "left-0 border-r border-border"
            : "right-0 border-l border-border"
        }`}
      >
        <div className="flex items-center justify-between border-b border-border p-4">
          <div>
            <p className="text-sm font-semibold text-foreground">
              {isIndex ? "Study path index" : "Regenerate"}
            </p>
            <p className="text-xs text-muted-foreground">
              {isIndex
                ? "Topics and subtopics"
                : "Give feedback to improve the content"}
            </p>
          </div>

          <button
            onClick={() => setRightPanel(null)}
            className="rounded-full border border-border px-3 py-1 text-sm font-semibold transition hover:bg-muted"
          >
            Close
          </button>
        </div>

        <div className="h-[calc(100vh-73px)] overflow-y-auto p-4">
          {isIndex ? renderIndexContent() : renderRegenerateContent()}
        </div>
      </aside>
    );
  }

  function renderIndexContent() {
    if (topics.length === 0) {
      return (
        <div className="rounded-2xl border border-dashed border-border bg-muted/30 p-4">
          <p className="text-sm font-semibold text-foreground">No topics yet</p>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">
            Generate the path to build your topic progression.
          </p>
        </div>
      );
    }

    const openIndexTopicId =
      expandedIndexTopicId === undefined
        ? selectedTopicId
        : expandedIndexTopicId;

    return (
      <div className="space-y-5">
        {groupedTopics.map((group) => (
          <div key={group.unitTitle}>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {group.unitTitle}
            </p>

            <div className="space-y-1">
              {group.topics.map((topic) => {
                const isCurrentTopic = topic.id === selectedTopicId;
                const isExpandedTopic = topic.id === openIndexTopicId;
                const lessonStatus = topicLessonStatuses[topic.id];
                const hasReadyLesson = isTopicLessonReady(topic.id);
                const isPreparing =
                  lessonStatus === "generating" ||
                  lessonStatus === "pending";
                const isLocked = !isCurrentTopic && !hasReadyLesson;

                return (
                  <div key={topic.id}>
                    <button
                      disabled={isLocked}
                      onClick={() => {
                        if (isLocked) return;
                        if (isExpandedTopic) {
                          setExpandedIndexTopicId(null);
                          return;
                        }

                        setExpandedIndexTopicId(topic.id);
                        if (isCurrentTopic) return;

                        stepNavigationIntentRef.current = "direct";
                        setFlowCheckpoint(null);
                        setSelectedTopicId(topic.id);
                        setCurrentStepIndex(0);
                        setCalibrationStep("lesson");
                        setStartingMode(null);
                        setAdaptationNote(null);
                        setSelfReportLevel(null);
                        setAdaptationNote(null);
                        setReviewQuestion(null);
                        setReviewAnswer("");
                        setReviewConfidence(3);
                        setReviewFeedback(null);
                        setTransferChallenge(null);
                        setTransferAnswer("");
                        setTransferConfidence(3);
                        setTransferFeedback(null);
                        setStatus("");
                      }}
                      className={`w-full rounded-xl px-3 py-2 text-left text-sm transition ${
                        isCurrentTopic
                          ? "bg-accent font-semibold text-primary"
                          : isLocked
                            ? "cursor-not-allowed text-muted-foreground/40"
                            : "text-foreground hover:bg-muted"
                      }`}
                    >
                      <span className="mr-2">
                        {topic.status === "completed"
                          ? "✓"
                          : isCurrentTopic
                            ? "→"
                            : isLocked
                              ? "🔒"
                              : "○"}
                      </span>
                      {topic.title.replace(/:+$/, "")}
                      {!isCurrentTopic && isPreparing && (
                        <span className="ml-2 text-[11px] font-semibold text-muted-foreground">
                          preparing
                        </span>
                      )}
                    </button>

                    {isExpandedTopic && isCurrentTopic && lessonSteps.length > 0 && (() => {
                      const seen = new Set<string>();
                      const dedupedSteps = lessonSteps.reduce<{ title: string; firstIndex: number; lastIndex: number }[]>(
                        (acc, step, index) => {
                          if (!seen.has(step.title)) {
                            seen.add(step.title);
                            acc.push({ title: step.title, firstIndex: index, lastIndex: index });
                          } else {
                            acc[acc.length - 1].lastIndex = index;
                          }
                          return acc;
                        },
                        [],
                      );
                      return (
                        <div className="ml-5 mt-1 space-y-1 border-l border-border pl-3">
                          {dedupedSteps.map((entry) => {
                            const isCurrent = safeCurrentStepIndex >= entry.firstIndex && safeCurrentStepIndex <= entry.lastIndex;
                            return (
                              <button
                                key={`${entry.title}-${entry.firstIndex}`}
                                onClick={() => {
                                  stepNavigationIntentRef.current = "direct";
                                  setCurrentStepIndex(entry.firstIndex);
                                  setRightPanel(null);
                                }}
                                className={`block w-full rounded-lg px-2 py-1.5 text-left text-xs transition ${
                                  isCurrent
                                    ? "bg-muted font-semibold text-foreground"
                                    : "text-muted-foreground hover:bg-muted"
                                }`}
                              >
                                {isCurrent ? "→" : "•"}{" "}
                                {entry.title}
                              </button>
                            );
                          })}
                        </div>
                      );
                    })()}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    );
  }

  function renderRegenerateContent() {
    return (
      <div className="rounded-2xl border border-border bg-muted/30 p-4">
        <h2 className="text-base font-bold text-foreground">
          Regenerate content
        </h2>
        <p className="mt-1 text-sm leading-6 text-muted-foreground">
          Tell Azalea what should change. You can update only this topic or
          rerender the full path.
        </p>

        <textarea
          value={regenerationFeedback}
          onChange={(e) => setRegenerationFeedback(e.target.value)}
          className="mt-4 min-h-32 w-full rounded-2xl border border-border bg-background px-4 py-3 text-sm text-foreground outline-none placeholder:text-muted-foreground focus:border-primary"
          placeholder="Example: make this more visual, add edge cases, focus more on practice..."
        />

        <div className="mt-3 grid gap-2">
          <button
            onClick={handleRegenerateCurrentTopic}
            disabled={
              !selectedTopicId || isRegeneratingTopic || isRegeneratingPath
            }
            className="rounded-2xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground transition hover:bg-foreground disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isRegeneratingTopic ? "Regenerating..." : "Regenerate Topic"}
          </button>

          <button
            onClick={handleRegeneratePath}
            disabled={isRegeneratingTopic || isRegeneratingPath}
            className="rounded-2xl border border-border bg-background px-4 py-3 text-sm font-semibold text-foreground transition hover:border-primary/40 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isRegeneratingPath ? "Regenerating..." : "Regenerate Full Path"}
          </button>
        </div>
      </div>
    );
  }

  function renderChatPanel() {
    return (
      <aside
        className={`fixed right-0 top-0 z-50 flex h-screen w-[420px] flex-col border-l border-border bg-background shadow-2xl transition-transform duration-300 ${
          isChatPanelOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Header */}
        <div className="flex shrink-0 items-center justify-between border-b border-border px-5 py-4">
          <div>
            <p className="text-sm font-semibold text-foreground">Ask Azalea</p>
            <p className="text-xs text-muted-foreground">
              {topicQAHistory.length > 0
                ? `${topicQAHistory.length} message${topicQAHistory.length === 1 ? "" : "s"}`
                : "Ask about this lesson"}
            </p>
          </div>
          <button
            onClick={() => setIsChatPanelOpen(false)}
            className="rounded-full border border-border p-2 text-muted-foreground transition hover:bg-muted hover:text-foreground"
            aria-label="Close chat"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M12 4L4 12M4 4l8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </button>
        </div>

        {/* Conversation thread */}
        <div
          ref={chatScrollRef}
          className="flex-1 overflow-y-auto px-4 py-4"
        >
          {topicQAHistory.length === 0 && !isAskingTopicQuestion && (
            <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-accent">
                <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
                  <path d="M11 2C6.03 2 2 5.69 2 10.25c0 2.56 1.26 4.84 3.25 6.35V20l3.5-1.75c.73.2 1.47.25 2.25.25 4.97 0 9-3.69 9-8.25S15.97 2 11 2Z" fill="currentColor" className="text-primary/20"/>
                  <path d="M7 10h2m2 0h2m-6 0a1 1 0 1 1-2 0 1 1 0 0 1 2 0Zm4 0a1 1 0 1 1-2 0 1 1 0 0 1 2 0Zm4 0a1 1 0 1 1-2 0 1 1 0 0 1 2 0Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" className="text-primary"/>
                </svg>
              </div>
              <p className="text-sm font-semibold text-foreground">Start a conversation</p>
              <p className="max-w-[240px] text-xs leading-5 text-muted-foreground">
                Ask anything about the current topic, a highlighted passage, or request an example.
              </p>
            </div>
          )}

          <div className="space-y-5">
            {topicQAHistory.map((item) => (
              <div key={item.id} className="space-y-3">
                {/* User message */}
                <div className="flex justify-end">
                  <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-primary px-4 py-3">
                    <p className="text-sm leading-6 text-primary-foreground">
                      {item.question}
                    </p>
                  </div>
                </div>

                {/* AI message */}
                <div className="flex justify-start">
                  <div className="max-w-[88%] rounded-2xl rounded-tl-sm border border-border bg-muted/30 px-4 py-3">
                    <p className="whitespace-pre-wrap text-sm leading-6 text-foreground">
                      {item.answer}
                    </p>
                  </div>
                </div>
              </div>
            ))}

            {/* Optimistic user bubble while waiting for response */}
            {pendingQuestion && (
              <div className="flex justify-end">
                <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-primary px-4 py-3">
                  <p className="text-sm leading-6 text-primary-foreground">
                    {pendingQuestion}
                  </p>
                </div>
              </div>
            )}

            {/* Loading indicator */}
            {isAskingTopicQuestion && (
              <div className="flex justify-start">
                <div className="rounded-2xl rounded-tl-sm border border-border bg-muted/30 px-4 py-3">
                  <div className="flex items-center gap-1">
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:-0.3s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:-0.15s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary" />
                  </div>
                </div>
              </div>
            )}

            {/* Follow-up actions after latest answer */}
            {topicQAResponse && !isAskingTopicQuestion && (
              <div className="flex flex-wrap gap-2 pl-1">
                <button
                  type="button"
                  onClick={() => void markCurrentClarificationResolved()}
                  className="rounded-full bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground transition hover:bg-foreground"
                >
                  Got it
                </button>
                <button
                  type="button"
                  onClick={askStillConfused}
                  className="rounded-full border border-border bg-background px-3 py-1.5 text-xs font-semibold transition hover:bg-muted"
                >
                  Still confused
                </button>
                <button
                  type="button"
                  onClick={insertClarificationFromQA}
                  className="rounded-full border border-border bg-background px-3 py-1.5 text-xs font-semibold transition hover:bg-muted"
                >
                  Insert clarification
                </button>
                <button
                  type="button"
                  onClick={() => {
                    void handleInstantClarification({
                      label: "Quick example",
                      question:
                        "Show one concrete example for the exact thing I asked about, then connect the example back to the current card.",
                      shouldAdaptFutureCards: false,
                    });
                  }}
                  className="rounded-full border border-border bg-background px-3 py-1.5 text-xs font-semibold transition hover:bg-muted"
                >
                  Show example
                </button>
                <button
                  type="button"
                  onClick={askForClarificationCheck}
                  className="rounded-full border border-border bg-background px-3 py-1.5 text-xs font-semibold transition hover:bg-muted"
                >
                  Test me
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Input area */}
        <div className="shrink-0 border-t border-border p-4">
          {/* Highlighted text preview */}
          {highlightedText && (
            <div className="mb-3 flex items-start justify-between gap-2 rounded-xl border border-primary/25 bg-accent/50 px-3 py-2">
              <p className="line-clamp-2 text-[11px] leading-4 text-foreground">
                <span className="font-semibold text-primary">
                  {activeVisualContext ? "Visual: " : "Highlight: "}
                </span>
                {highlightedText}
              </p>
              <button
                type="button"
                onClick={() => {
                  setHighlightedText("");
                  setSelectedTextForQuestion("");
                  setActiveVisualContext(null);
                  setActiveVisualLabel("");
                }}
                className="shrink-0 text-muted-foreground hover:text-foreground"
                aria-label="Clear highlight"
              >
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M9 3L3 9M3 3l6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                </svg>
              </button>
            </div>
          )}

          {/* Textarea + send button */}
          <form onSubmit={handleAskTopicQuestion} className="flex items-end gap-2">
            <textarea
              value={topicQuestion}
              onChange={(e) => {
                setTopicQuestion(e.target.value);
                if (!highlightedText) {
                  setSelectedTextForQuestion("");
                }
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void handleAskTopicQuestion({ preventDefault: () => {} } as FormEvent<HTMLFormElement>);
                }
              }}
              rows={2}
              className="flex-1 resize-none rounded-2xl border border-border bg-muted/30 px-4 py-3 text-sm text-foreground outline-none placeholder:text-muted-foreground focus:border-primary"
              placeholder="Ask a question… (Enter to send)"
            />
            <button
              type="submit"
              disabled={isAskingTopicQuestion || !selectedTopic || !topicQuestion.trim()}
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-primary text-primary-foreground transition hover:bg-foreground disabled:cursor-not-allowed disabled:opacity-50"
              aria-label="Send"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M8 13V3m0 0L3 8m5-5 5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          </form>
        </div>
      </aside>
    );
  }

  if (isCheckingAuth) {
    return (
      <main className="azalea-page-soft min-h-screen px-6 py-10 text-foreground">
        <div className="mx-auto flex min-h-[70vh] max-w-3xl items-center justify-center">
          <div className="azalea-surface-strong rounded-2xl border border-border p-8 text-center shadow-sm">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-accent">
              <Link href="/" aria-label="Go to Azalea home">
                <Image src="/Logo.png" alt="Azalea logo" width={40} height={40} />
              </Link>
            </div>
            <p className="text-sm font-semibold text-muted-foreground">
              Loading study path...
            </p>
          </div>
        </div>
      </main>
    );
  }

  if (v2LessonJson) {
    return (
      <HybridV2LegacyShell
        lesson={v2LessonJson}
        studyPathId={studyPathId}
        title={selectedTopic?.title || v2LessonJson.title || studyPath?.title || "Study path"}
        status={status}
      />
    );
  }

  return (
    <main className="h-screen overflow-hidden bg-[#FAF9FC] text-foreground">
      {(rightPanel || isChatPanelOpen) && (
        <button
          className="fixed inset-0 z-30 bg-black/10"
          onClick={() => {
            setRightPanel(null);
            setIsChatPanelOpen(false);
          }}
          aria-label="Close panels"
        />
      )}

      <header className="relative flex h-24 items-center justify-center border-b border-[#E6E1EE] bg-white/90 px-5 shadow-sm shadow-purple-100/30 backdrop-blur md:px-8">
        <div className="absolute left-5 flex items-center gap-2 md:left-8">
          <button
            onClick={() => setRightPanel("index")}
            className="inline-flex h-11 items-center gap-2 rounded-2xl border border-[#E1DCEA] bg-white px-4 text-sm font-black shadow-sm shadow-purple-100/30 transition hover:bg-[#F7F4FC]"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" aria-hidden="true">
              <path d="M8 6h13" />
              <path d="M8 12h13" />
              <path d="M8 18h13" />
              <path d="M3 6h.01" />
              <path d="M3 12h.01" />
              <path d="M3 18h.01" />
            </svg>
            Index
          </button>
          <Link
            href={`/study-paths/${studyPathId}`}
            className="inline-flex h-11 items-center gap-2 rounded-2xl border border-[#E1DCEA] bg-white px-4 text-sm font-black shadow-sm shadow-purple-100/30 transition hover:bg-[#F7F4FC]"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" aria-hidden="true">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <path d="M16 17l5-5-5-5" />
              <path d="M21 12H9" />
            </svg>
            Exit
          </Link>
        </div>

        <div className="flex min-w-0 max-w-[52rem] flex-col items-center gap-3 text-center">
          <p className="max-w-full truncate text-xl font-black tracking-tight text-foreground">
            {selectedTopic?.title || studyPath?.title || "Study path"}
          </p>
          <div className="flex items-center gap-2">
            <div className="h-2 w-72 rounded-full bg-[#E7E4E2]">
              <div
                className="h-2 rounded-full bg-primary shadow-sm shadow-primary/30 transition-all duration-500"
                style={{ width: `${calibrationStep === "lesson" ? lessonStepProgress : 0}%` }}
              />
            </div>
            <span className="min-w-10 text-sm font-black text-muted-foreground">
              {calibrationStep === "lesson" ? lessonStepProgress : 0}%
            </span>
          </div>
        </div>

        <div className="absolute right-5 md:right-8">
          <button
            onClick={() => setRightPanel("regenerate")}
            className="hidden h-11 items-center gap-2 rounded-2xl border border-primary/20 bg-white px-5 text-sm font-black text-foreground shadow-sm shadow-purple-100/40 transition hover:bg-[#F7F4FC] md:inline-flex"
          >
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.3" className="text-primary" aria-hidden="true">
              <path d="M12 2v4" />
              <path d="M12 18v4" />
              <path d="m4.93 4.93 2.83 2.83" />
              <path d="m16.24 16.24 2.83 2.83" />
              <path d="M2 12h4" />
              <path d="M18 12h4" />
              <path d="m4.93 19.07 2.83-2.83" />
              <path d="m16.24 7.76 2.83-2.83" />
            </svg>
            Regenerate
          </button>
        </div>
      </header>

      {(status ||
        practiceError ||
        isLoadingStudyPath ||
        preloadingStatus ||
        segmentAdaptationStatus ||
        autoAdvanceStatus) && (
        <div className="fixed left-1/2 top-32 z-20 w-[min(720px,calc(100vw-2rem))] -translate-x-1/2 space-y-2">
          {status && (
            <div className="rounded-2xl border border-primary/30 bg-accent px-4 py-3 text-sm font-medium text-foreground shadow-sm">
              {status}
            </div>
          )}
          {streamingPreviewCards.length > 0 && (
            <div className="rounded-2xl border border-primary/30 bg-white px-4 py-3 text-sm shadow-sm">
              <div className="mb-2 flex items-center gap-2 font-black text-primary">
                <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-primary" />
                Building your lesson… {streamingPreviewCards.length} card
                {streamingPreviewCards.length === 1 ? "" : "s"} ready
              </div>
              <ul className="max-h-64 space-y-1 overflow-y-auto">
                {streamingPreviewCards.map((card, index) => (
                  <li key={index} className="rounded-lg bg-[#F6F2FF] px-3 py-1.5">
                    <span className="font-bold text-foreground">{card.title || "Card"}</span>
                    {card.points[0] && (
                      <span className="ml-1 text-muted-foreground">
                        — {card.points[0].replace(/^\s*-\s*/, "")}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {practiceError && (
            <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700 shadow-sm">
              {practiceError}
            </div>
          )}
          {isLoadingStudyPath && (
            <div className="azalea-surface rounded-2xl border px-4 py-3 text-sm font-medium text-muted-foreground shadow-sm">
              Loading your study path...
            </div>
          )}
          {preloadingStatus && (
            <div className="azalea-surface rounded-2xl border px-4 py-3 text-sm font-medium text-muted-foreground shadow-sm">
              {preloadingStatus}
            </div>
          )}
          {autoAdvanceStatus && (
            <div className="rounded-2xl border border-primary/30 bg-accent px-4 py-3 text-sm font-medium text-foreground shadow-sm">
              {autoAdvanceStatus}
            </div>
          )}
          {segmentAdaptationStatus && (
            <div className="rounded-2xl border border-primary/30 bg-accent px-4 py-3 text-sm font-medium text-foreground shadow-sm">
              {segmentAdaptationStatus}
            </div>
          )}
        </div>
      )}

      <section
        onMouseUp={handleLessonTextSelection}
        onKeyUp={handleLessonTextSelection}
        onTouchStart={handleTouchStart}
        onTouchEnd={(event) => {
          handleLessonTextSelection();
          handleTouchEnd(event);
        }}
        className={`relative flex overflow-hidden ${calibrationStep === "lesson" && !flowCheckpoint && lesson && currentStep ? "h-[calc(100vh-176px)] bg-[#F6F4FA] p-4" : "h-[calc(100vh-96px)]"}`}
      >
        {calibrationStep === "lesson" && !flowCheckpoint && lesson && currentStep && (currentV2FocusVisual || currentFocusVisual) ? (
          // WORKSPACE: context + visual (left) + guidance panel (right)
          <div className="grid h-full w-full grid-cols-[minmax(0,1.8fr)_minmax(22rem,0.95fr)] gap-5">
            {/* LEFT: step context + persistent visual */}
            <div className="flex min-h-0 min-w-0 flex-col overflow-hidden rounded-2xl border border-[#E5DFEE] bg-white shadow-sm shadow-purple-100/40">
              {/* Step header: type label + title + description */}
              <div className="px-7 pb-4 pt-6">
                <div className="mb-5 flex items-center gap-3">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="shrink-0 text-primary">
                    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
                  </svg>
                  <span className="text-[12px] font-black uppercase tracking-widest text-primary">
                    {getStepTypeLabel(currentStep)}
                  </span>
                  {currentStep.type === "flow_card" && currentStep.card?.learning_job && (
                    <>
                      <span className="text-xs text-primary/35">|</span>
                      <span className="text-sm font-semibold text-muted-foreground">{currentStep.card.learning_job}</span>
                    </>
                  )}
                </div>
                <h2 className="text-[1.75rem] font-black leading-tight tracking-tight text-foreground md:text-[2rem]">
                  {currentStep.title}
                </h2>
                {currentStep.type === "flow_card" && (currentStep.body[0] ?? currentStep.card?.what_to_notice) && (
                  <p className="mt-3 max-w-4xl text-base leading-relaxed text-muted-foreground">
                    {currentStep.body[0] ?? currentStep.card?.what_to_notice}
                  </p>
                )}
              </div>

              {/* Visual workspace */}
              <div className="azalea-visual-scroll min-h-0 flex-1 overflow-y-auto px-7 pb-6 pr-5">
                <div className="flex min-h-full items-start justify-center py-2">
                <div
                  key={
                    currentV2FocusVisual
                      ? `focus-v2-${safeCurrentStepIndex}-${currentV2FocusVisual.model.id}-${currentV2FocusVisual.frameIndex}`
                      : `focus-${safeCurrentStepIndex}-${currentFocusVisual?.type}-${currentFocusVisual?.title}`
                  }
                  className="w-full"
                >
                  {currentV2FocusVisual ? (
                    <div className="w-full rounded-2xl border border-[#E5DFF0] bg-white p-3 shadow-sm shadow-purple-100/40">
                      {/* A single border around the whole visual; no inner
                          scroller, so the visual fills the workspace width and
                          the left workspace itself is the one scroll container. */}
                      {(() => {
                        // Strict slot separation: the Diagram view renders ONLY a real
                        // diagram (diagram_v2_ref); the Code view renders ONLY code. The
                        // toggle appears only when BOTH exist, so "Diagram" can never
                        // fall back to showing code (and vice versa).
                        const diagramAvailable = !!currentV2DiagramVisual;
                        const codeAvailable = !!workedExampleCode;
                        const view =
                          workedExampleVisualView === "diagram" && diagramAvailable
                            ? "diagram"
                            : workedExampleVisualView === "code" && codeAvailable
                              ? "code"
                              : diagramAvailable
                                ? "diagram"
                                : codeAvailable
                                  ? "code"
                                  : "focus";
                        return (
                          <>
                            {diagramAvailable && codeAvailable && (
                              <div className="mb-3 flex justify-center">
                                <div className="inline-flex items-center gap-1 rounded-full border border-[#E5DFF0] bg-[#F6F2FF] p-1">
                                  {(["diagram", "code"] as const).map((v) => {
                                    const active = view === v;
                                    return (
                                      <button
                                        key={v}
                                        type="button"
                                        onClick={() => setWorkedExampleVisualView(v)}
                                        className={[
                                          "rounded-full px-4 py-1.5 text-sm font-black transition",
                                          active
                                            ? "bg-primary text-primary-foreground shadow-sm"
                                            : "text-primary hover:bg-white",
                                        ].join(" ")}
                                      >
                                        {v === "diagram" ? "Diagram" : "</> Code"}
                                      </button>
                                    );
                                  })}
                                </div>
                              </div>
                            )}
                            {view === "diagram" && currentV2DiagramVisual ? (
                              <V2VisualRenderer
                                model={currentV2DiagramVisual.model}
                                frameIndex={currentV2DiagramVisual.frameIndex}
                                onElementClick={(element) => {
                                  const frame =
                                    currentV2DiagramVisual.model.frames[currentV2DiagramVisual.frameIndex] ??
                                    currentV2DiagramVisual.model.frames[0];
                                  if (frame) {
                                    handleLegacyV2VisualClick(element, currentV2DiagramVisual.model, frame);
                                  }
                                }}
                                selectedElementId={activeVisualContext?.element.element_id ?? null}
                              />
                            ) : view === "code" && workedExampleCode ? (
                              <div className="overflow-hidden rounded-2xl border border-[#E2DDEC] bg-white shadow-sm">
                                <div className="flex items-center justify-between border-b border-[#E8E3EF] px-4 py-3">
                                  <span className="text-sm font-black text-foreground">
                                    {workedExampleCode.language}
                                  </span>
                                  {workedExampleCode.highlight && (
                                    <span className="rounded-full border border-primary/15 bg-[#F3EEFF] px-3 py-1 text-[11px] font-black text-primary">
                                      Active line{workedExampleCode.highlight[0] !== workedExampleCode.highlight[1] ? "s" : ""}{" "}
                                      {workedExampleCode.highlight[0]}
                                      {workedExampleCode.highlight[1] !== workedExampleCode.highlight[0]
                                        ? `–${workedExampleCode.highlight[1]}`
                                        : ""}
                                    </span>
                                  )}
                                </div>
                                <CodeWithHighlight
                                  code={workedExampleCode.code}
                                  language={workedExampleCode.language}
                                  highlightLines={workedExampleCode.highlight}
                                  variant="light"
                                  showHeader={false}
                                />
                              </div>
                            ) : (
                              <V2VisualRenderer
                                model={currentV2FocusVisual.model}
                                frameIndex={currentV2FocusVisual.frameIndex}
                                onElementClick={(element) => {
                                  const frame =
                                    currentV2FocusVisual.model.frames[currentV2FocusVisual.frameIndex] ??
                                    currentV2FocusVisual.model.frames[0];
                                  if (frame) {
                                    handleLegacyV2VisualClick(element, currentV2FocusVisual.model, frame);
                                  }
                                }}
                                selectedElementId={activeVisualContext?.element.element_id ?? null}
                              />
                            )}
                          </>
                        );
                      })()}
                    </div>
                  ) : currentFocusVisual ? (
                    <VisualRenderer visual={currentFocusVisual} index={0} focusState={currentVisualFocus} />
                  ) : currentStep.type === "flow_card" &&
                    currentStep.card?.blueprint_key === "worked_example" ? (
                    (() => {
                      // No drawn visual for this worked example. Show the RICH intended-visual
                      // description (what the figure SHOULD show) in the visual space — the
                      // Phase-2 spec — falling back to the step text if none was authored.
                      const vd = String(
                        (currentStep.card as { visual_description?: string } | undefined)
                          ?.visual_description ?? "",
                      ).trim();
                      if (vd) {
                        return (
                          <VisualDataPanel
                            title="Intended visual (not drawn yet)"
                            sections={[{ label: "What the figure should show", value: vd }]}
                          />
                        );
                      }
                      const pts = ((currentStep.card?.points as string[] | undefined) ??
                        currentStep.bullets ??
                        []) as string[];
                      if (!pts.length) return null;
                      return (
                        <div className="w-full rounded-2xl border border-[#E5DFF0] bg-white p-6 shadow-sm shadow-purple-100/40">
                          <ol className="space-y-3">
                            {pts.map((point, i) => (
                              <li key={i} className="flex gap-3 text-[15px] leading-relaxed text-foreground">
                                <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-black text-primary">
                                  {i + 1}
                                </span>
                                <span>{String(point)}</span>
                              </li>
                            ))}
                          </ol>
                        </div>
                      );
                    })()
                  ) : null}
                </div>
                </div>
              </div>
            </div>

            {/* RIGHT: guidance panel */}
            <div className="flex min-h-0 min-w-0 flex-col overflow-hidden rounded-2xl border border-[#E5DFEE] bg-white shadow-sm shadow-purple-100/40">
              {/* Panel header */}
              <div className="flex shrink-0 items-center gap-3 px-6 pb-4 pt-6">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="shrink-0 text-primary">
                  <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
                </svg>
                <h3 className="text-lg font-black text-primary">What&apos;s happening here?</h3>
              </div>

              {/* Scrollable content */}
              <div ref={cardScrollContainerRef} className="azalea-sidebar-scroll min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 pb-5 pr-3">
                {memorySummary &&
                  !reviewQuestion &&
                  (memorySummary.concepts_to_skip.length > 0 ||
                    memorySummary.concepts_to_briefly_repair.length > 0) && (
                    <AdaptationExplanationBanner
                      className="mb-4 bg-background"
                      title="Building from what you know"
                      message="Azalea is using your prior progress to avoid reteaching stable concepts unless they are needed."
                      details={
                        memorySummary.recommended_lesson_guidance ||
                        "Azalea checks stable, transferable, and fragile concepts from earlier topics before deciding how much to explain here."
                      }
                    />
                  )}

                {reviewQuestion && (
                  <ReviewQuestionCard
                    reviewQuestion={reviewQuestion}
                    answer={reviewAnswer}
                    confidence={reviewConfidence}
                    feedback={reviewFeedback}
                    isSubmitting={isSubmittingReviewAnswer}
                    onAnswerChange={setReviewAnswer}
                    onConfidenceChange={setReviewConfidence}
                    onSubmit={handleSubmitReviewAnswer}
                  />
                )}

                {transferChallenge && (
                  <TransferChallengeCard
                    challenge={transferChallenge}
                    answer={transferAnswer}
                    confidence={transferConfidence}
                    feedback={transferFeedback}
                    isSubmitting={isSubmittingTransferChallenge}
                    onAnswerChange={setTransferAnswer}
                    onConfidenceChange={setTransferConfidence}
                    onSubmit={handleSubmitTransferChallenge}
                  />
                )}

                {!reviewQuestion && !transferChallenge && (
                  <>
                    {insertedClarification && (
                      <div className="mb-4 rounded-2xl border border-primary/20 bg-accent p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="text-sm font-bold text-foreground">
                              {activeClarificationLabel || "Clarification"}
                            </p>
                            <p className="mt-1 text-xs font-semibold text-primary">
                              Resolved inline so the lesson can keep moving.
                            </p>
                          </div>
                          <button
                            type="button"
                            onClick={() => {
                              setInsertedClarification("");
                              setActiveClarificationLabel("");
                            }}
                            className="text-xs font-semibold text-primary"
                          >
                            Dismiss
                          </button>
                        </div>
                        <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-foreground">
                          {insertedClarification}
                        </p>
                        <div className="mt-3 flex flex-wrap gap-2">
                          <button
                            type="button"
                            onClick={() => void markCurrentClarificationResolved()}
                            className="rounded-2xl bg-background px-4 py-2 text-xs font-semibold text-primary"
                          >
                            This resolved it
                          </button>
                          <button
                            type="button"
                            onClick={askStillConfused}
                            disabled={isAskingTopicQuestion}
                            className="rounded-2xl border border-border bg-background px-4 py-2 text-xs font-semibold text-foreground disabled:opacity-60"
                          >
                            Still confused
                          </button>
                          <button
                            type="button"
                            onClick={askForClarificationCheck}
                            disabled={isAskingTopicQuestion}
                            className="rounded-2xl border border-border bg-background px-4 py-2 text-xs font-semibold text-foreground disabled:opacity-60"
                          >
                            Test me
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Numbered bordered bullet cards */}
                    {(() => {
                      const pts = currentStep.type === "flow_card" ? currentStep.bullets : [];
                      const tree = buildBulletTree(pts);
                      const revealFromIndex =
                        currentStep.type === "flow_card" ? (currentStep.revealFromIndex ?? 0) : 0;
                      const shouldAnimateReveal = revealFromIndex > 0 && pts.length > revealFromIndex;
                      if (!tree.length) return null;
                      const shouldNumberMainBullets = tree.length > 1;
                      return (
                        <div className="space-y-3">
                          {tree.map((node, i) => {
                            const isNew = shouldAnimateReveal && node.index >= revealFromIndex;
                            const animationStyle = isNew
                              ? {
                                  animation:
                                    "ideaRevealIn 0.42s cubic-bezier(0.2, 0.8, 0.2, 1) both, ideaRevealFocus 0.9s ease-out both",
                                }
                              : undefined;
                            return (
                              <div
                                key={`${node.text}-${node.index}`}
                                className="rounded-2xl border border-[#E5DFEE] bg-white p-5 shadow-sm shadow-purple-100/30"
                                style={animationStyle}
                              >
                                <div className="flex items-start gap-4">
                                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-black text-primary-foreground shadow-sm shadow-primary/30">
                                    {shouldNumberMainBullets ? (
                                      i + 1
                                    ) : (
                                      <span
                                        aria-hidden="true"
                                        className="h-2.5 w-2.5 rounded-full bg-primary-foreground"
                                      />
                                    )}
                                  </span>
                                  <div className="min-w-0 flex-1">
                                    <p className="text-base font-black leading-6 text-foreground">
                                      {formatParentBulletText(node)}
                                    </p>
                                    {node.children.length > 0 && (
                                      <WorkspaceBulletChildren
                                        nodes={node.children}
                                        revealFromIndex={revealFromIndex}
                                        shouldAnimateReveal={shouldAnimateReveal}
                                      />
                                    )}
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      );
                    })()}

                    {/* Micro-check at bottom */}
                    {currentStep.type === "flow_card" && currentStep.card?.micro_check?.prompt && (
                      <div className="mt-4">
                        <MicrocheckReveal
                          microCheck={currentStep.card.micro_check}
                          onAskAboutText={(text) =>
                            void handleInstantClarification({
                              label: "Card highlight",
                              question:
                                "Explain this part of the current card plainly, including why it matters and what I might be misunderstanding.",
                              selectedText: text,
                            })
                          }
                        />
                      </div>
                    )}

                    {skipVerification?.stepIndex === safeCurrentStepIndex && (
                      <div className="mt-5 rounded-2xl border border-border bg-background p-4">
                        <p className="text-sm font-bold text-foreground">Tiny verification</p>
                        <p className="mt-1 text-sm leading-6 text-muted-foreground">
                          Explain the main idea in one sentence.
                        </p>
                        <textarea
                          value={skipVerification.answer}
                          onChange={(event) =>
                            setSkipVerification((prev) =>
                              prev ? { ...prev, answer: event.target.value } : prev,
                            )
                          }
                          className="mt-3 min-h-20 w-full rounded-2xl border border-border bg-background px-4 py-3 text-sm outline-none focus:border-primary"
                          placeholder="I already know this because..."
                        />
                        {skipVerification.feedback && (
                          <p className="mt-2 text-sm font-semibold text-primary">
                            {skipVerification.feedback}
                          </p>
                        )}
                        <div className="mt-3 flex flex-wrap gap-2">
                          <button
                            type="button"
                            onClick={handleSubmitSkipVerification}
                            className="rounded-2xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground"
                          >
                            Verify and skip
                          </button>
                          <button
                            type="button"
                            onClick={() => setSkipVerification(null)}
                            className="rounded-2xl border border-border px-4 py-2 text-sm font-semibold"
                          >
                            Cover it quickly
                          </button>
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
        ) : (
          // CENTERED LAYOUT for non-lesson states
          <div className="flex h-full w-full flex-col items-center justify-center px-20 py-6">
            <div className="azalea-surface flex max-h-[88vh] w-full max-w-4xl flex-col rounded-[2rem] border p-8 shadow-lg md:p-10">
              <div className="mb-5 flex items-center justify-between gap-3 md:hidden">
                <button
                  onClick={goToPreviousStep}
                  disabled={
                    calibrationStep !== "lesson" || (!flowCheckpoint && safeCurrentStepIndex === 0)
                  }
                  className="rounded-full border border-border bg-background px-4 py-2 text-sm font-semibold transition hover:bg-muted disabled:opacity-40"
                >
                  Back
                </button>
                <button
                  onClick={goToNextStep}
                  disabled={
                    !lesson ||
                    lessonSteps.length === 0 ||
                    calibrationStep !== "lesson" ||
                    shouldBlockFinishTopic ||
                    Boolean(flowCheckpoint) ||
                    Boolean(reviewQuestion || transferChallenge)
                  }
                  className="rounded-full bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition hover:bg-foreground disabled:opacity-40"
                >
                  {continueButtonLabel}
                </button>
              </div>

              <div
                ref={cardScrollContainerRef}
                className="min-h-0 flex-1 overflow-y-auto pr-1"
              >
                {topics.length === 0 && (
              <div className="py-12 text-center">
                <p className="text-lg font-semibold text-foreground">
                  No topics generated yet
                </p>
                <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted-foreground">
                  Generate a full progression to start learning in this path.
                </p>
                <div className="mt-5 flex justify-center gap-3">
                  <button
                    onClick={handleGenerateTopics}
                    disabled={isGeneratingTopics || isGeneratingFullPath}
                    className="rounded-2xl border border-border bg-background px-5 py-3 text-sm font-semibold transition hover:bg-muted disabled:opacity-60"
                  >
                    {isGeneratingTopics ? "Generating..." : "Generate Topics"}
                  </button>
                  <button
                    onClick={handleGenerateFullStudyPath}
                    disabled={isGeneratingFullPath || isGeneratingTopics}
                    className="rounded-2xl bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground transition hover:bg-foreground disabled:opacity-60"
                  >
                    {isGeneratingFullPath
                      ? "Generating..."
                      : "Generate Full Path"}
                  </button>
                </div>
              </div>
            )}

            {topics.length > 0 && !selectedTopic && (
              <EmptyLearningState
                title="No topic selected"
                description="Open the index and choose a topic to begin."
              />
            )}

            {selectedTopic && !lesson && (
              <div className="py-12 text-center">
                <p className="text-lg font-semibold text-foreground">
                  No lesson generated yet
                </p>
                <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted-foreground">
                  Generate a structured Azalea lesson to start this topic
                  progression.
                </p>
                <button
                  onClick={handleGenerateLesson}
                  disabled={isGeneratingLesson || isGeneratingFullPath}
                  className="mt-5 rounded-2xl bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground shadow-sm transition hover:bg-foreground disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isGeneratingLesson ? "Generating..." : "Generate Lesson"}
                </button>
              </div>
            )}

            {flowCheckpoint && (
              <FlowCheckpointCard
                checkpoint={flowCheckpoint}
                currentRunEstimatedMinutes={currentRunEstimatedMinutes}
                metrics={getFlowMetrics(studyPathId)}
                weakAreas={pathWeakAreas}
                onContinue={continueAfterCheckpoint}
                canContinue={checkpointCanContinue}
                continueDisabledReason={checkpointContinueDisabledReason}
                onBack={goToPreviousStep}
                onTakeBreak={takeBreakAtCheckpoint}
              />
            )}

            {!flowCheckpoint &&
              lesson &&
              selectedTopic &&
              calibrationStep === "calibration" && (
              <TopicCalibrationCard
                topicId={selectedTopic.id}
                onCalibrated={(result) => {
                  setSelfReportLevel(result.selfReportLevel ?? null);
                  beginLessonWithMode(result.recommendedStartingMode);
                }}
                onStartDiagnostic={(level) => {
                  setSelfReportLevel(level ?? null);
                  setCalibrationStep("diagnostic");
                }}
                onJumpToPractice={() => {
                  beginLessonWithMode("transfer_practice");
                }}
              />
            )}

            {!flowCheckpoint &&
              lesson &&
              selectedTopic &&
              calibrationStep === "diagnostic" && (
              <DiagnosticMiniFlow
                topicId={selectedTopic.id}
                selfReportLevel={selfReportLevel}
                onBack={() => setCalibrationStep("calibration")}
                onComplete={(result) => {
                  setStartingMode(result.recommendedStartingMode);
                  setAdaptationNote(
                    result.resultSummary ||
                      getAdaptationNoteForStartingMode(
                        result.recommendedStartingMode,
                      ),
                  );
                  setCalibrationStep("lesson");

                  if (result.recommendedStartingMode === "transfer_practice") {
                    setCurrentStepIndex(firstPracticeStepIndex);
                  } else {
                    setCurrentStepIndex(0);
                  }
                }}
              />
            )}

            {!flowCheckpoint &&
              lesson &&
              currentStep &&
              calibrationStep === "lesson" && (
              <div className="flex min-h-[56vh] flex-col items-center justify-center text-center">
                {memorySummary &&
                  !reviewQuestion &&
                  (memorySummary.concepts_to_skip.length > 0 ||
                    memorySummary.concepts_to_briefly_repair.length > 0) && (
                    <AdaptationExplanationBanner
                      className="mx-auto mb-5 max-w-3xl bg-background"
                      title="Building from what you know"
                      message="Azalea is using your prior progress to avoid reteaching stable concepts unless they are needed."
                      details={
                        memorySummary.recommended_lesson_guidance ||
                        "Azalea checks stable, transferable, and fragile concepts from earlier topics before deciding how much to explain here."
                      }
                    />
                  )}

                {reviewQuestion && (
                  <ReviewQuestionCard
                    reviewQuestion={reviewQuestion}
                    answer={reviewAnswer}
                    confidence={reviewConfidence}
                    feedback={reviewFeedback}
                    isSubmitting={isSubmittingReviewAnswer}
                    onAnswerChange={setReviewAnswer}
                    onConfidenceChange={setReviewConfidence}
                    onSubmit={handleSubmitReviewAnswer}
                  />
                )}

                {transferChallenge && (
                  <TransferChallengeCard
                    challenge={transferChallenge}
                    answer={transferAnswer}
                    confidence={transferConfidence}
                    feedback={transferFeedback}
                    isSubmitting={isSubmittingTransferChallenge}
                    onAnswerChange={setTransferAnswer}
                    onConfidenceChange={setTransferConfidence}
                    onSubmit={handleSubmitTransferChallenge}
                  />
                )}

                {!reviewQuestion && !transferChallenge && (
                  <>
                    {currentStep && renderLearningStep(currentStep, true)}

                    {insertedClarification && (
                      <div className="mx-auto mt-5 max-w-3xl rounded-2xl border border-primary/20 bg-accent p-4 text-left">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="text-sm font-bold text-foreground">
                              {activeClarificationLabel || "Clarification"}
                            </p>
                            <p className="mt-1 text-xs font-semibold text-primary">
                              Resolved inline so the lesson can keep moving.
                            </p>
                          </div>
                          <button
                            type="button"
                            onClick={() => {
                              setInsertedClarification("");
                              setActiveClarificationLabel("");
                            }}
                            className="text-xs font-semibold text-primary"
                          >
                            Dismiss
                          </button>
                        </div>
                        <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-foreground">
                          {insertedClarification}
                        </p>
                        <div className="mt-4 flex flex-wrap gap-2">
                          <button
                            type="button"
                            onClick={() => void markCurrentClarificationResolved()}
                            className="rounded-2xl bg-background px-4 py-2 text-xs font-semibold text-primary"
                          >
                            This resolved it
                          </button>
                          <button
                            type="button"
                            onClick={askStillConfused}
                            disabled={isAskingTopicQuestion}
                            className="rounded-2xl border border-border bg-background px-4 py-2 text-xs font-semibold text-foreground disabled:opacity-60"
                          >
                            Still confused
                          </button>
                          <button
                            type="button"
                            onClick={askForClarificationCheck}
                            disabled={isAskingTopicQuestion}
                            className="rounded-2xl border border-border bg-background px-4 py-2 text-xs font-semibold text-foreground disabled:opacity-60"
                          >
                            Test me
                          </button>
                        </div>
                      </div>
                    )}

                    {skipVerification?.stepIndex === safeCurrentStepIndex && (
                      <div className="mx-auto mt-5 max-w-2xl rounded-2xl border border-border bg-background p-4 text-left">
                        <p className="text-sm font-bold text-foreground">
                          Tiny verification
                        </p>
                        <p className="mt-1 text-sm leading-6 text-muted-foreground">
                          Explain the main idea in one sentence.
                        </p>
                        <textarea
                          value={skipVerification.answer}
                          onChange={(event) =>
                            setSkipVerification((prev) =>
                              prev
                                ? { ...prev, answer: event.target.value }
                                : prev,
                            )
                          }
                          className="mt-3 min-h-20 w-full rounded-2xl border border-border bg-background px-4 py-3 text-sm outline-none focus:border-primary"
                          placeholder="I already know this because..."
                        />
                        {skipVerification.feedback && (
                          <p className="mt-2 text-sm font-semibold text-primary">
                            {skipVerification.feedback}
                          </p>
                        )}
                        <div className="mt-3 flex flex-wrap gap-2">
                          <button
                            type="button"
                            onClick={handleSubmitSkipVerification}
                            className="rounded-2xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground"
                          >
                            Verify and skip
                          </button>
                          <button
                            type="button"
                            onClick={() => setSkipVerification(null)}
                            className="rounded-2xl border border-border px-4 py-2 text-sm font-semibold"
                          >
                            Cover it quickly
                          </button>
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
              </div>
            </div>
          </div>
        )}
      </section>

      {/* Bottom navigation bar — only for lesson workspace */}
      {calibrationStep === "lesson" && !flowCheckpoint && lesson && currentStep && (
        <div className="flex h-20 shrink-0 items-center justify-between border-t border-[#E5DFEE] bg-white px-7 shadow-[0_-8px_24px_rgba(46,38,80,0.04)]">
          <button
            onClick={goToPreviousStep}
            disabled={safeCurrentStepIndex === 0}
            className="flex h-12 min-w-32 items-center justify-center gap-2 rounded-2xl border border-[#E1DCEA] bg-white px-5 text-sm font-black text-foreground shadow-sm transition hover:bg-[#F7F4FC] disabled:opacity-40"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
              <path d="M15 18l-6-6 6-6" />
            </svg>
            Back
          </button>

          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                setActiveVisualContext(null);
                setActiveVisualLabel("");
                setIsChatPanelOpen(true);
              }}
              className="flex h-12 min-w-32 items-center justify-center gap-2 rounded-2xl border border-[#E1DCEA] bg-white px-5 text-sm font-black text-foreground shadow-sm transition hover:bg-[#F7F4FC]"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
              Chat
            </button>
          </div>

          <div className="flex flex-col items-end gap-1">
            <button
              onClick={goToNextStep}
              disabled={
                !lesson ||
                lessonSteps.length === 0 ||
                shouldBlockFinishTopic ||
                Boolean(reviewQuestion || transferChallenge)
              }
              className="flex h-12 min-w-36 items-center justify-center gap-2 rounded-2xl bg-primary px-6 text-sm font-black text-primary-foreground shadow-lg shadow-primary/20 transition hover:bg-foreground disabled:cursor-not-allowed disabled:opacity-40"
            >
              {continueButtonLabel}
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
                <path d="M9 18l6-6-6-6" />
              </svg>
            </button>
          </div>
        </div>
      )}

      {renderRightPanel()}
      {renderChatPanel()}
    </main>
  );
}

function withCardSynchronizedCodeVisual(
  visual: VisualPlanItem,
  step: LearningStep,
): VisualPlanItem {
  const type = normalizeVisualType(visual.type);
  if (
    step.type !== "flow_card" ||
    !isCodeTraceVisualType(type) ||
    (!step.highlightLines && !step.maxCodeLine)
  ) {
    return visual;
  }

  return {
    ...visual,
    highlight_lines: step.highlightLines,
    max_line: step.maxCodeLine,
  };
}

function codeVisualFromCard(card?: LessonFlowCard): VisualPlanItem | undefined {
  const code = card?.code_snippet?.trim();
  if (card?.blueprint_key !== "code_walkthrough" || !code) {
    return undefined;
  }

  return {
    type: "code_trace",
    title: card.title || "Code walkthrough",
    purpose: card.learning_job || card.main_concept || "Implementation so far",
    description: card.visual_description || "",
    code,
    language: card.code_language || "python",
  };
}

function workedExampleCodeVisualFromCard(card?: LessonFlowCard): VisualPlanItem | undefined {
  const code = card?.code_snippet?.trim();
  const isWorkedExample = card?.blueprint_key === "worked_example";
  if (!isWorkedExample || !code) {
    return undefined;
  }

  return {
    type: "code_trace",
    title: "Executing code",
    purpose: card.title || "Completed implementation",
    description: card.visual_description || "",
    code,
    language: card.code_language || "python",
  };
}

function codingWorkedExampleCompositeVisual(
  runtimeVisual: VisualPlanItem | undefined,
  codeVisual: VisualPlanItem | undefined,
): VisualPlanItem | undefined {
  if (!codeVisual) return runtimeVisual;

  const children = [runtimeVisual, codeVisual].filter(
    (item): item is VisualPlanItem => {
      if (!item) return false;
      return isLessonVisualRenderable(item);
    },
  );

  if (children.length <= 1) return children[0];

  return {
    type: "runtime_code_trace",
    title: runtimeVisual?.title || codeVisual.title || "Runtime and code",
    purpose: runtimeVisual?.purpose || codeVisual.purpose || "",
    description: runtimeVisual?.description || "",
    children,
  };
}

function isLessonVisualRenderable(visual: VisualPlanItem): boolean {
  const type = normalizeVisualType(visual.type);

  if (isCompositeVisualType(type)) {
    return Boolean(visual.children?.some((child) => isLessonVisualRenderable(child)));
  }

  // Each visual type requires actual STRUCTURAL content to be renderable.
  // We deliberately do NOT use a `hasFallbackContent` (title/description/
  // purpose/what_to_notice) escape hatch — those are metadata the LLM
  // always fills, so accepting them as "renderable" surfaces empty visuals
  // as prose blocks. Practice_feedback is the one exception: it is
  // intentionally a lightweight placeholder until the learner answers.
  if (isPracticeFeedbackVisualType(type)) {
    return true;
  }

  if (isNodeLinkVisualType(type)) {
    return Boolean(visual.nodes?.length && visual.nodes.length >= 2);
  }

  if (isCircuitVisualType(type)) {
    return Boolean(visual.components?.length || visual.wires?.length);
  }

  if (isGraphVisualType(type)) {
    return Boolean(visual.data_points && visual.data_points.length >= 2);
  }

  if (isCodeTraceVisualType(type)) {
    return Boolean(visual.code);
  }

  if (isArrayStateVisualType(type)) {
    return Boolean(visual.array_values?.length || visual.array_rows?.length);
  }

  if (isSpatialVisualType(type)) {
    return Boolean(hasSpatialVisualData(visual));
  }

  if (isInteractiveVisualType(type)) {
    return Boolean(hasInteractiveVisualData(visual));
  }

  if (isFormulaVisualType(type)) {
    return Boolean(visual.formula || visual.symbols?.length);
  }

  if (isTableVisualType(type)) {
    return Boolean(visual.columns?.length && visual.rows?.length);
  }

  if (isProgressiveStepFlowVisualType(type) || isFlowVisualType(type) || isCausalChainVisualType(type)) {
    return Boolean(visual.steps?.length);
  }

  if (isPathProgressVisualType(type)) {
    return Boolean(visual.steps?.length);
  }

  if (isConceptMapVisualType(type)) {
    return Boolean(visual.center || visual.nodes?.length);
  }

  if (isMisconceptionVisualType(type)) {
    return Boolean(visual.wrong && visual.correct);
  }

  if (isSourceAnnotationVisualType(type)) {
    return Boolean(visual.steps?.length || visual.nodes?.length);
  }

  return false;
}

function MathText({ text }: { text: string }) {
  return <>{renderMathText(text)}</>;
}

function LinkedMathText({
  text,
  links,
  onAskAboutText,
}: {
  text: string;
  links: LessonInteractiveLink[];
  onAskAboutText: (text: string) => void;
}) {
  const parts = splitTextByInteractiveLinks(text, links);

  if (parts.length === 1 && parts[0].type === "text") {
    return <MathText text={text} />;
  }

  return (
    <>
      {parts.map((part, index) => {
        if (part.type === "text") {
          return <MathText key={`${part.text}-${index}`} text={part.text} />;
        }

        return (
          <InteractiveLinkPopup
            key={`${part.link.text}-${index}`}
            link={part.link}
            matchedText={part.text}
            onAskAboutText={onAskAboutText}
          />
        );
      })}
    </>
  );
}

function InteractiveLinkPopup({
  link,
  matchedText,
  onAskAboutText,
}: {
  link: LessonInteractiveLink;
  matchedText: string;
  onAskAboutText: (text: string) => void;
}) {
  const actionLabel = getInteractiveLinkActionLabel(link);
  const askText = `${link.text}: ${link.explanation}${
    link.why_it_matters_here
      ? `\n\nWhy it matters here: ${link.why_it_matters_here}`
      : ""
  }`;

  return (
    <span className="relative inline-block align-baseline">
      <details className="group/link inline-block">
        <summary className="inline cursor-pointer list-none rounded-md px-1 font-semibold text-primary underline decoration-primary/60 decoration-dotted underline-offset-4 transition hover:bg-accent">
          {matchedText}
        </summary>
        <span className="absolute left-0 top-full z-30 mt-2 w-72 rounded-2xl border border-border bg-background p-4 text-left text-sm leading-6 text-foreground shadow-xl">
          <span className="block text-sm font-bold text-foreground">
            {link.text}
          </span>
          <span className="mt-1 block text-muted-foreground">
            <MathText text={link.explanation || ""} />
          </span>
          {link.why_it_matters_here && (
            <span className="mt-2 block rounded-xl bg-muted/40 p-2 text-xs leading-5 text-muted-foreground">
              <span className="font-semibold text-foreground">
                Why here:{" "}
              </span>
              <MathText text={link.why_it_matters_here} />
            </span>
          )}
          <button
            type="button"
            onClick={() => onAskAboutText(askText)}
            className="mt-3 rounded-xl border border-border bg-background px-3 py-1.5 text-xs font-semibold text-primary transition hover:bg-accent"
          >
            {actionLabel}
          </button>
        </span>
      </details>
    </span>
  );
}

function normalizeInteractiveLinks(value?: LessonInteractiveLink[]) {
  if (!Array.isArray(value)) {
    return [];
  }

  const seen = new Set<string>();
  return value
    .map((link) => ({
      text: String(link.text || "").trim(),
      explanation: String(link.explanation || "").trim(),
      why_it_matters_here: String(link.why_it_matters_here || "").trim(),
      action: String(link.action || "popup_only").trim(),
      target: String(link.target || "").trim(),
    }))
    .filter((link) => {
      if (!link.text || !link.explanation) {
        return false;
      }
      const key = link.text.toLowerCase();
      if (seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    })
    .slice(0, 6);
}

function splitTextByInteractiveLinks(
  text: string,
  links: LessonInteractiveLink[],
): Array<
  | { type: "text"; text: string }
  | { type: "link"; text: string; link: LessonInteractiveLink }
> {
  const lowerText = text.toLowerCase();
  const matches = normalizeInteractiveLinks(links)
    .map((link) => {
      const needle = String(link.text || "").toLowerCase();
      const start = needle ? lowerText.indexOf(needle) : -1;
      return {
        start,
        end: start >= 0 ? start + needle.length : -1,
        link,
      };
    })
    .filter((match) => match.start >= 0)
    .sort((a, b) => a.start - b.start || b.end - a.end);

  const nonOverlapping = [];
  let cursor = 0;
  for (const match of matches) {
    if (match.start < cursor) {
      continue;
    }
    nonOverlapping.push(match);
    cursor = match.end;
  }

  if (!nonOverlapping.length) {
    return [{ type: "text", text }];
  }

  const parts: Array<
    | { type: "text"; text: string }
    | { type: "link"; text: string; link: LessonInteractiveLink }
  > = [];
  cursor = 0;

  for (const match of nonOverlapping) {
    if (match.start > cursor) {
      parts.push({ type: "text", text: text.slice(cursor, match.start) });
    }
    parts.push({
      type: "link",
      text: text.slice(match.start, match.end),
      link: match.link,
    });
    cursor = match.end;
  }

  if (cursor < text.length) {
    parts.push({ type: "text", text: text.slice(cursor) });
  }

  return parts;
}

function getInteractiveLinkActionLabel(link: LessonInteractiveLink) {
  if (link.action === "open_study_path") {
    return "Open study path";
  }
  if (link.action === "review_earlier_topic") {
    return "Review earlier topic";
  }
  if (link.action === "ask_question") {
    return "Ask a question";
  }
  return "Ask about this";
}

function getDefaultCodingStarterCode(language: string) {
  const normalized = language.toLowerCase();

  if (normalized.includes("java") && !normalized.includes("javascript")) {
    return `class Solution {
    public String solve(String input) {
        return input;
    }
}`;
  }

  if (normalized.includes("typescript")) {
    return `function solve(input: string): string {
  return input;
}`;
  }

  if (normalized === "cpp" || normalized.includes("c++")) {
    return `#include <bits/stdc++.h>
using namespace std;

class Solution {
public:
    string solve(const string& input) {
        return input;
    }
};`;
  }

  if (normalized === "c") {
    return `#include <stdio.h>

void solve(const char* input) {
    printf("%s", input);
}`;
  }

  if (normalized.includes("javascript")) {
    return `function solve(input) {
  return input;
}`;
  }

  return `def solve(data: str):
    return data.strip()
`;
}

function renderBoldSegments(text: string, keyPrefix: string): ReactNode[] {
  const result: ReactNode[] = [];
  const boldPattern = /\*\*(.+?)\*\*/g;
  let cursor = 0;
  let m: RegExpExecArray | null;

  while ((m = boldPattern.exec(text)) !== null) {
    if (m.index > cursor) result.push(text.slice(cursor, m.index));
    result.push(<strong key={`${keyPrefix}-b${m.index}`}>{m[1]}</strong>);
    cursor = boldPattern.lastIndex;
  }

  if (cursor < text.length) result.push(text.slice(cursor));
  return result;
}

function renderMathText(text: string): ReactNode[] {
  if (!text) {
    return [];
  }

  if (shouldAutoRenderAsMathStrict(text)) {
    return [renderLatexExpression(normalizeMathExpressionStrict(text), true, "auto-math")];
  }

  const parts: ReactNode[] = [];
  const pattern = /(\$\$[\s\S]+?\$\$|\\\[[\s\S]+?\\\]|\\\([\s\S]+?\\\))/g;
  let cursor = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > cursor) {
      parts.push(...renderBoldSegments(text.slice(cursor, match.index), `${match.index}`));
    }

    const raw = match[0];
    const isDisplay = raw.startsWith("$$") || raw.startsWith("\\[");
    const latex = raw.startsWith("$$")
      ? raw.slice(2, -2)
      : raw.startsWith("\\[")
        ? raw.slice(2, -2)
        : raw.slice(2, -2);

    parts.push(renderLatexExpression(latex, isDisplay, `${match.index}-${raw.length}`));
    cursor = pattern.lastIndex;
  }

  if (cursor < text.length) {
    parts.push(...renderBoldSegments(text.slice(cursor), `tail`));
  }

  return parts;
}

function normalizeMathExpression(text: string) {
  let output = String(text || "").replace(/^\s*-\s*/, "").trim();
  output = output.replace(/∫\s*\[\s*([^,\]\s]+)\s*,?\s*([^\]\s]+)\s*\]/g, "\\int_{$1}^{$2}");
  output = output.replace(/∫/g, "\\int");
  output = output.replace(/√\(([^()]+)\)/g, "\\sqrt{$1}");
  output = output.replace(/√([A-Za-z0-9]+)/g, "\\sqrt{$1}");
  output = output.replace(/μ/g, "\\mu");
  output = output.replace(/σ/g, "\\sigma");
  output = output.replace(/π/g, "\\pi");
  output = output.replace(/\be\^\(([^)]+)\)/g, "e^{$1}");
  output = output.replace(/standard_deviation/g, "standard\\_deviation");
  return output;
}

function shouldAutoRenderAsMathStrict(text: string) {
  const cleaned = String(text || "").replace(/^\s*-\s*/, "").trim();
  if (!cleaned || cleaned.length > 220) {
    return false;
  }

  const hasStrongMathSignal = /\\int|\u222b|\\frac|\\sqrt|\u221a|\^|_\{/.test(cleaned);
  if (hasStrongMathSignal) {
    return true;
  }

  const phraseLikeMath = /\b(?:pdf|cdf|peak|area|right|left|probability|density|curve|decreases|increases|reflects|visualize|approaching|large|small|from|to|at)\b/i;
  if (
    phraseLikeMath.test(cleaned) &&
    !/^(?:mu|sigma|mean|standard_deviation|variance)\s*(?:=|\()/i.test(cleaned)
  ) {
    return false;
  }

  return /^(?:mu|sigma|mean|standard_deviation|variance|[a-zA-Z]|\u03bc|\u03c3)\s*(?:=|\()\s*[-+]?\d+(?:\.\d+)?\)?$/i.test(cleaned);
}

function normalizeMathExpressionStrict(text: string) {
  let output = String(text || "").replace(/^\s*-\s*/, "").trim();

  output = output.replace(/^mu\s*\(([^)]+)\)$/i, "\\mu = $1");
  output = output.replace(/^sigma\s*\(([^)]+)\)$/i, "\\sigma = $1");
  output = output.replace(/^mean\s*\(([^)]+)\)$/i, "\\mu = $1");
  output = output.replace(/^standard_deviation\s*\(([^)]+)\)$/i, "\\sigma = $1");
  output = output.replace(/^variance\s*\(([^)]+)\)$/i, "\\sigma^2 = $1");
  output = output.replace(/^mean\s*=\s*/i, "\\mu = ");
  output = output.replace(/^mu\s*=\s*/i, "\\mu = ");
  output = output.replace(/^standard_deviation\s*=\s*/i, "\\sigma = ");
  output = output.replace(/^sigma\s*=\s*/i, "\\sigma = ");
  output = output.replace(/^variance\s*=\s*/i, "\\sigma^2 = ");
  output = normalizeMathExpression(output);
  output = output.replace(/\u222b\s*\[\s*([^,\]\s]+)\s*,?\s*([^\]\s]+)\s*\]/g, "\\int_{$1}^{$2}");
  output = output.replace(/\u222b/g, "\\int");
  output = output.replace(/\u221a\(([^()]+)\)/g, "\\sqrt{$1}");
  output = output.replace(/\u221a([A-Za-z0-9]+)/g, "\\sqrt{$1}");
  output = output.replace(/\u03bc/g, "\\mu");
  output = output.replace(/\u03c3/g, "\\sigma");
  output = output.replace(/\u03c0/g, "\\pi");
  output = output.replace(/\\sqrt\s*2\s*(?:\\pi|pi)/gi, "\\sqrt{2\\pi}");
  output = output.replace(/\\sqrt\s*([A-Za-z0-9\\]+)\b/g, "\\sqrt{$1}");
  output = output.replace(/(\\mu|\\sigma)(\d+)/g, "$1^{$2}");
  output = output.replace(/([a-zA-Z])(\d+)(?=\b|[)+\-*/])/g, "$1^{$2}");
  output = output.replace(/\((x\s*-\s*\\mu\^\{2\})\)/g, "(x-\\mu)^2");
  output = output.replace(/1\/\((\\sigma\\sqrt\{2\\pi\})\)/g, "\\frac{1}{$1}");
  output = output.replace(/\(\\frac\{1\}\{(\\sigma\\sqrt\{2\\pi\})\}\)/g, "\\frac{1}{$1}");
  output = output.replace(/e\^\(-x-\\mu\^\{2\}\/\(2\\sigma\^\{2\}\)\)/g, "e^{-\\frac{(x-\\mu)^2}{2\\sigma^2}}");
  output = normalizeParenthesizedLatexPowers(output);
  output = normalizeCommonExponentFractions(output);

  return output;
}

function normalizeParenthesizedLatexPowers(source: string) {
  let output = "";
  let index = 0;

  while (index < source.length) {
    if (source[index] === "^" && source[index + 1] === "(") {
      let depth = 0;
      let end = -1;
      for (let cursor = index + 1; cursor < source.length; cursor += 1) {
        if (source[cursor] === "(") depth += 1;
        if (source[cursor] === ")") depth -= 1;
        if (depth === 0) {
          end = cursor;
          break;
        }
      }

      if (end > index) {
        output += `^{${source.slice(index + 2, end)}}`;
        index = end + 1;
        continue;
      }
    }

    output += source[index];
    index += 1;
  }

  return output;
}

function normalizeCommonExponentFractions(source: string) {
  return source
    .replace(
      /e\^\{\s*-\s*\(?\s*\((x\s*-\s*\\mu)\)\s*\)?\s*\^\{?2\}?\s*\/\s*\(?\s*2\s*\\sigma\^\{?2\}?\s*\)?\s*\}/g,
      "e^{-\\frac{($1)^2}{2\\sigma^2}}",
    )
    .replace(
      /e\^\{\s*-\s*(x\s*-\s*\\mu)\s*\^\{?2\}?\s*\/\s*\(?\s*2\s*\\sigma\^\{?2\}?\s*\)?\s*\}/g,
      "e^{-\\frac{($1)^2}{2\\sigma^2}}",
    );
}

function formatLatexForDisplayStrict(latex: string) {
  let output = latex.trim();

  output = output.replace(/\\frac\{([^{}]+)\}\{([^{}]+)\}/g, "($1)/($2)");
  output = output.replace(/\\sqrt\{([^{}]+)\}/g, "sqrt($1)");
  output = output.replace(/\\leq/g, "\u2264");
  output = output.replace(/\\geq/g, "\u2265");
  output = output.replace(/\\neq/g, "\u2260");
  output = output.replace(/\\approx/g, "\u2248");
  output = output.replace(/\\to/g, "\u2192");
  output = output.replace(/\\infty/g, "\u221e");
  output = output.replace(/\\cdot/g, "\u00b7");
  output = output.replace(/\\times/g, "\u00d7");
  output = output.replace(/\\sum/g, "\u03a3");
  output = output.replace(/\\int/g, "\u222b");
  output = output.replace(/\\partial/g, "\u2202");
  output = output.replace(/\\nabla/g, "\u2207");
  output = output.replace(/\\Delta/g, "\u0394");
  output = output.replace(/\\delta/g, "\u03b4");
  output = output.replace(/\\theta/g, "\u03b8");
  output = output.replace(/\\lambda/g, "\u03bb");
  output = output.replace(/\\mu/g, "\u03bc");
  output = output.replace(/\\sigma/g, "\u03c3");
  output = output.replace(/\\pi/g, "\u03c0");
  output = output.replace(/\\alpha/g, "\u03b1");
  output = output.replace(/\\beta/g, "\u03b2");
  output = output.replace(/\\gamma/g, "\u03b3");
  output = output.replace(/\\left|\\right/g, "");
  output = output.replace(/[{}]/g, "");

  return output;
}

function renderLatexExpression(latex: string, isDisplay: boolean, key: string) {
  return (
    <span
      key={key}
      className={
        isDisplay
          ? "my-2 block max-w-full overflow-x-auto rounded-xl bg-muted/50 px-4 py-3 text-center font-serif text-lg text-foreground"
          : "inline max-w-full overflow-x-auto rounded-md bg-muted/50 px-1.5 py-0.5 font-serif text-[0.95em] text-foreground"
      }
    >
      {renderLatexParts(normalizeMathExpressionStrict(latex), key)}
    </span>
  );
}

function renderLatexParts(latex: string, keyPrefix: string): ReactNode[] {
  return renderLatexPartsStructured(latex, keyPrefix);
}

function renderLatexPartsStructured(latex: string, keyPrefix: string): ReactNode[] {
  const parts: ReactNode[] = [];
  let index = 0;
  let tokenIndex = 0;

  while (index < latex.length) {
    const key = `${keyPrefix}-${tokenIndex++}`;
    const char = latex[index];

    if (/\s/.test(char)) {
      parts.push(<span key={key}> </span>);
      index += 1;
      continue;
    }

    if (latex.startsWith("\\frac", index)) {
      const numerator = readLatexGroup(latex, index + "\\frac".length);
      const denominator = numerator ? readLatexGroup(latex, numerator.nextIndex) : null;
      if (numerator && denominator) {
        parts.push(
          <span key={key} className="mx-1 inline-flex -translate-y-0.5 flex-col items-center align-middle text-[0.9em]">
            <span className="border-b border-current px-1 leading-5">
              {renderLatexPartsStructured(numerator.value, `${key}-num`)}
            </span>
            <span className="px-1 leading-5">
              {renderLatexPartsStructured(denominator.value, `${key}-den`)}
            </span>
          </span>,
        );
        index = denominator.nextIndex;
        continue;
      }
    }

    if (latex.startsWith("\\sqrt", index)) {
      const radicand = readLatexGroup(latex, index + "\\sqrt".length);
      if (radicand) {
        parts.push(
          <span key={key} className="inline-flex items-start gap-0.5">
            <span>{"\u221a"}</span>
            <span className="border-t border-current px-0.5">
              {renderLatexPartsStructured(radicand.value, `${key}-sqrt`)}
            </span>
          </span>,
        );
        index = radicand.nextIndex;
        continue;
      }
    }

    if (latex.startsWith("\\int", index)) {
      index += "\\int".length;
      const lower = readLatexScript(latex, index, "_");
      if (lower) {
        index = lower.nextIndex;
      }
      const upper = readLatexScript(latex, index, "^");
      if (upper) {
        index = upper.nextIndex;
      }
      parts.push(
        <span key={key} className="mx-3 inline-flex items-center align-middle">
          <span className="relative inline-block px-1 text-[1.55em] leading-none">
            {"\u222b"}
            {upper && (
              <sup className="absolute -right-3 -top-2 text-[0.42em]">
                {renderLatexPartsStructured(upper.value, `${key}-sup`)}
              </sup>
            )}
            {lower && (
              <sub className="absolute -bottom-2 -right-3 text-[0.42em]">
                {renderLatexPartsStructured(lower.value, `${key}-sub`)}
              </sub>
            )}
          </span>
        </span>,
      );
      continue;
    }

    const token = readLatexToken(latex, index);
    if (!token.value) {
      parts.push(<span key={key}>{char}</span>);
      index += 1;
      continue;
    }

    index = token.nextIndex;
    const subscript = readLatexScript(latex, index, "_");
    if (subscript) {
      index = subscript.nextIndex;
    }
    const superscript = readLatexScript(latex, index, "^");
    if (superscript) {
      index = superscript.nextIndex;
    }

    parts.push(renderLatexAtom(token.value, subscript?.value, superscript?.value, key));
  }

  return parts;
}

function readLatexGroup(source: string, startIndex: number): { value: string; nextIndex: number } | null {
  let index = startIndex;
  while (index < source.length && /\s/.test(source[index])) {
    index += 1;
  }
  if (source[index] !== "{") {
    return null;
  }

  let depth = 0;
  for (let cursor = index; cursor < source.length; cursor += 1) {
    const char = source[cursor];
    if (char === "{") depth += 1;
    if (char === "}") depth -= 1;
    if (depth === 0) {
      return {
        value: source.slice(index + 1, cursor),
        nextIndex: cursor + 1,
      };
    }
  }

  return null;
}

function readLatexScript(source: string, startIndex: number, marker: "_" | "^"): { value: string; nextIndex: number } | null {
  let index = startIndex;
  while (index < source.length && /\s/.test(source[index])) {
    index += 1;
  }
  if (source[index] !== marker) {
    return null;
  }

  index += 1;
  const group = readLatexGroup(source, index);
  if (group) {
    return group;
  }

  const token = readLatexToken(source, index);
  return token.value ? token : null;
}

function readLatexToken(source: string, startIndex: number): { value: string; nextIndex: number } {
  const command = source.slice(startIndex).match(/^\\[A-Za-z]+/);
  if (command) {
    return { value: command[0], nextIndex: startIndex + command[0].length };
  }

  const token = source.slice(startIndex).match(/^[A-Za-z0-9.]+/);
  if (token) {
    return { value: token[0], nextIndex: startIndex + token[0].length };
  }

  return { value: source[startIndex] || "", nextIndex: startIndex + 1 };
}

function renderLatexAtom(base: string, subscript: string | undefined, superscript: string | undefined, key: string) {
  return (
    <span key={key} className="relative inline-flex items-baseline px-0.5">
      <span>{formatLatexForDisplayStrict(base)}</span>
      {subscript && (
        <sub className="ml-0.5 text-[0.62em] leading-none">
          {renderLatexPartsStructured(subscript, `${key}-sub`)}
        </sub>
      )}
      {superscript && (
        <sup className="ml-0.5 text-[0.62em] leading-none">
          {renderLatexPartsStructured(superscript, `${key}-sup`)}
        </sup>
      )}
    </span>
  );
}

function CodeWithHighlight({
  code,
  language,
  highlightLines,
  maxLine,
  variant = "dark",
  showHeader = true,
}: {
  code: string;
  language?: string;
  highlightLines?: [number, number];
  maxLine?: number;
  variant?: "dark" | "light";
  showHeader?: boolean;
}) {
  const allLines = code.split("\n");
  const visibleLines = maxLine != null ? allLines.slice(0, maxLine) : allLines;
  const [hStart, hEnd] = highlightLines ?? [0, 0];
  const isLight = variant === "light";
  return (
    <div className={`overflow-hidden rounded-2xl border shadow-sm ${
      isLight
        ? "border-[#E2DDEC] bg-white text-foreground"
        : "border-[#343434] bg-[#1f1f1f] text-[#f4f4f4]"
    }`}>
      {showHeader && (
        <div className={`flex items-center justify-between border-b px-4 py-3 ${
          isLight
            ? "border-[#E8E3EF] bg-white"
            : "border-[#343434] bg-[#252525]"
        }`}>
          <span className={`text-sm font-black ${isLight ? "text-foreground" : "text-[#f4f4f4]"}`}>Code</span>
          {language && (
            <span className={`rounded-full px-2.5 py-1 text-[11px] font-black uppercase tracking-wide ${
              isLight
                ? "bg-[#F3EEFF] text-primary"
                : "bg-white/8 text-[#b9b9b9]"
            }`}>
              {language}
            </span>
          )}
        </div>
      )}
      <pre className={`max-h-[30rem] overflow-auto p-4 font-mono text-sm leading-6 ${
        isLight ? "bg-white" : ""
      }`}>
        <code>
          {visibleLines.map((line, idx) => {
            const lineNum = idx + 1;
            const isHighlighted = highlightLines != null && lineNum >= hStart && lineNum <= hEnd;
            return (
              <span
                key={idx}
                className={`block border-l-2 py-0.5 pl-3 ${
                  isHighlighted
                    ? isLight
                      ? "border-primary bg-primary/10 text-foreground"
                      : "border-[#AEBBFF] bg-[#6B7DFF]/18 text-[#FFFDF7]"
                    : isLight
                      ? "border-transparent text-[#1F1E26]"
                      : "border-transparent text-[#d8d8d8]"
                }`}
              >
                <span className={`mr-4 inline-block w-5 select-none text-right ${
                  isLight ? "text-[#9A94A8]" : "text-[#777]"
                }`}>
                  {lineNum}
                </span>
                {line}
              </span>
            );
          })}
        </code>
      </pre>
    </div>
  );
}

function LearningCard({
  step,
  visual,
  showVisual = true,
  compact = false,
  guidanceMode = false,
  onAskAboutText,
  focusState,
}: {
  step: Extract<LearningStep, { type: "flow_card" }>;
  visual: VisualPlanItem | null;
  showVisual?: boolean;
  compact?: boolean;
  guidanceMode?: boolean;
  onAskAboutText: (text: string) => void;
  focusState?: VisualFocusState | null;
}) {
  const card = step.card;
  const points = step.bullets;
  const revealFromIndex = step.revealFromIndex ?? 0;
  const shouldAnimateReveal = revealFromIndex > 0 && points.length > revealFromIndex;
  const bulletTree = buildBulletTree(points);
  const annotations = card?.annotations?.filter(
    (item) => item.label || item.explanation,
  ) ?? [];
  const microCheck = card?.micro_check;
  const hasMicroCheck = Boolean(microCheck?.prompt);
  const conceptSupport =
    card?.concept_support?.filter(
      (item) => item.concept && item.hover_explanation,
    ) ?? [];
  const interactiveLinks = normalizeInteractiveLinks(card?.interactive_links);
  const effectiveCompact = compact || guidanceMode;
  const visibleBulletTree = guidanceMode ? bulletTree.slice(0, 4) : bulletTree;
  const hiddenBulletCount = guidanceMode ? Math.max(0, bulletTree.length - 4) : 0;

  const resolvedVisual: VisualPlanItem | null = (() => {
    if (!showVisual) return null;
    if (visual) return visual;
    const codeVisual = codeVisualFromCard(card);
    if (codeVisual) return withCardSynchronizedCodeVisual(codeVisual, step);
    const workedExampleCodeVisual = workedExampleCodeVisualFromCard(card);
    if (workedExampleCodeVisual) {
      const inlineVisual =
        card?.visual_plan &&
        isMeaningfulCardVisual(card.visual_plan) &&
        isLessonVisualRenderable(card.visual_plan as VisualPlanItem)
          ? (card.visual_plan as VisualPlanItem)
          : undefined;
      return codingWorkedExampleCompositeVisual(
        inlineVisual,
        withCardSynchronizedCodeVisual(workedExampleCodeVisual, step),
      ) ?? withCardSynchronizedCodeVisual(workedExampleCodeVisual, step);
    }
    if (
      card?.visual_plan &&
      isMeaningfulCardVisual(card.visual_plan) &&
      isLessonVisualRenderable(card.visual_plan as VisualPlanItem)
    ) {
      return card.visual_plan as VisualPlanItem;
    }
    return null;
  })();
  const codeAlreadyRenderedAsVisual = Boolean(
    resolvedVisual &&
      (isCodeTraceVisualType(normalizeVisualType(resolvedVisual.type)) ||
        isCompositeVisualType(normalizeVisualType(resolvedVisual.type))),
  );

  return (
    <div className={effectiveCompact ? "w-full text-left" : "mx-auto w-full max-w-4xl text-left"}>
      <div className={effectiveCompact ? "" : "overflow-hidden rounded-3xl border border-[#E5DFEE] bg-white shadow-sm shadow-purple-100/40"}>

        {!effectiveCompact && resolvedVisual && (
          <div className="border-b border-border bg-muted/[0.03] p-6">
              <div className="azalea-visual-scroll max-h-[min(38vh,26rem)] overflow-auto overscroll-contain">
            <VisualRenderer
              visual={resolvedVisual}
              index={0}
              focusState={focusState ?? card?.visual_focus ?? null}
            />
            </div>
          </div>
        )}

        <div className={effectiveCompact ? "" : "azalea-sidebar-scroll max-h-[min(48vh,34rem)] overflow-y-auto overscroll-contain p-6 md:p-8"}>
        <div className="mb-5 flex flex-wrap items-center gap-3 text-xs font-black uppercase tracking-wide text-muted-foreground">
          <span className="rounded-full bg-[#EEE9FF] px-4 py-1.5 text-primary">
            {getStepTypeLabel(step)}
          </span>
          <span className="font-black text-muted-foreground">{getEstimatedTimeLabel(step.estimatedSeconds)}</span>
        </div>

        <h2 className={effectiveCompact ? "mb-4 text-xl font-black tracking-tight text-foreground" : "mb-7 text-center text-[2rem] font-black leading-tight tracking-tight text-foreground md:text-[2.35rem]"}>
          {step.title}
        </h2>

        {points.length > 0 ? (
          <ul className="space-y-3">
            {visibleBulletTree.map((node, index) => (
              <LearningBulletNode
                key={`${node.text}-${node.index}`}
                node={node}
                number={index + 1}
                links={interactiveLinks}
                onAskAboutText={onAskAboutText}
                revealFromIndex={revealFromIndex}
                shouldAnimateReveal={shouldAnimateReveal}
              />
            ))}
            {hiddenBulletCount > 0 && (
              <li className="list-none pl-1 text-xs text-muted-foreground">
                +{hiddenBulletCount} more
              </li>
            )}
          </ul>
        ) : (
          <div className="space-y-4">
            {step.body.map((paragraph, index) => (
              <div
                key={`${paragraph}-${index}`}
                className="group/clarify relative rounded-2xl p-2 text-lg leading-8 text-foreground transition hover:bg-muted/40 md:text-xl md:leading-9"
              >
                <p>
                  <LinkedMathText
                    text={paragraph}
                    links={interactiveLinks}
                    onAskAboutText={onAskAboutText}
                  />
                </p>
                <button
                  type="button"
                  onClick={() => onAskAboutText(paragraph)}
                  className="mt-3 rounded-xl border border-border bg-background px-3 py-1.5 text-xs font-semibold text-primary opacity-0 transition hover:bg-accent focus:opacity-100 group-hover/clarify:opacity-100"
                >
                  Ask about this
                </button>
              </div>
            ))}
          </div>
        )}

        {!guidanceMode && !codeAlreadyRenderedAsVisual && card?.code_snippet &&
          (card.blueprint_key === "worked_example" || card.card_type === "worked_example") && (
            <div className="mt-6">
              <CodeWithHighlight
                code={card.code_snippet}
                language={card.code_language}
                highlightLines={step.highlightLines}
                maxLine={step.maxCodeLine}
              />
            </div>
          )}


        {!guidanceMode && Array.isArray(card?.styled_elements) &&
          card.styled_elements.length > 0 && (
            <div className="mt-5 space-y-3">
              {card.styled_elements.map((element, index) => (
                <StyledElementRenderer
                  key={`${element.type}-${element.title}-${index}`}
                  element={element}
                />
              ))}
            </div>
          )}

        {!guidanceMode && conceptSupport.length > 0 && (
          <div className="mt-5 rounded-2xl border border-border bg-background p-4">
            <p className="text-sm font-bold text-foreground">
              Tap a concept if it feels fuzzy
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {conceptSupport.map((item) => (
                <details
                  key={`${item.concept}-${item.support}`}
                  className="group rounded-2xl border border-border bg-muted/30 px-3 py-2"
                >
                  <summary className="cursor-pointer list-none text-xs font-semibold text-foreground">
                    {item.concept}
                    {item.state_hint && (
                      <span className="ml-2 text-muted-foreground">
                        {item.state_hint}
                      </span>
                    )}
                  </summary>
                  <p className="mt-2 max-w-sm text-xs leading-5 text-muted-foreground">
                    <MathText text={item.hover_explanation || ""} />
                  </p>
                  <button
                    type="button"
                    onClick={() =>
                      onAskAboutText(
                        `Explain ${item.concept}: ${item.hover_explanation}`,
                      )
                    }
                    className="mt-2 rounded-xl border border-border bg-background px-3 py-1.5 text-xs font-semibold text-primary"
                  >
                    Ask about this
                  </button>
                </details>
              ))}
            </div>
          </div>
        )}

        {interactiveLinks.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2">
            {interactiveLinks.map((link) => (
              <button
                key={`${link.text}-${link.action}-${link.target}`}
                type="button"
                onClick={() =>
                  onAskAboutText(
                    `${link.text}: ${link.explanation}${
                      link.why_it_matters_here
                        ? `\n\nWhy it matters here: ${link.why_it_matters_here}`
                        : ""
                    }`,
                  )
                }
                className="rounded-full border border-primary/20 bg-accent px-3 py-1.5 text-xs font-semibold text-primary transition hover:bg-primary hover:text-primary-foreground"
              >
                {link.text}
              </button>
            ))}
          </div>
        )}

        {!guidanceMode && annotations.length > 0 && (
          <div className="mt-5 grid gap-3 md:grid-cols-2">
            {annotations.map((annotation, index) => (
              <div
                key={`${annotation.label}-${index}`}
                className="rounded-2xl border border-border bg-muted/30 p-4"
              >
                <p className="text-sm font-bold text-foreground">
                  {annotation.label || `Annotation ${index + 1}`}
                </p>
                {annotation.explanation && (
                  <p className="mt-1 text-sm leading-6 text-muted-foreground">
                    <MathText text={annotation.explanation} />
                  </p>
                )}
              </div>
            ))}
          </div>
        )}

        {!guidanceMode && card?.example && (
          <div className="mt-5 rounded-2xl border border-border bg-background p-4">
            <p className="text-sm font-bold text-foreground">Example</p>
            <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-muted-foreground">
              <MathText text={card.example} />
            </p>
          </div>
        )}

        {!guidanceMode && hasMicroCheck && (
          <MicrocheckReveal
            microCheck={microCheck}
            onAskAboutText={onAskAboutText}
          />
        )}

        </div>
      </div>
    </div>
  );
}

type BulletTreeNode = {
  text: string;
  level: number;
  index: number;
  children: BulletTreeNode[];
};

function LearningBulletNode({
  node,
  number,
  links,
  onAskAboutText,
  revealFromIndex,
  shouldAnimateReveal,
}: {
  node: BulletTreeNode;
  number?: number;
  links: LessonInteractiveLink[];
  onAskAboutText: (text: string) => void;
  revealFromIndex: number;
  shouldAnimateReveal: boolean;
}) {
  const isMain = node.level === 0;
  const isNew = shouldAnimateReveal && node.index >= revealFromIndex;
  const displayText = formatParentBulletText(node);

  const animationStyle = isNew
    ? {
        animation:
          "ideaRevealIn 0.42s cubic-bezier(0.2, 0.8, 0.2, 1) both, ideaRevealFocus 0.9s ease-out both",
      }
    : undefined;

  if (isMain) {
    return (
      <li
        className="group/clarify rounded-2xl border border-[#E5DFEE] bg-white p-5 text-lg leading-7 text-foreground shadow-sm shadow-purple-100/30"
        style={animationStyle}
      >
        <div className="flex gap-4">
          <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-black text-primary-foreground shadow-sm shadow-primary/30">
            {number}
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex gap-3">
              <span className="min-w-0 flex-1 font-black leading-7 text-foreground">
                <LinkedMathText
                  text={displayText}
                  links={links}
                  onAskAboutText={onAskAboutText}
                />
              </span>
              <AskBulletButton text={displayText} onAskAboutText={onAskAboutText} />
            </div>

            {node.children.length > 0 && (
              <ul className="mt-4 space-y-2 pl-4">
                {node.children.map((child) => (
                  <LearningBulletNode
                    key={`${child.text}-${child.index}`}
                    node={child}
                    links={links}
                    onAskAboutText={onAskAboutText}
                    revealFromIndex={revealFromIndex}
                    shouldAnimateReveal={shouldAnimateReveal}
                  />
                ))}
              </ul>
            )}
          </div>
        </div>
      </li>
    );
  }

  return (
    <li
      className="group/clarify rounded-xl px-2 py-1.5 text-base leading-7 text-foreground"
      style={animationStyle}
    >
      <div className="flex gap-3">
        <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-primary/60" />
        <div className="min-w-0 flex-1">
          <div className="flex gap-3">
            <span className="min-w-0 flex-1">
              <LinkedMathText
                text={displayText}
                links={links}
                onAskAboutText={onAskAboutText}
              />
            </span>
            <AskBulletButton text={displayText} onAskAboutText={onAskAboutText} />
          </div>

          {node.children.length > 0 && (
            <ul className="mt-2 space-y-1 pl-4">
              {node.children.map((child) => (
                <LearningBulletNode
                  key={`${child.text}-${child.index}`}
                  node={child}
                  links={links}
                  onAskAboutText={onAskAboutText}
                  revealFromIndex={revealFromIndex}
                  shouldAnimateReveal={shouldAnimateReveal}
                />
              ))}
            </ul>
          )}
        </div>
      </div>
    </li>
  );
}

function formatParentBulletText(node: BulletTreeNode) {
  const text = sentenceCaseBulletStart(String(node.text || "").trim());
  if (!text || node.children.length === 0) {
    return text;
  }

  if (/[?:]$/.test(text)) {
    return text;
  }

  return `${text.replace(/[.;,]+$/g, "")}:`;
}

function sentenceCaseBulletStart(text: string) {
  const value = String(text || "");
  if (!value || shouldPreserveBulletStartCase(value)) return value;
  const match = value.match(/^(\s*)(.*)$/);
  if (!match) return value;
  const [, whitespace, body] = match;
  for (let index = 0; index < body.length; index += 1) {
    const char = body[index];
    if (!char) continue;
    if (/[A-Za-z]/.test(char)) {
      return `${whitespace}${body.slice(0, index)}${char.toUpperCase()}${body.slice(index + 1)}`;
    }
    if (!/\s/.test(char) && !['"', "'", "(", "[", "{", "`"].includes(char)) {
      return value;
    }
  }
  return value;
}

function shouldPreserveBulletStartCase(text: string) {
  const stripped = String(text || "").trim();
  if (!stripped) return true;
  if (/^[`$\\([{]/.test(stripped)) return true;
  if (/^[a-z_][A-Za-z0-9_]*(?:\[[^\]]+\])?\s*(?:=|:|\+=|-=|\*=|\/=)/.test(stripped)) {
    return true;
  }
  if (/^(?:def|class|if|elif|else|for|while|return|import|from|try|except|with)\b/.test(stripped)) {
    return true;
  }
  const firstWord = stripped.split(/[\s,;:.=()[\]{}]/, 1)[0] || "";
  return firstWord.includes("_");
}

function WorkspaceBulletChildren({
  nodes,
  revealFromIndex,
  shouldAnimateReveal,
}: {
  nodes: BulletTreeNode[];
  revealFromIndex: number;
  shouldAnimateReveal: boolean;
}) {
  return (
    <ul className="mt-3 space-y-2 pl-1">
      {nodes.map((child) => {
        const isNew = shouldAnimateReveal && child.index >= revealFromIndex;
        const animationStyle = isNew
          ? {
              animation:
                "ideaRevealIn 0.42s cubic-bezier(0.2, 0.8, 0.2, 1) both, ideaRevealFocus 0.9s ease-out both",
            }
          : undefined;
        return (
          <li
            key={`${child.text}-${child.index}`}
            className="rounded-xl px-1 py-0.5"
            style={animationStyle}
          >
            <div className="flex items-start gap-3 text-sm leading-6 text-foreground">
              <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-primary/45" />
              <div className="min-w-0 flex-1">
                <MathText text={formatParentBulletText(child)} />
                {child.children.length > 0 && (
                  <WorkspaceBulletChildren
                    nodes={child.children}
                    revealFromIndex={revealFromIndex}
                    shouldAnimateReveal={shouldAnimateReveal}
                  />
                )}
              </div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function AskBulletButton({
  text: _text,
  onAskAboutText: _onAskAboutText,
}: {
  text: string;
  onAskAboutText: (text: string) => void;
}) {
  return null;
}

function buildBulletTree(points: string[]): BulletTreeNode[] {
  const roots: BulletTreeNode[] = [];
  const stack: BulletTreeNode[] = [];

  points.forEach((rawPoint, index) => {
    const parsed = parseBulletPoint(rawPoint, index, roots.length === 0);
    if (!parsed.text) return;

    while (stack.length > 0 && stack[stack.length - 1].level >= parsed.level) {
      stack.pop();
    }

    if (parsed.level === 0 || stack.length === 0) {
      roots.push(parsed);
    } else {
      stack[stack.length - 1].children.push(parsed);
    }

    stack.push(parsed);
  });

  return roots;
}

function parseBulletPoint(
  rawPoint: string,
  index: number,
  isFirstRenderablePoint: boolean,
): BulletTreeNode {
  const raw = String(rawPoint || "").replace(/\s+$/g, "");
  const match = raw.match(/^(\s*)-\s+(.*)$/);
  if (!match) {
    return {
      text: raw.trim(),
      level: 0,
      index,
      children: [],
    };
  }

  const leadingSpaces = match[1]?.length ?? 0;
  const markerText = (match[2] || "").trim();
  const inferredLevel = Math.max(1, Math.floor(leadingSpaces / 2));

  return {
    text: markerText,
    level: isFirstRenderablePoint ? 0 : inferredLevel,
    index,
    children: [],
  };
}

function StyledElementRenderer({ element }: { element: LessonStyledElement }) {
  const type = String(element.type || "").toLowerCase();
  const data = element.data || {};
  const title = element.title || styledElementDefaultTitle(type);
  const columns = normalizeStringArray(data.columns);
  const rows = normalizeTableRows(data.rows);
  const items = normalizeStyledItems(data.items);
  const steps = normalizeStyledItems(data.steps);
  const code = typeof data.code === "string" ? data.code : "";
  const language = typeof data.language === "string" ? data.language : "";

  if (normalizeVisualType(type) === "code_trace" && code) {
    return (
      <div className="rounded-2xl border border-border bg-slate-950 p-4 text-slate-50">
        <div className="mb-3 flex items-center justify-between gap-3">
          <p className="text-sm font-bold">{title}</p>
          {language && (
            <span className="rounded-full bg-white/10 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-slate-300">
              {language}
            </span>
          )}
        </div>
        <pre className="overflow-x-auto whitespace-pre-wrap text-sm leading-6">
          <code>{code}</code>
        </pre>
      </div>
    );
  }

  if (type === "formula_steps" && steps.length > 0) {
    return (
      <div className="rounded-2xl border border-primary/15 bg-primary/5 p-4">
        <p className="text-sm font-bold text-foreground">{title}</p>
        <div className="mt-3 space-y-3">
          {steps.map((step, index) => (
            <div key={`${step.label}-${index}`} className="rounded-xl bg-background p-3">
              <p className="text-sm font-semibold text-foreground">
                <MathText text={step.latex || step.label} />
              </p>
              {step.description && (
                <p className="mt-1 text-xs leading-5 text-muted-foreground">
                  <MathText text={step.description} />
                </p>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (columns.length > 0 && rows.length > 0) {
    return (
      <div className="overflow-hidden rounded-2xl border border-border bg-background">
        <div className="border-b border-border bg-muted/40 px-4 py-3">
          <p className="text-sm font-bold text-foreground">{title}</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[480px] text-left text-sm">
            <thead className="bg-muted/30 text-xs uppercase text-muted-foreground">
              <tr>
                {columns.map((column) => (
                  <th key={column} className="px-4 py-3 font-bold">
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, rowIndex) => (
                <tr key={rowIndex} className="border-t border-border">
                  {columns.map((_, columnIndex) => (
                    <td key={columnIndex} className="px-4 py-3 align-top text-muted-foreground">
                      <MathText text={row[columnIndex] || ""} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  const listItems = items.length > 0 ? items : steps;
  if (listItems.length > 0) {
    return (
      <div className="rounded-2xl border border-border bg-background p-4">
        <p className="text-sm font-bold text-foreground">{title}</p>
        <div className="mt-3 space-y-3">
          {listItems.map((item, index) => (
            <div key={`${item.label}-${index}`} className="flex gap-3">
              <span className="mt-1 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[11px] font-bold text-primary">
                {index + 1}
              </span>
              <div>
                <p className="text-sm font-semibold text-foreground">
                  <MathText text={item.label} />
                </p>
                {item.description && (
                  <p className="mt-1 text-sm leading-6 text-muted-foreground">
                    <MathText text={item.description} />
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return null;
}

function styledElementDefaultTitle(type: string) {
  return type
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function normalizeStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map((item) => String(item || "").trim()).filter(Boolean)
    : [];
}

function normalizeTableRows(value: unknown): string[][] {
  if (!Array.isArray(value)) return [];
  return value
    .map((row) => {
      if (Array.isArray(row)) return row.map((cell) => String(cell ?? ""));
      if (row && typeof row === "object") {
        return Object.values(row as Record<string, unknown>).map((cell) =>
          String(cell ?? ""),
        );
      }
      return [];
    })
    .filter((row) => row.length > 0);
}

function normalizeStyledItems(value: unknown): { label: string; description: string; latex?: string }[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => {
      if (typeof item === "string") {
        return { label: item, description: "" };
      }
      if (item && typeof item === "object") {
        const record = item as Record<string, unknown>;
        return {
          label: String(record.label || record.title || record.step || record.latex || "").trim(),
          description: String(record.description || record.reason || record.text || "").trim(),
          latex: typeof record.latex === "string" ? record.latex : undefined,
        };
      }
      return { label: "", description: "" };
    })
    .filter((item) => item.label || item.description);
}

function MicrocheckReveal({
  microCheck,
  onAskAboutText,
}: {
  microCheck?: {
    type?: string;
    prompt?: string;
    answer?: string;
  };
  onAskAboutText: (text: string) => void;
}) {
  const [isRevealed, setIsRevealed] = useState(false);
  const prompt = microCheck?.prompt || "";
  const answer = microCheck?.answer || "";

  if (!prompt) {
    return null;
  }

  return (
    <div className="mt-5 rounded-2xl border border-primary/20 bg-accent/60 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-wide text-primary">
            Quick check
          </p>
          <p className="mt-2 text-sm leading-6 text-foreground">
            <MathText text={prompt} />
          </p>
        </div>
        {answer && (
          <button
            type="button"
            onClick={() => setIsRevealed((value) => !value)}
            className="rounded-xl border border-primary/20 bg-background px-3 py-2 text-xs font-bold text-primary transition hover:bg-primary hover:text-primary-foreground"
          >
            {isRevealed ? "Hide answer" : "Reveal answer"}
          </button>
        )}
      </div>

      {isRevealed && answer && (
        <div className="mt-4 rounded-xl border border-border bg-background p-3">
          <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">
            Answer
          </p>
          <p className="mt-2 text-sm leading-6 text-foreground">
            <MathText text={answer} />
          </p>
          <button
            type="button"
            onClick={() => onAskAboutText(`Quick check: ${prompt}\n\nAnswer: ${answer}`)}
            className="mt-3 rounded-xl border border-border bg-background px-3 py-1.5 text-xs font-semibold text-primary transition hover:bg-accent"
          >
            Ask about this check
          </button>
        </div>
      )}
    </div>
  );
}

function isMeaningfulCardVisual(
  visualPlan?: VisualPlanItem | Record<string, unknown>,
) {
  if (!visualPlan) {
    return false;
  }

  const plan = visualPlan as Record<string, unknown>;

  return Boolean(
    plan.kind ||
      plan.type ||
      plan.title ||
      plan.description ||
      plan.purpose ||
      (Array.isArray(plan.elements) && plan.elements.length > 0) ||
      (Array.isArray(plan.labels) && plan.labels.length > 0),
  );
}

function FlowCheckpointCard({
  checkpoint,
  currentRunEstimatedMinutes,
  metrics,
  weakAreas,
  onContinue,
  canContinue,
  continueDisabledReason,
  onBack,
  onTakeBreak,
}: {
  checkpoint: FlowCheckpoint;
  currentRunEstimatedMinutes: number;
  metrics: FlowMetrics;
  weakAreas: WeakAreaSummary | null;
  onContinue: () => void;
  canContinue: boolean;
  continueDisabledReason?: string;
  onBack: () => void;
  onTakeBreak: () => void;
}) {
  const isPathComplete = checkpoint.type === "path_complete";
  const quickCheckAccuracy =
    metrics.quickChecks > 0
      ? Math.round((metrics.quickCheckCorrect / metrics.quickChecks) * 100)
      : null;
  const averageTransitionSeconds =
    metrics.transitionCount > 0
      ? Math.round(metrics.totalTransitionMs / metrics.transitionCount / 1000)
      : null;
  const topWeakAreas = weakAreas?.weak_areas.slice(0, 3) ?? [];

  return (
    <div className="flex min-h-[56vh] items-center justify-center">
      <div className="mx-auto w-full max-w-3xl rounded-3xl border border-border bg-background p-7 text-left shadow-sm md:p-8">
        <p className="text-xs font-semibold uppercase tracking-wide text-primary">
          {isPathComplete ? "Path complete" : "Topic complete"}
        </p>

        <h2 className="mt-3 text-3xl font-bold tracking-tight text-foreground md:text-4xl">
          Finished {checkpoint.completedTopicTitle}
        </h2>

        <p className="mt-4 text-sm leading-6 text-muted-foreground">
          {isPathComplete
            ? "Your break point is saved automatically. You can review this path now or return later."
            : "Your break point is saved automatically. When the next topic is ready, you can continue from here."}
        </p>

        {checkpoint.nextTopic ? (
          <div className="mt-6 rounded-2xl border border-border bg-muted/30 p-5">
            <p className="text-sm font-semibold text-foreground">
              Next: {checkpoint.nextTopic.title}
            </p>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              {checkpoint.nextTopic.purpose ||
                "This next topic builds on what you just finished."}
            </p>
            <p className="mt-3 text-xs font-semibold text-muted-foreground">
              Estimated next run:{" "}
              {checkpoint.nextTopic.estimated_minutes ??
                currentRunEstimatedMinutes}{" "}
              min
            </p>
          </div>
        ) : (
          <div className="mt-6 rounded-2xl border border-border bg-muted/30 p-5">
            <p className="text-sm font-semibold text-foreground">
              You reached the end of this path.
            </p>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              From here, the useful next move is review, weak-area practice, or
              a mastery check.
            </p>
          </div>
        )}

        {isPathComplete && (
          <div className="mt-5 grid gap-3 md:grid-cols-3">
            <CompletionMetric
              label="Cards completed"
              value={String(metrics.cardsCompleted)}
            />
            <CompletionMetric
              label="Quick check accuracy"
              value={
                quickCheckAccuracy !== null ? `${quickCheckAccuracy}%` : "N/A"
              }
            />
            <CompletionMetric
              label="Avg. between cards"
              value={
                averageTransitionSeconds !== null
                  ? `${averageTransitionSeconds}s`
                  : "N/A"
              }
            />
          </div>
        )}

        {isPathComplete && topWeakAreas.length > 0 && (
          <div className="mt-5 rounded-2xl border border-border bg-background p-5">
            <p className="text-sm font-semibold text-foreground">
              Recommended review
            </p>
            <div className="mt-3 space-y-3">
              {topWeakAreas.map((area) => (
                <div key={area.mistake_type} className="text-sm">
                  <p className="font-semibold text-foreground">
                    {area.mistake_type}
                  </p>
                  <p className="mt-1 leading-6 text-muted-foreground">
                    {area.recommended_action}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="mt-7 flex flex-wrap gap-3">
          {!isPathComplete && (
            <button
              type="button"
              onClick={onBack}
              className="rounded-2xl border border-border bg-background px-5 py-3 text-sm font-semibold text-foreground transition hover:bg-muted"
            >
              Back to last card
            </button>
          )}

          <button
            type="button"
            onClick={onContinue}
            disabled={!canContinue}
            className="rounded-2xl bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground transition hover:bg-foreground disabled:cursor-not-allowed disabled:opacity-40"
          >
            {isPathComplete ? "Review path summary" : "Move on to next topic"}
          </button>

          {!isPathComplete && continueDisabledReason && (
            <p className="basis-full text-xs font-semibold leading-5 text-muted-foreground">
              {continueDisabledReason}
            </p>
          )}

          {isPathComplete && (
            <button
              type="button"
              onClick={onTakeBreak}
              className="rounded-2xl border border-border bg-background px-5 py-3 text-sm font-semibold text-foreground transition hover:bg-muted"
            >
              Review tomorrow
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function CompletionMetric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl border border-border bg-muted/30 p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-lg font-bold text-foreground">{value}</p>
    </div>
  );
}

/**
 * Card types that accumulate bullets on the same page (reveal-build).
 * Clicking Next adds the next bullet rather than navigating to a new page.
 * All other content card types get one new page per bullet group.
 */
const REVEAL_BUILD_TYPES = new Set([
  "background",
  "process",
  "comparison",
  "edge_case",
  "formula_breakdown",
  "roadmap",
]);


/**
 * Splits a flat points array into groups where each group is
 * [mainBullet, ...subBullets]. Sub-bullets start with "  - ".
 */
function groupBulletsWithSubpoints(points: string[]): string[][] {
  const groups: string[][] = [];
  for (const point of points) {
    if (isIndentedBullet(point) && groups.length > 0) {
      groups[groups.length - 1].push(point);
    } else {
      groups.push([point]);
    }
  }
  return groups;
}

function isIndentedBullet(point: string) {
  return /^\s+-\s+/.test(point);
}

function normalizeSplitMathBullets(points: string[]) {
  const normalized: string[] = [];
  for (let index = 0; index < points.length; index++) {
    const point = points[index];
    const nextPoint = points[index + 1];
    const integralStart = point.match(/^(\s+-\s*)(?:∫|\\int)\s*\[\s*([^,\]\s]+)\s*$/);
    const integralEnd = nextPoint?.match(/^\s+-\s*([^\]\s]+)\]\s*(.+)$/);
    if (integralStart && integralEnd) {
      normalized.push(
        `${integralStart[1]}\\int_{${integralStart[2]}}^{${integralEnd[1]}} ${integralEnd[2].trim()}`,
      );
      index++;
      continue;
    }
    normalized.push(point);
  }
  return normalizeSplitTrackerBullets(normalized);
}

function normalizeSplitTrackerBullets(points: string[]) {
  const normalized: string[] = [];

  for (let index = 0; index < points.length; index++) {
    const point = points[index];

    if (!isIndentedBullet(point) || !hasUnclosedTrackerCollection(point)) {
      normalized.push(point);
      continue;
    }

    const bulletPrefix = point.match(/^(\s*-\s*)/)?.[1] || "  - ";
    let mergedText = stripIndentedBulletMarker(point);
    let nextIndex = index + 1;

    while (
      hasUnclosedCollectionValue(mergedText) &&
      nextIndex < points.length &&
      isIndentedBullet(points[nextIndex])
    ) {
      const continuation = stripIndentedBulletMarker(points[nextIndex]);
      if (looksLikeTrackerAssignment(continuation)) {
        break;
      }
      mergedText = joinTrackerContinuation(mergedText, continuation);
      nextIndex++;
    }

    normalized.push(`${bulletPrefix}${mergedText}`);
    index = nextIndex - 1;
  }

  return normalized;
}

function stripIndentedBulletMarker(point: string) {
  return point.replace(/^\s*-\s*/, "").trim();
}

function hasUnclosedTrackerCollection(point: string) {
  const text = stripIndentedBulletMarker(point);
  return looksLikeTrackerAssignment(text) && hasUnclosedCollectionValue(text);
}

function looksLikeTrackerAssignment(text: string) {
  return /^[A-Za-z_][A-Za-z0-9_ .-]*\s*=\s*[\[{]/.test(text.trim());
}

function hasUnclosedCollectionValue(text: string) {
  const squareBalance = countChar(text, "[") - countChar(text, "]");
  const braceBalance = countChar(text, "{") - countChar(text, "}");
  return squareBalance > 0 || braceBalance > 0;
}

function countChar(text: string, char: string) {
  return [...text].filter((item) => item === char).length;
}

function joinTrackerContinuation(current: string, continuation: string) {
  if (!continuation) return current;
  if (/^[\]}]/.test(continuation)) {
    return `${current}${continuation}`;
  }
  if (/[\[{]\s*$/.test(current)) {
    return `${current}${continuation}`;
  }
  return `${current}, ${continuation}`;
}

function buildRevealUnits(flatBullets: string[]): string[][] {
  const revealUnits: string[][] = [];
  for (let i = 0; i < flatBullets.length; i++) {
    const b = flatBullets[i];
    if (/^(Currently|Now)[: ]/.test(b)) {
      const unit = [b];
      while (i + 1 < flatBullets.length && isIndentedBullet(flatBullets[i + 1])) {
        i++;
        unit.push(flatBullets[i]);
      }
      revealUnits.push(unit);
    } else {
      revealUnits.push([b]);
    }
  }
  return revealUnits;
}

function expandCurrentlyNowBullets(points: string[]): string[] {
  const result: string[] = [];
  for (const point of points) {
    const match = /^(Currently|Now):\s*(.+)$/.exec(point);
    if (!match) {
      result.push(point);
      continue;
    }
    const content = match[2].trim();
    const emDashIdx = content.indexOf(" — ");
    if (emDashIdx < 0) {
      result.push(point);
    } else {
      const trackerPart = content.slice(0, emDashIdx).trim();
      const descPart = content.slice(emDashIdx + 3).trim();
      result.push(`${match[1]}: ${trackerPart}`);
      if (descPart) result.push(`  - ${descPart}`);
    }
  }
  return result;
}

function getFullWalkthroughCode(cards: LessonFlowCard[]): string {
  // Build the "full implementation" by combining all code_walkthrough cards
  // in topic order. Two LLM-output patterns are common:
  //   (a) Each card emits the FULL cumulative code (so all cards share the
  //       same snippet). In that case the longest single snippet IS the
  //       full program.
  //   (b) Each card emits ONLY its newly-added lines (a fragment per card).
  //       In that case we need to concatenate all the fragments — the
  //       longest single snippet is NOT the full program.
  // We compute both and pick whichever is longer.

  let bestSingleCode = "";
  let bestSingleLineCount = 0;
  const concatenatedLines: string[] = [];

  for (const card of cards) {
    const key = String(card.blueprint_key || card.card_type || "")
      .trim()
      .toLowerCase();
    if (key !== "code_walkthrough") {
      continue;
    }

    const code = (card.code_snippet || "").trim();
    if (!code) {
      continue;
    }

    const lineCount = code.split("\n").length;
    if (lineCount > bestSingleLineCount) {
      bestSingleLineCount = lineCount;
      bestSingleCode = code;
    }

    // Append this card's lines to the concatenation, deduping ones already
    // present (so cumulative-snippet patterns don't double up).
    for (const line of code.split("\n")) {
      if (!concatenatedLines.includes(line)) {
        concatenatedLines.push(line);
      }
    }
  }

  const concatenatedCode = concatenatedLines.join("\n");
  return concatenatedLines.length > bestSingleLineCount
    ? concatenatedCode
    : bestSingleCode;
}

/**
 * Computes the per-card progressive-reveal window for code_walkthrough cards.
 * Returns one entry per code_walkthrough card (in order) with:
 *   - `maxLine`: cumulative line count visible through this card
 *   - `highlight`: [start, end] of lines newly introduced on this card
 *
 * The result is GUARANTEED monotonic non-decreasing and ends at totalLines
 * on the last card, regardless of what the LLM emitted. See the long
 * comment block in buildLearningStepsFromCards for why we don't trust the
 * LLM's highlight_lines_per_step directly.
 */
function computeCodeWalkthroughReveal(
  cards: LessonFlowCard[] | undefined,
  fullCode: string,
  totalLines: number,
): Array<{ maxLine: number; highlight: [number, number]; perGroupRanges: Array<[number, number]> }> {
  if (!Array.isArray(cards) || !fullCode || totalLines <= 0) return [];

  const walkthroughIndices = cards
    .map((c, i) =>
      String(c.blueprint_key || c.card_type || "").trim().toLowerCase() ===
      "code_walkthrough"
        ? i
        : -1,
    )
    .filter((i) => i >= 0);

  const n = walkthroughIndices.length;
  if (n === 0) return [];

  // Read each card's LLM-supplied max-end-line (highest end across its ranges).
  const llmMaxLines: Array<number | null> = walkthroughIndices.map((idx) => {
    const ranges = cards[idx].highlight_lines_per_step;
    if (!Array.isArray(ranges) || ranges.length === 0) return null;
    let maxEnd = 0;
    for (const r of ranges) {
      if (Array.isArray(r) && r.length === 2) {
        const end = Math.max(1, Math.min(totalLines, Number(r[1])));
        if (Number.isFinite(end) && end > maxEnd) maxEnd = end;
      }
    }
    return maxEnd > 0 ? maxEnd : null;
  });

  // Accept the LLM's values only if they look genuinely progressive:
  //   - every card has a parseable range
  //   - first card covers ≤ 60% of total (no "this card introduces the
  //     whole function" pattern)
  //   - monotonically non-decreasing
  //   - last card reaches totalLines (or n === 1)
  let useLlm = false;
  if (llmMaxLines.every((v) => v != null)) {
    const firstMax = llmMaxLines[0] ?? 0;
    const firstSmall = firstMax <= Math.max(1, Math.floor((totalLines * 6) / 10));
    let monotonic = true;
    for (let i = 1; i < n; i++) {
      if ((llmMaxLines[i] ?? 0) < (llmMaxLines[i - 1] ?? 0)) {
        monotonic = false;
        break;
      }
    }
    const endsAtTotal = (llmMaxLines[n - 1] ?? 0) >= totalLines || n === 1;
    useLlm = firstSmall && monotonic && endsAtTotal;
  }

  const perCardMaxLine: number[] = useLlm
    ? llmMaxLines.map((m) => Math.max(1, m ?? 1))
    : Array.from({ length: n }, (_, i) =>
        Math.max(1, Math.min(totalLines, Math.ceil(((i + 1) * totalLines) / n))),
      );

  // Enforce monotonic non-decreasing and force last card to reveal full code.
  let prev = 0;
  for (let i = 0; i < n; i++) {
    if (perCardMaxLine[i] < prev) perCardMaxLine[i] = prev;
    prev = perCardMaxLine[i];
  }
  perCardMaxLine[n - 1] = totalLines;

  // Compute per-card highlight = the freshly introduced range, AND for each
  // card distribute that range across its bullet groups so each main bullet
  // gets its own per-line reveal step. The number of bullet groups per card
  // is read from the card's points so cards with N main bullets reveal N
  // sub-windows.
  const result: Array<{
    maxLine: number;
    highlight: [number, number];
    perGroupRanges: Array<[number, number]>;
  }> = [];
  let prevMax = 0;
  for (let i = 0; i < n; i++) {
    const cardIdx = walkthroughIndices[i];
    const card = cards[cardIdx];
    const maxLine = perCardMaxLine[i];
    const start = maxLine > prevMax ? prevMax + 1 : Math.max(1, maxLine);
    const cardSpan = Math.max(1, maxLine - start + 1);

    // Count main bullets on this card to know how many groups to subdivide
    // the per-card span across. A "main bullet" is a top-level line that
    // doesn't start with whitespace+dash (the indented sub-bullet shape).
    const points = (card.points || card.bullets || []).map((p) => String(p));
    const mainBulletCount = Math.max(
      1,
      points.filter((p) => p.trim().length > 0 && !/^\s+-\s+/.test(p)).length,
    );

    // Distribute the [start, maxLine] window across the main bullets so each
    // bullet group reveals a roughly equal portion of new code. Ceiling math
    // ensures the last group always reaches `maxLine`.
    const perGroupRanges: Array<[number, number]> = [];
    let prevEnd = start - 1;
    for (let g = 0; g < mainBulletCount; g++) {
      const target =
        g === mainBulletCount - 1
          ? maxLine
          : Math.min(
              maxLine,
              start + Math.ceil(((g + 1) * cardSpan) / mainBulletCount) - 1,
            );
      const groupStart = prevEnd + 1;
      const groupEnd = Math.max(target, groupStart);
      perGroupRanges.push([groupStart, groupEnd]);
      prevEnd = groupEnd;
    }

    result.push({ maxLine, highlight: [start, maxLine], perGroupRanges });
    prevMax = maxLine;
  }
  return result;
}


function buildLearningStepsFromCards({
  cards,
  practiceQuestions,
  visuals,
}: {
  cards?: LessonFlowCard[];
  practiceQuestions?: LessonPracticeQuestion[];
  visuals?: VisualPlanItem[];
}): LearningStep[] {
  if (!Array.isArray(cards) || cards.length === 0) {
    return [];
  }

  // Code walkthrough cards accumulate code progressively across the topic.
  // We DO NOT trust the LLM's `highlight_lines_per_step` for cross-card
  // accumulation because (a) the per-card local `maxCodeLine` resets to 0
  // each card so there's no monotonic counter, (b) the LLM sometimes emits
  // relative or overly-broad ranges (e.g. [[1, totalLines]] on card 1
  // meaning "this card introduces the whole function"), (c) some cards
  // arrive with no parseable ranges at all.
  //
  // Instead we compute a deterministic per-card max_line ourselves:
  //   1. Pick the canonical full code (longest snippet OR concatenation of
  //      unique lines across all walkthrough cards — whichever is longer).
  //   2. Compute per-card max_line by validating the LLM's ranges against
  //      a "looks progressive" rubric (first card ≤ 60% of total, monotonic,
  //      last reaches total). If the rubric passes, use the LLM's values.
  //      If not, fall back to even distribution: card i shows lines
  //      1..ceil(i * total / N), guaranteeing the last card has the
  //      complete program.
  //   3. Enforce monotonic non-decreasing on the resulting values.
  //   4. Store the cumulative max_line and the "newly introduced" highlight
  //      range on each code_walkthrough card so they survive into the step
  //      builder (which writes them onto `step.maxCodeLine` /
  //      `step.highlightLines`, which `withCardSynchronizedCodeVisual` then
  //      overlays onto the focus visual).
  const fullWalkthroughCode = getFullWalkthroughCode(cards);
  const walkthroughLineCount = fullWalkthroughCode
    ? fullWalkthroughCode.split("\n").length
    : 0;
  const computedWalkthroughReveal = computeCodeWalkthroughReveal(
    cards,
    fullWalkthroughCode,
    walkthroughLineCount,
  );

  const workingCards: LessonFlowCard[] = fullWalkthroughCode
    ? (() => {
        let walkthroughIdx = 0;
        return cards.map((card) => {
          const isWalkthrough =
            String(card.blueprint_key || card.card_type || "")
              .trim()
              .toLowerCase() === "code_walkthrough";
          if (!isWalkthrough) return card;
          const reveal = computedWalkthroughReveal[walkthroughIdx];
          walkthroughIdx += 1;
          return {
            ...card,
            code_snippet: fullWalkthroughCode,
            // Override the LLM's highlight_lines_per_step with our per-bullet
            // distribution: one range per main bullet on this card, each
            // covering a slice of the card's deterministic [start, maxLine]
            // window. The step builder then creates one reveal step per
            // bullet group with the corresponding code window, so the
            // learner sees each line of code revealed progressively as they
            // walk through each main bullet — not all at once.
            highlight_lines_per_step: reveal
              ? reveal.perGroupRanges
              : card.highlight_lines_per_step,
          };
        });
      })()
    : cards;

  const steps: LearningStep[] = [];
  let practiceCardCount = 0;

  for (let index = 0; index < workingCards.length; index++) {
    const card = workingCards[index];
    const base = {
      cardType: card.card_type,
      estimatedSeconds: card.estimated_seconds,
      transitionText: card.next_transition || card.transition_text,
      nextCardLabel: card.next_card_label,
    };

    const title = (card.title || `Card ${index + 1}`).replace(/:+$/, "");

    // Legacy quick_practice cards with an index into practiceQuestions
    if (
      card.card_type === "quick_practice" &&
      typeof card.practice_question_index === "number" &&
      card.practice_question_index >= 0 &&
      practiceQuestions?.[card.practice_question_index]
    ) {
      steps.push({
        ...base,
        type: "practice" as const,
        title,
        question: practiceQuestions[card.practice_question_index],
        questionIndex: card.practice_question_index,
      });
      continue;
    }

    // Lean lesson practice cards: question embedded directly on the card
    const bpKeyEarly = (card.blueprint_key || card.card_type || "").toLowerCase();
    if (bpKeyEarly === "practice" && card.practice_question) {
      const hasCoding = Boolean(card.code_snippet);
      const hasChoices = Array.isArray(card.practice_choices) && card.practice_choices.length > 0;
      const questionType = hasCoding ? "coding" : hasChoices ? "multiple_choice" : "short_answer";
      const question: LessonPracticeQuestion = {
        question_type: questionType,
        question_text: card.practice_question,
        correct_answer: card.practice_answer,
        choices: hasChoices ? card.practice_choices : undefined,
        starter_code: hasCoding ? card.code_snippet : undefined,
        language: hasCoding ? (card.code_language || undefined) : undefined,
        skill_target: card.learning_job || title,
        concept_tested: title,
      };
      steps.push({
        ...base,
        type: "practice" as const,
        title,
        question,
        questionIndex: practiceCardCount,
      });
      practiceCardCount++;
      continue;
    }

    const visual = resolveCardVisual(card, visuals);

    const rawPoints = normalizeSplitMathBullets((card.points || card.bullets || [])
      .map((item) => String(item).replace(/\s+$/g, ""))
      .filter(Boolean));

    const groups = groupBulletsWithSubpoints(expandCurrentlyNowBullets(rawPoints));

    // No points — render as body-text card (single step, legacy format)
    if (groups.length === 0) {
      const body = normalizeCardTextList(card.body);
      if (body.length > 0 || visual) {
        steps.push({
          ...base,
          type: "flow_card" as const,
          title,
          body,
          bullets: [],
          card,
          visual,
        });
      }
      continue;
    }

    const bpKey = (card.blueprint_key || card.card_type || "").toLowerCase();
    const isComponentsTerms = bpKey === "components_terms";
    const isRevealBuild = REVEAL_BUILD_TYPES.has(bpKey);

    if (isComponentsTerms) {
      // Key terms: each group (term + definition sub-bullets) is one reveal unit.
      // Strip trailing colons from term (main) bullets.
      const cleanedGroups = groups.map((group) =>
        group.map((b, gi) =>
          gi === 0 ? b.replace(/:+$/, "") : b
        )
      );
      let prevLength = 0;
      for (let i = 0; i < cleanedGroups.length; i++) {
        const cumulativeBullets = cleanedGroups.slice(0, i + 1).flat();
        steps.push({
          ...base,
          type: "flow_card" as const,
          title,
          body: [],
          bullets: cumulativeBullets,
          card,
          visual: i === cleanedGroups.length - 1 ? visual : undefined,
          revealFromIndex: prevLength,
        });
        prevLength = cumulativeBullets.length;
      }
      continue;
    }

    // code_walkthrough cards used to be short-circuited here to render the
    // full code block on every page (no progressive reveal). That broke the
    // intended "code grows line-by-line as each bullet group explains the
    // next functionality" behavior. We now fall through to the shared
    // worked_example / code_walkthrough branch below, which respects
    // highlight_lines_per_step and grows maxCodeLine as bullets reveal.

    if (bpKey === "worked_example" || bpKey === "code_walkthrough") {
      const isCodingTrace =
        Array.isArray(card?.highlight_lines_per_step) &&
        card.highlight_lines_per_step.length > 0;
      const shouldRevealCodeProgressively = bpKey === "code_walkthrough";

      if (isCodingTrace) {
        // Code block trace: each bullet group is one nav step. Groups accumulate so the learner
        // sees prior context, but only the latest group's bullets are new. Code walkthroughs
        // grow progressively; coding worked_examples show the complete implementation and
        // move only the highlight as the example runs.
        // All steps share the same title (the trace's test-case title).
        let prevLength = 0;
        let maxCodeLine = 0;
        for (let i = 0; i < groups.length; i++) {
          const cumulativeBullets = groups.slice(0, i + 1).flat();
          const hlSpec = card?.highlight_lines_per_step?.[i];
          const highlightLines: [number, number] | undefined =
            Array.isArray(hlSpec) && hlSpec.length === 2 ? [hlSpec[0], hlSpec[1]] : undefined;
          if (shouldRevealCodeProgressively && highlightLines) {
            maxCodeLine = Math.max(maxCodeLine, highlightLines[1]);
          }
          steps.push({
            ...base,
            type: "flow_card" as const,
            title,
            body: [],
            bullets: cumulativeBullets,
            card,
            // Pass the code visual to EVERY reveal step, not only the last.
            // `maxCodeLine` controls how much of the code is visible at this
            // step; without the visual on every step, earlier reveals showed
            // no code at all (rendering bug surfaced in the audit).
            visual,
            revealFromIndex: prevLength,
            highlightLines,
            maxCodeLine: shouldRevealCodeProgressively && maxCodeLine > 0
              ? maxCodeLine
              : undefined,
          });
          prevLength = cumulativeBullets.length;
        }
      } else if (bpKey === "worked_example") {
        // Worked examples reveal cumulatively like other build cards: first bullet
        // appears normally, then each later point enters as a new idea.
        const flatBullets = groups.flat();
        const revealUnits = buildRevealUnits(flatBullets);
        let prevLength = 0;
        for (let i = 0; i < revealUnits.length; i++) {
          const cumulativeBullets = revealUnits.slice(0, i + 1).flat();
          steps.push({
            ...base,
            type: "flow_card" as const,
            title,
            body: [],
            bullets: cumulativeBullets,
            card,
            visual: i === revealUnits.length - 1 ? visual : undefined,
            revealFromIndex: prevLength,
          });
          prevLength = cumulativeBullets.length;
        }
      } else {
        for (let i = 0; i < groups.length; i++) {
          steps.push({
            ...base,
            type: "flow_card" as const,
            title,
            body: [],
            bullets: groups[i],
            card,
            visual: i === 0 ? visual : undefined,
            revealFromIndex: 0,
          });
        }
      }
      continue;
    }

    if (isRevealBuild) {
      // Build reveal units: Currently/Now lines stay anchored to their sub-bullets
      // (appear together in one step). All other bullets get their own step.
      const flatBullets = groups.flat();
      const revealUnits = buildRevealUnits(flatBullets);
      // Advance the visual's active step only when a reveal unit introduces a
      // new MAIN bullet (top-level idea). Sub-bullet reveals stay on the same
      // visual step so the diagram doesn't get misaligned by detail bullets.
      // Cards may carry an offset (visual_focus.active_step) — used when a
      // multi-card process sequence shares one unified step-flow visual.
      const startOffset = Math.max(0, card?.visual_focus?.active_step ?? 0);
      let mainBulletIdx = startOffset - 1;
      let prevLength = 0;
      let maxCodeLine = 0;
      for (let i = 0; i < revealUnits.length; i++) {
        const cumulativeBullets = revealUnits.slice(0, i + 1).flat();
        const unitStartsWithMainBullet = revealUnits[i].some(
          (b) => !isIndentedBullet(b),
        );
        if (unitStartsWithMainBullet) {
          mainBulletIdx += 1;
        }
        const hlSpec = card?.highlight_lines_per_step?.[i];
        const highlightLines: [number, number] | undefined =
          Array.isArray(hlSpec) && hlSpec.length === 2 ? [hlSpec[0], hlSpec[1]] : undefined;
        if (highlightLines) {
          maxCodeLine = Math.max(maxCodeLine, highlightLines[1]);
        }
        steps.push({
          ...base,
          type: "flow_card" as const,
          title,
          body: [],
          bullets: cumulativeBullets,
          card,
          visual: i === revealUnits.length - 1 ? visual : undefined,
          revealFromIndex: prevLength,
          highlightLines,
          maxCodeLine: maxCodeLine > 0 ? maxCodeLine : undefined,
          activeStepOverride: Math.max(mainBulletIdx, 0),
        });
        prevLength = cumulativeBullets.length;
      }
      continue;
    }

    {
      // One page per bullet group (idea).
      // For edge_case cards, normalize generic "Edge case N" main bullets: if a group's
      // first bullet is just a numbered placeholder, promote the first sub-bullet text.
      const isEdgeCase = bpKey === "edge_case";
      const displayGroups = isEdgeCase
        ? groups.map((group) => {
            if (
              group.length >= 2 &&
              /^edge case \d+$/i.test(group[0].trim())
            ) {
              const firstSubText = group[1].replace(/^\s*-\s*/, "").trim();
              return [firstSubText, ...group.slice(2)];
            }
            return group;
          })
        : groups;

      for (let i = 0; i < displayGroups.length; i++) {
        steps.push({
          ...base,
          type: "flow_card" as const,
          title,
          body: [],
          bullets: displayGroups[i],
          card,
          visual: i === 0 ? visual : undefined,
          revealFromIndex: 0,
        });
      }
    }
  }

  return steps;
}

function resolveCardVisual(
  card: LessonFlowCard,
  visuals?: VisualPlanItem[],
): VisualPlanItem | undefined {
  if (shouldSuppressFocusVisual(card)) {
    return undefined;
  }

  const indexedVisual =
    typeof card.visual_index === "number" && card.visual_index >= 0
      ? visuals?.[card.visual_index]
      : undefined;
  if (
    indexedVisual &&
    !shouldSuppressFocusVisual(card, indexedVisual) &&
    isLessonVisualRenderable(indexedVisual)
  ) {
    return withPreferredCardVisualType(indexedVisual, card);
  }

  const inlineVisual = card.visual_plan as VisualPlanItem | undefined;
  if (
    inlineVisual &&
    !shouldSuppressFocusVisual(card, inlineVisual) &&
    isMeaningfulCardVisual(inlineVisual) &&
    isLessonVisualRenderable(inlineVisual)
  ) {
    return withPreferredCardVisualType(inlineVisual, card);
  }

  const visualType = chooseCardVisualType(card.visual_type, card);
  if (visualType !== "none" && card.visual_description) {
    return {
      type: visualType,
      title: card.title,
      purpose: card.visual_description,
      description: card.visual_description,
      what_to_notice: card.visual_description,
      placement: "card",
    };
  }

  return indexedVisual;
}

function shouldSuppressFocusVisual(card?: LessonFlowCard, visual?: VisualPlanItem) {
  const blueprintKey = String(card?.blueprint_key || card?.card_type || "").trim().toLowerCase();

  if (
    blueprintKey === "edge_case" ||
    blueprintKey === "common_mistake" ||
    blueprintKey === "process"
  ) {
    return true;
  }

  if (blueprintKey !== "components_terms") {
    return false;
  }

  if (!visual) {
    return true;
  }

  const type = normalizeVisualType(visual.type);
  const hasWholeSystemStructure = Boolean(
    (isNodeLinkVisualType(type) && visual.nodes?.length) ||
      (isArrayStateVisualType(type) && (visual.array_values?.length || visual.array_rows?.length)) ||
      (isSourceAnnotationVisualType(type) && hasSourceAnnotationData(visual)),
  );

  return !hasWholeSystemStructure;
}

function withPreferredCardVisualType(
  visual: VisualPlanItem,
  card: LessonFlowCard,
): VisualPlanItem {
  const preferredType = chooseCardVisualType(visual.type || card.visual_type, card, visual);
  return preferredType && preferredType !== normalizeVisualType(visual.type)
    ? { ...visual, type: preferredType }
    : visual;
}

function withCardSynchronizedStepFlow(
  visual: VisualPlanItem,
  step: Extract<LearningStep, { type: "flow_card" }>,
): VisualPlanItem {
  const type = normalizeVisualType(visual.type);
  if (!isProgressiveStepFlowVisualType(type) && !isFlowVisualType(type) && !isCausalChainVisualType(type)) {
    return visual;
  }

  const mainBulletGroups = getMainBulletGroupsForCard(step.card);
  if (mainBulletGroups.length === 0) {
    return visual;
  }

  const existingSteps = visual.steps ?? [];
  const shouldMirrorMainBullets =
    isProgressiveStepFlowVisualType(type) &&
    (!stepFlowStepsMatchMainBullets(existingSteps, mainBulletGroups) ||
      existingSteps.length !== mainBulletGroups.length);

  if (!shouldMirrorMainBullets && existingSteps.length >= mainBulletGroups.length) {
    return visual;
  }

  return {
    ...visual,
    steps: mainBulletGroups.map((group, index) =>
      visualStepFromBulletGroup(
        group,
        shouldMirrorMainBullets ? undefined : existingSteps[index],
        index,
      ),
    ),
  };
}

function stepFlowStepsMatchMainBullets(
  steps: VisualStep[],
  mainBulletGroups: string[][],
) {
  if (steps.length !== mainBulletGroups.length) {
    return false;
  }
  return mainBulletGroups.every((group, index) => {
    const mainBullet = group.find((item) => !isIndentedBullet(item)) || "";
    const expected = normalizeStepLabelForComparison(compactStepLabel(cleanBulletText(mainBullet), index));
    const actual = normalizeStepLabelForComparison(steps[index]?.label || "");
    return expected === actual;
  });
}

function normalizeStepLabelForComparison(value: string) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function getMainBulletGroupsForCard(card?: LessonFlowCard): string[][] {
  if (!card) {
    return [];
  }

  const points = normalizeSplitMathBullets(
    (card.points || card.bullets || [])
      .map((item) => String(item).replace(/\s+$/g, ""))
      .filter(Boolean),
  );

  return groupBulletsWithSubpoints(expandCurrentlyNowBullets(points)).filter(
    (group) => group.some((item) => !isIndentedBullet(item)),
  );
}

function visualStepFromBulletGroup(
  group: string[],
  existingStep: VisualStep | undefined,
  index: number,
): VisualStep {
  const mainBullet = group.find((item) => !isIndentedBullet(item)) || `Step ${index + 1}`;
  const subBullet = group.find((item) => isIndentedBullet(item));
  const cleanedMain = cleanBulletText(mainBullet);
  const cleanedSub = subBullet ? cleanBulletText(subBullet) : "";
  const label = compactStepLabel(cleanedMain, index);
  const fallbackMiniVisual = compactStepMiniVisual(cleanedSub || cleanedMain || label);
  const existingMiniVisual = String(existingStep?.mini_visual || "").trim();
  const stepDetail = existingStep?.step_detail || existingStep?.description || cleanedSub || cleanedMain;
  const kind = normalizeVisualStepKind(existingStep?.kind || inferVisualStepKind(label, stepDetail, fallbackMiniVisual));
  const visualLabel = visualStepLabel(
    {
      kind,
      label,
      step_title: existingStep?.step_title || label,
      visual_label: existingStep?.visual_label,
      description: stepDetail,
      step_detail: stepDetail,
      mini_visual: shouldReplaceStepMiniVisual(existingMiniVisual)
        ? fallbackMiniVisual
        : existingMiniVisual,
    },
    index,
  );

  return {
    kind,
    label,
    step_title: existingStep?.step_title || label,
    visual_label: visualLabel,
    description: stepDetail,
    step_detail: stepDetail,
    mini_visual: shouldReplaceStepMiniVisual(existingMiniVisual)
      ? fallbackMiniVisual
      : existingMiniVisual,
    formula: existingStep?.formula || "",
    cases: existingStep?.cases || [],
    active: existingStep?.active ?? index === 0,
  };
}

function cleanBulletText(value: string) {
  return String(value || "")
    .replace(/^\s*-\s*/, "")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/[.;]+$/g, "");
}

function compactStepLabel(text: string, index: number) {
  const beforeColon = text.split(":")[0]?.trim();
  const source = beforeColon || text;
  const words = source
    .replace(/\([^)]*\)/g, "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 4)
    .join(" ");
  return words || `Step ${index + 1}`;
}

const VISUAL_STEP_LABEL_FALLBACKS: Record<string, string> = {
  start: "Start",
  starting_state: "Start",
  initialize: "Initialize",
  initialize_stack: "Stack Ready",
  initialize_queue: "Queue Ready",
  loop: "Loop",
  repeat: "Repeat",
  pop: "Pop",
  pop_current: "Pop Node",
  dequeue: "Dequeue",
  dequeue_current: "Dequeue",
  select_current: "Pick Node",
  visit: "Visit",
  visit_current: "Visit",
  check_neighbors: "Check",
  push: "Push",
  push_unvisited: "Push New",
  enqueue: "Enqueue",
  enqueue_unvisited: "Enqueue New",
  mark_visited: "Mark",
  update_state: "Update",
  compare: "Compare",
  swap: "Swap",
  choose_mid: "Midpoint",
  discard_left: "Move Right",
  discard_right: "Move Left",
  recurse: "Recurse",
  recurse_left: "Go Left",
  recurse_right: "Go Right",
  return_value: "Return",
  output: "Output",
  complete: "Done",
};

function normalizeVisualStepKind(value: unknown) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function inferVisualStepKind(...values: Array<unknown>) {
  const text = values.map((value) => String(value || "").toLowerCase()).join(" ");
  const checks: Array<[string, string[]]> = [
    ["dequeue_current", ["dequeue"]],
    ["pop_current", ["pop"]],
    ["check_neighbors", ["neighbor", "check"]],
    ["push_unvisited", ["push"]],
    ["enqueue_unvisited", ["enqueue"]],
    ["mark_visited", ["mark", "visited"]],
    ["choose_mid", ["mid"]],
    ["choose_mid", ["middle"]],
    ["compare", ["compare"]],
    ["swap", ["swap"]],
    ["recurse_left", ["recurse left", "left child"]],
    ["recurse_right", ["recurse right", "right child"]],
    ["recurse", ["recurse"]],
    ["update_state", ["update", "now", "state"]],
    ["loop", ["each iteration", "repeat", "while"]],
    ["output", ["output", "result"]],
    ["complete", ["done"]],
    ["complete", ["complete"]],
    ["complete", ["finish"]],
    ["initialize_stack", ["initialize", "stack"]],
    ["initialize_stack", ["stack is empty", "empty stack"]],
    ["initialize_queue", ["initialize", "queue"]],
    ["initialize_queue", ["queue is empty", "empty queue"]],
    ["starting_state", ["starting state", "currently"]],
  ];

  return checks.find(([, needles]) => needles.every((needle) => text.includes(needle)))?.[0] || "";
}

function cleanVisualStepLabel(value: unknown) {
  return String(value || "")
    .replace(/\s+/g, " ")
    .replace(/^[A-Za-z]+\s*[-–—]\s*/g, "")
    .trim()
    .replace(/[,:.;]+$/g, "");
}

function isValidVisualStepLabel(value: unknown, detail?: unknown) {
  const cleaned = cleanVisualStepLabel(value);
  if (!cleaned || cleaned.length > 24) return false;
  if (cleaned.split(/\s+/).filter(Boolean).length > 4) return false;
  if (/[,:.;]$/.test(String(value || "").trim())) return false;
  if (/^(action|currently|now)$/i.test(cleaned)) return false;

  const detailWords = String(detail || "").toLowerCase().split(/\s+/).filter(Boolean);
  const labelWords = cleaned.toLowerCase().split(/\s+/).filter(Boolean);
  if (
    detailWords.length > labelWords.length + 2 &&
    labelWords.length > 0 &&
    labelWords.every((word, index) => detailWords[index] === word)
  ) {
    return false;
  }

  return true;
}

function visualStepLabel(step: VisualStep, index: number) {
  const detail = step.step_detail || step.description || step.label || "";
  const kind = normalizeVisualStepKind(step.kind) || inferVisualStepKind(step.label, detail, step.mini_visual);
  const candidates = [
    step.visual_label,
    kind ? VISUAL_STEP_LABEL_FALLBACKS[kind] : "",
    step.step_title,
    step.label,
  ];

  for (const candidate of candidates) {
    if (isValidVisualStepLabel(candidate, detail)) {
      return cleanVisualStepLabel(candidate);
    }
  }

  const compact = compactStepLabel(String(step.label || detail || ""), index);
  return isValidVisualStepLabel(compact, detail) ? cleanVisualStepLabel(compact) : `Step ${index + 1}`;
}

function uniqueVisualStepLabels(steps: VisualStep[]) {
  const used = new Set<string>();

  return steps.map((step, index) => {
    const initial = visualStepLabel(step, index);
    const initialKey = initial.toLowerCase();
    if (!used.has(initialKey)) {
      used.add(initialKey);
      return initial;
    }

    const detail = step.step_detail || step.description || "";
    const candidates = [
      step.step_title,
      step.label,
      step.mini_visual,
      `Step ${index + 1}`,
    ];

    for (const candidate of candidates) {
      const cleaned = cleanVisualStepLabel(candidate);
      const key = cleaned.toLowerCase();
      if (isValidVisualStepLabel(cleaned, detail) && !used.has(key)) {
        used.add(key);
        return cleaned;
      }
    }

    const fallback = `Step ${index + 1}`;
    used.add(fallback.toLowerCase());
    return fallback;
  });
}

function compactStepMiniVisual(text: string) {
  const normalized = text.replace(/\([^)]*\)/g, "").replace(/\s+/g, " ").trim();
  const lower = normalized.toLowerCase();

  const phrasePatterns = [
    /\bstack\s+is\s+empty\b/i,
    /\boutput\s+is\s+empty\b/i,
    /\bcurrent\s*=\s*[^,.;]+/i,
    /\bstack\s*=\s*[^,.;]+/i,
    /\boutput\s*=\s*[^,.;]+/i,
    /\bgo\s+to\s+node\.(left|right)\b/i,
    /\bmove\s+to\s+(left|right)\s+child\b/i,
    /\bvisit\s+(current|root|node)\b/i,
    /\bpush\s+[^,.;]+/i,
    /\bpop\s+[^,.;]+/i,
    /\breturn\s+[^,.;]+/i,
  ];

  for (const pattern of phrasePatterns) {
    const match = normalized.match(pattern);
    if (match?.[0]) {
      return limitWords(match[0], 5);
    }
  }

  if (/\bempty\b/.test(lower) && /\bstack\b/.test(lower)) {
    return "stack is empty";
  }
  if (/\bno\s+more\s+left\b|\bnull\s+left\b|\bleft\s+child\s+is\s+null\b/.test(lower)) {
    return "left child is null";
  }
  if (/\bno\s+right\b|\bnull\s+right\b|\bright\s+child\s+is\s+null\b/.test(lower)) {
    return "right child is null";
  }

  const stateMatch = normalized.match(/\b(current|stack|output|node|left|right|root)\b[^,.;]*/i);
  const source = stateMatch?.[0] || normalized;
  return limitWords(source, 5);
}

function shouldReplaceStepMiniVisual(value: string) {
  if (!value) {
    return true;
  }

  const wordCount = value.split(/\s+/).filter(Boolean).length;
  return (
    wordCount > 5 ||
    /\b(and|because|indicating|continuing|during|while|until|with|where)\s*$/i.test(value) ||
    /\b(stack is empty and no|current now points to|the visualization may|a bst root)\b/i.test(value)
  );
}

function limitWords(value: string, maxWords: number) {
  return String(value || "")
    .replace(/\s+/g, " ")
    .trim()
    .split(/\s+/)
    .slice(0, maxWords)
    .join(" ");
}

function chooseCardVisualType(
  rawType: string | undefined,
  card: LessonFlowCard,
  visual?: VisualPlanItem,
) {
  const currentType = normalizeVisualType(rawType);
  const text = [
    card.title,
    card.visual_description,
    visual?.title,
    visual?.description,
    visual?.purpose,
    visual?.what_to_notice,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

  if (
    (currentType === "concept_map" ||
      currentType === "topic_snapshot" ||
      currentType === "concept_snapshot" ||
      currentType === "visual") &&
    /\bmerge\s+sort\b/.test(text)
  ) {
    return "array_state_diagram";
  }

  if (
    (currentType === "array_state_diagram" ||
      currentType === "concept_map" ||
      currentType === "topic_snapshot" ||
      currentType === "visual") &&
    isDivideAndConquerOverviewVisual(text)
  ) {
    return "progressive_step_flow";
  }

  if (
    (currentType === "step_flow" || currentType === "visual" || currentType === "chart") &&
    /\b(pdf|cdf|normal distribution|normally distributed|curve|density|area under|x=|y=|probability)\b/.test(text)
  ) {
    return "graph_chart";
  }

  return currentType;
}

function normalizeCardTextList(value?: string[]) {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((item) => String(item).trim())
    .filter(Boolean)
    .slice(0, 5);
}

const CARD_TYPE_LABELS: Record<string, string> = {
  background: "Background",
  purpose_context: "Background",
  purpose: "Purpose",
  intro: "Introduction",
  hook: "Why it matters",
  core_idea: "Core concept",
  concept: "Core concept",
  definition: "Definition",
  intuition: "Intuition",
  example: "Example",
  worked_example: "Worked example",
  comparison: "Comparison",
  edge_case: "Edge case",
  method_process: "Method",
  process_step: "Step",
  formula: "Formula",
  visual: "Visual",
  quick_practice: "Practice",
  micro_check: "Quick check",
  summary: "Summary",
  bridge_to_next_topic: "Up next",
};

function getStepTypeLabel(step: LearningStep) {
  const cardBlueprintKey = "card" in step ? step.card?.blueprint_key : undefined;
  const rawType =
    cardBlueprintKey ||
    step.cardType ||
    (step.type === "practice" ? "quick_practice" : step.type);

  return CARD_TYPE_LABELS[rawType] ?? rawType.replace(/_/g, " ");
}

function getEstimatedTimeLabel(seconds?: number) {
  if (!seconds) {
    return "Quick card";
  }

  if (seconds < 60) {
    return `${seconds} sec`;
  }

  const minutes = Math.round(seconds / 60);
  return `${minutes} min`;
}

function getStoredPacingMode(studyPathId: string): PacingMode {
  if (typeof window === "undefined") {
    return "balanced";
  }

  const storedPacing = window.localStorage.getItem(
    `azalea.pacing.${studyPathId}`,
  );

  if (
    storedPacing === "fast" ||
    storedPacing === "balanced" ||
    storedPacing === "deep"
  ) {
    return storedPacing;
  }

  return "balanced";
}

function getDefaultFlowMetrics(): FlowMetrics {
  return {
    cardsCompleted: 0,
    topicsCompleted: 0,
    quickChecks: 0,
    quickCheckCorrect: 0,
    skips: 0,
    questionsAsked: 0,
    totalTransitionMs: 0,
    transitionCount: 0,
  };
}

function getFlowMetricsKey(studyPathId: string) {
  return `azalea.flowMetrics.${studyPathId}`;
}

function getFlowMetrics(studyPathId: string): FlowMetrics {
  if (typeof window === "undefined") {
    return getDefaultFlowMetrics();
  }

  try {
    const raw = window.localStorage.getItem(getFlowMetricsKey(studyPathId));
    return raw
      ? { ...getDefaultFlowMetrics(), ...JSON.parse(raw) }
      : getDefaultFlowMetrics();
  } catch {
    return getDefaultFlowMetrics();
  }
}

function recordFlowMetric(
  studyPathId: string,
  update: (metrics: FlowMetrics) => void,
) {
  if (typeof window === "undefined") {
    return;
  }

  const metrics = getFlowMetrics(studyPathId);
  update(metrics);
  window.localStorage.setItem(
    getFlowMetricsKey(studyPathId),
    JSON.stringify(metrics),
  );
}

function recordTransitionMetric(
  studyPathId: string,
  lastTransitionAtRef: MutableRefObject<number | null>,
) {
  const now = Date.now();
  const previous = lastTransitionAtRef.current;
  lastTransitionAtRef.current = now;

  if (!previous) {
    return;
  }

  recordFlowMetric(studyPathId, (metrics) => {
    metrics.totalTransitionMs += now - previous;
    metrics.transitionCount += 1;
  });
}

function getPacingInstruction(mode: PacingMode) {
  if (mode === "fast") {
    return {
      lessonGenerationNote:
        "Pacing mode: Fast. Use shorter explanation cards, more examples, fewer definitions when likely known, and quick checks only.",
      regenerationNote:
        "Regenerate in Fast pacing mode: compress explanations, keep cards short, and prioritize examples plus quick checks.",
    };
  }

  if (mode === "deep") {
    return {
      lessonGenerationNote:
        "Pacing mode: Deep. Add more intuition, edge cases, and detailed reasoning while preserving tiny sequential cards.",
      regenerationNote:
        "Regenerate in Deep pacing mode: add intuition, edge cases, and reasoning detail without creating long text walls.",
    };
  }

  return {
    lessonGenerationNote:
      "Pacing mode: Balanced. Use normal explanation depth, examples, practice, and concise bridges.",
    regenerationNote:
      "Regenerate in Balanced pacing mode: keep the default explanation depth with examples, practice, and concise bridges.",
  };
}

function getContinueLabel({
  currentStep,
  nextStep,
  isLastStep,
}: {
  currentStep?: LearningStep;
  nextStep?: LearningStep;
  isLastStep: boolean;
}) {
  void currentStep;
  void nextStep;
  void isLastStep;
  return "Next";
}

function shouldShowStepForStartingMode(
  startingMode: StartingMode | null,
  step: LearningStep,
) {
  if (!startingMode || startingMode === "full_teach") {
    return true;
  }

  if (step.type === "flow_card" || step.type === "practice") {
    const cardType = step.cardType || (step.type === "practice" ? "quick_practice" : "");

    if (startingMode === "compressed_refresher") {
      return !["intro", "source_preview"].includes(cardType);
    }

    if (startingMode === "nuance_first") {
      return [
        "purpose_context",
        "core_idea",
        "worked_example",
        "edge_case",
        "quick_practice",
        "summary",
        "bridge_to_next_topic",
      ].includes(cardType);
    }

    if (startingMode === "edge_cases") {
      return [
        "edge_case",
        "quick_practice",
        "summary",
        "bridge_to_next_topic",
      ].includes(cardType);
    }

    return [
      "worked_example",
      "edge_case",
      "common_mistake",
      "quick_practice",
      "summary",
      "bridge_to_next_topic",
    ].includes(cardType);
  }

  if (startingMode === "compressed_refresher") {
    return [
      "Purpose & Context",
      "Core Idea",
      "Components / Definitions",
      "Worked Example",
      "Edge Cases / Common Mistakes",
      "Practice",
      "Key Takeaways",
      "Source Grounding",
    ].some((title) => step.title.startsWith(title));
  }

  if (startingMode === "nuance_first") {
    return [
      "Purpose & Context",
      "Core Idea",
      "Edge Cases / Common Mistakes",
      "Worked Example",
      "Edge Cases",
      "Practice",
      "Key Takeaways",
      "Source Grounding",
    ].some((title) => step.title.startsWith(title));
  }

  if (startingMode === "edge_cases") {
    return [
      "Edge Cases / Common Mistakes",
      "Edge Cases",
      "Practice",
      "Key Takeaways",
      "Source Grounding",
    ].some((title) => step.title.startsWith(title));
  }

  return [
    "Practice",
    "Worked Example",
    "Edge Cases",
    "Key Takeaways",
    "Source Grounding",
  ].some((title) => step.title.startsWith(title));
}

function EmptyLearningState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-2xl border border-dashed border-border bg-muted/30 p-8 text-center">
      <p className="font-semibold text-foreground">{title}</p>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">
        {description}
      </p>
    </div>
  );
}

function OrientationMiniCard({ label, value }: { label: string; value: string }) {
  return (
    <section className="rounded-3xl border border-border bg-background p-5 shadow-sm">
      <p className="text-xs font-bold uppercase tracking-wide text-primary">
        {label}
      </p>
      <p className="mt-3 text-base leading-7 text-foreground">{value}</p>
    </section>
  );
}

function VisualRenderer({
  visual,
  index,
  focusState,
}: {
  visual: VisualPlanItem;
  index: number;
  focusState?: VisualFocusState | null;
}) {
  // Visual DEBUG mode: show the data that WOULD generate this visual, not the drawing.
  if (SHOW_VISUAL_DATA_INSTEAD_OF_RENDER) {
    const v = visual as unknown as Record<string, unknown>;
    const sections: { label: string; value: unknown }[] = [
      { label: "Type", value: String(v.type ?? "—") },
    ];
    if (v.title) sections.push({ label: "Title", value: String(v.title) });
    if (v.visual_description) sections.push({ label: "Visual description", value: String(v.visual_description) });
    if (v.description) sections.push({ label: "Description", value: String(v.description) });
    if (focusState) sections.push({ label: "Focus state", value: focusState });
    sections.push({ label: "Full visual", value: visual });
    return (
      <VisualDataPanel
        title={String(v.type ?? "visual") + (v.title ? ` · ${String(v.title)}` : "")}
        sections={sections}
      />
    );
  }

  const type = normalizeVisualType(visual.type);

  if (isCompositeVisualType(type) && visual.children?.length) {
    return <VisualCompositeStack visual={visual} index={index} focusState={focusState} />;
  }

  if (isNodeLinkVisualType(type)) {
    const nodeLinkVisual = withInferredNodeLinkData(visual);
    if (nodeLinkVisual.nodes?.length) {
      return <VisualNodeLinkDiagram visual={nodeLinkVisual} index={index} focusState={focusState} />;
    }
  }

  if (isCircuitVisualType(type) && (visual.components?.length || visual.wires?.length)) {
    return <VisualCircuitDiagram visual={visual} index={index} />;
  }

  if (isArrayStateVisualType(type)) {
    const arrayVisual = withInferredArrayStateData(visual);
    if (arrayVisual.array_values?.length || arrayVisual.array_rows?.length) {
      return <VisualArrayStateDiagram visual={arrayVisual} index={index} />;
    }
  }

  if (isInteractiveVisualType(type) && hasInteractiveVisualData(visual)) {
    return <VisualInteractiveChange visual={visual} index={index} />;
  }

  if (isSpatialVisualType(type)) {
    const spatialVisual = withInferredSpatialData(visual);
    if (hasSpatialVisualData(spatialVisual)) {
      return <VisualSpatialDiagram visual={spatialVisual} index={index} />;
    }
  }

  if (isSourceAnnotationVisualType(type) && hasSourceAnnotationData(visual)) {
    return <VisualSourceAnnotation visual={visual} index={index} />;
  }

  if (isRelationshipMapVisualType(type)) {
    const relVisual = withInferredConceptMapData(visual);
    if (relVisual.center || relVisual.nodes?.length) {
      return <VisualRelationshipMap visual={relVisual} index={index} />;
    }
  }

  if (isEdgeCaseSnapshotVisualType(type)) {
    const ecVisual = withInferredConceptMapData(visual);
    return <VisualEdgeCaseSnapshot visual={ecVisual} index={index} />;
  }

  if (isProgressiveStepFlowVisualType(type)) {
    const flowVisual = withInferredStepData(visual, "flow");
    if (flowVisual.steps?.length) {
      return <VisualProgressiveStepFlow visual={flowVisual} index={index} focusState={focusState} />;
    }
  }

  if (isPathProgressVisualType(type)) {
    const pathVisual = withInferredStepData(visual, "path");
    if (pathVisual.steps?.length) {
      return <VisualPathProgress visual={pathVisual} index={index} />;
    }
  }

  if (isCodeTraceVisualType(type) && visual.code) {
    return <VisualCodeBlock visual={visual} index={index} />;
  }

  if (isPracticeFeedbackVisualType(type) && (visual.wrong || visual.correct || visual.steps?.length)) {
    return <VisualPracticeFeedback visual={visual} index={index} />;
  }

  if (isTableVisualType(type)) {
    const tableVisual = withInferredTableData(visual, type);
    if (tableVisual.columns?.length && tableVisual.rows?.length) {
      return <VisualTable visual={tableVisual} index={index} />;
    }
  }

  if (isFlowVisualType(type)) {
    const flowVisual = withInferredStepData(visual, "flow");
    if (flowVisual.steps?.length) {
      return <VisualStepFlow visual={flowVisual} index={index} focusState={focusState} />;
    }
  }

  if (isFormulaVisualType(type)) {
    const formulaVisual = withInferredFormulaData(visual);
    if (formulaVisual.formula || formulaVisual.symbols?.length || formulaVisual.description) {
      return <VisualFormulaCard visual={formulaVisual} index={index} />;
    }
  }

  if (isConceptMapVisualType(type)) {
    const conceptVisual = withInferredConceptMapData(visual);
    if (conceptVisual.center || conceptVisual.nodes?.length) {
      return <VisualConceptMap visual={conceptVisual} index={index} />;
    }
  }

  if (isGraphVisualType(type)) {
    const graphVisual = withInferredGraphData(visual);
    if (graphVisual.data_points && graphVisual.data_points.length >= 2) {
      return <VisualGraph visual={graphVisual} index={index} />;
    }
  }

  if (isMisconceptionVisualType(type)) {
    const misconceptionVisual = withInferredMisconceptionData(visual);
    if (misconceptionVisual.wrong || misconceptionVisual.correct) {
      return <VisualMisconception visual={misconceptionVisual} index={index} />;
    }
  }

  if (isCausalChainVisualType(type)) {
    const chainVisual = withInferredStepData(visual, "chain");
    if (chainVisual.steps?.length) {
      return <VisualCausalChain visual={chainVisual} index={index} />;
    }
  }

  return <VisualFallbackCard visual={visual} index={index} />;
}

function normalizeVisualType(type: string | undefined) {
  const normalized = (type || "visual").trim().toLowerCase().replace(/\s+/g, "_");
  if (normalized === "code_block") return "code_trace";
  return normalized;
}

function isTableVisualType(type: string) {
  return (
    type === "concept_table" ||
    type === "comparison_table" ||
    type === "state_change" ||
    type === "example_trace" ||
    type.includes("worked_example_trace") ||
    type.includes("worked_solution") ||
    type.includes("before_after") ||
    type.includes("annotated_worked_solution") ||
    type.includes("what_changed") ||
    type.includes("same_different") ||
    type.includes("matrix") ||
    type.includes("venn") ||
    type.includes("table") ||
    (type.includes("trace") && !isCodeTraceVisualType(type))
  );
}

function isProgressiveStepFlowVisualType(type: string) {
  return type === "progressive_step_flow";
}

function isFlowVisualType(type: string) {
  return (
    !isProgressiveStepFlowVisualType(type) &&
    (type === "step_flow" ||
    type === "state_change" ||
    type.includes("process_flow") ||
    type.includes("flowchart") ||
    type.includes("flow") ||
    type.includes("process") ||
    type.includes("pipeline") ||
    type.includes("timeline") ||
    type.includes("step_timeline") ||
    type.includes("sequence") ||
    type.includes("state_transition"))
  );
}

function isFormulaVisualType(type: string) {
  return (
    type === "formula_card" ||
    type.includes("formula_breakdown") ||
    type.includes("formula_breakdown") ||
    type.includes("formula_annotation") ||
    type.includes("symbol_breakdown") ||
    type.includes("term_grouping") ||
    type.includes("plain_english") ||
    type.includes("symbol_by_symbol") ||
    type.includes("color_coded") ||
    type.includes("term_group") ||
    type.includes("formula") ||
    type.includes("equation") ||
    type.includes("notation")
  );
}

function isRelationshipMapVisualType(type: string) {
  return type === "relationship_map";
}

function isEdgeCaseSnapshotVisualType(type: string) {
  return type === "edge_case_snapshot";
}

function isConceptMapVisualType(type: string) {
  return (
    type === "concept_map" ||
    type === "topic_snapshot" ||
    type === "concept_snapshot" ||
    type.includes("concept_structure") ||
    type.includes("concept_map") ||
    type.includes("component_breakdown") ||
    type.includes("hierarchy_tree") ||
    type.includes("system_map") ||
    type.includes("framework_map") ||
    type.includes("argument_map") ||
    type.includes("theme_map") ||
    type.includes("idea_parts") ||
    type.includes("labeled_diagram") ||
    type.includes("structure_visual") ||
    type.includes("labeled_diagram") ||
    type.includes("parts_card")
  );
}

function isGraphVisualType(type: string) {
  return (
    type === "graph" ||
    type === "chart" ||
    type.includes("graph_chart") ||
    type.includes("line_graph") ||
    type.includes("scatter") ||
    type.includes("bar_chart") ||
    type.includes("histogram") ||
    type.includes("growth_rate") ||
    type.includes("area_under_curve") ||
    type.includes("runtime_growth") ||
    type.includes("confidence_interval") ||
    type.includes("coordinate_plane") ||
    type.includes("supply_demand") ||
    type.includes("loss_curve") ||
    type.includes("graph") ||
    type.includes("plot") ||
    type.includes("curve") ||
    type.includes("distribution")
  );
}

function isCodeTraceVisualType(type: string) {
  const normalized = normalizeVisualType(type);
  return (
    normalized === "code_trace" ||
    normalized.includes("coding_visual") ||
    normalized.includes("coding_specific") ||
    normalized.includes("array_trace") ||
    normalized.includes("dp_table") ||
    normalized.includes("call_stack") ||
    normalized.includes("linked_list") ||
    normalized.includes("graph_traversal") ||
    normalized.includes("database_relationship") ||
    normalized.includes("request_flow") ||
    normalized.includes("memory_diagram") ||
    normalized.includes("memory_box") ||
    normalized.includes("stack_heap") ||
    normalized.includes("frontend_backend") ||
    normalized.includes("api_flow") ||
    normalized.includes("object_state") ||
    normalized.includes("variable_timeline") ||
    normalized.includes("stack_frame") ||
    normalized.includes("pointer_diagram") ||
    normalized.includes("recursion_tree")
  );
}

function isCompositeVisualType(type: string) {
  const normalized = normalizeVisualType(type);
  return (
    normalized === "runtime_code_trace" ||
    normalized === "composite" ||
    normalized === "visual_stack" ||
    normalized === "dual_panel"
  );
}

function isArrayStateVisualType(type: string) {
  return (
    type === "array_state_diagram" ||
    type.includes("array_state") ||
    type.includes("sliding_window") ||
    type.includes("two_pointer") ||
    type.includes("two_pointers") ||
    type.includes("pointer_window") ||
    type.includes("array_window") ||
    type.includes("array_pointer")
  );
}

function isNodeLinkVisualType(type: string) {
  return (
    type.includes("node_link") ||
    type.includes("tree_diagram") ||
    type.includes("tree_traversal") ||
    type.includes("binary_tree") ||
    type.includes("bst_diagram") ||
    type.includes("graph_diagram") ||
    type.includes("linked_node") ||
    type.includes("traversal_diagram")
  );
}

function isCircuitVisualType(type: string) {
  return (
    type.includes("circuit") ||
    type.includes("logic_gate") ||
    type.includes("digital_logic") ||
    type.includes("hardware_diagram") ||
    type.includes("schematic")
  );
}

function isMisconceptionVisualType(type: string) {
  return (
    type === "misconception" ||
    type.includes("misconception_visual") ||
    type.includes("mistake") ||
    type.includes("wrong_right") ||
    type.includes("seems_true") ||
    type.includes("repair") ||
    type.includes("misconception") ||
    type.includes("mistake_vs") ||
    type.includes("wrong_vs") ||
    type.includes("correct_vs") ||
    type.includes("counterexample") ||
    type.includes("mental_model")
  );
}

function isCausalChainVisualType(type: string) {
  return (
    type === "causal_chain" ||
    type.includes("cause_effect") ||
    type.includes("cause_and_effect") ||
    type.includes("causal_chain") ||
    type.includes("cause_effect") ||
    type.includes("input_output") ||
    type.includes("because_arrow") ||
    type.includes("dependency_graph") ||
    type.includes("feedback_loop")
  );
}

function isSpatialVisualType(type: string) {
  return (
    type.includes("spatial") ||
    type.includes("spatial_geometric") ||
    type.includes("geometric") ||
    type.includes("geometry") ||
    type.includes("vector") ||
    type.includes("matrix_transformation") ||
    type.includes("geometric_construction") ||
    type.includes("spatial_relationship") ||
    type.includes("force_diagram") ||
    type.includes("molecular") ||
    type.includes("anatomy") ||
    type.includes("transformation_visual") ||
    type.includes("shape_breakdown")
  );
}

function isInteractiveVisualType(type: string) {
  return (
    type.includes("interactive") ||
    type.includes("interactive_change") ||
    type.includes("what_changes") ||
    type.includes("slider") ||
    type.includes("toggle") ||
    type.includes("simulator") ||
    type.includes("parameter")
  );
}

function isSourceAnnotationVisualType(type: string) {
  return (
    type.includes("source_annotation") ||
    type.includes("annotated_screenshot") ||
    type.includes("screenshot_region") ||
    type.includes("annotated_source") ||
    type.includes("highlighted_source") ||
    type.includes("margin_explanation") ||
    type.includes("source_bridge")
  );
}

function isPathProgressVisualType(type: string) {
  return (
    type === "path_progress" ||
    type.includes("path_map") ||
    type.includes("learning_path") ||
    type.includes("progress_visual") ||
    type.includes("topic_dependency") ||
    type.includes("dependency_tree") ||
    type.includes("mastery_meter") ||
    type.includes("concept_graph") ||
    type.includes("you_are_here") ||
    type.includes("review_queue") ||
    type.includes("weak_area") ||
    type.includes("heatmap")
  );
}

function isPracticeFeedbackVisualType(type: string) {
  return (
    type.includes("practice_feedback") ||
    type.includes("mini_repair") ||
    type.includes("answer_comparison") ||
    type.includes("mistake_highlight") ||
    type.includes("reasoning_trace") ||
    type.includes("gap_map") ||
    type.includes("user_solution") ||
    type.includes("next_step_visual")
  );
}

function getVisualTypeLabel(type: string | undefined) {
  const normalizedType = normalizeVisualType(type);

  if (normalizedType.includes("concept_structure")) {
    return "Concept Structure";
  }

  if (normalizedType.includes("process_flow")) {
    return "Process Flow";
  }

  if (normalizedType.includes("formula_breakdown")) {
    return "Formula Breakdown";
  }

  if (
    normalizedType.includes("worked_example_trace") ||
    normalizedType === "example_trace"
  ) {
    return "Example Trace";
  }

  if (
    normalizedType.includes("comparison_visual") ||
    normalizedType === "comparison_table"
  ) {
    return "Comparison";
  }

  if (
    normalizedType.includes("cause_effect") ||
    normalizedType.includes("causal_chain")
  ) {
    return "Cause and Effect";
  }

  if (
    normalizedType.includes("state_change") ||
    normalizedType.includes("coding_visual")
  ) {
    return "State Change";
  }

  if (normalizedType.includes("graph_chart")) {
    return "Graph";
  }

  if (normalizedType.includes("spatial_geometric")) {
    return "Spatial";
  }

  if (normalizedType.includes("interactive_change")) {
    return "Interactive";
  }

  if (normalizedType.includes("misconception_visual")) {
    return "Misconception";
  }

  if (normalizedType.includes("learning_path")) {
    return "Learning Path";
  }

  if (isNodeLinkVisualType(normalizedType)) {
    return "Node Link Diagram";
  }

  if (isCircuitVisualType(normalizedType)) {
    return "Circuit Diagram";
  }

  if (isTableVisualType(normalizedType)) {
    return "Table";
  }

  if (isFlowVisualType(normalizedType)) {
    return "Flow";
  }

  if (isFormulaVisualType(normalizedType)) {
    return "Formula";
  }

  if (isConceptMapVisualType(normalizedType)) {
    return "Concept Map";
  }

  if (isGraphVisualType(normalizedType)) {
    return "Graph";
  }

  if (isCodeTraceVisualType(normalizedType)) {
    return "Code Trace";
  }

  if (isArrayStateVisualType(normalizedType)) {
    return "Array State";
  }

  if (isMisconceptionVisualType(normalizedType)) {
    return "Misconception";
  }

  if (isCausalChainVisualType(normalizedType)) {
    return "Causal Chain";
  }

  if (isSpatialVisualType(normalizedType)) {
    return "Spatial";
  }

  if (isInteractiveVisualType(normalizedType)) {
    return "Interactive";
  }

  if (isSourceAnnotationVisualType(normalizedType)) {
    return "Source";
  }

  if (isPathProgressVisualType(normalizedType)) {
    return "Path";
  }

  if (isPracticeFeedbackVisualType(normalizedType)) {
    return "Feedback";
  }

  return "Visual";
}

function hasInteractiveVisualData(visual: VisualPlanItem) {
  return Boolean(
    visual.rows?.length ||
      visual.data_points?.length ||
      visual.steps?.length ||
      visual.nodes?.length,
  );
}

function hasSpatialVisualData(visual: VisualPlanItem) {
  return Boolean(
    visual.nodes?.length ||
      visual.key_points?.length ||
      visual.steps?.length ||
      visual.elements?.length ||
      visual.center,
  );
}

function hasSourceAnnotationData(visual: VisualPlanItem) {
  return Boolean(
    visual.code ||
      visual.center ||
      visual.nodes?.length ||
      visual.labels?.length ||
      visual.rows?.length,
  );
}

function tokenizeFormula(formula: string) {
  return formula
    .split(/(\s+|[=+\-*/^(){}\[\],:<>|])/)
    .filter((part) => part.length > 0);
}

function formulaTokenClassName(token: string) {
  if (/^\s+$/.test(token)) {
    return "";
  }

  if (/^[=+\-*/^(){}\[\],:<>|]$/.test(token)) {
    return "mx-1 text-primary";
  }

  if (/^\d+(\.\d+)?$/.test(token)) {
    return "rounded-md bg-background/70 px-1.5 py-0.5 text-[#2E9D77]";
  }

  return "rounded-md bg-background px-1.5 py-0.5 text-foreground";
}

function VisualHeader({
  visual: _visual,
  index: _index,
}: {
  visual: VisualPlanItem;
  index: number;
}) {
  return null;
}

function VisualTable({
  visual,
  index,
}: {
  visual: VisualPlanItem;
  index: number;
}) {
  const columns = visual.columns ?? [];
  const rows = visual.rows ?? [];
  const visualType = normalizeVisualType(visual.type);
  const firstColumnIsLabel = columns.length > 1;
  const isComparisonTable =
    visualType === "comparison_table" ||
    visualType.includes("comparison") ||
    visualType.includes("same_different");

  if (columns.length === 0 || rows.length === 0) {
    return <VisualFallbackCard visual={visual} index={index} />;
  }

  if (isComparisonTable && columns.length >= 2) {
    return (
      <VisualComparisonTable
        visual={visual}
        index={index}
        columns={columns}
        rows={rows}
      />
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-background shadow-sm">
      <div className="border-b border-border bg-muted/30 p-4">
        <VisualHeader visual={visual} index={index} />

        {visual.purpose && (
          <p className="text-sm leading-6 text-muted-foreground">
            {visual.purpose}
          </p>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-left text-sm">
          <thead className="bg-accent text-foreground">
            <tr>
              {columns.map((column, columnIndex) => (
                <th
                  key={`${column}-${columnIndex}`}
                  className="border-b border-border px-4 py-3 font-bold"
                  scope="col"
                >
                  {column}
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {rows.map((row, rowIndex) => (
              <tr
                key={rowIndex}
                className={
                  visualType === "example_trace"
                    ? "bg-background"
                    : rowIndex % 2 === 0
                      ? "bg-background"
                      : "bg-muted/30"
                }
              >
                {columns.map((_, cellIndex) => (
                  <td
                    key={`${rowIndex}-${cellIndex}`}
                    className={`border-b border-border px-4 py-3 leading-6 ${
                      firstColumnIsLabel && cellIndex === 0
                        ? "font-bold text-foreground"
                        : "text-[#5D6472]"
                    }`}
                  >
                    {visualType === "example_trace" && cellIndex === 0 ? (
                      <span className="inline-flex min-h-7 min-w-7 items-center justify-center rounded-full bg-[#E8F7F1] px-2 text-xs font-bold text-[#2E9D77]">
                        {row[cellIndex] ?? rowIndex + 1}
                      </span>
                    ) : (
                      (row[cellIndex] ?? "")
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function VisualComparisonTable({
  visual,
  index,
  columns,
  rows,
}: {
  visual: VisualPlanItem;
  index: number;
  columns: string[];
  rows: VisualTableRow[];
}) {
  const criterionHeader = columns[0] || "Point";
  const comparisonHeaders = columns.slice(1);
  const gridTemplateColumns = `minmax(11rem, 0.8fr) repeat(${comparisonHeaders.length}, minmax(13rem, 1fr))`;

  return (
    <div className="rounded-2xl border border-border bg-background p-4 shadow-sm">
      <VisualHeader visual={visual} index={index} />

      {visual.purpose && (
        <p className="mb-4 text-sm leading-6 text-muted-foreground">
          {visual.purpose}
        </p>
      )}

      <div className="overflow-x-auto pb-1">
        <div
          className="min-w-[640px] space-y-3"
          style={{
            minWidth: `${Math.max(640, (comparisonHeaders.length + 1) * 220)}px`,
          }}
        >
          <div
            className="grid gap-3 px-1 text-xs font-black uppercase tracking-wide text-muted-foreground"
            style={{ gridTemplateColumns }}
          >
            <div>{criterionHeader}</div>
            {comparisonHeaders.map((header, headerIndex) => (
              <div key={`${header}-${headerIndex}`}>{header}</div>
            ))}
          </div>

          {rows.map((row, rowIndex) => {
            const isHighlighted = visual.highlight_row === rowIndex;

            return (
              <div
                key={rowIndex}
                className={[
                  "grid gap-3 rounded-2xl border p-3 transition",
                  isHighlighted
                    ? "border-primary/60 bg-primary/[0.035] shadow-[0_10px_28px_rgba(124,78,240,0.12)]"
                    : "border-border bg-muted/20",
                ].join(" ")}
                style={{ gridTemplateColumns }}
              >
                <div className="flex min-h-24 items-center rounded-xl border border-border bg-background p-4">
                  <p className="text-sm font-black leading-5 text-foreground">
                    {row[0] || `Point ${rowIndex + 1}`}
                  </p>
                </div>

                {comparisonHeaders.map((_, cellIndex) => (
                  <div
                    key={`${rowIndex}-${cellIndex}`}
                    className="min-h-24 rounded-xl border border-border bg-background p-4"
                  >
                    <p className="text-sm leading-6 text-[#4C5563]">
                      {row[cellIndex + 1] || ""}
                    </p>
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function VisualStepFlow({
  visual,
  index,
  focusState,
}: {
  visual: VisualPlanItem;
  index: number;
  focusState?: VisualFocusState | null;
}) {
  const steps = visual.steps ?? [];
  const scrollRef = useRef<HTMLDivElement>(null);
  const activeCardRefs = useRef<(HTMLDivElement | null)[]>([]);

  const explicitActiveIndex = steps.findIndex((step) => step.active);
  const inferredActiveIndex =
    typeof visual.highlight_row === "number" &&
    visual.highlight_row >= 0 &&
    visual.highlight_row < steps.length
      ? visual.highlight_row
      : explicitActiveIndex >= 0
        ? explicitActiveIndex
        : -1;
  const activeIndex =
    focusState?.active_step !== undefined && focusState.active_step >= 0 && focusState.active_step < steps.length
      ? focusState.active_step
      : inferredActiveIndex;

  useEffect(() => {
    const container = scrollRef.current;
    const activeEl = activeCardRefs.current[activeIndex];
    if (!container || !activeEl || activeIndex < 0) return;
    const containerMid = container.offsetWidth / 2;
    const elLeft = activeEl.offsetLeft;
    const elMid = activeEl.offsetWidth / 2;
    container.scrollTo({ left: elLeft - containerMid + elMid, behavior: "smooth" });
  }, [activeIndex]);

  if (steps.length === 0) {
    return <VisualFallbackCard visual={visual} index={index} />;
  }
  const stepLabels = uniqueVisualStepLabels(steps);

  return (
    <div className="rounded-2xl border border-border bg-background p-4 shadow-sm">
      <VisualHeader visual={visual} index={index} />

      <div ref={scrollRef} className="overflow-x-auto pb-2">
        <div className="flex min-w-max items-stretch gap-3 pr-2 md:min-w-0">
          {steps.map((step, stepIndex) => (
            <div
              key={stepIndex}
              ref={(el) => { activeCardRefs.current[stepIndex] = el; }}
              className="flex items-center"
            >
              <StepFlowCard
                step={step}
                stepIndex={stepIndex}
                isActive={stepIndex === activeIndex}
                label={stepLabels[stepIndex]}
              />

              {stepIndex < steps.length - 1 && (
                <div className="mx-1 hidden h-full items-center md:flex">
                  <div className="relative h-1 w-9 rounded-full bg-primary/30">
                    <div className="absolute -right-1 -top-[5px] h-0 w-0 border-y-[7px] border-l-[9px] border-y-transparent border-l-primary/55" />
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function StepFlowCard({
  step,
  stepIndex,
  isActive,
  label,
}: {
  step: VisualStep;
  stepIndex: number;
  isActive: boolean;
  label?: string;
}) {
  const cases = (step.cases ?? [])
    .map((item) => String(item).trim())
    .filter(Boolean)
    .slice(0, 3);
  const displayLabel = label || visualStepLabel(step, stepIndex);

  return (
    <div
      className={[
        "relative flex min-h-[10rem] w-[11.5rem] shrink-0 flex-col rounded-2xl border bg-background p-4 shadow-sm transition md:w-[12.5rem]",
        isActive
          ? "border-primary/70 bg-primary/[0.035] shadow-[0_12px_32px_rgba(124,78,240,0.14)]"
          : "border-border",
      ].join(" ")}
    >
      <div className="flex items-center gap-3">
        <div
          className={[
            "flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-black shadow-sm",
            isActive
              ? "bg-primary text-primary-foreground"
              : "bg-primary/10 text-primary",
          ].join(" ")}
        >
          {stepIndex + 1}
        </div>
        <p
          className={[
            "min-w-0 text-sm font-black leading-5",
            isActive ? "text-primary" : "text-foreground",
          ].join(" ")}
        >
          {displayLabel}
        </p>
      </div>

      <StepFlowMiniVisual step={step} stepIndex={stepIndex} isActive={isActive} />

      {cases.length > 0 && (
        <div className="mt-4 border-t border-dashed border-primary/25 pt-3">
          <p className="text-center text-[0.68rem] font-black uppercase tracking-wide text-primary/75">
            Case split
          </p>
          <div className="mt-2 flex flex-wrap justify-center gap-2">
            {cases.map((item, caseIndex) => (
              <span
                key={`${item}-${caseIndex}`}
                className="rounded-full border border-primary/20 bg-primary/5 px-2.5 py-1 text-[0.7rem] font-bold text-primary"
              >
                {item}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StepFlowMiniVisual({
  step,
  stepIndex,
  isActive,
}: {
  step: VisualStep;
  stepIndex: number;
  isActive: boolean;
}) {
  const accentClass = isActive
    ? "border-primary/35 bg-primary/5"
    : "border-primary/20 bg-muted/20";
  const lineClass = isActive ? "bg-primary/60" : "bg-primary/30";

  if (step.formula) {
    return (
      <div className={`mt-auto rounded-2xl border border-dashed p-4 text-center ${accentClass}`}>
        <div className="font-mono text-sm font-black text-primary">
          <MathText text={step.formula} />
        </div>
      </div>
    );
  }

  if (step.mini_visual) {
    return (
      <div className={`mt-auto rounded-2xl border border-dashed p-4 text-center ${accentClass}`}>
        <p className="text-xs font-bold leading-5 text-primary">
          {step.mini_visual}
        </p>
      </div>
    );
  }

  const variant = stepIndex % 5;

  return (
    <div className={`mt-auto flex h-24 items-center justify-center rounded-2xl border border-dashed ${accentClass}`}>
      {variant === 0 && (
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-md border-2 border-primary/45" />
          <div className="h-8 w-8 rounded-full border-2 border-primary/45" />
        </div>
      )}

      {variant === 1 && (
        <div className="flex h-14 items-end gap-1.5">
          {[0.35, 0.55, 0.75, 1].map((height, barIndex) => (
            <div
              key={barIndex}
              className={`w-3 rounded-t ${lineClass}`}
              style={{ height: `${height * 3.4}rem` }}
            />
          ))}
        </div>
      )}

      {variant === 2 && (
        <div className="relative h-14 w-16">
          <div className={`absolute bottom-2 left-3 h-10 w-0.5 ${lineClass}`} />
          <div className={`absolute bottom-2 left-3 h-0.5 w-12 ${lineClass}`} />
          <div className="absolute bottom-5 left-5 h-8 w-8 rounded-tl-2xl border-l-2 border-t-2 border-primary/60" />
          <div className="absolute right-2 top-1 h-2 w-2 rounded-full bg-primary/60" />
        </div>
      )}

      {variant === 3 && (
        <div className="space-y-2">
          {[0, 1, 2].map((row) => (
            <div key={row} className="flex items-center gap-2">
              <span className="text-xs font-black text-primary">✓</span>
              <div className={`h-1.5 w-12 rounded-full ${lineClass}`} />
            </div>
          ))}
        </div>
      )}

      {variant === 4 && (
        <div className="flex h-12 w-12 items-center justify-center rounded-full border-2 border-primary/40">
          <span className="text-xl text-primary">☆</span>
        </div>
      )}
    </div>
  );
}

function VisualFormulaCard({
  visual,
  index,
}: {
  visual: VisualPlanItem;
  index: number;
}) {
  const formulaTokens = visual.formula ? tokenizeFormula(visual.formula) : [];

  return (
    <div className="rounded-2xl border border-border bg-background p-4 shadow-sm">
      <VisualHeader visual={visual} index={index} />

      {visual.purpose && (
        <p className="text-sm leading-6 text-muted-foreground">
          {visual.purpose}
        </p>
      )}

      {visual.formula && (
        <div className="mt-4 rounded-2xl border border-primary/20 bg-gradient-to-br from-primary/[0.06] to-primary/[0.02] p-5 text-center shadow-sm">
          <div className="inline-flex max-w-full flex-wrap items-center justify-center gap-y-2 break-words font-mono text-lg font-bold leading-10 sm:text-xl">
            {formulaTokens.map((token, tokenIndex) => (
              <span
                key={`${token}-${tokenIndex}`}
                className={formulaTokenClassName(token)}
              >
                {token}
              </span>
            ))}
          </div>
        </div>
      )}

      {visual.symbols && visual.symbols.length > 0 && (
        <div className="mt-4 space-y-1.5">
          <p className="text-xs font-black uppercase tracking-widest text-muted-foreground">Symbols</p>
          {visual.symbols.map((symbol, symbolIndex) => (
            <div
              key={`${symbol.symbol}-${symbolIndex}`}
              className="flex items-baseline gap-3 rounded-xl border border-border bg-muted/20 px-4 py-2.5"
            >
              <span className="shrink-0 font-mono text-base font-black text-primary">
                {symbol.symbol || "?"}
              </span>
              <span className="h-3.5 w-px shrink-0 self-center bg-border" />
              <span className="text-sm leading-5 text-muted-foreground">
                {symbol.meaning || ""}
              </span>
            </div>
          ))}
        </div>
      )}

      {visual.when_to_use && (
        <div className="mt-4 rounded-2xl border border-[#2E9D77]/20 bg-[#2E9D77]/[0.05] p-4">
          <p className="text-xs font-black uppercase tracking-widest text-[#2E9D77]">When to use</p>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            {visual.when_to_use}
          </p>
        </div>
      )}

    </div>
  );
}

function VisualConceptMap({
  visual,
  index,
}: {
  visual: VisualPlanItem;
  index: number;
}) {
  const nodes = visual.nodes ?? [];
  const nodeColors = [
    { bg: "bg-primary/10", border: "border-primary/30", text: "text-primary" },
    { bg: "bg-[#3B7DD8]/10", border: "border-[#3B7DD8]/30", text: "text-[#3B7DD8]" },
    { bg: "bg-[#2E9D77]/10", border: "border-[#2E9D77]/30", text: "text-[#2E9D77]" },
    { bg: "bg-[#C2762A]/10", border: "border-[#C2762A]/30", text: "text-[#C2762A]" },
  ];

  return (
    <div className="rounded-2xl border border-border bg-background p-5 shadow-sm">
      <VisualHeader visual={visual} index={index} />

      <div className="flex flex-col items-center gap-4">
        {visual.center && (
          <div className="rounded-2xl bg-gradient-to-br from-primary to-primary/70 px-8 py-3 text-center shadow-md shadow-primary/20">
            <p className="text-base font-black text-primary-foreground">{visual.center}</p>
          </div>
        )}

        {nodes.length > 0 && (
          <div className="flex flex-wrap justify-center gap-2.5">
            {nodes.map((node, nodeIndex) => {
              const color = nodeColors[nodeIndex % nodeColors.length];
              return (
                <div
                  key={nodeIndex}
                  className={`rounded-xl border px-4 py-2 text-center ${color.bg} ${color.border}`}
                >
                  {node.relation && (
                    <p className={`mb-0.5 text-[0.6rem] font-black uppercase tracking-widest opacity-70 ${color.text}`}>
                      {node.relation}
                    </p>
                  )}
                  <p className={`text-sm font-bold ${color.text}`}>{node.label}</p>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function VisualRelationshipMap({
  visual,
  index,
}: {
  visual: VisualPlanItem;
  index: number;
}) {
  const nodes = visual.nodes ?? [];
  return (
    <div className="rounded-2xl border border-border bg-background p-5 shadow-sm">
      <VisualHeader visual={visual} index={index} />
      <div className="flex flex-col gap-3">
        {visual.center && (
          <div className="self-start rounded-2xl bg-gradient-to-br from-primary to-primary/70 px-6 py-2.5 shadow-md shadow-primary/20">
            <p className="text-sm font-black text-primary-foreground">{visual.center}</p>
          </div>
        )}
        {nodes.length > 0 && (
          <div className="ml-3 flex flex-col gap-2 border-l-2 border-primary/20 pl-4">
            {nodes.map((node, i) => (
              <div key={i} className="flex items-center gap-2">
                {node.relation && (
                  <span className="shrink-0 rounded-full bg-primary/10 px-2 py-0.5 text-[0.6rem] font-black uppercase tracking-widest text-primary">
                    {node.relation}
                  </span>
                )}
                <span className="text-sm font-bold text-foreground">{node.label}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function VisualEdgeCaseSnapshot({
  visual,
  index,
}: {
  visual: VisualPlanItem;
  index: number;
}) {
  const nodes = visual.nodes ?? [];
  return (
    <div className="rounded-2xl border border-border bg-background p-5 shadow-sm">
      <VisualHeader visual={visual} index={index} />
      <div className="flex flex-col items-center gap-4">
        {visual.center && (
          <p className="text-sm font-black text-muted-foreground">{visual.center}</p>
        )}
        {nodes.length === 0 ? (
          <div className="flex h-20 w-32 items-center justify-center rounded-xl border-2 border-dashed border-border">
            <span className="text-xs font-bold text-muted-foreground/60">empty</span>
          </div>
        ) : (
          <div className="flex items-center gap-4">
            {nodes.map((node, i) => (
              <div
                key={i}
                className="flex h-14 w-14 items-center justify-center rounded-full border-2 border-primary/30 bg-primary/[0.06] text-xs font-black text-primary"
              >
                {node.label}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function VisualProgressiveStepFlow({
  visual,
  index,
  focusState,
}: {
  visual: VisualPlanItem;
  index: number;
  focusState?: VisualFocusState | null;
}) {
  const steps = visual.steps ?? [];
  const scrollRef = useRef<HTMLDivElement>(null);
  const activeCardRef = useRef<HTMLDivElement | null>(null);

  const explicitActive = steps.findIndex((s) => s.active);
  const activeIndex =
    focusState?.active_step !== undefined && focusState.active_step >= 0 && focusState.active_step < steps.length
      ? focusState.active_step
      : explicitActive >= 0
        ? explicitActive
        : -1;

  useEffect(() => {
    const container = scrollRef.current;
    const el = activeCardRef.current;
    if (!container || !el || activeIndex < 0) return;
    const containerMid = container.offsetWidth / 2;
    container.scrollTo({ left: el.offsetLeft - containerMid + el.offsetWidth / 2, behavior: "smooth" });
  }, [activeIndex]);

  if (steps.length === 0) return <VisualFallbackCard visual={visual} index={index} />;
  const stepLabels = uniqueVisualStepLabels(steps);

  return (
    <div className="rounded-2xl border border-border bg-background p-4 shadow-sm">
      <VisualHeader visual={visual} index={index} />
      <div ref={scrollRef} className="overflow-x-auto pb-2">
        <div className="flex min-w-max items-center gap-2 pr-2 md:min-w-0">
          {steps.map((step, i) => {
            const isActive = i === activeIndex;
            return (
              <div
                key={i}
                ref={isActive ? (el) => { activeCardRef.current = el; } : undefined}
                className="flex items-center"
              >
                {i > 0 && (
                  <div className={["mr-2 text-lg font-bold", isActive ? "text-primary" : "text-muted-foreground/40"].join(" ")}>
                    →
                  </div>
                )}
                {isActive ? (
                  <div className="flex min-w-[9rem] flex-col gap-2 rounded-2xl border border-primary/70 bg-primary/[0.035] p-3 shadow-[0_8px_24px_rgba(124,78,240,0.12)]">
                    <div className="flex items-center gap-2">
                      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary text-[0.7rem] font-black text-primary-foreground">
                        {i + 1}
                      </div>
                      <p className="min-w-0 text-sm font-black leading-5 text-primary">
                        {stepLabels[i]}
                      </p>
                    </div>
                    {step.mini_visual && (
                      <p className="rounded-lg bg-primary/10 px-2.5 py-1.5 text-center text-[0.7rem] font-bold text-primary">
                        {step.mini_visual}
                      </p>
                    )}
                  </div>
                ) : (
                  <div className="flex items-center gap-1.5 rounded-xl border border-border bg-background px-3 py-2">
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-muted text-[0.6rem] font-black text-muted-foreground">
                      {i + 1}
                    </span>
                    <span className="text-xs font-bold text-muted-foreground">
                      {stepLabels[i]}
                    </span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function VisualGraph({
  visual,
  index,
}: {
  visual: VisualPlanItem;
  index: number;
}) {
  const type = normalizeVisualType(visual.type);
  const rawPoints = visual.data_points ?? [];
  const data = rawPoints
    .map((point) => {
      if (Array.isArray(point)) {
        return { x: Number(point[0]), y: Number(point[1]) };
      }

      const pointRecord = point as unknown as Record<string, unknown>;
      return {
        x: Number(pointRecord.x),
        y: Number(pointRecord.y),
      };
    })
    .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y))
    .sort((a, b) => a.x - b.x);
  const keyPoints = visual.key_points ?? [];

  if (data.length < 2) {
    return <VisualFallbackCard visual={visual} index={index} />;
  }

  return (
    <div className="rounded-2xl border border-border bg-background p-4 shadow-sm">
      <VisualHeader visual={visual} index={index} />

      {visual.purpose && (
        <p className="mb-4 text-sm leading-6 text-muted-foreground">
          {visual.purpose}
        </p>
      )}

      <ResponsiveContainer width="100%" height={260}>
        {type.includes("bar") || type.includes("histogram") ? (
          <BarChart data={data} margin={{ top: 8, right: 20, left: 0, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis
              dataKey="x"
              type="number"
              domain={["auto", "auto"]}
              tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
            />
            <YAxis tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} width={40} />
            <Tooltip
              formatter={(value) => [typeof value === "number" ? value.toFixed(3) : value, visual.y_label ?? "y"]}
              labelFormatter={(label) => `${visual.x_label ?? "x"} = ${label}`}
              contentStyle={{
                fontSize: 12,
                borderRadius: 8,
                border: "1px solid var(--border)",
                background: "var(--background)",
                color: "var(--foreground)",
              }}
            />
            <ReferenceLine y={0} stroke="var(--border)" strokeWidth={1.5} />
            <Bar dataKey="y" fill="var(--primary)" radius={[6, 6, 0, 0]} />
          </BarChart>
        ) : type.includes("scatter") ? (
          <ScatterChart data={data} margin={{ top: 8, right: 20, left: 0, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis
              dataKey="x"
              type="number"
              name={visual.x_label ?? "x"}
              domain={["auto", "auto"]}
              tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
            />
            <YAxis
              dataKey="y"
              type="number"
              name={visual.y_label ?? "y"}
              tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
              width={40}
            />
            <Tooltip
              cursor={{ strokeDasharray: "3 3" }}
              contentStyle={{
                fontSize: 12,
                borderRadius: 8,
                border: "1px solid var(--border)",
                background: "var(--background)",
                color: "var(--foreground)",
              }}
            />
            <ReferenceLine y={0} stroke="var(--border)" strokeWidth={1.5} />
            <ReferenceLine x={0} stroke="var(--border)" strokeWidth={1.5} />
            <Scatter dataKey="y" fill="var(--primary)" />
          </ScatterChart>
        ) : (
          <LineChart data={data} margin={{ top: 8, right: 20, left: 0, bottom: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis
            dataKey="x"
            type="number"
            domain={["auto", "auto"]}
            label={{
              value: visual.x_label ?? "x",
              position: "insideBottom",
              offset: -12,
              style: { fontSize: 12, fill: "var(--muted-foreground)" },
            }}
            tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
          />
          <YAxis
            label={{
              value: visual.y_label ?? "y",
              angle: -90,
              position: "insideLeft",
              offset: 12,
              style: { fontSize: 12, fill: "var(--muted-foreground)" },
            }}
            tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
            width={40}
          />
          <Tooltip
            formatter={(value) => [typeof value === "number" ? value.toFixed(3) : value, visual.y_label ?? "y"]}
            labelFormatter={(label) => `${visual.x_label ?? "x"} = ${label}`}
            contentStyle={{
              fontSize: 12,
              borderRadius: 8,
              border: "1px solid var(--border)",
              background: "var(--background)",
              color: "var(--foreground)",
            }}
          />
          <ReferenceLine y={0} stroke="var(--border)" strokeWidth={1.5} />
          <ReferenceLine x={0} stroke="var(--border)" strokeWidth={1.5} />
          <Line
            type="monotone"
            dataKey="y"
            stroke="var(--primary)"
            strokeWidth={2.5}
            dot={false}
            activeDot={{ r: 4, fill: "var(--primary)" }}
          />
          </LineChart>
        )}
      </ResponsiveContainer>

      {keyPoints.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {keyPoints.map((kp, kpIndex) => (
            <div
              key={kpIndex}
              className="rounded-lg bg-[#E8F7F1] px-3 py-1.5 text-xs"
            >
              <span className="font-bold text-[#2E9D77]">{kp.label}</span>
              {kp.x !== undefined && kp.y !== undefined && (
                <span className="ml-1 text-[#2E9D77]/70">
                  ({kp.x}, {kp.y})
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      {visual.what_to_notice && (
        <div className="mt-3 rounded-xl bg-accent p-3">
          <p className="text-xs font-bold text-primary">What to notice</p>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            {visual.what_to_notice}
          </p>
        </div>
      )}

    </div>
  );
}

function VisualArrayStateDiagram({
  visual,
  index,
}: {
  visual: VisualPlanItem;
  index: number;
}) {
  const arrayRows = normalizeArrayRows(visual);
  const explicitValues = visual.array_values ?? [];
  const fallbackValues =
    arrayRows.length === 1 ? arrayRows[0].values ?? [] : [];
  const values = explicitValues.length > 0 ? explicitValues : fallbackValues;
  const pointers = (visual.array_pointers ?? []).filter(
    (pointer) =>
      typeof pointer.index === "number" &&
      pointer.index >= 0 &&
      pointer.index < values.length,
  );
  const ranges = (visual.array_ranges ?? []).filter(
    (range) =>
      typeof range.start === "number" &&
      typeof range.end === "number" &&
      range.start >= 0 &&
      range.end >= range.start &&
      range.start < values.length,
  );
  const annotations = (visual.array_annotations ?? [])
    .map((item) => String(item).trim())
    .filter(Boolean)
    .slice(0, 6);
  const cellWidthRem = 4.25;

  return (
    <div className="rounded-2xl border border-border bg-background p-4 shadow-sm">
      <VisualHeader visual={visual} index={index} />

      {visual.purpose && (
        <p className="mb-4 text-sm leading-6 text-muted-foreground">
          {visual.purpose}
        </p>
      )}

      {arrayRows.length > 1 ? (
        <MultiArrayStateRows rows={arrayRows} />
      ) : (
      <div className="overflow-x-auto pb-2">
        <div
          className="relative mx-auto min-h-[14rem] py-14"
          style={{ width: `${Math.max(values.length * cellWidthRem, 12)}rem` }}
        >
          {ranges.map((range, rangeIndex) => {
            const start = Math.max(0, range.start ?? 0);
            const end = Math.min(values.length - 1, range.end ?? start);
            const top = rangeIndex % 2 === 0;
            return (
              <div
                key={`${range.label}-${rangeIndex}`}
                className={[
                  "absolute h-9 rounded-t-lg border-2 border-primary/60",
                  top ? "top-6 border-b-0" : "bottom-6 border-t-0",
                ].join(" ")}
                style={{
                  left: `${start * cellWidthRem + 0.4}rem`,
                  width: `${(end - start + 1) * cellWidthRem - 0.8}rem`,
                }}
              />
            );
          })}

          {(() => {
            // Group pointers that share the same cell + side so their labels
            // can stack vertically instead of colliding on the same pixel.
            const groups = new Map<
              string,
              { side: "top" | "bottom"; index: number; labels: string[] }
            >();
            for (const pointer of pointers) {
              const side: "top" | "bottom" =
                (pointer.side || "top") === "bottom" ? "bottom" : "top";
              const idx = pointer.index ?? 0;
              const key = `${side}:${idx}`;
              const entry = groups.get(key);
              if (entry) {
                entry.labels.push(pointer.label || "");
              } else {
                groups.set(key, { side, index: idx, labels: [pointer.label || ""] });
              }
            }
            return Array.from(groups.values()).map((group, groupIndex) => {
              const pointerTop = group.side !== "bottom";
              return (
                <div
                  key={`pointer-group-${groupIndex}`}
                  className={[
                    "absolute z-20 flex -translate-x-1/2 flex-col items-center text-primary",
                    pointerTop ? "top-0" : "bottom-0 flex-col-reverse",
                  ].join(" ")}
                  style={{
                    left: `${group.index * cellWidthRem + cellWidthRem / 2}rem`,
                  }}
                >
                  <div
                    className={[
                      "flex flex-col items-center gap-0.5",
                      pointerTop ? "" : "flex-col-reverse",
                    ].join(" ")}
                  >
                    {group.labels.map((label, labelIdx) => (
                      <span
                        key={`${label}-${labelIdx}`}
                        className="font-mono text-sm font-black leading-tight"
                      >
                        {label}
                      </span>
                    ))}
                  </div>
                  <span className="h-9 w-1 rounded-full bg-primary" />
                  <span
                    className={[
                      "h-0 w-0 border-x-[9px] border-x-transparent",
                      pointerTop
                        ? "border-t-[12px] border-t-primary"
                        : "border-b-[12px] border-b-primary",
                    ].join(" ")}
                  />
                </div>
              );
            });
          })()}

          <div className="relative z-10 flex">
            {values.map((value, valueIndex) => {
              const isPointed = pointers.some((pointer) => pointer.index === valueIndex);
              const inRange = ranges.some(
                (range) =>
                  typeof range.start === "number" &&
                  typeof range.end === "number" &&
                  valueIndex >= range.start &&
                  valueIndex <= range.end,
              );
              const arrayState = arrayCellState({ valueIndex, isPointed, inRange, ranges });
              const arrayStyle = arrayCellStyle(arrayState);
              return (
                <div
                  key={`${value}-${valueIndex}`}
                  className={[
                    "flex h-20 w-17 shrink-0 flex-col items-center justify-center border-y-4 border-r-4 border-[#487A75] text-center first:rounded-l-lg first:border-l-4 last:rounded-r-lg",
                    arrayStyle.className,
                  ].join(" ")}
                  style={{ width: `${cellWidthRem}rem` }}
                >
                  <span className={`text-3xl font-black ${arrayStyle.textClass}`}>
                    {value}
                  </span>
                  <span className="mt-1 font-mono text-xs text-[#2D5B56]">
                    {valueIndex}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
      )}

      {annotations.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {annotations.map((annotation, annotationIndex) => (
            <span
              key={`${annotation}-${annotationIndex}`}
              className="rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-xs font-black text-primary"
            >
              {annotation}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function normalizeArrayRows(visual: VisualPlanItem): ArrayStateRow[] {
  const rawRows = Array.isArray(visual.array_rows) ? visual.array_rows : [];
  const rows = rawRows
    .map((row, rowIndex) => ({
      label: String(row?.label || `Level ${rowIndex + 1}`).trim(),
      values: Array.isArray(row?.values)
        ? row.values.map((value) => String(value).trim()).filter(Boolean).slice(0, 16)
        : [],
      emphasis: Boolean(row?.emphasis),
    }))
    .filter((row) => row.values.length > 0)
    .slice(0, 8);

  // Anti-pattern: the LLM splits a single array into an "INDICES" row and a
  // "VALUES" row. Collapse to a single values row so the single-array renderer
  // (with pointers + indices-inside-cells) is used. Legit multi-array cases
  // like merge sort split/sorted/merged rows are not affected — they don't
  // have an index row.
  if (rows.length === 2) {
    const isSequentialIndexRow = (row: ArrayStateRow) => {
      const lbl = (row.label ?? "").toLowerCase();
      if (/\b(index|indices|idx|position|i)\b/.test(lbl)) return true;
      // Values are 0,1,2,... matching the other row's length
      const vals = row.values ?? [];
      return vals.length > 0 && vals.every((v, i) => v === String(i));
    };
    const idxRowIdx = rows.findIndex(isSequentialIndexRow);
    if (idxRowIdx !== -1) {
      const valuesRow = rows[1 - idxRowIdx];
      const idxRow = rows[idxRowIdx];
      const valVals = valuesRow?.values ?? [];
      const idxVals = idxRow?.values ?? [];
      if (valVals.length > 0 && valVals.length === idxVals.length) {
        return [{ label: valuesRow?.label || "Array", values: valVals, emphasis: true }];
      }
    }
  }

  if (rows.length > 0) {
    return rows;
  }

  const values = (visual.array_values ?? []).map((value) => String(value).trim()).filter(Boolean);
  return values.length ? [{ label: "Array", values, emphasis: true }] : [];
}

function arrayCellState({
  valueIndex,
  isPointed,
  inRange,
  ranges,
}: {
  valueIndex: number;
  isPointed: boolean;
  inRange: boolean;
  ranges: ArrayStateRange[];
}) {
  if (isPointed) return "current";
  if (!inRange) return ranges.length > 0 ? "unvisited" : "neutral";
  const completedRange = ranges.some((range) => {
    const label = String(range.label || "").toLowerCase();
    return /done|sorted|complete|merged|fixed|processed/.test(label) &&
      typeof range.start === "number" &&
      typeof range.end === "number" &&
      valueIndex >= range.start &&
      valueIndex <= range.end;
  });
  if (completedRange) return "completed";
  return "active_range";
}

function arrayCellStyle(state: string) {
  switch (state) {
    case "current":
      return {
        className: "bg-primary ring-4 ring-primary/30 shadow-[0_0_0_6px_rgba(124,78,240,0.10)]",
        textClass: "text-white",
      };
    case "completed":
      return {
        className: "bg-[#EDE9FE] border-primary/50",
        textClass: "text-primary",
      };
    case "active_range":
      return {
        className: "bg-[#F7C63D] border-[#D99F12]",
        textClass: "text-foreground",
      };
    case "unvisited":
      return {
        className: "bg-[#F8FAFC] border-[#CBD5E1]",
        textClass: "text-muted-foreground",
      };
    default:
      return {
        className: "bg-[#8ED8D2]",
        textClass: "text-white",
      };
  }
}

function MultiArrayStateRows({ rows }: { rows: ArrayStateRow[] }) {
  return (
    <div className="flex flex-col items-center overflow-x-auto pb-3 pt-1">
      {rows.map((row, rowIndex) => {
        // Split values on "|" to get side-by-side sub-array groups within a level
        const groups: string[][] = [];
        let cur: string[] = [];
        for (const v of (row.values ?? [])) {
          if (v === "|") {
            if (cur.length) { groups.push(cur); cur = []; }
          } else {
            cur.push(v);
          }
        }
        if (cur.length) groups.push(cur);

        const cellSize = groups.some((g) => g.length > 8) ? "w-8 h-8 text-xs" : "w-10 h-10 text-sm";

        return (
          <div key={`${row.label}-${rowIndex}`} className="flex flex-col items-center">
            {row.label && (
              <p className="mb-1 text-[0.6rem] font-black uppercase tracking-widest text-muted-foreground">
                {row.label}
              </p>
            )}
            <div className="flex flex-wrap items-center justify-center gap-2">
              {groups.map((group, gi) => (
                <div key={gi} className="flex overflow-hidden rounded-xl border border-[#5C4AC8]/30 shadow-sm">
                  {group.map((value, vi) => (
                    <div
                      key={`${gi}-${vi}`}
                      className={[
                        "flex shrink-0 items-center justify-center border-r border-[#5C4AC8]/20 font-black last:border-r-0",
                        cellSize,
                        row.emphasis
                          ? "bg-primary text-primary-foreground"
                          : rowIndex % 2 === 0
                            ? "bg-violet-50 text-foreground"
                            : "bg-emerald-50 text-foreground",
                      ].join(" ")}
                    >
                      {value}
                    </div>
                  ))}
                </div>
              ))}
            </div>
            {rowIndex < rows.length - 1 && (
              <div className="my-1.5 text-base font-bold text-primary/30">↓</div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function VisualCompositeStack({
  visual,
  index,
  focusState,
}: {
  visual: VisualPlanItem;
  index: number;
  focusState?: VisualFocusState | null;
}) {
  const children = (visual.children ?? []).filter(isLessonVisualRenderable);

  return (
    <div className="space-y-3">
      {children.map((child, childIndex) => {
        const childType = normalizeVisualType(child.type);
        if (isCodeTraceVisualType(childType) && child.code) {
          return (
            <div
              key={`composite-code-${childIndex}`}
              className="overflow-hidden rounded-2xl border border-[#E2DDEC] bg-white shadow-sm"
            >
              <div className="flex items-center justify-between border-b border-[#E8E3EF] px-4 py-3">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-black uppercase tracking-widest text-primary">
                    &lt;/&gt;
                  </span>
                  <span className="text-sm font-black text-foreground">
                    {child.language || "Code"}
                  </span>
                </div>
                <span className="rounded-full border border-primary/15 bg-[#F3EEFF] px-3 py-1 text-[11px] font-black text-primary">
                  Active lines
                </span>
              </div>
              <CodeWithHighlight
                code={child.code}
                language={child.language}
                highlightLines={child.highlight_lines}
                maxLine={child.max_line}
                variant="light"
                showHeader={false}
              />
            </div>
          );
        }

        return (
          <VisualRenderer
            key={`composite-visual-${child.type ?? "visual"}-${childIndex}`}
            visual={child}
            index={index + childIndex}
            focusState={focusState}
          />
        );
      })}
    </div>
  );
}

function VisualCodeBlock({
  visual,
  index,
}: {
  visual: VisualPlanItem;
  index: number;
}) {
  return (
    <div className="overflow-hidden rounded-2xl border border-[#343434] bg-[#202020] shadow-sm">
      <div className="border-b border-[#343434] bg-[#252525] p-4">
        <VisualHeader visual={visual} index={index} />

        {visual.purpose && (
          <p className="text-sm leading-6 text-[#b9b9b9]">
            {visual.purpose}
          </p>
        )}
      </div>

      {visual.code && (
        <div className="border-b border-[#343434]">
          <CodeWithHighlight
            code={visual.code}
            language={visual.language}
            highlightLines={visual.highlight_lines}
            maxLine={visual.max_line}
            showHeader={false}
          />
        </div>
      )}
    </div>
  );
}

function VisualMisconception({
  visual,
  index,
}: {
  visual: VisualPlanItem;
  index: number;
}) {
  const comparisonRows = [
    {
      label: visual.wrong_label || "Error",
      value: visual.wrong,
      tone:
        "border-destructive/25 bg-destructive/[0.045] text-destructive",
    },
    {
      label: visual.correct_label || "Correct",
      value: visual.correct,
      tone: "border-[#2E9D77]/25 bg-[#E8F7F1]/70 text-[#2E9D77]",
    },
  ].filter((item) => item.value);

  return (
    <div className="rounded-2xl border border-border bg-background p-4 shadow-sm">
      <VisualHeader visual={visual} index={index} />

      {visual.purpose && (
        <p className="mb-4 text-sm leading-6 text-muted-foreground">
          {visual.purpose}
        </p>
      )}

      <div className="overflow-x-auto pb-1">
        <div className="min-w-[560px] space-y-3">
          <div className="grid grid-cols-2 gap-3 px-1 text-xs font-black uppercase tracking-wide text-muted-foreground">
            <div>Error</div>
            <div>Correct</div>
          </div>

          <div className="grid grid-cols-2 gap-3 rounded-2xl border border-border bg-muted/20 p-3">
            {comparisonRows.map((item) => (
              <div
                key={item.label}
                className={`min-h-28 rounded-xl border p-4 ${item.tone}`}
              >
                <p className="mb-2 text-xs font-black uppercase tracking-wide">
                  {item.label}
                </p>
                <p className="text-sm leading-6 text-foreground">
                  {item.value}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {visual.why && (
        <div className="mt-3 rounded-xl border border-border bg-muted/30 p-3">
          <p className="text-xs font-black uppercase tracking-wide text-primary">
            Why the error feels tempting
          </p>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            {visual.why}
          </p>
        </div>
      )}

      {visual.counterexample && (
        <div className="mt-3 rounded-xl border border-border bg-muted/30 p-3">
          <p className="text-xs font-bold text-foreground">Counterexample</p>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            {visual.counterexample}
          </p>
        </div>
      )}
    </div>
  );
}

function VisualCausalChain({
  visual,
  index,
}: {
  visual: VisualPlanItem;
  index: number;
}) {
  const steps = visual.steps ?? [];

  if (steps.length === 0) {
    return <VisualFallbackCard visual={visual} index={index} />;
  }
  const stepLabels = uniqueVisualStepLabels(steps);

  return (
    <div className="rounded-2xl border border-border bg-background p-4 shadow-sm">
      <VisualHeader visual={visual} index={index} />

      {visual.purpose && (
        <p className="mb-4 text-sm leading-6 text-muted-foreground">
          {visual.purpose}
        </p>
      )}

      <div className="space-y-1">
        {steps.map((step, stepIndex) => {
          const hues = ["bg-primary/10 border-primary/40 text-primary", "bg-[#3B7DD8]/10 border-[#3B7DD8]/40 text-[#3B7DD8]", "bg-[#2E9D77]/10 border-[#2E9D77]/40 text-[#2E9D77]", "bg-[#C2762A]/10 border-[#C2762A]/40 text-[#C2762A]", "bg-primary/10 border-primary/40 text-primary"];
          const dotColors = ["bg-primary", "bg-[#3B7DD8]", "bg-[#2E9D77]", "bg-[#C2762A]", "bg-primary"];
          const colorClass = hues[stepIndex % hues.length];
          const dotClass = dotColors[stepIndex % dotColors.length];
          return (
            <div key={stepIndex}>
              <div className={`flex items-start gap-3 rounded-2xl border p-4 ${colorClass}`}>
                <div className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-black text-white shadow-sm ${dotClass}`}>
                  {stepIndex + 1}
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-bold leading-5">
                    {stepLabels[stepIndex]}
                  </p>
                  {step.description && (
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">
                      {step.description}
                    </p>
                  )}
                  {step.mini_visual && (
                    <p className="mt-2 font-mono text-xs font-bold opacity-70">
                      {step.mini_visual}
                    </p>
                  )}
                </div>
              </div>

              {stepIndex < steps.length - 1 && (
                <div className="flex justify-center py-0.5">
                  <div className="flex flex-col items-center gap-0.5">
                    <div className="h-3 w-0.5 bg-gradient-to-b from-primary/50 to-primary/20 rounded-full" />
                    <div className="h-0 w-0 border-x-[5px] border-t-[7px] border-x-transparent border-t-primary/30" />
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function VisualSpatialDiagram({
  visual,
  index,
}: {
  visual: VisualPlanItem;
  index: number;
}) {
  const nodes = visual.nodes ?? [];
  const keyPoints = visual.key_points ?? [];
  const elements = visual.elements ?? [];

  return (
    <div className="rounded-2xl border border-border bg-background p-4 shadow-sm">
      <VisualHeader visual={visual} index={index} />

      {visual.purpose && (
        <p className="mb-4 text-sm leading-6 text-muted-foreground">
          {visual.purpose}
        </p>
      )}

      <div className="relative min-h-64 overflow-hidden rounded-2xl border border-border bg-muted/30 p-5">
        <div className="absolute inset-0 opacity-45 [background-image:linear-gradient(var(--border)_1px,transparent_1px),linear-gradient(90deg,var(--border)_1px,transparent_1px)] [background-size:32px_32px]" />

        <div className="relative z-10 flex min-h-52 items-center justify-center">
          <div className="rounded-2xl border-2 border-primary bg-background px-6 py-4 text-center shadow-sm">
            <p className="text-sm font-bold text-primary">
              {visual.center || visual.title || "Spatial relationship"}
            </p>
          </div>
        </div>

        {(nodes.length > 0 || elements.length > 0) && (
          <div className="relative z-10 mt-4 grid gap-3 sm:grid-cols-2">
            {nodes.map((node, nodeIndex) => (
              <div
                key={`${node.label}-${nodeIndex}`}
                className="rounded-xl border border-border bg-background/90 p-3"
              >
                <p className="text-sm font-bold text-foreground">
                  {node.label || `Part ${nodeIndex + 1}`}
                </p>
                {(node.relation || node.description) && (
                  <p className="mt-1 text-xs leading-5 text-muted-foreground">
                    {[node.relation, node.description].filter(Boolean).join(": ")}
                  </p>
                )}
              </div>
            ))}

            {elements.map((element, elementIndex) => (
              <div
                key={`${element}-${elementIndex}`}
                className="rounded-xl border border-border bg-background/90 p-3 text-sm font-semibold text-foreground"
              >
                {element}
              </div>
            ))}
          </div>
        )}
      </div>

      {keyPoints.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {keyPoints.map((point, pointIndex) => (
            <span
              key={`${point.label}-${pointIndex}`}
              className="rounded-full bg-accent px-3 py-1 text-xs font-semibold text-primary"
            >
              {point.label || `Point ${pointIndex + 1}`}
              {point.x !== undefined && point.y !== undefined
                ? ` (${point.x}, ${point.y})`
                : ""}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function VisualInteractiveChange({
  visual,
  index,
}: {
  visual: VisualPlanItem;
  index: number;
}) {
  const rows = visual.rows ?? [];
  const columns = visual.columns ?? [];
  const [selectedIndex, setSelectedIndex] = useState(0);
  const selectedRow = rows[Math.min(selectedIndex, Math.max(rows.length - 1, 0))];

  return (
    <div className="rounded-2xl border border-border bg-background p-4 shadow-sm">
      <VisualHeader visual={visual} index={index} />

      {visual.purpose && (
        <p className="mb-4 text-sm leading-6 text-muted-foreground">
          {visual.purpose}
        </p>
      )}

      {rows.length > 0 ? (
        <>
          <div className="flex flex-wrap gap-2">
            {rows.map((row, rowIndex) => (
              <button
                key={`${row[0] ?? "case"}-${rowIndex}`}
                type="button"
                onClick={() => setSelectedIndex(rowIndex)}
                className={`rounded-2xl px-3 py-2 text-xs font-semibold transition ${
                  selectedIndex === rowIndex
                    ? "bg-primary text-primary-foreground"
                    : "border border-border bg-muted/30 text-foreground hover:bg-muted"
                }`}
              >
                {row[0] || `Case ${rowIndex + 1}`}
              </button>
            ))}
          </div>

          {selectedRow && (
            <div className="mt-4 rounded-2xl border border-border bg-muted/30 p-4">
              <p className="text-sm font-bold text-foreground">
                {selectedRow[0] || `Case ${selectedIndex + 1}`}
              </p>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {selectedRow.slice(1).map((cell, cellIndex) => (
                  <div
                    key={`${cell}-${cellIndex}`}
                    className="rounded-xl bg-background px-3 py-2 text-sm"
                  >
                    <p className="text-xs font-bold uppercase tracking-wide text-primary/70">
                      {columns[cellIndex + 1] || `Output ${cellIndex + 1}`}
                    </p>
                    <p className="mt-1 leading-6 text-foreground">{cell}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="space-y-2">
          {(visual.steps ?? []).map((step, stepIndex) => (
            <div
              key={`${step.label}-${stepIndex}`}
              className="rounded-xl border border-border bg-muted/30 p-3"
            >
              <p className="text-sm font-bold text-foreground">
                {visualStepLabel(step, stepIndex)}
              </p>
              {step.description && (
                <p className="mt-1 text-sm leading-6 text-muted-foreground">
                  {step.description}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {visual.what_to_notice && (
        <div className="mt-3 rounded-xl bg-accent p-3">
          <p className="text-xs font-bold text-primary">What changes</p>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            {visual.what_to_notice}
          </p>
        </div>
      )}
    </div>
  );
}

function VisualSourceAnnotation({
  visual,
  index,
}: {
  visual: VisualPlanItem;
  index: number;
}) {
  const labels = visual.labels ?? [];
  const nodes = visual.nodes ?? [];

  return (
    <div className="rounded-2xl border border-border bg-background p-4 shadow-sm">
      <VisualHeader visual={visual} index={index} />

      {visual.purpose && (
        <p className="mb-4 text-sm leading-6 text-muted-foreground">
          {visual.purpose}
        </p>
      )}

      <div className="rounded-2xl border border-border bg-muted/30 p-4">
        <p className="text-xs font-bold uppercase tracking-wide text-primary/70">
          Source excerpt
        </p>
        <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-foreground">
          {visual.code || visual.center || visual.description || visual.title}
        </p>
      </div>

      {(labels.length > 0 || nodes.length > 0) && (
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          {labels.map((label, labelIndex) => (
            <div
              key={`${label.target}-${labelIndex}`}
              className="rounded-xl border border-border bg-accent/50 p-3"
            >
              <p className="text-xs font-bold uppercase tracking-wide text-primary">
                {label.target || `Callout ${labelIndex + 1}`}
              </p>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">
                {label.text}
              </p>
            </div>
          ))}

          {nodes.map((node, nodeIndex) => (
            <div
              key={`${node.label}-${nodeIndex}`}
              className="rounded-xl border border-border bg-background p-3"
            >
              <p className="text-sm font-bold text-foreground">
                {node.label || `Part ${nodeIndex + 1}`}
              </p>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">
                {node.description || node.relation}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function VisualNodeLinkDiagram({
  visual,
  index,
  focusState,
}: {
  visual: VisualPlanItem;
  index: number;
  focusState?: VisualFocusState | null;
}) {
  const rawNodes = visual.nodes ?? [];
  const edges = visual.edges ?? [];
  const useGraphLayout = shouldUseGraphNodeLayout(rawNodes, edges, visual);
  const nodes = layoutNodeLinkNodes(rawNodes, edges, visual);
  const nodeById = buildNodeLinkLookup(nodes);
  const inferredActiveEdge = inferActiveEdge(edges, nodes, visual);
  const inferredActiveNode = inferActiveNode(nodes, visual, inferredActiveEdge, useGraphLayout);
  const inferredActiveNodeId = inferredActiveNode?.id || inferredActiveNode?.label || "";

  // focusState overrides inferred active state when provided
  const focusNodeSet = focusState?.active_nodes?.length
    ? new Set(focusState.active_nodes)
    : null;
  const focusPathEdges = (() => {
    if (!focusState?.highlight_path?.length) return null;
    const set = new Set<string>();
    const path = focusState.highlight_path;
    for (let i = 0; i < path.length - 1; i++) {
      set.add(`${path[i]}||${path[i + 1]}`);
      set.add(`${path[i + 1]}||${path[i]}`);
    }
    return set;
  })();
  const focusPath = focusState?.highlight_path ?? [];

  const activeNodeId = focusNodeSet ? "" : inferredActiveNodeId;
  const activeEdge = focusPathEdges ? null : inferredActiveEdge;

  const viewBox = getNodeLinkViewBox(nodes);
  const hasStatefulTraversal = Boolean(
    focusNodeSet?.size ||
      focusPath.length ||
      nodes.some((node) => node.state) ||
      edges.some((edge) => edge.state),
  );

  return (
    <div className="rounded-2xl border border-border bg-background p-4 shadow-sm">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <VisualHeader visual={visual} index={index} />
        {focusNodeSet && focusNodeSet.size > 0 ? (
          <div className="rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-black text-primary">
            {[...focusNodeSet].map((id) => getNodeLabelForId(nodes, id) || id).join(", ")}
          </div>
        ) : inferredActiveEdge ? (
          <div className="rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-black text-primary">
            Current edge: {getNodeLabelForId(nodes, inferredActiveEdge.from)} - {getNodeLabelForId(nodes, inferredActiveEdge.to)}
          </div>
        ) : inferredActiveNode && (
          <div className="rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-black text-primary">
            Current node: {inferredActiveNode.label || inferredActiveNode.id}
          </div>
        )}
      </div>

      {visual.purpose && (
        <p className="mb-4 text-sm leading-6 text-muted-foreground">
          {visual.purpose}
        </p>
      )}

      <div className="overflow-hidden rounded-2xl border border-border bg-[#FBFBFA] shadow-inner">
        <svg
          viewBox={viewBox}
          role="img"
          aria-label={visual.title || "Node link diagram"}
          className="h-[22rem] w-full md:h-[24rem]"
          preserveAspectRatio="xMidYMid meet"
        >
          <defs>
            <marker
              id={`arrow-${index}`}
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="4.5"
              markerHeight="4.5"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#202124" />
            </marker>
            <filter id={`node-shadow-${index}`} x="-30%" y="-30%" width="160%" height="160%">
              <feDropShadow dx="0" dy="2" stdDeviation="1.8" floodColor="#000000" floodOpacity="0.18" />
            </filter>
            <radialGradient id={`node-fill-${index}`} cx="35%" cy="25%" r="70%">
              <stop offset="0%" stopColor="#FFFFFF" />
              <stop offset="100%" stopColor="#F3F4F6" />
            </radialGradient>
            <radialGradient id={`active-node-fill-${index}`} cx="35%" cy="25%" r="70%">
              <stop offset="0%" stopColor="#EDE9FE" />
              <stop offset="100%" stopColor="#7C4EF0" />
            </radialGradient>
          </defs>


          {edges.map((edge, edgeIndex) => {
            const edgeRecord = edge as VisualEdge & {
              source?: string;
              target?: string;
              start?: string;
              end?: string;
            };
            const fromId = edgeRecord.from || edgeRecord.source || edgeRecord.start;
            const toId = edgeRecord.to || edgeRecord.target || edgeRecord.end;
            const from = fromId ? nodeById.get(fromId) : null;
            const to = toId ? nodeById.get(toId) : null;
            if (!from || !to) return null;

            const edgeState = nodeLinkEdgeState({
              edge,
              fromId,
              toId,
              activeEdge,
              focusPathEdges,
            });
            const edgeStyle = nodeLinkEdgeStyle(edgeState, useGraphLayout);
            const isActiveEdge = edgeState === "active";
            const isPathEdge = focusPathEdges
              ? (focusPathEdges.has(`${fromId}||${toId}`) || focusPathEdges.has(`${toId}||${fromId}`))
              : activeEdge != null &&
                ((activeEdge.from === fromId && activeEdge.to === toId) ||
                  (activeEdge.from === toId && activeEdge.to === fromId));
            const angle = Math.atan2(to.y - from.y, to.x - from.x);
            const nodeRadius = 7.2;
            const fromX = from.x + Math.cos(angle) * nodeRadius;
            const fromY = from.y + Math.sin(angle) * nodeRadius;
            const toX = to.x - Math.cos(angle) * (nodeRadius + 1.8);
            const toY = to.y - Math.sin(angle) * (nodeRadius + 1.8);
            const midX = (from.x + to.x) / 2;
            const midY = (from.y + to.y) / 2;

            // Compute perpendicular offset so the weight label sits NEXT TO
            // the edge instead of overlapping it.
            const edgeLen = Math.hypot(to.x - from.x, to.y - from.y) || 1;
            const perpX = -(to.y - from.y) / edgeLen;
            const perpY = (to.x - from.x) / edgeLen;
            const labelOffset = 2.6;
            const labelX = midX + perpX * labelOffset;
            const labelY = midY + perpY * labelOffset;

            return (
              <g key={`${fromId}-${toId}-${edgeIndex}`}>
                <line
                  x1={fromX}
                  y1={fromY}
                  x2={toX}
                  y2={toY}
                  stroke={edgeStyle.stroke}
                  strokeWidth={edgeStyle.strokeWidth}
                  opacity={edgeStyle.opacity}
                  strokeLinecap="round"
                  strokeDasharray={edgeStyle.dash}
                  markerEnd={useGraphLayout ? undefined : `url(#arrow-${index})`}
                />
                {edge.label && (
                  <text
                    x={labelX}
                    y={labelY + 1.2}
                    textAnchor="middle"
                    fontSize={3.4}
                    fontWeight="700"
                    fill={isActiveEdge || isPathEdge ? "var(--primary)" : "#1a1a2e"}
                    stroke="#FBFBFA"
                    strokeWidth="0.9"
                    paintOrder="stroke"
                    style={{ paintOrder: "stroke" }}
                  >
                    {edge.label}
                  </text>
                )}
              </g>
            );
          })}

          {nodes.map((node, nodeIndex) => {
            const id = node.id || node.label || `node-${nodeIndex + 1}`;
            const positionedNode = nodeById.get(id);
            if (!positionedNode) return null;
            const isActive = focusNodeSet
              ? (focusNodeSet.has(id) || focusNodeSet.has(node.label ?? ""))
              : (id === activeNodeId ||
                node.label === activeNodeId);
            const isRoot = Boolean(node.relation?.toLowerCase().includes("root"));
            const state = nodeLinkNodeState({
              node,
              id,
              active: isActive,
              focusPath,
            });
            const nodeStyle = nodeLinkNodeStyle(state, isRoot);
            const rawLabel = compactNodeDataLabel(node.label || id);
            // Truncate long labels so they never overflow the circle
            const displayLabel = rawLabel.length > 5 ? rawLabel.slice(0, 4) + "…" : rawLabel;
            // Scale font size in SVG user-units so it proportionally matches circle size
            const nodeFontSize = displayLabel.length <= 2 ? 4.5 : displayLabel.length <= 4 ? 3.8 : 3.2;
            const nodeR = state === "current" ? 7.9 : 7;

            return (
              <g key={id}>
                {state === "current" && (
                  <circle
                    cx={positionedNode.x}
                    cy={positionedNode.y}
                    r={nodeR + 3.5}
                    fill="var(--primary)"
                    opacity="0.12"
                  />
                )}
                <circle
                  cx={positionedNode.x}
                  cy={positionedNode.y}
                  r={nodeR}
                  fill={nodeStyle.fill === "active-gradient" ? `url(#active-node-fill-${index})` : nodeStyle.fill}
                  stroke={nodeStyle.stroke}
                  strokeWidth={nodeStyle.strokeWidth}
                  strokeDasharray={nodeStyle.dash}
                  opacity={nodeStyle.opacity}
                  filter={`url(#node-shadow-${index})`}
                />
                <text
                  x={positionedNode.x}
                  y={positionedNode.y + nodeFontSize * 0.38}
                  textAnchor="middle"
                  fontSize={nodeFontSize}
                  fontWeight="800"
                  fill={nodeStyle.text}
                >
                  {displayLabel}
                </text>
                {state === "completed" && (
                  <g>
                    <circle cx={positionedNode.x + nodeR * 0.62} cy={positionedNode.y - nodeR * 0.62} r="2.6" fill="#7C4EF0" />
                    <text x={positionedNode.x + nodeR * 0.62} y={positionedNode.y - nodeR * 0.62 + 1.1} textAnchor="middle" fontSize="3.2" fontWeight="900" fill="#fff">✓</text>
                  </g>
                )}
                {state === "discovered" && (
                  <circle cx={positionedNode.x + nodeR * 0.72} cy={positionedNode.y - nodeR * 0.72} r="1.7" fill="#7C4EF0" />
                )}
              </g>
            );
          })}
        </svg>
      </div>

      {hasStatefulTraversal && <NodeLinkStateLegend />}

      {visual.traversal_path && visual.traversal_path.length > 0 && (
        <div className="mt-3 rounded-xl bg-accent p-3">
          <p className="text-xs font-bold uppercase tracking-wide text-primary">
            Traversal order
          </p>
          <p className="mt-1 text-sm font-semibold text-foreground">
            {visual.traversal_path.join(" -> ")}
          </p>
        </div>
      )}

      {visual.what_to_notice && (
        <p className="mt-3 rounded-xl border border-border bg-background p-3 text-sm leading-6 text-muted-foreground">
          {visual.what_to_notice}
        </p>
      )}
    </div>
  );
}

type NodeLinkNodeState =
  | "unvisited"
  | "discovered"
  | "newly_discovered"
  | "current"
  | "completed"
  | "skipped";

type NodeLinkEdgeState =
  | "unchecked"
  | "active"
  | "traversed"
  | "checked"
  | "skipped"
  | "completed";

function normalizeNodeLinkNodeState(value: unknown): NodeLinkNodeState | "" {
  const normalized = String(value || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
  if (["visited", "seen", "queued", "stacked", "waiting"].includes(normalized)) return "discovered";
  if (["active", "processing", "selected"].includes(normalized)) return "current";
  if (["done", "finished", "processed"].includes(normalized)) return "completed";
  if (["new", "newly_added", "just_discovered"].includes(normalized)) return "newly_discovered";
  return ["unvisited", "discovered", "newly_discovered", "current", "completed", "skipped"].includes(normalized)
    ? (normalized as NodeLinkNodeState)
    : "";
}

function normalizeNodeLinkEdgeState(value: unknown): NodeLinkEdgeState | "" {
  const normalized = String(value || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
  if (["traversal", "current", "selected"].includes(normalized)) return "active";
  if (["used", "tree", "tree_edge"].includes(normalized)) return "traversed";
  if (["ignored", "already_visited"].includes(normalized)) return "skipped";
  if (["done", "finished", "processed"].includes(normalized)) return "completed";
  return ["unchecked", "active", "traversed", "checked", "skipped", "completed"].includes(normalized)
    ? (normalized as NodeLinkEdgeState)
    : "";
}

function nodeLinkNodeState({
  node,
  id,
  active,
  focusPath,
}: {
  node: ConceptMapNode;
  id: string;
  active: boolean;
  focusPath: string[];
}): NodeLinkNodeState {
  const explicit = normalizeNodeLinkNodeState(node.state);
  if (explicit) return explicit;
  const text = `${node.relation || ""} ${node.description || ""}`.toLowerCase();
  if (active || /\b(current|active|processing)\b/.test(text)) return "current";
  if (/\b(newly|new|just discovered)\b/.test(text)) return "newly_discovered";
  if (/\b(completed|complete|done|finished|processed)\b/.test(text)) return "completed";
  if (/\b(visited|discovered|seen|queued|stacked)\b/.test(text)) return "discovered";
  const pathIndex = focusPath.findIndex((item) => item === id || item === node.label);
  if (pathIndex >= 0) {
    return pathIndex === focusPath.length - 1 ? "current" : "completed";
  }
  return "unvisited";
}

function nodeLinkEdgeState({
  edge,
  fromId,
  toId,
  activeEdge,
  focusPathEdges,
}: {
  edge: VisualEdge;
  fromId?: string;
  toId?: string;
  activeEdge: VisualEdge | null;
  focusPathEdges: Set<string> | null;
}): NodeLinkEdgeState {
  const explicit = normalizeNodeLinkEdgeState(edge.state);
  if (explicit) return explicit;
  if (!fromId || !toId) return "unchecked";
  if (
    activeEdge &&
    ((activeEdge.from === fromId && activeEdge.to === toId) ||
      (activeEdge.from === toId && activeEdge.to === fromId))
  ) {
    return "active";
  }
  if (focusPathEdges?.has(`${fromId}||${toId}`) || focusPathEdges?.has(`${toId}||${fromId}`)) {
    return "traversed";
  }
  if (edge.style === "traversal" || edge.style === "active") return "active";
  if (edge.style === "checked" || edge.style === "dashed") return "checked";
  if (edge.style === "completed") return "completed";
  return "unchecked";
}

function nodeLinkNodeStyle(state: NodeLinkNodeState, isRoot: boolean) {
  switch (state) {
    case "current":
      return { fill: "active-gradient", stroke: "var(--primary)", strokeWidth: "1.7", dash: undefined, opacity: 1, text: "#ffffff" };
    case "newly_discovered":
      return { fill: "#F7C63D", stroke: "#D99F12", strokeWidth: "1.4", dash: undefined, opacity: 1, text: "#171717" };
    case "discovered":
      return { fill: "#F1ECFF", stroke: "#A78BFA", strokeWidth: "1.2", dash: undefined, opacity: 1, text: "#231942" };
    case "completed":
      return { fill: "#EDE9FE", stroke: "#7C4EF0", strokeWidth: "1.1", dash: undefined, opacity: 0.9, text: "#231942" };
    case "skipped":
      return { fill: "#F3F4F6", stroke: "#9CA3AF", strokeWidth: "1", dash: "2 1.6", opacity: 0.65, text: "#4B5563" };
    default:
      return { fill: isRoot ? "#FFF7DF" : "#F8FAFC", stroke: isRoot ? "#D99F12" : "#CBD5E1", strokeWidth: "1", dash: undefined, opacity: 1, text: "#1F2937" };
  }
}

function nodeLinkEdgeStyle(state: NodeLinkEdgeState, useGraphLayout: boolean) {
  switch (state) {
    case "active":
      return { stroke: "var(--primary)", strokeWidth: 3.1, opacity: 1, dash: undefined };
    case "traversed":
      return { stroke: "var(--primary)", strokeWidth: 2.2, opacity: 0.78, dash: undefined };
    case "checked":
    case "skipped":
      return { stroke: "#9CA3AF", strokeWidth: 1.7, opacity: 0.72, dash: "4 3" };
    case "completed":
      return { stroke: "#8B7AC8", strokeWidth: 1.8, opacity: 0.58, dash: undefined };
    default:
      return { stroke: "#9CA3AF", strokeWidth: useGraphLayout ? 1.2 : 1.6, opacity: 0.52, dash: undefined };
  }
}

function NodeLinkStateLegend() {
  const items = [
    { label: "Current", className: "bg-primary text-white border-primary" },
    { label: "New", className: "bg-[#F7C63D] text-foreground border-[#D99F12]" },
    { label: "Visited", className: "bg-[#F1ECFF] text-primary border-[#A78BFA]" },
    { label: "Done", className: "bg-[#EDE9FE] text-primary border-primary/70" },
    { label: "Unvisited", className: "bg-[#F8FAFC] text-muted-foreground border-[#CBD5E1]" },
  ];

  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 text-[0.68rem] font-black uppercase tracking-wide text-muted-foreground">
      {items.map((item) => (
        <span key={item.label} className="inline-flex items-center gap-1.5">
          <span className={`h-3 w-3 rounded-full border ${item.className}`} />
          {item.label}
        </span>
      ))}
    </div>
  );
}

function withInferredNodeLinkData(visual: VisualPlanItem): VisualPlanItem {
  if (visual.nodes?.length) {
    return visual;
  }

  const inferred = inferNodeLinkFromDescription(
    [visual.description, visual.what_to_notice, visual.purpose]
      .filter(Boolean)
      .join(" "),
  );

  if (!inferred.nodes.length) {
    return visual;
  }

  return {
    ...visual,
    nodes: inferred.nodes,
    edges: inferred.edges,
  };
}

function withInferredConceptMapData(visual: VisualPlanItem): VisualPlanItem {
  if (visual.center || visual.nodes?.length) {
    return visual;
  }

  const text = getVisualText(visual);
  const center =
    cleanVisualTitle(visual.title) ||
    extractCentralConcept(text) ||
    getVisualTypeLabel(visual.type);
  const concepts = extractConceptLabels(text, center).slice(0, 5);
  const nodes = concepts.length
    ? concepts.map((label, nodeIndex) => ({
        id: nodeLinkId(label),
        label,
        relation: conceptRelationForIndex(nodeIndex),
        description: inferConceptDescription(label, text),
        x: 20 + (60 * (nodeIndex % 3)) / 2,
        y: 28 + Math.floor(nodeIndex / 3) * 28,
      }))
    : [
        {
          id: "concept_main",
          label: center,
          relation: "central idea",
          description: compactVisualDescription(text),
          x: 50,
          y: 50,
        },
      ];

  return {
    ...visual,
    center,
    nodes,
  };
}

function withInferredStepData(
  visual: VisualPlanItem,
  mode: "flow" | "chain" | "path",
): VisualPlanItem {
  if (visual.steps?.length) {
    return visual;
  }

  const text = getVisualText(visual);
  if (mode === "flow" && isDivideAndConquerOverviewVisual(text)) {
    return {
      ...visual,
      steps: [
        {
          label: "Divide",
          description: "Break the original problem into smaller subproblems.",
          mini_visual: "problem -> subproblems",
          formula: "",
          cases: [],
          active: true,
        },
        {
          label: "Conquer",
          description: "Solve each subproblem, usually by applying the same method recursively.",
          mini_visual: "solve each piece",
          formula: "",
          cases: [],
          active: false,
        },
        {
          label: "Combine",
          description: "Merge the subproblem solutions into the final answer.",
          mini_visual: "solutions -> final result",
          formula: "",
          cases: [],
          active: false,
        },
      ],
    };
  }

  const phrases = splitVisualPhrases(text).slice(0, mode === "path" ? 5 : 4);
  const fallbackPhrases =
    phrases.length >= 2
      ? phrases
      : [
          cleanVisualTitle(visual.title) || getVisualTypeLabel(visual.type),
          compactVisualDescription(getVisualText(visual)),
        ].filter(Boolean);

  if (fallbackPhrases.length < 2) {
    return visual;
  }

  return {
    ...visual,
    steps: fallbackPhrases.map((phrase, stepIndex) => ({
      label: inferStepLabel(phrase, stepIndex, mode),
      description: phrase,
      mini_visual: mode === "chain" ? "cause -> effect" : "",
      formula: "",
      cases: [],
      active: stepIndex === 0,
    })),
  };
}

function withInferredTableData(visual: VisualPlanItem, type: string): VisualPlanItem {
  if (visual.columns?.length && visual.rows?.length) {
    return visual;
  }

  const text = getVisualText(visual);
  const phrases = splitVisualPhrases(text).slice(0, 4);

  if (type === "state_change") {
    return {
      ...visual,
      columns: ["Before", "Change", "After"],
      rows: [
        [
          extractAfterLabel(text, "before") || "starting state",
          phrases[0] || "state changes",
          extractAfterLabel(text, "after") || phrases[1] || "updated state",
        ],
      ],
      highlight_row: 0,
    };
  }

  const rows = (phrases.length ? phrases : [compactVisualDescription(text)])
    .filter(Boolean)
    .slice(0, 4)
    .map((phrase, rowIndex) => [
      rowIndex === 0 ? "Main distinction" : `Point ${rowIndex + 1}`,
      phrase,
    ]);

  return {
    ...visual,
    columns: ["Focus", "Comparison"],
    rows,
    highlight_row: visual.highlight_row ?? -1,
  };
}

function withInferredFormulaData(visual: VisualPlanItem): VisualPlanItem {
  if (visual.formula || visual.symbols?.length || visual.when_to_use) {
    return visual;
  }

  const text = getVisualText(visual);
  const formulaMatch = text.match(/[A-Za-z][A-Za-z0-9_]*\s*=\s*[^.;]+/);
  return {
    ...visual,
    formula: formulaMatch?.[0]?.trim() || "",
    when_to_use: visual.when_to_use || compactVisualDescription(text),
  };
}

function withInferredGraphData(visual: VisualPlanItem): VisualPlanItem {
  if (visual.data_points && visual.data_points.length >= 2) {
    return visual;
  }

  const text = getVisualText(visual).toLowerCase();
  const isCdf = /\bcdf\b|cumulative/.test(text);
  const isPdf = /\bpdf\b|density|area under/.test(text);
  const points: [number, number][] = isCdf
    ? [
        [0, 0],
        [1, 0.1],
        [2, 0.5],
        [3, 0.9],
        [4, 1],
      ]
    : isPdf
      ? [
          [-3, 0.02],
          [-2, 0.12],
          [-1, 0.32],
          [0, 0.4],
          [1, 0.32],
          [2, 0.12],
          [3, 0.02],
        ]
      : [
          [0, 0],
          [1, 1],
          [2, 2],
          [3, 3],
        ];

  return {
    ...visual,
    x_label: visual.x_label || "x",
    y_label: visual.y_label || (isCdf ? "cumulative probability" : isPdf ? "density" : "value"),
    data_points: points,
    key_points: visual.key_points?.length
      ? visual.key_points
      : [{ x: points[Math.floor(points.length / 2)][0], y: points[Math.floor(points.length / 2)][1], label: "focus" }],
  };
}

function withInferredMisconceptionData(visual: VisualPlanItem): VisualPlanItem {
  if (visual.wrong || visual.correct) {
    return visual;
  }

  const text = getVisualText(visual);
  const wrong =
    extractLabeledClause(text, ["wrong", "incorrect", "mistake", "error"]) ||
    "The tempting interpretation follows the surface pattern.";
  const correct =
    extractLabeledClause(text, ["correct", "instead", "fix", "repair"]) ||
    compactVisualDescription(text);

  return {
    ...visual,
    wrong,
    correct,
    wrong_label: visual.wrong_label || "Error",
    correct_label: visual.correct_label || "Correct",
    why: visual.why || "It feels plausible because it matches part of the setup but misses the deciding condition.",
  };
}

function withInferredArrayStateData(visual: VisualPlanItem): VisualPlanItem {
  if (visual.array_values?.length || visual.array_rows?.length) {
    return visual;
  }

  const text = getVisualText(visual);

  if (isMergeSortOverviewVisual(text)) {
    return {
      ...visual,
      type: "array_state_diagram",
      purpose:
        visual.purpose ||
        "Merge sort repeatedly splits the array, sorts the smaller pieces, then merges them back together.",
      description:
        visual.description ||
        "Merge sort overview: original array, split groups, sorted halves, and final merged result.",
      array_rows: [
        { label: "Original", values: ["38", "27", "43", "3", "9", "82", "10"], emphasis: true },
        { label: "Split", values: ["38", "27", "43", "3", "|", "9", "82", "10"], emphasis: false },
        { label: "Sorted halves", values: ["3", "27", "38", "43", "|", "9", "10", "82"], emphasis: false },
        { label: "Merged", values: ["3", "9", "10", "27", "38", "43", "82"], emphasis: true },
      ],
      array_annotations: [
        "Split until subarrays are small",
        "Sort each half",
        "Merge in order",
      ],
    };
  }

  const arrayMatch = text.match(/\[([^\]]+)\]/);
  const values = arrayMatch?.[1]
    ?.split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 10);

  if (!values?.length) {
    return visual;
  }

  const pointers: ArrayStatePointer[] = [];
  for (const label of ["left", "right", "mid", "i", "j", "k"]) {
    const match = text.match(new RegExp(`\\b${label}\\s*[=:]\\s*(\\d+)`, "i"));
    if (match) {
      pointers.push({
        label,
        index: Number(match[1]),
        side: pointers.length % 2 === 0 ? "top" : "bottom",
      });
    }
  }

  return {
    ...visual,
    array_values: values,
    array_pointers: pointers,
    array_annotations: visual.array_annotations?.length
      ? visual.array_annotations
      : splitVisualPhrases(text).slice(0, 3),
  };
}

function isMergeSortOverviewVisual(text: string) {
  const normalized = text.toLowerCase();
  return (
    /\bmerge\s+sort\b/.test(normalized) &&
    /\b(split|divide|merge|sort|array|structure|overview|what is)\b/.test(normalized)
  );
}

function isDivideAndConquerOverviewVisual(text: string) {
  const normalized = text.toLowerCase();
  return (
    /\bdivide\s+and\s+conquer\b|\bdivide-and-conquer\b/.test(normalized) ||
    /\bproblem\b/.test(normalized) &&
      /\bsubproblems?\b/.test(normalized) &&
      /\b(combin|final solution|solve|solving)\b/.test(normalized)
  );
}

function withInferredSpatialData(visual: VisualPlanItem): VisualPlanItem {
  if (hasSpatialVisualData(visual)) {
    return visual;
  }

  const text = getVisualText(visual);
  const labels = extractConceptLabels(text, cleanVisualTitle(visual.title) || "").slice(0, 4);
  return {
    ...visual,
    center: cleanVisualTitle(visual.title) || extractCentralConcept(text) || "Spatial relationship",
    nodes: labels.map((label, nodeIndex) => ({
      id: nodeLinkId(label),
      label,
      relation: nodeIndex % 2 === 0 ? "position" : "relationship",
      description: inferConceptDescription(label, text),
      x: 25 + (nodeIndex % 2) * 50,
      y: 30 + Math.floor(nodeIndex / 2) * 35,
    })),
    key_points: visual.key_points ?? [],
  };
}

function getVisualText(visual: VisualPlanItem) {
  return [
    visual.title,
    visual.description,
    visual.purpose,
    visual.what_to_notice,
    visual.highlight,
  ]
    .filter(Boolean)
    .join(" ")
    .trim();
}

function cleanVisualTitle(value: string | undefined) {
  return String(value || "")
    .replace(/\?+$/, "")
    .replace(/\b(card|visual|diagram)$/i, "")
    .trim();
}

function compactVisualDescription(text: string) {
  return String(text || "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 180);
}

function splitVisualPhrases(text: string) {
  return String(text || "")
    .replace(/\s+/g, " ")
    .split(/\s*(?:->|→|;|\.\s+|\n)\s*/)
    .map((part) => part.trim().replace(/[.]+$/, ""))
    .filter((part) => part.length > 0)
    .slice(0, 6);
}

function extractCentralConcept(text: string) {
  const match =
    text.match(/\b(?:what is|introduce|show|visual representation of)\s+([^.;?]+)/i) ||
    text.match(/\b([A-Z][A-Za-z]+(?:\s+[A-Z]?[A-Za-z]+){1,4})\b/);
  return match?.[1]?.trim();
}

function extractConceptLabels(text: string, center: string) {
  const labels = new Set<string>();
  const acronymMatches = text.match(/\b[A-Z]{2,6}\b/g) ?? [];
  acronymMatches.forEach((item) => labels.add(item));

  const nounMatches = text.match(
    /\b(?:area under the curve|continuous interval|probabilities|probability density|cumulative probability|state change|current state|output|input|condition|result)\b/gi,
  ) ?? [];
  nounMatches.forEach((item) => labels.add(toTitleCase(item)));

  splitVisualPhrases(text).forEach((phrase) => {
    const firstChunk = phrase
      .replace(/^(visual representation of|showing|show|introduce|how)\s+/i, "")
      .split(/\b(?:corresponds|shows|changes|under|over|with|from|to)\b/i)[0]
      .trim();
    if (firstChunk.length >= 4 && firstChunk.length <= 42) {
      labels.add(toTitleCase(firstChunk));
    }
  });

  labels.delete(center);
  labels.delete(toTitleCase(center));
  return Array.from(labels).filter((label) => label.length <= 42);
}

function conceptRelationForIndex(index: number) {
  return ["part", "behavior", "interpretation", "condition", "output"][index % 5];
}

function inferConceptDescription(label: string, text: string) {
  const sentence = splitVisualPhrases(text).find((part) =>
    part.toLowerCase().includes(label.toLowerCase()),
  );
  return sentence || "";
}

function inferStepLabel(
  phrase: string,
  index: number,
  mode: "flow" | "chain" | "path",
) {
  const cleaned = phrase
    .replace(/^(then|next|finally|because|so)\s+/i, "")
    .trim();
  const allWords = cleaned.split(/\s+/);
  const fallback =
    mode === "chain"
      ? `Cause ${index + 1}`
      : mode === "path"
        ? `Point ${index + 1}`
        : `Step ${index + 1}`;

  if (allWords.length === 0) return fallback;

  // If the phrase is already short enough, use it verbatim.
  if (allWords.length <= 4) {
    return toTitleCase(allWords.join(" "));
  }

  // Phrase is longer than 4 words — a hard slice would produce mid-phrase
  // garbage like "the edge with the". Only truncate when the first 4 words
  // happen to end at a natural boundary (a content word like a noun/verb,
  // not a closed-class trailer like "the / a / of / with / in").
  const TRAILING_CLOSED_CLASS = new Set([
    "the", "a", "an", "of", "with", "in", "on", "at", "to", "for", "by",
    "and", "or", "but", "from", "into", "onto", "as", "is", "are", "was",
    "were", "be", "been", "being", "this", "that", "these", "those",
  ]);
  const fourth = allWords[3].toLowerCase().replace(/[^a-z]/g, "");
  if (fourth && TRAILING_CLOSED_CLASS.has(fourth)) {
    return fallback;
  }
  return toTitleCase(allWords.slice(0, 4).join(" "));
}

function extractAfterLabel(text: string, label: string) {
  const match = text.match(new RegExp(`\\b${label}\\s*[:=]\\s*([^.;]+)`, "i"));
  return match?.[1]?.trim();
}

function extractLabeledClause(text: string, labels: string[]) {
  for (const label of labels) {
    const match = text.match(new RegExp(`\\b${label}\\b\\s*[:\\-]?\\s*([^.;]+)`, "i"));
    if (match?.[1]) {
      return match[1].trim();
    }
  }
  return "";
}

function toTitleCase(value: string) {
  return String(value || "")
    .trim()
    .replace(/\s+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function layoutNodeLinkNodes(
  rawNodes: ConceptMapNode[],
  edges: VisualEdge[],
  visual?: VisualPlanItem,
): ConceptMapNode[] {
  if (rawNodes.length <= 1 || edges.length === 0) {
    return rawNodes.map((node, nodeIndex) => ({
      ...node,
      x: clampDiagramCoordinate(node.x, 50),
      y: clampDiagramCoordinate(node.y, 28 + nodeIndex * 18),
    }));
  }

  if (shouldUseGraphNodeLayout(rawNodes, edges, visual)) {
    return layoutGraphNodeLinkNodes(rawNodes);
  }

  const nodeIds = rawNodes.map(
    (node, nodeIndex) => node.id || node.label || `node-${nodeIndex + 1}`,
  );

  // Build alias → canonicalId map so edge from/to can reference node.id OR node.label interchangeably
  const aliasToId = new Map<string, string>();
  rawNodes.forEach((node, nodeIndex) => {
    const canonicalId = node.id || node.label || `node-${nodeIndex + 1}`;
    [
      node.id,
      node.label,
      node.label ? nodeLinkId(node.label) : "",
      node.id?.replace(/^node_/, ""),
    ].filter(Boolean).forEach((alias) => {
      if (alias && !aliasToId.has(alias)) aliasToId.set(alias, canonicalId);
    });
  });
  const resolveId = (raw: string | undefined) => (raw ? (aliasToId.get(raw) ?? raw) : undefined);

  const childIds = new Set(
    edges
      .map((edge) => resolveId(edge.to || (edge as VisualEdge & { target?: string }).target))
      .filter(Boolean),
  );
  const explicitRoot = rawNodes.find((node) =>
    node.relation?.toLowerCase().includes("root"),
  );
  const rootId =
    explicitRoot?.id ||
    explicitRoot?.label ||
    nodeIds.find((id) => !childIds.has(id)) ||
    nodeIds[0];

  const childrenByParent = new Map<string, string[]>();
  edges.forEach((edge) => {
    const from = resolveId(edge.from || (edge as VisualEdge & { source?: string }).source);
    const to = resolveId(edge.to || (edge as VisualEdge & { target?: string }).target);
    if (!from || !to) return;
    childrenByParent.set(from, [...(childrenByParent.get(from) ?? []), to]);
  });

  const levels = new Map<string, number>([[rootId, 0]]);
  const queue = [rootId];
  while (queue.length > 0) {
    const parent = queue.shift()!;
    const level = levels.get(parent) ?? 0;
    for (const child of childrenByParent.get(parent) ?? []) {
      if (!levels.has(child)) {
        levels.set(child, level + 1);
        queue.push(child);
      }
    }
  }

  nodeIds.forEach((id) => {
    if (!levels.has(id)) {
      levels.set(id, 1);
    }
  });

  const idsByLevel = new Map<number, string[]>();
  nodeIds.forEach((id) => {
    const level = levels.get(id) ?? 0;
    idsByLevel.set(level, [...(idsByLevel.get(level) ?? []), id]);
  });

  const maxLevel = Math.max(...Array.from(idsByLevel.keys()), 0);
  const positions = new Map<string, { x: number; y: number }>();
  idsByLevel.forEach((ids, level) => {
    const count = ids.length;
    const y = maxLevel === 0 ? 50 : 20 + (58 * level) / Math.max(1, maxLevel);
    ids.forEach((id, idIndex) => {
      const x = count === 1 ? 50 : 14 + (72 * idIndex) / Math.max(1, count - 1);
      positions.set(id, { x, y });
    });
  });

  return rawNodes.map((node, nodeIndex) => {
    const id = node.id || node.label || `node-${nodeIndex + 1}`;
    const position = positions.get(id);
    return {
      ...node,
      id,
      x: position ? position.x : clampDiagramCoordinate(node.x, 50),
      y: position ? position.y : clampDiagramCoordinate(node.y, 28 + nodeIndex * 18),
    };
  });
}

function buildNodeLinkLookup(nodes: ConceptMapNode[]) {
  const lookup = new Map<string, ConceptMapNode & { x: number; y: number }>();
  nodes.forEach((node, nodeIndex) => {
    const positionedNode = {
      ...node,
      x: clampDiagramCoordinate(node.x, 50),
      y: clampDiagramCoordinate(node.y, 20 + nodeIndex * 12),
    };
    const aliases = [
      node.id,
      node.label,
      node.label ? nodeLinkId(node.label) : "",
      node.id?.replace(/^node_/, ""),
    ].filter(Boolean) as string[];
    aliases.forEach((alias) => lookup.set(alias, positionedNode));
  });
  return lookup;
}

function shouldUseGraphNodeLayout(
  nodes: ConceptMapNode[],
  edges: VisualEdge[],
  visual?: VisualPlanItem,
) {
  // Strong override: if any node is explicitly marked as root AND edges form a
  // valid tree (no shared children), always use tree layout — the data clearly
  // describes a rooted tree even if the description text mentions "graph".
  const incoming = new Map<string, number>();
  edges.forEach((edge) => {
    const to = edge.to || (edge as VisualEdge & { target?: string }).target;
    if (to) incoming.set(to, (incoming.get(to) ?? 0) + 1);
  });
  const hasSharedChild = Array.from(incoming.values()).some((count) => count > 1);
  const hasExplicitRoot = nodes.some((node) =>
    node.relation?.toLowerCase().includes("root"),
  );
  if (hasExplicitRoot && !hasSharedChild) {
    return false;
  }

  const visualText = [
    visual?.type,
    visual?.title,
    visual?.description,
    visual?.purpose,
    visual?.what_to_notice,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  if (
    /\b(mst|minimum spanning tree|graph|edge list|edge weight|weighted|shortest path|dijkstra|prim|kruskal|bfs|dfs)\b/.test(
      visualText,
    ) &&
    !/\b(binary tree|bst|rooted tree|subtree|left child|right child)\b/.test(visualText)
  ) {
    return true;
  }

  const xValues = nodes.map((node) => clampDiagramCoordinate(node.x, 50));
  const yValues = nodes.map((node) => clampDiagramCoordinate(node.y, 50));
  const xSpread = Math.max(...xValues) - Math.min(...xValues);
  const ySpread = Math.max(...yValues) - Math.min(...yValues);

  return hasSharedChild || (!hasExplicitRoot && nodes.length >= 4) || xSpread < 18 || ySpread < 18;
}

function layoutGraphNodeLinkNodes(rawNodes: ConceptMapNode[]): ConceptMapNode[] {
  const count = rawNodes.length;
  if (count === 2) {
    return rawNodes.map((node, nodeIndex) => ({
      ...node,
      id: node.id || node.label || `node-${nodeIndex + 1}`,
      x: nodeIndex === 0 ? 32 : 68,
      y: 50,
      relation: node.relation || "node",
    }));
  }

  const centerX = 50;
  const centerY = 50;
  const radiusX = count <= 5 ? 31 : 35;
  const radiusY = count <= 5 ? 24 : 28;
  const startAngle = -Math.PI / 2;

  return rawNodes.map((node, nodeIndex) => {
    const angle = startAngle + (2 * Math.PI * nodeIndex) / Math.max(1, count);
    return {
      ...node,
      id: node.id || node.label || `node-${nodeIndex + 1}`,
      relation: node.relation?.toLowerCase().includes("root") ? "node" : node.relation || "node",
      x: centerX + Math.cos(angle) * radiusX,
      y: centerY + Math.sin(angle) * radiusY,
    };
  });
}

function inferActiveNode(
  nodes: ConceptMapNode[],
  visual: VisualPlanItem,
  activeEdge?: { from: string; to: string } | null,
  suppressFallback = false,
): ConceptMapNode | null {
  const direct = nodes.find((node) => {
    const text = `${node.relation || ""} ${node.description || ""}`.toLowerCase();
    return /\b(current|active|highlight|selected|visit|visited|focus)\b/.test(text);
  });
  if (direct) {
    return direct;
  }

  const visualText = [
    visual.description,
    visual.what_to_notice,
    visual.purpose,
    visual.title,
  ]
    .filter(Boolean)
    .join(" ");
  const currentMatch = visualText.match(
    /\b(?:current|active|highlight(?:ed)?|visit(?:ing)?|push|pushed|pop|popped|select(?:ing|ed)?)\s+(?:node\s*)?\(?([A-Za-z0-9_.-]+)\)?/i,
  );
  const currentLabel = currentMatch?.[1];
  if (currentLabel) {
    const matched = nodes.find(
      (node) => node.label === currentLabel || node.id === currentLabel || node.id === nodeLinkId(currentLabel),
    );
    if (matched) {
      return matched;
    }
  }

  if (activeEdge?.to || activeEdge?.from) {
    const endpoint = activeEdge.to || activeEdge.from;
    const matched = nodes.find(
      (node) =>
        node.id === endpoint ||
        node.label === endpoint ||
        (node.label ? nodeLinkId(node.label) === endpoint : false),
    );
    if (matched) {
      return matched;
    }
  }

  if (suppressFallback) {
    return null;
  }

  return nodes.find((node) => node.relation?.toLowerCase().includes("root")) || nodes[0] || null;
}

function inferActiveEdge(
  edges: VisualEdge[],
  nodes: ConceptMapNode[],
  visual: VisualPlanItem,
): { from: string; to: string } | null {
  const styled = edges.find((edge) => edge.style === "traversal" || edge.style === "active");
  if (styled?.from && styled?.to) {
    return { from: styled.from, to: styled.to };
  }

  const visualText = [
    visual.description,
    visual.what_to_notice,
    visual.purpose,
    visual.title,
  ]
    .filter(Boolean)
    .join(" ");
  const edgeMatch =
    visualText.match(/\(([A-Za-z0-9_.-]+)\s*,\s*([A-Za-z0-9_.-]+)\)/) ||
    visualText.match(/\bedge\s+([A-Za-z0-9_.-]+)\s*(?:-|->|to)\s*([A-Za-z0-9_.-]+)/i);
  const fromLabel = edgeMatch?.[1];
  const toLabel = edgeMatch?.[2];
  if (!fromLabel || !toLabel) {
    return null;
  }

  const fromAliases = nodeAliases(fromLabel);
  const toAliases = nodeAliases(toLabel);
  const matched = edges.find((edge) => {
    const edgeFrom = edge.from || (edge as VisualEdge & { source?: string }).source || "";
    const edgeTo = edge.to || (edge as VisualEdge & { target?: string }).target || "";
    return (
      (fromAliases.has(edgeFrom) && toAliases.has(edgeTo)) ||
      (fromAliases.has(edgeTo) && toAliases.has(edgeFrom))
    );
  });
  if (matched?.from && matched?.to) {
    return { from: matched.from, to: matched.to };
  }

  const nodeIds = new Set(
    nodes.flatMap((node) => [node.id, node.label, node.label ? nodeLinkId(node.label) : ""]).filter(Boolean) as string[],
  );
  const from = Array.from(fromAliases).find((alias) => nodeIds.has(alias));
  const to = Array.from(toAliases).find((alias) => nodeIds.has(alias));
  return from && to ? { from, to } : null;
}

function nodeAliases(label: string) {
  const trimmed = String(label || "").trim();
  return new Set([trimmed, nodeLinkId(trimmed), trimmed.replace(/^node_/, "")].filter(Boolean));
}

function getNodeLabelForId(nodes: ConceptMapNode[], id: string) {
  const matched = nodes.find(
    (node) =>
      node.id === id ||
      node.label === id ||
      (node.label ? nodeLinkId(node.label) === id : false),
  );
  return matched?.label || id.replace(/^node_/, "");
}

function getNodeLinkViewBox(nodes: ConceptMapNode[]) {
  if (nodes.length === 0) {
    return "0 0 100 100";
  }

  const xs = nodes.map((node) => clampDiagramCoordinate(node.x, 50));
  const ys = nodes.map((node) => clampDiagramCoordinate(node.y, 50));
  const minX = Math.max(0, Math.min(...xs) - 18);
  const maxX = Math.min(100, Math.max(...xs) + 18);
  const minY = Math.max(0, Math.min(...ys) - 20);
  const maxY = Math.min(100, Math.max(...ys) + 20);
  const width = Math.max(42, maxX - minX);
  const height = Math.max(36, maxY - minY);
  const centeredMinX = Math.max(0, Math.min(100 - width, minX + (maxX - minX - width) / 2));
  const centeredMinY = Math.max(0, Math.min(100 - height, minY + (maxY - minY - height) / 2));
  return `${centeredMinX} ${centeredMinY} ${width} ${height}`;
}

function inferNodeLinkFromDescription(description: string): {
  nodes: ConceptMapNode[];
  edges: VisualEdge[];
} {
  const text = String(description || "").trim();
  if (!text) {
    return { nodes: [], edges: [] };
  }

  const rootMatch = text.match(/\broot\s*[=:]\s*([A-Za-z0-9_.-]+)/i);
  const rootLabel = rootMatch?.[1] ?? "";
  const relationships: Array<[string, string[]]> = [];

  if (rootLabel) {
    const rootChildrenMatch = text.match(
      new RegExp(
        `\\broot\\s*[=:]\\s*${escapeRegExp(rootLabel)}\\s*\\([^)]*?\\bchildren\\s+([^)]*)\\)`,
        "i",
      ),
    );
    const children = parseNodeChildLabels(rootChildrenMatch?.[1] ?? "");
    if (children.length) {
      relationships.push([rootLabel, children]);
    }
  }

  for (const match of text.matchAll(
    /\b([A-Za-z0-9_.-]+)\s+(?:has\s+)?children\s+([A-Za-z0-9_.\-,\s]+)/gi,
  )) {
    const parent = match[1]?.trim();
    const children = parseNodeChildLabels(match[2] ?? "");
    if (parent && children.length) {
      relationships.push([parent, children]);
    }
  }

  if (!relationships.length && rootLabel) {
    relationships.push([rootLabel, []]);
  }

  if (!relationships.length) {
    return { nodes: [], edges: [] };
  }

  const labels: string[] = [];
  const addLabel = (label: string) => {
    if (label && !labels.includes(label)) {
      labels.push(label);
    }
  };

  const edges: VisualEdge[] = [];
  relationships.forEach(([parent, children]) => {
    addLabel(parent);
    children.forEach((child) => {
      addLabel(child);
      edges.push({
        from: nodeLinkId(parent),
        to: nodeLinkId(child),
        label: "",
        style: "solid",
      });
    });
  });

  const root = rootLabel || relationships[0]?.[0] || labels[0];
  const levels = new Map<string, number>([[root, 0]]);
  let changed = true;
  while (changed) {
    changed = false;
    relationships.forEach(([parent, children]) => {
      const parentLevel = levels.get(parent);
      if (parentLevel == null) return;
      children.forEach((child) => {
        const childLevel = parentLevel + 1;
        if (!levels.has(child) || (levels.get(child) ?? 0) > childLevel) {
          levels.set(child, childLevel);
          changed = true;
        }
      });
    });
  }

  labels.forEach((label) => {
    if (!levels.has(label)) {
      levels.set(label, label === root ? 0 : 1);
    }
  });

  const labelsByLevel = new Map<number, string[]>();
  labels.slice(0, 12).forEach((label) => {
    const level = levels.get(label) ?? 0;
    labelsByLevel.set(level, [...(labelsByLevel.get(level) ?? []), label]);
  });

  const parentIds = new Set(edges.map((edge) => edge.from).filter(Boolean));
  const nodes: ConceptMapNode[] = [];

  labelsByLevel.forEach((levelLabels, level) => {
    const count = levelLabels.length;
    levelLabels.forEach((label, labelIndex) => {
      const id = nodeLinkId(label);
      nodes.push({
        id,
        label,
        relation:
          label === root ? "root" : parentIds.has(id) ? "node" : "leaf",
        description: "",
        x: count === 1 ? 50 : 18 + (64 * labelIndex) / Math.max(1, count - 1),
        y: Math.min(88, 14 + level * 22),
      });
    });
  });

  const validIds = new Set(nodes.map((node) => node.id).filter(Boolean));
  return {
    nodes,
    edges: edges.filter(
      (edge) =>
        edge.from &&
        edge.to &&
        validIds.has(edge.from) &&
        validIds.has(edge.to),
    ),
  };
}

function parseNodeChildLabels(value: string) {
  const firstClause = String(value || "").split(/[.;]/, 1)[0] ?? "";
  return firstClause
    .split(/,|\band\b/i)
    .map((part) =>
      part
        .trim()
        .replace(/^(left|right|child|children)\s*[:=]?\s*/i, "")
        .replace(/\s+.*$/, "")
        .replace(/[()[\]{}]/g, ""),
    )
    .filter(Boolean)
    .slice(0, 4);
}

function nodeLinkId(label: string) {
  const cleaned = String(label || "")
    .trim()
    .replace(/[^A-Za-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return `node_${cleaned || "x"}`;
}

function compactNodeDataLabel(label: string) {
  const cleaned = String(label || "")
    .trim()
    .replace(/[_-]+/g, " ")
    .replace(/^(node|vertex|root|leaf|parent|child|left|right)\s+/i, "")
    .replace(/[()[\]{}:;,]/g, "")
    .trim();
  const token = cleaned.match(/\b[A-Za-z]{1,2}\b|\b\d{1,4}\b/)?.[0];
  if (token) {
    return /^[A-Za-z]+$/.test(token) ? token.toUpperCase() : token;
  }
  const compact = cleaned.replace(/\s+/g, "");
  return compact.length <= 4 ? compact : compact.slice(0, 4);
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function VisualCircuitDiagram({
  visual,
  index,
}: {
  visual: VisualPlanItem;
  index: number;
}) {
  const components = visual.components ?? [];
  const wires = visual.wires ?? [];
  const componentById = new Map(
    components.map((component, componentIndex) => [
      component.id || component.label || `component-${componentIndex + 1}`,
      {
        ...component,
        x: clampDiagramCoordinate(component.x, 20 + componentIndex * 14),
        y: clampDiagramCoordinate(component.y, 50),
      },
    ]),
  );

  return (
    <div className="rounded-2xl border border-border bg-background p-4 shadow-sm">
      <VisualHeader visual={visual} index={index} />

      {visual.purpose && (
        <p className="mb-4 text-sm leading-6 text-muted-foreground">
          {visual.purpose}
        </p>
      )}

      <div className="overflow-hidden rounded-2xl border border-border bg-muted/30">
        <svg
          viewBox="0 0 100 70"
          role="img"
          aria-label={visual.title || "Circuit diagram"}
          className="h-72 w-full"
          preserveAspectRatio="xMidYMid meet"
        >
          {wires.map((wire, wireIndex) => {
            const wireRecord = wire as VisualEdge & {
              source?: string;
              target?: string;
              start?: string;
              end?: string;
            };
            const fromId = wireRecord.from || wireRecord.source || wireRecord.start;
            const toId = wireRecord.to || wireRecord.target || wireRecord.end;
            const from = fromId ? componentById.get(fromId) : null;
            const to = toId ? componentById.get(toId) : null;
            if (!from || !to) return null;

            return (
              <g key={`${fromId}-${toId}-${wireIndex}`}>
                <line
                  x1={from.x}
                  y1={from.y}
                  x2={to.x}
                  y2={to.y}
                  stroke="var(--foreground)"
                  strokeWidth="1.2"
                />
                {wire.label && (
                  <text
                    x={(from.x + to.x) / 2}
                    y={(from.y + to.y) / 2 - 2}
                    textAnchor="middle"
                    className="fill-muted-foreground text-[3px] font-semibold"
                  >
                    {wire.label}
                  </text>
                )}
              </g>
            );
          })}

          {components.map((component, componentIndex) => {
            const id = component.id || component.label || `component-${componentIndex + 1}`;
            const positionedComponent = componentById.get(id);
            if (!positionedComponent) return null;

            return (
              <g key={id}>
                <CircuitSymbol component={positionedComponent} />
                <text
                  x={positionedComponent.x}
                  y={positionedComponent.y + 13}
                  textAnchor="middle"
                  className="fill-foreground text-[3.5px] font-bold"
                >
                  {component.label || component.type || id}
                </text>
                {component.value && (
                  <text
                    x={positionedComponent.x}
                    y={positionedComponent.y + 18}
                    textAnchor="middle"
                    className="fill-muted-foreground text-[3px] font-semibold"
                  >
                    {component.value}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>

      {visual.what_to_notice && (
        <p className="mt-3 rounded-xl border border-border bg-background p-3 text-sm leading-6 text-muted-foreground">
          {visual.what_to_notice}
        </p>
      )}
    </div>
  );
}

function CircuitSymbol({
  component,
}: {
  component: CircuitComponent & { x: number; y: number };
}) {
  const type = normalizeVisualType(component.type);

  if (type.includes("resistor")) {
    return (
      <polyline
        points={`${component.x - 9},${component.y} ${component.x - 6},${component.y - 4} ${component.x - 3},${component.y + 4} ${component.x},${component.y - 4} ${component.x + 3},${component.y + 4} ${component.x + 6},${component.y - 4} ${component.x + 9},${component.y}`}
        fill="none"
        stroke="var(--primary)"
        strokeWidth="1.4"
      />
    );
  }

  if (type.includes("capacitor")) {
    return (
      <g stroke="var(--primary)" strokeWidth="1.4">
        <line x1={component.x - 8} y1={component.y} x2={component.x - 2} y2={component.y} />
        <line x1={component.x - 2} y1={component.y - 6} x2={component.x - 2} y2={component.y + 6} />
        <line x1={component.x + 2} y1={component.y - 6} x2={component.x + 2} y2={component.y + 6} />
        <line x1={component.x + 2} y1={component.y} x2={component.x + 8} y2={component.y} />
      </g>
    );
  }

  if (type.includes("ground")) {
    return (
      <g stroke="var(--primary)" strokeWidth="1.4">
        <line x1={component.x} y1={component.y - 7} x2={component.x} y2={component.y} />
        <line x1={component.x - 7} y1={component.y} x2={component.x + 7} y2={component.y} />
        <line x1={component.x - 5} y1={component.y + 4} x2={component.x + 5} y2={component.y + 4} />
        <line x1={component.x - 3} y1={component.y + 8} x2={component.x + 3} y2={component.y + 8} />
      </g>
    );
  }

  if (type.includes("and") || type.includes("or") || type.includes("gate")) {
    return (
      <path
        d={`M ${component.x - 9} ${component.y - 8} L ${component.x - 2} ${component.y - 8} Q ${component.x + 10} ${component.y} ${component.x - 2} ${component.y + 8} L ${component.x - 9} ${component.y + 8} Z`}
        fill="var(--background)"
        stroke="var(--primary)"
        strokeWidth="1.3"
      />
    );
  }

  return (
    <rect
      x={component.x - 9}
      y={component.y - 7}
      width="18"
      height="14"
      rx="2"
      fill="var(--background)"
      stroke="var(--primary)"
      strokeWidth="1.3"
    />
  );
}

function clampDiagramCoordinate(value: number | undefined, fallback: number) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue)) {
      return fallback;
    }

    return Math.max(5, Math.min(95, numericValue));
  }

  return Math.max(5, Math.min(95, value));
}

function VisualPathProgress({
  visual,
  index,
}: {
  visual: VisualPlanItem;
  index: number;
}) {
  const steps = visual.steps ?? [];

  return (
    <div className="rounded-2xl border border-border bg-background p-5 shadow-sm">
      <VisualHeader visual={visual} index={index} />

      <div className="flex flex-wrap gap-2">
        {steps.map((step, stepIndex) => (
          <div
            key={`${step.label}-${stepIndex}`}
            className="flex items-center gap-2 rounded-xl border border-primary/20 bg-primary/[0.04] px-3.5 py-2"
          >
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary text-[0.6rem] font-black text-primary-foreground">
              {stepIndex + 1}
            </span>
            <p className="text-sm font-bold text-foreground">
              {step.label || `Topic ${stepIndex + 1}`}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function VisualPracticeFeedback({
  visual,
  index,
}: {
  visual: VisualPlanItem;
  index: number;
}) {
  return (
    <div className="rounded-2xl border border-border bg-background p-4 shadow-sm">
      <VisualHeader visual={visual} index={index} />

      {visual.purpose && (
        <p className="mb-4 text-sm leading-6 text-muted-foreground">
          {visual.purpose}
        </p>
      )}

      {(visual.wrong || visual.correct) && (
        <div className="grid gap-3 sm:grid-cols-2">
          {visual.wrong && (
            <div className="rounded-xl border border-destructive/20 bg-destructive/5 p-4">
              <p className="mb-2 text-xs font-bold uppercase tracking-wide text-destructive">
                {visual.wrong_label || "Current reasoning"}
              </p>
              <p className="text-sm leading-6 text-foreground">
                {visual.wrong}
              </p>
            </div>
          )}

          {visual.correct && (
            <div className="rounded-xl border border-[#2E9D77]/20 bg-[#E8F7F1]/60 p-4">
              <p className="mb-2 text-xs font-bold uppercase tracking-wide text-[#2E9D77]">
                {visual.correct_label || "Target reasoning"}
              </p>
              <p className="text-sm leading-6 text-foreground">
                {visual.correct}
              </p>
            </div>
          )}
        </div>
      )}

      {visual.steps && visual.steps.length > 0 && (
        <div className="mt-3 space-y-2">
          {visual.steps.map((step, stepIndex) => (
            <div
              key={`${step.label}-${stepIndex}`}
              className="rounded-xl border border-border bg-muted/30 p-3"
            >
              <p className="text-sm font-bold text-foreground">
                {visualStepLabel(step, stepIndex)}
              </p>
              {step.description && (
                <p className="mt-1 text-sm leading-6 text-muted-foreground">
                  {step.description}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {visual.why && (
        <div className="mt-3 rounded-xl bg-accent p-3">
          <p className="text-xs font-bold text-primary">Where reasoning changed</p>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            {visual.why}
          </p>
        </div>
      )}
    </div>
  );
}

function VisualFallbackCard({
  visual,
  index,
}: {
  visual: VisualPlanItem;
  index: number;
}) {
  return (
    <div className="rounded-2xl border border-border bg-background p-4">
      <VisualHeader visual={visual} index={index} />

      {visual.description && (
        <p className="mb-2 text-sm leading-6 text-muted-foreground">
          {visual.description}
        </p>
      )}
      {visual.purpose && visual.purpose !== visual.description && (
        <p className="text-xs leading-5 text-muted-foreground/70">
          {visual.purpose}
        </p>
      )}
      {!visual.description && !visual.purpose && (
        <p className="text-sm leading-6 text-muted-foreground">
          This visual should reduce confusion in the lesson.
        </p>
      )}
    </div>
  );
}

function SourceGroundingCard({ lesson }: { lesson: Lesson }) {
  const sourceCount = lesson.source_chunk_ids?.length ?? 0;

  if (!lesson.source_summary && sourceCount === 0) {
    return null;
  }

  return (
    <section className="rounded-2xl border border-border bg-muted/30 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-wide text-primary/70">
            Source Grounding
          </p>
          <h3 className="mt-1 font-bold text-foreground">
            Created from uploaded material
          </h3>
        </div>

        {sourceCount > 0 && (
          <span className="rounded-full bg-background px-3 py-1 text-xs font-bold text-primary">
            {sourceCount} source chunk{sourceCount === 1 ? "" : "s"}
          </span>
        )}
      </div>

      {lesson.source_summary && (
        <pre className="mt-4 whitespace-pre-wrap rounded-2xl border border-border bg-background p-4 text-xs leading-6 text-foreground">
          {lesson.source_summary}
        </pre>
      )}
    </section>
  );
}

function TransferChallengeCard({
  challenge,
  answer,
  confidence,
  feedback,
  isSubmitting,
  onAnswerChange,
  onConfidenceChange,
  onSubmit,
}: {
  challenge: TransferChallengeResponse;
  answer: string;
  confidence: number;
  feedback: TransferChallengeSubmitResponse | null;
  isSubmitting: boolean;
  onAnswerChange: (value: string) => void;
  onConfidenceChange: (value: number) => void;
  onSubmit: () => void;
}) {
  return (
    <div className="mx-auto w-full max-w-3xl rounded-3xl border border-primary/20 bg-background p-6 text-left shadow-sm">
      <p className="text-xs font-bold uppercase tracking-wide text-primary">
        Transfer challenge
      </p>

      <h2 className="mt-2 text-2xl font-bold text-foreground">
        {challenge.target_concept}
      </h2>

      <p className="mt-2 text-sm leading-6 text-muted-foreground">
        {challenge.reason}
      </p>

      <div className="mt-5 rounded-2xl border border-border bg-muted/30 p-5">
        <p className="text-base leading-7 text-foreground">
          {challenge.challenge}
        </p>
      </div>

      {challenge.expected_focus && (
        <p className="mt-4 text-xs leading-5 text-muted-foreground">
          Focus: {challenge.expected_focus}
        </p>
      )}

      <textarea
        value={answer}
        onChange={(event) => onAnswerChange(event.target.value)}
        disabled={Boolean(feedback)}
        className="mt-5 min-h-32 w-full rounded-2xl border border-border bg-background px-4 py-3 text-sm text-foreground outline-none placeholder:text-muted-foreground focus:border-primary disabled:opacity-70"
        placeholder="Apply the concept in this new situation..."
      />

      <div className="mt-5 rounded-2xl border border-border bg-muted/30 p-4">
        <p className="text-sm font-semibold text-foreground">
          How confident are you?
        </p>

        <div className="mt-3 flex flex-wrap gap-2">
          {[1, 2, 3, 4, 5].map((value) => {
            const selected = confidence === value;

            return (
              <button
                key={value}
                type="button"
                disabled={Boolean(feedback)}
                onClick={() => onConfidenceChange(value)}
                className={`rounded-2xl px-3 py-2 text-sm font-semibold transition ${
                  selected
                    ? "bg-primary text-primary-foreground"
                    : "border border-border bg-background text-foreground hover:bg-muted"
                } disabled:cursor-not-allowed disabled:opacity-60`}
              >
                {value}
              </button>
            );
          })}
        </div>
      </div>

      {!feedback && (
        <button
          type="button"
          onClick={onSubmit}
          disabled={isSubmitting}
          className="mt-5 rounded-2xl bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground transition hover:bg-foreground disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isSubmitting ? "Checking..." : "Submit transfer challenge"}
        </button>
      )}

      {feedback && (
        <div className="mt-5 rounded-2xl border border-border bg-muted/30 p-5">
          <p className="text-sm font-bold text-foreground">Feedback</p>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            {feedback.feedback}
          </p>
          <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-primary">
            Next: {feedback.next_action.replace(/_/g, " ")}
          </p>
        </div>
      )}
    </div>
  );
}

function ReviewQuestionCard({
  reviewQuestion,
  answer,
  confidence,
  feedback,
  isSubmitting,
  onAnswerChange,
  onConfidenceChange,
  onSubmit,
}: {
  reviewQuestion: ReviewQuestionResponse;
  answer: string;
  confidence: number;
  feedback: ReviewAnswerSubmitResponse | null;
  isSubmitting: boolean;
  onAnswerChange: (value: string) => void;
  onConfidenceChange: (value: number) => void;
  onSubmit: () => void;
}) {
  return (
    <div className="mx-auto w-full max-w-3xl rounded-3xl border border-primary/20 bg-background p-6 text-left shadow-sm">
      <p className="text-xs font-bold uppercase tracking-wide text-primary">
        Review check
      </p>

      <h2 className="mt-2 text-2xl font-bold text-foreground">
        {reviewQuestion.target_concept}
      </h2>

      <p className="mt-2 text-sm leading-6 text-muted-foreground">
        {reviewQuestion.reason}
      </p>

      <AdaptationExplanationBanner
        className="mt-4 bg-accent/60"
        title="Why review this?"
        message="Azalea is resurfacing this concept as a quick delayed check."
        details="Review checks help confirm that the concept still sticks after time has passed. If the answer is strong, Azalea can move this concept toward stability; if it is shaky, Azalea repairs only the missing piece."
      />

      {reviewQuestion.expected_focus && (
        <div className="mt-4 rounded-2xl border border-border bg-muted/30 p-4">
          <p className="text-xs font-bold uppercase tracking-wide text-primary/70">
            What this checks
          </p>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            {reviewQuestion.expected_focus}
          </p>
        </div>
      )}

      <div className="mt-5 rounded-2xl border border-border bg-muted/30 p-5">
        <p className="text-base leading-7 text-foreground">
          {reviewQuestion.question}
        </p>
      </div>

      <textarea
        value={answer}
        onChange={(event) => onAnswerChange(event.target.value)}
        disabled={Boolean(feedback)}
        className="mt-5 min-h-32 w-full rounded-2xl border border-border bg-background px-4 py-3 text-sm text-foreground outline-none placeholder:text-muted-foreground focus:border-primary disabled:opacity-70"
        placeholder="Answer the review check..."
      />

      <div className="mt-5 rounded-2xl border border-border bg-muted/30 p-4">
        <p className="text-sm font-semibold text-foreground">
          How confident are you?
        </p>

        <div className="mt-3 flex flex-wrap gap-2">
          {[1, 2, 3, 4, 5].map((value) => {
            const selected = confidence === value;

            return (
              <button
                key={value}
                type="button"
                disabled={Boolean(feedback)}
                onClick={() => onConfidenceChange(value)}
                className={`rounded-2xl px-3 py-2 text-sm font-semibold transition ${
                  selected
                    ? "bg-primary text-primary-foreground"
                    : "border border-border bg-background text-foreground hover:bg-muted"
                } disabled:cursor-not-allowed disabled:opacity-60`}
              >
                {value}
              </button>
            );
          })}
        </div>
      </div>

      {!feedback && (
        <button
          type="button"
          onClick={onSubmit}
          disabled={isSubmitting}
          className="mt-5 rounded-2xl bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground transition hover:bg-foreground disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isSubmitting ? "Checking..." : "Submit review check"}
        </button>
      )}

      {feedback && (
        <div className="mt-5 rounded-2xl border border-border bg-muted/30 p-5">
          <p className="text-sm font-bold text-foreground">Feedback</p>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            {feedback.feedback}
          </p>
          <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-primary">
            Next: {feedback.next_action.replace(/_/g, " ")}
          </p>
        </div>
      )}
    </div>
  );
}

function TargetedRepairCard({
  repair,
  answer,
  confidence,
  feedback,
  isLoading,
  onAnswerChange,
  onConfidenceChange,
  onSubmit,
}: {
  repair: TargetedRepairResponse;
  answer: string;
  confidence: number;
  feedback?: TargetedRepairFollowUpSubmitResponse;
  isLoading: boolean;
  onAnswerChange: (value: string) => void;
  onConfidenceChange: (value: number) => void;
  onSubmit: () => void;
}) {
  return (
    <div className="mt-4 rounded-3xl border border-purple-100 bg-purple-50/70 p-5 text-left">
      <p className="text-xs font-bold uppercase tracking-wide text-primary">
        Targeted repair
      </p>

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <h4 className="text-lg font-bold text-foreground">
          {repair.target_concept}
        </h4>

        {repair.repair_level && (
          <span className="rounded-full bg-background px-3 py-1 text-xs font-semibold text-primary">
            {repair.repair_level.replace(/_/g, " ")}
          </span>
        )}

        {repair.prior_repair_count > 0 && (
          <span className="rounded-full bg-background px-3 py-1 text-xs font-semibold text-foreground">
            Repair {repair.prior_repair_count + 1}
          </span>
        )}
      </div>

      <AdaptationExplanationBanner
        className="mt-4 bg-background/70"
        title="Why this repair?"
        message="Azalea is focusing only on the missing piece instead of restarting the whole topic."
        details="This keeps the lesson fast: first Azalea repairs the smallest shaky part, then it gives one quick check to confirm whether the repair worked. Repeated misses can trigger a simpler example or a mini-reteach."
      />

      <p className="mt-3 text-sm leading-6 text-foreground">
        {repair.repair_explanation}
      </p>

      <div className="mt-4 rounded-2xl border border-border bg-background/70 p-4">
        <p className="text-sm font-bold text-foreground">Why this matters</p>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          {repair.why_this_matters}
        </p>
      </div>

      <div className="mt-4 rounded-2xl border border-primary/20 bg-background p-4">
        <p className="text-sm font-bold text-foreground">One quick check</p>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          {repair.follow_up_question}
        </p>

        <textarea
          value={answer}
          onChange={(event) => onAnswerChange(event.target.value)}
          disabled={Boolean(feedback)}
          className="mt-4 min-h-24 w-full rounded-2xl border border-border bg-background px-4 py-3 text-sm text-foreground outline-none placeholder:text-muted-foreground focus:border-primary disabled:opacity-70"
          placeholder="Answer the quick check..."
        />

        <div className="mt-4">
          <p className="text-sm font-semibold text-foreground">
            How confident are you?
          </p>

          <div className="mt-2 flex flex-wrap gap-2">
            {[1, 2, 3, 4, 5].map((value) => {
              const selected = confidence === value;

              return (
                <button
                  key={value}
                  type="button"
                  disabled={Boolean(feedback)}
                  onClick={() => onConfidenceChange(value)}
                  className={`rounded-2xl px-3 py-2 text-sm font-semibold transition ${
                    selected
                      ? "bg-primary text-primary-foreground"
                      : "border border-border bg-background text-foreground hover:bg-muted"
                  } disabled:cursor-not-allowed disabled:opacity-60`}
                >
                  {value}
                </button>
              );
            })}
          </div>
        </div>

        {!feedback && (
          <button
            type="button"
            onClick={onSubmit}
            disabled={isLoading}
            className="mt-4 rounded-2xl bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground transition hover:bg-foreground disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isLoading ? "Checking..." : "Submit quick check"}
          </button>
        )}

        {feedback && (
          <div className="mt-4 rounded-2xl border border-border bg-muted/30 p-4">
            <p className="text-sm font-bold text-foreground">Result</p>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              {feedback.feedback}
            </p>
            <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-primary">
              Next: {feedback.next_action.replace(/_/g, " ")}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function PracticeFeedbackCard({
  feedback,
}: {
  feedback: PracticeSubmitResponse;
}) {
  return (
    <div className="mt-4 rounded-2xl border border-primary/30 bg-accent p-4">
      <div className="flex flex-wrap gap-2">
        <span className="rounded-full bg-background px-3 py-1 text-xs font-bold uppercase tracking-wide text-primary">
          {feedback.performance_level.replace(/_/g, " ")}
        </span>

        <span className="rounded-full bg-background px-3 py-1 text-xs font-bold uppercase tracking-wide text-foreground">
          {feedback.next_action.replace(/_/g, " ")}
        </span>

        <span className="rounded-full bg-background px-3 py-1 text-xs font-bold uppercase tracking-wide text-foreground">
          {feedback.is_correct ? "Correct" : "Needs work"}
        </span>
      </div>

      <p className="mt-4 text-sm font-bold text-foreground">Feedback</p>
      <p className="mt-2 text-sm leading-6 text-foreground">
        {feedback.feedback}
      </p>

      {feedback.adaptive_response?.message && (
        <div className="mt-4 rounded-xl border border-primary/20 bg-background p-3">
          <p className="text-sm font-bold text-foreground">Recommended Next Step</p>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            {feedback.adaptive_response.message}
          </p>
          {feedback.adaptive_response.review_scheduled_at && (
            <p className="mt-2 text-xs font-semibold text-primary">
              Review scheduled
            </p>
          )}
        </div>
      )}

      {feedback.mistake_type && (
        <>
          <p className="mt-4 text-sm font-bold text-foreground">Mistake Type</p>
          <p className="mt-2 text-sm leading-6 text-foreground">
            {feedback.mistake_type}
          </p>
        </>
      )}

      {feedback.follow_up_question && (
        <>
          <p className="mt-4 text-sm font-bold text-foreground">
            Follow-up Question
          </p>
          <p className="mt-2 text-sm leading-6 text-foreground">
            {feedback.follow_up_question}
          </p>
        </>
      )}
    </div>
  );
}

function isLessonV2(value: unknown): value is LessonV2 {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<LessonV2>;
  return (
    candidate.lesson_version === 2 &&
    Array.isArray(candidate.render_steps) &&
    Array.isArray(candidate.visual_models) &&
    !Array.isArray((candidate as { lesson_cards?: unknown }).lesson_cards)
  );
}

function HybridV2LegacyShell({
  lesson,
  studyPathId,
  title,
  status,
}: {
  lesson: LessonV2;
  studyPathId: string;
  title: string;
  status: string;
}) {
  const [stepIndex, setStepIndex] = useState(0);
  const [panel, setPanel] = useState<"index" | "regenerate" | null>(null);
  const [selectedContext, setSelectedContext] = useState<{
    element: SelectableElement;
    model: VisualModel;
    frame: VisualFrame;
  } | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatQuestion, setChatQuestion] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [selectedText, setSelectedText] = useState("");
  const [chatThreads, setChatThreads] = useState<
    Record<string, { question: string; answer: string }[]>
  >({});

  const modelsById = useMemo(() => {
    const map = new Map<string, VisualModel>();
    for (const model of lesson.visual_models || []) {
      map.set(model.id, model);
    }
    return map;
  }, [lesson.visual_models]);

  const steps = lesson.render_steps || [];
  const safeStepIndex =
    steps.length > 0 ? Math.min(stepIndex, steps.length - 1) : 0;
  const currentStep = steps[safeStepIndex];
  const progress =
    steps.length > 0 ? Math.round(((safeStepIndex + 1) / steps.length) * 100) : 0;

  const visualSlots = useMemo(() => {
    if (!currentStep) return [];
    const slots: {
      key: string;
      model: VisualModel;
      frameIndex: number | null;
    }[] = [];

    if (currentStep.visual_model_id) {
      const model = modelsById.get(currentStep.visual_model_id);
      if (model) {
        slots.push({
          key: `visual-${model.id}`,
          model,
          frameIndex: currentStep.frame_index,
        });
      }
    }

    if (
      currentStep.code_model_id &&
      currentStep.code_model_id !== currentStep.visual_model_id
    ) {
      const model = modelsById.get(currentStep.code_model_id);
      if (model) {
        slots.push({
          key: `code-${model.id}`,
          model,
          frameIndex: currentStep.code_frame_index,
        });
      }
    }

    return slots;
  }, [currentStep, modelsById]);

  const groupedPoints = useMemo(
    () => groupHybridV2Points(currentStep?.points ?? []),
    [currentStep?.points],
  );

  const activeThreadKey =
    currentStep && selectedContext
      ? `${currentStep.id}::${selectedContext.element.element_id}`
      : "";
  const activeThread = activeThreadKey ? chatThreads[activeThreadKey] || [] : [];
  const latestAnswer =
    activeThread.length > 0 ? activeThread[activeThread.length - 1]?.answer ?? "" : "";

  function getPrimaryVisualContext() {
    const firstSlot = visualSlots[0];
    if (!firstSlot) return null;
    const frame =
      firstSlot.frameIndex != null
        ? firstSlot.model.frames[firstSlot.frameIndex]
        : firstSlot.model.frames[0];
    if (!frame) return null;
    return { model: firstSlot.model, frame };
  }

  function setWholeVisualContext(question = "") {
    const context = getPrimaryVisualContext();
    if (!context) return false;

    const element: SelectableElement = {
      element_id: `__whole_visual__${context.model.id}`,
      element_type: "hotspot",
      semantic_label: `the entire ${context.model.base_type.replace(/_/g, " ")} visual`,
      bounds: { x: 0, y: 0, width: 100, height: 100 },
      aria_label: `Whole visual: ${context.model.base_type}`,
      keyboard_index: 0,
      payload: {
        whole_visual: true,
        base_type: context.model.base_type,
        mode: context.model.mode,
        frame_index: context.frame.index,
      },
    };
    setSelectedContext({ element, model: context.model, frame: context.frame });
    setSelectedText("");
    setChatQuestion(question);
    setChatOpen(true);
    return true;
  }

  function handleHybridTextSelection() {
    const text =
      typeof window !== "undefined"
        ? window.getSelection()?.toString().trim()
        : "";
    if (!text || text.length < 2) return;

    setSelectedText(text);
    const context = getPrimaryVisualContext();
    if (!context) {
      setChatOpen(true);
      return;
    }

    const element: SelectableElement = {
      element_id: `__selected_text__${currentStep?.id ?? "step"}`,
      element_type: "hotspot",
      semantic_label: `highlighted text: ${text.slice(0, 80)}`,
      bounds: { x: 0, y: 0, width: 100, height: 12 },
      aria_label: "Highlighted lesson text",
      keyboard_index: 0,
      payload: {
        highlighted_text: text,
        source: "hybrid_legacy_shell",
      },
    };
    setSelectedContext({ element, model: context.model, frame: context.frame });
    setChatOpen(true);
  }

  function handleVisualClick(
    element: SelectableElement,
    model: VisualModel,
    frame: VisualFrame,
  ) {
    setSelectedContext({ element, model, frame });
    setSelectedText("");
    setChatQuestion("");
    setChatOpen(true);
  }

  function handleExplainWholeVisual() {
    setWholeVisualContext("Explain this whole visual.");
  }

  function handleOpenSharedChat() {
    if (selectedContext) {
      setChatOpen((open) => !open);
      return;
    }
    if (setWholeVisualContext("")) return;
    setChatOpen((open) => !open);
  }

  async function handleAskVisualQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedContext || !currentStep || !chatQuestion.trim()) return;

    const question = chatQuestion.trim();
    const payload: VisualContextPayload = {
      visual_model_id: selectedContext.model.id,
      frame_index: selectedContext.frame.index,
      element: selectedContext.element,
      surrounding_state: selectedContext.frame.state,
      base_type: selectedContext.model.base_type,
      mode: selectedContext.model.mode,
      formatted_context: "",
    };

    setChatQuestion("");
    setChatLoading(true);
    const key = `${currentStep.id}::${selectedContext.element.element_id}`;

    try {
      const result = await askVisualQuestionV2(question, payload);
      setChatThreads((prev) => ({
        ...prev,
        [key]: [...(prev[key] || []), { question, answer: result.answer }],
      }));
    } catch (err) {
      const answer =
        err instanceof Error ? `Failed: ${err.message}` : "Failed to ask question.";
      setChatThreads((prev) => ({
        ...prev,
        [key]: [...(prev[key] || []), { question, answer }],
      }));
    } finally {
      setChatLoading(false);
    }
  }

  function handleBack() {
    setStepIndex((index) => Math.max(index - 1, 0));
    setSelectedContext(null);
    setSelectedText("");
    setChatOpen(false);
  }

  function handleNext() {
    setStepIndex((index) => Math.min(index + 1, Math.max(steps.length - 1, 0)));
    setSelectedContext(null);
    setSelectedText("");
    setChatOpen(false);
  }

  const roleLabel = (currentStep?.role || "lesson").replace(/_/g, " ");

  return (
    <main className="h-screen overflow-hidden bg-[#FAF9FC] text-foreground">
      <header className="relative flex h-24 items-center justify-center border-b border-[#E6E1EE] bg-white/90 px-5 shadow-sm shadow-purple-100/30 backdrop-blur md:px-8">
        <div className="absolute left-5 flex items-center gap-2 md:left-8">
          <button
            type="button"
            onClick={() => setPanel("index")}
            className="inline-flex h-11 items-center gap-2 rounded-2xl border border-[#E1DCEA] bg-white px-4 text-sm font-black shadow-sm shadow-purple-100/30 transition hover:bg-[#F7F4FC]"
          >
            Index
          </button>
          <Link
            href={`/study-paths/${studyPathId}`}
            className="inline-flex h-11 items-center gap-2 rounded-2xl border border-[#E1DCEA] bg-white px-4 text-sm font-black shadow-sm shadow-purple-100/30 transition hover:bg-[#F7F4FC]"
          >
            Exit
          </Link>
        </div>

        <div className="flex min-w-0 max-w-[52rem] flex-col items-center gap-3 text-center">
          <p className="max-w-full truncate text-xl font-black tracking-tight text-foreground">
            {title}
          </p>
          <div className="flex items-center gap-2">
            <div className="h-2 w-72 rounded-full bg-[#E7E4E2]">
              <div
                className="h-2 rounded-full bg-primary shadow-sm shadow-primary/30 transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
            <span className="min-w-10 text-sm font-black text-muted-foreground">
              {progress}%
            </span>
          </div>
        </div>

        <div className="absolute right-5 md:right-8">
          <button
            type="button"
            onClick={() => setPanel("regenerate")}
            className="hidden h-11 items-center gap-2 rounded-2xl border border-primary/20 bg-white px-5 text-sm font-black text-foreground shadow-sm shadow-purple-100/40 transition hover:bg-[#F7F4FC] md:inline-flex"
          >
            Regenerate
          </button>
        </div>
      </header>

      {status && (
        <div className="pointer-events-none fixed left-1/2 top-4 z-50 w-[min(42rem,calc(100vw-2rem))] -translate-x-1/2 rounded-2xl border border-primary/20 bg-[#F1ECFF] px-5 py-3 text-sm font-semibold shadow-lg shadow-purple-100/60">
          {status}
        </div>
      )}

      {panel && (
        <>
          <button
            type="button"
            className="fixed inset-0 z-30 bg-black/10"
            onClick={() => setPanel(null)}
            aria-label="Close panel"
          />
          <aside className="fixed left-0 top-0 z-40 h-screen w-[min(28rem,100vw)] overflow-y-auto border-r border-[#E5DFF0] bg-white p-5 shadow-2xl shadow-purple-100/60">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xl font-black text-foreground">
                  {panel === "index" ? "Study path index" : "Regenerate"}
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  {panel === "index"
                    ? "Jump to any generated step in this topic."
                    : "Hybrid lessons keep v2 visuals inside the legacy shell."}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setPanel(null)}
                className="rounded-2xl border border-[#E1DCEA] bg-white px-4 py-2 text-sm font-black"
              >
                Close
              </button>
            </div>

            {panel === "index" ? (
              <div className="mt-6 space-y-2">
                {steps.map((step, index) => (
                  <button
                    key={step.id}
                    type="button"
                    onClick={() => {
                      setStepIndex(index);
                      setPanel(null);
                      setSelectedContext(null);
                      setChatOpen(false);
                    }}
                    className={`w-full rounded-2xl px-4 py-3 text-left text-sm font-black transition ${
                      index === safeStepIndex
                        ? "bg-[#EEE8FF] text-primary"
                        : "text-muted-foreground hover:bg-[#F7F4FC] hover:text-foreground"
                    }`}
                  >
                    <span className="mr-2 text-xs uppercase tracking-wide">
                      {step.role.replace(/_/g, " ")}
                    </span>
                    {step.title}
                  </button>
                ))}
              </div>
            ) : (
              <div className="mt-6 rounded-2xl border border-[#E5DFF0] bg-[#FCFAFF] p-4">
                <p className="text-sm leading-6 text-muted-foreground">
                  Topic regeneration still lives on the study-path controls. This
                  hybrid page only changes presentation: it renders v2 synced
                  visuals and text inside the legacy learning shell.
                </p>
                <Link
                  href={`/study-paths/${studyPathId}`}
                  className="mt-4 inline-flex rounded-2xl bg-primary px-5 py-3 text-sm font-black text-primary-foreground"
                >
                  Open study path controls
                </Link>
              </div>
            )}
          </aside>
        </>
      )}

      <section className="grid h-[calc(100vh-9.5rem)] grid-cols-[minmax(0,1.9fr)_minmax(24rem,1fr)] gap-5 overflow-hidden p-5">
        <article
          className="flex min-h-0 flex-col overflow-hidden rounded-[1.75rem] border border-[#E5DFF0] bg-white shadow-sm shadow-purple-100/40"
          onMouseUp={handleHybridTextSelection}
        >
          <div className="shrink-0 px-8 pt-8">
            <p className="text-xs font-black uppercase tracking-[0.2em] text-primary">
              {roleLabel}
            </p>
            <h1 className="mt-6 text-4xl font-black tracking-tight text-foreground">
              {currentStep?.title || lesson.title}
            </h1>
            {(currentStep?.notes || lesson.topic_summary) && (
              <p className="mt-5 max-w-4xl text-lg leading-8 text-muted-foreground">
                {currentStep?.notes || lesson.topic_summary}
              </p>
            )}
          </div>

          <div className="azalea-visual-scroll min-h-0 flex-1 overflow-y-auto overscroll-contain px-8 pb-8 pt-6">
            {visualSlots.length > 0 || currentStep?.support_visual ? (
              <div className="space-y-4">
                {visualSlots.map((slot) => {
                  const frameIndex = slot.frameIndex ?? 0;
                  const frame = slot.model.frames[frameIndex] ?? slot.model.frames[0];
                  return (
                    <div
                      key={slot.key}
                      className="azalea-visual-scroll max-h-[min(42vh,28rem)] overflow-auto rounded-2xl border border-[#E5DFF0] bg-white shadow-sm shadow-purple-100/40"
                    >
                      <V2VisualRenderer
                        model={slot.model}
                        frameIndex={frameIndex}
                        onElementClick={(element) =>
                          frame && handleVisualClick(element, slot.model, frame)
                        }
                        selectedElementId={
                          selectedContext?.model.id === slot.model.id
                            ? selectedContext.element.element_id
                            : null
                        }
                      />
                    </div>
                  );
                })}

                {currentStep?.support_visual && (
                    <div className="azalea-visual-scroll max-h-[min(42vh,28rem)] overflow-auto rounded-2xl border border-[#E5DFF0] bg-white shadow-sm shadow-purple-100/40">
                    <V2VisualRenderer
                      supportVisual={currentStep.support_visual}
                      onElementClick={(element) => {
                        const firstSlot = visualSlots[0];
                        const frame = firstSlot?.model.frames[firstSlot.frameIndex ?? 0];
                        if (firstSlot && frame) {
                          handleVisualClick(element, firstSlot.model, frame);
                        }
                      }}
                      selectedElementId={selectedContext?.element.element_id ?? null}
                    />
                  </div>
                )}

                <button
                  type="button"
                  onClick={handleExplainWholeVisual}
                  disabled={visualSlots.length === 0}
                  className="rounded-2xl border border-primary/20 bg-[#F1ECFF] px-4 py-2 text-sm font-black text-primary transition hover:bg-[#E8DFFF] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Explain this visual
                </button>
              </div>
            ) : (
              <div className="flex min-h-[24rem] items-center justify-center rounded-[1.75rem] border border-[#E5DFF0] bg-white p-8 text-center shadow-sm shadow-purple-100/40">
                <div className="max-w-2xl">
                  <p className="text-2xl font-black text-foreground">
                    {currentStep?.title || lesson.title}
                  </p>
                  <p className="mt-4 text-lg leading-8 text-muted-foreground">
                    {currentStep?.notes || lesson.topic_summary}
                  </p>
                </div>
              </div>
            )}

          </div>
        </article>

        <aside
          className="azalea-sidebar-scroll min-h-0 overflow-y-auto overscroll-contain rounded-[1.75rem] border border-[#E5DFF0] bg-white p-7 shadow-sm shadow-purple-100/40"
          onMouseUp={handleHybridTextSelection}
        >
          <div className="mb-7 flex items-center gap-3">
            <h2 className="text-2xl font-black text-primary">
              {chatOpen ? "Chat" : "What&apos;s happening here?"}
            </h2>
            {chatOpen && (
              <button
                type="button"
                onClick={() => setChatOpen(false)}
                className="ml-auto rounded-2xl border border-[#E1DCEA] bg-white px-4 py-2 text-sm font-black"
              >
                Back to steps
              </button>
            )}
          </div>

          {chatOpen ? (
            <div className="flex min-h-[calc(100%-4rem)] flex-col">
              {selectedContext ? (
                <div className="rounded-2xl border border-primary/20 bg-[#FCFAFF] p-4">
                  <p className="text-xs font-black uppercase tracking-[0.16em] text-primary">
                    Asking about
                  </p>
                  <p className="mt-2 text-sm font-semibold leading-6 text-foreground">
                    {selectedContext.element.semantic_label}
                  </p>
                  {selectedText && (
                    <p className="mt-3 rounded-xl bg-white px-3 py-2 text-sm leading-6 text-muted-foreground">
                      {selectedText}
                    </p>
                  )}
                </div>
              ) : (
                <div className="rounded-2xl border border-[#E5DFF0] bg-[#FCFAFF] p-4">
                  <p className="text-sm leading-6 text-muted-foreground">
                    Select part of a visual, highlight text, or use Explain this
                    visual to give the chat specific context.
                  </p>
                </div>
              )}

              <div className="mt-4 flex-1 space-y-3 overflow-y-auto" aria-live="polite">
                {activeThread.map((turn, index) => (
                  <div key={`${turn.question}-${index}`} className="space-y-2">
                    <p className="rounded-2xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground">
                      {turn.question}
                    </p>
                    <p className="rounded-2xl border border-[#E5DFF0] bg-white px-4 py-3 text-sm leading-6 text-muted-foreground">
                      {turn.answer}
                    </p>
                  </div>
                ))}
                {latestAnswer && (
                  <span className="sr-only" aria-live="polite">
                    {latestAnswer}
                  </span>
                )}
              </div>

              <form onSubmit={handleAskVisualQuestion} className="mt-4 flex gap-2">
                <input
                  value={chatQuestion}
                  onChange={(event) => setChatQuestion(event.target.value)}
                  className="min-w-0 flex-1 rounded-2xl border border-[#E1DCEA] bg-white px-4 py-3 text-sm outline-none focus:border-primary"
                  placeholder={
                    selectedContext
                      ? "Ask about this context..."
                      : "Select visual/text context first..."
                  }
                />
                <button
                  type="submit"
                  disabled={chatLoading || !chatQuestion.trim() || !selectedContext}
                  className="rounded-2xl bg-primary px-5 py-3 text-sm font-black text-primary-foreground transition hover:bg-foreground disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {chatLoading ? "Asking..." : "Ask"}
                </button>
              </form>
            </div>
          ) : groupedPoints.length > 0 ? (
            <div className="space-y-4">
              {groupedPoints.map((group, index) => (
                <div
                  key={`${group.title}-${index}`}
                  className="rounded-2xl border border-[#E5DFF0] bg-white p-5 shadow-sm shadow-purple-100/30"
                >
                  <div className="flex gap-4">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary text-lg font-black text-primary-foreground shadow-md shadow-primary/30">
                      {groupedPoints.length > 1 ? (
                        index + 1
                      ) : (
                        <span
                          aria-hidden="true"
                          className="h-3 w-3 rounded-full bg-primary-foreground"
                        />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-lg font-black leading-7 text-foreground">
                        {ensureHybridHeadingPunctuation(group.title)}
                      </p>
                      {group.children.length > 0 && (
                        <ul className="mt-4 space-y-3 text-base leading-7 text-foreground">
                          {group.children.map((child, childIndex) => (
                            <li key={`${child}-${childIndex}`} className="flex gap-3">
                              <span className="mt-3 h-2 w-2 shrink-0 rounded-full bg-primary/40" />
                              <span>{child}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="rounded-2xl border border-[#E5DFF0] bg-white p-5 text-base leading-7 text-muted-foreground">
              {currentStep?.notes || lesson.topic_summary}
            </p>
          )}
        </aside>
      </section>

      <footer className="grid h-20 grid-cols-3 items-center border-t border-[#E6E1EE] bg-white/95 px-6">
        <div>
          <button
            type="button"
            onClick={handleBack}
            disabled={safeStepIndex === 0}
            className="inline-flex h-12 items-center gap-3 rounded-2xl border border-[#E1DCEA] bg-white px-7 text-sm font-black shadow-sm shadow-purple-100/40 transition hover:bg-[#F7F4FC] disabled:cursor-not-allowed disabled:opacity-45"
          >
            Back
          </button>
        </div>
        <div className="flex justify-center">
          <button
            type="button"
            onClick={handleOpenSharedChat}
            className="inline-flex h-12 items-center gap-3 rounded-2xl border border-[#E1DCEA] bg-white px-7 text-sm font-black shadow-sm shadow-purple-100/40 transition hover:bg-[#F7F4FC]"
          >
            Chat
          </button>
        </div>
        <div className="flex justify-end">
          <button
            type="button"
            onClick={handleNext}
            disabled={safeStepIndex >= steps.length - 1}
            className="inline-flex h-12 items-center gap-3 rounded-2xl bg-primary px-8 text-sm font-black text-primary-foreground shadow-lg shadow-primary/25 transition hover:bg-foreground disabled:cursor-not-allowed disabled:opacity-45"
          >
            Next
          </button>
        </div>
      </footer>
    </main>
  );
}

function groupHybridV2Points(points: string[]) {
  const groups: { title: string; children: string[] }[] = [];
  for (const rawPoint of points) {
    const point = rawPoint.trim();
    if (!point) continue;
    const subpoint = point.match(/^[-•]\s+(.+)$/);
    if (subpoint && groups.length > 0) {
      groups[groups.length - 1].children.push(sentenceCaseBulletStart(subpoint[1].trim()));
      continue;
    }
    groups.push({ title: sentenceCaseBulletStart(point.replace(/:$/, "")), children: [] });
  }
  return groups;
}

function ensureHybridHeadingPunctuation(value: string) {
  if (!value) return value;
  if (/[.!?]$/.test(value)) return value;
  return `${value}:`;
}
