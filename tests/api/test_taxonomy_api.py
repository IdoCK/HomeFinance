import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi.testclient import TestClient
from backend.main import create_app


def _client(tmp_path, monkeypatch):
    from modules import database
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "finance.db")
    database.init_db()
    return TestClient(create_app())


def test_categories_global_regardless_of_person(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.put("/api/categories", json={"person_id": 1, "name": "Travel", "keywords": "airline"})
    a = client.get("/api/categories", params={"person_id": 1}).json()
    b = client.get("/api/categories", params={"person_id": 2}).json()
    assert [c["name"] for c in a] == [c["name"] for c in b]
    assert any(c["name"] == "Travel" for c in a)


def test_vendors_global_regardless_of_person(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.put("/api/vendors", json={"person_id": 2, "name": "Foo", "keywords": "foo"})
    a = client.get("/api/vendors", params={"person_id": 1}).json()
    assert any(v["name"] == "Foo" for v in a)
