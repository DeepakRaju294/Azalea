"use client";

import Link from "next/link";
import { Fraunces } from "next/font/google";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  ArrowRight,
  BookOpen,
  Dumbbell,
  GraduationCap,
  LogOut,
  MessageSquarePlus,
  Paperclip,
  Plus,
  UploadCloud,
  X,
} from "lucide-react";

import {
  addStudyPathToClass,
  createClass,
  createQuickPracticeSession,
  createStudyPath,
  generateInitialStudyPath,
  generateQuickPracticeQuestionSet,
  getClasses,
  getQuickPracticeSessions,
  getStudyPaths,
  uploadPdfMaterial,
  uploadPdfMaterialToStudyPath,
  uploadQuickPracticePdf,
  type AzaleaClass,
  type QuickPracticeSession,
  type StudyPath,
} from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import BrandLockup from "@/components/BrandLockup";

const headlineFont = Fraunces({
  subsets: ["latin"],
  weight: ["700"],
});

type SidebarMode = "study_paths" | "classes";

type PromptMode = "study_path" | "practice" | "explain" | "solve";

const promptStarters: {
  label: string;
  mode: PromptMode;
  starter: string;
  description: string;
}[] = [
  {
    label: "Learn",
    mode: "study_path",
    starter: "Create a study path for ",
    description: "Create a study path for a lecture, unit, or learning objective.",
  },
  {
    label: "Practice",
    mode: "practice",
    starter: "Create a practice set for ",
    description: "Create a question set for a topic or learning objective.",
  },
  {
    label: "Explain",
    mode: "explain",
    starter: "Explain this problem step by step: ",
    description: "Turn one pasted problem into a short guided solution path.",
  },
  {
    label: "Solve",
    mode: "solve",
    starter: "Let me solve this problem: ",
    description: "Open the pasted problem in the matching math or coding workspace.",
  },
];

function isQuickPracticePrompt(prompt: string) {
  const normalizedPrompt = prompt.toLowerCase();

  return [
    "practice",
    "quiz me",
    "test me",
    "drill",
    "questions",
    "problems",
    "flashcards",
  ].some((phrase) => normalizedPrompt.includes(phrase));
}

function shouldCreateQuickPractice(mode: PromptMode | null, prompt: string) {
  if (mode === "practice" || mode === "solve") {
    return true;
  }

  return isQuickPracticePrompt(prompt);
}

function getStartButtonLabel(mode: PromptMode | null, prompt: string) {
  const resolvedMode = mode ?? inferPromptMode(prompt);

  if (!resolvedMode && prompt.trim()) return "Choose mode";

  if (!prompt.trim()) {
    if (resolvedMode === "practice") return "Start practice";
    if (resolvedMode === "explain") return "Explain";
    if (resolvedMode === "solve") return "Solve";
    return "Create path";
  }

  if (resolvedMode === "practice") return "Start practice";
  if (resolvedMode === "explain") return "Explain";
  if (resolvedMode === "solve") return "Solve";
  return "Create path";
}

function inferPromptMode(prompt: string): PromptMode | null {
  const normalizedPrompt = prompt.toLowerCase();

  if (
    /\b(let me solve|i want to solve|open.*ide|coding ide|math workspace|sandbox)\b/.test(
      normalizedPrompt
    )
  ) {
    return "solve";
  }

  if (
    /\b(practice|quiz me|test me|drill|question set|practice set)\b/.test(
      normalizedPrompt
    )
  ) {
    return "practice";
  }

  if (
    /\b(explain|teach|walk me through|step by step|guided solution|show solution|solution)\b/.test(
      normalizedPrompt
    )
  ) {
    return "explain";
  }

  if (/\b(create a study path|study path|learn)\b/.test(normalizedPrompt)) {
    return "study_path";
  }

  return null;
}

export default function HomePage() {
  const router = useRouter();

  const {
    userEmail,
    isCheckingAuth,
    logout: handleLogout,
  } = useRequireAuth();

  const [classes, setClasses] = useState<AzaleaClass[]>([]);
  const [studyPaths, setStudyPaths] = useState<StudyPath[]>([]);
  const [practiceSessions, setPracticeSessions] = useState<
    QuickPracticeSession[]
  >([]);

  const [sidebarMode, setSidebarMode] = useState<SidebarMode>("study_paths");

  const [className, setClassName] = useState("");
  const [classDescription, setClassDescription] = useState("");

  const [learningGoal, setLearningGoal] = useState("");
  const [selectedPromptMode, setSelectedPromptMode] =
    useState<PromptMode | null>(null);
  const [selectedPromptClassId, setSelectedPromptClassId] = useState("");
  const [selectedPromptPdf, setSelectedPromptPdf] = useState<File | null>(null);
  const [shouldAddPromptPathToClass, setShouldAddPromptPathToClass] =
    useState(false);

  const [selectedClassId, setSelectedClassId] = useState("");
  const [selectedStudyPathId, setSelectedStudyPathId] = useState("");

  const [status, setStatus] = useState("");
  const [isLoadingData, setIsLoadingData] = useState(false);
  const [isPromptSubmitting, setIsPromptSubmitting] = useState(false);
  const [isCreateClassOpen, setIsCreateClassOpen] = useState(false);
  const [isAttachPathOpen, setIsAttachPathOpen] = useState(false);
  const [isPromptIntentDialogOpen, setIsPromptIntentDialogOpen] =
    useState(false);

  const recentLearningItems = useMemo(() => {
    return [
      ...studyPaths.map((path) => ({
        id: path.id,
        type: "study_path" as const,
        title: path.title,
        subtitle: `${path.progress_percent}% complete`,
        href: `/study-paths/${path.id}`,
        created_at: path.created_at,
      })),
      ...practiceSessions.map((session) => ({
        id: session.id,
        type: "practice" as const,
        title: session.title || session.prompt,
        subtitle: session.source_filename
          ? `Quick practice · ${session.source_filename}`
          : "Quick practice",
        href: `/practice/${session.id}`,
        created_at: session.created_at,
      })),
    ].sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );
  }, [practiceSessions, studyPaths]);

  const recentClasses = useMemo(() => classes, [classes]);

  async function refreshData() {
    const [classData, studyPathData, practiceSessionData] = await Promise.all([
      getClasses(),
      getStudyPaths(),
      getQuickPracticeSessions(),
    ]);

    setClasses(classData);
    setStudyPaths(studyPathData);
    setPracticeSessions(practiceSessionData);
  }

  useEffect(() => {
    if (isCheckingAuth) return;

    async function fetchData() {
      try {
        setIsLoadingData(true);
        await refreshData();
      } catch (err) {
        console.error(err);
        setStatus("Failed to load data from backend.");
      } finally {
        setIsLoadingData(false);
      }
    }

    fetchData();
  }, [isCheckingAuth]);

  useEffect(() => {
    if (!status || isPromptSubmitting || isLoadingData) return;

    const timer = window.setTimeout(() => {
      setStatus("");
    }, 4500);

    return () => window.clearTimeout(timer);
  }, [isLoadingData, isPromptSubmitting, status]);

  async function handleCreateClass(e: FormEvent) {
    e.preventDefault();

    if (!className.trim()) return;

    try {
      await createClass({
        name: className,
        description: classDescription || undefined,
      });

      setClassName("");
      setClassDescription("");
      setIsCreateClassOpen(false);
      setSidebarMode("classes");
      setStatus("Class created.");
      await refreshData();
    } catch (err) {
      console.error(err);
      setStatus("Failed to create class.");
    }
  }

  async function handleCreateFromPrompt(e: FormEvent) {
    e.preventDefault();

    if (!learningGoal.trim()) return;

    const resolvedPromptMode =
      selectedPromptMode ?? inferPromptMode(learningGoal.trim());

    if (!resolvedPromptMode) {
      setIsPromptIntentDialogOpen(true);
      return;
    }

    try {
      setIsPromptSubmitting(true);

      if (shouldCreateQuickPractice(resolvedPromptMode, learningGoal)) {
        const isSolveMode = resolvedPromptMode === "solve";
        setStatus(
          isSolveMode
            ? "Opening this problem in a focused workspace..."
            : "Creating a focused practice set..."
        );

        const practiceSession = await createQuickPracticeSession({
          prompt: learningGoal.trim(),
          exact_problem: isSolveMode,
        });

        if (selectedPromptPdf) {
          setStatus("Uploading source material for practice...");
          await uploadQuickPracticePdf(practiceSession.id, selectedPromptPdf);
        }

        if (!isSolveMode) {
          setStatus("Building your practice question set...");
          await generateQuickPracticeQuestionSet(practiceSession.id, {
            count: 8,
            replace_existing: true,
          });
        }

        setLearningGoal("");
        setSelectedPromptPdf(null);
        setSelectedPromptClassId("");
        setShouldAddPromptPathToClass(false);
        setStatus("Practice session created.");
        router.push(`/practice/${practiceSession.id}`);
        return;
      }

      const isGuidedSolution = resolvedPromptMode === "explain";
      const studyPathGoal = isGuidedSolution
        ? [
            "Create exactly one guided solution topic for this pasted problem.",
            "Teach the solution step by step as an Azalea lesson.",
            "Use diagrams, graphs, tables, code traces, or math visuals when they reduce cognitive load.",
            "",
            "Problem:",
            learningGoal.trim(),
          ].join("\n")
        : learningGoal.trim();

      if (selectedPromptPdf && selectedPromptClassId) {
        setStatus(
          "Creating your study path and storing the PDF in the selected class..."
        );
      } else if (selectedPromptPdf) {
        setStatus("Creating your study path and attaching the PDF...");
      } else {
        setStatus("Creating your study path...");
      }

      const createdPath = await createStudyPath({
        title: learningGoal.trim().slice(0, 80),
        goal: studyPathGoal,
        estimated_minutes_remaining: 45,
      });

      if (selectedPromptClassId && shouldAddPromptPathToClass) {
        await addStudyPathToClass(selectedPromptClassId, createdPath.id);
      }

      if (selectedPromptPdf) {
        if (selectedPromptClassId) {
          await uploadPdfMaterial(selectedPromptClassId, selectedPromptPdf);
        } else {
          await uploadPdfMaterialToStudyPath(createdPath.id, selectedPromptPdf);
        }
      }

      setLearningGoal("");
      setSelectedPromptPdf(null);
      setSelectedPromptClassId("");
      setShouldAddPromptPathToClass(false);

      if (isGuidedSolution) {
        setStatus("Building a guided solution lesson...");
        // Phase 7 cutover (default ON, 2026-06-04):
        //   v2 is the default. ?v=1 on the homepage URL opts back into legacy.
        //   lesson_version in the response picks the learn route regardless.
        const useV2 =
          typeof window === "undefined" ||
          new URLSearchParams(window.location.search).get("v") !== "1";
        const initial = await generateInitialStudyPath(createdPath.id, {
          useV2,
        });
        await refreshData();
        const learnRoute = initial.lesson_version === 2 ? "learn-v2" : "learn";
        const topicQuery =
          initial.lesson_version === 2
            ? `?topic=${initial.first_topic_id}`
            : `?topicId=${initial.first_topic_id}`;
        router.push(
          `/study-paths/${createdPath.id}/${learnRoute}${topicQuery}`,
        );
      } else {
        setStatus("Study path created.");
        await refreshData();
        router.push(`/study-paths/${createdPath.id}`);
      }
    } catch (err) {
      console.error(err);
      setStatus("Failed to create from prompt.");
    } finally {
      setIsPromptSubmitting(false);
    }
  }

  function submitPromptWithMode(mode: PromptMode) {
    setSelectedPromptMode(mode);
    setIsPromptIntentDialogOpen(false);
    window.setTimeout(() => {
      const form = document.getElementById("azalea-home-prompt-form");
      if (form instanceof HTMLFormElement) {
        form.requestSubmit();
      }
    }, 0);
  }

  async function handleAttachStudyPath(e: FormEvent) {
    e.preventDefault();

    if (!selectedClassId || !selectedStudyPathId) return;

    try {
      await addStudyPathToClass(selectedClassId, selectedStudyPathId);
      setSelectedClassId("");
      setSelectedStudyPathId("");
      setIsAttachPathOpen(false);
      setStatus("Study path added to class.");
      await refreshData();
    } catch (err) {
      console.error(err);
      setStatus("Failed to add study path to class.");
    }
  }

  function applyPromptStarter(mode: PromptMode) {
    setSelectedPromptMode(mode);
  }

  if (isCheckingAuth) {
    return <HomeSkeleton />;
  }

  return (
    <main className="h-screen overflow-hidden bg-[#F7F4FB] text-[#17151F]">
      <div className="flex h-screen overflow-hidden">
        <aside className="hidden h-screen w-72 shrink-0 overflow-hidden border-r border-[#E2DCEA] bg-[#F3EFF8] p-4 lg:flex lg:flex-col">
          <div className="px-1 py-1">
            <BrandLockup size="lg" priority />
          </div>

          <div className="mt-2 grid grid-cols-2 rounded-2xl bg-[#EAE4F0] p-1">
            <button
              onClick={() => setSidebarMode("study_paths")}
              className={`rounded-xl px-3 py-2 text-xs font-semibold transition ${
                sidebarMode === "study_paths"
                  ? "bg-white text-[#21172F] shadow-sm"
                  : "text-[#7D748D] hover:text-[#21172F]"
              }`}
            >
              Study paths
            </button>

            <button
              onClick={() => setSidebarMode("classes")}
              className={`rounded-xl px-3 py-2 text-xs font-semibold transition ${
                sidebarMode === "classes"
                  ? "bg-white text-[#21172F] shadow-sm"
                  : "text-[#7D748D] hover:text-[#21172F]"
              }`}
            >
              Classes
            </button>
          </div>

          {sidebarMode === "classes" && (
            <Dialog
              open={isCreateClassOpen}
              onOpenChange={setIsCreateClassOpen}
            >
              <DialogTrigger asChild>
                <Button
                  className="mt-3 w-full justify-start rounded-2xl bg-[#8C5CF4] px-3 text-white shadow-sm shadow-purple-300/30 hover:bg-[#7D4DE5]"
                  size="sm"
                >
                  <Plus className="mr-2 h-4 w-4" />
                  New class
                </Button>
              </DialogTrigger>

              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Create class</DialogTitle>
                  <DialogDescription>
                    Group files, study paths, practice, and Q&A in one learning
                    space.
                  </DialogDescription>
                </DialogHeader>

                <form onSubmit={handleCreateClass} className="space-y-4">
                  <Input
                    placeholder="Class name, e.g. EECS 203"
                    value={className}
                    onChange={(e) => setClassName(e.target.value)}
                  />

                  <Textarea
                    placeholder="Optional description"
                    value={classDescription}
                    onChange={(e) => setClassDescription(e.target.value)}
                  />

                  <Button
                    type="submit"
                    className="w-full bg-[#8C5CF4] text-white hover:bg-[#7D4DE5]"
                  >
                    Create class
                  </Button>
                </form>
              </DialogContent>
            </Dialog>
          )}

          <Separator className="my-4 bg-[#E2DCEA]" />

          <div className="azalea-sidebar-scroll min-h-0 flex-1 overflow-y-auto pr-1">
            {sidebarMode === "study_paths" ? (
              <SidebarHistoryList
                isEmpty={recentLearningItems.length === 0}
                emptyTitle="No study paths or practice yet"
                emptyDescription="Create a study path or start a quick practice session from the prompt."
              >
                {recentLearningItems.map((item) => (
                  <Link
                    key={`${item.type}-${item.id}`}
                    href={item.href}
                    className="group block rounded-2xl px-3 py-2.5 transition hover:bg-white hover:shadow-sm"
                  >
                    <div className="flex items-start gap-2.5">
                      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-xl bg-white/70 text-[#7A6A93] ring-1 ring-[#E3DCEA] group-hover:text-[#7D4DE5]">
                        {item.type === "study_path" ? (
                          <BookOpen className="h-3.5 w-3.5" />
                        ) : (
                          <Dumbbell className="h-3.5 w-3.5" />
                        )}
                      </div>

                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-[#30283D]">
                          {item.title}
                        </p>
                        <p className="mt-0.5 truncate text-xs text-[#817A92]">
                          {item.subtitle}
                        </p>
                      </div>
                    </div>
                  </Link>
                ))}
              </SidebarHistoryList>
            ) : (
              <SidebarHistoryList
                isEmpty={recentClasses.length === 0}
                emptyTitle="No classes yet"
                emptyDescription="Create a class to group materials and paths."
              >
                {recentClasses.map((azaleaClass) => (
                  <Link
                    key={azaleaClass.id}
                    href={`/classes/${azaleaClass.id}`}
                    className="group block rounded-2xl px-3 py-2.5 transition hover:bg-white hover:shadow-sm"
                  >
                    <div className="flex items-start gap-2.5">
                      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-xl bg-white/70 text-[#7A6A93] ring-1 ring-[#E3DCEA] group-hover:text-[#7D4DE5]">
                        <GraduationCap className="h-3.5 w-3.5" />
                      </div>

                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-[#30283D]">
                          {azaleaClass.name}
                        </p>
                        <p className="mt-0.5 truncate text-xs text-[#817A92]">
                          {azaleaClass.description || "No description"}
                        </p>
                      </div>
                    </div>
                  </Link>
                ))}
              </SidebarHistoryList>
            )}
          </div>

          <Separator className="my-4 bg-[#E2DCEA]" />

          <Dialog open={isAttachPathOpen} onOpenChange={setIsAttachPathOpen}>
            <DialogTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="mb-3 w-full justify-start rounded-2xl px-3 text-[#766E85] hover:bg-white hover:text-[#21172F]"
                disabled={!classes.length || !studyPaths.length}
              >
                <MessageSquarePlus className="mr-2 h-4 w-4" />
                Attach path to class
              </Button>
            </DialogTrigger>

            <DialogContent>
              <DialogHeader>
                <DialogTitle>Add study path to class</DialogTitle>
                <DialogDescription>
                  Choose an existing study path and the class it should belong
                  to.
                </DialogDescription>
              </DialogHeader>

              <form onSubmit={handleAttachStudyPath} className="space-y-4">
                <select
                  className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                  value={selectedStudyPathId}
                  onChange={(e) => setSelectedStudyPathId(e.target.value)}
                >
                  <option value="">Choose study path</option>
                  {studyPaths.map((path) => (
                    <option key={path.id} value={path.id}>
                      {path.title}
                    </option>
                  ))}
                </select>

                <select
                  className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                  value={selectedClassId}
                  onChange={(e) => setSelectedClassId(e.target.value)}
                >
                  <option value="">Choose class</option>
                  {classes.map((azaleaClass) => (
                    <option key={azaleaClass.id} value={azaleaClass.id}>
                      {azaleaClass.name}
                    </option>
                  ))}
                </select>

                <Button
                  type="submit"
                  className="w-full"
                  disabled={!selectedClassId || !selectedStudyPathId}
                >
                  Add to class
                </Button>
              </form>
            </DialogContent>
          </Dialog>

          <div className="rounded-2xl border border-[#E0D7EA] bg-white/65 p-3 shadow-sm">
            <p className="truncate text-xs font-semibold text-[#30283D]">
              {userEmail ?? "Logged in"}
            </p>
            <Button
              variant="ghost"
              size="sm"
              className="mt-2 w-full justify-start rounded-xl px-2 text-[#766E85] hover:bg-[#F1E9FF] hover:text-[#21172F]"
              onClick={handleLogout}
            >
              <LogOut className="mr-2 h-4 w-4" />
              Log out
            </Button>
          </div>
        </aside>

        <section className="relative flex h-screen min-w-0 flex-1 flex-col overflow-hidden px-5 py-5 md:px-8">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(155,109,255,0.14),transparent_34%),linear-gradient(180deg,#FAF8FE_0%,#F7F4FB_48%,#F4F0F8_100%)]" />

          <header className="relative z-10 flex items-center justify-between gap-4 lg:hidden">
            <div>
              <BrandLockup size="sm" />
            </div>

            <Button variant="ghost" size="sm" onClick={handleLogout}>
              <LogOut className="mr-2 h-4 w-4" />
              Log out
            </Button>
          </header>

          <div className="relative z-10 mx-auto flex h-full w-full max-w-4xl flex-col justify-center">
            {status && (
              <div className="mb-5 rounded-2xl border border-[#E6E1EC] bg-white/80 px-4 py-3 text-sm text-[#6F6A7D] shadow-sm">
                {status}
              </div>
            )}

            {isLoadingData && (
              <div className="mb-5 rounded-2xl border border-[#E6E1EC] bg-white/80 px-4 py-3 text-sm text-[#6F6A7D] shadow-sm">
                Loading your workspace...
              </div>
            )}

            <div className="mb-6 text-center">
              <h1
                className={`${headlineFont.className} text-4xl font-bold tracking-[-0.035em] text-[#38206F] md:text-6xl`}
              >
                What do you want to learn today?
              </h1>
            </div>

            <form
              id="azalea-home-prompt-form"
              onSubmit={handleCreateFromPrompt}
              className="rounded-[2rem] border border-[#E7E1EF] bg-white/88 p-4 shadow-xl shadow-[#7B61FF]/10 backdrop-blur"
            >
              <Textarea
                value={learningGoal}
                onChange={(e) => setLearningGoal(e.target.value)}
                className="min-h-32 resize-none border-0 bg-transparent p-2 text-base text-[#21172F] shadow-none outline-none placeholder:text-[#8B8698] focus-visible:ring-0"
                placeholder="What do you want to learn, practice, or review?"
              />

              <div className="mt-3 flex flex-col gap-3 rounded-3xl border-t border-[#E9E3F0] bg-[#FBF9FE] px-1 pt-3 md:flex-row md:items-center md:justify-between">
                <div className="flex flex-wrap items-center gap-2">
                  <label className="inline-flex cursor-pointer items-center rounded-full border border-[#E1D9EA] bg-white px-3 py-2 text-sm font-semibold text-[#6F6A7D] transition hover:border-[#D7C3FF] hover:bg-[#F1E9FF] hover:text-[#6F46D9]">
                    <Paperclip className="mr-2 h-4 w-4" />
                    Attach PDF
                    <input
                      type="file"
                      accept="application/pdf"
                      className="hidden"
                      onChange={(e) =>
                        setSelectedPromptPdf(e.target.files?.[0] ?? null)
                      }
                    />
                  </label>

                  {selectedPromptPdf && (
                    <span className="inline-flex max-w-[260px] items-center gap-2 rounded-full border border-[#E1D9EA] bg-white px-3 py-2 text-xs text-[#6F6A7D]">
                      <UploadCloud className="h-3.5 w-3.5 shrink-0 text-[#8C5CF4]" />
                      <span className="truncate">{selectedPromptPdf.name}</span>
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedPromptPdf(null);
                          setShouldAddPromptPathToClass(false);
                        }}
                        className="rounded-full hover:text-[#21172F]"
                        aria-label="Remove selected PDF"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </span>
                  )}

                  {classes.length > 0 && (
                    <select
                      className="h-9 rounded-full border border-[#E1D9EA] bg-white px-3 text-sm font-medium text-[#6F6A7D] outline-none transition hover:border-[#D7C3FF]"
                      value={selectedPromptClassId}
                      onChange={(e) => {
                        setSelectedPromptClassId(e.target.value);
                        if (!e.target.value) {
                          setShouldAddPromptPathToClass(false);
                        }
                      }}
                    >
                      <option value="">Use class context</option>
                      {classes.map((azaleaClass) => (
                        <option key={azaleaClass.id} value={azaleaClass.id}>
                          {azaleaClass.name}
                        </option>
                      ))}
                    </select>
                  )}
                </div>

                <Button
                  type="submit"
                  disabled={!learningGoal.trim() || isPromptSubmitting}
                  className="rounded-full bg-[#9B6DFF] px-5 text-white shadow-md shadow-purple-300/40 hover:bg-[#8C5CF4]"
                >
                  {isPromptSubmitting ? (
                    "Creating..."
                  ) : (
                    <>
                      {getStartButtonLabel(selectedPromptMode, learningGoal)}
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </>
                  )}
                </Button>
              </div>


              {selectedPromptPdf && !selectedPromptClassId && (
                <p className="mt-3 text-xs leading-5 text-[#817A92]">
                  This PDF will be attached to the new study path. Select a class
                  only if you want to store the material inside a class workspace.
                </p>
              )}

              {selectedPromptPdf && selectedPromptClassId && (
                <p className="mt-3 text-xs leading-5 text-[#817A92]">
                  This PDF will be stored in the selected class. Check the box
                  above only if you also want this study path added to that class.
                </p>
              )}
            </form>

            <div className="mx-auto mt-5 grid w-full max-w-4xl gap-2 text-center text-xs text-[#817A92] sm:grid-cols-2 lg:grid-cols-4">
              {promptStarters.map((item) => (
                <button
                  key={`${item.mode}-description`}
                  type="button"
                  onClick={() => applyPromptStarter(item.mode)}
                  className={`rounded-2xl border px-3 py-2 text-left transition ${
                    selectedPromptMode === item.mode
                      ? "border-[#CBB5FF] bg-[#F4EEFF] text-[#5E35C8]"
                      : "border-[#E8E1EF] bg-white/55 hover:border-[#D7C3FF] hover:bg-[#F3ECFF]"
                  }`}
                >
                  <p className="font-semibold text-[#30283D]">{item.label}</p>
                  <p className="mt-1 leading-5">{item.description}</p>
                </button>
              ))}
            </div>

            <Dialog
              open={isPromptIntentDialogOpen}
              onOpenChange={setIsPromptIntentDialogOpen}
            >
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>How should Azalea handle this?</DialogTitle>
                  <DialogDescription>
                    Choose whether this should become a path, a practice set,
                    a guided explanation, or a solve workspace.
                  </DialogDescription>
                </DialogHeader>

                <div className="grid gap-3 md:grid-cols-2">
                  <button
                    type="button"
                    onClick={() => submitPromptWithMode("study_path")}
                    className="rounded-2xl border border-[#E1D9EA] bg-white p-4 text-left transition hover:border-[#D7C3FF] hover:bg-[#F3ECFF]"
                  >
                    <p className="font-semibold text-[#21172F]">
                      Learn
                    </p>
                    <p className="mt-2 text-sm leading-6 text-[#817A92]">
                      Create a study path for a lecture, unit, or learning
                      objective.
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() => submitPromptWithMode("practice")}
                    className="rounded-2xl border border-[#E1D9EA] bg-white p-4 text-left transition hover:border-[#D7C3FF] hover:bg-[#F3ECFF]"
                  >
                    <p className="font-semibold text-[#21172F]">
                      Practice
                    </p>
                    <p className="mt-2 text-sm leading-6 text-[#817A92]">
                      Create a focused question set for a topic or learning
                      objective.
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() => submitPromptWithMode("explain")}
                    className="rounded-2xl border border-[#E1D9EA] bg-white p-4 text-left transition hover:border-[#D7C3FF] hover:bg-[#F3ECFF]"
                  >
                    <p className="font-semibold text-[#21172F]">Explain</p>
                    <p className="mt-2 text-sm leading-6 text-[#817A92]">
                      Turn one individual problem into a short guided solution
                      path.
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() => submitPromptWithMode("solve")}
                    className="rounded-2xl border border-[#E1D9EA] bg-white p-4 text-left transition hover:border-[#D7C3FF] hover:bg-[#F3ECFF]"
                  >
                    <p className="font-semibold text-[#21172F]">Solve</p>
                    <p className="mt-2 text-sm leading-6 text-[#817A92]">
                      Open the pasted problem in the matching coding or math
                      workspace.
                    </p>
                  </button>
                </div>
              </DialogContent>
            </Dialog>

          </div>
        </section>
      </div>
    </main>
  );
}

function SidebarHistoryList({
  children,
  emptyTitle,
  emptyDescription,
  isEmpty,
}: {
  children: React.ReactNode;
  emptyTitle: string;
  emptyDescription: string;
  isEmpty?: boolean;
}) {
  const hasChildren =
    Array.isArray(children) ? children.length > 0 : Boolean(children);

  if (isEmpty ?? !hasChildren) {
    return (
      <div className="rounded-2xl border border-dashed border-[#D9D0E5] bg-white/45 p-4">
        <p className="text-sm font-semibold text-[#30283D]">{emptyTitle}</p>
        <p className="mt-1 text-xs leading-5 text-[#817A92]">
          {emptyDescription}
        </p>
      </div>
    );
  }

  return <div className="space-y-1">{children}</div>;
}


function HomeSkeleton() {
  return (
    <main className="h-screen overflow-hidden bg-[#F7F4FB] px-6 py-10">
      <div className="mx-auto max-w-4xl space-y-6 pt-[12vh]">
        <div className="mx-auto space-y-3 text-center">
          <Skeleton className="mx-auto h-7 w-60" />
          <Skeleton className="mx-auto h-12 w-96 max-w-full" />
          <Skeleton className="mx-auto h-5 w-[32rem] max-w-full" />
        </div>

        <Skeleton className="h-52 rounded-3xl" />

        <div className="grid gap-3 md:grid-cols-2">
          <Skeleton className="h-24 rounded-2xl" />
          <Skeleton className="h-24 rounded-2xl" />
        </div>
      </div>
    </main>
  );
}
