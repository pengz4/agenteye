import json
from datetime import UTC, datetime
from unittest.mock import patch

from src.obsidian_workbench import get_obsidian_overview


def _task(task_id, **overrides):
    task = {
        "id": task_id,
        "title": f"Task {task_id}",
        "status": "completed",
        "achievement_status": "linked",
        "start_date": "2026-11-20",
        "last_activity_date": "2026-11-23",
        "updated_at": "2026-11-23T09:00:00Z",
        "obsidian_path": f"AgentEye/Tasks/task-{task_id}.md",
    }
    task.update(overrides)
    return task


def test_obsidian_overview_aggregates_vault_git_daily_task_and_achievement_state(
    tmp_path,
):
    vault = tmp_path / "Obsidian Vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / ".git").mkdir()
    (vault / ".obsidian" / "daily-notes.json").write_text(
        json.dumps({"folder": "_Daily Notes", "format": "YYYY-MM-DD"}),
        encoding="utf-8",
    )
    (vault / "_Daily Notes").mkdir()
    (vault / "_Daily Notes" / "2026-11-23.md").write_text(
        "PRIVATE NOTE BODY", encoding="utf-8"
    )
    (vault / "AgentEye" / "Tasks").mkdir(parents=True)
    (vault / "AgentEye" / "Tasks" / "task-a.md").write_text(
        "PRIVATE TASK BODY", encoding="utf-8"
    )
    (vault / "Achievements" / "Daily").mkdir(parents=True)
    (vault / "Achievements" / "Daily" / "2026-11-23-achievement-work-summary.md").write_text(
        "PRIVATE ACHIEVEMENT BODY", encoding="utf-8"
    )
    tasks = [
        _task("a"),
        _task(
            "b",
            status="awaiting_confirmation",
            achievement_status="candidate",
            last_activity_date="2026-11-23",
        ),
        _task("c", achievement_status="skipped", start_date="2026-11-23"),
    ]
    git_result = type(
        "Result",
        (),
        {
            "returncode": 0,
            "stdout": "main\n82daa11|2026-11-23T08:00:00Z|vault backup\n M Private/secret.md\n M Porsche/data.csv\n",
            "stderr": "",
        },
    )()

    with patch("src.obsidian_workbench.subprocess.run", return_value=git_result):
        result = get_obsidian_overview(
            {"obsidian": {"enabled": True}, "stack": {"obsidian_vault": str(vault)}},
            tasks=tasks,
            now=datetime(2026, 11, 23, 10, tzinfo=UTC),
        )

    serialized = json.dumps(result)
    assert result["status"] == "connected"
    assert result["git"]["branch"] == "main"
    assert result["git"]["dirty_count"] == 2
    assert result["today"]["daily_note_exists"] is True
    assert result["tasks"]["total"] == 3
    assert result["tasks"]["cross_day"] == 2
    assert result["achievements"] == {
        "candidate": 1,
        "linked": 1,
        "skipped": 1,
        "pending_intake": 0,
        "queued_intake": 0,
    }
    assert result["links"]["daily_note"].startswith("obsidian://open?")
    assert result["links"]["achievements"].startswith("obsidian://open?")
    assert "Private/secret.md" not in serialized
    assert "PRIVATE NOTE BODY" not in serialized
    assert str(vault) not in serialized


def test_obsidian_overview_is_explicit_when_unconfigured(tmp_path):
    result = get_obsidian_overview(
        {"obsidian": {"enabled": False}, "stack": {}},
        tasks=[],
        now=datetime(2026, 11, 23, 10, tzinfo=UTC),
    )

    assert result["status"] == "not_configured"
    assert result["tasks"]["total"] == 0
    assert result["links"] == {}


def test_obsidian_overview_rejects_absolute_daily_folder(tmp_path):
    vault = tmp_path / "Obsidian Vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / ".obsidian" / "daily-notes.json").write_text(
        json.dumps({"folder": "/private/notes", "format": "YYYY-MM-DD"}),
        encoding="utf-8",
    )

    result = get_obsidian_overview(
        {
            "obsidian": {"enabled": True},
            "stack": {"obsidian_vault": str(vault)},
        },
        tasks=[],
        now=datetime(2026, 11, 23, 10, tzinfo=UTC),
    )

    assert result["status"] == "invalid_configuration"
    assert "daily_note" not in result["links"]
    assert "/private/notes" not in json.dumps(result)


def test_git_summary_returns_hash_and_time_without_commit_subject(tmp_path):
    vault = tmp_path / "Obsidian Vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / ".git").mkdir()
    git_result = type(
        "Result",
        (),
        {
            "returncode": 0,
            "stdout": "## main...origin/main\n M note.md\n82daa11|2026-11-23T08:00:00Z|SECRET PRIVATE SUBJECT\n",
            "stderr": "",
        },
    )()
    with patch("src.obsidian_workbench.subprocess.run", return_value=git_result):
        result = get_obsidian_overview(
            {
                "obsidian": {"enabled": True},
                "stack": {"obsidian_vault": str(vault)},
            },
            tasks=[],
            now=datetime(2026, 11, 23, 10, tzinfo=UTC),
        )

    assert result["git"]["last_commit"] == "82daa11"
    assert "SECRET PRIVATE SUBJECT" not in json.dumps(result)


def test_recent_notes_uses_configured_task_and_daily_folders(tmp_path):
    vault = tmp_path / "Obsidian Vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / ".obsidian" / "daily-notes.json").write_text(
        json.dumps({"folder": "Journal/Daily", "format": "YYYY-MM-DD"}),
        encoding="utf-8",
    )
    (vault / "Agent" / "Tasks").mkdir(parents=True)
    (vault / "Journal" / "Daily").mkdir(parents=True)
    (vault / "Agent" / "Tasks" / "custom-task.md").write_text("task", encoding="utf-8")
    (vault / "Journal" / "Daily" / "2026-11-23.md").write_text("daily", encoding="utf-8")

    result = get_obsidian_overview(
        {
            "obsidian": {"enabled": True, "task_folder": "Agent/Tasks"},
            "stack": {"obsidian_vault": str(vault)},
        },
        tasks=[],
        now=datetime(2026, 11, 23, 10, tzinfo=UTC),
    )

    relative_paths = {note["relative_path"] for note in result["recent_notes"]}
    assert "Agent/Tasks/custom-task.md" in relative_paths
    assert "Journal/Daily/2026-11-23.md" in relative_paths


def test_obsidian_overview_returns_fast_while_git_refreshes_in_background(tmp_path):
    vault = tmp_path / "Obsidian Vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / ".git").mkdir()
    (vault / ".obsidian" / "daily-notes.json").write_text(
        json.dumps({"folder": "", "format": "YYYY-MM-DD"}),
        encoding="utf-8",
    )
    with patch("src.obsidian_workbench.threading.Thread") as thread:
        result = get_obsidian_overview(
            {
                "obsidian": {"enabled": True},
                "stack": {"obsidian_vault": str(vault)},
            },
            tasks=[],
            now=datetime(2026, 11, 23, 10, tzinfo=UTC),
            git_async=True,
        )

    assert result["status"] == "connected"
    assert result["git"]["status"] == "refreshing"
    thread.assert_called_once()
    thread.return_value.start.assert_called_once()
