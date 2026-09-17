---
type: Reference
status: draft
---

# Upstream Tracking

This fork tracks [element-hq/element-x-android](https://github.com/element-hq/element-x-android),
licensed AGPL-3.0. This document is the seventwos record of our sync
state with upstream; update it (and add a `log.md` entry) every time
`develop` is rebased/merged against upstream.

## Fork relationship

* **Upstream**: `element-hq/element-x-android`, default branch `develop`.
* **Our branch**: `develop` (this repo's default branch).
* **Sync model**: pull-based. We periodically merge or rebase upstream
  `develop` into ours; we do not push changes upstream.

## Last known sync point

* **Recorded**: 2026-09-17
* **Our `develop` HEAD**: `9bf10fbc4f46f235b0737f534c272f88190efba1`
* **Upstream `develop` HEAD at time of recording**: `58a00fd4e5790b858898bbe2066003e04bf79a3f`
* **Divergence**: upstream was **11 commits ahead** of our last sync point
  (per `gh api repos/element-hq/element-x-android/compare/<our-sha>...<upstream-sha>`).

## Upstream changes since fork

No upstream sync has been performed yet since this tracking document was
created; the 11-commit gap above is outstanding. Record each sync as a
dated entry below once performed.

### Sync log

* _(none yet — this document was seeded before the first tracked sync)_

## Process for the next sync

1. Compare current `develop` HEAD against upstream `develop` HEAD.
2. Merge or rebase upstream changes into `develop`.
3. Re-run `python3 scripts/okf/validate_okf_markdown.py --all` to confirm
   the `documentation/` bundle is unaffected.
4. Update this file's **Last known sync point** and append a **Sync log**
   entry summarizing what upstream changed (feature areas, breaking
   changes, version bumps) and any adaptation needed on our side.
5. Add a corresponding `log.md` entry.
