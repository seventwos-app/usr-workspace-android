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


VALID_POLICY = """
schema_version: 1
principles:
  - id: P1
    statement: "example"
process:
  upstream_change_evaluation: []
"""

VALID_STATE = """
schema_version: 1
seed:
  recorded_at: "2026-09-20T00:00:00Z"
  evidence: "test"
  fork: {}
  upstream: {}
  our_branch_at_seed: {}
  merge_base:
    sha: "abc123"
"""

VALID_PATH_MAP = """
schema_version: 1
categories:
  branding:
    description: "test"
    paths:
      - "some/path/**"
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


class TestRealFiles(unittest.TestCase):
    """Sanity-check the actual committed .seventwos files validate clean."""

    def test_real_directory_has_no_base_ref_violations(self):
        errors: list[str] = []
        v.validate_policy(SEVENTWOS_ROOT, errors)
        v.validate_state(SEVENTWOS_ROOT, errors)
        v.validate_path_map(SEVENTWOS_ROOT, errors)
        v.validate_invariants(SEVENTWOS_ROOT, errors)
        v.validate_ledger(SEVENTWOS_ROOT, errors, base_ref=None)
        self.assertEqual(errors, [])

    def test_main_on_real_directory_succeeds(self):
        rc = v.main(["--root", str(SEVENTWOS_ROOT)])
        self.assertEqual(rc, 0)


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
            broken = VALID_STATE.replace('sha: "abc123"', "")
            _write(Path(td), "state.yml", broken)
            errors: list[str] = []
            v.validate_state(Path(td), errors)
            self.assertTrue(any("merge_base.sha" in e for e in errors))


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
    def _valid_entry(self, entry_id: str) -> str:
        return json.dumps(
            {
                "id": entry_id,
                "timestamp": "2026-09-20T00:00:00Z",
                "type": "system_init",
                "actor": "test",
                "summary": "test entry",
            }
        )

    def test_valid_ledger(self):
        with tempfile.TemporaryDirectory() as td:
            _write(Path(td), "ledger.jsonl", self._valid_entry("L1") + "\n")
            errors: list[str] = []
            v.validate_ledger(Path(td), errors, base_ref=None)
            self.assertEqual(errors, [])

    def test_invalid_json_line(self):
        with tempfile.TemporaryDirectory() as td:
            _write(Path(td), "ledger.jsonl", "{not valid json}\n")
            errors: list[str] = []
            v.validate_ledger(Path(td), errors, base_ref=None)
            self.assertTrue(any("invalid JSON" in e for e in errors))

    def test_empty_ledger_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            _write(Path(td), "ledger.jsonl", "\n")
            errors: list[str] = []
            v.validate_ledger(Path(td), errors, base_ref=None)
            self.assertTrue(any("at least one entry" in e for e in errors))

    def test_duplicate_ledger_id(self):
        with tempfile.TemporaryDirectory() as td:
            content = self._valid_entry("L1") + "\n" + self._valid_entry("L1") + "\n"
            _write(Path(td), "ledger.jsonl", content)
            errors: list[str] = []
            v.validate_ledger(Path(td), errors, base_ref=None)
            self.assertTrue(any("duplicate ledger id" in e for e in errors))

    def test_append_only_enforced_against_git_ref(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
            subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp, check=True)
            subprocess.run(["git", "config", "user.name", "test"], cwd=tmp, check=True)
            seventwos_dir = tmp / ".seventwos"
            seventwos_dir.mkdir()
            (seventwos_dir / "ledger.jsonl").write_text(self._valid_entry("L1") + "\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=tmp, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=tmp, check=True)

            # Legitimate append: should pass.
            (seventwos_dir / "ledger.jsonl").write_text(
                self._valid_entry("L1") + "\n" + self._valid_entry("L2") + "\n", encoding="utf-8"
            )
            errors: list[str] = []
            v.validate_ledger(seventwos_dir, errors, base_ref="HEAD")
            self.assertEqual(errors, [])

            # Editing an existing line: should fail.
            (seventwos_dir / "ledger.jsonl").write_text(
                self._valid_entry("L1-EDITED") + "\n" + self._valid_entry("L2") + "\n", encoding="utf-8"
            )
            errors = []
            v.validate_ledger(seventwos_dir, errors, base_ref="HEAD")
            self.assertTrue(any("append-only" in e for e in errors))

            # Removing a line: should fail.
            (seventwos_dir / "ledger.jsonl").write_text(self._valid_entry("L2") + "\n", encoding="utf-8")
            errors = []
            v.validate_ledger(seventwos_dir, errors, base_ref="HEAD")
            self.assertTrue(any("append-only" in e or "fewer lines" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
