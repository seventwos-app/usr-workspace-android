#!/usr/bin/env python3
"""Unit tests for scripts/seventwos/validate_seventwos.py.

Run with: python3 -m unittest scripts/seventwos/validate_seventwos_test.py -v
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import validate_seventwos as v  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
SEVENTWOS_ROOT = REPO_ROOT / ".seventwos"
WORKFLOWS_ROOT = REPO_ROOT / ".github" / "workflows"

VALID_SHA_A = "a" * 40
VALID_SHA_B = "b" * 40
VALID_SHA_C = "c" * 40

VALID_POLICY = """
schema_version: 1
principles:
  - id: P1
    statement: "example"
process:
  upstream_change_evaluation: []
"""

VALID_STATE = f"""
schema_version: 1
seed:
  recorded_at: "2026-09-20T00:00:00Z"
  evidence: "test"
  fork:
    origin_owner: "{v.EXPECTED_FORK_OWNER}"
    github_reported_parent: "{v.EXPECTED_UPSTREAM_REPO}"
  upstream:
    repo: "{v.EXPECTED_UPSTREAM_REPO}"
    tracked_branch: "{v.EXPECTED_UPSTREAM_BRANCH}"
    head_sha_at_seed: "{VALID_SHA_A}"
  our_branch_at_seed:
    branch: "{v.EXPECTED_OUR_BRANCH}"
    head_sha_at_seed: "{VALID_SHA_B}"
  merge_base:
    sha: "{VALID_SHA_C}"
"""

VALID_PATH_MAP = """
schema_version: 1
categories:
  branding:
    description: "test"
    paths:
      - "some/path/**"
  compatibility_sensitive_identifier:
    description: "test"
    paths:
      - "**/src/*/kotlin/io/element/**"
      - "**/src/*/java/io/element/**"
      - "**/*.gradle.kts"
      - "**/*.gradle"
"""

VALID_INVARIANTS = """
schema_version: 1
invariants:
  - id: INV-1
    category: identity
    statement: "test"
    evidence: "test"
"""


def _write(tmp: Path, name: str, content: str) -> None:
    (tmp / name).write_text(content, encoding="utf-8")


def _valid_ledger_entry(entry_id: str, **extra) -> dict:
    entry = {
        "id": entry_id,
        "timestamp": "2026-09-20T00:00:00Z",
        "type": "system_init",
        "actor": "test",
        "summary": "test entry",
    }
    entry.update(extra)
    return entry


def _valid_ledger_line(entry_id: str, **extra) -> str:
    return json.dumps(_valid_ledger_entry(entry_id, **extra))


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )


def _init_repo(repo: Path) -> None:
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "test")


def _commit_all(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


class TestRealFiles(unittest.TestCase):
    """Sanity-check the actual committed .seventwos files validate clean."""

    def test_real_directory_has_no_base_ref_violations(self):
        errors: list[str] = []
        v.validate_policy(SEVENTWOS_ROOT, errors)
        v.validate_state(SEVENTWOS_ROOT, errors)
        v.validate_path_map(SEVENTWOS_ROOT, errors)
        v.validate_invariants(SEVENTWOS_ROOT, errors)
        v.validate_ledger(SEVENTWOS_ROOT, errors, REPO_ROOT, None)
        self.assertEqual(errors, [])

    def test_main_on_real_directory_succeeds(self):
        rc = v.main(["--root", str(SEVENTWOS_ROOT)])
        self.assertEqual(rc, 0)

    def test_main_against_prior_commit_base_ref_succeeds(self):
        # The previously committed phase-1 baseline must still be a valid,
        # non-weakening ancestor of the current tree. Keep this test
        # hermetic: git identity verification is covered with synthetic
        # repositories below and remains mandatory in the production
        # workflow after it fetches the pinned upstream history.
        rc = v.main(
            [
                "--root",
                str(SEVENTWOS_ROOT),
                "--base-ref",
                "9439f8de737a49bc91561474d1c0085b2d4c744c",
            ]
        )
        self.assertEqual(rc, 0)

    def test_workflow_hardening_passes_on_real_workflows(self):
        errors: list[str] = []
        v.validate_workflow_hardening(WORKFLOWS_ROOT, errors)
        self.assertEqual(errors, [])


class TestPolicyValidation(unittest.TestCase):
    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as td:
            errors: list[str] = []
            v.validate_policy(Path(td), errors)
            self.assertTrue(any("missing required file" in e for e in errors))

    def test_missing_keys(self):
        with tempfile.TemporaryDirectory() as td:
            _write(Path(td), "policy.yml", "schema_version: 1\n")
            errors: list[str] = []
            v.validate_policy(Path(td), errors)
            self.assertTrue(any("missing top-level keys" in e for e in errors))

    def test_valid(self):
        with tempfile.TemporaryDirectory() as td:
            _write(Path(td), "policy.yml", VALID_POLICY)
            errors: list[str] = []
            v.validate_policy(Path(td), errors)
            self.assertEqual(errors, [])


class TestStateValidation(unittest.TestCase):
    def test_valid(self):
        with tempfile.TemporaryDirectory() as td:
            _write(Path(td), "state.yml", VALID_STATE)
            errors: list[str] = []
            v.validate_state(Path(td), errors)
            self.assertEqual(errors, [])

    def test_missing_merge_base_sha(self):
        with tempfile.TemporaryDirectory() as td:
            broken = VALID_STATE.replace(f'sha: "{VALID_SHA_C}"', "")
            _write(Path(td), "state.yml", broken)
            errors: list[str] = []
            v.validate_state(Path(td), errors)
            self.assertTrue(any("merge_base.sha" in e for e in errors))

    def test_rejects_abbreviated_sha(self):
        with tempfile.TemporaryDirectory() as td:
            broken = VALID_STATE.replace(VALID_SHA_C, VALID_SHA_C[:7])
            _write(Path(td), "state.yml", broken)
            errors: list[str] = []
            v.validate_state(Path(td), errors)
            self.assertTrue(any("not a full 40-hex-character git SHA" in e for e in errors))

    def test_rejects_non_hex_sha(self):
        with tempfile.TemporaryDirectory() as td:
            broken = VALID_STATE.replace(VALID_SHA_C, "g" * 40)
            _write(Path(td), "state.yml", broken)
            errors: list[str] = []
            v.validate_state(Path(td), errors)
            self.assertTrue(any("not a full 40-hex-character git SHA" in e for e in errors))

    def test_rejects_wrong_fork_owner(self):
        with tempfile.TemporaryDirectory() as td:
            broken = VALID_STATE.replace(
                f'origin_owner: "{v.EXPECTED_FORK_OWNER}"', 'origin_owner: "someone-else"'
            )
            _write(Path(td), "state.yml", broken)
            errors: list[str] = []
            v.validate_state(Path(td), errors)
            self.assertTrue(any("origin_owner" in e for e in errors))

    def test_rejects_wrong_upstream_repo(self):
        with tempfile.TemporaryDirectory() as td:
            broken = VALID_STATE.replace(
                f'repo: "{v.EXPECTED_UPSTREAM_REPO}"', 'repo: "someone/else"'
            )
            _write(Path(td), "state.yml", broken)
            errors: list[str] = []
            v.validate_state(Path(td), errors)
            self.assertTrue(any("seed.upstream.repo" in e for e in errors))

    def test_rejects_wrong_our_branch(self):
        with tempfile.TemporaryDirectory() as td:
            broken = VALID_STATE.replace(
                f'branch: "{v.EXPECTED_OUR_BRANCH}"', 'branch: "not-develop"'
            )
            _write(Path(td), "state.yml", broken)
            errors: list[str] = []
            v.validate_state(Path(td), errors)
            self.assertTrue(any("our_branch_at_seed.branch" in e for e in errors))


class TestStateGitIdentityVerification(unittest.TestCase):
    def _make_repo_with_state(self, tmp: Path) -> None:
        seventwos_dir = tmp / ".seventwos"
        seventwos_dir.mkdir()
        _write(seventwos_dir, "state.yml", VALID_STATE)

    def test_fails_closed_when_shas_are_not_real_objects(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _init_repo(tmp)
            self._make_repo_with_state(tmp)
            _commit_all(tmp, "init")
            errors: list[str] = []
            v.validate_state_git_identity(tmp / ".seventwos", tmp, errors)
            # None of VALID_SHA_A/B/C are real commit objects in this repo.
            self.assertTrue(any("not a commit object reachable" in e for e in errors))

    def test_passes_when_shas_are_real_and_merge_base_matches(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _init_repo(tmp)
            # Build a small real history: base -> ours, base -> upstream.
            (tmp / "f.txt").write_text("base\n")
            base_sha = _commit_all(tmp, "base")
            (tmp / "f.txt").write_text("ours\n")
            our_sha = _commit_all(tmp, "ours")
            _git(tmp, "checkout", "-q", base_sha)
            _git(tmp, "checkout", "-q", "-b", "upstream-branch")
            (tmp / "f.txt").write_text("upstream\n")
            upstream_sha = _commit_all(tmp, "upstream")
            _git(tmp, "checkout", "-q", "-B", "develop", our_sha)

            state_text = f"""
schema_version: 1
seed:
  recorded_at: "2026-09-20T00:00:00Z"
  evidence: "test"
  fork:
    origin_owner: "{v.EXPECTED_FORK_OWNER}"
    github_reported_parent: "{v.EXPECTED_UPSTREAM_REPO}"
  upstream:
    repo: "{v.EXPECTED_UPSTREAM_REPO}"
    tracked_branch: "{v.EXPECTED_UPSTREAM_BRANCH}"
    head_sha_at_seed: "{upstream_sha}"
  our_branch_at_seed:
    branch: "{v.EXPECTED_OUR_BRANCH}"
    head_sha_at_seed: "{our_sha}"
  merge_base:
    sha: "{base_sha}"
"""
            seventwos_dir = tmp / ".seventwos"
            seventwos_dir.mkdir()
            _write(seventwos_dir, "state.yml", state_text)
            _git(tmp, "remote", "add", "origin", f"https://github.com/{v.EXPECTED_FORK_OWNER}/repo.git")
            errors: list[str] = []
            v.validate_state_git_identity(seventwos_dir, tmp, errors)
            self.assertEqual(errors, [])

    def test_rejects_tampered_merge_base(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _init_repo(tmp)
            (tmp / "f.txt").write_text("base\n")
            base_sha = _commit_all(tmp, "base")
            (tmp / "f.txt").write_text("ours\n")
            our_sha = _commit_all(tmp, "ours")
            _git(tmp, "checkout", "-q", base_sha)
            _git(tmp, "checkout", "-q", "-b", "upstream-branch")
            (tmp / "f.txt").write_text("upstream\n")
            upstream_sha = _commit_all(tmp, "upstream")
            _git(tmp, "checkout", "-q", "-B", "develop", our_sha)

            # Claim our own "ours" commit is the merge-base: a real object,
            # but the wrong one, must be caught by recomputation.
            state_text = f"""
schema_version: 1
seed:
  recorded_at: "2026-09-20T00:00:00Z"
  evidence: "test"
  fork:
    origin_owner: "{v.EXPECTED_FORK_OWNER}"
    github_reported_parent: "{v.EXPECTED_UPSTREAM_REPO}"
  upstream:
    repo: "{v.EXPECTED_UPSTREAM_REPO}"
    tracked_branch: "{v.EXPECTED_UPSTREAM_BRANCH}"
    head_sha_at_seed: "{upstream_sha}"
  our_branch_at_seed:
    branch: "{v.EXPECTED_OUR_BRANCH}"
    head_sha_at_seed: "{our_sha}"
  merge_base:
    sha: "{our_sha}"
"""
            seventwos_dir = tmp / ".seventwos"
            seventwos_dir.mkdir()
            _write(seventwos_dir, "state.yml", state_text)
            errors: list[str] = []
            v.validate_state_git_identity(seventwos_dir, tmp, errors)
            self.assertTrue(any("does not match the recomputed merge-base" in e for e in errors))


class TestStateImmutability(unittest.TestCase):
    def test_first_introduction_allowed(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _init_repo(tmp)
            (tmp / "f.txt").write_text("x\n")
            base_sha = _commit_all(tmp, "unrelated base")
            seventwos_dir = tmp / ".seventwos"
            seventwos_dir.mkdir()
            _write(seventwos_dir, "state.yml", VALID_STATE)
            errors: list[str] = []
            v.validate_state_immutability(seventwos_dir, tmp, errors, base_sha)
            self.assertEqual(errors, [])

    def test_edited_seed_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _init_repo(tmp)
            seventwos_dir = tmp / ".seventwos"
            seventwos_dir.mkdir()
            _write(seventwos_dir, "state.yml", VALID_STATE)
            base_sha = _commit_all(tmp, "seed")
            _write(seventwos_dir, "state.yml", VALID_STATE.replace(VALID_SHA_C, VALID_SHA_B))
            errors: list[str] = []
            v.validate_state_immutability(seventwos_dir, tmp, errors, base_sha)
            self.assertTrue(any("must never be edited in place" in e for e in errors))

    def test_unchanged_seed_allowed(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _init_repo(tmp)
            seventwos_dir = tmp / ".seventwos"
            seventwos_dir.mkdir()
            _write(seventwos_dir, "state.yml", VALID_STATE)
            base_sha = _commit_all(tmp, "seed")
            # Unrelated later edit outside the seed block, seed untouched.
            errors: list[str] = []
            v.validate_state_immutability(seventwos_dir, tmp, errors, base_sha)
            self.assertEqual(errors, [])

    def test_fails_closed_on_unresolvable_base_ref(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _init_repo(tmp)
            (tmp / "f.txt").write_text("x\n")
            _commit_all(tmp, "base")
            seventwos_dir = tmp / ".seventwos"
            seventwos_dir.mkdir()
            _write(seventwos_dir, "state.yml", VALID_STATE)
            errors: list[str] = []
            v.validate_state_immutability(seventwos_dir, tmp, errors, "0" * 40)
            self.assertTrue(any("cannot resolve base ref" in e for e in errors))


class TestPathMapValidation(unittest.TestCase):
    def test_valid(self):
        with tempfile.TemporaryDirectory() as td:
            _write(Path(td), "path-map.yml", VALID_PATH_MAP)
            errors: list[str] = []
            v.validate_path_map(Path(td), errors)
            self.assertEqual(errors, [])

    def test_rejects_broad_wildcard(self):
        with tempfile.TemporaryDirectory() as td:
            broken = VALID_PATH_MAP.replace('"some/path/**"', '"**"')
            _write(Path(td), "path-map.yml", broken)
            errors: list[str] = []
            v.validate_path_map(Path(td), errors)
            self.assertTrue(any("overly broad pattern" in e for e in errors))

    def test_empty_categories(self):
        with tempfile.TemporaryDirectory() as td:
            _write(Path(td), "path-map.yml", "schema_version: 1\ncategories: {}\n")
            errors: list[str] = []
            v.validate_path_map(Path(td), errors)
            self.assertTrue(any("non-empty mapping" in e for e in errors))

    def test_missing_compat_identifier_patterns_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            broken = VALID_PATH_MAP.replace('      - "**/*.gradle"\n', "")
            _write(Path(td), "path-map.yml", broken)
            errors: list[str] = []
            v.validate_path_map(Path(td), errors)
            self.assertTrue(
                any("missing required Java/Gradle content-level coverage patterns" in e for e in errors)
            )

    def test_missing_java_root_pattern_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            broken = VALID_PATH_MAP.replace(
                '      - "**/src/*/java/io/element/**"\n', ""
            )
            _write(Path(td), "path-map.yml", broken)
            errors: list[str] = []
            v.validate_path_map(Path(td), errors)
            self.assertTrue(
                any("missing required Java/Gradle content-level coverage patterns" in e for e in errors)
            )


class TestInvariantsValidation(unittest.TestCase):
    def test_valid(self):
        with tempfile.TemporaryDirectory() as td:
            _write(Path(td), "invariants.yml", VALID_INVARIANTS)
            errors: list[str] = []
            v.validate_invariants(Path(td), errors)
            self.assertEqual(errors, [])

    def test_duplicate_id_detected(self):
        with tempfile.TemporaryDirectory() as td:
            doubled = VALID_INVARIANTS + """  - id: INV-1
    category: identity
    statement: "dup"
    evidence: "dup"
"""
            _write(Path(td), "invariants.yml", doubled)
            errors: list[str] = []
            v.validate_invariants(Path(td), errors)
            self.assertTrue(any("duplicate invariant id" in e for e in errors))

    def test_missing_required_key(self):
        with tempfile.TemporaryDirectory() as td:
            broken = """
schema_version: 1
invariants:
  - id: INV-1
    category: identity
    statement: "test"
"""
            _write(Path(td), "invariants.yml", broken)
            errors: list[str] = []
            v.validate_invariants(Path(td), errors)
            self.assertTrue(any("missing keys" in e for e in errors))


class TestLedgerValidation(unittest.TestCase):
    def test_valid_ledger(self):
        with tempfile.TemporaryDirectory() as td:
            _write(Path(td), "ledger.jsonl", _valid_ledger_line("L1") + "\n")
            errors: list[str] = []
            v.validate_ledger(Path(td), errors, REPO_ROOT, None)
            self.assertEqual(errors, [])

    def test_invalid_json_line(self):
        with tempfile.TemporaryDirectory() as td:
            _write(Path(td), "ledger.jsonl", "{not valid json}\n")
            errors: list[str] = []
            v.validate_ledger(Path(td), errors, REPO_ROOT, None)
            self.assertTrue(any("invalid JSON" in e for e in errors))

    def test_empty_ledger_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            _write(Path(td), "ledger.jsonl", "\n")
            errors: list[str] = []
            v.validate_ledger(Path(td), errors, REPO_ROOT, None)
            self.assertTrue(any("at least one entry" in e for e in errors))

    def test_duplicate_ledger_id(self):
        with tempfile.TemporaryDirectory() as td:
            content = _valid_ledger_line("L1") + "\n" + _valid_ledger_line("L1") + "\n"
            _write(Path(td), "ledger.jsonl", content)
            errors: list[str] = []
            v.validate_ledger(Path(td), errors, REPO_ROOT, None)
            self.assertTrue(any("duplicate ledger id" in e for e in errors))

    def test_change_type_entry_requires_target_ids_and_rationale(self):
        with tempfile.TemporaryDirectory() as td:
            bad = json.dumps(_valid_ledger_entry("L1", change_type="policy_change"))
            _write(Path(td), "ledger.jsonl", bad + "\n")
            errors: list[str] = []
            v.validate_ledger(Path(td), errors, REPO_ROOT, None)
            self.assertTrue(any("non-empty 'target_ids' list" in e for e in errors))
            self.assertTrue(any("non-empty 'rationale' string" in e for e in errors))

    def test_append_only_enforced_against_git_ref(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _init_repo(tmp)
            seventwos_dir = tmp / ".seventwos"
            seventwos_dir.mkdir()
            _write(seventwos_dir, "ledger.jsonl", _valid_ledger_line("L1") + "\n")
            base_sha = _commit_all(tmp, "base")

            # Legitimate append: should pass.
            _write(
                seventwos_dir,
                "ledger.jsonl",
                _valid_ledger_line("L1") + "\n" + _valid_ledger_line("L2") + "\n",
            )
            errors: list[str] = []
            v.validate_ledger(seventwos_dir, errors, tmp, base_sha)
            self.assertEqual(errors, [])

            # Editing an existing line: should fail.
            _write(
                seventwos_dir,
                "ledger.jsonl",
                _valid_ledger_line("L1-EDITED") + "\n" + _valid_ledger_line("L2") + "\n",
            )
            errors = []
            v.validate_ledger(seventwos_dir, errors, tmp, base_sha)
            self.assertTrue(any("append-only" in e for e in errors))

            # Removing a line: should fail.
            _write(seventwos_dir, "ledger.jsonl", _valid_ledger_line("L2") + "\n")
            errors = []
            v.validate_ledger(seventwos_dir, errors, tmp, base_sha)
            self.assertTrue(any("append-only" in e or "fewer lines" in e for e in errors))

    def test_fails_closed_on_unresolvable_base_ref(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _init_repo(tmp)
            (tmp / "f.txt").write_text("x\n")
            _commit_all(tmp, "base")
            seventwos_dir = tmp / ".seventwos"
            seventwos_dir.mkdir()
            _write(seventwos_dir, "ledger.jsonl", _valid_ledger_line("L1") + "\n")
            errors: list[str] = []
            v.validate_ledger(seventwos_dir, errors, tmp, "0" * 40)
            self.assertTrue(any("cannot resolve base ref" in e for e in errors))


class TestSemanticProtection(unittest.TestCase):
    """Anti-weakening protection for invariants.yml/policy.yml/path-map.yml."""

    def _seed_repo(self, tmp: Path):
        seventwos_dir = tmp / ".seventwos"
        seventwos_dir.mkdir()
        _write(seventwos_dir, "invariants.yml", VALID_INVARIANTS)
        _write(seventwos_dir, "policy.yml", VALID_POLICY)
        _write(seventwos_dir, "path-map.yml", VALID_PATH_MAP)
        _write(seventwos_dir, "ledger.jsonl", _valid_ledger_line("L1") + "\n")
        base_sha = _commit_all(tmp, "seed")
        return seventwos_dir, base_sha

    def test_removing_invariant_without_ledger_justification_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _init_repo(tmp)
            seventwos_dir, base_sha = self._seed_repo(tmp)
            _write(seventwos_dir, "invariants.yml", "schema_version: 1\ninvariants: []\n")
            errors: list[str] = []
            v.validate_invariants(seventwos_dir, errors)
            # invariants: [] is itself a structural error (non-empty required),
            # so exercise the protection logic directly against a *replaced*
            # id instead of an emptied list, to isolate the anti-weakening
            # check from the unrelated "must be non-empty" structural rule.
            replaced = VALID_INVARIANTS.replace("id: INV-1", "id: INV-2")
            _write(seventwos_dir, "invariants.yml", replaced)
            errors = []
            v.validate_semantic_protection(seventwos_dir, tmp, errors, base_sha)
            self.assertTrue(
                any("entry 'INV-1' was removed without a justifying ledger.jsonl entry" in e for e in errors)
            )

    def test_removing_invariant_with_ledger_justification_allowed(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _init_repo(tmp)
            seventwos_dir, base_sha = self._seed_repo(tmp)
            replaced = VALID_INVARIANTS.replace("id: INV-1", "id: INV-2")
            _write(seventwos_dir, "invariants.yml", replaced)
            justifying = _valid_ledger_line(
                "L2",
                change_type="invariant_change",
                target_ids=["INV-1"],
                rationale="INV-1 superseded by INV-2 after re-review.",
            )
            _write(
                seventwos_dir,
                "ledger.jsonl",
                _valid_ledger_line("L1") + "\n" + justifying + "\n",
            )
            errors: list[str] = []
            v.validate_semantic_protection(seventwos_dir, tmp, errors, base_sha)
            self.assertEqual(errors, [])

    def test_changing_invariant_statement_without_justification_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _init_repo(tmp)
            seventwos_dir, base_sha = self._seed_repo(tmp)
            weakened = VALID_INVARIANTS.replace('statement: "test"', 'statement: "weakened"')
            _write(seventwos_dir, "invariants.yml", weakened)
            errors: list[str] = []
            v.validate_semantic_protection(seventwos_dir, tmp, errors, base_sha)
            self.assertTrue(any("field 'statement' was changed without a justifying" in e for e in errors))

    def test_policy_principle_removed_without_justification_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _init_repo(tmp)
            seventwos_dir, base_sha = self._seed_repo(tmp)
            no_principles = """
schema_version: 1
principles: []
process:
  upstream_change_evaluation: []
"""
            _write(seventwos_dir, "policy.yml", no_principles)
            errors: list[str] = []
            v.validate_semantic_protection(seventwos_dir, tmp, errors, base_sha)
            self.assertTrue(
                any("entry 'P1' was removed without a justifying ledger.jsonl entry" in e for e in errors)
            )

    def test_path_map_category_narrowed_without_justification_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _init_repo(tmp)
            seventwos_dir, base_sha = self._seed_repo(tmp)
            narrowed = VALID_PATH_MAP.replace('      - "**/*.gradle"\n', "")
            _write(seventwos_dir, "path-map.yml", narrowed)
            errors: list[str] = []
            v.validate_semantic_protection(seventwos_dir, tmp, errors, base_sha)
            self.assertTrue(
                any("lost path pattern(s)" in e for e in errors)
            )

    def test_path_map_category_expanded_without_justification_allowed(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _init_repo(tmp)
            seventwos_dir, base_sha = self._seed_repo(tmp)
            expanded = VALID_PATH_MAP.replace(
                '      - "**/*.gradle"\n', '      - "**/*.gradle"\n      - "extra/**"\n'
            )
            _write(seventwos_dir, "path-map.yml", expanded)
            errors: list[str] = []
            v.validate_semantic_protection(seventwos_dir, tmp, errors, base_sha)
            self.assertEqual(errors, [])

    def test_path_map_category_removed_without_justification_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _init_repo(tmp)
            seventwos_dir, base_sha = self._seed_repo(tmp)
            data = VALID_PATH_MAP.split("\n  compatibility_sensitive_identifier:")[0] + "\n"
            _write(seventwos_dir, "path-map.yml", data)
            errors: list[str] = []
            v.validate_semantic_protection(seventwos_dir, tmp, errors, base_sha)
            self.assertTrue(
                any(
                    "category 'compatibility_sensitive_identifier' was removed without a "
                    "justifying" in e
                    for e in errors
                )
            )

    def test_fails_closed_on_unresolvable_base_ref(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _init_repo(tmp)
            seventwos_dir, _base_sha = self._seed_repo(tmp)
            errors: list[str] = []
            v.validate_semantic_protection(seventwos_dir, tmp, errors, "0" * 40)
            self.assertTrue(any("cannot resolve base ref" in e for e in errors))


class TestWorkflowHardening(unittest.TestCase):
    VALID_WORKFLOW = """
name: test
on: [push]
permissions:
  contents: read
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@""" + ("a" * 40) + """
        with:
          persist-credentials: false
"""

    def _write_both(self, tmp: Path, content: str) -> Path:
        for name in v.WORKFLOW_FILENAMES:
            _write(tmp, name, content)
        return tmp

    def test_valid_workflow_passes(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = self._write_both(Path(td), self.VALID_WORKFLOW)
            errors: list[str] = []
            v.validate_workflow_hardening(tmp, errors)
            self.assertEqual(errors, [])

    def test_missing_workflow_reported(self):
        with tempfile.TemporaryDirectory() as td:
            errors: list[str] = []
            v.validate_workflow_hardening(Path(td), errors)
            self.assertEqual(len(errors), len(v.WORKFLOW_FILENAMES))
            self.assertTrue(all("missing required workflow" in e for e in errors))

    def test_write_permission_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            bad = self.VALID_WORKFLOW.replace("contents: read", "contents: write")
            tmp = self._write_both(Path(td), bad)
            errors: list[str] = []
            v.validate_workflow_hardening(tmp, errors)
            self.assertTrue(any("grants write permission" in e for e in errors))

    def test_unpinned_action_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            bad = self.VALID_WORKFLOW.replace(
                "uses: actions/checkout@" + ("a" * 40), "uses: actions/checkout@v4"
            )
            tmp = self._write_both(Path(td), bad)
            errors: list[str] = []
            v.validate_workflow_hardening(tmp, errors)
            self.assertTrue(any("not pinned to a full commit SHA" in e for e in errors))

    def test_missing_persist_credentials_false_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            bad = self.VALID_WORKFLOW.replace(
                "        with:\n          persist-credentials: false\n", ""
            )
            tmp = self._write_both(Path(td), bad)
            errors: list[str] = []
            v.validate_workflow_hardening(tmp, errors)
            self.assertTrue(any("persist-credentials: false" in e for e in errors))

    def test_submodules_checkout_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            bad = self.VALID_WORKFLOW.replace(
                "          persist-credentials: false\n",
                "          persist-credentials: false\n          submodules: true\n",
            )
            tmp = self._write_both(Path(td), bad)
            errors: list[str] = []
            v.validate_workflow_hardening(tmp, errors)
            self.assertTrue(any("must not check out submodules" in e for e in errors))

    def test_secrets_reference_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            bad = self.VALID_WORKFLOW + "      - run: echo ${{ secrets.SOME_TOKEN }}\n"
            tmp = self._write_both(Path(td), bad)
            errors: list[str] = []
            v.validate_workflow_hardening(tmp, errors)
            self.assertTrue(any("references 'secrets.'" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
