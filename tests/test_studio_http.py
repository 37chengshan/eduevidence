"""HTTP boundary: reads never initialize local research, and writes are denied."""
import json
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
import pytest
import scripts.dashboard_server as studio


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(studio, 'RESEARCH_HOME', tmp_path / 'home')
    server = ThreadingHTTPServer(('127.0.0.1', 0), studio.StudioHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{server.server_port}', tmp_path / 'home'
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)


def get(base, path, **kwargs):
    try:
        return urllib.request.urlopen(urllib.request.Request(base + path, **kwargs))
    except urllib.error.HTTPError as error:
        return error


def test_http_read_endpoints_do_not_create_research_home(app):
    base, home = app
    for path in ('/api/studio/catalog', '/api/studio/evolution', '/api/research/projects'):
        with get(base, path) as response:
            assert response.status == 200
            assert response.headers.get('Access-Control-Allow-Origin') is None
            json.load(response)
    assert not home.exists()


def test_http_mutations_and_cross_origin_requests_denied(app):
    base, _ = app
    assert get(base, '/api/studio/catalog', method='POST', data=b'{}').status == 405
    assert get(base, '/api/studio/catalog', headers={'Sec-Fetch-Site':'cross-site'}).status == 403
    assert get(base, '/api/studio/catalog', headers={'Host':'evil.example'}).status == 403


def test_http_studio_assets_and_traversal(app):
    base, _ = app
    for route in ('/studio/', '/studio/config.json'):
        assert get(base, route).status == 200
    assert get(base, '/studio/%2e%2e/%2e%2e/SKILL.md').status == 404
    assert get(base, '/api/studio/projects/project--PRJ-..%2f..%2fsecret').status == 404


def test_missing_built_studio_never_falls_back_to_v5_ui(tmp_path, monkeypatch):
    """If the compiled Studio is absent, the compatibility target is an explicit tombstone."""
    web = tmp_path / 'web'
    web.mkdir()
    tombstone = (
        '<!doctype html><title>Research Studio build unavailable</title>'
        '<main>Compatibility boundary: rebuild web/studio/.</main>'
    )
    (web / 'index.html').write_text(tombstone, encoding='utf-8')
    monkeypatch.setattr(studio, 'WEB_DIR', web)

    server = ThreadingHTTPServer(('127.0.0.1', 0), studio.StudioHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f'http://127.0.0.1:{server.server_port}'
        with get(base, '/') as response:
            assert response.status == 200
            body = response.read().decode('utf-8')
        assert 'Research Studio build unavailable' in body
        assert 'EduEvidence 5.0' not in body
        assert get(base, '/studio/').status == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_http_missing_reports_do_not_return_html_success(app):
    base, _ = app
    assert get(base, '/api/studio/projects/example--not-a-project/report?theme=claude').status == 404
