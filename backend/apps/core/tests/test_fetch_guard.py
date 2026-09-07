"""Contract tests for ``block_lazy_fetches``.

The query-count tests that use the guard all pass, so nothing in the suite
would notice if the guard silently became a no-op. These pin that it bites,
and that it puts the default back.
"""

from __future__ import annotations

import pytest
from django.core.exceptions import FieldFetchBlocked
from django.db.models import FETCH_ONE
from django.db.models import query as query_module

from apps.catalog.models import MachineModel
from apps.catalog.tests.conftest import make_machine_model
from apps.core.fetch_guard import block_lazy_fetches


@pytest.mark.django_db
def test_blocks_an_on_demand_fk_fetch():
    """An FK read on a queryset that didn't select it raises, naming the field."""
    make_machine_model(name="MM", slug="mm-fetch-guard")
    with block_lazy_fetches():
        model = MachineModel.objects.get(slug="mm-fetch-guard")
        with pytest.raises(FieldFetchBlocked, match="MachineModel.title"):
            _ = model.title


@pytest.mark.django_db
def test_allows_a_fetch_the_queryset_already_selected():
    """The guard blocks the extra query, not the attribute access."""
    make_machine_model(name="MM", slug="mm-selected")
    with block_lazy_fetches():
        model = MachineModel.objects.select_related("title").get(slug="mm-selected")
        assert model.title.slug


@pytest.mark.django_db
def test_queryset_built_inside_a_callable_is_covered():
    """The guard reaches querysets it has no handle on — the reason it patches
    the module default rather than calling ``QuerySet.fetch_mode()``. This is
    the shape of a view building its own queryset behind ``client.get()``."""
    make_machine_model(name="MM", slug="mm-nested")

    def deep() -> str:
        return MachineModel.objects.get(slug="mm-nested").title.slug

    with block_lazy_fetches(), pytest.raises(FieldFetchBlocked):
        deep()


def test_default_is_restored_after_an_exception():
    with pytest.raises(RuntimeError), block_lazy_fetches():
        raise RuntimeError("boom")
    assert query_module.DEFAULT_FETCH_MODE is FETCH_ONE
