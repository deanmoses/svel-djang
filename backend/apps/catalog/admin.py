# Catalog models are intentionally not registered with Django admin.
#
# All catalog truth is managed through the claims/provenance system via the
# user-facing edit UI and ingest pipeline. Admin is reserved for:
#   - Source, Claim, ChangeSet  (provenance/admin.py)
#   - License                   (core/admin.py)
#   - User                      (accounts/admin.py)
#
# See docs/plans/ValidationFix3.md for the rationale.
