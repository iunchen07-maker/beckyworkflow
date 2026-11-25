#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
commit_issue_check — 動到 SPEC／mockup 的 commit 訊息必須寫出工作項全路徑
`<group>/<project>#<編號>`（短寫、裸編號不算）。

檢查 range 內每個非 merge commit；改到 WATCH（扣掉 EXEMPT）就要求訊息帶工作項。
  * 缺 → exit 1。口頭需求也先開工作項再 commit，沒有豁免字樣。
  * 帶兩個以上不同工作項 → 只警告（規則是一個 commit 對一個工作項）。
  * 動到 Spec/ 卻沒有 trailer `Verified-by: <agent 或人名>` → 只警告。trailer 寫在訊息最後一段、
    一行一個，寫實際親核這次改動的 agent 或人（例：`Verified-by: phase0-spec-verifier`）。

用法：
  python3 Spec/.convert_tools/commit_issue_check.py --range origin/main..HEAD
exit 0＝全過；exit 1＝有 commit 缺工作項。
"""
import argparse
import re
import subprocess
import sys

# ── 專案常數 ──────────────────────────────────────────────
PROJECT = "my-org/todo-app"                     # 工作項所在的 GitLab 專案路徑
ISSUE_RE = re.compile(r"(?<![\w./-])" + re.escape(PROJECT) + r"#(\d+)(?!\d)")
SPEC = "Spec/"
WATCH = (SPEC, "HTML設計稿/")
EXEMPT = ("Spec/.convert_tools/",)              # 工具本身不是 SPEC

VERIFIED_RE = re.compile(r"^Verified-by:[ \t]*\S", re.M | re.I)


def git(*args):
    return subprocess.run(["git", "-c", "core.quotepath=off", *args],
                          capture_output=True, text=True, check=True).stdout


def touched(sha):
    out = git("diff-tree", "--no-commit-id", "--name-only", "-r", "-z", "--root", sha)
    return [p for p in out.split("\0") if p and p.startswith(WATCH) and not p.startswith(EXEMPT)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--range", required=True, help="git revision range，如 origin/main..HEAD")
    a = ap.parse_args()

    shas = git("rev-list", "--no-merges", "--reverse", a.range).split()
    bad, warn, unverified, checked = [], [], [], 0
    for sha in shas:
        files = touched(sha)
        if not files:
            continue
        checked += 1
        msg = git("log", "-1", "--format=%B", sha)
        issues = sorted(set(ISSUE_RE.findall(msg)), key=int)
        subject = msg.split("\n", 1)[0]
        if not issues:
            bad.append((sha, subject, files))
        elif len(issues) > 1:
            warn.append((sha, subject, issues))
        if any(f.startswith(SPEC) for f in files) and not VERIFIED_RE.search(msg):
            unverified.append((sha, subject))

    print(f"commit-issue-check：range {a.range}，{len(shas)} 個非 merge commit，{checked} 個動到 SPEC／mockup")
    for sha, subject, issues in warn:
        print(f"  ⚠ {sha[:8]} 帶了 {len(issues)} 個工作項（一個 commit 應只對一個）："
              f"{', '.join('#' + i for i in issues)}｜{subject}")
    for sha, subject in unverified:
        print(f"  ⚠ {sha[:8]} 動到 Spec/ 但缺 trailer `Verified-by: <agent 或人名>`（提醒，不擋）｜{subject}")
    if bad:
        print(f"\n✗ {len(bad)} 個 commit 缺工作項全路徑 `{PROJECT}#<編號>`：")
        for sha, subject, files in bad:
            more = f" 等 {len(files)} 檔" if len(files) > 1 else ""
            print(f"  {sha[:8]} {subject}\n      → {files[0]}{more}")
        print("\n修法：commit 訊息補上工作項全路徑（口頭需求先開工作項）。已 push 的歷史不改寫。")
        return 1
    print("✓ 全部帶工作項")
    return 0


if __name__ == "__main__":
    sys.exit(main())
