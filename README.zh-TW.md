# 內部系統作品集

[English](README.md) · **繁體中文**

這裡收錄我在某科技公司擔任 PM 期間，透過 Claude 進行 Vibe Coding 產出的兩套內部系統的**架構說明與設計決策**，以及我和 Claude 協作時用的**規格驅動工作流（方法論）**。
- 教育訓練平台（Learning Platform）：公司 HR 擔任 PM 進行畫面設計和規格決策，我本人和 Claude 合作把網站建置起來，並串接公司內部服務，技術結構由 Claude 負責
- 內部需求管理平台（Internal Request Hub）：我本人只描述痛點和期望的規格，其他技術結構與畫面設計均由 Claude 負責
- Agent Workflow：上面兩套系統背後的做事方法，從規格討論、拍板、寫入、稽核，一路到測試與 User Guide，每一步由哪個 agent、用哪個模型負責；另附可直接裝的 SPEC CI 檢查、版本分支同步腳本與寫程式的驗證流程

基於保密義務，這裡不包含原始碼與任何內部資訊；所有系統名稱、整合對象均已改為中性代稱，數據做過模糊化處理；工作流裡的範例一律改用虛構的「待辦清單 App」重寫。重點放在：**系統怎麼設計、為什麼這樣設計、工程品質怎麼守住**。

## 從哪裡開始看

1. **本頁**：兩套系統是什麼、我的角色。
2. **系統設計**：[`learning-platform/ARCHITECTURE.md`](learning-platform/ARCHITECTURE.md)、[`internal-request-hub/ARCHITECTURE.md`](internal-request-hub/ARCHITECTURE.md)。
3. **方法論**：[`agent-workflow/README.zh-TW.md`](agent-workflow/README.zh-TW.md)。

## 專案一覽

| 專案 | 一句話 | 技術棧 | 我的角色 |
|---|---|---|---|
| [Learning Platform](learning-platform/) | 中大型規模的公司內部教育訓練平台（LMS） | Laravel + Nuxt/Vue 3 + PostgreSQL + K8s | 依 HR 的規格和 Claude 一起建置：串接內部服務、CI/CD、E2E 測試套件；技術結構由 Claude 負責 |
| [Internal Request Hub](internal-request-hub/) | 跨單位需求從許願到結案的生命週期管理平台 | FastAPI + htmx + SQLite | PM：描述痛點、訂規格與驗收；驅動 Claude 完成實作、CI/CD 與上線；技術結構與畫面設計由 Claude 負責 |
| [Agent Workflow](agent-workflow/) | PM 用 Claude Code 從零設計系統的規格驅動工作流：人決策，AI 執行與稽核 | Claude Code subagents（12 個）＋ 規則書＋ Python CI 檢查（GitLab CI） | 方法論設計、agent 定義、流程維護 |

兩個系統專案的資料夾內各有兩份文件：

- **README.md** — 系統定位、技術棧、工程亮點摘要
- **ARCHITECTURE.md** — 架構圖（Mermaid）、資料流、每個設計決策的「遇到什麼問題 → 怎麼解」

`agent-workflow/` 內容：

| 資料夾 | 內容 | 數量 | 語言 |
|---|---|---|---|
| [`workflow/`](agent-workflow/workflow/) | 工作流規則書（入口路由、地基軌、Phase 0–8、跨階段規則） | 20 份規則書＋1 份索引 README | 繁體中文（索引為中英雙語） |
| [`agents-setup/`](agent-workflow/agents-setup/) | Claude Code subagent 定義 | 12 個 | 繁體中文 |
| [`commands/`](agent-workflow/commands/) | `/spec-change` slash command | 1 個 | 繁體中文 |
| [`skills/`](agent-workflow/skills/) | skill（verify、scenario-expansion、task-breakdown） | 3 個 | 繁體中文 |
| [`recipes/`](agent-workflow/recipes/) | [SPEC CI 檢查](agent-workflow/recipes/spec-ci-gates.md)（9 項）、[SPEC 版本分支](agent-workflow/recipes/spec-version-branches.md)，皆附腳本、CI 片段與測試 | 2 份配方 | 繁體中文 |

所有文件、agent、指令與 skill 皆以繁體中文撰寫；只有 README 有中英兩版。

## 兩套系統的共同工程理念

- **測試當守門員，不是裝飾**：合併前全套測試必綠；另外自建「改哪跑哪」的影響面地圖，用 git diff 靜態算出該跑哪些測試，沒命中就 fail-safe 跑全套。
- **單一真相源**：能派生的就不重複儲存，避免雙寫不一致。
- **失敗要降級，不要擴散**：通知、AI、外部整合都是 best-effort，掛掉不能拖垮主流程。
- **維運自曝**：同步健康度、錯誤直接顯示在管理介面，不必翻 log。
