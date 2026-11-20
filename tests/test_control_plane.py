import json
from http.client import IncompleteRead
from unittest.mock import MagicMock, patch

import pytest

from src.control_plane import inspect_control_plane


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
        )

    by_name = {item["name"]: item for item in result["runtimes"]}
    assert by_name["Agent Eye"]["status"] == "reachable"
    assert by_name["Personal Memory"]["status"] == "installed"
    assert by_name["AI Coach"]["status"] == "reachable"
    assert by_name["AI Coach"]["url"] == "http://127.0.0.1:8765/"
    assert by_name["Obsidian"]["status"] == "connected"
    assert by_name["Control Plane"]["status"] == "configured"


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
