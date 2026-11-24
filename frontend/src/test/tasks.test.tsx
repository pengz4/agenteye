import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import TaskList from "../components/TaskList";
import type { AgentTask } from "../types";


const task = (overrides: Partial<AgentTask> = {}): AgentTask => ({
  id: "task-1",
  session_id: "session-1",
  source: "copilot",
  title: "Build the dashboard",
  summary: "Add Obsidian synchronization",
  status: "awaiting_confirmation",
  cwd: "/root/project",
  start_date: "2026-11-20",
  last_activity_date: "2026-11-20",
  last_turn_index: 0,
  created_at: "2026-11-20T08:00:00Z",
  updated_at: "2026-11-20T08:10:00Z",
  completed_at: null,
  obsidian_path: "AgentEye/Tasks/task.md",
  merged_into: null,
  achievement_status: "candidate",
  achievement_source_key: "task:task-1",
  achievement_ref: null,
  coach_status: "off",
  ...overrides,
});


describe("TaskList", () => {
  it("shows awaiting confirmation tasks and completes one", () => {
    const confirm = vi.fn();
    render(
      <TaskList
        tasks={[task()]}
        onConfirm={confirm}
        onReopen={vi.fn()}
        onSplit={vi.fn()}
        onMerge={vi.fn()}
      />,
    );

    expect(screen.getByText("Build the dashboard")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Confirm complete" }));
    expect(confirm).toHaveBeenCalledWith("task-1");
  });

  it("shows stable session identity and groups matching prompts", () => {
    const duplicate = {
      ...task({
        id: "task-2",
        session_id: "session-2",
      }),
      repository: "porsche/personal-agent-skills",
      branch: "main",
      session_short_id: "sessio",
    } as AgentTask;
    const first = {
      ...task({
        title: "Reply exactly READY.",
        summary: "Reply exactly READY.",
      }),
      repository: "porsche/personal-agent-skills",
      branch: "main",
      session_short_id: "sessio",
    } as AgentTask;
    const second = {
      ...duplicate,
      title: "Reply exactly READY.",
      summary: "Reply exactly READY.",
    };

    render(
      <TaskList
        tasks={[first, second]}
        onConfirm={vi.fn()}
        onReopen={vi.fn()}
        onSplit={vi.fn()}
        onMerge={vi.fn()}
      />,
    );

    expect(screen.getByText("2 matching reviews")).toBeInTheDocument();
    expect(screen.getAllByText(/personal-agent-skills · main/)).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: "View session" })).toHaveLength(2);
  });

  it("loads session conversation only after the card is expanded", async () => {
    const mockFetch = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          turns: [{
            turn_index: 4,
            user_message: "Fix the task review context",
            assistant_response: "Implemented the session drawer.",
          }],
          has_earlier: true,
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          turns: [{
            turn_index: 3,
            user_message: "Improve the Task Review identity",
            assistant_response: "Added session metadata.",
          }],
          has_earlier: false,
        }),
      });
    vi.stubGlobal("fetch", mockFetch);

    render(
      <TaskList
        tasks={[task()]}
        onConfirm={vi.fn()}
        onReopen={vi.fn()}
        onSplit={vi.fn()}
        onMerge={vi.fn()}
      />,
    );

    expect(mockFetch).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "View session" }));
    expect(await screen.findByRole("dialog", { name: "Session conversation" }))
      .toBeInTheDocument();
    expect(await screen.findByText("Fix the task review context")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Load earlier" }));
    expect(await screen.findByText("Improve the Task Review identity")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Load earlier" })).not.toBeInTheDocument();

    const dialog = screen.getByRole("dialog", { name: "Session conversation" });
    const initialLeft = dialog.style.left;
    fireEvent.pointerDown(screen.getByLabelText("Drag session conversation"), {
      clientX: 100,
      clientY: 100,
      pointerId: 1,
    });
    fireEvent.pointerMove(window, { clientX: 40, clientY: 70 });
    expect(dialog.style.left).not.toBe(initialLeft);

    await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(2));
    vi.unstubAllGlobals();
    const status = screen.getByRole("status", { name: "Task status: Needs review" });
    expect(status).toHaveClass("task-status-review");
  });

  it("shows and disables a task while its action is processing", () => {
    render(
      <TaskList
        tasks={[task()]}
        pendingActions={{ "task-1": "Confirming…" }}
        onConfirm={vi.fn()}
        onReopen={vi.fn()}
        onSplit={vi.fn()}
        onMerge={vi.fn()}
      />,
    );

    const confirm = screen.getByRole("button", { name: "Confirming…" });
    expect(confirm).toBeDisabled();
    expect(screen.getByRole("button", { name: "Split into new task" })).toBeDisabled();
    expect(screen.getByRole("status", { name: "Task action: Confirming…" }))
      .toHaveTextContent("Confirming…");
  });

  it("lets a completed task be reopened", () => {
    const reopen = vi.fn();
    render(
      <TaskList
        tasks={[task({ status: "completed", completed_at: "2026-11-20T09:00:00Z" })]}
        onConfirm={vi.fn()}
        onReopen={reopen}
        onSplit={vi.fn()}
        onMerge={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Reopen task" }));
    expect(reopen).toHaveBeenCalledWith("task-1");
  });

  it("submits a split title", () => {
    const split = vi.fn();
    vi.stubGlobal("prompt", vi.fn().mockReturnValue("Write documentation"));
    render(
      <TaskList
        tasks={[task()]}
        onConfirm={vi.fn()}
        onReopen={vi.fn()}
        onSplit={split}
        onMerge={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Split into new task" }));
    expect(split).toHaveBeenCalledWith("task-1", "Write documentation");
    vi.unstubAllGlobals();
  });

  it("does not retain the previous session while switching conversations", async () => {
    let resolveSecond: (value: {
      ok: boolean;
      status: number;
      json: () => Promise<unknown>;
    }) => void = () => {};
    const secondResponse = new Promise<{
      ok: boolean;
      status: number;
      json: () => Promise<unknown>;
    }>((resolve) => {
      resolveSecond = resolve;
    });
    const mockFetch = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          turns: [{
            turn_index: 0,
            user_message: "First session context",
            assistant_response: "First response",
          }],
          has_earlier: false,
        }),
      })
      .mockReturnValueOnce(secondResponse);
    vi.stubGlobal("fetch", mockFetch);

    render(
      <TaskList
        tasks={[
          task({
            id: "switch-task-1",
            session_id: "switch-session-1",
          }),
          task({
            id: "switch-task-2",
            session_id: "switch-session-2",
            title: "Second task",
            summary: "Second task summary",
          }),
        ]}
        onConfirm={vi.fn()}
        onReopen={vi.fn()}
        onSplit={vi.fn()}
        onMerge={vi.fn()}
      />,
    );

    fireEvent.click(screen.getAllByRole("button", { name: "View session" })[0]);
    expect(await screen.findByText("First session context")).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "View session" })[1]);
    expect(screen.queryByText("First session context")).not.toBeInTheDocument();
    expect(screen.getByText("Loading conversation…")).toBeInTheDocument();

    resolveSecond({
      ok: true,
      status: 200,
      json: () => Promise.resolve({
        turns: [{
          turn_index: 0,
          user_message: "Second session context",
          assistant_response: "Second response",
        }],
        has_earlier: false,
      }),
    });
    expect(await screen.findByText("Second session context")).toBeInTheDocument();
    vi.unstubAllGlobals();
  });

  it("merges another pending task in the same session", () => {
    const merge = vi.fn();
    render(
      <TaskList
        tasks={[task(), task({ id: "task-2", title: "Docs" })]}
        onConfirm={vi.fn()}
        onReopen={vi.fn()}
        onSplit={vi.fn()}
        onMerge={merge}
      />,
    );

    fireEvent.change(screen.getAllByLabelText("Merge with task")[0], {
      target: { value: "task-2" },
    });
    expect(merge).toHaveBeenCalledWith("task-1", "task-2");
  });

  it("shows an empty state", () => {
    render(
      <TaskList
        tasks={[]}
        onConfirm={vi.fn()}
        onReopen={vi.fn()}
        onSplit={vi.fn()}
        onMerge={vi.fn()}
      />,
    );
    expect(screen.getByText(/No tasks need review/)).toBeInTheDocument();
  });

  it("keeps completed tasks after every unfinished task", () => {
    render(
      <TaskList
        tasks={[
          task({
            id: "completed-newest",
            title: "Completed newest",
            status: "completed",
            completed_at: "2026-11-20T12:00:00Z",
            updated_at: "2026-11-20T12:00:00Z",
          }),
          task({
            id: "blocked",
            title: "Blocked older",
            status: "blocked",
            updated_at: "2026-11-20T10:00:00Z",
          }),
          task({
            id: "awaiting",
            title: "Awaiting older",
            status: "awaiting_confirmation",
            updated_at: "2026-11-20T09:00:00Z",
          }),
          task({
            id: "completed-oldest",
            title: "Completed oldest",
            status: "completed",
            completed_at: "2026-11-20T08:00:00Z",
            updated_at: "2026-11-20T08:00:00Z",
          }),
        ]}
        onConfirm={vi.fn()}
        onReopen={vi.fn()}
        onSplit={vi.fn()}
        onMerge={vi.fn()}
      />,
    );

    expect(
      screen.getAllByRole("heading", { level: 3 }).map((heading) => heading.textContent),
    ).toEqual([
      "Blocked older",
      "Awaiting older",
      "Completed oldest",
      "Completed newest",
    ]);
    expect(screen.getAllByText("Completed")).toHaveLength(2);
    expect(screen.getByRole("status", { name: "Task status: Blocked" }))
      .toHaveClass("task-status-blocked");
  });

  it("keeps candidate intake automatic and only offers skip", () => {
    const request = vi.fn();
    render(
      <TaskList
        tasks={[task({ status: "completed" })]}
        onConfirm={vi.fn()}
        onReopen={vi.fn()}
        onSplit={vi.fn()}
        onMerge={vi.fn()}
        onRequestAchievement={request}
      />,
    );

    expect(screen.queryByRole("button", { name: "Request achievement review" }))
      .not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Skip achievement" })).toBeInTheDocument();
    expect(request).not.toHaveBeenCalled();
  });

  it("shows linked achievement and asks before coach generation", () => {
    const coach = vi.fn();
    render(
      <TaskList
        tasks={[task({
          status: "completed",
          achievement_status: "linked",
          achievement_ref: "### 2026-11-20 — Agent workflow",
          coach_status: "needs_confirmation",
        })]}
        onConfirm={vi.fn()}
        onReopen={vi.fn()}
        onSplit={vi.fn()}
        onMerge={vi.fn()}
        onRequestCoach={coach}
      />,
    );

    expect(screen.getByText(/Achievement linked/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Generate coach practice" }));
    expect(coach).toHaveBeenCalledWith("task-1");
  });

  it("allows skipping a candidate and reviewing it again later", () => {
    const review = vi.fn();
    const skip = vi.fn();
    const { rerender } = render(
      <TaskList
        tasks={[task({ status: "completed", achievement_status: "skipped" })]}
        onConfirm={vi.fn()}
        onReopen={vi.fn()}
        onSplit={vi.fn()}
        onMerge={vi.fn()}
        onRequestAchievement={review}
        onSkipAchievement={skip}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Review achievement again" }));
    expect(review).toHaveBeenCalledWith("task-1");

    rerender(
      <TaskList
        tasks={[task({ status: "completed", achievement_status: "candidate" })]}
        onConfirm={vi.fn()}
        onReopen={vi.fn()}
        onSplit={vi.fn()}
        onMerge={vi.fn()}
        onRequestAchievement={review}
        onSkipAchievement={skip}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Skip achievement" }));
    expect(skip).toHaveBeenCalledWith("task-1");
  });
});
