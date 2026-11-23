---
phase: 6
name: 自動測試 → Bug 修復迴圈
executor: Claude（Bash 驅動 Playwright，或 Cowork computer-use）
reads_from: tests/AGENT_TEST_INSTRUCTION.md
feeds_into:
  - workflow/phase-7-review.md（測試報告）
  - workflow/phase-8-userguide.md（截圖 → User Guide）
  - CI artifact（截圖，供自動化流水線下載）
also_see: workflow/CONTRACTS.md（Contract C）
---

> 🔍 **驗證總則**：跑測試與看截圖照 [`verification.md`](verification.md)——不穩的測試不准靠重跑變綠、截圖用一般視窗大小且要有人對照預期看過、漏網 bug 變規則。


# Phase 6｜自動測試 → Bug 修復迴圈

---

## 執行方式選擇

執行方式只有一途：**Claude 直接驅動瀏覽器（Bash + Playwright）**。
Claude 直接讀 `AGENT_TEST_INSTRUCTION.md`，操作瀏覽器跑測試，截圖以固定命名存檔。依執行環境有兩種載體，流程與產出完全相同：

| 載體 | 適用環境 |
|---|---|
| **A1：Bash 驅動 Playwright**（等瀏覽器自動化） | Claude Code / `@phase6-test-runner` agent（agent 無 computer-use 工具，一律走這條） |
| **A2：Cowork computer-use** | Claude Cowork 主 session |

**優點：**
- 截圖命名 `{test_id}_step{n}.png` 由 Claude 控制，Phase 8 自動對應可靠
- 不依賴第三方工具的 YAML 解析能力
- Claude 可邊跑測試邊判斷、邊修 Bug

**執行指令範本：**
```
請讀取 tests/AGENT_TEST_INSTRUCTION.md，
依序執行所有 test case。
- 對每個 screenshot: true 的步驟，截圖後存入 reports/screenshots/，
  命名格式：{test_id}_step{step}.png（例：T1-1-HP_step2.png）
- 每個 Suite 跑完後記錄通過 / 失敗
- 全部完成後產出 reports/report-{YYYY-MM-DD}.md
- 發現 Bug 時標記並繼續，全部跑完後再彙整修復
```

---

## 流程

```
Deploy 完成（測試站可連線）
  ↓
執行 tests/AGENT_TEST_INSTRUCTION.md 中所有 test case
  （TC 帶 manual: true → 不執行、不算失敗，報告歸類「manual 待驗」；欄位定義見 phase-4-tests.md「TC 展開技法」節）
  ↓
截圖存入 reports/screenshots/{test_id}_step{n}.png
  ↓
產生測試報告 reports/report-{date}.md
  ↓
發現 Bug？
  Yes → Claude Code 自動修復 → 重跑失敗的 test case
  No  → 通知你「可以抽測了（Phase 7）」
```

---

## 截圖命名規則（Phase 8 強依賴）

```
reports/screenshots/{test_id}_step{step}.png

✅ 正確：T1-1-HP_step2.png、T1-3-EC_step1.png
❌ 錯誤：screenshot_001.png、T1-1-HP.png（缺 step 編號）
```

同時截 happy path 正常狀態和 edge case 例外狀態——這些是 User Guide 的原始素材。

---

## 截圖存為 CI Artifact（自動化流水線用）

截圖存 CI artifact（test stage、`when: on_success`——只有測試通過的截圖才代表正確的系統行為）。
CI 設定範本與 artifact 消費流程依各專案的 CI 平台而定（流水線細節未包含於此 repo）。

---

## 測試報告格式

```markdown
# Test Report — {YYYY-MM-DD}

## 執行方式
Bash 驅動 Playwright

## 總結
- 通過：X 項 / 失敗：X 項 / 跳過：X 項 / manual 待驗：X 項

## 失敗清單
| Suite | Test ID | 步驟 | 失敗原因 | Selector |
|---|---|---|---|---|

## manual 待驗清單
| Test ID | 名稱 | us | 說明 |
|---|---|---|---|

> 這張清單直接交 Phase 7 當人工抽測項目，人照 TC 步驟走。

## 截圖清單
| 檔名 | Test ID | 步驟 | 說明 |
|---|---|---|---|
| T1-1-HP_step1.png | T1-1-HP | 1 | 點擊新增任務按鈕 |

## 截圖存放路徑
reports/screenshots/ — 共 X 張
```

---

## Checklist（進入 Phase 7 前）

- [ ] 所有 Happy Path 測試通過
- [ ] 測試報告已存入 `reports/`
- [ ] 截圖已存入 `reports/screenshots/`，命名符合 `{test_id}_step{n}.png`
- [ ] 對照 Phase 4 的 `screenshot: true` 清單，確認截圖數量一致
- [ ] 失敗項目已記錄（可接受的已知問題需說明原因）
- [ ] CI 已設定截圖 artifact（`when: on_success`）
- [ ] 確認 artifact 可透過 Git 平台的 API 下載
