import { useEffect, useState } from "react";
import { fetchMemoryOverview } from "../api";
import type { MemoryOverview } from "../types";


interface MemoryWorkbenchProps {
  overview?: MemoryOverview;
}

function shortKind(kind: string) {
  return kind.replace(/-/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

export default function MemoryWorkbench({ overview: supplied }: MemoryWorkbenchProps) {
  const [overview, setOverview] = useState<MemoryOverview | null>(supplied ?? null);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    try {
      setOverview(await fetchMemoryOverview());
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Memory overview failed");
    }
  };

  useEffect(() => {
    if (supplied) return;
    let active = true;
    fetchMemoryOverview()
      .then((result) => {
        if (active) {
          setOverview(result);
          setError(null);
        }
      })
      .catch((caught) => {
        if (active) {
          setError(caught instanceof Error ? caught.message : "Memory overview failed");
        }
      });
    return () => {
      active = false;
    };
  }, [supplied]);

  if (!overview) {
    return <div className="empty-state" aria-busy={!error}>{error || "Loading Memory…"}</div>;
  }

  const counts = Object.entries(overview.counts).filter(
    ([name]) => name !== "total" && name !== "archived",
  );
  return (
    <section>
      <div className="page-head">
        <div>
          <h2 style={{ margin: 0 }}>Memory Health</h2>
          <p className="subhead">
            {overview.account_id || "No account"} · {overview.device || "no device scope"}
          </p>
        </div>
        <button className="view-btn" onClick={() => void refresh()}>Refresh</button>
      </div>

      {error && <div role="alert" className="empty-state">{error}</div>}
      <div className="workbench-stat-grid">
        <article className="workbench-stat">
          <span>Runtime</span>
          <strong>{overview.runtime_installed ? "Installed" : "Missing"}</strong>
          <small>{overview.status}</small>
        </article>
        <article className="workbench-stat">
          <span>Total memories</span>
          <strong>{overview.counts.total ?? 0}</strong>
          <small>{overview.today_captures} captures today · {overview.counts.archived ?? 0} archived</small>
        </article>
        <article className="workbench-stat">
          <span>Last sync</span>
          <strong>{overview.sync.last_outcome}</strong>
          <small>{overview.sync.last_successful_push_at || overview.sync.last_attempt_at || "No sync yet"}</small>
        </article>
        <article className="workbench-stat">
          <span>Queued / conflicts</span>
          <strong>{overview.sync.queue_count}</strong>
          <small>Archived memories: {overview.counts.archived ?? 0}</small>
        </article>
      </div>

      <div className="workbench-grid">
        <section className="panel">
          <div className="panel-head">
            <div><h3>Memory types</h3><small>Aggregate counts only</small></div>
          </div>
          <div className="workbench-list">
            {counts.length ? counts.map(([kind, count]) => (
              <div className="workbench-row" key={kind}>
                <span>{shortKind(kind)}</span><strong>{count}</strong>
              </div>
            )) : <div className="empty-state">No shared entries detected.</div>}
          </div>
        </section>

        <section className="panel">
          <div className="panel-head">
            <div><h3>Recent entries</h3><small>Titles and metadata only</small></div>
          </div>
          <div className="workbench-list">
            {overview.recent_entries.length ? overview.recent_entries.map((entry) => (
              <div className="workbench-event" key={entry.id}>
                <div><strong>{entry.title}</strong><small>{shortKind(entry.kind)}</small></div>
                <time>{entry.updated_at.slice(0, 10)}</time>
              </div>
            )) : <div className="empty-state">No recent entries.</div>}
          </div>
        </section>

        <section className="panel workbench-wide">
          <div className="panel-head">
            <div><h3>Recent capture activity</h3><small>Safe summaries; no memory body</small></div>
          </div>
          <div className="workbench-list">
            {overview.recent_activity.length ? overview.recent_activity.map((event) => (
              <div className="workbench-event" key={`${event.timestamp}-${event.summary}`}>
                <div><strong>{event.summary}</strong><small>{event.trigger} · {event.action}</small></div>
                <time>{new Date(event.timestamp).toLocaleString()}</time>
              </div>
            )) : <div className="empty-state">No recent capture events.</div>}
          </div>
        </section>
      </div>
    </section>
  );
}
