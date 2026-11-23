import json
from datetime import UTC, datetime

from src.memory_workbench import get_memory_overview


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_memory_overview_aggregates_counts_sync_and_safe_recent_activity(tmp_path):
    home = tmp_path / "home"
    runtime = tmp_path / "runtime"
    repository = home / ".copilot" / "memu" / "repository"
    (runtime / "bin").mkdir(parents=True)
    (runtime / "bin" / "personal-memory-mcp.js").write_text("", encoding="utf-8")
    _write_json(
        home / ".copilot" / "mcp-config.json",
        {
            "mcpServers": {
                "personal-agent-memory": {
                    "env": {
                        "MEMORY_ACCOUNT_ID": "pengz4",
                        "MEMORY_DEVICE": "company",
                        "MEMORY_REPOSITORY_DIR": str(repository),
                        "MEMORY_REMOTE_URL": "git@github.com:pengz4/private.git",
                    }
                }
            }
        },
    )
    entries = repository / "accounts" / "pengz4" / "memory" / "entries"
    _write_json(
        entries / "profile" / "profile-1.json",
        {
            "kind": "profile",
            "title": "Role evolution pattern",
            "content": "PRIVATE BODY",
            "updated_at": "2026-11-20T08:00:00Z",
        },
    )
    _write_json(
        entries / "workflow" / "workflow-1.json",
        {
            "kind": "workflow",
            "title": "Task review workflow",
            "content": "SECRET PROCEDURE",
            "updated_at": "2026-11-23T08:00:00Z",
        },
    )
    _write_json(
        home / ".copilot" / "memu" / "sync" / "accounts" / "pengz4"
        / "management-status.json",
        {
            "last_outcome": "synced",
            "queue_count": 0,
            "last_attempt_at": "2026-11-23T08:30:00Z",
            "last_successful_push_at": "2026-11-23T08:31:00Z",
            "last_successful_pull_at": "2026-11-23T08:30:30Z",
        },
    )
    audit = home / ".copilot" / "memu" / "audit" / "accounts" / "pengz4"
    audit.mkdir(parents=True)
    (audit / "capture-events.jsonl").write_text(
        json.dumps(
            {
                "receipt_id": "receipt-1",
                "safe_summary": "Persist AgentEye workflow",
                "action": "auto-write",
                "trigger": "task-outcome",
                "created_at": "2026-11-23T09:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = get_memory_overview(
        {"stack": {"memory_root": str(runtime)}},
        home=home,
        now=datetime(2026, 11, 23, 10, tzinfo=UTC),
    )

    serialized = json.dumps(result)
    assert result["status"] == "configured"
    assert result["account_id"] == "pengz4"
    assert result["device"] == "company"
    assert result["counts"] == {
        "profile": 1,
        "workflow": 1,
        "total": 2,
        "archived": 0,
    }
    assert result["sync"]["queue_count"] == 0
    assert result["today_captures"] == 1
    assert result["recent_activity"][0]["summary"] == "Persist AgentEye workflow"
    assert "PRIVATE BODY" not in serialized
    assert "SECRET PROCEDURE" not in serialized
    assert "git@github.com" not in serialized
    assert str(repository) not in serialized


def test_memory_overview_is_explicit_when_not_configured(tmp_path):
    result = get_memory_overview(
        {"stack": {}},
        home=tmp_path,
        now=datetime(2026, 11, 23, 10, tzinfo=UTC),
    )

    assert result["status"] == "not_configured"
    assert result["counts"]["total"] == 0
    assert result["recent_activity"] == []


def test_memory_overview_merges_active_device_entries_and_excludes_archived(tmp_path):
    home = tmp_path / "home"
    shared = home / ".copilot" / "memu" / "repository"
    device = home / ".copilot" / "memu" / "device-repository"
    _write_json(
        home / ".copilot" / "mcp-config.json",
        {
            "mcpServers": {
                "personal-agent-memory": {
                    "env": {
                        "MEMORY_ACCOUNT_ID": "pengz4",
                        "MEMORY_DEVICE": "company",
                        "MEMORY_REPOSITORY_DIR": str(shared),
                    }
                }
            }
        },
    )
    _write_json(
        shared / "accounts" / "pengz4" / "memory" / "entries" / "workflow"
        / "shared-active.json",
        {"kind": "workflow", "title": "Shared", "lifecycle": {"status": "active"}},
    )
    _write_json(
        shared / "accounts" / "pengz4" / "memory" / "entries" / "workflow"
        / "shared-archived.json",
        {"kind": "workflow", "title": "Archived", "lifecycle": {"status": "archived"}},
    )
    _write_json(
        device / "accounts" / "pengz4" / "memory" / "entries" / "environment"
        / "device-active.json",
        {"kind": "environment", "title": "Device", "lifecycle": {"status": "active"}},
    )

    result = get_memory_overview(
        {"stack": {}},
        home=home,
        now=datetime(2026, 11, 23, 10, tzinfo=UTC),
    )

    assert result["counts"]["total"] == 2
    assert result["counts"]["workflow"] == 1
    assert result["counts"]["environment"] == 1
    assert result["counts"]["archived"] == 1
