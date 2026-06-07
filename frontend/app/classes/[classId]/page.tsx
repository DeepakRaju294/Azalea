"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  ArrowLeft,
  ArrowRight,
  BarChart3,
  BookOpen,
  Clock3,
  FileText,
  MessageSquare,
  Plus,
  Send,
  Sparkles,
  Target,
  TriangleAlert,
  Upload,
} from "lucide-react";

import {
  addStudyPathToClass,
  askClassQuestion,
  createStudyPath,
  createStudySession,
  createTextMaterial,
  getClass,
  getClassAdaptivePlan,
  getClassAlignmentMetrics,
  getClassDailyPlan,
  getClassMaterials,
  getClassMemorySummary,
  getClassRecommendation,
  getClassStudyPaths,
  getClassTodaySessionSummary,
  getClassWeekSessionSummary,
  getClassWeakAreas,
  uploadPdfMaterial,
  type AlignmentMetrics,
  type AzaleaClass,
  type ClassAdaptivePlan,
  type ClassDailyPlan,
  type ClassMemorySummary,
  type ClassQAResponse,
  type ClassRecommendation,
  type LearningMaterial,
  type StudyPath,
  type StudySessionSummary,
  type WeakAreaSummary,
} from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";

import AdaptivePlanCard from "@/components/AdaptivePlanCard";
import AlignmentMetricsCard from "@/components/AlignmentMetricsCard";
import LearnerMemorySummaryCard from "@/components/LearnerMemorySummaryCard";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";

type ActiveTab = "overview" | "study-paths" | "sources";
type PromptMode = "ask" | "study-path" | "practice";

function formatMinutes(minutes: number | null | undefined) {
  if (!minutes || minutes <= 0) return "0 min";

  if (minutes < 60) return `${minutes} min`;

  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;

  if (remainingMinutes === 0) return `${hours}h`;

  return `${hours}h ${remainingMinutes}m`;
}

function getSourceLabel(source: ClassQAResponse["sources"][number]) {
  const extendedSource = source as ClassQAResponse["sources"][number] & {
    source_label?: string;
  };

  return extendedSource.source_label || source.material_title;
}

function getSourceFilename(source: ClassQAResponse["sources"][number]) {
  const extendedSource = source as ClassQAResponse["sources"][number] & {
    material_filename?: string | null;
  };

  return extendedSource.material_filename;
}

export default function ClassPage() {
  const params = useParams<{ classId: string }>();
  const classId = params.classId;

  const { isCheckingAuth } = useRequireAuth();

  const [activeTab, setActiveTab] = useState<ActiveTab>("overview");

  const [azaleaClass, setAzaleaClass] = useState<AzaleaClass | null>(null);
  const [studyPaths, setStudyPaths] = useState<StudyPath[]>([]);
  const [materials, setMaterials] = useState<LearningMaterial[]>([]);
  const [recommendation, setRecommendation] =
    useState<ClassRecommendation | null>(null);
  const [dailyPlan, setDailyPlan] = useState<ClassDailyPlan | null>(null);
  const [todaySessionSummary, setTodaySessionSummary] =
    useState<StudySessionSummary | null>(null);
  const [weekSessionSummary, setWeekSessionSummary] =
    useState<StudySessionSummary | null>(null);
  const [classWeakAreas, setClassWeakAreas] =
    useState<WeakAreaSummary | null>(null);

  const [classAdaptivePlan, setClassAdaptivePlan] =
    useState<ClassAdaptivePlan | null>(null);
  const [classMemorySummary, setClassMemorySummary] =
    useState<ClassMemorySummary | null>(null);
  const [classAlignmentMetrics, setClassAlignmentMetrics] =
    useState<AlignmentMetrics | null>(null);

  const [studyPathTitle, setStudyPathTitle] = useState("");
  const [studyPathGoal, setStudyPathGoal] = useState("");

  const [materialTitle, setMaterialTitle] = useState("");
  const [materialText, setMaterialText] = useState("");
  const [selectedPdf, setSelectedPdf] = useState<File | null>(null);

  const [promptMode, setPromptMode] = useState<PromptMode>("ask");
  const [prompt, setPrompt] = useState("");
  const [qaResponse, setQaResponse] = useState<ClassQAResponse | null>(null);

  const [status, setStatus] = useState("");
  const [isLoadingClass, setIsLoadingClass] = useState(false);
  const [isLoadingClassIntelligence, setIsLoadingClassIntelligence] =
    useState(false);
  const [isSubmittingPrompt, setIsSubmittingPrompt] = useState(false);

  const [isCreatePathOpen, setIsCreatePathOpen] = useState(false);
  const [isUploadPdfOpen, setIsUploadPdfOpen] = useState(false);
  const [isPasteTextOpen, setIsPasteTextOpen] = useState(false);

  const recommendedHref = useMemo(() => {
    if (recommendation?.study_path?.id) {
      if (recommendation.topic?.id) {
        return `/study-paths/${recommendation.study_path.id}?topicId=${recommendation.topic.id}&classId=${classId}`;
      }

      return `/study-paths/${recommendation.study_path.id}?classId=${classId}`;
    }

    const firstPath = studyPaths[0];

    if (firstPath) {
      return `/study-paths/${firstPath.id}?classId=${classId}`;
    }

    return null;
  }, [classId, recommendation, studyPaths]);

  const remainingMinutes = useMemo(() => {
    return studyPaths.reduce(
      (sum, path) => sum + (path.estimated_minutes_remaining ?? 0),
      0,
    );
  }, [studyPaths]);

  const dailyGoalMinutes =
    dailyPlan?.daily_goal_minutes ?? azaleaClass?.daily_goal_minutes ?? 60;

  const todayMinutes =
    dailyPlan?.today_minutes ?? todaySessionSummary?.total_minutes ?? 0;

  const dailyGoalPercent =
    dailyGoalMinutes > 0
      ? Math.min(100, Math.round((todayMinutes / dailyGoalMinutes) * 100))
      : 0;

  useEffect(() => {
    if (isCheckingAuth || !classId) return;

    async function fetchData() {
      try {
        setIsLoadingClass(true);
        setIsLoadingClassIntelligence(true);
        setStatus("");

        const [
          classData,
          pathData,
          materialData,
          recommendationData,
          dailyPlanData,
          todaySummaryData,
          weekSummaryData,
          weakAreaData,
          adaptivePlanData,
          memorySummaryData,
          alignmentMetricsData,
        ] = await Promise.all([
          getClass(classId),
          getClassStudyPaths(classId),
          getClassMaterials(classId),
          getClassRecommendation(classId),
          getClassDailyPlan(classId),
          getClassTodaySessionSummary(classId),
          getClassWeekSessionSummary(classId),
          getClassWeakAreas(classId),
          getClassAdaptivePlan(classId, { target_minutes: 30 }),
          getClassMemorySummary(classId),
          getClassAlignmentMetrics(classId),
        ]);

        setAzaleaClass(classData);
        setStudyPaths(pathData);
        setMaterials(materialData);
        setRecommendation(recommendationData);
        setDailyPlan(dailyPlanData);
        setTodaySessionSummary(todaySummaryData);
        setWeekSessionSummary(weekSummaryData);
        setClassWeakAreas(weakAreaData);
        setClassAdaptivePlan(adaptivePlanData);
        setClassMemorySummary(memorySummaryData);
        setClassAlignmentMetrics(alignmentMetricsData);
      } catch (err) {
        console.error(err);
        setStatus("Failed to load class.");
      } finally {
        setIsLoadingClass(false);
        setIsLoadingClassIntelligence(false);
      }
    }

    fetchData();
  }, [classId, isCheckingAuth]);

  useEffect(() => {
    if (!status || isLoadingClass || isSubmittingPrompt) return;

    const timer = window.setTimeout(() => {
      setStatus("");
    }, 4500);

    return () => window.clearTimeout(timer);
  }, [isLoadingClass, isSubmittingPrompt, status]);

  async function refreshClassData() {
    const [
      pathData,
      materialData,
      recommendationData,
      dailyPlanData,
      todaySummaryData,
      weekSummaryData,
      weakAreaData,
      adaptivePlanData,
      memorySummaryData,
      alignmentMetricsData,
    ] = await Promise.all([
      getClassStudyPaths(classId),
      getClassMaterials(classId),
      getClassRecommendation(classId),
      getClassDailyPlan(classId),
      getClassTodaySessionSummary(classId),
      getClassWeekSessionSummary(classId),
      getClassWeakAreas(classId),
      getClassAdaptivePlan(classId, { target_minutes: 30 }),
      getClassMemorySummary(classId),
      getClassAlignmentMetrics(classId),
    ]);

    setStudyPaths(pathData);
    setMaterials(materialData);
    setRecommendation(recommendationData);
    setDailyPlan(dailyPlanData);
    setTodaySessionSummary(todaySummaryData);
    setWeekSessionSummary(weekSummaryData);
    setClassWeakAreas(weakAreaData);
    setClassAdaptivePlan(adaptivePlanData);
    setClassMemorySummary(memorySummaryData);
    setClassAlignmentMetrics(alignmentMetricsData);
  }

  async function logClassStudySession(
    activityType: "lesson" | "practice" | "qa" | "review" | "regeneration",
    minutesSpent = 5,
  ) {
    try {
      await createStudySession({
        class_id: classId,
        minutes_spent: minutesSpent,
        activity_type: activityType,
      });

      const [
        updatedTodaySummary,
        updatedWeekSummary,
        updatedRecommendation,
        updatedAdaptivePlan,
        updatedAlignmentMetrics,
      ] = await Promise.all([
        getClassTodaySessionSummary(classId),
        getClassWeekSessionSummary(classId),
        getClassRecommendation(classId),
        getClassAdaptivePlan(classId, { target_minutes: 30 }),
        getClassAlignmentMetrics(classId),
      ]);

      setTodaySessionSummary(updatedTodaySummary);
      setWeekSessionSummary(updatedWeekSummary);
      setRecommendation(updatedRecommendation);
      setClassAdaptivePlan(updatedAdaptivePlan);
      setClassAlignmentMetrics(updatedAlignmentMetrics);
    } catch (err) {
      console.error("Failed to log class study session:", err);
    }
  }

  async function handleCreateStudyPathInClass(e: FormEvent) {
    e.preventDefault();

    if (!studyPathTitle.trim()) return;

    try {
      setStatus("Creating study path...");

      const createdPath = await createStudyPath({
        title: studyPathTitle,
        goal: studyPathGoal || undefined,
        estimated_minutes_remaining: 45,
      });

      await addStudyPathToClass(classId, createdPath.id);

      setStudyPathTitle("");
      setStudyPathGoal("");
      setIsCreatePathOpen(false);
      setActiveTab("study-paths");
      setStatus("Study path added to class.");
      await refreshClassData();
    } catch (err) {
      console.error(err);
      setStatus("Failed to create study path.");
    }
  }

  async function handleCreateTextMaterial(e: FormEvent) {
    e.preventDefault();

    if (!materialTitle.trim() || !materialText.trim()) return;

    try {
      setStatus("Adding text source...");

      await createTextMaterial(classId, {
        title: materialTitle,
        text: materialText,
      });

      setMaterialTitle("");
      setMaterialText("");
      setIsPasteTextOpen(false);
      setActiveTab("sources");
      setStatus("Text source added.");
      await refreshClassData();
    } catch (err) {
      console.error(err);
      setStatus("Failed to add text source.");
    }
  }

  async function handleUploadPdf(e: FormEvent) {
    e.preventDefault();

    if (!selectedPdf) return;

    try {
      setStatus("Uploading PDF...");

      await uploadPdfMaterial(classId, selectedPdf);

      setSelectedPdf(null);
      setIsUploadPdfOpen(false);
      setActiveTab("sources");
      setStatus("PDF source added.");
      await refreshClassData();
    } catch (err) {
      console.error(err);
      setStatus("Failed to upload PDF.");
    }
  }

  async function handlePromptSubmit(e: FormEvent) {
    e.preventDefault();

    if (!prompt.trim()) return;

    try {
      setIsSubmittingPrompt(true);
      setStatus("");

      if (promptMode === "ask") {
        setStatus("Asking Azalea about this class...");

        const response = await askClassQuestion(classId, prompt);

        setQaResponse(response);
        setPrompt("");
        await logClassStudySession("qa", 5);
        setStatus("Answer generated.");
        return;
      }

      if (promptMode === "study-path") {
        setStatus("Creating study path...");

        const createdPath = await createStudyPath({
          title: prompt,
          goal: prompt,
          estimated_minutes_remaining: 45,
        });

        await addStudyPathToClass(classId, createdPath.id);

        setPrompt("");
        setActiveTab("study-paths");
        await refreshClassData();
        setStatus("Study path created and added to class.");
        return;
      }

      if (promptMode === "practice") {
        await logClassStudySession("practice", 10);
        setPrompt("");
        setStatus(
          "Practice request logged. Connect this to your class practice route when ready.",
        );
      }
    } catch (err) {
      console.error(err);
      setStatus(
        promptMode === "ask"
          ? "Failed to answer question. Make sure this class has uploaded material."
          : "Failed to process request.",
      );
    } finally {
      setIsSubmittingPrompt(false);
    }
  }

  if (isCheckingAuth) {
    return <ClassPageSkeleton />;
  }

  return (
    <main className="azalea-page-soft min-h-screen pb-36 text-slate-950">
      <div className="mx-auto max-w-7xl px-6 py-7">
        <Link
          href="/"
          className="mb-8 inline-flex items-center gap-2 text-sm font-medium text-slate-900 transition hover:text-purple-700"
        >
          <ArrowLeft className="h-4 w-4" />
          Home
        </Link>

        <header className="mb-6">
          <div className="mt-2 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <h1 className="text-4xl font-semibold tracking-tight text-slate-950 md:text-5xl">
                {azaleaClass?.name || "Loading class..."}
              </h1>

              {azaleaClass?.description && (
                <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-500">
                  {azaleaClass.description}
                </p>
              )}
            </div>

            {activeTab === "overview" && (
              <div className="hidden items-center gap-3 lg:flex">
                <AddSourceButton onClick={() => setIsUploadPdfOpen(true)} />

                <Button
                  className="h-12 rounded-full bg-purple-600 px-7 text-base shadow-sm hover:bg-purple-700"
                  onClick={() => setIsCreatePathOpen(true)}
                >
                  <Plus className="mr-2 h-5 w-5" />
                  Add Study Path
                </Button>
              </div>
            )}
          </div>
        </header>

        <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-7">
            <TabButton
              active={activeTab === "overview"}
              onClick={() => setActiveTab("overview")}
            >
              Overview
            </TabButton>

            <TabButton
              active={activeTab === "study-paths"}
              onClick={() => setActiveTab("study-paths")}
            >
              Study Paths
            </TabButton>

            <TabButton
              active={activeTab === "sources"}
              onClick={() => setActiveTab("sources")}
            >
              Sources
            </TabButton>
          </div>

          <div className="flex items-center gap-3 lg:hidden">
            <AddSourceButton onClick={() => setIsUploadPdfOpen(true)} />

            <Button
              className="h-11 rounded-full bg-purple-600 px-5 shadow-sm hover:bg-purple-700"
              onClick={() => setIsCreatePathOpen(true)}
            >
              <Plus className="mr-2 h-4 w-4" />
              Add Study Path
            </Button>
          </div>
        </div>

        {status && (
          <div className="azalea-surface mb-5 rounded-2xl border px-4 py-3 text-sm text-slate-600 shadow-sm">
            {status}
          </div>
        )}

        {isLoadingClass && (
          <div className="azalea-surface mb-5 rounded-2xl border px-4 py-3 text-sm text-slate-600 shadow-sm">
            Loading your class workspace...
          </div>
        )}

        {activeTab === "overview" && (
          <OverviewTab
            classId={classId}
            classAdaptivePlan={classAdaptivePlan}
            classMemorySummary={classMemorySummary}
            classAlignmentMetrics={classAlignmentMetrics}
            isLoadingClassIntelligence={isLoadingClassIntelligence}
            recommendation={recommendation}
            recommendedHref={recommendedHref}
            dailyGoalMinutes={dailyGoalMinutes}
            todayMinutes={todayMinutes}
            dailyGoalPercent={dailyGoalPercent}
            remainingMinutes={remainingMinutes}
            weekSessionSummary={weekSessionSummary}
            classWeakAreas={classWeakAreas}
            onAddStudyPath={() => setIsCreatePathOpen(true)}
          />
        )}

        {activeTab === "study-paths" && (
          <StudyPathsTab
            studyPaths={studyPaths}
            classId={classId}
            onAddStudyPath={() => setIsCreatePathOpen(true)}
          />
        )}

        {activeTab === "sources" && (
          <SourcesTab
            materials={materials}
            onAddPdf={() => setIsUploadPdfOpen(true)}
            onAddText={() => setIsPasteTextOpen(true)}
          />
        )}

        {qaResponse && (
          <Card className="azalea-surface mt-6 rounded-3xl border shadow-sm">
            <CardHeader>
              <CardDescription>Class answer</CardDescription>
              <CardTitle>Azalea response</CardTitle>
            </CardHeader>

            <CardContent className="space-y-5">
              <p className="whitespace-pre-wrap text-sm leading-7 text-slate-700">
                {qaResponse.answer}
              </p>

              {qaResponse.sources.length > 0 && (
                <div>
                  <p className="text-sm font-semibold">Sources</p>

                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    {qaResponse.sources.slice(0, 4).map((source, index) => {
                      const filename = getSourceFilename(source);

                      return (
                        <div
                          key={`${source.material_id}-${source.chunk_index}-${index}`}
                          className="rounded-2xl border border-purple-100 bg-purple-50/40 p-4"
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="text-sm font-semibold">
                                {getSourceLabel(source)}
                              </p>

                              <p className="mt-1 text-xs text-slate-500">
                                Chunk {source.chunk_index}
                                {filename ? ` · ${filename}` : ""}
                              </p>
                            </div>

                            <Badge variant="secondary" className="rounded-full">
                              {index + 1}
                            </Badge>
                          </div>

                          <p className="mt-3 line-clamp-3 text-xs leading-5 text-slate-500">
                            {source.preview}
                          </p>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>

      <form
        onSubmit={handlePromptSubmit}
        className="fixed inset-x-0 bottom-0 z-30 border-t border-[#E2DCEA] bg-white/88 px-4 py-4 shadow-[0_-12px_40px_rgba(88,28,135,0.08)] backdrop-blur"
      >
        <div className="mx-auto max-w-5xl">
          <div className="mb-3 flex flex-wrap gap-2">
            <PromptModeButton
              active={promptMode === "ask"}
              onClick={() => setPromptMode("ask")}
            >
              Ask Question
            </PromptModeButton>

            <PromptModeButton
              active={promptMode === "study-path"}
              onClick={() => setPromptMode("study-path")}
            >
              Generate Study Path
            </PromptModeButton>

            <PromptModeButton
              active={promptMode === "practice"}
              onClick={() => setPromptMode("practice")}
            >
              Create Practice
            </PromptModeButton>
          </div>

          <div className="azalea-tint flex items-center gap-2 rounded-3xl border p-2">
            <MessageSquare className="ml-3 h-5 w-5 shrink-0 text-purple-500" />

            <Input
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              className="h-12 border-0 bg-transparent text-base shadow-none focus-visible:ring-0"
              placeholder={
                promptMode === "ask"
                  ? "Ask, generate, or practice in this class..."
                  : promptMode === "study-path"
                    ? "Describe the study path you want Azalea to create..."
                    : "Describe the practice you want for this class..."
              }
            />

            <Button
              type="submit"
              size="icon"
              className="h-12 w-12 shrink-0 rounded-full bg-purple-600 hover:bg-purple-700"
              disabled={isSubmittingPrompt || !prompt.trim()}
            >
              <Send className="h-5 w-5" />
            </Button>
          </div>
        </div>
      </form>

      <Dialog open={isCreatePathOpen} onOpenChange={setIsCreatePathOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add study path</DialogTitle>
            <DialogDescription>
              Create a new study path directly inside this class.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleCreateStudyPathInClass} className="space-y-4">
            <Input
              placeholder="Study path title"
              value={studyPathTitle}
              onChange={(e) => setStudyPathTitle(e.target.value)}
            />

            <Textarea
              placeholder="Learning goal, e.g. prepare for lectures 3–5"
              value={studyPathGoal}
              onChange={(e) => setStudyPathGoal(e.target.value)}
            />

            <Button type="submit" className="w-full">
              Add to class
            </Button>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={isUploadPdfOpen} onOpenChange={setIsUploadPdfOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add PDF source</DialogTitle>
            <DialogDescription>
              Upload a PDF so Azalea can use it for study paths, practice, and
              class Q&A.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleUploadPdf} className="space-y-4">
            <Input
              type="file"
              accept="application/pdf"
              onChange={(e) => setSelectedPdf(e.target.files?.[0] ?? null)}
            />

            <Button type="submit" className="w-full" disabled={!selectedPdf}>
              Upload PDF
            </Button>
          </form>

          <div className="border-t pt-4">
            <Button
              variant="outline"
              className="w-full"
              onClick={() => {
                setIsUploadPdfOpen(false);
                setIsPasteTextOpen(true);
              }}
            >
              Paste text instead
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={isPasteTextOpen} onOpenChange={setIsPasteTextOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Paste text source</DialogTitle>
            <DialogDescription>
              Add notes, lecture text, or problem statements as class material.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleCreateTextMaterial} className="space-y-4">
            <Input
              placeholder="Source title"
              value={materialTitle}
              onChange={(e) => setMaterialTitle(e.target.value)}
            />

            <Textarea
              className="min-h-36"
              placeholder="Paste material text here..."
              value={materialText}
              onChange={(e) => setMaterialText(e.target.value)}
            />

            <Button
              type="submit"
              className="w-full"
              disabled={!materialTitle.trim() || !materialText.trim()}
            >
              Add text source
            </Button>
          </form>
        </DialogContent>
      </Dialog>
    </main>
  );
}

function OverviewTab({
  classId,
  classAdaptivePlan,
  classMemorySummary,
  classAlignmentMetrics,
  isLoadingClassIntelligence,
  recommendation,
  recommendedHref,
  dailyGoalMinutes,
  todayMinutes,
  dailyGoalPercent,
  remainingMinutes,
  weekSessionSummary,
  classWeakAreas,
  onAddStudyPath,
}: {
  classId: string;
  classAdaptivePlan: ClassAdaptivePlan | null;
  classMemorySummary: ClassMemorySummary | null;
  classAlignmentMetrics: AlignmentMetrics | null;
  isLoadingClassIntelligence: boolean;
  recommendation: ClassRecommendation | null;
  recommendedHref: string | null;
  dailyGoalMinutes: number;
  todayMinutes: number;
  dailyGoalPercent: number;
  remainingMinutes: number;
  weekSessionSummary: StudySessionSummary | null;
  classWeakAreas: WeakAreaSummary | null;
  onAddStudyPath: () => void;
}) {
  const weakAreas = classWeakAreas?.weak_areas ?? [];

  return (
    <section className="grid gap-5 lg:grid-cols-2">
      <div className="lg:col-span-2">
        <AdaptivePlanCard
          plan={classAdaptivePlan}
          classId={classId}
          isLoading={isLoadingClassIntelligence}
          title="Recommended today"
        />
      </div>

      <AlignmentMetricsCard
        metrics={classAlignmentMetrics}
        isLoading={isLoadingClassIntelligence}
      />

      <LearnerMemorySummaryCard
        memorySummary={classMemorySummary}
        isLoading={isLoadingClassIntelligence}
      />

      <Card className="azalea-surface rounded-3xl border shadow-sm">
        <CardHeader className="pb-4">
          <div className="flex items-start gap-4">
            <div className="rounded-2xl bg-purple-100 p-3 text-purple-600">
              <Sparkles className="h-5 w-5" />
            </div>

            <div>
              <CardTitle>Recommended Next</CardTitle>
              <CardDescription className="mt-1">
                A simple fallback recommendation for this class.
              </CardDescription>
            </div>
          </div>
        </CardHeader>

        <CardContent>
          <div className="flex min-h-[150px] flex-col justify-between gap-6 md:flex-row md:items-end">
            <div>
              <h2 className="text-2xl font-semibold tracking-tight">
                {recommendation?.topic
                  ? recommendation.topic.title
                  : recommendation?.is_complete
                    ? "You’re caught up"
                    : "Start building this class"}
              </h2>

              <p className="mt-3 max-w-xl text-sm leading-6 text-slate-500">
                {recommendation?.message ||
                  "Add a source or study path so Azalea can recommend what to learn next."}
              </p>

              {recommendation?.topic && (
                <Badge className="mt-5 rounded-full bg-purple-100 text-purple-700 hover:bg-purple-100">
                  <Clock3 className="mr-1.5 h-3.5 w-3.5" />
                  {recommendation.topic.estimated_minutes
                    ? `${recommendation.topic.estimated_minutes} min · `
                    : ""}
                  {recommendation.topic.status.replace(/_/g, " ")}
                </Badge>
              )}
            </div>

            {recommendedHref ? (
              <Button
                asChild
                className="rounded-2xl bg-purple-600 px-8 hover:bg-purple-700"
              >
                <Link href={recommendedHref}>
                  Start
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
            ) : (
              <Button
                className="rounded-2xl bg-purple-600 px-8 hover:bg-purple-700"
                onClick={onAddStudyPath}
              >
                Add Path
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      <Card className="azalea-surface rounded-3xl border shadow-sm">
        <CardHeader className="pb-4">
          <div className="flex items-start gap-4">
            <div className="rounded-2xl bg-purple-100 p-3 text-purple-600">
              <Target className="h-5 w-5" />
            </div>

            <div>
              <CardTitle>Daily Goal</CardTitle>
              <CardDescription className="mt-1">
                Keep today’s progress visible.
              </CardDescription>
            </div>
          </div>
        </CardHeader>

        <CardContent>
          <div className="mt-1">
            <p className="text-4xl font-semibold text-purple-600">
              {todayMinutes}
              <span className="ml-2 text-2xl font-medium text-slate-500">
                / {dailyGoalMinutes} min
              </span>
            </p>

            <div className="mt-5">
              <ProgressBar value={dailyGoalPercent} />
            </div>

            <p className="mt-4 text-sm text-slate-500">
              {Math.max(0, dailyGoalMinutes - todayMinutes)} min left today
            </p>
          </div>
        </CardContent>
      </Card>

      <Card className="azalea-surface rounded-3xl border shadow-sm">
        <CardHeader className="pb-4">
          <div className="flex items-start gap-4">
            <div className="rounded-2xl bg-purple-100 p-3 text-purple-600">
              <TriangleAlert className="h-5 w-5" />
            </div>

            <div>
              <CardTitle>Weak Areas</CardTitle>
              <CardDescription className="mt-1">
                Mistake patterns Azalea is tracking.
              </CardDescription>
            </div>
          </div>
        </CardHeader>

        <CardContent>
          {weakAreas.length === 0 ? (
            <EmptyPanel
              title="No weak areas yet"
              description="Once you submit practice answers, repeated mistake patterns will appear here."
            />
          ) : (
            <div className="space-y-3">
              {weakAreas.slice(0, 3).map((weakArea, index) => (
                <div
                  key={`${weakArea.mistake_type}-${index}`}
                  className="flex items-center justify-between gap-4 rounded-2xl border border-[#E7E1EF] bg-white/70 px-4 py-3"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <span className="h-2 w-2 rounded-full bg-purple-600" />

                    <p className="truncate text-sm font-medium">
                      {weakArea.mistake_type}
                    </p>
                  </div>

                  <div className="flex shrink-0 items-center gap-3">
                    <Badge
                      variant="secondary"
                      className="rounded-full bg-red-50 text-red-600"
                    >
                      x{weakArea.count}
                    </Badge>

                    <ArrowRight className="h-4 w-4 text-slate-400" />
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="azalea-surface rounded-3xl border shadow-sm">
        <CardHeader className="pb-4">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-4">
              <div className="rounded-2xl bg-purple-100 p-3 text-purple-600">
                <BarChart3 className="h-5 w-5" />
              </div>

              <div>
                <CardTitle>Engagement</CardTitle>
                <CardDescription className="mt-1">
                  Time invested in this class.
                </CardDescription>
              </div>
            </div>

            <Badge variant="outline" className="rounded-full">
              This week
            </Badge>
          </div>
        </CardHeader>

        <CardContent>
          <div className="grid grid-cols-3 gap-4">
            <EngagementMetric label="Today" value={formatMinutes(todayMinutes)} />
            <EngagementMetric
              label="This week"
              value={formatMinutes(weekSessionSummary?.total_minutes ?? 0)}
            />
            <EngagementMetric
              label="Remaining"
              value={formatMinutes(remainingMinutes)}
            />
          </div>

          <div className="mt-7 flex h-16 items-end justify-between gap-4">
            {[20, 42, 58, 33, 18, 14, 16].map((height, index) => (
              <div key={index} className="flex flex-1 flex-col items-center gap-2">
                <div
                  className={`w-5 rounded-md ${
                    index < 4 ? "bg-purple-600" : "bg-slate-200"
                  }`}
                  style={{ height }}
                />
                <span className="text-xs text-slate-500">
                  {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][index]}
                </span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </section>
  );
}

function StudyPathsTab({
  studyPaths,
  classId,
  onAddStudyPath,
}: {
  studyPaths: StudyPath[];
  classId: string;
  onAddStudyPath: () => void;
}) {
  return (
    <section>
      <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <h2 className="text-3xl font-semibold tracking-tight">Study Paths</h2>
          <p className="mt-2 text-sm text-slate-500">
            All your learning paths with progress and performance data.
          </p>
        </div>

        <Button
          className="h-12 rounded-full bg-purple-600 px-7 text-base hover:bg-purple-700"
          onClick={onAddStudyPath}
        >
          <Plus className="mr-2 h-5 w-5" />
          New Study Path
        </Button>
      </div>

      {studyPaths.length === 0 ? (
        <EmptyPanel
          title="No study paths yet"
          description="Create a study path to start learning inside this class."
        />
      ) : (
        <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
          {studyPaths.map((path) => (
            <Link
              key={path.id}
              href={`/study-paths/${path.id}?classId=${classId}`}
              className="group azalea-surface rounded-3xl border p-7 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
            >
              <div className="mb-8 flex items-start justify-between gap-4">
                <div className="rounded-2xl bg-purple-100 p-3 text-purple-600">
                  <BookOpen className="h-6 w-6" />
                </div>

                <ArrowRight className="h-5 w-5 text-slate-400 transition group-hover:translate-x-1 group-hover:text-purple-600" />
              </div>

              <h3 className="text-xl font-semibold tracking-tight">
                {path.title}
              </h3>

              <p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-500">
                {path.goal || "No goal provided"}
              </p>

              <div className="mt-7">
                <div className="mb-2 flex items-center justify-between text-sm">
                  <span className="text-slate-500">Progress</span>
                  <span className="font-medium text-purple-600">
                    {path.progress_percent}%
                  </span>
                </div>

                <ProgressBar value={path.progress_percent} />
              </div>

              <div className="mt-5 border-t border-slate-100 pt-5 text-sm text-slate-500">
                {formatMinutes(path.estimated_minutes_remaining)} remaining
              </div>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}

function SourcesTab({
  materials,
  onAddPdf,
  onAddText,
}: {
  materials: LearningMaterial[];
  onAddPdf: () => void;
  onAddText: () => void;
}) {
  return (
    <section>
      <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <h2 className="text-3xl font-semibold tracking-tight">Sources</h2>
          <p className="mt-2 text-sm text-slate-500">
            PDFs and pasted notes that ground this class.
          </p>
        </div>

        <div className="flex flex-wrap gap-3">
          <Button
            className="h-12 rounded-full bg-purple-600 px-7 text-base hover:bg-purple-700"
            onClick={onAddPdf}
          >
            <Upload className="mr-2 h-5 w-5" />
            Add PDF
          </Button>

          <Button
            variant="outline"
            className="h-12 rounded-full border-purple-100 bg-white px-7 text-base"
            onClick={onAddText}
          >
            <FileText className="mr-2 h-5 w-5" />
            Add Text
          </Button>
        </div>
      </div>

      {materials.length === 0 ? (
        <EmptyPanel
          title="No sources yet"
          description="Add a PDF or paste text so Azalea can generate grounded study paths and Q&A."
        />
      ) : (
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {materials.map((material) => (
            <Card
              key={material.id}
              className="azalea-surface rounded-3xl border shadow-sm"
            >
              <CardContent className="p-6">
                <div className="mb-5 flex items-start justify-between gap-4">
                  <div className="rounded-2xl bg-purple-100 p-3 text-purple-600">
                    <FileText className="h-6 w-6" />
                  </div>

                  <Badge variant="outline" className="rounded-full">
                    {material.material_type.toUpperCase()}
                  </Badge>
                </div>

                <h3 className="truncate text-lg font-semibold">
                  {material.title}
                </h3>

                {material.filename && (
                  <p className="mt-2 truncate text-sm text-slate-500">
                    {material.filename}
                  </p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </section>
  );
}

function AddSourceButton({ onClick }: { onClick: () => void }) {
  return (
    <Button
      variant="outline"
      className="h-12 rounded-full border-purple-600 bg-white px-7 text-base text-purple-700 hover:bg-purple-50"
      onClick={onClick}
    >
      <Plus className="mr-2 h-5 w-5" />
      Add Source
    </Button>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`relative px-4 pb-4 text-base font-semibold transition ${
        active ? "text-purple-700" : "text-slate-500 hover:text-slate-900"
      }`}
    >
      {children}

      {active && (
        <span className="absolute inset-x-0 bottom-0 h-0.5 rounded-full bg-purple-600" />
      )}
    </button>
  );
}

function PromptModeButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full px-4 py-2 text-sm font-medium transition ${
        active
          ? "bg-purple-100 text-purple-700"
          : "bg-slate-100 text-slate-600 hover:bg-slate-200"
      }`}
    >
      {children}
    </button>
  );
}

function EngagementMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-r border-slate-100 last:border-r-0">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-purple-600">{value}</p>
    </div>
  );
}

function ProgressBar({ value }: { value: number }) {
  return (
    <div className="h-2 rounded-full bg-slate-200">
      <div
        className="h-2 rounded-full bg-purple-600"
        style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
      />
    </div>
  );
}

function EmptyPanel({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="azalea-surface rounded-3xl border border-dashed p-8 text-center shadow-sm">
      <p className="text-base font-semibold">{title}</p>
      <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500">
        {description}
      </p>
    </div>
  );
}

function ClassPageSkeleton() {
  return (
    <main className="azalea-page-soft min-h-screen px-6 py-7">
      <div className="mx-auto max-w-7xl space-y-6">
        <Skeleton className="h-7 w-24 rounded-full" />
        <Skeleton className="h-14 w-[520px] rounded-2xl" />

        <div className="grid gap-5 lg:grid-cols-2">
          <Skeleton className="h-64 rounded-3xl" />
          <Skeleton className="h-64 rounded-3xl" />
          <Skeleton className="h-64 rounded-3xl" />
          <Skeleton className="h-64 rounded-3xl" />
        </div>
      </div>
    </main>
  );
}