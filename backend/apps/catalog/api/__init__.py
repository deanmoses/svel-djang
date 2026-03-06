"""API endpoints for the catalog app.

Routers: models, titles, manufacturers, people, themes, systems, series,
franchises, technology_generations, display_types.
Wired into the main NinjaAPI instance in config/api.py.
"""

from .franchises import franchises_router
from .machine_models import models_router
from .manufacturers import manufacturers_router
from .people import people_router
from .series import series_router
from .systems import systems_router
from .taxonomy import display_types_router, technology_generations_router
from .themes import themes_router
from .titles import titles_router

__all__ = [
    "display_types_router",
    "franchises_router",
    "titles_router",
    "manufacturers_router",
    "models_router",
    "people_router",
    "series_router",
    "systems_router",
    "technology_generations_router",
    "themes_router",
]
