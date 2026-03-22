"""Person and Credit models."""

from __future__ import annotations

from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.db.models.functions import Lower

from apps.core.models import (
    AliasBase,
    Linkable,
    MarkdownField,
    TimeStampedModel,
    unique_slug,
)

__all__ = ["Person", "PersonAlias", "Credit"]


class Person(Linkable, TimeStampedModel):
    """A person involved in pinball machine design (designer, artist, etc.)."""

    link_url_pattern = "/people/{slug}"

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = MarkdownField(blank=True)

    # Wikidata cross-reference — direct field, not a claim
    wikidata_id = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Wikidata ID",
        help_text='Wikidata QID, e.g., "Q312897"',
    )

    # Birth / death dates — claimed fields, resolved from provenance
    birth_year = models.IntegerField(null=True, blank=True)
    birth_month = models.IntegerField(null=True, blank=True)
    birth_day = models.IntegerField(null=True, blank=True)
    death_year = models.IntegerField(null=True, blank=True)
    death_month = models.IntegerField(null=True, blank=True)
    death_day = models.IntegerField(null=True, blank=True)

    # Biography context — claimed fields, resolved from provenance
    birth_place = models.CharField(max_length=200, null=True, blank=True)
    nationality = models.CharField(max_length=200, null=True, blank=True)
    photo_url = models.URLField(null=True, blank=True)

    # Catch-all for fields without dedicated columns (e.g. fandom.bio)
    extra_data = models.JSONField(default=dict, blank=True)

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "people"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, "person")
        super().save(*args, **kwargs)


class PersonAlias(AliasBase):
    """An alternate name for a Person, used to match alternative spellings from
    external sources (e.g. "Keith Johnson" → "Keith P. Johnson").
    """

    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="aliases")

    class Meta(AliasBase.Meta):
        constraints = [
            models.UniqueConstraint(
                Lower("value"),
                name="catalog_unique_person_alias_lower",
            ),
        ]


class Credit(TimeStampedModel):
    """Links a person to a machine model or series with a specific role."""

    model = models.ForeignKey(
        "MachineModel",
        on_delete=models.CASCADE,
        related_name="credits",
        null=True,
        blank=True,
    )
    series = models.ForeignKey(
        "Series",
        on_delete=models.CASCADE,
        related_name="credits",
        null=True,
        blank=True,
    )
    person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        related_name="credits",
    )
    role = models.ForeignKey(
        "CreditRole",
        on_delete=models.PROTECT,
        related_name="credits",
    )

    class Meta:
        ordering = ["role__display_order", "person__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["model", "person", "role"],
                name="catalog_unique_credit_per_model_person_role",
                condition=models.Q(model__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["series", "person", "role"],
                name="catalog_unique_credit_per_series_person_role",
                condition=models.Q(series__isnull=False),
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(model__isnull=False, series__isnull=True)
                    | models.Q(model__isnull=True, series__isnull=False)
                ),
                name="catalog_credit_model_xor_series",
            ),
        ]

    def __str__(self) -> str:
        target = self.model.name if self.model else self.series.name
        return f"{self.person.name} — {self.role.name} on {target}"
