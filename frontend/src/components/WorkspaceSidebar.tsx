import { useAppDispatch, useAppState, type Tab } from "../state";
import RuntimeOverview from "./RuntimeOverview";

interface WorkspaceSidebarProps {
  activeCount: number;
  previousCount: number;
  taskCount: number;
}

const NAV_GROUPS: {
  label: string;
  items: { key: Tab; label: string; icon: string; title: string }[];
}[] = [
  {
    label: "Sessions",
    items: [
      { key: "active", label: "Active", icon: "⚡", title: "Currently running sessions" },
      { key: "previous", label: "Previous", icon: "📋", title: "Recent completed sessions" },
    ],
  },
  {
    label: "Review & knowledge",
    items: [
      { key: "tasks", label: "Task Review", icon: "✓", title: "Review and confirm completed tasks" },
      { key: "memory", label: "Memory", icon: "◇", title: "Personal Memory overview" },
      { key: "obsidian", label: "Obsidian", icon: "▤", title: "Vault and note synchronization" },
    ],
  },
  {
    label: "Inspect",
    items: [
      { key: "timeline", label: "Timeline", icon: "⌁", title: "Session activity timeline" },
      { key: "files", label: "Files", icon: "▦", title: "Frequently changed files" },
    ],
  },
];

export default function WorkspaceSidebar({
  activeCount,
  previousCount,
  taskCount,
}: WorkspaceSidebarProps) {
  const { currentTab } = useAppState();
  const dispatch = useAppDispatch();
  const counts: Partial<Record<Tab, number>> = {
    active: activeCount,
    previous: previousCount,
    tasks: taskCount,
  };

  const switchTab = (tab: Tab) => {
    dispatch({ type: "SET_TAB", tab });
    history.replaceState(null, "", `#${tab}`);
  };

  return (
    <aside className="workspace-sidebar">
      <div className="workspace-brand">
        <img src="/static/logo.png" alt="" />
        <div>
          <strong>Agent Eye</strong>
          <small>Personal Agent</small>
        </div>
      </div>

      <nav aria-label="Workspace navigation">
        {NAV_GROUPS.map((group) => (
          <div className="workspace-nav-group" key={group.label}>
            <div className="workspace-nav-label">{group.label}</div>
            {group.items.map((item) => (
              <button
                type="button"
                key={item.key}
                className={`workspace-nav-item ${currentTab === item.key ? "active" : ""}`}
                data-tab={item.key}
                onClick={() => switchTab(item.key)}
                title={item.title}
                aria-current={currentTab === item.key ? "page" : undefined}
              >
                <span className="workspace-nav-icon" aria-hidden="true">{item.icon}</span>
                <span>{item.label}</span>
                {counts[item.key] !== undefined && (
                  <span className="workspace-nav-count">{counts[item.key]}</span>
                )}
              </button>
            ))}
          </div>
        ))}
      </nav>

      <RuntimeOverview compact />
    </aside>
  );
}
