from django.contrib import admin

from .models import MediaAsset, MediaRendition


class MediaRenditionInline(admin.TabularInline):
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

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin):
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

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MediaRendition)
class MediaRenditionAdmin(admin.ModelAdmin):
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

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
