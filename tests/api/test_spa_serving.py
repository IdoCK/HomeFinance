import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client_no_dist(tmp_path, monkeypatch):
    """A TestClient with a temp DB AND a guaranteed-absent web/dist, so the
    dist-absent serving behavior is exercised regardless of whether a real
    web/dist has been built locally (the shared `client` fixture does not
    isolate DIST_DIR, so it would mount StaticFiles once the SPA is built)."""
    from modules import database
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    database.init_db()

    from backend import main
    importlib.reload(main)  # recomputes DIST_DIR from __file__...
    # ...so patch DIST_DIR to an absent path AFTER the reload.
    monkeypatch.setattr(main, "DIST_DIR", tmp_path / "no-dist")
    return TestClient(main.create_app())


def test_api_available_without_dist(client_no_dist):
    # With no web/dist, the app still serves the API and 404s unknown paths
    # rather than crashing at startup.
    assert client_no_dist.get("/api/health").status_code == 200
    assert client_no_dist.get("/definitely-not-a-route").status_code == 404


def test_root_redirects_to_docs_when_dist_absent(client_no_dist):
    # No web/dist -> the bare root redirects to the API docs rather than 404.
    # Disable auto-follow so we can assert the redirect itself.
    r = client_no_dist.get("/", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "/docs"
