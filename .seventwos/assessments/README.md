# .seventwos/assessments/

Landing zone for **immutable** upstream-assessment artifacts.

Each artifact is a single new file (suggested name:
`YYYY-MM-DD-<short-slug>.json` or `.md`) describing a specific evaluation of
upstream commits/changes against `../path-map.yml` and `../invariants.yml`.
Existing artifacts are never edited or deleted — a correction is a new file
plus a `../ledger.jsonl` entry explaining the correction.

This directory is currently empty: no assessment has been produced yet. The
`.github/workflows/seventwos-upstream-assessment.yml` workflow scaffold
accepts artifacts uploaded here (or as workflow_dispatch input) and archives
them as a CI artifact; it is read-only/report-only and does not evaluate,
apply, or act on their contents.
