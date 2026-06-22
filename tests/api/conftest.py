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
    return TestClient(main.create_app())


@pytest.fixture()
def people(client):
    return client.get("/api/people").json()
