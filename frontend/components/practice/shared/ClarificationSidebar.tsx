import { Send, X } from "lucide-react";
import { useState } from "react";
import type { PracticeQuestion } from "../types";

type ClarificationSidebarProps = {
  isOpen: boolean;
  onClose: () => void;
  question: PracticeQuestion;
};

type Message = {
  role: "user" | "assistant";
  text: string;
};

export default function ClarificationSidebar({
  isOpen,
  onClose,
  question,
}: ClarificationSidebarProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      text: "Ask me anything about this question. I can clarify the wording, context, or topic without giving away the full answer.",
    },
  ]);
  const [input, setInput] = useState("");

  function sendMessage() {
    const trimmed = input.trim();
    if (!trimmed) return;

    setMessages((currentMessages) => [
      ...currentMessages,
      {
        role: "user",
        text: trimmed,
      },
      {
        role: "assistant",
        text: "Clarification placeholder: I would explain what the question is asking and point you toward the right interpretation without solving it directly.",
      },
    ]);

    setInput("");
  }

  return (
    <>
      {isOpen && (
        <button
          aria-label="Close clarification overlay"
          onClick={onClose}
          className="fixed inset-0 z-40 bg-black/10"
        />
      )}

      <aside
        className={`fixed right-0 top-0 z-50 flex h-screen w-[430px] flex-col border-l border-zinc-200 bg-white shadow-2xl transition-transform duration-300 ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex h-20 items-center justify-between border-b border-zinc-200 px-5">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-zinc-400">
              Clarification
            </p>
            <h2 className="text-lg font-semibold text-zinc-950">
              Ask about this question
            </h2>
          </div>

          <button
            onClick={onClose}
            className="rounded-2xl border border-zinc-200 p-2 text-zinc-600 hover:bg-zinc-50"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="border-b border-zinc-200 bg-zinc-50 p-5">
          <p className="text-xs font-medium uppercase tracking-[0.16em] text-zinc-400">
            Context
          </p>

          <p className="mt-2 text-sm font-medium text-zinc-800">
            {question.topic} · {question.skillTarget}
          </p>

          <p className="mt-2 line-clamp-5 text-sm leading-6 text-zinc-600">
            {question.questionText}
          </p>
        </div>

        <div className="flex-1 space-y-3 overflow-y-auto p-5">
          {messages.map((message, index) => (
            <div
              key={`${message.role}-${index}`}
              className={`rounded-2xl px-4 py-3 text-sm leading-6 ${
                message.role === "user"
                  ? "ml-8 bg-violet-600 text-white"
                  : "mr-8 border border-zinc-200 bg-zinc-50 text-zinc-700"
              }`}
            >
              {message.text}
            </div>
          ))}
        </div>

        <div className="border-t border-zinc-200 p-4">
          <div className="flex items-end gap-2 rounded-2xl border border-zinc-200 bg-white p-2 shadow-sm">
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Ask what the question means..."
              className="max-h-32 min-h-10 flex-1 resize-none px-2 py-2 text-sm outline-none placeholder:text-zinc-400"
            />

            <button
              onClick={sendMessage}
              className="rounded-xl bg-violet-600 p-3 text-white hover:bg-violet-500"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}