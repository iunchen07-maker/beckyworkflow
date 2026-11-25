#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Acceptance tests: release-check ② accepts 「SPEC 變更：commit <sha>」 as coverage.

New rule (c): the issue description or a non-system note has 「SPEC 變更：commit <sha>」
(sha = 7–40 hex) and that sha resolves to a commit reachable from the spec/vX.Y.Z tip
and not reverted on the branch -> the issue counts as covered. The commit itself
need not mention the issue.

Reuses the helpers of recipes/spec-version-branches/test/test_spec_sync.py
(temp repos + bare remote + fake GitLab get()). The helper test class is NOT bound at
module level, so unittest discovery here does not re-run its tests.
"""
import os
import sys
import unittest

RECIPE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RECIPE)
sys.path.insert(0, os.path.join(RECIPE, "test"))
import test_spec_sync as _base  # noqa: E402

ISSUE = 20


class ReleaseSpecChangeMarkTest(unittest.TestCase):
    # borrow helpers from the existing suite
    setUp = _base.SpecSyncTest.setUp
    tearDown = _base.SpecSyncTest.tearDown
    g = _base.SpecSyncTest.g
    commit = _base.SpecSyncTest.commit
    edit = _base.SpecSyncTest.edit
    push_main = _base.SpecSyncTest.push_main
    clone_ci = _base.SpecSyncTest.clone_ci
    human_on = _base.SpecSyncTest.human_on
    remote_rev = _base.SpecSyncTest.remote_rev
    cli = _base.SpecSyncTest.cli
    sync = _base.SpecSyncTest.sync
    release = _base.SpecSyncTest.release

    def old_commit_branch(self):
        """Re-open spec/v1.10.0 after an old SPEC commit on main whose message has no issue ref.
        Returns that commit's sha (it is before the branch point, so it is on the branch)."""
        self.g(self.seed, "push", "-q", "origin", "--delete", "spec/v1.10.0")
        p = self.commit("Spec/old.md", "# old\n", "spec: 舊改動，當年還沒有帶票規則")
        self.push_main()
        self.g(self.seed, "push", "-q", "origin", "main:refs/heads/spec/v1.10.0")
        self.issues["v1.10.0"] = [ISSUE]
        return p

    def note(self, body, system=False):
        self.meta[ISSUE] = {"notes": [{"body": body, "system": system}]}

    def assert_covered(self):
        rc, out = self.release()
        self.assertEqual(rc, 0, out)
        self.assertNotIn("沒交代的 issue", out)
        self.assertNotIn(f"#{ISSUE}（", out)
        return out

    def assert_uncovered(self):
        rc, out = self.release()
        self.assertEqual(rc, 2, out)
        self.assertIn("沒交代的 issue：1 張", out)
        self.assertIn(f"#{ISSUE}（", out)
        return out

    # 1
    def test_note_short_sha_of_pre_branch_commit_covers(self):
        p = self.old_commit_branch()
        self.note(f"討論後確認\nSPEC 變更：commit {p[:7]}")
        self.assert_covered()

    # 2
    def test_note_full_sha_covers(self):
        p = self.old_commit_branch()
        self.note(f"SPEC 變更：commit {p}")
        self.assert_covered()

    # 3
    def test_mark_in_description_covers(self):
        p = self.old_commit_branch()
        self.meta[ISSUE] = {"description": f"背景說明。\nSPEC 變更：commit {p[:10]}\n"}
        self.assert_covered()

    # 4a
    def test_sha_on_main_skipped_as_later_milestone_not_covered(self):
        self.old_commit_branch()
        later = self.commit("Spec/later.md", "# later\n", "下版的事（my-org/todo-app#3）")
        self.push_main()
        self.assertEqual(self.sync()[0], 0)                # skipped: #3 is v1.11.0
        self.note(f"SPEC 變更：commit {later[:7]}")
        self.assert_uncovered()

    # 4b
    def test_sha_only_on_other_branch_not_covered(self):
        self.old_commit_branch()
        self.g(self.seed, "switch", "-q", "-c", "other")
        side = self.commit("Spec/side.md", "# side\n", "別的分支上的改動")
        self.g(self.seed, "push", "-q", "origin", "other")
        self.g(self.seed, "switch", "-q", "main")
        self.note(f"SPEC 變更：commit {side[:7]}")
        self.assert_uncovered()

    # 5
    def test_nonexistent_sha_not_covered(self):
        self.old_commit_branch()
        self.note("SPEC 變更：commit deadbee")
        self.assert_uncovered()

    # 6
    def test_system_note_not_covered(self):
        p = self.old_commit_branch()
        self.note(f"SPEC 變更：commit {p[:7]}", system=True)
        self.assert_uncovered()

    # 7
    def test_sha_reverted_on_branch_not_covered(self):
        p = self.old_commit_branch()
        self.note(f"SPEC 變更：commit {p[:7]}")
        h = self.human_on()
        self.g(h, "revert", "--no-edit", p)
        self.g(h, "push", "-q", "origin", "HEAD:spec/v1.10.0")
        self.assert_uncovered()

    # 8a
    def test_trailing_content_first_sha_qualifies(self):
        p = self.old_commit_branch()
        self.note(f"SPEC 變更：commit {p[:7]}（spec: 舊改動）；mockup：commit deadbee")
        self.assert_covered()

    # 8b
    def test_trailing_content_second_sha_qualifies(self):
        p = self.old_commit_branch()
        self.note(f"SPEC 變更：commit deadbee（spec: …）；mockup：commit {p[:7]}")
        self.assert_covered()


if __name__ == "__main__":
    unittest.main()
