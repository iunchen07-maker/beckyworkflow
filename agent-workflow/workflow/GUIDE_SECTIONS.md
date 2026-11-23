# User Guide 章節定義表（GUIDE_SECTIONS）— 空白範本

> **唯一來源（Single Source of Truth）**
>
> Phase 1（Mockup）和 Phase 4（測試腳本）的 `guide_section` 值，
> **必須完全照這裡的文字複製貼上**，不能自己改寫或縮短。
>
> 字串不一致 → Phase 8 的章節分組就會出錯（例：「建立任務」≠「新增任務」）。

---

## 使用說明

1. 把這份範本複製到你的專案根目錄：`<專案根>/GUIDE_SECTIONS.md`（vendored 專案中本範本在 `.claude/workflow/GUIDE_SECTIONS.md`）
2. 填入這個專案的章節清單（依使用者操作順序排列）
3. Phase 1 和 Phase 4 從你的專案資料夾的 `GUIDE_SECTIONS.md` 複製，**不要從這份範本複製**

---

## 章節清單（依使用者操作順序排列）

| 順序 | `guide_section` 值（精確字串） | 說明 |
|---|---|---|
| 01 | `[填入章節名稱]` | [說明這個章節對應什麼功能] |
| 02 | `[填入章節名稱]` | |
| 03 | `[填入章節名稱]` | |
| 04 | `[填入章節名稱]` | |
| 05 | `[填入章節名稱]` | |

> 視專案需求增減行數，順序由小到大決定 User Guide 章節順序。

---

## 使用方式

> 🔴 `guide_section` 值一律**從上表複製精確字串，禁止改寫或縮短**；不允許在 Phase 1 / Phase 4 使用本表之外的值。

- Phase 1（Mockup HTML）：`data-guide-section="[從上表複製精確字串]"`（其餘 `data-guide-*` 欄位表見 `phase-1-product-design.md`）
- Phase 4（測試腳本 YAML）：`guide_section: "[從上表複製精確字串]"`（`guide_order` 從「順序」欄填入，數字不補零）

新增章節：先在**你的專案** `GUIDE_SECTIONS.md` 加一行（決定順序 + 精確字串），Phase 1 / Phase 4 才能使用。

---

*如果某個功能不需要出現在 User Guide，不加 `guide_section` 即可，Phase 8 不會納入。*
