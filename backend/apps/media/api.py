"""Media upload API endpoint."""

from __future__ import annotations

import logging
import uuid as uuid_lib
from pathlib import PurePosixPath

from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from ninja import File, Form, Router, Schema, Status, UploadedFile
from ninja.errors import HttpError
from ninja.security import django_auth

from apps.catalog.claims import build_media_attachment_claim
from apps.catalog.resolve import resolve_media_attachments
from apps.core.models import MediaSupported
from apps.provenance.models import Claim
from apps.media.constants import (
    ALLOWED_IMAGE_EXTENSIONS,
    MAX_IMAGE_FILE_SIZE,
    MAX_UPLOADS_PER_HOUR,
    THUMB_MAX_DIMENSION,
    DISPLAY_MAX_DIMENSION,
)
from apps.media.models import EntityMedia, MediaAsset, MediaRendition
from apps.media.processing import (
    InvalidImageError,
    check_codec_support,
    generate_rendition,
    process_original,
    validate_image,
)
from apps.media.storage import (
    build_public_url,
    build_storage_key,
    delete_from_storage,
    upload_to_storage,
)

logger = logging.getLogger(__name__)

media_router = Router(tags=["media", "private"])

# Extensions that require optional codecs.
_CODEC_EXTENSIONS: dict[str, str] = {
    ".heic": "heic",
    ".heif": "heif",
    ".avif": "avif",
}


def _delete_media_storage_after_commit(storage_keys: list[str]) -> None:
    """Delete storage files after a successful DB commit."""
    try:
        delete_from_storage(storage_keys)
    except Exception:
        logger.exception("Storage cleanup failed for %d keys", len(storage_keys))


def _check_rate_limit(user_id: int) -> None:
    """Best-effort per-user upload rate limiting via cache.

    Only checks the limit — does not increment. Call _incr_rate_limit()
    after a successful upload so failed attempts don't consume quota.
    """
    key = f"media_upload_count:{user_id}"
    count = cache.get_or_set(key, 0, 3600)
    if count >= MAX_UPLOADS_PER_HOUR:
        raise HttpError(429, "Upload limit exceeded. Try again later.")


def _incr_rate_limit(user_id: int) -> None:
    """Increment the upload counter after a successful upload."""
    key = f"media_upload_count:{user_id}"
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, 3600)


class RenditionUrlsOut(Schema):
    original: str
    thumb: str
    display: str


class AttachmentMetaOut(Schema):
    entity_type: str
    slug: str
    category: str | None
    is_primary: bool


class UploadOut(Schema):
    asset_uuid: str
    kind: str
    status: str
    original_filename: str
    width: int
    height: int
    renditions: RenditionUrlsOut
    attachment: AttachmentMetaOut


class MediaAssetRefIn(Schema):
    entity_type: str
    slug: str
    asset_uuid: str


def _resolve_entity(entity_type: str, slug: str):
    """Resolve entity_type + slug to (ContentType, entity instance).

    Derives the model name by stripping hyphens from entity_type
    (e.g. "machine-model" -> "machinemodel"), matching ContentType.model.
    No registry needed — any model that inherits MediaSupported is valid.

    Returns (content_type, entity) or raises HttpError.
    """
    model_name = entity_type.replace("-", "")
    try:
        ct = ContentType.objects.get(model=model_name)
    except ContentType.DoesNotExist:
        raise HttpError(400, f"Unknown entity_type '{entity_type}'.")
    except ContentType.MultipleObjectsReturned:
        raise HttpError(400, f"Ambiguous entity_type '{entity_type}'.")

    model_class = ct.model_class()
    if model_class is None or not issubclass(model_class, MediaSupported):
        raise HttpError(400, f"{entity_type} does not support media attachments.")

    entity = model_class.objects.filter(slug=slug).first()
    if entity is None:
        raise HttpError(400, f"{entity_type} '{slug}' not found.")

    return ct, entity


@media_router.post("/upload/", response=UploadOut, auth=django_auth)
def upload_media(
    request,
    file: UploadedFile = File(...),
    entity_type: str = Form(...),
    slug: str = Form(...),
    category: str | None = Form(None),
    is_primary: bool = Form(False),
):
    """Upload an image and create MediaAsset + MediaRendition rows."""
    # --- Rate limit ---
    _check_rate_limit(request.user.id)

    # --- Validate file extension ---
    original_filename = file.name or "upload"
    ext = PurePosixPath(original_filename).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HttpError(400, f"File type '{ext}' is not allowed.")

    # --- Codec pre-flight ---
    codec_name = _CODEC_EXTENSIONS.get(ext)
    if codec_name:
        support = check_codec_support()
        if not support.get(codec_name):
            raise HttpError(
                400,
                f"{ext.lstrip('.').upper()} format is not supported on this server.",
            )

    # --- Read and check size ---
    data = file.read()
    if len(data) > MAX_IMAGE_FILE_SIZE:
        size_mb = MAX_IMAGE_FILE_SIZE // (1024 * 1024)
        raise HttpError(400, f"File exceeds maximum size of {size_mb} MB.")

    # --- Resolve entity and validate category ---
    ct, entity = _resolve_entity(entity_type, slug)
    try:
        # Validate category early (asset_pk=0 is a placeholder — only category
        # validation runs here; the real claim is built after asset creation).
        build_media_attachment_claim(
            entity,
            0,
            category=category,
            is_primary=is_primary,
        )
    except ValueError as exc:
        raise HttpError(400, str(exc))

    # --- Validate image ---
    try:
        validate_image(data)
    except InvalidImageError as exc:
        raise HttpError(400, f"Invalid image: {exc}")

    # --- Process ---
    try:
        original = process_original(data)
        thumb = generate_rendition(data, THUMB_MAX_DIMENSION)
        display = generate_rendition(data, DISPLAY_MAX_DIMENSION)
    except InvalidImageError as exc:
        raise HttpError(400, f"Image processing failed: {exc}")

    # --- Build storage keys ---
    asset_uuid = uuid_lib.uuid4()

    key_original = build_storage_key(asset_uuid, "original")
    key_thumb = build_storage_key(asset_uuid, "thumb")
    key_display = build_storage_key(asset_uuid, "display")

    # --- Upload to storage ---
    uploaded_keys: list[str] = []
    try:
        for key, processed in [
            (key_original, original),
            (key_thumb, thumb),
            (key_display, display),
        ]:
            upload_to_storage(key, processed.data, processed.mime_type)
            uploaded_keys.append(key)
    except Exception:
        logger.exception(
            "Storage upload failed, cleaning up %d keys", len(uploaded_keys)
        )
        delete_from_storage(uploaded_keys)
        raise HttpError(500, "Storage upload failed.")

    # --- Create DB rows ---
    try:
        with transaction.atomic():
            asset = MediaAsset.objects.create(
                uuid=asset_uuid,
                kind=MediaAsset.Kind.IMAGE,
                status=MediaAsset.Status.READY,
                original_filename=original_filename,
                mime_type=original.mime_type,
                byte_size=len(original.data),
                width=original.width,
                height=original.height,
                uploaded_by=request.user,
            )

            renditions_data = [
                ("original", original),
                ("thumb", thumb),
                ("display", display),
            ]
            for rtype, processed in renditions_data:
                MediaRendition.objects.create(
                    asset=asset,
                    rendition_type=rtype,
                    mime_type=processed.mime_type,
                    byte_size=len(processed.data),
                    width=processed.width,
                    height=processed.height,
                )

            # Assert media attachment claim and resolve.
            claim_key, claim_value = build_media_attachment_claim(
                entity,
                asset.pk,
                category=category,
                is_primary=is_primary,
            )
            Claim.objects.assert_claim(
                entity,
                "media_attachment",
                claim_value,
                user=request.user,
                claim_key=claim_key,
            )
            resolve_media_attachments(
                content_type_id=ct.id,
                entity_ids={entity.pk},
            )
    except Exception:
        logger.exception("DB transaction failed, cleaning up storage keys")
        delete_from_storage(uploaded_keys)
        raise HttpError(500, "Failed to save media records.")

    _incr_rate_limit(request.user.id)

    return UploadOut(
        asset_uuid=str(asset_uuid),
        kind="image",
        status="ready",
        original_filename=original_filename,
        width=original.width,
        height=original.height,
        renditions=RenditionUrlsOut(
            original=build_public_url(key_original),
            thumb=build_public_url(key_thumb),
            display=build_public_url(key_display),
        ),
        attachment=AttachmentMetaOut(
            entity_type=entity_type,
            slug=slug,
            category=category,
            is_primary=is_primary,
        ),
    )


@media_router.post("/detach/", response={200: None}, auth=django_auth)
def detach_media(request, body: MediaAssetRefIn):
    """Detach a media asset from an entity by asserting an exists=False claim."""
    ct, entity = _resolve_entity(body.entity_type, body.slug)

    try:
        asset = MediaAsset.objects.get(uuid=body.asset_uuid)
    except MediaAsset.DoesNotExist, ValidationError:
        raise HttpError(404, "Media asset not found.")

    if not EntityMedia.objects.filter(
        content_type=ct,
        object_id=entity.pk,
        asset=asset,
    ).exists():
        raise HttpError(404, "This asset is not attached to the specified entity.")

    storage_keys = [
        build_storage_key(asset.uuid, rendition_type)
        for rendition_type, _label in MediaRendition.RenditionType.choices
    ]

    with transaction.atomic():
        claim_key, claim_value = build_media_attachment_claim(
            entity,
            asset.pk,
            exists=False,
        )
        Claim.objects.assert_claim(
            entity,
            "media_attachment",
            claim_value,
            user=request.user,
            claim_key=claim_key,
        )
        resolve_media_attachments(
            content_type_id=ct.id,
            entity_ids={entity.pk},
        )
        asset.delete()
        if storage_keys:
            transaction.on_commit(
                lambda keys=storage_keys: _delete_media_storage_after_commit(keys)
            )

    return Status(200, None)


@media_router.post("/set-primary/", response={200: None}, auth=django_auth)
def set_primary(request, body: MediaAssetRefIn):
    """Set a media asset as primary for its category on an entity."""
    ct, entity = _resolve_entity(body.entity_type, body.slug)

    try:
        asset = MediaAsset.objects.get(uuid=body.asset_uuid)
    except MediaAsset.DoesNotExist, ValidationError:
        raise HttpError(404, "Media asset not found.")

    em = EntityMedia.objects.filter(
        content_type=ct,
        object_id=entity.pk,
        asset=asset,
    ).first()
    if em is None:
        raise HttpError(404, "This asset is not attached to the specified entity.")

    with transaction.atomic():
        claim_key, claim_value = build_media_attachment_claim(
            entity,
            asset.pk,
            category=em.category,
            is_primary=True,
        )
        Claim.objects.assert_claim(
            entity,
            "media_attachment",
            claim_value,
            user=request.user,
            claim_key=claim_key,
        )
        resolve_media_attachments(
            content_type_id=ct.id,
            entity_ids={entity.pk},
        )

    return Status(200, None)


routers = [
    ("/media/", media_router),
]
