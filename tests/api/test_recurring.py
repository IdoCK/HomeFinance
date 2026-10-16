from datetime import date, timedelta


def _monthly(desc, n=4, amount=-15.99, category="Subscriptions"):
    today = date.today()
    return [
        {"date": (today - timedelta(days=30 * (n - 1 - i))).isoformat(),
         "description": desc, "amount": amount, "category": category, "source": "card"}
        for i in range(n)
    ]


def test_recurring_detects_monthly_subscription(client, people):
    from modules import database as db
    you = people[0]["id"]
    db.add_transactions(you, _monthly("NETFLIX.COM"))

    r = client.get("/api/recurring", params={"person_id": you})
    assert r.status_code == 200
    data = r.json()
    nflx = next(c for c in data["charges"] if "netflix" in c["vendor"].lower())
    assert nflx["cadence"] == "monthly"
    assert nflx["kind"] == "fixed"
    assert data["committed"]["total"] > 0


def test_recurring_collapses_via_vendor_rule(client, people):
    from modules import database as db
    you = people[0]["id"]
    db.upsert_vendor("Amazon", "amazon,amzn")
    today = date.today()
    variants = ["AMAZON.COM", "AMZN MKTP US", "AMAZON.COM", "AMZN MKTP US"]
    rows = [
        {"date": (today - timedelta(days=30 * (3 - i))).isoformat(),
         "description": d, "amount": -12.99, "category": "Shopping", "source": "card"}
        for i, d in enumerate(variants)
    ]
    db.add_transactions(you, rows)

    data = client.get("/api/recurring", params={"person_id": you}).json()
    amazon = [c for c in data["charges"] if c["vendor"] == "Amazon"]
    assert len(amazon) == 1
    assert amazon[0]["count"] == 4
