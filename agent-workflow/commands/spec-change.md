---
description: Phase 0 SPEC 異動：不可跳步 checklist（MR 盤點→工作項＋草案→掃描→提案→等 PM OK→worktree→寫入或延後→稽核→drift→親核→存量稽核→總結）
---

# /spec-change — Phase 0 SPEC 異動 checklist

在**主線**執行。本檔是**調度清單 + 跳步防呆**，規則的唯一權威是
[`workflow/phase-0-spec-update.md`](../workflow/phase-0-spec-update.md)（七階段 ①~⑬）
與 [`workflow/phase-0-impact-scan.md`](../workflow/phase-0-impact-scan.md)（scanner 輸入格式）。
本檔**不重述**那些規則，只固定**順序**與**每步要吐的證據**。

**前置**：先讀 `workflow/phase-0-spec-update.md`。本檔各步標的 ①~⑬ 即該檔執行順序的編號。

> 安裝：把本檔複製到專案的 `.claude/commands/spec-change.md`，在 Claude Code 輸入 `/spec-change` 叫出。
> 下文的 `$CLAUDE_WORKSPACE` 指放規則書與工具腳本的位置（見 README）。

---

## 🚦 不可跳步（本 command 存在的理由）

1. **順序寫死**：Step 1 → 12 依序跑，**不得重排、不得併步**。
2. **每步必吐一行**，二選一，格式固定：
   - `Step N ✅ 已做：<證據>` — 證據＝指令、命中數、檔:行、agent 回報摘要。不准寫「已完成」了事。
   - `Step N ⏭ 略過理由：<一句>` — **沒有理由的略過＝未完成**。
3. **Step 5 是硬停點**：沒收到 PM 的回覆，**不准**往 Step 6 走。「PM 大概會同意」不算回覆。
4. **Step 3（掃描）只有一種合法略過**：規則書 ③④⑤ 的例外——在 Step 4 提案裡**明寫**「本議題無外部連動」並附掃過的詞與命中數。「議題很小」「我看過了」不算。
5. 十二行輸出（Step 1～12）**逐步即時吐**，不要攢到最後一次補完（補完＝事後編故事）。
6. **Step 6（開 worktree）是寫入前的硬門**：沒有吐 `Step 6 ✅ worktree：<路徑>` 這一行，**不准**呼叫 writer／deferrer。「push 到 main」≠「在 main 主樹編輯」。
7. **中途發現自己違規（主樹已被改、跳步…）→ 當下停、當下跟 PM 講**，不准做完再在總結裡補一句。

---

## Step 1 — 開著的 MR / 分支盤點（動任何檔之前）

別人正在改同幾行時，git 自動合併會靜默只留一邊。動手前先看一次。

```bash
git -C <repo> fetch --all --prune && git -C <repo> branch -r --sort=-committerdate | head -20
git -C <repo> worktree list
# GitLab repo 且 $SPEC_SYNC_API_URL／$SPEC_SYNC_API_TOKEN 有值時再加這段
# 專案 id 直接用 URL-encoded 路徑（<group>%2F<repo>），不必查數字 pid
curl -s --max-time 15 --header "PRIVATE-TOKEN: $SPEC_SYNC_API_TOKEN" \
  "$SPEC_SYNC_API_URL/api/v4/projects/<group>%2F<repo>/merge_requests?state=opened&per_page=100" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print('API_ERR',d) if isinstance(d,dict) else [print(f\"!{m['iid']} {m['source_branch']} -> {m['target_branch']} | {m['title'][:60]}\") for m in d]"
# 疑似撞車 → .../merge_requests/<iid>/changes 看對方改了哪些檔
```

疑似撞到本次要改的 SPEC 檔 → 讀對方 `/changes` 對檔名；真撞車就**先講**，不要悶著改。

**輸出**：`Step 1 ✅ 已做：<N 條開著的 MR / 遠端分支，其中撞到本次檔的：…（無則「無撞車」）>`
取不到 MR 清單（無 token / 非 GitLab / curl 失敗）→ 照樣吐 ✅，證據寫「只查到分支層：…，MR API 不可用（原因）」。

---

## Step 2 — 工作項 + 定案草案 + 結構化決策清單（規則書 ①②③）

**先記工作項**：issue 全路徑（格式照 repo `CLAUDE.md`，如 `my-org/todo-app#N`）＋ milestone。沒有 issue → 先請 PM 開（或 PM 明說無法開單＝`口頭需求`），不准自己編號。
**驗 milestone**（repo `CLAUDE.md` 宣告 `版本分支同步：有` 時必做；規則書 §SPEC 生命週期 7）：issue 的 milestone 必須是 ① 開著的 `spec/vX.Y.Z`（有分支、沒有 `spec/vX.Y.Z-release` tag）② 還沒開分支、也沒 release 過的未來版本號 ③ 非版本號（如 Backlog）三者之一。分支與 tag 一次列：`git -C <repo> ls-remote --heads --tags origin 'spec/v*'`。對不上（打錯字、指到已 release 的版本、沒掛 milestone）→ 先請 PM 改 issue，**不往下走**——錯的 milestone 會讓同步把 commit 挑進錯的分支。
再和 PM 一問一答推敲完，整理成 scanner 要的**結構化清單**（欄位以 `phase-0-impact-scan.md`「輸入格式」為準）。
此步**不動任何檔**。

**輸出**：`Step 2 ✅ 已做：<工作項全路徑＋milestone（有效：開著的分支／未來版本／非版本號；宣告「無」寫「不驗」）；議題編號/標題；草案 N 條；已知連動點 M 個>`

---

## Step 3 — 影響範圍掃描（規則書 ③④⑤）

1. 呼叫 `@phase0-impact-scanner`，餵 Step 2 的結構化清單。
2. agent 回來後**用腳本複掃**（不信任單一來源）。**兩段掃、不要一把梭**（`spec-grep.sh` 工具腳本未包含於此 repo；沒有就用 `grep -rn` 對 Spec 樹做同樣兩段）：
   ```bash
   # (a) 窄詞先掃：本次要動的那個值 / 那個專有名詞
   $CLAUDE_WORKSPACE/scripts/spec-grep.sh <repo> -- <窄詞>... > "${sg_out:=$(mktemp)}" 2>&1; echo "rc=$? out=$sg_out"
   # (b) 再補同義白話擴一輪；--count 只看每檔命中數
   $CLAUDE_WORKSPACE/scripts/spec-grep.sh <repo> --count -- <窄詞> <同義白話>...
   ```
   - ⚠️ **廣義詞（「通知」「提醒」「任務」這種）會打中整棵 Spec 樹＝等於沒掃**。命中檔數逼近 Spec md 總數就是掃太廣，回頭收窄。
   - ⚠️ **不要 `| head`**：grep 無命中時 exit 1，接 pipe 會被 `head` 的 rc 蓋掉；宣告「0 命中」前一定要導檔再讀 `rc`（上面 (a) 的寫法）。
3. 整理成三桶給 PM：強連動（必改）／弱連動（要 PM 選 A/B/C）／無影響（已掃清單）。

**輸出**：`Step 3 ✅ 已做：<scanner 回報 強N/弱M/無K；spec-grep 掃了「詞1,詞2…」命中 X 筆於 Y 檔>`
或 `Step 3 ⏭ 略過理由：本議題無外部連動（spec-grep「詞…」全庫 0 命中，rc=1）` ← 只有這個形狀合法。

---

## Step 4 — 提案：scope 兩欄草案（規則書 ⑤，備 ⑥ 用）

依規則書「✋ 寫前範圍控管」把草案分兩欄：`已拍板要寫的` vs `候選衍生情境`。

- **候選欄必須跑 [`scenario-expansion`](../skills/scenario-expansion/SKILL.md) skill §4.5「Phase 0 邊界 12 問」逐題產生**——
  **每題答「有情境（列出）」或「確認不適用（一句理由）」，不得空白**，不得只列自己想到的。
- 每條候選標【建議寫／建議跳過】＋一句理由，**預設從嚴、偏少**。
- 一併列出 Step 3 的弱連動選項、和「本批新名詞: [中文｜英文 …]｜無」（規則書 ⑦ 必填欄，先在此提案讓 PM 一起看）。
- 草案若是「先不做、晚點開」→ 提「**延後代替寫入**」選項（Step 7 改派 deferrer，正文不寫延後標記）；要啟用已延後的功能 → 提「**接回**」。

**輸出**：`Step 4 ✅ 已做：<已拍板 N 條；候選 M 條（建議寫 a / 建議跳過 b）；12 問全數作答；本批新名詞：…>`

---

## Step 5 — 🛑 等 PM 拍板（規則書 ⑥⑧）— **停在這裡**

把 Step 4 的兩欄貼給 PM，問三件事：① 候選欄勾哪幾條 ② 弱連動各選哪個 ③ 可以寫入了嗎（寫入／延後／接回 三選一）。

> **停。不准自動往下。** PM 沒回 = 沒拍板 = Step 6 起都不存在。
> PM 只回了一部分（例如只勾 scope 沒說可以寫）→ 也是停，追問缺的那項。

**輸出**：`Step 5 ⏸ 等 PM 拍板：<列出等 PM 回的三題>` → 然後**結束本輪輸出**。
收到回覆後續跑，改吐 `Step 5 ✅ 已做：<PM 勾了什麼、原文引一句>`。

---

## Step 6 — 開 worktree（寫入前硬門）

Step 1～5 都是唯讀，可以在主樹做；**從 Step 7 起會寫檔，必須先離開主樹**。

```bash
git -C <repo> fetch -q && git -C <repo> worktree add -b p0/<slug> ../<repo名>-<slug> origin/main
```

- **之後所有路徑一律用 worktree 路徑**：Step 7～10 的 `<repo>`、每個 subagent prompt 的「Repo:」欄、自己的 Edit 檔案路徑。**prompt 裡不准寫主樹路徑或「work on main」**。
- 跑前看 repo `CLAUDE.md`：有自訂 worktree 命名慣例就照它。
- **唯一合法略過**：repo `CLAUDE.md` 與 workspace `CLAUDE.md` 都沒有 worktree 規定。

**輸出**：`Step 6 ✅ worktree：<worktree 路徑>（branch p0/<slug>）`

---

## Step 7 — 寫入或延後（規則書 ⑦⑧⑨）

1. 整理「最終定案結論」＝Step 4 兩欄**只留 PM 勾的** + PM 補的連動 + `本批新名詞` 欄（必填，無則明寫「無」）+ Step 2 的工作項全路徑。
2. 清 dirty-log 讓本批改檔被乾淨記錄：
   ```bash
   > <repo>/.claude/spec-dirty.log
   ```
3. 呼叫 `@phase0-spec-writer` **一次寫完全部**（就地 Edit、不押日期、不新建檔；同步 Project_Context / Decision_Principles / Glossary / 決策檔 / README；**寫完不自己 commit**）。
   分組平行派多個 writer 時，每個 prompt 指定自己的 `.claude/spec-write-report.<group>.json`，不共用一份（會互相覆蓋）。
   Step 5 PM 拍「延後／接回」→ 改呼叫 `@phase0-spec-deferrer`（defer／restore 模式，餵功能名＋關鍵詞＋工作項＋PM 的拍板原文），產出 `.claude/spec-defer-report.json`；第 4 項改看它的 D 類／未接清單。
4. 若 `$CLAUDE_WORKSPACE/scripts/spec-writer-report-check.sh` 存在（工具腳本未包含於此 repo）→ 跑它核 writer 自報：
   ```bash
   $CLAUDE_WORKSPACE/scripts/spec-writer-report-check.sh <repo> [report 檔]   # 平行 writer 逐份跑
   ```
   不存在 → 這一項寫 ⏭ 並附「腳本未安裝」。

5. **決策檔**（writer／deferrer 都要寫，Step 8 verifier 會驗）：`Spec/memory/` 有本批決策檔，frontmatter `id`／`date`／`changes`／`supersedes`（可 `[]`）／`status`／`source`（＝Step 2 工作項）都填了、內文四段（結論／Why／否決的方案／推翻了什麼）齊；`milestone` 由腳本帶、不手填。沒有就退回重寫，不自己補。

**輸出**：`Step 7 ✅ 已做：<writer 或 deferrer；改了 N 檔（列檔名）；決策檔 D-NNNN 路徑；新名詞 K 個已進 Glossary（或搬出 A/剪 B/待 PM D）；report-check: 過/未安裝>`

---

## Step 8 — 獨立稽核（規則書 ⑨a）

呼叫 `@phase0-spec-verifier`（**與 writer 不同 agent，球員不兼裁判**）。它會對 `.claude/spec-dirty.log` 核 writer 自報、親自跑 lint、看每個改動 hunk、修機械性偏差、留非機械判定給 PM。

- **每個 SPEC／mockup commit 都要有一次 verifier pass**；主線自己動過 SPEC（含收尾順手修一句）也一樣，改完重跑 verifier 才能 commit。
- 派工 prompt 不寫「lint 已 0」「這類可放行」這種前提；給它工作項、定案清單、改檔清單就好。
- commit 訊息最後一段帶 trailer `Verified-by: phase0-spec-verifier`（PM 親核過再加 `Verified-by: <PM>`）。

**輸出**：`Step 8 ✅ 已做：<發現 N / 已自動修 M / 待 PM 裁決 K（逐條列 K）；決策檔／保留編號／接回錨點：過/問題；Verified-by 已備>`

---

## Step 9 — mockup / 流程圖 drift（規則書 ⑨b）

呼叫 `@phase0-mockup-drift-scanner`（規則書標**自動觸發**，不需 PM 同意；它不改檔）。
派工時把 Step 7 改到的**全部 SPEC 檔清單**原樣給 scanner，不要只描述主檔條文——只寫主檔的一節，scanner 會漏掉另一份 SPEC 檔裡被連動改到的小節。
拿到四 bucket：📝 修改有引用（必審）／🆕 新增（待規劃）／⚠️ 刪除有引用（dangling 必修）／⏭️ 修改無引用。

**輸出**：`Step 9 ✅ 已做：<必審 a / 待規劃 b / dangling c / 跳過 d>`

---

## Step 10 — `git diff` 親核 + commit 策略（規則書 ⑩⑪）

```bash
git -C <repo> status --short && git -C <repo> diff --stat && git -C <repo> diff
```

1. **逐段對** Step 7 的最終定案結論：每條定案在 diff 裡找得到；diff 裡每段改動對得回某條定案。對不上的**當場講**，不要放行。
   專案有限定詞守門工具（例：比對 diff 中限定詞／§ID／數字變動的腳本）→ 跑它，列出的每一對逐條對到某條定案，對不到＝規則範圍被改寫，當場講。
2. `git status` 有非預期 `??` SPEC md 副本 → 是 fork，刪副本、改回就地 Edit。
3. 依 Step 9 報告**建議** commit 策略（Path A 純文字單 commit／Path B feature branch 兩 commit + Phase 1 補 mockup），**由 PM 拍**。
4. **不代打 commit、不 push、不開 MR**（副作用分級：只報告）。
5. PM 點頭後在 **worktree 裡** commit（message 引用 Step 2 工作項全路徑，一個 commit 一個工作項；帶 Step 8 的 `Verified-by:` trailer）→ 回主樹 `git fetch` → 依 repo 慣例落地（例：cherry-pick／ff 進 `main` 再 push）→ `git worktree remove` ＋ `git branch -D p0/<slug>`。
6. **兩份 HTML 清單對帳**：Step 3 impact-scanner 報告裡的 HTML 命中 vs Step 9 drift-scanner 報告，只出現在一邊的 檔:行逐一看過才放行。
7. **刪了 data-testid 就全庫搜**：本批（含 Phase 1 mockup commit）刪掉的 data-testid，用 `grep -rn -F` 搜全 repo（排除 History），還有引用就一併修。
8. **push 到 `main` 之後：版本分支同步檢查**（機器判，三種結果；規則書 §SPEC 生命週期 7）。讀 repo `CLAUDE.md` 的 `版本分支同步：` 那一行：
   - **`無`** → 靜默略過，不吐字。
   - **`有`** → 兩項都查：
     ```bash
     $CLAUDE_WORKSPACE/recipes/spec-version-branches/check-spec-branches-sync.sh <repo>; echo "rc=$?"   # 0 ✓ ／ 1 腳本 drift 或缺檔（含缺 ci/spec_branches_config.py）／ 2 未安裝
     # 剛 push 的 pipeline 裡 spec-branch-sync job 的狀態（running／pending → 等它跑完再判）
     sha=$(git -C <repo> rev-parse origin/main)
     api="$SPEC_SYNC_API_URL/api/v4/projects/<group>%2F<repo>"
     pid=$(curl -s --max-time 15 --header "PRIVATE-TOKEN: $SPEC_SYNC_API_TOKEN" "$api/pipelines?sha=$sha&ref=main" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[0]['id'] if isinstance(d,list) and d else '')")
     [ -n "$pid" ] || echo "pipeline 還沒出現或 API 回錯（401／404）→ 稍後再查，不准當成 green"
     [ -n "$pid" ] && curl -s --max-time 15 --header "PRIVATE-TOKEN: $SPEC_SYNC_API_TOKEN" "$api/pipelines/$pid/jobs?per_page=100" \
       | python3 -c "import json,sys; print(next((j['status']+' '+j['web_url'] for j in json.load(sys.stdin) if j['name']=='spec-branch-sync'),'MISSING'))"
     ```
     （檢查腳本即本 repo 的 [`recipes/spec-version-branches/check-spec-branches-sync.sh`](../recipes/spec-version-branches/check-spec-branches-sync.sh)。）
     腳本 rc=0 且 job `success` → 印 `✓ green`；job `failed`／`canceled` 或腳本 rc=1 → 印 `✗ red: <pipeline 連結>`（腳本 drift 時改附 drift 的檔名）。**red＝照 [`recipes/spec-version-branches.md`](../recipes/spec-version-branches.md)「解同步衝突」／「更新腳本」處理完才算做完**，不准帶著紅燈進 Step 12 說收工。
   - **沒有這行宣告**、腳本 rc=2，或 pipeline 裡**沒有** `spec-branch-sync` job → 印 `⏭ 未安裝（見 recipes/spec-version-branches.md）`。
   - 沒 `$SPEC_SYNC_API_TOKEN` 查不了 job → 印 pipeline 頁網址（`$SPEC_SYNC_API_URL/<group>/<repo>/-/pipelines?ref=main`）請 PM 看那一格，不准當成 green。

**輸出**：`Step 10 ✅ 已做：<N 檔 +a/-b 行；定案 M 條全數對到 diff（或列出對不上的）；建議 Path A/B 因為…；（push 後）版本分支：✓ green ／ ✗ red: <連結> ／ ⏭ 未安裝（宣告「無」不寫）>`

---

## Step 11 — 存量清理／遷移的獨立稽核（規則書 §SPEC 生命週期 6(c)）

只在本批是**存量級**工作時跑（全庫套新規則、清歷程字樣、搬體例、遷移）；一般單項異動 → ⏭ 並寫「非存量清理」。

- 另派一個**沒參與本批**的 agent（不是 writer、不是本批 verifier）當稽核。
- prompt 只給：規則本身（規則書條文）、受影響檔案範圍、工作項。**不給**「lint 已 0」前提、不列預先核准的例外、不給 lint 命中清單當工作清單。
- 它讀整段受影響正文（不只 lint 命中行），回報剩餘違規與被改寫範圍的規則；有一條就不算完成，回 Step 7。
- lint 0 是必要條件，不是完成定義；只有這個稽核說乾淨才能對 PM 說「清完了」。

**輸出**：`Step 11 ✅ 已做：<稽核 agent 名；讀了 N 檔；剩餘違規 K 條（逐條列）>` 或 `Step 11 ⏭ 略過理由：非存量清理`

---

## Step 12 — 收尾總結

三段：**做完了什麼**（含檔案路徑）／**沒做完什麼**／**待 PM 拍**（每項附建議選項）。

不落草稿檔。送出前重讀一遍，抓「多出來的因果／判斷詞／時態變過去式／空泛成語」——總結只寫發生過的事，不替 PM 下結論。

總結**開頭先列 Step 1~12 的十二行**（✅／⏭／⏸ 原樣），讓 PM 一眼看出哪步被跳過、跳得有沒有道理。

**輸出**：`Step 12 ✅ 已做：<三段總結已送出>`
