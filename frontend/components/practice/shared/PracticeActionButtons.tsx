import { HelpCircle, Lightbulb } from "lucide-react";

type PracticeActionButtonsProps = {
  onHint: () => void;
  onAskClarification: () => void;
  isHintLoading?: boolean;
};

export default function PracticeActionButtons({
  onHint,
  onAskClarification,
  isHintLoading = false,
}: PracticeActionButtonsProps) {
  return (
    <div className="flex items-center gap-2">
      <button
        onClick={onHint}
        disabled={isHintLoading}
        className="inline-flex items-center gap-2 rounded-2xl border border-[#E7E1EF] bg-white/75 px-4 py-2 text-sm font-medium text-zinc-700 shadow-sm hover:bg-[#F3ECFF]"
      >
        <Lightbulb className="h-4 w-4" />
        {isHintLoading ? "Hint..." : "Hint"}
      </button>

      <button
        onClick={onAskClarification}
        className="inline-flex items-center gap-2 rounded-2xl border border-[#E7E1EF] bg-white/75 px-4 py-2 text-sm font-medium text-zinc-700 shadow-sm hover:bg-[#F3ECFF]"
      >
        <HelpCircle className="h-4 w-4" />
        Ask Clarification
      </button>
    </div>
  );
}
