"""Health check: GET /healthz → 200."""

from verify.acceptance.conftest import assert_200


def test_healthz_returns_200(client):
    """The health endpoint returns 200 OK."""
    r = client.get("/healthz")
    data = assert_200(r)
    assert data["status"] == "ok"
