"""White-box tests for the Post service (CRUD, soft-delete, index status)."""

import pytest


class TestPostService:
    """Post creation, retrieval, soft delete, and index status."""

    @pytest.mark.asyncio
    async def test_create_post(self, client, fresh_user):
        """Creating a post returns 201 with full post data."""
        response = await client.post(
            "/api/v1/posts",
            json={
                "author_id": str(fresh_user["user_id"]),
                "text": "hello world",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["text"] == "hello world"
        assert data["author_id"] == str(fresh_user["user_id"])
        assert data["language"] == "en"
        assert data["privacy"] == "public"
        assert data["like_count"] == 0

    @pytest.mark.asyncio
    async def test_create_post_unknown_author_returns_404(self, client):
        """Creating a post with non-existent author returns 404."""
        response = await client.post(
            "/api/v1/posts",
            json={
                "author_id": "00000000-0000-0000-0000-000000000000",
                "text": "test",
            },
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_post_detail(self, client, fresh_user):
        """Getting a post returns detail with author info."""
        create_resp = await client.post(
            "/api/v1/posts",
            json={
                "author_id": str(fresh_user["user_id"]),
                "text": "detail check",
            },
        )
        post = create_resp.json()

        response = await client.get(f"/api/v1/posts/{post['post_id']}")
        assert response.status_code == 200
        detail = response.json()
        assert detail["post_id"] == post["post_id"]
        assert detail["author"]["user_id"] == str(fresh_user["user_id"])
        assert detail["author"]["username"] == fresh_user["username"]

    @pytest.mark.asyncio
    async def test_index_status(self, client, fresh_user):
        """Index status returns indexed=True for generated tsvector columns."""
        create_resp = await client.post(
            "/api/v1/posts",
            json={
                "author_id": str(fresh_user["user_id"]),
                "text": "indexed post",
            },
        )
        post = create_resp.json()

        response = await client.get(f"/api/v1/posts/{post['post_id']}/index-status")
        assert response.status_code == 200
        status = response.json()
        assert status["indexed"] is True
        assert status["indexed_at"] is not None

    @pytest.mark.asyncio
    async def test_soft_delete(self, client, fresh_user):
        """Soft-deleting a post returns status archived."""
        create_resp = await client.post(
            "/api/v1/posts",
            json={
                "author_id": str(fresh_user["user_id"]),
                "text": "will be deleted",
            },
        )
        post = create_resp.json()

        response = await client.delete(f"/api/v1/posts/{post['post_id']}")
        assert response.status_code == 200
        assert response.json()["status"] == "archived"

        # Post should return 404 on detail
        detail_resp = await client.get(f"/api/v1/posts/{post['post_id']}")
        assert detail_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_already_archived_returns_404(self, client, fresh_user):
        """Deleting an already-archived post returns 404."""
        create_resp = await client.post(
            "/api/v1/posts",
            json={
                "author_id": str(fresh_user["user_id"]),
                "text": "already archived",
            },
        )
        post = create_resp.json()
        await client.delete(f"/api/v1/posts/{post['post_id']}")
        response = await client.delete(f"/api/v1/posts/{post['post_id']}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_empty_text_returns_422(self, client, fresh_user):
        """Empty post text returns 422."""
        response = await client.post(
            "/api/v1/posts",
            json={
                "author_id": str(fresh_user["user_id"]),
                "text": "",
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_language_returns_422(self, client, fresh_user):
        """Unsupported language returns 422."""
        response = await client.post(
            "/api/v1/posts",
            json={
                "author_id": str(fresh_user["user_id"]),
                "text": "hello",
                "language": "xx",
            },
        )
        assert response.status_code == 422
