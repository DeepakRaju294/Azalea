export type PracticeQuestionType =
  | "coding"
  | "coding_environment"
  | "debugging"
  | "debugging_scenario"
  | "math"
  | "math_input"
  | "short_answer"
  | "multiple_choice"
  | "select_all"
  | "visual_labeling"
  | "ordering"
  | "decision_scenario";

export type PracticeQuestion = {
  id: number;
  type: PracticeQuestionType;

  topic: string;
  skillTarget: string;
  difficulty: "Easy" | "Medium" | "Hard";

  questionNumber: number;
  totalQuestions: number;
  streak: number;

  questionText: string;

  scenario?: string;
  examples?: string[];
  constraints?: string[];
  given?: string[];

  choices?: string[];

  starterCode?: string;
  language?: string;
  testCases?: {
    input: string;
    expected: string;
  }[];

  sourceReference?: string;
};

export type CodeRunResult = {
  language: string;
  passed: number;
  total: number;
  all_passed: boolean;
  error?: string | null;
  hidden_passed?: number;
  hidden_total?: number;
  cases: {
    case_number: number;
    input: string;
    expected: string;
    actual: string;
    stderr: string;
    passed: boolean;
    status: string;
  }[];
};

export type PracticeLayoutProps = {
  question: PracticeQuestion;
  onHint: (partialAnswer?: string) => Promise<string | null> | string | null | void;
  onSubmitAnswer?: (answer: string) => Promise<string | null> | string | null | void;
  onRunCode?: (
    code: string,
    language: string,
    testCases: { input: string; expected: string }[]
  ) => Promise<CodeRunResult | null> | CodeRunResult | null | void;
  onAskClarification: () => void;
  isHintLoading?: boolean;
  isSubmitLoading?: boolean;
};
