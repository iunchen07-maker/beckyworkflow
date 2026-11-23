---
phase: 4
name: 驗收腳本
executor: Claude（基於 Phase 1 的 User Story 生成，PM 審閱確認）
reads_from:
  - dev-spec/product-spec.md（Phase 1 衍生的 User Story，含 data-action 標注）
  - HTML設計稿/定案/*.html（data-action selector 來源）
feeds_into:
  - workflow/phase-6-autotest.md（執行）
  - workflow/phase-8-userguide.md（步驟文字 + 例外情境 → User Guide）
also_see: workflow/CONTRACTS.md（Contract B）
---

> 🔍 **驗證總則**：本 Phase 的產物要符合 [`verification.md`](verification.md)——驗收腳本由非實作者先寫、實作方不得修改、誤判走留紀錄的跳過。


# Phase 4｜驗收腳本

> **Claude 的工作：** 讀取 Phase 1 的 User Story（已含 data-action 標注），直接生成可執行的 YAML 驗收腳本
> **PM 的工作：** 審閱生成的 YAML，確認驗收情境正確，如有遺漏再補充說明給 Claude

---

## 生成依據：User Story 中的 data-action 標注

Phase 1 的 `dev-spec/product-spec.md` 裡，每個互動步驟已標注 `[data-action: xxx]`，Claude 直接用這些值作為 YAML selector，不需要 PM 額外補充（YAML 欄位結構見下方「Happy Path 格式」節）。
如果 PM 需要補充驗收情境（User Story 之外的情況），用口語描述即可，Claude 會對照現有的 `data-action` 自動補上 selector。

---

## TC 展開技法（寫 TC 前的設計層）

> 這節管「怎麼想出該寫哪些 TC」。順序固定：**先建 coverage matrix → 套技法展開 → 最後才落 YAML**。

### 1. Coverage matrix 先行

寫任何 TC 之前，先建一張「需求 → 情境 → 優先級 → oracle」矩陣；**matrix 沒建好不准落 YAML**。

| 需求 | 情境 | 優先級 | oracle（預期結果怎麼驗） |
|---|---|---|---|
| 使用者把任務標為完成 | 在使用中的清單勾選任務（HP） | P0 | 任務移到「已完成」區，顯示完成時間 |
| 使用者把任務標為完成 | 在已封存的清單勾選任務（EC） | P1 | 畫面提示清單已封存，任務狀態不變 |

兩個規則：
- **oracle 與情境分開設計**：先想「這個情境要驗什麼業務結果」，再想操作步驟。斷言對準業務結果（例：「任務移到『已完成』區」），不寫實作細節（例：不寫「DB 某欄位=1」）。
- 上游已跑過 [scenario-expansion](../skills/scenario-expansion/SKILL.md) skill 的情境矩陣時，**直接沿用當 matrix 底稿**，不重做。

### 2. 五個技法速查表

套標準測試設計技法展開：等價劃分、邊界值、決策表、狀態轉移、pairwise（pairwise 僅參數 ≥4 且全組合爆炸時啟用，參數少直接決策表）。domain 範例：
- 任務標題長度 0 / 1–200 / >200 字三類各測一條（等價劃分）；標題上限 200 字 → 測 199 / 200 / 201（邊界值）
- 角色（Owner / Collaborator / Viewer）× 任務是否自己建立 × 任務是否已完成，決定「能不能刪除」（決策表）；任務狀態機每條合法轉移各一條＋封存後不能再改（狀態轉移）
- 顯示設定 排序方式 × 顯示密度 × 語系 × 主題色 全組合上百條 → pairwise 縮到十幾條

### 3. Pairwise 降層規則

pairwise 矩陣產出的組合，**只有 P0 代表組合**進 `tests/AGENT_TEST_INSTRUCTION.md` 給 Phase 6 自動跑。
其餘組合留在 matrix 裡，當 Phase 7 人工抽測清單、或未來 API 層測試的素材——**不佔瀏覽器自動化額度**（E2E 每條都貴）。

### 4. 白話紅線（硬約束）

每一條 TC——**包括矩陣機械展開出來的**——都必須寫成「一般用戶照著做得出來」的故事，沿用既有步驟規則：一般用戶語言、主動語態、不寫 selector / class / API。
某條組合怎麼寫都寫不成白話步驟＝**降層訊號**：它不該是 E2E case，改列 API 層素材或 manual。

### 5. manual 標記（天生不能自動化的驗收）

視覺判斷、信件文案通順度、列印版面這類天生不能自動化的驗收，**用同一套 YAML 格式寫**，加 `manual: true` 欄位：

```yaml
test_id: T3-4-EC
us: US-T3.2
ac: US-T3.2
name: 任務到期提醒信文案通順、收件人稱謂正確
manual: true      # Phase 6 跑到就跳過，報告列為「manual 待驗」
preconditions:
  - 系統已寄出任務到期提醒信
steps:
  - step: 1
    action: "打開到期提醒信，確認文案通順、稱謂與收件人相符"
    screenshot: false
expected:
  - 信件文案通順，稱謂正確
```

- Phase 6 跑到 `manual: true` 就跳過，並在報告列為「manual 待驗」
- Phase 7 人工照同一份步驟走完，不另寫第二套

---

## 兩層驗收的分工

| 驗收層 | 時機 | 負責人 | 說明 |
|---|---|---|---|
| **Mockup 驗收** | Phase 1 鎖版前 | PM | 在瀏覽器確認設計稿視覺和互動邏輯正確 |
| **功能驗收** | Phase 6 | Claude（Bash 驅動 Playwright / Cowork computer-use） | 對真實 DOM + 真實資料跑 YAML 腳本，自動截圖 |

Phase 4 的 YAML 腳本是給**功能驗收（Phase 6）**用的，不是重新驗 mockup。

---

## 測試觸發粒度

採 A / B **兩模式並存**，由 PM **每個 milestone 視情境挑**（非一次性鎖定）：

| 選 A（issue 完成即測） | 選 B（milestone 完成統一測） |
|---|---|
| 功能彼此獨立 | 功能相依高、要整合測 |
| 改動小、想早抓 bug | 多 issue 交錯、單測沒意義 |

PM 在該 milestone 開工時指定 A 或 B；未指定時問 PM，不自行假設。

---

## 測試腳本結構

每個 Suite 對應一個功能模組，每個 Suite 內分三類 test case：

```
Suite N：[功能名稱]
  T{N}-{n}-HP  Happy Path（主流程）
  T{N}-{n}-EC  Edge Case（邊界情境）
  T{N}-{n}-ER  Error（錯誤 / 例外情境）
```

---

## TC ↔ SPEC 追溯與編號紀律

每條 TC 都要能 5 秒查回對應 SPEC，但 **TC ID 與 US- 號脫鉤**，避免 SPEC 重編號時連動大改。

1. **TC ID 不內嵌 US- 號**：維持 `T{N}-{n}-TYPE`，發出去就是永久身分證，永不因 SPEC 改號而動。
2. **每條 TC 掛 `us:` / `ac:` 指標欄**，指向穩定的 US- 鍵：

   ```yaml
   test_id: T1-1-HP
   us: US-T1.1        # 對應 user story（穩定鍵）
   ac: US-T1.1.7      # 精準到驗收條件子節
   ```

   查 SPEC 靠這兩欄，不靠 ID 文字。

   **`ac:` 的粒度分兩類（對應 phase-1-product-design.md「升 AC 判準」）：**
   - 由 **AC 派生**的 TC（P0 情境已升 AC 子節）→ `ac:` 精準指子節：`ac: US-T1.1.7`
   - 由 **P1/P2 情境直生**的 TC（情境未升 AC、不在 SPEC）→ `ac:` 指 US 整體：`ac: US-T1.1`（情境敘述寫在 TC 的 `name` / `preconditions`，SPEC 不另記）
3. **append-only**：新功能給下一個沒用過的 Suite 號（不插隊重排）；新 TC 給該 Suite 下一個 `n`。
4. **刪 TC 用 SKIP 保號**：`~~T1-3-EC~~ SKIP`（附原因），不重用號。
5. **SPEC 舊格式段落轉成 US-（`SPEC_NUMBERING_RULES.md` §七 專項）時**：只改 `us:` / `ac:` 欄的值（機械 find-replace，併入專案的連結 regen 腳本，~0 LLM token）；TC ID 不動。

> 為什麼成本低：US- 標籤（L1.1 / T1.1…）本來就**獨立於 Chapter、既有編號永不重編**（見 `SPEC_NUMBERING_RULES.md` §3.5），日常不觸發改號；舊格式段落轉 US- 的專項也只是腳本替換 `us:` 欄。

---

## Happy Path 格式（同時是 User Guide 操作骨架）

> ⚠ **`guide_section` 的值必須從「專案根目錄的 `GUIDE_SECTIONS.md`」複製貼上，不能自己改寫**（`workflow/GUIDE_SECTIONS.md` 只是空白範本，不從那份複製）。
> Phase 1 mockup 的 `data-guide-section` 也用同一份表，字串不一致會導致 Phase 8 無法分組。

```yaml
test_id: T1-1-HP
us: US-T1.1                        # 對應的 user story（穩定鍵，查 SPEC 靠這欄）
ac: US-T1.1.7                      # 精準到驗收條件子節
name: 完成任務並封存
guide_section: "完成與封存任務"    # 從 GUIDE_SECTIONS.md 複製，必填
guide_order: 2                     # 從 GUIDE_SECTIONS.md 的「順序」欄填入（數字）
preconditions:
  - 以清單 Owner 帳號登入，清單「未完成」分頁至少有一筆任務

steps:
  - step: 1
    action: "在「未完成」分頁勾選任務前方的核取方塊"   # 一般用戶語言，主動語態
    selector: "[data-action='toggle-done']"     # Phase 1 mockup 的 data-action
    screenshot: true                             # Phase 6 截圖，Phase 8 使用

  - step: 2
    action: "點擊「已完成」分頁，確認剛勾選的任務出現在列表中"
    selector: "[data-action='tab-done']"
    screenshot: false

  - step: 3
    action: "點擊「封存已完成」"
    selector: "[data-action='archive-done']"
    screenshot: true

  - step: 4
    action: "在確認視窗點擊「封存」"
    selector: "[data-action='confirm-archive']"
    screenshot: false

expected:
  - 任務狀態為「已封存」，只出現在「已封存」分頁
  - 「已封存」分頁中的任務無法編輯
```

**步驟描述規則：**
- 用**一般用戶語言**，不寫 selector、class name、API
- 主動語態：「點擊」「填寫」「選擇」，不寫「系統將會⋯」
- 每個步驟一個動作，不合併
- `screenshot: true` 的步驟描述要夠清楚，截圖旁直接貼這句話就看得懂

---

## Edge Case / Error 格式（含 User Guide 例外情境標記）

格式同 Happy Path，增量欄位差異（用戶可見的例外情境要進 User Guide 時加）：

- `guide_include: true` — 這個情境要進 User Guide（判斷標準見下）
- `guide_type: "exception"` — 值域：exception | warning | info
- `guide_caption:` — 給一般用戶的例外說明（現象 → 原因 → 怎麼做），不超過 100 字

`guide_section` / `guide_order` 與同功能 happy path 對齊；`us:` 同功能 → 同 us，`ac:` 指邊界條件對到的 AC 子節；「錯誤狀態」畫面照樣標 `screenshot: true` 截圖。

**`guide_include: true` 的判斷標準：**

這個情境「一般用戶自己操作時可能遇到」就標 `true`。例如：
- ✅ 「已完成」分頁沒有任務時點「封存已完成」，只看到提示（使用者可能以為沒反應）
- ✅ 「已封存」任務無法編輯，要先點「還原」（使用者需要知道怎麼做）
- ✅ Viewer 看到核取方塊呈停用樣式（使用者可能困惑）
- ❌ DB 連線失敗（後端錯誤，不是用戶操作場景）
- ❌ Race condition 測試（技術測試，用戶不會遇到）

---

## 截圖標記說明

`screenshot: true` 的步驟，Phase 6 執行時會自動截圖並存入 `reports/screenshots/`。

命名規則（**必須符合才能讓 Phase 8 自動對應**）：
```
reports/screenshots/{test_id}_step{step}.png
例：T1-1-HP_step1.png
    T1-3-EC_step2.png
```

---

## Checklist（鎖版前確認）

- [ ] 每個功能都有 happy path，`guide_section` 與 Phase 1 mockup 的 `data-guide-section` 一致
- [ ] 關鍵步驟都有 `screenshot: true`；用戶可見的例外情境都有 `guide_include: true`
- [ ] 所有 selector 都對應 mockup 中的 `data-action`；每條 TC 都填了 `us:` / `ac:` 指標欄
- [ ] 新增 TC 用 append-only 號；刪除用 `~~TC~~ SKIP` 保號，不重用

**產出：** `tests/AGENT_TEST_INSTRUCTION.md`（status: locked 後進 Phase 5 / Phase 6）

**選用產出（僅專案走 Phase 5 Flow B 時）：** `engineer-prompt.md` —— Phase 4 收尾時由 PM＋Claude 從 Phase 1/2/4 產出彙整（Section A 開發指令＋Section B 測試站 BASE_URL 佔位＋Appendix selector 對照表），內容規格見 `phase-5-dev.md` Flow B 段。走 Flow A 的專案不需要。
