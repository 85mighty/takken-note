#!/usr/bin/env bash
# VPS에서 실행하는 배포/업데이트 스크립트.
# 최초 1회는 README의 「VPS 배포」 절차대로 clone 후 이 스크립트를 실행.
set -euo pipefail
cd "$(dirname "$0")"

# 1) VPS에서 쌓인 오답 기록(takken_db.json)을 먼저 커밋해 두고 pull (기록 유실 방지)
if ! git diff --quiet -- takken_db.json; then
  git add takken_db.json
  git commit -m "VPS 오답 기록 $(date +%F_%H%M)"
fi
git pull --rebase

# 2) 의존성
pip3 install -q -r requirements.txt

# 3) 일본어 폰트 (PDF용) — 없으면 안내만
if ! fc-list 2>/dev/null | grep -qi "Noto Sans CJK"; then
  echo "※ PDF 일본어 폰트가 없습니다:  sudo apt-get install -y fonts-noto-cjk"
fi

# 4) PM2 기동/재기동
pm2 startOrRestart ecosystem.config.js
pm2 save

# 5) 기록 커밋을 원격에도 백업 (권한 없으면 건너뜀)
git push origin HEAD 2>/dev/null || echo "※ git push 생략 (원격 쓰기 권한 없음 — 로컬 이력만 유지)"

echo "완료 → http://<VPS-IP>:8788"
