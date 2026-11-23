---
phase: 2
name: 技術規格推導
executor: 工程師（Claude Code）
reads_from:
  - dev-spec/product-spec.md（Phase 1 產出的 User Story 規格）
  - HTML設計稿/定案/*.html（Phase 1 產出的互動設計稿）
feeds_into: workflow/phase-5-dev.md
also_see: workflow/CONTRACTS.md（Contract D）
---

# Phase 2｜技術規格推導

> Phase 2 由工程師（Claude Code）從 Phase 1 的產品設計包自行推導，**PM 不參與。**
> 工程師讀取 `dev-spec/product-spec.md` 和 `HTML設計稿/定案/*.html`，整理出 Claude Code 可以直接執行的技術輸入。
>
> 📁 **`dev-spec/` ＝ Phase 1~5 工件資料夾**（product-spec / CLAUDE_DEV_INSTRUCTION / PENDING_SPEC / flow-*），跑到該 Phase 才生成。**刻意不叫小寫 `spec/`**：在 macOS 等大小寫不敏感檔案系統，`spec/` 會與 SPEC 正本 `Spec/` 撞成同一資料夾，工件混進正本、污染 impact-scanner 掃描。

---

## 必須產出的六項（缺一不可）

### ① 功能規格

每個功能必須寫清楚：

```
功能名稱：在清單中建立任務
觸發條件：清單 Owner 或 Collaborator 手動操作
輸入：[列出所有必填 / 選填欄位，含欄位名稱、型態、驗證規則]
系統行為：[逐步說明系統做什麼，包含自動計算、背景觸發]
輸出：[API response、UI 狀態、通知]
錯誤處理：[每種錯誤情境 → 系統行為]
```

---

### ② API Endpoint 完整 List

每個 endpoint 必須包含：

```
方法 + 路徑：POST /api/lists/{listId}/tasks
Request body schema：{ 欄位名: 型態, ... }（含必填標記）
Response schema 範例：{ "id": "uuid", "status": "open", ... }
錯誤 response：{ 狀態碼: 說明 }
```

---

### ③ 資料模型（DB Schema）

每張 table 必須包含：

```sql
CREATE TABLE tasks (
  id          UUID PRIMARY KEY,
  list_id     UUID NOT NULL REFERENCES lists(id),
  status      VARCHAR(20) NOT NULL,  -- 合法值見狀態機
  title       VARCHAR(100) NOT NULL,
  ...         型態、NOT NULL、DEFAULT、說明
);
```

欄位名稱 + 型態 + nullable + 說明，都要有。Table 之間的 FK 關係要標清楚。

---

### ④ 狀態機（有狀態流轉的功能必備）

```
所有合法的 status 值：open | done | archived

轉換條件：
  open     → done     ：Owner / Collaborator 勾選核取方塊
  done     → open     ：Owner / Collaborator 取消勾選
  done     → archived ：Owner 點「封存已完成」並在確認視窗確認
  archived → done     ：Owner 在「已封存」分頁點「還原」
  （open 不能直接封存；Viewer 不能觸發任何轉換）

UI 對應：
  open     → 「未完成」分頁，空心核取方塊
  done     → 「已完成」分頁，打勾＋標題刪除線
  archived → 「已封存」分頁，唯讀、灰色文字
```

沒有狀態機，Phase 5 的 status 欄位值會和 mockup / test 對不起來。

---

### ⑤ 演算法實作（有複雜邏輯的功能）

規則說清楚了，也要給**可直接執行的 code**（JS / Python / pseudo code 都可）。

範例：重複任務的下一個到期日計算

```js
function nextDueDate({ dueDate, repeat, skipWeekends }) {
  // Rule 1：依重複週期往後推
  let next = addInterval(dueDate, repeat)
  // Rule 2：若設定跳過週末，順延到下一個工作日 ...
  return skipWeekends ? toNextWeekday(next) : next
}
```

---

### ⑥ 專案資料夾結構

```
/project
  /frontend
    /src
      /views       ← 哪些頁面
      /components  ← 哪些共用元件
      /stores      ← Pinia store 清單
      /api         ← API 呼叫層
  /backend
    /routes        ← route 清單
    /services      ← 業務邏輯
    /models        ← DB model
  /mock-api        ← 開發用 mock
```

---

## Checklist（鎖版前確認）

- [ ] 所有功能都有「觸發條件 / 輸入 / 行為 / 輸出 / 錯誤」五項
- [ ] 所有 API endpoint 都有 route + request schema + response 範例
- [ ] 所有 table 欄位都有型態和說明
- [ ] 所有有 status 的 table 都有狀態機（含 UI 顯示對應）
- [ ] 複雜演算法都有 code，不只是文字說明
- [ ] 資料夾結構已定義

**產出：** `dev-spec/CLAUDE_DEV_INSTRUCTION.md`（工程師從 product-spec.md + mockup 推導，status: locked 後進 Phase 2.5）
