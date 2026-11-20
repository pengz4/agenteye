import json
from unittest.mock import MagicMock, patch

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
