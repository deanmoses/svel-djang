# Citation Granularity: Points vs. Ranges

Should citations be point markers inserted at a position, or ranges that wrap specific text?

## The Case for Ranges

Range-based citations (`[[cite-start:id:X]]some text[[cite-end]]`) wrap specific words, making scope explicit. A reader knows exactly which claim is supported by which source — no inference required.

This would be a genuine improvement over Wikipedia's point citations, where a footnote at end-of-sentence leaves the reader guessing whether it covers the whole sentence or just the last clause. For a project that aims to be the definitive pinball encyclopedia, that precision is appealing.

Ranges would also enable features like highlighted source coverage — visually showing which parts of a page are sourced and which aren't. And the museum director specifically identified per-sentence attribution as a differentiator from Wikipedia.

## Why We Chose Points Instead

Three practical problems make ranges unworkable despite their theoretical advantages.

### Problem 1: Multi-Source Sentences

A single sentence often draws on multiple sources:

```text
"The game was designed by Steve Ritchie and used DCS sound
which was a major upgrade over previous systems."
```

Source A (a flyer) confirms Ritchie. Source B (technical docs) confirms DCS. Source C (a review) confirms "major upgrade."

Precise wrapping means three separate ranges in one sentence — more markup than prose. Most editors will either wrap the whole sentence with one "main" source (a lie about what that source covers), stack all three on the whole sentence (source soup, no better than a point citation), or just cite once and move on (losing two sources).

All three outcomes are worse than point citations, because ranges _promise_ precision they can't deliver.

### Problem 2: Interleaving Truths

```text
The playfield was designed by [[cite-start:id:A]]Steve Ritchie[[cite-end]]
and the software was written by [[cite-start:id:B]]Larry DeMar[[cite-end]].
```

Source A is a flyer. Source B is the game ROM. Now someone finds Source C — an interview confirming both. Source C is unrepresentable: you can't wrap the whole sentence because A and B own sub-ranges, you can't nest C around them, and removing A and B loses precision.

This isn't an edge case. It's the success case — a well-sourced article naturally accumulates overlapping coverage. Ranges fight that instead of supporting it. Points handle it trivially: add another marker.

### Problem 3: People Are Lazy

Precise ranges require selecting small chunks of text: "designed by Pat Lawlor." That's fiddly. Every Wikipedia editor has been trained to put a footnote at the end of a sentence. When given a range tool, they'll select the whole sentence or paragraph — it's faster and it's what they know.

This feeds Problem 2. Large lazy ranges are easy to create and hard to subdivide later. When a new source covers part of an already-wrapped sentence, the contributor will add another whole-sentence range rather than carefully split the existing one. The system optimizes for precision but humans optimize for speed. The result is imprecise ranges that look precise to readers — worse than honest point citations.

## Decision

Point citations. Same as Wikipedia — proven at scale, honest about their granularity. See [CitationsDesign.md](CitationsDesign.md) for the format.
