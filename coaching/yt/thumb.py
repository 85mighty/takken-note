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
W, H = 1280, 720
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

def prompt_for(spec, cfg, with_text=True):
    lines = [l for l in cfg.get("lines") or [] if l.strip()][:3]
    person = PERSON.get(cfg.get("person") or "woman")
    cols = ["白い文字に濃紺の太いフチ", "黄色い文字に赤の太いフチ", "赤い文字に白の太いフチと黒い影"]
    p = ["日本のビジネス・資格試験系 YouTube チャンネルのサムネイル画像。横長 16:9。",
         "全体の雰囲気: 情報量が多く賑やかだがプロのデザイナーが作った仕上がり。背景は明るいオフィス街や白〜淡い水色のグラデーション。",
         ("右側に" + person + "の写真のようにリアルな上半身。驚いた表情か、少し上を見て考える表情。カメラ目線ではない。" if person else "人物は入れない。")]
    if with_text:
        p.append("左側 6 割に、日本語の見出しを極太ゴシック体で非常に大きく配置する。次の文字列を一字一句そのまま、この順で縦に並べる:")
        for i, l in enumerate(lines): p.append(f"  {i+1}行目「{l}」（{cols[i % 3]}）")
        if cfg.get("badge"): p.append(f"右上に赤い丸いバッジ、中に白い太字で「{cfg['badge']}」。")
        pts = [x for x in (cfg.get("points") or []) if x.strip()][:3]
        if pts: p.append("最下部に白い小さな情報ボックスを横に " + str(len(pts)) + " つ並べ、各ボックスに小さなアイコンと短い語: " + "、".join(f"「{x}」" for x in pts) + "。")
        p.append("禁止: 上記以外の文字・英語・ロゴ・実在の会社名を入れない。文字の誤字脱字や創作をしない。文字は切れないように余白を取る。")
    else:
        p.append("文字・数字・ロゴは一切描かない。左側 6 割は後から文字を載せるので、明るく単純な空間（淡いグラデーションや薄い街並み）にして要素を置かない。最下部 20% も帯を載せるので空けておく。")
    return "\n".join(p)

def _multipart(fields, files):
    b = uuid.uuid4().hex; body = io.BytesIO()
    for k, v in fields.items():
        body.write(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    for k, (fn, data, ct) in files:
        body.write(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{fn}\"\r\nContent-Type: {ct}\r\n\r\n".encode()); body.write(data); body.write(b"\r\n")
    body.write(f"--{b}--\r\n".encode())
    return body.getvalue(), f"multipart/form-data; boundary={b}"

def _call(prompt, refs, quality="medium", log=print):
    import urllib.request, urllib.error
    hdr = {"Authorization": "Bearer " + _key()}
    model = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1")
    if refs:
        log(f"  참고 썸네일 {len(refs)}장과 함께 생성 (images/edits)")
        files = [("image[]", (os.path.basename(f), open(f, "rb").read(), "image/png")) for f in refs]
        data, ct = _multipart({"model": model, "prompt": prompt + "\n参考画像はこのチャンネルの既存サムネイル。文字の太さ・色づかい・レイアウトの密度を同じ雰囲気にする（内容はコピーしない）。",
                               "size": "1536x1024", "quality": quality, "n": "1"}, files)
        req = urllib.request.Request("https://api.openai.com/v1/images/edits", data=data, headers={"Content-Type": ct, **hdr})
    else:
        req = urllib.request.Request("https://api.openai.com/v1/images/generations", data=json.dumps({"model": model, "prompt": prompt, "size": "1536x1024", "quality": quality, "n": 1}).encode(),
                                     headers={"Content-Type": "application/json", **hdr})
    try:
        with urllib.request.urlopen(req, timeout=300) as r: d = json.load(r)
    except urllib.error.HTTPError as e:
        try: detail = json.loads(e.read().decode("utf-8", "replace")).get("error", {}).get("message", "")[:300]
        except Exception: detail = e.reason
        raise RuntimeError(f"OpenAI HTTP {e.code}: {detail}")
    return base64.b64decode(d["data"][0]["b64_json"])

def _to_169(raw):
    from PIL import Image
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    th = round(im.width * 9 / 16)
    if im.height > th: im = im.crop((0, (im.height - th) // 2, im.width, (im.height - th) // 2 + th))
    return im.resize((W, H), Image.LANCZOS)

# ---------------- PIL 合成（ai_bg / plain） ----------------
def _text(d, xy, s, font, fill, strokes):
    """strokes = [(幅, 色), ...] 外側から順に"""
    x, y = xy
    for w, c in strokes: d.text((x, y), s, font=font, fill=c, stroke_width=w, stroke_fill=c)
    d.text((x, y), s, font=font, fill=fill)

def compose(im, cfg):
    """背景画像の上に 見出し（左）・バッジ（右上）・情報ボックス（下）を描く"""
    from PIL import ImageDraw, ImageFont
    d = ImageDraw.Draw(im, "RGBA")
    lines = [l for l in cfg.get("lines") or [] if l.strip()][:3]
    pts = [x for x in (cfg.get("points") or []) if x.strip()][:3]
    badge = (cfg.get("badge") or "").strip()
    bottom = 150 if pts else 40
    text_w = int(W * 0.62) - 50; area_h = H - bottom - 30
    # 行ごとに幅いっぱいまで大きくする（短い行＝キーワードほど大きく。参考サムネの「現実」「180点」のように）
    def fit(l, cap):
        sz = cap
        while sz > 48:
            f = ImageFont.truetype(GOTHIC, sz)
            if d.textlength(l, font=f) <= text_w: return sz, f
            sz -= 4
        return sz, ImageFont.truetype(GOTHIC, sz)
    cap = 170
    while True:
        fs = [fit(l, cap) for l in lines]
        if sum(int(sz * 1.12) for sz, _ in fs) <= area_h or cap <= 60: break
        cap -= 8
    total = sum(int(sz * 1.12) for sz, _ in fs); y = 30 + (area_h - total) // 2
    palette = [("#FFFFFF", "#0B1A3A", None), ("#FFE14D", "#0B1A3A", "#C0392B"), ("#E8352B", "#0B1A3A", "#FFFFFF")]
    for i, (l, (size, f)) in enumerate(zip(lines, fs)):
        fill, outer, inner = palette[i % 3]
        strokes = [(size // 7, outer)] + ([(size // 12, inner)] if inner else [])
        _text(d, (40 + size // 10, y + size // 10), l, f, "#000000", [(size // 7, "#000000")])          # 影
        _text(ImageDraw.Draw(im, "RGBA"), (40, y), l, f, fill, strokes); y += int(size * 1.12)
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

def _save(spec, im, out=None):
    out = out or os.path.join(_out(spec), "thumbnail.png")
    os.makedirs(os.path.dirname(out), exist_ok=True); im.save(out)
    hd = os.path.join(os.path.dirname(out), "thumb_hist"); os.makedirs(hd, exist_ok=True)      # 履歴（あとから選び直せる）
    im.save(os.path.join(hd, time.strftime("%Y%m%d_%H%M%S") + ".png"))
    return out

def make_ai(spec, cfg, log=print):
    mode = cfg.get("mode") or "ai"
    if not _key(): raise RuntimeError("OpenAI 키(.openai_api_key)가 없습니다")
    refs = references(spec) if cfg.get("use_refs", True) else []
    pr = prompt_for(spec, cfg, with_text=(mode == "ai"))
    log(f"썸네일 생성 ({mode}, {cfg.get('quality') or 'medium'}) …\n{pr}")
    raw = _call(pr, refs, cfg.get("quality") or "medium", log)
    im = _to_169(raw)
    if mode == "ai_bg": im = compose(im, cfg)
    return _save(spec, im)

if __name__ == "__main__":
    sp = json.load(open(sys.argv[1], encoding="utf-8"))
    if len(sys.argv) > 2 and sys.argv[2] == "--ai":
        print(make_ai(sp, sp.get("thumb") or {}))
    else:
        print(make(sp, sys.argv[2:], (sp.get("thumb") or {}).get("style", "navy")))
