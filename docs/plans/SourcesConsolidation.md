# Sources Consolidation

Catalog entities are supposed to present Edit History and Sources as the same experience across all models: same UX, shared code, and a single API surface area. That is only partially true today.

## Finding

Edit History is already close to the desired architecture. It uses a generic provenance endpoint, a shared frontend loader, and a shared UI component. There is still thin per-entity route glue, but the underlying surface is unified.

Sources is not. The UI renderer is shared, but the data contract is not. Per-entity source claims are currently embedded in many separate catalog page-detail responses, and the frontend consumes inconsistent shapes such as `data.title.sources`, `data.model.sources`, and `data.profile.sources`. The only generic `/api/sources/` endpoint is the global source catalog, not a per-entity sources surface.

The inconsistency is visible at the product level too: `credit-role` is a catalog entity, but it does not participate in the same Sources and Edit History subroute pattern as the other catalog entities.

## Proposal

Treat Sources the same way Edit History is already treated: make it a generic per-entity provenance surface with one normalized frontend contract, instead of having it piggyback on per-entity detail payloads.

The main win is structural consistency and ability to update the UI consistently (which we are going to do in a follow-up). A generic Sources surface would eliminate shape drift across entity pages, make the shared UX truly shared instead of convention-based, and make gaps like `credit-role` straightforward to close.
