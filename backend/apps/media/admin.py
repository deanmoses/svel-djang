from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from .models import MediaAsset, MediaRendition


class MediaRenditionInline(admin.TabularInline[MediaRendition, MediaAsset]):
    model = MediaRendition
    extra = 0
    readonly_fields = (
        "uuid",
        "rendition_type",
        "mime_type",
        "byte_size",
        "width",
        "height",
        "is_ready",
        "created_at",
        "updated_at",
    )

    # django-stubs declares conflicting `obj` types on
    # BaseModelAdmin.has_*_permission (child) vs InlineModelAdmin.has_*_permission
    # (parent), so a concrete annotation here triggers an LSP override error from
    # whichever side it doesn't match. `Any` is the only signature that satisfies
    # both. Idiom #3 (3rd-party API constraint).
    def has_add_permission(
        self,
        request: HttpRequest,
        obj: Any = None,  # noqa: ANN401
    ) -> bool:
        return False

    def has_change_permission(
        self,
        request: HttpRequest,
        obj: Any = None,  # noqa: ANN401
    ) -> bool:
        return False

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: Any = None,  # noqa: ANN401
    ) -> bool:
        return False


@admin.register(MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin[MediaAsset]):
    """Read-only inspection view. MediaAssets are created by the upload API."""

    list_display = (
        "uuid",
        "kind",
        "status",
        "original_filename",
        "uploaded_by",
        "created_at",
    )
    list_filter = ("kind", "status")
    search_fields = ("uuid", "original_filename")
    readonly_fields = (
        "uuid",
        "kind",
        "original_filename",
        "mime_type",
        "byte_size",
        "width",
        "height",
        "status",
        "uploaded_by",
        "created_at",
        "updated_at",
    )
    inlines = [MediaRenditionInline]

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: MediaAsset | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: MediaAsset | None = None
    ) -> bool:
        return False


@admin.register(MediaRendition)
class MediaRenditionAdmin(admin.ModelAdmin[MediaRendition]):
    """Read-only inspection view. MediaRenditions are created by the upload API."""

    list_display = ("asset", "rendition_type", "uuid", "is_ready")
    list_filter = ("rendition_type", "is_ready")
    list_select_related = ("asset",)
    search_fields = ("uuid",)
    readonly_fields = (
        "uuid",
        "asset",
        "rendition_type",
        "mime_type",
        "byte_size",
        "width",
        "height",
        "is_ready",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: MediaRendition | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: MediaRendition | None = None
    ) -> bool:
        return False
