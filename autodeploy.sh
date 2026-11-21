#!/usr/bin/env bash
# cron용 자동 배포: 원격 브랜치에 새 커밋이 있을 때만 deploy.sh 실행.
# 설치(1회):
#   ( crontab -l 2>/dev/null | grep -v autodeploy ; echo "*/5 * * * * $HOME/takken-note/autodeploy.sh" ) | crontab -
set -euo pipefail
cd "$(dirname "$0")"

# 중복 실행 방지
exec 9>/tmp/takken-autodeploy.lock
flock -n 9 || exit 0

BRANCH=$(git config takken.branch || git rev-parse --abbrev-ref HEAD)
if [ "$BRANCH" = "HEAD" ]; then BRANCH=claude/epic-mccarthy-gvvh3q; fi   # ブランチから外れていても追いかける先を固定
git config takken.branch "$BRANCH"
git fetch origin "$BRANCH" -q
if [ "$(git rev-parse HEAD)" != "$(git rev-parse "origin/$BRANCH")" ] || [ -d .git/rebase-merge ] || ! git symbolic-ref -q HEAD >/dev/null; then
  {
    echo "=== $(date '+%F %T') 새 커밋 감지 → 배포 ==="
    ./deploy.sh
  } >> autodeploy.log 2>&1
  tail -c 200000 autodeploy.log > autodeploy.log.tmp && mv autodeploy.log.tmp autodeploy.log
fi

# 예약 제작 (coaching/yt/jobs/*.json 의 "at" 시각이 지난 것): 새 커밋이 없어도 5분마다 확인해서 시작
if ls coaching/yt/jobs/*.json >/dev/null 2>&1 && [ -x .venv/bin/python3 ] && .venv/bin/python3 coaching/yt/autobuild.py --due 2>/dev/null; then
  mkdir -p coaching/yt/out/_jobs
  echo "=== $(date '+%F %T') 예약 제작 시작 ===" >> autodeploy.log
  setsid nohup .venv/bin/python3 coaching/yt/autobuild.py >> coaching/yt/out/_jobs/autobuild.log 2>&1 9>&- < /dev/null &
fi
