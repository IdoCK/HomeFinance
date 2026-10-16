import io


def test_parse_applies_upload_currency_default(client, monkeypatch):
    # Force the LLM-spec path to a deterministic spec so the test is offline.
    from modules import agent_parser as ap
    monkeypatch.setattr(ap, "_call_ollama", lambda *a, **k: {
        "header_row": 0, "data_starts_row": 1, "date_col": 0, "desc_col": 1, "amount_col": 2,
        "spend_is_negative": True})
    monkeypatch.setattr(ap, "categorize_with_agent", lambda *a, **k: {})

    pid = client.get("/api/people").json()[0]["id"]
    csv = b"Date,Desc,Amount\n2026-03-13,STORE,-100.00\n"
    res = client.post("/api/import/parse",
                      files={"file": ("s.csv", io.BytesIO(csv), "text/csv")},
                      data={"source": "bank", "person_id": str(pid), "currency": "ILS"})
    rows = res.json()["rows"]
    assert rows and rows[0]["currency"] == "ILS"
    assert rows[0]["currency_source"] in ("file_default", "cell_symbol", "column")
