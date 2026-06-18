def test_list_people_returns_two_seeded(client):
    r = client.get("/api/people")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert {p["name"] for p in data} == {"You", "Spouse"}
    assert all(isinstance(p["id"], int) for p in data)


def test_rename_person(client, people):
    pid = people[0]["id"]
    r = client.patch(f"/api/people/{pid}", json={"name": "Avi"})
    assert r.status_code == 200
    assert r.json() == {"id": pid, "name": "Avi"}
    assert any(p["name"] == "Avi" for p in client.get("/api/people").json())
