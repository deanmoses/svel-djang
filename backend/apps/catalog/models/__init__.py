"""Catalog models — pinball machines, manufacturers, groups, and people.

The catalog represents the resolved/materialized view of each entity.
Field values are derived by resolving claims from the provenance layer.
"""

from .base import AliasModel, CatalogModel
from .export_market import ModelExportMarket
from .gameplay_feature import (
    GameplayFeature,
    GameplayFeatureAlias,
    GameplayFeatureParent,
    MachineModelGameplayFeature,
)
from .location import CorporateEntityLocation, Location, LocationAlias
from .machine_model import MachineModel, ModelAbbreviation, SelfFkRole
from .manufacturer import (
    CorporateEntity,
    CorporateEntityAlias,
    Manufacturer,
    ManufacturerAlias,
    OperatingStatus,
)
from .model_relationship import (
    LicenseStatus,
    ModelRelationship,
    RelationshipType,
)
from .person import Credit, Person, PersonAlias
from .series import Franchise, Series
from .system import System, SystemMpuString
from .taxonomy import (
    PRODUCED_SLUG,
    UNCLASSIFIED_SLUG,
    Cabinet,
    CreditRole,
    DisplaySubtype,
    DisplayType,
    GameFormat,
    MachineModelRewardType,
    MachineModelTag,
    ProductionStatus,
    RewardType,
    RewardTypeAlias,
    Tag,
    TechnologyGeneration,
    TechnologySubgeneration,
)
from .theme import MachineModelTheme, Theme, ThemeAlias, ThemeParent
from .title import Title, TitleAbbreviation

__all__ = [
    "PRODUCED_SLUG",
    "UNCLASSIFIED_SLUG",
    "AliasModel",
    "Cabinet",
    "CatalogModel",
    "CorporateEntity",
    "CorporateEntityAlias",
    "CorporateEntityLocation",
    "Credit",
    "CreditRole",
    "DisplaySubtype",
    "DisplayType",
    "Franchise",
    "GameFormat",
    "GameplayFeature",
    "GameplayFeatureAlias",
    "GameplayFeatureParent",
    "LicenseStatus",
    "Location",
    "LocationAlias",
    "MachineModel",
    "MachineModelGameplayFeature",
    "MachineModelRewardType",
    "MachineModelTag",
    "MachineModelTheme",
    "Manufacturer",
    "ManufacturerAlias",
    "ModelAbbreviation",
    "ModelExportMarket",
    "ModelRelationship",
    "OperatingStatus",
    "Person",
    "PersonAlias",
    "ProductionStatus",
    "RelationshipType",
    "RewardType",
    "RewardTypeAlias",
    "SelfFkRole",
    "Series",
    "System",
    "SystemMpuString",
    "Tag",
    "TechnologyGeneration",
    "TechnologySubgeneration",
    "Theme",
    "ThemeAlias",
    "ThemeParent",
    "Title",
    "TitleAbbreviation",
]
