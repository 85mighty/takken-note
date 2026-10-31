# -*- coding: utf-8 -*-
"""完成した動画を YouTube に上げる（seido-tube の 07_upload.py と同じ仕組み）。URL は spec と台帳に自動で入る。
  python3 yt_upload.py --auth                      … 最初の1回: ブラウザで NIPPONリアル のアカウントを許可
  python3 yt_upload.py specs/R8_xxx.json           … 限定公開 (unlisted) で上げる。サムネイルがあれば設定
  python3 yt_upload.py specs/R8_xxx.json --publish-at 2026-11-05T19:00   … 非公開で上げて、その日時(日本時間)に公開予約
  python3 yt_upload.py specs/R8_xxx.json --publish  … すでに上げた動画を今すぐ公開（--publish-at で予約に変更）
  python3 yt_upload.py specs/R8_xxx.json --update   … タイトル・概要欄・タグ・サムネイルだけ更新

認証ファイル（git には入れない）:
  ~/takken-note/.yt_client_secret.json … Google Cloud の OAuth クライアント(デスクトップ)。なければ seido-tube の config/client_secret.json を使う
  ~/takken-note/.yt_token.json         … --auth で作られる
"""
import argparse, datetime as dt, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
ROOT = os.path.dirname(os.path.dirname(HERE))
TOKEN = os.path.join(ROOT, ".yt_token.json")
SECRET = os.path.join(ROOT, ".yt_client_secret.json")
SECRET_ALT = "/root/seido-tube/config/client_secret.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube", "https://www.googleapis.com/auth/youtube.force-ssl"]
REDIRECT = "http://localhost:8790/"
JST = dt.timezone(dt.timedelta(hours=9))

def ready():
    return os.path.exists(TOKEN)

def _secret():
    for p in (SECRET, SECRET_ALT):
        if os.path.exists(p): return p
    sys.exit("OAuth クライアントがありません。Google Cloud Console → 認証情報 → OAuth クライアント(デスクトップ) の JSON を ~/takken-note/.yt_client_secret.json に置いてください")

def creds():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    if not ready(): sys.exit("YouTube の認証がまだです。VPS で  .venv/bin/python3 coaching/yt/yt_upload.py --auth  を実行してください")
    c = Credentials.from_authorized_user_file(TOKEN, SCOPES)
    if c.expired and c.refresh_token:
        c.refresh(Request()); open(TOKEN, "w").write(c.to_json())
    return c

def auth():
    """ヘッドレスでも使える手順: URL を開いて許可 → localhost に飛ばされて表示されない画面の URL をそのまま貼る"""
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_secrets_file(_secret(), SCOPES, redirect_uri=REDIRECT)
    url, _ = flow.authorization_url(access_type="offline", prompt="consent")
    print("\n1) 아래 주소를 브라우저로 열고, NIPPONリアル 채널의 Google 계정으로 허용하세요:\n\n" + url + "\n")
    print("2) 허용하면 'localhost에 연결할 수 없음' 페이지가 뜹니다. 그 페이지의 주소창 URL 전체(http://localhost:8790/?code=... )를 복사해서 여기에 붙여넣으세요.\n")
    resp = input("붙여넣기: ").strip()
    flow.fetch_token(authorization_response=resp)
    open(TOKEN, "w").write(flow.credentials.to_json()); os.chmod(TOKEN, 0o600)
    from googleapiclient.discovery import build
    ch = build("youtube", "v3", credentials=flow.credentials).channels().list(part="snippet", mine=True).execute()
    name = (ch.get("items") or [{}])[0].get("snippet", {}).get("title", "?")
    print(f"\n✓ 인증 완료: 채널「{name}」로 업로드합니다 (.yt_token.json 저장)")

def _jst_iso(s):
    """'2026-11-05T19:00' (日本時間) → RFC3339 UTC"""
    t = dt.datetime.fromisoformat(s)
    if t.tzinfo is None: t = t.replace(tzinfo=JST)
    return t.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")

def _video_path(spec):
    import vkit as V
    return os.path.join(V.OUT, spec["outdir"], f"{spec['name']}.mp4")

def thumb_path(spec):
    import vkit as V
    p = os.path.join(V.OUT, spec["outdir"], "thumbnail.png")
    return p if os.path.exists(p) else None

def _save(path, spec):
    with open(path + ".tmp", "w", encoding="utf-8") as f: json.dump(spec, f, ensure_ascii=False, indent=1)
    os.replace(path + ".tmp", path)

def _record(path, spec, vid, log):
    import registry
    url = f"https://youtu.be/{vid}"
    spec.setdefault("youtube", {})["url"] = url; spec["youtube"]["id"] = vid
    order = ["topic", "script", "draft", "voiced", "uploaded", "blogged"]
    if order.index(spec.get("status", "script")) < order.index("uploaded"): spec["status"] = "uploaded"
    _save(path, spec)
    reg = registry.load(); registry.upsert(reg, spec["name"], label=spec.get("label"), title=spec["youtube"].get("title"), url=url); registry.save(reg)
    log(f"URL 저장: {url} (spec·URL 대장)")
    return url

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("spec", nargs="?"); ap.add_argument("--auth", action="store_true")
    ap.add_argument("--publish", action="store_true"); ap.add_argument("--publish-at"); ap.add_argument("--update", action="store_true")
    ap.add_argument("--privacy", default="unlisted", choices=["unlisted", "private", "public"])
    a = ap.parse_args()
    if a.auth: auth(); return
    if not a.spec: ap.error("spec を指定してください")
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    import ytext
    log = lambda m: print(m, flush=True)
    spec = json.load(open(a.spec, encoding="utf-8"))
    yt = build("youtube", "v3", credentials=creds())
    txt = ytext.compose(spec)
    vid = (spec.get("youtube") or {}).get("id") or (re.search(r"(?:youtu\.be/|v=)([\w-]{11})", (spec.get("youtube") or {}).get("url", "")) or [None, None])[1]
    snippet = {"title": txt["title"][:100], "description": txt["description"][:5000], "tags": [t for t in txt["tags"].split(", ") if t][:30],
               "categoryId": "27", "defaultLanguage": "ja", "defaultAudioLanguage": "ja"}
    if (a.publish or a.publish_at or a.update) and vid:
        if a.update:
            yt.videos().update(part="snippet", body={"id": vid, "snippet": snippet}).execute(); log("제목·설명란·태그 갱신")
        else:
            st = {"selfDeclaredMadeForKids": False}
            if a.publish_at: st.update(privacyStatus="private", publishAt=_jst_iso(a.publish_at)); log(f"공개 예약: {a.publish_at} (일본시간)")
            else: st.update(privacyStatus="public"); log("지금 공개로 전환")
            yt.videos().update(part="status", body={"id": vid, "status": st}).execute()
        tp = thumb_path(spec)
        if tp: yt.thumbnails().set(videoId=vid, media_body=tp).execute(); log("썸네일 설정")
        log(f"https://youtu.be/{vid}"); return
    if vid and not a.update:
        log(f"이미 올라간 영상이 있습니다: https://youtu.be/{vid}  (다시 올리려면 spec の youtube.url を空にしてください)"); return
    mp4 = _video_path(spec)
    if not os.path.exists(mp4): sys.exit("완성 영상(mp4)이 없습니다. 먼저 「음성 넣어 완성」을 해주세요")
    status = {"selfDeclaredMadeForKids": False}
    if a.publish_at: status.update(privacyStatus="private", publishAt=_jst_iso(a.publish_at))
    else: status["privacyStatus"] = a.privacy
    log(f"업로드 중… {os.path.getsize(mp4)/1e6:.0f}MB")
    req = yt.videos().insert(part="snippet,status", body={"snippet": snippet, "status": status},
                             media_body=MediaFileUpload(mp4, chunksize=8 * 1024 * 1024, resumable=True))
    r = None
    while r is None:
        st, r = req.next_chunk()
        if st: log(f"  {int(st.progress() * 100)}%")
    vid = r["id"]
    tp = thumb_path(spec)
    if tp:
        try: yt.thumbnails().set(videoId=vid, media_body=tp).execute(); log("썸네일 설정")
        except Exception as e: log(f"썸네일 설정 실패 (채널의 전화번호 인증이 필요할 수 있음): {str(e)[:150]}")
    url = _record(a.spec, spec, vid, log)
    log(("공개 예약 완료: " + a.publish_at + " (일본시간)  " if a.publish_at else f"{a.privacy} 로 업로드 완료  ") + url)

if __name__ == "__main__":
    main()
