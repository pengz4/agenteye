"""Read-only achievement intake bridge and idempotent handoff outboxes."""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any

SOURCE_KEY_PATTERN = re.compile(r"`?(task:[0-9a-f-]+)`?")
HEADING_PATTERN = re.compile(r"^###\s+(.+)$")


class AchievementBridge:
    """Observe achievement writes and queue requests without writing achievement data."""

    def __init__(
        self,
        *,
        ledger_path: Path | str,
        intake_outbox: Path | str,
        coach_outbox: Path | str | None = None,
    ):
        self.ledger_path = Path(ledger_path)
        self.intake_outbox = Path(intake_outbox)
        self.coach_outbox = Path(coach_outbox) if coach_outbox is not None else None
        self._lock = threading.RLock()

    def find_links(self) -> dict[str, list[str]]:
        """Map stable task source keys to achievement headings already in the ledger."""
        if not self.ledger_path.is_file():
            return {}
        links: dict[str, list[str]] = {}
        current_heading = ""
        for line in self.ledger_path.read_text(encoding="utf-8", errors="replace").splitlines():
            heading = HEADING_PATTERN.match(line)
            if heading:
                current_heading = line.strip()
                continue
            if not current_heading:
                continue
            for match in SOURCE_KEY_PATTERN.finditer(line):
                links.setdefault(match.group(1), []).append(current_heading)
        return {source_key: list(dict.fromkeys(headings)) for source_key, headings in links.items()}

    @staticmethod
    def _read_keys(path: Path) -> set[str]:
        if not path.is_file():
            return set()
        keys: set[str] = set()
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            source_key = payload.get("source_key")
            if isinstance(source_key, str):
                keys.add(source_key)
        return keys

    @staticmethod
    def _append(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")

    @staticmethod
    def _intake_payload(task: dict[str, Any]) -> dict[str, Any]:
        source_key = str(task["achievement_source_key"])
        return {
            "source_key": source_key,
            "task_id": str(task["id"]),
            "session_id": str(task["session_id"]),
            "source": str(task["source"]),
            "title": str(task["title"]),
            "summary": str(task["summary"]),
            "cwd": str(task.get("cwd") or ""),
            "started": str(task["start_date"]),
            "completed_at": task.get("completed_at"),
            "obsidian_path": task.get("obsidian_path"),
            "requested_action": "evaluate_and_intake",
        }

    def enqueue_intake(self, task: dict[str, Any]) -> bool:
        """Queue one sanitized request; the intake skill remains the only writer."""
        source_key = str(task["achievement_source_key"])
        with self._lock:
            if source_key in self._read_keys(self.intake_outbox):
                return False
            self._append(self.intake_outbox, self._intake_payload(task))
            return True

    def has_intake_request(self, source_key: str) -> bool:
        with self._lock:
            return source_key in self._read_keys(self.intake_outbox)

    def apply_coach_policy(self, task: dict[str, Any], mode: str) -> str:
        """Return the next Coach state and optionally queue one downstream request."""
        if mode not in {"off", "ask", "auto"}:
            raise ValueError("Coach mode must be off, ask, or auto")
        if task.get("achievement_status") != "linked":
            return "off"
        if mode == "off":
            return "off"
        if mode == "ask":
            return "needs_confirmation"
        if self.coach_outbox is None:
            return "needs_confirmation"
        source_key = str(task["achievement_source_key"])
        coach_key = f"{source_key}|{task.get('achievement_ref') or ''}"
        with self._lock:
            existing = set()
            if self.coach_outbox.is_file():
                for line in self.coach_outbox.read_text(
                    encoding="utf-8", errors="replace"
                ).splitlines():
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    key = payload.get("coach_key")
                    if isinstance(key, str):
                        existing.add(key)
            if coach_key not in existing:
                self._append(
                    self.coach_outbox,
                    {
                        "coach_key": coach_key,
                        "source_key": source_key,
                        "task_id": str(task["id"]),
                        "achievement_ref": str(task["achievement_ref"]),
                        "requested_action": "generate_practice_only",
                    },
                )
        return "pending"
