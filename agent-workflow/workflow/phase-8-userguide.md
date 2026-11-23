---
phase: 8
name: User Guide 產出
executor: 模式 A＝@phase8-guide-writer｜模式 B（選配）＝依專案而定
reads_from:
  - tests/AGENT_TEST_INSTRUCTION.md（happy path 步驟 + guide_include 例外情境）
  - reports/screenshots/（Phase 6 截圖，來自測試通過的 CI artifact）
  - HTML設計稿/定案/*.html（data-guide-caption 文字）
feeds_into: 模式 A＝reports/user-guide-v{n}.docx｜模式 B＝外部問答知識庫（選配）
also_see: workflow/CONTRACTS.md（Contract A、B、C）
---

# Phase 8｜User Guide 產出

Phase 8 的預設產出是**模式 A：靜態 User Guide**——`@phase8-guide-writer` 讀 Phase 1 的 `data-guide-*`、Phase 4 的 `guide_*`、Phase 6 截圖，產出 `reports/user-guide-v{n}.docx`。結構與語言規則見 `@phase8-guide-writer` agent 定義與下方「語言規則」段。

> **模式 B：外部問答知識庫（選配，依專案而定）。** 同一批素材（步驟文字、caption、例外情境、測試通過的截圖）也可以餵給專案自選的問答工具，讓使用者用提問取代翻手冊；要不要做、怎麼建置依各專案基建而定，未包含於此 repo。素材與標記規則與模式 A 完全共用。

---

## 章節組裝規則

章節分組照 `guide_section`＋`guide_order`，每章＝操作步驟（happy path 的 `screenshot: true` 步驟）＋注意事項（`guide_include: true` 例外情境）。

### 素材來源對應

| Guide 內容 | 來源 | 原始標記 |
|----------|------|---------|
| 章節分組 | GUIDE_SECTIONS.md | `guide_section` + `guide_order` |
| 操作步驟文字 | Phase 4 happy path | `action` 欄位 |
| 步驟截圖 | Phase 6 CI artifact | `{test_id}_step{n}.png` |
| Caption 文字 | Phase 1 mockup 或 Phase 4 | `data-guide-caption` 或 `action` |
| 例外情境說明 | Phase 4 edge case | `guide_caption`（guide_include: true） |
| 例外截圖 | Phase 6 CI artifact | edge case 的 `screenshot: true` 步驟 |

### 語言規則

- 主動語態、口語化、指示句
- 禁止技術詞彙：不出現 API、DB、selector、payload、endpoint、schema
- 例外情境格式：「如果你看到 [現象]，代表 [原因]，你需要 [動作]。」

---

## 截圖來源：只取測試通過的

> ⚠ **關鍵原則：只有測試通過的截圖才能用於 User Guide。**
> 失敗的截圖代表系統有 bug，拿來當操作說明會誤導使用者。

只取測試通過（`when: on_success`）的 CI artifact；篩選與下載細節依各 Git 平台的 API 而定（未包含於此 repo）。

---

## 與其他 Phase 的關係

| Phase | 提供什麼給 Phase 8 | 怎麼提供 |
|-------|-------------------|---------|
| Phase 1 | `data-guide-caption`、`data-guide-section` | 寫在 mockup HTML 裡 |
| Phase 4 | `guide_section`、`guide_caption`、`guide_include`、`screenshot: true` | 寫在測試腳本 YAML 裡 |
| Phase 6 | 截圖 `{test_id}_step{n}.png` | 測試通過後存為 CI artifact |
| GUIDE_SECTIONS.md | 章節定義（single source of truth） | 手動維護 |

---

## Checklist

- [ ] Phase 7 人工抽測已 passed
- [ ] 每個 `guide_section` 都有對應章節，順序照 `guide_order`
- [ ] 截圖全部來自測試通過的 CI artifact
- [ ] 例外情境照語言規則改寫，無技術詞彙

**產出：** 模式 A＝`reports/user-guide-v{n}.docx`｜模式 B（選配）＝依專案而定
