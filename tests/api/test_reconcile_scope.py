"""Task 1.2 — per-statement reconciliation scoped to (person, file_hash).

Tests verify:
- Two statements in different currencies for the same person reconcile INDEPENDENTLY.
- The endpoint returns { statements: [...] } with one entry per statement.
- Each statement entry carries its own currency (not converted to a global display).
- No single pooled chain is produced across all transactions.
"""

import pytest


def test_per_statement_reconcile_independent(client, people):
    """Two statements (USD + ILS) for the same person reconcile independently.
    Each result has its own currency; amounts are raw statement-currency values."""
    from modules import database as db

    you = people[0]["id"]

    # USD statement: opening 1000, two moves
    fh_usd = "stmt-usd-001"
    db.add_transactions(you, [
        {"date": "2026-05-01", "description": "Open USD",
         "amount": -200.0, "category": "x", "source": "bank",
         "balance": 800.0, "currency": "USD"},
        {"date": "2026-05-02", "description": "Deposit USD",
         "amount": 500.0, "category": "x", "source": "bank",
         "balance": 1300.0, "currency": "USD"},
    ], file_hash=fh_usd)
    db.record_import(you, fh_usd, "may-usd.csv", 2, "2026-06-01T00:00:00")

    # ILS statement: opening 5000, one move
    fh_ils = "stmt-ils-001"
    db.add_transactions(you, [
        {"date": "2026-05-01", "description": "Open ILS",
         "amount": -500.0, "category": "x", "source": "bank",
         "balance": 4500.0, "currency": "ILS"},
        {"date": "2026-05-15", "description": "Salary ILS",
         "amount": 3000.0, "category": "x", "source": "bank",
         "balance": 7500.0, "currency": "ILS"},
    ], file_hash=fh_ils)
    db.record_import(you, fh_ils, "may-ils.csv", 2, "2026-06-01T00:00:00")

    r = client.get("/api/networth/reconcile", params={"person_id": you}).json()

    # Response shape must be { statements: [...] }
    assert "statements" in r, f"Expected 'statements' key, got: {list(r.keys())}"
    stmts = r["statements"]

    # Two independent results — NOT one pooled chain
    assert len(stmts) == 2, f"Expected 2 per-statement results, got {len(stmts)}"

    by_hash = {s["filename"]: s for s in stmts}

    usd = by_hash["may-usd.csv"]
    assert usd["currency"] == "USD"
    assert usd["begin"] == 1000.0   # 800 - (-200) = 1000
    assert usd["end"] == 1300.0
    assert usd["ok"] is True

    ils = by_hash["may-ils.csv"]
    assert ils["currency"] == "ILS"
    assert ils["begin"] == 5000.0   # 4500 - (-500) = 5000
    assert ils["end"] == 7500.0
    assert ils["ok"] is True


def test_per_statement_result_shape(client, people):
    """Each statement entry carries filename, currency, begin, end,
    computed_end, discrepancy, n, chain_breaks, ok."""
    from modules import database as db

    you = people[0]["id"]
    fh = "stmt-shape-001"
    db.add_transactions(you, [
        {"date": "2026-05-01", "description": "A",
         "amount": 100.0, "category": "x", "source": "bank",
         "balance": 1100.0, "currency": "USD"},
        {"date": "2026-05-02", "description": "B",
         "amount": -50.0, "category": "x", "source": "bank",
         "balance": 1050.0, "currency": "USD"},
    ], file_hash=fh)
    db.record_import(you, fh, "shape-test.csv", 2, "2026-06-01T00:00:00")

    r = client.get("/api/networth/reconcile", params={"person_id": you}).json()
    assert "statements" in r
    stmt = r["statements"][0]

    for key in ("filename", "currency", "begin", "end", "computed_end",
                "discrepancy", "n", "chain_breaks", "ok"):
        assert key in stmt, f"Missing key '{key}' in statement result"


def test_no_pooled_chain_across_currencies(client, people):
    """When two statements exist, the old reconcilable/ok/begin/end flat keys
    are NOT present — only { statements: [...] }."""
    from modules import database as db

    you = people[0]["id"]
    fh = "stmt-no-pool-001"
    db.add_transactions(you, [
        {"date": "2026-05-01", "description": "X",
         "amount": 100.0, "category": "x", "source": "bank",
         "balance": 1100.0, "currency": "USD"},
        {"date": "2026-05-02", "description": "Y",
         "amount": -50.0, "category": "x", "source": "bank",
         "balance": 1050.0, "currency": "USD"},
    ], file_hash=fh)
    db.record_import(you, fh, "no-pool.csv", 2, "2026-06-01T00:00:00")

    r = client.get("/api/networth/reconcile", params={"person_id": you}).json()

    # The old flat keys must NOT appear at the top level
    assert "reconcilable" not in r, "Old pooled 'reconcilable' key must not be present"
    assert "ok" not in r, "Old pooled 'ok' key must not be present"
    assert "begin" not in r, "Old pooled 'begin' key must not be present"


def test_statement_without_balance_column_excluded(client, people):
    """A credit-card feed (no running balance) yields no entry in statements."""
    from modules import database as db

    you = people[0]["id"]
    fh = "stmt-nobal-001"
    db.add_transactions(you, [
        {"date": "2026-05-01", "description": "Card charge",
         "amount": -30.0, "category": "x", "source": "credit_card",
         "currency": "USD"},  # no balance key
    ], file_hash=fh)
    db.record_import(you, fh, "visa.csv", 1, "2026-06-01T00:00:00")

    r = client.get("/api/networth/reconcile", params={"person_id": you}).json()
    assert "statements" in r
    # No balance data → analytics.reconcile returns None → excluded
    assert len(r["statements"]) == 0


def test_joint_reconcile_pools_all_persons(client, people):
    """When no person_id is given (joint view), all persons' statements appear."""
    from modules import database as db

    ido = people[0]["id"]
    aviv = people[1]["id"]

    fh_ido = "stmt-ido-001"
    db.add_transactions(ido, [
        {"date": "2026-05-01", "description": "Ido A",
         "amount": 200.0, "category": "x", "source": "bank",
         "balance": 1200.0, "currency": "USD"},
        {"date": "2026-05-02", "description": "Ido B",
         "amount": -100.0, "category": "x", "source": "bank",
         "balance": 1100.0, "currency": "USD"},
    ], file_hash=fh_ido)
    db.record_import(ido, fh_ido, "ido.csv", 2, "2026-06-01T00:00:00")

    fh_aviv = "stmt-aviv-001"
    db.add_transactions(aviv, [
        {"date": "2026-05-01", "description": "Aviv A",
         "amount": 500.0, "category": "x", "source": "bank",
         "balance": 5500.0, "currency": "ILS"},
        {"date": "2026-05-03", "description": "Aviv B",
         "amount": -300.0, "category": "x", "source": "bank",
         "balance": 5200.0, "currency": "ILS"},
    ], file_hash=fh_aviv)
    db.record_import(aviv, fh_aviv, "aviv.csv", 2, "2026-06-01T00:00:00")

    r = client.get("/api/networth/reconcile").json()
    assert "statements" in r
    assert len(r["statements"]) == 2

    names = {s["filename"] for s in r["statements"]}
    assert "ido.csv" in names
    assert "aviv.csv" in names
