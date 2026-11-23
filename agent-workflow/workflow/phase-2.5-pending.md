---
phase: 2.5
name: 待確認規格清單
executor: Claude 整理，你（PM）補齊
reads_from: dev-spec/CLAUDE_DEV_INSTRUCTION.md（Phase 2 產出）
feeds_into: workflow/phase-5-dev.md（mock 替代）
also_see: workflow/CONTRACTS.md（Contract E）
---

# Phase 2.5｜待確認規格清單（PENDING_SPEC）

> 規格撰寫過程中，一定有項目「還沒確認」但不應該讓整個開發卡死。
> Phase 2.5 把這些項目集中管理，並為每一項提供「暫定 mock 值」，
> 讓 Phase 5 的開發不被阻擋，等你補齊後再替換。

---

## PENDING_SPEC.md 的結構

每個待確認項目必須包含以下四個欄位：

```markdown
### P0-1：[項目名稱]
**負責確認：** [人名 + 角色]
**問題：** [具體要確認什麼，列出問題點]
**暫定 Mock 值：** [Phase 5 先用這個，標記 TODO]
**確認狀態：** ⬜ 待確認 → ✅ 已確認（填入確認日期與結果）
```

---

## 三層優先級

### P0 Critical — 沒有這個無法建立 DB 或啟動後端

**開發啟動的前置條件**：P0 全部確認後，`dev-spec/CLAUDE_DEV_INSTRUCTION.md` 才能標記 `status: locked`，Phase 5 的真實 API 串接才能開始。例：外部系統 API 的 endpoint URL + 認證方式。

---

### P1 Important — 特定功能無法完整運作

不阻擋整體開發，但某個功能的關鍵行為無法完整實作。例：時限規則（「任務到期後幾天自動標為逾期」）。

---

### P2 Nice-to-have — 不影響核心開發

可在上線前補充，不影響主要功能測試。例：Email 模板視覺設計（HTML 樣式）。

---

## Phase 5 的處理規則

處理規則照 `phase-5-dev.md` §PENDING 項目的處理規則（權威）。各層對應的 mock 策略：

- P0 未確認 → 用 mock server 替代，整個功能先做前端 UI
- P1 未確認 → 用暫定值替代，用 `.env` 或 config 管理，方便日後替換
- P2 未確認 → 直接跳過或顯示「coming soon」

---

## Checklist（鎖版前確認）

- [ ] 所有 P0 項目已確認（才能 locked Phase 2 進入真實串接）
- [ ] 所有 P1 項目已有暫定 mock 值（Phase 5 可先跑）
- [ ] 每個項目都有「負責確認的人」

**產出：** `dev-spec/PENDING_SPEC.md`
