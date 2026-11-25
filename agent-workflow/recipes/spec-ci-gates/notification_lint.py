#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
notification_lint — 通知信總表的「全檔不變量」掃描（advisory，永遠 exit 0）

prose-lint／glossary-lint 逐行看；信件總表的缺陷常是全檔才看得見的——中英段落不對稱、
同一個目的地的中文連結文字各寫各的。

設計取捨：
  * **不 block**。信件文案在定稿前是草稿，硬門守草稿只會整批 waiver。
  * **不設連結句型白名單**：行動型連結各寫各的動作本來就合法，改成分組報表給人看。
  * 只掃「一列一封信、內文欄中英對照」的檔。

列格式（欄位位置見常數）：
  | **N-1** | 任務到期提醒 | 觸發條件 | 收件人 | 中文段<br>🔗 <a href="/t">查看任務</a><br><br>English…<br>🔗 <a href="/t">View task</a> | US-T1.1 |
  內文以 <br><br> 分段，依有無中日韓字元歸中／英；`**【變體名】**` 分隔多個變體；`\\|` 為跳脫的直線。

用法：
  python3 Spec/.convert_tools/notification_lint.py              # 掃預設清單
  python3 Spec/.convert_tools/notification_lint.py --path <md>  # 指定檔（相對 repo 根）
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

# ── 專案常數 ──────────────────────────────────────────────
DEFAULT_TARGETS = ["Spec/05_Notifications.md"]   # 沒有信件總表的專案：整支不裝
ROW_ID = r"N-\d+"                                # 信件列編號
BODY_COL = 5                                     # split_row 後的內文欄 index（1＝編號欄）

CJK = re.compile(r"[一-鿿]")
# 中文行動提示句：祈使詞必須落在**子句開頭**（句首 / 標點後 / <br> 後）。
# 用子句邊界而非單純出現，是為了排掉「申請」「邀請」裡的「請」。
# 兩類都算：① 祈使（請 / 麻煩…）② 告知許可（您可… / 可編輯…）。
# 許可句中文常寫成無主詞的「協作者可編輯任務」，對到英文的 You may / You can。
ZH_CTA = re.compile(
    r"(?:^|[。，；：、！？\n]|<br>)\s*(請|麻煩|您可|建議您)"
    r"|可(查看|編輯|完成|封存)")
# 裸 can/may 不收——「the app can send reminders」不是對收件人的指示。
# 只收「主詞相鄰的許可句」。
EN_CTA = re.compile(
    r"\b(please|kindly"
    r"|you\s+(may|can|should|must)"
    r"|can\s+(view|edit|complete|archive)"
    r"|(owners?|collaborators?|viewers?)\s+can)\b", re.I)


def split_row(line):
    """依未跳脫的 | 切表格列（信件內文欄大量使用 \\| 畫內嵌表格）。"""
    return re.split(r"(?<!\\)\|", line)


def letter_rows(lines):
    """回傳 [(編號, 內文欄)]；只取首欄為信件編號的列。"""
    out = []
    for ln in lines:
        c = split_row(ln)
        if ln.startswith("|") and len(c) > BODY_COL + 1:
            rid = c[1].strip().strip("*")
            if re.fullmatch(ROW_ID, rid):
                out.append((rid, c[BODY_COL]))
    return out


def variants(body):
    """把一封信的內文欄切成「變體」（【擁有者版】【協作者版】…各算一段）。"""
    parts = re.split(r"\*\*【[^】]*】\*\*", body)
    return [p for p in parts if p.strip()]


def zh_en_blocks(variant):
    """把一個變體切成中文塊 / 英文塊（以 <br><br> 分段，依有無 CJK 歸邊）。"""
    zh, en = [], []
    for blk in variant.split("<br><br>"):
        if not blk.strip():
            continue
        (zh if CJK.search(blk) else en).append(blk)
    return zh, en


def cta_sentences(text, pat, enders):
    """數「含行動提示詞的句子」數；斷句用句號類，避免整段只算一次。"""
    body = text.replace("<br>", "\n")
    # 剝掉內嵌 markdown 表格列（\| 欄 \| 欄 \|）——表格不是散文，且它的儲存格文字
    # 兩邊各自帶 CTA 詞時會互相抵銷，把真正少掉的那句蓋掉。
    body = "\n".join(ln for ln in body.split("\n") if not re.match(r"\s*\\\|", ln))
    body = re.sub(r"<[^>]+>", " ", body)
    parts = re.split(r"[" + re.escape(enders) + r"]", body)
    return sum(1 for p in parts if p.strip() and pat.search(p))


def check_symmetry(rid, body):
    """結構對稱：段落塊數、🔗 行數、段末行動提示句 parity。"""
    problems = []
    for i, v in enumerate(variants(body), 1):
        zh, en = zh_en_blocks(v)
        if not zh or not en:
            continue  # 純中文註記或純英文段，非中英對照結構
        tag = f"{rid}" + (f" 變體{i}" if len(variants(body)) > 1 else "")
        zt, et = "<br><br>".join(zh), "<br><br>".join(en)

        z_link, e_link = zt.count("🔗"), et.count("🔗")
        if z_link != e_link:
            problems.append(f"{tag}：🔗 連結行數不對稱（中 {z_link} / 英 {e_link}）")

        # 比句數而非有無：「英文有行動提示、但比中文少一句」用布林看不到。
        z_cta = cta_sentences(re.sub(r"<br>🔗[^<]*<[^>]*>[^<]*</a>", "", zt), ZH_CTA, "。！？")
        e_cta = cta_sentences(et, EN_CTA, ".!?")
        if z_cta > e_cta:
            problems.append(f"{tag}：中文行動提示句比英文多（中 {z_cta} / 英 {e_cta}）")
        elif e_cta > z_cta:
            problems.append(f"{tag}：英文行動提示句比中文多（中 {z_cta} / 英 {e_cta}）")
    return problems


def check_anchor_groups(rows):
    """分組報表：同一 (路徑, 英文 anchor) 下，中文 anchor 有幾種講法。"""
    groups = {}
    for rid, body in rows:
        found = re.findall(r'href="([^"]+)"[^>]*>([^<]*)</a>', body)
        by_path = {}
        for href, text in found:
            path = href.split("?")[0]
            by_path.setdefault(path, {"zh": set(), "en": set()})
            (by_path[path]["zh"] if CJK.search(text) else by_path[path]["en"]).add(text)
        for path, d in by_path.items():
            for en in d["en"] or {"(無英文 anchor)"}:
                key = (path, en)
                groups.setdefault(key, {})
                for zh in d["zh"]:
                    groups[key].setdefault(zh, []).append(rid)
    return {k: v for k, v in groups.items() if len(v) > 1}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", nargs="*", default=None)
    args = ap.parse_args()
    targets = args.path or DEFAULT_TARGETS

    print("── [notification-lint] 信件總表全檔不變量（advisory，不 block）──")
    total = 0
    for rel in targets:
        full = os.path.join(REPO, rel)
        if not os.path.exists(full):
            print(f"  ⚠️  找不到 {rel}，跳過")
            continue
        lines = open(full, encoding="utf-8").read().split("\n")
        rows = letter_rows(lines)
        print(f"\n  📄 {rel}（{len(rows)} 封信）")

        sym = [p for rid, body in rows for p in check_symmetry(rid, body)]
        if sym:
            print(f"  ① 中英結構對稱 — {len(sym)} 處：")
            for p in sym:
                print(f"      ⚠️  {p}")
        else:
            print("  ① 中英結構對稱 — ✅ 無異常")
        total += len(sym)

        gs = check_anchor_groups(rows)
        if gs:
            print(f"  ② 連結文字分組 — {len(gs)} 組同目的地有多種中文講法（人眼判斷，"
                  "行動型各寫各的動作是合法的）：")
            for (path, en), zhs in sorted(gs.items()):
                print(f"      • {path}  ⟵ EN「{en}」")
                for zh, rids in sorted(zhs.items()):
                    print(f"          「{zh}」← {', '.join(rids)}")
        else:
            print("  ② 連結文字分組 — ✅ 每個目的地的中文講法唯一")
        total += len(gs)

    print(f"\n  共 {total} 項待人眼判斷。此檢查不 block；判定要改就改 SPEC，"
          "判定合法就無視（不需 waiver 檔）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
