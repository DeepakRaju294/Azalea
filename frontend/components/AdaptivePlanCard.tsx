"use client";

import Link from "next/link";

type PlanTask = {
  task_type: string;
  title: string;
  reason: string;
  class_id?: string | null;
  study_path_id?: string | null;
  study_path_title?: string | null;
  topic_id?: string | null;
  topic_title?: string | null;
  concept_name?: string | null;
  estimated_minutes: number;
  priority: number;
  route_mode?: string | null;
};

type Plan = {
  recommended_minutes: number;
  summary: string;
  tasks: PlanTask[];
};

type AdaptivePlanCardProps = {
  plan: Plan | null;
  studyPathId?: string | null;
  classId?: string | null;
  isLoading?: boolean;
  title?: string;
};

export default function AdaptivePlanCard({
  plan,
  studyPathId,
  classId,
  isLoading = false,
  title = "Recommended today",
}: AdaptivePlanCardProps) {
  if (isLoading) {
    return (
      <div className="rounded-3xl border border-border bg-background p-5 shadow-sm">
        <p className="text-sm font-semibold text-foreground">{title}</p>
        <p className="mt-2 text-sm text-muted-foreground">
          Building your adaptive plan...
        </p>
      </div>
    );
  }

  if (!plan || plan.tasks.length === 0) {
    return (
      <div className="rounded-3xl border border-border bg-background p-5 shadow-sm">
        <p className="text-sm font-semibold text-foreground">{title}</p>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          No urgent work is due right now. Continue when you are ready.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-3xl border border-border bg-background p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-foreground">{title}</p>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            {plan.summary}
          </p>
        </div>

        <span className="rounded-full bg-accent px-3 py-1 text-xs font-semibold text-primary">
          {plan.recommended_minutes} min
        </span>
      </div>

      <div className="mt-5 space-y-3">
        {plan.tasks.slice(0, 6).map((task) => (
          <AdaptivePlanTaskRow
            key={`${task.priority}-${task.task_type}-${task.study_path_id ?? studyPathId ?? ""}-${task.topic_id ?? ""}-${task.concept_name ?? ""}`}
            task={task}
            fallbackStudyPathId={studyPathId}
            classId={classId}
          />
        ))}
      </div>
    </div>
  );
}

function AdaptivePlanTaskRow({
  task,
  fallbackStudyPathId,
  classId,
}: {
  task: PlanTask;
  fallbackStudyPathId?: string | null;
  classId?: string | null;
}) {
  const href = getTaskHref(task, fallbackStudyPathId, classId);

  return (
    <Link
      href={href}
      className="block rounded-2xl border border-border bg-muted/30 p-4 transition hover:border-primary/30 hover:bg-accent/50"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-background px-2.5 py-1 text-xs font-semibold text-primary">
              {formatTaskType(task.task_type)}
            </span>

            {task.study_path_title && (
              <span className="text-xs text-muted-foreground">
                {task.study_path_title}
              </span>
            )}

            <span className="text-xs text-muted-foreground">
              Priority {task.priority}
            </span>
          </div>

          <p className="mt-2 text-sm font-semibold text-foreground">
            {task.title}
          </p>

          <p className="mt-1 text-xs leading-5 text-muted-foreground">
            {task.reason}
          </p>
        </div>

        <span className="shrink-0 rounded-full bg-background px-3 py-1 text-xs font-semibold text-primary">
          {task.estimated_minutes} min
        </span>
      </div>
    </Link>
  );
}

function getTaskHref(
  task: PlanTask,
  fallbackStudyPathId?: string | null,
  classId?: string | null
) {
  const studyPathId = task.study_path_id || fallbackStudyPathId;

  if (!studyPathId || !task.topic_id) {
    return classId ? `/classes/${classId}` : "/";
  }

  const classQuery = classId ? `&classId=${classId}` : "";

  if (task.route_mode === "review" && task.concept_name) {
    return `/study-paths/${studyPathId}/learn?topicId=${task.topic_id}&mode=review&concept=${encodeURIComponent(
      task.concept_name
    )}${classQuery}`;
  }

  if (task.route_mode === "practice") {
    return `/study-paths/${studyPathId}/learn?topicId=${task.topic_id}&mode=practice${classQuery}`;
  }

  return `/study-paths/${studyPathId}/learn?topicId=${task.topic_id}${classQuery}`;
}

function formatTaskType(taskType: string) {
  if (taskType === "review") return "Review";
  if (taskType === "fragile_concept_check") return "Review";
  if (taskType === "repair_follow_up") return "Repair";
  if (taskType === "continue_topic") return "Continue";
  if (taskType === "next_topic") return "Learn";
  if (taskType === "transfer_challenge") return "Transfer";

  return taskType.replace(/_/g, " ");
}