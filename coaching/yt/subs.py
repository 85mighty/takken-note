# -*- coding: utf-8 -*-
"""字幕: スタイル（フォント・太さ・フチ・ボックス・位置）と、日本語の自然な区切り（1行◯字まで）
  スタイルは sub_style.json（チャンネル共通）。spec の "sub_style" で動画ごとに上書きできる。
"""
import json, os, re
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts")
STYLE_PATH = os.path.join(HERE, "sub_style.json")

FONT_CHOICES = {
    "BIZ UDPゴシック Bold": "BIZUDPGothic-Bold.ttf",
    "BIZ UDPゴシック Regular": "BIZUDPGothic-Regular.ttf",
    "Zen丸ゴシック Bold": "ZenMaruGothic-Bold.ttf",
    "Zen丸ゴシック Medium": "ZenMaruGothic-Medium.ttf",
    "M PLUS Rounded ExtraBold": "MPLUSRounded1c-ExtraBold.ttf",
    "M PLUS Rounded Medium": "MPLUSRounded1c-Medium.ttf",
    "Zen角ゴシックNew Bold": "ZenKakuGothicNew-Bold.ttf",
    "Zen角ゴシックNew Medium": "ZenKakuGothicNew-Medium.ttf",
    "Noto Sans JP Bold": "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "Noto Sans JP Regular": "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
}

PRESETS = {
    "box":    {"label": "半透明ボックス（読みやすさ重視）", "font": "BIZ UDPゴシック Bold", "size": 50, "color": "#FFFFFF",
               "stroke": 0, "stroke_color": "#000000", "box": True, "box_color": "#000000", "box_alpha": 0.62, "box_radius": 12,
               "shadow": False, "max_chars": 20, "max_lines": 1, "bottom": 56},
    "tv":     {"label": "テレビ風（白文字・細めの黒フチ）", "font": "Zen角ゴシックNew Bold", "size": 54, "color": "#FFFFFF",
               "stroke": 4, "stroke_color": "#111111", "box": False, "box_color": "#000000", "box_alpha": 0.0, "box_radius": 0,
               "shadow": True, "max_chars": 18, "max_lines": 1, "bottom": 60},
    "maru":   {"label": "丸ゴシック（やわらかい）", "font": "Zen丸ゴシック Bold", "size": 54, "color": "#FFFFFF",
               "stroke": 5, "stroke_color": "#0F1B33", "box": False, "box_color": "#000000", "box_alpha": 0.0, "box_radius": 0,
               "shadow": False, "max_chars": 18, "max_lines": 1, "bottom": 60},
    "yellow": {"label": "黄色文字（バラエティ寄り）", "font": "M PLUS Rounded ExtraBold", "size": 54, "color": "#FFE14D",
               "stroke": 6, "stroke_color": "#222222", "box": False, "box_color": "#000000", "box_alpha": 0.0, "box_radius": 0,
               "shadow": True, "max_chars": 18, "max_lines": 1, "bottom": 60},
    "plain":  {"label": "シンプル（黒文字・白ボックス）", "font": "BIZ UDPゴシック Bold", "size": 48, "color": "#111111",
               "stroke": 0, "stroke_color": "#FFFFFF", "box": True, "box_color": "#FFFFFF", "box_alpha": 0.88, "box_radius": 10,
               "shadow": False, "max_chars": 20, "max_lines": 1, "bottom": 56},
}
# スライド本文の書体（TTF だと書き出しが速い。Noto は TTC なので1枚6秒ほどかかる）
SLIDE_FONTS = {
    "Zen角ゴシックNew": ("ZenKakuGothicNew-Medium.ttf", "ZenKakuGothicNew-Bold.ttf"),
    "BIZ UDPゴシック": ("BIZUDPGothic-Regular.ttf", "BIZUDPGothic-Bold.ttf"),
    "Zen丸ゴシック": ("ZenMaruGothic-Medium.ttf", "ZenMaruGothic-Bold.ttf"),
    "M PLUS Rounded": ("MPLUSRounded1c-Medium.ttf", "MPLUSRounded1c-ExtraBold.ttf"),
    "Noto Sans JP（遅い）": None,
}
DEFAULT = dict(PRESETS["box"], preset="box", slide_font="Zen角ゴシックNew")

def slide_font_css(name):
    """スライド用 CSS の先頭に付ける @font-face と、使う font-family 名"""
    pair = SLIDE_FONTS.get(name)
    if not pair: return "", '"Noto Sans CJK JP"'
    reg, bold = (os.path.join(FONTS, f) for f in pair)
    css = (f"@font-face{{font-family:'SlideFont';font-weight:normal;src:url('file://{reg}')}}"
           f"@font-face{{font-family:'SlideFont';font-weight:bold;src:url('file://{bold}')}}")
    return css, "'SlideFont'"

def signature(st):
    return json.dumps(st, sort_keys=True, ensure_ascii=False)

def load_style(override=None):
    st = dict(DEFAULT)
    if os.path.exists(STYLE_PATH):
        try: st.update(json.load(open(STYLE_PATH, encoding="utf-8")))
        except Exception: pass
    if override: st.update(override)
    return st

def save_style(st):
    clean = {k: st[k] for k in DEFAULT if k in st and k != "label"}
    clean["preset"] = st.get("preset", "custom")
    with open(STYLE_PATH, "w", encoding="utf-8") as f: json.dump(clean, f, ensure_ascii=False, indent=1)

def font_path(name):
    f = FONT_CHOICES.get(name, name)
    return f if os.path.isabs(f) else os.path.join(FONTS, f)

# ---------------- 区切り ----------------
KANJI = r"一-鿿々"
KATA = r"゠-ヿｦ-ﾟ"
HIRA = r"぀-ゟ"
PARTICLES = ("から", "まで", "より", "ので", "けど", "ても", "では", "には", "とは", "って", "たら", "なら", "ため",
             "は", "が", "を", "に", "で", "と", "も", "へ", "の", "や")

def _kind(c):
    if re.match(f"[{KANJI}]", c): return "K"
    if re.match(f"[{KATA}]", c): return "T"
    if re.match(f"[{HIRA}]", c): return "H"
    if re.match(r"[0-9０-９.,，．％%]", c): return "N"
    return "O"

def _break_scores(s):
    """各位置 i（s[:i] と s[i:] の間）で区切る良さ。0 は区切らない"""
    sc = [0] * (len(s) + 1)
    for i in range(1, len(s)):
        a, b = s[i - 1], s[i]
        ka, kb = _kind(a), _kind(b)
        if a in "、，,": sc[i] = 10
        elif b in "（「『【(": sc[i] = 6
        elif a in "）」』】)": sc[i] = 6
        elif ka == "N" and kb == "N": sc[i] = 0               # 数字の途中では切らない
        elif kb in "KT" and ka == "H":                         # ひらがな → 漢字/カタカナ（語の切れ目になりやすい）
            sc[i] = 4
            for p in PARTICLES:                                 # 直前が助詞なら、さらに良い
                if s[:i].endswith(p) and i - len(p) >= 1 and _kind(s[i - len(p) - 1]) in "KTN": sc[i] = 7; break
        elif ka in "KT" and kb == "H": sc[i] = 0
    return sc

def _split(s, maxc):
    if len(s) <= maxc: return [s]
    sc = _break_scores(s)
    lo, hi = max(1, len(s) - maxc), min(len(s) - 1, maxc)       # 左右とも maxc 以下になる範囲
    best, bi = -1, None
    for i in range(1, len(s)):
        if sc[i] <= 0: continue
        fits = lo <= i <= hi
        bal = 1 - abs(i - len(s) / 2) / len(s)                  # 真ん中に近いほど良い
        v = sc[i] * 2 + bal * 3 + (6 if fits else 0) - (0 if i <= maxc else (i - maxc))
        if v > best: best, bi = v, i
    if bi is None: bi = maxc                                    # 区切れる所がなければ文字数で切る
    return _split(s[:bi], maxc) + _split(s[bi:], maxc)

def chunk(sentence, maxc=20):
    """1文 → 画面に出す単位のリスト。句点・読点は表示しない（読点は区切りに使う）"""
    s = sentence.strip().rstrip("。．.")
    parts = [p for p in _split(s, maxc) if p.strip("、 ")]
    return [p.strip().strip("、").replace("、", "　") for p in parts]

def timed_chunks(sents, spans, maxc=20):
    """[(text, t0, t1)]。文の時間を、区切った各部分の文字数で配分"""
    out = []
    for s, (t0, t1) in zip(sents, spans):
        cs = chunk(s, maxc) or [s]
        n = sum(max(2, len(c)) for c in cs); t = t0
        for c in cs:
            d = (t1 - t0) * max(2, len(c)) / n
            out.append((c, t, t + d)); t += d
    return out

# ---------------- 描画 ----------------
def _rgba(hexc, a=1.0):
    h = hexc.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(255 * a))

def band_height(st):
    lines = max(1, int(st.get("max_lines", 1)))
    return int(st["size"] * 1.45 * lines + st["size"] * 0.9 + 2 * st.get("stroke", 0))

def render(text, path, width, st):
    """字幕1枚 (透明PNG)。高さ = band_height(st)"""
    H = band_height(st)
    fnt = ImageFont.truetype(font_path(st["font"]), int(st["size"]), index=0)
    lines = [text]
    if int(st.get("max_lines", 1)) >= 2 and fnt.getlength(text) > width * 0.86:
        cs = _split(text, max(4, len(text) // 2 + 1)); lines = ["".join(cs[: len(cs) // 2 or 1]), "".join(cs[len(cs) // 2 or 1:])]
    size = int(st["size"])
    while size > 24 and max(fnt.getlength(l) for l in lines) > width * 0.9:   # はみ出すときだけ縮める
        size -= 2; fnt = ImageFont.truetype(font_path(st["font"]), size, index=0)
    im = Image.new("RGBA", (width, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    lh = int(size * 1.45); total = lh * len(lines); y0 = (H - total) // 2
    sw = int(st.get("stroke", 0))
    if st.get("box"):
        tw = max(fnt.getlength(l) for l in lines); padx, pady = int(size * 0.55), int(size * 0.22)
        x0 = (width - tw) / 2 - padx; y_top = y0 - pady + int(size * 0.08)
        d.rounded_rectangle([x0, y_top, x0 + tw + 2 * padx, y_top + total + 2 * pady - int(size * 0.18)],
                            radius=int(st.get("box_radius", 10)), fill=_rgba(st.get("box_color", "#000000"), float(st.get("box_alpha", 0.6))))
    y = y0
    for l in lines:
        x = (width - fnt.getlength(l)) / 2
        if st.get("shadow"):
            d.text((x + 3, y + 4), l, font=fnt, fill=(0, 0, 0, 120), stroke_width=sw, stroke_fill=(0, 0, 0, 120))
        d.text((x, y), l, font=fnt, fill=_rgba(st.get("color", "#FFFFFF")), stroke_width=sw, stroke_fill=_rgba(st.get("stroke_color", "#000000")))
        y += lh
    im.save(path)
    return path

def sample(path, st, bg=None, width=1920, height=1080, text="合格発表を待っている人も、来年受けようか迷っている人も、気になるところだと思います。"):
    """スタイル確認用の画像（背景のスライドに字幕を重ねる）。区切りの例も3つ並べる"""
    base = Image.open(bg).convert("RGBA").crop((0, 0, width, height)) if bg and os.path.exists(bg) else Image.new("RGBA", (width, height), (245, 246, 248, 255))
    cs = chunk(text, int(st.get("max_chars", 20)))
    tmp = path + ".sub.png"; render(cs[0], tmp, width, st)
    sub = Image.open(tmp); base.alpha_composite(sub, (0, height - int(st.get("bottom", 56)) - sub.size[1]))
    d = ImageDraw.Draw(base); f = ImageFont.truetype(font_path("Noto Sans JP Regular"), 26, index=0)
    d.text((40, 30), "区切り: " + " ／ ".join(cs), font=f, fill=(60, 60, 60, 255))
    base.convert("RGB").save(path); os.remove(tmp)
    return path
