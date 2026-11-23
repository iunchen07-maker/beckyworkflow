#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spec_at — 依 milestone 還原「該版」的 SPEC（只用標準函式庫）。

SPEC 只有一份、住在 main；版本歸屬看 issue 的 milestone。所以「v1.9.3 的 SPEC」＝
main 上的 SPEC 扣掉所有「屬於更晚 milestone 的 issue」的 commit。做法：

  1. 向 GitLab 查 PROJECT 的 milestone，取版本號（vX.Y.Z，v 可省）
     嚴格大於指定版本的那些；標題不是版本號的（Backlog、補漏…）跳過並列出。
  2. 列出那些 milestone 底下全部 issue（state=all，分頁）→ iid 集合。
  3. 在 <ref>（預設 origin/main）找非 merge、動到 SPEC 範圍（WATCH 減 EXEMPT）、
     訊息用 ISSUE_RE 抓得到該 iid 的 commit。
  4. 在暫存 detached worktree（或 --out DIR）從 <ref> 由新到舊 `git revert --no-commit`。
     衝突 → `revert --abort`、移除 worktree，印出 commit、issue、衝突檔，exit 2。
     例外：衝突只落在 GENERATED（產生的檢視）→ 先留現狀繼續，全部還原完再在結果樹跑
     REGEN_CMD 重產。
  5. 成功 → 印 milestone、納入的較晚 milestone、還原的 commit 表、`git diff --stat`、
     每檔改到的 § 節（HEADING 認得的標題；沒有或沒設 HEADING 時用最近的 Markdown 標題），
     以及結果 SPEC 樹的位置。結果留在 worktree 的 index（未 commit），
     `git -C <DIR> diff HEAD` 可看相對 <ref> 的差異。

沒有 milestone、或 milestone 不是版本號的 issue，其 commit 一律視為「留在 SPEC」。
有設 TRACE_SINCE／UNTRACED_UPTO 時另印「追溯起點以前的 commit 不一定帶 issue」的提醒。

專案設定（PROJECT、ISSUE_RE、WATCH…）不在本檔：同目錄 spec_branches_config.py
（範本 spec_branches_config.example.py；環境變數 SPEC_BRANCHES_CONFIG 可指到別的路徑）。
本檔與 spec_sync.py 的正本集中在 recipes/spec-version-branches/（裝進各專案的是複本），各專案不改。

用法：
  python3 ci/spec_at.py v1.9.3 [--out DIR] [--root REPO] [--ref origin/main]
需要 SPEC_SYNC_API_URL／SPEC_SYNC_API_TOKEN（GitLab 網址與 read_api token）。
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

# ── 專案設定（從 spec_branches_config.py 載入；欄位說明見 spec_branches_config.example.py）──
CONFIG_PATH = os.environ.get("SPEC_BRANCHES_CONFIG") or os.path.join(HERE, "spec_branches_config.py")
REQUIRED = ("PROJECT", "ISSUE_RE", "WATCH")
DEFAULTS = {
    "EXEMPT": (),
    "HEADING": None,
    "GENERATED": [],
    "REGEN_CMD": [],
    "SPEC_BRANCH_PREFIX": "spec/v",
    "RELEASE_TAG_SUFFIX": "-release",
    "TRACE_SINCE": None,
    "UNTRACED_UPTO": None,
    "NO_CHANGE_MARK": r"SPEC 不用改，§",
    "SPEC_CHANGE_MARK": r"SPEC 變更：",
    "WEBHOOK_ENV": "SPEC_SYNC_WEBHOOK",
}
CONFIGURED = False
PROJECT = ISSUE_RE = WATCH = EXEMPT = HEADING = GENERATED = REGEN_CMD = None
SPEC_BRANCH_PREFIX = RELEASE_TAG_SUFFIX = TRACE_SINCE = UNTRACED_UPTO = None
NO_CHANGE_MARK = SPEC_CHANGE_MARK = WEBHOOK_ENV = None


def _regex(v):
    return re.compile(v, re.M) if isinstance(v, str) else v


def apply_config(cfg):
    """把設定物件（module 或任何有屬性的物件）套到本模組的全域設定。缺必填 → ValueError。"""
    global CONFIGURED, PROJECT, ISSUE_RE, WATCH, EXEMPT, HEADING, GENERATED, REGEN_CMD
    global SPEC_BRANCH_PREFIX, RELEASE_TAG_SUFFIX, TRACE_SINCE, UNTRACED_UPTO, NO_CHANGE_MARK, WEBHOOK_ENV
    global SPEC_CHANGE_MARK
    missing = [k for k in REQUIRED if getattr(cfg, k, None) in (None, "", ())]
    if missing:
        raise ValueError(f"spec_branches_config 缺必填設定：{', '.join(missing)}")
    v = {k: getattr(cfg, k, d) for k, d in DEFAULTS.items()}
    PROJECT = cfg.PROJECT
    ISSUE_RE = _regex(cfg.ISSUE_RE)
    WATCH = tuple(cfg.WATCH)
    EXEMPT = tuple(v["EXEMPT"] or ())
    HEADING = _regex(v["HEADING"]) if v["HEADING"] else None
    GENERATED = list(v["GENERATED"] or [])
    REGEN_CMD = list(v["REGEN_CMD"] or [])
    SPEC_BRANCH_PREFIX = v["SPEC_BRANCH_PREFIX"]
    RELEASE_TAG_SUFFIX = v["RELEASE_TAG_SUFFIX"]
    TRACE_SINCE = v["TRACE_SINCE"]
    UNTRACED_UPTO = tuple(v["UNTRACED_UPTO"]) if v["UNTRACED_UPTO"] else None
    NO_CHANGE_MARK = _regex(v["NO_CHANGE_MARK"]) if v["NO_CHANGE_MARK"] else None
    SPEC_CHANGE_MARK = _regex(v["SPEC_CHANGE_MARK"]) if v["SPEC_CHANGE_MARK"] else None
    WEBHOOK_ENV = v["WEBHOOK_ENV"]
    CONFIGURED = True


def load_config(path=None):
    """載入設定檔並套用；檔案不存在回 False（main 會報錯），內容有誤直接拋例外。"""
    path = path or CONFIG_PATH
    if not os.path.exists(path):
        return False
    spec = importlib.util.spec_from_file_location("spec_branches_config", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    apply_config(mod)
    return True


load_config()


def require_config():
    """未設定 → 回傳錯誤訊息字串；已設定 → None。"""
    if CONFIGURED:
        return None
    return (f"找不到專案設定 {CONFIG_PATH}：從 spec_branches_config.example.py 複製一份填好"
            "（install.sh 會自動建）")


def version_str(v):
    return "v" + ".".join(map(str, v))


VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
MD_HEAD = re.compile(r"^#{1,6}\s+(.*?)\s*$")


def parse_version(title):
    m = VERSION.match((title or "").strip())
    return tuple(int(x) for x in m.groups()) if m else None


# ── GitLab ───────────────────────────────────────────────────
def gitlab_get():
    """回傳 get(path, params) -> (json, next_page)；環境變數不齊回 None。"""
    base = os.environ.get("SPEC_SYNC_API_URL", "")
    token = os.environ.get("SPEC_SYNC_API_TOKEN")
    if not token or not base:
        return None

    def get(path, params):
        url = f"{base.rstrip('/')}/api/v4{path}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"PRIVATE-TOKEN": token})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r), (r.headers.get("X-Next-Page") or "").strip()
    return get


def get_all(get, path, params):
    out, page = [], "1"
    while page:
        data, page = get(path, dict(params, per_page=100, page=page))
        out.extend(data)
    return out


def later_milestones(get, target):
    """(較晚的 milestone 標題（版本序）, 跳過的非版本標題)"""
    proj = "/projects/" + urllib.parse.quote(PROJECT, safe="")
    ms = get_all(get, proj + "/milestones", {"state": "all", "include_ancestors": "true"})
    later, skipped = [], []
    for m in ms:
        v = parse_version(m.get("title"))
        if v is None:
            skipped.append(m.get("title", ""))
        elif v > target:
            later.append((v, m["title"]))
    titles = [t for v, t in sorted(set(later))]
    return titles, sorted(set(skipped)), {m.get("title") for m in ms}


def issues_in(get, titles):
    """{iid: milestone 標題}"""
    proj = "/projects/" + urllib.parse.quote(PROJECT, safe="")
    out = {}
    for t in titles:
        for it in get_all(get, proj + "/issues", {"state": "all", "milestone": t}):
            out[int(it["iid"])] = t
    return out


# ── git ──────────────────────────────────────────────────────
def git(root, *args, check=True):
    r = subprocess.run(["git", "-C", root, "-c", "core.quotepath=off", *args],
                       capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失敗：{r.stderr.strip()}")
    return r


def spec_paths(root, sha):
    out = git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", "-z", "--root", sha).stdout
    return [p for p in out.split("\0") if p and p.startswith(WATCH) and not p.startswith(EXEMPT)]


def scan_commits(root, ref, iids):
    """(要還原的 commit（新到舊）, 動到 SPEC 卻沒帶 issue 的 commit 數)
    每筆 commit＝(sha, 命中的 issue 列表, 標題, 日期)"""
    shas = git(root, "rev-list", "--no-merges", ref).stdout.split()
    hits, untraced = [], 0
    for sha in shas:
        if not spec_paths(root, sha):
            continue
        msg = git(root, "log", "-1", "--format=%cs%n%B", sha).stdout
        date, _, body = msg.partition("\n")
        refs = sorted({int(n) for n in ISSUE_RE.findall(body)})
        if not refs:
            untraced += 1
            continue
        hit = [n for n in refs if n in iids]
        if hit:
            hits.append((sha, hit, body.split("\n", 1)[0], date))
    return hits, untraced


def conflicted(wt):
    return [p for p in git(wt, "diff", "--name-only", "--diff-filter=U").stdout.split("\n") if p]


def is_generated(path):
    return any(path.startswith(g) for g in GENERATED)


def regenerate(wt):
    """在結果樹（cwd）跑 REGEN_CMD 重產 GENERATED，成功就 git add。回傳 CompletedProcess。
    REGEN_CMD 每個元素的 {root}→結果樹絕對路徑、{python}→目前的 python 直譯器。"""
    if not REGEN_CMD:
        return subprocess.CompletedProcess([], 1, "", "REGEN_CMD 未設定，無法重產")
    cmd = [x.format(root=wt, python=sys.executable) for x in REGEN_CMD]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=wt)
    if r.returncode == 0:
        git(wt, "add", "-A", "--", *GENERATED)
    return r


def section_at(lines, n):
    """第 n 行（1 起算）所在的節：最近的 HEADING 標題（取具名群組 id，沒有就取最後一個群組）；
    沒有（或沒設 HEADING）就用最近的 Markdown 標題。"""
    md = None
    for i in range(min(n, len(lines)) - 1, -1, -1):
        m = HEADING.match(lines[i]) if HEADING else None
        if m:
            return "§" + (m.groupdict().get("id") or m.group(m.lastindex or 0))
        if md is None:
            mm = MD_HEAD.match(lines[i])
            if mm:
                md = "#" + mm.group(1)
    return md or "(檔頭)"


HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def changed_sections(wt, path):
    """比對 HEAD（原 ref）與還原後 worktree，回傳該檔改到的節（依出現順序去重）。"""
    if not path.endswith(".md"):
        return []
    old = git(wt, "show", f"HEAD:{path}", check=False).stdout.split("\n")
    p = os.path.join(wt, path)
    new = []
    if os.path.exists(p):
        with open(p, encoding="utf-8") as fh:
            new = fh.read().split("\n")
    out = []
    for ln in git(wt, "diff", "HEAD", "-U0", "--", path).stdout.split("\n"):
        m = HUNK.match(ln)
        if not m:
            continue
        a, b, c, d = (int(x) if x is not None else 1 for x in m.groups())
        if b and old:
            out += [section_at(old, a), section_at(old, a + b - 1)]
        if d and new:
            out += [section_at(new, c), section_at(new, c + d - 1)]
    return list(dict.fromkeys(out))


# ── 主流程 ───────────────────────────────────────────────────
def main(argv=None, get=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("milestone", help="如 v1.9.3")
    ap.add_argument("--out", help="結果 worktree 位置（不可已存在；預設建暫存目錄）")
    ap.add_argument("--root", default=REPO, help="repo 位置（預設本 repo）")
    ap.add_argument("--ref", default="origin/main", help="基準 ref（預設 origin/main）")
    a = ap.parse_args(argv)
    root = os.path.abspath(a.root)
    err = require_config()
    if err:
        print(err)
        return 1

    target = parse_version(a.milestone)
    if target is None:
        print(f"milestone `{a.milestone}` 不是 vX.Y.Z 格式")
        return 1
    get = get or gitlab_get()
    if get is None:
        print("SPEC_SYNC_API_URL／SPEC_SYNC_API_TOKEN 未設定")
        return 1

    titles, skipped, all_titles = later_milestones(get, target)
    iids = issues_in(get, titles)
    base_sha = git(root, "rev-parse", a.ref).stdout.strip()
    hits, untraced = scan_commits(root, a.ref, iids)

    print(f"spec_at：{a.milestone}（基準 {a.ref} = {base_sha[:8]}）")
    if a.milestone not in all_titles:
        print(f"  ⚠ GitLab 沒有叫 `{a.milestone}` 的 milestone，仍照版本號比較")
    print(f"  較晚的 milestone：{', '.join(titles) or '（無）'}（共 {len(iids)} 張 issue）")
    if skipped:
        print(f"  跳過非版本號 milestone：{', '.join(skipped)}（其 issue 的 commit 一律留著）")
    if TRACE_SINCE:
        upto = f"版本 ≤ {version_str(UNTRACED_UPTO)} 的結果不完整（過渡期，未追溯）。" if UNTRACED_UPTO else ""
        print(f"  ⚠ {TRACE_SINCE} 以前的 commit 不一定帶 issue 編號，追不到；{upto}")
    print(f"  本 ref 有 {untraced} 個動到 SPEC 範圍的 commit 沒帶 issue。")
    if UNTRACED_UPTO and target <= UNTRACED_UPTO:
        print(f"  ⚠ {a.milestone} ≤ {version_str(UNTRACED_UPTO)}：本次結果屬過渡期，不完整。")

    if a.out:
        wt = os.path.abspath(a.out)
        if os.path.exists(wt):
            print(f"--out {wt} 已存在，請給一個不存在的路徑")
            return 1
    else:
        wt = os.path.join(tempfile.mkdtemp(prefix=f"spec-at-{a.milestone}-"), "tree")
    git(root, "worktree", "add", "-q", "--detach", wt, base_sha)

    def cleanup():
        git(wt, "revert", "--abort", check=False)
        git(root, "worktree", "remove", "--force", wt, check=False)
        git(root, "worktree", "prune", check=False)
        if not a.out:
            try:
                os.rmdir(os.path.dirname(wt))
            except OSError:
                pass

    print(f"\n待還原 {len(hits)} 個 commit（新到舊）：")
    if hits:
        print("| sha | 日期 | issue | milestone | 標題 |\n|---|---|---|---|---|")
        for sha, refs, subject, date in hits:
            print(f"| {sha[:8]} | {date} | {', '.join('#' + str(n) for n in refs)} | "
                  f"{', '.join(sorted({iids[n] for n in refs}))} | {subject} |")

    regen = False
    for sha, refs, subject, _ in hits:          # rev-list 順序＝新到舊
        r = git(wt, "revert", "--no-commit", "--no-edit", sha, check=False)
        if r.returncode != 0:
            files = conflicted(wt)
            if files and all(is_generated(f) for f in files):
                # 只撞產生的檢視：先留現狀，全部還原完再用 REGEN_CMD 重產
                git(wt, "checkout", "--ours", "--", *files)
                git(wt, "add", "--", *files)
                git(wt, "revert", "--quit")
                regen = True
                continue
            print(f"\n✗ 還原 {sha[:8]} 衝突（{', '.join(f'{PROJECT}#{n}' for n in refs)}）｜{subject}")
            for f in files or ["（git 未列出衝突檔）"]:
                print(f"    {f}")
            if not files:
                print("    " + (r.stderr.strip() or r.stdout.strip()).replace("\n", "\n    "))
            cleanup()
            print("已 abort 並移除暫存 worktree，沒有留下半成品。")
            return 2

    print(f"\n✓ 還原 {len(hits)} 個 commit，無衝突")
    if regen:
        gen = "、".join(GENERATED)
        r = regenerate(wt)
        if r.returncode == 0:
            print(f"  {gen} 曾衝突（產生的檢視），已在還原後的樹跑 REGEN_CMD 重產")
        else:
            print(f"  ⚠ {gen} 曾衝突且重產失敗，內容不可信：{(r.stdout + r.stderr).strip()}")

    stat = git(wt, "diff", "HEAD", "--stat").stdout.rstrip()
    print("\n差異（相對基準）：\n" + (stat or "  （無）"))
    files = [p for p in git(wt, "diff", "HEAD", "--name-only").stdout.split("\n") if p]
    if files:
        print("\n改到的節：")
        for p in files:
            secs = changed_sections(wt, p)
            print(f"  {p}" + (f"：{'、'.join(secs)}" if secs else ""))
    print(f"\n結果 SPEC 樹：{wt}（detached、改動在 index 未 commit）")
    print(f"  看差異：git -C {wt} diff HEAD")
    print(f"  用完移除：git -C {root} worktree remove --force {wt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
