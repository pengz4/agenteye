"""Safe, one-way Markdown synchronization from Agent Eye to Obsidian."""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TASK_BLOCK_START = "<!-- agenteye:task-managed:start -->"
TASK_BLOCK_END = "<!-- agenteye:task-managed:end -->"
DAILY_BLOCK_START = "<!-- agenteye:daily-managed:start -->"
DAILY_BLOCK_END = "<!-- agenteye:daily-managed:end -->"
TASK_ID_PATTERN = re.compile(r"<!-- agenteye-task:([a-zA-Z0-9_-]+) -->")
INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_write_lock = threading.RLock()


@dataclass(frozen=True)
class ObsidianSyncConfig:
    """Resolved Obsidian synchronization paths."""

    vault_path: Path
    task_folder: str = "AgentEye/Tasks"
    daily_folder: str | None = None
    daily_format: str | None = None
    achievement_folders: tuple[str, ...] = ("Achievements",)


@dataclass(frozen=True)
class ObsidianSyncResult:
    """Paths written by one task synchronization."""

    task_path: Path
    daily_path: Path


def discover_obsidian_vault(config_home: Path | None = None) -> Path | None:
    """Return the only configured Obsidian Vault, or ``None`` when ambiguous."""
    candidates = []
    if config_home is not None:
        candidates.append(Path(config_home) / "obsidian" / "obsidian.json")
    else:
        xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config_home:
            candidates.append(Path(xdg_config_home) / "obsidian" / "obsidian.json")
        candidates.extend(
            [
                Path.home() / ".config" / "obsidian" / "obsidian.json",
                Path.home() / "Library" / "Application Support" / "obsidian" / "obsidian.json",
                Path(os.environ.get("APPDATA", "")) / "obsidian" / "obsidian.json",
            ]
        )

    vaults: set[Path] = set()
    for config_path in candidates:
        if not config_path.is_file():
            continue
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        configured = payload.get("vaults", {})
        if not isinstance(configured, dict):
            continue
        for entry in configured.values():
            path = entry.get("path") if isinstance(entry, dict) else None
            if not isinstance(path, str) or not path:
                continue
            resolved = Path(path).expanduser().resolve()
            if (resolved / ".obsidian").is_dir() or resolved.is_dir():
                vaults.add(resolved)

    if len(vaults) == 1:
        return next(iter(vaults))
    return None


class ObsidianSync:
    """Write Agent Eye task state without overwriting user-owned Markdown."""

    def __init__(self, config: ObsidianSyncConfig):
        self.config = config

    def _inside_vault(self, relative: Path) -> Path:
        vault = self.config.vault_path.expanduser().resolve()
        candidate = (vault / relative).resolve()
        try:
            resolved_relative = candidate.relative_to(vault)
        except ValueError as exc:
            raise ValueError("Obsidian paths must stay inside the Vault") from exc
        protected = {folder.casefold() for folder in self.config.achievement_folders}
        if any(part.casefold() in protected for part in resolved_relative.parts):
            raise ValueError("Obsidian task paths cannot enter achievement-owned folders")
        return candidate

    @staticmethod
    def _slug(value: str) -> str:
        cleaned = INVALID_FILENAME_CHARS.sub("", value).strip()
        cleaned = re.sub(r"\s+", "-", cleaned)
        cleaned = re.sub(r"-{2,}", "-", cleaned).strip(".- ")
        return cleaned[:80] or "task"

    def _task_path(self, task: dict[str, Any]) -> tuple[Path, Path]:
        configured = Path(self.config.task_folder)
        if configured.is_absolute():
            raise ValueError("Obsidian paths must stay inside the Vault")
        filename = (
            f"{task['start_date']}--{self._slug(str(task['title']))}--{str(task['id'])[:8]}.md"
        )
        relative = configured / filename
        return relative, self._inside_vault(relative)

    @staticmethod
    def _date_tokens(value: str) -> str:
        replacements = [
            ("YYYY", "%Y"),
            ("MM", "%m"),
            ("DD", "%d"),
        ]
        for token, replacement in replacements:
            value = value.replace(token, replacement)
        return value

    def _daily_config(self) -> tuple[str, str]:
        config_path = self.config.vault_path / ".obsidian" / "daily-notes.json"
        folder = self.config.daily_folder
        date_format = self.config.daily_format
        if config_path.is_file():
            try:
                payload = json.loads(config_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = {}
            if folder is None:
                configured_folder = payload.get("folder")
                if isinstance(configured_folder, str):
                    folder = configured_folder
            if date_format is None:
                configured_format = payload.get("format")
                if isinstance(configured_format, str):
                    date_format = configured_format
        return folder or "", date_format or "YYYY-MM-DD"

    def _daily_path(self, activity_date: str) -> tuple[Path, Path]:
        from datetime import date

        folder, date_format = self._daily_config()
        parsed = date.fromisoformat(activity_date)
        filename = parsed.strftime(self._date_tokens(date_format))
        if not filename.endswith(".md"):
            filename += ".md"
        relative = Path(folder) / filename
        return relative, self._inside_vault(relative)

    @staticmethod
    def _replace_block(content: str, start_marker: str, end_marker: str, managed: str) -> str:
        replacement = f"{start_marker}\n{managed.rstrip()}\n{end_marker}"
        start = content.find(start_marker)
        if start == -1:
            return (
                f"{content.rstrip()}\n\n{replacement}\n" if content.strip() else f"{replacement}\n"
            )
        end = content.find(end_marker, start)
        if end == -1:
            return f"{replacement}\n\n{content}"
        end += len(end_marker)
        return content[:start] + replacement + content[end:]

    @staticmethod
    def _write_atomic(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=path.parent, prefix=f".{path.name}.", suffix=".agenteye.tmp"
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()

    @staticmethod
    def _status_label(status: str) -> str:
        return status.replace("_", " ")

    def _render_task_block(self, task: dict[str, Any], activities: list[dict[str, Any]]) -> str:
        lines = [
            f"- **Task ID:** `{task['id']}`",
            f"- **Achievement source key:** `{task.get('achievement_source_key') or 'task:' + str(task['id'])}`",
            f"- **CLI:** {task['source']}",
            f"- **Session:** `{task['session_id']}`",
            f"- **Status:** {self._status_label(str(task['status']))}",
            f"- **Started:** {task['start_date']}",
            f"- **Working directory:** `{task['cwd'] or '-'}`",
            "",
            "## Summary",
            "",
            str(task["summary"]).strip() or "No summary available.",
        ]
        if task.get("merged_into"):
            lines.extend(["", "## Merged", "", f"- **Merged into:** `{task['merged_into']}`"])
        if activities:
            lines.extend(["", "## Activity", ""])
            for activity in activities[-50:]:
                summary = str(activity.get("summary") or "").strip()
                label = self._status_label(str(activity.get("status") or "active"))
                line = f"- {activity['activity_date']} — {label}"
                if summary:
                    line += f" — {summary}"
                lines.append(line)
        return "\n".join(lines)

    def _write_task_file(self, task: dict[str, Any], activities: list[dict[str, Any]]) -> Path:
        relative, path = self._task_path(task)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = path.read_text(encoding="utf-8") if path.exists() else f"# {task['title']}\n"
        content = self._replace_block(
            content,
            TASK_BLOCK_START,
            TASK_BLOCK_END,
            self._render_task_block(task, activities),
        )
        self._write_atomic(path, content)
        return relative

    def _daily_line(self, task: dict[str, Any], task_relative: Path) -> str:
        checked = "x" if task["status"] == "completed" else " "
        link = task_relative.as_posix().removesuffix(".md")
        return (
            f"- [{checked}] <!-- agenteye-task:{task['id']} --> "
            f"[[{link}|{task['title']}]] · {task['source']} · "
            f"{self._status_label(str(task['status']))}"
        )

    def _replace_daily_line(self, content: str, task: dict[str, Any], line: str) -> str:
        start = content.find(DAILY_BLOCK_START)
        end = content.find(DAILY_BLOCK_END, start) if start != -1 else -1
        if start == -1 or end == -1:
            return self._replace_block(content, DAILY_BLOCK_START, DAILY_BLOCK_END, line)

        managed = content[start + len(DAILY_BLOCK_START) : end].strip()
        rows = [row for row in managed.splitlines() if row.strip()]
        replaced = False
        for index, row in enumerate(rows):
            match = TASK_ID_PATTERN.search(row)
            if match and match.group(1) == str(task["id"]):
                rows[index] = line
                replaced = True
                break
        if not replaced:
            rows.append(line)
        return self._replace_block(content, DAILY_BLOCK_START, DAILY_BLOCK_END, "\n".join(rows))

    def _remove_daily_line(self, task: dict[str, Any], activity_date: str) -> None:
        _relative, path = self._daily_path(activity_date)
        if not path.is_file():
            return
        content = path.read_text(encoding="utf-8")
        start = content.find(DAILY_BLOCK_START)
        end = content.find(DAILY_BLOCK_END, start) if start != -1 else -1
        if start == -1 or end == -1:
            return
        managed = content[start + len(DAILY_BLOCK_START) : end].strip()
        rows = []
        for line in managed.splitlines():
            match = TASK_ID_PATTERN.search(line)
            if not match or match.group(1) != str(task["id"]):
                rows.append(line)
        updated = self._replace_block(content, DAILY_BLOCK_START, DAILY_BLOCK_END, "\n".join(rows))
        self._write_atomic(path, updated)

    def read_daily_task_completion(self, task: dict[str, Any]) -> bool | None:
        """Read a manually toggled Obsidian Tasks checkbox for one task."""
        _relative, path = self._daily_path(str(task["last_activity_date"]))
        with _write_lock:
            if not path.is_file():
                return None
            for line in path.read_text(encoding="utf-8").splitlines():
                match = TASK_ID_PATTERN.search(line)
                if match and match.group(1) == str(task["id"]):
                    checkbox = re.match(r"-\s+\[([ xX])\]", line)
                    return bool(checkbox and checkbox.group(1).lower() == "x")
        return None

    def sync_task(
        self, task: dict[str, Any], activities: list[dict[str, Any]]
    ) -> ObsidianSyncResult:
        """Create or update a canonical task and today's compact Daily Note link."""
        with _write_lock:
            task_relative = self._write_task_file(task, activities)
            daily_relative, daily_path = self._daily_path(str(task["last_activity_date"]))
            if task["status"] == "merged":
                activity_dates = {str(activity["activity_date"]) for activity in activities}
                activity_dates.add(str(task["start_date"]))
                for activity_date in activity_dates:
                    self._remove_daily_line(task, activity_date)
                return ObsidianSyncResult(task_path=task_relative, daily_path=daily_relative)
            daily_path.parent.mkdir(parents=True, exist_ok=True)
            existing = (
                daily_path.read_text(encoding="utf-8")
                if daily_path.exists()
                else f"# {task['last_activity_date']}\n"
            )
            line = self._daily_line(task, task_relative)
            self._write_atomic(daily_path, self._replace_daily_line(existing, task, line))
            return ObsidianSyncResult(task_path=task_relative, daily_path=daily_relative)
