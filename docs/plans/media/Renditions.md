# Image Renditions Plan

Plan date: 2026-04-03

This document describes the product and architecture direction for Pinbase-owned image delivery after the initial media support work. It focuses on uploaded images that Pinbase has the right to store and display. Third-party image references remain external.

## Background

Pinbase's current image system stores uploaded originals in R2 and also stores fixed derived files for the main UI use cases. Today that means the application decides in advance which sizes exist, generates those files during upload, and stores them as separate physical renditions.

That approach is simple and it was the right first step. It kept the initial media feature synchronous, easy to reason about, and independent of a background worker system.

It also has an obvious downside: image size becomes part of the storage model. If the product wants a different thumbnail size, a different card crop, or a new hero treatment, that is no longer just a presentation change. It becomes a media regeneration problem.

## Justification

Image dimensions are primarily a delivery concern, not catalog truth.

Pinbase's real source of truth is:

- which uploaded asset exists
- which entity it is attached to
- which category it belongs to
- which image is primary

Those facts belong in Pinbase and in the claims-based media model. By contrast, "400px thumbnail" versus "480px thumbnail" is not a piece of catalog truth. It is a presentation choice that should be cheap to change.

Cloudflare is well suited to that delivery layer. It can resize Pinbase-owned originals on demand, cache the generated result at the edge, and let the application change image presets without regenerating a library of stored files. That gives Pinbase more product flexibility while reducing application-owned image processing work.

This is also a cleaner operational split:

- Pinbase owns uploads, permissions, attachments, provenance, and editorial choices.
- Cloudflare owns delivery-time resizing, format negotiation, caching, and global distribution.

## Decision

Pinbase should move toward a model where the uploaded original is the canonical stored image and Cloudflare generates delivery variants for Pinbase-owned images.

The plan is not to let arbitrary sizes leak throughout the product. Instead, Pinbase should define a small vocabulary of named image presets such as thumbnail, card, detail, and hero. Product and frontend code should request those logical presets. Cloudflare should turn those preset requests into resized cached assets.

This keeps the product flexible without turning image delivery into an unbounded free-for-all.

## Goals

- Make image size and format a configuration concern rather than a migration concern.
- Keep Pinbase's claims-based attachment model unchanged.
- Keep Pinbase-owned originals in storage that Pinbase controls.
- Use Cloudflare for resizing, optimization, and CDN caching.
- Preserve the rule that third-party media stays external.
- Give product and frontend teams a stable set of named image variants.

## Non-Goals

- No re-hosting or proxying of OPDB, IPDB, Fandom, Wikidata, or other third-party images.
- No attempt to expose arbitrary width and height combinations across the product.
- No migration to Cloudflare Images managed storage as a prerequisite for this plan.
- No change to the editorial model for categories, primaries, or attachment claims.

## Product Shape

From a product perspective, Pinbase should stop thinking in terms of "files we pre-generated during upload" and start thinking in terms of "approved ways the product may present an image".

That means:

- the UI asks for named presets, not hard-coded one-off sizes
- changing a preset is a product decision, not a data migration
- new surfaces can reuse an existing preset or introduce a new one intentionally
- the same uploaded original can support multiple presentation contexts without extra ingest work

This keeps image behavior consistent across cards, lists, detail pages, and future layouts.

## Architecture Shape

At a high level, the architecture should be:

1. Pinbase accepts and validates uploads for Pinbase-owned images.
2. Pinbase stores the canonical original in R2 and records the media asset and attachment truth in its existing media models.
3. Cloudflare sits in front of that storage on a Pinbase media domain.
4. Cloudflare generates and caches approved delivery variants from the original when requested.
5. APIs and frontend code use stable preset-based URLs or helpers rather than treating stored derived files as first-class data.

The important boundary is that Pinbase still owns media truth, while Cloudflare owns rendition delivery.

## Why Not Keep Pre-Generated Renditions

Keeping pre-generated renditions is still viable for a very small system, but it locks presentation choices into stored artifacts. Over time that creates avoidable friction:

- every new image surface pressures the storage model
- old rendition sizes linger after the UI moves on
- changing a preset becomes a backfill or dual-support problem
- the application does work that the CDN layer is better positioned to do

That is not a good long-term fit for a product that will continue refining its presentation layer.

## Why Not Move Fully Into Cloudflare Images Storage

The main opportunity here is delivery, not a storage migration.

Pinbase already has an R2-backed media model and clear ownership boundaries around which files it stores. Moving to Cloudflare-hosted image storage would be a larger system change with less product benefit than simply adopting Cloudflare's resizing and caching layer in front of the originals Pinbase already stores.

The simpler plan is the better one: keep Pinbase's owned originals, put Cloudflare in charge of delivery.

## Relationship To Existing Media Architecture

This plan does not change the claims-based media attachment model.

`MediaAsset` remains the logical owned upload. `EntityMedia` remains the resolved attachment truth. What changes is how Pinbase thinks about delivery variants. The system should gradually move away from treating fixed stored thumbnails and display files as the long-term source of truth for presentation.

In other words:

- attachment truth stays in Pinbase
- canonical originals stay in Pinbase-controlled storage
- rendition generation moves to Cloudflare

## Rollout Direction

The rollout should be incremental:

1. Put a Cloudflare-served custom domain in front of Pinbase media storage.
2. Introduce named delivery presets for uploaded images.
3. Route those presets through Cloudflare resizing and caching.
4. Simplify Pinbase's own rendition generation once the new delivery path is established.

This keeps the migration low-risk. Pinbase can adopt the new delivery model before it fully removes old assumptions.

## Success Criteria

This plan is successful when:

- product can change thumbnail and hero sizing without a media migration
- frontend code uses a small stable preset vocabulary
- Pinbase stores fewer presentation-specific artifacts
- uploaded images are delivered faster and more consistently through Cloudflare
- the legal and editorial boundary around third-party media remains intact
