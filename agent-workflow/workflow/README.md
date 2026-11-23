# Rulebook index · 規則書索引

**English** · [繁體中文](#繁體中文)

All 20 rulebooks in this folder are written in Traditional Chinese. Descriptions below are taken from each file's own header.

## Entry and routing

| File | What it covers |
|---|---|
| [`entry-routing.md`](entry-routing.md) | Entry routing: when a session starts or a request arrives, decide which of the three axes it takes (not a single linear order) |

## Foundation (Axis A)

| File | What it covers |
|---|---|
| [`foundation-track.md`](foundation-track.md) | Foundation track for greenfield projects: L0 Vision → L1 Scope → L2 Entities → L3 Permission → seam → L4 Process → L5 UI → L6 Tech, one gate per layer |

## Phase 0 (Axis B, decision-write engine)

| File | What it covers |
|---|---|
| [`phase-0-spec-update.md`](phase-0-spec-update.md) | SPEC discussion and writing: discuss → scan → sign-off → write → verify → drift → release, plus the SPEC lifecycle rules |
| [`phase-0-impact-scan.md`](phase-0-impact-scan.md) | Impact scan before sign-off, run by `@phase0-impact-scanner` over every `.md` under `Spec/` and decided issues |

## Phases 1–8 (Axis C, artifact pipeline)

| File | What it covers |
|---|---|
| [`phase-1-product-design.md`](phase-1-product-design.md) | Product design pack: annotated mockups and user stories (`product-spec.md`) |
| [`phase-2-spec.md`](phase-2-spec.md) | Tech spec derived from Phase 1 output (`CLAUDE_DEV_INSTRUCTION.md`) |
| [`phase-2.5-pending.md`](phase-2.5-pending.md) | Open-question list (`PENDING_SPEC.md`) in P0/P1/P2 tiers, with mock values so building is not blocked |
| [`phase-3-mockup.md`](phase-3-mockup.md) | **Retired**: merged into Phase 1; do not use |
| [`phase-4-tests.md`](phase-4-tests.md) | Acceptance scripts generated from the Phase 1 user stories |
| [`phase-5-dev.md`](phase-5-dev.md) | Implementation, two flows: Flow A fully by Claude Code, Flow B engineer-led with Claude |
| [`phase-6-autotest.md`](phase-6-autotest.md) | Automated tests → bug-fix loop; report and screenshots feed Phases 7 and 8 |
| [`phase-7-review.md`](phase-7-review.md) | Manual spot-check by the PM to close out |
| [`phase-8-userguide.md`](phase-8-userguide.md) | User guide: mode A by `@phase8-guide-writer`, optional mode B per project |

## Cross-cutting rules

| File | What it covers |
|---|---|
| [`CONTRACTS.md`](CONTRACTS.md) | Input/output contracts between phases: what each phase reads, produces, and who uses it |
| [`SPEC_NUMBERING_RULES.md`](SPEC_NUMBERING_RULES.md) | SPEC section numbering: stable, citable numbers that never force a renumber |
| [`CROSSLINK_REGEN.md`](CROSSLINK_REGEN.md) | Keeping cross-links between SPEC, indexes and diagrams in sync |
| [`GUIDE_SECTIONS.md`](GUIDE_SECTIONS.md) | Blank template: the single list of user-guide section names that Phases 1 and 4 must copy exactly |
| [`discussion-docs.md`](discussion-docs.md) | How to open, edit and close discussion issues (the hand-off between discussion and SPEC writing) |
| [`file-discipline.md`](file-discipline.md) | Stopping files from slowly multiplying and growing until a big clean-up is needed |
| [`verification.md`](verification.md) | Verification for any work that writes code (not for SPEC/doc-only work) |

## Reading order for newcomers

1. [`entry-routing.md`](entry-routing.md): the three-axis map.
2. [`foundation-track.md`](foundation-track.md): how a new project lays its foundation.
3. [`phase-0-spec-update.md`](phase-0-spec-update.md), then [`phase-0-impact-scan.md`](phase-0-impact-scan.md): how every spec change is decided and written.
4. [`CONTRACTS.md`](CONTRACTS.md): how the phases hand off to each other.
5. Phases 1 → 8 as you need them (skip `phase-3-mockup.md`).
6. [`verification.md`](verification.md) before writing any code; the other cross-cutting rules when a phase points to them.

---

## 繁體中文

本資料夾 20 份規則書皆以繁體中文撰寫；以下說明取自各檔自身的開頭。

## 入口路由

| 檔案 | 內容 |
|---|---|
| [`entry-routing.md`](entry-routing.md) | 入口路由：session 冷啟動或收到新需求時，判定走三軸中的哪條軌（非單一線性順序） |

## 地基（軸 A）

| 檔案 | 內容 |
|---|---|
| [`foundation-track.md`](foundation-track.md) | 全新專案的地基軌：L0 Vision → L1 Scope → L2 Entities → L3 Permission →〔接縫〕→ L4 Process → L5 UI → L6 Tech，每層一個 gate |

## Phase 0（軸 B 決策寫入引擎）

| 檔案 | 內容 |
|---|---|
| [`phase-0-spec-update.md`](phase-0-spec-update.md) | SPEC 討論與寫入：討論 → 掃描 → 拍板 → 寫入 → 稽核 → drift → 收版，含 SPEC 生命週期規則 |
| [`phase-0-impact-scan.md`](phase-0-impact-scan.md) | 拍板前的影響範圍掃描，由 `@phase0-impact-scanner` 掃 `Spec/` 全部 `.md` 與已定案議題 |

## Phase 1–8（軸 C 工序）

| 檔案 | 內容 |
|---|---|
| [`phase-1-product-design.md`](phase-1-product-design.md) | 產品設計包：標註版 mockup 與 User Story（`product-spec.md`） |
| [`phase-2-spec.md`](phase-2-spec.md) | 從 Phase 1 產出推導技術規格（`CLAUDE_DEV_INSTRUCTION.md`） |
| [`phase-2.5-pending.md`](phase-2.5-pending.md) | 待確認規格清單（`PENDING_SPEC.md`），分 P0/P1/P2，附 mock 值讓開發不被阻擋 |
| [`phase-3-mockup.md`](phase-3-mockup.md) | **已退役**：併入 Phase 1，請勿使用 |
| [`phase-4-tests.md`](phase-4-tests.md) | 依 Phase 1 的 User Story 生成驗收腳本 |
| [`phase-5-dev.md`](phase-5-dev.md) | 開發實作雙流程：Flow A 全由 Claude Code，Flow B 工程師主導、Claude 協作 |
| [`phase-6-autotest.md`](phase-6-autotest.md) | 自動測試 → Bug 修復迴圈；報告與截圖餵 Phase 7、8 |
| [`phase-7-review.md`](phase-7-review.md) | PM 人工抽測結案 |
| [`phase-8-userguide.md`](phase-8-userguide.md) | User Guide 產出：模式 A 由 `@phase8-guide-writer`，模式 B 依專案選配 |

## 跨階段規則

| 檔案 | 內容 |
|---|---|
| [`CONTRACTS.md`](CONTRACTS.md) | 跨階段輸入輸出契約：每個 Phase 讀什麼、產出什麼、誰用 |
| [`SPEC_NUMBERING_RULES.md`](SPEC_NUMBERING_RULES.md) | SPEC 章節編號規則：編號穩定、可引用、新增不連帶重編 |
| [`CROSSLINK_REGEN.md`](CROSSLINK_REGEN.md) | SPEC、索引與圖之間的交叉連結同步 |
| [`GUIDE_SECTIONS.md`](GUIDE_SECTIONS.md) | 空白範本：User Guide 章節名稱唯一來源，Phase 1、4 必須照抄 |
| [`discussion-docs.md`](discussion-docs.md) | 待討論議題的開立、編輯、結案規則（討論與 SPEC 寫入的交接面） |
| [`file-discipline.md`](file-discipline.md) | 防止檔案「每次只多一點點」地變多變大，直到要大掃除 |
| [`verification.md`](verification.md) | 所有「直接寫程式」工作的驗證流程（只改 SPEC／文件不適用） |

## 新手閱讀順序

1. [`entry-routing.md`](entry-routing.md)：三軸全貌。
2. [`foundation-track.md`](foundation-track.md)：新專案怎麼立地基。
3. [`phase-0-spec-update.md`](phase-0-spec-update.md)，接著 [`phase-0-impact-scan.md`](phase-0-impact-scan.md)：每筆規格異動怎麼決定、怎麼寫入。
4. [`CONTRACTS.md`](CONTRACTS.md)：各 Phase 怎麼交棒。
5. Phase 1 → 8 依需要閱讀（跳過 `phase-3-mockup.md`）。
6. 寫程式前讀 [`verification.md`](verification.md)；其他跨階段規則在 Phase 文件指到時再讀。
