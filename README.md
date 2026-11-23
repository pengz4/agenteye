<h1><img src="https://raw.githubusercontent.com/JeffSteinbok/agenteye/main/src/static/icon-192.png" height="32" style="vertical-align: middle;"> Agent Eye</h1>

![Agent Eye](https://raw.githubusercontent.com/JeffSteinbok/agenteye/main/githubSocial.png?v=2)

[![GitHub](https://img.shields.io/badge/GitHub-agenteye-blue?logo=github)](https://github.com/JeffSteinbok/agenteye)
[![GitHub release](https://img.shields.io/github/v/release/JeffSteinbok/agenteye)](https://github.com/JeffSteinbok/agenteye/releases)
[![CI](https://github.com/JeffSteinbok/agenteye/actions/workflows/ci.yml/badge.svg)](https://github.com/JeffSteinbok/agenteye/actions/workflows/ci.yml)
[![Release](https://github.com/JeffSteinbok/agenteye/actions/workflows/release.yml/badge.svg)](https://github.com/JeffSteinbok/agenteye/actions/workflows/release.yml)
[![Publish to PyPI](https://github.com/JeffSteinbok/agenteye/actions/workflows/publish-pypi.yml/badge.svg)](https://github.com/JeffSteinbok/agenteye/actions/workflows/publish-pypi.yml)
[![PyPI version](https://img.shields.io/pypi/v/agenteye-app.svg)](https://pypi.org/project/agenteye-app/)
[![OpenAPI](https://img.shields.io/badge/OpenAPI-spec-green?logo=openapiinitiative)](https://editor.swagger.io/?url=https://raw.githubusercontent.com/JeffSteinbok/agenteye/main/docs/openapi.json)

A local web dashboard that monitors all your GitHub Copilot CLI, Claude Code, and Microsoft Scout sessions in real-time.
Designed for power users running multiple AI coding sessions simultaneously.

![Dashboard Screenshot](https://raw.githubusercontent.com/JeffSteinbok/agenteye/main/screenshot.png)

## Requirements

- Python >= 3.11
- At least one supported agent installed: GitHub Copilot CLI, Claude Code, or Microsoft Scout

## Installation

### Option 1: From PyPI

```bash
pip install agenteye-app
```

### Option 2: From Source

```bash
# Clone the repo
git clone https://github.com/JeffSteinbok/agenteye.git
cd agenteye

# Install in editable mode
pip install -e .
```

## Usage

### Native App (Recommended)

Run as a native desktop app with system tray integration:

```bash
# Start the tray app (window + tray icon)
agenteye app

# Start minimized to tray
agenteye app --hidden

# Custom port
agenteye app --port 8080
```

The tray app provides:
- Native window with dark/light title bar matching app theme
- System tray icon with quick access menu
- Close (X) minimizes to tray, quit from tray menu exits
- Native Windows notifications (no browser permission needed)

### macOS Applications / Spotlight Integration

On macOS, you can install a lightweight per-user `.app` launcher that points at
your current Python installation of Agent Eye:

```bash
# Install ~/Applications/Agent Eye.app
agenteye install-app

# Remove the generated app bundle
agenteye uninstall-app
```

This launcher is **not** a standalone packaged app yet. It reuses the Python
environment where you ran `agenteye install-app`, so reinstalling Agent Eye,
moving that interpreter, or changing environments may break the launcher until
you run `agenteye install-app` again.

### Browser Mode

Run as a background server and open in your browser:

```bash
# Start the dashboard
agenteye start

# Start in background
agenteye start --background

# Check status
agenteye status

# Stop
agenteye stop

# Upgrade to the latest version (restarts automatically if running)
agenteye upgrade
```

Open **http://localhost:5111** in your browser.

### Autostart at Login (Windows)

```bash
# Start tray app on login (recommended)
agenteye autostart --mode app

# Start background server on login
agenteye autostart --mode server

# Custom port
agenteye autostart --mode app --port 8080

# Remove login startup
agenteye autostart-remove
```

## Features

### Session States
- **Working / Thinking** (green) — session is actively running tools or reasoning
- **Waiting** (yellow) — session needs your input (`ask_user` or `ask_permission` pending)
- **Idle** (blue) — session is done and ready for your next task

### Key Features
- **Native tray app** — `agenteye app` runs as a native desktop application with system tray integration, eliminating the need for a separate browser tab
- **Dark/light title bar** — window title bar automatically matches your chosen theme
- **Native notifications** — Windows toast notifications with proper app name and icon (no browser permission prompts)
- **Start hidden** — `--hidden` flag starts the app minimized to tray (great for autostart)
- **Claude Code support** — automatically discovers Claude Code sessions from `~/.claude/projects/`. Active Claude sessions appear alongside Copilot sessions with a `✦ Claude` badge.
- **Microsoft Scout support** — automatically discovers Scout's embedded Copilot sessions from `~/.scout/copilot/`. Active Scout sessions appear with a `🧭 Scout` badge.
- **Cross-machine sync** — see active sessions from all your machines in one dashboard, powered by OneDrive or any cloud-synced folder. See [Cross-Machine Sync](#cross-machine-sync) for details.
- **Settings menu** — ☰ hamburger menu in the header with toggles for autostart-on-login and remote sync.
- **Upgrade command** — `agenteye upgrade` stops the server, upgrades via pip, and restarts automatically.
- **Desktop notifications** — get alerts when sessions transition between states
- **Focus window** — bring an active session's terminal to the foreground with one click
- **Restart commands** — copy-pasteable `copilot --resume <id>` commands for every session
- **Dismiss sessions** — hide completed/noisy sessions from the dashboard without deleting them on disk
- **Waiting context** — shows *what* a waiting session is asking (e.g. the `ask_user` question and choices)
- **Background tasks** — shows count of running subagents per session
- **Session details** — click any session to see checkpoints, recent tool output, references, and conversation history
- **Task review queue** — tracks one logical task across multiple CLI turns and moves finished work into **Task Review** for explicit confirmation
- **Memory workbench** — shows runtime/sync health, active-vs-archived memory counts, and safe recent activity without exposing memory bodies
- **Obsidian workbench** — shows Vault/Git health, Daily Note readiness, Task/Achievement counts, and safe deep links without rendering note content
- **Obsidian task sync** — optionally creates canonical task notes and compact links in Daily Notes without copying full transcripts
- **Tile & List views** — compact card grid or detailed expandable rows
- **9 color palettes** and light/dark mode

### Obsidian Task Sync

Enable **Obsidian tasks** in the ☰ settings menu. Agent Eye auto-detects a
single configured Obsidian Vault and reads the Daily Notes folder/format from
`.obsidian/daily-notes.json`. To pin a Vault or use a custom task directory,
configure `~/.copilot/dashboard-config.json`:

```json
{
  "obsidian": {
    "enabled": true,
    "vault_path": "/path/to/My Vault",
    "task_folder": "AgentEye/Tasks"
  }
}
```

Each logical task has one canonical Markdown file. Agent Eye owns only the
marked `agenteye:task-managed` section; hand-written notes in the same file are
preserved. Daily Notes receive a compact, idempotent status link rather than a
copy of the task. When a task crosses midnight, the next Daily Note links to the
original task file.

Completed CLI work first enters **Task Review**. Confirming in Agent Eye
or checking the task in Obsidian marks it complete; unchecking a completed task
reopens it. Agent Eye writes metadata, short summaries, statuses, and
milestones only—it does **not** copy prompts, transcripts, tool output, or code
into the Vault.

### Achievement and AI Coach Handoff

Agent Eye keeps Achievement state separate from task state:

1. A confirmed task becomes an achievement candidate.
2. The existing `achievement-intake` workflow remains the **only Achievement writer** and decides whether the verified outcome is worth recording.
3. Agent Eye observes the configured ledger for the stable `task:<task-id>` source key and shows `candidate`, `pending intake`, `linked`, or `skipped`.
4. Duplicate intake requests use the same idempotent source key, so they cannot silently create a second task identity.

Agent Eye can queue a sanitized re-review request, but it never writes the
Achievement ledger or Daily Achievement note itself. Linked achievements can
optionally feed AI Coach:

- `Off` — do not generate Coach practice.
- `Ask` — require a button click in Task Review.
- `Auto` — queue practice generation once for the linked achievement.

Coach requests generate practice-only events; they do not start a quiz or
change mastery. The default mode is `Ask`.

### Cross-Machine Sync

See active sessions from all your machines in one dashboard — powered by OneDrive, Google Drive, or any cloud-synced folder. No Git commits needed.

**How it works:**
- On each poll cycle, the dashboard exports your active sessions as JSON files to a shared cloud folder
- Other machines read those files and display them in a **"Remote Sessions"** section under Active
- Each machine only writes to its own subfolder — no sync conflicts

**Auto-detection (priority order):**
1. `OneDriveCommercial` (preferred — prevents data leakage to personal accounts)
2. `OneDriveConsumer`
3. User Documents folder

**Configuration** (`~/.copilot/dashboard-config.json`):
```json
{
  "sync": {
    "enabled": true,
    "folder": "D:\\MyCloudSync"
  }
}
```
- Set `"enabled": false` to disable sync entirely
- Set `"folder"` to override auto-detection with a specific path

**What remote sessions show:**
- Live state indicators (working, waiting, idle)
- Session summary, intent, branch, MCP servers, turn/checkpoint counts
- Machine name badge (e.g. `🖥️ LAPTOP-HOME`)

**What remote sessions don't show:**
- No detail drill-down (checkpoints, turns, files)
- No focus or kill actions (those are local-only)
- No past/previous sessions from remote machines

## Prerequisites

| Package | Purpose |
|---------|---------|
| `fastapi` | Web framework with auto-generated OpenAPI docs |
| `uvicorn` | ASGI server |
| `pywinauto` | Window focus and process detection (Windows-only) |
| `pywebview` | Native window for tray app |
| `pystray` | System tray icon |
| `plyer` | Native OS notifications |

All are installed automatically via `pip install agenteye-app`.

For more details on architecture, data sources, and API endpoints, see [DEVELOPMENT.md](DEVELOPMENT.md).
