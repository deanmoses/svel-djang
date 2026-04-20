# Model And Title Detail/Edit UX

## Goal

Create a clearer information architecture for model and title detail pages across both the public read-only views as well as the authenticated edit flows.

The current UI mixes too many concerns:

- reader content
- record metadata
- edit workflows
- page-level navigation
- edit-section navigation

This becomes especially problematic on mobile, where the current tab model does not have enough room and the edit form becomes overwhelming.

## Core Principles

- Optimize first for the end-user reader, not the editor.

## Edit Interaction Model

The model and title edit screens should behave as a set of accordion sections rather than one large always-open form.

Core behavior:

- render the screen as named accordion sections
- only one section is edited at a time
- each section has its own `Edit`, `Save`, and `Cancel` controls
- saving applies only to the current section, not the whole page
- edit note and citation attach to the section being saved, not to the page as a whole

## Model Detail UX

### Model Reader View

Sections:

- Overview
- Technology
- Features
- People
- Relationships
- Media

Utility actions (not part of the reading flow):

- Edit
- History
- Tools
  - Sources

### Model Edit

Sections:

- Overview
  - Model.Description
- Basics
  - Model.Title, Model.CorporateEntity (but label it Manufacturer)
  - Model.Name, Model.Slug
  - Model.Year, Model.Month
  - Model.Abbreviations
- Technology
  - Technology Generation, Technology Subgeneration
  - Display Type, Display Subtype
  - System
- Features
  - Game format, Cabinet
  - Reward types, Tags
  - Themes, Production quantity
  - \# Players, \# Flippers
  - Gameplay features
- Related Models
  - Variant of
  - Converted from
  - Remake of
- People
  - Person/Role rows
- Media
  - Photos & Videos
- External Data
  - Links
    - IPDB ID
    - OPDB ID
    - Pinside ID
  - Ratings
    - Pinside rating
    - IPDB rating
- Change Title
  - A dedicated section for changing the model's title?

## Title Detail UX

### Title Reader View

Actions in top bar are same as Model page:

- Edit menu of sections
- History
- Tools menu
  - Sources

#### Multi-Model Title Reader View

When showing a title with multiple models, it should have these accordion sections:

- Overview
  - Title.Description
- Models (hide if none)
  - Thumbnail of each model. The current tab approach tries to show hierarchy, with variants under parents. Don't. Show thumnail for each model, both top level AND variants.
- Technology (hide if none)
- Features (hide if none)
  - Include Franchise / Series here
- Related Titles
  - Show any related model info that aggregates
- People (hide if none/0)
- Media (hide if none/0)
- External Links (hide if none/0)
  - Links to OPDB group, fandom
- References (hide if none/0)

Aggregation rules:

- scalars: show-if-unanimous (intersection)
- people credits: intersection
- themes: intersection
- gameplay: intersection
- reward types: intersection
- tags: intersection
- related titles: intersection
- media: union
- references: only show references from Description

#### Single-Model Title Reader View

When showing a single-model title, the accordion sections should look like the model view, but with the addition of title-specific fields like series / franchise.

Put series / franchise under Features, even though it's not a good fit. There's no other great place for them.

### Title Edit View

#### Single-Model Title Edit

On a single-model title + model, some fields overlap and we're going to have to choose which to show:

- We will make Title.name and Title.slug editable and hide Model.name and Model.slug, because it's the title slug that's used for routing.
- We will hide Title.description and only show Model.description, because if we ever split the Title + Model, that description should go with the Model.
- We will hide Model.abbreviations and only show Title.Abbreviations, because if we ever split the Title + Model, those abbreviations will be more relevant to the title.

On a single-model title, the edit dropdown menu should contain a combined set of the editors from both title and model editors.

Sections:

- Overview [the existing Model Overview section]
  - Model.Description
- Title Basics
  - Title.Name, Title.Slug
  - Title.Franchise, Title.Series
  - Title.Abbreviations
- Model Basics (a slimmed down version w/o name, slug, abbreviations)
  - Model.Corporate Entity (but label it Manufacturer)
  - Model.Year, Model.Month
- Technology [The existing Model Technology section]
  - Technology Generation, Technology Subgeneration
  - Display Type, Display Subtype
  - System
- Features [the existing Model Features section]
  - Game format, Cabinet
  - Reward types, Tags
  - Themes, Production quantity
  - \# Players, \# Flippers
  - Gameplay features
- Related Models [the existing Model Related Features section]
  - Variant of
  - Converted from
  - Remake of
- People [The existing Model People section]
  - Person/Role rows
- Media [The existing Model Media section]
  - Photos & Videos
- Model External Data [the existing Model External Data section]
  - Links
    - IPDB ID
    - opdb_machine_id
    - Pinside ID
  - Ratings
    - Pinside rating
    - IPDB rating
- Title External Data
  - Title.obdb_group_id
  - Title.fandom_page_id
- Change Title
  - A dedicated section for changing the model's title?

#### Multi-Model Title Edit

Sections:

- Overview
  - Title.Description
- Title Basics
  - Title.Name, Title.Slug
  - Title.Franchise, Title.Series
  - Title.Abbreviations
- Title External Data
  - Title.obdb_group_id
  - Title.fandom_page_id

For multi-model titles, models are edited on their own page.
