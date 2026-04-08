"""Helpers for reader-facing cited edit evidence."""

from __future__ import annotations


def build_cited_changesets(active_claims) -> list[dict]:
    """Serialize active user changesets that have attached citation instances."""
    grouped: dict[int, dict] = {}

    for claim in active_claims:
        if claim.changeset_id is None or claim.user_id is None:
            continue

        claim_citations = getattr(claim, "prefetched_citation_instances", [])
        if not claim_citations:
            continue

        entry = grouped.get(claim.changeset_id)
        if entry is None:
            entry = {
                "id": claim.changeset_id,
                "user_display": claim.user.username if claim.user else None,
                "note": claim.changeset.note if claim.changeset else "",
                "created_at": (
                    claim.changeset.created_at.isoformat() if claim.changeset else ""
                ),
                "fields": [],
                "_field_set": set(),
                "_citations": {},
            }
            grouped[claim.changeset_id] = entry

        if claim.field_name not in entry["_field_set"]:
            entry["_field_set"].add(claim.field_name)
            entry["fields"].append(claim.field_name)

        for citation in claim_citations:
            signature = (citation.citation_source_id, citation.locator)
            if signature in entry["_citations"]:
                continue
            entry["_citations"][signature] = {
                "source_name": citation.citation_source.name,
                "source_type": citation.citation_source.source_type,
                "author": citation.citation_source.author,
                "year": citation.citation_source.year,
                "locator": citation.locator,
                "links": [
                    {"url": link.url, "label": link.label}
                    for link in citation.citation_source.links.all()
                ],
            }

    result = []
    for entry in grouped.values():
        result.append(
            {
                "id": entry["id"],
                "user_display": entry["user_display"],
                "note": entry["note"],
                "created_at": entry["created_at"],
                "fields": entry["fields"],
                "citations": list(entry["_citations"].values()),
            }
        )

    result.sort(key=lambda item: item["created_at"], reverse=True)
    return result
