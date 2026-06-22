import json


def test_preview_returns_payload_and_key_flag(client, people):
    r = client.get("/api/insights/preview", params={"person_id": people[0]["id"]})
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["payload"], str)
    assert isinstance(body["has_key"], bool)
    # payload is the exact anonymized JSON that would be sent — must parse.
    json.loads(body["payload"])


def test_preview_joint_is_household(client):
    # No person_id => Joint => household: one summary per person + shared-goals household.
    r = client.get("/api/insights/preview")
    assert r.status_code == 200
    summaries = json.loads(r.json()["payload"])
    labels = [s["who"] for s in summaries]
    assert "Person A" in labels and "Person B" in labels
    assert any("Household" in lbl for lbl in labels)
    # Anonymized: no real seeded names ("Ido"/"Aviv") leak into the payload.
    assert "Ido" not in labels and "Aviv" not in labels


def test_generate_returns_text(client, people):
    r = client.post("/api/insights/generate", json={"person_id": people[0]["id"]})
    assert r.status_code == 200
    assert isinstance(r.json()["text"], str)
    assert r.json()["text"]  # non-empty (preview-mode message when no API key)
