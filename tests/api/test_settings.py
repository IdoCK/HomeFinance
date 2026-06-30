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


def test_group_vendor_appends_keyword_to_existing_group(client, people):
    you = people[0]["id"]
    client.put("/api/vendors", json={"person_id": you, "name": "Whole Foods", "keywords": "whole foods"})
    r = client.post("/api/vendors/group", json={"person_id": you, "target": "Whole Foods", "keyword": "wholefds ues"})
    assert r.status_code == 200
    assert "wholefds ues" in r.json()["keywords"]
    wf = next(v for v in client.get("/api/vendors", params={"person_id": you}).json() if v["name"] == "Whole Foods")
    assert set(k.strip() for k in wf["keywords"].split(",")) == {"whole foods", "wholefds ues"}


def test_group_vendor_seeds_new_group_with_target_name(client, people):
    """Folding into an auto merchant key (no rule yet) seeds the rule with the
    target's own name first, so the target's existing rows stay grouped too."""
    you = people[0]["id"]
    r = client.post("/api/vendors/group", json={"person_id": you, "target": "trader joes", "keyword": "tj maxx"})
    assert r.status_code == 200
    tj = next(v for v in client.get("/api/vendors", params={"person_id": you}).json() if v["name"] == "trader joes")
    assert set(k.strip() for k in tj["keywords"].split(",")) == {"trader joes", "tj maxx"}


def test_group_vendor_is_idempotent(client, people):
    you = people[0]["id"]
    client.post("/api/vendors/group", json={"person_id": you, "target": "Costco", "keyword": "costco whse"})
    client.post("/api/vendors/group", json={"person_id": you, "target": "Costco", "keyword": "costco whse"})
    costco = next(v for v in client.get("/api/vendors", params={"person_id": you}).json() if v["name"] == "Costco")
    assert costco["keywords"].count("costco whse") == 1


def test_ungroup_vendor_removes_one_member(client, people):
    you = people[0]["id"]
    client.put("/api/vendors", json={"person_id": you, "name": "lelabar", "keywords": "lelabar,tst* sforno"})
    r = client.post("/api/vendors/ungroup", json={"person_id": you, "target": "lelabar", "keyword": "tst* sforno"})
    assert r.status_code == 200
    assert r.json()["keywords"] == ["lelabar"]
    lela = next(v for v in client.get("/api/vendors", params={"person_id": you}).json() if v["name"] == "lelabar")
    assert lela["keywords"] == "lelabar"


def test_ungroup_vendor_deletes_rule_when_last_member_removed(client, people):
    you = people[0]["id"]
    client.put("/api/vendors", json={"person_id": you, "name": "solo", "keywords": "solo"})
    r = client.post("/api/vendors/ungroup", json={"person_id": you, "target": "solo", "keyword": "solo"})
    assert r.status_code == 200
    assert r.json()["keywords"] == []
    assert all(v["name"] != "solo" for v in client.get("/api/vendors", params={"person_id": you}).json())
