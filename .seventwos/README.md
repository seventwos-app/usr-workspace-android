# .seventwos — upstream synchronization policy system

This directory is **repository-owned tooling**, not upstream code. It exists
because `usr-workspace-android` is a fork of
[`element-hq/element-x-android`](https://github.com/element-hq/element-x-android)
(AGPL-3.0) that carries intentional Seventwos product/UI divergence, and needs
a machine-checkable record of what is safe to accept from upstream, what must
be re-applied deliberately after a sync, and what must never silently change.

This is **foundation only**: it defines policy, seeds immutable state, and
validates structure/consistency in CI. It does **not** apply upstream changes,
compute merges, or run any automatic sync. See
[`documentation/upstream-tracking.md`](../documentation/upstream-tracking.md)
for the human-readable narrative log this system is designed to eventually
replace/back with machine-checked state; that document remains authoritative
for prose history until this system is adopted for real syncs.

## Files

| File | Purpose | Mutability |
|---|---|---|
| `policy.yml` | Principles and process for evaluating/applying upstream changes | Append-only changelog inside the file; rules change only via reviewed PR |
| `state.yml` | Seeded, point-in-time record of the upstream/fork/merge-base relationship | **Immutable seed.** Never edit in place; superseded only by a new dated entry recorded through `ledger.jsonl` and a fresh PR |
| `path-map.yml` | Categorizes repository paths (branding vs. compatibility-sensitive vs. product-divergence vs. infra) | Additive; categories are granular, not broad wildcard excludes |
| `invariants.yml` | Behavioral invariants (identity, endpoints, telemetry, protected changes) that must hold regardless of upstream sync | Additive; removing/weakening an invariant requires explicit review |
| `ledger.jsonl` | Append-only, one-JSON-object-per-line audit trail of policy/state decisions | **Append-only.** CI rejects any commit that edits or removes an existing line |
| `assessments/` | Landing zone for immutable upstream-assessment artifacts produced out-of-band | Each artifact is a new file; existing artifacts are never edited |

## Validation

`scripts/seventwos/validate_seventwos.py` checks structural integrity of all
of the above (schema, cross-references, append-only-ness of the ledger). It is
run in CI by `.github/workflows/seventwos-policy-validate.yml` and can be run
locally:

```sh
python3 -m unittest scripts/seventwos/validate_seventwos_test.py -v
python3 scripts/seventwos/validate_seventwos.py --base-ref origin/develop
```

## Explicit non-goals (this change)

* No automatic merge/sync logic of any kind.
* No broad path-only exclusions (e.g. "never touch `app/**`") — divergence is
  tracked at the identifier/behavior level so legitimate upstream fixes are
  not blanket-blocked.
* No changes to Graphify workflows.
* No access to or assumptions about the `enterprise/` submodule, which is a
  private, unpopulated git submodule in this checkout — its contents are out
  of scope and not read by this tooling.
* `.github/workflows/seventwos-upstream-assessment.yml` only accepts and
  archives immutable assessment artifacts; it does not evaluate, apply, or
  open sync PRs.
