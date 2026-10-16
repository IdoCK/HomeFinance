def test_goals_returns_progress(client, people):
    from modules import database as db
    you = people[0]["id"]
    db.add_goal(you, "Emergency fund", 10000.0, 2500.0, "2026-12-31", "short", "")

    r = client.get("/api/goals", params={"person_id": you})
    assert r.status_code == 200
    g = r.json()[0]
    assert g["name"] == "Emergency fund"
    assert g["percent"] == 25.0
    assert g["monthly_needed"] is not None


def test_add_goal_creates_row(client, people):
    you = people[0]["id"]
    r = client.post("/api/goals", json={"person_id": you, "name": "Car", "target_amount": 20000})
    assert r.status_code == 200
    goals = client.get("/api/goals", params={"person_id": you}).json()
    assert any(g["name"] == "Car" and g["saved_amount"] == 0 for g in goals)


def test_update_saved_recomputes_percent(client, people):
    from modules import database as db
    you = people[0]["id"]
    db.add_goal(you, "Vacation", 5000.0, 0.0, None, "short", "")
    gid = client.get("/api/goals", params={"person_id": you}).json()[0]["id"]

    r = client.patch(f"/api/goals/{gid}", json={"saved_amount": 1500})
    assert r.status_code == 200
    g = client.get("/api/goals", params={"person_id": you}).json()[0]
    assert g["saved_amount"] == 1500
    assert g["percent"] == 30.0


def test_create_goal_persists_horizon_and_notes(client, people):
    you = people[0]["id"]
    client.post("/api/goals", json={"person_id": you, "name": "House", "target_amount": 100000,
                                     "horizon": "long", "notes": "20% down payment"})
    g = client.get("/api/goals", params={"person_id": you}).json()[0]
    assert g["horizon"] == "long"
    assert g["notes"] == "20% down payment"


def test_update_goal_notes(client, people):
    from modules import database as db
    you = people[0]["id"]
    db.add_goal(you, "Vacation", 5000.0, 0.0, None, "short", "")
    gid = client.get("/api/goals", params={"person_id": you}).json()[0]["id"]

    r = client.patch(f"/api/goals/{gid}/notes", json={"notes": "Maldives in spring"})
    assert r.status_code == 200
    g = client.get("/api/goals", params={"person_id": you}).json()[0]
    assert g["notes"] == "Maldives in spring"


def test_delete_goal(client, people):
    from modules import database as db
    you = people[0]["id"]
    db.add_goal(you, "Temp", 100.0, 0.0, None, "short", "")
    gid = client.get("/api/goals", params={"person_id": you}).json()[0]["id"]

    client.delete(f"/api/goals/{gid}")
    assert client.get("/api/goals", params={"person_id": you}).json() == []


def test_joint_returns_all_goals(client, people):
    from modules import database as db
    you = people[0]["id"]
    db.add_goal(you, "Mine", 100.0, 0.0, None, "short", "")
    db.add_goal(None, "Shared", 200.0, 0.0, None, "long", "")

    names = {g["name"] for g in client.get("/api/goals").json()}  # no person_id -> Joint -> all
    assert {"Mine", "Shared"} <= names
