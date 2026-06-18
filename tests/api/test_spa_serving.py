def test_api_available_without_dist(client):
    # web/dist does not exist in dev/test; the app must still serve the API
    # and simply 404 unknown paths rather than crashing at startup.
    assert client.get("/api/health").status_code == 200
    assert client.get("/definitely-not-a-route").status_code == 404
