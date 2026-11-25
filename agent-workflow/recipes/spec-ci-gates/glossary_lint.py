#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
glossary_lint.py — Glossary ↔ SPEC 名詞一致性的確定性 linter（非 LLM）。

LLM 讀段落抓禁用詞不可靠，跨批會累積漏網；本工具全 repo 掃、子字串安全、例外當資料。

模式：
  --banned    掃禁用名詞對照表的「無條件禁用詞」，扣除例外，命中 → exit 1（CI 硬門）
  --coverage  抽 SPEC 概念詞 diff Glossary 詞彙，列「未收錄候選」→ 只提示，不影響 exit
  --structure 檢查 Glossary 本身（重複定義／同時定義又禁用／缺必要標頭）→ 有問題 exit 1
  --all       三者都跑（預設；banned 或 structure 失敗即 exit 1）

Glossary 格式（標頭字串見下方常數）：
  ## 核心名詞定義     | 中文 | 英文 | 定義 | …
  ## 禁用名詞對照表   | ❌ 禁用 | ✅ 改用 | 說明 |
  第 1 欄可用「a / b」或「a／b」列多個同義詞。只有可 grep 的裸詞進硬門；下列降為 advisory：
    * 帶語境限定：「關閉（指任務時）」。括號在講出處（舊名／舊值／原名／棄用）者仍是硬門。
    * 敘述句：含引號、vs、混用、當成… 的列（例：「把『完成』當成封存」）。
    * CONTEXTUAL_EXTRA 列的詞。

例外：
  1. 結構排除：frontmatter、第一個 ## 之前的 > 引言、禁用表本體的表格列。
  2. 子字串安全：命中被更長的正式詞涵蓋（禁「清單」用語時「清單擁有者」是正式詞）→ 不算。
  3. 行內 pragma：同行含 `glossary-lint: allow <詞>`（或 `allow-line`）。
  4. waiver 檔 glossary_lint_waivers.txt：每行 `相對路徑:行號|*:詞`，# 為註解。只收無法寫行內註解的
     情形（例：HTML 的 <title>），且用 `*`——行號一漂移，豁免就靜默落到別行。沒有這個檔＝沒有豁免。

用法：
  python3 Spec/.convert_tools/glossary_lint.py --banned
  python3 Spec/.convert_tools/glossary_lint.py --banned --path Spec/Tasks HTML設計稿/定案
"""
import argparse
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

# ── 專案常數（安裝後改成自己的值）────────────────────────────
GLOSSARY = os.path.join(REPO, "Spec", "Glossary.md")
WAIVERS = os.path.join(HERE, "glossary_lint_waivers.txt")
DEFAULT_PATHS = ["Spec", os.path.join("HTML設計稿", "定案")]
BANNED_HEADER = "## 禁用名詞對照表"
CORE_HEADER = "## 核心名詞定義"
TABLE_HEADERS = {"❌ 禁用", "禁用", "✅ 改用", "改用", "說明", "中文", "中文名詞", "名詞", "英文", "定義"}
# 沒寫（脈絡）、但合法同形用法很多的禁用詞 → 只提示、不擋
CONTEXTUAL_EXTRA = {"項目"}
# 不掃的檔：名詞定義本身、決策史、封存、逐字搬出的延後原文
EXCLUDE_NAME = ("Glossary.md",)
EXCLUDE_SUBSTR = ("README",)
EXCLUDE_DIR = ("memory", ".git", ".convert_tools")
EXCLUDE_PATH_SUBSTR = ("History",)
EXCLUDE_PREFIX = ("Spec/Deferred/", "Spec/BACKLOG.md")
COVERAGE_NOISE = re.compile(r"^(US-|AC-|EC-|ER-|HP-|[NR]-\d)")   # 編號不是概念詞

SLASH = r"\s*[/／]\s*"                      # 只切半形會讓「甲／乙」變成永遠不命中的死詞
NARRATIVE = re.compile(r"[「」『』]|\bvs\b|當成|混用|籠統")
PROVENANCE = re.compile(r"舊名|舊值|舊稱|原名|棄用")


# ---------- 共用（prose_lint 也 import） ----------
def read_lines(path):
    with open(path, encoding="utf-8") as f:
        return f.read().split("\n")


def frontmatter_end(lines):
    """frontmatter 之後的第一行 index；沒有 frontmatter 回傳 0。
    開頭的 `---` 沒有對應的結尾就不算 frontmatter——否則整份檔會被跳過、靜默不受守。"""
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines) and lines[i].strip() == "---":
        for j in range(i + 1, len(lines)):
            if lines[j].strip() == "---":
                return j + 1
    return 0


# ---------- Glossary 解析 ----------
def strip_md(s):
    return s.replace("**", "").replace("~~", "").replace("`", "").strip()


def strip_paren(s):
    return re.sub(r"[（(].*?[）)]", "", strip_md(s)).strip()


def split_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def is_table_row(s):
    return s.startswith("|") and not set(s) <= set("|-: ")


def parse_glossary(lines):
    """回傳 (無條件禁用詞, 語境限定禁用詞, 正式詞)。"""
    banned, ctx, canonical = set(), set(), set()
    in_banned = False
    for ln in lines:
        h = ln.strip()
        if h.startswith("## "):
            in_banned = h == BANNED_HEADER
            continue
        if not is_table_row(h):
            continue
        cells = split_row(ln)
        if len(cells) < 2:
            continue
        c0, c1 = cells[0], cells[1]
        if strip_md(c0) in TABLE_HEADERS:
            continue                           # 表頭不是資料，否則「禁用」兩字自己變成禁用詞
        if in_banned:
            # 語境／敘述看整列（標記常只掛在其中一個同義詞上），長度看逐片
            provenance = bool(PROVENANCE.search(c0))
            soft_row = not provenance and ("（" in c0 or "(" in c0 or bool(NARRATIVE.search(c0)))
            for term in re.split(SLASH, c0):
                core = strip_paren(term)
                if not core:
                    continue
                soft = soft_row or core in CONTEXTUAL_EXTRA or (len(core) > 12 and " " in core)
                (ctx if soft else banned).add(core)
            for good in re.split(SLASH, c1):
                g = strip_paren(good)
                if g and g != "N/A":
                    canonical.add(g)
        else:
            for cell in (c0, c1):
                for nm in re.split(SLASH, cell):
                    n = strip_md(nm)
                    if n:
                        canonical.add(n)
    return banned, ctx, {c for c in canonical if len(c) >= 2}


# ---------- 檔案掃描 ----------
def is_excluded(full):
    """目錄遞迴與 --path 單檔共用同一組排除。"""
    rel = os.path.relpath(full, REPO).replace(os.sep, "/")
    parts = rel.split("/")
    return (parts[-1] in EXCLUDE_NAME or any(x in parts[-1] for x in EXCLUDE_SUBSTR)
            or any(d in EXCLUDE_DIR for d in parts[:-1])
            or any(x in rel for x in EXCLUDE_PATH_SUBSTR) or rel.startswith(EXCLUDE_PREFIX))


def target_files(paths):
    out = set()
    for p in paths:
        ap = os.path.join(REPO, p)
        if os.path.isfile(ap):
            cands = [ap]
        else:
            cands = [os.path.join(r, f) for r, _, fs in os.walk(ap) for f in fs]
        out.update(f for f in cands if f.endswith((".md", ".html")) and not is_excluded(f))
    return sorted(out)


def structural_skip_map(lines):
    """frontmatter／第一個 ## 之前的 > 引言／禁用表的表格列。
    禁用表只跳表格本體：跳「到下一個標題為止」的話，表若在檔尾，之後新增的內容全部不受守。"""
    skip = [False] * len(lines)
    start = frontmatter_end(lines)
    for i in range(start):
        skip[i] = True
    seen_h2 = in_banned = False
    for i in range(start, len(lines)):
        s = lines[i].strip()
        if s.startswith("## "):
            seen_h2, in_banned = True, s == BANNED_HEADER
            skip[i] = in_banned
            continue
        if not seen_h2 and s.startswith(">"):
            skip[i] = True
        if in_banned:
            if s.startswith("|"):
                skip[i] = True
            elif s:
                in_banned = False
    return skip


def load_waivers():
    waived = set()
    if os.path.exists(WAIVERS):
        for ln in read_lines(WAIVERS):
            ln = ln.strip()
            if ln and not ln.startswith("#"):
                parts = ln.rsplit(":", 2)
                if len(parts) == 3:
                    waived.add(tuple(parts))
    return waived


PRAGMA_RE = re.compile(r"glossary-lint:\s*allow(?:-line|\s+(?P<term>\S+))?")


def covered_by_canonical(line, start, end, canonical_sorted):
    """命中 [start,end) 是否被更長的正式詞涵蓋。canonical_sorted 由長到短。"""
    for c in canonical_sorted:
        if len(c) <= end - start:
            break
        idx = line.find(c)
        while idx != -1:
            if idx <= start and idx + len(c) >= end:
                return True
            idx = line.find(c, idx + 1)
    return False


def scan_banned(files, banned, canonical, waived):
    canonical_sorted = sorted(canonical, key=len, reverse=True)
    hits = []
    for full in files:
        rel = os.path.relpath(full, REPO).replace(os.sep, "/")
        lines = read_lines(full)
        skip = structural_skip_map(lines)
        for i, line in enumerate(lines):
            if skip[i]:
                continue
            allowed = [m.group("term") for m in PRAGMA_RE.finditer(line)]
            if None in allowed:                # allow-line
                continue
            for term in sorted(banned, key=len, reverse=True):
                if term in allowed or (rel, str(i + 1), term) in waived or (rel, "*", term) in waived:
                    continue
                start = line.find(term)
                while start != -1:
                    if not covered_by_canonical(line, start, start + len(term), canonical_sorted):
                        hits.append((rel, i + 1, term, line.strip()))
                        break                  # 每行每詞報一次
                    start = line.find(term, start + 1)
    return hits


# ---------- coverage（advisory） ----------
EN_PHRASE = re.compile(r"[A-Z][A-Za-z0-9]+(?:[ /_-][A-Z][A-Za-z0-9]+)+")
ZH_QUOTED = re.compile(r"「([^」，。；、：（）()\s]{2,10})」")


def scan_coverage(files, glossary_text):
    cand = Counter()
    for full in files:
        for line in read_lines(full):
            cand.update(m.group(0) for m in EN_PHRASE.finditer(line))
            cand.update(m.group(1) for m in ZH_QUOTED.finditer(line))
    return sorted(((n, t) for t, n in cand.items()
                   if n >= 3 and not COVERAGE_NOISE.match(t) and "_" not in t and t not in glossary_text),
                  reverse=True)


# ---------- structure ----------
def check_structure(lines):
    problems = [f"缺必要標頭：{h}" for h in (CORE_HEADER, BANNED_HEADER)
                if not any(ln.strip() == h for ln in lines)]
    banned, _, _ = parse_glossary(lines)       # 語境限定詞本來就雙義合法，不列入
    seen, in_banned = Counter(), False
    for ln in lines:
        h = ln.strip()
        if h.startswith("## "):
            in_banned = h == BANNED_HEADER
            continue
        if in_banned or not is_table_row(h):
            continue
        cells = split_row(ln)
        if len(cells) >= 2 and strip_md(cells[0]) not in TABLE_HEADERS:
            seen.update(n for n in (strip_paren(x) for x in re.split(SLASH, cells[0])) if len(n) >= 2)
    for d, c in seen.items():
        if c > 1:
            problems.append(f"詞條重複定義 {c} 次：「{d}」")
        if d in banned:
            problems.append(f"同時被定義又被禁用：「{d}」")
    return problems


def main():
    ap = argparse.ArgumentParser(description="Glossary↔SPEC 名詞一致性 linter")
    for m in ("banned", "coverage", "structure", "all"):
        ap.add_argument("--" + m, action="store_true")
    ap.add_argument("--path", nargs="*", default=None, help="掃描路徑（相對 repo）")
    a = ap.parse_args()
    if not (a.banned or a.coverage or a.structure):
        a.all = True
    if not os.path.exists(GLOSSARY):
        print(f"❌ 找不到 {os.path.relpath(GLOSSARY, REPO)}（改 GLOSSARY 常數，或先建 Glossary）")
        return 1
    glines = read_lines(GLOSSARY)
    banned, ctx, canonical = parse_glossary(glines)
    files = target_files(a.path or DEFAULT_PATHS)
    fail = False

    if a.structure or a.all:
        probs = check_structure(glines)
        print("── [structure] Glossary 結構檢查 ──")
        fail |= bool(probs)
        for p in probs:
            print(f"  ❌ {p}")
        print("" if probs else "  ✅ 無結構問題\n")

    if a.banned or a.all:
        hits = scan_banned(files, banned, canonical, load_waivers())
        print(f"── [banned] 掃 {len(files)} 檔 · {len(banned)} 個無條件禁用詞 ──")
        fail |= bool(hits)
        for rel, n, term, text in hits:
            print(f"  ❌ {rel}:{n}  「{term}」  | {text[:80]}")
        print(f"  → 共 {len(hits)} 處違規" if hits else "  ✅ 0 處違規")
        if ctx:
            print(f"  ℹ️ 語境限定／敘述型（{len(ctx)} 個）不擋：{'、'.join(sorted(ctx))}")
        print()

    if a.coverage or a.all:
        undef = scan_coverage(files, "\n".join(glines))
        print("── [coverage] 未收錄概念詞候選（出現 ≥3 次、只提示）──")
        for n, term in undef[:40]:
            print(f"  ⚠️ {n:4d}  {term}")
        print(f"  → 共 {len(undef)} 個候選" if undef else "  ✅ 無明顯未收錄候選")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
