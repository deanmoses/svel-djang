# Entity Conversion Status

We've been moving all catalog entities:

1. Updating their detail reader view from a tabbed UI to be accordion-based and their edit to be section-based: docs/plans/DetailRefactorGuide.md
2. Implementing create, delete and restore: docs/plans/RecordCreateDelete.md

/#1 has to be done before #2 so that the delete menu item can be put into the Edit menu that #1 creates.

| Entity                  | Detail + Edit | Create + Delete + Restore |
| ----------------------- | ------------- | ------------------------- |
| Title                   | ✅            | ✅                        |
| MachineModel            | ✅            | ✅                        |
| Manufacturer            | ✅            | ❌                        |
| CorporateEntity         | ❌            | ❌                        |
| Person                  | ✅            | ✅                        |
| System                  | ✅            | ❌                        |
| Series                  | ✅            | ❌                        |
| Franchise               | ✅            | ❌                        |
| Theme                   | ✅            | ❌                        |
| GameplayFeature         | ✅            | ❌                        |
| TechnologyGeneration    | ✅            | ✅                        |
| TechnologySubgeneration | ✅            | ✅                        |
| DisplayType             | ✅            | ✅                        |
| DisplaySubtype          | ✅            | ✅                        |
| Cabinet                 | ✅            | ✅                        |
| GameFormat              | ✅            | ✅                        |
| RewardType              | ✅            | ✅                        |
| Tag                     | ✅            | ✅                        |
