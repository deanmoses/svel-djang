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
| PROTECT, referenced only by already-soft-deleted entities                   | Allow; those references don't count as active.                                                                                                                              |
| CASCADE to an independent lifecycle entity (e.g. Title → MachineModel)      | Write `status = deleted` claims for each child in the same ChangeSet.                                                                                                       |
| CASCADE to an owned child row with no lifecycle status (e.g. Title → Alias) | Do nothing special. The child disappears because the parent is hidden. Do not invent fake lifecycle claims.                                                                 |
| SET_NULL / SET_DEFAULT                                                      | Not currently present in catalog/media/provenance. (Citation app has a few, but citations are not user-deletable here.) If added later, per-relationship decision required. |

#### Resurrection Symmetry

Resurrecting a parent inverts the same ChangeSet that deleted it, which re-activates cascaded children in one atomic move. A user who deletes a Title and undoes it gets their Models back; they don't have to resurrect each child individually.

### Delete Confirmation

Every record type gets a delete confirmation screen. The delete confirmation needs to show what's at stake.

"Delete 'Godzilla'? This hides 1 model, 12 images, 8 changesets."

### Create With Minimum Fields

The general pattern for record creation is to create with the minimum number of fields to have a valid record -- often name and slug. All other changes will be made via the normal edit process.

### Note Field & Citations

Create and Delete screens should have both a Notes field and Citation support, just like Edit screens. They should be toggled closed by default. Neither is required.

### Duplicate Prevention

The system must aggressively prevent duplicate records.

#### Create Is Offered Only After Search

- Creation should only be offered to the user after a search for that record type returns no results.
  - This assumes the normal search normalizes basic things like case, punctuation, articles.
  - Aliases count as results.
- For a future version, maybe there's a special search that finds misspellings, chops things like "Limited" and "Edition". But not for this v1.

#### Name Collisions

Titles and Models names aren't unique. That's necessary because names _are_ re-used in the industry. However, if the user types in a name that is a collision, for this V1 will will block creation. Require the user to give a disambiguating name.

We may decide to change this approach later, but I think reusing names is an edge case and we can see how this feels for now. The first time we hit this I think we're going to have a discussion as a team about how to handle it, so it's not worth baking in rules now.

Because of this rule, we don't need slug auto-suggest like godzilla-2.

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

When the user first creates a Title and lands on the Title detail page, we should have a very obvious "Create first model" CTA. This "Create first model" is shown to any user viewing that page until the first model is created. If all models are deleted from the title, that CTA comes back.

#### Deletion Entry Point: Edit Menu Item

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

#### Deletion Entry Point: Edit Menu Item

On the MOdel Detail page, there's an Edit menu dropdown. Let's have Delete Model as the last item. It shows some sort of confirmation.

### People

#### Creation Entry Point: Search on the People List Page

If you search on the Peoples list page, you get text like this:

The person "NO_SUCH_PERSON" does not exist. Create?

... where "Create" is a hyperlink to a create flow.

### Manufacturers

#### Creation Entry Point: Search on the Manufacturers List Page

If you search on the Manufacturers list page, you get text like this:

The manufacturer "NO_SUCH_MANUFACTURER" does not exist. Create?

... where "Create" is a hyperlink to a create flow.

#### Big Open Question

We're going to have to think through creating a Manufacturer vs a Corporate Entity. We will think this through during planning for Manufacturer create & delete.
