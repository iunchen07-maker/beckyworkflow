#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spec_sync — 把 main 的 commit 同步到各開發中版本的 spec 分支（只用標準函式庫）。

分支模型：main 同時放好幾個版本的 SPEC；每個開發中 milestone 有一條 `spec/vX.Y.Z`
（人從當天 main 開），只放「該版該做的」，給 RD／QA 讀。PM 在該分支打
`spec/vX.Y.Z-release` tag ＝ 該版關閉，之後不再同步（release-check --tag 會在全過時打）。
（分支前綴、release 後綴、issue 專案與抓法、產生檔路徑與重產指令、通知 webhook 變數名都在
同目錄 spec_branches_config.py；本檔與 spec_at.py 是集中維護的正本的複本，各專案不改。）

挑選規則（版本號比較、issue 抓法、milestone 查詢全部沿用 spec_at.py）：
  commit 引用的 PROJECT issue 只要有一張在「比分支版本更晚」的 milestone → 跳過；
  其餘一律 cherry-pick——沒帶 issue、issue 沒 milestone、milestone 不是版本號（Backlog、補漏…）都挑。
  不看路徑（ci/ 等工具改動也挑，分支上的 lint 才跟 main 一致）。
  只走 main 的 first-parent。merge commit 當一個單位：`cherry-pick -m 1`，issue 取 merge 訊息
  ＋被併進來的所有 commit（M^1..M^2）的聯集。
  一律 `cherry-pick -x`；分支上已有 `(cherry picked from commit <sha>)` 的不重挑。

待挑清單（sync 與 check 同一套算法）：
  分支點＝merge-base(分支, main)；main 從分支點到最新的 first-parent commit（由舊到新），
  扣掉分支上已有 -x trailer（沒被撤）的、扣掉屬於更晚 milestone 的。
  分支點以前的 commit 永遠不挑。每次 sync 都重算整份待挑清單依序挑，所以某筆衝突沒解之前，
  每次都停在同一筆、紅燈；不會跳過它去挑後面的。
  「在分支上被 revert 掉」：分支上 merge-base 之後有 commit 訊息帶 `This reverts commit <X>`，
  X 是分支上那筆 cherry-pick 出來的 commit（不是 main 的 sha），就把它 -x trailer 指的 main commit
  視為「已撤」。已撤的照 issue「現在」的 milestone 判：仍屬更晚版本 → 不算缺也不算多；
  不晚於本版 → 回到待挑（sync 依 main 順序再 `cherry-pick -x` 一次，check 報缺）。
  挑→撤→再挑→（再撤）以分支上最後一個動作為準；revert 再被 revert → 恢復成已同步。

子指令：
  sync [--push] [--notify]
      對每條開著的 spec 分支，在暫存 worktree 由舊到新 cherry-pick 待挑清單。
      不帶 --push＝dry run（照樣在暫存 worktree 試挑、會抓到衝突，但不推）。
      衝突 → abort、該分支什麼都不推、exit 2。只撞 GENERATED（產生的檢視）→ 在結果樹跑
      REGEN_CMD 重產後繼續（同 spec_at）。
      舊參數 --range 仍接受但不使用（印一行提示）。
  check [--notify]
      每日比對：列「缺的」（待挑清單裡還沒挑的）與「多的」（挑過了、沒撤、但 issue 現在屬於
      更晚 milestone）。只報告不修。有落差 exit 2。
  release-check vX.Y.Z [--tag] [--notify]
      上線前檢查 spec/vX.Y.Z（不管有沒有 release tag 都照查）：
        ① 分支 vs main 一致（同 check：不缺、不多）。                              ［擋］
        ② milestone vX.Y.Z 每張 issue（state=all）要嘛分支 tip 能到的 commit（含分支點以前、
           開分支時就帶進來的；扣掉被撤的）有一筆帶它（commit 自己的訊息，或分支上 -x trailer
           指回的 main commit 訊息），要嘛 issue 描述或任一則非系統留言有
           SPEC_CHANGE_MARK（預設「SPEC 變更：」）那行帶 `commit <sha>`（7–40 hex，同行可多個，一個合格即可）
           且該 sha 是分支 tip 能到、沒被撤的 commit（或其 -x trailer 指回的 main commit；commit 本身不必帶票），
           要嘛符合 NO_CHANGE_MARK（預設「SPEC 不用改，§」）。都沒有 → 列出。［擋］
           還開著的 issue 另列（參考，不擋）。
        ③ 分支上（分支點以後、沒被撤）沒有 commit 帶「更晚 milestone」的 issue。     ［擋］
        ④ 分支上沒帶 issue 的 commit（參考，不擋）。
      全過 exit 0；任一擋的不過 exit 2。帶 --tag 且全過：在分支最新 commit 打 annotated tag
      `spec/vX.Y.Z-release` 並推（CI 用 SPEC_SYNC_PUSH_TOKEN，同 sync --push；本機 `git push <remote> <tag>`）。
      沒過一律不打 tag。tag 已存在 → 只報告，不重打。

exit：0 正常／2 衝突、落差或上線檢查不過／1 工具錯誤（GitLab API 失敗、git 失敗、推送失敗、設定不齊）。
GitLab API 失敗一律 exit 1，不會當成「沒 milestone → 挑」，也不推任何東西。

環境變數：
  SPEC_SYNC_API_URL／SPEC_SYNC_API_TOKEN   查 milestone（同 spec_at）；CI 裡缺時退用 CI_SERVER_URL／SPEC_SYNC_PUSH_TOKEN
  SPEC_SYNC_PUSH_TOKEN       --push／--tag 用：write_repository。沒設 SPEC_SYNC_API_TOKEN 時也拿來讀 milestone，
                             這時還要 read_api＋能讀 issue 專案。issue 在別的專案時，建議另設
                             SPEC_SYNC_API_TOKEN（read_api）。
  CI_SERVER_HOST／CI_PROJECT_PATH  推送目標 https://oauth2@<host>/<path>.git
  <WEBHOOK_ENV>              --notify 用的聊天工具 incoming webhook（變數名見設定，預設
                             SPEC_SYNC_WEBHOOK）；沒設就只印
  CI_PIPELINE_URL            放進通知訊息
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import spec_at  # noqa: E402
# 專案設定一律用 spec_at.<名稱> 在執行時讀（spec_at 從 spec_branches_config.py 載入；測試可 apply_config 換掉）
from spec_at import is_generated, regenerate, parse_version, git  # noqa: E402

REPO = spec_at.REPO
TRAILER = "(cherry picked from commit "
REVERT_RE = re.compile(r"^This reverts commit ([0-9a-f]{7,40})\b", re.M)
SPEC_CHANGE_SHA_RE = re.compile(r"\bcommit\s+([0-9a-fA-F]{7,40})(?![0-9a-fA-F])")


class ToolError(Exception):
    pass


def proj_path():
    return "/projects/" + urllib.parse.quote(spec_at.PROJECT, safe="")


def issue_refs(text):
    return sorted({int(n) for n in spec_at.ISSUE_RE.findall(text)})


# ── 分支與 milestone ──────────────────────────────────────────
def fetch(root, remote, main):
    pre = spec_at.SPEC_BRANCH_PREFIX
    r = git(root, "fetch", "-q", "--prune", remote,
            f"+refs/heads/{main}:refs/remotes/{remote}/{main}",
            f"+refs/heads/{pre}*:refs/remotes/{remote}/{pre}*",
            f"+refs/tags/{pre}*:refs/tags/{pre}*", check=False)
    if r.returncode != 0:
        raise ToolError(f"git fetch {remote} 失敗：{r.stderr.strip()}")


def open_branches(root, remote):
    """[(版本 tuple, 分支名 spec/vX.Y.Z, 遠端追蹤 ref)]，版本序；有 release tag 的略過。
    回傳 (開著的, 已關閉的分支名)。"""
    pre = spec_at.SPEC_BRANCH_PREFIX
    head = f"refs/remotes/{remote}/"
    refs = [r for r in git(root, "for-each-ref", "--format=%(refname)", head).stdout.split()
            if r.startswith(head + pre)]
    tags = set(git(root, "for-each-ref", "--format=%(refname:strip=2)", "refs/tags/").stdout.split())
    opened, closed = [], []
    for ref in refs:
        name = ref[len(head):]
        v = parse_version(name[len(pre):])
        if v is None:
            continue                      # spec/vnext 之類不是版本分支
        if f"{name}{spec_at.RELEASE_TAG_SUFFIX}" in tags:
            closed.append(name)
        else:
            opened.append((v, name, ref))
    return sorted(opened), sorted(closed)


def later_issue_map(get, min_version):
    """{iid: milestone 標題}，含所有版本號 > min_version 的 milestone。API 失敗 → ToolError。"""
    try:
        titles, _, _ = spec_at.later_milestones(get, min_version)
        return spec_at.issues_in(get, titles)
    except Exception as e:  # noqa: BLE001  任何 API 錯誤都不能退化成「沒 milestone → 挑」
        raise ToolError(f"GitLab API 失敗（{spec_at.PROJECT} milestone／issue）：{e}") from e


def ticket_milestones(get, iids):
    """{iid: milestone 標題或「無」}，給 sync 的表格看；API 失敗 → ToolError。"""
    out = {}
    n = None
    try:
        for n in sorted(iids):
            data, _ = get(f"{proj_path()}/issues/{n}", {})
            out[n] = ((data or {}).get("milestone") or {}).get("title") or "無"
    except Exception as e:  # noqa: BLE001
        raise ToolError(f"GitLab API 失敗（{spec_at.PROJECT}#{n}）：{e}") from e
    return out


def gitlab_get():
    env = os.environ
    if not env.get("SPEC_SYNC_API_URL") and env.get("CI_SERVER_URL"):
        env["SPEC_SYNC_API_URL"] = env["CI_SERVER_URL"]
    if not env.get("SPEC_SYNC_API_TOKEN") and env.get("SPEC_SYNC_PUSH_TOKEN"):
        env["SPEC_SYNC_API_TOKEN"] = env["SPEC_SYNC_PUSH_TOKEN"]
    return spec_at.gitlab_get()


# ── commit ───────────────────────────────────────────────────
def first_parent(root, rng):
    return git(root, "rev-list", "--first-parent", "--reverse", rng).stdout.split()


def commit_info(root, sha):
    """(是否 merge, issue 列表, 標題)。merge 的 issue＝自身訊息＋M^1..M^2 所有 commit 訊息。"""
    parents = git(root, "rev-list", "--parents", "-n1", sha).stdout.split()[1:]
    body = git(root, "log", "-1", "--format=%B", sha).stdout
    text = body
    if len(parents) > 1:
        text += git(root, "log", "--format=%B", f"{parents[0]}..{parents[1]}").stdout
    return len(parents) > 1, issue_refs(text), body.split("\n", 1)[0]


def branch_log(root, branch_ref, main_ref):
    """分支點以後分支上的 commit（新到舊）。回傳 (分支點, recs, undone)：
      recs  ＝[(sha, parent 數, 訊息, [-x trailer 指的 main sha], [revert 指到的 sha 前綴])]
      undone(sha) → 這筆分支 commit 是否已被（本身沒被撤的）分支 revert 撤掉
    revert 訊息的 `This reverts commit <X>` 指的是分支上的 commit。revert 的 revert ＝恢復。"""
    base = merge_base(root, branch_ref, main_ref)
    recs, undone = log_recs(root, f"{base}..{branch_ref}")
    return base, recs, undone


def log_recs(root, rng):
    """rng 內的 commit（新到舊）與撤銷判定。回傳 (recs, undone)，格式同 branch_log。
    revert 只認指向 rng 內 commit 的；undone(sha)＝被某個本身沒被撤的 revert 指到。"""
    out = git(root, "log", "--format=%H%x00%P%x00%B%x01", rng).stdout
    recs = []
    for rec in out.split("\x01"):
        parts = rec.lstrip("\n").split("\x00", 2)
        if len(parts) < 3:
            continue
        sha, parents, body = parts
        trailers = []
        for line in body.split("\n"):
            line = line.strip()
            if line.startswith(TRAILER) and line.endswith(")"):
                trailers.append(line[len(TRAILER):-1].strip())
        recs.append((sha, len(parents.split()), body, trailers, REVERT_RE.findall(body)))
    shas = [r[0] for r in recs]

    def full(short):
        return next((s for s in shas if s.startswith(short)), None)

    targets = {r[0]: {t for t in (full(x) for x in r[4]) if t} for r in recs if r[4]}
    memo = {}

    def undone(sha):
        """被某個「本身沒被撤」的分支 revert 指到 → 已撤（revert 的 revert ＝恢復）。"""
        if sha not in memo:
            memo[sha] = False                         # 防環
            memo[sha] = any(sha in ts and not undone(r) for r, ts in targets.items())
        return memo[sha]

    return recs, undone


def branch_state(root, branch_ref, main_ref):
    """分支點以後分支上的同步狀態。回傳 (分支點, picked, dropped)：
      picked  ＝{main sha: [分支上帶這個 -x trailer、沒被撤的 commit（新到舊）]}，含已撤的 main sha（值為 []）
      dropped ＝分支上每一筆都被 revert 掉的 main sha 集合
    同一個 main sha 可能挑→撤→重挑→再撤：每筆 pick 各自判撤沒撤，最後一個動作是重挑 → 那筆沒被撤
    → 算已同步；最後一個動作是撤 → 每筆都撤了 → dropped。只認 -x trailer 與 revert 指向，
    revert commit 本身沒有 trailer，所以不會重複計。"""
    base, recs, undone = branch_log(root, branch_ref, main_ref)
    picked = {}
    for sha, _, _, trailers, _ in recs:               # 新到舊
        for m in trailers:
            picked.setdefault(m, [])
            if not undone(sha):
                picked[m].append(sha)
    dropped = {m for m, live in picked.items() if not live}
    return base, picked, dropped


def merge_base(root, a, b):
    r = git(root, "merge-base", a, b, check=False)
    if r.returncode != 0:
        raise ToolError(f"{a} 與 {b} 找不到 merge-base")
    return r.stdout.strip()


def is_ancestor(root, a, b):
    return git(root, "merge-base", "--is-ancestor", a, b, check=False).returncode == 0


def classify(refs, later, version, names=None):
    """回傳 (挑不挑, 理由, milestone 欄)。later＝{iid: milestone}（含所有 > 最小開著版本者）；
    names＝{iid: milestone}（只給表格顯示用，可省）。"""
    late = [(n, later[n]) for n in refs if n in later and parse_version(later[n]) > version]
    names = {**(names or {}), **later}
    ms = ", ".join(f"#{n}={names[n]}" for n in refs if n in names) or "—"
    if late:
        return False, "較晚 milestone：" + ", ".join(f"#{n}→{t}" for n, t in late), ms
    if not refs:
        return True, "沒帶 issue", ms
    return True, "無較晚 milestone", ms


# 每筆 commit 對某分支的狀態
SYNCED, EXTRA, DROPPED, ON_BRANCH, PICK, SKIP = "synced", "extra", "dropped", "on-branch", "pick", "skip"


def plan(root, ref, main_ref, version, later, info):
    """分支點到 main 最新的 first-parent commit，逐筆標狀態。info＝{sha: commit_info}（共用快取）。
    回傳 (分支點, [(sha, 狀態, 理由)], picked)。sync 與 check 共用，兩邊算出來的待挑必定一致。"""
    base, picked, dropped = branch_state(root, ref, main_ref)
    rows = []
    for sha in first_parent(root, f"{base}..{main_ref}"):
        if sha not in info:
            info[sha] = commit_info(root, sha)
        ok, why, _ = classify(info[sha][1], later, version)
        if sha in dropped:
            # 已撤的照 issue 現在的 milestone：仍較晚 → 安靜；不晚於本版 → 回待挑（重挑）
            if ok:
                rows.append((sha, PICK, "分支上撤過，issue 現在不晚於本版 → 重挑"))
            else:
                rows.append((sha, DROPPED, "已在分支上 revert（不算缺也不算多）"))
        elif sha in picked:
            rows.append((sha, SYNCED if ok else EXTRA, "已同步（-x trailer）" if ok else why))
        elif is_ancestor(root, sha, ref):
            rows.append((sha, ON_BRANCH, "已在分支（main 併進分支過）"))
        else:
            rows.append((sha, PICK if ok else SKIP, why))
    return base, rows, picked


# ── cherry-pick ──────────────────────────────────────────────
def conflicted(wt):
    return [p for p in git(wt, "diff", "--name-only", "--diff-filter=U").stdout.split("\n") if p]


def pick(wt, sha, is_merge):
    """回傳 None（成功）或衝突檔清單。失敗已 abort。"""
    args = ["cherry-pick", "-x", "--allow-empty", "--keep-redundant-commits"]
    if is_merge:
        args += ["-m", "1"]
    r = git(wt, *args, sha, check=False)
    if r.returncode == 0:
        return None
    files = conflicted(wt)
    if files and all(is_generated(f) for f in files):
        # 只撞產生的檢視：在結果樹跑 REGEN_CMD 重產，再繼續
        if regenerate(wt).returncode == 0:
            c = git(wt, "-c", "core.editor=true", "cherry-pick", "--continue", check=False)
            if c.returncode != 0:
                c = git(wt, "commit", "-q", "--allow-empty", "--no-edit", check=False)
            if c.returncode == 0:
                return None
    git(wt, "cherry-pick", "--abort", check=False)
    return files or [(r.stderr.strip() or r.stdout.strip()).split("\n")[0] or "（git 未列出衝突檔）"]


def push_ref(cwd, push_url, refspec, label):
    """把 refspec 推到 push_url。有 SPEC_SYNC_PUSH_TOKEN 時用 ephemeral credential helper（token 不進 URL／argv）。"""
    token = os.environ.get("SPEC_SYNC_PUSH_TOKEN", "")
    cmd = ["git", "-C", cwd]
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    if token:
        # token 不進 URL／argv／.git/config：push 那一刻由 ephemeral credential helper 讀環境變數
        cmd += ["-c", "credential.helper=",
                "-c", "credential.helper=!f() { echo username=oauth2; echo \"password=$SPEC_SYNC_PUSH_TOKEN\"; }; f"]
    cmd += ["push", "-q", push_url, refspec]
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if r.returncode != 0:
        err = (r.stderr or r.stdout).strip()
        if token:
            err = err.replace(token, "***")
        # 診斷：runner 可能在 git config 放 url.*.insteadOf 把網址換成 CI job token（只報筆數，key 內含 token 不印）
        n = subprocess.run(["git", "-C", cwd, "config", "--get-regexp", r"^url\..*\.insteadof$"],
                           capture_output=True, text=True).stdout.count("\n")
        raise ToolError(f"push {label} 失敗：{err}\n（git config 內 url.*.insteadOf 共 {n} 筆）")


def push(root, wt, branch, push_url):
    push_ref(wt, push_url, f"HEAD:refs/heads/{branch}", branch)


def resolve_push_url(a):
    if a.push_url:
        return a.push_url
    host, path = os.environ.get("CI_SERVER_HOST"), os.environ.get("CI_PROJECT_PATH")
    if not (host and path and os.environ.get("SPEC_SYNC_PUSH_TOKEN")):
        raise ToolError("--push 需要 CI_SERVER_HOST、CI_PROJECT_PATH、SPEC_SYNC_PUSH_TOKEN")
    # 網址帶 username：runner 的 url."https://gitlab-ci-token:…@host/".insteadOf "https://host/" 以字首比對，
    # 帶 oauth2@ 就不會被換成 job token（job token 不能 push → 403）；密碼仍由 credential helper 給
    return f"https://oauth2@{host}/{path}.git"


# ── 通知 ─────────────────────────────────────────────────────
def notify(text, enabled):
    url = os.environ.get("CI_PIPELINE_URL")
    if url:
        text += f"\npipeline：{url}"
    var = spec_at.WEBHOOK_ENV or "SPEC_SYNC_WEBHOOK"
    hook = os.environ.get(var)
    print("\n── 通知 ──\n" + text)
    if not enabled:
        return
    if not hook:
        print(f"（{var} 未設定，只印不送）")
        return
    # payload 格式（form 欄位 payload＝{"text": ...} 的 JSON）依你的聊天工具調整
    data = urllib.parse.urlencode({"payload": json.dumps({"text": text}, ensure_ascii=False)}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(hook, data=data), timeout=30) as r:
            r.read()
    except Exception as e:  # noqa: BLE001  通知失敗不改變結果，只提示
        print(f"⚠ 通知送出失敗：{e}")


# ── sync ─────────────────────────────────────────────────────
def sync_branch(root, a, branch, ref, base, rows, info, names, push_url):
    """回傳 (rc, 通知行或 None)。"""
    todo = [sha for sha, st, _ in rows if st == PICK]
    synced = sum(1 for _, st, _ in rows if st == SYNCED)
    print(f"\n## {branch}（{git(root, 'rev-parse', '--short', ref).stdout.strip()}）："
          f"分支點 {base[:8]}，main 之後 {len(rows)} 個 first-parent commit；"
          f"已同步（-x trailer）{synced} 個不列")
    shown = [r for r in rows if r[1] != SYNCED]
    if shown:
        print("| commit | issue | milestone | 動作 | 理由 | 標題 |\n|---|---|---|---|---|---|")
    for sha, st, why in shown:
        is_merge, refs, subject = info[sha]
        tick = ", ".join(f"#{n}" for n in refs) or "—"
        ms = ", ".join(f"#{n}={names[n]}" for n in refs if n in names) or "—"
        if st == PICK and is_merge:
            why += "（merge，-m 1）"
        print(f"| {sha[:8]} | {tick} | {ms} | {'pick' if st == PICK else 'skip'} | {why} | {subject} |")
    if not todo:
        print("→ 沒有要挑的 commit")
        return 0, None

    wt = os.path.join(tempfile.mkdtemp(prefix="spec-sync-"), "tree")
    git(root, "worktree", "add", "-q", "--detach", wt, ref)
    try:
        for i, sha in enumerate(todo):
            bad = pick(wt, sha, info[sha][0])
            if bad is not None:
                is_merge, refs, subject = info[sha]
                tickets = ', '.join(f'{spec_at.PROJECT}#{n}' for n in refs) or '沒帶 issue'
                print(f"\n✗ {branch}：cherry-pick {sha[:8]} 衝突（{tickets}）｜{subject}")
                for f in bad:
                    print(f"    {f}")
                print(f"  已 abort；{branch} 這次什麼都沒推（排在後面的 {len(todo) - i - 1} 個也沒挑）。")
                msg = (f"⚠ spec-sync：{branch} cherry-pick 衝突，這次沒推任何 commit\n"
                       f"commit {sha[:8]}｜{subject}\n衝突檔：{', '.join(bad)}\n"
                       f"後面還有 {len(todo) - i - 1} 個待挑，解掉這筆之前每次同步都會停在這裡\n"
                       f"處理：git switch {branch} && git pull && "
                       f"git cherry-pick -x{' -m 1' if is_merge else ''} {sha}，解完 git push；"
                       f"之後重跑 spec-branch-sync（或等下一次 main push）會接著挑後面的")
                return 2, msg
        n = len(todo)
        if a.push:
            push(root, wt, branch, push_url)
            print(f"✓ {branch}：挑 {n} 個 commit，已推")
        else:
            print(f"✓ {branch}：挑 {n} 個 commit 無衝突（dry run，未推）")
        return 0, None
    finally:
        git(wt, "cherry-pick", "--abort", check=False)
        git(root, "worktree", "remove", "--force", wt, check=False)
        git(root, "worktree", "prune", check=False)
        try:
            os.rmdir(os.path.dirname(wt))
        except OSError:
            pass


def cmd_sync(a, get):
    root = a.root
    push_url = resolve_push_url(a) if a.push else None
    if not a.no_fetch:
        fetch(root, a.remote, a.main)
    opened, closed = open_branches(root, a.remote)
    print(f"spec-sync：對照 {a.main_ref}，每條分支從分支點重算待挑（{'推送' if a.push else 'dry run'}）")
    if a.range:
        print(f"  （--range {a.range} 已不使用：一律從分支點重算整份待挑清單）")
    print(f"  開著的分支：{', '.join(b for _, b, _ in opened) or '（無）'}")
    if closed:
        print(f"  已 release（不再同步）：{', '.join(closed)}")
    if not opened:
        return 0, []
    g = get()
    later = later_issue_map(g, opened[0][0])            # 先查完 API 才動任何分支
    info, plans = {}, []
    for version, branch, ref in opened:
        base, rows, _ = plan(root, ref, a.main_ref, version, later, info)
        plans.append((branch, ref, base, rows))
    shown = {sha for _, _, _, rows in plans for sha, st, _ in rows if st != SYNCED}
    names = {**ticket_milestones(g, {n for sha in shown for n in info[sha][1]} - set(later)), **later}
    rc, msgs = 0, []
    for branch, ref, base, rows in plans:
        r, msg = sync_branch(root, a, branch, ref, base, rows, info, names, push_url)
        rc = max(rc, r)
        if msg:
            msgs.append(msg)
    return rc, msgs


# ── check ────────────────────────────────────────────────────
def diff_report(root, branch, ref, main_ref, version, later, info, add):
    """分支 vs main 的缺／多（check 與 release-check ① 共用）。用 add(text) 輸出。
    回傳 (是否一致, 分支點)。"""
    base, rows, picked = plan(root, ref, main_ref, version, later, info)
    missing = [(sha, why) for sha, st, why in rows if st == PICK]
    extra = [(sha, why) for sha, st, why in rows if st == EXTRA]
    dropped = [sha for sha, st, _ in rows if st == DROPPED]
    synced = sum(1 for _, st, _ in rows if st in (SYNCED, EXTRA))
    print(f"\n## {branch}：分支點 {base[:8]}，main 之後 {len(rows)} 個 first-parent commit，"
          f"分支上已同步 {synced} 個" + (f"，已在分支上 revert {len(dropped)} 個" if dropped else ""))
    for sha in dropped:
        print(f"  （已撤）{sha[:8]}｜{info[sha][2]}")
    if not missing and not extra:
        print("✓ 一致")
        return True, base
    if missing:
        add(f"缺（該挑沒挑）：{len(missing)} 個")
        for sha, why in missing:
            _, refs, subject = info[sha]
            add(f"  {sha[:8]} {', '.join(f'#{n}' for n in refs) or '—'}｜{subject}｜{why}")
        add("  處理：等下一次 spec-branch-sync（或手動重跑），衝突照該 job 的通知解")
    if extra:
        add(f"多（挑了但現在屬於更晚 milestone）：{len(extra)} 個")
        for sha, why in extra:
            _, refs, subject = info[sha]
            bsha = picked[sha][0]
            add(f"  {sha[:8]} {', '.join(f'#{n}' for n in refs) or '—'}｜{subject}｜{why}")
            add(f"    要從分支撤掉：git switch {branch} && git pull && git revert {bsha} && git push"
                "（日後 issue 改回本版，sync 會自動重挑）")
    return False, base


def cmd_check(a, get):
    root = a.root
    if not a.no_fetch:
        fetch(root, a.remote, a.main)
    opened, closed = open_branches(root, a.remote)
    print(f"spec-check：對照 {a.main_ref}")
    print(f"  開著的分支：{', '.join(b for _, b, _ in opened) or '（無）'}")
    if closed:
        print(f"  已 release（不再檢查）：{', '.join(closed)}")
    if not opened:
        return 0, []
    later = later_issue_map(get(), opened[0][0])
    rc, msgs, info = 0, [], {}
    for version, branch, ref in opened:
        lines = [f"⚠ spec-check：{branch} 與 main 不一致"]

        def add(text):
            print(text)
            lines.append(text)

        ok, _ = diff_report(root, branch, ref, a.main_ref, version, later, info, add)
        if not ok:
            rc = 2
            msgs.append("\n".join(lines))
    return rc, msgs


# ── release-check ────────────────────────────────────────────
def milestone_title(get, version):
    """GitLab 上版本號等於 version 的 milestone 標題（v 可省）；沒有 → ToolError。"""
    ms = spec_at.get_all(get, proj_path() + "/milestones", {"state": "all", "include_ancestors": "true"})
    hits = sorted({m.get("title") for m in ms if parse_version(m.get("title")) == version})
    if not hits:
        raise ToolError(f"{spec_at.PROJECT} 沒有版本號 {spec_at.version_str(version)} 的 milestone")
    return hits[0]


def ticket_texts(get, issue):
    """issue 描述＋每則非系統留言的內文（release-check ② 認標記用）。"""
    notes = spec_at.get_all(get, f"{proj_path()}/issues/{int(issue['iid'])}/notes", {})
    return [issue.get("description") or ""] + [n.get("body") or "" for n in notes if not n.get("system")]


def no_change_marked(texts):
    """任一段符合 NO_CHANGE_MARK → True。"""
    mark = spec_at.NO_CHANGE_MARK
    return mark is not None and any(mark.search(t) for t in texts)


def spec_change_shas(texts):
    """每段裡符合 SPEC_CHANGE_MARK 的那一行，從標記之後取出所有 `commit <sha>`（7–40 hex，
    遇非 hex 就停，例：全形（）。同一行可有好幾個（例：「SPEC 變更：commit X（…）；mockup：commit Y」）。"""
    mark = spec_at.SPEC_CHANGE_MARK
    if mark is None:
        return []
    out = []
    for t in texts:
        for line in t.splitlines():
            m = mark.search(line)
            if m:
                out += SPEC_CHANGE_SHA_RE.findall(line[m.end():])
    return out


def has_commit(root, sha):
    return git(root, "rev-parse", "-q", "--verify", f"{sha}^{{commit}}", check=False).returncode == 0


def tag_exists(root, tag):
    return git(root, "rev-parse", "-q", "--verify", f"refs/tags/{tag}", check=False).returncode == 0


def push_tag(root, a, tag):
    """CI（有 SPEC_SYNC_PUSH_TOKEN＋CI_SERVER_HOST＋CI_PROJECT_PATH）或 --push-url：同 sync --push 的推法；
    否則本機 `git push <remote> <tag>`。"""
    ci = all(os.environ.get(k) for k in ("SPEC_SYNC_PUSH_TOKEN", "CI_SERVER_HOST", "CI_PROJECT_PATH"))
    url = resolve_push_url(a) if (a.push_url or ci) else a.remote
    push_ref(root, url, f"refs/tags/{tag}:refs/tags/{tag}", tag)


def cmd_release_check(a, get):
    root = a.root
    version = parse_version(a.version)
    if version is None:
        raise ToolError(f"`{a.version}` 不是 vX.Y.Z 格式")
    vs = spec_at.version_str(version)
    branch = f"{spec_at.SPEC_BRANCH_PREFIX}{'.'.join(map(str, version))}"
    tag = f"{branch}{spec_at.RELEASE_TAG_SUFFIX}"
    if not a.no_fetch:
        fetch(root, a.remote, a.main)
    ref = f"refs/remotes/{a.remote}/{branch}"
    if not has_commit(root, ref):
        raise ToolError(f"找不到分支 {a.remote}/{branch}")
    tip = git(root, "rev-parse", ref).stdout.strip()
    tagged = tag_exists(root, tag)
    print(f"spec-release-check：{branch}（{tip[:8]}）對照 {a.main_ref}"
          + (f"；⚠ 已有 tag {tag}" if tagged else ""))

    g = get()
    try:
        later = later_issue_map(g, version)
        title = milestone_title(g, version)
        issues = spec_at.get_all(g, proj_path() + "/issues", {"state": "all", "milestone": title})
    except ToolError:
        raise
    except Exception as e:  # noqa: BLE001
        raise ToolError(f"GitLab API 失敗（{spec_at.PROJECT} milestone／issue）：{e}") from e

    lines = [f"⚠ spec-release-check：{branch} 不能上線"]

    def add(text):
        print(text)
        lines.append(text)

    blocking = False
    info = {}
    # ① 分支 vs main
    print("\n### ① 分支 vs main 一致")
    ok, _ = diff_report(root, branch, ref, a.main_ref, version, later, info, add)
    blocking |= not ok

    def live_refs(recs, undone):
        """沒被撤、本身不是 revert、不是 merge 的 commit 與它帶的 issue（自己的訊息＋-x trailer 指回的 main commit）。"""
        out = []
        for sha, nparents, body, trailers, reverts in recs:
            if undone(sha) or reverts or nparents > 1:
                continue
            refs = set(issue_refs(body))
            for m in trailers:
                if has_commit(root, m):
                    if m not in info:
                        info[m] = commit_info(root, m)
                    refs |= set(info[m][1])
            out.append((sha, sorted(refs), body.split("\n", 1)[0]))
        return out

    # ③④ 看分支點以後分支上活著的 commit
    _, recs, undone = branch_log(root, ref, a.main_ref)
    live = live_refs(recs, undone)
    # ② 看分支 tip 能到的全部 commit（分支點以前的分支本來就含），扣掉被撤的
    all_recs, all_undone = log_recs(root, ref)
    covered = {n for _, refs, _ in live_refs(all_recs, all_undone) for n in refs}
    # 票上「SPEC 變更：commit <sha>」認得的 sha：分支 tip 能到、沒被撤的 commit，
    # 以及這些 commit 的 -x trailer 指回的 main commit（PM 多半抄 main 上的 sha）
    live_shas = set()
    for sha, _, _, trailers, _ in all_recs:
        if not all_undone(sha):
            live_shas.add(sha)
            live_shas.update(trailers)

    def on_branch(short):
        short = short.lower()
        return any(s.startswith(short) for s in live_shas)

    # ② milestone 的 issue 都有交代
    print(f"\n### ② milestone {title} 的 {len(issues)} 張 issue：分支有 commit、票上寫了「SPEC 變更：commit <sha>」，"
          "或標了「不用改」")
    uncovered, changed, marked, still_open = [], [], [], []
    try:
        for it in sorted(issues, key=lambda x: int(x["iid"])):
            n = int(it["iid"])
            if it.get("state") == "opened":
                still_open.append(it)
            if n in covered:
                continue
            texts = ticket_texts(g, it)
            if any(on_branch(s) for s in spec_change_shas(texts)):
                changed.append(it)
            elif no_change_marked(texts):
                marked.append(it)
            else:
                uncovered.append(it)
    except Exception as e:  # noqa: BLE001
        raise ToolError(f"GitLab API 失敗（{spec_at.PROJECT} issue 留言）：{e}") from e

    def ids(its):
        return f"（{', '.join('#' + str(it['iid']) for it in its)}）" if its else ""
    print(f"  分支有 commit：{len(issues) - len(uncovered) - len(changed) - len(marked)} 張；"
          f"票上寫了 SPEC 變更：{len(changed)} 張{ids(changed)}；標了不用改：{len(marked)} 張{ids(marked)}")
    if uncovered:
        blocking = True
        cmark = spec_at.SPEC_CHANGE_MARK.pattern if spec_at.SPEC_CHANGE_MARK else None
        nmark = spec_at.NO_CHANGE_MARK.pattern if spec_at.NO_CHANGE_MARK else None
        how = "、".join(x for x in (
            f"有改 SPEC → `{cmark}commit <sha>`（sha 要在分支上、沒被撤）" if cmark else "",
            f"沒改 SPEC → 符合 `{nmark}`" if nmark else "") if x) or "（兩種標記都未設定）"
        add(f"② 沒交代的 issue：{len(uncovered)} 張（分支上沒有帶它的 commit，票上描述／留言也沒交代；"
            f"票上補一行：{how}）")
        for it in uncovered:
            add(f"  #{it['iid']}（{it.get('state', '?')}）{it.get('title', '')}")
    else:
        print("✓ 每張都有交代")
    if still_open:
        print(f"  參考：還開著的 issue {len(still_open)} 張（不擋）：")
        for it in still_open:
            print(f"    #{it['iid']} {it.get('title', '')}")

    # ③ 分支上沒有更晚 milestone 的 issue
    print("\n### ③ 分支上沒有帶更晚 milestone issue 的 commit")
    late = [(sha, [(n, later[n]) for n in refs if n in later], subject)
            for sha, refs, subject in live if any(n in later for n in refs)]
    if late:
        blocking = True
        add(f"③ 分支上帶更晚 milestone issue 的 commit：{len(late)} 個")
        for sha, hits, subject in late:
            add(f"  {sha[:8]} {', '.join(f'#{n}→{t}' for n, t in hits)}｜{subject}"
                f"（要撤：git switch {branch} && git pull && git revert {sha} && git push）")
    else:
        print("✓ 沒有")

    # ④ 沒帶 issue 的 commit（參考）
    bare = [(sha, subject) for sha, refs, subject in live if not refs]
    print(f"\n### ④ 參考：分支上沒帶 issue 的 commit {len(bare)} 個（不擋）")
    for sha, subject in bare:
        print(f"  {sha[:8]}｜{subject}")

    if blocking:
        print(f"\n✗ {branch} 上線檢查不過" + ("；不打 tag" if a.tag else ""))
        return 2, ["\n".join(lines)]
    print(f"\n✓ {branch} 上線檢查全過（milestone {title}）")
    if not a.tag:
        return 0, []
    if tagged:
        print(f"  tag {tag} 已存在，不重打")
        return 0, []
    git(root, "tag", "-a", tag, "-m", f"{branch} release（spec_sync release-check 全過，milestone {title}）", tip)
    try:
        push_tag(root, a, tag)
    except ToolError:
        git(root, "tag", "-d", tag, check=False)       # 推不上去就別留本機 tag，重跑時才會再推
        raise
    print(f"✓ 已打 tag {tag}（{tip[:8]}）並推上去；{branch} 之後不再同步")
    return 0, [f"✓ spec-release-check：{branch} 全過，已打 {tag}（{tip[:8]}）"]


# ── 進入點 ───────────────────────────────────────────────────
def main(argv=None, get=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=REPO, help="repo 位置（預設本 repo）")
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--main", default=os.environ.get("CI_DEFAULT_BRANCH") or "main", help="main 分支名")
    ap.add_argument("--no-fetch", action="store_true", help="不 fetch（測試／本機用）")
    ap.add_argument("--notify", action="store_true", help="有衝突／落差／錯誤時送聊天工具通知")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sync")
    s.add_argument("--range", help="已不使用（相容舊呼叫）：一律從分支點重算待挑")
    s.add_argument("--push", action="store_true")
    s.add_argument("--push-url", help="覆寫推送目標（測試用）")
    c = sub.add_parser("check")
    rcp = sub.add_parser("release-check")
    rcp.add_argument("version", help="如 v1.10.0")
    rcp.add_argument("--tag", action="store_true", help="全過時打 <分支><RELEASE_TAG_SUFFIX> tag 並推")
    rcp.add_argument("--push-url", help="覆寫推送目標（測試用）")
    # --notify 也可寫在子指令後面
    for p in (s, c, rcp):
        p.add_argument("--notify", action="store_true", dest="notify_sub")
    a = ap.parse_args(argv)
    a.root = os.path.abspath(a.root)
    a.main_ref = f"refs/remotes/{a.remote}/{a.main}"
    a.notify = a.notify or a.notify_sub
    if a.cmd != "sync":
        a.push = False
    err = spec_at.require_config()
    if err:
        print(f"✗ {err}")
        return 1

    def get_or_fail():
        g = get or gitlab_get()
        if g is None:
            raise ToolError("SPEC_SYNC_API_URL／SPEC_SYNC_API_TOKEN 未設定（CI 可用 CI_SERVER_URL／SPEC_SYNC_PUSH_TOKEN）")
        return g

    run = {"sync": cmd_sync, "check": cmd_check, "release-check": cmd_release_check}[a.cmd]
    try:
        rc, msgs = run(a, get_or_fail)
    except ToolError as e:
        print(f"\n✗ 工具錯誤：{e}\n（沒有推送任何東西到尚未處理的分支）")
        notify(f"✗ spec-{a.cmd} 工具錯誤：{e}", a.notify)
        return 1
    except RuntimeError as e:          # spec_at.git 失敗
        print(f"\n✗ git 錯誤：{e}")
        notify(f"✗ spec-{a.cmd} git 錯誤：{e}", a.notify)
        return 1
    if msgs:
        notify("\n\n".join(msgs), a.notify)
    return rc


if __name__ == "__main__":
    sys.exit(main())
