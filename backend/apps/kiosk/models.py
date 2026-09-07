"""Kiosk configuration models.

Kiosk configs are operational settings for kiosk-mode displays — not catalog
claims. They use plain Django models with no claims plumbing (see
docs/Provenance.md).
"""

from __future__ import annotations

from typing import override

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import TimeStampedModel
from apps.core.validators import validate_no_mojibake

__all__ = ["KioskConfig", "KioskConfigItem"]

IDLE_SECONDS_MIN = 1


class KioskConfig(TimeStampedModel):
    """A kiosk display configuration.

    A device "selects" a config via the ``kioskConfigId`` cookie set in the
    frontend. Multiple devices can share one config; one device shows one
    config at a time. Configs are identified to operators by their integer
    primary key (``#7``), optionally augmented in UI by ``page_heading``.
    """

    items: models.Manager[KioskConfigItem]

    page_heading = models.CharField(
        max_length=60,
        blank=True,
        default="",
        validators=[validate_no_mojibake],
        help_text="H1 rendered on the kiosk display. Blank to render no heading.",
    )
    idle_seconds = models.PositiveIntegerField(
        default=180,
        validators=[MinValueValidator(IDLE_SECONDS_MIN)],
        help_text="Idle timeout before redirecting back to /kiosk.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(idle_seconds__gte=IDLE_SECONDS_MIN),
                name="kiosk_kioskconfig_idle_seconds_range",
            ),
        ]

    @override
    def __str__(self) -> str:
        return (
            f"#{self.pk} — {self.page_heading}" if self.page_heading else f"#{self.pk}"
        )


class KioskConfigItem(TimeStampedModel):
    """One Title slot in a KioskConfig, ordered by ``position``.

    CASCADE on the Title FK is deliberate: operational kiosk slots adapt when
    catalog titles are deleted.
    """

    config = models.ForeignKey(
        KioskConfig,
        on_delete=models.CASCADE,
        related_name="items",
    )
    title = models.ForeignKey(
        "catalog.Title",
        on_delete=models.CASCADE,
        related_name="+",
    )
    hook = models.CharField(
        max_length=80,
        blank=True,
        validators=[validate_no_mojibake],
        help_text="Optional short caption shown alongside the title.",
    )
    position = models.PositiveIntegerField()

    class Meta:
        ordering = ["config_id", "position"]
        constraints = [
            models.UniqueConstraint(
                fields=["config", "position"],
                name="kiosk_kioskconfigitem_position_unique",
            ),
            models.UniqueConstraint(
                fields=["config", "title"],
                name="kiosk_kioskconfigitem_title_unique",
            ),
        ]

    @override
    def __str__(self) -> str:
        return f"#{self.config_id} pos {self.position}: {self.title.name}"
