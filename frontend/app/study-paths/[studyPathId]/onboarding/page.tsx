"use client";

// Phase-1 onboarding wizard (ONBOARDING_AND_PREFERENCE_CAPTURE_SPEC §2/§2.1). Sits between the home-page prompt
// and the study-path view: confirm the inferred domain + pick depth, then hand off. Onboarding is NOT a routing
// dependency — Phase 0 already ran on the inferred domain; this only lets the learner override it.
//
// Phase-1 scope: two live steps (Content Type · Preferences/depth). The language question is intentionally
// hidden until the §5 compatibility preflight ships. Feature-flagged upstream (NEXT_PUBLIC_ONBOARDING_WIZARD).

import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { ArrowRight, Check, Sparkles } from "lucide-react";

import {
  getStudyPath,
  getUserPreferences,
  updateStudyPathPreferences,
  type DepthLevel,
  type OverrideDomain,
  type StudyPath,
} from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

const DOMAIN_OPTIONS: { value: OverrideDomain; label: string; blurb: string }[] = [
  { value: "coding", label: "Coding", blurb: "Programming, algorithms, data structures" },
  { value: "math", label: "Math", blurb: "Formulas, proofs, step-by-step solving" },
  { value: "science", label: "Science", blurb: "Mechanisms, laws, natural phenomena" },
  { value: "concept", label: "Concept", blurb: "Ideas, definitions, explanations" },
];

const DEPTH_OPTIONS: { value: DepthLevel; label: string; blurb: string }[] = [
  { value: "intuition", label: "Intuition", blurb: "Just the core idea" },
  { value: "working", label: "Working", blurb: "Enough to apply it" },
  { value: "deep", label: "Deep", blurb: "Edge cases + extra practice" },
];

// Mirror of the backend gate_family_of coarse mapping (fine domain -> the wizard's coarse choice).
function toCoarseDomain(domain?: string | null): OverrideDomain | null {
  if (!domain) return null;
  if (domain === "concept") return "concept";
  if (domain === "coding" || domain === "math" || domain === "science") return domain;
  const groups: Record<OverrideDomain, string[]> = {
    coding: ["coding", "machine_learning"],
    math: ["math", "logic", "statistics"],
    science: ["physics", "chemistry", "biology", "electrical_engineering", "astronomy", "earth_science", "medicine"],
    concept: ["finance", "economics", "humanities", "language_learning", "expository"],
  };
  for (const key of Object.keys(groups) as OverrideDomain[]) {
    if (groups[key].includes(domain)) return key;
  }
  return null; // mixed / unknown — no confident coarse mapping
}

type Step = "domain" | "preferences";

export default function OnboardingWizardPage() {
  const router = useRouter();
  const params = useParams<{ studyPathId: string }>();
  const studyPathId = params.studyPathId;
  const { isCheckingAuth } = useRequireAuth();

  const [path, setPath] = useState<StudyPath | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  // Inferred baseline (from Phase-0 classification) vs. the learner's current selection.
  const [inferredDomain, setInferredDomain] = useState<OverrideDomain | null>(null);
  const [highConfidence, setHighConfidence] = useState(false);
  const [defaultDepthIsSaved, setDefaultDepthIsSaved] = useState(false);

  const [domain, setDomain] = useState<OverrideDomain>("concept");
  const [depth, setDepth] = useState<DepthLevel>("working");

  const [step, setStep] = useState<Step>("domain");
  // Q8: a high-confidence domain + saved prefs shows a single compact confirm instead of the full wizard.
  const [compact, setCompact] = useState(false);

  useEffect(() => {
    if (isCheckingAuth) return;
    let active = true;
    (async () => {
      try {
        const [p, prefs] = await Promise.all([getStudyPath(studyPathId), getUserPreferences()]);
        if (!active) return;
        setPath(p);
        const coarse = toCoarseDomain(p.domain);
        const isHighConfidence = p.classification_status === "classified" && coarse !== null;
        const savedDepth = prefs.default_depth_level;
        const savedExists = savedDepth !== null || prefs.default_language !== null;

        setInferredDomain(coarse);
        setHighConfidence(isHighConfidence);
        setDefaultDepthIsSaved(savedDepth !== null);
        setDomain(coarse ?? "concept");
        setDepth(savedDepth ?? (p.effective_preferences?.depth_level as DepthLevel) ?? "working");
        setCompact(isHighConfidence && savedExists);
      } catch (err) {
        console.error(err);
        if (active) setError("Couldn't load this path. You can continue without setting preferences.");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [isCheckingAuth, studyPathId]);

  const goToPath = () => router.push(`/study-paths/${studyPathId}`);

  async function applyAndContinue() {
    setSubmitting(true);
    setError("");
    try {
      const payload: { domain?: OverrideDomain; depth_level: DepthLevel } = { depth_level: depth };
      // Only send a domain override when the learner actually changed it — an unchanged domain stays inferred
      // (preserves the classifier-quality signal, §8).
      if (domain !== inferredDomain) payload.domain = domain;
      await updateStudyPathPreferences(studyPathId, payload);
      goToPath();
    } catch (err) {
      console.error(err);
      setError("Couldn't save your preferences. Try again, or skip to continue.");
      setSubmitting(false);
    }
  }

  const domainSourceLabel = useMemo(
    () => (highConfidence ? "We detected this from your prompt" : "Best guess — pick what fits"),
    [highConfidence],
  );
  const depthSourceLabel = defaultDepthIsSaved ? "Your usual preference" : "A balanced default";

  if (isCheckingAuth || loading) return <WizardSkeleton />;

  const domainLabel = DOMAIN_OPTIONS.find((d) => d.value === domain)?.label ?? "Concept";
  const depthLabel = DEPTH_OPTIONS.find((d) => d.value === depth)?.label ?? "Working";

  return (
    <main className="min-h-screen bg-[#F7F4FB] text-[#17151F]">
      <div className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center px-5 py-10">
        <div className="mb-5 flex items-center justify-between">
          <span className="inline-flex items-center gap-2 text-sm font-semibold text-[#7D4DE5]">
            <Sparkles className="h-4 w-4" /> Set up your path
          </span>
          <button
            type="button"
            onClick={goToPath}
            className="text-sm text-[#817A92] underline-offset-2 hover:text-[#21172F] hover:underline"
          >
            Exit
          </button>
        </div>

        {!compact && <Stepper step={step} />}

        <div className="rounded-[2rem] border border-[#E7E1EF] bg-white/90 p-6 shadow-xl shadow-[#7B61FF]/10 md:p-8">
          <p className="mb-1 text-sm text-[#817A92]">{path?.title}</p>

          {compact ? (
            <CompactConfirm
              domainLabel={domainLabel}
              depthLabel={depthLabel}
              onConfirm={applyAndContinue}
              onChange={() => setCompact(false)}
              submitting={submitting}
            />
          ) : step === "domain" ? (
            <StepCard
              heading="What kind of topic is this?"
              source={domainSourceLabel}
              options={DOMAIN_OPTIONS}
              selected={domain}
              onSelect={(v) => setDomain(v as OverrideDomain)}
              primaryLabel="Next"
              onPrimary={() => setStep("preferences")}
              onSkip={goToPath}
            />
          ) : (
            <StepCard
              heading="How deep should we go?"
              source={depthSourceLabel}
              options={DEPTH_OPTIONS}
              selected={depth}
              onSelect={(v) => setDepth(v as DepthLevel)}
              primaryLabel={submitting ? "Saving…" : "Start learning"}
              onPrimary={applyAndContinue}
              onBack={() => setStep("domain")}
              onSkip={goToPath}
              primaryDisabled={submitting}
            />
          )}

          {error && <p className="mt-4 text-sm text-[#C2410C]">{error}</p>}

          <p className="mt-5 text-center text-xs text-[#9A93A8]">You can change this later in settings.</p>
        </div>

        {!compact && (
          <RecapRail
            items={[
              { label: "Content type", value: domainLabel },
              ...(step === "preferences" ? [{ label: "Depth", value: depthLabel }] : []),
            ]}
          />
        )}
      </div>
    </main>
  );
}

function Stepper({ step }: { step: Step }) {
  const steps: { id: Step; label: string }[] = [
    { id: "domain", label: "Content Type" },
    { id: "preferences", label: "Preferences" },
  ];
  const activeIndex = steps.findIndex((s) => s.id === step);
  return (
    <div className="mb-4 flex items-center justify-center gap-3">
      {steps.map((s, i) => (
        <div key={s.id} className="flex items-center gap-3">
          <span
            className={`inline-flex items-center gap-2 text-xs font-semibold ${
              i <= activeIndex ? "text-[#7D4DE5]" : "text-[#B4ADC2]"
            }`}
          >
            <span
              className={`flex h-6 w-6 items-center justify-center rounded-full text-[11px] ${
                i < activeIndex
                  ? "bg-[#7D4DE5] text-white"
                  : i === activeIndex
                    ? "bg-[#EEE6FF] text-[#7D4DE5] ring-1 ring-[#CBB5FF]"
                    : "bg-[#EFEAF5] text-[#B4ADC2]"
              }`}
            >
              {i < activeIndex ? <Check className="h-3 w-3" /> : i + 1}
            </span>
            {s.label}
          </span>
          {i < steps.length - 1 && <span className="h-px w-6 bg-[#E2DCEA]" />}
        </div>
      ))}
    </div>
  );
}

function StepCard({
  heading,
  source,
  options,
  selected,
  onSelect,
  primaryLabel,
  onPrimary,
  onBack,
  onSkip,
  primaryDisabled,
}: {
  heading: string;
  source: string;
  options: { value: string; label: string; blurb: string }[];
  selected: string;
  onSelect: (v: string) => void;
  primaryLabel: string;
  onPrimary: () => void;
  onBack?: () => void;
  onSkip: () => void;
  primaryDisabled?: boolean;
}) {
  return (
    <div>
      <h1 className="text-2xl font-bold tracking-[-0.02em] text-[#2B1D45]">{heading}</h1>
      <p className="mt-1 text-sm text-[#817A92]">{source}</p>

      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        {options.map((opt) => {
          const active = opt.value === selected;
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => onSelect(opt.value)}
              aria-pressed={active}
              className={`rounded-2xl border p-4 text-left transition ${
                active
                  ? "border-[#CBB5FF] bg-[#F4EEFF] ring-2 ring-[#9B6DFF]/40"
                  : "border-[#E8E1EF] bg-white hover:border-[#D7C3FF] hover:bg-[#FAF6FF]"
              }`}
            >
              <div className="flex items-center justify-between">
                <p className="font-semibold text-[#30283D]">{opt.label}</p>
                {active && <Check className="h-4 w-4 text-[#7D4DE5]" />}
              </div>
              <p className="mt-1 text-sm leading-5 text-[#817A92]">{opt.blurb}</p>
            </button>
          );
        })}
      </div>

      <div className="mt-6 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          {onBack && (
            <Button variant="ghost" onClick={onBack} className="text-[#766E85]">
              Back
            </Button>
          )}
          <Button variant="ghost" onClick={onSkip} className="text-[#766E85]">
            Skip
          </Button>
        </div>
        <Button
          onClick={onPrimary}
          disabled={primaryDisabled}
          className="rounded-full bg-[#9B6DFF] px-5 text-white shadow-md shadow-purple-300/40 hover:bg-[#8C5CF4]"
        >
          {primaryLabel}
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

function CompactConfirm({
  domainLabel,
  depthLabel,
  onConfirm,
  onChange,
  submitting,
}: {
  domainLabel: string;
  depthLabel: string;
  onConfirm: () => void;
  onChange: () => void;
  submitting: boolean;
}) {
  return (
    <div>
      <h1 className="text-2xl font-bold tracking-[-0.02em] text-[#2B1D45]">Ready to generate</h1>
      <p className="mt-2 text-[#4A4358]">
        Generating as{" "}
        <span className="font-semibold text-[#7D4DE5]">{domainLabel}</span> ·{" "}
        <span className="font-semibold text-[#7D4DE5]">{depthLabel} depth</span>.
      </p>
      <div className="mt-6 flex items-center justify-between gap-3">
        <Button variant="ghost" onClick={onChange} className="text-[#766E85]">
          Change
        </Button>
        <Button
          onClick={onConfirm}
          disabled={submitting}
          className="rounded-full bg-[#9B6DFF] px-5 text-white shadow-md shadow-purple-300/40 hover:bg-[#8C5CF4]"
        >
          {submitting ? "Saving…" : "Looks good"}
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

function RecapRail({ items }: { items: { label: string; value: string }[] }) {
  return (
    <div className="mt-4 flex flex-wrap items-center justify-center gap-2 text-xs text-[#817A92]">
      <span className="font-semibold">You selected:</span>
      {items.map((it) => (
        <span
          key={it.label}
          className="rounded-full border border-[#E8E1EF] bg-white px-3 py-1 text-[#5E35C8]"
        >
          {it.label}: <span className="font-semibold">{it.value}</span>
        </span>
      ))}
    </div>
  );
}

function WizardSkeleton() {
  return (
    <main className="min-h-screen bg-[#F7F4FB] px-5 py-10">
      <div className="mx-auto max-w-2xl space-y-5 pt-[10vh]">
        <Skeleton className="mx-auto h-6 w-48" />
        <Skeleton className="h-72 rounded-[2rem]" />
      </div>
    </main>
  );
}
