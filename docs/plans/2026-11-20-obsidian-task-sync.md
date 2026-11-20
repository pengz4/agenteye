# Obsidian Task Sync Implementation Plan

> **For Copilot:** Use executing-plans skill to implement this plan task-by-task.

**Goal:** Track every CLI task in AgentEye, expose tasks awaiting confirmation, and synchronize durable task summaries to Obsidian Daily Notes without copying transcripts.

**Architecture:** A local SQLite task store owns task identity and lifecycle. A background reconciler maps active Copilot/Claude/Scout sessions onto tasks, while an Obsidian writer stores the canonical task in a managed Markdown block and writes compact links into Daily Notes.

**Tech Stack:** Python 3.11+, FastAPI, SQLite, Pydantic, React, TypeScript, Vitest.

---

### Task 1: Create the task identity and lifecycle store

**Files:**
- Create: `src/task_store.py`
- Test: `tests/test_task_store.py`

**Steps:**
1. Write failing tests for task creation, multi-turn continuation, explicit splitting, merging, confirmation, reopening, and cross-day activity.
2. Run `pytest tests/test_task_store.py -q` and verify the missing store fails.
3. Implement `TaskStore` with a dedicated `agenteye-tasks.db`, task status values `active`, `awaiting_confirmation`, `completed`, `blocked`, and idempotent session/turn reconciliation.
4. Preserve one task ID per logical task and append cross-day activity rather than duplicating the task.
5. Run the focused tests and verify they pass.

### Task 2: Add Obsidian Vault discovery and safe Markdown sync

**Files:**
- Create: `src/obsidian_sync.py`
- Test: `tests/test_obsidian_sync.py`

**Steps:**
1. Write failing tests for Linux Obsidian config discovery, Daily Notes folder/format discovery, managed task blocks, preserved user notes, and daily-link idempotency.
2. Run `pytest tests/test_obsidian_sync.py -q` and verify the module is missing.
3. Implement vault discovery, safe path resolution, task Markdown rendering, managed-block replacement, and compact Daily Note links.
4. Ensure transcript/tool output is never written and all AgentEye mutations remain inside marked blocks.
5. Run the focused tests and verify they pass.

### Task 3: Add reconciliation and task API endpoints

**Files:**
- Modify: `src/dashboard_api.py`
- Modify: `src/schemas.py`
- Modify: `src/constants.py`
- Test: `tests/test_task_api.py`

**Steps:**
1. Write failing API tests for listing tasks, creating a split, merging tasks, confirming, reopening, and applying settings.
2. Run `pytest tests/test_task_api.py -q` and verify 404/missing schema failures.
3. Add `/api/tasks`, `/api/tasks/sync`, `/api/task/{id}/confirm`, `/api/task/{id}/reopen`, `/api/task/{id}/split`, and `/api/task/merge`.
4. Reconcile active session summaries into the store during task polling; transition idle/finished sessions to `awaiting_confirmation`.
5. Extend settings with `obsidian_enabled`, vault override, task folder, and synchronization status.
6. Run focused API tests and verify they pass.

### Task 4: Add the Needs Confirmation dashboard

**Files:**
- Create: `frontend/src/components/TaskList.tsx`
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/hooks/useTasks.ts`
- Modify: `frontend/src/state.tsx`
- Modify: `frontend/src/components/App.tsx`
- Modify: `frontend/src/components/TabBar.tsx`
- Test: `frontend/src/test/tasks.test.tsx`

**Steps:**
1. Add failing component/API-hook tests for an empty state, pending task rows, confirm, reopen, split, and merge actions.
2. Run `npm test -- --run src/test/tasks.test.tsx` and verify failures.
3. Add task types/client methods, polling state, a `Needs Confirmation` tab, task cards, and action buttons.
4. Keep task actions keyboard accessible and show API errors through the existing toast system.
5. Run frontend tests and verify they pass.

### Task 5: Wire Obsidian lifecycle and settings

**Files:**
- Modify: `src/dashboard_api.py`
- Modify: `frontend/src/components/HamburgerMenu.tsx`
- Modify: `frontend/src/hooks/useSettings.ts`
- Test: `tests/test_task_api.py`
- Test: `frontend/src/test/components.test.tsx`

**Steps:**
1. Write failing tests proving Obsidian sync is disabled by default, auto-discovery failures are visible, and enabling it creates one task file plus one Daily Note entry.
2. Implement background transition syncing during the AgentEye lifespan and safe last-known state persistence.
3. Add minimal settings controls for enabled state, vault override, and task folder.
4. Run backend and frontend focused tests.

### Task 6: Verify and install the development build

**Files:**
- Modify: `README.md`

**Steps:**
1. Update the README with configuration, task-state semantics, cross-day behavior, and privacy boundaries.
2. Run `ruff check src/`, `ruff format --check src/`, `mypy src/`, and `pytest -q`.
3. Run `npm test`, `npm run lint`, and `npm run build` from `frontend/`.
4. Install the worktree editable into the current AgentEye virtual environment, restart port 5112, and verify `/api/tasks` and the UI build.
