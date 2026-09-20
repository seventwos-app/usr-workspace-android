#!/usr/bin/env python3
"""Structural validator for the .seventwos upstream policy system.

Validates:
  * policy.yml / state.yml / path-map.yml / invariants.yml have the required
    top-level shape and required fields on each entry.
  * ledger.jsonl is valid JSON-lines, each object has the required fields,
    and (when --base-ref is given) is append-only relative to that ref: no
    existing line may be edited or removed, only new lines added.

This is a structural/consistency check, not a semantic one: it does not
evaluate upstream commits or apply any policy. Exits non-zero and prints
one message per violation on failure.

Usage:
  python3 scripts/seventwos/validate_seventwos.py [--base-ref <git-ref>] [--root <path>]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only when PyYAML missing
    yaml = None

REQUIRED_STATE_KEYS = {"schema_version", "seed"}
REQUIRED_SEED_KEYS = {
    "recorded_at",
    "evidence",
    "fork",
    "upstream",
    "our_branch_at_seed",
    "merge_base",
}
REQUIRED_PATH_MAP_CATEGORY_KEYS = {"description"}
REQUIRED_INVARIANT_KEYS = {"id", "category", "statement", "evidence"}
REQUIRED_LEDGER_KEYS = {"id", "timestamp", "type", "actor", "summary"}
REQUIRED_POLICY_KEYS = {"schema_version", "principles", "process"}


class ValidationError(Exception):
    pass


def _load_yaml(path: Path) -> dict:
    if yaml is None:
        raise ValidationError(
            f"PyYAML is required to validate {path.name} but is not installed"
        )
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValidationError(f"{path.name}: expected a YAML mapping at the top level")
    return data


def validate_policy(root: Path, errors: list[str]) -> None:
    path = root / "policy.yml"
    if not path.exists():
        errors.append(f"missing required file: {path}")
        return
    data = _load_yaml(path)
    missing = REQUIRED_POLICY_KEYS - data.keys()
    if missing:
        errors.append(f"policy.yml: missing top-level keys: {sorted(missing)}")
    for principle in data.get("principles", []):
        if "id" not in principle or "statement" not in principle:
            errors.append(f"policy.yml: principle missing id/statement: {principle}")


def validate_state(root: Path, errors: list[str]) -> None:
    path = root / "state.yml"
    if not path.exists():
        errors.append(f"missing required file: {path}")
        return
    data = _load_yaml(path)
    missing = REQUIRED_STATE_KEYS - data.keys()
    if missing:
        errors.append(f"state.yml: missing top-level keys: {sorted(missing)}")
        return
    seed = data.get("seed", {})
    missing_seed = REQUIRED_SEED_KEYS - seed.keys()
    if missing_seed:
        errors.append(f"state.yml: seed missing required keys: {sorted(missing_seed)}")
    merge_base = seed.get("merge_base") or {}
    if "sha" not in merge_base:
        errors.append("state.yml: seed.merge_base.sha is required")


def validate_path_map(root: Path, errors: list[str]) -> None:
    path = root / "path-map.yml"
    if not path.exists():
        errors.append(f"missing required file: {path}")
        return
    data = _load_yaml(path)
    categories = data.get("categories")
    if not isinstance(categories, dict) or not categories:
        errors.append("path-map.yml: 'categories' must be a non-empty mapping")
        return
    for name, body in categories.items():
        if not isinstance(body, dict):
            errors.append(f"path-map.yml: category '{name}' must be a mapping")
            continue
        missing = REQUIRED_PATH_MAP_CATEGORY_KEYS - body.keys()
        if missing:
            errors.append(f"path-map.yml: category '{name}' missing keys: {sorted(missing)}")
        paths = body.get("paths")
        if paths is not None and (not isinstance(paths, list) or not paths):
            errors.append(f"path-map.yml: category '{name}' has an empty/invalid 'paths' list")
        # Guard against accidental broad path-only excludes such as a bare
        # "**" or "*" pattern, which this system is explicitly designed to
        # avoid in favour of granular identifier-level tracking.
        for p in paths or []:
            if p.strip() in {"**", "*", "."}:
                errors.append(
                    f"path-map.yml: category '{name}' contains an overly broad pattern '{p}'"
                )


def validate_invariants(root: Path, errors: list[str]) -> None:
    path = root / "invariants.yml"
    if not path.exists():
        errors.append(f"missing required file: {path}")
        return
    data = _load_yaml(path)
    invariants = data.get("invariants")
    if not isinstance(invariants, list) or not invariants:
        errors.append("invariants.yml: 'invariants' must be a non-empty list")
        return
    seen_ids = set()
    for inv in invariants:
        if not isinstance(inv, dict):
            errors.append(f"invariants.yml: entry is not a mapping: {inv}")
            continue
        missing = REQUIRED_INVARIANT_KEYS - inv.keys()
        if missing:
            errors.append(f"invariants.yml: entry {inv.get('id', '?')} missing keys: {sorted(missing)}")
        inv_id = inv.get("id")
        if inv_id in seen_ids:
            errors.append(f"invariants.yml: duplicate invariant id '{inv_id}'")
        seen_ids.add(inv_id)


def _read_ledger_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.strip()]


def validate_ledger(root: Path, errors: list[str], base_ref: str | None) -> None:
    path = root / "ledger.jsonl"
    if not path.exists():
        errors.append(f"missing required file: {path}")
        return
    current_text = path.read_text(encoding="utf-8")
    current_lines = _read_ledger_lines(current_text)
    if not current_lines:
        errors.append("ledger.jsonl: must contain at least one entry")
        return

    seen_ids = set()
    for i, line in enumerate(current_lines, start=1):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"ledger.jsonl:{i}: invalid JSON ({exc})")
            continue
        if not isinstance(obj, dict):
            errors.append(f"ledger.jsonl:{i}: entry must be a JSON object")
            continue
        missing = REQUIRED_LEDGER_KEYS - obj.keys()
        if missing:
            errors.append(f"ledger.jsonl:{i}: missing keys: {sorted(missing)}")
        entry_id = obj.get("id")
        if entry_id in seen_ids:
            errors.append(f"ledger.jsonl:{i}: duplicate ledger id '{entry_id}'")
        seen_ids.add(entry_id)

    if base_ref:
        rel_path = path.relative_to(root.parent) if root.name == ".seventwos" else path
        try:
            base_text = subprocess.run(
                ["git", "show", f"{base_ref}:.seventwos/ledger.jsonl"],
                cwd=root.parent,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            errors.append("git executable not found; cannot check ledger append-only-ness")
            base_text = None
        if base_text is not None:
            if base_text.returncode != 0:
                # No ledger.jsonl at base_ref (e.g. this PR introduces it): nothing to compare.
                pass
            else:
                base_lines = _read_ledger_lines(base_text.stdout)
                if base_lines != current_lines[: len(base_lines)]:
                    errors.append(
                        "ledger.jsonl: existing lines were edited or removed relative to "
                        f"{base_ref}; the ledger must be append-only"
                    )
                elif len(current_lines) < len(base_lines):
                    errors.append(
                        f"ledger.jsonl: has fewer lines than {base_ref}; entries were removed"
                    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[2] / ".seventwos"),
        help="Path to the .seventwos directory (default: repo-relative .seventwos)",
    )
    parser.add_argument(
        "--base-ref",
        default=None,
        help="Git ref to diff ledger.jsonl against to enforce append-only-ness",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    errors: list[str] = []

    if not root.exists():
        print(f"error: {root} does not exist", file=sys.stderr)
        return 2

    validate_policy(root, errors)
    validate_state(root, errors)
    validate_path_map(root, errors)
    validate_invariants(root, errors)
    validate_ledger(root, errors, args.base_ref)

    if errors:
        print(f"seventwos policy validation failed with {len(errors)} error(s):", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print("seventwos policy validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
