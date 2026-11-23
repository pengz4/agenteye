import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import RuntimeOverview from "../components/RuntimeOverview";


describe("RuntimeOverview", () => {
  it("shows runtime statuses and safe dashboard links", async () => {
    const target = { location: { href: "" }, close: vi.fn() };
    const open = vi.fn(() => target);
    vi.stubGlobal("open", open);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      json: () => Promise.resolve({
        started: false,
        status: "reachable",
        url: "http://127.0.0.1:8765/",
      }),
    }));
    render(
      <RuntimeOverview
        runtimes={[
          {
            name: "Agent Eye",
            status: "reachable",
            detail: "Current dashboard · v1.3.0",
            url: "http://127.0.0.1:5112/",
          },
          {
            name: "AI Coach",
            status: "reachable",
            detail: "Dashboard reachable",
            url: "http://127.0.0.1:8765/",
          },
          {
            name: "Personal Memory",
            status: "healthy",
            detail: "Runtime present",
            url: null,
          },
        ]}
      />,
    );

    expect(screen.getByText("Personal Agent Runtime")).toBeInTheDocument();
    expect(screen.getByText("Agent Eye")).toBeInTheDocument();
    expect(screen.getByText("Personal Memory")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Open AI Coach" }));
    await waitFor(() => {
      expect(target.location.href).toBe("http://127.0.0.1:8765/");
    });
    vi.unstubAllGlobals();
  });

  it("renders compact sidebar statuses and starts an offline AI Coach before opening", async () => {
    const target = { location: { href: "" }, close: vi.fn() };
    vi.stubGlobal("open", vi.fn(() => target));
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      json: () => Promise.resolve({
        started: true,
        status: "reachable",
        url: "http://127.0.0.1:8765/",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <RuntimeOverview
        compact
        runtimes={[
          {
            name: "Agent Eye",
            status: "reachable",
            detail: "Current dashboard",
            url: "http://127.0.0.1:5112/",
          },
          {
            name: "AI Coach",
            status: "connection_failed",
            detail: "Runtime installed, but the dashboard is not reachable",
            url: "http://127.0.0.1:8765/",
          },
          {
            name: "Obsidian",
            status: "connected",
            detail: "Vault detected",
            url: null,
          },
        ]}
      />,
    );

    expect(screen.getByRole("heading", { name: "Runtimes" })).toBeInTheDocument();
    expect(screen.getByLabelText("Agent Eye status: Connected")).toHaveClass(
      "workspace-runtime-dot ok",
    );
    fireEvent.click(screen.getByRole("button", { name: "Open AI Coach" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/coach/start?token=test-token",
      { method: "POST" },
    ));
    await waitFor(() => {
      expect(target.location.href).toBe("http://127.0.0.1:8765/");
      expect(target.close).not.toHaveBeenCalled();
    });
    vi.unstubAllGlobals();
  });

  it("rechecks AI Coach readiness even when its cached status is reachable", async () => {
    const target = { location: { href: "" }, close: vi.fn() };
    vi.stubGlobal("open", vi.fn(() => target));
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      json: () => Promise.resolve({
        started: true,
        status: "reachable",
        url: "http://127.0.0.1:8765/",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <RuntimeOverview
        compact
        runtimes={[{
          name: "AI Coach",
          status: "reachable",
          detail: "Last known connected",
          url: "http://127.0.0.1:8765/",
        }]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Open AI Coach" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/coach/start?token=test-token",
      { method: "POST" },
    ));
    await waitFor(() => expect(target.location.href).toBe("http://127.0.0.1:8765/"));
    vi.unstubAllGlobals();
  });

  it("keeps AgentEye open when a popup is blocked", async () => {
    const assign = vi.fn();
    vi.stubGlobal("open", vi.fn(() => null));
    vi.stubGlobal("location", { assign });
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      json: () => Promise.resolve({
        started: false,
        status: "reachable",
        url: "http://127.0.0.1:8765/",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <RuntimeOverview
        compact
        runtimes={[{
          name: "AI Coach",
          status: "reachable",
          detail: "Dashboard reachable",
          url: "http://127.0.0.1:8765/",
        }]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Open AI Coach" }));
    await screen.findByRole("link", { name: "Open ready AI Coach" });
    expect(assign).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });
});
