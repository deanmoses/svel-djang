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
    uploaded_by_username: str
    renditions: MediaRenditionsSchema


class RenditionUrlsSchema(Schema):
    """Rendition URLs returned in the upload response. Includes ``original``,
    unlike the public-facing :class:`MediaRenditionsSchema`.
    """

    original: str
    thumb: str
    display: str


class AttachmentMetaSchema(Schema):
    """Echo of where an upload was attached, returned inside
    :class:`UploadSchema`.
    """

    entity_type: str
    public_id: str
    category: str | None


class UploadSchema(Schema):
    asset_uuid: str
    kind: str
    status: str
    original_filename: str
    width: int
    height: int
    renditions: RenditionUrlsSchema
    attachment: AttachmentMetaSchema


class MediaAssetInputSchema(Schema):
    entity_type: str
    public_id: str
    asset_uuid: str


class MediaSetCategoryInputSchema(MediaAssetInputSchema):
    category: str
