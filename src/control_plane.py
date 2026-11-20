"""Read-only personal-agent stack overview for the Agent Eye dashboard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
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
    except (URLError, HTTPError, OSError):
        return False


def inspect_control_plane(
    config: dict[str, Any], *, agenteye_version: str
) -> dict[str, list[dict[str, Any]]]:
    """Return safe status cards without exposing private local paths."""
    stack = config.get("stack", {})
    if not isinstance(stack, dict):
        stack = {}

    agenteye_url = str(stack.get("agenteye_url") or "http://127.0.0.1:5112/")
    coach_url = str(stack.get("coach_url") or "http://127.0.0.1:8765/")
    skills_root = Path(str(stack.get("skills_root") or ""))
    memory_root = Path(str(stack.get("memory_root") or ""))
    coach_root = Path(str(stack.get("coach_root") or ""))
    obsidian_vault = Path(str(stack.get("obsidian_vault") or ""))

    runtimes = [
        _runtime(
            "Agent Eye",
            "reachable",
            f"Current dashboard · v{agenteye_version}",
            agenteye_url,
        )
    ]

    if (memory_root / "bin" / "personal-memory-mcp.js").is_file():
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

    coach_installed = (coach_root / "scripts" / "dashboard_server.py").is_file()
    if coach_installed and _probe_coach(coach_url):
        coach_status = "reachable"
        coach_detail = "Dashboard reachable; credentials and model remain local"
    elif coach_installed:
        coach_status = "connection_failed"
        coach_detail = "Runtime installed, but the dashboard is not reachable"
    else:
        coach_status = "not_configured"
        coach_detail = "Coach runtime path is not configured"
    runtimes.append(_runtime("AI Coach", coach_status, coach_detail, coach_url))

    if (obsidian_vault / ".obsidian").is_dir():
        runtimes.append(
            _runtime("Obsidian", "connected", "Vault detected; task and Daily Note sync available")
        )
    else:
        runtimes.append(
            _runtime("Obsidian", "not_configured", "No configured Obsidian Vault detected")
        )

    lock_path = skills_root / "runtimes.lock.json"
    if lock_path.is_file():
        try:
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            runtime_count = len(lock.get("runtimes", {}))
            control_status = "configured"
            control_detail = f"Personal Agent control plane · {runtime_count} pinned runtimes"
        except (OSError, json.JSONDecodeError):
            control_status = "invalid"
            control_detail = "Control-plane runtime lock could not be read"
    else:
        control_status = "not_configured"
        control_detail = "Personal Agent control plane is not configured"
    runtimes.append(_runtime("Control Plane", control_status, control_detail))
    return {"runtimes": runtimes}
