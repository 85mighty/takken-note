# -*- coding: utf-8 -*-
"""텔레그램 알림 (VPS). 키는 저장소에 넣지 않는다: ~/takken-note/.telegram_bot_token / .telegram_chat_id (gitignore).
  python3 notify.py --find           … VPS 안에 이미 있는 텔레그램 봇 토큰/chat_id 를 찾아 저장 (값은 화면에 안 냄)
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

# ── VPS 안에 이미 있는 봇 토큰 찾기 (다른 프로젝트의 .env·설정·서비스 파일·실행 중 프로세스 환경변수) ──
import re
TOK_RE = re.compile(rb"(?<![0-9A-Za-z])(\d{8,10}:[A-Za-z0-9_-]{35})(?![A-Za-z0-9_-])")
CHAT_RE = re.compile(rb"(?i)chat_?id[\"' ]*[:=][\"' ]*(-?\d{5,16})")
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "out", "_jobs", "site-packages", "dist-packages", "cache", ".cache", "wp-includes", "wp-admin", "uploads", "proc", "sys"}
EXTS = (".env", ".py", ".js", ".ts", ".json", ".sh", ".service", ".conf", ".cfg", ".ini", ".yaml", ".yml", ".toml", ".txt", ".php")

def _mask(t): return t.split(":")[0] + ":" + t.split(":")[1][:4] + "…"

def _candidates():
    roots = ["/root", "/home", "/opt", "/srv", "/var/www", "/etc/systemd/system", "/etc/environment", "/etc/default"]
    for r in roots:
        if os.path.isfile(r): yield r; continue
        for dp, dns, fns in os.walk(r):
            dns[:] = [d for d in dns if d not in SKIP_DIRS and dp.count(os.sep) - r.count(os.sep) < 5]
            for f in fns:
                if f.startswith(".env") or f.endswith(EXTS) or "telegram" in f.lower() or f.startswith(".telegram"):
                    p = os.path.join(dp, f)
                    try:
                        if os.path.getsize(p) < 512_000: yield p
                    except OSError: pass
    for d in os.listdir("/proc"):                                        # 실행 중인 봇이 환경변수로 들고 있는 경우
        if d.isdigit(): yield f"/proc/{d}/environ"
    for c in (["crontab", "-l"], ["pm2", "jlist"]):
        yield c

def find():
    """[(token, chat_id or None, source)] — 같은 파일 안의 chat_id 를 짝으로"""
    import subprocess
    found = {}
    for src in _candidates():
        try:
            if isinstance(src, list): data = subprocess.run(src, capture_output=True, timeout=15).stdout; name = " ".join(src)
            else: data = open(src, "rb").read(); name = src
        except Exception: continue
        toks = TOK_RE.findall(data)
        if not toks: continue
        chats = CHAT_RE.findall(data)
        for t in toks:
            t = t.decode()
            if t not in found or (found[t][0] is None and chats):
                found[t] = (chats[0].decode() if chats else None, name)
    return [(t, c, s) for t, (c, s) in found.items()]

def find_and_save():
    hits = find()
    if not hits: print("텔레그램 봇 토큰을 찾지 못했습니다 (python3 notify.py --setup 방식으로 직접 저장)"); return False
    ok = []
    for t, c, s in hits:
        try:
            with urllib.request.urlopen(f"https://api.telegram.org/bot{t}/getMe", timeout=15) as r: me = json.load(r)["result"]
            ok.append((t, c, s, me.get("username", ""))); print(f"  유효: @{me.get('username')} ({_mask(t)}) ← {s}" + (" · chat_id 있음" if c else ""))
        except Exception as e: print(f"  무효/만료: {_mask(t)} ← {s} ({str(e)[:60]})")
    if not ok: print("찾은 토큰이 모두 무효입니다"); return False
    ok.sort(key=lambda x: x[1] is None)                                  # chat_id 짝이 있는 것 우선
    t, c, s, u = ok[0]
    def save(name, v):
        p = os.path.join(ROOT, name); open(p, "w").write(v); os.chmod(p, 0o600)
    save(".telegram_bot_token", t)
    if not c:                                                            # 짝이 없으면 봇에게 온 메시지에서
        try:
            for x in reversed(_api("getUpdates").get("result", [])):
                m = x.get("message") or x.get("channel_post") or {}
                if (m.get("chat") or {}).get("id"): c = str(m["chat"]["id"]); break
        except Exception as e: print(f"  getUpdates 실패: {str(e)[:80]}")
    if c: save(".telegram_chat_id", c)
    print(f"저장: @{u} ({_mask(t)})  chat_id: {'있음' if c else '없음 → 봇에게 /start 보낸 뒤 python3 notify.py --setup'}")
    if c: print("테스트:", "OK" if send("✅ NIPPONリアル 스튜디오 알림이 연결되었습니다. (자동 제작 시작·완성·실패를 여기로 알려드립니다)") else "실패")
    return bool(c)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--setup": setup()
    elif len(sys.argv) > 1 and sys.argv[1] == "--find": find_and_save()
    elif len(sys.argv) > 1: print("OK" if send(" ".join(sys.argv[1:])) else "보내지 못함 (키 확인)")
    else: print(__doc__)
