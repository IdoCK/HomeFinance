def test_categories_list_add_delete(client, people):
    you = people[0]["id"]
    r = client.put("/api/categories", json={"person_id": you, "name": "Groceries", "keywords": "whole foods,trader"})
    assert r.status_code == 200
    cats = client.get("/api/categories", params={"person_id": you}).json()
    g = next(c for c in cats if c["name"] == "Groceries")
    assert g["keywords"] == "whole foods,trader"

    client.delete(f"/api/categories/{g['id']}")
    assert all(c["name"] != "Groceries" for c in client.get("/api/categories", params={"person_id": you}).json())


def test_category_upsert_updates_existing(client, people):
    you = people[0]["id"]
    client.put("/api/categories", json={"person_id": you, "name": "Dining", "keywords": "chipotle"})
    client.put("/api/categories", json={"person_id": you, "name": "Dining", "keywords": "chipotle,sweetgreen"})
    dining = [c for c in client.get("/api/categories", params={"person_id": you}).json() if c["name"] == "Dining"]
    assert len(dining) == 1
    assert dining[0]["keywords"] == "chipotle,sweetgreen"


def test_categories_scoped_to_person(client, people):
    # init_db seeds a starter taxonomy for every person, so a person is never empty;
    # scoping means a category added for one person does not appear for the other.
    you, spouse = people[0]["id"], people[1]["id"]
    client.put("/api/categories", json={"person_id": you, "name": "MineOnly", "keywords": ""})
    you_names = {c["name"] for c in client.get("/api/categories", params={"person_id": you}).json()}
    spouse_names = {c["name"] for c in client.get("/api/categories", params={"person_id": spouse}).json()}
    assert "MineOnly" in you_names
    assert "MineOnly" not in spouse_names


def test_vendors_list_add_delete(client, people):
    you = people[0]["id"]
    r = client.put("/api/vendors", json={"person_id": you, "name": "Amazon", "keywords": "amazon,amzn"})
    assert r.status_code == 200
    vendors = client.get("/api/vendors", params={"person_id": you}).json()
    a = next(v for v in vendors if v["name"] == "Amazon")
    assert a["keywords"] == "amazon,amzn"

    client.delete(f"/api/vendors/{a['id']}")
    assert all(v["name"] != "Amazon" for v in client.get("/api/vendors", params={"person_id": you}).json())
