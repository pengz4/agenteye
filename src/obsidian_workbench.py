"""Read-only Vault, Git, task, and achievement aggregates for Agent Eye."""

from __future__ import annotations

import json
import re
import subprocess
import threading
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

GIT_CACHE_TTL_SECONDS = 30
_git_summaries: dict[str, tuple[float, dict[str, Any]]] = {}
_git_refreshing: set[str] = set()
_git_lock = threading.Lock()


def _daily_config(vault: Path) -> tuple[str, str]:
    path = vault / ".obsidian" / "daily-notes.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        value = {}
    folder = value.get("folder") if isinstance(value, dict) else ""
    date_format = value.get("format") if isinstance(value, dict) else ""
    return (
        str(folder or ""),
        str(date_format or "YYYY-MM-DD"),
    )


def _format_daily_name(day: str, date_format: str) -> str:
    replacements = {"YYYY": "%Y", "MM": "%m", "DD": "%d"}
    formatted = date_format
    for source, target in replacements.items():
        formatted = formatted.replace(source, target)
    return datetime.strptime(day, "%Y-%m-%d").strftime(formatted) + ".md"


def _obsidian_url(vault: Path, relative_path: str) -> str:
    return (
        f"obsidian://open?vault={quote(vault.name)}&file={quote(relative_path.removesuffix('.md'))}"
    )


def _git_summary(vault: Path) -> dict[str, Any]:
    summary = {
        "branch": "",
        "dirty_count": 0,
        "last_commit": "",
        "last_commit_at": "",
        "status": "not_a_repository",
    }
    if not (vault / ".git").exists():
        return summary
    try:
        status_result = subprocess.run(
            ["git", "status", "--short", "--branch"],
            cwd=vault,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        log_result = subprocess.run(
            ["git", "log", "-1", "--format=%h|%cI"],
            cwd=vault,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        summary["status"] = "unavailable"
        return summary

    branch = ""
    dirty = 0
    for line in status_result.stdout.splitlines():
        if line.startswith("## "):
            branch = line[3:].split("...", 1)[0].strip()
        elif re.match(r"^[ MADRCU?!]{2} ", line):
            dirty += 1
    if not branch and status_result.stdout.splitlines():
        first = status_result.stdout.splitlines()[0]
        if "|" not in first and not first.startswith(" M") and not first.startswith("??"):
            branch = first.strip()

    commit = ""
    commit_at = ""
    for line in log_result.stdout.splitlines():
        parts = line.split("|", 2)
        if len(parts) >= 2:
            commit, commit_at = parts[:2]
            break
    summary.update(
        {
            "branch": branch,
            "dirty_count": dirty,
            "last_commit": commit,
            "last_commit_at": commit_at,
            "status": "configured" if status_result.returncode == 0 else "unavailable",
        }
    )
    return summary


def _refresh_git_summary(vault: Path, key: str) -> None:
    summary = _git_summary(vault)
    with _git_lock:
        _git_summaries[key] = (time.monotonic(), summary)
        _git_refreshing.discard(key)


def _empty_git_summary() -> dict[str, Any]:
    return {
        "branch": "",
        "dirty_count": 0,
        "last_commit": "",
        "last_commit_at": "",
        "status": "refreshing",
    }


def _cached_git_summary(vault: Path) -> dict[str, Any]:
    key = str(vault.resolve())
    now = time.monotonic()
    with _git_lock:
        cached = _git_summaries.get(key)
        if cached is not None and now - cached[0] < GIT_CACHE_TTL_SECONDS:
            return dict(cached[1])
        snapshot = dict(cached[1]) if cached is not None else _empty_git_summary()
        snapshot["status"] = "refreshing"
        should_refresh = key not in _git_refreshing
        if should_refresh:
            _git_refreshing.add(key)
    if should_refresh:
        threading.Thread(
            target=_refresh_git_summary,
            args=(vault, key),
            daemon=True,
            name="agenteye-obsidian-git",
        ).start()
    return snapshot


def _safe_vault_folder(vault: Path, folder: str) -> Path | None:
    path = Path(folder)
    if not folder or path.is_absolute() or ".." in path.parts:
        return None
    candidate = (vault / path).resolve()
    try:
        candidate.relative_to(vault.resolve())
    except ValueError:
        return None
    return candidate


def _recent_notes(vault: Path, task_folder: str, daily_folder: str) -> list[dict[str, str]]:
    roots = [
        _safe_vault_folder(vault, task_folder),
        _safe_vault_folder(vault, "Achievements/Daily"),
        _safe_vault_folder(vault, daily_folder),
    ]
    notes: list[dict[str, str]] = []
    for root in roots:
        if root is None or not root.is_dir():
            continue
        for path in root.glob("**/*.md"):
            try:
                modified = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()
                relative = path.relative_to(vault).as_posix()
            except (OSError, ValueError):
                continue
            notes.append(
                {
                    "name": path.stem,
                    "relative_path": relative,
                    "updated_at": modified,
                    "open_url": _obsidian_url(vault, relative),
                }
            )
    notes.sort(key=lambda item: item["updated_at"], reverse=True)
    return notes[:8]


def _safe_daily_relative(vault: Path, folder: str, filename: str) -> str | None:
    if Path(folder).is_absolute() or ".." in Path(folder).parts:
        return None
    vault_root = vault.resolve()
    candidate = (vault / folder / filename).resolve()
    try:
        return candidate.relative_to(vault_root).as_posix()
    except ValueError:
        return None


def get_obsidian_overview(
    config: dict[str, Any],
    *,
    tasks: list[dict[str, Any]],
    now: datetime | None = None,
    git_async: bool = False,
    queued_intake: int = 0,
) -> dict[str, Any]:
    """Return Vault/Git/task aggregates without note bodies or absolute paths."""
    obsidian = config.get("obsidian", {})
    stack = config.get("stack", {})
    enabled = isinstance(obsidian, dict) and bool(obsidian.get("enabled", False))
    configured = (str(obsidian.get("vault_path") or "") if isinstance(obsidian, dict) else "") or (
        str(stack.get("obsidian_vault") or "") if isinstance(stack, dict) else ""
    )
    if not enabled or not configured:
        return {
            "status": "not_configured",
            "vault_connected": False,
            "git": {
                "branch": "",
                "dirty_count": 0,
                "last_commit": "",
                "last_commit_at": "",
                "status": "not_a_repository",
            },
            "today": {
                "date": (now or datetime.now(UTC)).date().isoformat(),
                "daily_note_exists": False,
                "daily_note_name": "",
            },
            "tasks": {"total": 0, "active": 0, "review": 0, "completed": 0, "cross_day": 0},
            "achievements": {
                "candidate": 0,
                "pending_intake": 0,
                "queued_intake": 0,
                "linked": 0,
                "skipped": 0,
            },
            "recent_notes": [],
            "links": {},
        }

    vault = Path(configured).expanduser()
    if not (vault / ".obsidian").is_dir():
        return {
            "status": "invalid_vault",
            "vault_connected": False,
            "git": _cached_git_summary(vault) if git_async else _git_summary(vault),
            "today": {
                "date": (now or datetime.now(UTC)).date().isoformat(),
                "daily_note_exists": False,
                "daily_note_name": "",
            },
            "tasks": {"total": 0, "active": 0, "review": 0, "completed": 0, "cross_day": 0},
            "achievements": {
                "candidate": 0,
                "pending_intake": 0,
                "queued_intake": 0,
                "linked": 0,
                "skipped": 0,
            },
            "recent_notes": [],
            "links": {},
        }

    today = (now or datetime.now(UTC)).astimezone(UTC).date().isoformat()
    daily_folder, daily_format = _daily_config(vault)
    task_folder = (
        str(obsidian.get("task_folder") or "AgentEye/Tasks")
        if isinstance(obsidian, dict)
        else "AgentEye/Tasks"
    )
    daily_name = _format_daily_name(today, daily_format)
    daily_relative = _safe_daily_relative(vault, daily_folder, daily_name)
    daily_exists = daily_relative is not None and (vault / daily_relative).is_file()
    task_counts: Counter[str] = Counter(task.get("status", "") for task in tasks)
    achievement_counts: Counter[str] = Counter(
        task.get("achievement_status", "not_candidate") for task in tasks
    )
    cross_day = sum(1 for task in tasks if task.get("start_date") != task.get("last_activity_date"))
    achievement_relative = "Achievements"
    links = {
        "vault": _obsidian_url(vault, ""),
        "achievements": _obsidian_url(vault, achievement_relative),
    }
    if daily_relative is not None:
        links["daily_note"] = _obsidian_url(vault, daily_relative)
    return {
        "status": "connected" if daily_relative is not None else "invalid_configuration",
        "vault_connected": True,
        "git": _cached_git_summary(vault) if git_async else _git_summary(vault),
        "today": {
            "date": today,
            "daily_note_exists": daily_exists,
            "daily_note_name": daily_name,
        },
        "tasks": {
            "total": len(tasks),
            "active": task_counts["active"] + task_counts["blocked"],
            "review": task_counts["awaiting_confirmation"] + task_counts["blocked"],
            "completed": task_counts["completed"],
            "cross_day": cross_day,
        },
        "achievements": {
            "candidate": achievement_counts["candidate"],
            "pending_intake": achievement_counts["pending_intake"],
            "queued_intake": queued_intake,
            "linked": achievement_counts["linked"],
            "skipped": achievement_counts["skipped"],
        },
        "recent_notes": _recent_notes(vault, task_folder, daily_folder),
        "links": links,
    }
