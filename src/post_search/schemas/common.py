"""Cursor token helpers — encode/decode with HMAC signature.

Token structure (payload is base64url-encoded JSON, then HMAC-signed with SECRET_KEY):

    <base64url(payload)>.<base64url(signature)>

Payload schema:
    {
        "query_hash": "sha256 hex of query string",
        "last_score": float,
        "last_post_id": "uuid hex"
    }
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json

from post_search.config import settings


def _hmac_key() -> bytes:
    return settings.secret_key.encode("utf-8")


def _hash_query(query: str) -> str:
    return hashlib.sha256(query.encode("utf-8")).hexdigest()


def encode_token(last_score: float, last_post_id: str, query: str) -> str:
    """Build a signed cursor token."""
    payload = {
        "query_hash": _hash_query(query),
        "last_score": last_score,
        "last_post_id": last_post_id,
    }
    payload_b64 = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).decode()
    signature = hmac.new(_hmac_key(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def decode_token(token: str, expected_query: str) -> dict | None:
    """Verify HMAC signature and return the decoded payload, or None if invalid."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, signature = parts
        expected_sig = hmac.new(
            _hmac_key(), payload_b64.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None
        payload: dict = json.loads(base64.urlsafe_b64decode(payload_b64).decode())
        # Verify query_hash matches the current query
        if payload.get("query_hash") != _hash_query(expected_query):
            return None
        return payload
    except (json.JSONDecodeError, ValueError, Exception):
        return None
