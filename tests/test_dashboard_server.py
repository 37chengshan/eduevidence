"""Read-only three-page Studio server tests (P3 gate).

The server must expose ONLY the Studio entry, the artifact API, web assets
and baked reports; every simulation/legacy route is rejected (404/405), and
project/theme/path lookups never fall back or escape WEB_DIR.
"""
import json
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PORT = 8899


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server():
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "scripts" / "dashboard_server.py"),
         "--port", str(port)],
        cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/projects", timeout=1)
            break
        except Exception:
            time.sleep(0.25)
    yield f"http://127.0.0.1:{port}"
    proc.send_signal(signal.SIGINT)
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()


def _get(base, path, method="GET", data=None):
    req = urllib.request.Request(base + path, method=method, data=data)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_studio_entry_and_api(server):
    assert _get(server, "/")[0] == 200
    assert _get(server, "/index.html")[0] == 200
    status, body = _get(server, "/api/projects")
    assert status == 200
    data = json.loads(body)
    assert data["stats"]["total_projects"] >= 3
    assert _get(server, "/api/labels")[0] == 200


def test_known_project_viz_and_reports(server):
    assert _get(server, "/api/projects/ai-coding-assistant/viz")[0] == 200
    assert _get(server, "/api/projects/ai-coding-assistant-evidence/viz")[0] == 200
    assert _get(server, "/report?id=ai-coding-assistant&theme=claude")[0] == 200
    assert _get(server, "/report?id=ai-coding-assistant")[0] == 200


def test_unknown_project_404(server):
    assert _get(server, "/api/projects/does-not-exist/viz")[0] == 404
    assert _get(server, "/report?id=does-not-exist")[0] == 404


def test_unknown_theme_404(server):
    assert _get(server, "/report?id=ai-coding-assistant&theme=nope")[0] == 404
    # URL metacharacters must not become a filesystem path or fallback theme.
    assert _get(server, "/report?id=ai-coding-assistant&theme=..%2F..%2FSKILL")[0] == 404

def test_legacy_routes_rejected(server):
    for path in ("/landing.html", "/landing", "/api/paradox/details",
                 "/api/did/sample", "/lieflat/", "/lieflat/basics",
                 "/api/wizard/simulate", "/api/projects/unknown"):
        assert _get(server, path)[0] in (404, 405), path


def test_post_disabled(server):
    status, _ = _get(server, "/api/did/run", method="POST", data=b"{}")
    assert status == 405
    status, _ = _get(server, "/api/wizard/simulate", method="POST", data=b"{}")
    assert status == 405


def test_path_traversal_rejected(server):
    for path in ("/js/%2e%2e/%2e%2e/scripts/dashboard_server.py",
                 "/js/../dashboard_server.py",
                 "/js/%2e%2e/etc/passwd",
                 "/server.py",
                 "/styles.css/../../scripts/dashboard_server.py"):
        assert _get(server, path)[0] == 404, path


def test_web_assets_served_inner_only(server):
    status, body = _get(server, "/js/main.js")
    assert status == 200
    assert b"loadProjects" in body
    assert _get(server, "/js/state.js")[0] == 200
    assert _get(server, "/styles.css")[0] == 200


def test_unknown_path_404(server):
    assert _get(server, "/nonexistent")[0] == 404
    assert _get(server, "/api/unknown")[0] == 404


def test_viz_payload_null_ci_not_zero(server):
    """Missing CI must surface as None/omitted, never coerced to 0 in payload."""
    status, body = _get(server, "/api/projects/ai-coding-assistant-evidence/viz")
    assert status == 200
    data = json.loads(body)
    for item in data.get("forest", []):
        lo, hi = item.get("ci_lower"), item.get("ci_upper")
        # fixture rows either carry both bounds or neither
        assert (lo is None) == (hi is None)