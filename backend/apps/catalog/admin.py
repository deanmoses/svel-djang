from decimal import Decimal

from django.contrib import admin, messages
from django.contrib.contenttypes.admin import GenericTabularInline
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

from apps.provenance.models import Claim

from .models import (
    Address,
    Cabinet,
    CorporateEntity,
    Credit,
    CreditRole,
    DisplaySubtype,
    DisplayType,
    Franchise,
    GameFormat,
    GameplayFeature,
    MachineModel,
    Manufacturer,
    ModelAbbreviation,
    Person,
    Series,
    System,
    Tag,
    TechnologyGeneration,
    TechnologySubgeneration,
    Theme,
    Title,
    TitleAbbreviation,
)
from .resolve import (
    DIRECT_FIELDS,
    FK_FIELDS,
    FRANCHISE_DIRECT_FIELDS,
    MANUFACTURER_DIRECT_FIELDS,
    PERSON_DIRECT_FIELDS,
    SERIES_DIRECT_FIELDS,
    SYSTEM_DIRECT_FIELDS,
    TAXONOMY_DIRECT_FIELDS,
    THEME_DIRECT_FIELDS,
    TITLE_DIRECT_FIELDS,
    resolve_franchise,
    resolve_manufacturer,
    resolve_model,
    resolve_person,
    resolve_series,
    resolve_system,
    resolve_taxonomy,
    resolve_theme,
    resolve_title,
)


class ProvenanceSaveMixin:
    """Routes writes to claim-controlled fields through the provenance system.

    Subclasses define:
    - ``CLAIM_FIELDS``: frozenset of form field names that are claim-controlled.
    - ``_to_claim_value(field_name, value)``: serialize a form value for storage
      in a Claim (override for FK fields).
    - ``_resolve(obj)``: call the appropriate resolve function after asserting claims.

    On save, any changed claim-controlled field is asserted as a user Claim, then
    the object is re-resolved so the materialized fields stay consistent.
    """

    CLAIM_FIELDS: frozenset = frozenset()

    def _to_claim_value(self, field_name: str, value):
        from apps.core.markdown_links import prepare_markdown_claim_value

        value = prepare_markdown_claim_value(field_name, value, self.model)
        if isinstance(value, Decimal):
            return str(value)
        return value

    def _resolve(self, obj) -> None:
        raise NotImplementedError

    def save_model(self, request, obj, form, change):
        # Persist the object first (required to have a PK for claim creation).
        super().save_model(request, obj, form, change)

        changed = [f for f in form.changed_data if f in self.CLAIM_FIELDS]
        if not changed:
            return

        for field_name in changed:
            try:
                claim_value = self._to_claim_value(
                    field_name, form.cleaned_data.get(field_name)
                )
            except ValidationError as exc:
                self.message_user(
                    request,
                    f"{field_name}: {'; '.join(exc.messages)}",
                    messages.ERROR,
                )
                continue
            if claim_value is None:
                # Field cleared: withdraw the user's claim rather than storing a
                # NULL value (Claim.value does not allow NULL).
                Claim.objects.filter(
                    content_type=ContentType.objects.get_for_model(obj),
                    object_id=obj.pk,
                    user=request.user,
                    field_name=field_name,
                    is_active=True,
                ).update(is_active=False)
            else:
                Claim.objects.assert_claim(
                    obj, field_name, claim_value, user=request.user
                )
        self._resolve(obj)


class ClaimInline(GenericTabularInline):
    model = Claim
    extra = 0
    readonly_fields = (
        "source",
        "field_name",
        "claim_key",
        "value",
        "citation",
        "is_active",
        "created_at",
    )
    can_delete = False
    show_change_link = True
    classes = ("collapse",)
    verbose_name_plural = "claims (provenance)"

    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_active=True)

    def has_add_permission(self, request, obj=None):
        return False


class CreditInline(admin.TabularInline):
    """Read-only inline — credits are materialized from relationship claims."""

    model = Credit
    extra = 0
    readonly_fields = ("person", "role")
    can_delete = False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("role")

    def has_add_permission(self, request, obj=None):
        return False


class ThemeInline(admin.TabularInline):
    """Read-only inline — theme tags are materialized from relationship claims."""

    model = MachineModel.themes.through
    extra = 0
    readonly_fields = ("theme",)


class GameplayFeatureInline(admin.TabularInline):
    """Read-only inline — gameplay features are materialized from relationship claims."""

    model = MachineModel.gameplay_features.through
    extra = 0
    readonly_fields = ("gameplayfeature",)
    can_delete = False
    verbose_name = "theme"
    verbose_name_plural = "themes"

    def has_add_permission(self, request, obj=None):
        return False


class AddressInline(admin.TabularInline):
    model = Address
    extra = 0
    fields = ("city", "state", "country")


class CorporateEntityInline(admin.TabularInline):
    model = CorporateEntity
    extra = 0
    fields = ("name", "years_active")


# ---------------------------------------------------------------------------
# Taxonomy models — lightweight admin registrations
# ---------------------------------------------------------------------------


class TaxonomyAdminMixin(ProvenanceSaveMixin):
    """Shared ProvenanceSaveMixin for taxonomy models."""

    CLAIM_FIELDS = frozenset(TAXONOMY_DIRECT_FIELDS)

    def _resolve(self, obj):
        resolve_taxonomy(obj)


@admin.register(TechnologyGeneration)
class TechnologyGenerationAdmin(TaxonomyAdminMixin, admin.ModelAdmin):
    list_display = ("display_order", "name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = (ClaimInline,)


@admin.register(TechnologySubgeneration)
class TechnologySubgenerationAdmin(TaxonomyAdminMixin, admin.ModelAdmin):
    list_display = ("display_order", "name", "technology_generation", "slug")
    list_filter = ("technology_generation",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = (ClaimInline,)


@admin.register(DisplayType)
class DisplayTypeAdmin(TaxonomyAdminMixin, admin.ModelAdmin):
    list_display = ("display_order", "name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = (ClaimInline,)


@admin.register(DisplaySubtype)
class DisplaySubtypeAdmin(TaxonomyAdminMixin, admin.ModelAdmin):
    list_display = ("display_order", "name", "display_type", "slug")
    list_filter = ("display_type",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = (ClaimInline,)


@admin.register(Cabinet)
class CabinetAdmin(TaxonomyAdminMixin, admin.ModelAdmin):
    list_display = ("display_order", "name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = (ClaimInline,)


@admin.register(GameFormat)
class GameFormatAdmin(TaxonomyAdminMixin, admin.ModelAdmin):
    list_display = ("display_order", "name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = (ClaimInline,)


@admin.register(GameplayFeature)
class GameplayFeatureAdmin(TaxonomyAdminMixin, admin.ModelAdmin):
    list_display = ("display_order", "name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = (ClaimInline,)


@admin.register(Tag)
class TagAdmin(TaxonomyAdminMixin, admin.ModelAdmin):
    list_display = ("display_order", "name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = (ClaimInline,)


@admin.register(CreditRole)
class CreditRoleAdmin(TaxonomyAdminMixin, admin.ModelAdmin):
    list_display = ("display_order", "name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = (ClaimInline,)


@admin.register(Franchise)
class FranchiseAdmin(ProvenanceSaveMixin, admin.ModelAdmin):
    CLAIM_FIELDS = frozenset(FRANCHISE_DIRECT_FIELDS)

    def _resolve(self, obj):
        resolve_franchise(obj)

    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = (ClaimInline,)


# ---------------------------------------------------------------------------
# Core models
# ---------------------------------------------------------------------------


@admin.register(Manufacturer)
class ManufacturerAdmin(ProvenanceSaveMixin, admin.ModelAdmin):
    CLAIM_FIELDS = frozenset(MANUFACTURER_DIRECT_FIELDS)

    def _resolve(self, obj):
        resolve_manufacturer(obj)

    list_display = (
        "name",
        "trade_name",
        "entity_count",
    )
    search_fields = ("name", "trade_name")
    prepopulated_fields = {"slug": ("name",)}
    inlines = (CorporateEntityInline, ClaimInline)

    @admin.display(description="Entities")
    def entity_count(self, obj):
        return obj.entities.count()


class TitleAbbreviationInline(admin.TabularInline):
    """Read-only inline — abbreviations are materialized from relationship claims."""

    model = TitleAbbreviation
    extra = 0
    readonly_fields = ("value",)
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class ModelAbbreviationInline(admin.TabularInline):
    """Read-only inline — abbreviations are materialized from relationship claims."""

    model = ModelAbbreviation
    extra = 0
    readonly_fields = ("value",)
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Title)
class TitleAdmin(ProvenanceSaveMixin, admin.ModelAdmin):
    CLAIM_FIELDS = frozenset(TITLE_DIRECT_FIELDS)

    def _resolve(self, obj):
        resolve_title(obj)

    list_display = ("name", "opdb_id", "machine_model_count")
    search_fields = ("name", "opdb_id")
    prepopulated_fields = {"slug": ("name",)}
    inlines = (TitleAbbreviationInline, ClaimInline)

    @admin.display(description="Machine Models")
    def machine_model_count(self, obj):
        return obj.machine_models.count()


@admin.register(Series)
class SeriesAdmin(ProvenanceSaveMixin, admin.ModelAdmin):
    CLAIM_FIELDS = frozenset(SERIES_DIRECT_FIELDS)

    def _resolve(self, obj):
        resolve_series(obj)

    list_display = ("name", "slug", "title_count")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ("titles",)
    inlines = (ClaimInline,)

    @admin.display(description="Titles")
    def title_count(self, obj):
        return obj.titles.count()


@admin.register(Theme)
class ThemeAdmin(ProvenanceSaveMixin, admin.ModelAdmin):
    CLAIM_FIELDS = frozenset(THEME_DIRECT_FIELDS)

    def _resolve(self, obj):
        resolve_theme(obj)

    list_display = ("name", "machine_count")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = (ClaimInline,)

    @admin.display(description="Machines")
    def machine_count(self, obj):
        return obj.machine_models.count()


@admin.register(System)
class SystemAdmin(ProvenanceSaveMixin, admin.ModelAdmin):
    CLAIM_FIELDS = frozenset(SYSTEM_DIRECT_FIELDS)

    def _resolve(self, obj):
        resolve_system(obj)

    list_display = ("name", "manufacturer", "machine_count")
    search_fields = ("name",)
    list_filter = ("manufacturer",)
    autocomplete_fields = ("manufacturer",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = (ClaimInline,)

    @admin.display(description="Machines")
    def machine_count(self, obj):
        return obj.machine_models.count()


@admin.register(Person)
class PersonAdmin(ProvenanceSaveMixin, admin.ModelAdmin):
    CLAIM_FIELDS = frozenset(PERSON_DIRECT_FIELDS)

    def _resolve(self, obj):
        resolve_person(obj)

    list_display = ("name", "credit_count")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = (ClaimInline,)

    @admin.display(description="Credits")
    def credit_count(self, obj):
        return obj.credits.count()


@admin.register(MachineModel)
class MachineModelAdmin(ProvenanceSaveMixin, admin.ModelAdmin):
    CLAIM_FIELDS = frozenset(DIRECT_FIELDS) | frozenset(FK_FIELDS)

    def _to_claim_value(self, field_name: str, value):
        if value is not None and field_name in FK_FIELDS:
            return getattr(value, FK_FIELDS[field_name].lookup_key)
        return super()._to_claim_value(field_name, value)

    def _resolve(self, obj):
        resolve_model(obj)

    list_display = (
        "name",
        "manufacturer",
        "year",
        "technology_generation",
        "display_type",
        "ipdb_id",
    )
    list_filter = ("technology_generation", "display_type", "manufacturer")
    search_fields = ("name", "ipdb_id", "manufacturer__name")
    autocomplete_fields = (
        "manufacturer",
        "title",
        "variant_of",
        "converted_from",
        "system",
        "technology_generation",
        "display_type",
        "display_subtype",
        "cabinet",
        "game_format",
    )
    inlines = (
        CreditInline,
        ThemeInline,
        GameplayFeatureInline,
        ModelAbbreviationInline,
        ClaimInline,
    )

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "slug",
                    "manufacturer",
                    "title",
                    "variant_of",
                    "converted_from",
                    "is_conversion",
                    "year",
                    "month",
                ),
            },
        ),
        (
            "Specifications",
            {
                "fields": (
                    "technology_generation",
                    "display_type",
                    "display_subtype",
                    "cabinet",
                    "game_format",
                    "player_count",
                    "production_quantity",
                    "system",
                    "flipper_count",
                ),
            },
        ),
        (
            "Cross-references",
            {
                "fields": ("ipdb_id", "opdb_id", "pinside_id"),
            },
        ),
        (
            "Ratings",
            {
                "fields": ("ipdb_rating", "pinside_rating"),
            },
        ),
        (
            "Extra Data",
            {
                "fields": ("extra_data",),
                "classes": ("collapse",),
            },
        ),
    )

    def get_prepopulated_fields(self, request, obj=None):
        if obj:
            return {}
        return {"slug": ("name",)}


@admin.register(Credit)
class CreditAdmin(admin.ModelAdmin):
    list_display = ("person", "role", "model", "series")
    list_filter = ("role",)
    search_fields = ("person__name", "model__name", "series__name")
    autocomplete_fields = ("person", "model", "series", "role")
