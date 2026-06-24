import importlib
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A TestClient bound to a fresh temp SQLite DB with the two seeded people."""
    from modules import database
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    database.init_db()  # creates schema + seeds "Ido" / "Aviv" into the temp db

    from backend import main
    importlib.reload(main)  # rebuild app against the patched DB_PATH
    app = main.create_app()
    # init_db seeds a starter USD->ILS display rate so the production currency
    # toggle works out of the box. FX tests drive rates from a clean table, so
    # drop the seed here (after the app's own init_db has run) — each test then
    # sets exactly the rates it needs.
    with database.get_conn() as conn:
        conn.execute("DELETE FROM fx_rates")
    return TestClient(app)


@pytest.fixture()
def people(client):
    return client.get("/api/people").json()
