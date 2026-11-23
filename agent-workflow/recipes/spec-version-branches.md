# SPEC 版本分支（`spec/vX.Y.Z`）＋ CI 自動同步

## 這是什麼/何時用

SPEC 一律寫在 `main`，但 `main` 常同時放好幾版的行為（v1.10.0 還在開發，PM 已經在寫 v1.11.0）。本配方讓**每個開發中的 milestone 有一條 `spec/vX.Y.Z` 分支**，CI 依工作項的 milestone 自動把 `main` 的 commit 挑進該挑的分支；RD／QA 讀分支，不讀 `main`。

**為什麼要這層**（兩個常見需求）：

1. **每個 milestone 要知道「這版完整的行為」**，不是只有「這版改了什麼」。`main` 混著下一版的條文，RD 照 `main` 做會做到還沒排的功能。
2. **大家拿到同一份 PM 確認過的版本，release 後凍結**。不能各自 `git log` 拼、也不能 release 後還被改。

**何時用**：專案有 milestone＝code 版本號（`vX.Y.Z`），而且 SPEC 會領先 code 一版以上。沒有版本的專案（單一持續上線、或只有 Backlog）不裝，在 `CLAUDE.md` 宣告「無」即可。

規則層（什麼時候開分支、release 要過什麼）住 [`../workflow/phase-0-spec-update.md`](../workflow/phase-0-spec-update.md) §SPEC 生命週期 7、⓪、⑤a；本配方只講**怎麼裝、怎麼操作、會踩什麼**。

## 模型（一頁講完）

- **SPEC 寫在 `main`**。每個 SPEC commit 引用**一個**工作項（全路徑，如 `my-org/todo-app#8`）；工作項的 milestone＝code 版本。正文與 commit 訊息不寫版本字樣，改歸屬＝改 issue 的 milestone。
- **每個開發中的 milestone 一條 `spec/vX.Y.Z`**，milestone 開工時從當下 `main` 開。RD／QA 讀它。**永不 merge 回 `main`**。
- **`spec-branch-sync`**（CI，每次 push `main`）：對每條開著的分支，從分支點起依 `main` 順序 `cherry-pick -x` 每個 commit，**除非**它的工作項**現在**的 milestone 晚於該分支。沒引用工作項、milestone 不是版本號（Backlog…）的照挑。衝突 → 停在那一筆、該分支這次什麼都不推、job 紅、通知團隊頻道；人在分支上解。分支上 revert 掉的 commit，工作項改回不晚於本版時會被重挑。**最終狀態跟著每個工作項現在的 milestone 走。**
- **`spec-branch-check`**（每日排程）：報「缺」（該挑沒挑）與「多」（挑了、工作項已改到更晚版），只報不修。
- **Release**：`spec_sync.py release-check vX.Y.Z` 通過 → `--tag` 打 `spec/vX.Y.Z-release`，分支關閉（不再同步、不再檢查）。不通過 → 清單給 PM，PM 決定。
- **不用改 SPEC 的工作項**：issue 上留一行固定字樣 `SPEC 不用改，§X 已經這樣寫`，release-check 機器比對。
- **SPEC 改動的 commit 沒帶這張票**（例：改在別張票、或帶票規則以前的舊 commit）：issue 上留一行 `SPEC 變更：commit <sha>`，sha 在分支上就算數。
- **過渡**：專案開始要求工作項之前的 commit 不追溯。
- **opt-in**：repo `CLAUDE.md` 一行宣告（見安裝第 8 步）；SPEC 異動流程 push 後讀這行決定要不要檢查同步結果。

## 工具與檔案

同一套腳本要裝進好幾個 repo，各 repo 只放一模一樣的複本；**正本在本 repo**，改腳本一律改正本再重裝。

正本目錄：[`spec-version-branches/`](spec-version-branches/)

| 檔 | 做什麼 |
|---|---|
| [`spec_at.py`](spec-version-branches/spec_at.py) | 依 milestone 還原某版 SPEC；載入設定、issue 抓法、版本比較、milestone 查詢（`spec_sync.py` 共用） |
| [`spec_sync.py`](spec-version-branches/spec_sync.py) | `sync`／`check`／`release-check` 三個子指令（規則全文在檔頭 docstring） |
| [`spec_branches_config.example.py`](spec-version-branches/spec_branches_config.example.py) | 專案設定範本（每個 key 的說明在檔內註解） |
| [`test/`](spec-version-branches/test/) | `test_spec_at.py`、`test_spec_sync.py`（假 GitLab＋暫存 repo，不連網） |
| [`gitlab-ci.snippet.yml`](spec-version-branches/gitlab-ci.snippet.yml) | 兩個 CI job＋共用 base＋其他 job 要加的排除規則 |
| [`install.sh <repo>`](spec-version-branches/install.sh) | 覆蓋複製 `spec_at.py`、`spec_sync.py` → `<repo>/ci/`，兩支測試 → `<repo>/ci/test/`；`ci/spec_branches_config.py` 只在缺時從範本建立（已有就不碰）；印出剩下的手動步驟。不 commit、不 push |
| [`check-spec-branches-sync.sh <repo>`](spec-version-branches/check-spec-branches-sync.sh) | 比對 `<repo>/ci/` 的四支複本與正本（設定檔不比對）：exit 0 一致／1 drift 或缺檔（含缺設定檔）／2 未安裝（`ci/spec_at.py`、`ci/spec_sync.py` 都沒有） |

## 完整流程（附例）

例：待辦清單 App（`my-org/todo-app`），v1.10.0 開發中，PM 已在寫 v1.11.0。

**① milestone 開工** — v1.10.0 開工那天，`main` 上該清的先清完，然後：
```bash
git push origin origin/main:refs/heads/spec/v1.10.0
```
從此 RD／QA 讀 `spec/v1.10.0`。

**② 每次改 SPEC**（走 Phase 0 SPEC 異動流程）
- 記工作項時驗 milestone：#8 掛 `v1.11.0`——還沒開分支的未來版本，合法。掛成 `v1.1.10`、`v1.11` 這種打錯字 → 先改 issue 再動手（錯字會被歸到錯的版本——`v1.1.10` 比 v1.10.0 早、會被挑進去——或被當成非版本號、挑進每一條分支）。
- 寫完 commit `…（my-org/todo-app#8）` push 到 `main` → `spec-branch-sync` 跑：#8 晚於 v1.10.0 → `spec/v1.10.0` **不挑**。同一天 #6（v1.10.0）的 commit → **挑**。
- push 後確認 pipeline 綠。若 #9（v1.10.0）改到 #8 剛改過的同一段 → 挑 #9 時衝突（分支上沒有 #8 那版的字）→ job 紅、團隊頻道收到通知，人去分支解（見下）。
- PM 決定 #8 提前到 v1.10.0 → 改 issue milestone 即可；下一次 push `main`，sync 依 `main` 原順序把它挑進來。

**③ 每日檢查** — #6 已挑進分支，後來改到 v1.11.0 → 隔天報「多」，附分支上那筆的 sha；要不要撤由人決定（撤法見下）。

**④ Release** — v1.10.0 上線前：
```bash
python3 ci/spec_sync.py release-check v1.10.0          # 只檢查
python3 ci/spec_sync.py release-check v1.10.0 --tag    # 全過才在分支最新 commit 打 annotated tag spec/v1.10.0-release 並推
```
本機跑（不放 CI），要 `SPEC_SYNC_API_URL`／`SPEC_SYNC_API_TOKEN`（GitLab 網址與 `read_api` token）。它查四件事：
- ① 分支 vs `main` 一致（同每日檢查：不缺、不多）。［擋］
- ② milestone v1.10.0 的每張 issue（含已關閉）：從分支最新 commit 往回找得到引用它的 commit（**含分支點以前的**，扣掉在分支上被撤的），或 issue 描述／任一則非系統留言有 `SPEC 變更：commit <sha>` 那行且 sha 是分支最新 commit 往回找得到、沒被撤的 commit（commit 不必帶票；同行多個 sha 一個合格即可；設定 `SPEC_CHANGE_MARK`），或有 `SPEC 不用改，§…` 那行（設定 `NO_CHANGE_MARK`）。都沒有 → 列出。［擋］還開著的 issue 另列，不擋。
- ③ 分支上沒有帶「更晚 milestone」issue 的 commit。［擋］
- ④ 分支上沒帶 issue 的 commit。［參考，不擋］

#7（v1.10.0）只改 code、SPEC 本來就對 → issue 上要有 `SPEC 不用改，§US-A1.3 已經這樣寫`，否則 ② 報它。不通過 → exit 2、不打 tag，清單給 PM 拍：補 commit、補那行、改 milestone，或照樣放行。tag 已存在 → 只報告、不重打。

**⑤ 下一版開工** — v1.11.0 開工時從當下 `main` 開 `spec/v1.11.0`，#8 自然在裡面。

### 人工操作

- **解同步衝突**：
  ```bash
  git switch spec/v1.10.0 && git pull
  git cherry-pick -x <main 上衝突那筆 sha>      # merge commit 加 -m 1
  # 解衝突 → git add … → git cherry-pick --continue
  git push
  ```
  後面的不用手挑：重跑該 pipeline 的 `spec-branch-sync`（或等下一次 push `main`）會從下一筆接著挑。
- **撤「多」**：`git switch spec/v1.10.0 && git pull && git revert <分支上那筆 sha> && git push`（通知給的是分支上 cherry-pick 出來那筆，不是 `main` 的 sha）。撤完 check 不再報、sync 不會挑回；日後工作項改回本版，sync 自動重挑。

## 安裝

1. **裝腳本**（在本 repo 根目錄）：
   ```bash
   bash recipes/spec-version-branches/install.sh <repo>
   ```
2. **專案設定** `<repo>/ci/spec_branches_config.py`（install.sh 第一次從範本建，之後不碰；專案差異**只**放這裡，不改複本）。這是普通 Python，可以 import 專案自己的模組讓同一個值只有一個出處；環境變數 `SPEC_BRANCHES_CONFIG` 可指到別的路徑。

   | key | 必填 | 填什麼 |
   |---|---|---|
   | `PROJECT` | ✅ | 工作項（milestone）所在的 GitLab 專案路徑；milestone 標題 `vX.Y.Z`（v 可省），其他標題一律當非版本號 |
   | `ISSUE_RE` | ✅ | commit 訊息認 issue 的 regex，第一群組＝編號。認全路徑＋短式、不認裸 `#N`、短編號不吃到更長編號的前綴（`#2` 不能命中 `#2` 開頭的更長編號） |
   | `WATCH` | ✅ | SPEC 範圍路徑前綴 tuple（`spec_at` 只還原動到這些的 commit）；專案已有 commit-issue 檢查就 import 那邊的值 |
   | `EXEMPT` | | WATCH 內要排除的前綴，預設 `()` |
   | `HEADING` | | `spec_at` 印「改到的 § 節」時認的標題 regex（具名群組 `id`）；預設 `None`＝最近的 Markdown 標題 |
   | `GENERATED` | | 產生檔路徑前綴清單（例：`["Spec/memory/index/"]`）；衝突只落在這裡＝跑 `REGEN_CMD` 重產、不算衝突。預設 `[]` |
   | `REGEN_CMD` | | 重產指令 argv，`{root}`＝結果樹、`{python}`＝目前的 python，例 `["{python}", "ci/regen_index.py", "--root", "{root}", "views"]` |
   | `SPEC_BRANCH_PREFIX`／`RELEASE_TAG_SUFFIX` | | 預設 `spec/v`／`-release` |
   | `TRACE_SINCE`／`UNTRACED_UPTO` | | 過渡期：`YYYY-MM-DD` 以前的 commit 不一定帶 issue；版本 ≤ `UNTRACED_UPTO`（tuple）的 `spec_at` 結果不完整。**只影響提醒文字** |
   | `NO_CHANGE_MARK` | | release-check ② 認「SPEC 不用改」的 regex，預設 `SPEC 不用改，§`；`None`＝每張都要有 commit |
   | `SPEC_CHANGE_MARK` | | release-check ② 認「SPEC 變更」那行的 regex，預設 `SPEC 變更：`；標記之後的 `commit <sha>` 要在分支上；`None`＝不接受 |
   | `WEBHOOK_ENV` | | 通知 webhook 放在哪個環境變數，預設 `SPEC_SYNC_WEBHOOK` |
3. **本機跑測試**：`(cd <repo> && python3 -m unittest discover -s ci/test -p 'test_spec_*.py')`（不連網）。
4. **CI job**：把 `gitlab-ci.snippet.yml` 的 `.spec-sync-base`＋兩個 job 貼進 `.gitlab-ci.yml`（`stages:` 加 `sync`；bot 信箱換成專案慣用的）。同時照檔內註解：
   - 所有 **deploy job 排除 `spec/v*`**（`- if: '$CI_COMMIT_BRANCH =~ /^spec\/v/'` → `when: never`），不然分支上的稿會蓋掉 `main` 的部署。
   - 既有的**排程 job 排除 `SPEC_BRANCH_CHECK == "1"`**，不然每日檢查會把它們一起叫醒。
5. **CI/CD 變數**（Settings → CI/CD → Variables，**全部 Masked、不勾 Protected**——勾了在非 protected 的 pipeline 讀不到）：

   | 變數 | 內容 |
   |---|---|
   | `SPEC_SYNC_PUSH_TOKEN` | Project Access Token，role **Developer**，scope `write_repository`；推 `spec/*` 分支與 release tag 用。**沒設 `SPEC_SYNC_API_TOKEN` 時它也拿來查 milestone**——這時還要加 `read_api`，而且這個 bot 要讀得到 `PROJECT`（工作項專案） |
   | `SPEC_SYNC_API_TOKEN` | 建議：工作項在**別的 GitLab 專案**時另設（scope `read_api`、讀得到該專案的 token；你不是那邊 Maintainer、開不了它的 project token 時用個人 token）。查 milestone 優先用它 |
   | `SPEC_SYNC_WEBHOOK` | 團隊頻道（聊天工具）的 incoming webhook，payload 格式依你的聊天工具調整 `spec_sync.py` 的 `notify()`；沒設＝只印 log（變數名可用 `WEBHOOK_ENV` 改） |

   `spec/*` 若設成 protected branch／protected tag，要允許該 token 的 bot 推。
6. **每日排程**：CI/CD → Schedules **新建一個**（例「spec-branch-check daily」），變數 `SPEC_BRANCH_CHECK=1`。不要掛在既有排程上（見坑 3）。
7. **開第一條分支**：`git push origin origin/main:refs/heads/spec/vX.Y.Z`（目前開發中的版本）。
8. **宣告**：repo `CLAUDE.md` 加一行（二擇一，字樣固定，SPEC 異動流程用它判斷）：
   ```
   版本分支同步：有（spec-branch-sync）
   版本分支同步：無（本專案無 milestone 版本）
   ```

## 更新腳本

1. **先改正本** `recipes/spec-version-branches/`，跑 `python3 -m unittest discover -s test -p 'test_spec_*.py'`（在該目錄），commit 正本所在的 repo。
2. 對每個宣告「有」的 repo 跑 `install.sh <repo>`，在該 repo commit（腳本改動也會被 sync 挑進各分支，分支上的 CI 才跟 `main` 一致）。
3. `recipes/spec-version-branches/check-spec-branches-sync.sh <repo>` 確認 exit 0。

**不准直接改 repo 裡的複本**——下次 install 會被蓋掉，push 後的 drift 檢查也會報。專案特有的行為只能放 `spec_branches_config.py`。複本若已被直接改過、而且改得對，先把改動搬回正本再 install。

## 鐵則與坑

1. **CI image 沒有 python3** → job 一跑就 `command not found`。用 `python:3.12-slim`，`before_script` 補 `apt-get install git`；`GIT_DEPTH: "0"`（要找 merge-base、讀分支上的 `-x` trailer），`PYTHONUTF8: "1"`。
2. **runner 的 `url.insteadOf` 把推送換成 job token → 403**。runner 在 git config 放了 `url."https://gitlab-ci-token:<job token>@host/".insteadOf "https://host/"`，job token 不能推。推送網址帶使用者名 `https://oauth2@host/<path>.git`（字首比對就不中），密碼由 credential helper 給 `SPEC_SYNC_PUSH_TOKEN`。腳本已這樣做；自己改推送邏輯時別改回去。
3. **既有排程會被一起叫醒**。`rules: if $CI_PIPELINE_SOURCE == "schedule"` 的 job 在新排程也會跑。每日檢查用獨立排程＋`SPEC_BRANCH_CHECK=1`，其他排程 job 加 `when: never` 排除它。
4. **永不把 spec 分支 merge 回 `main`**。分支是 `main` 的子集＋衝突解法，併回去會把解衝突的版本、revert 帶進 `main`。
5. **tag 名不能等於分支名**。用 `spec/vX.Y.Z-release`；同名時 `git push origin spec/vX.Y.Z` 會模稜兩可。
6. **手挑一律 `-x`**。sync 與 check 靠 `(cherry picked from commit <sha>)` 認「已同步」；沒有它，下次 sync 會再挑一次、check 會一直報缺。
7. **熱點共用檔會衝突**。跳過更晚版的 commit 後，後面改同一段的 commit 在分支上找不到上下文。產生出來的檔（索引、檢視）**一定要列進 `GENERATED`（並設好 `REGEN_CMD`）**——只撞它們時腳本會重產後繼續，不亮紅燈；手寫的熱點檔只能人解。
8. **deploy job 要跳過 `spec/v*`**。sync 推分支也會觸發 pipeline；沒排除 → 分支上的舊版稿覆蓋 `main` 的固定網址。
9. **衝突沒解之前每次都停在同一筆**，不會跳過它挑後面的。紅燈會一直紅到有人解，這是刻意的：跳過會讓分支少一段而沒人知道。
10. **GitLab API 失敗 → exit 1、什麼都不推**。不會把「查不到」當成「沒 milestone → 挑」。
11. **過渡期**：開始要求工作項之前的 commit 沒帶 issue 是正常的，不追溯——它們照「沒 issue＝挑」處理，release-check ④ 會列出但不擋。`TRACE_SINCE`／`UNTRACED_UPTO` 只讓輸出多一行提醒，不改判定。
12. **只同步 first-parent**。merge commit 當一個單位 `-m 1` 挑，工作項取 merge 訊息＋被併進來的所有 commit 的聯集（一張晚版就整個跳過）。

## 驗收 checklist

- [ ] `install.sh <repo>` 跑過，`check-spec-branches-sync.sh <repo>` exit 0
- [ ] `ci/spec_branches_config.py` 的 `PROJECT`／`ISSUE_RE`／`WATCH` 填好；有產生檔就填 `GENERATED`＋`REGEN_CMD`
- [ ] `ci/test/` 本機綠
- [ ] `.gitlab-ci.yml`：兩個 job 在、deploy job 排除 `spec/v*`、既有排程 job 排除 `SPEC_BRANCH_CHECK=1`
- [ ] 變數 Masked、非 Protected；`SPEC_SYNC_PUSH_TOKEN` 是 Developer＋`write_repository`（沒設 `SPEC_SYNC_API_TOKEN` 時另加 `read_api` 且讀得到工作項專案）
- [ ] 獨立排程帶 `SPEC_BRANCH_CHECK=1`；手動 Run 一次 → 只跑 `spec-branch-check`，沒叫醒別的 job
- [ ] 第一條 `spec/vX.Y.Z` 已開；push 一個 commit 到 `main` → `spec-branch-sync` 綠、分支多一筆帶 `-x` trailer 的 commit
- [ ] 🔴 **負向測試**：開一張掛**更晚** milestone 的票，push 一個引用它的 commit → 分支**沒有**挑它；再把票改回本版、push 任一 commit → 被挑進來
- [ ] 🔴 **衝突測試**（在測試分支／測試 repo）：製造一筆會衝突的 commit → job 紅、團隊頻道收到通知、分支沒被推半套
- [ ] repo `CLAUDE.md` 有 `版本分支同步：有（spec-branch-sync）` 那一行
- [ ] `release-check vX.Y.Z`（不帶 `--tag`）對目前版本跑一次，看得懂它列出的東西
