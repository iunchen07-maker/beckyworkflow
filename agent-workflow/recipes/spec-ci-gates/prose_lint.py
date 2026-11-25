#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prose_lint.py — SPEC 正文「只寫現行行為」的確定性 linter（非 LLM）。

規則的權威是 workflow/phase-0-spec-update.md §SPEC 生命週期 1；本工具把「表面可判」的那一子集
變成機械門。語意層（沒有日期也沒有過程詞的解釋句）測不準，留給 phase0-spec-verifier。

檢查對象：Spec/**/*.md 的正文與 heading 行（表格列、Glossary 禁用名詞對照表也算正文）。
排除：frontmatter、第一個 ## 之前的 > 引言、code fence、表格分隔行，以及 is_excluded 的檔。

規則：
  H1 絕對日期        YYYY-MM-DD／YYYY/MM/DD／YYYY 年 M 月 → 規則只用相對時間
  H2 討論過程詞      拍板／議題 N／覆蓋舊／沿革／PEOPLE 列的人名
  H3 歷程／延後字樣  延後字樣清單（DEFERRAL_WORDS）＋ H3_PATTERNS
  H4 heading 延後字  heading 行出現延後字樣清單的任一詞
  H5 理由段標籤      設計原因／設計理由／設計決策／原因：／理由：（Decision_Principles 不套）
  P1 豁免標記不合格
  保留編號佔位（含「已移至 Deferred/」「保留編號」）：heading 整行不查 H1–H4；正文行不查 H3；都不查 H5。

模式（可一起給，rc 取聯集）：
  --diff [BASE]               只檢查相對 BASE（預設 HEAD）新增的行 → 命中 exit 1；BASE 比不到也 exit 1
  --all                       全掃；不在 baseline 的命中 → exit 1
  --write-baseline            全掃結果寫成 baseline（只該用來「縮小」；CI 會擋 baseline 長大）
  --check-baseline-shrink REF baseline 相對 REF 版本多出任何一筆 → exit 1；REF 還沒有 baseline＝首次引入、不比

例外：
  行內 pragma  `<!-- prose-lint: allow <example|ui-copy|literal-term>: <理由> -->` → 該行豁免 H1–H5。
               理由必填，不得是「沿用／既有／非本次／非本批／本行既有」這類歷程 → 否則 P1。
  baseline 檔  prose_lint_baseline.txt，每行 `路徑<TAB>sha1(正規化行文)<TAB>規則`（不用行號：行移動不失效，
               行文一改就失效 → 改到就要清）。沒有這個檔＝空 baseline。
"""
import argparse
import collections
import hashlib
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
BASELINE = os.path.join(HERE, "prose_lint_baseline.txt")
sys.path.insert(0, HERE)
from glossary_lint import frontmatter_end, read_lines  # noqa: E402  兩支要一起裝

# ── 專案常數 ──────────────────────────────────────────────
BASELINE_REL = "Spec/.convert_tools/prose_lint_baseline.txt"
SCAN_ROOT = "Spec"
PEOPLE = ()        # 不該進正文的人名，例 ("小美", "王經理")
# 索引／進度追蹤／流程類檔：內容本質就是「哪節寫到哪、流程怎麼走」
EXCLUDE_SUBSTR = ("README", "ROADMAP", "WORKFLOW", "Progress_Tracker")
EXCLUDE_DIR = ("memory", ".git", ".convert_tools")
EXCLUDE_PATH_SUBSTR = ("History",)
EXCLUDE_PREFIX = ("Spec/Deferred/", "Spec/BACKLOG.md")      # 逐字搬出的延後原文

# 延後字樣清單＝phase-0-spec-update.md §SPEC 生命週期 1（唯一一份，照它、不自訂子集）
DEFERRAL_WORDS = ("本次不實作", "本次不發", "暫緩", "暫不", "本期不", "本年度不", "非本年度",
                  "後續版本", "未來可", "留待後續")
# H3 其餘子樣式。新增前先量現行正文命中數，要 0 才收；寬樣式（不再／原本／改為／未來／裸「本次」）
# 誤判高，不收。「Chapter N」是合法引用寫法（SPEC_NUMBERING_RULES §四），也不收。
H3_PATTERNS = [
    ("本批", r"本批"),
    ("取代原", r"取代原"),
    ("已移除", r"已移除"),
    ("議題字母", r"議題\s*[A-Z](?=[\s，、）)]|$)"),
    ("本次", r"本次(?:不做|新增|未變|不處理)"),
    ("待補", r"待補(?=[，。）)]|$)"),
    ("另議", r"另議"),
    ("暫定", r"暫定"),
    ("方案代號", r"方案\s*[A-Z](?![A-Za-z])"),
    ("已整合入", r"已整合入|已整併"),
]
H3_RX = re.compile("|".join([re.escape(w) for w in DEFERRAL_WORDS] + [f"(?:{rx})" for _, rx in H3_PATTERNS]))
H4_RX = re.compile("|".join(map(re.escape, DEFERRAL_WORDS)))

RULES = [
    ("H1", "絕對日期（規則只用相對時間；決策日期寫 Spec/memory/ 決策檔）",
     re.compile(r"20\d{2}\s*[-/年]\s*\d{1,2}")),
    ("H2", "討論過程詞（meta 層，不進正文）",
     re.compile("|".join([r"拍板|議題\s*[#＃]?\s*\d+|覆蓋舊|沿革"] + [re.escape(p) for p in PEOPLE]))),
    ("H3", "歷程／延後字樣（正文只寫現行行為；延後功能搬 Spec/Deferred/）", H3_RX),
]
HEADING_RULE = ("H4", "heading 帶延後字樣（延後功能搬 Spec/Deferred/，heading 只寫現行功能名）", H4_RX)
# 退役／保留編號佔位：heading 整行不查；正文行不查 H3。
PLACEHOLDER = re.compile(r"已移至\s*`?(?:Spec/)?Deferred/|保留編號|編號保留")  # 只認保留編號佔位；裸「退役」不豁免

# H5 理由段標籤：理由（Why）住 Spec/memory/ 決策檔；Decision_Principles 以原則與理由為本體，不套 H5。
H5_RX = re.compile(r"設計原因|設計理由|設計決策|的理由[：:]|(?<![\w])(?:原因|理由)\s*[：:＝=]")
H5_DESC = "理由段標籤（Why 寫 Spec/memory/ 決策檔；正文只留規則）"
H5_EXEMPT = ("Decision_Principles",)


def rationale_hits(rel, line):
    if any(s in rel for s in H5_EXEMPT) or PRAGMA_ANY.search(line) or PLACEHOLDER.search(line):
        return []
    m = H5_RX.search(line)
    return [("H5", H5_DESC, m.group(0))] if m else []


PRAGMA_ANY = re.compile(r"prose-lint:\s*allow")
PRAGMA_OK = re.compile(
    r"prose-lint:\s*allow\s+(?P<cat>[\w-]+)\s*[:：]\s*(?P<reason>.*?)\s*(?:-->|$)")
PRAGMA_CATS = ("example", "ui-copy", "literal-term")
BAD_REASON = re.compile(r"沿用|既有|非本次|非本批|本行既有")
P1_DESC = ("豁免標記不合格（格式 `prose-lint: allow <example|ui-copy|literal-term>: <理由>`；"
           "理由不得是「沿用／既有／非本次」這類歷程）")


def is_excluded(rel):
    """單一真相：路徑是否豁免本 linter。--diff 與全掃共用，避免兩模式範圍不一致。"""
    parts = rel.replace("\\", "/").split("/")
    if "/".join(parts).startswith(EXCLUDE_PREFIX):
        return True
    if any(d in EXCLUDE_DIR for d in parts[:-1]):
        return True
    if any(s in rel for s in EXCLUDE_PATH_SUBSTR):
        return True
    if any(s in parts[-1] for s in EXCLUDE_SUBSTR):
        return True
    return False


def target_files():
    out = []
    root = os.path.join(REPO, SCAN_ROOT)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIR]
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            if fn.endswith(".md") and not is_excluded(os.path.relpath(full, REPO)):
                out.append(full)
    return sorted(out)


def structural_skip(lines):
    """frontmatter 與第一個 ## 之前的 > 引言。不沿用 glossary_lint 的版本：那支另排除禁用名詞對照表，
    對 prose 規則會藏住表內「說明」欄的歷程字句。"""
    end = frontmatter_end(lines)
    skip = [i < end for i in range(len(lines))]
    seen_h2 = False
    for idx, ln in enumerate(lines):
        s = ln.strip()
        if s.startswith("## "):
            seen_h2 = True
        if not seen_h2 and s.startswith(">"):
            skip[idx] = True
    return skip


def line_kinds(lines):
    """每行的受檢種類：None（不查）/ "body" / "heading"。"""
    skip = structural_skip(lines)
    kinds = [None] * len(lines)
    in_fence = False
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or skip[i] or not s:
            continue
        if re.match(r"^\|[\s:|-]+\|$", s):   # 表格分隔行
            continue
        kinds[i] = "heading" if re.match(r"#{1,6}\s", s) else "body"
    return kinds


def check_line(line, kind):
    """回傳 [(rule_id, desc, hit_text)]。"""
    if PRAGMA_ANY.search(line):
        m = PRAGMA_OK.search(line)
        if m and m.group("cat") in PRAGMA_CATS and m.group("reason") \
                and not BAD_REASON.search(m.group("reason")):
            return []
        return [("P1", P1_DESC, (m.group(0) if m else PRAGMA_ANY.search(line).group(0))[:60])]
    placeholder = bool(PLACEHOLDER.search(line))
    if kind == "heading" and placeholder:
        return []
    out = []
    for rid, desc, rx in RULES:
        if rid == "H3" and placeholder:
            continue
        m = rx.search(line)
        if m:
            out.append((rid, desc, m.group(0)))
    if kind == "heading":
        rid, desc, rx = HEADING_RULE
        m = rx.search(line)
        if m:
            out.append((rid, desc, m.group(0)))
    return out


# ── baseline ──────────────────────────────────────────────────
def norm_hash(text):
    t = re.sub(r"\s+", " ", text.strip())
    return hashlib.sha1(t.encode("utf-8")).hexdigest()


def hit_key(rel, rid, text):
    return f"{rel}\t{norm_hash(text)}\t{rid}"


def parse_baseline(text):
    c = collections.Counter()
    for ln in text.split("\n"):
        ln = ln.strip()
        if ln and not ln.startswith("#"):
            c[ln] += 1
    return c


def load_baseline():
    if not os.path.exists(BASELINE):
        return collections.Counter()
    with open(BASELINE, encoding="utf-8") as f:
        return parse_baseline(f.read())


def apply_baseline(hits, baseline):
    """回傳 (新違規, 被 baseline 吃掉的, baseline 裡已不再命中的 key)。依次數對消。"""
    left = collections.Counter(baseline)
    new, known = [], []
    for h in hits:
        k = hit_key(h[0], h[2], h[6])
        if left[k] > 0:
            left[k] -= 1
            known.append(h)
        else:
            new.append(h)
    stale = sorted(k for k, n in left.items() for _ in range(n) if n > 0)
    return new, known, stale


# hit tuple: (rel, lineno, rid, desc, hit_text, ctx, full_line)
def scan_all():
    hits = []
    for full in target_files():
        rel = os.path.relpath(full, REPO).replace(os.sep, "/")
        lines = read_lines(full)
        kinds = line_kinds(lines)
        for i, line in enumerate(lines):
            if not kinds[i]:
                continue
            for rid, desc, hit in check_line(line, kinds[i]) + rationale_hits(rel, line):
                hits.append((rel, i + 1, rid, desc, hit, line.strip()[:90], line))
    return hits


def scan_diff(base):
    """只檢查相對 base 新增的行。用 git diff -U0 取 added 行與其新檔行號。"""
    # core.quotePath=false：git 預設把非 ASCII 路徑轉八進位並加引號，`+++ b/` 後
    # 取到的就不是真路徑，rel 無法更新 → 該檔的 added 行被錯歸到前一個檔案。
    cmd = ["git", "-C", REPO, "-c", "core.quotePath=false",
           "diff", "--unified=0", "--no-color", "--src-prefix=a/", "--dst-prefix=b/",
           base, "--", SCAN_ROOT]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    except subprocess.CalledProcessError as e:
        print(f"❌ git diff 失敗（base={base}）：{e.stderr.strip()}", file=sys.stderr)
        return None
    hits, rel, lineno = [], None, 0
    kinds_of = {}
    for ln in out.split("\n"):
        if ln.startswith("+++ "):
            rel = ln[6:] if ln.startswith("+++ b/") else None
            if rel and (not rel.endswith(".md") or is_excluded(rel)):
                rel = None
            if rel and rel not in kinds_of and os.path.exists(os.path.join(REPO, rel)):
                kinds_of[rel] = line_kinds(read_lines(os.path.join(REPO, rel)))
            continue
        if ln.startswith("@@"):
            m = re.search(r"\+(\d+)", ln)
            lineno = int(m.group(1)) if m else 0
            continue
        if ln.startswith("+"):
            body = ln[1:]
            kinds = kinds_of.get(rel)
            kind = kinds[lineno - 1] if kinds and 0 < lineno <= len(kinds) else None
            if kind:
                for rid, desc, hit in check_line(body, kind) + rationale_hits(rel, body):
                    hits.append((rel, lineno, rid, desc, hit, body.strip()[:90], body))
            lineno += 1
    return hits


def report(new, known, stale, scope):
    print(f"── [prose-lint] SPEC 正文只留結論（{scope}）──")
    for rel, ln, rid, desc, hit, ctx, _ in new:
        print(f"  ❌ {rel}:{ln} [{rid}] 命中「{hit}」— {desc}")
        print(f"      {ctx}")
    if known:
        print(f"  ℹ️  {len(known)} 處在 baseline（存量債，碰到就清；清完跑 --write-baseline 縮小）：")
        for rel, ln, rid, _, hit, _, _ in known:
            print(f"      {rel}:{ln} [{rid}] 「{hit}」")
    if stale:
        print(f"  ℹ️  baseline 有 {len(stale)} 筆已不再命中 → 跑 --write-baseline 縮小")
    if not new:
        print("  ✅ 0 處新違規")
        return 0
    print(f"\n  共 {len(new)} 處。修法：規則留正文，緣由移到 Spec/memory/ 決策檔；延後功能搬 Spec/Deferred/。")
    print("  真的該留（範例值／逐字 UI 文案／字面名詞）：行尾加 "
          "`<!-- prose-lint: allow <example|ui-copy|literal-term>: <理由> -->`")
    return 1


def cmd_write_baseline(hits):
    keys = sorted(hit_key(h[0], h[2], h[6]) for h in hits)
    head = ("# prose_lint baseline — 存量債，只能縮小（CI `--check-baseline-shrink` 擋長大）。\n"
            "# 每行：路徑<TAB>sha1(正規化行文)<TAB>規則。由 `prose_lint.py --write-baseline` 產生，勿手改。\n")
    with open(BASELINE, "w", encoding="utf-8") as f:
        f.write(head + "".join(k + "\n" for k in keys))
    print(f"baseline 已寫入 {BASELINE_REL}：{len(keys)} 筆")
    for rel, ln, rid, _, hit, ctx, _ in hits:
        print(f"  {rel}:{ln} [{rid}] 「{hit}」 {ctx}")
    return 0


def cmd_check_shrink(ref):
    r = subprocess.run(["git", "-C", REPO, "-c", "core.quotePath=false", "show", f"{ref}:{BASELINE_REL}"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        if subprocess.run(["git", "-C", REPO, "rev-parse", "-q", "--verify", f"{ref}^{{commit}}"],
                          capture_output=True).returncode != 0:
            print(f"⚠️  找不到 {ref}，無法比對 baseline，跳過")
            return 0
        print(f"── [prose-lint] {ref} 尚無 baseline 檔：本次為首次引入，不比對")
        return 0
    old, cur = parse_baseline(r.stdout), load_baseline()
    grown = sorted(k for k in cur if cur[k] > old.get(k, 0))
    print(f"── [prose-lint] baseline 只能縮小（{ref}：{sum(old.values())} 筆 → 現在 {sum(cur.values())} 筆）──")
    if grown:
        for k in grown:
            print(f"  ❌ 新增 baseline 項：{k}")
        print("  baseline 不收新債：改寫該行，或真的該留就加合格的 pragma。")
        return 1
    print("  ✅ 沒有新增項")
    return 0


def main():
    ap = argparse.ArgumentParser(description="SPEC 正文只留結論 linter")
    ap.add_argument("--diff", nargs="?", const="HEAD", metavar="BASE",
                    help="只檢查相對 BASE 新增的行（預設 HEAD）→ 命中即 exit 1")
    ap.add_argument("--all", action="store_true", help="全掃；不在 baseline 的命中 → exit 1")
    ap.add_argument("--write-baseline", action="store_true", help="全掃結果寫成 baseline")
    ap.add_argument("--check-baseline-shrink", metavar="BASE_REF",
                    help="baseline 相對 BASE_REF 多出任何一筆 → exit 1")
    a = ap.parse_args()
    if not (a.diff or a.all or a.write_baseline or a.check_baseline_shrink):
        ap.print_help()
        return 0
    if a.write_baseline:
        return cmd_write_baseline(scan_all())
    rc = 0
    if a.check_baseline_shrink:
        rc |= cmd_check_shrink(a.check_baseline_shrink)
    baseline = load_baseline()
    if a.diff:
        hits = scan_diff(a.diff)
        if hits is None:
            rc = 1                          # 比不到就當沒過，不靜默放行
        else:
            new, known, _ = apply_baseline(hits, baseline)
            rc |= report(new, known, [], f"diff vs {a.diff}")
    if a.all:
        new, known, stale = apply_baseline(scan_all(), baseline)
        rc |= report(new, known, stale, "全 repo")
    return rc


if __name__ == "__main__":
    sys.exit(main())
