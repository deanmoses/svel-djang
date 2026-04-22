from typing import Any, cast

from django.contrib import admin
from django.http import HttpRequest

from .models import CitationSource, CitationSourceLink


class CitationSourceLinkInline(admin.TabularInline[CitationSourceLink, CitationSource]):
    model = CitationSourceLink
    extra = 1
    readonly_fields = ("created_by", "updated_by")


@admin.register(CitationSource)
class CitationSourceAdmin(admin.ModelAdmin[CitationSource]):
    list_display = ("name", "source_type", "author", "year", "parent")
    list_filter = ("source_type",)
    search_fields = ("name", "author", "publisher", "isbn")
    list_select_related = ("parent",)
    readonly_fields = ("created_by", "updated_by")
    inlines = [CitationSourceLinkInline]

    def get_readonly_fields(
        self,
        request: HttpRequest,
        obj: CitationSource | None = None,
    ) -> tuple[str, ...]:
        if obj:  # editing existing — parent is locked
            return (*self.readonly_fields, "parent")
        return tuple(self.readonly_fields)

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: CitationSource | None = None,
    ) -> bool:
        return False

    def save_model(
        self,
        request: HttpRequest,
        obj: CitationSource,
        form: Any,
        change: bool,
    ) -> None:
        assert request.user.is_authenticated
        user = cast(Any, request.user)
        if not change:
            obj.created_by = user
        obj.updated_by = user
        super().save_model(request, obj, form, change)

    def save_formset(
        self,
        request: HttpRequest,
        form: Any,
        formset: Any,
        change: bool,
    ) -> None:
        assert request.user.is_authenticated
        user = cast(Any, request.user)
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, CitationSourceLink):
                if not instance.pk:
                    instance.created_by = user
                instance.updated_by = user
            instance.save()
        for obj in formset.deleted_objects:
            obj.delete()
        formset.save_m2m()
