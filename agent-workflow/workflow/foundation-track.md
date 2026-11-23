---
type: 前段方法論（立地基）
scope: 全新 greenfield 專案的地基軌；老專案 grandfather
applies_to: PM + Claude 討論主體
reads_from:
  - Spec/Progress_Tracker.md（北極星：地基軌進度 + exit criteria 勾選 + 接縫層宣告；拍板全史在 Spec/memory/ 決策檔）
  - Spec/Decision_Principles.md（該專案 domain 專屬的 exit criteria 與紅線）
feeds_into:
  - workflow/phase-0-spec-update.md（每層 gate 呼叫一次 Phase 0 交易）
also_see: workflow/CONTRACTS.md（產出物一覽）
---

# 地基軌（Foundation Track）｜前段方法論

> **你的角色（PM）：** 逐層拍板地基決策、每層過 gate 前簽 OK
> **Claude 的角色：** 陪你逐層推敲、守住「先上後下」的討論紀律、每層 gate 時呼叫 Phase 0 引擎把決策寫入
>
> 這是 **Phase 1 更前面**的一段：全新專案在畫任何 mockup、寫任何功能 SPEC 之前，要先把「地基」（vision / scope / entities / 權限）逐層拍清楚。地基軌就是這段的規則書。

---

## §1 什麼是地基軌？為什麼跟 Phase 0~8 分開？

整套工作流**不是單一線性順序**，而是**三條軸**互相「呼叫」：

- **軸 A｜地基軌（Foundation Track）＝ 7 層決策議程**
  L0 Vision → L1 Scope → L2 Entities → L3 Permission →〔接縫〕→ L4 Process → L5 UI → L6 Tech。
  **每專案一條、可增量重開**（不是 one-shot 做完就丟）。它是「**議程**」不是「**工序**」——刻意**不編 phase 號**，因為它是「該按什麼順序把決策拍下來」的清單，不是「該按什麼順序生出檔案」。
  每一層過 gate ＝ **呼叫一次軸 B 交易**（把該層拍板結論寫進 SPEC）。

- **軸 B｜決策寫入引擎 ＝ Phase 0**
  討論 → impact-scan → PM 拍板 → write → verify → drift-scan → Path A/B commit。
  三種情境（新專案地基 gate／既有專案新功能／改既有規格）**全走這裡**，差別只是參數（規模、動作）。詳見 [`phase-0-spec-update.md`](./phase-0-spec-update.md)。

- **軸 C｜Artifact 工序 ＝ Phase 1~8**
  mockup → tech-spec → test → dev → 測試 → guide。**按需組裝**：只重跑「上游已變、產出過期」的工序。

**三軸關係圖：**

```
   軸 A｜地基軌（Foundation Track）＝ 7 層決策議程（議程，非工序，不編 phase 號）
   ┌──────────────────────────────────────────────────────────────────────┐
   │  L0 Vision → L1 Scope → L2 Entities → L3 Permission                    │
   │                                        └──〔接縫〕── L4 Process → L5 UI → L6 Tech
   └──────────┬──────────────────────────────────────────────┬────────────┘
              │ 每層 gate 呼叫一次 ↓          接縫後逐功能各呼叫一次 ↓
              ▼
   軸 B｜決策寫入引擎（＝ Phase 0）
   ┌──────────────────────────────────────────────────────────────────────┐
   │  討論 → impact-scan → PM 拍板 → write → verify → drift-scan → Path A/B │
   └──────────┬───────────────────────────────────────────────────────────┘
              │ Path B／逐功能期回呼 ↓
              ▼
   軸 C｜Artifact 工序（＝ Phase 1~8）
   ┌──────────────────────────────────────────────────────────────────────┐
   │  Phase 1 → 2/4 → 2.5 → 5 → 6 → 7 → 8   （按需組裝，只跑上游已變的子集）  │
   └──────────────────────────────────────────────────────────────────────┘
```

**為什麼分開？** 地基層的決策**不可逆性高、改錯成本大**（見 §2），它需要的是「先上後下、逐層拍清楚」的**討論紀律**，不是「生 mockup / 寫測試」的**產出流水線**。把議程（軸 A）跟工序（軸 C）混成一條線，就會在還沒定 entity 時就去畫 UI、上層一改下層全 rework。地基軌把「討論議程」正式化成一條可追蹤的軌道，工序（Phase 1~8）留給接縫之後的逐功能期。

> **地基期零工序**：走 L0→接縫這段時，軸 C（Phase 1~8）**完全不啟動**——不畫 mockup、不寫測試。每層只做一件事：討論 → 過 gate（呼叫一次 Phase 0 把結論寫進 SPEC）。接縫之後才逐功能展開全鏈。

---

## §2 7 層定義（通用版）

> 適用**任何 spec-driven 專案**。核心原則：**越上層的決策決定越下層的設計空間**——先上後下，否則下層做完、上層一改就 rework。

| Layer | 名稱 | 不可逆性 | 改錯成本 |
|---|---|---|---|
| **L0** | Vision（願景 / 使用者 / 痛點 / 成功定義 / 邊界） | 🔴 完全不可逆 | 全砍重做 |
| **L1** | Scope & 邊界（範圍 / 真相源 / migration / 系統邊界） | 🔴 不可逆 | Migration 災難 |
| **L2** | Core Entities & Domain Model（entity / 關係 / identity / Glossary） | 🟠 半不可逆 | Schema migration |
| **L3** | Identity & Permission（角色 / 權限模型 / 欄位敏感度） | 🟠 半不可逆 | 大量 refactor |
| **L4** | Process（業務流程 / 狀態機 / 審核流） | 🟡 可調 | 流程 rework |
| **L5** | UI patterns（畫面 / 互動 / 元件） | 🟢 可 iterate | UI rework |
| **L6** | Technical 實作（DB / API / 排程 / 效能） | 🟢 可改 | 技術 refactor |

**套用規則：**

- **依賴向下流**：L_N 的決策界定 L_(N+1) 的設計空間；不可逆的上層先做、做最嚴格。
- **完成定義要明確**：每層有自訂的 **exit criteria**，全打勾才能往下（見 §3、§4）。
- **不可逆優先**：L0/L1 改錯全砍重做，必須最先做最嚴格；L5/L6 可 iterate，主流程先過即可。

> **為什麼 7 層？** 各層獨立可決定、合起來涵蓋「為什麼做→怎麼做」完整光譜；地基期的層要精實——寧可慢，不走回頭路。

---

## §3 每層 exit criteria（placeholder 模板）

> **每層的 exit criteria 由各專案自訂、打勾才過。** 本檔只給**通用格式**；不列 domain 專屬條目——那些是各專案自己的事。

**通用格式（寫在該專案 `Spec/Progress_Tracker.md` 的每層 section 內）：**

```
### Exit criteria（N 條）
- [ ] <這一層必須拍板的第一個決策問題>  → （拍板後填結論摘要 + 決策檔 id）
- [ ] <第二個決策問題>
- [ ] ...
```

**自訂原則：**

- 每條 = 「**這一層不拍清楚、下層就會做錯**」的決策問題（例：L0「主要使用者是誰」、L2「entity 清單與關係」）。
- 一律用 `- [ ]`／`- [x]`，**打勾才算過**；跳過要附理由。
- 條數不固定，由該層需要拍板的決策量決定。

---

## §4 Layer gate 協定（過層條件）

每一層要進下一層，**三條件缺一不可**：

1. **exit criteria 全勾** — 該層 `Spec/Progress_Tracker.md` 內自訂的 exit criteria 全部 `[x]`（跳過要附理由）。
2. **呼叫 `phase0-impact-scanner` 掃已拍板事實** — 跨 doc 掃描本層拍板結論與既有條文有無衝突／連動（已定案事實＝SPEC 正本＋專案 `Spec/memory/` 的 active 決策檔；Tracker 只是進度與指路，其中殘留的拍板紀錄段／舊 `拍板紀錄` 檔是凍結索引，不當定案來源）。強連動全部納入定案、弱連動逐項由 PM 裁。
3. **PM 簽 OK** — PM 看完 scanner 結果，最終確認「本層過 gate」，才進下一層。

> 每次過 gate 的三條件狀態記在 Tracker 該層 section 標題旁（格式例：「L3 — ✅ 完成（N/N exit + scanner X 強/Y 弱無致命 + PM 簽 OK）」）。
>
> **每層 gate ＝ 一筆 Phase 0 交易**：exit criteria 拍完後，該層的拍板結論由軸 B（Phase 0）的 write/verify 寫進 SPEC——地基期通常走 Path A（純文字），因為地基期零工序、沒有 mockup 要連動。

---

## §5 接縫規則（地基期 → 逐功能期）

**接縫層 = 地基軌轉入逐功能 Phase 0~8 的那一層。** 接縫之前（含）是地基期、逐層 gate、零工序；接縫之後每個功能各自走一輪 Phase 0~8。

- **各專案在自己的 `Spec/Progress_Tracker.md` 頂部宣告接縫層**（哪一層之後轉逐功能）。這是新專案開軌時**要問 PM 一次、寫進 Tracker 頂部**的決定（與 §6 的「地基層重開」同屬 PM 議程權，不由 Claude 自決）。
- **例：接縫 = L3 之後**：地基（L0–L3）鎖定後，從 L4 Process 起逐功能走 vendored Phase 0~8（[task-breakdown](../skills/task-breakdown/SKILL.md) 拆 to-do → [scenario-expansion](../skills/scenario-expansion/SKILL.md) 展情境 → Phase 0 寫 SPEC → Phase 1 mockup → …）。
- 接縫層放哪由專案性質決定（entity/權限重的系統多半放 L3 後；流程輕的可能更早）——**沒有通用固定值**，開軌時 PM 拍。

---

## §6 地基層可增量重開

**地基軌不是 one-shot。** 已過 gate 的層，之後仍可**增量重開**：

- **重開 = 該層一筆 Phase 0 交易**：把重開後的新結論走軸 B（討論 → impact-scan → 拍板 → write → verify → commit）寫回 SPEC，並更新 Tracker 該層 section。
- **何時重開由 PM 裁**：對應入口路由的 **R5** 與**必問 PM 的例外 ①**（路由表定義見 [`entry-routing.md`](./entry-routing.md)）——改動觸及地基物件（Glossary 既有名詞重定義／entity·domain 增刪／權限模型結構改動／persona 增刪／L1 邊界翻案）時**停下來問 PM**：是重開 L{n} gate 增量修，還是當功能級 patch？
- 重開一層可能連帶影響下層（依賴向下流）——impact-scanner 會掃出連動，PM 決定要不要連帶重開下層。

---

## §7 討論紀律：anti-pattern + session ritual（通用版）

### 7 個 anti-pattern（歪樓行為）

| # | Anti-pattern | 該做的事 |
|---|---|---|
| 1 | **跳到實作細節** | 「這是 L5/L6 細節，先處理當前 L_N」 |
| 2 | **跳到 UI 妄想** | 「先別畫 UI，回到當前層」 |
| 3 | **一次拍多個 layer** | 「這條屬 L_M，先把 L_N 結了，記到 Tracker 對應層」 |
| 4 | **重議已拍板的事** | 「這題已拍 X，記在決策檔 D-NNNN，不再重議」 |
| 5 | **scope creep** | 「這功能偏離主軸，記到 L1 backlog / future scope」 |
| 6 | **過度求精** | 「地基期不需 edge case 全解，主流先過」 |
| 7 | **沒 exit criteria 就往下** | 「先 confirm 當前層 exit criteria 全打勾了嗎？」 |

### Session ritual

- 新 session 先讀 `Spec/Progress_Tracker.md`「🎯 目前焦點」定位（哪一層、上次拍什麼）、重述 agenda，PM confirm 才開始討論。
- 討論中發現歪樓 → 立刻 flag、先回當前層，那條記回對應層的 Tracker。

---

> **本檔是源頭。** 各專案 domain 專屬的 exit criteria 留在該專案自己的 `Spec/Progress_Tracker.md` 與 `Spec/Decision_Principles.md`，不上收到本檔；通用規則以本檔為準。要吃本檔的框架更新，各專案用專案初始化腳本的更新模式刷新 vendored 的 `.claude/workflow/`（工具腳本未包含於此 repo）。
