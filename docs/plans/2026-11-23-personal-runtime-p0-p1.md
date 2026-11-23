# Personal Runtime P0/P1 Implementation Plan

> **For Copilot:** Use executing-plans skill to implement this plan task-by-task.

**Goal:** Ship the AgentEye/Coach UI work with an explicit personal build version, close the Achievement intake queue gap, and replace install-only runtime status with real verified health.

**Architecture:** Keep AgentEye and Coach as separate authority planes. AgentEye reports safe local health and exposes explicit side-effect endpoints; `achievement-intake` remains the only Achievement writer. Personal Memory is verified through local runtime files plus configured Copilot MCP registration, while Control Plane derives one aggregate status from component results.

**Tech Stack:** Python/FastAPI, React/TypeScript, JSON configuration, GitHub Actions/releases, AgentSkills Markdown, pytest/vitest/ruff/mypy/ESLint.

---

### Task 1: Add personal build version identity

**Files:**
- Modify: `src/__version__.py`
- Modify: `src/schemas.py`
- Modify: `src/dashboard_api.py`
- Modify: `src/control_plane.py`
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/hooks/useVersion.ts`
- Modify: `frontend/src/components/Header.tsx`
- Test: `tests/test_control_plane.py`
- Test: `tests/test_dashboard_api_extra.py`
- Test: `tests/test_version_update.py`
- Test: `frontend/src/test/hooks.test.ts`
- Test: `frontend/src/test/App.test.tsx`

**Step 1:** Add failing tests for `personal_version` in `/api/version` and header display.

**Step 2:** Run focused backend/frontend tests and confirm the missing field/display failures.

**Step 3:** Add `__personal_version__ = "1.3.0-personal.8"` while preserving `__version__ = "1.3.0"` for upstream update checks.

**Step 4:** Return and render the personal version consistently in Header and Agent Eye runtime detail.

**Step 5:** Run focused tests, lint, typecheck, and build.

### Task 2: Verify Personal Memory host registration

**Files:**
- Modify: `src/control_plane.py`
- Test: `tests/test_control_plane.py`

**Step 1:** Add failing tests for a configured `personal-agent-memory` MCP entry, executable command, script args, repository path, and missing/invalid registration.

**Step 2:** Run focused tests and confirm `installed` does not yet upgrade to verified health.

**Step 3:** Read `~/.copilot/mcp-config.json` without exposing environment values. Mark the component `healthy` only when runtime files, dependencies, MCP registration, executable, script and repository path exist.

**Step 4:** Run focused tests and ensure malformed config never raises or leaks values.

### Task 3: Derive aggregate Control Plane health

**Files:**
- Modify: `src/control_plane.py`
- Modify: `frontend/src/components/RuntimeOverview.tsx`
- Test: `tests/test_control_plane.py`
- Test: `frontend/src/test/control-plane.test.tsx`

**Step 1:** Add failing tests for `healthy`, `degraded`, and `invalid` aggregate states.

**Step 2:** Implement aggregation from Agent Eye, Personal Memory, AI Coach, Obsidian, and runtime lock status.

**Step 3:** Map healthy to a green dot, degraded to yellow, invalid/failure to red.

**Step 4:** Run focused backend/frontend tests.

### Task 4: Close Achievement intake queue consumption

**Files:**
- Modify: `/root/personal-agent-skills/skills/achievement-intake/SKILL.md`
- Modify: `/root/personal-agent-skills/skills/achievement-intake/test-prompts.json`
- Modify: `frontend/src/components/ObsidianWorkbench.tsx`
- Modify: `frontend/src/test/workbench.test.tsx`
- Modify: `src/achievement_bridge.py`
- Test: `tests/test_achievement_bridge.py`

**Step 1:** Add failing tests/documented prompts for queue-aware intake, dedupe by `source_key`, and explicit `review-needed` behavior when source evidence is unavailable.

**Step 2:** Add a safe AgentEye API/Workbench summary for queued requests without exposing payload paths or summaries.

**Step 3:** Update the skill to read `/root/.copilot/agenteye/achievement-intake-requests.jsonl` during explicit queue-processing intake, match stable ledger refs, and never write unverifiable entries.

**Step 4:** Deploy the updated skill and verify the installed copy/hash.

### Task 5: Preserve meaningful Task Review failure feedback

**Files:**
- Modify: `frontend/src/hooks/useTasks.ts`
- Test: `frontend/src/test/hooks.test.ts`

**Step 1:** Add a failing test that a server error produces a specific toast and clears pending state.

**Step 2:** Preserve the thrown error message instead of replacing every failure with "Task update failed".

**Step 3:** Run the focused hook test.

### Task 6: Merge and publish Coach UI changes

**Files:**
- Commit: `coach/unified_ui.css`
- Commit: `coach/unified_ui.js`
- Commit: `scripts/dashboard_server.py`
- Commit: `tests/test_unified_browser.py`

**Step 1:** Run all Coach tests and `py_compile`.

**Step 2:** Commit the existing AgentEye-unification branch with the required Co-authored-by trailer.

**Step 3:** Push, create PR to `main`, wait for checks, merge, and record the final commit.

### Task 7: Release AgentEye personal.8 and pin the stack

**Files:**
- Release: AgentEye main
- Modify: `/root/personal-agent-skills/runtimes.lock.json`
- Modify: `/root/personal-agent-skills/source-origins.json` if hash metadata requires it
- Test: `/root/personal-agent-skills/tests`

**Step 1:** Finish all AgentEye changes, run full backend/frontend/lint/type/build validation, and request code review.

**Step 2:** Commit the AgentEye release branch, push, create PR to `main`, merge, and create `v1.3.0-personal.8` with the built wheel.

**Step 3:** Update the Personal Agent runtime pin to the merged AgentEye revision, wheel URL/SHA, and Coach merged revision.

**Step 4:** Run personal-agent-skills deploy/runtime tests and deploy `--with-runtimes`.

### Task 8: Live verification

**Step 1:** Restart 5112 from the deployed managed personal.8 runtime.

**Step 2:** Verify root, sessions, tasks, control-plane, Obsidian and startup endpoints.

**Step 3:** Verify the dashboard displays `v1.3.0-personal.8`, green Personal Memory/Control Plane where checks pass, and Task Review/Coach remain functional.

**Step 4:** Record the final release and runtime receipts in the achievement/conversation handoff if requested by the established intake workflow.

