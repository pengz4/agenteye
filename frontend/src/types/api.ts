/**
 * TypeScript type definitions matching the Python API responses.
 *
 * These interfaces mirror the Pydantic models in src/schemas.py. Keep them
 * in sync whenever the backend API changes.
 */

/** A single running background subagent task. */
export interface BackgroundTask {
  agent_name: string;
  description: string;
}

/** Matches Python ProcessInfo model (src/schemas.py). */
export interface ProcessInfo {
  pid: number;
  parent_pid: number;
  terminal_pid: number;
  terminal_name: string;
  cmdline: string;
  yolo: boolean;
  state: "waiting" | "working" | "thinking" | "idle" | "unknown";
  waiting_context: string;
  bg_tasks: number;
  bg_task_list: BackgroundTask[];
  mcp_servers: string[];
  window_title: string;
}

/** A session as returned by GET /api/sessions. */
export interface Session {
  id: string;
  cwd: string | null;
  repository: string | null;
  branch: string | null;
  summary: string | null;
  created_at: string;
  updated_at: string;
  created_ago: string;
  time_ago: string;
  turn_count: number;
  file_count: number;
  checkpoint_count: number;
  is_running: boolean;
  state: string | null;
  waiting_context: string;
  bg_tasks: number;
  group: string;
  recent_activity: string | null;
  restart_cmd: string;
  mcp_servers: string[];
  tool_calls: number;
  subagent_runs: number;
  intent: string;
  source: "copilot" | "claude" | "scout";
  machine_name: string;
}

/** Checkpoint detail returned within GET /api/session/:id. */
export interface Checkpoint {
  checkpoint_number: number;
  title: string | null;
  overview: string | null;
  next_steps: string | null;
}

/** Reference (commit, PR, issue) returned within GET /api/session/:id. */
export interface Ref {
  ref_type: string;
  ref_value: string;
}

/** Conversation turn returned within GET /api/session/:id. */
export interface Turn {
  turn_index: number;
  user_message: string | null;
  assistant_response: string | null;
}

/** Tool usage count returned within GET /api/session/:id. */
export interface ToolCount {
  name: string;
  count: number;
}

export interface PlanProgress {
  done: number;
  total: number;
}

export interface SessionPlan {
  path: string | null;
  content: string | null;
  mtime: string | null;
  progress: PlanProgress | null;
}

/** Full response from GET /api/session/:id. */
export interface SessionDetail {
  checkpoints: Checkpoint[];
  refs: Ref[];
  turns: Turn[];
  recent_output: string[];
  tool_counts: ToolCount[];
  files: string[];
}

export interface SessionTurnsPage {
  turns: Turn[];
  has_earlier: boolean;
}

/** Map of session_id → ProcessInfo from GET /api/processes. */
export type ProcessMap = Record<string, ProcessInfo>;

/** File frequency from GET /api/files. */
export interface FileFrequency {
  file_path: string;
  session_count: number;
}

/** GET /api/version response. */
export interface VersionInfo {
  current: string;
  personal?: string | null;
  latest: string | null;
  update_available: boolean;
}

/** GET /api/server-info response. */
export interface ServerInfo {
  pid: number;
  port: string;
  sync_folder: string | null;
  log_file: string | null;
  log_level: string;
}

/** GET /api/autostart response. */
export interface AutostartStatus {
  supported: boolean;
  enabled: boolean;
}

/** GET/PUT /api/settings response. */
export interface DashboardSettings {
  sync_enabled: boolean;
  log_level: string;
  mtime_active_threshold: number;
  obsidian_enabled: boolean;
  obsidian_vault_path: string;
  obsidian_task_folder: string;
  obsidian_status: string;
  achievement_ledger_path: string;
  coach_mode: "off" | "ask" | "auto";
}

export interface RuntimeCard {
  name: string;
  status: string;
  detail: string;
  url: string | null;
}

export interface ControlPlaneOverview {
  runtimes: RuntimeCard[];
}

export interface MemorySyncSummary {
  last_outcome: string;
  queue_count: number;
  last_attempt_at: string;
  last_successful_pull_at: string;
  last_successful_push_at: string;
}

export interface MemoryActivity {
  timestamp: string;
  summary: string;
  action: string;
  trigger: string;
}

export interface MemoryEntrySummary {
  id: string;
  kind: string;
  title: string;
  updated_at: string;
}

export interface MemoryOverview {
  status: string;
  runtime_installed: boolean;
  account_id: string;
  device: string;
  counts: Record<string, number>;
  sync: MemorySyncSummary;
  today_captures: number;
  recent_entries: MemoryEntrySummary[];
  recent_activity: MemoryActivity[];
}

export interface ObsidianNoteSummary {
  name: string;
  relative_path: string;
  updated_at: string;
  open_url: string;
}

export interface ObsidianOverview {
  status: string;
  vault_connected: boolean;
  git: {
    branch: string;
    dirty_count: number;
    last_commit: string;
    last_commit_at: string;
    status: string;
  };
  today: {
    date: string;
    daily_note_exists: boolean;
    daily_note_name: string;
  };
  tasks: {
    total: number;
    active: number;
    review: number;
    completed: number;
    cross_day: number;
  };
  achievements: {
    candidate: number;
    pending_intake: number;
    queued_intake: number;
    linked: number;
    skipped: number;
  };
  recent_notes: ObsidianNoteSummary[];
  links: Record<string, string>;
}

export type AgentTaskStatus =
  | "active"
  | "awaiting_confirmation"
  | "completed"
  | "blocked"
  | "merged";

/** Durable logical task tracked across CLI session turns and calendar days. */
export interface AgentTask {
  id: string;
  session_id: string;
  source: "copilot" | "claude" | "scout";
  title: string;
  summary: string;
  status: AgentTaskStatus;
  cwd: string;
  start_date: string;
  last_activity_date: string;
  last_turn_index: number;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  obsidian_path: string | null;
  merged_into: string | null;
  achievement_status:
    | "not_candidate"
    | "candidate"
    | "pending_intake"
    | "linked"
    | "skipped";
  achievement_source_key: string | null;
  achievement_ref: string | null;
  coach_status:
    | "off"
    | "needs_confirmation"
    | "pending"
    | "generated"
    | "skipped";
  repository?: string | null;
  branch?: string | null;
  session_short_id?: string | null;
}

export interface TaskSyncResult {
  tasks: AgentTask[];
  reconciled: number;
  obsidian_synced: number;
  obsidian_status: string;
  achievement_linked: number;
  coach_staged: number;
}
