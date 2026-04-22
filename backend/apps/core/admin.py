from django.contrib import admin

from .models import License


@admin.register(License)
class LicenseAdmin(admin.ModelAdmin[License]):
    list_display = (
        "short_name",
        "slug",
        "spdx_id",
        "allows_display",
        "permissiveness_rank",
    )
    list_filter = ("allows_display", "requires_attribution", "restricts_commercial")
    search_fields = ("name", "short_name", "spdx_id")
    prepopulated_fields = {"slug": ("short_name",)}
    ordering = ("-permissiveness_rank",)
