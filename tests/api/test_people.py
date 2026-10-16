def test_list_people_returns_two_seeded(client):
    r = client.get("/api/people")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert {p["name"] for p in data} == {"Ido", "Aviv"}
    assert all(isinstance(p["id"], int) for p in data)


def test_rename_person(client, people):
    pid = people[0]["id"]
    r = client.patch(f"/api/people/{pid}", json={"name": "Avi"})
    assert r.status_code == 200
    assert r.json() == {"id": pid, "name": "Avi"}
    assert any(p["name"] == "Avi" for p in client.get("/api/people").json())


def test_rename_to_duplicate_name_returns_409(client, people):
    # Rename people[0] to people[1]'s current name (should fail with 409)
    pid_0 = people[0]["id"]
    existing_name = people[1]["name"]  # "Aviv"
    r = client.patch(f"/api/people/{pid_0}", json={"name": existing_name})
    assert r.status_code == 409
    assert "name already in use" in r.json()["detail"].lower()


def test_rename_missing_person_returns_404(client):
    r = client.patch("/api/people/999999", json={"name": "X"})
    assert r.status_code == 404
