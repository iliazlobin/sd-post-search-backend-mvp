"""FR5: Cursor-based stateless pagination.

POST /api/v1/search with page_size and page_token
First page returns page_size results + next_page_token
Second page returns different results
Last page returns next_page_token=null
Invalid token → 400
Tampered token → 400
"""

from verify.acceptance.conftest import (
    assert_400,
    create_user,
    create_post,
    search_posts,
)


def test_first_page_returns_page_size_results(client):
    """The first page returns exactly page_size results + next_page_token."""
    user = create_user(client, username="pager_fr5")

    # Create 25 posts with distinct searchable content
    for i in range(25):
        create_post(
            client, user["user_id"], text=f"pagination test post number {i:03d}"
        )

    results = search_posts(client, "pagination", page_size=10)

    assert (
        len(results["results"]) == 10
    ), f"First page should have 10 results, got {len(results['results'])}"
    assert results["next_page_token"] is not None, "Should have next_page_token"


def test_second_page_returns_different_results(client):
    """The second page returns different posts from the first page."""
    user = create_user(client, username="page2_fr5")

    for i in range(15):
        create_post(client, user["user_id"], text=f"page two test post {i:03d}")

    page1 = search_posts(client, "page two", page_size=5)
    page1_ids = {r["post_id"] for r in page1["results"]}
    assert len(page1_ids) == 5

    assert page1["next_page_token"] is not None
    page2 = search_posts(
        client, "page two", page_size=5, page_token=page1["next_page_token"]
    )
    page2_ids = {r["post_id"] for r in page2["results"]}
    assert len(page2_ids) == 5

    # No overlap between pages
    assert page1_ids.isdisjoint(
        page2_ids
    ), f"Pages should return different posts: page1={page1_ids}, page2={page2_ids}"


def test_last_page_returns_null_token(client):
    """The last page returns next_page_token=null."""
    user = create_user(client, username="lastpage_fr5")

    for i in range(8):
        create_post(client, user["user_id"], text=f"last page test post {i:03d}")

    results = search_posts(client, "last page", page_size=10)

    assert len(results["results"]) <= 8
    assert (
        results["next_page_token"] is None
    ), f"Last page should have null next_page_token: {results}"


def test_invalid_token_returns_400(client):
    """A malformed or garbage page_token returns 400."""
    r = client.post(
        "/api/v1/search",
        json={
            "query": "test",
            "mode": "lexical",
            "page_token": "not-a-valid-token",
        },
    )
    assert_400(r)


def test_tampered_token_returns_400(client):
    """A token with a valid-looking structure but invalid HMAC returns 400."""
    user = create_user(client, username="tamper_fr5")

    for i in range(15):
        create_post(client, user["user_id"], text=f"tamper test post {i:03d}")

    page1 = search_posts(client, "tamper", page_size=5)
    assert page1["next_page_token"] is not None

    # Try to decode and tamper with the token
    # The token is base64-encoded JSON + HMAC; tampering the payload
    # should fail signature verification
    r = client.post(
        "/api/v1/search",
        json={
            "query": "tamper",
            "mode": "lexical",
            "page_token": page1["next_page_token"] + "x",  # append to break signature
        },
    )
    assert_400(r)


def test_page_size_respected(client):
    """Custom page_size parameter is respected."""
    user = create_user(client, username="pagesize_fr5")

    for i in range(30):
        create_post(client, user["user_id"], text=f"page size test post {i:03d}")

    results_small = search_posts(client, "page size", page_size=3)
    results_large = search_posts(client, "page size", page_size=20)

    assert len(results_small["results"]) == 3
    assert len(results_large["results"]) == 20
