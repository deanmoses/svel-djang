# Model And Title UX

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
- Use section-scoped editing rather than one giant page-level form.

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

The model detail page should organize reader content as:

- Overview
- Specifications
- People
- Relationships
- Media

Utility actions (not part of the reading flow):

- Sources
- History

### Model Edit Sections

The model edit page should use these sections:

### Description

Fields:

- Description

### Gameplay & Theme

Fields:

- Themes
- Tags
- Gameplay features

### Technology

Fields:

- Technology generation
- Technology subgeneration
- System
- Display type
- Display subtype

### Basics

Fields:

- Name
- Slug
- Year
- Month
- Manufacturer
- Abbreviations
- Players
- Flippers
- Cabinet
- Game format
- Reward types
- Production quantity

Suggested visual subgroups:

- `Identity`: name, slug, year, month, manufacturer, abbreviations
- `Core machine facts`: players, flippers, cabinet, game format, reward types, production quantity

### Relationships

Fields:

- Variant of
- Converted from
- Remake of

### External Data

Fields:

- IPDB ID
- OPDB ID
- Pinside ID
- IPDB rating
- Pinside rating

### Credits

Same contents as existing Credits/People tab

## Title Detail UX

### Title Reader View

The title detail page should use the same reader-first structure:

- Overview
- Specifications
- People
- Relationships
- Media

Utility actions:

- Sources
- History

Notes:

- When a title has a single model and the public view merges title/model information, the reading surface should still feel like one coherent entity page.
- The reader should not need to understand title-owned vs model-owned facts in order to consume the page.

### Title Edit Sections

The title edit page should be leaner than the model edit page.

Suggested sections:

### Overview

Expanded by default.

Fields:

- Description

### Title Basics

Collapsed by default.

Fields:

- Name
- Slug
- Franchise
- Abbreviations

Rationale:

- Title editing should stay focused on title-owned facts.
- Identity fields should remain available, but not dominant.

### Ownership Boundary

The title edit page should preserve a clear boundary between title-owned facts and model-owned facts.

Model-owned facts that should not be edited from title edit:

- machine roster
- variants
- specifications
- ratings
- external IDs
- credits
- model-specific metadata

Rationale:

- The boundary is important to preserve internally.
- But it should be presented clearly and simply, without forcing the reader/editor to think in implementation terms more than necessary.
