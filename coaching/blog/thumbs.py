# -*- coding: utf-8 -*-
"""ブログ記事のアイキャッチ（一覧のサムネイル）。
  動画がある記事 … その YouTube 動画のサムネイルをそのまま使う
  動画がない記事 … 紺のグラデーションに大きな文字（白・黄色を交互）の画像を作る
"""
import os, re, tempfile, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
FONT = os.path.join(ROOT, "coaching", "yt", "fonts", "MPLUSRounded1c-ExtraBold.ttf")
W, H = 1280, 720

def youtube_id(url):
    m = re.search(r"(?:youtu\.be/|v=|shorts/)([A-Za-z0-9_-]{11})", url or "")
    return m.group(1) if m else None

def youtube_thumb(url):
    """YouTube のサムネイルを一時ファイルに保存してパスを返す（取れなければ None）"""
    vid = youtube_id(url)
    if not vid: return None
    out = os.path.join(tempfile.gettempdir(), f"yt_{vid}.jpg")
    for q in ("maxresdefault", "sddefault", "hqdefault"):
        try:
            with urllib.request.urlopen(f"https://i.ytimg.com/vi/{vid}/{q}.jpg", timeout=30) as r:
                data = r.read()
            if len(data) > 5000:
                open(out, "wb").write(data); return out
        except Exception:
            continue
    return None

def text_thumb(lines, name):
    """文字だけのサムネイル。lines は2〜3行（短いほど大きく）"""
    from PIL import Image, ImageDraw, ImageFont
    im = Image.new("RGB", (W, H)); d = ImageDraw.Draw(im)
    top, bot = (16, 38, 82), (40, 96, 190)
    for y in range(H):
        k = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * k) for i in range(3)))
    lines = [l for l in lines if l][:3]
    size = 150
    while size > 60:
        f = ImageFont.truetype(FONT, size)
        if max(d.textlength(l, font=f) for l in lines) <= W - 120 and size * 1.25 * len(lines) <= H - 100: break
        size -= 6
    lh = int(size * 1.25); y = (H - lh * len(lines)) // 2 - int(size * 0.08)
    for i, l in enumerate(lines):
        x = (W - d.textlength(l, font=f)) / 2
        d.text((x, y), l, font=f, fill="#FFFFFF" if i % 2 == 0 else "#FFE14D", stroke_width=max(4, size // 18), stroke_fill="#0B1A3A")
        y += lh
    out = os.path.join(tempfile.gettempdir(), f"thumb_{name}.png")
    im.save(out); return out
