import { useCallback, useRef, useState } from "react";
import { TOOLTIP_DELAY_MS } from "../constants";
import { useNotifications } from "../hooks";
import {
  useAppDispatch,
  useAppState,
  type GroupBy,
  type SortMode,
  type View,
} from "../state";

export default function WorkspaceToolbar() {
  const { currentTab, currentView, groupBy, sortMode } = useAppState();
  const isSessionPage = currentTab === "active" || currentTab === "previous";
  const dispatch = useAppDispatch();
  const { notificationsEnabled, toggle, popoverContent } = useNotifications();
  const [popoverVisible, setPopoverVisible] = useState(false);
  const hintTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showHint = useCallback(() => {
    if (hintTimer.current) clearTimeout(hintTimer.current);
    hintTimer.current = setTimeout(() => setPopoverVisible(true), TOOLTIP_DELAY_MS);
  }, []);
  const hideHint = useCallback(() => {
    if (hintTimer.current) clearTimeout(hintTimer.current);
    setPopoverVisible(false);
  }, []);
  const setView = (view: View) => dispatch({ type: "SET_VIEW", view });

  return (
    <div className="workspace-toolbar" aria-label="Session display controls">
      <div className="notification-control" onMouseEnter={showHint} onMouseLeave={hideHint}>
        <button
          className="view-btn"
          type="button"
          onClick={toggle}
          aria-pressed={notificationsEnabled}
          aria-label={notificationsEnabled ? "Notifications On" : "Notifications Off"}
        >
          {notificationsEnabled ? "🔔 On" : "🔕 Off"}
        </button>
        {popoverVisible && <div className="notif-popover visible">{popoverContent()}</div>}
      </div>

      {isSessionPage && <select
        className="palette-select"
        value={groupBy}
        onChange={(event) => dispatch({
          type: "SET_GROUP_BY",
          groupBy: event.target.value as GroupBy,
        })}
        aria-label="Group sessions by"
      >
        <option value="none">No grouping</option>
        <option value="project">Group by project</option>
        <option value="machine">Group by machine</option>
      </select>}

      {currentTab === "active" && (
        <select
          className="palette-select"
          value={sortMode}
          onChange={(event) => dispatch({
            type: "SET_SORT_MODE",
            sortMode: event.target.value as SortMode,
          })}
          aria-label="Sort running sessions"
        >
          <option value="default">Default order</option>
          <option value="status_changed">Recently changed status</option>
        </select>
      )}

      {isSessionPage && <div className="workspace-view-switch" aria-label="Session view">
        <button
          type="button"
          className={`view-btn ${currentView === "tile" ? "active" : ""}`}
          onClick={() => setView("tile")}
          aria-pressed={currentView === "tile"}
          title="Tile view"
        >
          ▦
        </button>
        <button
          type="button"
          className={`view-btn ${currentView === "list" ? "active" : ""}`}
          onClick={() => setView("list")}
          aria-pressed={currentView === "list"}
          title="List view"
        >
          ☰
        </button>
      </div>}
    </div>
  );
}
