# Catalog Data Model

This document describes the catalog data model.

## The Hierarchy

There's a hierarchy: `Title` → `Production` → `Tier` → `Model`

- `Title`: the same conceptual game, like the original Medieval Madness _and_ its remakes
  - `Production`: a group of machines within a Title that were all produced by one manufacturer using a shared hardware platform. Medieval Madness has three Productions: the Williams original (1997), the Chicago Gaming remake on a DMD platform (2015–2016), and the Chicago Gaming Merlin Edition on an XL HD color display platform (2025). Same manufacturer doesn't mean same Production — a substantial hardware rework is a new Production.
    - `Tier`: a group of machines within the Production that play identically and is considered equivalent at tournaments. For example, Godzilla Pro and Godzilla Premium are separate Tiers, each with multiple models underneath them.
      - `Model`: the actual buyable SKU. Every Tier has at least one Model, with one marked as the default. All Models within a Tier share the same gameplay and differ only in cosmetics. For example, the Godzilla Premium Tier contains the models Godzilla Premium, Godzilla LE, and Godzilla 70th Anniversary. Godzilla LE, for example, has its own cabinet art, a numbered plaque, colored plastics, and an exclusive topper - but nothing that changes gameplay.

A standalone game that has never been remade -- like Buckaroo (1965) by Gottlieb -- will have 1 Title, 1 Production, 1 Tier and 1 Model.

## Optional Entities

Not every `Model` will be associated to these:

- `Series`: a series of games with the same design lineage by the same creative team, such as the Eight Ball Series. A `Person` can be credited with roles on a `Series`, like Steve Ritchie gets Design credit for the Black Knight Series
- `Franchise`: a group of titles related by IP, like all the Indiana Jones pins in existence regardless of manufacturer. Unlike `Series`, `People` cannot be credited with roles on a Franchise.

## Entity Reference

### Franchise

Groups items related by IP, like all the Indiana Jones pins in existence regardless of manufacturer.

- Most Titles do not belong to any Franchise.
- A Franchise can span multiple manufacturers (e.g., Star Trek has been produced by Bally, Data East, Williams, and Stern across different eras).

#### Franchise Fields

- `description`: history of the franchise in pinball

### Series

Groups related Titles that share a design lineage — for
example, the _Eight Ball_ series spans _Eight Ball_ (1977), _Eight Ball Deluxe_ (1981), and _Eight Ball Champ_ (1985).

- Most Titles do not belong to any Series.
- A Series can span multiple manufacturers (e.g., _Black Knight_ spans Williams and Stern)
- The relationship is many-to-many: a Title could theoretically belong to more than one
  Series, though that is rare in practice.
- People can be credited on a Series, like Steve Ritchie → Black Knight Series

#### Series Fields

- `description`: history of the series

### Title

A distinct pinball game design — the canonical identity of a game regardless of how many different versions / editions / models / variants were produced. Examples: _Medieval Madness_, _Eight Ball Deluxe_, _The Addams Family_.

- A `Title` can span multiple manufacturers, like _Medieval Madness_ and its remakes.
- Every `Production` belongs to exactly one `Title`.
- Most `Titles` contain only one `Production` (the original production run). Some contain several — e.g., _Medieval Madness_ contains the Williams original (1997), the Chicago Gaming DMD remake (2015–2016), and the Chicago Gaming Merlin Edition (2025).

#### Title Fields

- `description`: overall game design history

#### Mapping from 3rd party sources

Example: Medieval Madness (OPDB Group G5pe4)

| OPDB ID     | Name                              | Manufacturer   | Year |
| ----------- | --------------------------------- | -------------- | ---- |
| G5pe4-MePZv | Medieval Madness                  | Williams       | 1997 |
| G5pe4-MkPRV | Medieval Madness (Remake Royal)   | Chicago Gaming | 2015 |
| G5pe4-M5W7V | Medieval Madness (Remake Special) | Chicago Gaming | 2016 |

All of these are the same Title.

### Production

A specific manufacturer's hardware platform for a parent `Title`. Examples: _Williams Medieval Madness (1997)_, _Chicago Gaming Medieval Madness Remake (2015)_, _Chicago Gaming Medieval Madness Merlin Edition (2025)_, _Stern Black Knight: Sword of Rage (2019)_. Note that the same manufacturer can have multiple Productions if the hardware platform changes substantially.

#### Production Fields

- `description`: the description of this specific production, such as what was interesting about the remakes of Medieval Madness by Chicago Gaming.
- `year` and `month` of the production's reveal date — anchored to the World Premiere (press release or trade show), not the ship date.
- `manufacturer` (FK)
- `system` (FK)
- `display_type` (FK)
- `machine_type` (FK)
- `player_count`
- `flipper_count`
- Credits mapping to People (such as Art credit to Pat Lawlor)
- `features`: text (for now) containing just the features that distinguish this Production from its parent `Title`

### Tier

A gameplay tier within a `Production`. Pro vs Premium are different Tiers because they have different rules, shots, and features. Every `Production` has at least one `Tier`.

This is NOT a distinct production run. When we get around to modeling it in the future, Tier will have 0..n ProductionRun records.

#### Tier Fields

- `description`: the story of this specific tier — e.g., what was notable about _Eight Ball Deluxe (LE)_ as a release.

### Model

The actual buyable SKU — the concrete thing a collector owns. Every `Tier` has at least one `Model`, with one marked as the **default**. All Models within a Tier share the same gameplay and differ only in cosmetics (cabinet art, numbered plaques, toppers, colored plastics). The default Model represents the standard offering of that Tier.

For example, the Godzilla Premium Tier has three Models: Godzilla Premium _(default)_, Godzilla LE, and Godzilla 70th Anniversary.

#### Model Fields

- `description`: describes history or circumstances of the model
- `default`: boolean flag — true for the canonical model of the Tier
- `sku`: the SKU of this model
- `year` and `month` first produced
- `features`: text (for now) containing just the cosmetic features that distinguish it from the default Model

## Fields common to all entities

- `name`: Human-friendly title of item
- `slug`: URL-friendly identifier
- `description`: markdown. We will eventually be adding rich linking support so that markdown can contain links that survive slug renames, by storing the record's ID in the markdown rather than the actual URL.
- `created_at`: bookkeeping of when the record was initially created in the database
- `updated_at`: bookkeeping of when the record was last updated in the database

## Use Cases

Tournaments care about what, Tier?

## Mapping from OPDB

OPDB has no `Franchise`, `Series`, `Production`, or `Tier` concept. Franchise and Series data is hand-curated in `data/series.json`. `Production` and `Tier` are derived at ingest time using the logic below.

| OPDB record type                 | `physical_machine` | Maps to               |
| -------------------------------- | ------------------ | --------------------- |
| Group ID (e.g. `G5pe4`)          | n/a                | `Title`               |
| Non-alias record                 | `0`                | `Production` + `Tier` |
| Non-alias record                 | `1`                | `Tier`                |
| Alias record (`is_alias` is set) | n/a                | `Model`               |

### Deriving Production at ingest

By default, each distinct `(opdb_group_id, manufacturer, technology_generation)` triple among non-alias rows becomes one `Production`. This automatically splits EM and SS versions from the same manufacturer (e.g., Bally's electromechanical and solid-state Black Jack become separate Productions). For cases where this triple is still insufficient — e.g., Chicago Gaming's DMD-based Medieval Madness remake (2015–2016) and the XL HD color display Merlin Edition (2025) share the same technology generation but have substantially different hardware — manual overrides in `data/productions.json` and `data/tiers.json` split them into separate Productions.

When a `physical_machine=0` row exists for a Production, it defines the Production (the shared hardware). Its fields (year, system, display_type, etc.) populate the `Production` record.

If no `physical_machine=0` row exists, derive the `Production` from the earliest `manufacture_date` among the `physical_machine=1` rows, then lowest `opdb_id` for stability.

### Deriving Tier at ingest

Every non-alias OPDB row produces one `Tier` under its `Production`:

- A `physical_machine=0` row (e.g. "Godzilla (Premium/LE)") produces both the `Production` and a `Tier` representing that gameplay tier.
- Each `physical_machine=1` row (e.g. "Godzilla (Pro)") produces an additional `Tier` under the same `Production`.

For simple games with a single OPDB row and no aliases, that row produces a `Production` with one `Tier` and one default `Model`.

### Mapping alias records at ingest

All OPDB alias records (`is_alias` is set) become `Models`. They are assigned to the `Tier` created by their parent record (the non-alias row whose `opdb_id` is the prefix of the alias ID). The first alias processed for a `Tier` is marked as the default `Model`.
