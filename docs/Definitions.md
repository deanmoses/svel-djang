# Pinball Terminology

Here are precise definitions for terms used by enthusiasts, collectors and the pinball industry.

These should map exactly to how those constituents use the terms; these aren't "our" terms.

## Model

An actual buyable SKU.

**Examples**:

- These are all separate models: Godzilla Pro, Godzilla Premium, Godzilla LE, Godzilla 70th Anniversary Edition

## Title

A distinct pinball game design — the canonical identity of a game regardless of how many different versions / editions / models / variants were produced.

**Examples**:

- _Medieval Madness_: both the 1997 original as well as the 2014 Chicago Gaming remakes that are 1-to-1 clones.
- _Eight Ball Deluxe_
- _The Addams Family_

## Variant

A version of a pinball machine produced by the original manufacturer that shares the same hardware platform and playfield layout, differing only in ways that do not affect gameplay, such as cosmetic trim, artwork, minor software features, minor mechanical differences (e.g., different toys, lights, speakers).

Collectors and enthusiasts think "It's the same game".

The word 'variant' is often more loosely, to to talk about any version within the same family: Godzilla Pro/Premium/LE are all variants/versions. But there's no other word that expresses "it's the same machine", so it's really useful to use the narrower definition here.

**Examples**:

- These are variants of each other: Godzilla Premium and Godzilla LE, Godzilla 70th Anniversary Edition. However, Godzilla Pro is not a variant of those, because it has different hardware and plays differently.

## Revision

A technical update to a `Model` by the original manufacturer to fix a hardware flaw (e.g., changing the power supply mid-run).

Collectors often refer to these as factory updates or mid-run changes rather than “revisions.”

## Clone

A machine with a substantially identical playfield layout but produced by a different manufacturer using different hardware, often for regional markets or licensing constraints.

Clones are not always identical; sometimes they can differ in:

- electronics
- cabinet proportions
- scoring behavior

A clone can either be licensed or unlicensed.

**Examples**:

- Taito Brazil’s Cavaleiro Negro was an unlicensed clone of Black Knight

## Re-theme

A machine that uses the same physical layout but changes the artwork, sound, and often the rules to create a “new” game.

**Examples**:

- JACK•BOT is a re-theme of PIN•BOT

## Remake

Remaking an older game with new technology and modernizing its components. Remakes often preserve the original layout and rules, though small adjustments are sometimes made.

Unlike a Vault release, a Remake typically uses modern hardware and components rather than reproducing the original electronics.

**Examples**:

- Chicago Gaming Company’s Monster Bash Remake is a remake of Williams' Monster Bash
- Chicago Gaming Company’s Attack from Mars Remake is a remake of Attack from Mars

**How it differs from OPDB**:
OPDB calls these aliases; collectors call them "Remakes."

## Export

Same manufacturer, different market.

**Examples**:

- Bally produced an export version of Scared Stiff (1996) for the European market.

## Vault

The same manufacturer (classically, Stern), producing new runs of older games. Essentially the same machine produced again, typically with only small component updates rather than a full technological redesign.

**How it differs from OPDB**:
OPDB calls it an "Alias."

**Examples**:

- Iron Man Vault Edition

## Alias

`Alias` is not a term born from collectors or the industry; rather, it is a data architecture term necessitated by competitive play.

Whereas `Variant` and `Clone` describe the physical machine, `Alias` describes the gameplay identity.

In databases like OPDB or the IFPA (International Flipper Pinball Association), an `Alias` is a way to say: "For the purposes of rules, scoring, and strategy, these two machines are the same."

Some tournament directors may not want players to have two separate rankings for Black Knight and Caballero Negro because they are playing the exact same layout and rules, so they "alias" them to a single master record to keep the data clean. However, this is on a per-tournament basis; there is no universal rule.

IFPA does not use the word “alias”; instead, they talk about:

- combining games
- grouping games
- treating games as the same
