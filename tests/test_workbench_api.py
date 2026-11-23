from unittest.mock import MagicMock, patch


def test_memory_overview_endpoint_returns_aggregate(client):
    expected = {
        "status": "configured",
        "runtime_installed": True,
        "account_id": "pengz4",
        "device": "company",
        "counts": {"profile": 26, "workflow": 10, "total": 36},
        "sync": {
            "last_outcome": "synced",
            "queue_count": 0,
            "last_attempt_at": "2026-11-23T08:00:00Z",
            "last_successful_pull_at": "2026-11-23T08:00:00Z",
            "last_successful_push_at": "2026-11-23T08:00:00Z",
        },
        "today_captures": 2,
        "recent_entries": [],
        "recent_activity": [],
    }
    with patch("src.dashboard_api.get_memory_overview", return_value=expected):
        response = client.get("/api/memory-overview")

    assert response.status_code == 200
    assert response.json()["counts"]["workflow"] == 10
    assert "repository" not in response.json()


def test_obsidian_overview_endpoint_uses_existing_tasks(client):
    tasks = [{"id": "task-1", "status": "completed"}]
    store = MagicMock()
    store.list.return_value = tasks
    expected = {
        "status": "connected",
        "vault_connected": True,
        "git": {
            "branch": "main",
            "dirty_count": 2,
            "last_commit": "vault backup",
            "last_commit_at": "2026-11-23T08:00:00Z",
            "status": "configured",
        },
        "today": {
            "date": "2026-11-23",
            "daily_note_exists": True,
            "daily_note_name": "2026-11-23.md",
        },
        "tasks": {
            "total": 1,
            "active": 0,
            "review": 0,
            "completed": 1,
            "cross_day": 0,
        },
        "achievements": {
            "candidate": 0,
            "pending_intake": 0,
            "linked": 1,
            "skipped": 0,
        },
        "recent_notes": [],
        "links": {"vault": "obsidian://open?vault=Obsidian%20Vault"},
    }
    with (
        patch("src.dashboard_api._get_task_store", return_value=store),
        patch("src.dashboard_api.get_obsidian_overview", return_value=expected) as overview,
    ):
        response = client.get("/api/obsidian-overview")

    assert response.status_code == 200
    assert response.json()["tasks"]["completed"] == 1
    overview.assert_called_once()
    assert overview.call_args.kwargs["tasks"] == tasks
