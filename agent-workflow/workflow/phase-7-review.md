---
phase: 7
name: 人工抽測結案
executor: 你
reads_from: reports/report-{date}.md
feeds_into: workflow/phase-8-userguide.md（確認系統可用後才生成 Guide）
---

# Phase 7｜人工抽測結案

---

## 你要做的事

1. 打開 `reports/report-{date}.md`，挑幾個關鍵路徑
2. 自己在測試站跑一遍（重點放 happy path 和你最擔心的流程）
3. 發現問題：直接告訴 Claude，走快速修復流程（不用重跑整個 Phase 6）
4. 沒問題：宣告 **Phase 7 passed**，進入 Phase 8

---

## 建議抽測路徑（優先）——以下以虛構的「待辦清單 App」示意，換專案代換成自己的關鍵路徑

1. 勾選任務完成 → 任務移到「已完成」分頁、標題顯示刪除線
2. 封存已完成任務 → 確認視窗出現，確認後任務只出現在「已封存」分頁且唯讀
3. 還原已封存任務 → 任務回到「已完成」分頁、可再取消勾選
4. 以 Viewer 身分登入 → 核取方塊與「封存已完成」皆呈停用樣式

---

## Checklist

- [ ] 核心 happy path 自己跑過一遍
- [ ] 沒有影響上線的阻斷性問題
- [ ] 進入 Phase 8
