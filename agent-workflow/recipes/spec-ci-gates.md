# SPEC 品質閘門（確定性 CI lint，非 LLM）

## 這是什麼/何時用

把規則書寫了、但靠模型記憶與人工 review 守不住的 SPEC／mockup 紀律，改成**每次 push 都跑的機械檢查**。適用有「SPEC md＋HTML 設計稿＋決策檔」的專案。

規則本身住 [`../workflow/phase-0-spec-update.md`](../workflow/phase-0-spec-update.md)（§SPEC 生命週期）、[`../workflow/SPEC_NUMBERING_RULES.md`](../workflow/SPEC_NUMBERING_RULES.md)、[`../workflow/phase-1-product-design.md`](../workflow/phase-1-product-design.md)（標注鐵則）；本配方只講**怎麼裝、怎麼調、會踩什麼**。

**共同原則**：

1. **確定性、零 token**：純 Python 標準函式庫＋正則，不呼叫 LLM。
2. **一支腳本兩個呼叫點**：本機 hook 與 CI 跑同一支，規則不會有兩份。
3. **例外當資料**：行內 pragma、waiver、baseline，不改 code。
4. **增量門與全檔門分清**：只看 diff 的門不追溯存量；全檔門要先清乾淨或有 baseline。
5. **硬門一上線就要是綠的**。上線即一片紅 → 會被整批豁免，門就死了。存量走 baseline，只縮不長。

## 九項檢查

| job | 查什麼 | 擋／報／試行 | 腳本 |
|---|---|---|---|
| `glossary-lint` | Glossary 禁用名詞出現在 SPEC 或定案稿 | **擋**（`--banned`）；`--structure`、`--coverage` 只報 | [`glossary_lint.py`](spec-ci-gates/glossary_lint.py) |
| `prose-lint` | 正文的絕對日期、討論過程詞、歷程／延後字樣、理由段、不合格的豁免標記 | **擋**（新增行＋全庫對 baseline＋baseline 長大） | [`prose_lint.py`](spec-ci-gates/prose_lint.py) |
| `prose-lint`（同 job） | 改寫時限定詞變少、§ID 消失、數字改變 | 報（永遠 exit 0） | [`qualifier_guard.py`](spec-ci-gates/qualifier_guard.py) |
| `numbering-lint` | 同檔重號、AC 缺號／重複、保留編號被重用 | **擋**；標題排列沒遞增只報（`--strict-order` 才擋） | [`numbering_lint.py`](spec-ci-gates/numbering_lint.py) |
| `notification-lint` | 通知信總表中英不對稱、同目的地連結文字不一 | 報（永遠 exit 0） | [`notification_lint.py`](spec-ci-gates/notification_lint.py) |
| `mockup-lint` | 規格落畫面（R1）、視覺紅線（R2）、三屬性（R3）、無依據元素（R5）、延後功能未標（R6） | R1–R3、R6、baseline 長大 **擋**；R5 只報（`R5_BLOCKS = True` 才擋） | [`mockup_lint.py`](spec-ci-gates/mockup_lint.py) |
| `commit-issue-check` | 動到 SPEC／mockup 的 commit 沒寫工作項全路徑 | **試行**（`allow_failure`）；多工作項、缺 `Verified-by:` 只報 | [`commit_issue_check.py`](spec-ci-gates/commit_issue_check.py) |
| `decision-schema-check` | 決策檔必填鍵、id 唯一、`changes` 對得到 SPEC、推翻關係一致；新增／改正文者的固定四段與 8 KB | **擋** | [`decisions.py`](spec-ci-gates/decisions.py) `check` |
| `decision-views-check` | `Spec/memory/index/` 與決策檔一致 | **試行**（`allow_failure`） | [`decisions.py`](spec-ci-gates/decisions.py) `views --check` |

`spec-grep.sh`、`closed-claim-lint.sh` 這兩支手動複掃工具（未包含於此 repo）。

## 安裝

1. **複製腳本**（在本 repo 根目錄；`$REPO`＝你的專案）。位置固定，不能改——腳本用它找專案根目錄與彼此 import：

   | 來源 | 裝到 | 一起裝 |
   |---|---|---|
   | `recipes/spec-ci-gates/glossary_lint.py`、`prose_lint.py`、`qualifier_guard.py`、`numbering_lint.py`、`notification_lint.py`、`mockup_lint.py`、`commit_issue_check.py` | `<repo>/Spec/.convert_tools/` | `prose_lint` 需要 `glossary_lint` |
   | `recipes/spec-ci-gates/decisions.py` | `<repo>/ci/` | 需要 `numbering_lint` |
   | [`gitlab-ci.snippet.yml`](spec-ci-gates/gitlab-ci.snippet.yml) | 貼進 `<repo>/.gitlab-ci.yml` | `stages:` 加 `lint` |
   | [`claude-settings.hook.json`](spec-ci-gates/claude-settings.hook.json) | 併進 `<repo>/.claude/settings.json` | 需要 `jq` |

   ```bash
   mkdir -p "$REPO/Spec/.convert_tools" "$REPO/ci"
   cp recipes/spec-ci-gates/*.py "$REPO/Spec/.convert_tools/"
   mv "$REPO/Spec/.convert_tools/decisions.py" "$REPO/ci/"
   ```
2. **改常數**：每支檔頭的「專案常數」都是待辦清單 App 的範例值，一律換成你的（見下表）。專案用不到的檢查整支不裝、job 刪掉。
3. **跑 checklist**（文末）。測試 [`test_spec_ci_gates.py`](spec-ci-gates/test/test_spec_ci_gates.py) 驗的是範例常數，在本 repo 跑，不用裝進專案：
   ```bash
   (cd recipes/spec-ci-gates && python3 -m unittest discover -s test -p 'test_*.py')
   ```

### 要換的常數

| 腳本 | 常數 |
|---|---|
| `glossary_lint.py` | `GLOSSARY`、`DEFAULT_PATHS`、`BANNED_HEADER`／`CORE_HEADER`（要跟 Glossary 標頭逐字相同）、`TABLE_HEADERS`、`CONTEXTUAL_EXTRA`、`EXCLUDE_*` |
| `prose_lint.py` | `SCAN_ROOT`、`PEOPLE`（不該進正文的人名）、`EXCLUDE_*`。`DEFERRAL_WORDS` 跟規則書清單一致，規則書改了才改 |
| `qualifier_guard.py` | `SCAN_ROOT`、`SPEC_ID` |
| `numbering_lint.py` | `US_ID`、`CATALOG_ID`／`CATALOG_FILE_SUBSTR`（目錄列編號、放在哪類檔）、`AC_SECTION`／`AC_RE` |
| `notification_lint.py` | `DEFAULT_TARGETS`、`ROW_ID`、`BODY_COL`（內文在第幾欄） |
| `mockup_lint.py` | `SCAN_DIRS`／`FINAL_DIR`／`WIP_DIR`、`STATE_ENUMS`、`DISCUSSION_WORDS`、`WHITELIST_CLASSES`／`META_BG`（meta 層）、`BANNED_CSS`／`BANNED_COLORS`／`LEGAL_RADII`、`SPEC_REF_RE`、`R5_BLOCKS` |
| `commit_issue_check.py` | `PROJECT`、`WATCH`、`EXEMPT` |
| `decisions.py` | `PROJECT`、`CATALOG_TITLE_COL`；編號規則 import 自 `numbering_lint` |

## CI 片段說明

[`gitlab-ci.snippet.yml`](spec-ci-gates/gitlab-ci.snippet.yml)：

- **`PYTHONUTF8: "1"`** 不能省：slim image 預設 locale 處理不了中文檔名與內容。
- **`GIT_DEPTH: "50"`＋安裝 git** 只有看歷史的四個 job 要（`prose-lint`、`mockup-lint`、`commit-issue-check`、`decision-schema-check`）。
- **BASE 的 fallback 不能省**：`CI_COMMIT_BEFORE_SHA` 在 branch 首次 push 是全 0，force-push 後可能指到不存在的 commit。`prose_lint --diff` 遇到比不到的 BASE 會直接失敗（不靜默放行），所以 job 先驗 BASE 存在。
- **比不到 BASE 時的略過**：`commit-issue-check` 連 default branch 也比不到就印「無可比對 base，跳過」並 exit 0——那次 push **沒有檢查**，綠燈不代表有帶工作項。`prose-lint` 退成只跑全掃、`mockup-lint` 略過 baseline 比對、`decision-schema-check` 不查新增檔的固定段落。
- **`--selftest` 排在 `--all` 前面**：規則改壞要先炸在自測，不要拿壞規則誤判一整批稿。
- **試行** job 用 `allow_failure: true`；團隊看一陣子沒有誤報再拿掉。
- `lint` 排在 deploy 之前；排程 pipeline 不重複 lint。

## 本機 hook

[`claude-settings.hook.json`](spec-ci-gates/claude-settings.hook.json)：Claude Code 存 `HTML設計稿/*.html` 後立刻跑 `mockup_lint.py --file`。往上找到有 `Spec/.convert_tools/mockup_lint.py` 的資料夾為止，不寫死絕對路徑，worktree 也能用。一定要 `exit 2`——`exit 2` 才會把 stderr 回饋給 Claude 讓它自己修。

## 例外的格式

這些檔案都不附，**缺檔＝空清單**；需要時才建，放 `Spec/.convert_tools/`。

| 檔／標記 | 格式 | 規矩 |
|---|---|---|
| 行內 pragma（prose） | `<!-- prose-lint: allow <example\|ui-copy\|literal-term>: <理由> -->` | 類別只收這三種，理由必填、不得拿歷程當理由；不合格＝P1 |
| 行內 pragma（glossary） | `<!-- glossary-lint: allow <詞> -->`／`allow-line` | 只給「在說明這個詞」的行 |
| `glossary_lint_waivers.txt` | 每行 `相對路徑:行號\|*:詞`，`#` 註解 | 只收寫不了行內註解的（如 HTML `<title>`），一律用 `*`——行號會漂移，豁免會落到別行 |
| `prose_lint_baseline.txt` | 每行 `路徑<TAB>sha1(正規化行文)<TAB>規則` | 只由 `--write-baseline` 產生、只縮不長（`--check-baseline-shrink` 會擋）；行一改就失效 |
| `mockup_lint_baseline.txt` | 每行一個相對路徑，`#` 註解 | 整檔豁免 R1–R3／R5，只收 `定案/` 舊稿，列了其他路徑就直接失敗；只縮不長（`--check-baseline-shrink` 會擋）；R6 豁免不到 |

## 各檢查要點

**glossary**：Glossary 兩個表，`## 核心名詞定義`（中文｜英文｜定義）與 `## 禁用名詞對照表`（❌ 禁用｜✅ 改用｜說明）。只有**可 grep 的裸詞**進硬門；帶語境（`關閉（指任務時）`）或敘述句（`把「完成」當成封存`）的列自動降為只報，括號在講出處（`task_closed（舊值）`）的仍是硬門。欄位格式不同 → 改 parser，不是改常數。

**numbering**：照 [`SPEC_NUMBERING_RULES.md`](../workflow/SPEC_NUMBERING_RULES.md)。排列沒遞增是既有債務，§3.5 規定回報、不擋，所以預設只報。退役的 AC 要留 `- **AC-2**：已退役（保留編號）`；延後的編號由 `Spec/Deferred/*.md` 檔頭 `保留編號：` 行認得。跨檔重號、H3 跳號不查，由 spec-writer／verifier 照規則書 §五檢查。

**mockup**：R1 只看可見文字，規格放 `data-*` 不算。meta 層（規格資訊列、DEMO 切換列、出處 chip、活待辦標記）靠 `WHITELIST_CLASSES` 豁免，可帶單層前綴（`t1-case-note`）。JS 用字串拼的標記也驗（`·js`）。R5 要求 `data-spec` 引得出節號，不然掛 `data-chrome="true"`；規則書沒有明文要求，預設只報。`--audit <檔>` 列出每個元素引用的節號，附在提案給 PM 目視——引到別的畫面的節號，機器擋不掉。

**decisions**：欄位照 [`phase-0-spec-update.md`](../workflow/phase-0-spec-update.md) §SPEC 生命週期 3。`milestone` 鍵要在、值留空，由 `stamp-milestone` 填。額外可用的鍵：`supersedes_partial`（只推翻一部分，對方維持 active）、`kind: non-spec`（不改 SPEC 規則的決策，`changes` 可空）；`changes` 另收 `原則-N` 與 `<SPEC 檔名>#<標題>`。`Spec/memory/` 一份 `id: D-NNNN` 都沒有時整支跳過——**跳過不等於有守**，第一份決策檔寫好後要確認輸出不是「跳過」。

```bash
python3 ci/decisions.py why US-T1.1            # 這節現行決策＋推翻鏈
python3 ci/decisions.py list --since 1999-01-01
python3 ci/decisions.py views                  # 重產 Spec/memory/index/
python3 ci/decisions.py next-id
python3 ci/decisions.py stamp-milestone --write  # 需 SPEC_SYNC_API_URL／SPEC_SYNC_API_TOKEN
```

用[版本分支](spec-version-branches.md)的專案：`ci/spec_branches_config.py` 的 `WATCH`／`EXEMPT` 跟 `commit_issue_check.py` 保持一致；`Spec/memory/index/` 列進 `GENERATED`。

## 鐵則與坑

1. **綠燈不等於有在守**。豁免區開太大、硬門詞永遠不命中，都會回報 0 違規，比沒裝更危險（以為有人守）。一定做負向測試，違規要塞在**檔尾**。
2. **豁免綁在內容本體，不要「跳到下一個標題為止」**。那一段若在檔尾，之後新增的全部不受守。
3. **同義詞分隔要切全形「／」**。只切半形會產生永遠不命中的死詞。
4. **baseline 用行文雜湊，不用行號**。行號一移，豁免會放過新寫的字。
5. **寬樣式不收**。新增 prose 子樣式前先量現行正文命中數，要 0 才收；「不再／原本／改為」這類誤判高。領域用語撞到清單 → 行內 pragma。
6. **R2 只看樣式宣告**：說明文字要能談「不准用陰影」而不被當成用了。未定義的 `var()` 照樣亮燈。
7. **R5 不做祖先繼承**：容器引了節號就讓子元素免驗，等於容器的依據罩住任何塞進去的鈕。
8. **信件總表不設硬門、不設句型白名單**：草稿文案會一直改，硬門只會換來整批豁免。
9. **`data-*` 屬性值 glossary 也掃得到**（它逐行掃 HTML）。命中就改用正式詞，真的不能改才進 waiver；不要整批跳過屬性。

## 啟用前 checklist

- [ ] 適用的腳本在 `Spec/.convert_tools/` 與 `ci/`，檔頭常數都換成自己的值（搜 `my-org/todo-app` 應無結果）
- [ ] `mockup_lint.py --selftest` 綠。改了 R2 常數、`STATE_ENUMS` 或白名單，自測案例（`R2_SELFTEST`／`SELFTEST_CASES`）要一起改
- [ ] 每個硬門本機都是綠的：`glossary_lint.py --banned`、`prose_lint.py --all`、`numbering_lint.py`、`mockup_lint.py --all`／`--deferred`、`decisions.py check`。不綠 → 先清或 baseline，不要帶紅燈上線
- [ ] `prose_lint.py --diff HEAD~1` 跑得動（確認 `glossary_lint.py` 也裝了）
- [ ] `.gitlab-ci.yml`：用得到的 job 都在、`PYTHONUTF8`／`GIT_DEPTH` 都在；push 一個 branch → lint stage 綠（試行 job 可黃）
- [ ] hook：在 `討論中/` 的稿寫一行可見文字 `§US-T1.1`，存檔應被擋
- [ ] 🔴 **負向測試**（在測試 branch）：往一支 SPEC 的**檔尾**加三行——一個禁用名詞、一句「暫不提供」、一個重複的 `## US-…` 標題；決策檔的 `changes` 加一個不存在的 §ID；定案稿檔尾加一個延後功能關鍵詞。push → 對應的 job 逐一變紅、行號指得到，確認後整批撤掉
- [ ] 🔴 **豁免也要驗**：`已移至 Deferred/…（保留編號）` 的佔位列、合格 pragma 的行仍然放行
