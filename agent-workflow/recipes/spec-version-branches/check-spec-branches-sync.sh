#!/usr/bin/env bash
# SPEC 版本分支 script 同步自檢（免 AI、零 token、唯讀）——
#   比對正本（本腳本所在的 recipes/spec-version-branches/）與專案 <repo>/ci/ 裡安裝的副本：
#   spec_at.py、spec_sync.py、test/test_spec_at.py、test/test_spec_sync.py、test/test_release_spec_change_mark.py
#   （ci/spec_branches_config.py 是專案自己的設定，不比對）
#
# 用法: recipes/spec-version-branches/check-spec-branches-sync.sh <repo>
# exit 0 = 一致, 1 = 有 drift, 2 = 未安裝（<repo>/ci/ 沒有任何一支）或用法錯
#
# drift 的修法：改正本（不要改專案副本）→ recipes/spec-version-branches/install.sh <repo>。
# 專案副本若有人直接改過、而且改得對，先把改動搬回正本再 install。
set -u

SRC="$(cd "$(dirname "$0")" && pwd)"
case "${1:-}" in
  ""|-h|--help) sed -n '2,11p' "$0"; [ -n "${1:-}" ] && exit 0 || exit 2 ;;
esac
REPO="$(cd "$1" 2>/dev/null && pwd)" || { echo "找不到 repo: $1" >&2; exit 2; }
name="$(basename "$REPO")"

# 正本路徑（相對 $SRC）→ 專案路徑（相對 $REPO）
PAIRS="spec_at.py:ci/spec_at.py
spec_sync.py:ci/spec_sync.py
test/test_spec_at.py:ci/test/test_spec_at.py
test/test_spec_sync.py:ci/test/test_spec_sync.py
test/test_release_spec_change_mark.py:ci/test/test_release_spec_change_mark.py"

if [ ! -f "$REPO/ci/spec_at.py" ] && [ ! -f "$REPO/ci/spec_sync.py" ]; then
  echo "· $name：未安裝 SPEC 版本分支 script（ci/spec_at.py、ci/spec_sync.py 都沒有）"
  exit 2
fi

same=0 drift="" missing=""
while IFS=: read -r src dst; do
  if [ ! -f "$REPO/$dst" ]; then missing="$missing $dst"; continue; fi
  if diff -q "$SRC/$src" "$REPO/$dst" >/dev/null 2>&1; then
    same=$((same + 1))
  else
    drift="$drift $dst"
  fi
done <<EOF
$PAIRS
EOF

[ -f "$REPO/ci/spec_branches_config.py" ] || missing="$missing ci/spec_branches_config.py"

if [ -z "$drift" ] && [ -z "$missing" ]; then
  echo "✓ $name：SPEC 版本分支 script $same 檔與正本一致"
  exit 0
fi

echo "✗ $name：SPEC 版本分支 script 與正本不一致（一致 $same 檔）"
[ -n "$missing" ] && echo "  缺檔:$missing"
for dst in $drift; do
  src="$(printf '%s\n' "$PAIRS" | awk -F: -v d="$dst" '$2==d{print $1}')"
  stat="$(diff "$SRC/$src" "$REPO/$dst" | grep -c '^[<>]')"
  echo "  drift: $dst（$stat 行不同；< 正本 / > 專案）"
  diff "$SRC/$src" "$REPO/$dst" | grep '^[<>]' | head -6 | sed 's/^/      /'
done
echo "  修法：改正本 $SRC → $SRC/install.sh $REPO"
exit 1
