"""Shared schemas for media-owned API payloads."""

from __future__ import annotations

from ninja import Schema


class MediaRenditionsSchema(Schema):
    """Public URLs for the renditions exposed in catalog payloads."""

    thumb: str
    display: str


class UploadedMediaSchema(Schema):
    """A media attachment as surfaced on catalog detail endpoints."""

    asset_uuid: str
    category: str | None = None
    is_primary: bool
    uploaded_by_username: str | None = None
    renditions: MediaRenditionsSchema
