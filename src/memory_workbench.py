"""Read-only metadata summary for the Personal Memory workbench."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _memory_environment(config: dict[str, Any], home: Path) -> dict[str, str]:
    configured_path = home / ".copilot" / "mcp-config.json"
    try:
        payload = json.loads(configured_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    servers = payload.get("mcpServers", {}) if isinstance(payload, dict) else {}
    server: dict[str, Any] = {}
    if isinstance(servers, dict):
        server = servers.get("personal-agent-memory") or servers.get("personal-memory") or {}
        if not server:
            server = next(
                (
                    candidate
                    for candidate in servers.values()
                    if isinstance(candidate, dict)
                    and isinstance(candidate.get("env"), dict)
                    and "MEMORY_ACCOUNT_ID" in candidate["env"]
                ),
                {},
            )
    environment = server.get("env", {}) if isinstance(server, dict) else {}
    if not isinstance(environment, dict):
        return {}
    return {str(key): str(value) for key, value in environment.items()}


def _configured_repositories(
    config: dict[str, Any], environment: dict[str, str], home: Path
) -> list[Path]:
    stack = config.get("stack", {})
    configured = (
        stack.get("memory_repository") if isinstance(stack, dict) else None
    ) or environment.get("MEMORY_REPOSITORY_DIR")
    if isinstance(configured, str) and configured.strip():
        shared = Path(configured).expanduser()
    else:
        shared = home / ".copilot" / "memu" / "repository"
    device = home / ".copilot" / "memu" / "device-repository"
    return [path for path in (shared, device) if path.exists()]


def _recent_entries(repositories: list[Path], account_id: str) -> tuple[dict[str, int], list[dict]]:
    records_by_id: dict[str, dict[str, Any]] = {}
    archived_count = 0
    for repository in repositories:
        entries_root = repository / "accounts" / account_id / "memory" / "entries"
        if not entries_root.is_dir():
            continue
        for path in entries_root.glob("*/*.json"):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(value, dict):
                continue
            lifecycle = value.get("lifecycle", {})
            status = (
                str(lifecycle.get("status") or "active")
                if isinstance(lifecycle, dict)
                else "active"
            )
            if status != "active":
                archived_count += 1
                continue
            entry_id = str(value.get("entry_id") or path.stem)
            record = {
                "id": entry_id,
                "kind": str(value.get("kind") or path.parent.name),
                "title": str(value.get("title") or "Untitled memory"),
                "updated_at": str(value.get("updated_at") or ""),
            }
            existing = records_by_id.get(entry_id)
            if existing is None or record["updated_at"] > existing["updated_at"]:
                records_by_id[entry_id] = record
    counts: Counter[str] = Counter(record["kind"] for record in records_by_id.values())
    records = list(records_by_id.values())
    records.sort(key=lambda item: item["updated_at"], reverse=True)
    return {
        **{kind: counts[kind] for kind in sorted(counts)},
        "total": sum(counts.values()),
        "archived": archived_count,
    }, records[:8]


def _sync_summary(home: Path, account_id: str) -> dict[str, Any]:
    path = home / ".copilot" / "memu" / "sync" / "accounts" / account_id / "management-status.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        value = {}
    return {
        "last_outcome": str(value.get("last_outcome") or "unknown"),
        "queue_count": int(value.get("queue_count") or 0),
        "last_attempt_at": str(value.get("last_attempt_at") or ""),
        "last_successful_pull_at": str(value.get("last_successful_pull_at") or ""),
        "last_successful_push_at": str(value.get("last_successful_push_at") or ""),
    }


def _audit_summary(home: Path, account_id: str, today: str) -> tuple[int, list[dict]]:
    path = home / ".copilot" / "memu" / "audit" / "accounts" / account_id / "capture-events.jsonl"
    records: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        lines = []
    for line in reversed(lines):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(value, dict):
            continue
        records.append(
            {
                "timestamp": str(value.get("created_at") or ""),
                "summary": str(value.get("safe_summary") or "Memory event"),
                "action": str(value.get("action") or "unknown"),
                "trigger": str(value.get("trigger") or "unknown"),
            }
        )
    today_count = sum(1 for record in records if record["timestamp"].startswith(today))
    return today_count, records[:8]


def get_memory_overview(
    config: dict[str, Any],
    *,
    home: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return aggregate Memory status without reading memory bodies into the response."""
    root = (home or Path.home()).expanduser()
    environment = _memory_environment(config, root)
    account_id = environment.get("MEMORY_ACCOUNT_ID", "")
    device = environment.get("MEMORY_DEVICE", "")
    repositories = _configured_repositories(config, environment, root)
    stack = config.get("stack", {})
    runtime_path = Path(str(stack.get("memory_root") or "")) if isinstance(stack, dict) else None
    runtime_present = (
        runtime_path is not None
        and bool(str(runtime_path))
        and (runtime_path / "bin" / "personal-memory-mcp.js").is_file()
    )

    if not account_id or not repositories:
        return {
            "status": "not_configured",
            "runtime_installed": runtime_present,
            "account_id": "",
            "device": device,
            "counts": {"total": 0},
            "sync": {
                "last_outcome": "unknown",
                "queue_count": 0,
                "last_attempt_at": "",
                "last_successful_pull_at": "",
                "last_successful_push_at": "",
            },
            "today_captures": 0,
            "recent_entries": [],
            "recent_activity": [],
        }

    counts, recent_entries = _recent_entries(repositories, account_id)
    today = (now or datetime.now(UTC)).astimezone(UTC).date().isoformat()
    today_captures, recent_activity = _audit_summary(root, account_id, today)
    return {
        "status": "configured",
        "runtime_installed": runtime_present,
        "account_id": account_id,
        "device": device,
        "counts": counts,
        "sync": _sync_summary(root, account_id),
        "today_captures": today_captures,
        "recent_entries": recent_entries,
        "recent_activity": recent_activity,
    }
