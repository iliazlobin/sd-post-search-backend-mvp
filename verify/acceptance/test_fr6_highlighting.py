"""FR6: Highlight matching terms in returned post snippets.

POST /api/v1/search results include:
- text_snippet with <mark> tags around matching terms
- highlights array containing matching terms (plain text)
No <mark> tags when query doesn't match
Multiple matching terms all highlighted
"""

from verify.acceptance.conftest import (
    create_user,
    create_post,
    search_posts,
)


def test_text_snippet_contains_mark_tags(client):
    """Search results include text_snippet with <mark> tags around matching terms."""
    user = create_user(client, username="highlighter_fr6")
    create_post(
        client, user["user_id"], text="the quick brown fox jumps over the lazy dog"
    )

    results = search_posts(client, "fox")

    assert len(results["results"]) > 0
    snippet = results["results"][0]["text_snippet"]
    assert (
        "<mark>fox</mark>" in snippet.lower() or "<mark>Fox</mark>" in snippet
    ), f"Expected <mark> around 'fox' in snippet: {snippet}"


def test_highlights_array_contains_matching_terms(client):
    """The highlights array contains plain-text matching terms."""
    user = create_user(client, username="higharray_fr6")
    create_post(
        client,
        user["user_id"],
        text="rust programming language for systems programming",
    )

    results = search_posts(client, "programming")

    assert len(results["results"]) > 0
    highlights = results["results"][0]["highlights"]
    assert (
        "programming" in highlights
    ), f"Highlights should contain 'programming': {highlights}"


def test_multiple_terms_highlighted(client):
    """Multiple matching terms in a post are all highlighted."""
    user = create_user(client, username="multihigh_fr6")
    create_post(
        client, user["user_id"], text="docker containers and kubernetes orchestration"
    )

    results = search_posts(client, "docker kubernetes")

    assert len(results["results"]) > 0
    snippet = results["results"][0]["text_snippet"].lower()
    assert (
        "<mark>docker</mark>" in snippet
    ), f"Expected <mark> around 'docker': {snippet}"
    assert (
        "<mark>kubernetes</mark>" in snippet
    ), f"Expected <mark> around 'kubernetes': {snippet}"


def test_no_highlights_for_non_matching_query(client):
    """Results still have text_snippet and highlights fields even when no terms match."""
    user = create_user(client, username="nomatch_fr6")
    create_post(client, user["user_id"], text="coffee and tea are great beverages")

    results = search_posts(client, "coffee")

    assert len(results["results"]) > 0
    result = results["results"][0]
    assert "text_snippet" in result
    assert "highlights" in result
    # "coffee" should be highlighted
    assert "coffee" in result["highlights"]


def test_highlighting_with_phrase_search(client):
    """Phrase search highlights the entire phrase."""
    user = create_user(client, username="phrasehigh_fr6")
    create_post(
        client, user["user_id"], text="machine learning is transforming the world"
    )

    results = search_posts(client, '"machine learning"')

    assert len(results["results"]) > 0
    snippet = results["results"][0]["text_snippet"].lower()
    # Both words should be highlighted when they form the phrase
    assert (
        "<mark>machine</mark>" in snippet
    ), f"Expected <mark> around 'machine': {snippet}"
    assert (
        "<mark>learning</mark>" in snippet
    ), f"Expected <mark> around 'learning': {snippet}"
