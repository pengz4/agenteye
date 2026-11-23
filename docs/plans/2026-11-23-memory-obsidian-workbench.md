# Memory and Obsidian Workbench Plan

> **For Copilot:** Use executing-plans skill to implement this plan task-by-task.

**Goal:** Add read-only Memory and Obsidian pages to AgentEye that explain integration health, recent activity, and useful deep links without exposing full private content.

**Architecture:** A backend workbench service derives aggregate, metadata-only summaries from existing local sources. React pages consume the summaries and reuse the shared dashboard shell; write operations remain in their owning runtimes.

**Tech Stack:** Python, FastAPI, React, TypeScript, Vitest.

---

### Task 1: Add Memory aggregate overview

**Files:**
- Create: `src/memory_workbench.py`
- Test: `tests/test_memory_workbench.py`

**Steps:**
1. Write failing tests for configured/unconfigured MCP runtime, kind counts, last sync, today capture count, and recent safe summaries.
2. Implement metadata-only parsing from the Memory repository, sync status, and audit JSONL.
3. Never return absolute paths, content bodies, remote URL, tokens, or title hashes.
4. Run focused tests.

### Task 2: Add Obsidian aggregate overview

**Files:**
- Create: `src/obsidian_workbench.py`
- Test: `tests/test_obsidian_workbench.py`

**Steps:**
1. Write failing tests for Vault detection, Daily Note config, Git dirty state, task/achievement counts, and Obsidian deep links.
2. Implement aggregate Vault/Git/note/task sync parsing.
3. Return basenames/relative note identifiers only; do not return note bodies or absolute paths.
4. Run focused tests.

### Task 3: Add workbench APIs

**Files:**
- Modify: `src/dashboard_api.py`
- Modify: `src/schemas.py`
- Test: `tests/test_dashboard_api_extra.py`

**Steps:**
1. Add failing API tests for `/api/memory-overview` and `/api/obsidian-overview`.
2. Wire services to stack configuration and existing TaskStore.
3. Degrade per-panel failures to explicit status rather than a whole dashboard 500.
4. Run focused tests.

### Task 4: Add Memory and Obsidian tabs

**Files:**
- Create: `frontend/src/components/MemoryWorkbench.tsx`
- Create: `frontend/src/components/ObsidianWorkbench.tsx`
- Modify: `frontend/src/components/TabBar.tsx`
- Modify: `frontend/src/components/App.tsx`
- Modify: `frontend/src/state/AppContext.tsx`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/types/api.ts`
- Test: `frontend/src/test/workbench.test.tsx`

**Steps:**
1. Add failing tests for tab visibility, health cards, activity rows, and deep-link actions.
2. Implement API polling on page entry and explicit refresh action.
3. Keep all page actions as Open/Refresh/Retry; do not add inline editors.
4. Run frontend tests, lint, typecheck, and build.

### Task 5: Verify and deploy

**Steps:**
1. Run backend full tests and frontend full tests.
2. Review sensitive-field leakage and URL safety.
3. Build, restart on 5112, and verify both live endpoints.
