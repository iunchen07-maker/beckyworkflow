#!/usr/bin/env bash
# 把 SPEC 版本分支 script 的正本裝進專案 repo（免 AI、零 token）。
#
# 用法: recipes/spec-version-branches/install.sh <repo>
#   複製（覆蓋）  spec_at.py、spec_sync.py            → <repo>/ci/
#                 test/test_spec_at.py、test_spec_sync.py、test_release_spec_change_mark.py → <repo>/ci/test/
#   只在缺時建立  <repo>/ci/spec_branches_config.py（從 spec_branches_config.example.py；已有就不碰）
#   印出剩下的手動步驟。不 commit、不 push。
# 裝完用同目錄的 check-spec-branches-sync.sh <repo> 確認與正本一致。
# exit 0 = 完成, 2 = 用法錯
set -eu

SRC="$(cd "$(dirname "$0")" && pwd)"
case "${1:-}" in
  ""|-h|--help) sed -n '2,10p' "$0"; [ -n "${1:-}" ] && exit 0 || exit 2 ;;
esac
REPO="$(cd "$1" 2>/dev/null && pwd)" || { echo "找不到 repo: $1" >&2; exit 2; }
[ -e "$REPO/.git" ] || { echo "$REPO 不是 git repo" >&2; exit 2; }

mkdir -p "$REPO/ci/test"
for f in spec_at.py spec_sync.py; do
  cp "$SRC/$f" "$REPO/ci/$f"
  echo "✓ ci/$f"
done
for f in test_spec_at.py test_spec_sync.py test_release_spec_change_mark.py; do
  cp "$SRC/test/$f" "$REPO/ci/test/$f"
  echo "✓ ci/test/$f"
done

CFG="$REPO/ci/spec_branches_config.py"
if [ -e "$CFG" ]; then
  echo "· ci/spec_branches_config.py 已存在，不覆蓋"
  NEW_CFG=0
else
  cp "$SRC/spec_branches_config.example.py" "$CFG"
  echo "✓ ci/spec_branches_config.py（從範本建立，要改成專案的值）"
  NEW_CFG=1
fi

cat <<EOF

剩下的手動步驟（$REPO）：
$( [ "$NEW_CFG" -eq 1 ] && echo "  0. 填 ci/spec_branches_config.py：PROJECT、ISSUE_RE、WATCH 必填，其餘看註解。" )
  1. 跑測試：python3 -m unittest discover -s ci/test -p 'test_*.py'
  2. CI：把 $SRC/gitlab-ci.snippet.yml 的兩個 job 貼進 .gitlab-ci.yml
     （已貼過且 job 指令沒變就跳過），並照檔內註解替部署 job／其他排程 job 加排除規則。
  3. CI/CD 變數：SPEC_SYNC_PUSH_TOKEN（Masked，Project Access Token，Developer：write_repository；
     沒設 SPEC_SYNC_API_TOKEN 時也拿來讀 milestone，這時還要 read_api＋能讀 issue 專案）、
     SPEC_SYNC_API_TOKEN（建議；issue 在別的專案時另設，read_api 即可）、
     SPEC_SYNC_WEBHOOK（Masked，聊天工具的 incoming webhook；變數名可在設定 WEBHOOK_ENV 改）。
  4. 排程：Pipeline schedules 建「spec-branch-check daily」，變數 SPEC_BRANCH_CHECK=1。
  5. 專案 CLAUDE.md 加一行宣告：版本分支同步：有（spec-branch-sync）
  6. 確認與正本一致：$SRC/check-spec-branches-sync.sh $REPO
EOF
