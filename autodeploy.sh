#!/usr/bin/env bash
# cron용 자동 배포: 원격 브랜치에 새 커밋이 있을 때만 deploy.sh 실행.
# 설치(1회):
#   ( crontab -l 2>/dev/null | grep -v autodeploy ; echo "*/5 * * * * $HOME/takken-note/autodeploy.sh" ) | crontab -
set -euo pipefail
cd "$(dirname "$0")"

# 중복 실행 방지
exec 9>/tmp/takken-autodeploy.lock
flock -n 9 || exit 0

BRANCH=$(git rev-parse --abbrev-ref HEAD)
git fetch origin "$BRANCH" -q
if [ "$(git rev-parse HEAD)" != "$(git rev-parse "origin/$BRANCH")" ]; then
  {
    echo "=== $(date '+%F %T') 새 커밋 감지 → 배포 ==="
    ./deploy.sh
  } >> autodeploy.log 2>&1
  tail -c 200000 autodeploy.log > autodeploy.log.tmp && mv autodeploy.log.tmp autodeploy.log
fi
