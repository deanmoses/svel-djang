# Citation Edit UX Improvements

Concise product-direction sketch for improving citation entry.

## Goal

Citation entry should feel like one unified flow:

- the user starts typing to find an existing citation source, OR pastes evidence such as a URL, ISBN, DOI, or similar identifier
- the system first tries to find an existing source
- if no existing source is found, the system tries to build a new source draft automatically

## Desired UX

The citation input should accept both:

- free-text search queries for existing sources
- pasted evidence inputs

Examples:

- `Bueschel`
- `The Encyclopedia of Pinball`
- `0964359219`
- `https://www.ipdb.org/machine.cgi?id=1681`

The user should not have to choose a mode up front. The product should interpret the input and move into the appropriate path.

## High-Level Flow

### 1. Search existing first

Every input goes through the existing-source search path first.

- text queries search known source fields
- ISBN-like input searches ISBN
- URL input searches known source links

If the system finds a strong existing match, the user can cite it immediately.

### 2. If not found, resolve from pasted evidence

If no existing source matches and the input looks like evidence rather than ordinary text, the system should attempt automatic resolution.

Examples:

- ISBN -> resolve book metadata
- DOI -> resolve publication metadata
- URL -> resolve metadata for a known or generic site

The output is a proposed new `CitationSource` draft, not a silent auto-create.

### 3. Confirm, then cite

The user sees a lightweight confirmation step:

- use existing source
- or create the proposed new source
- then optionally add a locator if the source type calls for one

## Known-Site Extractors

For arbitrary URLs, generic extraction is weak. The stronger model is:

- sparse generic fallback for unknown sites
- rich extraction for known sites

For example, an `ipdb.org` extractor could understand:

- IPDB URL patterns
- the IPDB machine/page ID
- the page title and other structured page information

## Plugin Architecture

The automatic-resolution layer should use a plugin architecture inspired by Zotero translators. Extraction lives on the Django backend (see [CitationAutogenerationDesign.md](CitationAutogenerationDesign.md)) since extractors need server-side HTTP, API keys, and rate limiting.

Each plugin should be responsible for a narrow slice of behavior:

- recognizing whether it can handle an input
- extracting metadata for that input or site
- normalizing the result into Pinbase's `CitationSource` draft shape

Examples:

- an ISBN plugin
- a DOI plugin
- a generic URL plugin
- a site-specific `ipdb.org` plugin

The important idea is that the system should be extensible without rewriting the whole resolver every time we want to support a new source family or domain.

## Product Constraints

- Existing-source search remains the first step.
- Automatic resolution should help create a new source draft, not bypass review entirely.
- URL support should prioritize known-site extractors over optimistic generic scraping.
- Locator entry should happen at citation time only when it is actually useful.
