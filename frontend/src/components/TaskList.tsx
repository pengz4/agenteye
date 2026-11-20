import type { AgentTask } from "../types";


interface TaskListProps {
  tasks: AgentTask[];
  onConfirm: (id: string) => void;
  onReopen: (id: string) => void;
  onSplit: (id: string, title: string) => void;
  onMerge: (targetId: string, sourceId: string) => void;
  onRequestAchievement?: (id: string) => void;
  onSkipAchievement?: (id: string) => void;
  onRequestCoach?: (id: string) => void;
}

function TaskCard({
  task,
  tasks,
  onConfirm,
  onReopen,
  onSplit,
  onMerge,
  onRequestAchievement,
  onSkipAchievement,
  onRequestCoach,
}: TaskListProps & { task: AgentTask }) {
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

  return (
    <article className="session-card" style={{ padding: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ color: "var(--muted)", fontSize: 12, marginBottom: 6 }}>
            {task.source} · {task.start_date}
          </div>
          <h3 style={{ margin: 0, overflowWrap: "anywhere" }}>{task.title}</h3>
          <p style={{ color: "var(--text-secondary)", margin: "8px 0 0" }}>
            {task.summary}
          </p>
          {task.obsidian_path && (
            <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 8 }}>
              Obsidian: {task.obsidian_path}
            </div>
          )}
          {task.achievement_status === "candidate" && (
            <div style={{ color: "var(--yellow)", fontSize: 12, marginTop: 8 }}>
              Achievement intake is evaluating this task automatically
            </div>
          )}
          {task.achievement_status === "linked" && (
            <div style={{ color: "var(--green)", fontSize: 12, marginTop: 8 }}>
              Achievement linked: {task.achievement_ref}
            </div>
          )}
          {task.achievement_status === "pending_intake" && (
            <div style={{ color: "var(--yellow)", fontSize: 12, marginTop: 8 }}>
              Achievement intake pending
            </div>
          )}
          {task.achievement_status === "skipped" && (
            <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 8 }}>
              Achievement skipped
            </div>
          )}
          {task.coach_status === "pending" && (
            <div style={{ color: "var(--yellow)", fontSize: 12, marginTop: 4 }}>
              AI Coach practice pending
            </div>
          )}
        </div>
        <span
          className={`state-badge state-${task.status}`}
          style={{ height: "fit-content", whiteSpace: "nowrap" }}
        >
          {task.status.replace(/_/g, " ")}
        </span>
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 14 }}>
        {task.status === "completed" ? (
          <button
            className="view-btn"
            aria-label="Reopen task"
            onClick={() => onReopen(task.id)}
          >
            Reopen
          </button>
        ) : (
          <button
            className="view-btn"
            aria-label="Confirm complete"
            onClick={() => onConfirm(task.id)}
          >
            Confirm complete
          </button>
        )}
        <button
          className="view-btn"
          aria-label="Split into new task"
          onClick={split}
        >
          Split
        </button>
        {mergeOptions.length > 0 && (
          <select
            className="palette-select"
            aria-label="Merge with task"
            defaultValue=""
            onChange={(event) => {
              if (event.target.value) onMerge(task.id, event.target.value);
            }}
          >
            <option value="" disabled>Merge with…</option>
            {mergeOptions.map((candidate) => (
              <option key={candidate.id} value={candidate.id}>
                {candidate.title}
              </option>
            ))}
          </select>
        )}
        {task.status === "completed" &&
          task.achievement_status === "candidate" && (
            <>
              <button
                className="view-btn"
                aria-label="Skip achievement"
                onClick={() => onSkipAchievement?.(task.id)}
              >
                Skip
              </button>
            </>
          )}
        {task.status === "completed" &&
          task.achievement_status === "skipped" && (
            <button
              className="view-btn"
              aria-label="Review achievement again"
              onClick={() => onRequestAchievement?.(task.id)}
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
            >
              Generate Coach Practice
            </button>
          )}
      </div>
    </article>
  );
}

export default function TaskList(props: TaskListProps) {
  const visible = props.tasks
    .filter((task) => task.status === "awaiting_confirmation" ||
      task.status === "blocked" ||
      task.status === "completed")
    .sort((a, b) => {
      const aCompleted = a.status === "completed";
      const bCompleted = b.status === "completed";
      if (aCompleted !== bCompleted) return aCompleted ? 1 : -1;
      return aCompleted
        ? a.updated_at.localeCompare(b.updated_at)
        : b.updated_at.localeCompare(a.updated_at);
    });

  if (visible.length === 0) {
    return (
      <div className="empty-state">
        No tasks need review.
      </div>
    );
  }

  return (
    <div className="session-grid">
      {visible.map((task) => (
        <TaskCard key={task.id} task={task} {...props} />
      ))}
    </div>
  );
}
