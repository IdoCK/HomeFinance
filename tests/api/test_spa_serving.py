def test_api_available_without_dist(client):
    # web/dist does not exist in dev/test; the app must still serve the API
    # and simply 404 unknown paths rather than crashing at startup.
    assert client.get("/api/health").status_code == 200
    assert client.get("/definitely-not-a-route").status_code == 404


def test_root_redirects_to_docs_when_dist_absent(client):
    # No web/dist in the test env, so the bare root should redirect to the API docs
    # rather than 404. Disable auto-follow so we can assert the redirect itself.
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "/docs"
