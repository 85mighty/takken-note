#!/usr/bin/env bash
# 宅建ベンチマークの収集 → 分析 → 結果をコミット (VPS で実行)
#   bash coaching/bench/run_bench.sh            … 全チャンネル
#   bash coaching/bench/run_bench.sh --only 棚田 … 1チャンネルだけ
# 結果は スタジオ（/studio/bench）で見られる。毎週自動で更新するなら:
#   ( crontab -l 2>/dev/null | grep -v run_bench ; echo "30 19 * * 5 cd $HOME/takken-note && bash coaching/bench/run_bench.sh >> coaching/bench/out/bench.log 2>&1" ) | crontab -
set -uo pipefail
cd "$(dirname "$0")/../.."
PY=python3; [ -x .venv/bin/python3 ] && PY=.venv/bin/python3

# yt-dlp は古いとすぐ取れなくなるので毎回更新
if [ -x .venv/bin/pip ]; then .venv/bin/pip install -q -U yt-dlp; else python3 -m pip install -q -U --user yt-dlp; fi

$PY coaching/bench/collect.py "$@"
$PY coaching/bench/analyze.py || exit 1

git add coaching/bench/out/*.json coaching/bench/out/*.csv coaching/bench/out/summary.* 2>/dev/null
if ! git diff --cached --quiet; then
  git commit -q -m "宅建ベンチマーク更新 $(date +%F)"
  git push -q 2>/dev/null && echo "→ GitHub に送信しました" || echo "→ コミットだけしました（GitHub への送信はできませんでした。結果はスタジオで見られます）"
fi
echo "結果: http://<VPSのアドレス>:8788/studio/bench"
