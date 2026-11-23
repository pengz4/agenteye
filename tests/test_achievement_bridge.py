import json

from src.achievement_bridge import AchievementBridge


def _task(**overrides):
    value = {
        "id": "12345678-1234-1234-1234-123456789abc",
        "session_id": "session-1",
        "source": "copilot",
        "title": "Build AgentEye task handoff",
        "summary": "Build AgentEye task handoff",
        "status": "completed",
        "cwd": "/project",
        "start_date": "2026-11-20",
        "last_activity_date": "2026-11-20",
        "last_turn_index": 2,
        "created_at": "2026-11-20T08:00:00+00:00",
        "updated_at": "2026-11-20T09:00:00+00:00",
        "completed_at": "2026-11-20T09:00:00+00:00",
        "achievement_status": "candidate",
        "achievement_source_key": "task:12345678-1234-1234-1234-123456789abc",
        "achievement_ref": None,
        "coach_status": "off",
    }
    value.update(overrides)
    return value


def test_find_linked_achievements_by_stable_task_marker(tmp_path):
    ledger = tmp_path / "ACHIEVEMENT_LOG.md"
    ledger.write_text(
        """
### 2026-11-20 — AgentEye handoff
- Evidence: verified output; `task:12345678-1234-1234-1234-123456789abc`

### 2026-11-20 — Duplicate source key
- Evidence: `task:12345678-1234-1234-1234-123456789abc`
""",
        encoding="utf-8",
    )
    bridge = AchievementBridge(ledger_path=ledger, intake_outbox=tmp_path / "intake.jsonl")

    result = bridge.find_links()

    assert result["task:12345678-1234-1234-1234-123456789abc"] == [
        "### 2026-11-20 — AgentEye handoff",
        "### 2026-11-20 — Duplicate source key",
    ]


def test_enqueue_intake_request_is_idempotent_and_sanitized(tmp_path):
    outbox = tmp_path / "intake.jsonl"
    bridge = AchievementBridge(
        ledger_path=tmp_path / "missing-ledger.md",
        intake_outbox=outbox,
    )
    task = _task(transcript="SECRET", tool_output="PRIVATE")

    first = bridge.enqueue_intake(task)
    second = bridge.enqueue_intake(task)

    assert first is True
    assert second is False
    rows = [
        json.loads(line)
        for line in outbox.read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert len(rows) == 1
    assert rows[0]["source_key"] == task["achievement_source_key"]
    assert "transcript" not in rows[0]
    assert "tool_output" not in rows[0]


def test_reports_missing_intake_outbox_entry_for_retry(tmp_path):
    bridge = AchievementBridge(
        ledger_path=tmp_path / "ledger.md",
        intake_outbox=tmp_path / "intake.jsonl",
    )
    task = _task()

    assert bridge.has_intake_request(task["achievement_source_key"]) is False
    bridge.enqueue_intake(task)
    assert bridge.has_intake_request(task["achievement_source_key"]) is True


def test_counts_only_current_pending_source_keys_in_intake_outbox(tmp_path):
    bridge = AchievementBridge(
        ledger_path=tmp_path / "ledger.md",
        intake_outbox=tmp_path / "intake.jsonl",
    )
    first = _task()
    bridge.enqueue_intake(first)
    bridge.enqueue_intake(
        _task(id="other", achievement_source_key="task:other"),
    )

    assert bridge.queued_intake_count({
        first["achievement_source_key"],
        "task:missing",
    }) == 1


def test_coach_policy_never_generates_on_off_or_unlinked_task(tmp_path):
    coach_outbox = tmp_path / "coach.jsonl"
    bridge = AchievementBridge(
        ledger_path=tmp_path / "ledger.md",
        intake_outbox=tmp_path / "intake.jsonl",
        coach_outbox=coach_outbox,
    )

    assert bridge.apply_coach_policy(_task(achievement_status="candidate"), "auto") == "off"
    assert bridge.apply_coach_policy(
        _task(achievement_status="linked", achievement_ref="Achievement heading"),
        "off",
    ) == "off"
    assert not coach_outbox.exists()


def test_coach_policy_ask_requests_confirmation_and_auto_enqueues_once(tmp_path):
    coach_outbox = tmp_path / "coach.jsonl"
    bridge = AchievementBridge(
        ledger_path=tmp_path / "ledger.md",
        intake_outbox=tmp_path / "intake.jsonl",
        coach_outbox=coach_outbox,
    )
    linked = _task(
        achievement_status="linked",
        achievement_ref="### 2026-11-20 — AI Agent task",
    )

    assert bridge.apply_coach_policy(linked, "ask") == "needs_confirmation"
    assert bridge.apply_coach_policy(linked, "auto") == "pending"
    assert bridge.apply_coach_policy(linked, "auto") == "pending"

    rows = [
        json.loads(line)
        for line in coach_outbox.read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert len(rows) == 1
    assert rows[0]["source_key"] == linked["achievement_source_key"]
