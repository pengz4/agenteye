/**
 * Root application component — assembles all sub-components into the full
 * dashboard layout and kicks off data-fetching on mount.
 *
 * Layout: Header → StatsRow → TabBar → SearchBar → TabPanels → Tooltip → Disconnect
 */

import { useEffect, useState, useCallback } from "react";
import { AppProvider, useAppState, useAppDispatch } from "../state";
import type { Tab } from "../state";
import { useSessions, useTasks } from "../hooks";
import { fetchServerInfo } from "../api";
import { filterSessions, splitActivePrevious } from "../utils";
import Header from "./Header";
import StatsRow from "./StatsRow";
import SearchBar from "./SearchBar";
import SessionList from "./SessionList";
import SessionGrid from "./SessionGrid";
import Timeline from "./Timeline";
import FilesTab from "./FilesTab";
import DetailModal from "./DetailModal";
import DisconnectOverlay from "./DisconnectOverlay";
import Tooltip from "./Tooltip";
import AutostartPopover from "./AutostartPopover";
import { ToastContainer } from "./Toast";
import TaskList from "./TaskList";
import MemoryWorkbench from "./MemoryWorkbench";
import ObsidianWorkbench from "./ObsidianWorkbench";
import WorkspaceSidebar from "./WorkspaceSidebar";
import WorkspaceToolbar from "./WorkspaceToolbar";

/** Version injected at build time — falls back to "dev" during development. */
const INITIAL_VERSION = "dev";

const PAGE_META: Record<Tab, { title: string; description: string }> = {
  active: {
    title: "Active sessions",
    description: "Follow live Agent work without losing the larger runtime context.",
  },
  previous: {
    title: "Previous sessions",
    description: "Review completed work from the last five days.",
  },
  tasks: {
    title: "Task Review",
    description: "Confirm, reopen, split, or hand off completed logical tasks.",
  },
  memory: {
    title: "Memory",
    description: "Inspect Personal Memory health, recent entries, and sync state.",
  },
  obsidian: {
    title: "Obsidian",
    description: "Review Vault, Daily Note, task, and achievement synchronization.",
  },
  timeline: {
    title: "Timeline",
    description: "Compare recent sessions and activity on one readable timeline.",
  },
  files: {
    title: "Files",
    description: "Find the files most frequently touched across recent sessions.",
  },
};

function Dashboard() {
  const state = useAppState();
  const dispatch = useAppDispatch();
  const { sessions, remoteSessions, processes, currentTab, currentView, searchFilter, widgetsCollapsed } = state;

  // Start polling
  useSessions({
    fullSessionPolling: currentTab === "active" ||
      currentTab === "previous" ||
      currentTab === "timeline" ||
      currentTab === "files",
  });
  const taskState = useTasks();

  // Fetch server PID on mount
  useEffect(() => {
    fetchServerInfo()
      .then((d) => dispatch({ type: "SET_SERVER_PID", pid: d.pid }))
      .catch(() => {});
  }, [dispatch]);

  // Derived data: filter → split active/previous
  const filtered = filterSessions(sessions, searchFilter);
  const { active, previous } = splitActivePrevious(filtered, processes);

  // Waiting count for header badge
  const waitingCount = Object.values(processes).filter(
    (process) => process.state === "waiting",
  ).length;

  // Last updated — based on actual fetch timestamp
  const lastUpdated = state.lastFetchedAt
    ? new Date(state.lastFetchedAt).toLocaleTimeString()
    : "-";

  // Current timestamp for Timeline. Date.now() is inherently impure but required
  // for a live timeline — the value refreshes on every poll-triggered re-render.
  // eslint-disable-next-line react-hooks/purity
  const now = Date.now();
  const isSessionPage = currentTab === "active" || currentTab === "previous";

  // Timeline detail modal (opened from timeline bar clicks)
  const [timelineModal, setTimelineModal] = useState<{
    id: string;
    title: string;
  } | null>(null);
  const handleTimelineDetail = useCallback(
    (id: string, title: string) => setTimelineModal({ id, title }),
    [],
  );

  return (
    <div className="app-shell">
      <WorkspaceSidebar
        activeCount={active.length}
        previousCount={previous.length}
        taskCount={taskState.reviewCount}
        showSessionCounts={
          currentTab === "active" ||
          currentTab === "previous" ||
          currentTab === "timeline" ||
          currentTab === "files"
        }
      />

      <div className="workspace-main">
        <Header
          initialVersion={INITIAL_VERSION}
          lastUpdated={lastUpdated}
          waitingCount={waitingCount}
        />

        <main className="container workspace-content">
          <div className="workspace-page-heading">
            <div>
              <h1>{PAGE_META[currentTab].title}</h1>
              <p>{PAGE_META[currentTab].description}</p>
            </div>
            {currentTab === "active" && (
              <span className="workspace-live-pill">
                <span className="workspace-health-dot" />
                Live monitoring
              </span>
            )}
          </div>

          {currentTab === "active" && !widgetsCollapsed && (
            <StatsRow active={active} processes={processes} />
          )}

          <div className={`workspace-session-tools ${isSessionPage ? "" : "global-controls"}`}>
            {isSessionPage && <SearchBar />}
            <WorkspaceToolbar />
          </div>

          {/* Active panel */}
          <div
            className={`tab-panel ${currentTab === "active" ? "active" : ""}`}
          >
          {currentView === "tile" ? (
            <SessionGrid sessions={active} processes={processes} isActive />
          ) : (
            <SessionList
              sessions={active}
              processes={processes}
              isActive
              panelId="panel-active"
            />
          )}

          {/* Remote Sessions */}
          {remoteSessions.length > 0 && (
            <div className="remote-sessions-section" style={{ marginTop: "2rem" }}>
              <h3 className="remote-sessions-header">🖥️ Remote Sessions ({remoteSessions.length})</h3>
              {currentView === "tile" ? (
                <SessionGrid sessions={remoteSessions} processes={{}} isActive />
              ) : (
                <SessionList
                  sessions={remoteSessions}
                  processes={{}}
                  isActive
                  panelId="panel-remote"
                />
              )}
            </div>
          )}
          </div>

          {/* Previous panel */}
          <div
            className={`tab-panel ${currentTab === "previous" ? "active" : ""}`}
          >
          {currentView === "tile" ? (
            <SessionGrid sessions={previous} processes={processes} isActive={false} />
          ) : (
            <SessionList
              sessions={previous}
              processes={processes}
              isActive={false}
              panelId="panel-previous"
            />
          )}
          </div>

          {/* Task confirmation panel */}
          <div
            className={`tab-panel ${currentTab === "tasks" ? "active" : ""}`}
          >
          {taskState.error && (
            <div role="alert" className="empty-state" style={{ color: "var(--red)" }}>
              Task sync unavailable: {taskState.error}
            </div>
          )}
          <TaskList
            tasks={taskState.tasks}
            pendingActions={taskState.pendingActions}
            onConfirm={taskState.confirm}
            onReopen={taskState.reopen}
            onSplit={taskState.split}
            onMerge={taskState.merge}
            onRequestAchievement={taskState.requestAchievement}
            onSkipAchievement={taskState.skipAchievement}
            onRequestCoach={taskState.requestCoach}
          />
          </div>

          {/* Timeline panel */}
          <div
            className={`tab-panel ${currentTab === "memory" ? "active" : ""}`}
          >
            {currentTab === "memory" && <MemoryWorkbench />}
          </div>

          <div
            className={`tab-panel ${currentTab === "obsidian" ? "active" : ""}`}
          >
            {currentTab === "obsidian" && (
              <ObsidianWorkbench onRetrySync={taskState.refresh} />
            )}
          </div>

          <div
            className={`tab-panel ${currentTab === "timeline" ? "active" : ""}`}
          >
            <Timeline
              sessions={sessions}
              processes={processes}
              now={now}
              onOpenDetail={handleTimelineDetail}
            />
          </div>

          {/* Files panel */}
          <div
            className={`tab-panel ${currentTab === "files" ? "active" : ""}`}
          >
            {currentTab === "files" && <FilesTab />}
          </div>
        </main>
      </div>

      {/* Timeline detail modal (from clicking a Gantt bar) */}
      {timelineModal && (
        <DetailModal
          sessionId={timelineModal.id}
          title={timelineModal.title}
          processes={processes}
          sessions={sessions}
          onClose={() => setTimelineModal(null)}
        />
      )}

      <Tooltip />
      <ToastContainer />
      <DisconnectOverlay />
      <AutostartPopover />
    </div>
  );
}

/** Wrapped with AppProvider so all children can access global state. */
export default function App() {
  return (
    <AppProvider>
      <Dashboard />
    </AppProvider>
  );
}
