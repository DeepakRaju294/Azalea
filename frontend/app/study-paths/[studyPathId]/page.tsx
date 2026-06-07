"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
} from "react";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  FileText,
  LogOut,
  RotateCcw,
  Sparkles,
  Star,
} from "lucide-react";

import {
  generateInitialStudyPath,
  getStudyPath,
  getStudyPathRecommendation,
  getStudyPathSessionSummary,
  getStudyPathSessions,
  getStudyPathTopics,
  regenerateStudyPath,
  type StudyPath,
  type StudyPathRecommendation,
  type StudySession,
  type StudySessionSummary,
  type Topic,
} from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";

import BrandLockup from "@/components/BrandLockup";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  getFlowResume,
  type FlowResumeState,
} from "@/lib/flowResume";

type SessionWithTopic = StudySession & {
  topic_id?: string | null;
};

function formatMinutes(minutes?: number | null) {
  if (minutes === null || minutes === undefined) return "Unknown";
  return `${minutes} min`;
}

function getStatusLabel(status: string) {
  return status.replace(/_/g, " ");
}

function getValidFlowResume(studyPathId: string, topics: Topic[]) {
  const savedResume = getFlowResume(studyPathId);
  const resumeTopicStillExists = savedResume
    ? topics.some((topic) => topic.id === savedResume.topicId)
    : false;

  return resumeTopicStillExists ? savedResume : null;
}

export default function StudyPathLandingPage() {
  const params = useParams<{ studyPathId: string }>();
  const studyPathId = params.studyPathId;
  const router = useRouter();

  const { userEmail, isCheckingAuth, logout: handleLogout } = useRequireAuth();

  const [studyPath, setStudyPath] = useState<StudyPath | null>(null);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [recommendation, setRecommendation] =
    useState<StudyPathRecommendation | null>(null);
  const [sessionSummary, setSessionSummary] =
    useState<StudySessionSummary | null>(null);
  const [recentSessions, setRecentSessions] = useState<StudySession[]>([]);
  const [flowResume, setFlowResume] = useState<FlowResumeState | null>(null);

  const [knowledgeLevel, setKnowledgeLevel] = useState(0);
  const [experienceNotes, setExperienceNotes] = useState("");
  const [pathFeedback, setPathFeedback] = useState("");

  const [status, setStatus] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isLaunching, setIsLaunching] = useState(false);
  const [isGeneratingInitialPath, setIsGeneratingInitialPath] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);

  const topicMinutesById = useMemo(() => {
    const map = new Map<string, number>();

    recentSessions.forEach((session) => {
      const topicId = (session as SessionWithTopic).topic_id;
      if (!topicId) return;

      map.set(topicId, (map.get(topicId) ?? 0) + session.minutes_spent);
    });

    return map;
  }, [recentSessions]);

  const completedTopicCount = useMemo(() => {
    return topics.filter((topic) => topic.status === "completed").length;
  }, [topics]);

  const nextTopic = useMemo(() => {
    if (recommendation?.topic) return recommendation.topic;

    return (
      topics.find((topic) => topic.status === "in_progress") ??
      topics.find((topic) => topic.status !== "completed") ??
      topics[0] ??
      null
    );
  }, [recommendation, topics]);

  const materialReferences = useMemo(() => {
    const refs = new Set<string>();

    topics.forEach((topic) => {
      if (!topic.source_refs) return;

      topic.source_refs
        .split(/[,\n]/)
        .map((item) => item.trim())
        .filter(Boolean)
        .forEach((item) => refs.add(item));
    });

    return Array.from(refs).slice(0, 6);
  }, [topics]);

  const launchLabel = useMemo(() => {
    if (topics.length === 0) return "Generate study path";
    if (!flowResume && completedTopicCount === 0) return "Launch study path";
    if (flowResume) return `Resume ${flowResume.topicTitle}`;
    if ((studyPath?.progress_percent ?? 0) >= 100) return "Review study path";
    if (nextTopic) return `Continue ${nextTopic.title}`;
    return "Start study path";
  }, [
    completedTopicCount,
    flowResume,
    nextTopic,
    studyPath?.progress_percent,
    topics.length,
  ]);

  const refreshData = useCallback(async () => {
    const [
      pathData,
      topicData,
      recommendationData,
      summaryData,
      sessionData,
    ] = await Promise.all([
      getStudyPath(studyPathId),
      getStudyPathTopics(studyPathId),
      getStudyPathRecommendation(studyPathId),
      getStudyPathSessionSummary(studyPathId),
      getStudyPathSessions(studyPathId),
    ]);

    setStudyPath(pathData);
    setTopics(topicData);
    setRecommendation(recommendationData);
    setSessionSummary(summaryData);
    setRecentSessions(sessionData);
    setFlowResume(getValidFlowResume(studyPathId, topicData));
  }, [studyPathId]);

  useEffect(() => {
    if (isCheckingAuth || !studyPathId) return;

    async function fetchData() {
      try {
        setIsLoading(true);
        await refreshData();
      } catch (err) {
        console.error(err);
        setStatus("Failed to load study path.");
      } finally {
        setIsLoading(false);
      }
    }

    fetchData();
  }, [isCheckingAuth, studyPathId, refreshData]);

  useEffect(() => {
    if (
      !status ||
      isLoading ||
      isLaunching ||
      isGeneratingInitialPath ||
      isRegenerating
    ) {
      return;
    }

    const timer = window.setTimeout(() => {
      setStatus("");
    }, 4500);

    return () => window.clearTimeout(timer);
  }, [isGeneratingInitialPath, isLaunching, isLoading, isRegenerating, status]);

  async function handleLaunchStudyPath() {
    try {
      setIsLaunching(true);

      if (topics.length === 0) {
        setStatus("Generate the lesson before launching this path.");
        return;
      }

      if (flowResume) {
        const pureV2Mode =
          typeof window !== "undefined" &&
          new URLSearchParams(window.location.search).get("v") === "2";
        if (pureV2Mode) {
          router.push(
            `/study-paths/${studyPathId}/learn-v2?topic=${flowResume.topicId}`,
          );
          return;
        }
        router.push(
          `/study-paths/${studyPathId}/learn?topicId=${flowResume.topicId}&card=${flowResume.cardIndex}&resume=1`,
        );
        return;
      }

      const topicQuery = nextTopic ? `?topicId=${nextTopic.id}` : "";
      // Hybrid cutover (2026-06-04):
      //   normal launch uses `/learn`, which keeps the preferred legacy shell
      //   and renders v2 VisualModels when the stored lesson is v2.
      //   ?v=2 opens the standalone v2 page for direct inspection.
      const pureV2Mode =
        typeof window !== "undefined" &&
        new URLSearchParams(window.location.search).get("v") === "2";
      const learnRoute = pureV2Mode ? "learn-v2" : "learn";
      const v2TopicQuery = nextTopic ? `?topic=${nextTopic.id}` : "";
      router.push(
        `/study-paths/${studyPathId}/${learnRoute}${
          pureV2Mode ? v2TopicQuery : topicQuery
        }`,
      );
    } catch (err) {
      console.error(err);
      setStatus(
        "Failed to launch study path. Make sure this path has source material or generated topics.",
      );
    } finally {
      setIsLaunching(false);
    }
  }

  async function handleGenerateInitialPath() {
    try {
      setIsGeneratingInitialPath(true);
      setStatus("Generating lesson...");
      // Hybrid visual cutover (default ON, 2026-06-04):
      //   normal launch uses legacy lesson_cards enriched with v2 visuals.
      //   ?v=2 opens the standalone /learn-v2 experiment.
      //   ?regenerate=1 wipes any cached lesson and re-rolls it.
      const params =
        typeof window !== "undefined"
          ? new URLSearchParams(window.location.search)
          : new URLSearchParams();
      const useV2 = params.get("v") === "2";
      const regenerate = params.get("regenerate") === "1";
      const result = await generateInitialStudyPath(studyPathId, {
        useV2,
        regenerate,
      });
      await refreshData();
      setStatus(result.message);
    } catch (err) {
      console.error(err);
      setStatus("Failed to generate lesson.");
    } finally {
      setIsGeneratingInitialPath(false);
    }
  }

  async function handleRegeneratePath(e: FormEvent) {
    e.preventDefault();

    const feedbackParts = [
      knowledgeLevel
        ? `Learner knowledge level is ${knowledgeLevel}/5.`
        : "Learner knowledge level was not provided.",
      experienceNotes.trim()
        ? `Learner experience notes: ${experienceNotes.trim()}`
        : "No learner experience notes provided.",
      pathFeedback.trim()
        ? `Requested path changes: ${pathFeedback.trim()}`
        : "No specific rerender feedback provided.",
    ];

    try {
      setIsRegenerating(true);
      setStatus("Rerendering study path with your preferences...");

      await regenerateStudyPath(studyPathId, feedbackParts.join("\n\n"), true);
      setPathFeedback("");
      await refreshData();
      setStatus("Study path rerendered.");
    } catch (err) {
      console.error(err);
      setStatus("Failed to rerender study path.");
    } finally {
      setIsRegenerating(false);
    }
  }

  if (isCheckingAuth || isLoading) {
    return <StudyPathLandingSkeleton />;
  }

  return (
    <main className="azalea-page-soft min-h-screen text-foreground">
      <div className="mx-auto max-w-7xl px-5 py-6 md:px-8 lg:px-10">
        <nav className="mb-6 flex items-center justify-between gap-4">
          <Button asChild variant="ghost" size="sm">
            <Link href="/">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Home
            </Link>
          </Button>

          <div className="flex items-center gap-3">
            {userEmail && (
              <span className="hidden max-w-[240px] truncate text-sm text-muted-foreground md:inline">
                {userEmail}
              </span>
            )}

            <div className="hidden md:block">
              <BrandLockup size="sm" />
            </div>

            <Button variant="outline" size="sm" onClick={handleLogout}>
              <LogOut className="mr-2 h-4 w-4" />
              Log out
            </Button>
          </div>
        </nav>

        {status && (
          <div className="azalea-surface mb-5 rounded-xl border px-4 py-3 text-sm text-muted-foreground shadow-sm">
            {status}
          </div>
        )}

        <header className="azalea-surface-strong mb-6 rounded-2xl border p-6 shadow-sm">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0">
              <div className="mb-3 flex items-center gap-2 text-sm text-muted-foreground">
                <BookOpen className="h-4 w-4" />
                Study path
              </div>

              <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">
                {studyPath?.title || "Untitled study path"}
              </h1>

              <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">
                {studyPath?.goal ||
                  "This path will guide you through topics, examples, practice, and mastery checks."}
              </p>
            </div>

            <div className="flex flex-wrap gap-2">
              <Badge variant="secondary" className="rounded-full">
                {completedTopicCount}/{topics.length} topics complete
              </Badge>
              <Badge variant="secondary" className="rounded-full">
                {studyPath?.progress_percent ?? 0}% complete
              </Badge>
            </div>
          </div>

          <div className="mt-5">
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Materials used
            </p>

            {materialReferences.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {materialReferences.map((reference) => (
                  <span
                    key={reference}
                    className="inline-flex max-w-xs items-center gap-2 rounded-full border bg-muted/30 px-3 py-1 text-xs text-muted-foreground"
                  >
                    <FileText className="h-3.5 w-3.5 shrink-0" />
                    <span className="truncate">{reference}</span>
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                No source material references have been stored yet. Generate the
                path from uploaded class or study path material to populate
                this.
              </p>
            )}
          </div>
        </header>

        <section className="grid gap-5 lg:grid-cols-[300px_1fr_360px]">
          <aside className="space-y-5">
            <Card>
              <CardHeader>
                <CardDescription>Customize</CardDescription>
                <CardTitle>Knowledge level</CardTitle>
              </CardHeader>

              <CardContent>
                <p className="text-sm leading-6 text-muted-foreground">
                  Rate how familiar you are with this subject so Azalea can tune
                  the explanation depth.
                </p>

                <div className="mt-4 flex gap-1">
                  {[1, 2, 3, 4, 5].map((rating) => (
                    <button
                      key={rating}
                      type="button"
                      onClick={() => setKnowledgeLevel(rating)}
                      className="rounded-lg p-1 transition hover:bg-muted"
                      aria-label={`Set knowledge level to ${rating}`}
                    >
                      <Star
                        className={`h-7 w-7 ${
                          rating <= knowledgeLevel
                            ? "fill-primary text-primary"
                            : "text-muted-foreground"
                        }`}
                      />
                    </button>
                  ))}
                </div>

                <p className="mt-3 text-xs text-muted-foreground">
                  {knowledgeLevel === 0 && "No level selected"}
                  {knowledgeLevel === 1 && "1 = I am new to this"}
                  {knowledgeLevel === 2 && "2 = I recognize the terms"}
                  {knowledgeLevel === 3 && "3 = I understand the basics"}
                  {knowledgeLevel === 4 && "4 = I can solve standard problems"}
                  {knowledgeLevel === 5 && "5 = I need review or edge cases"}
                </p>

                <Textarea
                  value={experienceNotes}
                  onChange={(e) => setExperienceNotes(e.target.value)}
                  className="mt-4 min-h-28"
                  placeholder="Example: I know recursion but struggle with memoization. I need this for an exam next week."
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardDescription>Rerender</CardDescription>
                <CardTitle>Improve this path</CardTitle>
              </CardHeader>

              <CardContent>
                <form onSubmit={handleRegeneratePath} className="space-y-4">
                  <Textarea
                    value={pathFeedback}
                    onChange={(e) => setPathFeedback(e.target.value)}
                    className="min-h-32"
                    placeholder="Example: make topics smaller, add more visuals, focus on exam-style problems."
                  />

                  <Button
                    type="submit"
                    className="w-full"
                    disabled={isRegenerating}
                  >
                    <RotateCcw className="mr-2 h-4 w-4" />
                    {isRegenerating ? "Rerendering..." : "Rerender study path"}
                  </Button>
                </form>
              </CardContent>
            </Card>
          </aside>

          <section className="space-y-5">
            <div className="azalea-surface-strong flex min-h-[420px] items-center justify-center rounded-2xl border p-8 text-center shadow-sm">
              <div className="mx-auto max-w-xl">
                <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-accent text-primary">
                  <Sparkles className="h-8 w-8" />
                </div>

                <p className="text-sm font-medium text-muted-foreground">
                  {topics.length === 0 ? "Ready to build" : "Next step"}
                </p>

                <h2 className="mt-2 text-3xl font-semibold tracking-tight">
                  {topics.length === 0
                    ? "Launch your study path"
                    : nextTopic
                      ? nextTopic.title
                      : "Review your study path"}
                </h2>

                <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-muted-foreground">
                  {topics.length === 0
                    ? "Azalea will generate your lesson when you are ready."
                    : recommendation?.message ||
                      "Continue from your current topic and move through the path one step at a time."}
                </p>

                <Button
                  onClick={
                    topics.length === 0
                      ? handleGenerateInitialPath
                      : handleLaunchStudyPath
                  }
                  disabled={isLaunching || isGeneratingInitialPath}
                  className="mt-7 h-14 rounded-2xl px-8 text-base"
                >
                  {isLaunching
                    ? "Launching..."
                    : isGeneratingInitialPath
                      ? "Generating..."
                      : launchLabel}
                  {!isLaunching && !isGeneratingInitialPath && (
                    <ArrowRight className="ml-2 h-5 w-5" />
                  )}
                </Button>

                {nextTopic && topics.length > 0 && (
                  <div className="azalea-tint mx-auto mt-5 max-w-md rounded-xl border p-4 text-left">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold">Current topic</p>
                      <Badge variant="secondary" className="rounded-full">
                        {getStatusLabel(nextTopic.status)}
                      </Badge>
                    </div>

                    <p className="mt-2 text-sm leading-6 text-muted-foreground">
                      {nextTopic.purpose ||
                        "Open this topic to continue learning, practice, and review."}
                    </p>
                  </div>
                )}
              </div>
            </div>
          </section>

          <aside>
            <PathProgressIndex
              topics={topics}
              topicMinutesById={topicMinutesById}
              totalMinutes={sessionSummary?.total_minutes ?? 0}
              estimatedRemaining={
                studyPath?.estimated_minutes_remaining ?? null
              }
            />
          </aside>
        </section>
      </div>
    </main>
  );
}

function PathProgressIndex({
  topics,
  topicMinutesById,
  totalMinutes,
  estimatedRemaining,
}: {
  topics: Topic[];
  topicMinutesById: Map<string, number>;
  totalMinutes: number;
  estimatedRemaining: number | null;
}) {
  const completedTopics = topics.filter(
    (topic) => topic.status === "completed",
  ).length;

  const progressPercent =
    topics.length > 0 ? Math.round((completedTopics / topics.length) * 100) : 0;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardDescription>Progress</CardDescription>
        <CardTitle>Progress & index</CardTitle>
      </CardHeader>

      <CardContent className="space-y-5">
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-xl border bg-muted/30 p-4">
            <p className="text-xs text-muted-foreground">Time spent</p>
            <p className="mt-1 text-lg font-semibold">
              {formatMinutes(totalMinutes)}
            </p>
          </div>

          <div className="rounded-xl border bg-muted/30 p-4">
            <p className="text-xs text-muted-foreground">Remaining</p>
            <p className="mt-1 text-lg font-semibold">
              {formatMinutes(estimatedRemaining)}
            </p>
          </div>
        </div>

        <div>
          <div className="mb-2 flex items-center justify-between text-xs text-muted-foreground">
            <span>
              {completedTopics}/{topics.length} topics complete
            </span>
            <span>{progressPercent}%</span>
          </div>

          <div className="h-1.5 rounded-full bg-muted">
            <div
              className="h-1.5 rounded-full bg-primary"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>

        <Separator />

        <div>
          <p className="mb-3 text-sm font-medium">Topic index</p>

          {topics.length === 0 ? (
            <div className="rounded-xl border border-dashed bg-muted/30 p-4">
              <p className="text-sm font-medium">No topics yet</p>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">
                Launch this path to generate a topic progression.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {topics.map((topic, index) => {
                const minutesSpent = topicMinutesById.get(topic.id) ?? 0;
                const estimatedMinutes = topic.estimated_minutes ?? 0;
                const remainingMinutes = estimatedMinutes
                  ? Math.max(estimatedMinutes - minutesSpent, 0)
                  : null;
                const topicProgressPercent =
                  topic.status === "completed"
                    ? 100
                    : estimatedMinutes
                      ? Math.min(
                          100,
                          Math.round((minutesSpent / estimatedMinutes) * 100),
                        )
                      : 0;

                return (
                  <div key={topic.id} className="space-y-1.5">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex min-w-0 items-center gap-2">
                          <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-muted text-[11px] font-medium text-muted-foreground">
                            {index + 1}
                          </span>
                          <p className="truncate text-sm font-medium">
                            {topic.title}
                          </p>
                        </div>

                        <p className="mt-0.5 truncate text-xs capitalize text-muted-foreground">
                          {getStatusLabel(topic.status)}
                          {remainingMinutes !== null
                            ? ` · ${remainingMinutes} min left`
                            : topic.estimated_minutes
                              ? ` · ${topic.estimated_minutes} min estimate`
                              : ""}
                        </p>
                      </div>

                      <span className="shrink-0 text-xs text-muted-foreground">
                        {minutesSpent}m
                      </span>
                    </div>

                    <div className="h-1.5 rounded-full bg-muted">
                      <div
                        className="h-1.5 rounded-full bg-primary"
                        style={{ width: `${topicProgressPercent}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function StudyPathLandingSkeleton() {
  return (
    <main className="azalea-page-soft min-h-screen px-5 py-6 md:px-8 lg:px-10">
      <div className="mx-auto max-w-7xl space-y-5">
        <div className="flex items-center justify-between">
          <Skeleton className="h-10 w-28" />
          <Skeleton className="h-10 w-40" />
        </div>

        <Skeleton className="h-52 rounded-2xl" />

        <div className="grid gap-5 lg:grid-cols-[300px_1fr_360px]">
          <Skeleton className="h-[460px] rounded-2xl" />
          <Skeleton className="h-[460px] rounded-2xl" />
          <Skeleton className="h-[460px] rounded-2xl" />
        </div>
      </div>
    </main>
  );
}
