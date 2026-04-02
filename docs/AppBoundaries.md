# Django App Boundaries

This document defines the dependency rules and responsibilities of Pinbase's Django apps.

## Apps

- `core`: shared foundation layer used by the rest of the project
- `accounts`: authentication and account-specific behavior
- `catalog`: the pinball business/domain model and catalog-facing APIs
- `provenance`: the generic claims, source, and audit system
- `media`: Pinbase-hosted media infrastructure

## Dependencies

```text
catalog | provenance | media
____________________________
    core  |   accounts
```

- `core` and `accounts` depend on nothing.
- `catalog`, `provenance`, and `media` may depend on `core` and `accounts` but not on each other.
