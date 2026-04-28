from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class UserProfile(TimeStampedModel):
    """Extended profile for each user, tracking contributor priority and metadata."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    workos_user_id = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        default=None,
        unique=True,
        help_text="WorkOS user ID (e.g. user_01ABC...). Null until first SSO login, then auto-linked by email.",
    )
    priority = models.PositiveSmallIntegerField(
        default=10000,
        help_text="Claim priority for conflict resolution. Higher beats lower.",
    )

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self) -> str:
        return f"{self.user.username} (priority={self.priority})"
