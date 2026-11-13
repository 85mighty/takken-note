# -*- coding: utf-8 -*-
"""長い動画のスライド1枚から、宣伝用のショート (縦 1080×1920) を作る。
  python3 shorts.py specs/R8_menjo.json 4 [--hook "5問免除は誰が使える？"]
  過去の動画 (specs/_archive) にも使える。音声つきのスライドがなければ、その1枚だけ音声を作る。
画面: 上=フック（大きな文字）／中=スライド／字幕（大きめ）／下=「続きは本編で」
出力: out/<outdir>/shorts/<name>_s04.mp4 と .txt（タイトル・概要欄。本編のURLは videos.json から）
"""
import argparse, json, os, re, subprocess, sys

def subs_plain(t): return (t or "").replace("【", "").replace("】", "")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
SW, SH = 1080, 1920
TOP, SLIDE_Y = 400, 400            # フック帯の高さ・スライドの位置
NAVY = (26, 61, 124)

def spec_path(name):
    for d in ("specs", os.path.join("specs", "_archive")):
        p = os.path.join(HERE, d, name + ".json")
        if os.path.exists(p): return p
    return None

def _font(size, bold=True):
    import subs
    from PIL import ImageFont
    return ImageFont.truetype(subs.font_path("BIZ UDPゴシック Bold" if bold else "BIZ UDPゴシック Regular"), size, index=0)

def _wrap(d, text, fnt, maxw):
    """幅に収まるように折る。改行（\n）はそのまま行の区切りにする"""
    import subs
    lines = []
    for para in text.split("\n"):
        cur = ""
        for c in subs._split(para, 9) if len(para) > 9 else [para]:
            if d.textlength(cur + c, font=fnt) > maxw and cur: lines.append(cur); cur = c
            else: cur += c
        if cur: lines.append(cur)
    return lines

def render_narrow(G, title, sub, body, name="sh_narrow"):
    """縦動画用: スライドを幅 1080px のページで描き直す（表が折り返されて文字が大きくなる）。
    自由配置の要素(ov)があるときは座標が合わないので None（従来の 16:9 を使う）"""
    if "class='ov" in body: return None
    body = body.replace("class='two'", "class='two-narrow'")              # 縦では2列を上下に積む
    body = G.ILL_RE.sub("", body)                                           # 縦ではイラストを外して字幕の場所を空ける
    head = f"<h1>{G.E(title)}</h1>" if title else ""                      # 縦では小見出しは出さない
    avail = SH - TOP - 300 - 280                     # フック帯と下の帯の間から、字幕のぶん（約280px）を引く
    import vkit as V, subs
    oldW, oldst = G.W, V.SUB_STYLE; G.W = SW
    st = subs.load_style(V.SUB_STYLE)
    if st.get("slide_theme") == "kokuban": V.SUB_STYLE = dict(st, slide_theme="paper")   # 縦では黒板の枠が合わないので紙だけ
    try:
        best = None
        for sc in ((1.0, 0.9, 0.8, 0.7) if "class='huge" in body else (1.0, 1.2, 1.4, 0.9, 0.8, 0.7)):   # 大文字の場面はこれ以上大きくすると折り返す
            im, ch, png = G._render_once(head, body, name, sc)
            if ch <= avail and (best is None or ch > best[1]): best = (im, ch, png, sc)
            if best and best[1] >= avail * 0.75: break
        if best is None: return None
        im, ch, png, sc = best
    finally:
        G.W = oldW; V.SUB_STYLE = oldst
    im.crop((0, 0, SW, min(im.size[1], ch + 40))).save(png)
    return png

CHAR_H = 608                       # 話すキャラクター（16:9 → 1080×608）を下部に置くときの高さ

def background(slide_png, hook, out, long_label="", crop169=True, char_h=0):
    """char_h>0 なら、スライドは上部に収め（高さ上限）、下に char_h ぶんの空きを残す（あとで動画を重ねる）"""
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (SW, SH), "white"); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, SW, TOP], fill=NAVY)
    size = 92
    while True:
        f = _font(size); lines = _wrap(d, hook, f, SW - 120)
        if len(lines) <= 3 or size <= 56: break
        size -= 6
    lh = int(size * 1.3); y = (TOP - lh * len(lines)) // 2 + 10
    for l in lines:
        d.text(((SW - d.textlength(l, font=f)) / 2, y), l, font=f, fill="white", stroke_width=3, stroke_fill=(10, 25, 60)); y += lh
    sl = Image.open(slide_png).convert("RGB")
    from PIL import ImageOps
    if crop169: sl = sl.crop((0, 0, sl.size[0], min(sl.size[1], int(sl.size[0] * 9 / 16))))
    bb = ImageOps.invert(sl.convert("L")).point(lambda v: 255 if v > 40 else 0).getbbox()
    if bb:                                       # 余白を切って文字を大きく
        sl = sl.crop((max(0, bb[0] - 30), max(0, bb[1] - 30), min(sl.size[0], bb[2] + 30), min(sl.size[1], bb[3] + 30)))
    sl = sl.resize((SW, int(sl.size[1] * SW / sl.size[0])))
    if char_h:
        maxh = SH - 300 - char_h - SLIDE_Y - 20
        if sl.size[1] > maxh: sl = sl.resize((int(sl.size[0] * maxh / sl.size[1]), maxh))
        im.paste(sl, ((SW - sl.size[0]) // 2, SLIDE_Y))
        d.rectangle([0, SH - 300 - char_h, SW, SH - 300], fill=(236, 240, 247))     # キャラ動画の下地（動画が来るまでの色）
    else:
        im.paste(sl, (0, SLIDE_Y)); d.line([0, SLIDE_Y + sl.size[1], SW, SLIDE_Y + sl.size[1]], fill=(220, 220, 220), width=3)
    f2, f3 = _font(54), _font(38, False)
    d.rectangle([0, SH - 300, SW, SH], fill=(255, 243, 196))
    t = "続きは本編で ▶ 概要欄のリンクから"
    d.text(((SW - d.textlength(t, font=f2)) / 2, SH - 250), t, font=f2, fill=(26, 26, 26))
    if long_label:
        lab = long_label if len(long_label) <= 24 else long_label[:23] + "…"
        d.text(((SW - d.textlength(lab, font=f3)) / 2, SH - 160), lab, font=f3, fill=(90, 90, 90))
    im.save(out)
    return (SH - 300 - char_h) if char_h else SLIDE_Y + sl.size[1]

_TRANSITION = re.compile(r"^(こんにちは|まず|次に|つぎに|そして|さて|では|最後に|続いて|つづいて|ここで|それでは|今日は|きょうは|[0-9０-９一二三四五六七八九十]+\s*つ[めも目]|[①-⑳]|(第)?[0-9０-９一二三四五六七八九十]+に)")

def desc_line(speech):
    """ショートの概要欄 1 行: 読み上げから「中身のある最初の文」を選ぶ。
    「2つめ、実務です。」「まず結論から。」のような前置き・つなぎの文は飛ばし、【】の強調がある文があればそれを優先する。"""
    sents = [x.strip() for x in re.split(r"(?<=[。！？])", speech or "") if x.strip()]
    good = [x for x in sents if len(subs_plain(x)) >= 12 and not _TRANSITION.match(x)]
    pick = next((x for x in good if "【" in x), None) or (good[0] if good else (sents[0] if sents else ""))
    return subs_plain(pick).strip()

def thumb_prompt(spec, s, hook, desc):
    """ChatGPT に貼るショート用サムネイルのプロンプト（docs/THUMB_STYLE.md・docs/SHORTS_RULES.md の形）。サムネイルは自動では作らない"""
    src = desc + " " + subs_plain(s.get("speech") or "")
    src = re.sub(r"[0-9０-９]+\s*点満点", "", src)                                  # 「100点満点」は数字に数えない
    nums = []
    for n in re.findall(r"[0-9０-９][0-9０-９,，.．]*\s*(?:%|％|点|万円|円|人|時間|か月)", src):
        if n not in nums: nums.append(n)
    big = next((n for n in nums if n.endswith(("%", "％"))), nums[0] if nums else "")   # 割合 → それ以外の順
    label = spec.get("short_badge") or (spec.get("label") or "").replace("【ショート】", "").split("｜")[0].split(" ")[0][:14]
    lines = [x for x in hook.split("\n") if x.strip()]
    pts = []
    for n in nums:
        if n not in pts and n != big: pts.append(n)
        if len(pts) >= 3: break
    return "\n".join([
        "日本の資格試験を扱うYouTubeチャンネルの「ショート動画」用サムネイルを1枚作ってください。縦長9:16（1080×1920）。", "",
        f"【テーマ】\n{desc}", "",
        "【画像内に入れる文字：この表記を一字一句そのまま。ほかの文字・数字は入れない】",
        f"最上部の赤い帯（白文字）：{label}",
        f"その下（白に太い黒フチ）：{next((x for x in lines if x.strip() != label), '')}",
        (f"画面中央・いちばん大きく（黄色に太い黒フチと赤い縁取り、強い影）：{big}" if big else f"画面中央・いちばん大きく（黄色に太い黒フチ）：{lines[-1] if lines else ''}"),
        (f"その下の赤い吹き出し（白文字）：{lines[-1]}" if big and len(lines) > 1 else ""),
        ("小さな情報カード（白地・紺文字・左にチェックマーク）：" + "／".join(pts) if pts else ""),
        "", "【ビジュアルスタイル】",
        "日本の人気資格試験解説YouTubeのような、赤・黄色・濃紺・白・黒の高コントラストなデザイン。文字は極太の日本語ゴシック体。太い黒フチ、細い白フチ、強いドロップシャドウ。",
        "いちばん大きな文字はスマホの小さな画面でも一瞬で読める、画面幅の8割ほどの大きさ。黄色いブラシストローク、集中線、光のアクセントを適度に。", "",
        "【人物・背景】\n中央より下に、テーマに合う表情（驚き・喜び・考え込む）の日本人（写真のようにリアルな上半身）。背景はテーマに関係する場所を少しぼかして。", "",
        "【配置】\n重要な文字は画面の中央寄り。左右それぞれ6%と上下8%には文字を置かない（ショートの画面UIに隠れないように）。", "",
        "【禁止事項】\n誤字、文字化け、指定していない文字・数字、英語、実在企業のロゴ、透かしは入れない。数字を変えたり追加したりしない。"])

def make(path, i, hook=None, log=print, character=None):
    """character=True: Hedra で話すキャラクターを下部に重ねる（None なら spec の short_character に従う）"""
    import build_spec, registry, vkit as V
    spec = json.load(open(path, encoding="utf-8"))
    if character is None: character = bool(spec.get("short_character"))
    G = build_spec.setup(spec)
    s = spec["slides"][i - 1]
    key = G.slide_key(s.get("title", ""), s.get("sub", ""), s["_body"], s.get("speech", ""))
    seg, png = os.path.join(G.OUT, f"c_{key}.mp4"), os.path.join(G.OUT, f"c_{key}.png")
    if not os.path.exists(seg) and os.path.exists(os.path.join(G.OUT, f"s{i:02d}.mp4")):   # 前回書き出した本編の同じ番号を使う
        seg = os.path.join(G.OUT, f"s{i:02d}.mp4")
        if os.path.exists(os.path.join(G.OUT, f"s{i:02d}.png")): png = os.path.join(G.OUT, f"s{i:02d}.png")
    if not os.path.exists(seg):
        log(f"슬라이드 {i} 의 음성 영상이 없어서 만듭니다…")
        G.build(only=i, name=spec["name"])
    if not os.path.exists(png):
        png, _h = G.render(s["_body"], s.get("title", ""), s.get("sub", ""), f"sh{i:02d}")
    odir = os.path.join(G.OUT, "shorts"); os.makedirs(odir, exist_ok=True)
    base = os.path.join(odir, f"{spec['name']}_s{i:02d}")
    hook = hook or s.get("short_hook") or (s.get("title") or spec.get("label", "")).replace("｜", "\n").split("\n")[0]
    reg = registry.load(); v = registry.get(reg, spec.get("short_target") or spec["name"]) or {}   # 本編 = short_target の動画（なければ自分）
    if spec.get("short_target") and not v: log(f"※ 本編 {spec['short_target']} が URL 대장에 없습니다 → 링크 없이 만듭니다")
    long_title = v.get("yt_title") or (spec.get("youtube") or {}).get("title") or v.get("label") or spec.get("label", "")
    narrow = render_narrow(G, s.get("title", ""), s.get("sub", ""), s["_body"])       # 縦向きに描き直せれば文字が大きい方を使う
    import character as CH
    use_char = bool(character and CH.available() and CH.mascot_path())
    if character and not use_char: log("  ※ 캐릭터 생략: Hedra 키(.hedra_api_key) 또는 마스코트(mascot/default.png)가 없습니다")
    bottom = background(narrow or png, hook, base + "_bg.png", long_title, crop169=not narrow, char_h=CHAR_H if use_char else 0)
    # 音声と字幕の時刻は本編と同じ TTS から。cached_tts は同じ読み上げ文なら本編で作った音声と「文ごとの実測時刻」をそのまま返す
    # （以前は文字数で按分していたため、話す速さが文ごとに違うと字幕が遅れた）
    sents = V.split_sentences(s.get("speech", "")) or [""]
    m4a = base + ".mp3"
    try:
        tp = G.cached_tts(V.ssml_sentences(sents), m4a)
        total = V.dur(m4a) + 1.5                                                      # 本編と同じく末尾に 1.5 秒の余白
        log(f"  자막 시각: TTS 실측 ({len(sents)}문장)")
    except Exception as e:                                                            # TTS が使えないときだけ従来の按分
        log(f"  TTS 시각을 못 얻어 글자 수로 배분합니다 ({str(e)[:80]})")
        m4a = base + ".m4a"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", seg, "-vn", "-c:a", "aac", "-b:a", "128k", m4a], check=True)
        total = V.dur(m4a)
        lens = [max(1, len(x)) for x in sents]; span = max(1.0, total - 1.5); t, tp = 0.4, {}
        for k, n in enumerate(lens): tp[f"s{k}"] = t; t += span * n / sum(lens)
    layers = []
    if use_char:                                                                       # 話すキャラクター（失敗したら通常のショート）
        try:
            cmp4 = base + "_char.mp4"
            CH.talk(CH.mascot_path(), m4a, cmp4, aspect="16:9", resolution=spec.get("short_character_res") or "540p", log=log)
            layers = [{"type": "video", "file": cmp4, "x": 0, "y": SH - 300 - CHAR_H, "w": SW, "h": CHAR_H, "t": 0}]
        except Exception as e:
            log(f"  ✗ 캐릭터 생성 실패 → 캐릭터 없이 만듭니다: {str(e)[:200]}")
            use_char = False; bottom = background(narrow or png, hook, base + "_bg.png", long_title, crop169=not narrow)
    import subs
    st = dict(subs.load_style(spec.get("sub_style")))
    st.update(size=max(62, min(int(st["size"] * 0.85), 88)), max_chars=12, max_lines=1)   # 縦は1行・やや小さめ（スライドと下の帯の間に収める）
    if use_char: st["bottom"] = 300 + 28                                                 # キャラ動画の下端に字幕を重ねる
    else: st["bottom"] = SH - ((bottom + SH - 300) // 2) - subs.band_height(st) // 2      # スライドと下の帯の間の真ん中に字幕
    old = V.SUB_STYLE; V.SUB_STYLE = st
    try:
        V.encode_subtitled(base + "_bg.png", m4a, "0", total, sents, tp, base + ".mp4", odir, os.path.basename(base), width=SW, height=SH, layers=layers)
    finally:
        V.SUB_STYLE = old
    url = v.get("url") or ("" if spec.get("short_target") else (spec.get("youtube") or {}).get("url")) or ""
    title = f"{hook.replace(chr(10), ' ')} {spec.get('short_tags') or '#宅建 #宅建士'}"   # ショートの題名: フック + タグ2つだけ（宅建以外は spec.short_tags）
    desc = (s.get("short_desc") or desc_line(s.get("speech") or "") or hook.replace(chr(10), " "))[:70]   # 概要欄は1行だけ（リンクなし）
    pin = f"詳しくは本編で▶ {url}" if url else "（本編の URL を登録すると、ここに固定コメント用の一文が入ります）"
    tp = thumb_prompt(spec, s, hook, desc)
    open(base + ".txt", "w", encoding="utf-8").write(f"【タイトル】\n{title}\n\n【概要欄】\n{desc}\n\n【固定コメント】\n{pin}\n\n【ChatGPT サムネイル用プロンプト（9:16）】\n{tp}\n")
    for f in (m4a, base + ".m4a", base + "_bg.png"):
        if os.path.exists(f): os.remove(f)
    log(f"쇼츠 완성: {base}.mp4  {total:.0f}초" + (" (60초를 넘습니다. 쇼츠는 3분까지 올릴 수 있습니다)" if total > 60 else ""))
    return {"video": base + ".mp4", "title": title, "description": desc, "dur": round(total, 1), "url_missing": not url}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("spec"); ap.add_argument("slide", type=int); ap.add_argument("--hook"); ap.add_argument("--character", action="store_true", help="Hedra の話すキャラクターを重ねる"); ap.add_argument("--no-character", action="store_true")
    a = ap.parse_args()
    p = a.spec if os.path.exists(a.spec) else spec_path(a.spec)
    make(p, a.slide, a.hook, log=lambda m: print(m, flush=True), character=(True if a.character else (False if a.no_character else None)))
