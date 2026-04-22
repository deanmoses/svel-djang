"""Canonical citation source seed data, split by source type."""

from apps.citation.seed_data.books import BOOK_SOURCES
from apps.citation.seed_data.magazines import MAGAZINE_SOURCES
from apps.citation.seed_data.websites import WEBSITE_SOURCES

SEED_SOURCES: list[dict[str, object]] = [
    *BOOK_SOURCES,
    *MAGAZINE_SOURCES,
    *WEBSITE_SOURCES,
]

__all__ = ["BOOK_SOURCES", "MAGAZINE_SOURCES", "SEED_SOURCES", "WEBSITE_SOURCES"]
