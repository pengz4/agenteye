import { useCallback, useEffect, useRef, useState } from "react";
import {
  confirmTask,
  fetchTasks,
  mergeTasks,
  requestAchievementReview,
  requestCoachPractice,
  reopenTask,
  skipAchievement,
  splitTask,
} from "../api";
import type { AgentTask } from "../types";
import { showToast } from "../components/Toast";


const TASK_POLL_MS = 5000;

export function useTasks() {
  const [tasks, setTasks] = useState<AgentTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingActions, setPendingActions] = useState<Record<string, string>>({});
  const pendingTaskIds = useRef(new Set<string>());

  const refresh = useCallback(async () => {
    try {
      const nextTasks = await fetchTasks();
      setTasks(nextTasks);
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Task sync failed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), TASK_POLL_MS);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const runAction = useCallback(async (
    id: string,
    label: string,
    action: () => Promise<AgentTask>,
    success: string,
    relatedIds: string[] = [],
  ) => {
    const lockedIds = [...new Set([id, ...relatedIds])];
    if (lockedIds.some((taskId) => pendingTaskIds.current.has(taskId))) return;
    lockedIds.forEach((taskId) => pendingTaskIds.current.add(taskId));
    setPendingActions((current) => ({
      ...current,
      ...Object.fromEntries(lockedIds.map((taskId) => [taskId, label])),
    }));
    try {
      await action();
      await refresh();
      showToast(success, "success");
    } catch (caught) {
      const detail = caught instanceof Error ? `: ${caught.message}` : "";
      showToast(`Task update failed${detail}`, "error");
    } finally {
      lockedIds.forEach((taskId) => pendingTaskIds.current.delete(taskId));
      setPendingActions((current) => {
        const next = { ...current };
        lockedIds.forEach((taskId) => delete next[taskId]);
        return next;
      });
    }
  }, [refresh]);

  return {
    tasks,
    refresh,
    loading,
    error,
    pendingActions,
    reviewCount: tasks.filter((task) =>
      task.status === "awaiting_confirmation" ||
      task.status === "blocked" ||
      (task.status === "completed" && task.achievement_status === "candidate") ||
      task.coach_status === "needs_confirmation"
    ).length,
    confirm: (id: string) =>
      runAction(id, "Confirming…", () => confirmTask(id), "Task confirmed"),
    reopen: (id: string) =>
      runAction(id, "Reopening…", () => reopenTask(id), "Task reopened"),
    split: (id: string, title: string) =>
      runAction(id, "Splitting…", () => splitTask(id, title), "Task split"),
    merge: (targetId: string, sourceId: string) =>
      runAction(
        targetId,
        "Merging…",
        () => mergeTasks(targetId, sourceId),
        "Tasks merged",
        [sourceId],
      ),
    requestAchievement: (id: string) =>
      runAction(
        id,
        "Requesting review…",
        () => requestAchievementReview(id),
        "Achievement review requested",
      ),
    skipAchievement: (id: string) =>
      runAction(id, "Skipping…", () => skipAchievement(id), "Achievement skipped"),
    requestCoach: (id: string) =>
      runAction(
        id,
        "Generating practice…",
        () => requestCoachPractice(id),
        "Coach practice requested",
      ),
  };
}
