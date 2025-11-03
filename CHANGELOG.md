## Changelog

### 2025-11-03
- Added automated pytest suite under `tests/` covering inbox parsing, lemma extraction, CSV writes, Anki auto-launch retry, UI refresh, and dry-run/full pipeline behaviors.
- Updated `run_pipeline.sh` to default to production runs, expose CLI flags for dry-run testing, auto-open Anki, refresh the UI, and trigger a post-import sync.
- Documented the Anki auto-launch, refresh, and sync workflow in README “Automation notes”.
