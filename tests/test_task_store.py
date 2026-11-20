from datetime import UTC, datetime

import pytest

from src.task_store import TaskStore


def _now(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def test_reconcile_creates_task_then_continues_same_task_for_multiple_turns(tmp_path):
    store = TaskStore(tmp_path / "tasks.db")

    first = store.reconcile_session(
        session_id="session-1",
        source="copilot",
        title="Implement dashboard",
        turn_index=0,
        cwd="/project",
        is_running=True,
        session_state="working",
        now=_now("2026-11-20T08:00:00Z"),
    )
    second = store.reconcile_session(
        session_id="session-1",
        source="copilot",
        title="Add Obsidian export",
        turn_index=1,
        cwd="/project",
        is_running=True,
        session_state="thinking",
        now=_now("2026-11-20T08:10:00Z"),
    )

    assert second["id"] == first["id"]
    assert second["title"] == "Implement dashboard"
    assert second["summary"] == "Add Obsidian export"
    assert second["status"] == "active"
    assert second["last_turn_index"] == 1


def test_idle_session_becomes_awaiting_confirmation(tmp_path):
    store = TaskStore(tmp_path / "tasks.db")
    store.reconcile_session(
        session_id="session-1",
        source="copilot",
        title="Implement dashboard",
        turn_index=0,
        cwd="/project",
        is_running=True,
        session_state="working",
        now=_now("2026-11-20T08:00:00Z"),
    )

    task = store.reconcile_session(
        session_id="session-1",
        source="copilot",
        title="Implement dashboard",
        turn_index=0,
        cwd="/project",
        is_running=True,
        session_state="idle",
        now=_now("2026-11-20T08:30:00Z"),
    )

    assert task["status"] == "awaiting_confirmation"


def test_completed_task_stays_completed_until_reopened_or_new_turn(tmp_path):
    store = TaskStore(tmp_path / "tasks.db")
    task = store.reconcile_session(
        session_id="session-1",
        source="claude",
        title="Fix test",
        turn_index=0,
        cwd="/project",
        is_running=True,
        session_state="idle",
        now=_now("2026-11-20T08:00:00Z"),
    )

    confirmed = store.confirm(task["id"], now=_now("2026-11-20T08:01:00Z"))
    still_completed = store.reconcile_session(
        session_id="session-1",
        source="claude",
        title="Fix test",
        turn_index=0,
        cwd="/project",
        is_running=False,
        session_state="unknown",
        now=_now("2026-11-20T08:02:00Z"),
    )
    new_task = store.reconcile_session(
        session_id="session-1",
        source="claude",
        title="Write docs",
        turn_index=1,
        cwd="/project",
        is_running=True,
        session_state="working",
        now=_now("2026-11-20T08:03:00Z"),
    )

    assert confirmed["status"] == "completed"
    assert still_completed["id"] == task["id"]
    assert still_completed["status"] == "completed"
    assert new_task["id"] != task["id"]
    assert new_task["title"] == "Write docs"


def test_split_and_merge_preserve_task_identity_and_activities(tmp_path):
    store = TaskStore(tmp_path / "tasks.db")
    first = store.reconcile_session(
        session_id="session-1",
        source="copilot",
        title="Build feature",
        turn_index=0,
        cwd="/project",
        is_running=True,
        session_state="working",
        now=_now("2026-11-20T08:00:00Z"),
    )

    split = store.split(
        first["id"],
        title="Write documentation",
        turn_index=1,
        now=_now("2026-11-20T09:00:00Z"),
    )
    merged = store.merge(
        target_id=first["id"],
        source_id=split["id"],
        now=_now("2026-11-20T09:05:00Z"),
    )

    assert split["id"] != first["id"]
    assert merged["id"] == first["id"]
    assert merged["summary"] == "Write documentation"
    assert store.get(split["id"])["status"] == "merged"
    assert store.get(split["id"])["merged_into"] == first["id"]
    assert len(store.activities(first["id"])) >= 2


def test_cross_day_reconciliation_keeps_original_task_and_records_new_day(tmp_path):
    store = TaskStore(tmp_path / "tasks.db")
    task = store.reconcile_session(
        session_id="session-1",
        source="scout",
        title="Long migration",
        turn_index=0,
        cwd="/project",
        is_running=True,
        session_state="working",
        now=_now("2026-11-20T23:55:00Z"),
    )

    continued = store.reconcile_session(
        session_id="session-1",
        source="scout",
        title="Long migration",
        turn_index=0,
        cwd="/project",
        is_running=True,
        session_state="working",
        now=_now("2026-11-21T00:05:00Z"),
    )

    assert continued["id"] == task["id"]
    assert continued["start_date"] == "2026-11-20"
    assert {row["activity_date"] for row in store.activities(task["id"])} == {
        "2026-11-20",
        "2026-11-21",
    }


def test_confirm_and_reopen_require_known_task(tmp_path):
    store = TaskStore(tmp_path / "tasks.db")

    with pytest.raises(KeyError):
        store.confirm("missing")
    with pytest.raises(KeyError):
        store.reopen("missing")


def test_unchanged_reconciliation_is_idempotent(tmp_path):
    store = TaskStore(tmp_path / "tasks.db")
    first = store.reconcile_session(
        session_id="session-1",
        source="copilot",
        title="Review API",
        turn_index=0,
        cwd="/project",
        is_running=True,
        session_state="working",
        now=_now("2026-11-20T08:00:00Z"),
    )

    second = store.reconcile_session(
        session_id="session-1",
        source="copilot",
        title="Review API",
        turn_index=0,
        cwd="/project",
        is_running=True,
        session_state="working",
        now=_now("2026-11-20T08:05:00Z"),
    )

    assert second == first
    assert len(store.activities(first["id"])) == 1


def test_reopened_task_survives_idle_reconciliation_until_a_new_turn(tmp_path):
    store = TaskStore(tmp_path / "tasks.db")
    task = store.reconcile_session(
        session_id="session-1",
        source="copilot",
        title="Review API",
        turn_index=0,
        cwd="/project",
        is_running=True,
        session_state="idle",
        now=_now("2026-11-20T08:00:00Z"),
    )
    store.confirm(task["id"], now=_now("2026-11-20T08:01:00Z"))
    reopened = store.reopen(task["id"], now=_now("2026-11-20T08:02:00Z"))

    reconciled = store.reconcile_session(
        session_id="session-1",
        source="copilot",
        title="Review API",
        turn_index=0,
        cwd="/project",
        is_running=True,
        session_state="idle",
        now=_now("2026-11-20T08:03:00Z"),
    )

    assert reopened["status"] == "active"
    assert reconciled["status"] == "active"


def test_reconciliation_selects_new_active_split_task(tmp_path):
    store = TaskStore(tmp_path / "tasks.db")
    original = store.reconcile_session(
        session_id="session-1",
        source="copilot",
        title="Build API",
        turn_index=0,
        cwd="/project",
        is_running=True,
        session_state="working",
        now=_now("2026-11-20T08:00:00Z"),
    )
    split_time = _now("2026-11-20T08:30:00Z")
    split = store.split(
        original["id"], title="Write docs", turn_index=1, now=split_time
    )

    reconciled = store.reconcile_session(
        session_id="session-1",
        source="copilot",
        title="Write docs",
        turn_index=1,
        cwd="/project",
        is_running=True,
        session_state="working",
        now=split_time,
    )

    assert reconciled["id"] == split["id"]


def test_new_turn_after_completed_split_creates_new_task(tmp_path):
    store = TaskStore(tmp_path / "tasks.db")
    original = store.reconcile_session(
        session_id="session-1",
        source="copilot",
        title="Build API",
        turn_index=0,
        cwd="/project",
        is_running=True,
        session_state="working",
        now=_now("2026-11-20T08:00:00Z"),
    )
    split = store.split(
        original["id"],
        title="Write docs",
        turn_index=1,
        now=_now("2026-11-20T08:30:00Z"),
    )
    store.confirm(split["id"], now=_now("2026-11-20T08:40:00Z"))

    new_task = store.reconcile_session(
        session_id="session-1",
        source="copilot",
        title="Deploy release",
        turn_index=2,
        cwd="/project",
        is_running=True,
        session_state="working",
        now=_now("2026-11-20T09:00:00Z"),
    )

    assert new_task["id"] not in {original["id"], split["id"]}
    assert new_task["title"] == "Deploy release"


def test_split_without_reopen_override_becomes_awaiting_when_idle(tmp_path):
    store = TaskStore(tmp_path / "tasks.db")
    original = store.reconcile_session(
        session_id="session-1",
        source="copilot",
        title="Build API",
        turn_index=0,
        cwd="/project",
        is_running=True,
        session_state="working",
        now=_now("2026-11-20T08:00:00Z"),
    )
    split = store.split(
        original["id"],
        title="Write docs",
        turn_index=1,
        now=_now("2026-11-20T08:30:00Z"),
    )

    reconciled = store.reconcile_session(
        session_id="session-1",
        source="copilot",
        title="Write docs",
        turn_index=1,
        cwd="/project",
        is_running=True,
        session_state="idle",
        now=_now("2026-11-20T08:31:00Z"),
    )

    assert reconciled["id"] == split["id"]
    assert reconciled["status"] == "awaiting_confirmation"


def test_split_without_turn_index_infers_current_turn(tmp_path):
    store = TaskStore(tmp_path / "tasks.db")
    original = store.reconcile_session(
        session_id="session-1",
        source="copilot",
        title="Build API",
        turn_index=9,
        cwd="/project",
        is_running=True,
        session_state="working",
        now=_now("2026-11-20T08:00:00Z"),
    )
    split = store.split(
        original["id"],
        title="Write docs",
        turn_index=None,
        now=_now("2026-11-20T08:30:00Z"),
    )

    reconciled = store.reconcile_session(
        session_id="session-1",
        source="copilot",
        title="Write docs",
        turn_index=9,
        cwd="/project",
        is_running=True,
        session_state="working",
        now=_now("2026-11-20T08:30:00Z"),
    )

    assert split["last_turn_index"] == 9
    assert reconciled["id"] == split["id"]


def test_confirm_creates_achievement_candidate_without_writing_intake(tmp_path):
    store = TaskStore(tmp_path / "tasks.db")
    task = store.reconcile_session(
        session_id="session-1",
        source="copilot",
        title="Build dashboard",
        turn_index=0,
        cwd="/project",
        is_running=True,
        session_state="working",
        now=_now("2026-11-20T08:00:00Z"),
    )

    completed = store.confirm(task["id"], now=_now("2026-11-20T09:00:00Z"))

    assert completed["achievement_status"] == "candidate"
    assert completed["achievement_source_key"] == f"task:{task['id']}"
    assert completed["coach_status"] == "off"


def test_achievement_actions_are_idempotent_and_reopen_preserves_link(tmp_path):
    store = TaskStore(tmp_path / "tasks.db")
    task = store.reconcile_session(
        session_id="session-1",
        source="copilot",
        title="Build dashboard",
        turn_index=0,
        cwd="/project",
        is_running=True,
        session_state="idle",
        now=_now("2026-11-20T08:00:00Z"),
    )
    store.confirm(task["id"])
    linked = store.mark_achievement_linked(
        task["id"],
        achievement_ref="2026-11-20-achievement-work-summary",
        coach_status="needs_confirmation",
    )
    reopened = store.reopen(task["id"])
    retried = store.request_achievement_review(task["id"])

    assert linked["achievement_status"] == "linked"
    assert reopened["achievement_status"] == "linked"
    assert retried["achievement_status"] == "linked"
    assert retried["achievement_ref"] == "2026-11-20-achievement-work-summary"


def test_skip_and_review_again_change_only_achievement_state(tmp_path):
    store = TaskStore(tmp_path / "tasks.db")
    task = store.reconcile_session(
        session_id="session-1",
        source="claude",
        title="Small cleanup",
        turn_index=0,
        cwd="/project",
        is_running=True,
        session_state="idle",
        now=_now("2026-11-20T08:00:00Z"),
    )
    completed = store.confirm(task["id"])
    skipped = store.skip_achievement(task["id"])
    reviewed = store.request_achievement_review(task["id"])

    assert completed["status"] == "completed"
    assert skipped["status"] == "completed"
    assert skipped["achievement_status"] == "skipped"
    assert reviewed["status"] == "completed"
    assert reviewed["achievement_status"] == "pending_intake"


@pytest.mark.parametrize("session_state", ["working", "idle"])
def test_achievement_actions_reject_unfinished_or_unconfirmed_tasks(
    tmp_path, session_state
):
    store = TaskStore(tmp_path / "tasks.db")
    task = store.reconcile_session(
        session_id="session-1",
        source="copilot",
        title="Still working",
        turn_index=0,
        cwd="/project",
        is_running=True,
        session_state=session_state,
        now=_now("2026-11-20T08:00:00Z"),
    )

    with pytest.raises(ValueError, match="completed"):
        store.request_achievement_review(task["id"])
    with pytest.raises(ValueError, match="completed"):
        store.skip_achievement(task["id"])
