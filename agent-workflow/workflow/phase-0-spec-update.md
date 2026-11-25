---
phase: 0
name: SPEC 討論與寫入
executor: PM + Claude（討論用 Opus；impact-scanner、spec-verifier、spec-deferrer 為 Opus subagent，spec-writer、mockup-drift-scanner 為 Sonnet subagent）
reads_from:
  - 對話中的討論脈絡
  - 專案資料夾內的 Spec/Project_Context.md（既有架構級事實）
  - 專案資料夾內的 Spec/Decision_Principles.md（既有決策原則 / 紅線）
  - 專案資料夾內的 Spec/README.md（文件地圖）
  - 專案資料夾內的 Spec/Progress_Tracker.md（若存在，地基軌進度；拍板全史在 Spec/memory/ 決策檔）
  - 專案資料夾內的 mockup 與流程圖（依該專案 CLAUDE.md 標示位置，供 ⑨b drift 掃描）
feeds_into:
  - workflow/phase-0-impact-scan.md（拍板前的影響範圍掃描）
  - workflow/phase-1-product-design.md（定案後才進 Phase 1 畫 mockup；若 ⑨b 掃出 mockup 需更新，PM 在 ⑩ 拍板後排 Phase 1）
also_see: workflow/CONTRACTS.md（跨 phase 契約）；workflow/phase-1-product-design.md（PM SPEC 禁止清單全文）
---

# Phase 0｜SPEC 討論與寫入

> **你的角色：** 描述需求、和 Claude 討論、做最後決策
> **Claude 的角色：** 陪你推敲方案、寫入既有 SPEC 文件、同步更新脈絡與 memory
>
> 這是 Phase 1 的**前置階段**。任何新功能或現有功能的調整，都從這裡開始：討論定案 → 寫入 SPEC → 才進 Phase 1 畫 mockup。

---

## 本 Phase 的定位：三情境共用的決策寫入引擎

Phase 0＝三軸模型的**軸 B｜決策寫入引擎**，三情境共用：新專案地基 gate（每層 gate 拍板結論寫入，見 foundation-track §4）、既有專案新功能（R3＝一筆「新增 US」交易）、改既有規格（R4＝一筆「改條文」交易，Path A/B）。
兩種模式跑同一套七階段機具（討論→掃描→拍板→寫入→稽核→drift→收版）：**批次量產**（greenfield／大批新增：Opus 驅動、PM 零碎批次介入，每節寫入前給「寫前提案」讓 PM 勾 scope，含「⓪ milestone 起手清理」）vs **單項維護**（改一兩條：逐項拍板、不需 milestone 清理、通常走 Path A）。

> 三軸關係詳見 [`foundation-track.md`](./foundation-track.md) §1；三情境路由判定表見 [`entry-routing.md`](./entry-routing.md)（R1–R5）。

---

> **背景／設計理由**（為什麼需要 Phase 0、為什麼有影響掃描層、Opus vs Sonnet 分工）另存於 rationale 檔（未包含於此 repo）——**人看用、agent 不載入**，操作規則全在本檔。

> **依賴**：本流程用到 `$CLAUDE_WORKSPACE/scripts/{spec-grep,spec-writer-report-check,closed-claim-lint}.sh`（工具腳本未包含於此 repo，不 vendor 進專案）。本機找不到 → 各 agent 照其檔頭「依賴」改用 Grep 或列「⚠️ 未安裝」，不靜默略過。

---

## 執行順序

```
① PM 提出需求 / 修改想法（對話）；**先記工作項**（issue 全路徑＋milestone，見 §SPEC 生命週期 4；宣告版本分支的專案另驗 milestone 有效，見 7）
      ↓
② Claude（Opus）和 PM 一問一答，推敲設計方案 → 產出**定案草案**
      ↓
③ Claude（Opus）整理「結構化決策清單」，呼叫 @phase0-impact-scanner
   （格式見 phase-0-impact-scan.md「輸入格式」段）
      ↓
④ @phase0-impact-scanner（Opus subagent）先把關鍵詞自擴成 ≥30 詞、grep 一律走 `$CLAUDE_WORKSPACE/scripts/spec-grep.sh`（工具腳本未包含於此 repo），掃描整份 SPEC + 已定案議題：
   - 強連動：必改清單（含原文摘要、衝突點、建議方向）
   - 弱連動：請 PM 確認清單（含 PM 判斷選項 A/B/C）
   - 無影響：已掃檔案清單
      ↓
⑤ Claude（Opus）整理 scanner 結果給 PM
      ↓
⑥ PM 拍板（可能調整草案 / 補連動修改清單 / **確認 scope：本次要寫哪些情境**，見下方「✋ 寫前範圍控管」；**或拍「延後」／「接回」**＝⑨ 改走 `@phase0-spec-deferrer`）
      ↓
⑦ Claude（Opus）整理「最終定案結論」（含 PM 補的連動修改），準備交給寫入
   （此步只是整理，**不自己動手寫檔**；實際寫入全由 ⑨ 的 spec-writer 一次完成）
   - **本批新名詞宣告（必填）**：定案結論列一欄 `本批新名詞: [中文｜英文 …]｜無`——本批引入的**新命名概念**（功能／機制／角色／狀態／畫面 surface）一律列出，沒有就明寫「無」
      ↓
⑧ PM 下達「寫入 SPEC」的指令
      ↓
⑨ （主流程先 `> .claude/spec-dirty.log` 清空 dirty-log，讓本批改檔被乾淨記錄）→ @phase0-spec-writer（Sonnet subagent）一次寫入全部：
   - 讀 Spec/README.md 找到對應拆檔 md（`<module>/NN_*.md`）
   - **就地 Edit 既有 md**；該 SPEC 有 frontmatter `last_updated` 者更新為今日（只放日期）（**不複製押日期、不新建檔**；版本歷史由 git 承擔）
   - 用 Read / Edit / Grep 直接修改 md（**不用 python-docx**）
   - **編號穩定、永不重編**：刪除／退役的節保留 heading 行，下一行註記「已退役（保留編號）」；搬去 Deferred 的佔位格式見 §SPEC 生命週期 2（SPEC_NUMBERING_RULES §3.5）；新增節取號規則不變
   - **正文不寫延後字樣與未來意圖**（清單與改寫法見 §SPEC 生命週期 1）：定案含「這次先不做」→ 停，回主流程改走 deferrer
   - **同步寫入**（依分流判斷）：Project_Context.md（架構級事實）、Decision_Principles.md（可重複套用原則）
   - **同步更新**：Spec/README.md 文件清單、**決策檔**（`Spec/memory/`，欄位與四段見 §SPEC 生命週期 3；`Spec/memory/index/` 跑腳本、不手改）
   - **新名詞原子寫入 Glossary**：`本批新名詞` 欄的每個概念，**同批在 `Spec/Glossary.md` 補對應詞條**（中英名＋一句定義＋出處 §）；寫任何 SPEC 前一律先讀 Glossary，用既有詞、不自造同義詞
   - **輸出 `.claude/spec-write-report.json`**（`{"files": [...], "added": [{"file": ..., "strings": [新增原句...]}]}`），供 ⑨a 機器複驗；多個 writer 平行時各寫自己的 `.claude/spec-write-report.<group>.json`，不共用一份
   - 回報做了什麼（**寫完不自己 commit**，等 ⑩ PM 審閱通過再由主流程 commit）
   - **⑥ 拍「延後／接回」時**：本步改呼叫 `@phase0-spec-deferrer`（defer／restore 模式），同批在定案 mockup 標「延後功能，見 Spec/Deferred/…」，輸出 `.claude/spec-defer-report.json`；⑨a、⑨b 照跑
      ↓
⑨a @phase0-spec-verifier（Opus subagent，**與 spec-writer 不同 agent**）獨立稽核 + 自動修正：
   - **維度 0（清單外維度）**：獨立從 (a) 議題檔拍板結論 (b) impact-scanner 強連動項 (c) `git diff` 每個 hunk 用 spec-grep 反推同主題條文，各產一份 checklist 交集比對；三來源不一致＝回報
   - 對照「結構化定案清單」+ 議題檔「拍板結論」區塊，逐項驗證寫入是否忠實、有無漏寫 / 寫錯（不信任 writer 的 Self-Review，自己重讀檔案）
   - **自報 JSON 機器複驗**：跑 `$CLAUDE_WORKSPACE/scripts/spec-writer-report-check.sh <repo> [report 檔]`（工具腳本未包含於此 repo；平行 writer 逐份跑），逐條確認 report 的檔與新增原句真的在 `git diff`；🔴＝謊報
   - **lint 自己跑**：專案有的 lint（prose／glossary／numbering／mockup）verifier 親自跑；派工 prompt 寫「lint 已 0」不算數
   - **語意層涵蓋每個改動 hunk**（含刪除與改寫，不只新增行）：逐對問「規則範圍有沒有跟著變」；專案有限定詞守門工具（[`qualifier_guard.py`](../recipes/spec-ci-gates/qualifier_guard.py)）者對 base 跑 diff 模式，它列出的每一對（限定詞／§ID／數字消失或改變）逐條判定
   - **自報 vs 實際改檔對照**：讀 `.claude/spec-dirty.log`（PostToolUse hook 客觀記錄本批改檔，hook 未包含於此 repo；⑨ 前已清空）對 spec-writer 自報改檔清單，揪脫稿改檔 / 謊報；log 不存在則用 `git diff --name-only`
   - **生命週期檢查**：決策檔有動且欄位填齊、`changes` 的 §ID 都還在（或已列 `retired`）、`source`＝本批工作項；新取的號不撞 `Spec/Deferred/` 保留編號；改動行（含 heading）無延後字樣與未來意圖（§SPEC 生命週期 1）；`Spec/Deferred/*.md` 每列錨點（三種：剪後句全文／佔位 heading／§ID）仍在活檔逐字唯一（斷了＝回報 PM「<功能>更難接回」）；工作項為全路徑（commit 時引用它）
   - 檢查編號規則（SPEC_NUMBERING_RULES）、frontmatter `last_updated`（有 frontmatter 者；只有日期）、cross-ref 有效性、**禁用名詞（有 glossary lint 工具〔[`glossary_lint.py`](../recipes/spec-ci-gates/glossary_lint.py)〕的專案一律跑禁用詞檢查＝確定性、取代人工讀段落，命中即修；無此工具的專案才退回人工對照禁用表）**、文件分流（Project_Context 不塞細節）、memory 位置（該專案 `Spec/memory/`）
   - **本批新名詞兩向對照（治「超脫 Glossary」根因：出生即登記，不事後挖）**：對定案結論 `本批新名詞` 欄——(a) 宣告的每個詞都要在本批 Glossary diff 出現（漏補即補）；(b) Glossary diff 不得多出未宣告的詞（多出＝疑似脫稿造詞，回報 PM）。有 glossary lint 工具者另跑覆蓋率檢查，掃有無新 drift 概念未收錄。此欄的宣告來源＝⑦、原子寫入＝⑨。
   - **機械性偏差直接修正**（漏寫 / 編號 / 格式 / 禁用名詞〔linter 命中〕/ cross-ref / memory 位置 / 漏補 Glossary 詞條）；**僅「SPEC 內容與議題檔拍板結論互相矛盾」「Glossary diff 多出未宣告詞」這類非機械判定回報 PM**
   - 破解 spec-writer「球員兼裁判」：寫的人與驗的人是不同 agent
   - 不 commit；產出「發現 + 已修 + 待 PM」報告
      ↓
⑨b @phase0-mockup-drift-scanner（Sonnet subagent，**自動觸發**）mockup / 流程圖 drift 掃描：
   - 讀本次 spec-writer 改檔的 git diff，抓出本次涉及的 US-ID（含 added / modified / deleted 標註）
   - 依該專案 CLAUDE.md 標示，掃描 mockup HTML（如 `HTML設計稿/*.html`）與流程圖 HTML（如 `Spec/*Flow*.html`）的 `data-spec` 引用與文字提及
   - 另用 `Spec/Deferred/*.md` 的 `關鍵詞：` 行掃 mockup，列出提到延後功能卻沒標「延後功能」的位置
   - **自動門檻邏輯**：modified US 有引用 → 列入必審；無引用 → silent（這條 US 還沒進入維護期）。added US 一律列出（提醒 PM 是否排 Phase 1）。deleted US 有引用 → flag dangling（必修）
   - 產出四段分類報告：📝 修改有引用（必審） / 🆕 新增（待規劃） / ⚠️ 刪除有引用（dangling 必修） / ⏭️ 修改無引用（跳過）
   - **不修改任何檔案、不自動同步、不 commit**；只列清單給 PM 決定
      ↓
⑩ PM 打開 md 審閱 + 看 mockup-drift 報告，做兩個決定：
   - 確認 SPEC 內容與編號歸類（verifier 已自動修正機械性偏差，PM 掃一眼「已修 / 待 PM」即可，不需逐條核准已修項）
   - **依 mockup-drift 報告判斷 commit 策略：**
     - **Path A — 純文字微調**（drift 報告中無「必審」「dangling 必修」項，或 PM 判斷規則改動不影響 UI / 流程） → 直接走 ⑪a
     - **Path B — 要動 mockup**（drift 報告有「必審」項且 PM 判斷 UI / 流程要連動，或有「dangling 必修」項，或 PM 決定排 Phase 1 補畫新增 US 的 mockup） → 走 ⑪b
      ↓
⑪ 兩條 Path 的每個 commit message 都引用本批工作項全路徑（一個 commit 一個工作項），並帶 `Verified-by:` trailer（§SPEC 生命週期 6）；宣告版本分支的專案 push `main` 後確認 `spec-branch-sync` 綠（§SPEC 生命週期 7）

⑪a **Path A — 純文字 commit**：個案 Phase 0 的所有改動（SPEC md + Project_Context + Decision_Principles + memory + README）都在**同一個專案 repo**，單一 repo commit 即收齊；push 前確認 working tree 乾淨。main 是 protected branch，只能 fast-forward
      ↓ 跳 ⑫

⑪b **Path B — feature branch 兩 commit 流程**（mockup 需更新時）：
   - 開 feature branch（如 `phase0/<feature>-<topic>`）
   - **Commit 1**：本次 Phase 0 的 SPEC / 脈絡 / memory / README 變更
   - 排 **Phase 1** 任務，依 mockup-drift 報告更新對應 mockup（必審項調整 / dangling 退役或改引用 / 新增項補畫）
   - **Commit 2**：Phase 1 mockup 更新
   - 專案若有 mockup lint（本機 hook 或 CI，見配方 [`spec-ci-gates.md`](../recipes/spec-ci-gates.md)），Commit 2 前跑一次確認無新 drift
   - feature branch 合回 main（fast-forward）；main 上永遠看不到「SPEC 已改但 mockup 沒跟」的中間狀態
      ↓
⑫ （可選）需要交付 docx 給雲端硬碟 / Reviewer 時，若專案有 md→docx 轉檔工具（未包含於此 repo），用它一鍵生成
      ↓
⑬ Phase 0 locked，可進 Phase 1（若 ⑩ 走 Path B，Phase 1 已在 ⑪b 內並行完成）
```

> **SPEC source of truth＝md**；docx 為 rendered output，需要時從 md 生成（專案有 md→docx 轉檔工具者用它；未包含於此 repo）；歷史 docx 為封存快照，不再修改。

> **③④⑤ 是拍板前的掃描層**。議題單純（PM ↔ Opus 在討論時就已確認沒有連動）時，Opus 可略過 scanner，但必須在 ⑥ 拍板時**明確宣告「本議題無外部連動」**，否則預設要跑掃描。

---

## ✋ 寫前範圍控管（scope gate）— 只寫拍板的、衍生情境 opt-in

**核心：PM 拍板的是「本節寫哪些情境（scope）」，不是逐句措辭；嚴格前控範圍、不「先寫多再刪」（長全新 SPEC（greenfield）量產時尤其必守）。**

- 草案分兩欄：`已拍板要寫的` vs `候選衍生情境（edge / error / 防呆 / 邊界）`；候選**逐條**標【建議寫 / 建議跳過】＋一句理由，**預設從嚴、偏少**（[scenario-expansion](../skills/scenario-expansion/SKILL.md) skill 的情境矩陣＝候選菜單，不是全部要寫）。
- `候選衍生情境` 欄必須逐題走過「邊界情境檢查清單」產生（每題有情境或確認不適用；預設用 scenario-expansion skill §4.5「Phase 0 邊界 12 問」，專案可自訂），不得只列 Opus 想到的。
- PM 勾 scope → spec-writer(⑨) 只寫勾的；**衍生 error / 防呆 / 邊界一律 opt-in、拍板後才寫**——不投機、不加戲。scope 定了、節內 Opus 照寫、不逐行煩 PM。

> 這道 gate 落在執行順序的 **⑥ PM 拍板**：拍板同時確認 scope（要寫哪些情境）。

---

## SPEC 生命週期（正文／延後／決策／工作項／驗證）— 本段為此模型唯一權威

1. **正文只寫現行行為**（heading、表格、Glossary 對照表都算正文）：
   - **延後字樣清單**（唯一一份，writer／verifier／deferrer 都引用這裡）：本次不實作、本次不發、暫緩、暫不、本期不、本年度不、非本年度、後續版本、未來可、留待後續。正文一律不出現；要延後走 deferrer。
   - **未來意圖不入正文**：「本年度不做／今年先這樣／未來可…」→ 正文寫現況事實（如「不提供 X」），原句逐字記進本批決策檔「推翻了什麼」；PM 拍為延後的才走 2。
   - **heading 同樣適用**：不寫「（議題 X 拍板 日期）」、不帶延後字樣。
   - **lint 豁免 pragma（封閉清單）**：只收行尾 `<!-- prose-lint: allow <example|ui-copy|literal-term>: <理由> -->`（範例值／逐字 UI 文案／字面名詞）；理由必填，不得拿歷程當理由（沿用、既有、非本次…）。拿不準 → **不加 pragma**，列給 PM。
   - **baseline 只縮不長**（專案的 prose lint 工具有 baseline 檔者；工具見 [`prose_lint.py`](../recipes/spec-ci-gates/prose_lint.py)）：全庫模式是硬門，不在 baseline 的命中即紅；清完債才重寫 baseline 縮小，新命中不得寫進 baseline。
2. **延後功能**（已定案、晚點啟用、啟用時不必再議）→ 由 `@phase0-spec-deferrer`（defer 模式）原文搬到 `Spec/Deferred/<功能>.md`；檔末**接回清單**逐列記「檔案／§／原句全文／剪掉的字／錨點」，restore 模式照清單**依錨點**接回（不依編號）、錨點對不上列給 PM。`Spec/BACKLOG.md` 每個延後功能一行 → Deferred 檔＋工作項。與延後文字相鄰的**永久規則不搬**。
   - **保留編號**：搬走的每個編號項在正文原位留佔位——表格／目錄列 `| R-3 | 已移至 Deferred/<功能>.md（保留編號） |`；搬走的節（US- 或單獨 H3，任一層級）heading 改成 `<編號> <功能名> — 已移至 Deferred/<功能>.md（保留編號）`（不留延後字樣、議題、日期；原 heading 全文逐字搬進 Deferred 檔）；只有段落中間的片段走剪句＋接回清單。Deferred 檔第一行 `保留編號：<ids>`。取新號時這些號視同已存在（SPEC_NUMBERING_RULES §3.5）；接回時編號原樣回來。
   - **接回錨點**三種：剪後句全文、清理後的佔位 heading、§ID；不得以延後字樣片語當錨點。
   - **關鍵詞**：Deferred 檔第二行 `關鍵詞：a、b、c`，供 mockup lint 與 drift 掃描找延後功能字眼；mockup 提到延後功能 → 該行或容器 `data-spec` 標「延後功能，見 Spec/Deferred/<功能>.md」。
3. **決策史住 `Spec/memory/` 決策檔**（一決策一檔，≤ 8 KB），frontmatter 一行一個 key：

   | 欄 | 內容 |
   |---|---|
   | `id` | `D-NNNN`，依序取、永不重用；新文字引用 id、不引用檔名 |
   | `date` | 拍板日 |
   | `changes` | 本決策**定了規則**的 §ID 清單（通常 1–3 個；正文只是提到的不算，grep 找得到）；writer 填 |
   | `retired` | 本決策退役的 §ID 清單（有才寫）；每個 §ID 也必須列在同檔 `changes`（不可 `changes: []` 只填 `retired`） |
   | `supersedes` | 必有；被本決策推翻的 id 清單，`[]`＝刻意不推翻任何決策（被推翻那份 `status` 改 `superseded`） |
   | `status` | `active`／`superseded` |
   | `source` | 工作項全路徑（如 `<group>/<project>#NNN`）；真的無法開單才寫 `口頭需求` |
   | `milestone` | 由腳本從 issue 帶入，**不手填** |

   - 內文固定四段：**結論／Why／否決的方案**（可寫「無」）**／推翻了什麼**。影響範圍由 `changes` 產生、不手寫。as-built 調查放 issue、只貼連結。
   - 既有 §ID 不改號（SPEC_NUMBERING_RULES §3.5）；§ 退役 → writer 把該 §ID 同時列進本批決策檔的 `changes` 與 `retired`。
   - **檔案建立後永不搬移**（路徑被多處連結）；可在建立時放進年份子資料夾。「只看有效決策」＝用 `status` 篩，不搬資料夾。`superseded_by` 不手寫。
   - **切換前的舊決策史**凍結在 `Spec/memory/legacy/*.md`（舊條目一條一列、可 grep、不進產生的視圖）；不另建 stub 決策檔。
   - **查詢**：依 SPEC 檔產生 `Spec/memory/index/<檔名>.md`（以 `changes` 的 §ID 歸列，腳本產生、**不手改**）＋專案 `CLAUDE.md` 宣告的 CLI（如 `decisions why <§ID>`）；agent 先 grep frontmatter。不做全域單一索引、不做依日期視圖。
   - 檔頭 `last_updated` 只放日期、不寫歷史。
4. **每個 SPEC／mockup commit 只引用一個工作項**，寫全路徑（路徑格式見專案 `CLAUDE.md` 的 `工作項路徑格式：<group>/<project>#NNN`；本模型適用所有專案、不設 opt-in，專案缺這行 → writer／deferrer 停下並提示補上）；milestone 掛在 issue 上（milestone＝code 版本號；SPEC 正文與 commit 訊息不寫版本字樣，要改歸屬就改 issue 的 milestone）。專案 CI（若有）擋沒引用的 SPEC commit。「milestone X 改了什麼」＝引用 X 底下 issue 的 commit；「milestone X 的完整行為」＝`main` 扣掉工作項屬於比 X 更晚 milestone 的 commit 之後的 SPEC——宣告版本分支的專案就是 `spec/vX.Y.Z` 的內容（見 7）。
5. **交棒給工程的格式**（如 milestone 異動摘要）依各團隊慣例而定，不在本工作流範圍內（見下方 ⑤）；若團隊要產出，從工作項＋決策檔產生，不另手寫一份。
6. **驗證關卡**：
   - (a) **每個 SPEC／mockup commit 都過 verifier**，commit 訊息帶 trailer `Verified-by: <agent 或人名>`；主流程不得繞過 verifier 直接改 SPEC（含在別的 issue 的 worktree 順手改）。
   - (b) verifier 語意檢查涵蓋**每個改動 hunk**（含刪除與改寫），專案有限定詞守門工具（[`qualifier_guard.py`](../recipes/spec-ci-gates/qualifier_guard.py)）就跑；lint 由 verifier 親自跑，不採信派工 prompt 的「lint 已 0」。
   - (c) **存量清理／遷移**（全庫套新規則、搬體例）只能由**獨立稽核 agent** 宣告完成——不是該批 writer、也不是該批 verifier；派工 prompt 不給「lint 已 0」前提、不預先核准例外，稽核讀整段受影響正文，不只 lint 命中行。lint 0 是必要條件，不是完成定義。
   - (d) 平行 writer 各寫自己的 report（`.claude/spec-write-report.<group>.json`），不共用一份。
7. **版本分支（`spec/vX.Y.Z`）**：專案 `CLAUDE.md` 必須有一行宣告——`版本分支同步：有（spec-branch-sync）` 或 `版本分支同步：無（本專案無 milestone 版本）`；宣告「無」只守 4、5。安裝與操作步驟見配方 [`../recipes/spec-version-branches.md`](../recipes/spec-version-branches.md)（同步工具在 [`../recipes/spec-version-branches/`](../recipes/spec-version-branches/)；專案沒裝 → 回報「未安裝」，不自己補做法）。宣告「有」的專案守以下規則：
   - **SPEC 只寫在 `main`**，`main` 可同時放好幾版的行為；版本歸屬只看 commit 引用的工作項**現在**的 milestone。
   - **每個開發中的 milestone 一條 `spec/vX.Y.Z`**：milestone 開工時從當下 `main` 開（⓪）；RD／QA 讀這條。**永不 merge 回 `main`**；除了解同步衝突與撤回，不手改。
   - **同步**（CI `spec-branch-sync`，每次 push `main`）：從分支點起依 `main` 順序 `cherry-pick -x` 每個 commit，**除非**它的工作項現在的 milestone 晚於該分支；沒引用工作項、milestone 不是版本號（如 Backlog）的照挑。衝突 → 停在那一筆、job 紅、通知團隊頻道，人在分支上解完才繼續（不跳過它挑後面的）；手挑一律帶 `-x`。分支上被 revert 的 commit，工作項改回不晚於本版時會被重挑。最終內容跟著每個工作項**現在**的 milestone 走。
   - **每日檢查**（排程 `spec-branch-check`）：報「缺」（該挑沒挑）與「多」（挑了，但工作項已改到更晚的 milestone），只報不修；撤不撤由人決定。
   - **工作項不需改 SPEC**：在 issue 留一行固定字樣 `SPEC 不用改，§X 已經這樣寫`（X＝現行條文的 §ID）。release 檢查機器比對這行，字樣不得改寫。
   - **SPEC 改動的 commit 沒引用這個工作項**（改在別張票，或帶票規則以前的舊 commit）：在 issue 留一行 `SPEC 變更：commit <sha>`（同行可列多個 sha），release 檢查認 sha 在分支上、沒被撤。
   - **Release**（⑤a）：跑 `spec_sync.py release-check vX.Y.Z`；通過才打 `spec/vX.Y.Z-release` tag，打了 tag 的分支＝關閉（不再同步、不再檢查）；不通過 → 清單給 PM，由 PM 決定。
   - **工作項 milestone 必須有效**：開著的 `spec/vX.Y.Z`、還沒開分支的未來版本號，或非版本號（如 Backlog）；打錯字的 milestone 會被歸到錯的版本，或被當成非版本號、挑進每一條分支。
   - **過渡**：專案開始要求每個 commit 引用工作項之前的 commit 不追溯（不判歸屬、不報缺）。

---

## 主要產出

### ⓪ milestone 起手清理（每個 milestone 開工前；從零到有 / 批次模式）

開新 milestone 前，先清上個 milestone 遺留的廢棄內容，避免 agent 誤讀失效規格：
- 廢棄的 Feature / US- 描述、對應的 TC
- TC 用 `~~TC-xxx~~ SKIP` 保留編號（防流水號錯亂），不直接刪號
- 清理動作走一張工作項＋決策檔

> 維護模式（逐項改）不需要這步；只在 milestone 批次開工時做。

**開版本分支（宣告 `版本分支同步：有` 的專案；不分批次／維護模式，每個 milestone 開工都做）**：從當下 `main` 開 `spec/vX.Y.Z`——`git push origin origin/main:refs/heads/spec/vX.Y.Z`（規則見 §SPEC 生命週期 7）。要先清理的，清理 commit 進 `main` 之後再開。

---

### ① `Spec/<module>/NN_*.md`（拆檔 SPEC 文件）

**鐵則：SPEC source of truth＝拆檔的固定檔名 `<module>/NN_<topic>.md`（NN＝章節編號；＋ Project_Context / Decision_Principles / Glossary / INDEX / Permission_Matrix）——一律就地 Edit、不押日期、不 cp 副本**；版本歷史由 git 承擔，有 frontmatter 者日期記 `last_updated`。INDEX / 流程圖 / cross-ref 都引用固定檔名，另存押日期會 fork 成孤兒檔（已知失敗模式）。押日期 `<feature>_SPEC_YYYYMMDD.md` 僅為拆檔前 monolithic 歷史快照，不再新建 / 追加。

**寫入工具：** 直接用 `Read` / `Edit` / `Grep` 操作 md（**禁止用 python-docx**，docx 不是 source of truth）；既有編號永不重編，刪除／退役／延後的節留 heading＋「（保留編號）」註記（SPEC_NUMBERING_RULES §3.5；專案原則若寫「刪節後重新連續編號」，以 §3.5 為準）。

**章節編號規則：** 所有 SPEC md 的 H1/H2/H3 編號照 [`SPEC_NUMBERING_RULES.md`](./SPEC_NUMBERING_RULES.md) 執行；spec-writer 寫入前後的強制檢查照其 §五逐項跑（scanner 順掃＝§六）。

**docx 輸出**（給雲端硬碟 / Reviewer / 工程師 handoff；專案有轉檔工具者）：用 md→docx 轉檔工具（未包含於此 repo）輸出 `<feature>_SPEC_YYYYMMDD.docx`（日期只加在**輸出 docx** 檔名、不動 source md）；樣式由專案自備的 docx 範本決定。

**寫入規範：** 只寫 PM 視角（使用者行為、操作流程、業務規則、畫面呈現原則）、不寫工程師細節——完整禁止清單見 `phase-1-product-design.md`（唯一權威）。

**✂️ 正文只留最後結論（本段為此規則唯一權威）**：SPEC 正文寫**規則本身**，不寫「為什麼會有這條」。

| 不進正文 | 例 | 該去哪 |
|---|---|---|
| 緣由 / 動機 | 「補 A 與 B 之間的空窗」 | `Spec/memory/` 個案決策檔的 Why |
| 演進 / 覆蓋史 | 「原本 X，後改 Y」 | 決策檔（`supersedes`）＋ git |
| 比照說明 | 「比照 §C 慣例」 | 不寫（規則自己站得住就好） |
| 拍板日期 / 過程 | 「（YYYY-MM-DD 拍板定案）」「議題 N」 | 決策檔 `date`／`source` |
| 延後字樣 | §SPEC 生命週期 1 清單 | `Spec/Deferred/`（走 deferrer） |
| 未來意圖 | 「今年先這樣」「未來可…」 | 正文改寫成現況事實；原句進決策檔「推翻了什麼」 |

- **反向護欄**：為了短而砍掉**規則**＝更嚴重的錯。邊界條件、例外、排序依據、適用範圍都是規則，一條不能少。
- **密度基準**：新寫的列 / 段落跟**鄰近既有列**同一密度；明顯長 2~3 倍就是在解釋自己，回頭刪。
- **`last_updated` 只放日期**，不寫歷史；heading 同受本表約束（見 §SPEC 生命週期 1）。
- **機械把關**（專案若有 prose lint 工具，見配方 [`spec-ci-gates.md`](../recipes/spec-ci-gates.md)）：diff 模式查新增行、全庫模式對 baseline 查全庫（皆硬門；pragma 與 baseline 規約見 §SPEC 生命週期 1）；限定詞守門工具列出改寫後限定詞／§ID／數字的變化供 verifier 判定。語意層（無日期無過程詞的解釋句）測不準，由 `phase0-spec-verifier` 維度 3 判。

**保留既有章節的格式語言**：heading 層級（## / ###）、表格風格、列表縮排，新章節和原文件一致。

---

### ② `Spec/Project_Context.md`（架構級事實）

**用途：** 記錄跨任務都要知道的脈絡（Navigation、頁面定位、模組分工、命名規則）。新 session 進來必讀。

**寫入規範（避免肥厚）：**
- 用「**一句話結論 + 指向 SPEC md 的連結**」格式，**不複製 SPEC 細節**
- 不寫版本演進史（「X 月 X 日覆蓋舊決議」）→ 直接覆蓋成最新版，歷史由 git 承擔
- 不寫待確認事項、未來擴充點

**每次寫入 SPEC 時的判斷：** 「這件事是否影響其他模組 / 其他 US 的設計判斷？」是 → 更新 Project_Context；否 → 不更新。

`Spec/Project_Context.md` 頂部若有「寫入規範」段，另照它執行。

---

### ②a `Spec/Decision_Principles.md`（決策原則）

**用途：** 記錄 PM 的設計原則、紅線、優先順序、利害關係人痛點。讓 agent 在 SPEC 沒明確規定時也能用 PM 的思路推論。

**每次寫入 SPEC 時的判斷：** 「這次討論是否揭露了一條**下次討論其他 US 還用得到**的原則 / 紅線？」是 → 抽象成原則寫入對應段；否 → 不更新。

**禁止行為：** 把個案決策（「這次選 A 不選 B 因為 X」）寫進來 → 那是個案決策，留在 SPEC md。

`Spec/Decision_Principles.md` 頂部若有「寫入規範」段，另照它執行。

---

### ③ 決策檔（`Spec/memory/`）

**每次 SPEC 異動**都寫／更新一份決策檔（一決策一檔；欄位與內文四段見 §SPEC 生命週期 3），`Spec/memory/index/` 跑專案腳本（[`decisions.py`](../recipes/spec-ci-gates/decisions.py) `views`）產生、不手改。寫入位置與分層照 workspace 的 memory 分層政策（未包含於此 repo）：`$CLAUDE_WORKSPACE` 的 MEMORY.md 只收跨專案內容。

---

### ④ `Spec/README.md`（文件地圖）

**用途：** `Spec/` 資料夾的目錄頁（檔案地圖），列出所有 SPEC 文件。

**新增／刪除／改名 SPEC md 時：** 更新本 README 的文件清單表（檔名、說明；不寫日期）。

---

### ⑤ 交棒給工程

SPEC 定案後交給工程的方式（交棒格式、待決事項追蹤）依各團隊慣例而定，不在本工作流範圍內。

---

### ⑤a milestone release：release-check → tag（宣告 `版本分支同步：有` 的專案）

milestone 上線前：
1. 本機跑 `python3 ci/spec_sync.py release-check vX.Y.Z`，它查四件事：① 分支與同步結果一致（沒有缺、沒有多）② milestone 下每個工作項（含已關閉）有引用它的 commit 從分支最新 commit 往回找得到（含分支點以前的，扣掉分支上撤掉的），或 issue 描述／留言有 `SPEC 變更：commit <sha>`（sha 在分支上、沒被撤）或 `SPEC 不用改，§X 已經這樣寫` 那行 ③ 分支上沒有更晚 milestone 的東西 ④ 列出沒引用工作項的 commit（參考，不擋）。
2. 通過 → `python3 ci/spec_sync.py release-check vX.Y.Z --tag`：全過才在分支最新 commit 打 `spec/vX.Y.Z-release` 並推；分支從此關閉。
3. 不通過 → 清單原樣給 PM，由 PM 決定補、撤或照樣放行；Claude 不自己改分支、不自己打 tag。

---

## PM SPEC 禁止清單（Not In Scope）

> PM 產出的規格（SPEC md、Project_Context.md）只描述行為、不描述實作——完整禁止清單（含錯誤示例 / 正確寫法 / 可保留的技術語言）見 `phase-1-product-design.md`（唯一權威）。

---

## 自我檢查層（Self-Review）── 寫入完成後、送出回報前強制執行

- 回報前對照「結構化定案清單」逐項核：重讀實際輸出檔案，確認每條定案都已落檔（不靠記憶或假設）
- 決策檔欄位填齊、`last_updated`（若有）只有日期、改動行（含 heading）無延後字樣與未來意圖、沒有新增不合格 pragma
- 跑 `git status` 確認無多餘新檔（防 fork）：出現非預期 `??` SPEC md 副本 → 刪副本、內容改回就地 Edit 原檔
- 漏項即補、不留裸項；跳過必附一句理由（沒有理由的跳過＝未完成）
- ⑨a verifier 與 `.claude/spec-dirty.log` 會對自報結果做客觀複核（不信任 Self-Review 自報）

---

## 收尾：連結 regen（若專案有 regen 工具）

SPEC 鎖版後、commit 前：**若本專案 CLAUDE.md 定義了「連結 regen 工具」，主動問 PM 要不要跑它**（PM 同意才 `--apply`，不靜默自動跑；問時列出它會做的事）。
工具與「圖是哪個檔」由各專案 CLAUDE.md 宣告（例：專案自備的連結 regen 腳本，未包含於此 repo）；沒定義 regen 工具的專案跳過此步。概念、分層與完整說明見 [`CROSSLINK_REGEN.md`](./CROSSLINK_REGEN.md)。

---

## Checklist（Phase 0 鎖版前）

- [ ] 討論的 open question 都有明確答案（不留 TBD）；PM 已拍板並**確認 scope**（本次要寫哪些情境）
- [ ] **已執行影響範圍掃描**（或 Opus 在拍板時明確宣告「本議題無外部連動」）；強連動已全部納入定案、弱連動已逐項由 PM 拍板處理方式
- [ ] **章節編號完整性檢查通過**（照 `SPEC_NUMBERING_RULES.md`；發現既有破損已在回報中明示通知 PM）
- [ ] **已執行 @phase0-spec-verifier 獨立稽核（⑨a）**：每個 commit 都有 verifier pass 與 `Verified-by:` trailer；機械性偏差已自動修正並列於報告；「待 PM 裁決」項（若有）已處理
- [ ] **（存量清理／遷移）已由獨立稽核 agent 宣告完成**（§SPEC 生命週期 6(c)）
- [ ] **已執行 @phase0-mockup-drift-scanner（⑨b）**：四 bucket 分類報告已產出（必審 / 待規劃 / dangling 必修 / 跳過）
- [ ] **PM 已依 drift 報告選定 commit 策略**（Path A 純文字單 commit / Path B feature branch 兩 commit + Phase 1 mockup 更新）；dangling 必修項已在 Path B 內處理，不允許帶 dangling reference 進 main
- [ ] **決策檔正確**：本批決策已寫入該專案 repo 的 `Spec/memory/` 決策檔（欄位齊、`changes` §ID 都存在、`source`＝工作項；**不是** `$CLAUDE_WORKSPACE` 的 MEMORY.md），`Spec/memory/index/` 由腳本重產；正文（含 heading）無延後字樣、`Spec/Deferred/` 錨點未斷（斷了 PM 已知情）
- [ ] **（若專案有 regen 工具）已主動問 PM 是否跑連結 regen**；PM 同意則已 `--apply`
- [ ] **PM 審閱通過後才 commit & push**（每個 commit 引用一個工作項全路徑；⑨ 寫完不自 commit；單一專案 repo；working tree 乾淨；main 只能 fast-forward；Path B 確保 SPEC + mockup 同一個 merge 進 main）

**產出：**
- `Spec/<module>/NN_*.md`（拆檔；就地 Edit；status: locked，source of truth）
- `Spec/Project_Context.md`（若需要更新，用一句話 + 連結格式；status: current）
- `Spec/Decision_Principles.md`（若有新原則，更新對應段；status: current）
- `Spec/memory/` 決策檔（new／`status` 改 superseded）＋腳本重產的 `Spec/memory/index/`
- （延後／接回時）`Spec/Deferred/<功能>.md`、`Spec/BACKLOG.md`
- `Spec/README.md`（更新文件清單）
- 以上全部 commit & push 到該專案 repo（PM 審閱通過後）
