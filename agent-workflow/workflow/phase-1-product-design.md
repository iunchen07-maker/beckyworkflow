---
phase: 1
name: 產品設計包
executor: PM + Claude（你討論方向，Claude 產出，你審閱修改）
reads_from: BRIEF.md（或對話中的需求描述）
feeds_into:
  - workflow/phase-2-spec.md（工程師從這裡推導技術規格）
  - workflow/phase-4-tests.md（驗收腳本的基礎）
  - workflow/phase-8-userguide.md（guide caption → User Guide）
also_see: workflow/CONTRACTS.md（Contract A、B）
---

# Phase 1｜產品設計包

> **你的角色：** 描述需求、給修改方向、最後審閱確認
> **Claude 的角色：** 產出所有文件，包含畫面、功能標注、User Story
>
> 你不需要自己寫規格或畫畫面——把你的想法說給 Claude 聽，Claude 寫出來你再說「這裡不對」。

---

## 執行順序

```
① PM 描述需求（對話）
      ↓
② Claude 產出 annotated mockup HTML（畫面 + 功能標注 + data-action）
      ↓
③ PM 在瀏覽器審閱，給修改方向
      ↓
④ Claude 修改直到 PM 確認
      ↓
⑤ Claude 從 mockup 衍生 User Story（dev-spec/product-spec.md）
      ↓
⑥ PM 審閱 User Story，確認後鎖版
```

> **HTML 與 SPEC 是往返的（不是單向）**：① SPEC 訂版後才開始畫 HTML → ② 畫的過程常冒出新的規格問題 → **繞回 Phase 0 討論、拍板那批新 SPEC** → ③ HTML 訂版。所以 Phase 0 ↔ Phase 1 會來回幾輪。每次訂版收尾都要做下方「連結 regen」。

---

## 主要產出

### ① `HTML設計稿/` 的 mockup HTML（設計稿 + 功能標注）

**這是 Phase 1 的主規格。** 每個主要頁面一個 HTML 檔，在瀏覽器直接開可預覽。

**落點與命名（三層結構，規則詳見專案 `HTML設計稿/README.md`）：**
- 新畫、未拍板 → 一律先放 `HTML設計稿/討論中/`
- 拍板後 promote → `git mv` 進 `HTML設計稿/定案/` ＋ 更新專案的**稿件狀態索引**（預設＝`定案/index.html` 補卡；專案若在 `HTML設計稿/README.md` 另有指定索引物則從其記載。一律對號入座既有分類，不自創新大類）
- 下游（Phase 2/4/5/8、drift 掃描）**只認 `定案/`**；被取代舊稿 `git mv` 進 mockup 封存資料夾（封存禁區）

#### 功能標注：`data-spec`（PM 看的說明）

每個區塊和互動元素都要有功能說明，讓 PM 在畫面上就能看懂這個東西做什麼。`data-spec` 是給 PM 看的純說明文字，不影響程式邏輯，可以寫得口語一點：

```html
<section data-spec="擁有者建立新任務的表單。填完後點儲存，任務加入目前清單並通知清單協作者。">
  <!-- 互動元素用 data-spec + data-testid + data-action 三標注（標注鐵則第 2 條） -->
  <button data-action="save-task" data-testid="task-form-save"
          data-spec="儲存並建立任務。觸發：系統建立任務 → 狀態設為「未完成」→ 通知清單協作者。">儲存</button>
</section>
```

#### `data-action`（工程師實作依據）

所有互動元素都要加，並且**值要在 User Story 裡也出現**（見下方），讓工程師在 spec 和程式碼之間能對齊：

```html
<button data-action="save-task">儲存</button>
```

> ⚠ **工程師交接規範：`data-action` 的值在真實實作的 DOM 上必須保留，不能改名或移除。**
> Phase 4 驗收腳本的 selector 依賴這個屬性，改了就斷。

#### `data-guide-*`（給 Phase 8 User Guide 用）

> ⚠ **`data-guide-section` 的值必須從專案的 `GUIDE_SECTIONS.md` 複製貼上，不能自己改寫。**

| 屬性 | 規則 |
|---|---|
| `data-guide-order` | 從 `GUIDE_SECTIONS.md` 的「順序」欄填入（兩位數字） |
| `data-guide-section` | **從 `GUIDE_SECTIONS.md` 複製，完全一致** |
| `data-guide-step` | 兩位數字，同一章節內的步驟順序 |
| `data-guide-caption` | 一般用戶語言，30 字以內 |
| `data-guide-type` | `exception`（系統擋住）/ `warning`（警告可繼續）/ `info`（說明性提示） |

例外狀態也要做出來，加 `data-guide-type`：

```html
<div data-action="task-title-input-error" data-testid="task-title-input-error"
     data-spec="任務標題超過 100 字元時的錯誤狀態。用戶手動修改縮短後錯誤提示自動消失。"
     data-guide-order="02" data-guide-section="建立任務" data-guide-step="03"
     data-guide-caption="若標題超過 100 字元，欄位出現紅色警告，直接修改縮短即可。"
     data-guide-type="exception"><!-- 錯誤狀態畫面 --></div>
```

#### 📐 標注鐵則（基準範例＝專案指定的一支 `HTML設計稿/定案/` 基準 mockup）

> 動機：規格手抄印在畫面上會（1）淹沒 UI 本體害 PM 審不動（2）變成會過期說謊的第二份真相。
> 規格真相只有兩個家：**SPEC md（給人）＋元素 data-* 屬性（給機器）**，畫面不留第三份。

**0. 紅線：非畫面元素絕對不准落入畫面。** 任何不屬於產品 UI 本體的內容——規格說明、決策紀錄、驗收條件、收件者/分流規則、對照表、開發者備註——**一律不得畫進產品畫面區**；它們只能活在 `data-*` 屬性、SPEC md，或下方白名單的 meta 層。meta 層必須一眼可辨非產品（深色、固定高度、與產品 UI 物理分離），絕不混進產品畫面內部（不放 info box、不放說明卡、不佔產品版面一格）。

**1. 畫面上只准出現 UI 本體＋白名單 meta 層（其餘一律禁止）：**
- 頂部「規格資訊列」（meta 區第 1 列，深色）：US 編號＋標題＋摘要（`<details>` 收合）＋ SPEC 檔案路徑＋「🔍 規格標注」toggle 按鈕
- 「DEMO 切換列」（meta 區第 2 列，選配，見第 5 條）：角色／情境切換器
- `▼ 狀態展示 N：標題` 分區標題
- `§US-x.y.z` 出處 chip（一行，不寫拍板長文）
- 唯一例外：⚠ 活待辦標記（如「SPEC §X 待改寫」）——它是待辦不是說明，事畢即刪

**1b. 位置鐵則＋完整頁面示意**：白名單 meta 元素一律位於**畫面框外**（分區標題行／畫面上方 meta 區），絕不插進畫面內容流——排進頁面裡看起來就是規格印在畫面上，工程師會以為要實作。每個呈現的畫面態本體必須是**完整頁面示意**（一看就知道上線後長怎樣）；多狀態／多身份只走兩法：(a) DEMO 切換列切完整頁（首選），或 (b) 情境區塊靜態並列（「情境 N — 標題」行＋完整畫面片段＋下方灰底「→」單行註解、區塊間明顯區隔）。禁止同一張底圖用分隔線切狀態、禁止自創視窗框包狀態。

**2. 規格內容一律寫進三個屬性，不印在畫面上（三者缺一不可）：**
- `data-spec`：SPEC 對齊＋drift 掃描錨點（給 PM / drift-scanner）
- `data-testid`：Playwright 定位錨點（給 Phase 6；同一動作多入口時 testid 必須各自唯一）
- `data-action`：動作語意（給 Phase 4 生測試、Phase 5 實作對齊；實作 DOM 必須保留）

**3. 給人看規格＝開「🔍 規格標注」annotation overlay：**
hover 任一帶 `data-spec` 的元素 → 底部面板**即時讀屬性渲染**它的 testid / action / 規格全文。
前端工程師指著元素抄名字、讀行為，全程不開 source。內容無第二份文字、結構上不會 drift。
**禁止**再新增任何印在畫面上的規格手抄：驗收清單、Tech Note、testid/action 對照表、規則說明 box、側欄 spec panel——一律不留。

**4. overlay snippet＝固定區塊，原樣複製（每支 mockup 一份、inline 自足）：**

> 三個 snippet（overlay／DEMO 切換列／guide-section 標注）一律從專案指定的基準 mockup 檔原樣複製——不要手打、不要重寫。

- 頂部規格資訊列：放 `<body>` 第一個元素；app 外框高度改 `calc(100vh - 36px)`
- overlay 本體：放 `</body>` 前

**5. 角色／情境切換器＝統一用「DEMO 切換列」（基準範例＝專案指定基準 mockup 的 demo-bar）：**
同一支稿需要多角色（Owner / Collaborator / Viewer…）或多情境檢視時，切換器**一律**做成 meta 區第 2 列，緊貼規格資訊列下方，不准散落在產品畫面裡（snippet 從基準檔複製，見第 4 條）。

規矩：
- 切換器**只切換檢視狀態**（show/hide 對應區塊），不得承載規格文字；各視角的差異規則寫進該列與對應元素的 `data-spec`
- 標示「DEMO」＋「不會出現在真實產品上」，與規格資訊列同為深色 meta 族
- app 外框高度記得再扣這列的 36px（`calc(100vh - 72px)`）
- 切換 seg 的樣式固定：深色底、active 用強調色白字（色值依專案指定的 design system）

**6. 既有舊稿**：不強制回頭改；改到哪支（Phase 0 drift 必審、design review）就順手收斂到本鐵則。

---

### ② `dev-spec/product-spec.md`（User Story——派生自 `Spec/` 正本 + 綁 mockup 對應）

PM 審閱確認 mockup 後，Claude 讀取所有 `data-action` + `data-spec` + 例外狀態，整理成 User Story 格式。**PM 不需要自己寫，只需要審閱和確認。**

> **US 文字的正本在 `Spec/` feature md（Phase 0 已寫的 US-）**：若該功能的 US 已在 Phase 0 進 `Spec/`，product-spec 的 US 文字一律**以 `Spec/` 為準、派生不重訂**，本階段只新增「US ↔ mockup 畫面 / `data-action` 對應」。Phase 0 尚未涵蓋的部分才在此首次成文（之後繞回 Phase 0 收進 `Spec/`），避免兩處各有一份 US 文字 drift。

每個功能一個 User Story，**互動步驟帶上 `data-action`**，讓工程師看 spec 就知道 DOM 要埋什麼：

```markdown
## US-001：完成並封存任務

**角色：** 清單擁有者（Owner）
**前置條件：**
- Owner 已登入並開啟一個含任務的清單（清單頁有「未完成／已完成／已封存」三個分頁）

**主流程（Happy Path）：**
1. 在「未完成」分頁勾選任務前方的核取方塊 `[data-action: toggle-done]`
2. 切到「已完成」分頁 `[data-action: tab-done]`，確認任務已移入
3. 點擊「封存已完成」 `[data-action: archive-done]`
4. 在確認視窗點擊「封存」 `[data-action: confirm-archive]`

**成功條件：**
- 勾選後任務狀態為「已完成」，標題顯示刪除線
- 封存後原「已完成」任務狀態為「已封存」，只出現在「已封存」分頁且為唯讀

**例外條件：**
| 情境 | 系統行為 | data-action |
|---|---|---|
| 「已完成」分頁沒有任務時點擊「封存已完成」 | 確認視窗改為提示「目前沒有可封存的任務」，只提供「關閉」 | `archive-done` |
| 以 Viewer 身分開啟清單 | 核取方塊與「封存已完成」呈停用樣式，滑鼠移上提示「僅可檢視」 | `toggle-done` |
```

> **驗收條件寫成可驗證 AC：** 每條「成功條件 / 例外條件」要是**可被單一 TC 驗證**的原子敘述（避免「系統正確處理」這種測不到的描述）。Phase 4 的 TC 會用 `ac:` 欄指回對應的 US- 驗收條件子節（見 `phase-4-tests.md`「TC ↔ SPEC 追溯與編號紀律」）。
>
> **升 AC 判準：** 情境矩陣（把功能展開成 HP/EC/ER 情境的產出，每條標 P0/P1/P2）中**只有 P0 情境升為 AC 子節**——維持 AC 薄、窮舉留 Phase 4。P1/P2 情境**不寫進 SPEC**，直接交 Phase 4 生 TC（該類 TC 的 `ac:` 指 US 層級，見 phase-4-tests.md）。

---

### ③ 流程圖

每個功能的操作動線 + 系統狀態流轉，Claude 產出，PM 審閱。

**形式不限：**
- 內嵌在 mockup HTML 裡（mermaid / SVG）
- 獨立的 `dev-spec/flow-{功能名稱}.md`

**必須涵蓋：**
- 主流程（Happy Path）
- 每個例外條件的分支走向
- 狀態變化（如有）

### 收尾：連結 regen（HTML / 流程圖訂版後）

HTML 或流程圖鎖版後：**若本專案 CLAUDE.md 定義了連結 regen 工具，主動問 PM 要不要跑**（PM 同意才 `--apply`）。
同步範圍、待人工 curate 項、工具宣告方式見 [`CROSSLINK_REGEN.md`](./CROSSLINK_REGEN.md)。

---

## PM SPEC 禁止清單（Not In Scope）

> PM 產出的規格（mockup、product-spec.md、SPEC 文件）**只描述行為，不描述實作**。
> 以下內容屬於 Phase 2 工程師自行推導的範疇，出現在 PM SPEC 中會干擾工程師的 Claude 判斷。

**禁止出現的內容類型：**

| 類型 | 錯誤示例 | 正確寫法 |
|---|---|---|
| DB table 名稱 | 查詢 `tag` 表 | 系統確認標籤被引用數量後顯示警告 |
| DB column 名稱 | 更新 `owner_id` 欄位 | 系統將清單轉移給新擁有者 |
| SQL / 查詢語法 | `UPDATE task SET status = ...` | 系統批量將任務標為完成 |
| Enum 值定義 | `status = archived` | 狀態：已封存 |
| 外鍵 / 計數查詢 | 檢查 `tag_id` 外鍵計數 | 系統確認引用關係後才允許刪除 |
| 排程 Job 實作細節 | `Nightly job：UPDATE task SET overdue = ...` | 系統每日標記逾期任務 |
| 後端 API 版本格式 | `client_version` 欄位比對 | 使用者使用舊版本時，系統推送更新通知 |

**可以保留的技術語言：**
- 狀態代碼（如 `task_open`、`task_done`）——這是溝通語言，PM 與工程師對齊用
- 外部系統名稱（如行事曆服務、身分驗證服務）——說明資料來源
- 觸發條件描述（如「每日凌晨系統同步」）——行為層，不是實作層

---

## Checklist（鎖版前確認；PM 在瀏覽器逐頁打開每個 HTML 確認）

- [ ] 所有功能都有 mockup（含例外狀態畫面），畫面視覺符合設計意圖
- [ ] `data-spec` 說明準確，看畫面就能理解每個元素的功能
- [ ] 所有互動元素都有 `data-spec` + `data-testid` + `data-action`（標注鐵則第 2 條：三者缺一不可；同一動作多入口時 testid 各自唯一）
- [ ] 每個關鍵畫面和例外狀態都有 `data-guide-*` 標記
- [ ] User Story 已從 mockup 衍生完成、PM 審閱確認，且每個互動步驟都有 `[data-action: xxx]` 標注
- [ ] 流程圖涵蓋所有 User Story 的主流程 + 例外條件
- [ ] 設計遵循**該專案指定的 UI 規範 skill**（見專案 CLAUDE.md 指定的 design skill／design system）
- [ ] **（若專案有 regen 工具）已主動問 PM 是否跑連結 regen；PM 同意則已 `--apply`，且待補卡 / 加節點項已處理**

> **Mockup 驗收是 Phase 1 的最後關卡**，不是 Phase 6。
> Phase 6 是功能驗收（真實 DOM + 真實資料），不是設計審查。

**產出：**
- `HTML設計稿/定案/*.html`（annotated，status: locked；經 `討論中/` → 拍板 promote ＋ index 補卡）
- `dev-spec/product-spec.md`（User Story，status: locked）
- `dev-spec/flow-*.md` 或流程圖內嵌於 HTML
