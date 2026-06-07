import { Flame } from "lucide-react";
import type { PracticeQuestion } from "./types";
import BrandLockup from "@/components/BrandLockup";

type PracticeHeaderProps = {
  question: PracticeQuestion;
  onExit?: () => void;
};

export default function PracticeHeader({
  question,
  onExit,
}: PracticeHeaderProps) {
  return (
    <header className="flex h-20 items-center justify-between border-b border-[#E2DCEA] bg-white/78 px-6 text-zinc-950 shadow-sm shadow-purple-100/30 backdrop-blur">
      <div className="flex items-center gap-5">
        <div className="flex items-center gap-5">
          <BrandLockup size="sm" />
          <div className="h-8 w-px bg-zinc-200" />
          <p className="text-sm font-medium text-zinc-600">
            Practice Question
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <HeaderChip label="Topic" value={question.topic} />
        <HeaderChip label="Skill Target" value={question.skillTarget} />

        <div className="rounded-2xl border border-[#E7E1EF] bg-white/75 px-4 py-2 text-sm shadow-sm">
          <span className="text-zinc-500">Difficulty</span>
          <span className="rounded-full bg-[#EEE5FF] px-2 py-0.5 text-xs font-medium text-[#6F46D9]">
            {question.difficulty}
          </span>
        </div>

        <p className="ml-4 whitespace-nowrap text-sm font-medium text-zinc-700">
          Question {question.questionNumber} of {question.totalQuestions}
        </p>

        <div className="rounded-2xl border border-[#E7E1EF] bg-white/75 px-3 py-2 shadow-sm">
          <Flame className="h-5 w-5 text-orange-500" />
          <span className="text-xs font-semibold text-zinc-600">
            {question.streak}
          </span>
        </div>

        <button
          onClick={onExit}
          className="rounded-2xl border border-[#E7E1EF] bg-white/75 px-4 py-2 text-sm font-medium text-zinc-700 shadow-sm hover:bg-[#F3ECFF]"
        >
          Exit
        </button>
      </div>
    </header>
  );
}

function HeaderChip({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl border border-[#E7E1EF] bg-white/75 px-4 py-2 text-sm shadow-sm">
      <span className="text-zinc-500">{label}: </span>
      <span className="font-medium text-zinc-800">{value}</span>
    </div>
  );
}
