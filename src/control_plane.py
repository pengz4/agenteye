"""Read-only personal-agent stack overview for the Agent Eye dashboard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, new_url):
        return None


def _runtime(name: str, status: str, detail: str, url: str | None = None) -> dict:
    return {"name": name, "status": status, "detail": detail, "url": url}


def _probe_coach(url: str) -> bool:
    if not url.startswith(("http://127.0.0.1:", "http://localhost:")):
        return False
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        with opener.open(url, timeout=2) as response:
            page = response.read(32768)
            return response.status == 200 and any(
                marker in page for marker in (b"AI Coach", b"AI Interview", b"AI/Agent")
            )
    except (URLError, HTTPError, OSError, ValueError):
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


def inspect_control_plane(
    config: dict[str, Any], *, agenteye_version: str
) -> dict[str, list[dict[str, Any]]]:
    """Return safe status cards without exposing private local paths."""
    stack = config.get("stack", {})
    if not isinstance(stack, dict):
        stack = {}

    agenteye_url = _safe_dashboard_url(stack.get("agenteye_url")) or "http://127.0.0.1:5112/"
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
            f"Current dashboard · v{agenteye_version}",
            agenteye_url,
        )
    ]

    if memory_root is not None and (memory_root / "bin" / "personal-memory-mcp.js").is_file():
        dependencies = (memory_root / "node_modules" / "tsx").is_dir()
        runtimes.append(
            _runtime(
                "Personal Memory",
                "installed" if dependencies else "needs_dependencies",
                "Runtime present; MCP host registration is configured separately"
                if dependencies
                else "Runtime present; Node dependencies are missing",
            )
        )
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
            control_status = "configured"
            control_detail = f"Personal Agent control plane · {runtime_count} pinned runtimes"
        except (OSError, json.JSONDecodeError, ValueError):
            control_status = "invalid"
            control_detail = "Control-plane runtime lock could not be read"
    else:
        control_status = "not_configured"
        control_detail = "Personal Agent control plane is not configured"
    runtimes.append(_runtime("Control Plane", control_status, control_detail))
    return {"runtimes": runtimes}
