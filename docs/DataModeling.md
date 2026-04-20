# Data Modeling

Principles and conventions for Django models in Pinbase.

## Principles

### Validate strictly, validate early

Add the strictest constraint you can defend. Relaxing a constraint is a one-line migration. Tightening one means auditing every existing row and hoping nothing breaks — so start strict.

### Validate in the database

Push as much validation as you can to the database. Django has multiple code paths that skip Python validation (`objects.create()`, `bulk_create()`, `update()`, management commands, raw SQL, migrations). A CHECK constraint catches all of them.

### Default to PROTECT on foreign keys

`on_delete=PROTECT` blocks deletion of a referenced row. This is the safe default — it forces you to handle the dependency explicitly rather than silently losing data. Use `CASCADE` only for wholly owned children (e.g., `MediaVariant` belongs to `MediaAsset` — deleting the asset should delete its variants). Never use `SET_NULL` unless there's a clear product reason to preserve the row without its parent.

### Know which uniqueness guarantees are DB-enforced vs app-enforced

Not every "no duplicates" rule lives in the DB. When a rule needs normalization the DB can't easily express (case-insensitive, article-stripped, punctuation-folded), it lives at the application layer. The split is meaningful:

- **DB-enforced** (e.g., `Title.slug`, `MachineModel.slug`): a unique constraint. The DB raises `IntegrityError` on violation. No TOCTOU race is possible — the constraint is atomic with the insert.
- **App-enforced** (e.g., `Title.name` normalized): a query-then-insert pattern. There is a race window between the query and the insert where two concurrent writers can both pass the check. The correctness floor is the DB constraint (when one exists) or the acceptance that rare races produce near-duplicates that have to be cleaned up editorially.

When adding an app-enforced uniqueness rule:

1. Document the normalization rule in a colocated module (see [backend/apps/catalog/naming.py](../backend/apps/catalog/naming.py) as the template).
2. Enforce at the API layer, not only the UI. A UI gate is ergonomic; the API check is the invariant.
3. State the race behavior in the endpoint's docstring so future readers know what isn't guaranteed.
4. Prefer a stricter check over a looser one, since relaxing is a one-line change and tightening requires auditing existing rows.

## Django Pitfalls

These are the specific reasons we enforce constraints at the DB level rather than relying on Django's Python-layer validation:

- **`CharField(blank=False)`** is only enforced at `full_clean()`, not at the DB level. Use `field_not_blank()` from `apps.core.models` to add a CHECK constraint.
- **`PositiveIntegerField`** allows 0. If you need `> 0`, add a CHECK constraint.
- **`choices=`** on CharField is only enforced at `full_clean()`. Add a CHECK constraint (`field__in=[...]`) to enforce valid values at the DB level.
- **`objects.create()`** bypasses `full_clean()` entirely. Without DB constraints, invalid data enters the database from management commands, migrations, bulk operations, and raw SQL.

## Conventions

### Timestamps

Inherit from `TimeStampedModel` (in `apps.core.models`) for `created_at` / `updated_at`. Don't define these fields manually.

### GenericForeignKey

Use `PositiveBigIntegerField` for `object_id` to match `BigAutoField` PKs. Use `on_delete=PROTECT` on the `ContentType` FK.

### Constraint naming

Use explicit names: `{app}_{model}_{description}`. Never rely on Django's auto-generated names.

Cross-field constraints use `violation_error_code="cross_field"`.

### Range and enum constants

Define range bounds and enum values as module-level constants. Reference them from both validators and constraints so they can't drift apart. See `test_constraint_drift.py` for the meta-test that enforces this.

### Storage keys

Store relative paths, never full URLs. The storage prefix (e.g., `media/`) is enforced in application code, not DB constraints, so the storage location stays configurable without schema changes.

### No regex in CHECK constraints

`__startswith`, `__contains`, and `__endswith` generate standard SQL `LIKE`, which works identically on PostgreSQL and SQLite. Use these in CHECK constraints.

**Do not use `__regex` in CHECK constraints.** On SQLite, `__regex` generates `REGEXP`, which depends on a Python function that Django registers on the connection. It works during normal Django operations, but anything that touches the database outside Django (DB browsers, backup restores, raw migration scripts) won't have the function — causing "no such function: regexp" errors or silently unenforced constraints.

If a pattern can't be expressed with LIKE, enforce it in Django model validation instead of a CHECK constraint.

## Testing DB Constraints

Use `objects.create()` with `pytest.raises(IntegrityError)`. Django's `create()` bypasses `full_clean()`, so invalid values hit the DB constraint directly. No raw SQL or `_raw_update` helper needed.

Test both directions:

- **Negative**: invalid data is rejected (the constraint fires).
- **Positive**: valid edge cases are accepted (the constraint doesn't over-reject).

```python
def test_byte_size_zero_rejected(self, user):
    with pytest.raises(IntegrityError):
        MediaAsset.objects.create(**_asset_kwargs(user, byte_size=0))

def test_valid_asset_without_dimensions(self, user):
    """Non-ready assets can omit dimensions."""
    asset = MediaAsset.objects.create(
        **_asset_kwargs(user, status="failed", width=None, height=None)
    )
    assert asset.pk is not None
```
