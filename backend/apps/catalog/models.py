"""Catalog models — pinball machines, manufacturers, groups, and people.

The catalog represents the resolved/materialized view of each entity.
Field values are derived by resolving claims from the provenance layer.
"""

from __future__ import annotations

from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from apps.core.models import TimeStampedModel, unique_slug


# ---------------------------------------------------------------------------
# Manufacturer
# ---------------------------------------------------------------------------


class Manufacturer(TimeStampedModel):
    """A pinball machine brand (user-facing grouping).

    Corporate incarnations are tracked separately in ManufacturerEntity.
    For example, "Gottlieb" is one Manufacturer with four ManufacturerEntity
    records spanning different ownership eras.
    """

    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    trade_name = models.CharField(
        max_length=200,
        blank=True,
        help_text='Brand name if different (e.g., "Bally" for Midway Manufacturing)',
    )
    wikidata_id = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        help_text="Wikidata QID, e.g. Q180268",
    )
    description = models.TextField(blank=True)
    founded_year = models.IntegerField(null=True, blank=True)
    dissolved_year = models.IntegerField(null=True, blank=True)
    country = models.CharField(max_length=200, null=True, blank=True)
    headquarters = models.CharField(max_length=200, null=True, blank=True)
    logo_url = models.URLField(null=True, blank=True)
    website = models.URLField(blank=True)

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        if self.trade_name and self.trade_name != self.name:
            return f"{self.trade_name} ({self.name})"
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.trade_name or self.name, "manufacturer")
        super().save(*args, **kwargs)


class CorporateEntity(TimeStampedModel):
    """A specific corporate incarnation of a manufacturer brand.

    IPDB tracks corporate entities (e.g., four separate entries for Gottlieb
    across its ownership eras). Each entity maps to one brand-level Manufacturer.
    """

    manufacturer = models.ForeignKey(
        Manufacturer,
        on_delete=models.CASCADE,
        related_name="entities",
    )
    name = models.CharField(
        max_length=300,
        help_text='Full corporate name, e.g., "D. Gottlieb & Company"',
    )
    years_active = models.CharField(
        max_length=50,
        blank=True,
        help_text='Operating period, e.g., "1931-1977"',
    )

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["manufacturer", "years_active"]
        verbose_name = "corporate entity"
        verbose_name_plural = "corporate entities"
        constraints = [
            models.UniqueConstraint(
                fields=["manufacturer", "name"],
                name="catalog_unique_corporate_entity_per_manufacturer",
            ),
        ]

    def __str__(self) -> str:
        if self.years_active:
            return f"{self.name} ({self.years_active})"
        return self.name


class Address(models.Model):
    corporate_entity = models.ForeignKey(
        CorporateEntity, on_delete=models.CASCADE, related_name="addresses"
    )
    city = models.CharField(max_length=255, blank=True)
    state = models.CharField(max_length=255, blank=True)
    country = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name_plural = "addresses"

    def __str__(self):
        parts = [p for p in (self.city, self.state, self.country) if p]
        return ", ".join(parts)


# ---------------------------------------------------------------------------
# Taxonomy models
# ---------------------------------------------------------------------------


class TechnologyGeneration(TimeStampedModel):
    """A major technological era: Pure Mechanical, Electromechanical, Solid State.

    Replaces the old MachineType enum. Seeded from technology_generations.json.
    Name and display_order are claim-controlled; description is direct editorial.
    """

    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    description = models.TextField(blank=True)

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["display_order"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, "techgen")
        super().save(*args, **kwargs)


class TechnologySubgeneration(TimeStampedModel):
    """A subdivision within a TechnologyGeneration.

    e.g., Solid State → Discrete Logic, Integrated (MPU), PC-Based.
    Seeded from technology_subgenerations.json.
    """

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    description = models.TextField(blank=True)
    technology_generation = models.ForeignKey(
        TechnologyGeneration,
        on_delete=models.CASCADE,
        related_name="subgenerations",
    )

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["display_order"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, "techsubgen")
        super().save(*args, **kwargs)


class DisplayType(TimeStampedModel):
    """A display technology category: Score Reels, DMD, LCD, etc.

    Replaces the old DisplayType enum. Seeded from display_types.json.
    """

    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    description = models.TextField(blank=True)

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["display_order"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, "displaytype")
        super().save(*args, **kwargs)


class DisplaySubtype(TimeStampedModel):
    """A subdivision within a DisplayType.

    e.g., LCD → Standard LCD, HD LCD. Seeded from display_subtypes.json.
    """

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    description = models.TextField(blank=True)
    display_type = models.ForeignKey(
        DisplayType,
        on_delete=models.CASCADE,
        related_name="subtypes",
    )

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["display_order"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, "displaysubtype")
        super().save(*args, **kwargs)


class Cabinet(TimeStampedModel):
    """Physical cabinet form factor: Floor, Tabletop, Countertop, Cocktail.

    Seeded from cabinets.json.
    """

    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    description = models.TextField(blank=True)

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["display_order"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, "cabinet")
        super().save(*args, **kwargs)


class GameFormat(TimeStampedModel):
    """Game format: Pinball, Bagatelle, Shuffle Alley, Pitch-and-Bat.

    Seeded from game_formats.json.
    """

    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    description = models.TextField(blank=True)

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["display_order"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, "gameformat")
        super().save(*args, **kwargs)


class GameplayFeature(TimeStampedModel):
    """A gameplay mechanism: Flippers, Pop Bumpers, Ramps, Multiball, etc.

    Seeded from gameplay_features.json. Linked to MachineModel via M2M.
    """

    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    description = models.TextField(blank=True)

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["display_order"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, "feature")
        super().save(*args, **kwargs)


class Tag(TimeStampedModel):
    """A classification tag: Home Use, Prototype, Widebody, Remake, etc.

    Seeded from tags.json. Linked to MachineModel via M2M relationship claims.
    """

    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    description = models.TextField(blank=True)

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["display_order"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, "tag")
        super().save(*args, **kwargs)


class Franchise(TimeStampedModel):
    """An IP grouping that spans manufacturers and eras.

    e.g., Indiana Jones, Star Trek. Most Titles do not belong to a Franchise.
    Seeded from franchises.json.
    """

    name = models.CharField(max_length=300, unique=True)
    slug = models.SlugField(max_length=300, unique=True, blank=True)
    description = models.TextField(blank=True)

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, "franchise")
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------


class Title(TimeStampedModel):
    """The canonical identity of a pinball game, independent of edition or variant.

    OPDB calls this a "group" (e.g., "Medieval Madness" spans the 1997 original,
    the 2015 remake, and LE/SE variants). We use "Title" as it is the natural
    pinball-world term. Like Manufacturer, this is a direct reference entity —
    no source contests the title's identity itself. Assignment of machine models
    to titles goes through the claims system.
    """

    opdb_id = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="group ID",
        help_text='OPDB group ID (e.g., "G5pe4") or synthetic ID (e.g., "ipdb:1234").',
    )
    name = models.CharField(max_length=300)
    slug = models.SlugField(max_length=300, unique=True, blank=True)
    short_name = models.CharField(
        max_length=50,
        blank=True,
        help_text='Common abbreviation, e.g., "MM" for Medieval Madness',
    )
    description = models.TextField(blank=True)
    franchise = models.ForeignKey(
        Franchise,
        on_delete=models.SET_NULL,
        related_name="titles",
        null=True,
        blank=True,
    )
    needs_review = models.BooleanField(
        default=False,
        help_text="Title was auto-generated and may need human review.",
    )
    needs_review_notes = models.TextField(
        blank=True,
        help_text="Context for reviewers about why this title needs attention.",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        if self.short_name:
            return f"{self.name} ({self.short_name})"
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, "title")
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# Series
# ---------------------------------------------------------------------------


class Series(TimeStampedModel):
    """A manually-curated grouping of related Titles sharing a thematic lineage.

    e.g., the "Eight Ball" series spans Eight Ball, Eight Ball Deluxe, and
    Eight Ball Champ. Series are sparse — most Titles belong to none. They can
    span multiple manufacturers. No data ingest populates them; they are
    maintained by curators via the admin or seed data.
    """

    name = models.CharField(max_length=300)
    slug = models.SlugField(max_length=300, unique=True, blank=True)
    description = models.TextField(blank=True)
    titles = models.ManyToManyField(
        Title,
        blank=True,
        related_name="series",
    )

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "series"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, "series")
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------


class Theme(TimeStampedModel):
    """A thematic tag for pinball machines (e.g., Sports, Horror, Licensed).

    Flat taxonomy — no hierarchy. Fields are claim-controlled.
    The MachineModel↔Theme relationship is materialized from relationship claims.
    """

    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = models.TextField(blank=True)

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, "theme")
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------


class System(TimeStampedModel):
    """An electronic hardware generation for pinball machines.

    e.g. WPC-95, System 6, SAM System, SPIKE.
    MachineModel.system FK is resolved from 'system' slug claims,
    created by IPDB ingest (via mpu_strings mapping) or admin.
    """

    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = models.TextField(blank=True)
    manufacturer = models.ForeignKey(
        "Manufacturer",
        on_delete=models.SET_NULL,
        related_name="systems",
        null=True,
        blank=True,
    )
    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, "system")
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# MachineModel
# ---------------------------------------------------------------------------


class MachineModel(TimeStampedModel):
    """A pinball machine title/design — the resolved/materialized view.

    Fields are derived from resolving claims. The resolution logic picks the
    winning claim per field (highest priority source, most recent if tied).
    """

    # Identity
    name = models.CharField(max_length=300)
    slug = models.SlugField(max_length=300, unique=True, blank=True)

    # Cross-reference IDs
    ipdb_id = models.PositiveIntegerField(
        unique=True, null=True, blank=True, verbose_name="IPDB ID"
    )
    opdb_id = models.CharField(
        max_length=50, unique=True, null=True, blank=True, verbose_name="OPDB ID"
    )
    pinside_id = models.PositiveIntegerField(
        unique=True, null=True, blank=True, verbose_name="Pinside ID"
    )

    # Hierarchy
    title = models.ForeignKey(
        Title,
        on_delete=models.SET_NULL,
        related_name="machine_models",
        null=True,
        blank=True,
        help_text="Title this machine belongs to (resolved from claims).",
    )
    alias_of = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="aliases",
        null=True,
        blank=True,
        help_text="Parent machine model if this is a cosmetic/LE variant.",
    )

    # Core filterable fields
    manufacturer = models.ForeignKey(
        Manufacturer,
        on_delete=models.PROTECT,
        related_name="models",
        null=True,
        blank=True,
    )
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    month = models.PositiveSmallIntegerField(null=True, blank=True)
    technology_generation = models.ForeignKey(
        TechnologyGeneration,
        on_delete=models.SET_NULL,
        related_name="machine_models",
        null=True,
        blank=True,
        help_text="Technology generation (resolved from claims).",
    )
    display_type = models.ForeignKey(
        DisplayType,
        on_delete=models.SET_NULL,
        related_name="machine_models",
        null=True,
        blank=True,
        help_text="Display type (resolved from claims).",
    )
    display_subtype = models.ForeignKey(
        DisplaySubtype,
        on_delete=models.SET_NULL,
        related_name="machine_models",
        null=True,
        blank=True,
        help_text="Display subtype (resolved from claims).",
    )
    cabinet = models.ForeignKey(
        Cabinet,
        on_delete=models.SET_NULL,
        related_name="machine_models",
        null=True,
        blank=True,
        help_text="Cabinet form factor (resolved from claims).",
    )
    game_format = models.ForeignKey(
        GameFormat,
        on_delete=models.SET_NULL,
        related_name="machine_models",
        null=True,
        blank=True,
        help_text="Game format (resolved from claims).",
    )
    player_count = models.PositiveSmallIntegerField(null=True, blank=True)
    themes = models.ManyToManyField(
        "Theme",
        blank=True,
        related_name="machine_models",
        help_text="Resolved theme tags (materialized from relationship claims).",
    )
    gameplay_features = models.ManyToManyField(
        "GameplayFeature",
        blank=True,
        related_name="machine_models",
        help_text="Gameplay features (materialized from relationship claims).",
    )
    tags = models.ManyToManyField(
        "Tag",
        blank=True,
        related_name="machine_models",
        help_text="Classification tags (materialized from relationship claims).",
    )
    production_quantity = models.CharField(max_length=100, blank=True)
    system = models.ForeignKey(
        "System",
        on_delete=models.SET_NULL,
        related_name="machine_models",
        null=True,
        blank=True,
        help_text="Hardware system (resolved from system claims).",
    )
    flipper_count = models.PositiveSmallIntegerField(null=True, blank=True)

    # Ratings
    ipdb_rating = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True
    )
    pinside_rating = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True
    )

    # Museum content
    educational_text = models.TextField(blank=True)
    sources_notes = models.TextField(blank=True)

    # Catch-all for fields without dedicated columns
    extra_data = models.JSONField(default=dict, blank=True)

    # Reverse access to provenance claims for this model.
    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["manufacturer", "year"]),
            models.Index(fields=["technology_generation", "year"]),
            models.Index(fields=["display_type"]),
        ]

    def __str__(self) -> str:
        parts = [self.name]
        if self.manufacturer:
            parts.append(f"({self.manufacturer})")
        if self.year:
            parts.append(f"[{self.year}]")
        return " ".join(parts)

    def save(self, *args, **kwargs):
        if not self.slug:
            parts = [self.name]
            if self.manufacturer:
                parts.append(self.manufacturer.trade_name or self.manufacturer.name)
            if self.year:
                parts.append(str(self.year))
            self.slug = unique_slug(self, " ".join(parts), "model")
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# Person / DesignCredit
# ---------------------------------------------------------------------------


class Person(TimeStampedModel):
    """A person involved in pinball machine design (designer, artist, etc.)."""

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    bio = models.TextField(blank=True)

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


class DesignCredit(TimeStampedModel):
    """Links a person to a machine model or series with a specific role."""

    class Role(models.TextChoices):
        CONCEPT = "concept", "Concept"
        DESIGN = "design", "Design"
        ART = "art", "Art"
        MECHANICS = "mechanics", "Mechanics"
        MUSIC = "music", "Music"
        SOUND = "sound", "Sound"
        VOICE = "voice", "Voice"
        SOFTWARE = "software", "Software"
        ANIMATION = "animation", "Dots/Animation"
        OTHER = "other", "Other"

    model = models.ForeignKey(
        MachineModel,
        on_delete=models.CASCADE,
        related_name="credits",
        null=True,
        blank=True,
    )
    series = models.ForeignKey(
        Series,
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
    role = models.CharField(max_length=20, choices=Role.choices)

    class Meta:
        ordering = ["role", "person__name"]
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
        return f"{self.person.name} — {self.get_role_display()} on {target}"
