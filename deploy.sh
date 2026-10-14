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
git pull --rebase --autostash

# 2) 비밀번호 파일 확인
if [ ! -s .takken_password ]; then
  echo "※ 경고: .takken_password 파일이 없습니다 → 로그인 없이 전체 공개 상태로 뜹니다."
  echo "   설정:  echo '원하는비밀번호' > .takken_password   후 ./deploy.sh 재실행"
fi

# 3) 의존성 — 프로젝트 전용 venv (PEP 668 externally-managed 환경 대응)
if [ ! -d .venv ]; then
  python3 -m venv .venv || {
    echo "venv 생성 실패 → 먼저:  apt-get install -y python3-venv  후 ./deploy.sh 재실행"
    exit 1
  }
fi
.venv/bin/pip install -q -r requirements.txt

# 3) 일본어 폰트 (PDF용) — 없으면 안내만
if ! fc-list 2>/dev/null | grep -qi "Noto Sans CJK"; then
  echo "※ PDF 일본어 폰트가 없습니다:  sudo apt-get install -y fonts-noto-cjk"
fi

# 4) ElevenLabs 음성: API 키(환경변수 ELEVEN_API_KEY 또는 .eleven_api_key 파일)가 있으면 생성해서 커밋 (변경 없으면 즉시 종료)
if [ -z "$(git status --porcelain -- static/audio)" ] && \
   .venv/bin/python3 - <<'PY'
import sys; sys.path.insert(0, "coaching")
from make_audio_eleven import find_api_key
sys.exit(0 if find_api_key() else 1)
PY
then
  if ! command -v ffmpeg >/dev/null; then
    (apt-get install -y ffmpeg || sudo -n apt-get install -y ffmpeg) >/dev/null 2>&1 || echo "※ ffmpeg 설치 실패 → sudo apt-get install -y ffmpeg"
  fi
  if command -v ffmpeg >/dev/null; then
    ok=1
    for subj in toshi kenki; do
      .venv/bin/python3 coaching/make_audio_eleven.py --subject "$subj" || ok=0
    done
    if [ "$ok" = 1 ]; then
      if ! git diff --quiet -- static/audio || [ -n "$(git ls-files --others --exclude-standard static/audio)" ]; then
        git add static/audio
        git commit -qm "ElevenLabs 音声 生成 $(date +%F_%H%M)"
      fi
    else
      echo "※ ElevenLabs 음성 생성 실패 (위 메시지 참고) → 기존 음성 유지"
    fi
  fi
fi

# 5) PM2 기동/재기동
pm2 startOrRestart ecosystem.config.js
pm2 save

# 6) 기록/음성 커밋을 원격에도 백업 (권한 없으면 건너뜀)
git push origin HEAD 2>/dev/null || echo "※ git push 생략 (원격 쓰기 권한 없음 — 로컬 이력만 유지)"

echo "완료 → http://<VPS-IP>:8788"
