import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import MemoryWorkbench from "../components/MemoryWorkbench";
import ObsidianWorkbench from "../components/ObsidianWorkbench";


describe("MemoryWorkbench", () => {
  it("shows health counts sync and safe recent activity", () => {
    render(
      <MemoryWorkbench
        overview={{
          status: "configured",
          runtime_installed: true,
          account_id: "pengz4",
          device: "company",
          counts: {
            profile: 26,
            workflow: 10,
            "career-evidence": 146,
            total: 184,
            archived: 5,
          },
          sync: {
            last_outcome: "synced",
            queue_count: 0,
            last_attempt_at: "2026-11-23T08:00:00Z",
            last_successful_pull_at: "2026-11-23T08:00:00Z",
            last_successful_push_at: "2026-11-23T08:00:00Z",
          },
          today_captures: 2,
          recent_entries: [
            {
              id: "1",
              kind: "workflow",
              title: "AgentEye task review",
              updated_at: "2026-11-23T08:00:00Z",
            },
          ],
          recent_activity: [
            {
              timestamp: "2026-11-23T09:00:00Z",
              summary: "Persist AgentEye workflow",
              action: "auto-write",
              trigger: "task-outcome",
            },
          ],
        }}
      />,
    );

    expect(screen.getByText("Memory Health")).toBeInTheDocument();
    expect(screen.getByText("Career Evidence")).toBeInTheDocument();
    expect(screen.getByText(/Archived memories/)).toBeInTheDocument();
    expect(screen.queryByText("Archived", { selector: ".workbench-row span" })).not.toBeInTheDocument();
    expect(screen.getByText("Persist AgentEye workflow")).toBeInTheDocument();
    expect(screen.queryByText(/PRIVATE BODY/)).not.toBeInTheDocument();
  });
});


describe("ObsidianWorkbench", () => {
  it("shows Vault Git task achievement state and opens note links", () => {
    const open = vi.fn();
    const retry = vi.fn();
    vi.stubGlobal("open", open);
    render(
      <ObsidianWorkbench
        overview={{
          status: "connected",
          vault_connected: true,
          git: {
            branch: "main",
            dirty_count: 2,
            last_commit: "vault backup",
            last_commit_at: "2026-11-23T08:00:00Z",
            status: "configured",
          },
          today: {
            date: "2026-11-23",
            daily_note_exists: true,
            daily_note_name: "2026-11-23.md",
          },
          tasks: { total: 8, active: 2, review: 3, completed: 5, cross_day: 1 },
          achievements: {
            candidate: 2,
            pending_intake: 1,
            queued_intake: 1,
            linked: 4,
            skipped: 1,
          },
          recent_notes: [
            {
              name: "task-dashboard",
              relative_path: "AgentEye/Tasks/task-dashboard.md",
              updated_at: "2026-11-23T08:00:00Z",
              open_url: "obsidian://open?vault=Obsidian%20Vault&file=AgentEye%2FTasks%2Ftask-dashboard",
            },
          ],
          links: {
            vault: "obsidian://open?vault=Obsidian%20Vault",
            daily_note: "obsidian://open?vault=Obsidian%20Vault&file=_Daily%20Notes%2F2026-11-23",
            achievements: "obsidian://open?vault=Obsidian%20Vault&file=Achievements",
          },
        }}
        onRetrySync={retry}
      />,
    );

    expect(screen.getByText("Obsidian Health")).toBeInTheDocument();
    expect(screen.getByText("Dirty files")).toBeInTheDocument();
    expect(screen.getByText("Queued for intake")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Open today note" }));
    expect(open).toHaveBeenCalledWith(
      expect.stringContaining("2026-11-23"),
      "_blank",
    );
    fireEvent.click(screen.getByRole("button", { name: "Retry task sync" }));
    expect(retry).toHaveBeenCalled();
    vi.unstubAllGlobals();
  });

  it("polls a refreshing Git summary without holding the page in loading state", async () => {
    const base = {
      status: "connected",
      vault_connected: true,
      git: {
        branch: "",
        dirty_count: 0,
        last_commit: "",
        last_commit_at: "",
        status: "refreshing",
      },
      today: {
        date: "2026-11-23",
        daily_note_exists: true,
        daily_note_name: "2026-11-23.md",
      },
      tasks: { total: 1, active: 0, review: 1, completed: 0, cross_day: 0 },
      achievements: {
        candidate: 0,
        pending_intake: 0,
        queued_intake: 0,
        linked: 0,
        skipped: 0,
      },
      recent_notes: [],
      links: { vault: "obsidian://open?vault=Obsidian%20Vault" },
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      json: () => Promise.resolve({
        ...base,
        git: {
          ...base.git,
          branch: "main",
          dirty_count: 2,
          last_commit: "abc1234",
          status: "configured",
        },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<ObsidianWorkbench overview={base} />);

    expect(screen.queryByText("Loading Obsidian…")).not.toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1), { timeout: 2500 });
    expect(await screen.findByText("main")).toBeInTheDocument();
    vi.unstubAllGlobals();
  });
});
