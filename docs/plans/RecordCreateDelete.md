# Creating and Deleting Records

Up to this point, all records have been created during ingest; users could not create them or delete them. Now it's time to let users create records AND delete them.

We're going to start with models and titles.

## Basics of Creation and Deletion

### Any Registered User Can Create & Delete

Any logged-in user can create or delete a record.

We'll almost certainly tighten this up later -- such as you need to have 5 edits to do a create, or have some level of status -- but fully open is what we're doing for now.

### Creation or Deletion Not Subject to Review

Going through the record creation UI publishes the record publicly immediately. Deleting a record deletes it immediately.

We'll almost certainly tighten this up later -- such as proposed creates going into an approval queue -- but immediate is what we're doing for now.

### No Special Marking of User-Created Records

Newly created records will not be visibly marked as “user-created / needs review”. Again, in the future we may change to have record creates go into an approval queue -- but not right now.

### Records Are Findable Immediately

The default pattern is that newly created records show up immediately in lists / search / dropdowns, even though they might be sparse or incomplete.

### Record Creation / Deletion Creates a ChangeSet

Creating / deleting a record generates a normal user ChangeSet and appear in edit history/sources exactly like any other edit.

### Resolution Priority: Same as Edits

Creates and deletes are resolved at the same precedence as normal user edits. Currently that's set by user.profile.priority, default 10000. Ingest sources are much lower priority: e.g. IPDB 100 and OPDB 200.
Yes, this is pretty permissive: any logged-in user can create or delete and it's not just public immediately, it is usually the winning canonical truth immediately. Again, we can tighten up in a follow-up release.

Yes, this means if a user creates "Godzilla" today and IPDB imports Godzilla tomorrow, the user's sparse record wins on every field the user touched. Again, we can tighten up in a follow-up release.

### Deletion Claims

Delete is a claim `status = deleted` attached to a ChangeSet at user priority. Highest-priority claim wins, same as every other field.

#### Consequences

- User deletes → `status = deleted` at priority 10000 → record hidden everywhere it's user-facing.
- Ingest re-imports tomorrow at priority 100 → still hidden.
- Resurrection: another user later writes a `status = active` claim, wins by recency. This would require a UI to find deleted records.
- Admin can hard-delete if truly needed.

#### Entities With a Status Field

Only the independent lifecycle-managed entities: Title, MachineModel, Manufacturer, CorporateEntity, Person, Theme, GameplayFeature, System, Series, Franchise, taxonomy entities. These are the things a user can meaningfully "delete."

Owned child rows — aliases, abbreviations, credits, M2M through rows (MachineModelTheme, MachineModelTag, etc.), media renditions, provenance bookkeeping — do not have status. They ride with their parent's visibility.

#### Cascade Behavior

Cascade behavior mirrors DB FK semantics, but splits by target type:

| FK target                                                                   | Soft-delete behavior                                                                                                                                                        |
| --------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| PROTECT, referenced by an _active_ independent entity                       | Block the delete. UI explains what's referencing it.                                                                                                                        |
| PROTECT, referenced only by already-soft-deleted entities                   | Allow; those references don't count as active. See note below on enforcement.                                                                                               |
| CASCADE to an independent lifecycle entity (e.g. Title → MachineModel)      | Write `status = deleted` claims for each child in the same ChangeSet.                                                                                                       |
| CASCADE to an owned child row with no lifecycle status (e.g. Title → Alias) | Do nothing special. The child disappears because the parent is hidden. Do not invent fake lifecycle claims.                                                                 |
| SET_NULL / SET_DEFAULT                                                      | Not currently present in catalog/media/provenance. (Citation app has a few, but citations are not user-deletable here.) If added later, per-relationship decision required. |

**Enforcement note on PROTECT.** DB-level FK PROTECT operates on raw rows; it has no awareness of `status = deleted`. So the "allow if referrers are all soft-deleted" rule cannot be enforced by the DB — it must be computed at the application layer by walking the reference graph and filtering out entities whose resolved status is `deleted`. The DB's PROTECT constraint remains as a safety net against bugs, not as the mechanism that implements this policy.

#### Links to Deleted Records

If an admin hard deletes a record, it's gone and the system serves a 404 like any not found record.

For claims-deleted records, the v1 will also serve a 404.

In a future version -- NOT v1 -- we should look at serving a HTTP 410 Gone, with a "This record was deleted" page with links to view history and restore the record.

#### Resurrection

There are two distinct ways a soft-deleted record can come back, and they have different cascade semantics. The spec supports both.

**Undo** — invert a specific past delete ChangeSet. Because the delete ChangeSet contained `status = deleted` claims for every cascaded child, inverting it restores the whole tree atomically. Symmetric by construction. A user who deletes a Title and immediately hits Undo gets their Models back without having to resurrect each child individually. This is the primary expected flow, especially for fat-finger deletes.

**Restore** — a fresh ChangeSet that writes `status = active` on the record. This is just another claim, and normal resolution handles it: the later same-priority claim wins by recency. Restore does **not** automatically bring children back, because the children still carry their own `status = deleted` claims from the original delete ChangeSet. If the user wants the tree restored, they either Undo the original delete or Restore each child individually.

Undo is only available while the delete ChangeSet is still the latest action against the record. Restore is the mechanism for bringing back a record whose delete is older or has been superseded.

### Delete Confirmation

Every record type gets a delete confirmation screen. The delete confirmation needs to show what's at stake.

"Delete 'Godzilla'? This hides 1 model, 12 images, 8 changesets."

### Create With Minimum Fields

The general pattern for record creation is to create with the minimum number of fields to have a valid record -- often name and slug. All other changes will be made via the normal edit process.

### Note Field & Citations

Create and Delete screens should have both a Notes field and Citation support, just like Edit screens. They should be toggled closed by default. Neither is required.

### Duplicate Prevention

The system must aggressively prevent duplicate records.

#### Enforced at the API, Not Just the UI

All duplicate-prevention rules below are enforced at the API layer, independent of whatever the UI does. The UI gates (search-then-create, collision messaging) are ergonomic affordances, not the mechanism. The API must reject a colliding create even when it arrives without having gone through the UI gate — whether because two users raced to submit the same name, a client has stale state, or the request bypassed the UI entirely. Slug uniqueness is already enforced by the DB; name-collision rules are not, and must be enforced in the create endpoint.

#### Create Is Offered Only After Search (or When the List Is Fully Visible)

The rule's intent is duplicate prevention — force the user to look before they create. How "look" is surfaced depends on list size, matching the existing `SearchableGrid.svelte` threshold (`SEARCH_THRESHOLD = 12`):

- **`items.length >= SEARCH_THRESHOLD`** (larger lists like titles, people, manufacturers): search is required, and creation is offered only when a search returns zero results, via `NoResultsCreatePrompt`.
  - This assumes the normal search normalizes basic things like case, punctuation, articles.
  - Aliases count as results.
- **`items.length < SEARCH_THRESHOLD`** (smaller lists like most taxonomy entities): no search input is rendered — the full list is visible on screen, so duplicate prevention is satisfied by visibility. Creation is offered as an auth-gated "+ New {entity}" link in the list header.

As a list crosses the threshold, the header link disappears and the search + no-results prompt takes over. The transition is coherent and happens automatically based on item count. Both list-page variants and any dedicated create routes must keep the constant in lockstep — reuse `SEARCH_THRESHOLD` from `SearchableGrid.svelte` rather than redefining it.

For a future version, maybe there's a special search that finds misspellings, chops things like "Limited" and "Edition". But not for this v1.

The API-level duplicate prevention described above applies in both cases — the UI gate is an ergonomic affordance, not the enforcement mechanism.

#### Name Collisions

Title and Model names aren't unique. That's necessary because names _are_ re-used in the industry. However, if the user types in a name that is a collision, for this V1 will will block creation. Require the user to give a disambiguating name.

People's names are not unique. However, in the history of pinball as recorded in IPDB and our database, there's been zero duplicates so far. For v1 we will reject duplicate names.

We may decide to change this approach later, but reusing names is an edge case and we can see how the "no duplicate creation via the UI" feels for now. The first time we hit an issue, I think we're going to have a discussion as a team about how to handle it, so it's not worth baking in rules now.

Because of this rule, we don't need slug auto-suggest like godzilla-2.

#### Slug Collisions

Slugs are a separate collision surface from names, and the rules are enforced by the DB, not by editorial preference.

Current model (as of this writing):

- `Title.slug` — globally unique (`unique=True`).
- `MachineModel.slug` — globally unique. The URL pattern is `/models/{slug}` with no title segment, so global uniqueness is load-bearing for routing, not just a DB nicety.
- `Manufacturer.slug` — globally unique.
- `Location.slug` — not globally unique (scoped).

Implication: duplicate prevention must check both axes, because they can disagree:

- Two models with the same name but different slugs (`godzilla-stern-pro` vs `godzilla-williams-pro`) pass the DB check but fail the name-collision rule.
- Two models with different names that sluggify to the same thing pass the name check but fail the DB check.

UX should surface each with distinct messaging:

- Name collision → "A Title/Model/Manufacturer named X already exists. Pick a disambiguating name."
- Slug collision → "The slug `x` is already taken. Edit the slug field."

Model slugs being globally unique is worth calling out separately: it means "Pro" as a model slug is only claimable once across the entire catalog, so in practice Model slugs need to be title-qualified (`godzilla-pro`, not `pro`). The auto-populate-from-name behavior should reflect this — likely by prepending or incorporating the parent Title's slug — but the exact rule is a detail to settle during Model Create implementation.

### Rate Limits

Values:

- create: 5 ChangeSets / hour
- edit: 60 ChangeSets / hour
- delete: 5 ChangeSets / day

Notes:

- Enforce per user, not per IP
- Staff/admin accounts are exempt from these limits
- Inverting your own ChangeSet (delete, create, or edit) is exempt from these limits
- Both successful AND attempted ChangeSets count against these limits
- Rolling window, not calendar hour/day
- Restore uses the same bucket as create
- A cascading delete counts as one delete ChangeSet, not one per hidden child
- If a single UI action creates one ChangeSet, that’s what the limit applies to, even if many claims are written inside it.
- These values must be in well-documented constants where they can be easily found and updated
- The API returns 429 with a Retry-After header
- The UI surfaces the time at which the next slot frees up

## Specific Record Types

We're going to implement Title Create, learn from that, apply those learnings to a detailed plan for Model Create, learn from that, then move on to other record types.

### Titles

#### Creation Entry Point: Search on Titles List Page

If you search on the Titles list page ( http://localhost:5173/titles?q=NO_SUCH_TITLE ), you get text like this:

The title "NO_SUCH_RECORD" does not exist. Create?

... where "Create" is a hyperlink to a create flow.

#### Title Create Screen

Fields: Name, Slug (autopopulated from name, but editable)

After you click Save you're taken to the Title Detail page, where you can further edit the title.

#### Titles with Zero Models

When the user first creates a Title and lands on the Title detail page, we should have a very obvious "Create first model" CTA with a link to the model create screen. This "Create first model" is shown to any user viewing that page until the first model is created. If all models are deleted from the title, that CTA comes back.

#### Deletion Entry Point: Title Detail Edit Menu Item

On the Title Detail page, there's an Edit menu dropdown. Let's have Delete Title as the last item. It shows some sort of confirmation.

On single-model titles, this deletes both the model and the title.

### Models

#### Creation Entry Point: the Titles Detail Page

To create a Model, the parent Title must first exist. Go to the parent title's detail page. In the Edit menu dropdown, we're going to add a "Create Model" as the last menu item.

There is no global Models page or Models search; the UI requires you to go through the parent Title to see a Model.

#### Model Create Screen

Fields: Name, Slug (autopopulated from name, but editable)

There's a strong argument to also have variants, which is pretty fundamental, but since the record is valid without it, let's leave it off at first, see how it feels.

After you click Save you're taken to the Model Detail page, where you can further edit the model.

#### Deletion Entry Point: Model Detail Edit Menu Item

On the Model Detail page, there's an Edit menu dropdown. Let's have Delete Model as the last item. It shows some sort of confirmation.

### People

#### Creation Entry Point: Search on the People List Page

If you search on the People list page, you get text like this:

The person "NO_SUCH_PERSON" does not exist. Create?

... where "Create" is a hyperlink to a create flow.

### Manufacturers

#### Creation Entry Point: Search on the Manufacturers List Page

If you search on the Manufacturers list page, you get text like this:

The manufacturer "NO_SUCH_MANUFACTURER" does not exist. Create?

... where "Create" is a hyperlink to a create flow.

#### Big Open Question

We're going to have to think through creating a Manufacturer vs a Corporate Entity. We will think this through during planning for Manufacturer create & delete.
