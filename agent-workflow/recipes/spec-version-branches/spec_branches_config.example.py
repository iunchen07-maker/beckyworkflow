# -*- coding: utf-8 -*-
"""
spec_branches_config — SPEC 版本分支 script（spec_at.py／spec_sync.py）的專案設定。

這是範本。install.sh 會在專案沒有 ci/spec_branches_config.py 時從這裡複製一份（已有就不碰），
之後只改專案那份；spec_at.py／spec_sync.py 本身各專案一律不改（正本在本 repo 的
recipes/spec-version-branches/，改正本再 install.sh）。

這個檔是普通 Python：可以 import 專案自己的模組，讓同一個值只有一個出處
（例：WATCH／EXEMPT 直接從專案的 commit-issue 檢查 import）。本檔所在目錄已在 sys.path。
環境變數 SPEC_BRANCHES_CONFIG 可指到別的設定檔路徑。

必填：PROJECT、ISSUE_RE、WATCH。其餘可省（省略＝下面寫的預設值）。
"""
import re

# ── 必填 ─────────────────────────────────────────────────────

# issue（milestone）所在的 GitLab 專案路徑。milestone 標題要是版本號 vX.Y.Z（v 可省）；
# 其他標題（Backlog、補漏…）一律當「不是版本」——其 issue 的 commit 不會被跳過或還原。
PROJECT = "my-org/todo-app"

# commit 訊息怎麼認 issue：第一個群組＝issue 編號。字串或已 compile 的 regex 都可。
# 建議：認全路徑＋短式、不認裸 `#N`（常是別的專案的編號）、編號要完整（短編號不吃到更長編號的前綴）。
ISSUE_RE = re.compile(r"(?<![\w/])(?:my-org/)?todo-app#(\d+)(?!\d)")

# SPEC 範圍（spec_at 只還原動到這些路徑的 commit）：路徑前綴 tuple。
# 若專案已有 commit-issue 檢查，建議直接 import 那邊的值，不要抄一份。
WATCH = ("Spec/",)

# ── 選填 ─────────────────────────────────────────────────────

# SPEC 範圍內要排除的前綴（例：放在 Spec/ 底下的工具目錄）。預設 ()。
EXEMPT = ()

# spec_at 印「改到的 § 節」時認哪種標題：第一個符合的往上找。要有具名群組 `id`
# （沒有就取最後一個群組）作節名。None＝只用最近的 Markdown 標題。預設 None。
# 例（US 編號標題）：r"^(#{2,6})\s+(?:§\s*)?(?P<id>US-[A-Za-z0-9.]+)(?=\s|$)"
HEADING = None

# 產生的檔案（不是人寫的）：還原／cherry-pick 衝突只落在這些路徑前綴底下時，
# 不算衝突，改在結果樹跑 REGEN_CMD 重產。預設 []（沒有產生檔）。
GENERATED = []

# 重產指令（argv 清單），在結果樹的根目錄跑。{root}＝結果樹絕對路徑、{python}＝目前的 python。
# 只有 GENERATED 非空才會用到。預設 []。
# 例：["{python}", "ci/regen_index.py", "--root", "{root}", "views"]
REGEN_CMD = []

# 版本分支＝<SPEC_BRANCH_PREFIX>X.Y.Z；在分支上打 <分支名><RELEASE_TAG_SUFFIX> tag ＝該版關閉。
SPEC_BRANCH_PREFIX = "spec/v"
RELEASE_TAG_SUFFIX = "-release"

# 追溯起點：TRACE_SINCE（YYYY-MM-DD）以前的 commit 不一定帶 issue；版本 ≤ UNTRACED_UPTO（tuple）
# 的 spec_at 結果不完整。只影響提醒文字。預設 None（不提醒）。
TRACE_SINCE = None
UNTRACED_UPTO = None          # 例：(1, 9, 3)

# release-check ②：issue 沒有 commit 時，描述或任一則非系統留言符合這個 regex ＝「SPEC 不用改」，算有交代。
# None＝不接受這種交代（每張都要有 commit）。
NO_CHANGE_MARK = r"SPEC 不用改，§"

# release-check ②：issue 沒有帶它的 commit 時，描述或任一則非系統留言有符合這個 regex 的那一行，
# 且該行標記之後的任一個 `commit <sha>`（7–40 hex）是分支 tip 能到、沒被撤的 commit ＝「SPEC 有改」，算有交代。
# commit 本身不必帶票。例：「SPEC 變更：commit abc1234（…）；mockup：commit def5678」。None＝不接受。
SPEC_CHANGE_MARK = r"SPEC 變更："

# --notify 用的聊天工具 incoming webhook 放在哪個環境變數（CI/CD 變數，Masked）。
WEBHOOK_ENV = "SPEC_SYNC_WEBHOOK"
