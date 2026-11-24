import { useMemo, useState } from "react";
import type { AgentTask } from "../types";
import SessionConversationOverlay from "./SessionConversationOverlay";

interface TaskListProps {
  tasks: AgentTask[];
  pendingActions?: Record<string, string>;
  onConfirm: (id: string) => void;
  onReopen: (id: string) => void;
  onSplit: (id: string, title: string) => void;
  onMerge: (targetId: string, sourceId: string) => void;
  onRequestAchievement?: (id: string) => void;
  onSkipAchievement?: (id: string) => void;
  onRequestCoach?: (id: string) => void;
}

const TASK_STATUS: Record<
  AgentTask["status"],
  { label: string; tone: "review" | "blocked" | "completed" | "active" | "neutral" }
> = {
  active: { label: "Active", tone: "active" },
  awaiting_confirmation: { label: "Needs review", tone: "review" },
  blocked: { label: "Blocked", tone: "blocked" },
  completed: { label: "Completed", tone: "completed" },
  merged: { label: "Merged", tone: "neutral" },
};

const GENERIC_PROMPTS = [
  /^reply\s+exactly\s+ready\.?$/i,
  /^(continue|go ahead|please continue|resume|yes|ok|okay|done)\.?$/i,
  /^(继续|可以|好的|确认|执行|开始|好)[。！!？?]*$/u,
];

function isGenericPrompt(value: string): boolean {
  const normalized = value.trim();
  return GENERIC_PROMPTS.some((pattern) => pattern.test(normalized));
}

function projectName(task: AgentTask): string {
  if (task.repository) return task.repository.split("/").pop() || task.repository;
  return task.cwd.split(/[\\/]/).filter(Boolean).pop() || "Unknown project";
}

function displayTitle(task: AgentTask): string {
  const title = task.title.trim();
  const summary = task.summary?.trim() || "";
  if (title && !isGenericPrompt(title)) return title;
  if (summary && !isGenericPrompt(summary)) return summary;
  return `${projectName(task)} review`;
}

function identityParts(task: AgentTask): string {
  const project = projectName(task);
  const branch = task.branch ? ` · ${task.branch}` : "";
  const rawSessionId = task.session_id.replace(/^(cc:|scout:)/, "");
  const session = task.session_short_id || rawSessionId.slice(0, 6);
  return `${task.source} · ${project}${branch} · session ${session}`;
}

function groupKey(task: AgentTask): string {
  return (task.summary || task.title)
    .trim()
    .replace(/\s+/g, " ")
    .toLocaleLowerCase();
}

function TaskCard({
  task,
  tasks,
  pendingActions = {},
  onConfirm,
  onReopen,
  onSplit,
  onMerge,
  onRequestAchievement,
  onSkipAchievement,
  onRequestCoach,
  onViewSession,
}: TaskListProps & { task: AgentTask; onViewSession: (task: AgentTask) => void }) {
  const pendingLabel = pendingActions[task.id];
  const isPending = Boolean(pendingLabel);
  const status = TASK_STATUS[task.status];
  const mergeOptions = tasks.filter(
    (candidate) =>
      candidate.id !== task.id &&
      candidate.session_id === task.session_id &&
      candidate.status !== "completed",
  );
  const split = () => {
    const title = window.prompt("Title for the new task");
    if (title?.trim()) onSplit(task.id, title.trim());
  };
  const title = displayTitle(task);
  const latestPrompt = task.summary || task.title;

  return (
    <article className="session-card task-review-card">
      <div className="task-review-card-head">
        <div className="task-review-content">
          <div className="task-review-identity">{identityParts(task)}</div>
          <h3>{title}</h3>
          {latestPrompt && (
            <p className="task-review-prompt">
              <span>{isGenericPrompt(latestPrompt) ? "Latest prompt" : "Summary"}</span>
              {latestPrompt}
            </p>
          )}
          <div className="task-review-meta">
            <span>Started {task.start_date}</span>
            <span>Turn {task.last_turn_index + 1}</span>
            <span>Updated {new Date(task.updated_at).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            })}</span>
          </div>
          {task.obsidian_path && (
            <div className="task-review-reference">
              Obsidian: {task.obsidian_path}
            </div>
          )}
          {task.achievement_status === "candidate" && (
            <div className="task-review-note is-warn">
              Achievement intake is evaluating this task automatically
            </div>
          )}
          {task.achievement_status === "linked" && (
            <div className="task-review-note is-success">
              Achievement linked: {task.achievement_ref}
            </div>
          )}
          {task.achievement_status === "pending_intake" && (
            <div className="task-review-note is-warn">Achievement intake pending</div>
          )}
          {task.achievement_status === "skipped" && (
            <div className="task-review-reference">Achievement skipped</div>
          )}
          {task.coach_status === "pending" && (
            <div className="task-review-note is-warn">AI Coach practice pending</div>
          )}
        </div>
        <span
          className={`task-status-pill task-status-${status.tone}`}
          role="status"
          aria-label={`Task status: ${status.label}`}
        >
          <span className="task-status-dot" aria-hidden="true" />
          {status.label}
        </span>
      </div>

      <div className="task-review-actions">
        {isPending && (
          <div
            className="task-pending-status"
            role="status"
            aria-label={`Task action: ${pendingLabel}`}
            aria-live="polite"
          >
            <span className="task-pending-spinner" aria-hidden="true" />
            {pendingLabel}
          </div>
        )}
        <button
          className="view-btn"
          aria-label="View session"
          onClick={() => onViewSession(task)}
        >
          View session
        </button>
        {task.status === "completed" ? (
          <button
            className="view-btn"
            aria-label="Reopen task"
            onClick={() => onReopen(task.id)}
            disabled={isPending}
          >
            {pendingLabel || "Reopen"}
          </button>
        ) : (
          <button
            className="view-btn"
            aria-label={pendingLabel || "Confirm complete"}
            onClick={() => onConfirm(task.id)}
            disabled={isPending}
          >
            {pendingLabel || "Confirm complete"}
          </button>
        )}
        <button
          className="view-btn"
          aria-label="Split into new task"
          onClick={split}
          disabled={isPending}
        >
          Split
        </button>
        {mergeOptions.length > 0 && (
          <select
            className="palette-select"
            aria-label="Merge with task"
            defaultValue=""
            disabled={isPending}
            onChange={(event) => {
              if (event.target.value) onMerge(task.id, event.target.value);
            }}
          >
            <option value="" disabled>Merge with…</option>
            {mergeOptions.map((candidate) => (
              <option key={candidate.id} value={candidate.id}>
                {displayTitle(candidate)}
              </option>
            ))}
          </select>
        )}
        {task.status === "completed" && task.achievement_status === "candidate" && (
          <button
            className="view-btn"
            aria-label="Skip achievement"
            onClick={() => onSkipAchievement?.(task.id)}
            disabled={isPending}
          >
            Skip
          </button>
        )}
        {task.status === "completed" && task.achievement_status === "skipped" && (
          <button
            className="view-btn"
            aria-label="Review achievement again"
            onClick={() => onRequestAchievement?.(task.id)}
            disabled={isPending}
          >
            Review Again
          </button>
        )}
        {task.achievement_status === "linked" &&
          task.coach_status === "needs_confirmation" && (
            <button
              className="view-btn"
              aria-label="Generate coach practice"
              onClick={() => onRequestCoach?.(task.id)}
              disabled={isPending}
            >
              Generate Coach Practice
            </button>
          )}
      </div>
    </article>
  );
}

export default function TaskList(props: TaskListProps) {
  const [query, setQuery] = useState("");
  const [source, setSource] = useState("all");
  const [status, setStatus] = useState("all");
  const [conversationTask, setConversationTask] = useState<AgentTask | null>(null);

  const visible = useMemo(
    () =>
      props.tasks
        .filter((task) =>
          task.status === "awaiting_confirmation" ||
          task.status === "blocked" ||
          task.status === "completed",
        )
        .filter((task) => status === "all" || (status === "pending" ? task.status !== "completed" : task.status === status))
        .filter((task) => source === "all" || task.source === source)
        .filter((task) => {
          const needle = query.trim().toLocaleLowerCase();
          if (!needle) return true;
          return [
            displayTitle(task),
            task.title,
            task.summary,
            task.repository,
            task.branch,
            task.session_id,
            task.cwd,
          ].some((value) => String(value || "").toLocaleLowerCase().includes(needle));
        })
        .sort((a, b) => {
          const aCompleted = a.status === "completed";
          const bCompleted = b.status === "completed";
          if (aCompleted !== bCompleted) return aCompleted ? 1 : -1;
          return aCompleted
            ? a.updated_at.localeCompare(b.updated_at)
            : b.updated_at.localeCompare(a.updated_at);
        }),
    [props.tasks, query, source, status],
  );

  const groups = useMemo(() => {
    const result = new Map<string, AgentTask[]>();
    visible.forEach((task) => {
      const key = `${task.status}:${groupKey(task)}`;
      const existing = result.get(key) || [];
      existing.push(task);
      result.set(key, existing);
    });
    return [...result.values()];
  }, [visible]);

  const availableSources = [...new Set(props.tasks.map((task) => task.source))];

  return (
    <>
      <div className="task-review-toolbar">
        <label className="task-review-search">
          <span>Search reviews</span>
          <input
            type="search"
            aria-label="Search task reviews"
            placeholder="Task, project, branch, or session…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <label>
          <span>Status</span>
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="pending">Pending</option>
            <option value="blocked">Blocked</option>
            <option value="completed">Completed only</option>
            <option value="all">All reviews</option>
          </select>
        </label>
        <label>
          <span>Agent</span>
          <select value={source} onChange={(event) => setSource(event.target.value)}>
            <option value="all">All agents</option>
            {availableSources.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        </label>
        <strong className="task-review-count">{visible.length} of {props.tasks.length}</strong>
      </div>

      {visible.length === 0 ? (
        <div className="empty-state">No tasks need review.</div>
      ) : (
        <div className="task-review-list">
          {groups.map((group) => (
            <section
              className={`task-review-group ${group.length > 1 ? "is-duplicate" : ""}`}
              key={group.map((task) => task.id).join(":")}
            >
              {group.length > 1 && (
                <div className="task-review-group-head">
                  <strong>{group.length} matching reviews</strong>
                  <span>{group[0].summary || group[0].title}</span>
                </div>
              )}
              {group.map((task) => (
                <TaskCard
                  key={task.id}
                  task={task}
                  {...props}
                  onViewSession={setConversationTask}
                />
              ))}
            </section>
          ))}
        </div>
      )}

      {conversationTask && (
        <SessionConversationOverlay
          key={conversationTask.id}
          task={conversationTask}
          title={displayTitle(conversationTask)}
          onClose={() => setConversationTask(null)}
        />
      )}
    </>
  );
}
