"""FR3: Filter search results by author, date range, or language.

POST /api/v1/search with filters:{author_id, date_from, date_to, language}
Author filter returns only that author's posts
Date range filtering includes/excludes correctly
Language filter narrows to specified language
Combined filters work together
Filter returning empty results → 200 with empty array
"""

import time

from verify.acceptance.conftest import (
    create_user,
    create_post,
    search_posts,
)


def test_author_filter(client):
    """Filtering by author_id returns only that author's posts."""
    user_a = create_user(client, username="author_a")
    user_b = create_user(client, username="author_b")

    create_post(client, user_a["user_id"], text="post from author A about cats")
    create_post(client, user_a["user_id"], text="another post from author A about dogs")
    create_post(client, user_b["user_id"], text="post from author B about birds")

    results = search_posts(client, "post", filters={"author_id": user_a["user_id"]})

    author_ids = {r["author_id"] for r in results["results"]}
    assert author_ids == {
        user_a["user_id"]
    }, f"Author filter should return only author A's posts: {author_ids}"
    assert (
        len(results["results"]) == 2
    ), f"Expected 2 results from author A, got {len(results['results'])}"


def test_date_range_filter(client):
    """Date range filters include posts within the range and exclude those outside."""
    user = create_user(client, username="dateranger")

    # Create posts; we can't control created_at precisely, so we check with a wide range
    create_post(client, user["user_id"], text="recent post about tech")
    time.sleep(0.1)  # ensure timestamp separation
    create_post(client, user["user_id"], text="also recent post about science")

    # Wide future range should include all
    results_all = search_posts(
        client,
        "post",
        filters={"date_from": "2020-01-01T00:00:00", "date_to": "2030-12-31T23:59:59"},
    )
    assert len(results_all["results"]) >= 2

    # Very narrow past range should exclude all
    results_none = search_posts(
        client,
        "post",
        filters={"date_from": "2020-01-01T00:00:00", "date_to": "2020-01-01T00:00:01"},
    )
    assert (
        len(results_none["results"]) == 0
    ), f"Narrow past range should have 0 results: {results_none}"


def test_language_filter(client):
    """Language filter narrows results to the specified language."""
    user = create_user(client, username="langfilter")

    create_post(
        client, user["user_id"], text="english post about programming", language="en"
    )
    create_post(
        client,
        user["user_id"],
        text="publicación en español sobre programación",
        language="es",
    )

    results_en = search_posts(client, "programming", filters={"language": "en"})
    results_es = search_posts(client, "programación", filters={"language": "es"})

    assert len(results_en["results"]) > 0, "Should find English post"
    assert len(results_es["results"]) > 0, "Should find Spanish post"


def test_combined_filters(client):
    """Multiple filters combined narrow results correctly."""
    user_a = create_user(client, username="combo_author_a")
    user_b = create_user(client, username="combo_author_b")

    create_post(client, user_a["user_id"], text="english tech article", language="en")
    create_post(client, user_a["user_id"], text="spanish tech artículo", language="es")
    create_post(
        client, user_b["user_id"], text="english tech article by B", language="en"
    )

    # Author A + English only
    results = search_posts(
        client,
        "tech",
        filters={
            "author_id": user_a["user_id"],
            "language": "en",
        },
    )

    author_ids = {r["author_id"] for r in results["results"]}
    assert author_ids == {user_a["user_id"]}
    assert (
        len(results["results"]) == 1
    ), f"Combined filter should return 1 result, got {len(results['results'])}"


def test_filter_returns_empty_200(client):
    """Filter that matches nothing returns 200 with empty results array."""
    user = create_user(client, username="empty_filter")
    create_post(client, user["user_id"], text="some post")

    results = search_posts(client, "post", filters={"language": "ja"})

    assert "results" in results
    assert len(results["results"]) == 0
