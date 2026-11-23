import { useCallback, useEffect, useState } from "react";
import {
  confirmTask,
  mergeTasks,
  requestAchievementReview,
  requestCoachPractice,
  reopenTask,
  skipAchievement,
  splitTask,
  syncTasks,
} from "../api";
import type { AgentTask } from "../types";
import { showToast } from "../components/Toast";


const TASK_POLL_MS = 5000;

export function useTasks() {
  const [tasks, setTasks] = useState<AgentTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const result = await syncTasks();
      setTasks(result.tasks);
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

  const runAction = useCallback(async (action: () => Promise<AgentTask>, success: string) => {
    try {
      await action();
      await refresh();
      showToast(success, "success");
    } catch {
      showToast("Task update failed", "error");
    }
  }, [refresh]);

  return {
    tasks,
    refresh,
    loading,
    error,
    reviewCount: tasks.filter((task) =>
      task.status === "awaiting_confirmation" ||
      task.status === "blocked" ||
      (task.status === "completed" && task.achievement_status === "candidate") ||
      task.coach_status === "needs_confirmation"
    ).length,
    confirm: (id: string) => runAction(() => confirmTask(id), "Task confirmed"),
    reopen: (id: string) => runAction(() => reopenTask(id), "Task reopened"),
    split: (id: string, title: string) =>
      runAction(() => splitTask(id, title), "Task split"),
    merge: (targetId: string, sourceId: string) =>
      runAction(() => mergeTasks(targetId, sourceId), "Tasks merged"),
    requestAchievement: (id: string) =>
      runAction(() => requestAchievementReview(id), "Achievement review requested"),
    skipAchievement: (id: string) =>
      runAction(() => skipAchievement(id), "Achievement skipped"),
    requestCoach: (id: string) =>
      runAction(() => requestCoachPractice(id), "Coach practice requested"),
  };
}
