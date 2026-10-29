#!/usr/bin/env bash
# VPS에서 실행하는 배포/업데이트 스크립트.
# 최초 1회는 README의 「VPS 배포」 절차대로 clone 후 이 스크립트를 실행.
set -euo pipefail
cd "$(dirname "$0")"

# 1) VPS에서 쌓인 오답 기록(takken_db.json)을 먼저 커밋해 두고 pull (기록 유실 방지)
#    スタジオ(/studio)で直した動画の定義(coaching/yt/specs)も同じく先にコミット
#    スタジオで作ったもの（台本・テーマ候補・URL台帳・字幕スタイル・イラスト・ブログ原稿）も同じく
KEEP="takken_db.json coaching/yt/specs coaching/yt/topics.json coaching/yt/videos.json coaching/yt/sub_style.json coaching/yt/illust coaching/blog"
for p in $KEEP; do [ -e "$p" ] && git add -A -- "$p"; done   # 없いパスが混ざると全部失敗するので1つずつ
if ! git diff --cached --quiet; then
  git commit -m "VPS 오답 기록・スタジオ編集 $(date +%F_%H%M)"
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
if ! command -v pdftoppm >/dev/null; then
  echo "※ スタジオの動画書き出しに pdftoppm が必要です:  sudo apt-get install -y poppler-utils"
fi
if ! fc-list 2>/dev/null | grep -qi "Noto Sans CJK"; then
  echo "※ PDF 일본어 폰트가 없습니다:  sudo apt-get install -y fonts-noto-cjk"
fi

# 4) 暗記ノート 音声 생성 (변경 없으면 즉시 종료). 엔진 선택:
#    .tts_engine 파일에 google / gtts / eleven 를 쓰면 그것을 사용.
#    없으면: .google_api_key 가 있으면 google → ElevenLabs 키가 있으면 eleven → 둘 다 없으면 건너뜀.
ENGINE=$(cat .tts_engine 2>/dev/null | tr -d '[:space:]' || true)
if [ -z "$ENGINE" ]; then
  if [ -s .google_api_key ]; then ENGINE=google
  elif grep -q '"voice": "Google' static/audio/toshi_tracks.json 2>/dev/null; then
    # 現在の音声が Google 製 → キーが無ければ ElevenLabs で上書きせず、そのまま維持
    echo "※ 音声は Google 製のまま維持 (再生成するには .google_api_key を置くか .tts_engine に eleven と書く)"
  elif .venv/bin/python3 - <<'PY'
import sys; sys.path.insert(0, "coaching")
from make_audio_eleven import find_api_key
sys.exit(0 if find_api_key() else 1)
PY
  then ENGINE=eleven; fi
fi
if [ -n "$ENGINE" ] && [ -z "$(git status --porcelain -- static/audio)" ]; then
  if ! command -v ffmpeg >/dev/null; then
    (apt-get install -y ffmpeg || sudo -n apt-get install -y ffmpeg) >/dev/null 2>&1 || echo "※ ffmpeg 설치 실패 → sudo apt-get install -y ffmpeg"
  fi
  if command -v ffmpeg >/dev/null; then
    ok=1
    for subj in toshi kenki; do
      case "$ENGINE" in
        google) .venv/bin/python3 coaching/make_audio_google.py --subject "$subj" --engine cloud || ok=0 ;;
        gtts)   .venv/bin/pip install -q gTTS; .venv/bin/python3 coaching/make_audio_google.py --subject "$subj" --engine gtts || ok=0 ;;
        eleven) .venv/bin/python3 coaching/make_audio_eleven.py --subject "$subj" || ok=0 ;;
        *) echo "※ .tts_engine の値が不正: $ENGINE (google/gtts/eleven)"; ok=0 ;;
      esac
    done
    if [ "$ok" = 1 ]; then
      if ! git diff --quiet -- static/audio || [ -n "$(git ls-files --others --exclude-standard static/audio)" ]; then
        git add static/audio
        git commit -qm "音声 生成 ($ENGINE) $(date +%F_%H%M)"
      fi
    else
      echo "※ 음성 생성 실패 (위 메시지 참고) → 기존 음성 유지"
    fi
  fi
fi

# 4.6) takken.ekunblog.com (이 서버의 WordPress) 조정 플러그인 — 코멘트 없음·목록 행 형식
WPD=/var/www/takken.ekunblog.com/html/wp-content
if [ -d "$WPD" ]; then
  mkdir -p "$WPD/mu-plugins" && cp coaching/blog/wp/takken-tweaks*.php "$WPD/mu-plugins/" && echo "takken-tweaks 플러그인 반영"
fi

# 5) PM2 기동/재기동
pm2 startOrRestart ecosystem.config.js
pm2 save

# 6) 기록/음성 커밋을 원격에도 백업 (권한 없으면 건너뜀)
git push origin HEAD 2>/dev/null || echo "※ git push 생략 (원격 쓰기 권한 없음 — 로컬 이력만 유지)"

echo "완료 → http://<VPS-IP>:8788"
