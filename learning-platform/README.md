# Learning Platform — 內部教育訓練平台（LMS）

某科技公司中大型規模的內部教育訓練平台：員工上課、主管追蹤團隊進度、HR 派課與管理、講師批改作業。本 repo 為去機密後的對外版本，只保留架構與工程實務內容，不含原始碼。

## 我的角色
HR 真人負責設計畫面和規格，PM 我真人負責驅使 Claude 實作出來，並協助 Claude 串接公司內部服務並上架服務，Claude 獨立負責本專案的全端開發、架構設計、CI/CD 與測試策略

- **後端主責**：API、資料模型、權限、通知、排程等全部後端功能
- **架構設計**：BFF 分流、檔案直傳、外部系統整合邊界
- **CI/CD**：GitLab CI 多 stage 管線、fail-fast 閘門設計、K8s + Helm 部署
- **E2E 測試套件**：Playwright 套件從零建立，含「改哪跑哪」的 spec-map 機制

協作模式：與一位非技術背景的 HR 兩人協作——她負責需求與驗收，我負責從規格到上線的全部技術面。這個組合逼出了不少「規格要白話、驗收要能自己點」的工程慣例。

## 技術棧

| 層 | 技術 |
|---|---|
| 後端 | PHP 8.3 / Laravel |
| 前端 | Nuxt 4 + Vue 3 + TypeScript |
| 資料庫 | PostgreSQL 16（UUID 主鍵） |
| 快取 / Queue | Redis |
| 檔案儲存 | S3 相容物件儲存（開發用 MinIO） |
| 部署 | Kubernetes + Helm |
| CI/CD | 自建 GitLab，多 stage pipeline |

## 工程亮點

細節都在 [ARCHITECTURE.md](./ARCHITECTURE.md)，這裡是摘要：

- **[BFF 架構](./ARCHITECTURE.md#a-bff-架構nginx-依-path-分流身分走-cookie)** — Nginx 單一 server block 依 path 分流：`/api` 進 Laravel、其餘進 Nuxt SSR。身分一律走 cookie 而非 Bearer token，前端完全不碰 token 儲存，少掉一整類 XSS 竊取風險。

- **[S3 presigned 直傳/直取](./ARCHITECTURE.md#b-s3-presigned-直傳直取bytes-不經應用伺服器)** — 上傳與下載的 bytes 都不經過應用伺服器，教學影片這種大檔不會吃掉後端頻寬。object key 一律由後端產生、不信任前端，並有每週 GC 回收孤兒物件（含寬限期保護剛上傳還沒存檔的）。

- **[去原生 ENUM → varchar + CHECK](./ARCHITECTURE.md#c-去原生-enum--varchar--check)** — PostgreSQL 原生 enum 改值要 `ALTER TYPE`，維運成本高。改用 CHECK 約束後，配套測試對每個欄位釘死「約束存在、合法值全過、非法值全擋」，順帶把每一欄的驗證責任明確化。

- **[CI 三段閘門 fail-fast](./ARCHITECTURE.md#f-ci-三段閘門-fail-fast)** — `php -l` → class 載入 smoke → 全測。中間那段強制 autoload 每一個 class，專抓「載入期 fatal」——語法檢查抓不到、單元測試沒覆蓋到也踩不到的那種。這個閘門源自一次真實事故。

- **[E2E 測試套件與「改哪跑哪」](./ARCHITECTURE.md#g-e2e-套件playwright改哪跑哪)** — Playwright 數十支 spec／數百個 test，hermetic、與前端專案隔離。spec-map 由 git diff 靜態算出該跑哪些 spec，含 fail-safe（算不出來就全跑）與 stale 檢查（被刪改的 `data-testid` 還有誰引用）。

- **[i18n runtime 字串同步](./ARCHITECTURE.md#e-i18n-runtime-字串同步)** — 文案存 DB，前端啟動或切語系時拉 API 蓋在打包後備字串上；字串服務或 DB 掛掉都退回打包字串，絕不白畫面。

- **[安全紅線](./ARCHITECTURE.md#i-安全紅線)** — 完課判定在後端（前端只送事件）、每個 endpoint 再驗角色不靠藏按鈕、重要操作留 audit log、不自建密碼體系。

## 規模數據

| 項目 | 數量 |
|---|---|
| Database migration | 數十支 |
| 後端測試 | 上千個 tests |
| Playwright E2E | 數十支 spec／數百個 tests |
| 使用規模 | 中大型企業規模（以影片心跳為主要負載模型做過容量估算） |
