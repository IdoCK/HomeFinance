def test_guide_served_as_html(client):
    """The standalone user guide is reachable at /guide and returns the HTML doc,
    even with no web/dist built (the route is registered before the SPA mount)."""
    r = client.get("/guide")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "<title>Household Finance — User Guide</title>" in r.text
