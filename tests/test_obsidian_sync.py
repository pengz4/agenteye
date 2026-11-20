import json

import pytest

from src.obsidian_sync import (
    TASK_BLOCK_START,
    ObsidianSync,
    ObsidianSyncConfig,
    discover_obsidian_vault,
)


def _task(**overrides):
    value = {
        "id": "12345678-1234-1234-1234-123456789abc",
        "session_id": "session-1",
        "source": "copilot",
        "title": "Add task dashboard",
        "summary": "Implement the confirmation view",
        "status": "awaiting_confirmation",
        "cwd": "/project",
        "start_date": "2026-11-20",
        "last_activity_date": "2026-11-20",
        "last_turn_index": 2,
        "created_at": "2026-11-20T08:00:00+00:00",
        "updated_at": "2026-11-20T08:10:00+00:00",
        "completed_at": None,
        "obsidian_path": None,
    }
    value.update(overrides)
    return value


def test_discovers_single_vault_from_obsidian_app_config(tmp_path):
    config_home = tmp_path / "config"
    vault = tmp_path / "Knowledge"
    vault.mkdir()
    obsidian_dir = config_home / "obsidian"
    obsidian_dir.mkdir(parents=True)
    (obsidian_dir / "obsidian.json").write_text(
        json.dumps({"vaults": {"vault-1": {"path": str(vault)}}}),
        encoding="utf-8",
    )

    assert discover_obsidian_vault(config_home) == vault.resolve()


def test_sync_creates_canonical_task_and_compact_daily_link(tmp_path):
    vault = tmp_path / "Vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / ".obsidian" / "daily-notes.json").write_text(
        json.dumps({"folder": "Journal/Daily", "format": "YYYY-MM-DD"}),
        encoding="utf-8",
    )
    sync = ObsidianSync(ObsidianSyncConfig(vault_path=vault))

    result = sync.sync_task(_task(), activities=[])

    task_file = vault / result.task_path
    daily_file = vault / "Journal" / "Daily" / "2026-11-20.md"
    assert task_file.exists()
    assert daily_file.exists()
    assert "Add task dashboard" in task_file.read_text(encoding="utf-8")
    assert "Implement the confirmation view" in task_file.read_text(encoding="utf-8")
    assert "[[AgentEye/Tasks/" in daily_file.read_text(encoding="utf-8")
    assert "awaiting confirmation" in daily_file.read_text(encoding="utf-8").lower()


def test_sync_updates_managed_block_without_overwriting_user_notes(tmp_path):
    vault = tmp_path / "Vault"
    sync = ObsidianSync(ObsidianSyncConfig(vault_path=vault))
    first = sync.sync_task(_task(), activities=[])
    task_file = vault / first.task_path
    task_file.write_text(
        task_file.read_text(encoding="utf-8") + "\n## My Notes\n\nKeep this line.\n",
        encoding="utf-8",
    )

    sync.sync_task(_task(status="completed"), activities=[])

    content = task_file.read_text(encoding="utf-8")
    assert "completed" in content
    assert "Keep this line." in content
    assert content.count(TASK_BLOCK_START) == 1


def test_daily_link_is_idempotent_and_moves_status_across_days(tmp_path):
    vault = tmp_path / "Vault"
    sync = ObsidianSync(ObsidianSyncConfig(vault_path=vault))
    sync.sync_task(_task(), activities=[])
    sync.sync_task(
        _task(
            status="completed",
            completed_at="2026-11-21T09:00:00+00:00",
            last_activity_date="2026-11-21",
        ),
        activities=[],
    )

    origin = (vault / "2026-11-20.md").read_text(encoding="utf-8")
    next_day = (vault / "2026-11-21.md").read_text(encoding="utf-8")
    assert origin.count("<!-- agenteye-task:12345678-1234-1234-1234-123456789abc -->") == 1
    assert next_day.count("<!-- agenteye-task:12345678-1234-1234-1234-123456789abc -->") == 1
    assert "completed" in next_day.lower()


def test_sync_rejects_task_folder_outside_vault(tmp_path):
    sync = ObsidianSync(
        ObsidianSyncConfig(vault_path=tmp_path / "Vault", task_folder="../escape")
    )

    with pytest.raises(ValueError, match="inside the Vault"):
        sync.sync_task(_task(), activities=[])


def test_sync_rejects_achievement_owned_task_folder(tmp_path):
    sync = ObsidianSync(
        ObsidianSyncConfig(vault_path=tmp_path / "Vault", task_folder="Achievements/Tasks")
    )

    with pytest.raises(ValueError, match="achievement-owned"):
        sync.sync_task(_task(), activities=[])


def test_sync_rejects_achievement_owned_daily_folder(tmp_path):
    vault = tmp_path / "Vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / ".obsidian" / "daily-notes.json").write_text(
        '{"folder":"Achievements/Daily","format":"YYYY-MM-DD"}',
        encoding="utf-8",
    )
    sync = ObsidianSync(ObsidianSyncConfig(vault_path=vault))

    with pytest.raises(ValueError, match="achievement-owned"):
        sync.sync_task(_task(), activities=[])


def test_sync_rejects_symlink_into_achievement_owned_folder(tmp_path):
    vault = tmp_path / "Vault"
    (vault / "Achievements" / "Daily").mkdir(parents=True)
    (vault / "AgentEye").mkdir(parents=True)
    (vault / "AgentEye" / "Tasks").symlink_to(
        vault / "Achievements" / "Daily", target_is_directory=True
    )
    sync = ObsidianSync(
        ObsidianSyncConfig(vault_path=vault, task_folder="AgentEye/Tasks")
    )

    with pytest.raises(ValueError, match="achievement-owned"):
        sync.sync_task(_task(), activities=[])


def test_sync_never_writes_transcript_fields(tmp_path):
    sync = ObsidianSync(ObsidianSyncConfig(vault_path=tmp_path / "Vault"))
    task = _task(transcript="SECRET conversation", tool_output="PRIVATE code")

    result = sync.sync_task(task, activities=[])

    content = (sync.config.vault_path / result.task_path).read_text(encoding="utf-8")
    assert "SECRET conversation" not in content
    assert "PRIVATE code" not in content


def test_malformed_managed_block_preserves_existing_content(tmp_path):
    vault = tmp_path / "Vault"
    sync = ObsidianSync(ObsidianSyncConfig(vault_path=vault))
    first = sync.sync_task(_task(), activities=[])
    task_file = vault / first.task_path
    task_file.write_text(
        "# Task\n\n"
        "<!-- agenteye:task-managed:start -->\n"
        "broken managed content\n\n"
        "## User Notes\n\nNever delete this.\n",
        encoding="utf-8",
    )

    sync.sync_task(_task(status="completed"), activities=[])

    content = task_file.read_text(encoding="utf-8")
    assert "Never delete this." in content
    assert content.count(TASK_BLOCK_START) == 2
    assert content.index("completed") < content.index(TASK_BLOCK_START, content.index(TASK_BLOCK_START) + 1)


def test_atomic_write_does_not_follow_predictable_symlink(tmp_path):
    vault = tmp_path / "Vault"
    outside = tmp_path / "outside.txt"
    outside.write_text("safe", encoding="utf-8")
    sync = ObsidianSync(ObsidianSyncConfig(vault_path=vault))
    task = _task()
    relative, final = sync._task_path(task)
    final.parent.mkdir(parents=True, exist_ok=True)
    predictable_temp = final.with_name(f".{final.name}.agenteye.tmp")
    predictable_temp.symlink_to(outside)

    sync.sync_task(task, activities=[])

    assert outside.read_text(encoding="utf-8") == "safe"
    assert (vault / relative).exists()


def test_merged_task_removes_daily_link_and_marks_canonical_note(tmp_path):
    vault = tmp_path / "Vault"
    sync = ObsidianSync(ObsidianSyncConfig(vault_path=vault))
    source = _task()
    sync.sync_task(source, activities=[])

    sync.sync_task(
        {
            **source,
            "status": "merged",
            "merged_into": "87654321-1234-1234-1234-123456789abc",
        },
        activities=[
            {
                "activity_date": source["last_activity_date"],
                "status": "merged",
                "summary": source["summary"],
            }
        ],
    )

    daily = (vault / f"{source['last_activity_date']}.md").read_text(encoding="utf-8")
    task_file = sync._task_path(source)[1].read_text(encoding="utf-8")
    assert f"agenteye-task:{source['id']}" not in daily
    assert "merged" in task_file.lower()
    assert "87654321-1234-1234-1234-123456789abc" in task_file
