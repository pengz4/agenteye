import { useEffect, useState } from "react";
import { fetchObsidianOverview } from "../api";
import type { ObsidianOverview } from "../types";


interface ObsidianWorkbenchProps {
  overview?: ObsidianOverview;
  onRetrySync?: () => void;
}

export default function ObsidianWorkbench({
  overview: supplied,
  onRetrySync,
}: ObsidianWorkbenchProps) {
  const [overview, setOverview] = useState<ObsidianOverview | null>(supplied ?? null);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    try {
      setOverview(await fetchObsidianOverview());
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Obsidian overview failed");
    }
  };

  useEffect(() => {
    if (supplied) return;
    let active = true;
    fetchObsidianOverview()
      .then((result) => {
        if (active) {
          setOverview(result);
          setError(null);
        }
      })
      .catch((caught) => {
        if (active) {
          setError(caught instanceof Error ? caught.message : "Obsidian overview failed");
        }
      });
    return () => {
      active = false;
    };
  }, [supplied]);

  if (!overview) {
    return <div className="empty-state" aria-busy={!error}>{error || "Loading Obsidian…"}</div>;
  }

  const open = (url?: string) => {
    if (url) window.open(url, "_blank");
  };

  return (
    <section>
      <div className="page-head">
        <div>
          <h2 style={{ margin: 0 }}>Obsidian Health</h2>
          <p className="subhead">Vault · Git · Task · Achievement synchronization</p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="view-btn" onClick={() => void refresh()}>Refresh</button>
          <button
            className="view-btn"
            aria-label="Retry task sync"
            onClick={() => onRetrySync?.()}
          >
            Retry task sync
          </button>
        </div>
      </div>

      {error && <div role="alert" className="empty-state">{error}</div>}
      <div className="workbench-stat-grid">
        <article className="workbench-stat">
          <span>Vault</span>
          <strong>{overview.vault_connected ? "Connected" : "Missing"}</strong>
          <small>{overview.status}</small>
        </article>
        <article className="workbench-stat">
          <span>Git branch</span>
          <strong>{overview.git.branch || "—"}</strong>
          <small>{overview.git.last_commit || "No commit"}</small>
        </article>
        <article className="workbench-stat">
          <span>Dirty files</span>
          <strong>{overview.git.dirty_count}</strong>
          <small>{overview.git.last_commit_at || "No timestamp"}</small>
        </article>
        <article className="workbench-stat">
          <span>Today note</span>
          <strong>{overview.today.daily_note_exists ? "Ready" : "Missing"}</strong>
          <small>{overview.today.daily_note_name || overview.today.date}</small>
        </article>
      </div>

      <div className="workbench-grid">
        <section className="panel">
          <div className="panel-head">
            <div><h3>Task sync</h3><small>Logical tasks and cross-day links</small></div>
          </div>
          <div className="workbench-list">
            <div className="workbench-row"><span>Total</span><strong>{overview.tasks.total}</strong></div>
            <div className="workbench-row"><span>Active</span><strong>{overview.tasks.active}</strong></div>
            <div className="workbench-row"><span>Needs review</span><strong>{overview.tasks.review}</strong></div>
            <div className="workbench-row"><span>Completed</span><strong>{overview.tasks.completed}</strong></div>
            <div className="workbench-row"><span>Cross-day</span><strong>{overview.tasks.cross_day}</strong></div>
          </div>
        </section>

        <section className="panel">
          <div className="panel-head">
            <div><h3>Achievement handoff</h3><small>Single-writer intake states</small></div>
          </div>
          <div className="workbench-list">
            <div className="workbench-row"><span>Candidate</span><strong>{overview.achievements.candidate}</strong></div>
            <div className="workbench-row"><span>Pending intake</span><strong>{overview.achievements.pending_intake}</strong></div>
            <div className="workbench-row"><span>Linked</span><strong>{overview.achievements.linked}</strong></div>
            <div className="workbench-row"><span>Skipped</span><strong>{overview.achievements.skipped}</strong></div>
          </div>
        </section>

        <section className="panel workbench-wide">
          <div className="panel-head">
            <div><h3>Recent notes</h3><small>Open in Obsidian; AgentEye does not edit note bodies</small></div>
            <div style={{ display: "flex", gap: 8 }}>
              {overview.links.daily_note && (
                <button
                  className="view-btn"
                  aria-label="Open today note"
                  onClick={() => open(overview.links.daily_note)}
                >
                  Open today
                </button>
              )}
              {overview.links.achievements && (
                <button
                  className="view-btn"
                  aria-label="Open achievements"
                  onClick={() => open(overview.links.achievements)}
                >
                  Achievements
                </button>
              )}
            </div>
          </div>
          <div className="workbench-list">
            {overview.recent_notes.length ? overview.recent_notes.map((note) => (
              <button
                className="workbench-event workbench-link"
                key={note.relative_path}
                onClick={() => open(note.open_url)}
              >
                <div><strong>{note.name}</strong><small>{note.relative_path}</small></div>
                <time>{new Date(note.updated_at).toLocaleString()}</time>
              </button>
            )) : <div className="empty-state">No recent managed notes.</div>}
          </div>
        </section>
      </div>
    </section>
  );
}
