"""
Pydantic response models for the FastAPI dashboard API.

These define the JSON shapes for all API endpoints and give us
automatic OpenAPI schema generation + Swagger UI.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ── Session list (/api/sessions) ─────────────────────────────────────────────


class SessionResponse(BaseModel):
    """A session as returned by GET /api/sessions."""

    id: str
    cwd: str | None = None
    repository: str | None = None
    branch: str | None = None
    summary: str | None = None
    created_at: str
    updated_at: str
    created_ago: str = ""
    time_ago: str = ""
    turn_count: int = 0
    file_count: int = 0
    checkpoint_count: int = 0
    is_running: bool = False
    state: str | None = None
    waiting_context: str = ""
    bg_tasks: int = 0
    group: str = "General"
    recent_activity: str | None = None
    restart_cmd: str = ""
    mcp_servers: list[str] = Field(default_factory=list)
    tool_calls: int = 0
    subagent_runs: int = 0
    intent: str = ""
    source: str = "copilot"
    machine_name: str = ""


# ── Process map (/api/processes) ─────────────────────────────────────────────


class BackgroundTaskResponse(BaseModel):
    """A single running background subagent task."""

    agent_name: str = ""
    description: str = ""


class ProcessResponse(BaseModel):
    """A running Copilot process as returned by GET /api/processes."""

    pid: int
    parent_pid: int = 0
    terminal_pid: int = 0
    terminal_name: str = ""
    cmdline: str = ""
    yolo: bool = False
    agency: bool = False
    state: str = "unknown"
    waiting_context: str = ""
    bg_tasks: int = 0
    bg_task_list: list[BackgroundTaskResponse] = Field(default_factory=list)
    mcp_servers: list[str] = Field(default_factory=list)
    window_title: str = ""


# ── Session detail (/api/session/{id}) ───────────────────────────────────────


class CheckpointResponse(BaseModel):
    checkpoint_number: int
    title: str | None = None
    overview: str | None = None
    next_steps: str | None = None


class RefResponse(BaseModel):
    ref_type: str
    ref_value: str


class TurnResponse(BaseModel):
    turn_index: int
    user_message: str | None = None
    assistant_response: str | None = None


class ToolCountResponse(BaseModel):
    name: str
    count: int


class PlanProgressResponse(BaseModel):
    done: int
    total: int


class PlanResponse(BaseModel):
    path: str | None = None
    content: str | None = None
    mtime: str | None = None
    progress: PlanProgressResponse | None = None


class SessionDetailResponse(BaseModel):
    checkpoints: list[CheckpointResponse] = Field(default_factory=list)
    refs: list[RefResponse] = Field(default_factory=list)
    turns: list[TurnResponse] = Field(default_factory=list)
    recent_output: list[str] = Field(default_factory=list)
    tool_counts: list[ToolCountResponse] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)


class SessionCountsResponse(BaseModel):
    active: int
    previous: int


class SessionTurnsResponse(BaseModel):
    turns: list[TurnResponse] = Field(default_factory=list)
    has_earlier: bool = False


# ── Files (/api/files) ──────────────────────────────────────────────────────


class FileEntryResponse(BaseModel):
    file_path: str
    session_count: int
    session_ids: str  # comma-separated


# ── Version (/api/version) ──────────────────────────────────────────────────


class VersionResponse(BaseModel):
    current: str
    personal: str | None = None
    latest: str | None = None
    update_available: bool = False


# ── Generic ─────────────────────────────────────────────────────────────────


class ActionResponse(BaseModel):
    """Generic success/failure response for POST actions."""

    success: bool
    message: str = ""


class ServerInfoResponse(BaseModel):
    pid: int
    port: str
    sync_folder: str | None = None
    log_file: str | None = None
    log_level: str = "INFO"


class AutostartStatusResponse(BaseModel):
    """Response for GET /api/autostart — reports whether autostart is supported and enabled."""

    supported: bool
    enabled: bool


class SettingsResponse(BaseModel):
    """Response for GET/PUT /api/settings — dashboard configuration."""

    sync_enabled: bool = True
    log_level: str = "INFO"
    mtime_active_threshold: int = 120
    obsidian_enabled: bool = False
    obsidian_vault_path: str = ""
    obsidian_task_folder: str = "AgentEye/Tasks"
    obsidian_status: str = "disabled"
    achievement_ledger_path: str = ""
    coach_mode: str = "ask"


# ── Tasks (/api/tasks) ──────────────────────────────────────────────────────


class TaskResponse(BaseModel):
    id: str
    session_id: str
    source: str
    title: str
    summary: str
    status: str
    cwd: str = ""
    start_date: str
    last_activity_date: str
    last_turn_index: int
    created_at: str
    updated_at: str
    completed_at: str | None = None
    obsidian_path: str | None = None
    merged_into: str | None = None
    achievement_status: str = "not_candidate"
    achievement_source_key: str | None = None
    achievement_ref: str | None = None
    coach_status: str = "off"
    repository: str | None = None
    branch: str | None = None
    session_short_id: str | None = None


class TaskSyncResponse(BaseModel):
    tasks: list[TaskResponse] = Field(default_factory=list)
    reconciled: int = 0
    obsidian_synced: int = 0
    obsidian_status: str = "disabled"
    achievement_linked: int = 0
    coach_staged: int = 0


class TaskSplitRequest(BaseModel):
    title: str
    turn_index: int | None = None


class TaskMergeRequest(BaseModel):
    target_id: str
    source_id: str


# ── Workbenches (/api/memory-overview, /api/obsidian-overview) ──────────────


class MemorySyncSummary(BaseModel):
    last_outcome: str = "unknown"
    queue_count: int = 0
    last_attempt_at: str = ""
    last_successful_pull_at: str = ""
    last_successful_push_at: str = ""


class MemoryActivity(BaseModel):
    timestamp: str
    summary: str
    action: str
    trigger: str


class MemoryEntrySummary(BaseModel):
    id: str
    kind: str
    title: str
    updated_at: str


class MemoryOverviewResponse(BaseModel):
    status: str
    runtime_installed: bool = False
    account_id: str = ""
    device: str = ""
    counts: dict[str, int] = Field(default_factory=dict)
    sync: MemorySyncSummary = Field(default_factory=MemorySyncSummary)
    today_captures: int = 0
    recent_entries: list[MemoryEntrySummary] = Field(default_factory=list)
    recent_activity: list[MemoryActivity] = Field(default_factory=list)


class ObsidianGitSummary(BaseModel):
    branch: str = ""
    dirty_count: int = 0
    last_commit: str = ""
    last_commit_at: str = ""
    status: str = "not_a_repository"


class ObsidianNoteSummary(BaseModel):
    name: str
    relative_path: str
    updated_at: str
    open_url: str


class ObsidianOverviewResponse(BaseModel):
    status: str
    vault_connected: bool = False
    git: ObsidianGitSummary = Field(default_factory=ObsidianGitSummary)
    today: dict[str, Any] = Field(default_factory=dict)
    tasks: dict[str, int] = Field(default_factory=dict)
    achievements: dict[str, int] = Field(default_factory=dict)
    recent_notes: list[ObsidianNoteSummary] = Field(default_factory=list)
    links: dict[str, str] = Field(default_factory=dict)
