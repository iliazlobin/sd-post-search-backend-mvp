"""Shared fixtures and helpers for the Post Search MVP black-box acceptance suite.

These tests do NOT import `src.post_search`. They talk to the running system
via HTTP at API_BASE_URL. Test isolation is achieved through unique
identifiers per test — no database clearing required.
"""

import os
import uuid

import httpx
import pytest

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def base_url():
    return API_BASE_URL


@pytest.fixture(scope="session")
def client(base_url):
    """Session-scoped httpx client for the entire acceptance run."""
    with httpx.Client(base_url=base_url, timeout=30) as c:
        yield c


@pytest.fixture
def fresh_uuid():
    """Unique UUID per test for isolation."""
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def assert_status(r, expected_status):
    """Assert status and return parsed JSON."""
    assert (
        r.status_code == expected_status
    ), f"Expected {expected_status}, got {r.status_code}: {r.text}"
    if r.status_code == 204:
        return None
    return r.json()


def assert_200(r):
    return assert_status(r, 200)


def assert_201(r):
    return assert_status(r, 201)


def assert_404(r):
    return assert_status(r, 404)


def assert_409(r):
    return assert_status(r, 409)


def assert_422(r):
    return assert_status(r, 422)


def assert_400(r):
    return assert_status(r, 400)


def assert_501(r):
    return assert_status(r, 501)


def create_user(client, username=None):
    """Create a user and return the response dict."""
    if username is None:
        username = f"user_{uuid.uuid4().hex[:8]}"
    r = client.post("/api/v1/users", json={"username": username})
    return assert_201(r)


def create_post(
    client, author_id, text="test post content", language="en", privacy="public"
):
    """Create a post and return the response dict."""
    r = client.post(
        "/api/v1/posts",
        json={
            "author_id": author_id,
            "text": text,
            "language": language,
            "privacy": privacy,
        },
    )
    return assert_201(r)


def search_posts(
    client, query, mode="lexical", filters=None, page_size=20, page_token=None
):
    """Search posts and return the response dict."""
    body = {"query": query, "mode": mode, "page_size": page_size}
    if filters:
        body["filters"] = filters
    if page_token:
        body["page_token"] = page_token
    r = client.post("/api/v1/search", json=body)
    return assert_200(r)
