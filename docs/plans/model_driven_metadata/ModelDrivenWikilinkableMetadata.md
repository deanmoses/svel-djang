# Wikilinkable Model

## Context

This work is an instance of the broader pattern in [ModelDrivenMetadata.md](ModelDrivenMetadata.md): encode per-model behavior on the model itself, consume it generically from shared infrastructure. It's adjacent to but separate from [ModelDrivenLinkability.md](ModelDrivenLinkability.md) — see "Why this is separate from `LinkableModel`" below.

`WikilinkableModel` is a new mixin that catalog models opt into to participate in the **wikilink autocomplete picker** — the popup that appears when a user types `[[` in a markdown textarea, letting them choose a type and then autocomplete a target row of that type. The wikilink system itself stays model-agnostic; it consumes a registry of `LinkType` entries built once at app-ready time by walking `WikilinkableModel.__subclasses__()`.

## The contract

```python
class WikilinkableModel(LinkableModel):
    """A linkable model that appears in the wikilink autocomplete picker."""

    link_sort_order: ClassVar[int] = 100
    link_label: ClassVar[str] = ""        # derived in __init_subclass__ if empty
    link_description: ClassVar[str] = ""  # derived in __init_subclass__ if empty
    link_autocomplete_search_fields: ClassVar[tuple[str, ...]] = ("name__icontains",)
    link_autocomplete_ordering: ClassVar[tuple[str, ...]] = ("name",)
    link_autocomplete_select_related: ClassVar[tuple[str, ...]] = ()
```

| Attr                               | Default                                   | Purpose                                                                  |
| ---------------------------------- | ----------------------------------------- | ------------------------------------------------------------------------ |
| `link_sort_order`                  | `100`                                     | Display order in the wikilink picker (lower = earlier).                  |
| `link_label`                       | `str(model._meta.verbose_name).title()`   | Human-readable type label in the picker.                                 |
| `link_description`                 | `f"Link to a {model._meta.verbose_name}"` | One-liner description shown alongside the label.                         |
| `link_autocomplete_search_fields`  | `("name__icontains",)`                    | Django ORM filter spec for autocomplete queries against the type's rows. |
| `link_autocomplete_ordering`       | `("name",)`                               | Django ORM ordering for autocomplete results.                            |
| `link_autocomplete_select_related` | `()`                                      | `select_related()` kwargs for autocomplete queries.                      |

Subclasses declare overrides where needed:

```python
class Title(ClaimControlledModel, WikilinkableModel):
    link_sort_order: ClassVar[int] = 10
```

`link_label` and `link_description` are derived in `__init_subclass__` from `model._meta.verbose_name` when the subclass leaves them empty — the same trick `LinkableModel` uses for `link_url_pattern`. Defaults live in the mixin; the consumer reads attributes directly with no `getattr` fallback.

Discovery is `WikilinkableModel.__subclasses__()`. No hand-maintained list of who participates; mixing in opts the model into the picker, not mixing in keeps it out.

## Why this is separate from `LinkableModel`

`LinkableModel` answers "what's this model's URL identity?" — `entity_type`, `entity_type_plural`, `public_id_field`, `link_url_pattern`. Every model that has URLs declares this.

`WikilinkableModel` answers "should this type appear in the wikilink picker, and how?" — picker label, sort order, autocomplete config. Only types that the editorial UI exposes for wikilinking declare this. A future admin-only or internal-only linkable model would skip `WikilinkableModel` and not appear in the picker.

This matches the umbrella's [one capability per base](ModelDrivenMetadata.md#pattern-base-class--mixin) rule. Linkability and wikilinkability are independent capabilities, even though one depends on the other (you must be linkable to be wikilinkable; the mixin enforces this by inheriting from `LinkableModel`).

It also keeps the wikilink system itself model-agnostic. The wikilink registry doesn't know about Title or Manufacturer; it just walks `WikilinkableModel` subclasses and reads each one's declared ClassVars. Editorial decisions ("Title appears first in the picker") live on the model class as the source of truth — not in a hand-maintained registry inside the wikilink layer.

## Current state and hoist plan

The wikilink registration loop in [`apps/catalog/apps.py`](../../backend/apps/catalog/apps.py) iterates `apps.get_app_config("catalog").get_models()`, filters by `issubclass(model, LinkableModel)`, and reads picker config via `getattr(model, "link_*", default)` for six different attrs — the [field-on-model antipattern](ModelDrivenMetadata.md#antipattern-field-on-model) shape, six call sites, untyped, with consumer-side fallbacks.

Declarations today:

- `link_sort_order = 10/20/30/40` declared bare on Title, MachineModel, Manufacturer, Person.
- `link_type_name`, `link_label`, `link_description`, `link_autocomplete_*` — zero declarations; every model uses the registry's fallback.

Hoist:

1. Add `WikilinkableModel(LinkableModel)` to `apps/core/models.py` with the six typed ClassVars and the `__init_subclass__` derivation for `link_label` / `link_description`.
2. **Strip the "Class attributes for link registration (all optional)" block** from `LinkableModel`'s docstring. Today's class body never actually declared those attrs — the docstring just listed them as recognized override hooks. The hooks move to `WikilinkableModel`, so the block becomes misleading and should go away (or be replaced with a one-line pointer to `WikilinkableModel` for picker presentation).
3. **Drop `link_type_name` entirely.** Zero declarers; the registry can use `model.entity_type` (already on `LinkableModel`) as the registry name. No need for an unused override hook.
4. Make Title, MachineModel, Manufacturer, Person inherit `WikilinkableModel`. Their existing `link_sort_order` declarations become typed overrides of the base default.
5. Make every other catalog model that should appear in the wikilink picker inherit `WikilinkableModel` — the same `__subclasses__()` walk that drives discovery requires explicit opt-in. (This is intentional: a model only appears in the picker if it declares it should.)
6. Replace the registration loop in `catalog/apps.py` with a walk over `WikilinkableModel.__subclasses__()`, using direct attribute access on the mixin's ClassVars. No `getattr` fallbacks, no `issubclass` filter.

No semantic change to the wikilink picker. Existing tests covering the registry and the picker UI carry over; one new test asserts that a `LinkableModel` subclass that doesn't mix in `WikilinkableModel` doesn't appear in the registry.

## Why this lives in `apps.core.models`

`WikilinkableModel` is a catalog-app-aware concept (the picker only lists catalog entity types), but the mixin itself is generic Python infrastructure. Living in `apps/core/models.py` alongside `LinkableModel` keeps the linkability/wikilinkability stack co-located. Catalog models import and inherit from it; the wikilink registration loop in `catalog/apps.py` walks its subclass set.
