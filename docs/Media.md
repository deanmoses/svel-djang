# Media System

Pinbase hosts user-uploaded images in S3-compatible storage (Cloudflare R2). Uploads go through Django, which generates renditions synchronously and stores them directly in R2. The browser loads images straight from storage — Django is never in the serving path.

## Ownership Boundary

The media system only handles media that Pinbase has a clear license to display: images uploaded by users (who grant Pinbase a license) or owned by The Flip Museum.

Third-party media (OPDB, IPDB, Fandom, Wikidata) stays outside. Pinbase does not download, transcode, re-host, or proxy third-party files — there are legal issues with doing so. Third-party image references remain in `extra_data` where they came from.

The API prefers uploaded media first, then falls back to third-party references when no uploads exist for a given entity.

## Three-Layer Data Model

Media uses three models with a deliberate separation between infrastructure and catalog truth:

- **MediaAsset** — One logical upload. Tracks metadata (kind, filename, dimensions, who uploaded it). Infrastructure, not a claim.
- **MediaRendition** — One physical file for an asset. Each image upload produces three: original (format-converted), thumbnail (400px, WebP), and display (1600px, WebP). Infrastructure, not a claim.
- **EntityMedia** — The attachment linking a catalog entity to an asset. Carries category and primary flag. This is catalog truth, materialized from claims.

The split matters because assets and renditions are storage infrastructure that exists independently of how the catalog uses them. Attachments are editorial decisions (which images belong to which entity, which is primary) that go through provenance like every other catalog fact.

## Claims and Primaries

Media attachments go through the provenance system via the `media_attachment` claim namespace, just like credits, themes, and every other relationship. Uploading an image asserts a claim; detaching it asserts an `exists=False` claim. Resolution materializes the winning claims into `EntityMedia` rows.

Primary enforcement happens at resolution time: at most one primary image per (entity, category) pair. If multiple claims compete, highest priority wins, ties broken by most recent upload. If a category ends up with no primary (e.g. after a detach), the oldest remaining attachment is auto-promoted — so every category always has a primary for the UI to display.

## Upload Mental Model

Upload and attach happen in a single synchronous request. The user is always uploading _to_ a specific entity with a specific category — there's no use case for uploading without immediately attaching. Combining them avoids orphaned assets.

Image processing (thumbnail + display generation) takes under a second with Pillow, so there's no task queue or "processing" state for images. The request either succeeds atomically (storage writes + DB rows + claim + resolution) or fails cleanly with nothing left behind. Async processing is reserved for video, where it genuinely matters.

When the user selects multiple files, the frontend sends one request per file concurrently with per-file progress tracking.

## Adding a New Entity

Adding media support to a new entity type is ~20 lines of wiring across backend and frontend. Inherit the `MediaSupportedModel` mixin, set `MEDIA_CATEGORIES` on the model, add a `GenericRelation`, and wire the existing shared helpers into the entity's API and UI. No new resolver code, no new claim logic, no new storage code.

## Follow-Up Work

### Follow-Up: Video Support

Schema additions:

- Add `duration_seconds` (PositiveIntegerField, nullable) to `MediaAsset`.
- Add constraints: `duration_seconds > 0` when set; when `kind = 'image'`, `duration_seconds` must be null.

Infrastructure:

- Presigned direct-to-S3 uploads (needed for large video files — no migration, same S3 bucket).
- Async task queue (evaluate options: Celery, django-q2, or lighter-weight).
- Video transcoding worker: poster frame + MP4 fallback (adapted from flipfix's `core/transcoding.py`).
- Full status state machine: `pending` -> `processing` -> `ready` / `failed`.
- Frontend polling pattern activation in `media-upload.ts`.
- `VideoPlayer.svelte` component with transcode state handling (adapted from flipfix's video player patterns).
- HLS adaptive streaming only if demand justifies operational cost.

### Follow-Up: CDN

Put a CDN in front of the image serving. This requires no code changes.

- Point a custom domain (e.g. `media.pinbase.app`) through Cloudflare DNS — this automatically enables Cloudflare's CDN in front of R2 (free tier, zero additional cost).
- Switch `MEDIA_PUBLIC_BASE_URL` to the custom domain.
- Configure cache headers and optional purge hooks.

### Follow-Up: Dedupe

Detect when someone uploads the same image.

- Add `sha256` field to `MediaAsset`.
- Compute hash on upload, check for existing asset.
- Decide UX: block duplicate, reuse existing asset, or warn.

### Follow-Up: User Roles and Permissions

- Design a cross-cutting user-role/permission model that applies to all claim types (not just media).
- Topics: tiered permissions, who can retract whose claims, moderation workflows, promotion paths.
- This is a broader product decision that should be considered as a whole rather than decided piecemeal per feature.
