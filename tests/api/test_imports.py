from modules import agent_parser

SAMPLE_ROWS = [
    {"date": "2026-06-01", "description": "WHOLE FOODS", "amount": -52.10,
     "category": "Groceries", "source": "bank", "included": True, "balance": None},
    {"date": "2026-06-02", "description": "PAYROLL", "amount": 3000.0,
     "category": "Income", "source": "bank", "included": True, "balance": None},
]


def test_status_is_200_even_when_ollama_offline(client):
    r = client.get("/api/import/status")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["ok"], bool)
    assert isinstance(body["message"], str)


def test_parse_returns_rows_and_hash(client, people, monkeypatch):
    monkeypatch.setattr(agent_parser, "parse_file_with_agent",
                        lambda *a, **k: (SAMPLE_ROWS, ["skipped 1 row"]))
    r = client.post(
        "/api/import/parse",
        data={"source": "bank", "person_id": people[0]["id"]},
        files={"file": ("june.csv", b"date,desc,amt\n2026-06-01,WF,-52.10", "text/csv")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["already_imported"] is False
    assert len(body["rows"]) == 2
    assert body["warnings"] == ["skipped 1 row"]
    assert len(body["file_hash"]) == 64  # sha256 hex


def test_commit_inserts_rows(client, people):
    you = people[0]["id"]
    r = client.post("/api/import/commit", json={
        "person_id": you, "filename": "june.csv", "file_hash": "a" * 64,
        "source": "bank", "rows": SAMPLE_ROWS,
    })
    assert r.status_code == 200
    assert r.json()["imported"] == 2
    txns = client.get("/api/transactions", params={"person_id": you}).json()
    assert {t["description"] for t in txns} == {"WHOLE FOODS", "PAYROLL"}


def test_parse_flags_already_imported(client, people, monkeypatch):
    you = people[0]["id"]
    monkeypatch.setattr(agent_parser, "parse_file_with_agent",
                        lambda *a, **k: (SAMPLE_ROWS, []))
    content = b"date,desc,amt\n2026-06-01,WF,-52.10"
    first = client.post(
        "/api/import/parse",
        data={"source": "bank", "person_id": you},
        files={"file": ("june.csv", content, "text/csv")},
    ).json()
    # Commit it under its real hash, then re-parse the same bytes.
    client.post("/api/import/commit", json={
        "person_id": you, "filename": "june.csv", "file_hash": first["file_hash"],
        "source": "bank", "rows": SAMPLE_ROWS,
    })
    again = client.post(
        "/api/import/parse",
        data={"source": "bank", "person_id": you},
        files={"file": ("june.csv", content, "text/csv")},
    ).json()
    assert again["already_imported"] is True
