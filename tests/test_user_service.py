"""White-box tests for the User service and endpoint."""

import pytest


class TestUserService:
    """User creation — uniqueness, validation."""

    @pytest.mark.asyncio
    async def test_create_user(self, client):
        """POST /api/v1/users creates a user and returns 201."""
        response = await client.post("/api/v1/users", json={"username": "alice"})
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "alice"
        assert "user_id" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_duplicate_username_returns_409(self, client):
        """Creating a user with an existing username returns 409."""
        await client.post("/api/v1/users", json={"username": "bob"})
        response = await client.post("/api/v1/users", json={"username": "bob"})
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_empty_username_returns_422(self, client):
        """Empty username returns 422."""
        response = await client.post("/api/v1/users", json={"username": ""})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_long_username_returns_422(self, client):
        """Username over 50 chars returns 422."""
        response = await client.post("/api/v1/users", json={"username": "a" * 51})
        assert response.status_code == 422
