from django.contrib import admin

from .models import ChangeSet, Claim, Source, SourceFieldLicense


class SourceFieldLicenseInline(admin.TabularInline):
    model = SourceFieldLicense
    extra = 1


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "source_type",
        "priority",
        "is_enabled",
        "default_license",
        "url",
    )
    list_editable = ("is_enabled", "default_license")
    list_filter = ("source_type", "is_enabled")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = [SourceFieldLicenseInline]


@admin.register(ChangeSet)
class ChangeSetAdmin(admin.ModelAdmin):
    list_display = ("pk", "user", "note_truncated", "created_at")
    list_filter = ("user",)
    readonly_fields = ("created_at",)

    @admin.display(description="Note")
    def note_truncated(self, obj):
        if len(obj.note) > 80:
            return obj.note[:80] + "..."
        return obj.note


@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    """Read-only inspection view. Claims must not be created or edited in admin."""

    list_display = (
        "subject",
        "field_name",
        "value_truncated",
        "source",
        "is_active",
        "created_at",
    )
    list_filter = ("source", "is_active", "field_name")
    search_fields = ("field_name",)
    readonly_fields = ("content_type", "object_id", "changeset", "created_at")

    @admin.display(description="Value")
    def value_truncated(self, obj):
        s = str(obj.value)
        if len(s) > 80:
            return s[:80] + "..."
        return s

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
