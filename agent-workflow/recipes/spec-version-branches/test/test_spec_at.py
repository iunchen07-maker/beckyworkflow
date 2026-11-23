#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spec_at.py 本地測試：假的 GitLab（函式）＋暫存 git repo，不連網。
跑法：python3 -m unittest ci/test/test_spec_at.py（正本：recipes/spec-version-branches/test/）
不讀專案的 spec_branches_config.py：每個測試先套 TEST_CONFIG（測試用的固定設定）。

涵蓋：版本號比較（v1.10.0 > v1.9.3、2.0.0 無 v、非版本標題跳過）／短編號不吃更長編號的前綴／
只還原動到 SPEC 的 commit（EXEMPT 不算）／由新到舊還原、§ 節對應（HEADING 沒設時用 Markdown 標題）／
衝突時 abort、移除 worktree、exit 2／只撞 GENERATED 時跑 REGEN_CMD 重產／沒有設定檔 → exit 1。
"""
import contextlib
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import spec_at  # noqa: E402

TEST_CONFIG = types.SimpleNamespace(
    PROJECT="my-org/todo-app",
    ISSUE_RE=r"(?<![\w/])(?:my-org/todo-)?app#(\d+)(?!\d)",
    WATCH=("Spec/", "HTML設計稿/"),
    EXEMPT=("Spec/tools/",),
    HEADING=r"^(#{2,6})\s+(?:§\s*)?(?P<id>US-[A-Za-z0-9.]+)(?=\s|$)",
    GENERATED=["Spec/memory/index/"],
    REGEN_CMD=["{python}", "ci/regen_index.py", "--root", "{root}", "views"],
    TRACE_SINCE="2000-01-01",
    UNTRACED_UPTO=(1, 9, 3),
)

MILESTONES = [{"title": t} for t in ("v1.9.2", "v1.9.3", "v1.10.0", "2.0.0", "Backlog")]
ISSUES = {"v1.10.0": [{"iid": 2}], "2.0.0": [{"iid": 4}], "Backlog": [{"iid": 20}]}


def fake_get(path, params):
    """分頁：每次只回一筆，逼 get_all 走 X-Next-Page。"""
    if path.endswith("/milestones"):
        data = MILESTONES
    else:
        data = ISSUES.get(params["milestone"], [])
    i = int(params["page"]) - 1
    nxt = str(i + 2) if i + 1 < len(data) else ""
    return data[i:i + 1], nxt


def read(base, rel):
    with open(os.path.join(base, rel), encoding="utf-8") as fh:
        return fh.read()


SPEC_V0 ="# 檔\n\n## US-A.1 甲\n甲規則 v0\n\n## US-A.2 乙\n乙規則 v0\n"


class SpecAtTest(unittest.TestCase):
    def setUp(self):
        spec_at.apply_config(TEST_CONFIG)
        self.tmp = tempfile.mkdtemp()
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(os.path.join(self.repo, "Spec", "tools"))
        self.g("init", "-q", "-b", "main")
        self.g("config", "user.name", "t")
        self.g("config", "user.email", "t@t")
        self.commit("Spec/a.md", SPEC_V0, "init（my-org/todo-app#1）")

    def tearDown(self):
        subprocess.run(["git", "-C", self.repo, "worktree", "prune"], capture_output=True)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def g(self, *args):
        return subprocess.run(["git", "-C", self.repo, *args], check=True,
                              capture_output=True, text=True).stdout

    def commit(self, rel, text, msg):
        p = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        self.g("add", rel)
        self.g("commit", "-q", "-m", msg)
        return self.g("rev-parse", "HEAD").strip()

    def run_main(self, *extra):
        out = os.path.join(self.tmp, "out")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = spec_at.main(["v1.9.3", "--root", self.repo, "--ref", "main", "--out", out, *extra],
                              get=fake_get)
        return rc, buf.getvalue(), out

    def test_version_order(self):
        titles, skipped, _ = spec_at.later_milestones(fake_get, (1, 9, 3))
        self.assertEqual(titles, ["v1.10.0", "2.0.0"])
        self.assertEqual(skipped, ["Backlog"])

    def test_revert_later_commits(self):
        self.commit("Spec/a.md", SPEC_V0.replace("甲規則 v0", "甲規則 v1"), "甲（my-org/todo-app#7）")
        self.commit("Spec/a.md", SPEC_V0.replace("甲規則 v0", "甲規則 v1").replace("乙規則 v0", "乙規則 v2"),
                    "乙（my-org/todo-app#2）")
        self.commit("Spec/a.md", SPEC_V0.replace("甲規則 v0", "甲規則 v3").replace("乙規則 v0", "乙規則 v2"),
                    "甲再改（my-org/todo-app#4）")
        self.commit("Spec/b.md", "# b\n\n## US-B.1 丙\nx\n", "Backlog 票（my-org/todo-app#20）")
        self.commit("Spec/tools/x.py", "pass\n", "工具（my-org/todo-app#2）")
        rc, text, out = self.run_main()
        self.assertEqual(rc, 0, text)
        body = read(out, "Spec/a.md")
        self.assertIn("甲規則 v1", body)          # #7 不在較晚 milestone，留著
        self.assertIn("乙規則 v0", body)          # #2 還原
        self.assertTrue(os.path.exists(os.path.join(out, "Spec", "b.md")))   # 長編號那張不被短編號吃到
        self.assertTrue(os.path.exists(os.path.join(out, "Spec", "tools", "x.py")))
        self.assertIn("還原 2 個 commit", text)
        self.assertIn("§US-A.1", text)
        self.assertIn("§US-A.2", text)
        self.assertIn("2000-01-01", text)

    def test_issue_regex(self):
        f = spec_at.ISSUE_RE.findall
        self.assertEqual(f("spec: x（app#3）"), ["3"])
        self.assertEqual(f("my-org/todo-app#3"), ["3"])
        self.assertEqual(f("todo-app#3"), ["3"])
        self.assertEqual(f("app#30"), ["30"])            # 不會當成 3
        self.assertEqual(f("修 #3"), [])                   # 裸 #N 不認
        self.assertEqual(f("other#3 xapp#3"), [])

    def test_short_form_ref(self):
        self.commit("Spec/a.md", SPEC_V0.replace("乙規則 v0", "乙規則 v1"), "spec: 乙（app#2）")
        self.commit("Spec/b.md", "# b\n", "spec: 裸號（#2）")
        self.commit("Spec/c.md", "# c\n", "spec: 長號（app#21）")
        rc, text, out = self.run_main()
        self.assertEqual(rc, 0, text)
        self.assertIn("乙規則 v0", read(out, "Spec/a.md"))
        self.assertTrue(os.path.exists(os.path.join(out, "Spec", "b.md")))
        self.assertTrue(os.path.exists(os.path.join(out, "Spec", "c.md")))
        self.assertIn("還原 1 個 commit", text)

    def test_generated_view_conflict_regenerates(self):
        # 假 regen_index.py：views 只寫一個固定檢視，驗證有被呼叫
        self.commit("ci/regen_index.py",
                    "import os, sys\nroot = sys.argv[sys.argv.index('--root') + 1]\n"
                    "open(os.path.join(root, 'Spec/memory/index/x.md'), 'w').write('regen\\n')\n",
                    "stub")
        self.commit("Spec/memory/index/x.md", "v0\n", "檢視（my-org/todo-app#1）")
        self.commit("Spec/memory/index/x.md", "v1\n", "新票（my-org/todo-app#2）")
        self.commit("Spec/memory/index/x.md", "v2\n", "舊票（my-org/todo-app#7）")
        rc, text, out = self.run_main()
        self.assertEqual(rc, 0, text)
        self.assertEqual(read(out, "Spec/memory/index/x.md"), "regen\n")
        self.assertIn("跑 REGEN_CMD 重產", text)

    def test_no_heading_falls_back_to_markdown(self):
        spec_at.apply_config(types.SimpleNamespace(**{**vars(TEST_CONFIG), "HEADING": None}))
        self.commit("Spec/a.md", SPEC_V0.replace("乙規則 v0", "乙規則 v1"), "乙（app#2）")
        rc, text, _ = self.run_main()
        self.assertEqual(rc, 0, text)
        self.assertIn("#US-A.2 乙", text)
        self.assertNotIn("§US-A.2", text)

    def test_config_applies_strings_and_defaults(self):
        self.assertIsInstance(spec_at.ISSUE_RE, re.Pattern)
        self.assertEqual(spec_at.SPEC_BRANCH_PREFIX, "spec/v")
        self.assertEqual(spec_at.RELEASE_TAG_SUFFIX, "-release")
        self.assertTrue(spec_at.NO_CHANGE_MARK.search("SPEC 不用改，§US-A.1 已涵蓋"))
        with self.assertRaises(ValueError):
            spec_at.apply_config(types.SimpleNamespace(PROJECT="x", ISSUE_RE=r"#(\d+)"))   # 缺 WATCH

    def test_missing_config_exit1(self):
        saved = spec_at.CONFIGURED
        spec_at.CONFIGURED = False
        try:
            rc, text, _ = self.run_main()
        finally:
            spec_at.CONFIGURED = saved
        self.assertEqual(rc, 1, text)
        self.assertIn("spec_branches_config", text)

    def test_conflict_aborts_clean(self):
        self.commit("Spec/a.md", SPEC_V0.replace("甲規則 v0", "甲規則 v1"), "新票（my-org/todo-app#2）")
        self.commit("Spec/a.md", SPEC_V0.replace("甲規則 v0", "甲規則 v2"), "舊票覆寫（my-org/todo-app#7）")
        rc, text, out = self.run_main()
        self.assertEqual(rc, 2, text)
        self.assertIn("衝突", text)
        self.assertIn("my-org/todo-app#2", text)
        self.assertIn("Spec/a.md", text)
        self.assertFalse(os.path.exists(out))
        self.assertNotIn(out, self.g("worktree", "list"))
        self.assertEqual(self.g("status", "--porcelain"), "")


if __name__ == "__main__":
    unittest.main()
