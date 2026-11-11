# -*- coding: utf-8 -*-
"""YouTube サムネイル (1280×720)。
  方式 (spec["thumb"]["mode"]):
    ai     … OpenAI gpt-image に「日本のビジネス系サムネイル」として文字ごと描かせる（人物・バッジ・下部の情報ボックス込み）
    ai_bg  … OpenAI に文字なしの背景（人物・小物）だけ描かせ、見出し・バッジ・ボックスは PIL で正確に合成する（誤字が出ない）
    plain  … 単色グラデ背景 + 文字（従来。API 不要）
  python3 thumb.py specs/R8_xxx.json --ai              → spec["thumb"] の設定で生成 → out/<outdir>/thumbnail.png (+ 履歴 thumb_hist/)
  python3 thumb.py specs/R8_xxx.json "1行目" "2行目"    → plain
spec["thumb"] = {"lines": [...], "badge": "11月最新!", "points": ["登録の手順", "3つの仕事", "年代別戦略"], "person": "woman"|"man"|"none",
                 "mode": "ai"|"ai_bg"|"plain", "quality": "medium"|"high", "style": "navy"|"red"|"white"}
"""
import base64, glob, io, json, os, re, sys, time, uuid
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
FONT = os.path.join(HERE, "fonts", "MPLUSRounded1c-ExtraBold.ttf")
GOTHIC = os.path.join(HERE, "fonts", "ZenKakuGothicNew-Bold.ttf")
W, H = 1280, 720            # 롱폼 (16:9)
SW, SH = 1080, 1920         # 쇼츠 (9:16)
STYLES = {  # (上の色, 下の色, 文字1, 文字2, フチ)
    "navy":  ((16, 38, 82), (40, 96, 190), "#FFFFFF", "#FFE14D", "#0B1A3A"),
    "red":   ((120, 20, 20), (210, 50, 40), "#FFFFFF", "#FFE14D", "#3A0808"),
    "white": ((250, 247, 238), (235, 228, 210), "#1A3D7C", "#C0392B", "#FFFFFF"),
}
PERSON = {"woman": "20〜30代の日本人女性（スーツまたはオフィスカジュアル）", "man": "20〜30代の日本人男性（スーツ）", "none": None}

def _out(spec):
    import vkit as V
    return os.path.join(V.OUT, spec["outdir"])

# ---------------- 提案値（タイトルから自動で） ----------------
def suggest(spec):
    """스튜디오の初期値: 見出し行・バッジ・下部ポイント"""
    t = (spec.get("youtube") or {}).get("title") or spec.get("label", "")
    head = re.split(r"[【】｜|]", t); head = [x.strip() for x in head if x.strip()]
    lines = []
    for h in head[:2]:
        for part in re.split(r"[・／/（）()]", h):
            part = part.strip()
            if part and len(lines) < 3: lines.append(part[:14])
    badge = ""
    m = re.search(r"(\d{1,2}/\d{1,2})", t) or re.search(r"(\d{1,2}月最新)", t) or re.search(r"(令和\d+年度?)", t) or re.search(r"(20\d\d年)", t)
    if m: badge = m.group(1) + ("" if "最新" in m.group(1) else " 実施" if "/" in m.group(1) else "")
    pts = []
    for s in spec.get("slides", [])[1:]:
        tt = (s.get("title") or "").split("｜")[0].strip()
        tt = re.sub(r"^[①-⑳\d]+[．.、\s]*", "", tt)
        if tt and len(tt) <= 9 and tt not in pts and tt not in ("結論", "まとめ", "はじめに", "この動画の要点"): pts.append(tt)
        if len(pts) >= 3: break
    return {"lines": lines[:3], "badge": badge, "points": pts}

# ---------------- OpenAI ----------------
def _key():
    import illust
    return illust._key(".openai_api_key", "OPENAI_API_KEY")

def _rkey():
    import illust
    return illust._key(".replicate_api_token", "REPLICATE_API_TOKEN")

def providers():
    return {"replicate": bool(_rkey()), "openai": bool(_key())}

# Replicate: 日本語の文字が得意な順。先頭が失敗したら次へ
R_MODELS = [m for m in os.environ.get("REPLICATE_IMAGE_MODELS", "bytedance/seedream-4.5,google/nano-banana-pro,bytedance/seedream-4,qwen/qwen-image-2512").split(",") if m]

def _r_input(model, prompt, refs, quality, vert=False):
    ar = "9:16" if vert else "16:9"
    """モデルごとの入力。参照画像は data URI で渡す（Replicate はファイル入力に data URI を受け付ける）"""
    if model.startswith("bytedance/seedream"):
        inp = {"prompt": prompt, "size": "2K", "aspect_ratio": ar, "max_images": 1}
        if refs: inp["image_input"] = [_data_uri(f) for f in refs[:3]]
        return inp
    if model.startswith("google/nano-banana"):                       # Gemini 3 Pro Image: 多言語の文字に強い。参照画像は最大 14 枚
        inp = {"prompt": prompt, "aspect_ratio": ar, "resolution": "2K", "output_format": "png"}
        if refs: inp["image_input"] = [_data_uri(f) for f in refs[:3]]
        return inp
    if model.startswith("qwen/"):
        return {"prompt": prompt, "aspect_ratio": ar, "output_format": "png", "go_fast": quality != "high"}
    if model.startswith("ideogram-ai/"):
        inp = {"prompt": prompt, "aspect_ratio": ar, "magic_prompt_option": "Off"}
        if refs: inp["style_reference_images"] = [_data_uri(f) for f in refs[:3]]
        return inp
    return {"prompt": prompt, "aspect_ratio": ar}

def _data_uri(path):
    from PIL import Image
    im = Image.open(path).convert("RGB"); im.thumbnail((1024, 1024))
    b = io.BytesIO(); im.save(b, "JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()

def _replicate(prompt, refs, quality="medium", log=print, vert=False):
    """Replicate の公式モデルを同期実行（Prefer: wait → 足りなければ urls.get をポーリング）。戻り値 (画像bytes, 使ったモデル)"""
    import urllib.request, urllib.error
    hdr = {"Authorization": "Bearer " + _rkey(), "Content-Type": "application/json", "Prefer": "wait=60"}
    last = None
    for model in R_MODELS:
        try:
            log(f"  Replicate 모델: {model}" + (f" (참고 {len(refs)}장)" if refs else ""))
            body = json.dumps({"input": _r_input(model, prompt, refs, quality, vert)}).encode()
            req = urllib.request.Request(f"https://api.replicate.com/v1/models/{model}/predictions", data=body, headers=hdr)
            with urllib.request.urlopen(req, timeout=120) as r: pred = json.load(r)
            t0 = time.time()
            while pred.get("status") in ("starting", "processing") and time.time() - t0 < 240:
                time.sleep(2)
                req = urllib.request.Request(pred["urls"]["get"], headers={"Authorization": "Bearer " + _rkey()})
                with urllib.request.urlopen(req, timeout=60) as r: pred = json.load(r)
            if pred.get("status") != "succeeded":
                raise RuntimeError(f"{pred.get('status')}: {str(pred.get('error'))[:200]}")
            out = pred["output"]; url = out[0] if isinstance(out, list) else out
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "takken-studio"}), timeout=120) as r: return r.read(), model
        except urllib.error.HTTPError as e:
            try: detail = json.loads(e.read().decode("utf-8", "replace")).get("detail") or ""
            except Exception: detail = e.reason
            last = f"{model}: HTTP {e.code} {str(detail)[:160]}"; log(f"  ✗ {last}")
            if e.code in (401, 402): break                                # 鍵・残高の問題は次のモデルでも同じ
        except Exception as e:
            last = f"{model}: {str(e)[:160]}"; log(f"  ✗ {last}")
    raise RuntimeError("Replicate 실패: " + (last or "모델 없음"))

def references(spec, n=2):
    """スタイル参照: ほかの動画で「自分で上げた」または「AIで作って採用した」サムネイル（新しい順に n 枚）"""
    import vkit as V
    out = []
    for p in glob.glob(os.path.join(HERE, "specs", "*.json")) + glob.glob(os.path.join(HERE, "specs", "_archive", "*.json")):
        try: sp = json.load(open(p, encoding="utf-8"))
        except Exception: continue
        if sp.get("name") == spec.get("name"): continue
        th = sp.get("thumb") or {}
        f = os.path.join(V.OUT, sp.get("outdir", ""), "thumbnail.png")
        if os.path.exists(f) and (th.get("custom") or th.get("mode") in ("ai", "ai_bg")): out.append((os.path.getmtime(f), f))
    return [f for _, f in sorted(out, reverse=True)[:n]]

def prompt_for(spec, cfg, with_text=True, vert=False):
    lines = [l for l in cfg.get("lines") or [] if l.strip()][:3]
    person = PERSON.get(cfg.get("person") or "woman")
    cols = ["白い文字に濃紺の太いフチ", "黄色い文字に赤の太いフチ", "赤い文字に白の太いフチと黒い影"]
    if vert:
        p = ["日本のビジネス・資格試験系 YouTube ショート動画のサムネイル画像。縦長 9:16（スマホ全画面）。",
             "全体の雰囲気: 情報量が多く賑やかだがプロのデザイナーが作った仕上がり。背景は明るいオフィス街や白〜淡い水色のグラデーション。",
             ("中央から下に" + person + "の写真のようにリアルな上半身。驚いた表情か、少し上を見て考える表情。カメラ目線ではない。" if person else "人物は入れない。")]
    else:
        p = ["日本のビジネス・資格試験系 YouTube チャンネルのサムネイル画像。横長 16:9。",
             "全体の雰囲気: 情報量が多く賑やかだがプロのデザイナーが作った仕上がり。背景は明るいオフィス街や白〜淡い水色のグラデーション。",
             ("右側に" + person + "の写真のようにリアルな上半身。驚いた表情か、少し上を見て考える表情。カメラ目線ではない。" if person else "人物は入れない。")]
    if with_text:
        p.append(("上 3 分の 1 に、日本語の見出しを極太ゴシック体で画面幅いっぱいに大きく配置する。" if vert else "左側 6 割に、日本語の見出しを極太ゴシック体で非常に大きく配置する。") + "次の文字列を一字一句そのまま、この順で縦に並べる:")
        for i, l in enumerate(lines): p.append(f"  {i+1}行目「{l}」（{cols[i % 3]}）")
        if cfg.get("badge"): p.append(f"右上に赤い丸いバッジ、中に白い太字で「{cfg['badge']}」。")
        pts = [x for x in (cfg.get("points") or []) if x.strip()][:3]
        if pts: p.append("最下部に白い小さな情報ボックスを横に " + str(len(pts)) + " つ並べ、各ボックスに小さなアイコンと短い語: " + "、".join(f"「{x}」" for x in pts) + "。")
        p.append("禁止: 上記以外の文字・英語・ロゴ・実在の会社名を入れない。文字の誤字脱字や創作をしない。文字は切れないように余白を取る。")
    else:
        p.append("文字・数字・ロゴは一切描かない。" + ("上 3 分の 1 は後から文字を載せるので、明るく単純な空間にして要素を置かない。" if vert else "左側 6 割は後から文字を載せるので、明るく単純な空間（淡いグラデーションや薄い街並み）にして要素を置かない。") + "最下部 20% も帯を載せるので空けておく。")
    return "\n".join(p)

def _multipart(fields, files):
    b = uuid.uuid4().hex; body = io.BytesIO()
    for k, v in fields.items():
        body.write(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    for k, (fn, data, ct) in files:
        body.write(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{fn}\"\r\nContent-Type: {ct}\r\n\r\n".encode()); body.write(data); body.write(b"\r\n")
    body.write(f"--{b}--\r\n".encode())
    return body.getvalue(), f"multipart/form-data; boundary={b}"

PREFER = ["gpt-image-2", "gpt-image-1.5", "gpt-image-1", "gpt-image-1-mini", "dall-e-3"]

def available_models(log=print):
    """この鍵で使える画像モデル（/v1/models から）。gpt-image 系は組織の本人確認が済んでいないと出てこない"""
    import urllib.request
    try:
        req = urllib.request.Request("https://api.openai.com/v1/models", headers={"Authorization": "Bearer " + _key()})
        with urllib.request.urlopen(req, timeout=30) as r: ids = [m["id"] for m in json.load(r).get("data", [])]
        return [m for m in ids if m.startswith("gpt-image") or m.startswith("dall-e")]
    except Exception as e:
        log(f"  모델 목록 조회 실패 ({str(e)[:80]}) → 순서대로 시도"); return None

def pick_model(log=print):
    env = os.environ.get("OPENAI_IMAGE_MODEL")
    avail = available_models(log)
    if env and (avail is None or env in avail): return env
    if avail is not None:
        for m in PREFER:
            if m in avail: return m
        for m in avail:
            if m.startswith("gpt-image"): return m
        if avail: return avail[0]
    return "gpt-image-1"

def _call(prompt, refs, quality="medium", log=print, model=None, vert=False):
    import urllib.request, urllib.error
    hdr = {"Authorization": "Bearer " + _key()}
    gsize = "1024x1536" if vert else "1536x1024"
    model = model or pick_model(log)
    log(f"  모델: {model}")
    if model.startswith("dall-e"):                                   # 参照画像・品質指定が違う。日本語文字も苦手
        body = {"model": model, "prompt": prompt[:3900], "size": "1024x1792" if vert else "1792x1024", "quality": "hd" if quality == "high" else "standard", "response_format": "b64_json", "n": 1}
        req = urllib.request.Request("https://api.openai.com/v1/images/generations", data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **hdr})
    elif refs:
        log(f"  참고 썸네일 {len(refs)}장과 함께 생성 (images/edits)")
        files = [("image[]", (os.path.basename(f), open(f, "rb").read(), "image/png")) for f in refs]
        data, ct = _multipart({"model": model, "prompt": prompt + "\n参考画像はこのチャンネルの既存サムネイル。文字の太さ・色づかい・レイアウトの密度を同じ雰囲気にする（内容はコピーしない）。",
                               "size": gsize, "quality": quality, "n": "1"}, files)
        req = urllib.request.Request("https://api.openai.com/v1/images/edits", data=data, headers={"Content-Type": ct, **hdr})
    else:
        req = urllib.request.Request("https://api.openai.com/v1/images/generations", data=json.dumps({"model": model, "prompt": prompt, "size": gsize, "quality": quality, "n": 1}).encode(),
                                     headers={"Content-Type": "application/json", **hdr})
    try:
        with urllib.request.urlopen(req, timeout=300) as r: d = json.load(r)
    except urllib.error.HTTPError as e:
        try: detail = json.loads(e.read().decode("utf-8", "replace")).get("error", {}).get("message", "")[:300]
        except Exception: detail = e.reason
        if e.code in (400, 403, 404) and ("does not exist" in detail or "not have access" in detail or "verif" in detail.lower()) and model != "dall-e-3":
            log(f"  {model} 사용 불가 ({detail[:120]}) → dall-e-3 로 다시 시도")
            return _call(prompt, [], quality, log, model="dall-e-3", vert=vert)
        raise RuntimeError(f"OpenAI HTTP {e.code}: {detail}")
    return base64.b64decode(d["data"][0]["b64_json"]), model

def _to_ratio(raw, vert=False):
    """生成画像を 16:9 (1280×720) か 9:16 (1080×1920) に中央トリミング"""
    from PIL import Image
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    tw, th = (SW, SH) if vert else (W, H)
    r = tw / th
    if im.width / im.height > r:
        nw = round(im.height * r); im = im.crop(((im.width - nw) // 2, 0, (im.width - nw) // 2 + nw, im.height))
    else:
        nh = round(im.width / r); im = im.crop((0, (im.height - nh) // 2, im.width, (im.height - nh) // 2 + nh))
    return im.resize((tw, th), Image.LANCZOS)

# ---------------- PIL 合成（ai_bg / plain） ----------------
def _text(d, xy, s, font, fill, strokes):
    """strokes = [(幅, 色), ...] 外側から順に"""
    x, y = xy
    for w, c in strokes: d.text((x, y), s, font=font, fill=c, stroke_width=w, stroke_fill=c)
    d.text((x, y), s, font=font, fill=fill)

def compose(im, cfg, vert=False):
    """背景画像の上に 見出し（横は左 / 縦は上）・バッジ（右上）・情報ボックス（下）を描く"""
    from PIL import ImageDraw, ImageFont
    W, H = im.size
    d = ImageDraw.Draw(im, "RGBA")
    lines = [l for l in cfg.get("lines") or [] if l.strip()][:3]
    pts = [x for x in (cfg.get("points") or []) if x.strip()][:3]
    badge = (cfg.get("badge") or "").strip()
    bottom = 150 if pts else 40
    if vert:
        text_w = W - 80; area_h = int(H * 0.36); top0 = 120
    else:
        text_w = int(W * 0.62) - 50; area_h = H - bottom - 30; top0 = 30
    # 行ごとに幅いっぱいまで大きくする（短い行＝キーワードほど大きく。参考サムネの「現実」「180点」のように）
    def fit(l, cap):
        sz = cap
        while sz > 48:
            f = ImageFont.truetype(GOTHIC, sz)
            if d.textlength(l, font=f) <= text_w: return sz, f
            sz -= 4
        return sz, ImageFont.truetype(GOTHIC, sz)
    cap = 190 if vert else 170
    while True:
        fs = [fit(l, cap) for l in lines]
        if sum(int(sz * 1.12) for sz, _ in fs) <= area_h or cap <= 60: break
        cap -= 8
    total = sum(int(sz * 1.12) for sz, _ in fs); y = top0 + (area_h - total) // 2
    palette = [("#FFFFFF", "#0B1A3A", None), ("#FFE14D", "#0B1A3A", "#C0392B"), ("#E8352B", "#0B1A3A", "#FFFFFF")]
    for i, (l, (size, f)) in enumerate(zip(lines, fs)):
        fill, outer, inner = palette[i % 3]
        strokes = [(size // 7, outer)] + ([(size // 12, inner)] if inner else [])
        x0 = (W - d.textlength(l, font=f)) // 2 if vert else 40
        _text(d, (x0 + size // 10, y + size // 10), l, f, "#000000", [(size // 7, "#000000")])          # 影
        _text(ImageDraw.Draw(im, "RGBA"), (x0, y), l, f, fill, strokes); y += int(size * 1.12)
    if badge:
        bf = ImageFont.truetype(FONT, 40); tw = d.textlength(badge, font=bf)
        bw = int(tw + 60); bx, by = W - bw - 26, 22
        d.rounded_rectangle([bx, by, bx + bw, by + 70], radius=35, fill="#E8352B", outline="#FFFFFF", width=4)
        d.text((bx + 30, by + 13), badge, font=bf, fill="#FFFFFF")
    if pts:
        d.rectangle([0, H - 130, W, H], fill=(11, 26, 58, 215))
        pf = ImageFont.truetype(FONT, 34); n = len(pts); gap = 18; bw = (W - 40 - gap * (n - 1)) // n
        for i, p in enumerate(pts):
            x = 20 + i * (bw + gap); d.rounded_rectangle([x, H - 112, x + bw, H - 24], radius=14, fill="#FFFFFF", outline="#FFE14D", width=4)
            cx, cy = x + 40, H - 68
            d.rounded_rectangle([cx - 22, cy - 22, cx + 22, cy + 22], radius=10, fill=["#1A3D7C", "#C0392B", "#1F7A45"][i % 3])
            d.line([(cx - 11, cy + 1), (cx - 3, cy + 9), (cx + 12, cy - 9)], fill="#FFFFFF", width=5, joint="curve")   # チェック印
            d.text((x + 76, cy), p[:10], font=pf, fill="#1A3D7C", anchor="lm")
    return im

def make(spec, lines, style="navy", out=None):
    """plain: 単色グラデ + 文字（従来）"""
    from PIL import Image, ImageDraw, ImageFont
    import illust
    top, bot, c1, c2, stroke = STYLES.get(style, STYLES["navy"])
    im = Image.new("RGB", (W, H)); d = ImageDraw.Draw(im)
    for y in range(H):
        k = y / H; d.line([(0, y), (W, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * k) for i in range(3)))
    ill = illust.path_for(spec["slides"][0]) if spec.get("slides") else None
    text_w = W - 80
    if ill and ill.endswith((".png", ".jpg")):
        pic = Image.open(ill).convert("RGBA")
        ph = int(H * 0.86); pic = pic.resize((int(pic.width * ph / pic.height), ph))
        if pic.width > W * 0.48: pic = pic.resize((int(W * 0.48), int(pic.height * W * 0.48 / pic.width)))
        im.paste(pic, (W - pic.width - 20, (H - pic.height) // 2), pic)
        text_w = W - pic.width - 80
    lines = [l for l in lines if l.strip()][:3]
    size = 140
    while size > 56:
        f = ImageFont.truetype(FONT, size)
        if max(d.textlength(l, font=f) for l in lines) <= text_w and size * 1.22 * len(lines) <= H - 80: break
        size -= 6
    lh = int(size * 1.22); y = (H - lh * len(lines)) // 2
    for i, l in enumerate(lines):
        x = 40 + (text_w - d.textlength(l, font=f)) / 2
        d.text((x, y), l, font=f, fill=c1 if i % 2 == 0 else c2, stroke_width=max(4, size // 16), stroke_fill=stroke); y += lh
    return _save(spec, im, out)

def _save(spec, im, out=None, hist="thumb_hist"):
    out = out or os.path.join(_out(spec), "thumbnail.png")
    os.makedirs(os.path.dirname(out), exist_ok=True); im.save(out)
    hd = os.path.join(os.path.dirname(out), hist); os.makedirs(hd, exist_ok=True)      # 履歴（あとから選び直せる）
    im.save(os.path.join(hd, time.strftime("%Y%m%d_%H%M%S") + ".png"))
    return out

def make_plain(spec, cfg, short=None):
    """API なし: グラデ背景 + 合成（縦横どちらも）"""
    from PIL import Image, ImageDraw
    vert = bool(short); tw, th = (SW, SH) if vert else (W, H)
    top, bot = STYLES.get(cfg.get("style") or "navy", STYLES["navy"])[:2]
    if cfg.get("style") == "white": top, bot = (236, 242, 252), (205, 220, 245)
    im = Image.new("RGB", (tw, th)); d = ImageDraw.Draw(im)
    for y in range(th):
        k = y / th; d.line([(0, y), (tw, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * k) for i in range(3)))
    im = compose(im, cfg, vert)
    if short:
        sp_ = short_paths(spec, short); spec.setdefault("thumb_shorts", {}).setdefault(short, {}).update(cfg)
        out = _save(spec, im, sp_["png"], sp_["hist"])
        if cfg.get("cover", True) and os.path.exists(sp_["mp4"]): apply_cover(sp_["mp4"], out, sp_["raw"])
        return out
    return _save(spec, im)

def suggest_short(spec, key):
    """ショートの初期値: フック（short_hook）を行に。なければ txt の題名"""
    import re
    m = re.search(r"_s(\d+)$", key); hook = ""
    if m and 0 < int(m.group(1)) <= len(spec.get("slides", [])): hook = spec["slides"][int(m.group(1)) - 1].get("short_hook") or ""
    if not hook:
        t = os.path.join(_out(spec), "shorts", key + ".txt")
        if os.path.exists(t):
            mm = re.search(r"【タイトル】\n(.+)", open(t, encoding="utf-8").read()); hook = re.sub(r"【[^】]*】|\s*#\S+", "", mm.group(1)).strip() if mm else ""
    lines = [x.strip() for x in re.split(r"[\n／/]", hook) if x.strip()][:3]
    return {"lines": lines, "badge": "", "points": []}

def short_paths(spec, key):
    """ショート <key> (= mp4 のファイル名, 例 R8_x_s06) のサムネイル・履歴・動画のパス"""
    d = os.path.join(_out(spec), "shorts")
    return {"png": os.path.join(d, key + "_thumb.png"), "hist": "thumb_hist_" + key, "mp4": os.path.join(d, key + ".mp4"), "raw": os.path.join(d, key + "_raw.mp4")}

def apply_cover(mp4, png, raw=None, sec=1.0, log=print):
    """ショートの先頭 sec 秒にサムネイル画像を差し込む（YouTube のショートは任意画像のサムネを選べないので、最初のコマで見せる）。
    元の動画は <base>_raw.mp4 に残し、2回目以降はそこから作り直す"""
    import subprocess, shutil
    raw = raw or mp4[:-4] + "_raw.mp4"
    if not os.path.exists(raw): shutil.copyfile(mp4, raw)
    tmp = mp4[:-4] + "_cover_tmp.mp4"
    fc = (f"[0:v]scale={SW}:{SH}:force_original_aspect_ratio=increase,crop={SW}:{SH},format=yuv420p,setsar=1[v0];"
          f"[1:v]scale={SW}:{SH},setsar=1,format=yuv420p[v1];[1:a]aresample=48000,aformat=channel_layouts=stereo[a1];"
          f"anullsrc=r=48000:cl=stereo,atrim=0:{sec}[a0];[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-t", str(sec), "-framerate", "30", "-i", png, "-i", raw,
           "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", tmp]
    subprocess.run(cmd, check=True); os.replace(tmp, mp4)
    log(f"  쇼츠 첫 {sec:g}초에 썸네일을 넣었습니다: {os.path.basename(mp4)}")
    return mp4

def make_ai(spec, cfg, log=print, short=None):
    """short=<key> なら 9:16 のショート用サムネイル（出力は shorts/<key>_thumb.png）"""
    vert = bool(short)
    mode = cfg.get("mode") or "ai"
    av = providers()
    prov = cfg.get("provider") or "auto"
    if prov == "auto": prov = "replicate" if av["replicate"] else "openai"
    if prov == "replicate" and not av["replicate"]: raise RuntimeError("Replicate 토큰(.replicate_api_token)이 없습니다")
    if prov == "openai" and not av["openai"]: raise RuntimeError("OpenAI 키(.openai_api_key)가 없습니다")
    refs = references(spec) if cfg.get("use_refs", True) else []
    quality = cfg.get("quality") or "medium"
    if prov == "replicate":
        pr = prompt_for(spec, cfg, with_text=(mode == "ai"), vert=vert)
        log(f"썸네일 생성 (Replicate, {mode}{', 쇼츠 9:16' if vert else ''}) …\n{pr}")
        raw, used = _replicate(pr, refs, quality, log, vert=vert)
    else:
        model = pick_model(log)
        if mode == "ai" and model.startswith("dall-e"):             # dall-e は日本語の文字を正しく描けない → 背景だけ描かせて文字は合成
            log("  ※ gpt-image 系が使えない鍵です（OpenAI の組織認証が未了の可能性）。dall-e-3 で背景を描き、文字は合成します")
            mode = "ai_bg"; refs = []
        pr = prompt_for(spec, cfg, with_text=(mode == "ai"), vert=vert)
        log(f"썸네일 생성 (OpenAI, {mode}, {quality}{', 쇼츠 9:16' if vert else ''}) …\n{pr}")
        raw, used = _call(pr, refs, quality, log, model=model, vert=vert)
    im = _to_ratio(raw, vert)
    if mode == "ai_bg" or used.startswith("dall-e"): im = compose(im, cfg, vert)
    log(f"  사용 모델: {used}")
    if short:
        sp_ = short_paths(spec, short)
        spec.setdefault("thumb_shorts", {}).setdefault(short, {}).update(cfg, used_model=used)
        out = _save(spec, im, sp_["png"], sp_["hist"])
        if cfg.get("cover", True) and os.path.exists(sp_["mp4"]): apply_cover(sp_["mp4"], out, sp_["raw"], log=log)
        return out
    spec.setdefault("thumb", {})["used_model"] = used
    return _save(spec, im)

if __name__ == "__main__":
    sp = json.load(open(sys.argv[1], encoding="utf-8"))
    if len(sys.argv) > 2 and sys.argv[2] == "--ai":
        if len(sys.argv) > 4 and sys.argv[3] == "--short":
            key = sys.argv[4]; print(make_ai(sp, (sp.get("thumb_shorts") or {}).get(key) or {}, short=key))
        else:
            print(make_ai(sp, sp.get("thumb") or {}))
    else:
        print(make(sp, sys.argv[2:], (sp.get("thumb") or {}).get("style", "navy")))
