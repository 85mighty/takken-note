# -*- coding: utf-8 -*-
"""텔레그램 알림 (VPS). 키는 저장소에 넣지 않는다: ~/takken-note/.telegram_bot_token / .telegram_chat_id (gitignore).
  python3 notify.py --setup          … 봇에게 아무 메시지나 보낸 뒤 실행 → chat_id 를 찾아 .telegram_chat_id 에 저장하고 테스트 메시지
  python3 notify.py "보낼 문장"      … 바로 보내기
  from notify import send; send("…")  … 코드에서 (키가 없으면 조용히 아무것도 안 함)
"""
import json, os, sys, urllib.parse, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
STUDIO = os.environ.get("STUDIO_URL", "http://66.245.217.115:8789")

def _read(name, env):
    if os.environ.get(env): return os.environ[env].strip()
    p = os.path.join(ROOT, name)
    return open(p).read().strip() if os.path.exists(p) else ""

def token(): return _read(".telegram_bot_token", "TELEGRAM_BOT_TOKEN")
def chat_id(): return _read(".telegram_chat_id", "TELEGRAM_CHAT_ID")

def _api(method, **params):
    data = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(f"https://api.telegram.org/bot{token()}/{method}", data=data, timeout=20) as r:
        return json.load(r)

def send(text, silent=False):
    """보내고 True/False. 키가 없거나 실패해도 예외를 던지지 않는다 (작업을 멈추지 않도록)"""
    if not token() or not chat_id(): return False
    try:
        _api("sendMessage", chat_id=chat_id(), text=text[:4000], disable_web_page_preview="true", disable_notification="true" if silent else "false")
        return True
    except Exception as e:
        print(f"  텔레그램 알림 실패: {str(e)[:120]}", flush=True); return False

def studio_link(name): return f"{STUDIO}/studio/v/{name}"

def setup():
    if not token():
        sys.exit("먼저 .telegram_bot_token 을 저장하세요 (BotFather 가 준 토큰)")
    r = _api("getUpdates")
    chats = []
    for u in r.get("result", []):
        m = u.get("message") or u.get("channel_post") or {}
        c = m.get("chat") or {}
        if c.get("id") and c["id"] not in [x[0] for x in chats]: chats.append((c["id"], c.get("username") or c.get("title") or c.get("first_name") or ""))
    if not chats:
        sys.exit("봇에게 아직 메시지가 없습니다. 텔레그램에서 봇을 열고 /start 를 보낸 뒤 다시 실행하세요")
    cid = chats[-1][0]
    p = os.path.join(ROOT, ".telegram_chat_id"); open(p, "w").write(str(cid)); os.chmod(p, 0o600)
    print(f"chat_id 저장: {cid} ({chats[-1][1]})")
    print("테스트:", "OK" if send("✅ NIPPONリアル 스튜디오 알림이 연결되었습니다.") else "실패")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--setup": setup()
    elif len(sys.argv) > 1: print("OK" if send(" ".join(sys.argv[1:])) else "보내지 못함 (키 확인)")
    else: print(__doc__)
