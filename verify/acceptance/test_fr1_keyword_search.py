"""FR1: Search posts by keyword or phrase with relevance-ranked results.

POST /api/v1/search — lexical search mode
Finds posts matching keywords in text
Results ranked by relevance (score descending)
Phrase search with quotes
Empty query → 422
Unsupported mode (semantic/hybrid) → 501
"""

from verify.acceptance.conftest import (
    assert_422,
    assert_501,
    create_user,
    create_post,
    search_posts,
)


def test_search_by_keyword_finds_matching_posts(client):
    """Searching by a keyword finds posts containing that word."""
    user = create_user(client, username="searcher_fr1")
    create_post(client, user["user_id"], text="learning rust is fun and productive")
    create_post(client, user["user_id"], text="python is great too")
    create_post(client, user["user_id"], text="completely unrelated content")

    results = search_posts(client, "rust")

    post_texts = [r["text_snippet"].lower() for r in results["results"]]
    assert any(
        "rust" in t for t in post_texts
    ), f"Expected to find 'rust' in results: {results}"
    assert not any(
        "completely" in t for t in post_texts
    ), f"Unrelated post should not appear: {results}"


def test_search_results_ranked_by_relevance(client):
    """Results are ordered by score descending (more relevant first)."""
    user = create_user(client, username="ranker_fr1")
    # Post A: "rust" appears once
    create_post(
        client, user["user_id"], text="rust is one of many programming languages"
    )
    # Post B: "rust" appears twice
    create_post(client, user["user_id"], text="rust programming rust language guide")

    results = search_posts(client, "rust")

    scores = [r["score"] for r in results["results"]]
    assert (
        len(scores) >= 2
    ), f"Expected at least 2 results, got {len(scores)}: {results}"
    # Higher score = more relevant; first result should have highest score
    assert (
        scores[0] >= scores[1]
    ), f"Results should be ranked by score descending: {scores}"


def test_phrase_search_with_quotes(client):
    """Quoted phrases match exact word sequences."""
    user = create_user(client, username="phraser_fr1")
    create_post(
        client, user["user_id"], text="machine learning is transforming industries"
    )
    create_post(client, user["user_id"], text="the machine is learning slowly")

    # Phrase search: only exact sequence matches
    results = search_posts(client, '"machine learning"')

    post_texts = [r["text_snippet"].lower() for r in results["results"]]
    # "machine learning" as contiguous phrase should match the first post
    matching = [t for t in post_texts if "machine learning" in t]
    assert len(matching) > 0, f"Phrase 'machine learning' should match: {results}"


def test_empty_query_returns_422(client):
    """Empty query string is rejected."""
    r = client.post("/api/v1/search", json={"query": "", "mode": "lexical"})
    assert_422(r)


def test_semantic_mode_returns_501(client):
    """Semantic search mode is not implemented in MVP."""
    r = client.post("/api/v1/search", json={"query": "test", "mode": "semantic"})
    assert_501(r)


def test_hybrid_mode_returns_501(client):
    """Hybrid search mode is not implemented in MVP."""
    r = client.post("/api/v1/search", json={"query": "test", "mode": "hybrid"})
    assert_501(r)


def test_search_case_insensitive(client):
    """Search is case-insensitive."""
    user = create_user(client, username="casecheck_fr1")
    create_post(client, user["user_id"], text="RUST programming language")

    results_lower = search_posts(client, "rust")
    results_upper = search_posts(client, "RUST")

    assert len(results_lower["results"]) == len(results_upper["results"])
    assert len(results_lower["results"]) > 0
