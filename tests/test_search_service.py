"""White-box tests for the Search service — FTS queries, pagination, cursor tokens, error modes."""

import pytest
from httpx import AsyncClient


class TestSearchService:
    """Search endpoint tests — FR1, FR3, FR5, FR6."""

    @pytest.mark.asyncio
    async def test_search_by_keyword(self, client: AsyncClient, fresh_user: dict):
        """Searching by keyword finds matching posts."""
        await client.post(
            "/api/v1/posts",
            json={
                "author_id": str(fresh_user["user_id"]),
                "text": "rust programming language",
            },
        )
        response = await client.post(
            "/api/v1/search",
            json={
                "query": "rust",
                "mode": "lexical",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) > 0
        assert any("rust" in r["text_snippet"].lower() for r in data["results"])

    @pytest.mark.asyncio
    async def test_empty_query_returns_422(self, client: AsyncClient):
        """Empty query returns 422."""
        response = await client.post("/api/v1/search", json={"query": ""})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_semantic_mode_returns_501(self, client: AsyncClient):
        """Semantic mode returns 501."""
        response = await client.post(
            "/api/v1/search", json={"query": "test", "mode": "semantic"}
        )
        assert response.status_code == 501

    @pytest.mark.asyncio
    async def test_hybrid_mode_returns_501(self, client: AsyncClient):
        """Hybrid mode returns 501."""
        response = await client.post(
            "/api/v1/search", json={"query": "test", "mode": "hybrid"}
        )
        assert response.status_code == 501

    @pytest.mark.asyncio
    async def test_author_filter(self, client: AsyncClient, fresh_user: dict):
        """Filtering by author_id returns only that author's posts."""
        # Create a second user
        resp2 = await client.post("/api/v1/users", json={"username": "author_b_filter"})
        user_b = resp2.json()

        await client.post(
            "/api/v1/posts",
            json={
                "author_id": str(fresh_user["user_id"]),
                "text": "post from alice",
            },
        )
        await client.post(
            "/api/v1/posts",
            json={
                "author_id": user_b["user_id"],
                "text": "post from bob",
            },
        )

        response = await client.post(
            "/api/v1/search",
            json={
                "query": "post",
                "filters": {"author_id": str(fresh_user["user_id"])},
            },
        )
        data = response.json()
        author_ids = {r["author_id"] for r in data["results"]}
        assert author_ids == {str(fresh_user["user_id"])}

    @pytest.mark.asyncio
    async def test_cursor_pagination(self, client: AsyncClient, fresh_user: dict):
        """Cursor pagination works across pages."""
        for i in range(15):
            await client.post(
                "/api/v1/posts",
                json={
                    "author_id": str(fresh_user["user_id"]),
                    "text": f"pagination test post {i:03d}",
                },
            )

        page1 = await client.post(
            "/api/v1/search",
            json={
                "query": "pagination",
                "page_size": 5,
            },
        )
        p1_data = page1.json()
        assert len(p1_data["results"]) == 5
        assert p1_data["next_page_token"] is not None

        page2 = await client.post(
            "/api/v1/search",
            json={
                "query": "pagination",
                "page_size": 5,
                "page_token": p1_data["next_page_token"],
            },
        )
        p2_data = page2.json()
        assert len(p2_data["results"]) == 5
        assert p2_data["next_page_token"] is not None

        p1_ids = {r["post_id"] for r in p1_data["results"]}
        p2_ids = {r["post_id"] for r in p2_data["results"]}
        assert p1_ids.isdisjoint(p2_ids)

    @pytest.mark.asyncio
    async def test_invalid_page_token_returns_400(self, client: AsyncClient):
        """Malformed page_token returns 400."""
        response = await client.post(
            "/api/v1/search",
            json={
                "query": "test",
                "page_token": "not-a-valid-token",
            },
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_highlighting(self, client: AsyncClient, fresh_user: dict):
        """Search results include text_snippet with <mark> tags and highlights array."""
        await client.post(
            "/api/v1/posts",
            json={
                "author_id": str(fresh_user["user_id"]),
                "text": "the quick brown fox jumps over the lazy dog",
            },
        )
        response = await client.post("/api/v1/search", json={"query": "fox"})
        data = response.json()
        assert len(data["results"]) > 0
        snippet = data["results"][0]["text_snippet"]
        assert "<mark>" in snippet
        assert "fox" in data["results"][0]["highlights"]
