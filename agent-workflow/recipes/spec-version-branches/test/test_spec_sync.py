#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spec_sync.py 本地測試：假的 GitLab（函式）＋暫存 git repo（假 bare remote），不連網。
跑法：python3 -m unittest ci/test/test_spec_sync.py（正本：recipes/spec-version-branches/test/）
不讀專案的 spec_branches_config.py：每個測試先套 TEST_CONFIG（測試用的固定設定）。

涵蓋：依 milestone 挑／跳過／沒帶 issue 照挑／已挑過不重挑／有 -release tag 的分支不碰／
衝突 → exit 2 且遠端分支不動／衝突沒解時下一次 push 仍停在同一筆、人解完後依序接著挑／
分支點以前的 commit 不挑／API 失敗 → exit 1 且什麼都沒推／check 報缺與多（附 revert 指令）／
在分支上 revert 掉的 → issue 仍較晚時 check 一致、sync 不重挑；issue 改回本版 → check 報缺、
sync 依 main 順序重挑（重挑衝突 → exit 2）；挑→撤→重挑→再撤以最後動作為準（revert 的 revert → 恢復）／
dry run 不推（舊參數 --range 仍接受）／只撞 GENERATED 時重產後繼續／merge commit 走 -m 1／
release-check：全過＋--tag 打 annotated tag 並推、之後 sync 視為已關閉／tag 已存在不重打／
分支缺 commit、milestone issue 沒交代（系統留言不算）、分支帶更晚 milestone issue → exit 2 且不打 tag／
「不用改」標記在描述或留言都認／merge 經 -x trailer 對回 main 才認得 issue／分支點以前的 commit 也算交代、
在分支上被撤就不算（revert 的 revert 恢復）／還開著的 issue 與沒帶 issue
的 commit 只列不擋／分支不存在、API 失敗、推 tag 失敗 → exit 1（推失敗不留本機 tag）。
"""
import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import spec_at  # noqa: E402
import spec_sync  # noqa: E402

TEST_CONFIG = types.SimpleNamespace(
    PROJECT="my-org/todo-app",
    ISSUE_RE=r"(?<![\w/])(?:my-org/todo-)?app#(\d+)(?!\d)",
    WATCH=("Spec/", "HTML設計稿/"),
    EXEMPT=("Spec/tools/",),
    GENERATED=["Spec/memory/index/"],
    REGEN_CMD=["{python}", "ci/regen_index.py", "--root", "{root}", "views"],
)

MILESTONES = [{"title": t} for t in ("v1.9.3", "v1.10.0", "v1.11.0", "Backlog")]
TRAILER = "(cherry picked from commit "


def make_get(issues, meta=None):
    """issues＝{milestone: [iid]}；meta＝{iid: {state, description, notes: [{body, system}]}}（可省）。"""
    meta = meta or {}

    def get(path, params):
        if path.endswith("/milestones"):
            data = MILESTONES
        elif path.endswith("/notes"):                  # issue 留言（release-check 用）
            n = int(path.split("/issues/")[1].split("/")[0])
            data = meta.get(n, {}).get("notes", [])
        elif "/issues/" in path:                       # 單張 issue（表格顯示 milestone 用）
            n = int(path.rsplit("/", 1)[1])
            t = next((t for t, ns in issues.items() if n in ns), None)
            return {"iid": n, "milestone": {"title": t} if t else None}, ""
        else:
            data = [{"iid": n, "title": f"票{n}", "state": meta.get(n, {}).get("state", "closed"),
                     "description": meta.get(n, {}).get("description", "")}
                    for n in issues.get(params["milestone"], [])]
        if not data:
            return [], ""
        i = int(params["page"]) - 1
        nxt = str(i + 2) if i + 1 < len(data) else ""
        return data[i:i + 1], nxt
    return get


def broken_get(path, params):
    raise OSError("HTTP 502")


SPEC = "# 檔\n\n## US-A.1 甲\n甲 v0\n\n## US-A.2 乙\n乙 v0\n"


class SpecSyncTest(unittest.TestCase):
    def setUp(self):
        spec_at.apply_config(TEST_CONFIG)
        self.meta = {}
        self.tmp = tempfile.mkdtemp()
        self.remote = os.path.join(self.tmp, "remote.git")
        self.seed = os.path.join(self.tmp, "seed")      # 模擬 main 上的開發者
        self.ci = os.path.join(self.tmp, "ci")          # 模擬 CI checkout
        self.human = os.path.join(self.tmp, "human")    # 模擬在 spec 分支上手動處理的人
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", self.remote], check=True)
        subprocess.run(["git", "init", "-q", "-b", "main", self.seed], check=True)
        self.g(self.seed, "config", "user.name", "t")
        self.g(self.seed, "config", "user.email", "t@t")
        self.g(self.seed, "remote", "add", "origin", self.remote)
        self.commit("Spec/a.md", SPEC, "init（my-org/todo-app#1）")
        self.g(self.seed, "push", "-q", "origin", "main")
        # 從今天的 main 開 v1.10.0 分支
        self.g(self.seed, "push", "-q", "origin", "main:refs/heads/spec/v1.10.0")
        self.issues = {"v1.10.0": [2], "v1.11.0": [3], "Backlog": [9]}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ── helpers ──
    def g(self, repo, *args, check=True):
        r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
        if check and r.returncode != 0:
            raise AssertionError(f"git {args} 失敗：{r.stderr}")
        return r.stdout

    def commit(self, rel, text, msg):
        p = os.path.join(self.seed, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        self.g(self.seed, "add", rel)
        self.g(self.seed, "commit", "-q", "-m", msg)
        return self.g(self.seed, "rev-parse", "HEAD").strip()

    def edit(self, old, new, msg, rel="Spec/a.md"):
        p = os.path.join(self.seed, rel)
        with open(p, encoding="utf-8") as fh:
            text = fh.read()
        return self.commit(rel, text.replace(old, new), msg)

    def push_main(self):
        self.g(self.seed, "push", "-q", "origin", "main")

    def clone_ci(self):
        if not os.path.exists(self.ci):
            subprocess.run(["git", "clone", "-q", self.remote, self.ci], check=True)
            self.g(self.ci, "config", "user.name", "spec-sync-bot")
            self.g(self.ci, "config", "user.email", "bot@t")
        else:
            self.g(self.ci, "fetch", "-q", "origin")

    def human_on(self, branch="spec/v1.10.0"):
        """人在 spec 分支上：clone（或 pull）並切到該分支。"""
        if not os.path.exists(self.human):
            subprocess.run(["git", "clone", "-q", self.remote, self.human], check=True)
            self.g(self.human, "config", "user.name", "pm")
            self.g(self.human, "config", "user.email", "pm@t")
        self.g(self.human, "fetch", "-q", "origin")
        self.g(self.human, "switch", "-q", "-C", branch, f"origin/{branch}")
        return self.human

    def remote_rev(self, ref):
        return self.g(self.remote, "rev-parse", ref).strip()

    def branch_file(self, ref="spec/v1.10.0", rel="Spec/a.md"):
        return self.g(self.remote, "show", f"{ref}:{rel}")

    def branch_picks(self, ref="spec/v1.10.0"):
        """分支上 -x trailer 指的 main sha，由舊到新。"""
        log = self.g(self.remote, "log", "--reverse", "--format=%B", ref)
        return [ln.strip()[len(TRAILER):-1] for ln in log.split("\n") if ln.strip().startswith(TRAILER)]

    def cli(self, *argv, get=None):
        self.clone_ci()
        buf = io.StringIO()
        env = {k: v for k, v in os.environ.items() if k != "SPEC_SYNC_WEBHOOK"}
        with mock.patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(buf):
            rc = spec_sync.main(["--root", self.ci, *argv], get=get or make_get(self.issues, self.meta))
        return rc, buf.getvalue()

    def sync(self, *extra, get=None):
        return self.cli("sync", "--push", "--push-url", self.remote, *extra, get=get)

    # ── sync ──
    def test_pick_skip_by_milestone_and_no_ticket(self):
        self.edit("甲 v0", "甲 v1", "本版（my-org/todo-app#2）")
        self.edit("乙 v0", "乙 v1", "下版（my-org/todo-app#3）")
        self.commit("ci/tool.py", "pass\n", "ci: 工具沒帶票")
        self.commit("Spec/b.md", "# b\n", "Backlog（app#9）")
        self.push_main()
        rc, out = self.sync()
        self.assertEqual(rc, 0, out)
        body = self.branch_file()
        self.assertIn("甲 v1", body)
        self.assertIn("乙 v0", body)                       # #3 屬 v1.11.0 → 跳過
        self.assertEqual(self.branch_file(rel="ci/tool.py"), "pass\n")
        self.assertEqual(self.branch_file(rel="Spec/b.md"), "# b\n")
        self.assertEqual(len(self.branch_picks()), 3)
        self.assertIn("較晚 milestone：#3→v1.11.0", out)
        self.assertIn("沒帶 issue", out)
        self.assertIn("#2=v1.10.0", out)
        self.assertIn("#9=Backlog", out)

    def test_already_picked_not_repicked(self):
        self.edit("甲 v0", "甲 v1", "本版（my-org/todo-app#2）")
        self.push_main()
        rc, out = self.sync()
        self.assertEqual(rc, 0, out)
        head = self.remote_rev("spec/v1.10.0")
        rc, out = self.sync()                              # 再跑一次
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.remote_rev("spec/v1.10.0"), head)
        self.assertIn("已同步（-x trailer）1 個", out)
        self.assertIn("沒有要挑的 commit", out)

    def test_commits_before_branch_point_never_picked(self):
        a = self.edit("甲 v0", "甲 v1", "本版（my-org/todo-app#2）")
        self.push_main()
        # 之後才開 v1.11.0：a 在它的分支點以前 → 只有 v1.10.0 要挑
        self.g(self.seed, "push", "-q", "origin", "main:refs/heads/spec/v1.11.0")
        before = self.remote_rev("spec/v1.11.0")
        rc, out = self.sync()
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.branch_picks(), [a])
        self.assertEqual(self.remote_rev("spec/v1.11.0"), before)
        self.assertEqual(self.branch_picks("spec/v1.11.0"), [])

    def test_closed_branch_ignored(self):
        self.g(self.seed, "push", "-q", "origin", "main:refs/heads/spec/v1.9.3")
        self.g(self.seed, "tag", "spec/v1.9.3-release", "main")
        self.g(self.seed, "push", "-q", "origin", "spec/v1.9.3-release")
        before = self.remote_rev("spec/v1.9.3")
        self.edit("甲 v0", "甲 v1", "沒帶票")
        self.push_main()
        rc, out = self.sync()
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.remote_rev("spec/v1.9.3"), before)
        self.assertIn("已 release（不再同步）：spec/v1.9.3", out)
        self.assertIn("甲 v1", self.branch_file())        # v1.10.0 照樣同步

    def test_conflict_exit2_branch_untouched(self):
        self.edit("甲 v0", "甲 v1", "下版改甲（my-org/todo-app#3）")
        self.edit("甲 v1", "甲 v2", "本版接著改甲（my-org/todo-app#2）")
        self.commit("Spec/c.md", "# c\n", "本版另一檔（my-org/todo-app#2）")
        self.push_main()
        before = self.remote_rev("spec/v1.10.0")
        rc, out = self.sync("--notify")
        self.assertEqual(rc, 2, out)
        self.assertEqual(self.remote_rev("spec/v1.10.0"), before)
        self.assertIn("衝突", out)
        self.assertIn("Spec/a.md", out)
        self.assertIn("cherry-pick -x", out)               # 通知裡附手動解法
        self.assertNotIn("spec-sync-", self.g(self.ci, "worktree", "list"))
        self.assertEqual(self.g(self.ci, "status", "--porcelain"), "")

    def test_conflict_then_next_push_stays_at_same_commit_until_resolved(self):
        # push 1：K1 依賴下版的 X → 衝突，什麼都沒推
        self.edit("甲 v0", "甲 v1", "下版改甲（my-org/todo-app#3）")
        k1 = self.edit("甲 v1", "甲 v2", "本版接著改甲（my-org/todo-app#2）")
        self.push_main()
        before = self.remote_rev("spec/v1.10.0")
        rc, out = self.sync()
        self.assertEqual(rc, 2, out)
        self.assertIn(f"cherry-pick {k1[:8]} 衝突", out)
        # push 2：K2、K3 本身不衝突，但 K1 沒解 → 仍停在 K1，分支不前進
        k2 = self.commit("Spec/c.md", "# c\n", "本版另一檔（my-org/todo-app#2）")
        k3 = self.commit("Spec/f.md", "# f\n", "本版第三檔（my-org/todo-app#2）")
        self.push_main()
        rc, out = self.sync("--notify")
        self.assertEqual(rc, 2, out)
        self.assertIn(f"cherry-pick {k1[:8]} 衝突", out)
        self.assertIn("後面還有 2 個待挑", out)
        self.assertEqual(self.remote_rev("spec/v1.10.0"), before)
        self.assertEqual(self.branch_picks(), [])
        # 人解 K1 後推上去
        h = self.human_on()
        r = subprocess.run(["git", "-C", h, "cherry-pick", "-x", k1], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        with open(os.path.join(h, "Spec/a.md"), "w", encoding="utf-8") as fh:
            fh.write(SPEC.replace("甲 v0", "甲 v2"))
        self.g(h, "add", "Spec/a.md")
        self.g(h, "-c", "core.editor=true", "cherry-pick", "--continue")
        self.g(h, "push", "-q", "origin", "HEAD:spec/v1.10.0")
        # 下一次同步：依序接著挑 K2、K3
        rc, out = self.sync()
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.branch_picks(), [k1, k2, k3])
        self.assertIn("甲 v2", self.branch_file())
        rc, out = self.cli("check")
        self.assertEqual(rc, 0, out)
        self.assertIn("✓ 一致", out)

    def test_api_failure_exit1_nothing_pushed(self):
        self.edit("甲 v0", "甲 v1", "本版（my-org/todo-app#2）")
        self.push_main()
        before = self.remote_rev("spec/v1.10.0")
        rc, out = self.sync(get=broken_get)
        self.assertEqual(rc, 1, out)
        self.assertEqual(self.remote_rev("spec/v1.10.0"), before)
        self.assertIn("GitLab API 失敗", out)

    def test_dry_run_does_not_push_and_range_is_ignored(self):
        a = self.edit("甲 v0", "甲 v1", "本版（my-org/todo-app#2）")
        self.push_main()
        before = self.remote_rev("spec/v1.10.0")
        b = self.commit("Spec/c.md", "# c\n", "本版（my-org/todo-app#2）")
        self.push_main()
        # 舊呼叫只給最後一筆的 range：照樣從分支點算，a、b 都挑
        rc, out = self.cli("sync", "--range", f"{a}..origin/main")
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.remote_rev("spec/v1.10.0"), before)
        self.assertIn("dry run，未推", out)
        self.assertIn("已不使用", out)
        self.assertIn("挑 2 個 commit", out)
        self.assertIn(a[:8], out)
        self.assertIn(b[:8], out)

    def test_generated_view_conflict_regenerates(self):
        self.commit("ci/regen_index.py",
                    "import os, sys\nroot = sys.argv[sys.argv.index('--root') + 1]\n"
                    "open(os.path.join(root, 'Spec/memory/index/x.md'), 'w').write('regen\\n')\n",
                    "stub")
        self.commit("Spec/memory/index/x.md", "v0\n", "檢視（my-org/todo-app#1）")
        self.push_main()
        self.g(self.seed, "push", "-q", "-f", "origin", "main:refs/heads/spec/v1.10.0")
        self.commit("Spec/memory/index/x.md", "v1\n", "下版（my-org/todo-app#3）")
        self.commit("Spec/memory/index/x.md", "v2\n", "本版（my-org/todo-app#2）")
        self.push_main()
        rc, out = self.sync()
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.branch_file(rel="Spec/memory/index/x.md"), "regen\n")

    def test_merge_commit_picked_with_m1(self):
        self.g(self.seed, "switch", "-q", "-c", "feat")
        self.edit("甲 v0", "甲 v1", "側枝（my-org/todo-app#2）")
        self.g(self.seed, "switch", "-q", "main")
        self.commit("Spec/d.md", "# d\n", "main 上另一筆")
        self.g(self.seed, "merge", "-q", "--no-ff", "-m", "Merge feat", "feat")
        merge = self.g(self.seed, "rev-parse", "HEAD").strip()
        self.push_main()
        rc, out = self.sync()
        self.assertEqual(rc, 0, out)
        self.assertIn("甲 v1", self.branch_file())
        self.assertIn(merge, self.branch_picks())
        self.assertIn("-m 1", out)

    def test_merge_commit_skipped_when_side_has_later_ticket(self):
        self.g(self.seed, "switch", "-q", "-c", "feat")
        self.edit("甲 v0", "甲 v1", "側枝（my-org/todo-app#3）")
        self.g(self.seed, "switch", "-q", "main")
        self.commit("Spec/d.md", "# d\n", "main 上另一筆")
        self.g(self.seed, "merge", "-q", "--no-ff", "-m", "Merge feat", "feat")
        self.push_main()
        rc, out = self.sync()
        self.assertEqual(rc, 0, out)
        self.assertIn("甲 v0", self.branch_file())

    # ── check ──
    def test_check_reports_missing_and_extra(self):
        a = self.edit("甲 v0", "甲 v1", "原本本版（my-org/todo-app#4）")
        self.push_main()
        self.issues["v1.10.0"].append(4)
        rc, out = self.sync()
        self.assertEqual(rc, 0, out)
        rc, out = self.cli("check", get=make_get(self.issues))
        self.assertEqual(rc, 0, out)
        self.assertIn("✓ 一致", out)
        # 票改到下版 → 分支上那筆變「多」；main 新 commit 沒同步 → 「缺」
        self.issues["v1.10.0"].remove(4)
        self.issues["v1.11.0"].append(4)
        b = self.commit("Spec/e.md", "# e\n", "沒同步到（my-org/todo-app#2）")
        self.push_main()
        rc, out = self.cli("check", "--notify", get=make_get(self.issues))
        self.assertEqual(rc, 2, out)
        self.assertIn("缺（該挑沒挑）：1 個", out)
        self.assertIn(b[:8], out)
        self.assertIn("多（挑了但現在屬於更晚 milestone）：1 個", out)
        self.assertIn(a[:8], out)
        bsha = self.remote_rev("spec/v1.10.0")             # 分支上那筆（不是 main 的 a）
        self.assertIn(f"git switch spec/v1.10.0 && git pull && git revert {bsha} && git push", out)

    # 票 #4 在 v1.10.0 ↔ v1.11.0 之間搬
    def move_4(self, to):
        for t in ("v1.10.0", "v1.11.0"):
            if 4 in self.issues[t]:
                self.issues[t].remove(4)
        self.issues[to].append(4)

    def revert_branch_head(self):
        """照通知的指令在分支上 revert 分支最新那筆，回傳被撤的分支 sha。"""
        h = self.human_on()
        bsha = self.g(h, "rev-parse", "HEAD").strip()
        self.g(h, "revert", "--no-edit", bsha)
        self.g(h, "push", "-q", "origin", "HEAD:spec/v1.10.0")
        return bsha

    def test_dropped_commit_repicked_when_milestone_moves_back(self):
        a = self.edit("甲 v0", "甲 v1", "原本本版（my-org/todo-app#4）")
        self.push_main()
        self.move_4("v1.10.0")
        rc, out = self.sync()
        self.assertEqual(rc, 0, out)
        self.move_4("v1.11.0")                            # 票改到下版 → 多
        rc, out = self.cli("check")
        self.assertEqual(rc, 2, out)
        self.revert_branch_head()
        rc, out = self.cli("check")                        # 撤了、票仍較晚 → 安靜
        self.assertEqual(rc, 0, out)
        self.assertIn("✓ 一致", out)
        self.assertIn("已在分支上 revert 1 個", out)
        self.assertIn(f"（已撤）{a[:8]}", out)
        head = self.remote_rev("spec/v1.10.0")
        rc, out = self.sync()                              # 票仍較晚 → 不重挑
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.remote_rev("spec/v1.10.0"), head)
        # 票改回本版 → check 報缺
        self.move_4("v1.10.0")
        rc, out = self.cli("check")
        self.assertEqual(rc, 2, out)
        self.assertIn("缺（該挑沒挑）：1 個", out)
        self.assertIn(a[:8], out)
        self.assertNotIn("已在分支上 revert", out)
        # sync 重挑
        rc, out = self.sync()
        self.assertEqual(rc, 0, out)
        self.assertIn("挑 1 個 commit，已推", out)
        self.assertEqual(self.branch_picks(), [a, a])     # 原本那筆＋重挑那筆
        self.assertEqual(self.branch_file(), self.g(self.seed, "show", "main:Spec/a.md"))
        rc, out = self.cli("check")
        self.assertEqual(rc, 0, out)
        self.assertIn("✓ 一致", out)
        self.assertIn("分支上已同步 1 個", out)
        self.assertNotIn("已在分支上 revert", out)
        head = self.remote_rev("spec/v1.10.0")
        rc, out = self.sync()                              # 不會再挑第三次
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.remote_rev("spec/v1.10.0"), head)

    def test_repick_then_revert_again(self):
        a = self.edit("甲 v0", "甲 v1", "原本本版（my-org/todo-app#4）")
        self.push_main()
        self.move_4("v1.10.0")
        self.assertEqual(self.sync()[0], 0)
        self.move_4("v1.11.0")
        self.revert_branch_head()                          # 挑 → 撤
        self.move_4("v1.10.0")
        rc, out = self.sync()                              # → 重挑
        self.assertEqual(rc, 0, out)
        self.assertIn("甲 v1", self.branch_file())
        # 票又改到下版：重挑那筆是「多」，revert 指令給的是重挑那筆
        self.move_4("v1.11.0")
        rc, out = self.cli("check")
        self.assertEqual(rc, 2, out)
        self.assertIn("多（挑了但現在屬於更晚 milestone）：1 個", out)
        repick = self.remote_rev("spec/v1.10.0")
        self.assertIn(f"git revert {repick}", out)
        self.assertEqual(self.revert_branch_head(), repick)  # → 再撤
        rc, out = self.cli("check")
        self.assertEqual(rc, 0, out)
        self.assertIn("✓ 一致", out)
        self.assertIn("已在分支上 revert 1 個", out)
        self.assertIn("甲 v0", self.branch_file())
        head = self.remote_rev("spec/v1.10.0")
        self.assertEqual(self.sync()[0], 0)                # 票仍較晚 → 不挑
        self.assertEqual(self.remote_rev("spec/v1.10.0"), head)
        # 票第三次改回本版 → 再重挑一次
        self.move_4("v1.10.0")
        rc, out = self.cli("check")
        self.assertEqual(rc, 2, out)
        self.assertIn("缺（該挑沒挑）：1 個", out)
        self.assertEqual(self.sync()[0], 0)
        self.assertEqual(self.branch_picks(), [a, a, a])
        self.assertIn("甲 v1", self.branch_file())
        rc, out = self.cli("check")
        self.assertEqual(rc, 0, out)
        self.assertIn("✓ 一致", out)

    def test_repick_follows_main_order(self):
        a = self.edit("甲 v0", "甲 v1", "原本本版（my-org/todo-app#4）")
        self.push_main()
        self.move_4("v1.10.0")
        self.assertEqual(self.sync()[0], 0)
        self.move_4("v1.11.0")
        self.revert_branch_head()
        # main 之後有一筆本版的 b 接著改甲（依賴 a）：票改回本版後 a 先重挑、b 才挑得上
        b = self.edit("甲 v1", "甲 v2", "本版接著改甲（my-org/todo-app#2）")
        self.push_main()
        self.move_4("v1.10.0")
        rc, out = self.sync()
        self.assertEqual(rc, 0, out)
        self.assertIn("挑 2 個 commit，已推", out)
        self.assertEqual(self.branch_picks(), [a, a, b])
        self.assertIn("甲 v2", self.branch_file())

    def test_repick_conflict_exit2(self):
        a = self.edit("甲 v0", "甲 v1", "原本本版（my-org/todo-app#4）")
        self.push_main()
        self.move_4("v1.10.0")
        self.assertEqual(self.sync()[0], 0)
        self.move_4("v1.11.0")
        h = self.human_on()
        self.g(h, "revert", "--no-edit", "HEAD")
        # 撤完後有人直接在分支上改了同一行 → 重挑會衝突
        with open(os.path.join(h, "Spec/a.md"), "w", encoding="utf-8") as fh:
            fh.write(SPEC.replace("甲 v0", "甲 分支手改"))
        self.g(h, "commit", "-q", "-am", "分支手改（my-org/todo-app#2）")
        self.g(h, "push", "-q", "origin", "HEAD:spec/v1.10.0")
        self.move_4("v1.10.0")
        before = self.remote_rev("spec/v1.10.0")
        rc, out = self.sync("--notify")
        self.assertEqual(rc, 2, out)
        self.assertIn(f"cherry-pick {a[:8]} 衝突", out)
        self.assertIn("Spec/a.md", out)
        self.assertEqual(self.remote_rev("spec/v1.10.0"), before)

    def test_revert_of_revert_restores_synced(self):
        self.edit("甲 v0", "甲 v1", "原本本版（my-org/todo-app#4）")
        self.push_main()
        self.issues["v1.10.0"].append(4)
        rc, out = self.sync()
        self.assertEqual(rc, 0, out)
        h = self.human_on()
        self.g(h, "revert", "--no-edit", "HEAD")
        self.g(h, "revert", "--no-edit", "HEAD")           # 反悔：撤銷那個 revert
        self.g(h, "push", "-q", "origin", "HEAD:spec/v1.10.0")
        self.issues["v1.10.0"].remove(4)
        self.issues["v1.11.0"].append(4)
        rc, out = self.cli("check")
        self.assertEqual(rc, 2, out)                       # 又算「已同步」→ 票改到下版就是「多」
        self.assertIn("多（挑了但現在屬於更晚 milestone）：1 個", out)

    def test_check_api_failure_exit1(self):
        rc, out = self.cli("check", get=broken_get)
        self.assertEqual(rc, 1, out)

    # ── release-check ──
    TAG = "spec/v1.10.0-release"

    def release(self, *extra, get=None):
        return self.cli("release-check", "v1.10.0", "--push-url", self.remote, *extra, get=get)

    def remote_has_tag(self):
        return subprocess.run(["git", "-C", self.remote, "rev-parse", "-q", "--verify", f"refs/tags/{self.TAG}"],
                              capture_output=True).returncode == 0

    def synced_release_branch(self):
        """main 上兩筆本版 commit 都同步到分支；回傳 (a, b)。"""
        a = self.edit("甲 v0", "甲 v1", "本版（my-org/todo-app#2）")
        b = self.commit("Spec/c.md", "# c\n", "本版另一張（app#4）")
        self.push_main()
        self.issues["v1.10.0"] += [4]
        self.assertEqual(self.sync()[0], 0)
        return a, b

    def test_release_pass_tags_and_closes_branch(self):
        self.synced_release_branch()
        self.issues["v1.10.0"] += [5, 6]
        self.meta[5] = {"notes": [{"body": "討論過了\nSPEC 不用改，§US-A.1 已涵蓋", "system": False}]}
        self.meta[6] = {"description": "純後端調整。SPEC 不用改，§US-A.2"}
        rc, out = self.release()
        self.assertEqual(rc, 0, out)                       # 沒帶 --tag：不打
        self.assertFalse(self.remote_has_tag())
        self.assertIn("標了不用改：2 張", out)
        rc, out = self.release("--tag", "--notify")
        self.assertEqual(rc, 0, out)
        self.assertIn("已打 tag spec/v1.10.0-release", out)
        tip = self.remote_rev("spec/v1.10.0")
        self.assertEqual(self.g(self.remote, "cat-file", "-t", self.TAG).strip(), "tag")   # annotated
        self.assertEqual(self.remote_rev(f"{self.TAG}^{{commit}}"), tip)
        rc, out = self.release("--tag")                    # 再跑：不重打
        self.assertEqual(rc, 0, out)
        self.assertIn("已存在，不重打", out)
        self.edit("乙 v0", "乙 v1", "之後的本版改動（my-org/todo-app#2）")
        self.push_main()
        rc, out = self.sync()                              # 打了 tag → 不再同步
        self.assertEqual(rc, 0, out)
        self.assertIn("已 release（不再同步）：spec/v1.10.0", out)
        self.assertEqual(self.remote_rev("spec/v1.10.0"), tip)

    def test_release_uncovered_issue_blocks_and_no_tag(self):
        self.synced_release_branch()
        self.issues["v1.10.0"] += [7]
        self.meta[7] = {"notes": [{"body": "changed milestone; SPEC 不用改，§US-A.1", "system": True}]}
        rc, out = self.release("--tag", "--notify")
        self.assertEqual(rc, 2, out)
        self.assertIn("沒交代的 issue：1 張", out)
        self.assertIn("#7", out)
        self.assertIn("不打 tag", out)
        self.assertFalse(self.remote_has_tag())
        self.assertNotIn(self.TAG, self.g(self.ci, "tag"))

    def test_release_branch_missing_commit_blocks(self):
        self.synced_release_branch()
        c = self.commit("Spec/e.md", "# e\n", "還沒同步（my-org/todo-app#2）")
        self.push_main()
        rc, out = self.release("--tag")
        self.assertEqual(rc, 2, out)
        self.assertIn("缺（該挑沒挑）：1 個", out)
        self.assertIn(c[:8], out)
        self.assertFalse(self.remote_has_tag())

    def test_release_later_milestone_commit_on_branch_blocks(self):
        self.synced_release_branch()
        h = self.human_on()
        with open(os.path.join(h, "Spec/f.md"), "w", encoding="utf-8") as fh:
            fh.write("# f\n")
        self.g(h, "add", "Spec/f.md")
        self.g(h, "commit", "-q", "-m", "直接在分支上做下版的事（my-org/todo-app#3）")
        self.g(h, "push", "-q", "origin", "HEAD:spec/v1.10.0")
        bad = self.remote_rev("spec/v1.10.0")
        rc, out = self.release("--tag")
        self.assertEqual(rc, 2, out)
        self.assertIn("帶更晚 milestone issue 的 commit：1 個", out)
        self.assertIn(f"{bad[:8]} #3→v1.11.0", out)
        self.assertIn("✓ 一致", out)                      # ① 本身沒事，是 ③ 擋下
        self.assertFalse(self.remote_has_tag())

    def test_release_lists_open_issues_and_untracked_commits(self):
        self.synced_release_branch()
        self.commit("ci/tool.py", "pass\n", "ci: 工具沒帶票")
        self.push_main()
        self.assertEqual(self.sync()[0], 0)
        self.meta[2] = {"state": "opened"}
        rc, out = self.release()
        self.assertEqual(rc, 0, out)
        self.assertIn("還開著的 issue 1 張", out)
        self.assertIn("#2 票2", out)
        self.assertIn("沒帶 issue 的 commit 1 個", out)
        self.assertIn("ci: 工具沒帶票", out)

    def test_release_coverage_via_trailer_of_merge(self):
        # merge 訊息本身沒帶票、票在側枝：分支上那筆（-m 1）只能靠 -x trailer 對回 main 才認得 #2
        self.g(self.seed, "switch", "-q", "-c", "feat")
        self.edit("甲 v0", "甲 v1", "側枝（my-org/todo-app#2）")
        self.g(self.seed, "switch", "-q", "main")
        self.commit("Spec/d.md", "# d\n", "main 上另一筆")
        self.g(self.seed, "merge", "-q", "--no-ff", "-m", "Merge feat", "feat")
        self.push_main()
        self.assertEqual(self.sync()[0], 0)
        self.issues["v1.10.0"] = [2]
        rc, out = self.release()
        self.assertEqual(rc, 0, out)
        self.assertIn("分支有 commit：1 張", out)
        self.assertIn("沒帶 issue 的 commit 1 個", out)    # 只有「main 上另一筆」
        self.assertIn("｜main 上另一筆", out)
        self.assertNotIn("｜Merge feat", out)

    def test_release_reverted_commit_does_not_cover(self):
        a, _ = self.synced_release_branch()
        self.issues["v1.10.0"].remove(2)
        self.issues["v1.11.0"].append(2)
        self.revert_branch_head()                          # 撤掉 #4 那筆
        self.issues["v1.10.0"].remove(4)
        self.issues["v1.11.0"].append(4)
        self.issues["v1.10.0"].append(8)                  # 本版只剩 #8，分支上沒有它
        h = self.human_on()
        self.g(h, "revert", "--no-edit", "HEAD~2")         # 也撤掉 #2 那筆（HEAD~1＝#4 那筆）
        self.g(h, "push", "-q", "origin", "HEAD:spec/v1.10.0")
        rc, out = self.release()
        self.assertEqual(rc, 2, out)
        self.assertIn("沒交代的 issue：1 張", out)
        self.assertIn("#8", out)
        self.assertNotIn("帶更晚 milestone issue 的 commit：", out)   # 撤掉的不算 ③

    def test_release_pre_branch_point_commit_covers(self):
        # #1 的 commit（init）在分支點以前：分支開的時候就帶進來了 → 算有交代
        self.synced_release_branch()
        self.issues["v1.10.0"] += [1]
        rc, out = self.release()
        self.assertEqual(rc, 0, out)
        self.assertIn("分支有 commit：3 張", out)

    def test_release_pre_branch_point_commit_reverted_on_branch_does_not_cover(self):
        # 分支點以前的 #5 commit，在分支上被 revert → 不算交代
        self.g(self.seed, "push", "-q", "origin", "--delete", "spec/v1.10.0")
        p = self.commit("Spec/g.md", "# g\n", "本版早做的（my-org/todo-app#5）")
        self.push_main()
        self.g(self.seed, "push", "-q", "origin", "main:refs/heads/spec/v1.10.0")   # 分支點＝p
        self.issues["v1.10.0"] = [5]
        rc, out = self.release()
        self.assertEqual(rc, 0, out)                       # 撤之前：分支點以前的 commit 算交代
        h = self.human_on()
        self.g(h, "revert", "--no-edit", p)
        self.g(h, "push", "-q", "origin", "HEAD:spec/v1.10.0")
        rc, out = self.release()
        self.assertEqual(rc, 2, out)
        self.assertIn("沒交代的 issue：1 張", out)
        self.assertIn("#5（closed）票5", out)
        self.g(h, "revert", "--no-edit", "HEAD")           # revert 的 revert → 恢復
        self.g(h, "push", "-q", "origin", "HEAD:spec/v1.10.0")
        rc, out = self.release()
        self.assertEqual(rc, 0, out)

    def test_release_missing_branch_or_api_failure_exit1(self):
        rc, out = self.cli("release-check", "v1.11.0")
        self.assertEqual(rc, 1, out)
        self.assertIn("找不到分支", out)
        rc, out = self.release("--tag", get=broken_get)
        self.assertEqual(rc, 1, out)
        self.assertFalse(self.remote_has_tag())

    def test_release_tag_push_failure_exit1_no_local_tag(self):
        self.synced_release_branch()
        rc, out = self.cli("release-check", "v1.10.0", "--tag", "--push-url", os.path.join(self.tmp, "nope.git"))
        self.assertEqual(rc, 1, out)
        self.assertIn(f"push {self.TAG} 失敗", out)
        self.assertNotIn(self.TAG, self.g(self.ci, "tag"))
        self.assertFalse(self.remote_has_tag())


if __name__ == "__main__":
    unittest.main()
