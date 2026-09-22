#!/usr/bin/env python3
"""Structural + anti-tamper validator for the .seventwos upstream policy system.

Validates:
  * policy.yml / state.yml / path-map.yml / invariants.yml have the required
    top-level shape and required fields on each entry.
  * state.yml's identity fields (fork owner, upstream repo, tracked branches)
    match the hardcoded expected identities in this script, and its SHAs are
    well-formed 40-hex-character git object ids.
  * (opt-in, `--verify-git-identity`) those SHAs exist as real commit objects
    reachable from this checkout, the recorded merge-base is recomputed and
    must match exactly, and the local `origin` remote matches the expected
    fork owner/repo.
  * (when `--base-ref` is given) state.yml's `seed:` block is byte-identical
    to its content at the base ref (immutable seed), ledger.jsonl is
    append-only, and invariants.yml/policy.yml/path-map.yml cannot have
    existing entries silently removed or weakened without a matching,
    well-formed ledger.jsonl justification entry added in the same change.
  * both seventwos-owned GitHub Actions workflows are structurally hardened:
    read-only permissions, every `uses:` pinned to a full commit SHA,
    `persist-credentials: false` on every checkout step, no submodule
    checkout, and no `secrets.*` references anywhere in the file.

All base-ref-relative checks are fail-closed: if the base ref itself cannot
be resolved, or `git show <base>:<path>` fails for a reason other than
"this path did not exist at that ref", the check reports an error rather
than silently skipping. A path is only treated as "first introduction" (no
prior content to protect) when the base ref resolves cleanly and the path
is conclusively absent from it.

This is a structural/consistency + anti-tamper check, not a semantic one:
it does not evaluate upstream commits or apply any policy, and none of its
"protection" logic auto-approves anything - a human reviewer still gates
every pull request; this only requires that an authorized change also
carry a machine-checkable audit trail.

Usage:
  python3 scripts/seventwos/validate_seventwos.py \
      [--root <.seventwos path>] [--repo-root <repo root>] \
      [--base-ref <git ref or sha>] [--verify-git-identity] \
      [--workflows-root <.github/workflows path>]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only when PyYAML missing
    yaml = None

# --- Hardcoded expected identities -----------------------------------------
# These are intentionally NOT read from state.yml: state.yml is the thing
# being checked against them. Changing what this fork/upstream relationship
# *is* requires changing this script (and therefore going through normal
# code review), not just editing YAML.
EXPECTED_FORK_OWNER = "seventwos-app"
EXPECTED_OUR_BRANCH = "develop"
EXPECTED_UPSTREAM_REPO = "element-hq/element-x-android"
EXPECTED_UPSTREAM_BRANCH = "develop"

SHA_RE = re.compile(r"^[0-9a-f]{40}$")

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

# Compatibility-sensitive identifier coverage that must be present in
# path-map.yml's compatibility_sensitive_identifier category: Kotlin *and*
# Java package roots, plus Gradle build files, since `io.element` shows up
# as a content-level Gradle groupId/plugin id (e.g. `id("io.element.android-
# compose-application")`, `groupId = "io.element.android"`), not just as a
# directory path segment.
REQUIRED_COMPAT_IDENTIFIER_PATTERNS = {
    "**/src/*/kotlin/io/element/**",
    "**/src/*/java/io/element/**",
    "**/*.gradle.kts",
    "**/*.gradle",
}

# change_type values used to justify a protected removal/weakening via a
# ledger.jsonl entry. Each must be paired with non-empty target_ids and a
# non-empty rationale on the justifying entry.
CHANGE_TYPE_INVARIANTS = "invariant_change"
CHANGE_TYPE_POLICY = "policy_change"
CHANGE_TYPE_PATH_MAP = "path_map_change"

ABSENT_PATH_MARKERS = (
    "does not exist in",
    "exists on disk, but not in",
    "no such path",
)

WORKFLOW_FILENAMES = (
    "seventwos-policy-validate.yml",
    "seventwos-upstream-assessment.yml",
)

FULL_SHA_USES_RE = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")


class ValidationError(Exception):
    pass


# --- generic helpers ---------------------------------------------------------

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


def _run_git(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo_root, capture_output=True, text=True, check=False
    )


def _resolve_ref(repo_root: Path, ref: str) -> tuple[bool, str]:
    """Resolve `ref` to a commit sha. Returns (ok, sha_or_error_message)."""
    proc = _run_git(repo_root, ["rev-parse", "--verify", f"{ref}^{{commit}}"])
    if proc.returncode == 0:
        return True, proc.stdout.strip()
    return False, (proc.stderr or proc.stdout).strip()


def _git_show_path_at_ref(
    repo_root: Path, ref_sha: str, rel_path: str
) -> tuple[str, Optional[str], Optional[str]]:
    """Fail-closed lookup of `rel_path` at `ref_sha`.

    Returns a (status, content, error) triple where status is one of:
      "found"  - content holds the file's text at that ref
      "absent" - the ref resolved fine but conclusively has no such path
      "error"  - the lookup could not be trusted; content is None and the
                 caller must treat this as a validation failure, not a skip
    """
    proc = _run_git(repo_root, ["show", f"{ref_sha}:{rel_path}"])
    if proc.returncode == 0:
        return "found", proc.stdout, None
    stderr = (proc.stderr or proc.stdout).strip()
    if any(marker in stderr for marker in ABSENT_PATH_MARKERS):
        return "absent", None, stderr
    return "error", None, stderr


# --- policy.yml ---------------------------------------------------------------

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


# --- state.yml ------------------------------------------------------------

def validate_state(root: Path, errors: list[str]) -> None:
    """Structural + identity + SHA-format checks (no git object access)."""
    path = root / "state.yml"
    if not path.exists():
        errors.append(f"missing required file: {path}")
        return
    data = _load_yaml(path)
    missing = REQUIRED_STATE_KEYS - data.keys()
    if missing:
        errors.append(f"state.yml: missing top-level keys: {sorted(missing)}")
        return
    seed = data.get("seed") or {}
    missing_seed = REQUIRED_SEED_KEYS - seed.keys()
    if missing_seed:
        errors.append(f"state.yml: seed missing required keys: {sorted(missing_seed)}")

    fork = seed.get("fork") or {}
    upstream = seed.get("upstream") or {}
    our_branch = seed.get("our_branch_at_seed") or {}
    merge_base = seed.get("merge_base") or {}

    # Hardcoded expected identity checks: these fields cannot be silently
    # changed to point this policy system at a different fork/upstream
    # relationship without also changing this script.
    if fork.get("origin_owner") != EXPECTED_FORK_OWNER:
        errors.append(
            f"state.yml: seed.fork.origin_owner {fork.get('origin_owner')!r} does not match "
            f"expected {EXPECTED_FORK_OWNER!r}"
        )
    if fork.get("github_reported_parent") != EXPECTED_UPSTREAM_REPO:
        errors.append(
            "state.yml: seed.fork.github_reported_parent "
            f"{fork.get('github_reported_parent')!r} does not match expected "
            f"{EXPECTED_UPSTREAM_REPO!r}"
        )
    if our_branch.get("branch") != EXPECTED_OUR_BRANCH:
        errors.append(
            f"state.yml: seed.our_branch_at_seed.branch {our_branch.get('branch')!r} does not "
            f"match expected {EXPECTED_OUR_BRANCH!r}"
        )
    if upstream.get("repo") != EXPECTED_UPSTREAM_REPO:
        errors.append(
            f"state.yml: seed.upstream.repo {upstream.get('repo')!r} does not match expected "
            f"{EXPECTED_UPSTREAM_REPO!r}"
        )
    if upstream.get("tracked_branch") != EXPECTED_UPSTREAM_BRANCH:
        errors.append(
            "state.yml: seed.upstream.tracked_branch "
            f"{upstream.get('tracked_branch')!r} does not match expected "
            f"{EXPECTED_UPSTREAM_BRANCH!r}"
        )

    # SHA format verification: full 40-hex-character git object ids only,
    # never abbreviated shas or branch names.
    sha_fields = {
        "seed.merge_base.sha": merge_base.get("sha"),
        "seed.upstream.head_sha_at_seed": upstream.get("head_sha_at_seed"),
        "seed.our_branch_at_seed.head_sha_at_seed": our_branch.get("head_sha_at_seed"),
    }
    for field_name, value in sha_fields.items():
        if not value or not SHA_RE.match(str(value)):
            errors.append(
                f"state.yml: {field_name} = {value!r} is not a full 40-hex-character git SHA"
            )


def validate_state_git_identity(root: Path, repo_root: Path, errors: list[str]) -> None:
    """Opt-in, network/object-dependent verification of state.yml's seed.

    Verifies (fail-closed): the recorded SHAs exist as real commit objects
    reachable from this checkout, the recorded merge-base recomputes to the
    same value, and the local `origin` remote matches the expected fork
    owner. Callers must have already fetched the objects these SHAs refer
    to (e.g. by fetching the upstream remote) or this will correctly fail.
    """
    path = root / "state.yml"
    if not path.exists():
        return  # already reported by validate_state
    data = _load_yaml(path)
    seed = data.get("seed") or {}
    merge_base_sha = (seed.get("merge_base") or {}).get("sha")
    upstream_sha = (seed.get("upstream") or {}).get("head_sha_at_seed")
    our_sha = (seed.get("our_branch_at_seed") or {}).get("head_sha_at_seed")

    if not (merge_base_sha and upstream_sha and our_sha):
        errors.append(
            "state.yml: cannot perform git identity verification because one or more seed "
            "SHAs is missing (see prior format errors)"
        )
        return

    for label, sha in (
        ("merge_base.sha", merge_base_sha),
        ("upstream.head_sha_at_seed", upstream_sha),
        ("our_branch_at_seed.head_sha_at_seed", our_sha),
    ):
        proc = _run_git(repo_root, ["cat-file", "-e", f"{sha}^{{commit}}"])
        if proc.returncode != 0:
            errors.append(
                f"state.yml: seed.{label} = {sha} is not a commit object reachable from this "
                "checkout (fetch it before validating; fail-closed, not skipped)"
            )

    # Recompute the merge-base and require an exact match, but only if both
    # endpoints resolved above; otherwise this would just produce a
    # confusing secondary error.
    mb_proc = _run_git(repo_root, ["merge-base", our_sha, upstream_sha])
    if mb_proc.returncode != 0:
        errors.append(
            "state.yml: could not recompute merge-base between "
            f"{our_sha} and {upstream_sha}: {(mb_proc.stderr or mb_proc.stdout).strip()}"
        )
    else:
        recomputed = mb_proc.stdout.strip()
        if recomputed != merge_base_sha:
            errors.append(
                f"state.yml: recorded merge_base.sha ({merge_base_sha}) does not match the "
                f"recomputed merge-base ({recomputed}) of the recorded upstream/our SHAs"
            )

    remote_proc = _run_git(repo_root, ["remote", "get-url", "origin"])
    if remote_proc.returncode != 0:
        errors.append("state.yml: could not read the local 'origin' remote URL for verification")
    else:
        origin_url = remote_proc.stdout.strip().lower()
        if EXPECTED_FORK_OWNER.lower() not in origin_url:
            errors.append(
                f"state.yml: local 'origin' remote ({origin_url}) does not reference the "
                f"expected fork owner {EXPECTED_FORK_OWNER!r}"
            )


def validate_state_immutability(
    root: Path, repo_root: Path, errors: list[str], base_ref: Optional[str]
) -> None:
    """The `seed:` block of state.yml must be byte-identical to base_ref.

    Fail-closed: an unresolvable base_ref, or any git-show error other than
    a conclusive "path absent at base", is reported as an error. A path is
    only allowed to be introduced fresh when the base ref resolves cleanly
    and the file conclusively did not exist there.
    """
    if not base_ref:
        return
    ok, resolved = _resolve_ref(repo_root, base_ref)
    if not ok:
        errors.append(
            f"state.yml: cannot resolve base ref {base_ref!r} to verify seed immutability "
            f"(fail-closed): {resolved}"
        )
        return

    status, base_text, err = _git_show_path_at_ref(repo_root, resolved, ".seventwos/state.yml")
    if status == "error":
        errors.append(
            f"state.yml: git-show failed unexpectedly against base {resolved} (fail-closed, "
            f"not treated as first introduction): {err}"
        )
        return
    if status == "absent":
        return  # first introduction of state.yml: nothing to protect yet

    current_path = root / "state.yml"
    if not current_path.exists():
        return  # reported elsewhere
    current_text = current_path.read_text(encoding="utf-8")

    def _seed_block(text: str) -> Optional[str]:
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if line.rstrip() == "seed:":
                return "\n".join(lines[i:])
        return None

    base_seed_block = _seed_block(base_text or "")
    current_seed_block = _seed_block(current_text)
    if base_seed_block is None:
        errors.append(f"state.yml: base version at {resolved} has no 'seed:' block to compare")
        return
    if current_seed_block is None:
        errors.append("state.yml: current version has no 'seed:' block")
        return
    if base_seed_block != current_seed_block:
        errors.append(
            "state.yml: the immutable 'seed:' block differs from its content at base ref "
            f"{resolved}; the seed must never be edited in place (append a ledger.jsonl entry "
            "and record a superseded_by pointer instead)"
        )


# --- path-map.yml ---------------------------------------------------------

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

    compat = categories.get("compatibility_sensitive_identifier") or {}
    compat_paths = set(compat.get("paths") or [])
    missing_compat = REQUIRED_COMPAT_IDENTIFIER_PATTERNS - compat_paths
    if missing_compat:
        errors.append(
            "path-map.yml: category 'compatibility_sensitive_identifier' is missing required "
            f"Java/Gradle content-level coverage patterns: {sorted(missing_compat)}"
        )


# --- invariants.yml --------------------------------------------------------

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


# --- ledger.jsonl -----------------------------------------------------------

def _read_ledger_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.strip()]


def _ledger_entries_from_text(text: str) -> list[dict]:
    entries = []
    for line in _read_ledger_lines(text):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            entries.append(obj)
    return entries


def validate_ledger(
    root: Path, errors: list[str], repo_root: Path, base_ref: Optional[str]
) -> None:
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
        # Entries that claim to justify a protected removal/weakening must
        # themselves be well-formed: a real target and a real rationale,
        # not just a bare change_type.
        if "change_type" in obj:
            target_ids = obj.get("target_ids")
            rationale = obj.get("rationale")
            if not isinstance(target_ids, list) or not target_ids:
                errors.append(
                    f"ledger.jsonl:{i}: entry with change_type={obj.get('change_type')!r} must "
                    "have a non-empty 'target_ids' list"
                )
            if not isinstance(rationale, str) or not rationale.strip():
                errors.append(
                    f"ledger.jsonl:{i}: entry with change_type={obj.get('change_type')!r} must "
                    "have a non-empty 'rationale' string"
                )

    if not base_ref:
        return

    ok, resolved = _resolve_ref(repo_root, base_ref)
    if not ok:
        errors.append(
            f"ledger.jsonl: cannot resolve base ref {base_ref!r} to verify append-only-ness "
            f"(fail-closed): {resolved}"
        )
        return

    status, base_text, err = _git_show_path_at_ref(repo_root, resolved, ".seventwos/ledger.jsonl")
    if status == "error":
        errors.append(
            f"ledger.jsonl: git-show failed unexpectedly against base {resolved} (fail-closed, "
            f"not treated as first introduction): {err}"
        )
        return
    if status == "absent":
        return  # first introduction: nothing to compare

    base_lines = _read_ledger_lines(base_text or "")
    if base_lines != current_lines[: len(base_lines)]:
        errors.append(
            "ledger.jsonl: existing lines were edited or removed relative to "
            f"{resolved}; the ledger must be append-only"
        )
    elif len(current_lines) < len(base_lines):
        errors.append(f"ledger.jsonl: has fewer lines than {resolved}; entries were removed")


def _new_ledger_entries(
    root: Path, repo_root: Path, base_ref: str
) -> tuple[Optional[list[dict]], Optional[str]]:
    """Entries present now but not (by id) at base_ref. Fail-closed on error."""
    current_path = root / "ledger.jsonl"
    current_text = current_path.read_text(encoding="utf-8") if current_path.exists() else ""
    current_entries = _ledger_entries_from_text(current_text)

    ok, resolved = _resolve_ref(repo_root, base_ref)
    if not ok:
        return None, f"cannot resolve base ref {base_ref!r}: {resolved}"

    status, base_text, err = _git_show_path_at_ref(repo_root, resolved, ".seventwos/ledger.jsonl")
    if status == "error":
        return None, f"git-show failed unexpectedly against base {resolved}: {err}"
    base_ids = set()
    if status == "found":
        base_ids = {e.get("id") for e in _ledger_entries_from_text(base_text or "")}
    return [e for e in current_entries if e.get("id") not in base_ids], None


def _is_justified(
    new_entries: list[dict], change_type: str, target_id: object
) -> bool:
    return any(
        e.get("change_type") == change_type
        and target_id in (e.get("target_ids") or [])
        and isinstance(e.get("rationale"), str)
        and e.get("rationale").strip()
        for e in new_entries
    )


# --- anti-weakening protection for invariants.yml / policy.yml -------------

def _protect_id_list(
    root: Path,
    repo_root: Path,
    errors: list[str],
    base_ref: str,
    filename: str,
    list_key: str,
    protect_fields: list[str],
    change_type: str,
    new_ledger_entries: list[dict],
) -> None:
    path = root / filename
    if not path.exists():
        return  # reported elsewhere
    try:
        current_data = _load_yaml(path)
    except ValidationError:
        return
    current_items = current_data.get(list_key)
    if not isinstance(current_items, list):
        return  # structural error reported elsewhere
    current_by_id = {i.get("id"): i for i in current_items if isinstance(i, dict)}

    ok, resolved = _resolve_ref(repo_root, base_ref)
    if not ok:
        errors.append(
            f"{filename}: cannot resolve base ref {base_ref!r} to verify anti-weakening "
            f"protection (fail-closed): {resolved}"
        )
        return

    status, base_text, err = _git_show_path_at_ref(repo_root, resolved, f".seventwos/{filename}")
    if status == "error":
        errors.append(
            f"{filename}: git-show failed unexpectedly against base {resolved} (fail-closed, "
            f"not treated as first introduction): {err}"
        )
        return
    if status == "absent":
        return  # first introduction: nothing to protect yet

    try:
        base_data = yaml.safe_load(base_text or "") or {}
    except yaml.YAMLError as exc:
        errors.append(
            f"{filename}: base version at {resolved} is not valid YAML, cannot verify "
            f"anti-weakening protection (fail-closed): {exc}"
        )
        return
    base_items = base_data.get(list_key) or []
    base_by_id = {i.get("id"): i for i in base_items if isinstance(i, dict)}

    for bid, bitem in base_by_id.items():
        if bid not in current_by_id:
            if not _is_justified(new_ledger_entries, change_type, bid):
                errors.append(
                    f"{filename}: entry '{bid}' was removed without a justifying ledger.jsonl "
                    f"entry (need change_type={change_type!r}, target_ids containing '{bid}', "
                    "and a non-empty rationale)"
                )
            continue
        citem = current_by_id[bid]
        for field in protect_fields:
            if bitem.get(field) != citem.get(field):
                if not _is_justified(new_ledger_entries, change_type, bid):
                    errors.append(
                        f"{filename}: entry '{bid}' field '{field}' was changed without a "
                        f"justifying ledger.jsonl entry (need change_type={change_type!r}, "
                        f"target_ids containing '{bid}', and a non-empty rationale)"
                    )


def _protect_path_map(
    root: Path,
    repo_root: Path,
    errors: list[str],
    base_ref: str,
    new_ledger_entries: list[dict],
) -> None:
    filename = "path-map.yml"
    path = root / filename
    if not path.exists():
        return
    try:
        current_data = _load_yaml(path)
    except ValidationError:
        return
    current_categories = current_data.get("categories") or {}

    ok, resolved = _resolve_ref(repo_root, base_ref)
    if not ok:
        errors.append(
            f"{filename}: cannot resolve base ref {base_ref!r} to verify anti-weakening "
            f"protection (fail-closed): {resolved}"
        )
        return

    status, base_text, err = _git_show_path_at_ref(repo_root, resolved, f".seventwos/{filename}")
    if status == "error":
        errors.append(
            f"{filename}: git-show failed unexpectedly against base {resolved} (fail-closed, "
            f"not treated as first introduction): {err}"
        )
        return
    if status == "absent":
        return

    try:
        base_data = yaml.safe_load(base_text or "") or {}
    except yaml.YAMLError as exc:
        errors.append(
            f"{filename}: base version at {resolved} is not valid YAML, cannot verify "
            f"anti-weakening protection (fail-closed): {exc}"
        )
        return
    base_categories = base_data.get("categories") or {}

    for name, bbody in base_categories.items():
        if not isinstance(bbody, dict):
            continue
        justified = _is_justified(new_ledger_entries, CHANGE_TYPE_PATH_MAP, name)
        if name not in current_categories:
            if not justified:
                errors.append(
                    f"{filename}: category '{name}' was removed without a justifying "
                    f"ledger.jsonl entry (need change_type={CHANGE_TYPE_PATH_MAP!r}, target_ids "
                    f"containing '{name}', and a non-empty rationale)"
                )
            continue
        cbody = current_categories.get(name) or {}
        if bbody.get("description") != cbody.get("description") and not justified:
            errors.append(
                f"{filename}: category '{name}' description changed without a justifying "
                "ledger.jsonl entry"
            )
        base_paths = set(bbody.get("paths") or [])
        current_paths = set(cbody.get("paths") or [])
        shrunk = base_paths - current_paths
        if shrunk and not justified:
            errors.append(
                f"{filename}: category '{name}' lost path pattern(s) {sorted(shrunk)} without "
                "a justifying ledger.jsonl entry (adding coverage is unrestricted; narrowing it "
                "is a weakening and must be justified)"
            )


def validate_semantic_protection(
    root: Path, repo_root: Path, errors: list[str], base_ref: Optional[str]
) -> None:
    if not base_ref:
        return
    new_entries, err = _new_ledger_entries(root, repo_root, base_ref)
    if new_entries is None:
        errors.append(f"ledger.jsonl: {err} (fail-closed: cannot verify change justifications)")
        return

    _protect_id_list(
        root, repo_root, errors, base_ref, "invariants.yml", "invariants",
        ["statement", "evidence", "category"], CHANGE_TYPE_INVARIANTS, new_entries,
    )
    _protect_id_list(
        root, repo_root, errors, base_ref, "policy.yml", "principles",
        ["statement"], CHANGE_TYPE_POLICY, new_entries,
    )
    _protect_path_map(root, repo_root, errors, base_ref, new_entries)


# --- workflow hardening ------------------------------------------------------

def _iter_uses_and_with(doc: dict):
    """Yield (uses_value, with_dict) for every step in every job."""
    jobs = doc.get("jobs") or {}
    if not isinstance(jobs, dict):
        return
    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps") or []:
            if not isinstance(step, dict):
                continue
            uses = step.get("uses")
            if uses:
                yield uses, (step.get("with") or {})


def _iter_permission_maps(doc: dict):
    perms = doc.get("permissions")
    if perms is not None:
        yield "top-level", perms
    jobs = doc.get("jobs") or {}
    if isinstance(jobs, dict):
        for job_name, job in jobs.items():
            if isinstance(job, dict) and job.get("permissions") is not None:
                yield f"job '{job_name}'", job["permissions"]


def validate_workflow_hardening(workflows_root: Path, errors: list[str]) -> None:
    for filename in WORKFLOW_FILENAMES:
        path = workflows_root / filename
        if not path.exists():
            errors.append(f"missing required workflow: {path}")
            continue
        raw_text = path.read_text(encoding="utf-8")
        try:
            doc = yaml.safe_load(raw_text)
        except yaml.YAMLError as exc:
            errors.append(f"{filename}: invalid YAML: {exc}")
            continue
        if not isinstance(doc, dict):
            errors.append(f"{filename}: expected a YAML mapping at the top level")
            continue

        # Read-only permissions everywhere: no "write" scope anywhere,
        # top-level or per-job, and no bare 'write-all' strings.
        for location, perms in _iter_permission_maps(doc):
            if isinstance(perms, str):
                if perms not in ("read-all", "none"):
                    errors.append(
                        f"{filename}: {location} permissions is the string {perms!r}; must be "
                        "a restricted mapping, 'read-all', or 'none'"
                    )
                continue
            if not isinstance(perms, dict):
                errors.append(f"{filename}: {location} permissions has an unexpected type")
                continue
            for scope, level in perms.items():
                if str(level).lower() == "write":
                    errors.append(
                        f"{filename}: {location} grants write permission for '{scope}'; these "
                        "workflows must remain read-only/report-only"
                    )

        # Every `uses:` must be pinned to a full 40-hex-character commit SHA.
        for uses, step_with in _iter_uses_and_with(doc):
            if not FULL_SHA_USES_RE.match(uses):
                errors.append(
                    f"{filename}: step uses '{uses}' is not pinned to a full commit SHA "
                    "(expected 'owner/action@<40-hex-sha>')"
                )
            if uses.split("@", 1)[0].endswith("actions/checkout"):
                if step_with.get("persist-credentials") is not False:
                    errors.append(
                        f"{filename}: actions/checkout step must set "
                        "'with.persist-credentials: false'"
                    )
                submodules = step_with.get("submodules")
                if submodules not in (None, False, "false"):
                    errors.append(
                        f"{filename}: actions/checkout step must not check out submodules "
                        f"(found submodules: {submodules!r})"
                    )

        if "secrets." in raw_text:
            errors.append(
                f"{filename}: references 'secrets.' but these workflows must not access any "
                "secret (no private-secret access)"
            )


# --- entrypoint --------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_seventwos_root = Path(__file__).resolve().parents[2] / ".seventwos"
    parser.add_argument(
        "--root",
        default=str(default_seventwos_root),
        help="Path to the .seventwos directory (default: repo-relative .seventwos)",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Path to the repository root (default: parent of --root)",
    )
    parser.add_argument(
        "--workflows-root",
        default=None,
        help="Path to .github/workflows (default: <repo-root>/.github/workflows)",
    )
    parser.add_argument(
        "--base-ref",
        default=None,
        help=(
            "Exact base git ref/sha to diff the immutable seed, ledger, and "
            "invariants/policy/path-map protection against. Should be an exact "
            "event base sha (pull_request.base.sha / push 'before' / "
            "merge_group.base_sha), not a moving branch name."
        ),
    )
    parser.add_argument(
        "--verify-git-identity",
        action="store_true",
        help=(
            "Also verify state.yml's SHAs exist as real commit objects, recompute the "
            "merge-base, and check the local origin remote. Requires the relevant commit "
            "objects (e.g. from the upstream remote) to already be fetched; fails closed "
            "if they are not."
        ),
    )
    parser.add_argument(
        "--skip-workflow-hardening",
        action="store_true",
        help="Skip the .github/workflows hardening checks (for isolated unit tests).",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else root.parent
    workflows_root = (
        Path(args.workflows_root).resolve()
        if args.workflows_root
        else repo_root / ".github" / "workflows"
    )
    errors: list[str] = []

    if not root.exists():
        print(f"error: {root} does not exist", file=sys.stderr)
        return 2

    validate_policy(root, errors)
    validate_state(root, errors)
    validate_path_map(root, errors)
    validate_invariants(root, errors)
    validate_ledger(root, errors, repo_root, args.base_ref)
    validate_state_immutability(root, repo_root, errors, args.base_ref)
    validate_semantic_protection(root, repo_root, errors, args.base_ref)

    if args.verify_git_identity:
        validate_state_git_identity(root, repo_root, errors)

    if not args.skip_workflow_hardening:
        validate_workflow_hardening(workflows_root, errors)

    if errors:
        print(f"seventwos policy validation failed with {len(errors)} error(s):", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print("seventwos policy validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
