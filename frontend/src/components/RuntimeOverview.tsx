import { useEffect, useState } from "react";
import { fetchControlPlane } from "../api";
import type { RuntimeCard } from "../types";


interface RuntimeOverviewProps {
  runtimes?: RuntimeCard[];
}

const STATUS_LABEL: Record<string, string> = {
  reachable: "Connected",
  installed: "Installed",
  configured: "Configured",
  connected: "Connected",
  configured_unverified: "Needs verification",
  connection_failed: "Not reachable",
  needs_dependencies: "Needs setup",
  not_configured: "Not configured",
  invalid: "Invalid",
};

export default function RuntimeOverview({ runtimes: supplied }: RuntimeOverviewProps) {
  const [runtimes, setRuntimes] = useState<RuntimeCard[]>(supplied ?? []);

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
                onClick={() => window.open(runtime.url!, "_blank")}
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
