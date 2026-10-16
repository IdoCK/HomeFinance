def test_guide_served_as_html(client):
    """The user guide HTML is reachable at /api/guide and returns the HTML doc,
    even with no web/dist built (the route is registered before the SPA mount).
    It's served under /api so the Vite dev proxy reaches it and the SPA can own
    the in-app /guide route, embedding this content in an iframe."""
    r = client.get("/api/guide")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "<title>Household Finance — User Guide</title>" in r.text


def test_guide_supports_embed_mode(client):
    """The guide ships an embed mode (?embed) that the app uses to hide the
    standalone chrome when showing the guide inside its own page."""
    r = client.get("/api/guide")
    assert 'classList.add("embed")' in r.text
    assert "body.embed aside { display: none; }" in r.text
