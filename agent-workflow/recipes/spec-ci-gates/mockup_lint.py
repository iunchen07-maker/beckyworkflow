#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mockup_lint.py — Mockup「規格不落畫面＋元素要有依據」的確定性 linter（非 LLM）。

規則權威：workflow/phase-1-product-design.md「標注鐵則」。專案差異（路徑、狀態碼、白名單 class、
視覺紅線）都在檔頭「專案常數」。

規則：
  R1 規格字眼落畫面：只檢可見文字（HTML 文字節點；<style>／<script>／<title> 與屬性值不檢）：
     §US／US-ID／AC-ID／cross-ref／狀態 enum／討論過程詞。白名單 meta 子樹整棵豁免 R1、R3、R5：
     class 命中 WHITELIST_CLASSES，或 inline style 背景色命中 META_BG。
  R2 視覺紅線：BANNED_CSS、BANNED_COLORS、border-radius 不在 LEGAL_RADII。只掃 <style> 區塊與
     style="…"（說明文字裡「提到」紅線不算用了）；先把 var(--x) 解成實際值再驗，未定義的變數照樣亮燈。
  R3 三屬性：帶 data-action 的元素缺 data-testid 或 data-spec；同檔 data-testid 重複。
  R5 無依據元素：帶 data-action 的元素，自己的 data-spec 引不出 SPEC 節號，又沒掛
     `data-chrome="true"`（承認是 UI 慣例元素、沒有專屬 SPEC，如縮放、重試）。刻意不做祖先繼承：
     容器引了節號就讓子元素免驗，等於容器的依據罩住任何塞進去的鈕。預設只報不擋（R5_BLOCKS）。
     R5 擋不住「引到別的畫面的依據」——那靠 --audit 盤點表由 PM 目視。
  R6 延後功能字眼未標延後：只掃 HTML設計稿/定案/*.html，🔴 不受 baseline 豁免；
     `--deferred` 會跑（含 index.html）；`--file` 對定案稿也跑，但不查 index.html；`--all` 不跑。
     關鍵詞＝Spec/Deferred/*.md 第二行「關鍵詞：a、b、c」（分隔 、 , ，），沒寫這行 → R6 設定錯。
     逐字、大小寫敏感；英數開頭／結尾的關鍵詞加邊界（N-11 不吃 N-110）。
     掃可見文字（含 <title>）、data-spec、<script> 的字串常值；不掃註解、<style>、其他屬性值，
     及 index.html 的 footer 更新紀錄（class="updated" 子樹、含「最後更新」的行）。
     任一成立即放行：(a) 同一原始行有「延後功能」或「Deferred/」；(b) 該元素或祖先的 data-spec 有
     「延後功能」或「Deferred/」；(c) 檔內有整頁 banner「本頁整頁為延後功能」。

JS 產生的標記（規則名帶 `·js` 後綴）：靜態 parser 看不到 <script> 裡用字串拼出來的標記，JS 渲染型
mockup 會有一大塊不受守。本工具把 script 切成「字串鏈」（由 `+` 串起、中間不跨 ; , { } 的字串常數，
運算式換成佔位符 ░），還原成近似 HTML 再餵同一組 R1／R3／R5。不含標籤的孤兒字串只驗 R1。
  已知邊界：跨 ; , { } 的鏈會被切斷；反引號樣板字串不當字串常值解析（R6 例外）；正則字面值用啟發式判定。

排除：index.html（導覽物）、*.wire.html（線稿）、路徑含 History 的檔（封存禁區，--file 指到也不讀）。
Baseline：mockup_lint_baseline.txt — 整檔豁免 R1–R3／R5 的清單，每行一個相對 repo 根的路徑，# 為註解；
  沒有這個檔＝沒有豁免。只收 定案/：清單裡有別的路徑就直接失敗（手改也擋）；討論中/ 的新稿必須直接合規。
  只縮不長：--check-baseline-shrink REF 比 REF 版多出任何一筆 → exit 1（REF 還沒有 baseline＝首次引入、不比）。

用法：
  python3 Spec/.convert_tools/mockup_lint.py --selftest                 # 規則正／反案例（含 R6）
  python3 Spec/.convert_tools/mockup_lint.py --all
  python3 Spec/.convert_tools/mockup_lint.py --deferred                 # R6
  python3 Spec/.convert_tools/mockup_lint.py --file HTML設計稿/討論中/T1-task-list.html
  python3 Spec/.convert_tools/mockup_lint.py --audit HTML設計稿/討論中/T1-task-list.html
  python3 Spec/.convert_tools/mockup_lint.py --update-baseline
  python3 Spec/.convert_tools/mockup_lint.py --check-baseline-shrink <REF>

掃描範圍單層 glob、不遞迴。違規 exit 1、乾淨 exit 0。
"""
import argparse
import re
import subprocess
import sys
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BASELINE = HERE / "mockup_lint_baseline.txt"

# ── 專案常數（安裝後改成自己的值）────────────────────────────
SCAN_DIRS = [Path("HTML設計稿") / "定案", Path("HTML設計稿") / "討論中"]
FINAL_DIR = (Path("HTML設計稿") / "定案").as_posix()
WIP_DIR = (Path("HTML設計稿") / "討論中").as_posix()

ARCHIVE_SUBSTR = "History"
EXCLUDE_NAMES = {"index.html"}      # 設計稿索引＝導覽物，非產品畫面
EXCLUDE_SUFFIX = ".wire.html"        # 線稿＝灰階 wireframe，不掛 data-*、規格註記本來就是它的用途

# R1：SPEC 的狀態碼（含退役舊值）
STATE_ENUMS = ["task_open", "task_done", "task_archived", "list_active", "list_archived",
               "role_owner", "role_collaborator", "role_viewer"]
DISCUSSION_WORDS = r"拍板|待拍|PENDING|mock 值"
# meta 層 class：規格資訊列、DEMO 切換列、狀態展示標題、§ 出處 chip、⚠ 活待辦標記、情境標題與註解
WHITELIST_CLASSES = {"spec-bar", "demo-bar", "state-label", "spec-chip", "todo-mark",
                     "case-title", "case-note"}
META_BG = ("#ABCDEF",)               # meta 列的背景色
# R2
BANNED_CSS = ("box-shadow", "gradient(", "backdrop-filter")
BANNED_COLORS = {"#ff00ff": "舊主色，已換掉"}      # 小寫
LEGAL_RADII = {"0", "4px", "50%", "999px"}
# R5：data-spec 要引得出 SPEC 節號。規則書沒有明文要求每個元素都引節號 → 預設只報；要擋改 True
R5_BLOCKS = False
SPEC_REF_RE = re.compile(r"US-[A-Z]{1,2}\d+(?:\.\d+)*|(?<![A-Za-z0-9-])[NR]-\d+|Glossary")


def is_archived(path) -> bool:
    return ARCHIVE_SUBSTR in str(path)


# ---------- R1 規格字眼 ----------
# 左右邊界是 \b 的中文安全等價：中文字算 \w，「狀態task_open」緊貼時 \b 會漏
_B = r"(?<![A-Za-z0-9_])"
_E = r"(?![A-Za-z0-9_])"
R1_PATTERNS = [
    ("§US", re.compile(r"§US")),
    ("US-ID", re.compile(_B + r"US-[A-Z]{1,2}\d")),
    ("AC-ID", re.compile(_B + r"AC-\d+")),
    ("cross-ref", re.compile(r"cross-ref", re.IGNORECASE)),
    ("狀態enum", re.compile(_B + "(?:" + "|".join(map(re.escape, STATE_ENUMS)) + ")" + _E)),
    ("討論過程詞", re.compile(DISCUSSION_WORDS)),
]

META_BG_RE = re.compile(r"background(?:-color)?:\s*(?:" + "|".join(map(re.escape, META_BG)) + ")", re.IGNORECASE)

# ---------- HTML 解析 ----------
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
             "link", "meta", "param", "source", "track", "wbr"}
SKIP_TEXT_TAGS = {"style", "script", "title"}


class MockupChecker(HTMLParser):
    def __init__(self, tag="", check_dup_testids=True):
        super().__init__(convert_charrefs=True)
        self.tag = tag                  # 規則名後綴（JS 產生的標記＝"·js"）
        self.col_mode = bool(tag)       # JS 模式：湯是單行，改記 col 供事後映射回原始行
        self.check_dup = check_dup_testids
        self.stack = []
        self.r1_depth = 0
        self.meta_depth = 0
        self.skip_depth = 0
        self.hits = []
        self.testids = defaultdict(list)
        self.actions = []      # (lineno, action, testid, refs) — 供 --audit

    def _r(self, rule):
        return rule + self.tag

    def _pos(self):
        p = self.getpos()
        return p[1] if self.col_mode else p[0]

    def _flags(self, attrs):
        style = attrs.get("style") or ""
        classes = set((attrs.get("class") or "").split())
        meta = bool(META_BG_RE.search(style)) or self._is_meta_class(classes)
        return meta, meta

    @staticmethod
    def _is_meta_class(classes):
        """白名單比對容許單層畫面前綴：單檔多畫面的稿會寫成 `t1-case-note`。
        不做子字串比對，免得 `my-case-note-wrapper` 這類無關 class 也被豁免。"""
        if classes & WHITELIST_CLASSES:
            return True
        for c in classes:
            if "-" in c and c.split("-", 1)[1] in WHITELIST_CLASSES:
                return True
        return False

    def _check_attrs(self, attrs, lineno, meta_subtree):
        if "data-testid" in attrs and attrs["data-testid"]:
            self.testids[attrs["data-testid"]].append(lineno)
        if "data-action" in attrs and not meta_subtree:
            action = attrs["data-action"]
            missing = [a for a in ("data-testid", "data-spec") if not attrs.get(a)]
            if missing:
                self.hits.append((lineno, self._r("R3"),
                                  'data-action="%s" 缺 %s（三屬性鐵則）'
                                  % (action, "、".join(missing)), ""))
            spec = attrs.get("data-spec") or ""
            refs = sorted(set(SPEC_REF_RE.findall(spec)))
            self.actions.append((lineno, action, attrs.get("data-testid", ""), refs,
                                 "data-chrome" in attrs))
            if spec and not refs and "data-chrome" not in attrs:
                self.hits.append((lineno, self._r("R5"),
                                  'data-action="%s" 的 data-spec 引不出任何 SPEC 節號'
                                  '（無依據元素：先確認 SPEC 有這條，或掛 data-chrome）' % action,
                                  spec[:70]))

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        lineno = self._pos()
        r1, meta = self._flags(attrs)
        self._check_attrs(attrs, lineno, self.meta_depth > 0 or meta)
        if tag in VOID_TAGS:
            return
        skip = tag in SKIP_TEXT_TAGS
        self.stack.append((tag, r1, meta, skip))
        self.r1_depth += r1
        self.meta_depth += meta
        self.skip_depth += skip

    def handle_startendtag(self, tag, attrs):
        attrs = dict(attrs)
        r1, meta = self._flags(attrs)
        self._check_attrs(attrs, self._pos(), self.meta_depth > 0 or meta)

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                for (_t, r1, meta, skip) in self.stack[i:]:
                    self.r1_depth -= r1
                    self.meta_depth -= meta
                    self.skip_depth -= skip
                del self.stack[i:]
                break

    def handle_data(self, data):
        if self.skip_depth > 0 or self.r1_depth > 0:
            return
        base = self._pos()
        for off, seg in enumerate(data.split("\n")):
            if self.col_mode:
                off = 0
            if not seg.strip():
                continue
            for label, pat in R1_PATTERNS:
                m = pat.search(seg)
                if m:
                    self.hits.append((base + off, self._r("R1"),
                                      "規格字眼落入可見文字：「%s」（%s）"
                                      % (m.group(0), label), seg.strip()))
                    break

    def finish(self):
        if not self.check_dup:
            return self.hits
        for tid, lns in sorted(self.testids.items()):
            if len(lns) > 1:
                for ln in lns[1:]:
                    self.hits.append((ln, self._r("R3"),
                                      'data-testid="%s" 重複（首見行 %d）' % (tid, lns[0]), ""))
        return self.hits


# ---------- R2 視覺紅線 ----------
RADIUS_RE = re.compile(r"border-radius:\s*([^;{}\"']+)")


def _css_regions(text):
    """回傳 [(起始 offset, CSS 文字)]：<style> 區塊＋style="…" 屬性值。"""
    out = []
    for m in re.finditer(r"<style\b[^>]*>(.*?)</style>", text, re.S | re.I):
        out.append((m.start(1), m.group(1)))
    for m in re.finditer(r"""\bstyle\s*=\s*(["'])(.*?)\1""", text, re.S | re.I):
        out.append((m.start(2), m.group(2)))
    return out


CUSTOM_PROP_RE = re.compile(r"(--[\w-]+)\s*:\s*([^;{}]+)")
VAR_USE_RE = re.compile(r"var\(\s*(--[\w-]+)\s*(?:,\s*([^()]*?)\s*)?\)")


def _custom_props(text):
    """收集全檔的 CSS 自訂屬性宣告 → {--name: value}。"""
    props = {}
    for _base, css in _css_regions(text):
        for m in CUSTOM_PROP_RE.finditer(css):
            props.setdefault(m.group(1), m.group(2).strip())
    return props


def _resolve_vars(line, props, depth=0):
    """把 var(--x) 換成實際值；解不出來換成不會被當成合法值的記號。"""
    if depth > 4 or "var(" not in line:
        return line

    def sub(m):
        name, fallback = m.group(1), m.group(2)
        if name in props:
            return props[name]
        if fallback:
            return fallback
        return "⟪未定義的變數 %s⟫" % name

    return _resolve_vars(VAR_USE_RE.sub(sub, line), props, depth + 1)


def scan_r2(text):
    hits, props = [], _custom_props(text)
    for base, css in _css_regions(text):
        line0 = text.count("\n", 0, base) + 1
        for off, line in enumerate(css.split("\n")):
            hits.extend(_scan_r2_line(_resolve_vars(line, props), line0 + off))
    return sorted(set(hits))


def _scan_r2_line(line, i):
    hits = []
    low = line.lower()
    for word in BANNED_CSS:
        if word in re.sub(re.escape(word) + r"\s*:\s*none", "", low):
            hits.append((i, "R2", "禁用 %s（視覺紅線）" % word.rstrip("("), line.strip()))
    for color, why in BANNED_COLORS.items():
        if color in low:
            hits.append((i, "R2", "禁用色值 %s（%s）" % (color, why), line.strip()))
    for m in RADIUS_RE.finditer(line):
        val = m.group(1).strip()
        if val not in LEGAL_RADII:
            hits.append((i, "R2", "非法圓角 %s（只准 %s）" % (val, "／".join(sorted(LEGAL_RADII))), line.strip()))
    return hits


# R2 自我測試：說明文字裡提到紅線關鍵字，不得誤判為使用
R2_SELFTEST = [
    ("R2 真的用了 box-shadow", 1, '<style>.c{ box-shadow:0 2px 4px #FFF; }</style>'),
    ("R2 inline style 也要抓", 1, '<div style="border-radius:8px">x</div>'),
    ("R2 說明文字提到不算用", 0, '<style>.c{ border-radius:4px; }</style><p>設計規範禁 box-shadow 與 gradient</p>'),
    ("R2 合法圓角不誤報", 0, '<style>.c{ border-radius:4px; } .p{ border-radius:999px; }</style>'),
    # ↓ CSS 變數：解得開就驗實際值，解不開不得放行
    ("R2 變數解出合法值", 0, '<style>:root{--r:4px}.c{ border-radius:var(--r); }</style>'),
    ("R2 變數解出非法值", 1, '<style>:root{--r:8px}.c{ border-radius:var(--r); }</style>'),
    ("R2 未定義變數不得放行", 1, '<style>.c{ border-radius:var(--nope); }</style>'),
    ("R2 禁用色值", 1, '<style>.c{ color:#FF00FF; }</style>'),
    ("R2 變數藏 box-shadow 也要抓", 1, '<style>:root{--e:box-shadow:0 2px 4px #FFF}.c{ --x:var(--e); }</style>'),
]


# ---------- JS 產生的標記 ----------
# 做法：把 script 內容切成「字串鏈」——由 `+` 串起、中間不跨 ; , { } 的字串常數序列，
# 運算式位置換成佔位符——還原成近似 HTML 的湯，再餵給同一組規則。
# 只有含 `<tag` 的鏈才進 HTML 解析（`getElementById('crumb')` 這種孤兒字串不算標記）。
PH = "░"                     # 佔位：JS 運算式（不觸發任何規則）
_HTMLISH_RE = re.compile(r"<[a-zA-Z]")
_REGEX_PREV = set("(,=:[!&|?{};+-*%~^ \t\n\r")
# 孤兒字串若是這類「註記欄位」的值，之後會被拼成 data-spec 之類的屬性，不是畫面文字。
ANNOT_KEY_RE = re.compile(r"\b\w*(?:spec|anno|note|desc|doc|tip|help)\w*\s*[:=]\s*$", re.I)


def _js_tokens(src, base_line):
    """把 script 內容切成 ('str'|'code', text, 起始行) —— 註解剔除、正則字面值當 code。"""
    out, i, n, line = [], 0, len(src), base_line
    buf, buf_line = [], base_line

    def flush():
        nonlocal buf, buf_line
        if buf:
            out.append(("code", "".join(buf), buf_line))
            buf = []

    def prev_code_char():
        for ch in reversed(buf):
            if not ch.isspace():
                return ch
        return "("

    while i < n:
        c = src[i]
        if c in "'\"":
            j, parts = i + 1, []
            while j < n:
                if src[j] == "\\":
                    parts.append(src[j + 1:j + 2])
                    j += 2
                    continue
                if src[j] == c:
                    break
                parts.append(src[j])
                j += 1
            flush()
            out.append(("str", "".join(parts), line))
            line += src[i:j + 1].count("\n")
            i, buf_line = j + 1, line
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            j = n if j < 0 else j
            flush()
            buf_line = line
            i = j
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            flush()
            line += src[i:j].count("\n")
            buf_line = line
            i = j
            continue
        if c == "/" and prev_code_char() in _REGEX_PREV:
            j = i + 1                       # 正則字面值：整段吞掉，別讓裡面的引號亂拆
            while j < n and src[j] != "\n":
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == "]":
                    pass
                if src[j] == "/":
                    break
                j += 1
            if j < n and src[j] == "/":
                if not buf:
                    buf_line = line
                buf.append(" ")
                i = j + 1
                continue
        if c == "\n":
            line += 1
        if not buf:
            buf_line = line
        buf.append(c)
        i += 1
    flush()
    return out


def _js_chains(tokens):
    """回傳 [(起始行, 湯, [(湯內 col, 原始行)], 鏈前的 code 尾巴)]。"""
    chains, parts, cols, start, prev = [], [], [], None, ""
    last_code = ""

    def close():
        nonlocal parts, cols, start, prev
        if parts:
            chains.append((start, "".join(parts), list(cols), prev))
        parts, cols, start, prev = [], [], None, ""

    for kind, text, line in tokens:
        if kind == "str":
            if start is None:
                start, prev = line, last_code[-80:]
            cols.append((sum(len(p) for p in parts), line))
            parts.append(text.replace("\n", " "))
        else:
            last_code = text
            if start is None:
                continue
            if any(ch in text for ch in ";,{}") or "+" not in text:
                close()
            else:
                parts.append(PH)
    close()
    return chains


def _col_to_line(cols, col):
    src = cols[0][1] if cols else 0
    for c, ln in cols:
        if c <= col:
            src = ln
        else:
            break
    return src


def scan_js(text, want_actions=False):
    """對 script 內用字串拼出來的標記，套 R1／R3／R5。"""
    hits, actions = [], []
    for m in re.finditer(r"<script\b[^>]*>(.*?)</script>", text, re.S | re.I):
        base = text.count("\n", 0, m.start(1)) + 1
        chains = _js_chains(_js_tokens(m.group(1), base))
        for start_line, soup, cols, prev in chains:
            if not _HTMLISH_RE.search(soup):
                # 非標記的孤兒字串：仍可能是被塞進畫面的可見文案，只驗 R1。
                if "=\"" in soup or soup.lstrip().startswith("data-"):
                    continue
                if ANNOT_KEY_RE.search(prev):
                    continue          # 註記欄位的值（spec:/anno:/note:…），之後才變 data-* 屬性
                for label, pat in R1_PATTERNS:
                    mm = pat.search(soup)
                    if mm:
                        hits.append((start_line, "R1·js",
                                     "規格字眼落入 JS 產生的可見文字：「%s」（%s）"
                                     % (mm.group(0), label), soup.strip()[:80]))
                        break
                continue
            ck = MockupChecker(tag="·js", check_dup_testids=False)
            ck.feed(soup)
            ck.close()
            for col, rule, msg, ctx in ck.finish():
                hits.append((_col_to_line(cols, col), rule, msg, ctx))
            for a in ck.actions:
                actions.append((_col_to_line(cols, a[0]),) + tuple(a[1:]))
    return (hits, actions) if want_actions else hits


# ---------- 檔案層 ----------
def lint_file(path: Path, want_actions=False):
    text = path.read_text(encoding="utf-8", errors="replace")
    checker = MockupChecker()
    checker.feed(text)
    checker.close()
    js_hits, js_actions = scan_js(text, want_actions=True)
    hits = checker.finish() + scan_r2(text) + js_hits
    hits = sorted(hits, key=lambda h: (h[0], h[1]))
    if not want_actions:
        return hits
    acts = ([tuple(a) + ("html",) for a in checker.actions]
            + [tuple(a) + ("js",) for a in js_actions])
    return hits, sorted(acts, key=lambda a: a[0])


def target_files():
    out = []
    for d in SCAN_DIRS:
        dp = REPO / d
        if not dp.is_dir():
            continue
        for f in sorted(dp.glob("*.html")):
            if (is_archived(f.relative_to(REPO)) or f.name in EXCLUDE_NAMES
                    or f.name.endswith(EXCLUDE_SUFFIX)):
                continue
            out.append(f)
    return out


def parse_baseline(text):
    return {ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")}


def load_baseline():
    files = parse_baseline(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else set()
    bad = sorted(f for f in files if not f.startswith(FINAL_DIR + "/") or ".." in f.split("/"))
    if bad:
        print("❌ %s 只收 %s/，不得列入：%s" % (BASELINE.name, FINAL_DIR, "、".join(bad)))
        sys.exit(1)
    return files


def run_check_shrink(ref):
    def git(*args):
        return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True)
    if git("rev-parse", "-q", "--verify", ref + "^{commit}").returncode:
        print("❌ 找不到 %s，無法比對 baseline" % ref)
        return 1
    cur = load_baseline()
    r = git("show", "%s:%s" % (ref, BASELINE.relative_to(REPO).as_posix()))
    if r.returncode:
        print("── [mockup-lint] %s 尚無 baseline 檔：首次引入，不比對 ──" % ref)
        return 0
    grown = sorted(cur - parse_baseline(r.stdout))
    print("── [mockup-lint] baseline 只能縮小（相對 %s）──" % ref)
    for f in grown:
        print("  ❌ 新增 baseline 項：" + f)
    if not grown:
        print("  ✅ 沒有新增項")
    return 1 if grown else 0


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def is_advisory(rule):
    return rule.startswith("R5") and not R5_BLOCKS


def report(per_file, n_scanned, n_baseline_skipped):
    """印清單＋統計，回傳會擋的違規數。"""
    blocking = defaultdict(int)
    advisory = 0
    for rp in sorted(per_file):
        for lineno, rule, msg, ctx in per_file[rp]:
            soft = is_advisory(rule)
            advisory += soft
            if not soft:
                blocking[rule] += 1
            tail = ("  | " + ctx[:80]) if ctx else ""
            print("  %s %s:%d: [%s] %s%s" % ("⚠️" if soft else "❌", rp, lineno, rule, msg, tail))
    total = sum(blocking.values())
    print()
    print("── 統計 ──")
    print("  掃描 %d 檔（baseline 豁免跳過 %d 檔）" % (n_scanned, n_baseline_skipped))
    if advisory:
        print("  ⚠️ %d 處 R5 只報不擋（R5_BLOCKS）" % advisory)
    if total:
        print("  ❌ 共 %d 處違規（%s）" % (total, " / ".join("%s: %d" % (r, blocking[r]) for r in sorted(blocking))))
    else:
        print("  ✅ 0 處違規")
    return total


# ---------- R6 延後功能字眼（不受 baseline 豁免）----------
DEFERRED_DIR = REPO / "Spec" / "Deferred"
KW_LINE_RE = re.compile(r"^\s*關鍵詞\s*[：:]\s*(.+?)\s*$")
DEFERRED_MARKERS = ("延後功能", "Deferred/")
PAGE_BANNER = "本頁整頁為延後功能"
FOOTER_LINE_MARK = "最後更新"          # index.html footer 更新紀錄
FOOTER_CLASS = "updated"               # index.html footer <p class="updated">


def load_deferred_keywords():
    """回傳 (kw_map, config_errors)。kw_map: keyword -> Deferred 檔名。"""
    kws, errors = {}, []
    if not DEFERRED_DIR.is_dir():
        return kws, errors
    for md in sorted(DEFERRED_DIR.glob("*.md")):
        lines = md.read_text(encoding="utf-8", errors="replace").splitlines()
        words = None
        if len(lines) >= 2:
            m = KW_LINE_RE.match(lines[1])
            if m:
                words = [w.strip() for w in re.split(r"[、,，]", m.group(1)) if w.strip()]
        if not words:
            errors.append(md.name)
            continue
        for w in words:
            kws.setdefault(w, md.name)
    return kws, errors


def build_kw_regex(kws):
    if not kws:
        return None
    parts = []
    for w in sorted(kws, key=len, reverse=True):   # 長詞優先
        p = re.escape(w)
        if re.match(r"[A-Za-z0-9]", w):
            p = r"(?<![A-Za-z0-9_-])" + p          # N-11 不吃 XN-11
        if re.search(r"[A-Za-z0-9]$", w):
            p = p + r"(?![A-Za-z0-9_])"            # N-11 不吃 N-110
        parts.append(p)
    return re.compile("|".join(parts))             # 大小寫敏感：照 Deferred 檔寫法逐字比對


def has_marker(s):
    return any(m in s for m in DEFERRED_MARKERS)


def js_string_literals(code):
    """極簡 JS lexer：回傳 [(offset, content)]，跳過 // 與 /* */ 註解。"""
    out, i, n = [], 0, len(code)
    while i < n:
        c = code[i]
        if c == "/" and i + 1 < n and code[i + 1] == "/":
            j = code.find("\n", i)
            i = n if j < 0 else j
        elif c == "/" and i + 1 < n and code[i + 1] == "*":
            j = code.find("*/", i + 2)
            i = n if j < 0 else j + 2
        elif c in "'\"`":
            j = i + 1
            while j < n and code[j] != c:
                if code[j] == "\\":
                    j += 1
                elif code[j] == "\n" and c != "`":
                    break
                j += 1
            out.append((i + 1, code[i + 1:j]))
            i = j + 1
        else:
            i += 1
    return out


class DeferredScanner(HTMLParser):
    def __init__(self, kw_re, raw_lines, is_index):
        super().__init__(convert_charrefs=True)
        self.kw_re = kw_re
        self.raw_lines, self.is_index = raw_lines, is_index
        self.stack = []          # (tag, deferred, excluded)
        self.deferred_depth = 0  # >0 → 祖先已標延後
        self.excluded_depth = 0  # >0 → footer 更新紀錄
        self.mode = []           # 'script' / 'style' / None
        self.hits = []           # (lineno, kw, excerpt)

    def _line(self, ln):
        return self.raw_lines[ln - 1] if 0 < ln <= len(self.raw_lines) else ""

    def _check(self, text, base_line, element_deferred=False):
        """text 內每個關鍵詞命中 → 依放行條件判斷；base_line＝text 第一個字元所在行。"""
        if self.deferred_depth > 0 or self.excluded_depth > 0 or element_deferred:
            return
        for m in self.kw_re.finditer(text):
            ln = base_line + text.count("\n", 0, m.start())
            raw = self._line(ln)
            if has_marker(raw):
                continue
            if self.is_index and FOOTER_LINE_MARK in raw:
                continue
            self.hits.append((ln, m.group(0), raw.strip()))

    def _check_spec_attr(self, attrs):
        spec = attrs.get("data-spec") or ""
        if spec:
            raw_tag = self.get_starttag_text() or ""
            k = raw_tag.find("data-spec")
            base = self.getpos()[0] + (raw_tag.count("\n", 0, k) if k >= 0 else 0)
            self._check(spec, base, element_deferred=has_marker(spec))
        return spec

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        spec = self._check_spec_attr(attrs)
        if tag in VOID_TAGS:
            return
        deferred = has_marker(spec)
        excluded = self.is_index and FOOTER_CLASS in set((attrs.get("class") or "").split())
        self.stack.append((tag, deferred, excluded))
        self.deferred_depth += deferred
        self.excluded_depth += excluded
        self.mode.append(tag if tag in ("script", "style") else None)

    def handle_startendtag(self, tag, attrs):
        self._check_spec_attr(dict(attrs))

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                for (_t, d, e) in self.stack[i:]:
                    self.deferred_depth -= d
                    self.excluded_depth -= e
                del self.stack[i:]
                del self.mode[i:]
                break

    def handle_data(self, data):
        kind = next((k for k in reversed(self.mode) if k), None)
        base = self.getpos()[0]
        if kind == "style":
            return
        if kind == "script":
            for off, s in js_string_literals(data):
                self._check(s, base + data.count("\n", 0, off))
            return
        self._check(data, base)


def scan_deferred_text(text, kw_re, kw_map, is_index=False):
    """R6：回傳 [(lineno, 'R6', msg, ctx)]。整頁 banner → 全檔放行。"""
    if kw_re is None or PAGE_BANNER in text:
        return []
    sc = DeferredScanner(kw_re, text.split("\n"), is_index)
    sc.feed(text)
    sc.close()
    out, seen = [], set()
    for ln, kw, ctx in sc.hits:
        if ln in seen:          # 每行報一次
            continue
        seen.add(ln)
        out.append((ln, "R6",
                    "延後功能字眼「%s」（Deferred/%s）未標延後——同行補「延後功能／Deferred/」、"
                    "容器 data-spec 標延後，或整頁 banner「%s」" % (kw, kw_map.get(kw, "?"), PAGE_BANNER), ctx))
    return out


def deferred_target_files():
    dp = REPO / FINAL_DIR
    if not dp.is_dir():
        return []
    return [f for f in sorted(dp.glob("*.html"))
            if not is_archived(f.relative_to(REPO)) and not f.name.endswith(EXCLUDE_SUFFIX)]


def run_deferred():
    kw_map, kw_errors = load_deferred_keywords()
    kw_re = build_kw_regex(kw_map)
    per_file = {"Spec/Deferred/" + name: [(2, "R6",
                "Deferred 檔第二行缺「關鍵詞：a、b、c」——R6 無法掃這個延後功能", "")] for name in kw_errors}
    files = deferred_target_files()
    for f in files:
        hits = scan_deferred_text(f.read_text(encoding="utf-8", errors="replace"), kw_re, kw_map,
                                  f.name == "index.html")
        if hits:
            per_file[rel(f)] = hits
    print("── [mockup-lint --deferred] R6 延後功能字眼未標延後（定案/；不受 baseline 豁免）──")
    if not DEFERRED_DIR.is_dir():
        print("  ℹ️ Spec/Deferred/ 不存在：沒有延後功能，R6 無關鍵詞可掃")
    else:
        print("  關鍵詞 %d 個（來自 %s）" % (len(kw_map), "、".join(sorted(set(kw_map.values()))) or "—"))
    total = report(per_file, len(files), 0)
    return 1 if total else 0


DEFERRED_SELFTEST = [
    # (名稱, 應否命中, 片段)；合成關鍵詞見 run_deferred_selftest
    ("可見文字提到延後功能", 1, "<div>\n<p>週期任務 設定</p>\n</div>"),
    ("<title> 也算可見文字", 1, "<title>週期任務</title>"),
    ("data-spec 提到但沒標延後", 1, '<div data-spec="週期任務的入口">x</div>'),
    ("JS 字串常值", 1, "<script>var t='週期任務';</script>"),
    ("同行標了延後功能", 0, "<p>週期任務（延後功能，見 Spec/Deferred/週期任務.md）</p>"),
    ("祖先 data-spec 標延後", 0,
     '<section data-spec="〔延後功能，見 Spec/Deferred/週期任務.md〕">\n<button>\n週期任務\n</button>\n</section>'),
    ("整頁 banner", 0, "<p>本頁整頁為延後功能</p>\n<p>週期任務</p>"),
    ("HTML 註解不掃", 0, "<!-- 週期任務 -->"),
    ("<style> 不掃", 0, "<style>/* 週期任務 */ .a{}</style>"),
    ("JS 註解不掃", 0, "<script>// 週期任務\n/* 週期任務 */ var a=1;</script>"),
    ("其他屬性值不掃", 0, '<a title="週期任務" href="#">x</a>'),
    ("英數關鍵詞有邊界（N-11 不吃 XN-11／N-110）", 0, "<p>XN-11 與 N-110</p>"),
    ("英數關鍵詞本身命中", 1, "<p>見 N-11</p>"),
    ("大小寫敏感（repeat-task ≠ Repeat-task）", 0, "<p>repeat-task</p>"),
    ("index footer 更新紀錄不掃", 0, '<p class="updated">週期任務 改版</p>'),
]


def run_deferred_selftest():
    print("── [mockup-lint --selftest] R6 正／反案例 ──")
    kw_map = {"週期任務": "週期任務.md", "N-11": "週期任務.md", "Repeat-task": "週期任務.md"}
    kw_re = build_kw_regex(kw_map)
    bad = 0
    for name, expect, src in DEFERRED_SELFTEST:
        got = 1 if scan_deferred_text(src, kw_re, kw_map, is_index=True) else 0
        ok = got == expect
        bad += not ok
        print("  %s %-40s 預期%s／實際%s" % ("✅" if ok else "❌", name,
                                         "命中" if expect else "不命中", "命中" if got else "不命中"))
    print()
    print("  ❌ %d/%d 案不符預期" % (bad, len(DEFERRED_SELFTEST)) if bad
          else "  ✅ %d/%d 案全過" % (len(DEFERRED_SELFTEST), len(DEFERRED_SELFTEST)))
    return 1 if bad else 0


# ---------- 模式 ----------
def run_all():
    baseline = load_baseline()
    files = target_files()
    per_file, skipped = {}, 0
    for f in files:
        rp = rel(f)
        if rp in baseline:
            skipped += 1
            continue
        hits = lint_file(f)
        if hits:
            per_file[rp] = hits
    print("── [mockup-lint] R1 規格落畫面 / R2 視覺紅線 / R3 三屬性 / R5 無依據元素 ──")
    total = report(per_file, len(files), skipped)
    return 1 if total else 0


def run_file(arg: str):
    p = Path(arg)
    if not p.is_absolute():
        p = REPO / p
    rp = rel(p)
    if (is_archived(rp) or is_archived(p) or p.name in EXCLUDE_NAMES
            or p.name.endswith(EXCLUDE_SUFFIX)):
        return 0
    if not p.is_file():
        return 0
    hits = [] if rp in load_baseline() else lint_file(p)
    if rp.startswith(FINAL_DIR + "/"):             # R6 不受 baseline 豁免
        kw_map, _ = load_deferred_keywords()
        hits = hits + scan_deferred_text(p.read_text(encoding="utf-8", errors="replace"),
                                         build_kw_regex(kw_map), kw_map)
    if not hits:
        return 0
    print("── [mockup-lint] %s ──" % rp)
    total = report({rp: hits}, 1, 0)
    return 1 if total else 0


def run_audit(arg: str):
    """元素盤點：列出每個可互動元素引用的 SPEC 節號，供 scope 提案附上給 PM 目視。
    R5 擋得住「完全沒依據」，擋不住「引到別的畫面的依據」——那要靠這張表人工看。"""
    p = Path(arg)
    if not p.is_absolute():
        p = REPO / p
    rp = rel(p)
    if not p.is_file():
        print("  ⏭️ 檔案不存在：%s" % rp)
        return 0
    _hits, actions = lint_file(p, want_actions=True)
    print("── [mockup-lint --audit] 元素盤點：%s ──" % rp)
    print()
    print("  %-6s %-4s %-28s %-32s %s"
          % ("行", "來源", "data-action", "data-testid", "引用的 SPEC 節號"))
    print("  " + "─" * 112)
    no_ref = n_chrome = n_js = 0
    for lineno, action, testid, refs, chrome, origin in actions:
        n_js += origin == "js"
        if refs:
            mark, cell = "  ", "、".join(refs)
        elif chrome:
            mark, cell = "  ", "— UI 慣例元素（data-chrome，無專屬 SPEC）"
            n_chrome += 1
        else:
            mark, cell = "🔴", "（無）"
            no_ref += 1
        print("  %s%-4d %-4s %-28s %-32s %s"
              % (mark, lineno, "JS" if origin == "js" else "—",
                 action[:28], testid.replace(PH, "*")[:32], cell))
    print()
    print("  共 %d 個可互動元素（靜態 %d、JS 產生 %d）：有 SPEC 依據 %d、UI 慣例 chrome %d、🔴 無依據 %d"
          % (len(actions), len(actions) - n_js, n_js,
             len(actions) - n_chrome - no_ref, n_chrome, no_ref))
    if no_ref:
        print("  ⚠️ 無依據元素：畫之前先確認 SPEC 有這條。")
    print("  ℹ️ 引用「不在本畫面依據欄」的節號本工具擋不掉，請 PM 在 scope 提案時目視這張表。")
    return 1 if no_ref else 0


SELFTEST_CASES = [
    # (名稱, 應否命中, 片段) —— JS 產生的標記；改動 scan_js 前後都跑一次
    ("R5·js 無依據元素", 1,
     """<script>h+='<button data-testid="T1.sort" data-action="sort-by" data-spec="排序依據。">排序</button>';</script>"""),
    ("R3·js 三屬性缺一", 1,
     """<script>h+='<button data-action="filter-open" data-spec="篩選（§US-T1.2.1）。">篩選</button>';</script>"""),
    ("R1·js §US 落畫面文字", 1,
     """<script>h+='<div class="hint">依 §US-T1.1.2 只列未完成任務</div>';</script>"""),
    ("R1·js 討論過程詞落畫面", 1,
     """<script>h+='<span>本欄為拍板前的值</span>';</script>"""),
    ("R1·js 狀態 enum 落畫面", 1,
     """<script>h+='<span class="badge">task_open</span>';</script>"""),
    ("R1·js 孤兒字串也要抓", 1,
     """<script>document.getElementById('t').textContent='目前為 PENDING 值';</script>"""),
    ("合規元素不誤報", 0,
     """<script>h+='<button data-testid="T1.d" data-action="open-task" data-spec="開啟任務（§US-T1.1.3）。">開啟</button>';</script>"""),
    ("chrome 元素不誤報", 0,
     """<script>h+='<button data-testid="T1.z" data-action="zoom-in" data-chrome="true" data-spec="放大。">＋</button>';</script>"""),
    ("白名單子樹豁免", 0,
     """<script>h+='<div class="case-note">依 §US-T1.1.2：空清單不是錯誤</div>';</script>"""),
    ("data-spec 屬性內的 §US 不算落畫面", 0,
     """<script>h+='<div data-testid="x" data-action="go" data-spec="返回清單（§US-L1.1.1）。">清單</div>';</script>"""),
    ("選擇器／變數字串不誤報", 0,
     """<script>var el=document.getElementById('crumb'); var s='chart';</script>"""),
    ("正則字面值不拆壞", 0,
     """<script>function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;');}</script>"""),
    ("註記欄位的值不算畫面文字", 0,
     """<script>var C=[{title:'x', spec:'清單卡片（§US-L1.1.1）'}];</script>"""),
    ("但註記欄位不是萬用豁免", 1,
     """<script>var msg='狀態：task_open'; el.textContent=msg;</script>"""),
]


def run_selftest():
    print("── [mockup-lint --selftest] 規則正／反案例 ──")
    bad = 0
    for name, expect, src in R2_SELFTEST:
        got = 1 if scan_r2(src) else 0
        ok = got == expect
        bad += not ok
        print("  %s %-34s 預期%s／實際%s"
              % ("✅" if ok else "❌", name,
                 "命中" if expect else "不命中", "命中" if got else "不命中"))
    for name, expect, src in SELFTEST_CASES:
        got = 1 if scan_js(src) else 0
        ok = got == expect
        bad += not ok
        print("  %s %-34s 預期%s／實際%s"
              % ("✅" if ok else "❌", name,
                 "命中" if expect else "不命中", "命中" if got else "不命中"))
    total = len(SELFTEST_CASES) + len(R2_SELFTEST)
    print()
    if bad:
        print("  ❌ %d/%d 案不符預期" % (bad, total))
    else:
        print("  ✅ %d/%d 案全過" % (total, total))
    print()
    return 1 if run_deferred_selftest() or bad else 0


def run_update_baseline():
    files = target_files()
    final_bad, wip_bad = {}, {}
    for f in files:
        rp = rel(f)
        hits = lint_file(f)
        if not any(not is_advisory(h[1]) for h in hits):
            continue
        (final_bad if rp.startswith(FINAL_DIR + "/") else wip_bad)[rp] = hits
    lines = [
        "# mockup_lint baseline — 整檔豁免清單（grandfather 既有定案舊稿）",
        "# 由 mockup_lint.py --update-baseline 產生；只收 HTML設計稿/定案/。",
        "# 討論中/ 的檔不得列入（新稿必須直接合規）。",
        "# 每行一個相對 repo root 的路徑；# 開頭為註解。",
        "",
    ]
    for rp in sorted(final_bad):
        cnt = defaultdict(int)
        for _ln, rule, _msg, _ctx in final_bad[rp]:
            cnt[rule] += 1
        lines.append("# ↓ %s" % " / ".join("%s×%d" % (r, cnt[r]) for r in sorted(cnt)))
        lines.append(rp)
    BASELINE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("── [mockup-lint] baseline 重建 ──")
    print("  ✍️ 已寫入 %s：收錄 %d 檔（只收 定案/）" % (rel(BASELINE), len(final_bad)))
    if wip_bad:
        print("  ❌ 討論中/ 有違規檔，不得進 baseline——修檔或（若為合規範本誤報）回頭調規則：")
        report(wip_bad, len(wip_bad), 0)
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser(description="Mockup 規格不落畫面 ＋ 元素要有依據 linter")
    ap.add_argument("--all", action="store_true", help="掃 定案/ + 討論中/ 全部 mockup")
    ap.add_argument("--file", metavar="PATH", help="只掃單一檔（本機 hook 用；乾淨時無輸出）")
    ap.add_argument("--audit", metavar="PATH", help="元素盤點表（scope 提案附件用）")
    ap.add_argument("--update-baseline", action="store_true",
                    help="重建 baseline（整檔豁免；只收 定案/）")
    ap.add_argument("--check-baseline-shrink", metavar="REF", help="baseline 相對 REF 多出任何一筆 → exit 1")
    ap.add_argument("--selftest", action="store_true",
                    help="規則正／反案例（含 R6；改規則後必跑）")
    ap.add_argument("--deferred", action="store_true",
                    help="R6 延後功能字眼未標延後（只掃 定案/；不受 baseline 豁免）")
    args = ap.parse_args()

    if args.deferred:
        sys.exit(run_deferred())
    if args.selftest:
        sys.exit(run_selftest())
    if args.check_baseline_shrink:
        sys.exit(run_check_shrink(args.check_baseline_shrink))
    if args.update_baseline:
        sys.exit(run_update_baseline())
    if args.audit:
        sys.exit(run_audit(args.audit))
    if args.file:
        sys.exit(run_file(args.file))
    sys.exit(run_all())


if __name__ == "__main__":
    main()
