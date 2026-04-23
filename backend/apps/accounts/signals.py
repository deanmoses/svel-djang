from typing import Any

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(
    sender: type[User],
    instance: User,
    created: bool,
    **kwargs: Any,  # noqa: ANN401 - Django signal receivers accept framework-defined kwargs.
) -> None:
    """Auto-create a UserProfile whenever a new User is created."""
    if created:
        UserProfile.objects.create(user=instance)
