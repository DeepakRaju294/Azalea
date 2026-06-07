export type FlowResumePhase = "lesson" | "practice" | "qa" | "review";

export type FlowResumeState = {
  studyPathId: string;
  topicId: string;
  topicTitle: string;
  cardIndex: number;
  cardTitle: string;
  totalCards: number;
  phase: FlowResumePhase;
  updatedAt: string;
};

const RESUME_STORAGE_KEY = "azalea.flowResume.v1";

function readResumeMap(): Record<string, FlowResumeState> {
  if (typeof window === "undefined") {
    return {};
  }

  try {
    const raw = window.localStorage.getItem(RESUME_STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function writeResumeMap(map: Record<string, FlowResumeState>) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(RESUME_STORAGE_KEY, JSON.stringify(map));
}

export function getFlowResume(studyPathId: string) {
  return readResumeMap()[studyPathId] ?? null;
}

export function saveFlowResume(state: Omit<FlowResumeState, "updatedAt">) {
  const map = readResumeMap();

  map[state.studyPathId] = {
    ...state,
    updatedAt: new Date().toISOString(),
  };

  writeResumeMap(map);
}

export function clearFlowResume(studyPathId: string) {
  const map = readResumeMap();
  delete map[studyPathId];
  writeResumeMap(map);
}

export function formatResumeTime(updatedAt: string) {
  const timestamp = Date.parse(updatedAt);

  if (Number.isNaN(timestamp)) {
    return "recently";
  }

  const minutesAgo = Math.max(0, Math.round((Date.now() - timestamp) / 60000));

  if (minutesAgo < 1) {
    return "just now";
  }

  if (minutesAgo < 60) {
    return `${minutesAgo} min ago`;
  }

  const hoursAgo = Math.round(minutesAgo / 60);
  return `${hoursAgo} hr ago`;
}
