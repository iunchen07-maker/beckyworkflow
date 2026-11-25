#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
九支檢查的驗收測試：每支都驗「合規的待辦清單 App 過」與「故意違規（含檔尾）擋得住」。
在暫存 git repo 把腳本裝到安裝位置（Spec/.convert_tools/、ci/）再跑，不連網。
跑法（在 recipes/spec-ci-gates/）：python3 -m unittest discover -s test -p 'test_*.py'
腳本用範例常數；專案改過常數後，改用配方「啟用前 checklist」的負向測試。
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = "Spec/.convert_tools"
LINTS = ("glossary_lint", "prose_lint", "qualifier_guard", "numbering_lint",
         "notification_lint", "mockup_lint", "commit_issue_check")
ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1",
       "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}

GLOSSARY = """# Glossary

## 核心名詞定義

| 中文 | 英文 | 定義 |
|---|---|---|
| 任務 | Task | 清單裡的一件事 |
| 清單 | List | 任務的集合 |
| 封存 | Archive | 收起、唯讀 |
| 待辦清單 App | Todo App | 本產品 |
| 協作者 | Collaborator | 可編輯清單的人 |

## 禁用名詞對照表

| ❌ 禁用 | ✅ 改用 | 說明 |
|---|---|---|
| 待辦 / 工作項目 | 任務 | 統一用詞 |
| 歸檔／收納 | 封存 | 全形分隔也要切開 |
| `task_closed`（舊值） | 已完成 | 出處註記仍是硬門 |
| 關閉（指任務時） | 完成 | 只在任務脈絡禁用 |
| 把「完成」當成封存 | 完成／封存 | 兩者不同 |
"""

TASKS = """---
last_updated: 1999-01-02
---
# 2. 任務管理

## US-T1.1 建立任務

### US-T1.1.1 模組概述

待辦清單 App 的擁有者與協作者可建立任務。僅擁有者可封存清單。到期前 24 小時提醒一次。
詳見 Chapter 2。

### US-T1.1.2 驗收條件

- **AC-1**：標題必填。
- **AC-2**：已退役（保留編號）
- **AC-3**：標題最多 100 字元。

## US-T1.2 週期任務 — 已移至 Deferred/週期任務.md（保留編號）

## US-T1.3 完成任務

### US-T1.3.1 模組概述

檢視者不可完成任務。
"""

NOTIF = """# 5. 通知

## 全域規則

寄給清單成員。

| 編號 | 名稱 | 觸發 | 收件人 | 內文 | 對應 |
|---|---|---|---|---|---|
| **N-1** | 任務到期 | 到期前 | 協作者 | 任務「甲」將到期，請盡快完成。<br>🔗 <a href="/t?id=1">查看任務</a><br><br>Task A is due soon. Please complete it.<br>🔗 <a href="/t?id=1">View task</a> | US-T1.1 |
| N-2 | 已移至 Deferred/週期任務.md（保留編號） |
"""

DEFERRED = """保留編號：US-T1.2、N-2
關鍵詞：週期任務、Repeat-task

## US-T1.2 週期任務（拍板，1999 年）

本次不實作。
"""

DECISION = """---
id: D-0001
date: 1999-01-02
changes: [US-T1.1, N-1, 05_Notifications#全域規則]
supersedes: []
status: active
source: my-org/todo-app#8
milestone:
---
# 建立任務與提醒

## 結論
可建立任務。
## Why
基本功能。
## 否決的方案
無
## 推翻了什麼
無
"""

MOCKUP = """<!doctype html><html><head><title>任務清單</title>
<style>.card{border-radius:4px}</style></head><body>
<div class="spec-bar">§US-T1.1 建立任務</div>
<main>
<button data-action="save-task" data-testid="task-save" data-spec="儲存任務（§US-T1.1.1）">儲存</button>
<button data-action="zoom-in" data-testid="zoom" data-chrome="true" data-spec="放大">＋</button>
</main>
</body></html>
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="spec-ci-"))
        self.addCleanup(shutil.rmtree, self.root)
        for n in LINTS:
            self.install(n + ".py", TOOLS)
        self.install("decisions.py", "ci")
        self.write("Spec/Glossary.md", GLOSSARY)
        self.write("Spec/02_任務管理.md", TASKS)
        self.write("Spec/05_Notifications.md", NOTIF)
        self.write("Spec/Deferred/週期任務.md", DEFERRED)
        self.write("Spec/BACKLOG.md", "- 週期任務 → Deferred/週期任務.md（my-org/todo-app#9）\n")
        self.write("Spec/memory/D-0001_建立任務.md", DECISION)
        self.write("HTML設計稿/定案/T1-task-list.html", MOCKUP)
        self.write("HTML設計稿/討論中/L1-list.html", MOCKUP)
        self.g("init", "-q", "-b", "main")
        self.g("config", "user.name", "t")
        self.g("config", "user.email", "t@t")
        self.g("config", "commit.gpgsign", "false")
        self.base = self.commit("spec: 起始（my-org/todo-app#8）\n\nVerified-by: phase0-spec-verifier")

    def install(self, name, to):
        dst = os.path.join(self.root, to)
        os.makedirs(dst, exist_ok=True)
        shutil.copy(os.path.join(SRC, name), dst)

    def path(self, rel):
        return os.path.join(self.root, rel)

    def write(self, rel, text):
        os.makedirs(os.path.dirname(self.path(rel)), exist_ok=True)
        with open(self.path(rel), "w", encoding="utf-8") as f:
            f.write(text)

    def read(self, rel):
        with open(self.path(rel), encoding="utf-8") as f:
            return f.read()

    def append(self, rel, text):
        self.write(rel, self.read(rel) + text)

    def replace(self, rel, a, b):
        t = self.read(rel)
        self.assertIn(a, t)
        self.write(rel, t.replace(a, b))

    def g(self, *args):
        return subprocess.run(["git", "-C", self.root, *args], env=ENV, check=True,
                              capture_output=True, text=True).stdout.strip()

    def commit(self, msg):
        self.g("add", "-A")
        self.g("commit", "-q", "--allow-empty", "-m", msg)
        return self.g("rev-parse", "HEAD")

    def run_script(self, script, *args, **env):
        r = subprocess.run([sys.executable, self.path(script), *args], cwd=self.root,
                           env={**ENV, **env}, capture_output=True, text=True)
        self.assertNotIn("Traceback", r.stderr, r.stderr)
        return r.returncode, r.stdout + r.stderr

    def lint(self, name, *args):
        return self.run_script(f"{TOOLS}/{name}.py", *args)

    def ok(self, res, *texts):
        self.assertEqual(res[0], 0, res[1])
        for t in texts:
            self.assertIn(t, res[1])

    def bad(self, res, *texts):
        self.assertEqual(res[0], 1, res[1])
        for t in texts:
            self.assertIn(t, res[1])


SPEC = "Spec/02_任務管理.md"


def n_lines(text):
    return text.count("\n")


class GlossaryTest(Base):
    def test_compliant(self):
        self.ok(self.lint("glossary_lint", "--all"), "0 處違規", "無結構問題", "關閉")

    def test_violations_at_end_of_file(self):
        self.append(SPEC, "新增一筆待辦。\n收納清單。\n狀態 task_closed。\n")
        n = n_lines(TASKS)
        self.bad(self.lint("glossary_lint", "--banned"), f"{SPEC}:{n + 1}", "「待辦」",
                 f"{SPEC}:{n + 2}", "「收納」", "「task_closed」", "共 3 處")

    def test_contextual_and_narrative_only_advise(self):
        self.append(SPEC, "關閉視窗。把「完成」當成封存是錯的。\n")
        self.ok(self.lint("glossary_lint", "--banned"))

    def test_text_after_banned_table_still_guarded(self):
        self.append(SPEC, "\n## 禁用名詞對照表\n\n| ❌ 禁用 | ✅ 改用 |\n|---|---|\n| 待辦 | 任務 |\n\n歸檔清單。\n")
        res = self.lint("glossary_lint", "--banned")
        self.bad(res, "「歸檔」", "共 1 處")

    def test_unclosed_frontmatter_does_not_hide_file(self):
        self.write("Spec/06_x.md", "---\n# 6. x\n\n歸檔清單。\n")
        self.bad(self.lint("glossary_lint", "--banned"), "06_x.md:4")

    def test_pragma_and_waiver(self):
        self.append(SPEC, "舊稱待辦。<!-- glossary-lint: allow 待辦 -->\n")
        self.write("HTML設計稿/定案/T2.html", "<title>待辦</title>\n")
        self.bad(self.lint("glossary_lint", "--banned"), "T2.html:1", "共 1 處")
        self.write(f"{TOOLS}/glossary_lint_waivers.txt", "# 註解\nHTML設計稿/定案/T2.html:*:待辦\n")
        self.ok(self.lint("glossary_lint", "--banned"))

    def test_structure(self):
        self.replace("Spec/Glossary.md", "| 清單 | List", "| 待辦 | List")
        self.bad(self.lint("glossary_lint", "--structure"), "同時被定義又被禁用：「待辦」")
        self.replace("Spec/Glossary.md", "## 核心名詞定義", "## 名詞")
        self.bad(self.lint("glossary_lint", "--structure"), "缺必要標頭")

    def test_missing_glossary(self):
        os.remove(self.path("Spec/Glossary.md"))
        self.bad(self.lint("glossary_lint", "--banned"), "找不到")


class ProseTest(Base):
    def test_compliant(self):
        self.ok(self.lint("prose_lint", "--all", "--diff", self.base, "--check-baseline-shrink", self.base),
                "0 處新違規")

    def test_every_rule_at_end_of_file(self):
        for line, rule in (("2099年7月起生效。", "H1"), ("期限 2099/7/1。", "H1"), ("擁有者已拍板。", "H2"),
                           ("議題 7 的結論。", "H2"), ("提醒暫緩。", "H3"), ("暫不支援子任務。", "H3"),
                           ("本年度不提供匯出。", "H3"), ("匯出另議。", "H3"),
                           ("## US-T1.4 匯出（後續版本）", "H4"), ("原因：避免誤刪。", "H5"),
                           ("拍板 <!-- prose-lint: allow -->", "P1"),
                           ("拍板 <!-- prose-lint: allow example: 沿用 -->", "P1"),
                           ("拍板 <!-- prose-lint: allow other: 範例值 -->", "P1")):
            with self.subTest(line=line):
                self.write(SPEC, TASKS + line + "\n")
                loc = f"{SPEC}:{n_lines(TASKS) + 1} [{rule}]"
                self.bad(self.lint("prose_lint", "--all"), loc)
                self.bad(self.lint("prose_lint", "--diff", self.base), loc)

    def test_whole_deferral_list_of_rulebook(self):
        rulebook = os.path.join(SRC, "..", "..", "workflow", "phase-0-spec-update.md")
        with open(rulebook, encoding="utf-8") as f:
            m = re.search(r"\*\*延後字樣清單\*\*（[^）]*）：([^。]+)。", f.read())
        words = m.group(1).split("、")
        self.assertGreaterEqual(len(words), 10)
        for w in words:
            with self.subTest(w=w):
                self.write(SPEC, TASKS + f"這功能{w}提供。\n")
                self.bad(self.lint("prose_lint", "--all"), "[H3]")

    def test_allowed(self):
        self.append(SPEC, "按鈕「暫不提醒」。<!-- prose-lint: allow ui-copy: 按鈕文字 -->\n"
                          "```\n拍板\n```\n"
                          "### US-T1.3.2 匯出 — 已移至 Deferred/匯出.md（保留編號）\n")
        self.ok(self.lint("prose_lint", "--all"))

    def test_diff_only_new_lines_and_bad_base_fails_closed(self):
        self.append(SPEC, "存量拍板。\n")
        old = self.commit("存量")
        self.append(SPEC, "乾淨的一行。\n")
        self.ok(self.lint("prose_lint", "--diff", old))
        self.bad(self.lint("prose_lint", "--diff", "no-such-ref"), "git diff 失敗")

    def test_baseline_only_shrinks(self):
        self.append(SPEC, "存量拍板。\n")
        self.bad(self.lint("prose_lint", "--all"))
        self.ok(self.lint("prose_lint", "--write-baseline"), "1 筆")
        self.ok(self.lint("prose_lint", "--all", "--check-baseline-shrink", self.base), "首次引入")
        head = self.commit("baseline")
        self.write(SPEC, self.read(SPEC).replace("# 2. 任務管理\n", "# 2. 任務管理\n\n多一行。\n"))
        self.ok(self.lint("prose_lint", "--all"))                   # 行移動不失效
        self.append(SPEC, "又一筆拍板。\n")
        self.bad(self.lint("prose_lint", "--all"), "又一筆")
        self.ok(self.lint("prose_lint", "--write-baseline"), "2 筆")
        self.bad(self.lint("prose_lint", "--all", "--check-baseline-shrink", head), "新增 baseline 項")


class QualifierTest(Base):
    def test_nothing_flagged(self):
        self.replace(SPEC, "標題必填", "任務標題必填")
        self.ok(self.lint("qualifier_guard", "--diff", self.base), "限定詞／數字有變 0 對")

    def test_flags_but_never_blocks(self):
        self.replace(SPEC, "僅擁有者可封存清單。到期前 24 小時", "擁有者可封存清單。到期前 48 小時")
        self.ok(self.lint("qualifier_guard", "--diff", self.base), "限定詞變少：僅×1", "少了 24", "多了 48", SPEC)

    def test_last_line_and_lost_id(self):
        self.replace(SPEC, "檢視者不可完成任務。", "檢視者可完成任務。")
        self.ok(self.lint("qualifier_guard", "--diff", self.base),
                "限定詞變少：不可×1", f"{SPEC}:{n_lines(TASKS)}")
        self.replace("Spec/05_Notifications.md", "| US-T1.1 |", "| — |")
        self.ok(self.lint("qualifier_guard", "--diff", self.base), "引用 id 不見：US-T1.1")

    def test_removed_history_label_is_not_flagged(self):
        self.replace(SPEC, "標題必填。", "標題必填（議題 7 已拍板定案）。")
        b = self.commit("x")
        self.replace(SPEC, "標題必填（議題 7 已拍板定案）。", "標題必填。")
        self.ok(self.lint("qualifier_guard", "--diff", b), "有變 0 對")


class NumberingTest(Base):
    def test_compliant(self):
        self.ok(self.lint("numbering_lint"), "0 處違規")

    def test_duplicate_at_end_of_file(self):
        self.append(SPEC, "\n## US-T1.1 又一個\n")
        self.bad(self.lint("numbering_lint"), f"{SPEC}:{n_lines(TASKS) + 2}", "US-T1.1 重複")

    def test_ac_gap_and_duplicate(self):
        self.replace(SPEC, "- **AC-2**：已退役（保留編號）\n", "")
        self.bad(self.lint("numbering_lint"), "缺 AC：[2]")
        self.append(SPEC, "\n### US-T1.3.2 驗收條件\n\n- **AC-1**：甲。\n- **AC-1**：乙。\n")
        self.bad(self.lint("numbering_lint"), "AC 重複：[1]")

    def test_reserved_numbers_not_reused(self):
        self.append("Spec/05_Notifications.md", "| N-2 | 新通知 | 觸發 | 收件人 | 內文 | US-T1.1 |\n")
        self.write("Spec/03_其他.md", "# 3. 其他\n\n## US-T1.2 新功能\n")
        self.bad(self.lint("numbering_lint"), "N-2 是保留編號", "US-T1.2 是保留編號", "03_其他.md:3")

    def test_retired_marker_on_next_line_reuse_in_other_file(self):
        shutil.rmtree(self.path("Spec/Deferred"))
        self.append(SPEC, "\n## US-T7.1 舊功能\n\n已退役（保留編號）\n\n## US-T7.2 現行\n\n保留編號的規則見原則 1。\n")
        self.ok(self.lint("numbering_lint"), "0 處違規")              # 佔位本身不誤報
        self.write("Spec/03_其他.md", "# 3. 其他\n\n## US-T7.1 新功能\n")
        self.bad(self.lint("numbering_lint"), "03_其他.md:3 US-T7.1 是保留編號", "1 處違規")

    def test_same_line_marker_without_deferred_dir(self):
        shutil.rmtree(self.path("Spec/Deferred"))
        self.ok(self.lint("numbering_lint"))
        self.write("Spec/03_其他.md", "# 3. 其他\n\n## §US-T1.2 新功能\n")
        self.bad(self.lint("numbering_lint"), "US-T1.2 是保留編號")

    def test_section_sign_heading_same_as_plain(self):
        self.append(SPEC, "\n## §US-T7.1 甲\n\n## §US-T7.1 乙\n")
        self.bad(self.lint("numbering_lint"), "US-T7.1 重複")
        self.write(SPEC, TASKS + "\n## US-T7.1 甲\n\n## §US-T7.1 乙\n")
        self.bad(self.lint("numbering_lint"), "US-T7.1 重複")
        self.replace(DEC, "[US-T1.1,", "[US-T7.1,")
        self.ok(self.run_script("ci/decisions.py", "check"))

    def test_order_reports_but_strict_blocks(self):
        self.append(SPEC, "\n## US-T1.0 補節\n")
        self.ok(self.lint("numbering_lint"), "US-T1.0 排在 US-T1.3 後面")
        self.bad(self.lint("numbering_lint", "--strict-order"), "US-T1.0")


class NotificationTest(Base):
    def test_compliant(self):
        self.ok(self.lint("notification_lint"), "1 封信", "共 0 項")

    def test_flags_last_row_but_never_blocks(self):
        self.append("Spec/05_Notifications.md",
                    '| **N-3** | 封存 | 封存後 | 協作者 | 清單已封存，請確認。<br>🔗 <a href="/t?id=2">開啟任務</a>'
                    '<br><br>The list is archived.<br><br><a href="/t?id=2">View task</a> | US-T1.1 |\n')
        self.ok(self.lint("notification_lint"), "N-3：🔗 連結行數不對稱（中 1 / 英 0）",
                "N-3：中文行動提示句比英文多", "「查看任務」← N-1", "「開啟任務」← N-3")

    def test_missing_target(self):
        self.ok(self.lint("notification_lint", "--path", "Spec/none.md"), "找不到")


FINAL, WIP = "HTML設計稿/定案/T1-task-list.html", "HTML設計稿/討論中/L1-list.html"


class MockupTest(Base):
    def test_selftest_installed_and_in_recipe(self):
        self.ok(self.lint("mockup_lint", "--selftest"), "案全過")
        r = subprocess.run([sys.executable, os.path.join(SRC, "mockup_lint.py"), "--selftest"], env=ENV)
        self.assertEqual(r.returncode, 0)

    def test_compliant(self):
        self.ok(self.lint("mockup_lint", "--all"), "0 處違規", "掃描 2 檔")
        self.ok(self.lint("mockup_lint", "--deferred"), "0 處違規")
        self.ok(self.lint("mockup_lint", "--file", WIP))
        self.ok(self.lint("mockup_lint", "--audit", WIP), "save-task", "US-T1.1.1")

    def test_violations(self):
        for html, rule in (("<p>依 §US-T1.1</p>", "R1"), ("<p>狀態task_open</p>", "R1"), ("<p>AC-3</p>", "R1"),
                           ("<p>待拍</p>", "R1"), ('<p style="box-shadow:0 0 1px">x</p>', "R2"),
                           ("<style>a{box-shadow:none}b{box-shadow:0 0 1px}</style>", "R2"),
                           ('<a data-action="x" data-spec="US-T1.1">x</a>', "R3"),
                           ('<a data-testid="task-save">x</a>', "R3"),
                           ("<script>h+='<i>task_done</i>';</script>", "R1·js")):
            with self.subTest(html=html):
                self.write(WIP, MOCKUP + html + "\n")             # 檔尾（</html> 之後）也要抓到
                self.bad(self.lint("mockup_lint", "--all"), f"[{rule}]", f"{WIP}:{n_lines(MOCKUP) + 1}")
                self.bad(self.lint("mockup_lint", "--file", WIP), f"[{rule}]")

    def test_r5_advisory_by_default(self):
        self.append(WIP, '<a data-action="sort" data-testid="s" data-spec="排序">x</a>\n')
        self.ok(self.lint("mockup_lint", "--all"), "[R5]", "只報不擋")
        self.bad(self.lint("mockup_lint", "--audit", WIP))
        self.replace(f"{TOOLS}/mockup_lint.py", "R5_BLOCKS = False", "R5_BLOCKS = True")
        self.bad(self.lint("mockup_lint", "--all"), "R5: 1")

    def test_deferred_words_not_exempt_by_baseline(self):
        self.append(FINAL, "<p>設定週期任務</p>\n")
        self.ok(self.lint("mockup_lint", "--all"))
        loc = f"{FINAL}:{n_lines(MOCKUP) + 1}"
        self.bad(self.lint("mockup_lint", "--deferred"), "[R6]", loc)
        self.write(f"{TOOLS}/mockup_lint_baseline.txt", FINAL + "\n")
        self.bad(self.lint("mockup_lint", "--deferred"), loc)
        self.bad(self.lint("mockup_lint", "--file", FINAL), loc)
        self.write(FINAL, MOCKUP + '<section data-spec="延後功能，見 Spec/Deferred/週期任務.md">\n<p>週期任務</p></section>\n')
        self.ok(self.lint("mockup_lint", "--deferred"))

    def test_deferred_file_needs_keywords(self):
        self.write("Spec/Deferred/匯出.md", "保留編號：US-T9.1\n\n內容\n")
        self.bad(self.lint("mockup_lint", "--deferred"), "Spec/Deferred/匯出.md:2")

    def test_baseline_only_final(self):
        self.append(FINAL, "<p>§US-T1.1</p>\n")
        self.ok(self.lint("mockup_lint", "--update-baseline"), "收錄 1 檔")
        self.ok(self.lint("mockup_lint", "--all"), "豁免跳過 1 檔")
        self.append(WIP, "<p>§US-T1.1</p>\n")
        self.bad(self.lint("mockup_lint", "--update-baseline"), "不得進 baseline")
        self.bad(self.lint("mockup_lint", "--all"), WIP)

    def test_baseline_rejects_wip_entry(self):
        self.append(WIP, "<p>§US-T1.1</p>\n")
        for entry in (WIP, "HTML設計稿/定案/../討論中/L1-list.html"):
            self.write(f"{TOOLS}/mockup_lint_baseline.txt", entry + "\n")
            for args in (["--all"], ["--file", WIP], ["--check-baseline-shrink", self.base]):
                self.bad(self.lint("mockup_lint", *args), "不得列入")

    def test_baseline_shrink(self):
        b = f"{TOOLS}/mockup_lint_baseline.txt"
        self.write(b, FINAL + "\n")
        self.ok(self.lint("mockup_lint", "--check-baseline-shrink", self.base), "首次引入")
        head = self.commit("baseline")
        self.ok(self.lint("mockup_lint", "--check-baseline-shrink", head), "沒有新增項")
        self.append(b, "HTML設計稿/定案/T2.html\n")
        self.bad(self.lint("mockup_lint", "--check-baseline-shrink", head), "T2.html")
        self.write(b, "")
        self.ok(self.lint("mockup_lint", "--check-baseline-shrink", head))
        self.bad(self.lint("mockup_lint", "--check-baseline-shrink", "no-such"), "找不到")

    @unittest.skipUnless(shutil.which("jq"), "需要 jq")
    def test_local_hook(self):
        with open(os.path.join(SRC, "claude-settings.hook.json"), encoding="utf-8") as f:
            cmd = json.load(f)["hooks"]["PostToolUse"][0]["hooks"][0]["command"]

        def hook(rel):
            return subprocess.run(["sh", "-c", cmd], env=ENV, capture_output=True, text=True,
                                  input=json.dumps({"tool_input": {"file_path": self.path(rel)}}))
        self.assertEqual(hook(WIP).returncode, 0)
        self.assertEqual(hook(SPEC).returncode, 0)
        self.append(WIP, "<p>§US-T1.1</p>\n")
        r = hook(WIP)
        self.assertEqual(r.returncode, 2)
        self.assertIn("[R1]", r.stderr)


class CommitIssueTest(Base):
    def check(self):
        return self.lint("commit_issue_check", "--range", f"{self.base}..HEAD")

    def test_compliant(self):
        self.append(SPEC, "甲。\n")
        self.commit("spec: 甲（my-org/todo-app#8）\n\nVerified-by: phase0-spec-verifier")
        self.write("src/app.py", "")
        self.commit("code 不管")
        self.append(f"{TOOLS}/prose_lint.py", "\n")
        self.commit("工具不管")
        res = self.check()
        self.ok(res, "全部帶工作項", "1 個動到")
        self.assertNotIn("⚠", res[1])

    def test_missing_or_short_ref_blocks_even_in_last_commit(self):
        self.append(SPEC, "甲。\n")
        self.commit("spec: 甲（my-org/todo-app#8）")
        for i, ref in enumerate(("", "app#8", "#8", "other/my-org/todo-app#8")):
            self.append(FINAL, f"<!-- {i} -->\n")
            self.commit(f"mockup {i} {ref}")
        self.bad(self.check(), "4 個 commit 缺", "mockup 0", "mockup 3")

    def test_warnings_do_not_block(self):
        self.append(SPEC, "甲。\n")
        self.commit("spec（my-org/todo-app#8、my-org/todo-app#9）")
        self.ok(self.check(), "帶了 2 個工作項", "Verified-by")


DEC = "Spec/memory/D-0001_建立任務.md"
DEC2 = "Spec/memory/1999/D-0002_完成.md"


def dec2(**kw):
    t = DECISION.replace("D-0001", "D-0002")
    for k, v in kw.items():
        t = re.sub(rf"(?m)^{k}:.*$", f"{k}: {v}", t)
    return t


class DecisionsCheckTest(Base):
    def check(self, *a):
        return self.run_script("ci/decisions.py", "check", *a)

    def test_compliant(self):
        self.ok(self.check(), "0 處違規")
        self.write(DEC2, dec2(changes="[US-T1.2, US-T1.3]", source="口頭需求"))   # 延後中的節也認得
        self.commit("d2")
        self.ok(self.check("--base", self.base), "新增／改正文 1 份")

    def test_schema_violations(self):
        for kw, text in (({"changes": "[US-T9.9]"}, "US-T9.9 在 SPEC 找不到"), ({"changes": "[]"}, "changes 是空的"),
                         ({"id": "D-0001"}, "重複"), ({"date": "昨天"}, "不是 YYYY-MM-DD"),
                         ({"source": "todo-app#8"}, "要寫全路徑"), ({"source": ""}, "要寫全路徑"),
                         ({"status": "done"}, "只能是"), ({"supersedes": "[D-0099]"}, "D-0099 不存在"),
                         ({"supersedes": "[D-0001]"}, "仍是 active"), ({"status": "superseded"}, "沒有任何決策整份推翻"),
                         ({"changes": "[US-T1.1]\nretired: [US-T1.2]"}, "延後不是退役")):
            with self.subTest(kw=kw):
                self.write(DEC2, dec2(**kw))
                self.bad(self.check(), text)
        self.write(DEC2, dec2().replace("supersedes: []\n", ""))
        self.bad(self.check(), "缺鍵 supersedes")

    def test_supersede_pair_passes(self):
        self.write(DEC2, dec2(supersedes="[D-0001]"))
        self.replace(DEC, "status: active", "status: superseded")
        self.ok(self.check())

    def test_body_of_new_file_missing_last_section_and_too_big(self):
        self.write(DEC2, dec2().replace("## 推翻了什麼\n無\n", "") + "\n## 影響範圍\n" + "字" * 3000)
        self.commit("d2")
        self.bad(self.check("--base", self.base), "缺段落「## 推翻了什麼」", "不手寫", "超過 8192")
        self.ok(self.check())                                       # 沒給 --base 不查正文

    def test_not_started_is_skipped(self):
        os.remove(self.path(DEC))
        self.ok(self.check(), "跳過")
        self.ok(self.run_script("ci/decisions.py", "views", "--check"), "跳過")


class DecisionsViewsTest(Base):
    def dec(self, *a):
        return self.run_script("ci/decisions.py", *a)

    def test_views_fresh_then_stale(self):
        self.bad(self.dec("views", "--check"), "缺 02_任務管理.md")
        self.ok(self.dec("views"))
        self.ok(self.dec("views", "--check"), "最新")
        self.assertIn("[D-0001](../D-0001_建立任務.md)", self.read("Spec/memory/index/02_任務管理.md"))
        self.write(DEC2, dec2(changes="[US-T1.2]"))
        self.bad(self.dec("views", "--check"), "過期 _deferred.md")
        self.ok(self.dec("views"))
        self.append("Spec/memory/index/02_任務管理.md", "手改\n")     # 檔尾手改
        self.bad(self.dec("views", "--check"), "過期 02_任務管理.md")
        self.ok(self.dec("views"))
        self.write("Spec/memory/index/舊.md", "x")
        self.bad(self.dec("views", "--check"), "多出 舊.md")

    def test_queries(self):
        self.write(DEC2, dec2(supersedes="[D-0001]", changes="[US-T1.1]"))
        self.replace(DEC, "status: active", "status: superseded")
        self.write("Spec/memory/legacy/old.md", "| 1998-01-01 | US-T1.1 | 舊決定 |\n")
        self.ok(self.dec("why", "§US-T1.1"), "D-0002", "← 推翻 D-0001", "legacy/old.md:1")
        self.ok(self.dec("why", "US-T1.2"), "延後中，見 Deferred/週期任務.md")
        self.ok(self.dec("list", "--since", "1999-01-01"), "2 筆")
        self.ok(self.dec("next-id"), "D-0003")
        self.bad(self.run_script("ci/decisions.py", "stamp-milestone", SPEC_SYNC_API_URL="",
                                 SPEC_SYNC_API_TOKEN=""), "未設定")

    def test_runs_from_recipe_folder(self):
        for args in (["decisions.py", "--root", self.root, "check"], ["numbering_lint.py", "--root", self.root],
                     ["prose_lint.py", "--help"], ["qualifier_guard.py", "--help"], ["glossary_lint.py", "--help"],
                     ["notification_lint.py", "--help"], ["commit_issue_check.py", "--help"]):
            r = subprocess.run([sys.executable, os.path.join(SRC, args[0]), *args[1:]], env=ENV,
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
