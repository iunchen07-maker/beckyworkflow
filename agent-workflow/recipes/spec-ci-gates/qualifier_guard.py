#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qualifier_guard.py — 改寫 SPEC 句子時「限定詞／數字被順手改掉」的提醒（advisory，永遠 exit 0）。

為什麼存在：「只改措辭、規則不變」的改寫最容易把限定詞一起刪掉——
例：「僅擁有者可封存清單」→「擁有者可封存清單」，少一個「僅」，協作者能不能封存就變成沒寫。
prose_lint 只看新增行有沒有歷程字樣，看不到「刪掉的那半句其實是規則」。

做法：取 `git diff -U0 BASE -- Spec`，每個 hunk 內把刪除行與新增行用 difflib 相似度配對
（同一 hunk、相似度 ≥ 0.5、一對一），對每一對比較：
  ① 限定詞次數變少：本年度 今年 本期 僅 只 非 不 未 禁止 不得 不可 除 例外 仍 一律 每 各
     （「除」不算 廢除／刪除／移除…；「未」不算「未來」）
  ② SPEC id（§US-／AC-／目錄列 N-7・R-3／原則 N／02_任務管理 這類檔名）舊行有、新行沒有（新增引用不報）
  ③ 其他數字序列改變（多出或少了任何一個數字）
比較前先把舊行裡「被拿掉的延後標記」與「歷程標籤」遮掉，這兩種本來就該刪、不算規則改變：
  延後標記  本次不實作 / 本次不發 / 本期不 / 本年度不做 / 留待後續 / 後續版本
            （連同它所在的全形括號或到句末）
  歷程標籤  絕對日期、議題 N／議題 X、D-NNNN、#NNN、vX.Y；舊行裡帶歷程字樣（拍板／定案／
            議題／日期…）而新行已拿掉的整個括號
沒配到對的純刪除／純新增行不報（那是搬移或新增，不是改寫）。不掃 Spec/memory/index/（產出物）。

用法：
  python3 Spec/.convert_tools/qualifier_guard.py --diff BASE          # BASE 對工作樹
  python3 Spec/.convert_tools/qualifier_guard.py --diff A..B          # 兩個 commit 之間
輸出每一對的 檔案:新行號、舊／新兩行、命中原因；永遠 exit 0，交給人判斷。
"""
import argparse
import collections
import difflib
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

# ── 專案常數 ──────────────────────────────────────────────
SCAN_ROOT = "Spec"
SKIP_PATH = ("History", "/.convert_tools/", "/memory/index/")  # index＝decisions.py 產出物
SPEC_ID = re.compile(
    r"(?:§\s*)?US-[A-Z]+[\d.]*\d|(?<![A-Za-z])AC-\d+"     # 節號、驗收條件
    r"|(?<![A-Za-z0-9-])[NR]-\d+"                          # 目錄列編號（通知 N-、提醒 R-）
    r"|原則\s*-?\s*\d+|(?<!\d)\d{2}_[^\s/`)）\]（(.,，、；;：:「」|]+(?:\.md)?")   # 原則、SPEC 檔名

# (名稱, regex)；由長到短排，數過的字遮掉，避免「不得」裡的「不」重複算。
# 「除」不收 廢除／刪除／移除／解除／清除／扣除（動詞，不是「除…外」）；「未」不收「未來」。
QUALIFIERS = [
    ("本年度", r"本年度"), ("禁止", r"禁止"), ("不得", r"不得"), ("不可", r"不可"),
    ("例外", r"例外"), ("一律", r"一律"), ("今年", r"今年"), ("本期", r"本期"),
    ("僅", r"僅"), ("只", r"只"), ("非", r"非"), ("不", r"不"), ("未", r"未(?!來)"),
    ("除", r"(?<![廢刪移解清扣])除"), ("仍", r"仍"), ("每", r"每"), ("各", r"各"),
]
QUAL_ORDER = [(q, re.compile(rx)) for q, rx in QUALIFIERS]

# 都取自 phase-0 §SPEC 生命週期 1，刻意只取一部分：「暫不」「非本年度」可能是規則本身，遮掉就看不到它消失
DEFERRAL = re.compile(r"本次不實作|本次不發|本期不|本年度不做|留待後續|後續版本")
HISTORY_TAG = re.compile(r"20\d{2}\s*[-/年]\s*\d{1,2}(?:\s*[-/月]\s*\d{1,2}\s*日?)?|"
                         r"議題\s*[#＃]?\s*(?:[A-Z]\d*(?:-\d+)?|\d+)|D-\d{3,}|[#＃]\d+|"
                         r"v\d+(?:\.\d+)+")
PAIR_MIN = 0.5


def mask_span(s, start, end):
    return s[:start] + " " * (end - start) + s[end:]


def mask_removed_deferrals(old, new):
    """舊行有、新行沒有（或變少）的延後標記：連同所在全形括號（或到句末）遮掉。"""
    lost = collections.Counter(m.group(0) for m in DEFERRAL.finditer(old))
    lost.subtract(m.group(0) for m in DEFERRAL.finditer(new))
    out = old
    for m in DEFERRAL.finditer(old):
        if lost[m.group(0)] <= 0:
            continue
        lost[m.group(0)] -= 1
        start, end = m.start(), m.end()
        lp = old.rfind("（", 0, start)
        rp_before = old.rfind("）", 0, start)
        if lp != -1 and lp > rp_before:                     # 在括號裡 → 遮整個括號
            rp = old.find("）", end)
            start, end = lp, (rp + 1 if rp != -1 else len(old))
        else:                                               # 否則遮到句末
            stop = min([p for p in (old.find(c, end) for c in "。；;") if p != -1] or [len(old)])
            end = stop
        out = mask_span(out, start, end)
    return out


HISTORY_WORD = re.compile(r"拍板|定案|議題")
PAREN = re.compile(r"（[^（）]*）|\([^()]*\)")


def mask_history(s, other=None):
    """遮歷程標籤；給 other（新行）時，舊行裡「帶歷程字樣、且新行沒有」的整個括號一併遮掉
    （例：「（US-T1.1 拍板、議題 X）」整段拿掉，裡面的 id 不算引用消失）。"""
    if other is not None:
        for m in PAREN.finditer(s):
            g = m.group(0)
            if g not in other and (HISTORY_TAG.search(g) or HISTORY_WORD.search(g)):
                s = mask_span(s, m.start(), m.end())
    return HISTORY_TAG.sub(lambda m: " " * len(m.group(0)), s)


def qual_counts(s):
    c = collections.Counter()
    for q, rx in QUAL_ORDER:
        n = len(rx.findall(s))
        if n:
            c[q] += n
            s = rx.sub(lambda m: " " * len(m.group(0)), s)
    return c


def ids_and_digits(s):
    ids = collections.Counter(re.sub(r"[§\s]", "", m.group(0)) for m in SPEC_ID.finditer(s))
    rest = SPEC_ID.sub(lambda m: " " * len(m.group(0)), s)
    return ids, collections.Counter(re.findall(r"\d+", rest))


def judge(old, new):
    o = mask_history(mask_removed_deferrals(old, new), new)
    n = mask_history(new)
    reasons = []
    qo, qn = qual_counts(o), qual_counts(n)
    lost = [f"{q}×{qo[q] - qn[q]}" for q, _ in QUAL_ORDER if qo[q] > qn[q]]
    if lost:
        reasons.append("限定詞變少：" + "、".join(lost))
    (io, do), (inn, dn) = ids_and_digits(o), ids_and_digits(n)
    gone_ids = sorted((io - inn).elements())
    if gone_ids:
        reasons.append("引用 id 不見：" + ",".join(gone_ids))
    if do != dn:
        gone = sorted((do - dn).elements())
        added = sorted((dn - do).elements())
        reasons.append("數字改變：" + "／".join(x for x in (
            ("少了 " + ",".join(gone)) if gone else "", ("多了 " + ",".join(added)) if added else "") if x))
    return reasons


def pair_lines(removed, added):
    """一對一貪婪配對：相似度由高到低，≥ PAIR_MIN 才算同一句的改寫。"""
    cands = []
    for i, (_, a) in enumerate(removed):
        for j, (_, b) in enumerate(added):
            sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
            if sm.real_quick_ratio() < PAIR_MIN or sm.quick_ratio() < PAIR_MIN:
                continue
            r = sm.ratio()
            if r >= PAIR_MIN:
                cands.append((r, i, j))
    used_i, used_j, pairs = set(), set(), []
    for r, i, j in sorted(cands, reverse=True):
        if i in used_i or j in used_j:
            continue
        used_i.add(i)
        used_j.add(j)
        pairs.append((removed[i], added[j]))
    return sorted(pairs, key=lambda p: p[1][0])


def hunks(rev):
    cmd = ["git", "-C", REPO, "-c", "core.quotePath=false", "diff", "--unified=0", "--no-color",
           "--src-prefix=a/", "--dst-prefix=b/",
           *rev.split(" "), "--", SCAN_ROOT]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    rel, removed, added, old_no, new_no = None, [], [], 0, 0

    def flush():
        if rel and removed and added:
            yield rel, list(removed), list(added)

    for ln in out.split("\n"):
        if ln.startswith("diff --git"):
            yield from flush()
            rel, removed, added = None, [], []
            continue
        if ln.startswith("+++ "):
            p = ln[6:] if ln.startswith("+++ b/") else None
            rel = p if p and p.endswith(".md") and not any(s in "/" + p for s in SKIP_PATH) else None
            continue
        if ln.startswith("--- "):
            continue
        if ln.startswith("@@"):
            yield from flush()
            removed, added = [], []
            m = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)", ln)
            old_no, new_no = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
            continue
        if ln.startswith("-"):
            removed.append((old_no, ln[1:]))
            old_no += 1
        elif ln.startswith("+"):
            added.append((new_no, ln[1:]))
            new_no += 1
    yield from flush()


def clip(s, n=160):
    s = s.strip()
    return s if len(s) <= n else s[:n] + "…"


def focus(old, new, n=70):
    """只印改動附近：去掉共同前後綴，各留一點上下文。"""
    i = 0
    while i < min(len(old), len(new)) and old[i] == new[i]:
        i += 1
    j = 0
    while j < min(len(old), len(new)) - i and old[-1 - j] == new[-1 - j]:
        j += 1
    s = max(0, i - 20)

    def cut(x):
        seg = x[s:len(x) - max(0, j - 20)]
        return ("…" if s else "") + clip(seg, n) + ("…" if j > 20 else "")
    return cut(old), cut(new)


def main():
    ap = argparse.ArgumentParser(description="SPEC 改寫時限定詞／數字消失提醒（advisory）")
    ap.add_argument("--diff", required=True, metavar="BASE",
                    help="比對起點：BASE（對工作樹）或 A..B（兩個 commit 之間）")
    a = ap.parse_args()
    try:
        flagged = []
        n_pairs = 0
        for rel, removed, added in hunks(a.diff):
            for (ono, old), (nno, new) in pair_lines(removed, added):
                n_pairs += 1
                reasons = judge(old, new)
                if reasons:
                    flagged.append((rel, nno, old, new, reasons))
    except subprocess.CalledProcessError as e:
        print(f"⚠️  git diff 失敗（{a.diff}）：{e.stderr.strip()}；跳過")
        return 0
    print(f"── [qualifier-guard] 改寫配對 {n_pairs} 對，限定詞／數字有變 {len(flagged)} 對（{a.diff}；advisory）──")
    for rel, nno, old, new, reasons in flagged:
        fo, fn = focus(old, new)
        print(f"  ⚠ {rel}:{nno}  {'；'.join(reasons)}")
        print(f"      - {fo}")
        print(f"      + {fn}")
    if flagged:
        print("\n  逐對確認：規則範圍真的沒變就不用動；變了就把限定詞補回正文。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
