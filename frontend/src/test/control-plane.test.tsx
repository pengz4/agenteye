import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import RuntimeOverview from "../components/RuntimeOverview";


describe("RuntimeOverview", () => {
  it("shows runtime statuses and safe dashboard links", () => {
    const open = vi.fn();
    vi.stubGlobal("open", open);
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
            status: "installed",
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
    expect(open).toHaveBeenCalledWith("http://127.0.0.1:8765/", "_blank");
    vi.unstubAllGlobals();
  });
});
