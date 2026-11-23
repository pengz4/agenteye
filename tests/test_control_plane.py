import json
from http.client import IncompleteRead
from unittest.mock import MagicMock, patch

import pytest

from src.control_plane import CoachStartError, inspect_control_plane, start_coach


def test_inspect_control_plane_reports_runtime_links_and_status(tmp_path):
    skills = tmp_path / "skills"
    memory = tmp_path / "memory"
    coach = tmp_path / "coach"
    vault = tmp_path / "vault"
    skills.mkdir()
    (skills / "runtimes.lock.json").write_text(
        json.dumps({"runtimes": {"agenteye": {}, "memory": {}, "coach": {}}}),
        encoding="utf-8",
    )
    (memory / "bin").mkdir(parents=True)
    (memory / "bin" / "personal-memory-mcp.js").write_text("", encoding="utf-8")
    (memory / "node_modules" / "tsx").mkdir(parents=True)
    (coach / "scripts").mkdir(parents=True)
    (coach / "scripts" / "dashboard_server.py").write_text("", encoding="utf-8")
    (vault / ".obsidian").mkdir(parents=True)

    response = MagicMock(status=200)
    response.__enter__.return_value = response
    response.__exit__.return_value = None
    response.read.return_value = b"<title>AI Coach</title>"
    with patch("src.control_plane.build_opener") as opener:
        opener.return_value.open.return_value = response
        result = inspect_control_plane(
            {
                "stack": {
                    "skills_root": str(skills),
                    "memory_root": str(memory),
                    "coach_root": str(coach),
                    "coach_url": "http://127.0.0.1:8765/",
                    "obsidian_vault": str(vault),
                }
            },
            agenteye_version="1.3.0",
            personal_version="1.3.0-personal.8",
            copilot_home=tmp_path / "home",
        )

    by_name = {item["name"]: item for item in result["runtimes"]}
    assert by_name["Agent Eye"]["status"] == "reachable"
    assert by_name["Agent Eye"]["detail"] == "Current dashboard · v1.3.0-personal.8"
    assert by_name["Personal Memory"]["status"] == "installed"
    assert by_name["AI Coach"]["status"] == "reachable"
    assert by_name["AI Coach"]["url"] == "http://127.0.0.1:8765/"
    assert by_name["Obsidian"]["status"] == "connected"
    assert by_name["Control Plane"]["status"] == "degraded"


def test_personal_memory_is_healthy_when_runtime_and_mcp_registration_match(tmp_path):
    memory = tmp_path / "memory"
    (memory / "bin").mkdir(parents=True)
    (memory / "bin" / "personal-memory-mcp.js").write_text("", encoding="utf-8")
    (memory / "node_modules" / "tsx").mkdir(parents=True)
    home = tmp_path / "home"
    (home / ".copilot").mkdir(parents=True)
    repository = home / "memory-repository"
    repository.mkdir()
    command = tmp_path / "node"
    command.write_text("#!/bin/sh\n", encoding="utf-8")
    command.chmod(0o755)
    script = memory / "bin" / "personal-memory-mcp.js"
    (home / ".copilot" / "mcp-config.json").write_text(
        json.dumps({
            "mcpServers": {
                "personal-agent-memory": {
                    "type": "local",
                    "command": str(command),
                    "args": [str(script)],
                    "env": {
                        "MEMORY_ACCOUNT_ID": "pengz4",
                        "MEMORY_DEVICE": "company",
                        "MEMORY_REPOSITORY_DIR": str(repository),
                    },
                }
            }
        }),
        encoding="utf-8",
    )

    result = inspect_control_plane(
        {"stack": {"memory_root": str(memory)}},
        agenteye_version="1.3.0",
        personal_version="1.3.0-personal.8",
        copilot_home=home,
    )

    memory_runtime = next(
        item for item in result["runtimes"] if item["name"] == "Personal Memory"
    )
    assert memory_runtime["status"] == "healthy"
    assert "MCP registration" in memory_runtime["detail"]


def test_control_plane_is_healthy_when_all_runtime_checks_pass(tmp_path):
    skills = tmp_path / "skills"
    coach = tmp_path / "coach"
    vault = tmp_path / "vault"
    skills.mkdir()
    (skills / "runtimes.lock.json").write_text(
        json.dumps({"runtimes": {"agenteye": {}, "memory": {}, "coach": {}}}),
        encoding="utf-8",
    )
    (coach / "scripts").mkdir(parents=True)
    (coach / "scripts" / "dashboard_server.py").write_text("", encoding="utf-8")
    (vault / ".obsidian").mkdir(parents=True)

    with (
        patch(
            "src.control_plane._memory_runtime_status",
            return_value=("healthy", "Runtime and MCP registration verified"),
        ),
        patch("src.control_plane._probe_coach", return_value=True),
    ):
        result = inspect_control_plane(
            {
                "stack": {
                    "skills_root": str(skills),
                    "memory_root": str(tmp_path / "memory"),
                    "coach_root": str(coach),
                    "coach_url": "http://127.0.0.1:8765/",
                    "obsidian_vault": str(vault),
                }
            },
            agenteye_version="1.3.0",
            personal_version="1.3.0-personal.8",
        )

    control = next(item for item in result["runtimes"] if item["name"] == "Control Plane")
    assert control["status"] == "healthy"
    assert "5/5" in control["detail"]


def test_control_plane_is_unhealthy_for_hard_runtime_failures(tmp_path):
    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "runtimes.lock.json").write_text(
        json.dumps({"runtimes": {"agenteye": {}, "memory": {}, "coach": {}}}),
        encoding="utf-8",
    )
    coach = tmp_path / "coach"
    (coach / "scripts").mkdir(parents=True)
    (coach / "scripts" / "dashboard_server.py").write_text("", encoding="utf-8")

    with (
        patch(
            "src.control_plane._memory_runtime_status",
            return_value=("needs_dependencies", "Dependencies missing"),
        ),
        patch("src.control_plane._probe_coach", return_value=False),
    ):
        result = inspect_control_plane(
            {
                "stack": {
                    "skills_root": str(skills),
                    "memory_root": str(tmp_path / "memory"),
                    "coach_root": str(coach),
                    "coach_url": "http://127.0.0.1:8765/",
                    "obsidian_vault": str(tmp_path / "missing-vault"),
                }
            },
            agenteye_version="1.3.0",
        )

    control = next(item for item in result["runtimes"] if item["name"] == "Control Plane")
    assert control["status"] == "unhealthy"


def test_memory_registration_must_resolve_to_configured_entrypoint(tmp_path):
    memory = tmp_path / "memory"
    other = tmp_path / "other"
    (memory / "bin").mkdir(parents=True)
    (memory / "node_modules" / "tsx").mkdir(parents=True)
    (other / "bin").mkdir(parents=True)
    configured = memory / "bin" / "personal-memory-mcp.js"
    unrelated = other / "bin" / "personal-memory-mcp.js"
    configured.write_text("", encoding="utf-8")
    unrelated.write_text("", encoding="utf-8")
    home = tmp_path / "home"
    (home / ".copilot").mkdir(parents=True)
    repository = home / "repository"
    repository.mkdir()
    command = tmp_path / "node"
    command.write_text("#!/bin/sh\n", encoding="utf-8")
    command.chmod(0o755)
    (home / ".copilot" / "mcp-config.json").write_text(
        json.dumps({
            "mcpServers": {
                "personal-agent-memory": {
                    "type": "local",
                    "command": str(command),
                    "args": [str(unrelated)],
                    "env": {
                        "MEMORY_ACCOUNT_ID": "pengz4",
                        "MEMORY_DEVICE": "company",
                        "MEMORY_REPOSITORY_DIR": str(repository),
                    },
                }
            }
        }),
        encoding="utf-8",
    )

    result = inspect_control_plane(
        {"stack": {"memory_root": str(memory)}},
        agenteye_version="1.3.0",
        copilot_home=home,
    )
    memory_runtime = next(
        item for item in result["runtimes"] if item["name"] == "Personal Memory"
    )
    assert memory_runtime["status"] == "installed"


def test_inspect_control_plane_redacts_private_paths(tmp_path):
    result = inspect_control_plane(
        {
            "stack": {
                "skills_root": "/secret/private/control-plane",
                "memory_root": "/secret/private/memory",
                "coach_root": "/secret/private/coach",
                "coach_url": "http://127.0.0.1:8765/",
                "obsidian_vault": "/secret/private/vault",
            }
        },
        agenteye_version="1.3.0",
    )

    serialized = json.dumps(result)
    assert "/secret/private" not in serialized


def test_inspect_control_plane_sanitizes_dashboard_urls():
    result = inspect_control_plane(
        {
            "stack": {
                "agenteye_url": "file:///home/alice/private/dashboard",
                "coach_url": "http://user:secret@127.0.0.1:8765/?token=secret",
            }
        },
        agenteye_version="1.3.0",
    )

    by_name = {item["name"]: item for item in result["runtimes"]}
    assert by_name["Agent Eye"]["url"] == "http://127.0.0.1:5111/"
    assert by_name["AI Coach"]["url"] is None
    assert by_name["AI Coach"]["status"] == "invalid_configuration"


def test_default_agenteye_url_uses_packaged_default_port():
    result = inspect_control_plane({}, agenteye_version="1.3.0")
    agenteye = next(item for item in result["runtimes"] if item["name"] == "Agent Eye")
    assert agenteye["url"] == "http://127.0.0.1:5111/"


def test_active_request_origin_overrides_stale_configured_agenteye_port():
    result = inspect_control_plane(
        {"stack": {"agenteye_url": "http://127.0.0.1:5112/"}},
        agenteye_version="1.3.0",
        active_agenteye_url="http://127.0.0.1:8088/",
    )

    agenteye = next(item for item in result["runtimes"] if item["name"] == "Agent Eye")
    assert agenteye["url"] == "http://127.0.0.1:8088/"


def test_missing_roots_do_not_probe_current_working_directory(tmp_path, monkeypatch):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "personal-memory-mcp.js").write_text("", encoding="utf-8")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "dashboard_server.py").write_text("", encoding="utf-8")
    (tmp_path / "runtimes.lock.json").write_text('{"runtimes": {}}', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = inspect_control_plane({}, agenteye_version="1.3.0")

    by_name = {item["name"]: item for item in result["runtimes"]}
    assert by_name["Personal Memory"]["status"] == "not_configured"
    assert by_name["AI Coach"]["status"] == "not_configured"
    assert by_name["Obsidian"]["status"] == "not_configured"
    assert by_name["Control Plane"]["status"] == "not_configured"


@pytest.mark.parametrize(
    "lock_payload",
    ["[]", '{"runtimes":[]}', '{"runtimes":null}'],
)
def test_invalid_lock_shapes_do_not_raise(tmp_path, lock_payload):
    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "runtimes.lock.json").write_text(lock_payload, encoding="utf-8")

    result = inspect_control_plane(
        {"stack": {"skills_root": str(skills)}},
        agenteye_version="1.3.0",
    )

    control = next(item for item in result["runtimes"] if item["name"] == "Control Plane")
    assert control["status"] == "invalid"


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:8765/",
        "http://127.0.0.1/",
        "http://[::1]:8765/",
    ],
)
def test_probe_coach_uses_same_loopback_validation_as_card_url(url):
    from src.control_plane import _probe_coach

    response = MagicMock(status=200)
    response.__enter__.return_value = response
    response.__exit__.return_value = None
    response.read.return_value = b"<title>AI Coach</title>"
    with patch("src.control_plane.build_opener") as opener:
        opener.return_value.open.return_value = response
        assert _probe_coach(url) is True
    opener.return_value.open.assert_called_once()


def test_probe_coach_treats_truncated_response_as_unreachable():
    from src.control_plane import _probe_coach

    response = MagicMock(status=200)
    response.__enter__.return_value = response
    response.__exit__.return_value = None
    response.read.side_effect = IncompleteRead(b"", 100)
    with patch("src.control_plane.build_opener") as opener:
        opener.return_value.open.return_value = response
        assert _probe_coach("http://127.0.0.1:8765/") is False


def test_start_coach_launches_only_configured_dashboard_and_waits_until_ready(tmp_path):
    coach = tmp_path / "coach"
    script = coach / "scripts" / "dashboard_server.py"
    script.parent.mkdir(parents=True)
    script.write_text("", encoding="utf-8")
    process = MagicMock()
    process.pid = 4321
    process.poll.return_value = None

    with (
        patch("src.control_plane._probe_coach", side_effect=[False, False, True]),
        patch("src.control_plane.subprocess.Popen", return_value=process) as popen,
        patch("src.control_plane.time.sleep"),
    ):
        result = start_coach({
            "stack": {
                "coach_root": str(coach),
                "coach_url": "http://127.0.0.1:8765/",
            }
        })

    assert result == {
        "started": True,
        "status": "reachable",
        "url": "http://127.0.0.1:8765/",
    }
    args = popen.call_args.args[0]
    assert args[-5:] == [
        str(script),
        "--host",
        "127.0.0.1",
        "--port",
        "8765",
    ]
    assert popen.call_args.kwargs["cwd"] == coach


@pytest.mark.parametrize(
    ("coach_root", "coach_url"),
    [
        (None, "http://127.0.0.1:8765/"),
        ("/tmp/not-a-coach", "http://127.0.0.1:8765/"),
        ("/tmp/not-a-coach", "https://example.com/coach"),
    ],
)
def test_start_coach_rejects_incomplete_or_non_loopback_configuration(
    coach_root,
    coach_url,
):
    with pytest.raises(CoachStartError):
        start_coach({
            "stack": {
                "coach_root": coach_root,
                "coach_url": coach_url,
            }
        })
