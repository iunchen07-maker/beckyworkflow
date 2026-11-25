#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
numbering_lint — SPEC 編號檢查（全檔掃；規則權威＝workflow/SPEC_NUMBERING_RULES.md）

擋（❌，exit 1）：
  1. 同一檔內同一個 `US-` 節號（標題可寫 `US-` 或 `§US-`）出現兩次。
  2. 「驗收條件」節內的 `- **AC-N**` 清單：1～最大號都要出現、不可重複。退役要留佔位行
     （`- **AC-3**：已退役（保留編號）`），直接刪掉會被抓。不用 AC-N 清單的專案＝no-op。
  3. 保留編號不重用（有沒有 `Spec/Deferred/` 都查，跨檔也擋）：保留來源＝`Spec/Deferred/*.md` 檔頭的
     「保留編號：US-T3.2、N-07、US-T1.1/AC-3」行，＋正文含「已移至 Deferred/」或「保留編號」的
     US 標題／目錄列／AC 行，或 US 標題下一個非空行是「已退役（保留編號）」。同一個 id 又在正文以正式定義出現 → 違規。
報（⚠️，不影響 exit；§3.5：排列債務回報 PM，不擋寫入）：
  4. 同一層、同一字母前綴、同一父節底下的 `US-` 標題沒有依編號遞增排列。加 --strict-order 改為擋。

不查：跨檔重號、不同字母前綴之間的順序、H3 <seq> 跳號、AC 的排列順序、frontmatter、code fence、
`Spec/memory/`、History 資料夾。`Spec/Deferred/` 與 `Spec/BACKLOG.md` 只參與第 3 項。

用法：
  python3 Spec/.convert_tools/numbering_lint.py [--root <含 Spec/ 的資料夾>] [--strict-order]
"""
import argparse
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

# ── 專案常數（ci/decisions.py 也 import HEAD_RE、CATALOG_*、DEF_SKIP_NAMES、PLACEHOLDER_RE）──
US_ID = r'US-[A-Z]+[0-9]+(?:\.(?:[0-9]+|[A-Z]))*'
CATALOG_ID = r'[NR]-\d{1,3}'                    # 目錄列編號：N-07（通知）、R-3（提醒）
CATALOG_FILE_SUBSTR = 'Notifications'           # 檔名含此字串的檔才認目錄列（首欄＝編號）
AC_SECTION = '驗收條件'                          # 標題含此字串的節才查 AC 清單
AC_RE = re.compile(r'^- (?:~~|〜〜)?\*\*AC-(\d+)\*\*')
DEF_SKIP_NAMES = {'INDEX.md', 'README.md', 'BACKLOG.md'}

HEAD_RE = re.compile(r'^(#{2,6})\s+(?:~~)?(?:§\s*)?(' + US_ID + r')(?![0-9A-Za-z.])')
CATALOG_ROW_RE = re.compile(r'^\|\s*(?:~~)?\**(?:~~)?(' + CATALOG_ID + r')(?!\d)')


def ver(uid):
    parts = uid[3:].split('.')
    head = int(re.sub(r'^[A-Z]+', '', parts[0]))
    return ((0, head),) + tuple((0, int(x)) if x.isdigit() else (1, x) for x in parts[1:])


def body_start(lines):
    if lines and lines[0] == '---':
        for i in range(1, len(lines)):
            if lines[i] == '---':
                return i + 1
    return 0


def scan(path, rel):
    """回傳 (errors, order_warnings)。"""
    errors, order = [], []
    lines = open(path, encoding='utf-8').read().split('\n')
    last, seen = {}, {}          # last: (level, prefix, parent) -> (ver, uid)
    ac_sec, acs = None, []       # ac_sec: (uid, line)
    fence = False

    def flush():
        if ac_sec and acs:
            miss = sorted(set(range(1, max(acs) + 1)) - set(acs))
            dup = sorted({n for n in acs if acs.count(n) > 1})
            if miss:
                errors.append(f'{rel}:{ac_sec[1]} {ac_sec[0]} 缺 AC：{miss}（退役請留佔位行）')
            if dup:
                errors.append(f'{rel}:{ac_sec[1]} {ac_sec[0]} AC 重複：{dup}')

    for ln in range(body_start(lines), len(lines)):
        t = lines[ln]
        if t.startswith('```'):
            fence = not fence
        if fence:
            continue
        m = HEAD_RE.match(t)
        if m or re.match(r'^#{1,6}\s', t):
            flush()
            ac_sec, acs = None, []
        if m:
            lvl, uid = len(m.group(1)), m.group(2)
            if uid in seen:
                errors.append(f'{rel}:{ln + 1} 節號 {uid} 重複（首見行 {seen[uid]}）')
            seen.setdefault(uid, ln + 1)
            v = ver(uid)
            key = (lvl, re.match(r'US-[A-Z]+', uid).group(0), v[:-1] if lvl > 2 else ())
            prev = last.get(key)
            if prev and v < prev[0]:
                order.append(f'{rel}:{ln + 1} 節號 {uid} 排在 {prev[1]} 後面（應遞增）')
            last[key] = (v, uid)
            for k in [k for k in last if k[0] > lvl]:
                del last[k]
            if AC_SECTION in t:
                ac_sec = (uid, ln + 1)
        elif ac_sec:
            a = AC_RE.match(t)
            if a:
                acs.append(int(a.group(1)))
    flush()
    return errors, order


# ── 3. 保留編號（Spec/Deferred/）：保留的 id 不得再被正文當成新定義使用 ──────────
PLACEHOLDER_RE = re.compile(r'已移至\s*`?(?:Spec/)?Deferred/|保留編號')
RETIRED_NEXT_RE = re.compile(r'^[>\s*_（(-]*已退役\**\s*[（(]\s*保留編號')   # 規則書 §3.5 的退役寫法
RESERVE_LINE_RE = re.compile(r'^\s*(?:>\s*)?\**保留編號\**\s*[：:]\s*(.+)$')
RES_TOKEN = re.compile(r'§?(' + US_ID + r')(?:\s*[/／]\s*(AC-\d+))?|(?<![A-Za-z0-9-])§?(' + CATALOG_ID + r')(?!\d)')


def is_deferred(rel):
    """Spec/Deferred/ 與 Spec/BACKLOG.md：逐字搬出的延後原文，只參與保留編號檢查、不查 1／2。"""
    parts = rel.split(os.sep)
    return parts[:2] == ['Spec', 'Deferred'] or parts == ['Spec', 'BACKLOG.md']


def res_keys(text):
    out = []
    for m in RES_TOKEN.finditer(text):
        if m.group(1):
            out.append(m.group(1) + (f'/{m.group(2)}' if m.group(2) else ''))
        else:
            out.append(m.group(3))
    return out


def reserved_from_deferred(root):
    """Spec/Deferred/*.md 開頭（frontmatter 後前 20 個非空行）的「保留編號：…」行 → {key: 位置}。"""
    out = {}
    for p in sorted(glob.glob(os.path.join(root, 'Spec', 'Deferred', '*.md'))):
        rel = os.path.relpath(p, root)
        lines = open(p, encoding='utf-8').read().split('\n')
        seen = 0
        for ln in range(body_start(lines), len(lines)):
            if not lines[ln].strip():
                continue
            seen += 1
            if seen > 20:
                break
            m = RESERVE_LINE_RE.match(lines[ln])
            if m:
                for k in res_keys(m.group(1)):
                    out.setdefault(k, f'{rel}:{ln + 1}')
    return out


def scan_defs(path, rel):
    """回傳 (佔位 {key: 位置}, 正式定義 {key: [位置]})。
    key：US 標題＝US-X.Y；目錄列＝N-07 等；AC＝US-X.Y/AC-N（掛在最近的 US 標題下）。
    佔位＝該行含「已移至 Deferred/」或「保留編號」，或 US 標題下一個非空行是「已退役（保留編號）」；刪除線（~~）的退役行不算正式定義。"""
    ph, live = {}, {}
    lines = open(path, encoding='utf-8').read().split('\n')
    is_catalog = CATALOG_FILE_SUBSTR in os.path.basename(path)
    cur = None
    fence = False

    def put(key, line_no, text, struck):
        loc = f'{rel}:{line_no}'
        if PLACEHOLDER_RE.search(text):
            ph.setdefault(key, loc)
        elif not struck:
            live.setdefault(key, []).append(loc)

    for ln in range(body_start(lines), len(lines)):
        t = lines[ln]
        if t.startswith('```'):
            fence = not fence
        if fence:
            continue
        m = HEAD_RE.match(t)
        if m:
            cur = m.group(2)
            nxt = next((x for x in lines[ln + 1:] if x.strip()), '')
            retired = '（保留編號）' if RETIRED_NEXT_RE.match(nxt) else ''
            put(cur, ln + 1, t + retired, t[len(m.group(1)):].lstrip().startswith('~~'))
            continue
        m = AC_RE.match(t)
        if m and cur:
            put(f'{cur}/AC-{m.group(1)}', ln + 1, t, t[2:4] in ('~~', '〜〜'))
            continue
        if is_catalog:
            m = CATALOG_ROW_RE.match(t)
            if m:
                put(m.group(1), ln + 1, t, '~~' in t[:12])
    return ph, live


def reservation_findings(root, rels):
    reserved = reserved_from_deferred(root)
    live = {}
    for rel in rels:
        parts = rel.split(os.sep)
        if 'Deferred' in parts or os.path.basename(rel) in DEF_SKIP_NAMES:
            continue
        ph, lv = scan_defs(os.path.join(root, rel), rel)
        for k, loc in ph.items():
            reserved.setdefault(k, loc)
        for k, locs in lv.items():
            live.setdefault(k, []).extend(locs)
    out = []
    for k in sorted(set(reserved) & set(live)):
        for loc in live[k]:
            out.append(f'{loc} {k} 是保留編號（{reserved[k]}），不得再拿來定義新內容；改用新編號')
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=REPO, help='含 Spec/ 的資料夾（預設本 repo）')
    ap.add_argument('--strict-order', action='store_true', help='排列沒遞增也擋（預設只報）')
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    errors, order, rels = [], [], []
    for p in sorted(glob.glob(os.path.join(root, 'Spec', '**', '*.md'), recursive=True)):
        rel = os.path.relpath(p, root)
        if rel.startswith(os.path.join('Spec', 'memory') + os.sep) or 'History' in rel:
            continue
        rels.append(rel)
        if not is_deferred(rel):
            e, o = scan(p, rel)
            errors += e
            order += o
    errors += reservation_findings(root, rels)
    if a.strict_order:
        errors, order = errors + order, []
    print(f'── [numbering-lint] 掃 {len(rels)} 檔：重號／AC 連續／保留編號不重用（擋）、排列遞增（報）──')
    for f in errors:
        print('  ❌ ' + f)
    for f in order:
        print('  ⚠️ ' + f + '——回報 PM，不搬節、不重編')
    print(f'  {len(errors)} 處違規' if errors else '  ✅ 0 處違規')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
