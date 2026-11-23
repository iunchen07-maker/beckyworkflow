# 跨階段輸入輸出契約（Phase Contracts）

> 本文件是整套工作流程的「膠水」。
> 當你要執行某個 Phase 時，先查這裡確認：你需要什麼輸入、你要產出什麼、哪個 Phase 會用你的產出。
> 每個 Phase 文件頂部也有對應的 `reads_from` / `feeds_into` 標記與本文件一致。

---

## 一覽表

| 產出物 | 由誰產出 | 被誰消費 | 格式規範 |
|---|---|---|---|
| `dev-spec/product-spec.md` | Phase 1（PM） | Phase 2（技術推導）、Phase 4（驗收基礎） | User Story 格式，含角色 / 前置條件 / 成功條件 / 例外條件 |
| `HTML設計稿/定案/*.html` | Phase 1（PM） | Phase 4（selector）、Phase 5（UI 參考）、Phase 8（caption） | data-action + data-guide-*，見 phase-1-product-design.md |
| `dev-spec/CLAUDE_DEV_INSTRUCTION.md` | Phase 2（工程師） | Phase 5 | 見 phase-2-spec.md |
| `dev-spec/PENDING_SPEC.md` | Phase 2.5 | Phase 5（mock 替代）、PM（補齊後解鎖） | 見 phase-2.5-pending.md |
| `GUIDE_SECTIONS.md`（專案資料夾） | Phase 0（或 Phase 1 前） | Phase 1、Phase 4、Phase 8 | chapter 名稱唯一來源，見 GUIDE_SECTIONS.md |
| `tests/AGENT_TEST_INSTRUCTION.md` | Phase 4（PM → Claude 轉換） | Phase 6（執行）、Phase 8（步驟文字 + 截圖清單） | 見 phase-4-tests.md |
| `engineer-prompt.md`（Flow B 選用） | Phase 4 收尾（PM＋Claude 彙整） | Phase 5 Flow B（工程師的 Claude） | Section A 指令 + Section B BASE_URL + Appendix selector 對照表，見 phase-5-dev.md |
| `reports/screenshots/{test_id}_step{n}.png` | Phase 6 | Phase 8、CI artifact | 命名格式：`{test_id}_step{step}.png`，例：`T1-1-HP_step2.png`；同時存為 CI artifact 供自動化流水線下載 |
| `reports/report-{date}.md` | Phase 6 | Phase 7（抽測依據） | 測試通過 / 失敗清單 |
| `reports/user-guide-v{n}.docx` | Phase 8 模式 A（@phase8-guide-writer） | 一般用戶（終端使用者） | Word 操作手冊，見 phase-8-userguide.md |
| 外部問答知識庫素材（選配） | Phase 8 模式 B（依專案而定） | 專案自選的問答工具 | 與模式 A 共用素材，見 phase-8-userguide.md |
| `Spec/Progress_Tracker.md` | foundation-track 地基軌（PM+Claude 討論） | session 冷啟動定位、Phase 0 impact-scanner（只當進度與指路；定案事實＝SPEC＋`Spec/memory/` 決策檔） | 北極星 md，7 層進度 + exit criteria 勾選（附決策檔 id）；殘留的拍板紀錄段是凍結索引，見 foundation-track.md |
| 入口路由標號（R1–R5 / 4 例外） | `entry-routing.md`（vendored 單一真相） | foundation-track.md（R5/例外①）、phase-0-spec-update.md（R3/R4）、workspace CLAUDE.md（指標） | 三軸判定表，見 entry-routing.md |

---

## 詳細契約

### Contract A：Phase 1 Mockup → Phase 8 User Guide

- **契約：** Phase 1 在 mockup HTML 每個要進 User Guide 的畫面區塊埋 `data-guide-order` / `data-guide-section` / `data-guide-step` / `data-guide-caption`（section 值從 `GUIDE_SECTIONS.md` 複製）；Phase 8 按 section 分組讀取，作為 User Guide 截圖 caption 的預設文字。
- **斷了會怎樣：** Phase 8 拿不到 caption 素材、User Guide 章節分組失效。
- **欄位表見：** `phase-1-product-design.md` §「`data-guide-*`（給 Phase 8 User Guide 用）」。

> **注意：** Phase 1 Mockup 驗收（在瀏覽器確認設計稿）發生在 Phase 1 鎖版前，不是 Phase 6。Phase 6 是功能驗收（真實 DOM + 真實資料）。

---

### Contract B：Phase 4 測試腳本 → Phase 8 User Guide

- **契約：** Happy Path 提供 `guide_section`＋一般用戶語言的步驟 `action`＋`screenshot` 標記；用戶可見的例外情境加 `guide_include: true`／`guide_type`／`guide_caption`。Phase 8 依 `guide_section` 分組產出操作步驟與「注意事項」區塊。
- **斷了會怎樣：** User Guide 缺步驟文字與例外說明素材。
- **欄位表見：** `phase-4-tests.md` §「Happy Path 格式」＋§「Edge Case / Error 格式」。

---

### Contract C：Phase 6 截圖 → Phase 8 User Guide

- **契約：** 所有 `screenshot: true` 的步驟自動截圖存入 `reports/screenshots/`，命名 `{test_id}_step{step}.png`（例：`T1-1-HP_step2.png`）；同時存為 CI artifact（僅成功時保存），Phase 8 只取測試通過的截圖（失敗截圖＝bug 狀態，不入 User Guide）。Phase 8 依 test_id＋step 把截圖嵌入對應操作步驟旁。
- **斷了會怎樣：** Phase 8 無法把截圖對應到操作步驟，User Guide 缺圖或用到 bug 畫面。
- 命名格式字串以本條為唯一權威（phase-6 / phase-8 引用此處）。

---

### Contract D：Phase 2 → Phase 5 Claude Code

**Phase 2（工程師）從 Phase 1 產出（product-spec.md + HTML設計稿/定案/*.html）推導，必須提供六項（缺一 Claude Code 會卡住；與 phase-2-spec.md 的「必須產出的六項」一致）：**
1. 功能規格（從 product-spec + mockup 整理的可執行功能敘述）
2. 資料模型（完整 DB schema，含欄位名稱 + 型態）
3. API endpoint 完整 list（含 request/response schema 範例）
4. 狀態機（所有合法狀態值 + 轉換條件）
5. 演算法實作（可執行的 pseudo code 或實際語言）
6. 專案資料夾結構

**Phase 5 讀取：** `dev-spec/CLAUDE_DEV_INSTRUCTION.md`

---

### Contract E：Phase 2.5 → Phase 5（Mock 處理）

**Phase 2.5 必須提供：**
- P0 / P1 / P2 分層的待確認項目
- 每個項目的**暫定 Mock 值**（讓 Phase 5 不被卡住）

**Phase 5 處理方式：** 遇到 PENDING 項目先用 mock 替代，並在 code 中加 `// TODO: replace after PENDING_SPEC P0-X confirmed` 標記。**TODO 標記格式以本條為唯一權威**（其他規則書／agent 只引用「照 Contract E」，不再重複格式字串）。

---

### Contract F：Phase 1 data-action → Phase 5 真實 DOM

- **契約：** mockup 定義的 `data-action` 是 Phase 4 驗收腳本 selector 的唯一來源；Phase 5 真實 DOM 必須原值保留 `data-action` 與 `data-testid`，不因重構／改名／組件化移除或更名（前端框架的 class / id / ref 可自由定義）。
- **斷了會怎樣：** Phase 6 的自動驗收腳本全部 selector 失效，需要重新對應。
- **屬性規則見：** `phase-1-product-design.md` §「📐 標注鐵則」第 2 條（`data-spec`＋`data-testid`＋`data-action` 三屬性）。
