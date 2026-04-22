from typing import Any

from django.contrib import admin

from .models import CitationSource, CitationSourceLink


class CitationSourceLinkInline(admin.TabularInline):
    model = CitationSourceLink
    extra = 1
    readonly_fields = ("created_by", "updated_by")


@admin.register(CitationSource)
class CitationSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "source_type", "author", "year", "parent")
    list_filter = ("source_type",)
    search_fields = ("name", "author", "publisher", "isbn")
    list_select_related = ("parent",)
    readonly_fields = ("created_by", "updated_by")
    inlines = [CitationSourceLinkInline]

    def get_readonly_fields(self, request, obj=None) -> tuple[Any, ...]:
        if obj:  # editing existing — parent is locked
            return (*self.readonly_fields, "parent")
        return tuple(self.readonly_fields)

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, CitationSourceLink):
                if not instance.pk:
                    instance.created_by = request.user
                instance.updated_by = request.user
            instance.save()
        for obj in formset.deleted_objects:
            obj.delete()
        formset.save_m2m()
