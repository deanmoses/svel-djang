"""API endpoints for the catalog app.

Routers: models, titles, manufacturers, people, themes, systems, series,
franchises, and all taxonomy types.
Wired into the main NinjaAPI instance in config/api.py.
"""

from .franchises import franchises_router
from .gameplay_features import gameplay_features_router
from .locations import locations_router
from .machine_models import models_router
from .manufacturers import manufacturers_router
from .people import people_router
from .series import series_router
from .systems import systems_router
from .taxonomy import (
    cabinets_router,
    credit_roles_router,
    display_subtypes_router,
    display_types_router,
    game_formats_router,
    reward_types_router,
    tags_router,
    technology_generations_router,
    technology_subgenerations_router,
)
from .themes import themes_router
from .titles import titles_router

__all__ = [
    "cabinets_router",
    "credit_roles_router",
    "display_subtypes_router",
    "display_types_router",
    "franchises_router",
    "game_formats_router",
    "gameplay_features_router",
    "locations_router",
    "manufacturers_router",
    "models_router",
    "people_router",
    "reward_types_router",
    "series_router",
    "systems_router",
    "tags_router",
    "technology_generations_router",
    "technology_subgenerations_router",
    "themes_router",
    "titles_router",
]
