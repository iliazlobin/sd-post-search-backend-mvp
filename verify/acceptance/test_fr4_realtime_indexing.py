"""FR4: Near real-time indexing — posts searchable immediately on creation.

POST /api/v1/posts → 201
GET /api/v1/posts/{id} → 200 with post detail
GET /api/v1/posts/{id}/index-status → {indexed: true}
Post is searchable immediately after creation
Soft delete (DELETE) removes post from search results
Archived post excluded from search but detail returns 404
404 on unknown author_id
422 on empty text or invalid language
"""

from verify.acceptance.conftest import (
    assert_200,
    assert_201,
    assert_404,
    assert_422,
    create_user,
    search_posts,
)


def test_create_post_returns_201(client):
    """Creating a post returns 201 with the full post object."""
    user = create_user(client, username="poster_fr4")
    r = client.post(
        "/api/v1/posts",
        json={
            "author_id": user["user_id"],
            "text": "hello world this is a test post",
        },
    )
    data = assert_201(r)
    assert data["post_id"] is not None
    assert data["text"] == "hello world this is a test post"
    assert data["author_id"] == user["user_id"]
    assert data["language"] == "en"
    assert data["privacy"] == "public"
    assert data["like_count"] == 0
    assert data["created_at"] is not None


def test_post_immediately_searchable(client):
    """A newly created post appears in search results immediately."""
    user = create_user(client, username="instant_fr4")
    post = client.post(
        "/api/v1/posts",
        json={
            "author_id": user["user_id"],
            "text": "immediate search indexing test keyword ZYZZYVA",
        },
    )
    data = assert_201(post)

    results = search_posts(client, "ZYZZYVA")
    post_ids = {r["post_id"] for r in results["results"]}
    assert data["post_id"] in post_ids, (
        f"New post should be immediately searchable: {results}"
    )


def test_index_status_returns_indexed_true(client):
    """Index status endpoint confirms post is indexed."""
    user = create_user(client, username="indexstat_fr4")
    post = client.post(
        "/api/v1/posts",
        json={
            "author_id": user["user_id"],
            "text": "check my index status",
        },
    )
    data = assert_201(post)

    r = client.get(f"/api/v1/posts/{data['post_id']}/index-status")
    status = assert_200(r)
    assert status["indexed"] is True, f"Post should be indexed: {status}"
    assert status["indexed_at"] is not None


def test_post_detail_returns_200(client):
    """GET /api/v1/posts/{id} returns post with author info."""
    user = create_user(client, username="detail_fr4")
    post = client.post(
        "/api/v1/posts",
        json={
            "author_id": user["user_id"],
            "text": "post with detail view",
        },
    )
    data = assert_201(post)

    r = client.get(f"/api/v1/posts/{data['post_id']}")
    detail = assert_200(r)
    assert detail["post_id"] == data["post_id"]
    assert detail["text"] == "post with detail view"
    assert detail["author"]["user_id"] == user["user_id"]
    assert detail["author"]["username"] == user["username"]


def test_soft_delete_removes_from_search(client):
    """Deleting a post (soft delete) excludes it from search results."""
    user = create_user(client, username="softdel_fr4")
    post = client.post(
        "/api/v1/posts",
        json={
            "author_id": user["user_id"],
            "text": "this post will be deleted XYZZY",
        },
    )
    data = assert_201(post)

    # Verify it's searchable
    results_before = search_posts(client, "XYZZY")
    assert len(results_before["results"]) >= 1

    # Soft delete
    r = client.delete(f"/api/v1/posts/{data['post_id']}")
    assert_200(r)

    # Should not appear in search
    results_after = search_posts(client, "XYZZY")
    assert len(results_after["results"]) == 0, (
        f"Deleted post should not appear in search: {results_after}"
    )

    # Detail returns 404 for archived post
    r2 = client.get(f"/api/v1/posts/{data['post_id']}")
    assert_404(r2)


def test_create_post_unknown_author_returns_404(client):
    """Creating a post with a non-existent author_id returns 404."""
    r = client.post(
        "/api/v1/posts",
        json={
            "author_id": "00000000-0000-0000-0000-000000000000",
            "text": "post with unknown author",
        },
    )
    assert_404(r)


def test_create_post_empty_text_returns_422(client):
    """Creating a post with empty text returns 422."""
    user = create_user(client, username="emptytext_fr4")
    r = client.post(
        "/api/v1/posts",
        json={
            "author_id": user["user_id"],
            "text": "",
        },
    )
    assert_422(r)


def test_create_post_invalid_language_returns_422(client):
    """Creating a post with an unsupported language returns 422."""
    user = create_user(client, username="badlang_fr4")
    r = client.post(
        "/api/v1/posts",
        json={
            "author_id": user["user_id"],
            "text": "hello",
            "language": "xx",
        },
    )
    assert_422(r)
