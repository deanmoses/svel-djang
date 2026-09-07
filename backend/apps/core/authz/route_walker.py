"""Walk a NinjaAPI's routers and yield every registered operation.

Used by the route-inventory test to confirm every mutating route
carries an authz marker. Iterates `api._routers` exactly once —
`api._routers[0]` *is* `api.default_router`, so iterating both would
double-count routes registered directly on the API (e.g. `@api.get(...)`
decorations in `config/api.py`).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from typing import NamedTuple

from ninja import NinjaAPI

_DUPLICATE_SLASHES = re.compile(r"/{2,}")


class RouteOperation(NamedTuple):
    """A single registered Ninja operation.

    ``method`` is uppercase (matches ``Operation.methods``).
    ``path`` is ``prefix + path`` — the route as it appears under the
    NinjaAPI mount.
    ``view_func`` is the bare callable passed to ``router.<verb>(...)``,
    after any decorators. Consumers read marker attributes off this
    object.
    """

    method: str
    path: str
    view_func: Callable[..., object]


def iter_operations(api: NinjaAPI) -> Iterator[RouteOperation]:
    """Yield a :class:`RouteOperation` for every registered operation."""
    for prefix, router in api._routers:  # noqa: SLF001 — django-ninja exposes no public router enumeration
        for path, path_view in router.path_operations.items():
            for op in path_view.operations:
                # Most apps register a router prefix that ends in `/`
                # (`/auth/`) and per-route paths that start with `/`
                # (`/logout/`), so naive concatenation produces
                # `/auth//logout/`. The default router has prefix `""`
                # and paths that already start with `/`. Collapsing
                # repeated slashes handles both cases without special-
                # casing.
                full_path = _DUPLICATE_SLASHES.sub("/", f"{prefix}{path}")
                for method in op.methods:
                    yield RouteOperation(method, full_path, op.view_func)
