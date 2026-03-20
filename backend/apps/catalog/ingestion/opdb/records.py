"""Typed record dataclass for OPDB source data.

Mirrors the OPDB record shape with minimal normalization. The from_raw()
factory maps raw JSON keys to Python field names — key mapping and minimal
type coercion only. Heavier normalization (date parsing, manufacturer
resolution) stays in parsers.py and the ingest command.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OpdbRecord:
    """Raw OPDB record — close to source shape, minimal normalization."""

    opdb_id: str
    name: str = "Unknown"
    ipdb_id: int | None = None
    manufacturer_name: str = ""
    manufacturer_id: int | None = None
    manufacture_date: str = ""
    physical_machine: int = 1
    is_machine: bool = False
    is_alias: bool = False
    features: list[str] = field(default_factory=list)
    player_count: int | None = None
    type: str = ""
    display: str = ""
    keywords: list | None = None
    description: str | None = None
    common_name: str | None = None
    images: list | None = None
    shortname: str | None = None

    @classmethod
    def from_raw(cls, d: dict) -> OpdbRecord:
        """Map raw JSON keys to Python field names. Key mapping only."""
        mfr = d.get("manufacturer") or {}
        return cls(
            opdb_id=d["opdb_id"],
            name=d.get("name", "Unknown"),
            ipdb_id=d.get("ipdb_id"),
            manufacturer_name=mfr.get("name", ""),
            manufacturer_id=mfr.get("manufacturer_id"),
            manufacture_date=d.get("manufacture_date", ""),
            physical_machine=d.get("physical_machine", 1),
            is_machine=d.get("is_machine") is True,
            is_alias=d.get("is_alias") is True,
            features=d.get("features") or [],
            player_count=d.get("player_count"),
            type=d.get("type", ""),
            display=d.get("display", ""),
            keywords=d.get("keywords"),
            description=d.get("description"),
            common_name=d.get("common_name"),
            images=d.get("images"),
            shortname=d.get("shortname"),
        )

    @property
    def parent_opdb_id(self) -> str:
        """Extract the parent machine's opdb_id from an alias opdb_id.

        OPDB IDs follow the pattern G{group}-M{machine}[-A{alias}].
        The parent is the first two segments.
        """
        return "-".join(self.opdb_id.split("-")[:2])

    @property
    def group_opdb_id(self) -> str:
        """Extract the OPDB group prefix from this record's opdb_id."""
        return self.opdb_id.split("-")[0]
