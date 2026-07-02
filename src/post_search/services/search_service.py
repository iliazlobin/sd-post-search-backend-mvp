"""Search service — tsquery builder, filter application, ts_rank scoring, ts_headline highlights, cursor pagination.

Uses raw SQL with asyncpg through SQLAlchemy's text() execution because
Postgres FTS functions (websearch_to_tsquery, ts_rank, ts_headline) are
not expressible through the ORM query builder.
"""

from __future__ import annotations

import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from post_search.schemas.common import decode_token, encode_token
from post_search.schemas.search import SearchRequest, SearchResponse, SearchResult


class SearchServiceError(Exception):
    """Base exception for search service errors."""


class UnsupportedMode(SearchServiceError):
    """Raised when search mode is semantic or hybrid (not in MVP)."""


class InvalidPageToken(SearchServiceError):
    """Raised when page_token is malformed, tampered, or doesn't match the query."""


class SearchService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(self, data: SearchRequest) -> SearchResponse:
        """Execute a keyword search with optional filters and cursor pagination."""
        if data.mode in ("semantic", "hybrid"):
            raise UnsupportedMode(f"{data.mode} search not available in MVP")

        return await self._lexical_search(data)

    async def _lexical_search(self, data: SearchRequest) -> SearchResponse:
        """Execute a lexical (full-text) search.

        NOTE: fts_vector is always built with to_tsvector('english', text)
        regardless of the post's language column. We therefore always use
        'english' for tsquery generation and ts_headline. The language
        filter, when set, only narrows by the `language` column — it does
        not change the FTS configuration. Multi-language tsvector columns
        are a V2 optimization (design.md D6).
        """

        params: dict = {
            "query_text": data.query,
            "limit": data.page_size + 1,  # fetch one extra to detect has-more
        }

        # Where clauses
        where_clauses = ["p.is_archived = false"]

        # Author filter
        if data.filters and data.filters.author_id:
            params["author_id"] = data.filters.author_id
            where_clauses.append("p.author_id = :author_id")

        # Date range filters
        if data.filters and data.filters.date_from:
            params["date_from"] = data.filters.date_from
            where_clauses.append("p.created_at >= :date_from")
        if data.filters and data.filters.date_to:
            params["date_to"] = data.filters.date_to
            where_clauses.append("p.created_at <= :date_to")

        # Language filter (on the service-side config, not the column — the tsvector
        # is always built with 'english', but we filter by language column)
        if data.filters and data.filters.language:
            params["filter_language"] = data.filters.language
            where_clauses.append("p.language = :filter_language")

        # Cursor pagination
        if data.page_token:
            decoded = decode_token(data.page_token, data.query)
            if decoded is None:
                raise InvalidPageToken("invalid or tampered page_token")
            params["last_score"] = decoded["last_score"]
            params["last_post_id"] = decoded["last_post_id"]
            where_clauses.append(
                "(ts_rank(p.fts_vector, sq.q), p.post_id::text) < (:last_score, :last_post_id)"
            )

        where_sql = " AND ".join(where_clauses)

        sql = text(f"""
            WITH search_query AS (
                SELECT websearch_to_tsquery('english', :query_text) AS q
            )
            SELECT p.post_id, p.author_id, u.username AS author_username,
                   p.text, p.language, p.created_at, p.like_count,
                   ts_rank(p.fts_vector, sq.q) AS score,
                   ts_headline('english', p.text, sq.q,
                       'MaxWords=50 MinWords=20 ShortWord=3 MaxFragments=3 StartSel=<mark> StopSel=</mark>'
                   ) AS text_snippet
            FROM posts p
            JOIN users u ON p.author_id = u.user_id
            CROSS JOIN search_query sq
            WHERE p.fts_vector @@ sq.q
              AND {where_sql}
            ORDER BY score DESC, p.post_id DESC
            LIMIT :limit
        """)

        result = await self.session.execute(sql, params)
        rows = result.fetchall()

        has_more = len(rows) > data.page_size
        if has_more:
            rows = rows[: data.page_size]

        results: list[SearchResult] = []
        for row in rows:
            snippet: str = row.text_snippet or ""
            highlights = re.findall(r"<mark>(.*?)</mark>", snippet, re.IGNORECASE)

            results.append(
                SearchResult(
                    post_id=row.post_id,
                    author_id=row.author_id,
                    author_username=row.author_username,
                    text_snippet=snippet,
                    highlights=highlights,
                    score=float(row.score),
                    created_at=row.created_at,
                )
            )

        next_page_token: str | None = None
        if has_more and results:
            last = results[-1]
            next_page_token = encode_token(
                last_score=last.score,
                last_post_id=str(last.post_id),
                query=data.query,
            )

        return SearchResponse(results=results, next_page_token=next_page_token)
