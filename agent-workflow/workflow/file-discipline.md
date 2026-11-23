---
type: 全局規則
scope: 所有專案的開發／文件工作（vendored 專案經 `.claude/workflow/` 自帶本檔）
applies_to:
  - Phase 5 開發實作（Flow A / Flow B）
  - 任何直接改 code / docs 的 Claude session
---

# 檔案紀律準則（file-discipline）

> **要防什麼**：repo 檔案「每次只多一點點」地變多、變大，直到需要一次大掃除。
> 這類債沒有一筆是一次造成的。
> **專案 override**：警戒線數字是預設值，專案可在自己的 CLAUDE.md 調整；**「棘輪」與「新檔必接線」兩條原則不可拿掉**。

## 四條原則

1. **Edit 優先，不開新檔**：寫任何內容前先問「這屬於哪個既有檔的哪一段」。合法新檔只有四種：程式結構需要（新頁面／元件／service／測試）、提案（執行完歸檔）、runbook、PM 明確指示。新 docs 檔＝**同一 commit** 進專案的文件索引（CLAUDE.md 文件表之類）——沒被索引到的檔案，下個 session 等於讀不到。
2. **警戒線＋棘輪**：新檔一律必須在警戒線內；既有超線檔＝已知債，**只能變小、不能變大**——要加的功能會讓它更長，就先拆再加（拆與加分開 commit）。預設警戒線：前端單檔（頁面／元件）**400 行**、狀態 store **300 行**、後端 service **500 行**、docs 單檔 **800 行**。大檔的代價：session 整檔載入燒 token、誤傷面大、測試影響面判定變寬。
3. **新檔必接線**：新檔案在同一個 commit 接上它所有的索引／地圖——測試觸發地圖、元件清單、API 文件回填、docs 索引、`.gitignore`（新產物型態）。不留孤兒。
4. **一次性內容不落地**：報告類寫進 MR description 或對話回報，不進 docs/ 根；提案檔標狀態、執行完同 MR 歸檔；工件（測試輸出、批次產物、截圖）不進版控。

## 拆大檔鐵則（觸線要拆時）

- **拆分 commit＝純搬家**：不改邏輯、文案、i18n key、樣式、`data-testid`；diff 接近「剪下貼上＋import」。想順手修的東西記下來回報，不混進來。
- **狀態留集中 store**：子元件自己取用 store，props 只傳最小資訊；不要複製 store 資料成本地狀態、不要整包物件轉發。
- **安全敏感邏輯整段留母層**：搬「引擎」不搬「判定」。
- **每步一 commit＋獨立驗證**（lint → build → 對應測試）。

## 機械化（強烈建議每專案照抄）

紀律不能只靠模型自律——可機檢的部分寫成 **0-token 腳本＋CI warn-only job**：

- 建議實作：一支 `file-discipline.sh`（三檢：新檔超線／超線檔又變大／新 docs 沒進索引；棘輪設計只看本次 diff、不追溯舊債）＋ CI 的 `file-discipline` job（每條 MR 自動跑、不擋 merge、review 看得到黃燈）。（工具腳本未包含於此 repo）
- 移植方式：複製腳本、改警戒線 glob 與索引檔路徑即可，純 bash＋git 零依賴。中文檔名記得 `git -c core.quotepath=off`。
