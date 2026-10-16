import importlib

from fastapi.testclient import TestClient


def test_serves_index_when_dist_present(tmp_path, monkeypatch):
    # Isolate the DB exactly like conftest's client fixture, so create_app()'s
    # init_db() doesn't touch the real data/finance.db.
    from modules import database
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    database.init_db()

    from backend import main
    importlib.reload(main)  # rebuild module-level app against the patched DB_PATH

    # IMPORTANT: patch DIST_DIR *after* reload — reload recomputes DIST_DIR from
    # __file__, which would otherwise clobber an earlier patch.
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(
        "<!doctype html><title>HomeFinance</title>", encoding="utf-8"
    )
    monkeypatch.setattr(main, "DIST_DIR", dist)

    # create_app() reads main.DIST_DIR at call time, so it sees the temp dist
    # and mounts StaticFiles at "/".
    client = TestClient(main.create_app())

    r = client.get("/")
    assert r.status_code == 200
    assert "HomeFinance" in r.text
    assert client.get("/api/health").json() == {"status": "ok"}
