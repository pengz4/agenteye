# Task Achievement Coach Handoff Implementation Plan

> **For Copilot:** Use executing-plans skill to implement this plan task-by-task.

**Goal:** Let completed tasks become achievement-intake candidates without duplicate achievement writes, then expose an optional AI Coach follow-up mode.

**Architecture:** AgentEye stores task-local handoff state in its task SQLite database and only reads the configured achievement ledger to recognize already-written task markers. It never writes achievement files; an idempotent request queue exposes `session_id + task_id` to the existing achievement-intake workflow. AI Coach is a separate downstream state machine controlled by `off`, `ask`, or `auto`.

**Tech Stack:** Python, SQLite, FastAPI, React, TypeScript, Vitest.

---

### Task 1: Extend the task lifecycle with achievement state

**Files:**
- Modify: `src/task_store.py`
- Test: `tests/test_task_store.py`

**Steps:**
1. Add failing tests for automatic candidate creation at confirmation, skip/review actions, idempotent intake request creation, and reopening clearing only task completion while preserving achievement linkage.
2. Implement `achievement_status` states: `not_candidate`, `candidate`, `pending_intake`, `linked`, `skipped`; stable source key `task:<task-id>`; optional `achievement_ref`.
3. Make requests idempotent and never duplicate an existing pending/linked state.
4. Run focused tests and verify they pass.

### Task 2: Add a read-only achievement ledger bridge

**Files:**
- Create: `src/achievement_bridge.py`
- Test: `tests/test_achievement_bridge.py`

**Steps:**
1. Add failing tests that find `task:<id>` markers in an existing ledger, reject duplicate or malformed sources, and produce one sanitized intake request.
2. Implement ledger discovery, source-key scanning, and a JSONL request outbox.
3. Ensure the bridge never writes the ledger or Obsidian achievement notes.
4. Run focused tests and verify they pass.

### Task 3: Add Task Review APIs and candidate visibility

**Files:**
- Modify: `src/dashboard_api.py`
- Modify: `src/schemas.py`
- Test: `tests/test_task_api.py`

**Steps:**
1. Add failing API tests for candidate listing, skip, re-review, idempotent intake request, and linked-state reconciliation from the ledger.
2. Expose `/api/task/{id}/achievement/request`, `/skip`, and `/review`.
3. Reconcile ledger links during task sync and return explicit achievement status in task responses.
4. Run focused API tests and verify they pass.

### Task 4: Add Coach downstream state and settings

**Files:**
- Modify: `src/task_store.py`
- Modify: `src/dashboard_api.py`
- Modify: `src/schemas.py`
- Modify: `frontend/src/hooks/useSettings.ts`
- Modify: `frontend/src/components/HamburgerMenu.tsx`
- Test: `tests/test_task_api.py`

**Steps:**
1. Add failing tests for `coach_mode=off|ask|auto`, linked achievements producing no coach request in off mode, ask prompts in ask mode, and one request in auto mode.
2. Persist `coach_mode` with default `ask`; do not start quizzes or change mastery.
3. Keep Coach requests in a separate outbox with an idempotent `achievement_ref + task_id` key.
4. Run focused tests and verify they pass.

### Task 5: Extend Task Review UI

**Files:**
- Modify: `frontend/src/components/TaskList.tsx`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/hooks/useTasks.ts`
- Modify: `frontend/src/types/api.ts`
- Test: `frontend/src/test/tasks.test.tsx`

**Steps:**
1. Add failing tests for candidate, pending intake, linked, skipped, coach request/disabled badges, and actions.
2. Add `Add to Achievement`, `Skip`, and `Review Again` actions without duplicating Confirm complete.
3. Add a clear Coach mode selector in Settings.
4. Run frontend tests and verify they pass.

### Task 6: Verify and restart AgentEye

**Files:**
- Modify: `README.md`

**Steps:**
1. Document the single-writer intake model, idempotency key, status meanings, and Coach isolation.
2. Run `ruff check src/`, `ruff format --check src/`, `mypy src/`, and `pytest -q`.
3. Run `npm test`, `npm run lint`, and `npm run build`.
4. Restart `_serve` on port 5112 and verify task APIs plus UI bundle.
