from unittest.mock import patch

from src.task_store import TaskStore


ACTIVE_SESSION = {
    "id": "session-1",
    "cwd": "/project",
    "repository": None,
    "branch": None,
    "summary": "First dashboard request",
    "created_at": "2026-11-20T08:00:00Z",
    "updated_at": "2026-11-20T08:00:00Z",
    "is_running": True,
    "state": "working",
    "source": "copilot",
    "turn_count": 1,
    "intent": "",
}


def _session_detail():
    return {
        "turns": [
            {
                "turn_index": 0,
                "user_message": "Build an Obsidian task dashboard",
                "assistant_response": None,
            }
        ],
        "checkpoints": [],
        "refs": [],
        "recent_output": [],
        "tool_counts": [],
        "files": [],
    }


def test_task_sync_creates_task_from_latest_user_turn(client, tmp_path):
    with (
        patch("src.dashboard_api.TASK_STORE_DB", str(tmp_path / "tasks.db")),
        patch("src.dashboard_api._build_session_list", return_value=[ACTIVE_SESSION]),
        patch("src.dashboard_api.api_session_detail", side_effect=lambda _sid: _session_detail()),
    ):
        response = client.post("/api/tasks/sync")

    assert response.status_code == 200
    task = response.json()["tasks"][0]
    assert task["session_id"] == "session-1"
    assert task["title"] == "First dashboard request"
    assert task["summary"] == "First dashboard request"
    assert "Build an Obsidian task dashboard" not in str(task)
    assert task["status"] == "active"
    assert task["last_turn_index"] == 0


def test_task_sync_enriches_session_identity(client, tmp_path):
    session = {
        **ACTIVE_SESSION,
        "repository": "porsche/personal-agent-skills",
        "branch": "main",
    }
    with (
        patch("src.dashboard_api.TASK_STORE_DB", str(tmp_path / "tasks.db")),
        patch("src.dashboard_api._build_session_list", return_value=[session]),
        patch("src.dashboard_api.api_session_detail", side_effect=lambda _sid: _session_detail()),
    ):
        response = client.post("/api/tasks/sync")

    task = response.json()["tasks"][0]
    assert task["repository"] == "porsche/personal-agent-skills"
    assert task["branch"] == "main"
    assert task["session_short_id"] == "sessio"


def test_idle_task_is_listed_as_awaiting_confirmation(client, tmp_path):
    idle = {**ACTIVE_SESSION, "state": "idle"}
    with (
        patch("src.dashboard_api.TASK_STORE_DB", str(tmp_path / "tasks.db")),
        patch("src.dashboard_api._build_session_list", return_value=[idle]),
        patch("src.dashboard_api.api_session_detail", side_effect=lambda _sid: _session_detail()),
    ):
        client.post("/api/tasks/sync")
        response = client.get("/api/tasks?status=awaiting_confirmation")

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_task_list_does_not_rebuild_all_sessions(client, tmp_path):
    with (
        patch("src.dashboard_api.TASK_STORE_DB", str(tmp_path / "tasks.db")),
        patch(
            "src.dashboard_api._build_session_list",
            side_effect=AssertionError("task list must stay read-only and cheap"),
        ),
    ):
        response = client.get("/api/tasks")

    assert response.status_code == 200
    assert response.json() == []


def test_task_list_preserves_claude_identity_without_full_rebuild(client, tmp_path):
    tasks_path = tmp_path / "tasks.db"
    store = TaskStore(tasks_path)
    store.reconcile_session(
        session_id="cc:claude-1",
        source="claude",
        title="Claude review",
        turn_index=1,
        cwd="/work/my-project",
        is_running=True,
        session_state="idle",
    )
    claude_session = {
        "id": "cc:claude-1",
        "repository": "owner/my-project",
        "branch": "feature/task-context",
    }
    with (
        patch("src.dashboard_api.TASK_STORE_DB", str(tasks_path)),
        patch(
            "src.dashboard_api.get_claude_session_identities",
            return_value=[claude_session],
        ),
        patch(
            "src.dashboard_api._build_session_list",
            side_effect=AssertionError("task list must not scan every session"),
        ),
    ):
        response = client.get("/api/tasks")

    assert response.status_code == 200
    assert response.json()[0]["repository"] == "owner/my-project"
    assert response.json()[0]["branch"] == "feature/task-context"


def test_confirm_reopen_split_and_merge_task_actions(client, tmp_path):
    with (
        patch("src.dashboard_api.TASK_STORE_DB", str(tmp_path / "tasks.db")),
        patch("src.dashboard_api._build_session_list", return_value=[ACTIVE_SESSION]),
        patch("src.dashboard_api.api_session_detail", side_effect=lambda _sid: _session_detail()),
    ):
        original = client.post("/api/tasks/sync").json()["tasks"][0]
        confirmed = client.post(f"/api/task/{original['id']}/confirm")
        reopened = client.post(f"/api/task/{original['id']}/reopen")
        split = client.post(
            f"/api/task/{original['id']}/split",
            json={"title": "Write Obsidian docs", "turn_index": 1},
        )
        merged = client.post(
            "/api/task/merge",
            json={"target_id": original["id"], "source_id": split.json()["id"]},
        )

    assert confirmed.json()["status"] == "completed"
    assert reopened.json()["status"] == "active"
    assert split.status_code == 200
    assert merged.json()["id"] == original["id"]


def test_obsidian_settings_are_persisted(client, tmp_path):
    config_path = tmp_path / "dashboard-config.json"
    with patch("src.dashboard_api.DASHBOARD_CONFIG_PATH", str(config_path)):
        response = client.put(
            "/api/settings",
            json={
                "obsidian_enabled": True,
                "obsidian_vault_path": "/tmp/My Vault",
                "obsidian_task_folder": "AgentEye/Tasks",
            },
        )
        current = client.get("/api/settings")

    assert response.status_code == 200
    assert response.json()["obsidian_enabled"] is True
    assert current.json()["obsidian_vault_path"] == "/tmp/My Vault"
    assert current.json()["obsidian_task_folder"] == "AgentEye/Tasks"


def test_task_actions_return_404_for_unknown_id(client, tmp_path):
    with patch("src.dashboard_api.TASK_STORE_DB", str(tmp_path / "tasks.db")):
        response = client.post("/api/task/missing/confirm")

    assert response.status_code == 404


def test_obsidian_checkbox_confirms_task(client, tmp_path):
    config_path = tmp_path / "dashboard-config.json"
    vault = tmp_path / "Vault"
    (vault / ".obsidian").mkdir(parents=True)
    idle_session = {**ACTIVE_SESSION, "state": "idle"}
    with (
        patch("src.dashboard_api.DASHBOARD_CONFIG_PATH", str(config_path)),
        patch("src.dashboard_api.TASK_STORE_DB", str(tmp_path / "tasks.db")),
        patch("src.dashboard_api._build_session_list", return_value=[idle_session]),
        patch("src.dashboard_api.api_session_detail", side_effect=lambda _sid: _session_detail()),
    ):
        client.put(
            "/api/settings",
            json={
                "obsidian_enabled": True,
                "obsidian_vault_path": str(vault),
                "obsidian_task_folder": "AgentEye/Tasks",
            },
        )
        initial = client.post("/api/tasks/sync").json()["tasks"][0]
        daily = vault / f"{initial['last_activity_date']}.md"
        content = daily.read_text(encoding="utf-8")
        daily.write_text(
            content.replace(
                f"<!-- agenteye-task:{initial['id']} -->",
                f"<!-- agenteye-task:{initial['id']} -->",
            ).replace("- [ ] <!-- agenteye-task:", "- [x] <!-- agenteye-task:", 1),
            encoding="utf-8",
        )

        completed = client.post("/api/tasks/sync").json()["tasks"][0]

    assert completed["status"] == "completed"


def test_dashboard_confirmation_is_published_before_obsidian_feedback(client, tmp_path):
    config_path = tmp_path / "dashboard-config.json"
    vault = tmp_path / "Vault"
    (vault / ".obsidian").mkdir(parents=True)
    idle_session = {**ACTIVE_SESSION, "state": "idle"}
    with (
        patch("src.dashboard_api.DASHBOARD_CONFIG_PATH", str(config_path)),
        patch("src.dashboard_api.TASK_STORE_DB", str(tmp_path / "tasks.db")),
        patch("src.dashboard_api._build_session_list", return_value=[idle_session]),
        patch("src.dashboard_api.api_session_detail", side_effect=lambda _sid: _session_detail()),
    ):
        client.put(
            "/api/settings",
            json={"obsidian_enabled": True, "obsidian_vault_path": str(vault)},
        )
        task = client.post("/api/tasks/sync").json()["tasks"][0]

        confirmed = client.post(f"/api/task/{task['id']}/confirm").json()
        stored = client.get("/api/tasks").json()[0]
        daily = (vault / f"{task['last_activity_date']}.md").read_text(encoding="utf-8")

    assert confirmed["status"] == "completed"
    assert stored["status"] == "completed"
    assert "- [x]" in daily


def test_dashboard_reopen_remains_active_on_next_idle_sync(client, tmp_path):
    idle_session = {**ACTIVE_SESSION, "state": "idle"}
    with (
        patch("src.dashboard_api.TASK_STORE_DB", str(tmp_path / "tasks.db")),
        patch("src.dashboard_api._build_session_list", return_value=[idle_session]),
        patch("src.dashboard_api.api_session_detail", side_effect=lambda _sid: _session_detail()),
    ):
        task = client.post("/api/tasks/sync").json()["tasks"][0]
        client.post(f"/api/task/{task['id']}/confirm")
        client.post(f"/api/task/{task['id']}/reopen")

        reopened = client.post("/api/tasks/sync").json()["tasks"][0]

    assert reopened["status"] == "active"


def test_merged_tombstone_does_not_overwrite_target_after_session_closes(
    client, tmp_path
):
    with (
        patch("src.dashboard_api.TASK_STORE_DB", str(tmp_path / "tasks.db")),
        patch("src.dashboard_api._build_session_list", return_value=[ACTIVE_SESSION]),
        patch("src.dashboard_api.api_session_detail", side_effect=lambda _sid: _session_detail()),
    ):
        original = client.post("/api/tasks/sync").json()["tasks"][0]
        split = client.post(
            f"/api/task/{original['id']}/split",
            json={"title": "Docs", "turn_index": 1},
        ).json()
        client.post(
            "/api/task/merge",
            json={"target_id": original["id"], "source_id": split["id"]},
        )
        from src.dashboard_api import _get_task_store

        store = _get_task_store()
        store.reconcile_session(
            session_id="session-1",
            source="copilot",
            title="Current target summary",
            turn_index=2,
            cwd="/project",
            is_running=True,
            session_state="working",
        )

    with (
        patch("src.dashboard_api.TASK_STORE_DB", str(tmp_path / "tasks.db")),
        patch("src.dashboard_api._build_session_list", return_value=[]),
    ):
        client.post("/api/tasks/sync")
        target = client.get(f"/api/tasks").json()
        surviving = next(task for task in target if task["id"] == original["id"])

    assert surviving["summary"] == "Current target summary"


def test_task_sync_links_existing_achievement_and_applies_coach_ask_mode(
    client, tmp_path
):
    task_db = tmp_path / "tasks.db"
    ledger = tmp_path / "ACHIEVEMENT_LOG.md"
    outbox = tmp_path / "intake.jsonl"
    coach_outbox = tmp_path / "coach.jsonl"
    config_path = tmp_path / "dashboard-config.json"
    idle_session = {**ACTIVE_SESSION, "state": "idle"}
    with (
        patch("src.dashboard_api.TASK_STORE_DB", str(task_db)),
        patch("src.dashboard_api.ACHIEVEMENT_LEDGER_PATH", str(ledger)),
        patch("src.dashboard_api.ACHIEVEMENT_INTAKE_OUTBOX", str(outbox)),
        patch("src.dashboard_api.AI_COACH_OUTBOX", str(coach_outbox)),
        patch("src.dashboard_api.DASHBOARD_CONFIG_PATH", str(config_path)),
        patch("src.dashboard_api._build_session_list", return_value=[idle_session]),
        patch("src.dashboard_api.api_session_detail", side_effect=lambda _sid: _session_detail()),
    ):
        task = client.post("/api/tasks/sync").json()["tasks"][0]
        task = client.post(f"/api/task/{task['id']}/confirm").json()
        ledger.write_text(
            f"""
### 2026-11-20 — Built dashboard
- Evidence: verified API and UI; `{task['achievement_source_key']}`
""",
            encoding="utf-8",
        )

        linked = client.post("/api/tasks/sync").json()["tasks"][0]

    assert linked["achievement_status"] == "linked"
    assert linked["achievement_ref"] == "### 2026-11-20 — Built dashboard"
    assert linked["coach_status"] == "needs_confirmation"
    assert not outbox.exists()
    assert not coach_outbox.exists()


def test_achievement_request_is_idempotent_and_skip_only_changes_intake_state(
    client, tmp_path
):
    task_db = tmp_path / "tasks.db"
    outbox = tmp_path / "intake.jsonl"
    ledger = tmp_path / "ACHIEVEMENT_LOG.md"
    idle_session = {**ACTIVE_SESSION, "state": "idle"}
    with (
        patch("src.dashboard_api.TASK_STORE_DB", str(task_db)),
        patch("src.dashboard_api.ACHIEVEMENT_LEDGER_PATH", str(ledger)),
        patch("src.dashboard_api.ACHIEVEMENT_INTAKE_OUTBOX", str(outbox)),
        patch("src.dashboard_api._build_session_list", return_value=[idle_session]),
        patch("src.dashboard_api.api_session_detail", side_effect=lambda _sid: _session_detail()),
    ):
        task = client.post("/api/tasks/sync").json()["tasks"][0]
        task = client.post(f"/api/task/{task['id']}/confirm").json()
        first = client.post(f"/api/task/{task['id']}/achievement/request")
        second = client.post(f"/api/task/{task['id']}/achievement/request")
        skipped = client.post(f"/api/task/{task['id']}/achievement/skip")

    assert first.status_code == second.status_code == 200
    assert second.json()["achievement_status"] == "pending_intake"
    assert skipped.json()["achievement_status"] == "skipped"
    assert skipped.json()["status"] == "completed"
    assert len(outbox.read_text(encoding="utf-8").splitlines()) == 1


def test_coach_mode_auto_creates_one_downstream_request(client, tmp_path):
    task_db = tmp_path / "tasks.db"
    ledger = tmp_path / "ACHIEVEMENT_LOG.md"
    coach_outbox = tmp_path / "coach.jsonl"
    config_path = tmp_path / "dashboard-config.json"
    idle_session = {**ACTIVE_SESSION, "state": "idle"}
    with (
        patch("src.dashboard_api.TASK_STORE_DB", str(task_db)),
        patch("src.dashboard_api.ACHIEVEMENT_LEDGER_PATH", str(ledger)),
        patch("src.dashboard_api.ACHIEVEMENT_INTAKE_OUTBOX", str(tmp_path / "intake.jsonl")),
        patch("src.dashboard_api.AI_COACH_OUTBOX", str(coach_outbox)),
        patch("src.dashboard_api.DASHBOARD_CONFIG_PATH", str(config_path)),
        patch("src.dashboard_api._build_session_list", return_value=[idle_session]),
        patch("src.dashboard_api.api_session_detail", side_effect=lambda _sid: _session_detail()),
    ):
        client.put("/api/settings", json={"coach_mode": "auto"})
        task = client.post("/api/tasks/sync").json()["tasks"][0]
        task = client.post(f"/api/task/{task['id']}/confirm").json()
        ledger.write_text(
            f"### 2026-11-20 — AI agent workflow\n- Evidence: `"
            f"{task['achievement_source_key']}`\n",
            encoding="utf-8",
        )
        linked = client.post("/api/tasks/sync").json()["tasks"][0]
        client.post("/api/tasks/sync")

    assert linked["coach_status"] == "pending"
    assert len(coach_outbox.read_text(encoding="utf-8").splitlines()) == 1


def test_settings_reject_invalid_coach_mode(client, tmp_path):
    config_path = tmp_path / "dashboard-config.json"
    with patch("src.dashboard_api.DASHBOARD_CONFIG_PATH", str(config_path)):
        response = client.put("/api/settings", json={"coach_mode": "sometimes"})

    assert response.status_code == 400


def test_control_plane_endpoint_returns_runtime_overview(client, tmp_path):
    with patch(
        "src.dashboard_api.inspect_control_plane",
        return_value={"runtimes": [{"name": "Agent Eye", "status": "reachable"}]},
    ):
        response = client.get("/api/control-plane")

    assert response.status_code == 200
    assert response.json()["runtimes"][0]["name"] == "Agent Eye"


def test_start_coach_endpoint_uses_configured_runtime(client):
    expected = {
        "started": True,
        "status": "reachable",
        "url": "http://127.0.0.1:8765/",
    }
    with patch("src.dashboard_api.start_coach", return_value=expected):
        response = client.post("/api/coach/start")

    assert response.status_code == 200
    assert response.json() == expected


def test_completed_candidate_is_queued_for_intake_automatically(client, tmp_path):
    task_db = tmp_path / "tasks.db"
    outbox = tmp_path / "intake.jsonl"
    idle_session = {**ACTIVE_SESSION, "state": "idle"}
    with (
        patch("src.dashboard_api.TASK_STORE_DB", str(task_db)),
        patch("src.dashboard_api.ACHIEVEMENT_LEDGER_PATH", str(tmp_path / "ledger.md")),
        patch("src.dashboard_api.ACHIEVEMENT_INTAKE_OUTBOX", str(outbox)),
        patch("src.dashboard_api._build_session_list", return_value=[idle_session]),
        patch("src.dashboard_api.api_session_detail", side_effect=lambda _sid: _session_detail()),
    ):
        task = client.post("/api/tasks/sync").json()["tasks"][0]
        client.post(f"/api/task/{task['id']}/confirm")
        queued = client.post("/api/tasks/sync").json()["tasks"][0]
        client.post("/api/tasks/sync")

    assert queued["achievement_status"] == "pending_intake"
    assert len(outbox.read_text(encoding="utf-8").splitlines()) == 1


def test_coach_off_mode_rejects_direct_request(client, tmp_path):
    task_db = tmp_path / "tasks.db"
    ledger = tmp_path / "ACHIEVEMENT_LOG.md"
    coach_outbox = tmp_path / "coach.jsonl"
    config_path = tmp_path / "dashboard-config.json"
    idle_session = {**ACTIVE_SESSION, "state": "idle"}
    with (
        patch("src.dashboard_api.TASK_STORE_DB", str(task_db)),
        patch("src.dashboard_api.ACHIEVEMENT_LEDGER_PATH", str(ledger)),
        patch("src.dashboard_api.ACHIEVEMENT_INTAKE_OUTBOX", str(tmp_path / "intake.jsonl")),
        patch("src.dashboard_api.AI_COACH_OUTBOX", str(coach_outbox)),
        patch("src.dashboard_api.DASHBOARD_CONFIG_PATH", str(config_path)),
        patch("src.dashboard_api._build_session_list", return_value=[idle_session]),
        patch("src.dashboard_api.api_session_detail", side_effect=lambda _sid: _session_detail()),
    ):
        client.put("/api/settings", json={"coach_mode": "off"})
        task = client.post("/api/tasks/sync").json()["tasks"][0]
        task = client.post(f"/api/task/{task['id']}/confirm").json()
        ledger.write_text(
            f"### 2026-11-20 — Linked\n- Evidence: `{task['achievement_source_key']}`\n",
            encoding="utf-8",
        )
        linked = client.post("/api/tasks/sync").json()["tasks"][0]
        response = client.post(f"/api/task/{task['id']}/coach/request")

    assert linked["coach_status"] == "off"
    assert response.status_code == 409
    assert not coach_outbox.exists()


def test_pending_intake_request_is_retried_after_outbox_failure(client, tmp_path):
    task_db = tmp_path / "tasks.db"
    outbox = tmp_path / "intake.jsonl"
    idle_session = {**ACTIVE_SESSION, "state": "idle"}
    with (
        patch("src.dashboard_api.TASK_STORE_DB", str(task_db)),
        patch("src.dashboard_api.ACHIEVEMENT_LEDGER_PATH", str(tmp_path / "ledger.md")),
        patch("src.dashboard_api.ACHIEVEMENT_INTAKE_OUTBOX", str(outbox)),
        patch("src.dashboard_api._build_session_list", return_value=[idle_session]),
        patch("src.dashboard_api.api_session_detail", side_effect=lambda _sid: _session_detail()),
        patch(
            "src.dashboard_api.AchievementBridge.enqueue_intake",
            side_effect=[OSError("disk full"), True],
        ),
    ):
        task = client.post("/api/tasks/sync").json()["tasks"][0]
        client.post(f"/api/task/{task['id']}/confirm")
        first = client.post("/api/tasks/sync")
        second = client.post("/api/tasks/sync")

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["tasks"][0]["achievement_status"] == "pending_intake"


def test_coach_request_is_idempotent_after_success(client, tmp_path):
    task_db = tmp_path / "tasks.db"
    ledger = tmp_path / "ACHIEVEMENT_LOG.md"
    coach_outbox = tmp_path / "coach.jsonl"
    config_path = tmp_path / "dashboard-config.json"
    idle_session = {**ACTIVE_SESSION, "state": "idle"}
    with (
        patch("src.dashboard_api.TASK_STORE_DB", str(task_db)),
        patch("src.dashboard_api.ACHIEVEMENT_LEDGER_PATH", str(ledger)),
        patch("src.dashboard_api.ACHIEVEMENT_INTAKE_OUTBOX", str(tmp_path / "intake.jsonl")),
        patch("src.dashboard_api.AI_COACH_OUTBOX", str(coach_outbox)),
        patch("src.dashboard_api.DASHBOARD_CONFIG_PATH", str(config_path)),
        patch("src.dashboard_api._build_session_list", return_value=[idle_session]),
        patch("src.dashboard_api.api_session_detail", side_effect=lambda _sid: _session_detail()),
    ):
        task = client.post("/api/tasks/sync").json()["tasks"][0]
        task = client.post(f"/api/task/{task['id']}/confirm").json()
        ledger.write_text(
            f"### 2026-11-20 — Linked\n- Evidence: `{task['achievement_source_key']}`\n",
            encoding="utf-8",
        )
        client.post("/api/tasks/sync")
        first = client.post(f"/api/task/{task['id']}/coach/request")
        second = client.post(f"/api/task/{task['id']}/coach/request")

    assert first.status_code == second.status_code == 200
    assert second.json()["coach_status"] == "pending"
    assert len(coach_outbox.read_text(encoding="utf-8").splitlines()) == 1
