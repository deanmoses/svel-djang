"""Typed record dataclass for IPDB source data.

Mirrors the IPDB record shape with minimal normalization. The from_raw()
factory maps raw JSON keys to Python field names — key mapping and minimal
type coercion only. Heavier normalization (HTML unescape, date parsing,
manufacturer resolution) stays in parsers.py and the ingest command.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class IpdbRecord:
    """Raw IPDB record — close to source shape, minimal normalization."""

    ipdb_id: int
    title: str = "Unknown"
    players: int | None = None
    manufacturer: str = ""
    manufacturer_short_name: str = ""
    manufacturer_id: int | None = None
    type: str = ""
    type_short_name: str = ""
    date_of_manufacture: str = ""
    theme: str = ""
    average_fun_rating: float | None = None
    model_number: str = ""
    production_number: int | str | None = None
    notable_features: str = ""
    notes: str = ""
    toys: str = ""
    marketing_slogans: str = ""
    common_abbreviations: str = ""
    mpu: str = ""
    image_files: list[dict] = field(default_factory=list)

    # Credit fields
    design_by: str = ""
    art_by: str = ""
    dots_animation_by: str = ""
    mechanics_by: str = ""
    music_by: str = ""
    sound_by: str = ""
    software_by: str = ""

    @classmethod
    def from_raw(cls, d: dict[str, Any]) -> IpdbRecord:
        """Map raw JSON keys to Python field names. Key mapping only.

        ``d`` is the parsed IPDB JSON dict — fields are heterogeneous
        (string/int/list/null per IPDB schema), so the value type stays
        ``Any`` rather than enumerating the upstream schema here.
        """
        return cls(
            ipdb_id=d["IpdbId"],  # KeyError if missing = drift detection
            title=d.get("Title", "Unknown"),
            players=d.get("Players"),
            manufacturer=d.get("Manufacturer", ""),
            manufacturer_short_name=d.get("ManufacturerShortName", ""),
            manufacturer_id=d.get("ManufacturerId"),
            type=d.get("Type", ""),
            type_short_name=d.get("TypeShortName", ""),
            date_of_manufacture=d.get("DateOfManufacture", ""),
            theme=d.get("Theme", ""),
            average_fun_rating=d.get("AverageFunRating"),
            model_number=str(d["ModelNumber"]) if d.get("ModelNumber") else "",
            production_number=d.get("ProductionNumber"),
            notable_features=d.get("NotableFeatures", ""),
            notes=d.get("Notes", ""),
            toys=d.get("Toys", ""),
            marketing_slogans=d.get("MarketingSlogans", ""),
            common_abbreviations=d.get("CommonAbbreviations", ""),
            mpu=d.get("MPU", ""),
            image_files=d.get("ImageFiles") or [],
            design_by=d.get("DesignBy", ""),
            art_by=d.get("ArtBy", ""),
            dots_animation_by=d.get("DotsAnimationBy", ""),
            mechanics_by=d.get("MechanicsBy", ""),
            music_by=d.get("MusicBy", ""),
            sound_by=d.get("SoundBy", ""),
            software_by=d.get("SoftwareBy", ""),
        )
