"""Typing protocols for dynamic provenance query shapes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .models import Claim


class HasActiveClaims(Protocol):
    active_claims: list[Claim]


class HasEffectivePriority(Protocol):
    effective_priority: int
