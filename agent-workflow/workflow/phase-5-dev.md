---
phase: 5
name: 開發實作（雙流程）
executor: Flow A — Claude Code（全自動）｜Flow B — 工程師主導 + Claude 協作
reads_from:
  - dev-spec/CLAUDE_DEV_INSTRUCTION.md
  - dev-spec/PENDING_SPEC.md
  - HTML設計稿/定案/*.html
  - engineer-prompt.md（Flow B 專用，含 data-testid 對照表）
feeds_into: workflow/phase-6-autotest.md
also_see: workflow/CONTRACTS.md（Contract D、E）、workflow/file-discipline.md（檔案紀律：Edit 優先／警戒線棘輪／新檔必接線）
---

# Phase 5｜開發實作

> 本 Phase 有兩種合法的執行流程，視專案與工程師偏好選擇其一。
> 兩種流程都必須滿足 Phase 6 自動化測試的前提條件：selector 屬性 100% 保留。

---

## 選擇開發流程

| | Flow A：Claude Code 全自動 | Flow B：工程師主導 + Claude 協作 |
|---|---|---|
| **適用時機** | 技術選型已由設計端決定，或專案為全新系統 | 工程師有既有架構偏好，或已有部分程式碼基礎 |
| **決策者** | Claude 自己讀 spec，自行規劃架構與拆步驟 | 工程師決定架構，Claude 照指令執行 |
| **Claude 角色** | 全端自主開發 | 受指揮的高速執行者 |
| **工程師介入** | 僅在 PENDING 項目需確認時 | 每個架構決策點都需工程師指示 |
| **前置文件** | `dev-spec/CLAUDE_DEV_INSTRUCTION.md` | `engineer-prompt.md`（含 data-testid 對照表） |

---

## 共用強制規範：selector 屬性必須保留

> ⚠ **兩種流程都適用，不得省略。**

Phase 1 的 mockup HTML 裡所有的 selector 屬性（`data-action` 或 `data-testid`，依專案約定），在真實實作的 DOM 上**必須原封不動保留**：

```html
<!-- mockup 裡是這樣（data-action 為通用約定；部分專案使用 data-testid） -->
<button data-action="save-task">儲存</button>

<!-- 真實實作也必須是這樣，不能改名或移除 -->
<button data-action="save-task" @click="handleSave">儲存</button>
```

Phase 6 的自動化測試 selector 全部依賴這些屬性，**改了就斷**。
前端框架的 class、id、位置都可以改，selector 屬性不行。

> **專案約定確認：** 開始開發前，確認本專案使用 `data-action` 還是 `data-testid`。
> 答案在 `HTML設計稿/定案/*.html` 或 `engineer-prompt.md` 的 Appendix 欄位對照表中。

---

## Flow A｜Claude Code 全自動開發

### 開發前確認

進入 Flow A 前，確認以下狀態：

| 項目 | 要求 |
|---|---|
| `dev-spec/CLAUDE_DEV_INSTRUCTION.md` | status: review（P0 確認後才能 locked） |
| `dev-spec/PENDING_SPEC.md` | P0 全部有「暫定 Mock 值」，不需全部確認 |
| `HTML設計稿/定案/*.html` | status: locked |
| `tests/AGENT_TEST_INSTRUCTION.md` | status: locked |

P0 未確認時照樣可以開始，前端 UI + 非 P0 功能都可以先做。

### 分步驟 Prompt 範本

不要只丟一句「依照規格開發」，照以下四行原則分步下指令：

- 分步推進（結構 → DB → 演算法 → 頁面 → 功能模組），每步有明確可驗收點
- 每步先讀 `dev-spec/CLAUDE_DEV_INSTRUCTION.md` 對應 Section 再動工；頁面參考 `HTML設計稿/定案/*.html`，UI 樣式遵循專案指定的 design skill
- PENDING 項目照本檔「PENDING 項目的處理規則」節處理（mock 替代＋TODO 標記照 Contract E）
- 每步完成的回報照本檔「每步驟完成的回報格式」節的三行格式

### PENDING 項目的處理規則

```js
// ✅ 正確：外部 API 尚未確認 → 先指向本地 mock server，標記 TODO，不阻擋開發
const APP_BASE_URL = process.env.APP_BASE_URL ?? 'http://localhost:3001/mock-api'

// ❌ 錯誤：因為等不到確認而跳過整個功能
```

TODO 標記格式照 CONTRACTS.md Contract E（唯一權威，不在此重複格式字串）。

### 每步驟完成的回報格式

Claude Code 每完成一步，必須回報：

```
✅ 已完成：[檔案清單]
⚠ 用了 Mock：[哪些 PENDING 項目，用了什麼替代值]
❌ 需要真實 API：[哪些功能現在無法測試，原因]
```

---

## Flow B｜工程師主導 + Claude 協作開發

> 工程師自己決定技術架構與拆解方式，Claude 作為高速執行者。
> 適合已有技術偏好的工程師，或需要融入現有程式碼結構的情況。

### 工程師需要準備什麼

在把任務交給 Claude 之前，工程師要準備：

| 文件 | 說明 |
|---|---|
| `engineer-prompt.md` | 給工程師的 Claude 的完整指令，含開發規則、路由表、狀態邏輯、角色權限與 data-testid 對照表 |
| `HTML設計稿/定案/*.html` | 設計稿 HTML，包含所有 selector 屬性 |
| 技術架構說明 | 工程師告訴 Claude 用什麼 tech stack、資料夾結構、API 規範 |

`engineer-prompt.md` 是本 Flow 的核心文件：**僅在專案選走 Flow B 時才產出**，由設計/PM 端在 Phase 4 收尾時從既有產出彙整（不另創內容）——Section A 開發指令（源自 `dev-spec/CLAUDE_DEV_INSTRUCTION.md` 的規則、路由表、狀態邏輯、角色權限）＋ Section B 測試站 `{{BASE_URL}}` 佔位＋ Appendix selector（data-testid / data-action）對照表（源自 Phase 1 mockup 與 Phase 4 YAML）。工程師在對話開頭直接貼給自己的 Claude。走 Flow A 不需要此檔。

### 給工程師的 Claude：Section A（開發指令）

工程師在開始開發時，把以下結構貼給他的 Claude：

```
[貼上 engineer-prompt.md Section A 的完整內容]

我們使用的技術架構：
- 前端：[e.g. React 18 + TypeScript + Zustand]
- 後端：[e.g. Node.js + Express + PostgreSQL]
- 部署：[e.g. Docker + Nginx]

請從 [頁面名稱] 開始，參考設計稿 [檔案名稱].html。
```

### 工程師的角色與責任

Flow B 中工程師需要主動做的事：

1. **架構決策**：每個功能的資料流、API 設計、元件拆分由工程師指示，不讓 Claude 自行假設
2. **分頁逐步推進**：每次只交代一個頁面或功能模組，確認後才進下一個
3. **selector 屬性驗收**：每個頁面完成後，對照 `engineer-prompt.md` Appendix 的 data-testid 對照表，確認所有屬性存在
4. **設計稿差異說明**：若實作無法 100% 符合設計稿，必須說明原因並記錄

### Flow B 的 Checklist（每頁完成後）

工程師收到 Claude 回報後，逐項確認：

- [ ] 頁面路由是否正確（依 engineer-prompt.md 路由表）
- [ ] `data-testid` 清單是否與對照表 100% 吻合（多一個不行，少一個也不行）
- [ ] 狀態驅動的 UI 元素可見性條件是否正確實作
- [ ] 角色權限邊界是否正確（無權限頁面回傳 403 或導向）
- [ ] 有無與設計稿的差異？若有，原因是否記錄

### Flow B 完成後的測試站移交

Flow B 的測試由設計/PM 端接手（Phase 6），工程師需要提供：

```
測試站 URL：https://[測試站網址]
測試帳號（每個角色一組）：
  - Owner：owner_test / [密碼]
  - Collaborator：collaborator_test / [密碼]
  - Viewer：viewer_test / [密碼]
備注：[任何已知限制或與設計稿的差異說明]
```

接到這些資訊後，將 `{{BASE_URL}}` 填入 `engineer-prompt.md` Section B，即可執行 Phase 6 自動化測試。

---

## Checklist（進入 Phase 6 前，兩種流程通用）

- [ ] 所有 P0 已確認，mock 已替換為真實 API
- [ ] 所有 TODO 標記已清除或有追蹤記錄
- [ ] 應用程式可以在測試站啟動
- [ ] 主要頁面可以在瀏覽器打開，無 console error
- [ ] 所有 selector 屬性（`data-action` / `data-testid`）已按對照表驗收
- [ ] 測試站 URL 與帳號資訊已確認，可交給 Phase 6
