/**
 * Header component — logo, title, waiting badge, credits, theme controls,
 * and last-updated timestamp.
 */

import { useState } from "react";
import { useTheme, useVersion } from "../hooks";
import type { Palette } from "../hooks";
import { useAppState, useAppDispatch } from "../state";
import { PALETTE_OPTIONS } from "../constants";
import HamburgerMenu from "./HamburgerMenu";
import ConfirmModal from "./ConfirmModal";

const BREADCRUMB_LABELS = {
  active: "Active sessions",
  previous: "Previous sessions",
  tasks: "Task Review",
  memory: "Memory",
  obsidian: "Obsidian",
  timeline: "Timeline",
  files: "Files",
} as const;

interface HeaderProps {
  /** Version string from the Python package, e.g. "1.2.3". */
  initialVersion: string;
  /** ISO timestamp string for "last updated" display. */
  lastUpdated: string;
  /** Number of sessions currently in "waiting" state. */
  waitingCount: number;
}

export default function Header({
  initialVersion,
  lastUpdated,
  waitingCount,
}: HeaderProps) {
  const { theme, toggleMode, setPalette } = useTheme();
  const { versionInfo, updating, doUpdate } = useVersion(initialVersion);
  const { serverPid, widgetsCollapsed, currentTab } = useAppState();
  const dispatch = useAppDispatch();
  const [showConfirm, setShowConfirm] = useState(false);

  const showUpdateModal = versionInfo.update_available && !updating;

  return (
    <div className="header">
      <div className="header-context">
        <div className="header-breadcrumb">
          <span>Personal Agent</span>
          <span>/</span>
          <strong>{BREADCRUMB_LABELS[currentTab]}</strong>
        </div>
        <div className="header-credits">
          AgentEye
          <span
            id="version-display"
            data-tip={
              showUpdateModal
                ? `v${versionInfo.latest} available — click to update`
                : "Up to date"
            }
            className={showUpdateModal ? "version-update-available" : ""}
            onClick={showUpdateModal ? () => setShowConfirm(true) : undefined}
            style={showUpdateModal ? { cursor: "pointer" } : undefined}
          >
            {versionInfo.personal
              ? ` v${versionInfo.personal}`
              : ` v${versionInfo.current}`}
            {updating && " ⏳ Updating…"}
            {showUpdateModal && " ⬆"}
          </span>
        </div>
        {waitingCount > 0 && (
          <span id="waiting-badge" data-tip="Sessions waiting for input">
            ⏳ {waitingCount} waiting
          </span>
        )}
      </div>

      <div className="header-right">
        <div className="theme-controls">
          {currentTab === "active" && (
            <button
              className="theme-btn"
              onClick={() => dispatch({ type: "TOGGLE_WIDGETS_COLLAPSED" })}
              data-tip={widgetsCollapsed ? "Show stats widgets" : "Hide stats widgets"}
            >
              {widgetsCollapsed ? "📊 Show Stats" : "📊 Hide Stats"}
            </button>
          )}
          <button
            className="theme-btn"
            onClick={toggleMode}
            data-tip="Toggle light/dark mode"
          >
            {theme.mode === "dark" ? "🌙 Dark" : "☀️ Light"}
          </button>
          <select
            className="palette-select"
            data-tip="Color palette"
            value={theme.palette}
            onChange={(e) => setPalette(e.target.value as Palette)}
          >
            {PALETTE_OPTIONS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </div>
        <div className="header-meta">
          <span className="refresh-dot" />
          <span id="last-updated">{lastUpdated}</span>
        </div>
        <HamburgerMenu />
      </div>

      {/* Server PID — small fixed footer element */}
      {serverPid && (
        <div
          style={{
            position: "fixed",
            bottom: 8,
            right: 12,
            fontSize: 11,
            opacity: 0.4,
            color: "var(--text2)",
            fontFamily: "monospace",
          }}
          data-tip="Dashboard server process ID"
        >
          server PID {serverPid}
        </div>
      )}

      {showConfirm && (
        <ConfirmModal
          title="Update Available"
          message={`Update from v${versionInfo.current} to v${versionInfo.latest}?`}
          confirmLabel="Update Now"
          cancelLabel="Not Now"
          onConfirm={() => {
            setShowConfirm(false);
            doUpdate();
          }}
          onCancel={() => setShowConfirm(false)}
        />
      )}
    </div>
  );
}
