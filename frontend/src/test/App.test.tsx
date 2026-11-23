import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import App from "../components/App";

describe("App", () => {
  it("renders the dashboard header", () => {
    render(<App />);
    expect(screen.getByText("Agent Eye")).toBeInTheDocument();
  });

  it("shows the personal AgentEye build version", async () => {
    window.__DASHBOARD_TOKEN__ = "test-token";
    const fetchMock = vi.fn((url: string) => {
      let payload: unknown = {};
      if (String(url).includes("/api/version")) {
        payload = {
          current: "1.3.0",
          personal: "1.3.0-personal.8",
          latest: null,
          update_available: false,
        };
      } else if (String(url).includes("/api/control-plane")) {
        payload = { runtimes: [] };
      } else if (
        String(url).includes("/api/sessions")
        || String(url).includes("/api/remote-sessions")
      ) {
        payload = [];
      } else if (String(url).includes("/api/processes")) {
        payload = {};
      } else if (String(url).includes("/api/tasks/sync")) {
        payload = {
          tasks: [],
          reconciled: 0,
          obsidian_synced: 0,
          obsidian_status: "connected",
          achievement_linked: 0,
          coach_staged: 0,
        };
      } else if (String(url).includes("/api/server-info")) {
        payload = { pid: 1, port: "5112", sync_folder: null, log_file: "", log_level: "INFO" };
      } else if (String(url).includes("/api/settings")) {
        payload = {
          sync_enabled: false,
          log_level: "INFO",
          mtime_active_threshold: 120,
        };
      } else if (String(url).includes("/api/autostart")) {
        payload = { supported: false, enabled: false };
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        statusText: "OK",
        json: () => Promise.resolve(payload),
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText("v1.3.0-personal.8")).toBeInTheDocument();
    });
    vi.unstubAllGlobals();
  });

  it("shows the Active tab by default", () => {
    render(<App />);
    expect(
      within(screen.getByRole("navigation", { name: "Workspace navigation" }))
        .getByRole("button", { name: /Active/ }),
    ).toHaveAttribute("aria-current", "page");
  });

  it("uses a focused workspace sidebar and page heading", () => {
    render(<App />);
    const navigation = screen.getByRole("navigation", {
      name: "Workspace navigation",
    });
    expect(within(navigation).getByRole("button", { name: /Task Review/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Active sessions" })).toBeInTheDocument();
  });

  it("removes session search and widgets from Task Review", () => {
    render(<App />);
    fireEvent.click(
      screen.getByRole("navigation", { name: "Workspace navigation" })
        .querySelector('[data-tab="tasks"]') as HTMLElement,
    );
    expect(screen.getByRole("heading", { name: "Task Review" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Notifications/ }),
    ).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/Filter sessions/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Stats/ })).not.toBeInTheDocument();
  });
});
