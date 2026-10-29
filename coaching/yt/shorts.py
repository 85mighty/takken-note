# -*- coding: utf-8 -*-
"""長い動画のスライド1枚から、宣伝用のショート (縦 1080×1920) を作る。
  python3 shorts.py specs/R8_menjo.json 4 [--hook "5問免除は誰が使える？"]
  過去の動画 (specs/_archive) にも使える。音声つきのスライドがなければ、その1枚だけ音声を作る。
画面: 上=フック（大きな文字）／中=スライド／字幕（大きめ）／下=「続きは本編で」
出力: out/<outdir>/shorts/<name>_s04.mp4 と .txt（タイトル・概要欄。本編のURLは videos.json から）
"""
import argparse, json, os, re, subprocess, sys
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
    import subs
    lines, cur = [], ""
    for c in subs._split(text, 9) if len(text) > 9 else [text]:
        if d.textlength(cur + c, font=fnt) > maxw and cur: lines.append(cur); cur = c
        else: cur += c
    if cur: lines.append(cur)
    return lines

def background(slide_png, hook, out, long_label=""):
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
    sl = sl.crop((0, 0, sl.size[0], min(sl.size[1], int(sl.size[0] * 9 / 16))))
    bb = ImageOps.invert(sl.convert("L")).point(lambda v: 255 if v > 40 else 0).getbbox()
    if bb:                                       # 余白を切って文字を大きく
        sl = sl.crop((max(0, bb[0] - 30), max(0, bb[1] - 30), min(sl.size[0], bb[2] + 30), min(sl.size[1], bb[3] + 30)))
    sl = sl.resize((SW, int(sl.size[1] * SW / sl.size[0])))
    im.paste(sl, (0, SLIDE_Y)); d.line([0, SLIDE_Y + sl.size[1], SW, SLIDE_Y + sl.size[1]], fill=(220, 220, 220), width=3)
    f2, f3 = _font(54), _font(38, False)
    d.rectangle([0, SH - 300, SW, SH], fill=(255, 243, 196))
    t = "続きは本編で ▶ 概要欄のリンクから"
    d.text(((SW - d.textlength(t, font=f2)) / 2, SH - 250), t, font=f2, fill=(26, 26, 26))
    if long_label:
        lab = long_label if len(long_label) <= 24 else long_label[:23] + "…"
        d.text(((SW - d.textlength(lab, font=f3)) / 2, SH - 160), lab, font=f3, fill=(90, 90, 90))
    im.save(out)
    return SLIDE_Y + sl.size[1]

def make(path, i, hook=None, log=print):
    import build_spec, registry, vkit as V
    spec = json.load(open(path, encoding="utf-8"))
    G = build_spec.setup(spec)
    s = spec["slides"][i - 1]
    key = G.slide_key(s.get("title", ""), s.get("sub", ""), s["_body"], s.get("speech", ""))
    seg, png = os.path.join(G.OUT, f"c_{key}.mp4"), os.path.join(G.OUT, f"c_{key}.png")
    if not os.path.exists(seg) and os.path.exists(os.path.join(G.OUT, f"s{i:02d}.mp4")):   # 前回書き出した本編の同じ番号を使う
        seg = os.path.join(G.OUT, f"s{i:02d}.mp4")
        if os.path.exists(os.path.join(G.OUT, f"s{i:02d}.png")): png = os.path.join(G.OUT, f"s{i:02d}.png")
    if not os.path.exists(seg):
        log(f"スライド{i}の音声つき映像がないので作ります…")
        G.build(only=i, name=spec["name"])
    if not os.path.exists(png):
        png, _h = G.render(s["_body"], s.get("title", ""), s.get("sub", ""), f"sh{i:02d}")
    odir = os.path.join(G.OUT, "shorts"); os.makedirs(odir, exist_ok=True)
    base = os.path.join(odir, f"{spec['name']}_s{i:02d}")
    hook = hook or s.get("short_hook") or (s.get("title") or spec.get("label", "")).replace("｜", "\n").split("\n")[0]
    reg = registry.load(); v = registry.get(reg, spec["name"]) or {}
    long_title = v.get("yt_title") or (spec.get("youtube") or {}).get("title") or v.get("label") or spec.get("label", "")
    bottom = background(png, hook, base + "_bg.png", long_title)
    # 音声は本編のスライドから。字幕の時間は文字数で配分
    m4a = base + ".m4a"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", seg, "-vn", "-c:a", "aac", "-b:a", "128k", m4a], check=True)
    total = V.dur(m4a)
    sents = V.split_sentences(s.get("speech", "")) or [""]
    lens = [max(1, len(x)) for x in sents]; span = max(1.0, total - 1.5); t, tp = 0.4, {}
    for k, n in enumerate(lens): tp[f"s{k}"] = t; t += span * n / sum(lens)
    import subs
    st = dict(subs.load_style(spec.get("sub_style")))
    st.update(size=int(st["size"] * 1.25), max_chars=13, max_lines=2)
    st["bottom"] = SH - ((bottom + SH - 300) // 2) - subs.band_height(st) // 2   # スライドと下の帯の間の真ん中に字幕
    old = V.SUB_STYLE; V.SUB_STYLE = st
    try:
        V.encode_subtitled(base + "_bg.png", m4a, "0", total, sents, tp, base + ".mp4", odir, os.path.basename(base), width=SW, height=SH)
    finally:
        V.SUB_STYLE = old
    url = v.get("url") or (spec.get("youtube") or {}).get("url") or ""
    title = f"{hook.replace(chr(10), ' ')}【宅建】 #shorts"
    desc = (f"本編はこちら ▶ {url or '（本編のURLが未登録です）'}\n{long_title}\n\n"
            f"{(s.get('speech') or '')[:120]}…\n\n#宅建 #宅建士 #宅建試験 #shorts")
    open(base + ".txt", "w", encoding="utf-8").write(f"【タイトル】\n{title}\n\n【概要欄】\n{desc}\n")
    for f in (m4a, base + "_bg.png"):
        if os.path.exists(f): os.remove(f)
    log(f"ショート完成: {base}.mp4  {total:.0f}秒" + ("（60秒を超えています。ショートは3分まで投稿できます）" if total > 60 else ""))
    return {"video": base + ".mp4", "title": title, "description": desc, "dur": round(total, 1), "url_missing": not url}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("spec"); ap.add_argument("slide", type=int); ap.add_argument("--hook")
    a = ap.parse_args()
    p = a.spec if os.path.exists(a.spec) else spec_path(a.spec)
    make(p, a.slide, a.hook, log=lambda m: print(m, flush=True))
