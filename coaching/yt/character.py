# -*- coding: utf-8 -*-
"""AI キャラクター（Hedra Character-3）: 立ち絵 1 枚 + 読み上げ音声 → 口と表情が動く「話すキャラクター」動画。
  鍵: .hedra_api_key（形式 <key_id>:<secret>、https://www.hedra.com/develop/api-keys で作成。API ウォレットに入金が必要）
  料金目安: 540p 2.5¢/秒・720p 5¢/秒（60 秒のショートで $1.5 / $3）

  python3 character.py --mascot "20代の日本人女性、紺のスーツ…"   → mascot/default.png を生成（illust の生成元を使う）
  python3 character.py --talk mascot/default.png voice.mp3 out.mp4 [--aspect 16:9] [--res 540p]
"""
import argparse, io, json, os, sys, time, uuid
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
ROOT = os.path.dirname(os.path.dirname(HERE))
MASCOT_DIR = os.path.join(HERE, "mascot"); os.makedirs(MASCOT_DIR, exist_ok=True)
API = "https://api.hedra.com/v3"
MODEL = os.environ.get("HEDRA_CHARACTER_MODEL", "hedra-character-3")

def _key():
    import illust
    return illust._key(".hedra_api_key", "HEDRA_API_KEY")

def available(): return bool(_key())

def _req(method, path, body=None, data=None, ctype=None, timeout=120):
    import urllib.request, urllib.error
    hdr = {"Authorization": "Key " + _key(), "User-Agent": "takken-studio/1.0"}
    if body is not None: data = json.dumps(body).encode(); hdr["Content-Type"] = "application/json"
    if ctype: hdr["Content-Type"] = ctype
    req = urllib.request.Request(API + path if path.startswith("/") else path, data=data, headers=hdr, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return json.load(r)
    except urllib.error.HTTPError as e:
        b = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"Hedra HTTP {e.code} {path}: {b[:400]}")

def _multipart(fields, files):
    b = uuid.uuid4().hex; body = io.BytesIO()
    for k, v in fields.items():
        body.write(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    for k, (fn, raw, ct) in files:
        body.write(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{fn}\"\r\nContent-Type: {ct}\r\n\r\n".encode()); body.write(raw); body.write(b"\r\n")
    body.write(f"--{b}--\r\n".encode())
    return body.getvalue(), f"multipart/form-data; boundary={b}"

def upload(path):
    """POST /v3/files → アップロードハンドル (url)。1 時間で失効するので使う直前に"""
    ct = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "mp3": "audio/mpeg", "m4a": "audio/mp4", "wav": "audio/wav"}.get(path.rsplit(".", 1)[-1].lower(), "application/octet-stream")
    data, mct = _multipart({}, [("file", (os.path.basename(path), open(path, "rb").read(), ct))])
    r = _req("POST", "/files", data=data, ctype=mct, timeout=300)
    return r["url"]

_SCHEMA = None
def schema(log=print):
    """GET /v3/models/<model> の input_schema。フィールド名がドキュメントに明記されていないので実物を見て組み立てる"""
    global _SCHEMA
    if _SCHEMA is None:
        r = _req("GET", f"/models/{MODEL}")
        _SCHEMA = r.get("input_schema") or r.get("inputSchema") or r
        try: json.dump(_SCHEMA, open(os.path.join(HERE, "out", "_hedra_schema.json"), "w"), indent=1)
        except Exception: pass
    return _SCHEMA

def _props(sc):
    p = sc.get("properties") if isinstance(sc, dict) else None
    if not p and isinstance(sc, dict):                              # {"input": {...}} に包まれている場合
        inner = sc.get("input") or {}
        p = inner.get("properties") if isinstance(inner, dict) else None
    return p or {}

def _pick(props, *cands):
    for c in cands:
        for k in props:
            if k == c or k.lower() == c: return k
    for c in cands:
        for k in props:
            if c in k.lower(): return k
    return None

def _media(url):
    return {"source": "url", "url": url}

def talk(image, audio, out, aspect="16:9", resolution="540p", prompt="", log=print):
    """立ち絵 + 音声 → 話す動画 (mp4)。入力フィールド名は実際の input_schema から選ぶ"""
    if not _key(): raise RuntimeError("Hedra 키(.hedra_api_key)가 없습니다")
    sc = schema(log); props = _props(sc)
    k_img = _pick(props, "start_image", "image", "start_frame", "start_keyframe", "keyframe")
    k_aud = _pick(props, "audio", "audios", "audio_inputs", "voice")
    if not k_img or not k_aud:
        raise RuntimeError("Hedra input_schema 에서 이미지/음성 필드를 찾지 못했습니다: " + ", ".join(props.keys())[:300])
    log(f"  Hedra {MODEL}: 업로드 중 (이미지·음성) …")
    iu, au = upload(image), upload(audio)
    aud_prop = props.get(k_aud) or {}
    aud_val = [_media(au)] if aud_prop.get("type") == "array" else _media(au)
    inp = {k_img: _media(iu), k_aud: aud_val}
    for k, v in (("aspect_ratio", aspect), ("resolution", resolution)):
        kk = _pick(props, k)
        if kk: inp[kk] = v
    kp = _pick(props, "prompt", "text_prompt")
    if kp and prompt: inp[kp] = prompt
    try:
        est = _req("POST", f"/models/{MODEL}/estimate", {"input": inp}); log(f"  예상 비용: {json.dumps(est)[:160]}")
    except Exception as e:
        log(f"  (견적 생략: {str(e)[:120]})")
    job = _req("POST", f"/models/{MODEL}", {"input": inp}, timeout=120)
    jid = job.get("job_id") or job.get("id")
    log(f"  job {jid} 생성. 대기 중 …")
    t0 = time.time(); st = None
    while time.time() - t0 < 900:
        s = _req("GET", f"/jobs/{jid}/status"); st = s.get("status")
        if st in ("COMPLETED", "FAILED", "CANCELLED"): break
        time.sleep(5)
    if st != "COMPLETED":
        d = _req("GET", f"/jobs/{jid}")
        raise RuntimeError(f"Hedra job {jid} {st}: {str(d.get('error'))[:300]}")
    d = _req("GET", f"/jobs/{jid}")
    outs = d.get("outputs") or []
    url = next((o.get("url") for o in outs if o.get("url")), None)
    if not url: raise RuntimeError("Hedra 출력 URL 없음: " + json.dumps(d)[:300])
    import urllib.request
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "takken-studio/1.0"}), timeout=600) as r:
        open(out, "wb").write(r.read())
    log(f"  캐릭터 영상 완성: {os.path.basename(out)} ({(time.time()-t0):.0f}초)")
    return out

# ---------------- マスコット（立ち絵） ----------------
MASCOT_PROMPT = ("YouTube の解説動画に出る案内役キャラクターの立ち絵。{desc}。"
                 "正面向きのバストアップ、カメラ目線、口は軽く閉じた自然な微笑み、肩まで入る。顔を画面中央に大きく、頭の上と肩の左右に余白。"
                 "背景は単色に近い明るいクリーム色〜淡い水色で、文字・ロゴ・小物は入れない。"
                 "画風: 日本のアニメ寄りの清潔な2Dイラスト、はっきりした輪郭線、フラットな陰影、鮮やかすぎない色。口と目がはっきり分かる描き方（あとで口を動かすため）。")

def mascot_path(name="default"):
    for ext in ("png", "jpg"):
        p = os.path.join(MASCOT_DIR, f"{name}.{ext}")
        if os.path.exists(p): return p
    return None

def make_mascot(desc, name="default", log=print):
    """illust の生成元（Gemini → OpenAI）で立ち絵を作る"""
    import illust
    prompt = MASCOT_PROMPT.format(desc=desc or "20代後半の日本人女性、紺のジャケットに白いブラウス、黒髪のミディアムヘア、宅建士証の名札")
    base = os.path.join(MASCOT_DIR, name)
    for prov in [q for q in ("gemini", "openai") if illust.providers().get(q)]:
        try:
            log(f"  마스코트 생성 ({prov}) …")
            out = illust.GEN[prov](prompt, base)
            json.dump({"desc": desc, "provider": prov, "at": time.strftime("%Y-%m-%d %H:%M")}, open(base + ".json", "w", encoding="utf-8"), ensure_ascii=False)
            return out
        except Exception as e:
            log(f"  ✗ {prov}: {str(e)[:160]}")
    raise RuntimeError("마스코트를 만들 생성원이 없습니다 (.gemini_api_key / .openai_api_key)")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mascot", help="立ち絵の説明（日本語）→ mascot/default.png")
    ap.add_argument("--name", default="default")
    ap.add_argument("--talk", nargs=3, metavar=("IMAGE", "AUDIO", "OUT"))
    ap.add_argument("--aspect", default="16:9"); ap.add_argument("--res", default="540p")
    a = ap.parse_args()
    if a.mascot is not None: print(make_mascot(a.mascot, a.name))
    elif a.talk: print(talk(a.talk[0], a.talk[1], a.talk[2], a.aspect, a.res))
    else: ap.print_help()
