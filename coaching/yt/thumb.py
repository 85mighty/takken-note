# -*- coding: utf-8 -*-
"""YouTube サムネイル (1280×720)。左に大きな文字（白・黄色を交互）、右に表紙のイラスト（あれば）。
  python3 thumb.py specs/R8_xxx.json "1行目" "2行目" ["3行目"]  → out/<outdir>/thumbnail.png
spec["thumb"] = {"lines": [...], "style": "navy"|"red"|"white"} に保存して使う。
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
FONT = os.path.join(HERE, "fonts", "MPLUSRounded1c-ExtraBold.ttf")
W, H = 1280, 720
STYLES = {  # (上の色, 下の色, 文字1, 文字2, フチ)
    "navy":  ((16, 38, 82), (40, 96, 190), "#FFFFFF", "#FFE14D", "#0B1A3A"),
    "red":   ((120, 20, 20), (210, 50, 40), "#FFFFFF", "#FFE14D", "#3A0808"),
    "white": ((250, 247, 238), (235, 228, 210), "#1A3D7C", "#C0392B", "#FFFFFF"),
}

def make(spec, lines, style="navy", out=None):
    from PIL import Image, ImageDraw, ImageFont
    import illust, vkit as V
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
    out = out or os.path.join(V.OUT, spec["outdir"], "thumbnail.png")
    os.makedirs(os.path.dirname(out), exist_ok=True); im.save(out); return out

if __name__ == "__main__":
    sp = json.load(open(sys.argv[1], encoding="utf-8")); print(make(sp, sys.argv[2:]))
