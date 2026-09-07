from typing import override

from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "apps.core"
    verbose_name = "Core"

    @override
    def ready(self) -> None:
        from django.db.models import CharField, TextField
        from django.db.models.functions import Length

        from . import checks  # noqa: F401 — registers system checks
        from .authz import (
            checks as authz_checks,  # noqa: F401 — registers system checks
        )
        from .authz import rules  # noqa: F401 — registers core-owned activities

        # Register Length as a transform so ``Q(field__length__lte=N)``
        # works for any CharField/TextField — used by BoundedTextField and
        # MarkdownField to auto-contribute char-length CHECK constraints.
        # Safe to defer to ready(): the Q is constructed at model class
        # creation but the lookup chain is only resolved when the
        # constraint condition compiles to SQL (migrate, system checks),
        # all of which run after AppConfig.ready().
        CharField.register_lookup(Length)
        TextField.register_lookup(Length)
