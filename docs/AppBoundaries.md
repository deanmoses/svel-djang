# Django App Boundaries

This document defines the dependency rules and responsibilities of Pinbase's Django apps.

## Apps

- `core`: shared foundation layer used by the rest of the project
- `accounts`: authentication and account-specific behavior
- `catalog`: the pinball business/domain/data model
- `citation`: citation-source metadata and evidence objects that can be cited
- `provenance`: claims, source, and audit system
- `media`: media upload and hosting infrastructure

## Dependencies

```text
catalog | provenance | media | citation
____________________________
   core | accounts
```

- `core` and `accounts` depend on nothing
- `catalog`, `provenance`, and `media` must not depend on each other (peer isolation)
- `provenance` depends on `citation` but `citation` does not depend on `provenance`
