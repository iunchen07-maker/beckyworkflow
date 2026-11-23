# Internal Request Hub — 內部需求管理平台

> 把「跨單位需求」從許願、評估、開發到結案的完整生命週期，收進一個平台管理。

某科技公司內部，各行政單位對開發團隊的需求原本散落在即時通訊、口頭交辦與各自的表格裡：需求方不知道自己的許願到哪一關了，開發方（PM／工程師）則要在多個工具之間手動搬運資訊。Internal Request Hub 解決的就是這件事——**需求方在一個入口許願、追蹤進度；PM 在同一個入口評估、產出工單草稿、一鍵開到自建 GitLab；之後的開發狀態不再人工回填，直接從 GitLab 派生顯示。**

## 我的角色
我以 PM 身分描述痛點、期望流程與規格，並負責驗收；技術結構（全端開發、架構設計、CI/CD 與測試策略）與畫面設計由 Claude 負責，我驅動 Claude 一路實作到上線。Claude 負責的範圍包括：

- 後端 API 與領域邏輯、前端頁面（htmx + Jinja2）
- 與自建 GitLab、企業 IM、S3、NotebookLM 的整合層
- CI pipeline 設計（含「改哪跑哪」影響地圖）與測試分層
- 排程、備份、監控等維運機制

## 技術棧

| 層面 | 技術 | 備註 |
|---|---|---|
| 後端 | Python / FastAPI | 單一服務，無微服務拆分 |
| 前端 | htmx + Jinja2 server-side rendering | 不引入前端框架與 build chain |
| 資料庫 | SQLite | 同時兼任通知佇列（見亮點） |
| 排程 | cron jobs | 同步、通知派送、備份、探活 |
| 外部整合 | 自建 GitLab API、企業 IM webhook、S3、NotebookLM | 全部收在獨立的整合封裝層 |
| 測試 | unit 測試 + E2E 測試，共數十個測試檔 | 領域層可完全離線測試 |
| CI/CD | 自建 GitLab CI | main protected、一律走 MR |

## 工程亮點

以下每一項在 [ARCHITECTURE.md](ARCHITECTURE.md) 都有對應章節，含「遇到什麼問題、為什麼這樣解」的完整脈絡。

- **Deterministic 為主、AI 為輔** — 工單草稿預設走純機械組裝、零 AI 呼叫，結果可預期、可重現；只有設定了 NotebookLM 知識庫的系統，才在 PM 手動觸發時呼叫一次 LLM，且失敗自動降級、不阻塞主流程。AI 是加值選項，不是單點故障。

- **後段不存狀態，GitLab 是單一真相源** — 需求進入開發階段後，平台不維護自己的一份狀態，只存快照、顯示時即時派生。從根本上消滅「兩邊狀態對不上」這類雙寫不一致問題。

- **無 broker 的通知佇列** — 用一張 DB table 當佇列（`sent_at IS NULL` 即待送），cron 定期消化。以內部平台的流量規模，省掉 Redis/Celery 一整套 broker 的部署與運維成本。

- **純函式領域層** — chatbot 狀態機、草稿組裝、狀態派生等核心邏輯刻意不 import ORM、不碰 DB、不碰 HTTP，可以完全離線做單元測試，測試又快又穩。

- **「隱形契約」測試** — htmx/Jinja 這種無型別架構最怕「改 A 靜默壞 B」。把四類跨檔契約（template URL ↔ route、HX-Trigger 事件字串、跨 template DOM id、狀態 class ↔ CSS）明文寫成測試，讓編譯器抓不到的斷裂在 CI 就爆出來。

- **「改哪跑哪」影響地圖** — 用 git diff × source→test 對映算出這次改動該跑哪些測試；對映未命中時 fail-safe 跑全套、並點名要求補地圖。速度與安全兩頭都顧。

- **維運自曝** — 同步健康度寫回 DB、直接顯示在設定頁；watchdog 探活自動拉起；每日產出去識別化備份（備份包不含任何 key/token）。系統自己說出「我現在健不健康」。

## 規模

- 萬行級的 **Python** 程式碼
- 數十個測試檔（unit + E2E）
- 一位 PM（我）＋ Claude 完成開發與維運

## 文件

- [ARCHITECTURE.md](ARCHITECTURE.md) — 系統架構圖、資料流、分層說明與九項設計決策的完整說明
