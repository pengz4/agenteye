import { useEffect, useState } from "react";
import { fetchControlPlane, startCoach } from "../api";
import type { RuntimeCard } from "../types";


interface RuntimeOverviewProps {
  runtimes?: RuntimeCard[];
  compact?: boolean;
}

const STATUS_LABEL: Record<string, string> = {
  reachable: "Connected",
  healthy: "Verified",
  installed: "Installed",
  configured: "Configured",
  degraded: "Degraded",
  unhealthy: "Unhealthy",
  connected: "Connected",
  configured_unverified: "Needs verification",
  connection_failed: "Not reachable",
  needs_dependencies: "Needs setup",
  not_configured: "Not configured",
  invalid: "Invalid",
};

export default function RuntimeOverview({
  runtimes: supplied,
  compact = false,
}: RuntimeOverviewProps) {
  const [runtimes, setRuntimes] = useState<RuntimeCard[]>(supplied ?? []);
  const [startingCoach, setStartingCoach] = useState(false);
  const [error, setError] = useState("");
  const [readyCoachUrl, setReadyCoachUrl] = useState("");

  useEffect(() => {
    if (supplied) return;
    let active = true;
    fetchControlPlane()
      .then((result) => {
        if (active) setRuntimes(result.runtimes);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [supplied]);

  if (runtimes.length === 0) return null;

  const statusTone = (status: string) => {
    if (status === "reachable" || status === "connected" || status === "healthy") return "ok";
    if (
      status === "installed"
      || status === "configured"
      || status === "configured_unverified"
      || status === "degraded"
    ) {
      return "warn";
    }
    if (
      status === "connection_failed"
      || status === "invalid"
      || status === "invalid_configuration"
      || status === "needs_dependencies"
      || status === "unhealthy"
    ) {
      return "fail";
    }
    return "neutral";
  };

  const openRuntime = async (runtime: RuntimeCard) => {
    if (!runtime.url) return;
    if (runtime.name !== "AI Coach") {
      window.open(runtime.url, "_blank");
      return;
    }

    const target = window.open("about:blank", "_blank");
    setStartingCoach(true);
    setError("");
    setReadyCoachUrl("");
    try {
      const result = await startCoach();
      setRuntimes((current) => current.map((item) => (
        item.name === "AI Coach"
          ? { ...item, status: result.status, url: result.url, detail: "Dashboard reachable" }
          : item
      )));
      if (target) target.location.href = result.url;
      else setReadyCoachUrl(result.url);
    } catch (caught) {
      target?.close();
      setError(caught instanceof Error ? caught.message : "AI Coach could not start");
    } finally {
      setStartingCoach(false);
    }
  };

  if (compact) {
    return (
      <section className="workspace-runtime-status">
        <div className="workspace-runtime-heading">
          <h2>Runtimes</h2>
          <span>{runtimes.length}</span>
        </div>
        <div className="workspace-runtime-list">
          {runtimes.map((runtime) => {
            const label = STATUS_LABEL[runtime.status]
              ?? runtime.status.replace(/_/g, " ");
            return (
              <div className="workspace-runtime-row" key={runtime.name}>
                <span
                  className={`workspace-runtime-dot ${statusTone(runtime.status)}`}
                  role="img"
                  aria-label={`${runtime.name} status: ${label}`}
                  title={runtime.detail}
                />
                <span className="workspace-runtime-name">
                  {runtime.name}
                  <span className="sr-only"> — {label}</span>
                </span>
                {runtime.url && (
                  <button
                    type="button"
                    className="workspace-runtime-open"
                    aria-label={`Open ${runtime.name}`}
                    disabled={runtime.name === "AI Coach" && startingCoach}
                    onClick={() => openRuntime(runtime)}
                  >
                    {runtime.name === "AI Coach" && startingCoach ? "…" : "Open"}
                  </button>
                )}
              </div>
            );
          })}
        </div>
        {error && <div className="workspace-runtime-error" role="alert">{error}</div>}
        {readyCoachUrl && (
          <a
            className="workspace-runtime-ready"
            href={readyCoachUrl}
            target="_blank"
            rel="noreferrer"
            aria-label="Open ready AI Coach"
          >
            AI Coach is ready — open
          </a>
        )}
      </section>
    );
  }

  return (
    <section style={{ marginBottom: 16 }}>
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        marginBottom: 8,
      }}>
        <h2 style={{ margin: 0, fontSize: 16 }}>Personal Agent Runtime</h2>
        <span style={{ color: "var(--muted)", fontSize: 12 }}>
          Control plane overview
        </span>
      </div>
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
        gap: 10,
      }}>
        {runtimes.map((runtime) => (
          <article
            key={runtime.name}
            className="session-card"
            style={{ padding: 12, border: "1px solid var(--border)", borderRadius: 8 }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
              <strong>{runtime.name}</strong>
              <span className={`state-badge state-${runtime.status}`}>
                {STATUS_LABEL[runtime.status] ?? runtime.status.replace(/_/g, " ")}
              </span>
            </div>
            <div style={{ color: "var(--text-secondary)", fontSize: 12, marginTop: 7 }}>
              {runtime.detail}
            </div>
            {runtime.url && (
              <button
                className="view-btn"
                style={{ marginTop: 10 }}
                aria-label={`Open ${runtime.name}`}
                onClick={() => openRuntime(runtime)}
              >
                Open
              </button>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
