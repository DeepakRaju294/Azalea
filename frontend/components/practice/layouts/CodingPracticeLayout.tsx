import { ChevronDown, ChevronUp, Play, Send, Terminal } from "lucide-react";
import { useRef, useState, type ReactNode } from "react";
import type { CodeRunResult, PracticeLayoutProps } from "../types";
import PracticeActionButtons from "../shared/PracticeActionButtons";

export default function CodingPracticeLayout({
  question,
  onHint,
  onRunCode,
  onSubmitAnswer,
  onAskClarification,
  isHintLoading = false,
  isSubmitLoading = false,
}: PracticeLayoutProps) {
  const [language, setLanguage] = useState(question.language || "python");
  const [code, setCode] = useState(
    question.starterCode || defaultStarterCode(question.language || "python")
  );
  const [runResult, setRunResult] = useState<CodeRunResult | null>(null);
  const [output, setOutput] = useState("Run your code to see test results here.");
  const [hint, setHint] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const [isConsoleOpen, setIsConsoleOpen] = useState(false);
  const lineNumberRef = useRef<HTMLDivElement | null>(null);

  async function requestHint() {
    const result = await onHint(code);

    if (result) {
      setHint(result);
    }
  }

  async function runCode() {
    if (!code.trim()) {
      setOutput("Write code before running tests.");
      setIsConsoleOpen(true);
      return;
    }

    if (!onRunCode) {
      setOutput("Code runner is not available for this question yet.");
      setIsConsoleOpen(true);
      return;
    }

    try {
      setIsRunning(true);
      setRunResult(null);
      setIsConsoleOpen(true);
      setOutput("Running visible tests...");
      const result = await onRunCode(code, language, question.testCases || []);

      if (!result) {
        setOutput("No runner result returned.");
        return;
      }

      setRunResult(result);
      setOutput(
        result.error ||
          `${result.passed}/${result.total} tests passed. ${
            result.all_passed ? "Ready to submit." : "Inspect failed cases below."
          }${
            result.hidden_total
              ? ` Hidden: ${result.hidden_passed}/${result.hidden_total}.`
              : ""
          }`
      );
    } finally {
      setIsRunning(false);
    }
  }

  async function submitCode() {
    if (!code.trim()) {
      setOutput("Write code before submitting.");
      setIsConsoleOpen(true);
      return;
    }

    if (!onSubmitAnswer) {
      setOutput("Submit is not available for this practice question yet.");
      setIsConsoleOpen(true);
      return;
    }

    await onSubmitAnswer(code);
  }

  return (
    <section className="grid h-[calc(100vh-80px)] max-h-[calc(100vh-80px)] min-h-0 grid-cols-[38%_62%] gap-4 overflow-hidden bg-[#F5F0FF] p-4">
      <div className="min-h-0 overflow-hidden">
        <aside className="flex h-full min-h-0 flex-col overflow-hidden rounded-3xl border border-violet-200 bg-white/90 text-zinc-900 shadow-xl shadow-violet-200/40">
          <div className="shrink-0 px-5 pt-5">
            <div className="mb-6 flex items-center gap-6 border-b border-violet-100 pb-4 text-sm font-semibold text-zinc-500">
            <span className="text-violet-700">Question</span>
            <span>Solution</span>
            <span>Submissions</span>
            <span>Feedback</span>
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-5">
          <div className="mb-5 flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.18em] text-violet-400">
                Coding Problem
              </p>
              <h2 className="mt-1 text-xl font-semibold text-zinc-950">
                {question.skillTarget}
              </h2>
            </div>

            <PracticeActionButtons
              onHint={requestHint}
              onAskClarification={onAskClarification}
              isHintLoading={isHintLoading}
            />
          </div>

          {hint && (
            <div className="mb-5 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
              {hint}
            </div>
          )}

          {question.scenario && (
            <Section title="Scenario">
              <p>{question.scenario}</p>
            </Section>
          )}

          <Section title="Question">
            <p>{question.questionText}</p>
          </Section>

          {question.examples && question.examples.length > 0 && (
            <Section title="Examples">
              <div className="space-y-3">
                {question.examples.map((example, index) => (
                  <pre
                    key={`${example}-${index}`}
                    className="whitespace-pre-wrap rounded-2xl border border-violet-100 bg-[#FAF7FF] p-4 text-xs leading-5 text-zinc-800"
                  >
                    {example}
                  </pre>
                ))}
              </div>
            </Section>
          )}

          {question.constraints && question.constraints.length > 0 && (
            <Section title="Constraints">
              <ul className="space-y-2">
                {question.constraints.map((constraint) => (
                  <li key={constraint} className="flex gap-2">
                    <span className="text-violet-500">-</span>
                    <span>{constraint}</span>
                  </li>
                ))}
              </ul>
            </Section>
          )}
          </div>
        </aside>
      </div>

      <div
        className={`relative grid h-full min-h-0 max-h-full gap-0 overflow-hidden rounded-3xl border border-violet-200 bg-[#FDFBFF] shadow-xl shadow-violet-200/50 ${
          isConsoleOpen ? "grid-rows-[minmax(0,1fr)_360px]" : "grid-rows-[minmax(0,1fr)_56px]"
        }`}
      >
        {!isConsoleOpen && (
          <button
            type="button"
            onClick={() => setIsConsoleOpen(true)}
            className="absolute bottom-16 left-1/2 z-20 inline-flex -translate-x-1/2 items-center gap-2 rounded-2xl border border-violet-300 bg-white px-4 py-2 text-sm font-bold text-violet-700 shadow-lg shadow-violet-200/70 transition hover:bg-violet-50"
          >
            <ChevronUp className="h-5 w-5" />
            Console / Output
          </button>
        )}

        <section className="flex min-h-0 flex-col overflow-hidden bg-[#FDFBFF]">
          <div className="flex h-14 items-center justify-between border-b border-violet-100 bg-[#F2EAFE] px-5">
            <select
              value={language}
              onChange={(event) => {
                const nextLanguage = event.target.value;
                setLanguage(nextLanguage);
                setCode(defaultStarterCode(nextLanguage));
                setRunResult(null);
                setOutput("Run your code to see test results here.");
                setIsConsoleOpen(false);
              }}
              className="rounded-xl border border-violet-200 bg-white px-3 py-2 text-sm font-semibold text-violet-800 outline-none transition focus:border-violet-400"
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
                onClick={runCode}
                disabled={isRunning}
                className="inline-flex items-center gap-2 rounded-xl border border-violet-200 bg-white px-4 py-2 text-sm font-semibold text-violet-700 transition hover:bg-violet-50 disabled:opacity-60"
              >
                <Play className="h-4 w-4" />
                {isRunning ? "Running..." : "Run Tests"}
              </button>

              <button
                onClick={submitCode}
                disabled={isSubmitLoading}
                className="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-4 py-2 text-sm font-semibold text-white shadow-sm shadow-violet-200 transition hover:bg-violet-500 disabled:opacity-60"
              >
                <Send className="h-4 w-4" />
                {isSubmitLoading ? "Submitting..." : "Submit"}
              </button>
            </div>
          </div>

          <div className="grid min-h-0 flex-1 grid-cols-[56px_1fr] bg-[#FDFBFF]">
            <div
              ref={lineNumberRef}
              className="overflow-hidden select-none border-r border-violet-100 bg-[#F6F0FF] px-3 py-5 text-right font-mono text-sm leading-6 text-violet-400"
            >
              {code.split("\n").map((_, index) => (
                <div key={index}>{index + 1}</div>
              ))}
            </div>
            <textarea
              value={code}
              onChange={(event) => setCode(event.target.value)}
              onScroll={(event) => {
                if (lineNumberRef.current) {
                  lineNumberRef.current.scrollTop = event.currentTarget.scrollTop;
                }
              }}
              spellCheck={false}
              wrap="off"
              className="min-h-0 flex-1 resize-none overflow-auto whitespace-pre bg-[#FDFBFF] p-5 font-mono text-sm leading-6 text-zinc-900 caret-violet-600 outline-none selection:bg-violet-200 selection:text-violet-950 placeholder:text-violet-400/60"
              style={{ scrollbarColor: "#a78bfa #fdfbff" }}
            />
          </div>
        </section>

        <section className="min-h-0 overflow-hidden border-t border-violet-100 bg-[#F2EAFE]">
          <button
            type="button"
            onClick={() => setIsConsoleOpen((open) => !open)}
            className="flex h-14 w-full items-center justify-between px-5 text-left text-sm font-semibold text-violet-800 transition hover:bg-violet-100/70"
          >
            <span className="inline-flex items-center gap-2">
              <Terminal className="h-4 w-4" />
              <span className="rounded-lg bg-white px-3 py-1.5 text-violet-700 shadow-sm shadow-violet-200">
                Console
              </span>
              <span className="text-violet-400">|</span>
              Test Case
              <span className="text-violet-400">|</span>
              Output
            </span>
            <span className="inline-flex items-center gap-3">
              {runResult && (
                <span
                  className={`rounded-full px-3 py-1 text-xs font-semibold ${
                    runResult.all_passed
                      ? "bg-emerald-100 text-emerald-700"
                      : "bg-amber-100 text-amber-700"
                  }`}
                >
                  {runResult.passed}/{runResult.total} passed
                </span>
              )}
              <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-violet-200 bg-white text-violet-700 shadow-sm shadow-violet-200">
                {isConsoleOpen ? (
                  <ChevronDown className="h-6 w-6" />
                ) : (
                  <ChevronUp className="h-6 w-6" />
                )}
              </span>
            </span>
          </button>

          {isConsoleOpen && (
            <div className="h-[calc(100%-56px)] overflow-y-auto border-t border-violet-100 bg-white p-5 font-mono text-xs leading-6 text-zinc-900 selection:bg-violet-200 selection:text-violet-950">
              <pre className="whitespace-pre-wrap">{output}</pre>

              {runResult ? (
                <CodeRunCases result={runResult} />
              ) : question.testCases && question.testCases.length > 0 ? (
                <div className="mt-5 flex flex-wrap gap-3">
                  {question.testCases.map((testCase, index) => (
                    <div
                      key={`${testCase.input}-${index}`}
                      className="min-w-52 rounded-xl border border-violet-100 bg-[#FAF7FF] p-3"
                    >
                      <p className="text-violet-700">Case {index + 1}</p>
                      <p>Input: {testCase.input || "(empty)"}</p>
                      <p>Expected: {testCase.expected}</p>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          )}
        </section>
      </div>
    </section>
  );
}

function CodeRunCases({ result }: { result: CodeRunResult }) {
  return (
    <div className="mt-5 space-y-3">
      {result.cases.map((testCase) => (
        <div
          key={testCase.case_number}
          className={`rounded-xl border p-3 ${
            testCase.passed
              ? "border-emerald-200 bg-emerald-50"
              : "border-rose-200 bg-rose-50"
          }`}
        >
          <div className="mb-2 flex items-center justify-between">
            <p className="text-zinc-600">Case {testCase.case_number}</p>
            <p className={testCase.passed ? "text-emerald-700" : "text-rose-700"}>
              {testCase.passed ? "Passed" : testCase.status}
            </p>
          </div>
          <p className="text-zinc-500">Input</p>
          <pre className="whitespace-pre-wrap">{testCase.input || "(empty)"}</pre>
          <p className="mt-2 text-zinc-500">Expected</p>
          <pre className="whitespace-pre-wrap">{testCase.expected}</pre>
          <p className="mt-2 text-zinc-500">Actual</p>
          <pre className="whitespace-pre-wrap">{testCase.actual || "(no stdout)"}</pre>
          {testCase.stderr && (
            <>
              <p className="mt-2 text-zinc-500">stderr</p>
              <pre className="whitespace-pre-wrap text-rose-700">
                {testCase.stderr}
              </pre>
            </>
          )}
        </div>
      ))}
      {Boolean(result.hidden_total) && (
        <div className="rounded-xl border border-violet-200 bg-violet-50 p-3">
          <p className="text-violet-700">
            Hidden tests: {result.hidden_passed}/{result.hidden_total} passed
          </p>
        </div>
      )}
    </div>
  );
}

function defaultStarterCode(language: string) {
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

function Section({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="mb-6">
      <h3 className="mb-2 text-sm font-semibold text-zinc-950">{title}</h3>
      <div className="text-sm leading-6 text-zinc-700">{children}</div>
    </section>
  );
}
