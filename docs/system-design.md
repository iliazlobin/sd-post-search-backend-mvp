# Post Search MVP — System Design

This document is the architect's full design. See `DESIGN.md` in the project root for the complete specification, including architecture diagram, data model with generated tsvector columns, API spec for all 7 endpoints, per-FR implementation flows, and key design decisions with evidence-backed trade-off analysis.

Key architecture highlights:

- Single FastAPI process on port 8000
- PostgreSQL 16 with generated `to_tsvector` column + GIN index
- Three-layer separation: routers → services → data
- Cursor-based pagination with HMAC-signed opaque tokens
- ts_headline for result snippet generation

See `design.md` for the full 387-line architect spec.
