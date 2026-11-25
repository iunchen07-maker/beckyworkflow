#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
decisions — 查詢與檢查 Spec/memory/ 決策檔（只用標準函式庫）。

決策檔＝Spec/memory/*.md（及日後的年份子資料夾 Spec/memory/YYYY/*.md），README.md／INDEX.md 除外；
Spec/memory/legacy/（凍結的舊歷史）與 Spec/memory/index/（產生的檢視）不算決策檔。
frontmatter 一行一個鍵，plain grep 可查：
  id: D-NNNN          流水號，永不重用
  date: YYYY-MM-DD
  changes: [§ID, ...] 這份決策「定下規則」的節（不是正文提到的所有節）。除 US-／目錄列 id（N-07、R-3）外收兩種代號：
                        原則-N                         Spec/Decision_Principles.md 的「### N.」原則
                        <SPEC 檔名 stem>#<標題文字>     沒有 § id 的區塊，如 05_Notifications#全域規則
  kind: non-spec      不改 SPEC 規則的決策（維持現況、流程／體例）；changes 可空，不進 why／檢視（列在 _non_spec.md）
  changes_source: review|title|conclusion|commit…   changes 的來源；review＝人工核過
  source: <group>/<project>#N   工作項全路徑；真的無法開單才寫「口頭需求」
  supersedes: [D-NNNN, ...]   一定要有；[]＝刻意不推翻任何決策
  supersedes_partial: [D-NNNN, ...]  supersedes 中只推翻一部分的（對方維持 active）；有才寫
  status: active|superseded
  milestone: 鍵必有、值留空；由 stamp-milestone 依 GitLab issue 蓋章，不手填
  relation: unverified        推翻關係是推論、未經人核時
  changes_inferred: true      changes 是遷移時推論的（人核過的改寫 changes_source: review、不寫此鍵）
  retired: [§ID, ...]         changes 裡已不存在於 SPEC 的節（不做存在檢查）；
                              Spec/Deferred/*.md「保留編號：…」列的延後 id 不是退役，不列進來（自動認得）

子命令：
  why <§ID>                       現行決策（active、新到舊）＋推翻鏈；另列 legacy 列
  list [--milestone vX] [--since YYYY-MM-DD]
  views [--check]                 產生／檢查 Spec/memory/index/<SPEC 檔名>.md（另產 _retired／_deferred／_no_changes／_non_spec）
  check [--base SHA]              frontmatter schema＋推翻一致性（整份推翻的對方須為 superseded）＋
                                  全部決策檔 changes 不得為空（kind: non-spec 或有 retired 者除外）；
                                  --base 時另查新增／改正文的決策檔（固定段落、8 KB 上限）
  next-id                         印下一個可用 id
  stamp-milestone [--write]       依 source 向 GitLab 查 milestone 蓋章（需 SPEC_SYNC_API_URL／SPEC_SYNC_API_TOKEN）

共用：--root <含 Spec/ 的資料夾>（預設本 repo）
"""
import argparse
import collections
import glob
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "Spec", ".convert_tools"))   # 安裝後；在配方資料夾內則與本檔同目錄
from numbering_lint import (CATALOG_FILE_SUBSTR, CATALOG_ROW_RE, DEF_SKIP_NAMES,  # noqa: E402
                            HEAD_RE as HEADING, PLACEHOLDER_RE, reserved_from_deferred)  # 編號解析與 numbering-lint 共用

# ── 專案常數 ──────────────────────────────────────────────
PROJECT = "my-org/todo-app"                     # 工作項所在的 GitLab 專案路徑
ORAL_SOURCE = "口頭需求"
CATALOG_TITLE_COL = 1                           # 目錄列的名稱欄（0＝編號欄）

NON_DECISION = {"README.md", "INDEX.md"}
REQUIRED = ("id", "date", "changes", "source", "supersedes", "status", "milestone")
BODY_SECTIONS = ("結論", "Why", "否決的方案", "推翻了什麼")
GENERATED_SECTION = "影響範圍"
SIZE_CAP = 8 * 1024
TITLE_MAX = 60
VIEW_TITLE_MAX = 40
TOP_KEY = re.compile(r"^([a-z_]+):(.*)$")
ID_RE = re.compile(r"^D-\d{4}$")
DATE_RE = re.compile(r"^\d{4}-\d\d-\d\d$")
SOURCE_RE = re.compile("^" + re.escape(PROJECT) + r"#\d+$")


# ── frontmatter ─────────────────────────────────────────────
def split_fm(text):
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return None, text
    return text[4:end].split("\n"), text[end + 5:]


def fm_dict(fm_lines):
    out, key, buf = {}, None, []
    for ln in fm_lines or []:
        m = TOP_KEY.match(ln)
        if m:
            if key:
                out[key] = "\n".join(buf).strip()
            key, buf = m.group(1), [m.group(2)]
        elif key:
            buf.append(ln)
    if key:
        out[key] = "\n".join(buf).strip()
    return out


def parse_list(v):
    v = (v or "").strip()
    if v.startswith("[") and v.endswith("]"):
        return [x.strip() for x in v[1:-1].split(",") if x.strip()]
    return [v] if v else []


def norm_id(s):
    return s.strip().lstrip("§").strip()


# ── SPEC 節 ──────────────────────────────────────────────────
def spec_files(root):
    out = []
    for p in sorted(glob.glob(os.path.join(root, "Spec", "**", "*.md"), recursive=True)):
        rel = os.path.relpath(p, root)
        parts = rel.split(os.sep)
        if "History" in rel or "memory" in parts or ".convert_tools" in parts:
            continue
        if parts[:2] == ["Spec", "Deferred"]:       # 延後功能不算 SPEC 現行節
            continue
        if os.path.basename(p) in DEF_SKIP_NAMES:
            continue
        out.append(rel)
    return out


def spec_ids(root):
    """{§ID: (rel, line, 標題)}：US- 標題＋目錄列 id。同 id 取第一個。
    保留編號的佔位行（含「保留編號」或「已移至 Deferred/」）不算現行節。"""
    ids = {}
    for rel in spec_files(root):
        lines = open(os.path.join(root, rel), encoding="utf-8").read().split("\n")
        is_catalog = CATALOG_FILE_SUBSTR in os.path.basename(rel)
        for n, ln in enumerate(lines, 1):
            if PLACEHOLDER_RE.search(ln):
                continue
            m = HEADING.match(ln)
            if m and "~~" not in ln[:m.end()]:         # 刪除線標題＝作廢，不算現行節
                title = ln[m.end():].strip()
                ids.setdefault(m.group(2), (rel, n, clean(title)))
                continue
            if is_catalog:
                m = CATALOG_ROW_RE.match(ln)
                if m:
                    cells = [c.strip() for c in ln.strip().strip("|").split("|")]
                    title = cells[CATALOG_TITLE_COL] if len(cells) > CATALOG_TITLE_COL else ""
                    ids.setdefault(m.group(1), (rel, n, clean(title)))
    return ids


def deferred_ids(root):
    """{§ID: Deferred 檔名}：Spec/Deferred/*.md 開頭「保留編號：…」行列的 id（延後中、非退役）。
    US-X.Y/AC-N 形式只取 US 部分。"""
    out = {}
    for k, loc in reserved_from_deferred(root).items():
        out.setdefault(k.split("/")[0], os.path.basename(loc.rsplit(":", 1)[0]))
    return out


PRINCIPLES = os.path.join("Spec", "Decision_Principles.md")
PRINCIPLE_HEAD = re.compile(r"^###\s+(\d+)\.\s*(.*)$")
MD_HEAD = re.compile(r"^(#{1,6})\s+(.*?)\s*$")


def is_code(s):
    """changes 裡的非 §ID 代號：原則-N 或 <stem>#<標題>。"""
    return s.startswith("原則-") or "#" in s


def code_targets(root):
    """{代號: (rel, line, 標題)}：原則-N（Decision_Principles 的「### N.」）＋
    <SPEC 檔名 stem>#<標題文字>（spec_files 中各檔的 Markdown 標題；檔名 stem 重複者不收）。"""
    out = {}
    p = os.path.join(root, PRINCIPLES)
    if os.path.exists(p):
        for n, ln in enumerate(open(p, encoding="utf-8").read().split("\n"), 1):
            m = PRINCIPLE_HEAD.match(ln)
            if m:
                out.setdefault(f"原則-{m.group(1)}", (PRINCIPLES, n, clean(m.group(2))))
    rels = spec_files(root)
    stems = collections.Counter(os.path.splitext(os.path.basename(r))[0] for r in rels)
    for rel in rels:
        stem = os.path.splitext(os.path.basename(rel))[0]
        if stems[stem] > 1:
            continue
        fence = False
        for n, ln in enumerate(open(os.path.join(root, rel), encoding="utf-8").read().split("\n"), 1):
            if ln.startswith("```"):
                fence = not fence
            m = None if fence else MD_HEAD.match(ln)
            if m and not HEADING.match(ln):          # 有 § id 的標題請直接寫 §ID
                out.setdefault(f"{stem}#{m.group(2)}", (rel, n, clean(m.group(2))))
    return out


def clean(s, n=TITLE_MAX):
    s = re.sub(r"<!--.*?-->", "", s)
    s = re.sub(r"[*`~]", "", s).replace("|", "／")
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[:n - 1] + "…"


# ── 決策檔 ───────────────────────────────────────────────────
def decision_paths(root):
    mem = os.path.join(root, "Spec", "memory")
    paths = glob.glob(os.path.join(mem, "*.md")) + glob.glob(os.path.join(mem, "[12][0-9][0-9][0-9]", "*.md"))
    return sorted(p for p in paths if os.path.basename(p) not in NON_DECISION)


def title_of(fm, body, fallback):
    t = ""
    for k in ("description", "topic", "title"):
        if fm.get(k):
            t = fm[k].split("\n")[0].strip().strip("\"'")
            break
    if not t:
        t = next((ln[2:].strip() for ln in body.split("\n") if ln.startswith("# ")), fallback)
    return re.sub(r"^\d{4}-\d\d-\d\d\s*[：:—-]?\s*", "", t) or t


def load(root):
    out = []
    for p in decision_paths(root):
        text = open(p, encoding="utf-8").read()
        fm_lines, body = split_fm(text)
        fm = fm_dict(fm_lines)
        rel = os.path.relpath(p, os.path.join(root, "Spec", "memory"))
        out.append({
            "path": p, "rel": rel, "fm": fm, "has_fm": fm_lines is not None,
            "id": fm.get("id", ""), "date": fm.get("date", ""),
            "changes": [norm_id(x) for x in parse_list(fm.get("changes"))],
            "retired": [norm_id(x) for x in parse_list(fm.get("retired"))],
            "supersedes": parse_list(fm.get("supersedes")),
            "partial": parse_list(fm.get("supersedes_partial")),
            "status": fm.get("status", ""), "source": fm.get("source", ""),
            "milestone": fm.get("milestone", "").strip('"'),
            "unverified": fm.get("relation", "") == "unverified",
            "inferred": fm.get("changes_inferred", "") == "true",
            "kind": fm.get("kind", ""), "non_spec": fm.get("kind", "") == "non-spec",
            "title": clean(title_of(fm, body, os.path.basename(p)[:-3]), 200),
            "size": len(text.encode("utf-8")), "body": body,
        })
    return out


def migrated(decs):
    return [d for d in decs if ID_RE.match(d["id"])]


def section_index(root):
    """why／views 用的位置表：§ID（spec_ids）＋代號（code_targets）。"""
    out = dict(code_targets(root))
    out.update(spec_ids(root))
    return out


def fmt_line(d, n=TITLE_MAX):
    bits = [d["id"], d["date"]]
    if d["status"] == "superseded":
        bits.append("(superseded)")
    bits.append(clean(d["title"], n))
    tail = [x for x in (d["milestone"], short_src(d["source"])) if x]
    if d["unverified"]:
        tail.append("⚠推翻關係未核")
    return "  ".join(bits) + (f"  [{' · '.join(tail)}]" if tail else "")


def short_src(s):
    m = re.search(r"#(\d+)$", s or "")
    return f"#{m.group(1)}" if m else (s or "")


def chain_lines(d, by_id, depth, seen):
    out = []
    for sid in d["supersedes"]:
        if sid in seen or sid not in by_id:
            continue
        seen.add(sid)
        verb = "← 部分推翻 " if sid in d["partial"] else "← 推翻 "
        out.append("    " * depth + verb + fmt_line(by_id[sid]) + f"  {by_id[sid]['rel']}")
        out += chain_lines(by_id[sid], by_id, depth + 1, seen)
    return out


# ── legacy ───────────────────────────────────────────────────
CELL_SPLIT = re.compile(r"(?<!\\)\|")


def legacy_rows(root):
    """[(rel, line, date, [§ID], rest)]；legacy 表第 2 欄固定是 sections。"""
    out = []
    for p in sorted(glob.glob(os.path.join(root, "Spec", "memory", "legacy", "*.md"))):
        rel = os.path.relpath(p, os.path.join(root, "Spec", "memory"))
        for n, ln in enumerate(open(p, encoding="utf-8"), 1):
            if not re.match(r"\|\s*\d{4}-\d\d-\d\d", ln):
                continue
            cells = [c.strip() for c in CELL_SPLIT.split(ln.strip())[1:-1]]
            if len(cells) < 3:
                continue
            secs = [x.strip() for x in cells[1].split(",") if x.strip()]
            out.append((rel, n, cells[0], secs, " ｜ ".join(c for c in cells[2:] if c)))
    return out


# ── 子命令 ───────────────────────────────────────────────────
def cmd_why(a, decs):
    sid = norm_id(a.section)
    ds = migrated(decs)
    by_id = {d["id"]: d for d in ds}
    hits = [d for d in ds if sid in d["changes"] and not d["non_spec"]]
    act = sorted((d for d in hits if d["status"] == "active"), key=lambda d: (d["date"], d["id"]), reverse=True)
    where = section_index(a.root).get(sid)
    dfile = deferred_ids(a.root).get(sid)
    if dfile:
        print(f"延後中，見 Deferred/{dfile}")
    loc = (f"{where[0]}:{where[1]} {where[2]}" if where
           else "（SPEC 正文無此節：延後功能保留編號）" if dfile
           else "（SPEC 找不到此節：已退役或改名）")
    print(f"§{sid} — {loc}")
    print(f"\n現行決策（active，新→舊）：{len(act)} 筆")
    shown = set()
    for d in act:
        print("  " + fmt_line(d, 80) + f"  {d['rel']}")
        seen = set()
        for ln in chain_lines(d, by_id, 2, seen):
            print("  " + ln)
        shown |= seen
    rest = sorted((d for d in hits if d["status"] != "active" and d["id"] not in shown),
                  key=lambda d: (d["date"], d["id"]), reverse=True)
    if rest:
        print(f"\n其他 superseded（changes 含本節、不在上列推翻鏈）：{len(rest)} 筆")
        for d in rest:
            print("  " + fmt_line(d, 80) + f"  {d['rel']}")
    leg = [r for r in legacy_rows(a.root) if sid in r[3]]
    print(f"\nlegacy（切換前的舊決策史；凍結、僅供查）：{len(leg)} 列")
    for rel, n, date, _, rest_ in sorted(leg, key=lambda r: r[2], reverse=True):
        txt = clean(rest_, a.width)
        print(f"  {date}  {rel}:{n}  {txt}")
    return 0


def cmd_list(a, decs):
    ds = migrated(decs)
    if a.milestone:
        ds = [d for d in ds if d["milestone"] == a.milestone]
    if a.since:
        ds = [d for d in ds if d["date"] >= a.since]
    for d in sorted(ds, key=lambda d: (d["date"], d["id"]), reverse=True):
        print(fmt_line(d, 80) + f"  {d['rel']}")
    print(f"（{len(ds)} 筆）", file=sys.stderr)
    return 0


def view_name(rel, all_rels):
    stem = os.path.splitext(os.path.basename(rel))[0]
    dup = sum(os.path.splitext(os.path.basename(r))[0] == stem for r in all_rels) > 1
    return (os.path.basename(os.path.dirname(rel)) + "_" + stem if dup else stem) + ".md"


def render_views(root, decs):
    ds = migrated(decs)
    by_id = {d["id"]: d for d in ds}
    ids = section_index(root)
    rels = spec_files(root)
    per_sec = collections.defaultdict(list)
    for d in ds:
        if d["non_spec"]:
            continue
        for s in d["changes"]:
            per_sec[s].append(d)
    files = collections.defaultdict(list)       # rel -> [(line, sid)]
    orphan = []
    deferred = deferred_ids(root)
    per_def = collections.defaultdict(list)     # Deferred 檔名 -> [sid]
    for s in per_sec:
        if s in ids:
            files[ids[s][0]].append((ids[s][1], s))
        elif s in deferred:
            per_def[deferred[s]].append(s)
        else:
            orphan.append(s)
    head = ("> 🤖 **產出物，勿手改**：`python3 ci/decisions.py views` 依 `Spec/memory/` 決策檔的 `changes` 產生。"
            "每節列現行（active）決策、新到舊，`←` 為它推翻的決策。"
            "`*`＝changes 為遷移推論（changes_inferred）；⚠＝推翻關係未核。")

    def sec_lines(s):
        hits = per_sec[s]
        act = sorted((d for d in hits if d["status"] == "active"), key=lambda d: (d["date"], d["id"]), reverse=True)
        out, shown = [], set()
        for d in act:
            seen = set()
            ch = chain_flat(d, by_id, seen)
            shown |= seen
            star = "*" if d["inferred"] else ""
            out.append(f"- [{d['id']}](../{d['rel']}){star} {d['date']} {clean(d['title'], VIEW_TITLE_MAX)}"
                       + (f" · {d['milestone']}" if d["milestone"] else "")
                       + (" ⚠" if d["unverified"] else "")
                       + (f"（← {ch}）" if ch else ""))
        rest = [d["id"] for d in sorted(hits, key=lambda d: d["id"], reverse=True)
                if d["status"] != "active" and d["id"] not in shown]
        if rest:
            out.append("- 其他 superseded：" + ", ".join(rest))
        return out

    views = {}
    for rel in sorted(files):
        L = [f"# {rel} — 決策檢視", "", head, ""]
        for _, s in sorted(files[rel]):
            title = "" if "#" in s else clean(ids[s][2], VIEW_TITLE_MAX)     # 區塊代號本身已含標題
            L.append(f"## {s} {title}".rstrip())
            L.append("")
            L += sec_lines(s)
            L.append("")
        views[view_name(rel, rels)] = "\n".join(L)
    L = ["# 已不存在於 SPEC 的節 — 決策檢視", "", head, "",
         "> 這些 §ID 出現在決策的 `changes`，但 SPEC 已找不到對應標題／目錄列（退役或改名）。", ""]
    for s in sorted(orphan):
        L.append(f"## {s}")
        L.append("")
        L += sec_lines(s)
        L.append("")
    views["_retired.md"] = "\n".join(L)
    L = ["# 延後功能的保留編號 — 決策檢視", "", head, "",
         "> 這些 §ID 出現在決策的 `changes`，目前延後中：規格原文在 `Spec/Deferred/<檔>`，"
         "id 列在該檔開頭「保留編號：…」行（不是退役）。", ""]
    for fname in sorted(per_def):
        L.append(f"## Deferred/{fname}")
        L.append("")
        for s in sorted(per_def[fname]):
            L.append(f"### {s}")
            L.append("")
            L += sec_lines(s)
            L.append("")
    views["_deferred.md"] = "\n".join(L)
    empty = sorted((d for d in ds if not d["changes"] and not d["non_spec"]),
                   key=lambda d: (d["date"], d["id"]), reverse=True)
    L = ["# changes 為空的決策", "", "> 🤖 **產出物，勿手改**：這些決策沒有標出定下規則的節，"
         "因此不出現在任何檢視。補 `changes` 後重跑 `python3 ci/decisions.py views`。", ""]
    L += [f"- [{d['id']}](../{d['rel']}) {d['date']} {clean(d['title'], VIEW_TITLE_MAX)}" for d in empty]
    L.append("")
    views["_no_changes.md"] = "\n".join(L)
    ns = sorted((d for d in ds if d["non_spec"]), key=lambda d: (d["date"], d["id"]), reverse=True)
    L = ["# 不改 SPEC 規則的決策（kind: non-spec）", "",
         "> 🤖 **產出物，勿手改**：這些決策沒有定下 SPEC 規則（維持現況、流程／體例等），"
         "不進各節檢視與 `why`。", ""]
    L += [f"- [{d['id']}](../{d['rel']}) {d['date']}"
          + (" (superseded)" if d["status"] == "superseded" else "")
          + f" {clean(d['title'], VIEW_TITLE_MAX)}" for d in ns]
    L.append("")
    views["_non_spec.md"] = "\n".join(L)
    return views


def chain_flat(d, by_id, seen):
    parts = []
    for sid in d["supersedes"]:
        if sid in seen or sid not in by_id:
            continue
        seen.add(sid)
        sub = chain_flat(by_id[sid], by_id, seen)
        parts.append(sid + (f" ← {sub}" if sub else ""))
    return ", ".join(parts)


def cmd_views(a, decs):
    idx = os.path.join(a.root, "Spec", "memory", "index")
    if not migrated(decs):
        print("views：Spec/memory/ 尚未遷移（沒有任何 id: D-NNNN），跳過")
        return 0
    views = render_views(a.root, decs)
    have = {os.path.basename(p) for p in glob.glob(os.path.join(idx, "*.md"))}
    if a.check:
        bad = []
        for name, text in views.items():
            p = os.path.join(idx, name)
            if not os.path.exists(p):
                bad.append(f"缺 {name}")
            elif open(p, encoding="utf-8").read() != text:
                bad.append(f"過期 {name}")
        bad += [f"多出 {n}（已無對應，應刪）" for n in sorted(have - set(views))]
        if bad:
            print("✗ Spec/memory/index/ 與決策檔不一致，請跑 `python3 ci/decisions.py views`：")
            for b in bad:
                print("  " + b)
            return 1
        print(f"✓ Spec/memory/index/ 最新（{len(views)} 份）")
        return 0
    os.makedirs(idx, exist_ok=True)
    for n in have - set(views):
        os.remove(os.path.join(idx, n))
    sizes = []
    for name, text in sorted(views.items()):
        open(os.path.join(idx, name), "w", encoding="utf-8").write(text)
        sizes.append((len(text.encode("utf-8")), name))
    sizes.sort(reverse=True)
    print(f"views → {os.path.relpath(idx, a.root)}：{len(views)} 份，合計 {sum(s for s, _ in sizes)} bytes，"
          f"最大 {sizes[0][1]} {sizes[0][0]} bytes")
    return 0


def changed_bodies(root, base):
    """base..HEAD 新增、或正文（frontmatter 以外）有改的決策檔 rel 路徑。只改 frontmatter 不算。"""
    def git(*args):
        return subprocess.run(["git", "-C", root, "-c", "core.quotepath=off", *args],
                              capture_output=True, text=True, check=True).stdout
    out = []
    names = git("diff", "--name-status", "--no-renames", "-z", base, "HEAD", "--", "Spec/memory/").split("\0")
    pairs = [(names[i], names[i + 1]) for i in range(0, len(names) - 1, 2)]
    for st, path in pairs:
        rel = os.path.relpath(path, "Spec/memory")
        parts = rel.split(os.sep)
        if not path.endswith(".md") or os.path.basename(path) in NON_DECISION:
            continue
        if parts[0] in ("legacy", "index") or (len(parts) > 1 and not re.match(r"[12]\d{3}$", parts[0])):
            continue
        if st == "A":
            out.append((rel, "新增"))
        elif st == "M":
            old = subprocess.run(["git", "-C", root, "show", f"{base}:{path}"],
                                 capture_output=True, text=True).stdout
            new = open(os.path.join(root, path), encoding="utf-8").read()
            if split_fm(old)[1] != split_fm(new)[1]:
                out.append((rel, "改正文"))
    return out


def cmd_check(a, decs):
    ds = migrated(decs)
    if not ds:
        print("check：Spec/memory/ 尚未遷移（沒有任何 id: D-NNNN），跳過")
        return 0
    errs = []
    ids = spec_ids(a.root)
    codes = code_targets(a.root)
    deferred = deferred_ids(a.root)
    seen = collections.defaultdict(list)
    for d in decs:
        seen[d["id"]].append(d["rel"])
    by_id = {d["id"]: d for d in ds}
    superseded_by = collections.defaultdict(list)      # 只算整份推翻
    for d in ds:
        for s in d["supersedes"]:
            if s not in d["partial"]:
                superseded_by[s].append(d["id"])
    for d in decs:
        r = d["rel"]
        missing = [k for k in REQUIRED if k not in d["fm"]]
        if missing:
            errs.append(f"{r}：缺鍵 {', '.join(missing)}")
            if "id" in missing:
                continue
        if not ID_RE.match(d["id"]):
            errs.append(f"{r}：id `{d['id']}` 不是 D-NNNN")
        elif len(seen[d["id"]]) > 1:
            errs.append(f"{r}：id {d['id']} 重複（{', '.join(x for x in seen[d['id']] if x != r)}）")
        if "date" in d["fm"] and not DATE_RE.match(d["date"]):
            errs.append(f"{r}：date `{d['date']}` 不是 YYYY-MM-DD")
        if "status" in d["fm"] and d["status"] not in ("active", "superseded"):
            errs.append(f"{r}：status `{d['status']}` 只能是 active／superseded")
        if "source" in d["fm"] and d["source"] != ORAL_SOURCE and not SOURCE_RE.match(d["source"]):
            errs.append(f"{r}：source `{d['source']}` 要寫全路徑 {PROJECT}#N（真的無法開單才寫「{ORAL_SOURCE}」）")
        if "supersedes" in d["fm"] and not d["fm"]["supersedes"].startswith("["):
            errs.append(f"{r}：supersedes 要寫成清單（沒有推翻就寫 []）")
        for s in d["supersedes"]:
            if s == d["id"]:
                errs.append(f"{r}：supersedes 指向自己")
            elif s not in by_id:
                errs.append(f"{r}：supersedes {s} 不存在")
        if "supersedes_partial" in d["fm"] and not d["fm"]["supersedes_partial"].startswith("["):
            errs.append(f"{r}：supersedes_partial 要寫成清單")
        for s in d["partial"]:
            if s not in d["supersedes"]:
                errs.append(f"{r}：supersedes_partial 的 {s} 不在 supersedes 裡")
        for s in d["supersedes"]:
            if s in d["partial"] or s not in by_id or s == d["id"]:
                continue
            if by_id[s]["status"] == "active":
                errs.append(f"{r}：整份推翻 {s}，但 {s} 仍是 active"
                            f"（改成 superseded；只推翻一部分就把 {s} 列進 supersedes_partial）")
        if d["status"] == "superseded" and not superseded_by.get(d["id"]):
            errs.append(f"{r}：status superseded，但沒有任何決策整份推翻 {d['id']}"
                        "（supersedes 指向它、且不在 supersedes_partial）")
        if d["kind"] and d["kind"] != "non-spec":
            errs.append(f"{r}：kind `{d['kind']}` 只能是 non-spec（一般決策不寫 kind）")
        for s in d["changes"]:
            if s.startswith("AC-"):
                errs.append(f"{r}：changes 不收 AC（{s} 不是全域唯一，請寫它所屬的 US 節）")
            elif s.startswith("原則-"):
                if s not in codes and s not in d["retired"]:
                    errs.append(f"{r}：changes 的 {s} 在 {PRINCIPLES} 找不到「### N.」標題")
            elif "#" in s:
                if s not in codes and s not in d["retired"]:
                    errs.append(f"{r}：changes 的 {s} 找不到——格式 <SPEC 檔名 stem>#<標題文字>，"
                                "標題要逐字相同、且不是有 § id 的標題（那種直接寫 §ID）")
            elif s not in ids and s not in deferred and s not in d["retired"]:
                errs.append(f"{r}：changes 的 {s} 在 SPEC 找不到標題／目錄列，也不是 Spec/Deferred/ 的保留編號"
                            "（已退役請列進 retired: [...]）")
        for s in d["retired"]:
            if s in deferred:
                errs.append(f"{r}：retired 的 {s} 是延後功能的保留編號（Deferred/{deferred[s]}），"
                            "延後不是退役，從 retired 拿掉")
        for s in d["retired"]:
            if s not in d["changes"]:
                errs.append(f"{r}：retired 的 {s} 不在 changes 裡")
        # 全部決策檔都查（不限 --base）：changes 空的決策不出現在任何檢視，等於沒人找得到
        if not d["changes"] and not d["retired"] and not d["non_spec"]:
            errs.append(f"{r}：changes 是空的——寫出這份決策定下規則的節（已退役的節同時列進 retired；"
                        "不改 SPEC 規則的決策加 kind: non-spec）")
    n_body = 0
    if a.base:
        known = {d["rel"]: d for d in decs}
        for rel, why in changed_bodies(a.root, a.base):
            d = known.get(rel)
            if not d:
                continue
            n_body += 1
            heads = [m.group(1).strip() for m in re.finditer(r"^#{2,3}\s+(.+)$", d["body"], re.M)]
            for want in BODY_SECTIONS:
                if not any(h.lower().startswith(want.lower()) for h in heads):
                    hint = "（沒有就寫「無」）" if want in ("否決的方案", "推翻了什麼") else ""
                    errs.append(f"{rel}（{why}）：缺段落「## {want}」{hint}")
            if any(h.startswith(GENERATED_SECTION) for h in heads):
                errs.append(f"{rel}（{why}）：「{GENERATED_SECTION}」由 changes 產生，不手寫")
            if d["size"] > SIZE_CAP:
                errs.append(f"{rel}（{why}）：{d['size']} bytes，超過 {SIZE_CAP}（as-built 調查放工作項、這裡只連結）")
    print(f"decisions check：{len(decs)} 份決策檔（已遷移 {len(ds)}）"
          + (f"；base {a.base[:12]} 起新增／改正文 {n_body} 份" if a.base else ""))
    if errs:
        for e in errs:
            print("  ✗ " + e)
        print(f"  {len(errs)} 處違規")
        return 1
    print("  ✓ 0 處違規")
    return 0


def cmd_next_id(a, decs):
    nums = [int(d["id"][2:]) for d in migrated(decs)]
    print(f"D-{(max(nums) if nums else 0) + 1:04d}")
    return 0


def cmd_stamp(a, decs):
    base, token = os.environ.get("SPEC_SYNC_API_URL"), os.environ.get("SPEC_SYNC_API_TOKEN")
    if not (base and token):
        print("SPEC_SYNC_API_URL／SPEC_SYNC_API_TOKEN 未設定")
        return 1
    proj = urllib.parse.quote(PROJECT, safe="")
    cache, changed = {}, 0
    for d in migrated(decs):
        m = re.search(r"#(\d+)$", d["source"])
        if not m:
            continue
        n = m.group(1)
        if n not in cache:
            req = urllib.request.Request(f"{base.rstrip('/')}/api/v4/projects/{proj}/issues/{n}",
                                         headers={"PRIVATE-TOKEN": token})
            try:
                with urllib.request.urlopen(req, timeout=15) as r:
                    cache[n] = (json.load(r).get("milestone") or {}).get("title", "") or ""
            except Exception as e:  # noqa: BLE001
                print(f"  #{n}: {e}")
                cache[n] = None
        ms = cache[n]
        if ms is None or ms == d["milestone"]:
            continue
        changed += 1
        print(f"  {d['id']} {d['rel']}: milestone `{d['milestone']}` → `{ms}`")
        if a.write:
            text = open(d["path"], encoding="utf-8").read()
            v = json.dumps(ms, ensure_ascii=False) if re.search(r"[:#\[\]{}]|^\s|\s$", ms) else ms
            text = re.sub(r"(?m)^milestone:.*$", f"milestone: {v}".rstrip(), text, count=1)
            open(d["path"], "w", encoding="utf-8").write(text)
    print(f"{changed} 份{'已改' if a.write else '待改（加 --write 才寫）'}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=REPO)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("why")
    p.add_argument("section")
    p.add_argument("--width", type=int, default=160, help="legacy 列文字截斷長度")
    p = sub.add_parser("list")
    p.add_argument("--milestone")
    p.add_argument("--since")
    p = sub.add_parser("views")
    p.add_argument("--check", action="store_true")
    p = sub.add_parser("check")
    p.add_argument("--base", help="比對起點 commit（CI 用 CI_COMMIT_BEFORE_SHA）")
    sub.add_parser("next-id")
    p = sub.add_parser("stamp-milestone")
    p.add_argument("--write", action="store_true")
    a = ap.parse_args()
    a.root = os.path.abspath(a.root)
    decs = load(a.root)
    fn = {"why": cmd_why, "list": cmd_list, "views": cmd_views, "check": cmd_check,
          "next-id": cmd_next_id, "stamp-milestone": cmd_stamp}[a.cmd]
    return fn(a, decs)


if __name__ == "__main__":
    sys.exit(main())
