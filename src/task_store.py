"""Durable task identity and lifecycle storage for Agent Eye."""

from __future__ import annotations

import builtins
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class TaskStore:
    """Store one durable record per logical CLI task."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    status TEXT NOT NULL,
                    cwd TEXT NOT NULL DEFAULT '',
                    start_date TEXT NOT NULL,
                    last_activity_date TEXT NOT NULL,
                    last_turn_index INTEGER NOT NULL DEFAULT -1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    obsidian_path TEXT,
                    merged_into TEXT,
                    manual_override INTEGER NOT NULL DEFAULT 0,
                    achievement_status TEXT NOT NULL DEFAULT 'not_candidate',
                    achievement_source_key TEXT,
                    achievement_ref TEXT,
                    coach_status TEXT NOT NULL DEFAULT 'off'
                );
                CREATE INDEX IF NOT EXISTS idx_tasks_session
                    ON tasks(session_id, updated_at);
                CREATE INDEX IF NOT EXISTS idx_tasks_status
                    ON tasks(status, updated_at);

                CREATE TABLE IF NOT EXISTS task_activities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                    activity_date TEXT NOT NULL,
                    status TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    occurred_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_task_activities_task_date
                    ON task_activities(task_id, activity_date, occurred_at);
                """
            )
            columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(tasks)").fetchall()
            }
            if "manual_override" not in columns:
                connection.execute(
                    "ALTER TABLE tasks ADD COLUMN manual_override INTEGER NOT NULL DEFAULT 0"
                )
            if "merged_into" not in columns:
                connection.execute("ALTER TABLE tasks ADD COLUMN merged_into TEXT")
            if "achievement_status" not in columns:
                connection.execute(
                    """
                    ALTER TABLE tasks
                    ADD COLUMN achievement_status TEXT NOT NULL DEFAULT 'not_candidate'
                    """
                )
            if "achievement_source_key" not in columns:
                connection.execute("ALTER TABLE tasks ADD COLUMN achievement_source_key TEXT")
            if "achievement_ref" not in columns:
                connection.execute("ALTER TABLE tasks ADD COLUMN achievement_ref TEXT")
            if "coach_status" not in columns:
                connection.execute(
                    "ALTER TABLE tasks ADD COLUMN coach_status TEXT NOT NULL DEFAULT 'off'"
                )

    @staticmethod
    def _normalize_now(now: datetime | None) -> datetime:
        value = now or datetime.now(UTC)
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row is not None else None

    def _record_activity(
        self,
        connection: sqlite3.Connection,
        task: dict[str, Any],
        now: datetime,
    ) -> None:
        activity_date = now.date().isoformat()
        previous = connection.execute(
            """
            SELECT status, summary
            FROM task_activities
            WHERE task_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (task["id"],),
        ).fetchone()
        if (
            previous is not None
            and previous["status"] == task["status"]
            and previous["summary"] == task["summary"]
            and connection.execute(
                """
                SELECT activity_date
                FROM task_activities
                WHERE task_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (task["id"],),
            ).fetchone()["activity_date"]
            == activity_date
        ):
            return
        connection.execute(
            """
            INSERT INTO task_activities(task_id, activity_date, status, summary, occurred_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                task["id"],
                activity_date,
                task["status"],
                task["summary"],
                now.isoformat(),
            ),
        )

    def _get_connection_task(self, connection: sqlite3.Connection, task_id: str) -> dict[str, Any]:
        task = self._row_to_dict(
            connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        )
        if task is None:
            raise KeyError(task_id)
        return task

    def get(self, task_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as connection:
            return self._row_to_dict(
                connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            )

    def list(self, status: str | None = None) -> builtins.list[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            if status is None:
                rows = connection.execute("SELECT * FROM tasks ORDER BY updated_at DESC").fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM tasks WHERE status = ? ORDER BY updated_at DESC",
                    (status,),
                ).fetchall()
            return [dict(row) for row in rows]

    def activities(self, task_id: str) -> builtins.list[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            self._get_connection_task(connection, task_id)
            rows = connection.execute(
                """
                SELECT id, task_id, activity_date, status, summary, occurred_at
                FROM task_activities
                WHERE task_id = ?
                ORDER BY id
                """,
                (task_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def _find_session_task(
        self, connection: sqlite3.Connection, session_id: str
    ) -> dict[str, Any] | None:
        return self._row_to_dict(
            connection.execute(
                """
                SELECT *
                FROM tasks
                WHERE session_id = ? AND status != 'merged'
                ORDER BY
                    last_turn_index DESC,
                    CASE status
                        WHEN 'active' THEN 0
                        WHEN 'blocked' THEN 1
                        WHEN 'awaiting_confirmation' THEN 2
                        ELSE 3
                    END,
                    updated_at DESC,
                    created_at DESC,
                    id DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
        )

    def _create(
        self,
        connection: sqlite3.Connection,
        *,
        session_id: str,
        source: str,
        title: str,
        summary: str,
        turn_index: int,
        cwd: str,
        status: str,
        now: datetime,
    ) -> dict[str, Any]:
        timestamp = now.isoformat()
        activity_date = now.date().isoformat()
        task_id = str(uuid.uuid4())
        connection.execute(
            """
            INSERT INTO tasks(
                id, session_id, source, title, summary, status, cwd,
                start_date, last_activity_date, last_turn_index, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                session_id,
                source,
                title.strip() or "Untitled task",
                summary.strip() or title.strip() or "Untitled task",
                status,
                cwd,
                activity_date,
                activity_date,
                turn_index,
                timestamp,
                timestamp,
            ),
        )
        task = self._get_connection_task(connection, task_id)
        self._record_activity(connection, task, now)
        return task

    def reconcile_session(
        self,
        *,
        session_id: str,
        source: str,
        title: str,
        turn_index: int,
        cwd: str,
        is_running: bool,
        session_state: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Continue the latest task, or create one for a new post-completion turn."""
        current = self._normalize_now(now)
        timestamp = current.isoformat()
        activity_date = current.date().isoformat()

        with self._lock, self._connect() as connection:
            task = self._find_session_task(connection, session_id)
            creates_new_task = task is None or (
                task["status"] == "completed" and turn_index > task["last_turn_index"]
            )

            if creates_new_task:
                status = self._reconciled_status(is_running, session_state)
                return self._create(
                    connection,
                    session_id=session_id,
                    source=source,
                    title=title,
                    summary=title,
                    turn_index=turn_index,
                    cwd=cwd,
                    status=status,
                    now=current,
                )

            if task is None:
                raise AssertionError("task must exist after reconciliation")

            previous_status = task["status"]
            previous_summary = task["summary"]
            previous_date = task["last_activity_date"]
            if previous_status == "completed" and turn_index <= task["last_turn_index"]:
                return task
            if task["manual_override"] and turn_index <= task["last_turn_index"]:
                return task

            status = self._reconciled_status(is_running, session_state)
            summary = title.strip() or previous_summary
            next_turn_index = max(turn_index, task["last_turn_index"])
            next_cwd = cwd or task["cwd"]
            if (
                source == task["source"]
                and status == previous_status
                and summary == previous_summary
                and next_cwd == task["cwd"]
                and next_turn_index == task["last_turn_index"]
                and activity_date == previous_date
            ):
                return task
            connection.execute(
                """
                UPDATE tasks
                SET source = ?, summary = ?, status = ?, cwd = ?,
                    last_activity_date = ?, last_turn_index = ?, updated_at = ?,
                    manual_override = CASE WHEN ? > ? THEN 0 ELSE manual_override END,
                    completed_at = CASE WHEN ? = 'completed' THEN ? ELSE completed_at END
                WHERE id = ?
                """,
                (
                    source,
                    summary,
                    status,
                    next_cwd,
                    activity_date,
                    next_turn_index,
                    timestamp,
                    next_turn_index,
                    task["last_turn_index"],
                    status,
                    timestamp,
                    task["id"],
                ),
            )
            task = self._get_connection_task(connection, task["id"])
            if (
                status != previous_status
                or summary != previous_summary
                or activity_date != previous_date
            ):
                self._record_activity(connection, task, current)
            return task

    @staticmethod
    def _reconciled_status(is_running: bool, session_state: str) -> str:
        if not is_running or session_state in {"idle", "unknown"}:
            return "awaiting_confirmation"
        if session_state == "waiting":
            return "blocked"
        return "active"

    def split(
        self,
        task_id: str,
        *,
        title: str,
        turn_index: int | None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Create a new active task in the same session and park the old one."""
        current = self._normalize_now(now)
        with self._lock, self._connect() as connection:
            original = self._get_connection_task(connection, task_id)
            next_turn_index = max(original["last_turn_index"], turn_index or 0)
            timestamp = current.isoformat()
            connection.execute(
                "UPDATE tasks SET status = 'awaiting_confirmation', updated_at = ? WHERE id = ?",
                (timestamp, task_id),
            )
            original = self._get_connection_task(connection, task_id)
            self._record_activity(connection, original, current)
            return self._create(
                connection,
                session_id=original["session_id"],
                source=original["source"],
                title=title,
                summary=title,
                turn_index=next_turn_index,
                cwd=original["cwd"],
                status="active",
                now=current,
            )

    def merge(
        self, *, target_id: str, source_id: str, now: datetime | None = None
    ) -> dict[str, Any]:
        """Merge source activity and summary into the target task."""
        if target_id == source_id:
            task = self.get(target_id)
            if task is None:
                raise KeyError(target_id)
            return task

        current = self._normalize_now(now)
        with self._lock, self._connect() as connection:
            target = self._get_connection_task(connection, target_id)
            source = self._get_connection_task(connection, source_id)
            if target["session_id"] != source["session_id"]:
                raise ValueError("Tasks from different sessions cannot be merged")
            timestamp = current.isoformat()
            connection.execute(
                """
                UPDATE tasks
                SET summary = ?, status = ?, last_turn_index = ?,
                    last_activity_date = ?, updated_at = ?, completed_at = NULL
                WHERE id = ?
                """,
                (
                    source["summary"],
                    "active",
                    max(target["last_turn_index"], source["last_turn_index"]),
                    current.date().isoformat(),
                    timestamp,
                    target_id,
                ),
            )
            connection.execute(
                """
                UPDATE tasks
                SET status = 'merged', merged_into = ?, updated_at = ?,
                    completed_at = ?, manual_override = 0
                WHERE id = ?
                """,
                (target_id, timestamp, timestamp, source_id),
            )
            merged = self._get_connection_task(connection, target_id)
            self._record_activity(connection, merged, current)
            merged_source = self._get_connection_task(connection, source_id)
            self._record_activity(connection, merged_source, current)
            return merged

    def confirm(self, task_id: str, now: datetime | None = None) -> dict[str, Any]:
        return self._set_status(task_id, "completed", now)

    def reopen(self, task_id: str, now: datetime | None = None) -> dict[str, Any]:
        return self._set_status(task_id, "active", now, manual_override=True)

    def mark_blocked(self, task_id: str, now: datetime | None = None) -> dict[str, Any]:
        return self._set_status(task_id, "blocked", now)

    def _set_status(
        self,
        task_id: str,
        status: str,
        now: datetime | None = None,
        *,
        manual_override: bool = False,
    ) -> dict[str, Any]:
        current = self._normalize_now(now)
        with self._lock, self._connect() as connection:
            self._get_connection_task(connection, task_id)
            completed_at = current.isoformat() if status == "completed" else None
            achievement_status = (
                "candidate" if status == "completed" and not manual_override else None
            )
            connection.execute(
                """
                UPDATE tasks
                SET status = ?, updated_at = ?, completed_at = ?,
                    last_activity_date = ?, manual_override = ?,
                    achievement_status = CASE
                        WHEN ? IS NOT NULL AND achievement_status = 'not_candidate'
                            THEN ?
                        ELSE achievement_status
                    END,
                    achievement_source_key = CASE
                        WHEN ? IS NOT NULL AND achievement_source_key IS NULL
                            THEN 'task:' || id
                        ELSE achievement_source_key
                    END
                WHERE id = ?
                """,
                (
                    status,
                    current.isoformat(),
                    completed_at,
                    current.date().isoformat(),
                    int(manual_override),
                    achievement_status,
                    achievement_status,
                    achievement_status,
                    task_id,
                ),
            )
            task = self._get_connection_task(connection, task_id)
            self._record_activity(connection, task, current)
            return task

    def mark_achievement_linked(
        self,
        task_id: str,
        *,
        achievement_ref: str,
        coach_status: str | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        current = self._normalize_now(now)
        with self._lock, self._connect() as connection:
            task = self._get_connection_task(connection, task_id)
            connection.execute(
                """
                UPDATE tasks
                SET achievement_status = 'linked',
                    achievement_ref = ?,
                    achievement_source_key = COALESCE(achievement_source_key, 'task:' || id),
                    coach_status = COALESCE(?, coach_status),
                    updated_at = ?
                WHERE id = ?
                """,
                (achievement_ref, coach_status, current.isoformat(), task_id),
            )
            linked = self._get_connection_task(connection, task_id)
            if task["achievement_status"] != "linked":
                self._record_activity(connection, linked, current)
            return linked

    def request_achievement_review(
        self, task_id: str, now: datetime | None = None
    ) -> dict[str, Any]:
        current = self._normalize_now(now)
        with self._lock, self._connect() as connection:
            task = self._get_connection_task(connection, task_id)
            if task["achievement_status"] == "linked":
                return task
            if task["status"] != "completed":
                raise ValueError("Achievement review requires a completed task")
            connection.execute(
                """
                UPDATE tasks
                SET achievement_status = 'pending_intake',
                    achievement_source_key = COALESCE(achievement_source_key, 'task:' || id),
                    coach_status = 'off',
                    updated_at = ?
                WHERE id = ?
                """,
                (current.isoformat(), task_id),
            )
            return self._get_connection_task(connection, task_id)

    def skip_achievement(self, task_id: str, now: datetime | None = None) -> dict[str, Any]:
        current = self._normalize_now(now)
        with self._lock, self._connect() as connection:
            task = self._get_connection_task(connection, task_id)
            if task["achievement_status"] == "linked":
                return task
            if task["status"] != "completed":
                raise ValueError("Achievement review requires a completed task")
            connection.execute(
                """
                UPDATE tasks
                SET achievement_status = 'skipped', coach_status = 'off', updated_at = ?
                WHERE id = ?
                """,
                (current.isoformat(), task_id),
            )
            return self._get_connection_task(connection, task_id)

    def set_coach_status(
        self, task_id: str, status: str, now: datetime | None = None
    ) -> dict[str, Any]:
        if status not in {"off", "needs_confirmation", "pending", "generated", "skipped"}:
            raise ValueError("Invalid coach status")
        current = self._normalize_now(now)
        with self._lock, self._connect() as connection:
            self._get_connection_task(connection, task_id)
            connection.execute(
                "UPDATE tasks SET coach_status = ?, updated_at = ? WHERE id = ?",
                (status, current.isoformat(), task_id),
            )
            return self._get_connection_task(connection, task_id)

    def set_obsidian_path(self, task_id: str, path: str) -> dict[str, Any]:
        with self._lock, self._connect() as connection:
            self._get_connection_task(connection, task_id)
            connection.execute("UPDATE tasks SET obsidian_path = ? WHERE id = ?", (path, task_id))
            return self._get_connection_task(connection, task_id)
