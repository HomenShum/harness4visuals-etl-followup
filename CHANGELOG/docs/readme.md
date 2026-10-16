# README surface history

## 2026-10-16 — Clarify CLI first-run and export boundaries

- Added the declared Python/CLI entrypoint and repository-root working-directory requirement.
- Clarified that `verify` runs ETL plus threshold checks and unit tests run separately.
- Clarified that integration exports write local files for later provider steps.
- Preserved the existing overview, command examples, output shapes and integration-guide material.
- Source review checked immutable code, command dispatch and paths/links. The existing PR/push CI workflow separately declares unit tests and CLI verification; native CI results are separate evidence. Provider/model, browser and deployment readiness were not validated.
