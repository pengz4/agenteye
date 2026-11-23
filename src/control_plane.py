"""Read-only personal-agent stack overview for the Agent Eye dashboard."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from http.client import HTTPException
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener

from .constants import DEFAULT_PORT

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


class CoachStartError(RuntimeError):
    """Configured AI Coach runtime could not be started safely."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, new_url):
        return None


def _runtime(name: str, status: str, detail: str, url: str | None = None) -> dict:
    return {"name": name, "status": status, "detail": detail, "url": url}


def _probe_coach(url: str) -> bool:
    safe_url = _safe_dashboard_url(url)
    if safe_url is None:
        return False
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        with opener.open(safe_url, timeout=2) as response:
            page = response.read(32768)
            return response.status == 200 and any(
                marker in page for marker in (b"AI Coach", b"AI Interview", b"AI/Agent")
            )
    except (URLError, HTTPError, HTTPException, OSError, ValueError):
        return False


def _safe_dashboard_url(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = urlsplit(value.strip())
        if parsed.scheme not in {"http", "https"}:
            return None
        if parsed.username or parsed.password:
            return None
        if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            return None
        port = parsed.port
        if port is not None and not 1 <= port <= 65535:
            return None
        if parsed.query or parsed.fragment:
            return None
        path = parsed.path or "/"
        return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))
    except ValueError:
        return None


def _configured_path(value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return Path(value.strip()).expanduser()


def _memory_runtime_status(
    memory_root: Path,
    copilot_home: Path,
) -> tuple[str, str]:
    entrypoint = memory_root / "bin" / "personal-memory-mcp.js"
    dependencies = memory_root / "node_modules" / "tsx"
    if not entrypoint.is_file():
        return ("not_configured", "Memory runtime entrypoint is not configured")
    if not dependencies.is_dir():
        return ("needs_dependencies", "Runtime present; Node dependencies are missing")

    config_path = copilot_home / ".copilot" / "mcp-config.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        servers = config.get("mcpServers") if isinstance(config, dict) else None
        server = servers.get("personal-agent-memory") if isinstance(servers, dict) else None
    except (OSError, json.JSONDecodeError):
        return ("installed", "Runtime present; MCP host registration could not be verified")
    if not isinstance(server, dict) or server.get("type") != "local":
        return ("installed", "Runtime present; MCP host registration is missing")

    command_value = server.get("command")
    command = (
        Path(str(command_value)).expanduser()
        if isinstance(command_value, str) and command_value
        else None
    )
    if command is not None and not command.is_absolute():
        resolved_command = shutil.which(str(command))
        command = Path(resolved_command) if resolved_command else None
    args = server.get("args")
    registered_scripts = []
    for value in args or []:
        if not isinstance(value, str) or not value.endswith("personal-memory-mcp.js"):
            continue
        script = Path(value).expanduser()
        if not script.is_absolute():
            script = copilot_home / script
        registered_scripts.append(script.resolve())
    env = server.get("env")
    repository_value = env.get("MEMORY_REPOSITORY_DIR") if isinstance(env, dict) else None
    repository = Path(str(repository_value)).expanduser() if repository_value else None
    registration_complete = (
        command is not None
        and command.is_file()
        and os.access(command, os.X_OK)
        and entrypoint.resolve() in registered_scripts
        and any(script.is_file() for script in registered_scripts)
        and repository is not None
        and repository.is_dir()
        and isinstance(env, dict)
        and bool(env.get("MEMORY_ACCOUNT_ID"))
        and bool(env.get("MEMORY_DEVICE"))
    )
    if registration_complete:
        return ("healthy", "Runtime, dependencies, and MCP registration verified")
    return ("installed", "Runtime present; MCP host registration needs attention")


_coach_start_lock = threading.Lock()


def start_coach(config: dict[str, Any]) -> dict[str, Any]:
    """Start the configured loopback Coach server and wait until it is ready."""
    stack = config.get("stack", {})
    if not isinstance(stack, dict):
        raise CoachStartError("Coach runtime is not configured")
    coach_root = _configured_path(stack.get("coach_root"))
    coach_url = _safe_dashboard_url(stack.get("coach_url"))
    if coach_root is None or coach_url is None:
        raise CoachStartError("Coach runtime or loopback URL is not configured")

    script = coach_root / "scripts" / "dashboard_server.py"
    if not script.is_file():
        raise CoachStartError("Configured Coach runtime is missing dashboard_server.py")

    parsed = urlsplit(coach_url)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
        or parsed.port is None
        or parsed.path not in {"", "/"}
    ):
        raise CoachStartError("Coach startup requires an explicit loopback HTTP port and root path")

    with _coach_start_lock:
        if _probe_coach(coach_url):
            return {"started": False, "status": "reachable", "url": coach_url}

        kwargs: dict[str, Any] = {
            "cwd": coach_root,
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if os.name == "nt":
            kwargs["creationflags"] = CREATE_NO_WINDOW
        else:
            kwargs["start_new_session"] = True
        process = subprocess.Popen(
            [
                sys.executable,
                str(script),
                "--host",
                parsed.hostname,
                "--port",
                str(parsed.port),
            ],
            **kwargs,
        )

        for _ in range(40):
            if _probe_coach(coach_url):
                return {"started": True, "status": "reachable", "url": coach_url}
            if process.poll() is not None:
                raise CoachStartError("Coach process exited before becoming ready")
            time.sleep(0.25)

        process.terminate()
        raise CoachStartError("Coach process did not become ready within 10 seconds")


def inspect_control_plane(
    config: dict[str, Any],
    *,
    agenteye_version: str,
    personal_version: str | None = None,
    copilot_home: Path | str | None = None,
    active_agenteye_url: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Return safe status cards without exposing private local paths."""
    stack = config.get("stack", {})
    if not isinstance(stack, dict):
        stack = {}

    agenteye_url = (
        _safe_dashboard_url(active_agenteye_url)
        or _safe_dashboard_url(stack.get("agenteye_url"))
        or f"http://127.0.0.1:{DEFAULT_PORT}/"
    )
    configured_coach_url = stack.get("coach_url")
    coach_url = _safe_dashboard_url(configured_coach_url)
    skills_root = _configured_path(stack.get("skills_root"))
    memory_root = _configured_path(stack.get("memory_root"))
    coach_root = _configured_path(stack.get("coach_root"))
    obsidian_vault = _configured_path(stack.get("obsidian_vault"))

    runtimes = [
        _runtime(
            "Agent Eye",
            "reachable",
            f"Current dashboard · v{personal_version or agenteye_version}",
            agenteye_url,
        )
    ]

    if memory_root is not None:
        memory_status, memory_detail = _memory_runtime_status(
            memory_root,
            Path(copilot_home).expanduser() if copilot_home is not None else Path.home(),
        )
        runtimes.append(_runtime("Personal Memory", memory_status, memory_detail))
    else:
        runtimes.append(
            _runtime("Personal Memory", "not_configured", "Memory runtime path is not configured")
        )

    if configured_coach_url and coach_url is None:
        runtimes.append(
            _runtime(
                "AI Coach",
                "invalid_configuration",
                "Coach dashboard URL must be a loopback HTTP URL without credentials or query data",
            )
        )
        coach_root = None
    coach_installed = (
        coach_root is not None and (coach_root / "scripts" / "dashboard_server.py").is_file()
    )
    if coach_installed and coach_url is not None and _probe_coach(coach_url):
        coach_status = "reachable"
        coach_detail = "Dashboard reachable; credentials and model remain local"
    elif coach_installed:
        coach_status = "connection_failed"
        coach_detail = "Runtime installed, but the dashboard is not reachable"
    else:
        coach_status = "not_configured"
        coach_detail = "Coach runtime path is not configured"
    if not configured_coach_url or coach_url is not None:
        runtimes.append(_runtime("AI Coach", coach_status, coach_detail, coach_url))

    if obsidian_vault is not None and (obsidian_vault / ".obsidian").is_dir():
        runtimes.append(
            _runtime("Obsidian", "connected", "Vault detected; task and Daily Note sync available")
        )
    else:
        runtimes.append(
            _runtime("Obsidian", "not_configured", "No configured Obsidian Vault detected")
        )

    lock_path = skills_root / "runtimes.lock.json" if skills_root is not None else None
    if lock_path is not None and lock_path.is_file():
        try:
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            runtimes_config = lock.get("runtimes") if isinstance(lock, dict) else None
            if not isinstance(runtimes_config, dict):
                raise ValueError("invalid runtimes lock")
            runtime_count = len(runtimes_config)
            healthy_statuses = {"reachable", "healthy", "connected"}
            component_checks = runtimes
            healthy_count = sum(
                1 for runtime in component_checks if runtime["status"] in healthy_statuses
            )
            hard_failures = {
                "connection_failed",
                "needs_dependencies",
                "invalid",
                "invalid_configuration",
                "needs_setup",
            }
            if any(runtime["status"] in hard_failures for runtime in component_checks):
                control_status = "unhealthy"
                control_detail = (
                    "Personal Agent control plane · hard runtime failure detected · "
                    f"{healthy_count + 1}/{len(component_checks) + 1} checks verified"
                )
            elif healthy_count == len(component_checks):
                control_status = "healthy"
                control_detail = (
                    f"Personal Agent control plane · "
                    f"{healthy_count + 1}/{len(component_checks) + 1} checks verified"
                )
            else:
                control_status = "degraded"
                control_detail = (
                    f"Personal Agent control plane · "
                    f"{healthy_count + 1}/{len(component_checks) + 1} checks verified · "
                    f"{runtime_count} pinned runtimes"
                )
        except (OSError, json.JSONDecodeError, ValueError):
            control_status = "invalid"
            control_detail = "Control-plane runtime lock could not be read"
    else:
        control_status = "not_configured"
        control_detail = "Personal Agent control plane is not configured"
    runtimes.append(_runtime("Control Plane", control_status, control_detail))
    return {"runtimes": runtimes}
