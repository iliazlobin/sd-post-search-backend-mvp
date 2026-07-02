"""White-box tests for the health endpoint."""

import pytest


class TestHealth:
    """GET /healthz → 200 {status: ok}."""

    @pytest.mark.asyncio
    async def test_healthz_returns_200(self, client):
        response = await client.get("/healthz")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
