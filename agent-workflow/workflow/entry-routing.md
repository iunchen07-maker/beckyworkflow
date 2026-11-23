---
type: 入口路由（三軸判定）
scope: 所有 spec-driven 專案（vendored，隨 .claude/workflow/ 帶進專案）
applies_to: PM + Claude 討論主體（session 冷啟動 / 收到新需求時判定走哪條軌）
reads_from:
  - Spec/Progress_Tracker.md（是否存在 + 各層 gate 狀態 → R1/R2）
  - Spec/ 全檔 + 討論排程/待討論/0_議題總覽.md（grep 對應 US/章節 → R3/R4）
also_see:
  - workflow/foundation-track.md（軸 A 地基軌，R1/R5 會回到這裡）
  - workflow/phase-0-spec-update.md（軸 B 引擎，R3/R4 走這裡）
  - workflow/CONTRACTS.md（跨階段膠水）
---

# 入口路由（三軸，非單一線性順序）

> **這是「收到一個需求，該走哪條軌」的判定表。** 是整套工作流最上游的膠水——foundation-track（軸 A）與 phase-0（軸 B）都會回到本檔的 R1–R5／4 例外標號。
>
> 本檔隨 vendoring 進每個專案的 `.claude/workflow/`，所以 handed-off 專案（沒掛 `$CLAUDE_WORKSPACE`）也解得開 R1–R5。

---

## 三軸模型（速覽）

**軸 A｜地基軌**（[`foundation-track.md`](./foundation-track.md)）× **軸 B｜Phase 0 引擎**（[`phase-0-spec-update.md`](./phase-0-spec-update.md)）× **軸 C｜Phase 1~8 工序**（跨階段產出契約見 [`CONTRACTS.md`](./CONTRACTS.md)），彼此是呼叫關係、不是線性順序——三軸解說與三情境映射見 [`foundation-track.md`](./foundation-track.md) §1。

---

## 入口路由 decision table（由上往下，第一個命中即路由）

| # | 可觀測訊號 | 情境 | 走什麼 |
|---|---|---|---|
| **R1** | 無 `Spec/Progress_Tracker.md`，且 Glossary / Project_Context 仍是模板空殼 | 情境 1 greenfield | 開地基軌：建 Tracker，L0 起逐層，每層 gate 跑一筆 Phase 0 交易（見 [`foundation-track.md`](./foundation-track.md)） |
| **R2** | Tracker 存在且接縫前各層 ✅ gate；**或**無 Tracker 老專案但 Spec/ 已成體系（INDEX 有 US- 條目）→ 地基 grandfathered 視為已鎖 | 進 R3 | — |
| **R3** | grep Spec/ 全檔 + 查 `討論排程/待討論/0_議題總覽.md`，**找不到**對應 US-id / 章節 | 情境 2 新功能 | （選用 task-breakdown / scenario-expansion skill，未包含於此 repo）→ Phase 0 新增-US 交易 → 軸 C 全鏈 |
| **R4** | **找得到**既有條文，且不觸及 R5 地基物件 | 情境 3 改規格 | Phase 0 維護交易 → Path A/B → 只補受影響 artifact |
| **R5** | 改動觸及**地基物件**（Glossary 既有名詞重定義／entity·domain 增刪／權限模型結構改動／persona 增刪／L1 邊界翻案） | 模糊 → 升級問 PM | 停，問：重開 L{n} gate 增量修（見 [`foundation-track.md`](./foundation-track.md) §6），還是當功能級 patch？ |

---

## 必問 PM 的 4 種例外

**路由表外唯一要停下來的**；除這 4 種全自動路由——路由判錯成本極低，因 Phase 0 的 PM 拍板／收版 gate 無條件擋著。

1. **重開地基層**（＝ R5）：改動觸及地基物件，判「重開 L{n} gate 增量修」還是「功能級 patch」。
2. **立新專案 vs 塞進既有**：ask 幾乎是獨立子系統（新 persona 群 / 新 domain / 既有 Glossary 幾乎用不上）時，問這算不算新專案。
3. **老專案是否補建 Tracker**：grandfathered 老專案第一次踩到地基級改動時問一次，答案記進該專案 `CLAUDE.md`，之後不再問。
4. **新專案接縫層放哪**：開專案時問一次，寫進 `Spec/Progress_Tracker.md` 頂部（接縫層宣告欄）。
